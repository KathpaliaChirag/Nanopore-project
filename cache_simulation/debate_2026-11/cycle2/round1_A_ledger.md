# cycle 2, round 1, agent A (ledger): what is established about the kraken2 cache, 2026-11-23

sources read: debate_2026-11 rounds 1 to 7, e1/analysis_8gb_T1.txt, e5/sweep.csv, e5/ab_103.txt, command_log.md headers and the size-sweep and correction sections. read-only. every ratio below was recomputed from the source table, not copied. tags: [L] measured on luna, [S] sniper simulator, [T] offline simulation over a measured luna trace, [E] estimate or arithmetic on other numbers.

## 1. ledger of established facts

### reuse profile (8GB db, S19, T=1, 105k reads, 12,237,762 lookups) [L trace, T analysis]
1. hit share of lookups 86.75%. source e1/analysis_8gb_T1.txt, round5. [L]
2. unique slots 2,270,742 = 18.56% of lookups, so global repeat rate = 1 - 0.1856 = 81.44%. matches the file's 0.8144. [L]
3. coverage of lookups by hottest slots: top 16K 12.5%, 64K 24.2%, 262K 55.8%, 1M 90.0%. [L]
4. top 1024 slots cover only 7.6%, so there is no tiny hot set. [L]
5. reuse distance (distinct slots between uses): the 2^17 to 2^21 buckets hold 0.1046+0.1554+0.2302+0.2161+0.0611 = 76.7% of repeats, the "about 77%" in round5. only 10.1% of repeats are closer than 2^12 slots (cum 0.1006). [L]
6. windowed dedup (share of lookups removable inside non-overlapping windows): 8.2% at 10K, 15.4% at 100K, 43.7% at 1M, 75.8% at 10M. [L]
7. unique 64 B lines per lookup 0.184. [L]
8. tracer is cheap and correct: 15.4 s vs 14.9 s (+3.4%), output identical (101,922 of 104,980 classified = 97.09%). [L]
9. caveat on 1 to 7: one 105k-read sample, one db, T=1. nothing else was traced.

### hit rate of an N-entry cache on that trace [T over L trace]
| N | LRU (full) | 4-way LRU | Belady | 4-way / LRU | LRU / Belady |
|---|---|---|---|---|---|
| 4096 | 8.19% | 8.17% | 17.92% | 0.998 | 0.457 |
| 16K | 10.39% | 10.39% | 28.01% | 1.000 | 0.371 |
| 64K | 18.94% | 18.49% | 44.06% | 0.976 | 0.430 |
| 262K | 40.11% | 38.94% | 66.60% | 0.971 | 0.602 |
| 1M | 76.46% | 71.04% | 81.44% | 0.929 | 0.939 |
| 4M | 81.44% | 81.10% | 81.44% | 0.996 | 1.000 |

10. Belady at 1M and 4M equals the repeat rate 81.44%, so 81.44% is the ceiling for any cache on this trace. [T]
11. LRU needs 262K entries for 40% and 1M for 76%. at 16K entries the best realistic policy (LRU) gets 10.4%, the optimum 28.0%. [T]
12. 4-way loses at most 2.9% relative to full LRU up to 262K, 7.1% at 1M. associativity is not the constraint, capacity is. [T]
13. entry size for capacity arithmetic: 262K x 24 B = 6.3 MB and 1M x 24 B = 25 MB per thread (round4_B). at 16 B it is 4.2 MB and 16.8 MB. 262K is above a 2 MB private L2, so a cache with that hit rate lives in L3 (about 30 ns per round4_B). [E]
14. break-even: a cache with probe cost Tp beats a miss path Td only if h > Tp/Td. round4_A put h* near 20% in the S16 regime against a small-cache h of 10.65%, below break-even. [E, from round4]

### lookup share of cpu, perf record, S19 [L]
| db | T | reads | PrefetchIndex | GetAt | lookup total | note |
|---|---|---|---|---|---|---|
| 8GB | 1 | 105k | 7.08% | 0.66% | 7.74% | kernel load ~20%, so ~15% of user time |
| 16GB | 1 | 105k | 5.98% | 0.94% | 6.92% | kernel load ~45% |
| 103GB | 1 | 105k | 1.13% | 0.58% | 1.71% | kernel load ~65%, ~450 user samples |
| 103GB | 32 | 1.87M | 9.7% | 6.7% | 16.4% (report prints 16.3%, rounding) | NextMinimizer 19.0, ClassifySequence 17.0, HLL insert 3.3 + merge 1.2 |

15. the T=1 rows are diluted by database loading and are not production shares. at 103GB the share moves from 1.7% (T=1) to 16.4% (T=32), a factor of 9.6, so T=1 shares cannot be carried to T=32. no T=32 profile exists for 8GB or 16GB.
16. GetAt alone is 0.58% to 0.94% at T=1 and 6.7% at T=32 on 103GB. the stall shows up only under T=32 contention at 103GB.

### double hashing (structbench, 4-byte cells, load 0.70, S16-style prefetch, 13% misses) [L]
| table, T | linear ns | aligned ns | double ns | double + prefetch ns | double / linear |
|---|---|---|---|---|---|
| 8GB, 1 | 28.5 | 36.1 | 65.5 | 56.4 | 2.30 |
| 8GB, 32 | 82.5 | 72.4 | 151.0 | 130.6 | 1.83 |
| 32GB, 1 | 35.1 | 38.1 | 79.1 | 66.0 | 2.25 |
| 32GB, 32 | 49.2 | 63.6 | 125.0 | 112.1 | 2.54 |

17. lines per lookup, hit / miss: linear 1.073 / 1.316, double 1.720 / 3.333, aligned 1.016 / 1.154. double vs linear is +60.3% hit (1.720/1.073) and +153.3% miss (3.333/1.316). round4 quoted +61% / +152% from rounded values; use the exact ones. [L, counted]
18. prefetching both probes recovers 13.9% (65.5 to 56.4), 13.5% (151.0 to 130.6), 16.6% (79.1 to 66.0) and 10.3% (125.0 to 112.1). range 10.3% to 16.6%, slightly wider than the "10% to 15%" in round5.
19. line-aligned shows no reliable win: faster by 12% at 8GB T=32, slower by 29% at 32GB T=32. [L, noise level]
20. the gcd risk is real: failed_inserts was 1 at 2^26 and 2^31 cells and 0 at 2^33 (capacities 2^k-1 divisible by 3). [L]
21. these are microbenchmark timings. nothing ran kraken2 with -DLINEAR_PROBING removed on a rebuilt db, and no false-positive measurement exists for double hashing.

### hll guard (E5) [L]
22. 103GB, T=32, 1.87M reads, 4 interleaved reps: stock 19.96 to 20.45 s (mean 20.275), guard 12.24 to 12.48 s (mean 12.375). ratio 20.275/12.375 = 1.638. user cpu 334 to 268 s (ratio 1.244).
23. control: stock without --report 12.41 / 12.29 s, guard 12.4 s. the whole gap is the report path. no gain without --report.
24. size sweep (252 runs, median of 3, 7 read counts x 4 dbs): at 1.87M reads 50MB 1.06x, 8GB 1.15x, 16GB 1.17x, 103GB 1.62x (19.73/12.21 = 1.616). at 500k: 1.06, 1.12, 1.16, 1.35. no cell slower. guard equals the no-report floor in every cell.
25. correctness: per-read output byte-identical in 28 of 28 cells, sorted report identical, tied-sibling line order in plain --report differs (a behaviour change that needs sir's decision).
26. caveats: one machine, warm cache, uncommitted S19 tree, upstream stock not checked. the exit-tax cause is claimed, not separately timed.

### other measured facts that bound the cache question
27. stock-to-S15 speedups (1.8x to 4.4x at 1.87M reads) were not caused by the 4-way cache; ablation 11.06 s vs 11.10 s. [L, from memory note and round4_B; the source table is outside the folder I read]
28. hardware LLC associativity 1 to 30 ways: spread 0.32% at 500 reads, 0.86% at 100 reads. [S, single run per cell, one cold 1.1 MB slice]
29. old sniper results: 4-way cycles vs S0 are 0.546x, 0.488x, 0.507x on 8/16/103GB (28.3/51.8, 29.6/60.7, 47.8/94.3). arithmetic correct but instruction counts differ 25% to 33%. [S]
30. S4.0 hashmix fix gave an 8.9x hit-rate change in the old index with no wall-clock effect (memory note). [L]

## 2. claims in the repo that are superseded or contradicted

| # | claim | where | status |
|---|---|---|---|
| a | "no reuse", "near-zero reuse", "almost no data reuse" in this workload | command_log.md ~line 2088, round1_C | contradicted by items 2 and 3 (81.4% repeats). the story page already says so; command_log line 2088 is not annotated. nuance: for 1 to 2 MB caches reuse really is 8% to 10% (item 11), so the claim was true for small caches and wrong as a statement about the workload |
| b | "4-way about 2x faster than S0 on big dbs" (sniper) | final_fair_batch, round1_A E2 | superseded: binary-lineage artifact (instruction counts differ 25% to 33%), and on luna the 4-way cache gave 11.06 vs 11.10 s. old binaries also had a broken index hash (item 30) |
| c | hardware associativity has no effect | hw_assoc_sweep | narrowed: one cold-window slice, 1.1 MB, single run per cell. says nothing about luna's 105 MB LLC |
| d | S2Entry is 16 B | command_log ~1596 | contradicted for the original S2, which is 24 B (round1_C: 4096 sets, static thread_local). 16 B holds only for the sizepin binaries. the size in the S19 tree is unverified; a 4-way set is 64 B or 96 B, which decides the "one line per set" argument |
| e | "no positive result" at the cache | round1_C | partly a statement about the instrument (low-reuse workloads, 1 to 2 MB slice, confounded binaries), not about the idea |
| f | eviction sweeps could give a noteworthy speedup at 8GB | week6plan, round3_A | bounded: at T=1 gain <= 0.3894 x 0.0774 = 3.0% (4-way LRU 262K) to 0.666 x 0.0774 = 5.2% (Belady). valid only at T=1, see section 3 |
| g | pinning eviction +25.2% win; 22x slowdown cliff; size=65536 spike magnitudes (+4.4% / +10.2%) | older log and memory | already superseded in the log by S4.0 (+25.2% to -3.9%), S3.0 / S3.3 (the cliff) and the 21:52 correction (+2.5% / +6.0%). do not cite the older numbers |
| h | double hashing as a speed candidate, "shrink the false-positive cliff" | CLAUDE.md thesis 2, round1_B | superseded for speed: 1.8x to 2.5x slower per lookup (items 17, 18). still open for false positives only |
| i | "the lookup layer is capped at 3 to 5%" | round5 verdict | contradicted at production scale: at 103GB T=32 lookup is 16.4%, and the HLL path was 3.3 + 1.2 = 4.5% of samples and 7.9 s of 20.3 s. the cap holds only for 8GB T=1 |
| j | E2 (amac) gate of 25% lookup share, 103GB "28% of user time" | round5 | that 28% came from a ~450-sample T=1 profile dominated by db load. the T=32 profile gives 16.4% of all samples. the gate was never computed on T=32 user time |
| k | "double hashing needs only a flag flip" | memory, round1_B | incomplete: it needs a rebuilt db, and the gcd risk (item 20) means it is not safe as shipped |
| l | noatomics binaries are comparable to the rest of the sweep | round1_C, memory | noatomics binaries were never benchmarked and contaminate older sweeps |

## 3. what has NOT been measured that a cache design depends on

1. reuse at T=32, per thread vs shared. all trace data is T=1. a per-thread cache sees 1/32 of the reads, so reuse distances of 2^17 to 2^21 may mostly vanish; a shared cache needs atomics or sharding. no number exists for either.
2. trace at 103GB and at 1.87M reads. the 81% repeat rate is from 105k reads on 8GB. a bigger db changes hit share and slot ids; more reads should raise the repeat rate. not measured.
3. any trace for 16GB or 50MB.
4. held-out generalisation of a hot set. top-262K covers 55.8% on the trace used to pick it. there is no train-on-file-A, test-on-file-B run, so a static or learned hot set is untested. 16 fastq files exist, so this is cheap.
5. miss-path cost split. no measurement of the time of a cache hit vs a table lookup at T=32, nor of the cache probe cost Tp on luna at 6.3 MB or 25 MB per thread. h* in item 14 rests on estimates (4 ns L2, 30 ns L3, 90 ns dram); round4_B says Td must be the post-S16 measured value, which was not measured.
6. lookup share at T=32 for 8GB and 16GB, and lookup share at 103GB after the HLL fix (the guard drops user time from 334 s to 268 s, so the share rises).
7. whether the 16.4% is stall or work. PrefetchIndex 9.7% is mostly instruction cost of computing and issuing prefetches, which a cache removes only if its check comes before the prefetch. no split.
8. what a hit really saves: the minimizer is computed anyway (NextMinimizer 19.0%), so only the probe is skipped.
9. LLC contention at T=32: 32 threads x 6.3 MB = 201 MB vs 105 MB per socket (memory note). per-thread caches at 262K entries would evict db lines. never measured on luna; sniper used one 1.1 MB slice.
10. end-to-end double hashing: structbench only, no rebuilt db in kraken2, no false-positive measurement.
11. entry size in the S19 tree (16 vs 24 B).
12. variance: E1 and E3 are single or best-of-3 runs on a shared machine (about 65 users); round5 says differences under 15% are noise. E5 used 3 to 4 reps and is fine.
13. a real cache implementation timed on S19 at T=32 and 103GB: none exists. the bound below is arithmetic.
14. wall-clock budget split: wall 12.2 s at 103GB includes about 3.0 s of load and exit (the 10-read run is 3.0 s), so classification is about 9.2 s. a cpu share does not map one-to-one onto wall.

## 4. best-supported upper bound on any cache gain at production scale

rule: gain <= hit rate x lookup share. hit rate <= 81.44% (item 10, from the 8GB T=1 trace). a hit costs zero, which no real cache achieves.

103GB, T=32, 1.87M reads (lookup share 16.4% of perf samples, item 15):
- ceiling with a free infinite cache: 0.8144 x 0.164 = 13.4% of samples (13.3% with the report's rounded 16.3%).
- after the HLL guard the lookup is a larger share of a smaller total. if the samples are user time: 0.164 x 334 = 54.8 s, guard user is 268 s, share 20.4%, ceiling 0.8144 x 0.204 = 16.6%. if samples include sys (334+105 = 439 s; guard 268+105 = 373 s): 0.164 x 439 = 72.0 s, share 19.3%, ceiling 15.7%. so the ceiling is 13% to 17% of cpu.
- cpu to wall: guard wall 12.2 s. at 16% of cpu, best case wall about 12.2 x (1 - 0.16) = 10.2 s, if the cpu share maps onto wall (it does not exactly, see section 3 item 14).
- realisable at 262K entries on the measured hit rates: 4-way LRU 0.3894 x 0.164 = 6.4%, full LRU 0.4011 x 0.164 = 6.6%, Belady 0.666 x 0.164 = 10.9%. on the post-guard share (about 20%): 7.8%, 8.0%, 13.3%.
- all of these ignore the cache's own probe cost (section 3 items 5, 8), per-thread dilution (item 1) and LLC contention (item 9). each only lowers the gain. best supported bound for a per-thread cache at 103GB T=32 is 13% to 17%; a realistic gain is well under half of that, and that part is not measured.

8GB, T=32 (no lookup share measured):
- T=1 share 7.74%: ceiling 0.8144 x 0.0774 = 6.3%, Belady 262K 5.2%, 4-way LRU 262K 3.0%. this is the round5 "3 to 5%".
- on T=1 user time (15% share, kernel load excluded): 0.8144 x 0.15 = 12.2%, Belady 262K 10.0%, 4-way 5.8%. closer to the 103GB T=32 figure.
- the T=1 to T=32 share growth at 103GB was 9.6x, so the 8GB production share may be far above 7.7%. the 8GB production bound is not established: 6% to 12% is a bracket from T=1 numbers only. cost to settle it: one perf record of 8GB at T=32, 1.87M reads, minutes.

comparison with measured wins: the HLL guard saves 7.9 s of 20.3 s at 103GB (39% of wall, 1.64x) and about 1.1 s of 8.6 s at 8GB (13%). the most a cache can do (13% to 17% at 103GB, 6% to 12% at 8GB, before any cost) is smaller than the guard at 103GB and comparable at 8GB. any cache result must be measured against the guard binary, not stock.

## summary (8 lines)
1. reuse is real: 81.4% of lookups repeat a slot, but 77% of repeats are 2^17 to 2^21 slots apart, so only caches of 262K entries or more (6 to 25 MB per thread) capture it.
2. hit rates at 262K: full LRU 40.1%, 4-way 38.9%, Belady 66.6%; at 16K entries LRU gets 10.4% and Belady 28.0%. associativity costs under 3% relative; capacity is the constraint.
3. lookup share: 7.7% at 8GB T=1, 1.7% at 103GB T=1 (load-dominated), 16.4% at 103GB T=32; no T=32 profile at 8GB or 16GB, and T=1 shares do not carry over (9.6x change at 103GB).
4. double hashing: 1.8x to 2.5x slower per lookup (1.72 hit / 3.33 miss lines vs 1.07 / 1.32), prefetching recovers 10% to 17%, a gcd risk exists; microbenchmark only.
5. hll guard: 1.64x at 103GB T=32 (20.3 to 12.4 s), 1.62x in the sweep, 1.17x / 1.15x at 16GB / 8GB, never slower, byte-identical output, report tie order changes.
6. superseded: "no reuse", the sniper 2x win, 16 B entry for original S2, "lookup layer capped at 3 to 5%" at production scale, old pinning and cliff numbers.
7. unmeasured: T=32 reuse (per thread vs shared), trace at 103GB and 1.87M reads, held-out hot set, miss-path cost split, 8GB T=32 share, LLC contention from 32 per-thread caches, post-guard share.
8. upper bound: 0.8144 x 0.164 = 13% of cpu at 103GB T=32 (about 16% after the guard), 6% to 12% at 8GB from T=1 shares; realisable (262K LRU) 6% to 8% at 103GB, before probe cost, dilution and contention.
