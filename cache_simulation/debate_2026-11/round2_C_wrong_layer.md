# round 2, agent C: the question was at the wrong layer

position: the sniper study asked "which cache (size, associativity, eviction) is best for kraken2". kraken2 is not limited by what its caches retain. it is limited by how many dram round trips a random probe stream pays, and by how many of them overlap. so a cache-hierarchy study was always going to read as null, and the things that did move real runtime (S9, S10, S14, S16) all act on access pattern and layout. sources: round 1 reports A, B, C, plus plan_paper/s6_s15_speedup_report_2026-09-24.md and cache_simulation/measurements/*.csv. nothing run.

## 1. what the real hardware says about where time goes

all numbers are luna, 32 threads, 1.87M reads, from the s6 to s15 report and B's section 2 unless stated.

- stock to S19 on 103GB: 95.62 s to 20.08 s, 4.76x. on 8GB 2.31x, on 16GB 2.36x, on 50MB 1.88x. byte-identical output in all 16 cells.
- the 4-way software cache was ablated to zero (S6): 11.06 s and 14.48 s without it vs 11.10 s and 14.55 s with it, perf samples 174K vs 175K. the cache did not cause any of the gain.
- what did cause it, ranked by size on the big table:
  - S10 parallel pread load: 103GB 90.5 s to 34.5 s (a 56 s change). this is an io-layer fix, not a lookup fix.
  - S14 2 MB aligned table plus MADV_HUGEPAGE: 103GB 35 s to 13-20 s, 16GB 11.9 to 9.15 s (1.30x), 8GB 10.36 to 8.29 s (1.25x). pure tlb and page-fault effect. the table bytes and the probe sequence are unchanged.
  - S9 batched software prefetch: 103GB about 87 s to 76 s (1.14x). null on 8GB and 16GB.
  - S16 software-pipelined prefetch (scan batch n+1 before resolving n): 103GB 19.18 s to 17.21 s (-10%), 16GB -1.4%, 8GB tied.
  - S8 one reader across files: 50MB 15.6 to 11.1 s. pipeline barrier, no memory system content at all.
- null or tiny: S7, S11, S20 (prefetch batch size and ring buffer, K2_B 16 to 64: within 0.6% on all four dbs). S12, S15, S17, S18 each 1 to 4%.
- the pattern: every step that touched what is looked up (cache, associativity, eviction, hash mixing) is null on real hardware (S3.4, S4.0 hit rate 0.40% to 3.58% with no wall-clock effect). every step that touched how the probes reach memory (page size, overlap, parallel load) is a real win, and the wins grow with table size, 50MB smallest, 103GB largest. that is the signature of a dram-latency and tlb problem.
- supporting counters: real luna llc-miss rate 80.03% (T=1) to 83.87% (T=32) on 8GB, per B's saved perf stat. a cache that sees 80% misses on a hit-or-miss stream of mostly unique keys has nothing to evict wisely. the sim agrees: unique cache lines about equals lookups (C round 1 section 2e), llc hit 0.15 to 0.49% of loads in every cleanstart cell, hw associativity moves cycles 0.0 to 0.9%.

## 2. the ceiling argument

- S19 cpu profile on 50MB: NextMinimizer 38.5%, ClassifySequence 25.1%, GetAt 12.5%, PrefetchIndex 7.0%. lookup share 19.5%, so a free table gives at most 1/(1-0.195) = 1.24x on 50MB (B section 2, brief). any cache-hierarchy change can only act inside those 19.5%, and at 99% l1d hit and under 0.5% llc hit it acts on almost none of it.
- sim cross-check: marginal cost is about 297 instructions per base (C round 1 2e). most of kraken2 is minimizer scanning and compute, not memory, on small dbs. the cache layer cannot see that cost either.
- honest limit: the 19.5% is 50MB only. the big-db lookup share was never profiled (stage 0c of the trie brief is not run). on 103GB the load phase alone was about 55 of 90 s stock, and S14+S16 show lookups there are dram-bound. so the ceiling is higher on big dbs, but the lever that works is still latency overlap and page reach, not retention.

## 3. the layer where the cost sits

mechanism, from zero. a lookup hashes a 48-bit minimizer to a slot in a flat table (load factor 0.70, 1.07 hit lines and 1.32 miss lines per lookup, from the trie brief). keys are effectively random, so each lookup touches a random cache line out of 8 to 104 GB. the cost of one such access has two parts: a dram access (about 80 to 100 ns on a server, sim default 45 ns) and, with 4 KB pages, a tlb miss and page walk that is itself several dependent memory accesses. a 104 GB table is 27 million 4 KB pages against a 2048-entry l2 tlb (cleanstart cfg), so nearly every probe also misses the tlb. S14 removing most of that, 35 s to 13-20 s, is the proof the walk was a large share. the second lever is memory-level parallelism: one core can have roughly 10 to 12 outstanding misses (line fill buffers), and a serial probe-then-branch loop uses one. S9 and S16 restructure the loop so many probes are in flight, which is the same idea as AMAC and group-prefetching in the hash-join literature. S16 gained 10% on top of S9 only on 103GB, which says the remaining stall is the dram wait itself.

so the fruitful design space is:

1. access-pattern: batch size, software-pipelined stages (AMAC-style interleaving of several lookup state machines), prefetch distance, multi-socket numa placement of table and threads.
2. page reach: 2 MB vs 1 GB pages, hugetlbfs vs thp (S14 showed thp variance 13 to 21 s from fragmentation, itself a finding), -M mmap with 4 KB page-cache pages (never composed with S14: E1 not run).
3. layout: fewer lines per probe. bucketed or cuckoo-style tables (one line per lookup, bounded), a bloom or quotient prefilter that answers absent keys without touching the big table (misses cost 1.32 lines at load 0.70 vs a prefilter that fits in l3), double hashing (already compiled out behind -DLINEAR_PROBING, no measurement exists), 6-bit-per-organism cells (thesis 2). the b-trie brief's own prediction is that radix and trie variants lose on speed, 2 to 3 reads at best vs 1.07, and win on space (mphf plus fingerprint -23%, elias-fano -31%). that is a layout result, not a cache result.
4. hardware that exploits it: a near-memory or gather engine, a bigger tlb or a page-walk cache, a runahead or prefetch unit keyed on minimizer streams. these are the architecture ideas that follow from the data; an eviction policy is not.

## 4. what sniper can and cannot model for those levers

fidelity ratings are my reading of the configs and the round 1 reports. items marked verify are not confirmed by any log.

| lever | sniper can model it? | fidelity and caveat |
|---|---|---|
| dram latency and bandwidth | yes | one latency (45 ns) and a bandwidth cap, ddr4_2400 default, never calibrated to luna ddr5. no bank, row buffer or refresh detail. good for ratios across structures, poor for absolute cycles |
| tlb and page walk | yes, partly | the baseline address-translation scheme models l1/l2 tlbs and a page-table walk; cleanstart cfg sets 64-entry l1 and 2048-entry l2. page-walk and dram counters were checked once (iteration 2) and looked negligible at the 65536 spike. never validated against perf dtlb counters. page size can be set in the mmu scheme (verify which sizes). cannot reproduce linux thp fragmentation or fallback to 4 KB |
| memory-level parallelism | yes, coarsely | interval core with a rob window (meteor_lake_pcore). overlap of independent misses inside the window is modelled; real line-fill-buffer limits and mshr contention are only approximated (verify mshr counts in cfg). this is the lever most worth validating |
| software prefetch instructions | unknown, verify | frontend is an sde trace; whether a trace prefetch becomes a real fill that overlaps in sniper's memory model is not in any log. a 20-line microbenchmark (random probes, with and without prefetch, 1 vs 16 in flight) answers it in an hour |
| hardware prefetchers | no, in practice | never configured (prefetcher=none in flat-l3, others unknown). irrelevant for random probes, relevant for load phase |
| table layout (bucketed, cuckoo, prefilter, mphf, double hashing) | yes, as software | these are just different binaries or a standalone structbench, traced like any program. the sim sees the resulting access stream and the dram reads, so it can compare lines touched and overlap, but not run-to-run thp effects |
| io and parallel load (S10), pipeline barriers (S8) | no | all runs were -n 1 -p 1; the stock-to-S15 wins from pipeline, load and thread structure are outside the instrument (A section 4) |
| numa, atomics, multi-socket contention | no | no real multicore in any usable run; 2 of 14 four-core runs deadlocked |
| os effects (page cache, thp availability, exit tax 3.9 to 4.7 s) | no | not simulated |

consequence: sniper fits the layout, mlp and tlb-reach questions better than it fit the cache-capacity question, because those depend on the dram and tlb models and the interval window, not on llc capacity. but it is not yet validated for them. no sim cycle count was ever compared to perf on one binary (A open question 7). until the prefetch and tlb behaviour is calibrated against S9, S14 and S16 as known targets, a sim result there is a hypothesis.

a clean test of my position, using results already measured: run sniper on stock vs S14 vs S16 style traces at a table size large enough to miss the tlb. if the sim reproduces the direction and rough size of 1.25x to 2.7x (S14) and -10% (S16), the instrument can see this layer and the cache null was a choice of question. if it shows nothing, then the instrument, not the layer, is the limit, and B's position gains weight.

## 5. rebuttal to A: "the null is real, there is no reuse"

what I concede: A is right that the hardware associativity sweep is a genuine null in the sim, and the real-hardware cache null (S3.4, S6 ablation, commit 84436dd) independently agrees. unique lines about equal lookups. I do not claim there was a hidden cache win.

where A stops short: "no reuse" is a property of the access stream, and it is the reason the question was wrong, not a finding that ends the project. if a stream has no reuse, the next question is how to make the unavoidable misses cheap, and real hardware already answered that with 4.76x on 103GB without a single cache change. A reports the null as the result; I report it as the diagnosis. the same data say the right dependent variable is dram stall per lookup, not hit rate. A also leans on 10 to 500 reads; reuse could rise at production scale (C round 1 notes this cuts both ways), but even the best case is bounded by the 19.5% lookup share on small dbs.

## 6. rebuttal to B: "it was a modelling artifact"

what I concede: B and the auditor are right that many flaws are real. -n 1 gives one 1.1 MB nuca slice, S0 and the variants are different source lineages (instruction gap S0 minus 1way grows 50mb -2.4M, 8gb +16.4M, 16gb +25.7M, 103gb +34.1M), two S2 designs were mixed, icache was off, latency does not scale with size, and flat vs nuca moves cycles 17 to 31% with identical instructions. the sim 2x win is not usable, and the sim is unvalidated.

where B's argument fails as an explanation of "no positive result": fixing every artifact still leaves the real machine saying the cache is worth nothing. the S6 ablation and S3.4 were measured on real luna with none of these flaws, and they are null too. a corrected simulator would have to find a win that real hardware does not show at the sizes it can build. B's best surviving point is that the real 105 MB llc with 96 cores shared was never simulated, so an llc-topology-aware idea was untested rather than refuted. I accept that for thesis 1 specifically. but that is a point about one candidate, not an explanation of why every result was flat. also, artifacts in B's list cut both directions: the unvalidated 45 ns dram is the same parameter that decides whether a layout study is trustworthy, so B's own fix list (measured latency, calibration against perf) is a prerequisite for my track too.

## 7. what I do not know and could be wrong about

- big-db lookup share of cpu (unmeasured). if it is 60 to 70% then lookup layout has a ceiling of 2.5 to 3x; if it is 25% then my claim shrinks to 1.3x.
- whether sniper overlaps traced software prefetches (unverified).
- whether S14's gain is tlb reach or fewer page faults at first touch (the report says "tlb / page faults"; they were not separated).
- how -M composes with S14 (E1 not run).
- no sim cycle count has been calibrated to perf. every sim claim above is conditional.
- thp variance (13 to 21 s) means 103GB numbers for S14+ are ranges, so S16's 10% (3 reps) is near the noise there.

## 8. proposed next steps if this position wins

1. microbenchmark in sniper: random probes into a 1 to 8 GB array, with 1 vs 16 independent chains and with and without prefetch, 4 KB vs 2 MB pages. confirms what the instrument sees. about 1 day.
2. profile big-db lookup share with perf on 8GB (stage 0c of the trie brief, about 2 hours).
3. reproduce S14 and S16 direction in the sim as a calibration check (section 4).
4. then compare candidate layouts (bucketed, prefilter, double hashing, mphf) in structbench and sniper by dram reads per lookup and overlap, not by hit rate.
5. keep one cache-hierarchy run as a characterization result: full 105 MB llc, one lineage, real latency. a clean null with a mechanism is publishable.

## summary

1. real data: every cache change is null, every pattern, page-size and load change is real (S10, S14, S9, S16; 103GB stock to S19 is 4.76x with the cache ablated to zero).
2. the cache layer can only act on 19.5% of cpu on 50MB (ceiling 1.24x), and llc miss is 80 to 84% on 8GB with near-unique keys.
3. the cost is dram latency plus tlb walks on random probes into a 8 to 104 GB table; the levers are overlap (mlp, prefetch, amac), page reach, and fewer lines per probe.
4. sniper models dram, tlb walks and overlap within the rob window, coarsely and uncalibrated; it cannot model thp, io, numa, atomics or threading.
5. whether sniper executes traced software prefetch is unverified and decides how much of this track it can serve.
6. A is right that there is no reuse, but that is the diagnosis of the wrong question, not the end of it.
7. B is right that the sim has artifacts, but real-hardware nulls (S6, S3.4) remove the idea that fixing them would reveal a cache win; the untested llc-topology idea is the one exception I grant.
8. weakest point of my case: big-db lookup share and sim calibration are unmeasured, so test S14 and S16 in the sim first.
