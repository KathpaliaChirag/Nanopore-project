# round 4, agent C: attacks, retractions, final vote

read all nine files in this folder. nothing run, no luna. i checked plan_paper/ for prior work on latency hiding (see section 2). every number below is either quoted from a round file or marked as my guess.

## 1. attacks on A and B

### A rank 1, belady plus all-policy trace replay
- the idea is sound and cheap, and i adopt it (it is step 1 of my vote). the attacks are on how its result gets used.
- flaw 1, the kill rule uses the wrong Td. A's h* = Tp/Td uses Td = 90 ns, the cost of a full dram miss. after S9 and S16 the lookup is already overlapped, so the saving per cache hit is the remaining exposed latency, not 90 ns. S16 took 103GB from 19.18 s to 17.21 s, so most of the stall is not exposed. a hit that skips a prefetched, overlapped access saves less, so true h* is higher than 33%. this makes the kill easier to trigger, which means a "dead" verdict is almost guaranteed and the experiment cannot fail. state it as a bound on h, and drop the claim that it "proves" no policy wins on wall time.
- flaw 2, the window problem. M5 says 90.7% of 351.8M lookups are repeats globally, but A's replay uses a 3M to 30M window, where the repeat share is 54% at T=1. belady on a window cuts off every repeat whose gap exceeds the window, so the bound is pessimistic by construction, and 81% of repeats sit at 1e4 to 1e6, near the window edge. run at least one full-run trace (351.8M x 8 B is about 2.8 GB, fine) or the bound is not a bound.
- flaw 3, T=32. per-thread belady on a 1/32 slice of the stream is far lower than shared belady. kraken2's cache is thread-local, so per-thread is the real design, but then the 90.7% global repeat number is irrelevant to it. A mentions both; the plan must report both and not mix them.

### A rank 2, 16-way simd set with srrip and victim slot
- predicted gain 1 to 4% on 8GB, noise band 0.6%, three days. my objection: the S6 ablation already showed the 4-way cache was not the cause of the speedups, and S3.4 found S0 equal to the S2 baseline equal to S2 final everywhere. the prior that a cache variant moves wall time by more than 1% on top of S16 is low, and A's own arithmetic (10.65% hit x exposed Td minus L2 access) goes to about zero once Td is the exposed latency from flaw 1. cost-to-chance is the worst of the three. it is also the item the user already parked as week7plan item 5. do it only if step 1 shows belady at 16K entries above 25%.

### A rank 3, static hot set
- A predicts the top 64K keys cover 8 to 15% and sets the pass bar at 25%. by A's own prediction it fails. its cost is nearly zero because the coverage curve falls out of rank 1 for free. keep as a free output, not as a separate experiment.

### B rank 1, sort-and-partition batched lookup
- B's own text undercuts it: S14 removed most walks, S16 overlapped most waits, and two random queries almost never share a line out of 1.6e9. what is left is dedup, and dedup is exactly the repeat rate that A's trace measures. so B's "stage 0" and A's rank 1 are one experiment, and B's 4 to 5 day prototype is the only extra part.
- a missed cost: batching millions of lookups per worker breaks the streaming read pipeline and needs about 12 to 16 B x 1e7 = 120 to 160 MB per thread (B's per-lookup figure times B's batch size), so at 32 threads that is 4 to 5 GB of extra buffers and a second full-memory pass that can itself cost a few percent. that eats a 5% gain.
- a missed benefit: dram row-buffer locality. partitioning by slot bits puts consecutive probes in the same 8 KB dram row. this is not a line or page effect, so B's "share a line" arithmetic misses it. it is plausible, unmeasured, and the one reason the prototype could beat B's own 1.05 prediction.

### B rank 2, structbench of aligned vs linear vs double hashing
- double hashing at +60% (hit) and +150% (miss) lines is arithmetic, so the experiment mostly confirms a textbook result. its value is the aligned-bucket number and the measured ns, not the double-hashing prediction. good value for two to three days anyway because it gives thesis 2 a number.
- flaw, it measures a 64 GB random array. real kraken2 hit mixes are not 0/50/100%; the hit rate per db is the missing weight. take the lookup hit fraction from the step 1 trace instead of guessing 50%.
- flaw, "B1.1 needs zero new code" (earlier memory) is true for the binary, but a double-hashing db cannot be read by a linear-probing binary, so a real end-to-end test needs a db rebuild. the 8GB db rebuild time is unrecorded in what i read.
- flaw, a 64 GB array needs at least that much free ram on luna. unknown to me, so prerequisite.

### B rank 3, mphf (pthash) or elias-fano
- 4 to 6 days for a standalone with a predicted 1.3 to 2x slower lookup. cannot be a wall-clock win by B's own prediction. it is a space point, and sir's thesis is "smaller database". so it has value but not in a 2-week window with a 4 to 6 day standalone and an unmeasured key-dump step: kraken2 build computes lca values per key, so exporting 1.4e9 (8GB db) keys with values is itself a patch. excluded from the vote, kept as reserve.

## 2. my own top 3, defend or retract, and what is genuinely new

checked: plan_paper/ and dorado-kraken-research docs for "AMAC", "coroutine", "interleav", "state machine" in the S6-S15 report, next_steps plan, the next_speedups research brief and the S16 explanation: zero hits. round1_B and the S16 row say S16 is "scan batch n+1 before resolving n", a one-batch software pipeline. a wider grep for "S16" and "prefetch" returns many hits, all about S9/S16 themselves. so the honest claim is: i did not find AMAC-style per-lookup state machines or deeper interleaving in the repo. that is "not found", not "never done".

- my exp 1, sniper prefetch/hugepage gate. retract as a top-3 item. it tests the instrument, and the user wants a positive result on kraken2. it is worth 1 to 2 days only if sniper work continues. S9, S14, S16 and the prefetch microbenchmark are not new (they exist on real luna); only the sniper side was untested.
- my exp 2, CAT sweep. downgrade. it needs root and cat_l3, both unverified, and my own prediction was flat curves for 8GB and above. its one live outcome (50MB db sensitive to llc size) is a bounded characterisation for thesis 1. keep as an opportunistic parallel item, not in the four.
- my exp 3, trace plus fitted mlp model. retract the model part. it needs 3 to 4 constants fit to four runtimes, then a held-out check; with luna's 13 to 21 s thp noise at 103GB, 15% held-out error means little. keep only the probe logger and reuse-distance pass, which is now step 1.
- my AMAC idea (section 5 of round 3). defend, and it is genuinely new in this repo, with caveats:
  - the case for it: lookups have variable chain length (1.07 hit, 1.32 miss lines per lookup at load 0.70). a lockstep batch waits for its slowest member. the 32% of misses that cross a line pay a demand miss for the second line after the S16 prefetch covered only the first.
  - the case against: S16 gained 10% at 103GB, 1.4% at 16GB, 0 at 8GB. the headroom beyond S16 is bounded by what dram latency is still exposed, and i have not measured that. kocberber's 2.3x was over naive baselines, not over software pipelining. the 5 to 15% at 103GB is my guess, and 16GB and below will see roughly nothing. so it is a big-db-only result.
  - a cheap first check that makes the new work smaller: sweep S16's batch depth, and add a prefetch of the next line when the probe start is at cell 12 to 15 of the line. half a day. if that alone gives 2%, AMAC is worth writing; if nothing moves, the exposed latency is gone and AMAC is dead before it costs 3 days.
  - the c++20 coroutine route needs a compiler flag change on luna's gcc, unverified. hand-written state machine avoids it.

## 3. final vote

dependencies in short: 1 has no dependency, 2 depends on 1 only for the profile, 3 is independent, 4 depends on 1.

### 1. T0, probe trace plus big-db profile plus offline analysis (2 days)
- why first: it is the shared input of A rank 1 and 3, B rank 1 stage 0, and my model idea, and it prices every ceiling in B and C. it also measures the one thing everyone flagged as unmeasured: big-db lookup share of cpu (round 3 B, C).
- luna: S19 binary, 8GB db (and 103GB for the profile only), reads at the 1.87M count, flags the standard S19 ones plus -M off. patch: append the slot index (8 B) per probe to a per-thread buffer, flush at exit; also log hit or miss. runs: T=1 on a 3M window and one full pass, T=32 per-thread files. also `perf record` or `perf stat` on stock S19 at 8GB and 103GB for lookup share (about 2 hours, needs perf permission).
- offline (a small C++ file built on luna; the windows box has no compiler): belady, lru, 2-touch, srrip, per-2MB-region and per-8KB-row sharing, coverage of top 16K, 64K, 262K keys, dedup at batch 1e6 and 1e7.
- success: a full table of belady h by cache size on the full-run trace, both per-thread and shared, plus lookup share of cpu at 103GB. noteworthy if either belady at 64K entries per-thread exceeds 25%, or dedup at batch 1e7 removes 15% or more of lookups (opens steps 2 and 4 with a real ceiling).
- kill: if belady at 262K per-thread is under 20% and dedup at 1e7 is under 10%, publish this as a bounded negative ("no retention or batching policy can win"), stop eviction work, and spend the days on steps 2 and 3.
- honest label: this is a characterisation. it cannot itself make kraken2 faster.

### 2. S16 headroom check, then AMAC variant (0.5 day check, then 3 to 4 days)
- depends on: 1 for the lookup share (if lookup is under 30% of classify at 103GB, the ceiling is small, stop).
- luna: S19 binary and a rebuilt variant, 103GB and 16GB dbs, 1.87M reads, 32 and 64 threads (the 64-thread point is S0's best), 5 alternating reps in one session (the same binary was 23% faster on 2026-10-21 than 2026-09-24, so only same-session comparisons count), classify time and `perf stat` cycles, dtlb walks, plus output sha256 against S19 on all runs.
- check: S16 batch depth sweep and next-line prefetch on probes starting at cell 12 to 15. then AMAC: a fixed pool of 16 to 32 in-flight lookup slots, each a state (hash, probe line k, resolve), refill a slot when it finishes.
- success: at least 5% classify time at 103GB and no loss at 16GB, byte-identical, outside the 13 to 21 s thp band (so alternating reps, paired differences, not absolute).
- kill: under 3% at 103GB in the check phase, then stop after half a day; under 3% after the full build, stop and write it up as "S16 already extracts the mlp".
- honest label: the only item here with a real wall-clock chance; my probability of a 5% or better result is about 30 to 35 percent. guess, not measured.

### 3. structbench: linear vs line-aligned buckets vs double hashing (2.5 days)
- independent. luna: a one-file C++ microbench, no kraken2 binary. arrays of 4 B cells at load 0.70, size at least 32 GB (64 GB only if free ram is confirmed), random 48-bit keys, hit mix taken from step 1 (fallback 0, 50, 100%), 1 and 32 threads, S16-style batch-16 prefetch, madvise 2MB pages. record ns per lookup, lines per lookup (software counter, cross-checked with perf llc loads), 3 reps.
- success: measured lines per lookup within 10% of the arithmetic (1.07/1.32 linear, 1.72/3.33 double), and a ns per lookup ratio for double hashing at 32 GB that is a single number. noteworthy positive if aligned buckets save 8% or more of ns at 32 GB, because that justifies a db rebuild.
- kill: if the aligned-bucket gain is under 3% at 32 GB, drop it and keep the double-hashing number as the thesis 2 trade-off result. the double-hashing result stands whichever way it goes.
- honest label: mostly a clean characterisation for thesis 2 (a cost the false-positive cliff fix has to pay), with a small chance of a layout win.

### 4. batched dedup and partition prototype (4 to 5 days, gated by step 1)
- runs only if step 1 shows dedup at batch 1e7 removing at least 15%, or row/region sharing that predicts at least a 5% gain. otherwise the slot is given to the opportunistic CAT sweep (needs root and cat_l3, see prerequisites) or to the 16-way simd item.
- luna: S19 plus a two-pass batch lookup per worker (collect minimizers, radix-partition by top slot bits, probe region by region with the S16 pipeline inside each partition, restore read order by id), 103GB and 16GB, 1.87M reads, 32 and 64 threads, 5 alternating reps, sha256 vs S19.
- success: 5% or better classify time at 103GB net of the extra pass and buffers (about 4 to 5 GB at 32 threads by my arithmetic in section 1).
- kill: under 3% at 103GB, or a memory increase that breaks the 103GB run.
- honest label: likelier null than win (B itself predicts 1.05 to 1.2 at best); my guess is 15% chance of 5% or better.

## 4. prerequisites i cannot verify, to check before day 1

- perf permission on luna (perf_event_paranoid) and the CPU model name.
- free ram for step 3 (32 or 64 GB array) and for step 4 buffers.
- gcc version on luna (c++20 coroutine option only).
- whether S19's source tree is clean and buildable now, and whether the 8GB db rebuild time is on record.
- thp state and whether the machine is quiet; compare only inside one session.
- root and `cat_l3` in /proc/cpuinfo, only for the CAT fallback.
- the earlier next_steps plan E1, E3, E5 may still be unrun (that file was uncommitted when memory was written). E3 (-march=native, LTO, PGO) costs about 2 hours and could beat step 2 on expected value; i could not tell whether it has been run, so check the command log first.

## 5. order and timing

day 0 to 0.5: prerequisites. days 1 to 2: step 1 and, in parallel on a different thread count slot, step 3's code. day 3: S16 headroom check. days 4 to 8: AMAC if the check passed. days 9 to 13: step 4 if gated in, otherwise write-up. step 3 runs whenever the machine is idle between the others.

## summary of my vote

1. first, the probe trace plus big-db lookup-share profile and offline belady/dedup (2 days): characterisation, decides the rest, cannot itself speed anything up.
2. second, S16 headroom check then AMAC variant (about 4 days): the only real wall-clock shot, big-db only, about 30% chance of 5% or better, genuinely not found in the repo.
3. third, structbench of linear vs aligned vs double hashing (2.5 days): a clean number for thesis 2, small chance of a layout win.
4. fourth, batched dedup/partition prototype, only if step 1 shows 15% dedup (4 to 5 days); otherwise CAT or nothing.
5. dropped: 16-way simd/srrip (expected near zero after S16), mphf (a space point, too long), sniper gate and fitted mlp model (instrument work, not a result).
6. biggest caveat: every ceiling rests on 19.5% lookup share measured at 50MB only; step 1 measures it on the big dbs and may change the whole ranking.
