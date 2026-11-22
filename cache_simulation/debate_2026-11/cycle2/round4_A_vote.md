# cycle 2 round 4, agent A: cross-examination and final vote

read all of cycle2 (round1 to round3, both RESULT files, data/). tags: [M] measured in repo data, [A] my arithmetic from those numbers, [G] guess. nothing was run. the thread/numa sweep on luna is not assumed.

## 0. one finding that changes the ranking: the call counts do not add up

take cpu seconds = share x user time (8 GB: 214 s, 103 GB: 268 s, from ceil.csv and nat.csv) [M].

- GetAt: 1.53% x 214 = 3.3 cpu-s at 8 GB; 8.04% x 268 = 21.5 cpu-s at 103 GB. the tracer counted about 218M real lookups (round1_C, the non-dedup branch) [M]. that gives 15 ns per call at 8 GB and 99 ns at 103 GB. plausible: a cached line vs an exposed dram miss.
- PrefetchIndex: 11.79% x 214 = 25 cpu-s at 8 GB; 10.63% x 268 = 28.5 cpu-s at 103 GB. over 218M calls that is 116 ns and 130 ns per call. a FastMod (two multiplies) plus a prefetch cannot cost 116 ns, and the cost does not grow with table size (25 vs 28.5 cpu-s for a 13x bigger table), so it is not walks or dram either. agent C noticed the ns were too big and blamed the denominator. the denominator is not the problem, the call count is.
- if PrefetchIndex runs once per scanner output (6.04G bases, one output per base), it costs 4.1 ns per call at 8 GB and 4.7 ns at 103 GB. flat across db size, plausible for hash plus FastMod plus an L1-hitting prefetch. if it runs once per minimizer change (density about 1/3, about 2G calls) it costs 12 to 14 ns, also plausible.
- so PrefetchIndex (and the MurmurHash3 before it, which perf folds into fill/ClassifySequence) runs on roughly 10x to 30x more keys than GetAt does. most calls are on repeated minimizers whose lookup is skipped later (the skip_lookup slots in round2_C). that work is pure waste: prefetching a line the thread touched one base ago.
- caveat [G]: S19 may already skip hash and prefetch for repeats. my round 3 read of fill() said the dedupe is "later, in ClassifySequence via last_minimizer", but I did not check whether the hash/prefetch sit before or after it. the arithmetic says they sit before. this is a 15 minute source read on luna, and it is the cheapest possible check of the largest unexplained line in the profile.
- upper bound if true [A]: 11.8% (PrefetchIndex) plus the share of MurmurHash3 and the is_ambiguous check inside fill, minus the cost of one compare per base. at 8 GB I would expect 6 to 10% wall, at 103 GB 4 to 8%. output byte-identical by construction (a prefetch has no semantic effect, and the hash is only skipped for slots that skip_lookup already skips).

## 1. cross-examination of agent B (build/system)

L1 thread sweep. fair and cheap, and already running, so it costs nothing now. arithmetic check: user/wall/32 = 214/7.5/32 = 0.89 at 8 GB and 234/7.93/32 = 0.92 at 50 MB [M], so 32 threads are about 90% busy. that fits cpu-bound. B's ceiling of 1.8x needs 64 threads on 64 distinct physical cores; with about 65 other users on the box the scheduler decides that, not us. also 50 MB (7.93 s) is slower than 8 GB (7.58 s) [M, nat.csv], so the wall floor is not memory at all: it is scan plus classify plus fixed costs. a thread win is a deployment flag for stock too, not a patch win (B says this). verdict: read the results when they land, do not spend new time.

L2 numactl. B's 3 to 10% at 8 GB is overstated by arithmetic. the only size-sensitive memory cost in the 8 GB profile is GetAt, 1.5% of cpu. PrefetchIndex is size-insensitive (section 0) so it is not remote-memory driven. even if half of GetAt lookups are remote at 1.5x latency, the gain is under 1%. 103 GB: interleave makes 50% remote by design and GetAt is 8%, so 0 to 1%. my vote: one membind arm as a free rider, expect under 2%, do not allocate hours.

L3 LTO+PGO. LTO is a fair 1 to 3% (kills the call and 9% prologue/epilogue of a 38.6% symbol, so at most 3.5% [A]). PGO is oversold. the scanner's cost is data-dependent branches, and a profile tells gcc how often a branch is taken, not whether it is predictable. a 50/50 branch stays a branch. B also trains on 8 GB and tests on 103 GB, but the scanner does not care about db size, so that generalisation test proves nothing. -march=native already produced a null, which is mild evidence the gain is not in compiler tuning. build cost is real (instrumented run with atomic counters at 32 threads is slow). verdict: LTO as a 20 minute rider on the final binary, skip PGO.

L5 kernel diagnosis. B's hypothesis (load = zeroing plus copy) checks out in my arithmetic: kernel share 22% of about 340 cpu-s is about 75 cpu-s, and 3 s of load x 32 loader threads is 96 cpu-s [A]. so the load phase is about 3 s of the 12.25 s wall at 103 GB, 25%. B says the load is bandwidth bound at "70 GB/s". my number: zero 111 GB, read 111 GB, write 111 GB is about 333 GB of traffic in 3 s, 110 GB/s, against about 300 GB/s peak per socket (C's number, 2 sockets). that is under 20% of peak. so the load is per-thread bound (about 3.4 GB/s per loader thread), not socket bound, and the cap `min(omp_get_max_threads(), 32)` in compact_hash.cc is the limiter. B ranked this "2% to 8%". by my arithmetic doubling loader threads could save up to 1.5 s of 12.25, about 12% at 103 GB, 0% at 8 GB. B under-ranked the best item on its own list.

## 2. cross-examination of agent C (memory system)

region-shrink ladder oracle. its own prediction (R0 minus R3 is 12 to 16% at 103 GB) is already bounded by the skip oracle: 80% skip gave 12.5%, so 100% is about 15.6% [M, A]. the ladder re-measures a known ceiling. its confound: folding idx into a small region changes hit/miss mix, so GetAt probes lengthen (a miss probes about 6.1 cells vs 2.2 for a hit, by C's own Knuth numbers) and branches in the probe loop change. the round 2 lesson (data-dependent branches wreck an oracle) is not fully avoided. what it would tell us (TLB 2 to 5%) cannot be fixed without root (1 GB pages). knowledge, not a win.

perf stat MLP events. cheap but diagnostic only. K2_B 16 vs 64 null already says MLP is saturated. the one event worth keeping is `mem_load_retired.l3_miss` per GetAt, and it fits in my E0.

C's Little's law arithmetic divides by 218M lookups and gets 0.4% fill-buffer utilisation. that is the GetAt count. the prefetch count is 10x to 30x higher (section 0), so the buffers see far more traffic than C assumes, and "2 to 3 ns FastMod" times 6G calls is itself 12 to 18 cpu-s. C's conclusion (PrefetchIndex is a size-insensitive floor) is right, but the floor is removable, not "hash, issue, buffer bursts" to accept.

aligned buckets and smaller cells need a db rebuild (103 GB build takes many hours) and cells change output (false positives) so they fail "byte-identical in 4 to 5 hours" by construction. C's own ceiling is 1 to 3% wall for aligned buckets and 5 to 6% for 24-bit cells via load time, which the loader-cap fix reaches without touching accuracy. the prefetch-next-line oracle (3.1) is a one line, byte-identical change and the only C item worth a slot; GetAt at 8% of 103 GB cpu caps it at about 3% [A], so it goes in only if time is left.

## 3. my own scanner proposals, honestly

branch-misses per base: no evidence exists. nothing in the repo has branch-misses, instructions or IPC for the S19 binary. what I had was (a) a flat annotate with top instruction 3.9%, (b) -march=native null, which only says the vectoriser found nothing, (c) arithmetic: 38.6% x 214 s / 6.04G = 13.7 ns per base, about 35 to 40 cycles. that is a large number but it also includes smt sharing, so it is an upper bound. I retract "about 1 mispredict per base" as a finding; it is a guess. instructions per base and IPC are the two numbers that decide it: a flat 40 cycles with 60 instructions is IPC 1.5 (stalled or mispredicting), with 150 instructions is just executing (then the loop is instruction bound and branchless buys little).

retractions: change 3 (avx2 multi-lane, 5 to 7 days) is out of this window and I withdraw it until the slope test and the branch data justify it. my 17% at 8 GB for changes 1+2 was a ceiling stacked on a guess; shade it to 5 to 10%. my "dedupe in the scan loop is a small extra win" in round 3 section 6 was wrong in size: by section 0 it is the biggest item.

cheapest time-only oracle for the scanner: the slope test. in a copy of guarded S19, inside fill() call a second MinimizerScanner on the same read, fold its outputs into one thread-local xor sink (written once per read so the compiler cannot delete it). build two variants: +1 pass and +2 passes. wall(+1) minus wall(0) divided by wall(0) is the scanner's true wall share s; wall(+2) checks linearity (if +2 is not twice +1, overlap is hiding work and s is not additive). it measures the same mispredicts as the real scan, since the data and branches are identical. what it bounds: removing the scanner entirely saves s, halving it saves s/2. at user/wall/32 of 0.89 I expect s about 30 to 35% at 8 GB [A]; the kill is s under 8%. one flaw to state: a dummy pass is independent of the lookup pipeline, so out-of-order overlap may make it cheaper than the real scan, which makes s a lower-ish bound; that errs on the safe side for a kill decision. the counters for the section 0 call counts go into the same build (three thread_local ints: bases scanned, minimizer changes, GetAt calls, printed at exit).

## 4. final vote: ordered plan, at most 5 experiments, about 4.75 h

all comparisons: guarded S19 as control, T=32, 1.87M reads, plain --report, interleaved reps, byte compare of per-read output (cmp, no sort) on every variant. dbs 8 GB, 16 GB, 103 GB unless stated. timing runs need the box quiet, builds can overlap with analysis, not with timing.

### E0: diagnostics and source read (0.5 h, no build, no dependency)
runs: (a) on luna read fill() and the ClassifySequence batch loop: are MurmurHash3 and PrefetchIndex before or after the last_minimizer / skip_lookup test? (b) `perf stat -e cycles,instructions,branches,branch-misses` and `-M TopdownL1` on guarded S19, 8 GB, T=32, 1.87M reads; one `perf record -e branch-misses` run, report by symbol. divide by 6.04G bases. (c) /proc/vmstat diff (thp_fault_alloc, thp_fault_fallback, compact_stall, numa_pages_migrated) around one 103 GB 10-read run. (d) read the thread/numa sweep results when they land.
success: a clear yes/no on (a); branch-misses per base and instructions per base as numbers; thp_fault_fallback near 0.
kill: none, it is the gate. if (a) says the guard already exists, E2 is dead and its time moves to E4.

### E1: loader thread cap 32 to 64 and 96 (0.75 h, no dependency except E0c)
what: one line in compact_hash.cc (`if (nthr > 32) nthr = 32`), rebuild twice (cap 64, cap 96). runs: 0-read (or 10-read) 103 GB, 5 interleaved reps, record `processed in` and total wall; then the full 1.87M-read run 3 reps for the best cap. also 8 GB (expect 0).
success: 10-read wall from about 3.0 s to 2.0 s or less, and at least 8% on the full 103 GB run (about 1 s of 12.25 s). kill: under 0.3 s saved on the 10-read run, or thp_fault_fallback large in E0c (then the kernel cost is 4 KB faults and a different fix). output cannot change; still cmp.

### E2: dedupe before hash and prefetch (1.5 h, depends on E0a saying the guard is missing)
what: in fill()/the batch loop, test `minimizer == last_minimizer` (the existing skip_lookup condition) before MurmurHash3 and PrefetchIndex, and fill the slot as skip_lookup without computing either. nothing else changes. runs: 50 MB, 8 GB, 16 GB, 103 GB, 5 reps interleaved vs control, cmp every output.
success: at least 4% wall at 8 GB and 16 GB (median of 5), at least 2% at 103 GB. kill: under 2% at 8 GB, or any byte difference. if it works, the new binary becomes the control for E3/E4.

### E3: scanner slope test plus call counters (0.5 h, build overlaps with E1 runs, no dependency)
what: the +1 and +2 dummy-pass variants of section 3, with the three counters. runs: 8 GB and 103 GB, 3 interleaved reps each of control, +1, +2.
success: s (wall(+1)/wall(0) minus 1) at least 15% at 8 GB, +2 within 20% of twice +1 (linear), and the counters tell the true GetAt/minimizer-change/base ratios (settles whether 218M or about 2G is the real lookup count). kill: s under 8% at 8 GB (scanner hidden, drop E4). output is wrong by design in no case: the dummy pass is discarded, so cmp should still pass; run it once as a check.

### E4: in-place branchless 5-slot window minimum (2 h, depends on E3 s at least 10% and E0b branch-misses at least 0.3 per base)
what: no bulk-scan restructure, keep NextMinimizer's interface. replace the deque with a fixed ring of 8 candidates (UINT64_MAX filled on reset) and a fixed min over the last k-l+1 = 5 (four min ops, cmov). keep the spaced-seed and toggle masks and the reset on ambiguous bases exactly. first the stream harness (mmtest.cc extension): compare the old and new minimizer value, ambiguity flag and count for every position of the 1.87M reads plus synthetic edge reads (N mid-read, lowercase, IUPAC, length k-3 to k+50, all-A). then wall, 3 to 5 interleaved reps at 8 GB and 103 GB, cmp every output.
success: harness differences 0; single-thread scanner speed at least 1.25x on the harness; wall at least 5% at 8 GB and 2% at 103 GB. kill: any stream difference, or microbenchmark under 1.25x, or wall under 3% at 8 GB. then stop, the scanner is not a branch problem and the next step would be a different oracle, not avx2.

### order and slack
1. E0, 2. E1 and E3 build overlap, 3. E2 (if alive), 4. E4 (if gated in). if E2 is dead, E4 starts right after E3. optional riders only if the box is still quiet: LTO build (20 min, kill under 1.5%), numactl membind 8 GB arm (kill under 2%), prefetch-next-line one-liner (kill under 1.5% at 103 GB).

## summary
1. the profile arithmetic says PrefetchIndex (11.8%, flat across db size) runs on 10x to 30x more keys than GetAt: the biggest unexplained cost is probably hash plus prefetch on repeated minimizers, removable and byte-identical; 15 minute source read decides.
2. loader thread cap is the second bet: load is about 3 s of 12.25 s at 103 GB and runs at under 20% of memory bandwidth, so more loader threads could save about 1 to 1.5 s; B under-ranked it.
3. attacked B: numactl is under 2% at 8 GB (GetAt is only 1.5%), PGO does not fix unpredictable branches; attacked C: the ladder re-measures the known 15% ceiling, aligned buckets and small cells need a rebuild and cannot be byte-identical inside 5 h.
4. scanner: branch-misses-per-base evidence does not exist, retracted the 1-mispredict claim and the avx2 change; the honest oracle is a +1/+2 dummy-pass slope test, which bounds the scanner's wall share s.
5. plan: E0 diagnostics 0.5 h, E1 loader cap 0.75 h, E2 dedupe-before-hash 1.5 h, E3 slope test 0.5 h, E4 in-place branchless window min 2 h, with kill criteria 0.3 s, 2%, 8%, 3% as written.
6. dependencies: E2 needs E0a, E4 needs E3 (s at least 10%) and E0b (branch-misses at least 0.3 per base); E1 and E3 are independent; thread/numa sweep results are read, not assumed.
