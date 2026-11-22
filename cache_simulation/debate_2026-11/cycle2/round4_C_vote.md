# cycle 2 round 4, agent C: cross-examination and final vote

read: all of cycle2 (round1 to round3, both result files, data/). nothing run. tags: [L] measured by us, [S] source, [A] my arithmetic, [G] guess.

## 0. one fact that reorders everything

stock-vs-guarded walls at T=32 [L, nat.csv]: 50 MB 7.93 s, 8 GB 7.58 s, 16 GB 8.58 s, 103 GB 12.25 s. the 50 MB db fits in L2 and is no faster than the 8 GB db, in fact 0.35 s slower. so at 8 GB the exposed memory cost is about zero [A]. the 103 GB run is 4.3 s above the 50 MB floor, of which the load is about 3 s (10-read run, ledger item 14) and exposed lookup memory is about 1.3 s, about 10% of wall [A]. this agrees with the skip oracle (15% extrapolated ceiling for all lookups at 103 GB). two consequences:

1. the 7.5 to 7.9 s floor is cpu work (scanner, classify, parse, output) or a serial stage. no memory idea can touch it. only the scanner/classify side or the thread count can.
2. at 103 GB the biggest single block that is not scanner is the load, about 25% of wall, bigger than the whole lookup path.

## 1. attacks on agent A (scanner)

1. the 38.6% share is a perf sample share, not a wall share. A says so in section 5, but the headline table (12 to 17% at 8 GB) multiplies the sample share by a speedup anyway. cpu seconds at 8 GB are 215 s over 32 threads is 6.7 s, wall 7.5 s. so threads are busy, but busy includes OpenMP spin and the load phase (about 0.7 s of that at 8 GB). the "40 cycles per base" is therefore an upper bound and A already admits it. do not rank on it.
2. the branch-misprediction story is a guess with exactly one weak support: -march=native was a null. that fits "branchy, not arithmetic", but it also fits "serial reader or barrier is the wall". a null from a vector flag cannot tell these apart. the perf stat line settles the first half for free, the thread sweep the second.
3. test B (pseudo-minimizer every third base) is flawed. it changes the key stream: it repeats the previous value and emits canonical^toggle on a fixed phase, so the lookups hit different slots with different hit rates and a different dedupe pattern. at 103 GB that changes the memory cost, so the delta is scanner savings plus a memory change, and cannot be read as either. test A (dummy second scanner on the same read) leaves the key stream alone and is the clean one. drop B, keep A.
4. test A has a bias in the other direction: the second scan runs on a hot line of read bytes while prefetches are in flight, so part of its cost hides behind memory waits and the slope underestimates. at 8 GB the memory wait is about zero [section 0] so the bias is small there. it is a lower bound on the share, which is the safe direction for a kill rule.
5. change 3 (AVX2 lanes, 5 to 7 days) is outside any window we have. the literature 3.4x to 6.8x is on a Rust crate with ntHash, not on the exact kraken2 ordering with spaced seed and toggle; A discounts it but then still prints 25 to 29% end to end. treat that as an uncheckable ceiling. change 2 (branchless w=5) is the only scanner change worth a design, and it is days, not hours.
6. A's bit-identical argument for change 2 is sound (value only is output). the real risk is the first k-l positions after an ambiguous base. A covers it with UINT64_MAX fill. fine.

## 2. attacks on agent B (build and system)

1. numactl membind at 8 and 16 GB (B's rank 2, "3 to 10%") fails the arithmetic in section 0. at 8 GB the db costs nothing exposed (8 GB wall equals the 50 MB wall), so removing remote accesses cannot gain 3 to 10%. realistic gain at 8 GB is under 1%, at 16 GB (wall 1.0 s above the floor) at most 0.5 s, about 3%, if every remote access vanished. B multiplied "50% remote" by the 12% PrefetchIndex sample share, but that share is mostly skid and floor, not remote latency (my round 3 section 1.2). interleave at 103 GB: 50% remote stays, ceiling is the same 1.3 s. the sweep is already running, so read it, but do not budget extra hours for it.
2. thread sweep 64/96 predicts "1.3x to 1.8x". that holds only if the work scales, and 50 MB user cpu of 234 s over 7.93 s wall is 29.5 busy threads of 32, so cpu is saturated and more cores can help. so this one is plausible, and it is the only lever with a large upside. but at 103 GB the loader is capped at 32 threads and the load is 3 s of 12.25 s, so the cap on the wall gain is 9.2/(2) = 4.6 s saved at best, 1.3x not 1.8x. also user cpu rising with flat wall means spin. it is already running, wait for it.
3. LTO+PGO "5 to 12%" has no kraken number [B admits]. but it is the only no-code lever aimed at the 38.6%. -march=native shows cross-translation-unit scalar tuning is not the story, so LTO alone is likely about 1 to 2% (call and prologue were 9% of NextMinimizer samples = 3.5% of cpu [A]). PGO is the part with upside, because it lays out the data-dependent pop and expiry branches. cost is honest (45 min), byte identical by construction. keep it, expect 2 to 6%.
4. B's kernel 22% explanation (zero plus copy of 111 GB) is the best idea in the file and is also the cheapest test (vmstat diff). but "loader cap 32 to 64 gives 0.3 to 1 s" assumes the load is not already at memory bandwidth. 111 GB in 3 s is 37 GB/s read plus 37 GB/s zero write, about 74 GB/s of traffic against a two-socket peak of roughly 600 GB/s [G], so there is headroom. keep.
5. tcmalloc and OMP env are under 2% by B's own arithmetic and malloc is not in the top 9 symbols. drop them from the window.

## 3. retractions and defences of my own round 3 proposals

- region-shrink ladder (R0 to R3): defend the method, retract the priority. the oracle plus the 50 MB floor already bound the whole lookup path at about 10 to 15% of wall at 103 GB and about 0 at 8 GB. the ladder only splits that into TLB, DRAM and L3. that split is a good figure for a characterisation paper (it says why S14 mattered and why nothing left is large) but it cannot produce a speedup. keep as the last item, about 1 hour.
- perf stat events: defend, but cut to six events, since only the decision rules matter: branch-misses, cycles, instructions, dtlb_load_misses.walk_active, l1d_pend_miss.pending (measured MLP), memory_activity.stalls_l3_miss. it also serves A's branch question for free. 0.5 hour.
- aligned buckets: retract as a build. predicted lookup-path gain -12 to -14%, wall 1 to 3% at 103 GB and 0 at 8 GB, and it needs a db rebuild with a changed hash-to-slot map. below noise on one wall-clock number. the one-line "prefetch next line when idx&15 >= 10" oracle stays as an optional 40 minute filler, not in the vote.
- smaller cells: retract for this window. the load-phase gain (5 to 6% at 24-bit) is real, but a smaller cell moves the false-positive law, so output is not byte identical, which is the stated goal of the window. it stays as thesis item 2 with the accuracy cost reported.
- analytic MLP model: retract as a build now. see section 4.

## 4. what the project can honestly claim and publish about caches

claim (bounded negative, all on one machine, one read set, T=32 unless stated):

1. reuse profile [L, E1 trace]: 262K hottest slots cover 56% of lookups at 8 GB, 1M slots cover 90%. real skew exists.
2. oracle ceiling [L, ceil.csv]: a free front table at 45% coverage gains about 0% at 103 GB (-1.3%) and loses 7% at 8 GB. 80% coverage gains 12.5% at 103 GB but needs 10 to 16 MB that does not stay in L2 and 0% at 8 GB. so a static hot-set cache cannot beat batched software prefetch here.
3. Belady bound and the 4-way ablation [earlier cycle]: replacement policy has nothing to optimise when the whole lookup path is at most 10 to 15% of wall and the cache was not the cause of the S6 to S15 speedups.
4. MLP saturation: K2_B 16 vs 64 null, S16 gave -10%, so latency overlap is already at the knee.
5. double hashing: implemented, dead behind -DLINEAR_PROBING, costs a new random line per probe (n goes up), so linear stays.
6. -march=native null, HLL guard 1.15x to 1.62x as the one real memory-side-adjacent win (it removes lookups, not latency).

this is a publishable characterisation: "why caching and eviction policy do not pay for a prefetch-batched k-mer classifier, with a method to prove it before building". the method matters more than any one number.

on the model question: build the oracle-ceiling method, not the analytic model. the oracle needs no simulator, measures the real machine including page walks and fill buffers, and killed a 2 to 4 day build in one hour. the four-parameter MLP model (c, L, w, buffers) would be fitted to the very series (S9, S14, S16, K2_B) that already exist, so it can only reproduce them, and the oracle already shows the ceiling is below the model's resolution (1 to 3% per idea, noise about 1%). build the model only if a new layout idea survives the oracle and then needs ranking among variants. what to do instead: package the oracle as a three-step recipe (control hook, skip or shrink with no data-dependent branch, compare to the hook-0 control) and cite the 8 GB branch artifact as the pitfall.

## 5. final vote: five experiments, about 4.5 hours of Luna

the thread sweep and numactl sweep already running on Luna are not counted. if they show a large win (T=64 more than 15% at 8 GB), that result outranks everything below and becomes experiment 0 (re-run stock at the same T for fairness).

### E1: perf stat bundle on guarded S19 (0.5 h)
- runs: T=32, full 1.87M reads, 50 MB, 8 GB and 103 GB, 2 reps each, `perf stat -e branch-misses,cycles,instructions,dtlb_load_misses.walk_active,l1d_pend_miss.pending,memory_activity.stalls_l3_miss`, plus a 10-read run per db to subtract load. divide branch-misses by 6.04e9 bases.
- success: branch-misses per base at least 0.5 (scanner branch story confirmed, E2 and E3 go on), or IPC above 2 (it is not branch bound, kill the scanner branch plan). also record stalls_l3_miss share: if above 15% at 103 GB the oracle is wrong and I withdraw.
- kill: not applicable, it is a measurement. it gates E2 and E3.

### E2: scanner slope test (A's test A) (1.0 h including a 10 minute build)
- runs: copy e1/src_hll, in fill() call a second MinimizerScanner on the same read, discard output into a volatile sink, keep the real lookup path. T=32, all reads, 50 MB and 8 GB and 103 GB, 3 interleaved reps against the hook-free guarded build.
- success: wall rises at least 15% at 8 GB (so halving the scanner is worth at least 7%), which green-lights change 2 in the next window.
- kill: under 5% at 8 GB and 50 MB means the scanner hides behind a serial stage or spin; drop all scanner work and read the thread sweep instead.

### E3: LTO + PGO build (1.25 h)
- runs: edit Makefile in place (keep -DLINEAR_PROBING) to add `-flto=auto -ffp-contract=off`, build as variant L. second variant P: `-fprofile-generate -fprofile-update=atomic`, train on 8 GB with 105k reads, rebuild with `-fprofile-use -fprofile-correction`. time L and P against guarded S19 at T=32, all reads, 50 MB, 8 GB, 103 GB, 5 interleaved reps, byte compare per-read output on all three.
- success: P at least 4% faster at 8 GB and 50 MB (median of 5), byte identical. test the 8 GB profile on 103 GB to see if it generalises.
- kill: P under 2% at both, or any byte mismatch. LTO alone under 1% is expected and is itself reported as a null.

### E4: load-phase diagnostic and loader cap (0.75 h)
- runs: `grep -E "thp_fault_alloc|thp_fault_fallback|compact_stall|numa_pages_migrated|numa_hint_faults" /proc/vmstat` before and after one fast and one slow 103 GB run. then change `if (nthr > 32) nthr = 32` in compact_hash.cc to 64, rebuild, time the 10-read 103 GB run, 4 interleaved reps against cap 32, byte compare a full run.
- success: load time at least 0.4 s lower (3 s to 2.6 s, 3% of the 12.25 s wall), output identical. also the counters explain the 13 to 21 s variance.
- kill: under 0.2 s (load already bandwidth bound) or thp_fault_fallback near zero and compact_stall flat (variance is not thp).

### E5: branch-free region-shrink ladder (1.0 h including build)
- runs: copy e1/src_ceil without the skip hook, change `FastMod(hc)` to fold the index into R bytes with a mask, no branch. rungs 103 GB (R0), 4 GB (R1), 128 MB (R2), 8 MB (R3), db 103 GB, T=32, all reads, 3 interleaved reps, output wrong by design. also T=1 on 10k reads for the latency-only reading.
- success: R0 minus R3 between 8% and 16% of wall, with R0 minus R1 (walks) reported as its own figure. this is the publishable decomposition.
- kill: R0 minus R2 under 5% at 103 GB: the lookup path is closed, state it as a stronger bounded negative and stop all memory-side ideas.

order rationale: E1 gates E2 and E3's interpretation, E2 gates the scanner build, E3 and E4 are the two byte-identical changes that could land a win in the window (E3 against the 38.6% scanner, E4 against the 25% load), E5 is the characterisation last because it cannot produce a speedup. total 4.5 h.

## summary (6 lines)

1. fact that reorders the plan: 8 GB wall (7.58 s) equals the 50 MB wall (7.93 s), so exposed memory is about zero there and the floor is cpu; at 103 GB exposed lookup memory is about 1.3 s of 12.25 s.
2. kill A's test B (it changes the key stream), keep the slope test; kill B's numactl budget (cannot gain more than about 1% at 8 GB), keep PGO and the vmstat load diagnostic; retract aligned buckets and smaller cells for this window.
3. publish the bounded negative: reuse profile, oracle ceiling, MLP saturation, double hashing cost, null -march, with the oracle recipe as the method.
4. oracle-ceiling method beats an analytic MLP model now; build the model only if a layout idea survives an oracle.
5. vote: E1 perf stat (0.5 h), E2 scanner slope test (1 h), E3 LTO+PGO (1.25 h), E4 loader cap and vmstat (0.75 h), E5 region ladder (1 h).
6. kill thresholds: branch-misses per base under 0.2 or slope under 5% ends scanner work; PGO under 2% ends build flags; loader gain under 0.2 s ends E4; R0 minus R2 under 5% closes the memory axis.
