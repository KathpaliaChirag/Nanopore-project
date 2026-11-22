# cycle 2 round 4, agent B: cross-examination and final vote (2026-11-23)

read: all round1 to round3 files, both RESULT files, data/. tags: [M] measured in repo data, [A] my arithmetic, [G] guess. nothing was run. the thread and numactl sweep is still running, so nothing below assumes its result.

## 1. what the new facts change

- the lookup path is capped near 15 to 19% of wall at 103 GB by the oracle, and the static front table is dead. so the only large block left that the code can touch is the scanner (38.6, 33.9, 22.9% of samples) plus ClassifySequence (21.6, 19.9, 14.0).
- -march=native is a null even though 61 vector instructions were emitted. so the scanner is not bound by arithmetic throughput. it is bound by something else: branches, dependent loads, or a stall that perf charges to it.
- a number nobody has used yet: 240 cpu-seconds at T=32 on 8 GB over 6.04e9 bases is about 40 ns per base in total, and the scanner's 38.6% of that is about 15 ns, roughly 45 cycles per base [A]. one mispredict (15 to 20 cycles) plus a 5-slot window update cannot reach 45 cycles. so either the scanner mispredicts about twice per base, or a large part of its samples is skid from the prefetch stalls in fill() (agent C's mechanism 2) or smt sharing. this is the single most important unknown for the scanner track, and it is checked by two free perf runs (experiment 1).

## 2. attack on agent A (scanner)

1. bulk scan, claimed 1.1 to 1.3x. the only measured support is the 9% of NextMinimizer samples spent in prologue and epilogue. 9% of 38.6% is 3.5% of the whole run at 8 GB, and that is the ceiling for removing the call. the rest ("state in registers") is a guess. LTO can inline the call without any rewrite, so change 1 is mostly a duplicate of my LTO experiment and should not be built separately.
2. branchless window min, claimed 1.5 to 2x on top. it only pays if mispredicts are the cost. A estimates 1 mispredict per base from a flat profile, which is an inference, not a count. but the 45 cycles per base above says the story is incomplete. also the deque pop loop is not random: for w=5 the pop count is geometric with a small mean, and the predictor learns the common case of zero or one pop, so 0.5 mispredicts per base is more likely than 1.0 [G]. A's own kill (under 0.2 misses per base) is right, I would raise the go line to 0.6.
3. AVX2 lanes, 3 to 5x, 5 to 7 days. the literature speedup (3.4x to 6.8x) is against a scalar deque with ntHash on 2-bit input, and our code uses direct l-mer values with a spaced-seed and, and a toggle xor. the sign-flip unsigned min on AVX2 costs two extra ops per lane. it does not fit a 4 to 5 hour window and the march=native null says compiled vector code did not help, which is weak (the compiler cannot vectorise a loop-carried deque, so the null does not refute hand lanes). I keep it as a later item, only if the scanner is still over 20% of cpu after the cheap changes.
4. test B (pseudo-minimizer every third base) is a biased ceiling. a fixed period of 3 makes the lookup pattern perfectly regular, which also removes the batch holes and ClassifySequence's data-dependent branches (the skip oracle lost 7% at 8 GB for exactly that reason). it overstates the gain. test A (second dummy scan) is honest, but a dummy scan over a read already in L1 is cheaper than the real one, so it understates. take them as brackets, not as a decision.
5. A's end-to-end maths (38.6% x 0.44 = 17%) treats cpu share as wall share. at 50 MB and 8 GB that is nearly true (234 s / 32 = 7.3 s of 7.9 s wall [M]), so I accept it for the small dbs. at 103 GB the 22.9% share and the 25% kernel share make it inapplicable, 10% at most.

## 3. attack on agent C (memory system)

1. the ladder oracle (shrink idx to 4 GB, 128 MB, 8 MB) is not a pure memory test. with wrong table contents at the tiny sizes, lookups return mostly absent or wrong taxa, so ClassifySequence takes different paths (fewer hits, shorter hit lists, different LCA work). the wall delta mixes memory and compute. it also costs half a day to bound ideas that C itself prices at 1 to 3% each. the skip oracle already gave the cap: about 15.6% at 103 GB by extrapolation, 0% at 8 GB.
2. C's own arithmetic contradicts its premise. section 0 says K2_B 64 being a null shows MLP is saturated. section 1.2 computes 0.4% fill-buffer utilisation and 0.6 M lookups per second per thread, one lookup per 1.75 us against a 120 ns miss. that means memory is about 7% of per-lookup time and prefetch depth is irrelevant, not saturated. the null is explained by "memory is mostly hidden", which is the S19 story.
3. perf stat with 11 events on 32 threads will multiplex (8 general counters on Sapphire Rapids), and whole-process counts include the 22% kernel load phase at 103 GB. every decision rule C wrote ends in a layout idea worth 1 to 3%. the information is cheap but its value is low. I would take only cycles, instructions, branch-misses, and one memory group, not the full table.
4. aligned buckets: C prices the wall gain at 1 to 3%, below the 1% run noise on a single comparison, and it needs a new 103 GB database build. the 32% second-line crossing rests on "half of lookups miss", which is unmeasured.
5. smaller cells for the load phase: breaks the requirement. a 24-bit cell changes the false-positive rate, so output is not byte-identical. also the claim that the two kernel addresses are the load is unproven (kptr_restrict). kill for this plan.
6. the kache-hash style locality idea: C's own estimate is 1 to 3%, needs a full rebuild, key-bit changes and a spill rule. kill for this window.

## 4. honest re-estimate of LTO and PGO

what each does to this code:
- LTO lets gcc inline NextMinimizer into fill() and drop the call. the saving is the 9% prologue and epilogue plus some redundant loads, so at most 3.5% at 8 GB and I expect 1 to 2%, because the scanner state lives in a heap object and fill() calls hash and prefetch between scans, so gcc cannot keep scanner state in registers across them [G].
- -fprofile-use gives gcc taken-probabilities per branch, not predictability. it does hot/cold block layout (hot path falls through, cold paths move away), better inlining and loop peeling, and decides when if-conversion (cmov) is worth it. it does NOT fix a data-dependent unpredictable branch, because a 50/50 branch profiles as 50/50 and gets the same code. so for a mispredict-bound scanner PGO changes little. it helps front-end effects (taken-branch bubbles, i-cache), which are a smaller part when mispredicts dominate. realistic: 0 to 4% on the scanner-heavy small dbs, about 0 at 103 GB.
- combined realistic gain 1 to 5%, central 2%. I lower my round 3 figure (5 to 12%) because the march=native null shows this binary is not compute-shaped, and the 5 to 12% was a generic prior with no kraken number behind it.
- still ranked: yes, rank 3. it costs about 1 hour of mostly build time, needs no source change, is byte-identical by construction, and the detectable threshold is about 1.5% (the guarded 8 GB runs vary 7.53 to 7.60, about 1%, with 5 reps). it is also the cheap way to learn what code layout can give the scanner, which sets the value of the harder scanner rewrite.
- kernel-share diagnostic (vmstat diff): rank high, because it is 10 minutes and it explains a quarter of the 103 GB run. I fold it into the loader experiment so it rides on runs I am doing anyway. note an earlier claim of mine needs a correction: an early _exit would not save the exit tax, because the kernel frees the pages in exit_mmap either way. only fewer pages (THP actually taking) shrinks it, so the vmstat thp_fault_fallback counter is the test.
- loader cap 32 to 96: rank 2, the best chance of a clean win at 103 GB. load plus exit is about 3.0 s of 12.2 s wall [M]. 111 GB in about 2.5 s is about 1.2 GB/s per loader thread [A], far below what one core copies, so the loader is not bandwidth-bound and more threads should cut it. if it goes from about 2.5 s to about 1.5 s that is 8% of the wall. the loader ignores --threads, so the sweep uses OMP_NUM_THREADS.

## 5. final vote: five experiments, in order

all run on a copy of the guarded S19 tree (e1/src_hll, the tree used for the march=native build), never the live one. every build edits src/Makefile in place so -DLINEAR_PROBING stays. after every build run `grep -n "LINEAR_PROBING" src/Makefile` and confirm the flag is on the compile line of the first object in the make output. never override CXXFLAGS on the make command line. always `make clean` first (the install script does not). byte-compare per-read output with cmp, no sort, and the plain report. interleave reps, 5 per arm, T=32, all 1,872,777 reads, same harness as data/nat.csv (grid.sh).

### E1. discriminate the scanner story (0.5 h, no build)

run: on the guarded binary, 8 GB and 50 MB, T=32: `perf stat -e cycles,instructions,branches,branch-misses -- <the usual classify command>`. also run it with 0 reads (or 10 reads) and subtract, to remove load. then `perf record -e cycles:pp -g0` on 8 GB and read the NextMinimizer share (cycles:pp uses precise sampling and removes most skid).
success: branch-misses per base (divide by 6.04e9) of at least 0.6, and NextMinimizer share under :pp still at least 30%. then E4 is a go.
kill for E4: under 0.3 misses per base, or the :pp share drops below 20% (the scanner share was skid from prefetch stalls and the scanner is not the cost). if the :pp share drops, the cost lives in fill() and E4 is dead, and the remaining time goes to the loader and the sweep result.

### E2. loader cap plus vmstat diagnostic (0.7 h)

build: copy tree to e1/src_ld; edit the line `if (nthr > 32) nthr = 32` in src/compact_hash.cc to 96 (keep all else); `cd e1/src_ld/src && make clean && make -j16`.
run: 103 GB and 16 GB, the 10-read run and the full 1.87M-read run, with `OMP_NUM_THREADS=32` and `OMP_NUM_THREADS=96` (two arms, same binary pair: guarded vs capped), 5 interleaved reps. before and after one 103 GB run, `grep -E "thp_fault_alloc|thp_fault_fallback|compact_stall|numa_pages_migrated|pgfault" /proc/vmstat` and diff. record load, classify and exit separately (grid.sh already does).
success: 103 GB wall down by at least 0.5 s (4%) median, load part down by at least 30%, output byte-identical.
kill: under 0.25 s (2%) at 103 GB, or any mismatch. if thp_fault_fallback is large, report that as the cause of the 13 to 21 s swings and stop the cap work (the variance, not the cap, is the problem).

### E3. LTO then PGO (1.0 h, mostly build time)

build LTO, tree e1/src_lto:
`cp -r e1/src_hll e1/src_lto && cd e1/src_lto/src && sed -i '/^CXXFLAGS/ s/-O3/-O3 -flto=auto/' Makefile && grep -n "CXXFLAGS\|LDFLAGS\|LINEAR_PROBING" Makefile && make clean && make -j16 V=1 2>&1 | tee build.log | grep -c LINEAR_PROBING`
check that the link line also carries -flto (if the Makefile links with a separate LDFLAGS, add it there with sed; if link uses $(CXXFLAGS) it is already there). check `nm classify | grep NextMinimizer` shows whether the symbol was inlined away.
build PGO instrumented, tree e1/src_pgo: same copy, sed adds `-O3 -fprofile-generate -fprofile-update=prefer-atomic` (threads, so counters must be atomic), make clean, make. run once on 8 GB with the first 105k reads (the usual small-read file), T=32, which writes .gcda files beside the objects. then `make clean-objects-only` is not safe (it deletes .gcda): instead `find . -name '*.o' -delete`, change the flags to `-O3 -flto=auto -fprofile-use -fprofile-correction -Wno-missing-profile`, and `make -j16`. train on 8 GB, test on 50 MB and 103 GB to check the profile generalises. skip -ffp-contract=off: with no -march the x86-64 baseline has no fma, so it changes nothing, and I do not want a stray flag in the artifact.
run: guarded vs LTO vs LTO+PGO, 50 MB, 8 GB, 16 GB, 103 GB, 5 reps, T=32, cmp every output.
success: at least 2.5% median wall on both 50 MB and 8 GB for LTO+PGO, no loss at 16 or 103 GB beyond 0.5%.
kill: under 1.5% on both, or a byte mismatch. if LTO alone is under 1% and PGO adds under 1%, stop, and write it up as a second compiler-level null next to march=native. per-machine profile note for the paper (Orion needs its own).

### E4. branchless 5-slot window min inside NextMinimizer (1.5 h Luna, about 2 h coding off-machine; only if E1 passes)

change: in mmscanner.cc, for the case k-l+1 <= 8 (the standard db has 5), replace the deque with a ring of 8 candidates indexed by position mod 8, and compute the window minimum with fixed min operations over the filled slots. empty slots hold UINT64_MAX so the first k-l positions after an ambiguous base return the same partial min as the deque. keep the spaced-seed and, the toggle xor, the call structure and the ambiguity flag exactly as they are. no bulk array, no lanes. other w values use the old path.
test first, before timing: extend mmtest.cc to compare the old and new scanner per position (value, ambiguity flag, count) on every read of the 1.87M-read file plus synthetic cases (an N in the middle, lowercase, IUPAC codes, reads of length k-1, k, k+1, all-A, palindromes). zero differences required.
build: tree e1/src_bm from e1/src_hll, patch applied, same Makefile (LINEAR_PROBING untouched), `make clean && make -j16`. then the grid with cmp.
success: at least 6% wall at 8 GB and 4% at 50 MB, byte-identical output.
kill: under 2% at 8 GB, or any stream mismatch. if it lands between 2 and 6%, keep it, stack with E3 if E3 won, and do not start the lane work.

### E5. stack and confirm (0.6 h)

take every winner from E2 to E4, plus any thread-count or numactl setting from the running sweep that shows at least 5%, combine in one tree e1/src_stack, and run the full 4 read counts by 4 db grid, 5 reps, cmp on every cell, medians against stock S15-era baseline and guarded S19 at the same T. report the whole grid, not a subset. this is the number the paper can quote; individual wins are not.
success: byte-identical in all 16 cells and the stack at least 5% over guarded S19 at 8 GB.
kill: any mismatch (bisect the stack, drop the offender), or the stack is under the sum of parts by more than half (the wins overlap, keep the cheapest).

## 6. time budget and why this order

E1 0.5 + E2 0.7 + E3 1.0 + E4 1.5 + E5 0.6 = 4.3 h of Luna, and builds in E3 run while E4 is being coded. E1 goes first because it gates E4 and costs 0.5 h. E2 goes second because it has the best chance of a clean win with almost no code. E3 third because it is the cheap compiler test. E4 fourth because it is the only experiment with a plausible 10% or more, but it is conditional and the most work.

dropped and why: bulk scan (3.5% ceiling, LTO covers it), AVX2 lanes (days, not hours), ladder oracle and the MLP perf stat table (cap already known, ideas priced at 1 to 3%), aligned buckets and kache-style placement (need a rebuilt db, under noise), smaller cells (not byte-identical), tcmalloc and OMP env (0 to 2%, malloc is not in the profile), BOLT and clang (not installed), -M (loses huge pages).

## summary (6 lines)
1. order: E1 perf stat branch-misses plus cycles:pp skid check, E2 loader cap 32 to 96 with vmstat diff, E3 LTO then PGO, E4 branchless 5-slot window min, E5 stacked 16-cell byte-compare grid.
2. my LTO+PGO estimate drops from 5 to 12% to 1 to 5% (central 2%): PGO fixes layout, not unpredictable branches, and -march=native proved the scanner is not arithmetic-bound; still ranked third because it is a 1 hour no-code test.
3. 240 cpu-s over 6.04e9 bases is about 45 cycles per scanner base, more than mispredicts explain, so E1 must check for skid before any scanner rewrite; go for E4 only at 0.6 or more misses per base.
4. A's bulk scan is a 3.5% ceiling that LTO covers, its AVX2 plan is days and its test B overstates; C's ladder oracle is confounded by changed classify paths, its MLP premise contradicts its own 0.4% buffer arithmetic, smaller cells break byte-identity.
5. every build copies e1/src_hll, edits src/Makefile in place with sed, runs make clean, and checks LINEAR_PROBING appears on the compile line; correctness is cmp on all 16 cells plus a per-position stream harness for the scanner.
6. correction to my round 3: an early _exit does not remove the exit tax, the kernel frees the pages either way; only THP taking (vmstat thp_fault_fallback) shrinks it.
