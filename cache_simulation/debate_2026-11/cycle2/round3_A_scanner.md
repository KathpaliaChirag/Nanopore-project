# round 3, agent A: make the minimizer scanner faster

sources read: round2_RESULT_oracle_ceiling.md, data/p32_summary.txt, luna kraken2-src-s19/src/mmscanner.{h,cc} and classify.cc lines 780-900 (read-only), plan_paper/explanations/06_S11.md, next_steps_plan E3. literature from web search. tags: [measured] from repo files, [read] from source, [lit] from papers, [guess] my reasoning.

## 1. what NextMinimizer does per base in this code [read]

parameters for the standard db: k=35, l=31, so the window holds k-l+1 = 5 l-mers. the toggle mask is xored in, and a spaced-seed mask is anded in (the standard build uses 7 spaces, so spaced_seed_mask_ is nonzero; any rewrite must keep that and-step).

classify.cc calls LoadSequence once per read (or per frame), then fill() calls NextMinimizer in a loop. one call consumes exactly one new base and returns one value per base (the final `break` fires whenever str_pos_ >= k, so the "changed_minimizer" loop almost never loops twice). the dedupe of repeated minimizers happens later in ClassifySequence via last_minimizer, not in the scanner. so the scanner does full work for every one of the 6,036 Mbp [measured, next_steps_plan line 114], and about 2 of 3 outputs are the same minimizer as the previous base [guess, density ~1/3].

per call, in order:
1. entry check str_pos_ >= finish_, then compute bits_per_char and ambig_code (cheap, but dna_ is a runtime member, not a constant).
2. char loading loop: lookup_table_[byte], compare with 0xFF (never true for clean reads), shift lmer_ and last_ambig_, or in the code, update rolling rc_lmer_ (S17), two mask ands. branches here are all well predicted.
3. canonical = min(lmer_, rc_lmer_): one compare, probably cmov.
4. and spaced mask, xor toggle.
5. monotonic queue: `while back.candidate > cand: pop_back` (loop count is 0 to 4, data dependent), `if queue empty` branch, push (two stores, S18), `if front.pos < queue_pos_ - k + l` expiry branch, `if queue_pos_ == k-l` branch, increment.
6. read front().candidate, xor toggle, store last_minimizer_, return pointer. then fill() calls is_ambiguous() (two compares), MurmurHash3 and PrefetchIndex.

cost breakdown [measured + guess]:
- perf annotate of NextMinimizer is flat, top instruction 3.9%. prologue and epilogue (push, sub, ret) are about 9% of the function's samples [measured, ann_next.txt]. it is a separate symbol, so it is not inlined into fill().
- rough per-base time: 38.6% of cpu at 8GB, wall 7.5 s, if 32 threads were fully busy that is about 93 cpu-seconds over 6.04e9 bases, about 15 ns, about 40 cycles per base [guess, upper bound: includes db-load cpu and SMT sharing]. even at half that, 20 cycles per base is 10 times slower than the SIMD literature (below).
- a flat profile with no hot instruction plus the 3-way data dependent pop loop and the front/expiry branches points at branch misprediction as the main hidden cost: the pop count and the expiry are close to random for random-looking hashes, so I expect about 1 mispredict per base (15 to 20 cycles) [guess, not measured; perf stat -e branch-misses on the S19 binary would confirm for free]. S18 already removed the store-forwarding stall, which is why what is left looks flat.

how stock Kraken2 does it: same algorithm (Wood, Lu, Langmead), std::deque queue, 3-stage bit reversal for revcomp. S17 and S18 here already replaced those. what stock and S19 both keep is the one-base-per-call structure and the branchy deque.

## 2. literature

- SimdMinimizers (Groot Koerkamp and Martayan, SEA 2025, simd-minimizers Rust crate): splits the bit-packed sequence into 8 chunks processed in the 8 lanes of an AVX2 (or NEON) register, ntHash for the hash, sliding window min done lane-parallel and branch-free. reported 3.4x (w=19) to 6.8x (w=5) faster than the best scalar algorithm; about 4 s forward and 6 s canonical for a 3.2 Gbp genome on one thread, so about 1.3 to 2 ns per base [lit]. our w=5 is exactly their best case (small window, branchless wins most), but their canonical hash is ntHash on 2-bit-packed input, not our direct l-mer value.
- sliding window min algorithms: monotonic deque (what we have), van Herk-Gil-Werman (3 comparisons per element, two prefix/suffix passes per block, branch-free, good for large w), and for w=5 the plain min of 5 registers is just 4 min ops. at w=5 brute force beats the deque [guess, standard result].
- ntHash rolling hash is for large k and random hashes. we do not need it: Kraken2 orders l-mers by value xor toggle, not by a hash, so our candidate is already a 62-bit integer from shifts. keep our ordering (bit-identical requirement), skip ntHash.
- SIMD lanes need 64-bit unsigned min: AVX2 has only signed 64-bit compare (_mm256_cmpgt_epi64), so use the sign-flip trick (xor 1<<63 before compare). AVX-512 has vpminuq directly.

## 3. the three changes, ranked by value per day

### change 1: bulk scan of the whole read into an array (kill the per-call structure)

mechanism: new method `ScanRead(seq, out_min[], out_amb[])` that runs the exact same logic as NextMinimizer in one tight loop over the read, with all state (lmer_, rc_lmer_, queue, positions) in registers, dna_ and bits_per_char as compile-time constants (template on dna), writing minimizers to a per-thread array. fill() then reads the array, hashes and prefetches. removes the call, the prologue and epilogue (9% [measured]), the repeated member loads and stores of state, and the redundant per-call checks. it also lets the hash loop be separate and the compiler pipeline across iterations.
expected scanner speedup: 1.1 to 1.3x [guess]. the 9% is the floor, the rest is state-in-register gains.
end to end: scanner share x (1 - 1/speedup): 38.6% x (0.09 to 0.23) = 3.5 to 9% at 8GB; 2.1 to 5% at 103GB.
bit identical: same code per base, so the stream is equal by construction; verify below.
cost: 1 to 1.5 days. risk: batch interleaving with prefetch (fill() overlaps scan with outstanding prefetches; bulk scanning the whole read first means the prefetch for the first batch issues later). mitigate by scanning in chunks of la_batch outputs, not the whole read.
kill: under 2% end to end at 8GB after oracle test A says the ceiling is larger, or any stream mismatch.
note: this is the cheap relative of E3 (LTO would inline NextMinimizer into fill for free). run E3 s21a/s21b first if the machine is free (2 h). it was never built, only s20 exists.

### change 2: branchless window minimum (replace the deque for w <= 8)

mechanism: because w = 5, keep the last 5 candidates in a small array indexed by position mod 8, and compute the window min as a fixed sequence of min operations (cmov, no loops, no branches): m = min(min(c0,c1),min(min(c2,c3),c4)), or a two-stack variant that shares work across steps. no pops, no front/expiry branches. reset (ambiguous base) just fills the array with UINT64_MAX and a counter. emit the window min from the moment the window is full.
equivalence: the deque returns the minimum candidate value of the last k-l+1 l-mers. position tie-breaking changes which entry is "front" but the returned value (candidate ^ toggle) is identical, and only the value is output. the first k-l positions after a reset are flagged ambiguous by is_ambiguous(), so partial windows only need to match when not flagged: after a reset the stock returns min of the partial queue, ours should also return min of the filled entries (identical if empty slots are UINT64_MAX), so even the flagged values match.
expected scanner speedup: removes the data-dependent branches, expected about 1.5 to 2x on top of change 1 [guess, depends on the mispredict rate; measure branch-misses first].
end to end: combined with change 1, scanner 1.8x: 38.6% x 0.44 = 17% at 8GB, 15% at 16GB, 10% at 103GB. [guess, upper because freed cycles may be partly absorbed by prefetch waits; see risk].
cost: 1 to 2 days including the test harness. kill: if branch-misses per base is under 0.2 [measured], the branch story is wrong and the gain will be small; stop. or if combined 1+2 scanner is under 1.3x in a microbenchmark.

### change 3: multi-lane SIMD scan (the simd-minimizers idea, on the exact Kraken2 definition)

mechanism: for reads with no non-ACGT byte (check with one pass OR-ing lookup codes, nanopore reads from the basecaller are nearly always clean), split the read into 4 (AVX2 64-bit lanes) or 8 chunks with k-1 bases of overlap so each lane produces a contiguous part of the output. each lane keeps lmer, rc_lmer and a 5-slot window in registers: shifts, xors, unsigned 64-bit min (sign flip on AVX2), and the spaced-seed and toggle masks are lane-wise ands and xors. output is written lane-wise and un-interleaved (transposed). any read with an ambiguous base uses the scalar path from change 2. translated (protein) mode keeps the old path.
expected scanner speedup: 3 to 5x over change 2 baseline at AVX2 [lit: 3.4 to 6.8x for w=5 vs best scalar, our scalar after change 2 is already better than a deque, so I discount]. 
end to end: scanner 4x total: 38.6% x 0.75 = 29% at 8GB, 25% at 16GB, 17% at 103GB. [guess, ceiling.]
bit identical: lane overlap logic is the hard part; prove by exhaustive comparison to the scalar stream on all reads, plus synthetic reads of length k-3 to k+50 (edge cases at chunk joins).
cost: 5 to 7 days. needs avx2 (check /proc/cpuinfo on luna; build with function-level target attribute plus runtime dispatch so the binary still runs on Orin and old CPUs, NEON version is a separate port). kill: if change 2 already yields over 1.8x scanner and the oracle shows the scanner is no longer over 20% of cpu, do not build it. also kill if reads are mostly short (mean here is 3.2 kbp [measured], so lanes of 400 to 800 bases are fine; with 8 lanes and k-1=34 overlap the overhead is about 7%).

## 4. correctness guarantee (all three)

1. stream test harness (extend mmtest.cc): for every read of the 1.87M-read file, and for synthetic cases (N in the middle, lowercase, IUPAC letters, read shorter than k, exactly k, k+1, all-A, all-T, palindromic stretches), run old NextMinimizer loop and new scanner, compare per position (value when not ambiguous, amb flag, count). any difference fails. runs on any machine, minutes.
2. classify output diff: full `--report` and per-read output on 8GB and 103GB with byte compare (grid.sh already reports MISMATCH, modes.sh covers 1 and 7 threads).
3. keep revcom_version==0 and protein mode on the original code path, untouched.

## 5. oracle ceiling tests to run FIRST (time only, output wrong by design)

lesson from round 2: S19 overlaps a lot of latency, so scanner share of cpu in perf is not the same as scanner share of wall. measure the wall effect before building.

test A, slope test (cheapest, most honest): in a copy of guarded S19, call a second dummy MinimizerScanner on the same read inside fill() (discard its output, volatile sink). measures how much wall one more scanner pass costs. if wall rises by X% the scanner's true wall share is about X%, and removing half of it saves about X/2. 3 interleaved reps, T=32, 1.87M reads, 8GB and 103GB, like ceil.csv.
test B, queue-removed ceiling (bounds change 2): in the scalar path skip the whole queue block and return a pseudo-minimizer: new value = canonical ^ toggle only when (str_pos_ % 3 == 0), otherwise repeat the previous value. this keeps lookup count and the dedupe behavior close to real (density about 1/3) while removing every pop, push and expiry branch. wall delta vs control bounds what changes 1+2 can save from the queue part.
test C (bounds change 3): do the scan once per read into an array (change 1 skeleton, scalar), then run the scan a second and third time identically; not needed if A and B agree, skip otherwise. instead use `perf stat -e branch-misses,instructions,cycles` on stock S19 8GB T=32 and compute branch-misses per base (divide by 6.04e9). this costs one 1-minute run and decides the branch hypothesis.
decision rule: go to change 1+2 if B shows at least 8% at 8GB and at least 4% at 103GB. go to change 3 only if after 1+2 the scanner is still above 20% of cpu in perf. stop everything if A shows under 5% at 8GB (the scanner is hidden behind memory waits).

## 6. risks specific to this code

- freed cycles can turn into stalls: fill() scans batch n+1 while the prefetches of batch n are in flight. a faster scan leaves less time for lines to arrive before GetAt, so la_batch (K2_B, 16 now; 64 was a null in s20) may need retuning after each change. check PrefetchIndex plus GetAt share (11.8 + 1.5% at 8GB, 10.6 + 8% at 103GB) does not grow.
- at 103GB the kernel frames (14.2 + 10.6% of cpu) and GetAt stalls dominate, so the upside is smaller there (10 to 17%), but 8GB and 16GB, the sizes real users run, gain most.
- ClassifySequence at 14 to 22% was never annotated (ann_classify.txt was 0 bytes); change 1 will move per-base work between it and the scanner, so judge end to end only, not symbol shares.
- the repeated minimizer dedupe (2 of 3 outputs repeat) can be moved into the scan loop in change 1 to also skip MurmurHash3 and the amb check for repeats. this is a small extra win, output unchanged.

## 7. order and cost summary

| step | what | days | expected end to end at 8GB [guess] |
|---|---|---|---|
| 0 | perf stat branch-misses, test A, test B | 0.5 | decides everything |
| 0b | E3 s21a/s21b (-march=native, LTO), if luna free | 0.1 | 0 to 4% (LTO may do change 1's inlining) |
| 1 | bulk scan array | 1 to 1.5 | 3 to 9% |
| 2 | branchless window min | 1 to 2 | cumulative 12 to 17% |
| 3 | AVX2 multi-lane | 5 to 7 | cumulative 20 to 29% |

## summary (6 lines)
1. NextMinimizer runs the full deque algorithm once per base on all 6.04 Gbp, branchy pops and expiry checks, never inlined (prologue and epilogue 9% [measured]); about 40 cycles per base estimated versus 4 to 7 cycles per base in the SIMD literature (simd-minimizers, 3.4x to 6.8x at w=5).
2. proposed: (1) bulk per-read scan into an array, (2) branchless fixed-window min for w=5, (3) AVX2 multi-lane scan with scalar fallback on N bases.
3. expected end to end at 8GB / 103GB: change 1 about 3 to 9% / 2 to 5%; with 2 about 12 to 17% / 7 to 10%; with 3 about 25 to 29% / 15 to 17% [guess, ceilings].
4. bit-identical by construction (same window-min value, spaced-seed and toggle kept) and proven by a per-position stream harness plus classify byte compare.
5. run first: perf stat branch-misses per base, a double-scan slope test, and a queue-removed pseudo-minimizer ceiling; kill if the slope test shows under 5% wall at 8GB.
6. cost 0.5 day for the tests, 1 to 2 days for changes 1+2, 5 to 7 more days for the SIMD change; E3 (LTO) is a 2 hour pre-step that may capture change 1's inlining gain.
