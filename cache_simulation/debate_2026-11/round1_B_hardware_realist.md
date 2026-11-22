# round 1, agent B (hardware-realist): what has actually been measured

date of this read: 2026-11-22. read-only pass over cleanstart/, plan_paper/, planning/, cache_simulation/ and dorado-kraken-research/docs/meeting_minutes.md. nothing was run, luna was not touched. every ratio below was re-derived from the csv or table named next to it. tags: [csv] a measurements file, [log] a command_log or report, [arith] my arithmetic, [guess] estimate, [UNCLEAR] not found in repo.

---

## 1. cleanstart baseline

### what it is (README.md, command_log.md steps 0-16)

- started 2026-09-19. one question: which L1d / L2 / L3 size and associativity is best for kraken2.
- binary S0 only (stock, no software cache). the software cache is out of scope here.
- reads: first 10, 50 or 100 reads (nested prefixes) of one 104,980-read sup fastq. bases: 372,413 / 2,209,336 / 5,262,723 [log step 3]. so 100 reads is about 14.1x the bases of 10 reads, not 10x [arith: 5,262,723 / 372,413].
- dbs: sample_targeted (50 MB), standard_8gb, standard_16gb.
- sniper detailed mode, no fast-forward. config = laptop.cfg (Ryzen 7 5800H, Zen 3) plus cleanstart_laptop.cfg (icache modeling on, L1 TLBs 64-entry fully associative, L2 TLB 2048 entries 8-way).
- cores 1, 4, 8 via `classify -p N` and forced `general/total_cores=N`. total L3 held at 16 MB for every core count (per-slice = 16 MB / cores), so core count never changes L3 capacity.
- baseline knobs: L1d 32 KB 8-way, L2 512 KB 8-way private, L3 16 MB 16-way NUCA, LRU, no prefetchers, DRAM 45 ns, 57.6 GB/s (sniper default, not measured).
- planned queue: 3 cores x 3 reads x 3 dbs = 27 runs.

### results in measurements/summary_all.csv (17 rows, last committed 2026-09-21)

1 core, 9 of 9 done [csv]:

| reads | db | instr M | cycles M | IPC | L1d hit % | L2 hit % | L3 hit % | wall s |
|---|---|---|---|---|---|---|---|---|
| 10 | 50mb | 124.9 | 86.0 | 1.45 | 99.09 | 0.12 | 0.49 | 696 |
| 10 | 8gb | 132.6 | 80.3 | 1.65 | 99.21 | 0.22 | 0.42 | 758 |
| 10 | 16gb | 154.1 | 99.4 | 1.55 | 99.23 | 0.20 | 0.42 | 883 |
| 50 | 50mb | 677.5 | 446.1 | 1.52 | 99.15 | 0.09 | 0.45 | 3607 |
| 50 | 8gb | 685.0 | 373.3 | 1.84 | 99.31 | 0.15 | 0.43 | 3640 |
| 50 | 16gb | 783.1 | 470.8 | 1.66 | 99.31 | 0.15 | 0.42 | 4220 |
| 100 | 50mb | 1583.6 | 1017.1 | 1.56 | 99.19 | 0.08 | 0.43 | 8126 |
| 100 | 8gb | 1640.7 | 880.9 | 1.86 | 99.37 | 0.13 | 0.40 | 8475 |
| 100 | 16gb | 1858.1 | 1096.0 | 1.70 | 99.35 | 0.14 | 0.38 | 9731 |

4 cores, 8 of 9 done [csv] (cycles = slowest core; IPC = total instructions / that cycle count, so it is aggregate over cores, not per core):

| reads | db | instr M | cycles M | IPC (aggregate) | L1d hit % | L3 hit % | wall s |
|---|---|---|---|---|---|---|---|
| 10 | 50mb | 148.2 | 89.3 | 1.66 | 99.16 | 0.37 | 772 |
| 10 | 8gb | 156.1 | 84.0 | 1.86 | 99.28 | 0.37 | 839 |
| 10 | 16gb | 177.9 | 105.1 | 1.69 | 99.29 | 0.36 | 966 |
| 50 | 50mb | 707.9 | 348.9 | 2.03 | 99.14 | 0.26 | 3739 |
| 50 | 8gb | 719.5 | 317.1 | 2.27 | 99.30 | 0.24 | 3844 |
| 50 | 16gb | missing (hung) | | | | | |
| 100 | 50mb | 1638.2 | 450.2 | 3.64 | 99.16 | 0.17 | 8561 |
| 100 | 8gb | 1692.4 | 465.6 | 3.63 | 99.34 | 0.16 | 8864 |
| 100 | 16gb | 1904.3 | 574.1 | 3.32 | 99.33 | 0.15 | 10069 |

8 cores: no rows in the csv. 0 of 9.

### re-derived ratios

- 4-core speedup in cycles (1c / 4c) [arith]: 10 reads 0.96x / 0.96x / 0.95x (slower; 86.0/89.3, 80.3/84.0, 99.4/105.1); 50 reads 1.28x (50mb, 446.1/348.9) and 1.18x (8gb, 373.3/317.1); 100 reads 2.26x (50mb), 1.89x (8gb), 1.91x (16gb). the log quotes the same values.
- why: kraken2 hands reads to threads in batches. at 10 reads one thread does all the work (log: core 0 ran about 125M of 148M instr, the others spun). at 50 reads two threads work (per-core split about 73/27). at 100 reads three threads are balanced and one is light. so these are not clean core-scaling numbers; they measure how many threads got work.
- total instructions rise with cores: 4c / 1c = 1.19x at 10 reads 50mb (148.2/124.9), 1.04x at 50 reads (707.9/677.5), 1.03x at 100 reads (1638.2/1583.6). that is spin and sync overhead.
- ordering oddity, unexplained and repeated: at 1 core, 8gb is faster than 50mb at 10 reads (80.3 vs 86.0), 50 reads (373.3 vs 446.1, ratio 0.84) and 100 reads (880.9 vs 1017.1, ratio 0.87). 16gb is the slowest at 100 reads (1096.0 vs 880.9 = 1.24x of 8gb). log hypothesis, untested: the 50mb table is nearly full, so misses probe long linear chains; 50mb also classifies fewer reads (84% vs 98% at 50 reads), has more DRAM reads (1.11M vs 0.81M) and more unique lines (842K vs 612K).
- every cell has 99.1 to 99.4 percent L1d hit, L2 hit under 0.25 percent, L3 hit 0.15 to 0.49 percent of loads. so under 1 percent of loads leave L1 at all. that is the number that matters for "which cache level to resize": the hierarchy is nearly idle for these workloads at this size.
- L3 share of loads falls with cores (0.43% at 1c to 0.17% at 4c at 100 reads 50mb); cause not investigated in the log.

### hangs and bugs found (all in command_log.md)

- `-n N` alone is silently ignored (total_cores stays 1); fixed with `-c general/total_cores=N`.
- 4c r10 50mb deadlocked 9 h at 0% cpu and was killed. a smoke test (`-n 4 -p 4`, 2 reads) later passed, so multithreading works in general. 4c r10 50mb was re-run and completed (row in csv).
- 4c r50 16gb deadlocked the same way (startup race suspected, not verified). the first watchdog never fired because the python wrapper kept cpu time creeping; replaced by a cpu-rate rule (under 60 cpu-s growth per 900 s means hung). killed by hand 2026-09-21 00:37, never retried. log count at that point: 2 hangs in 14 four-core launches, 0 in 9 one-core runs.
- int32 overflow in sim_time_max_fs awk parse, fixed to %.0f.
- the log's own caveat: sniper cache latency does not scale with cache size, so any size sweep will make bigger look artificially better unless latency is modeled.

### current state

- finished: 1-core group (9), 4-core group except 4c_r50_16gb (8). 17 of 27 rows.
- last log entry [16] (2026-09-21 08:14 IST) says the queue "continues into the 8-core group". last git commit touching cleanstart is 4bb02ba, 2026-09-21. nothing in the repo after that, 62 days before today.
- [UNCLEAR] whether the 8-core runs finished on luna, are still running, or hung. only `~/cleanstart/results/queue_progress.log` on luna can answer.
- not started at all: any sweep of a hardware knob (L3 size, L2, L1d, associativity). the README says one knob per run after the baseline. so cleanstart has produced a partial baseline and zero comparisons.
- scripts: run_one.sh (knobs via env vars, hang watchdog, grep -a), run_baseline_queue.sh (re-launch skips finished runs; loops cores 1 4 8, reads 10 50 100, dbs 50mb 8gb 16gb).

---

## 2. real-hardware results (no simulator)

all on luna (2x Xeon 8468, 192 threads, 105 MB L3 per socket, 4 of 8 memory channels populated per socket, about 359 GB page cache) unless said otherwise.

### S6 to S19 chain (plan_paper/s6_s15_speedup_report_2026-09-24.md, 32 threads, one run per cell)

S19 vs stock, 16 cells, byte-identical output in all [log]. re-derived: 50MB 1.3x / 1.6x / 1.9x at 1,000 / 104,918 / 1.87M reads (0.30/0.23; 1.31/0.84 = 1.56; 16.71/8.88 = 1.88); 8GB 9.8x at 10 reads down to 2.3x at 1.87M (21.17/9.18 = 2.31); 16GB 10.9x down to 2.4x (25.81/10.94 = 2.36); 103GB 15.4x at 10 reads down to 4.8x at 1.87M (95.62/20.08 = 4.76).

per-stage effect at 1.87M reads, which stage did what:

| stage | change | effect | note |
|---|---|---|---|
| S6 | 4-way per-thread kmer cache | looked like 13-20% faster; ablation (stock plus multi-file streaming, no cache) = 11.06 s and 14.48 s vs 11.10 s and 14.55 s with cache; perf cycles 174K vs 175K samples | cache contributed nothing |
| S8 | one reader streams all input files (stock had one omp region per file with a barrier) | 50MB 15.6 to 11.1 s, 8GB 19.7 to 14.6 s | pipeline fix |
| S9 | batched software prefetch | 103GB ~87 to ~76 s, null on 8GB/16GB | only where dram-bound |
| S10 | parallel pread load | 16GB 10 reads 9.14 to 1.89 s; 103GB 90.5 to 34.5 s | biggest win for large dbs |
| S13 | memchr newline scan | 8GB 11.94 to 10.41 s | cpu |
| S14 | 2 MB aligned table, MADV_HUGEPAGE | 16GB 11.9 to 9.15 s, 8GB 10.36 to 8.29 s, 103GB 35 to 13-20 s | tlb / page faults |
| S16 | software-pipelined prefetch (scan batch n+1 before resolving n) | 103GB 19.18 to 17.21 s (-10%), 16GB -1.4%, 8GB tied | latency hiding |
| S12, S15, S17, S18 | one modulo, run-length counts, rolling revcomp, store-forwarding stall fix | each 1 to 4% | cpu |
| S7, S11, S20 | prefetch batch / ring buffer / K2_B 16 to 64 | null (S20 within +/-0.6% on all 4 dbs) | null |

- thp caveat: 103GB S14/S15 range 13 to 21 s depending on fragmentation (13.1-13.3 s on 4 back-to-back runs, 20.2 s after a non-huge-page run, 21.58 s in the matrix, 16.55-16.79 s in a 10-07 session). treat as a range.
- small-machine test (taskset, 1.87M reads, S0 to S15): 16 cores 1.41x / 1.43x / 1.81x (50MB / 8GB / 16GB); 8 cores 1.35x / 1.22x / 1.50x; 4 cores 1.33x / 1.13x / 1.36x. with few cores the run is compute-bound and the pipeline wins shrink.
- cpu profile S19, 50MB, 32 threads (perf_s19.data): NextMinimizer 38.5%, ClassifySequence 25.1%, GetAt 12.5%, PrefetchIndex 7.0%. lookup share = 19.5%, so a free table gives at most 1/(1-0.195) = 1.24x [arith]. only 50MB was profiled; the big-db share is not measured.
- thread sweep, 103GB, stock vs s10 (next_steps plan section 6, one rep per point): classify scales near ideal to 32 threads, best at 64 (S0 20.38 s, s10 11.75 s), 3-9% worse at 96, 13-14% worse at 192. load 56-58 s stock vs 5.7-6.5 s s10 at every --threads (the loader ignores --threads). exit tax 3.9-4.7 s at 32+ threads. the same binary was 23% faster on 2026-10-21 than on 2026-09-24 (26.40 vs 34.46 s), so compare only inside one interleaved session.

### -M, hugepages, double hashing

- `-M` (memory-mapping), measured 2026-08-03 on an older patch build, 48 cells: about 0% on 50MB, 78-85% wall reduction on 8GB/16GB, 92-93% (12-14x) on pluspf_103gb at 32-96 threads. never used in any earlier baseline. E1 (`-M` vs S19, all 16 cells) has written predictions (for example 50MB about 1x, 8GB/16GB at 10 reads 3-15x, 8GB at 1.87M reads 0.8-0.97x) but is "planned but not run" per portable_kraken2/00_context.md. so how `-M` composes with S14 hugepages is unknown. expectation from the plan's own reasoning: `-M` uses 4 KB page-cache pages, so big-table random lookups pay a tlb miss each [guess].
- hugepages: S14 is the real tlb result (table above). it is a storage-layout change, the same class as sir's trie question.
- double hashing: upstream `second_hash()` is complete and compiled out by `-DLINEAR_PROBING` (Makefile line 4). B1 needs a flag flip and a db rebuild, not new code. unaudited risk: nothing forces gcd(step, capacity) = 1. no double-hashing measurement exists in the repo [UNCLEAR: none found in plan_paper/command_log.md]. trap: overriding CXXFLAGS on the make line drops the flag silently and breaks output for dbs built with linear probing.
- load factor 0.70 (M1): linear probing expects 2.17 probes for a hit and 6.06 for a miss, 1.07 / 1.32 cache lines per lookup [arith in the trie brief, textbook formulas].

### the old software-cache (S2) line of work, real hardware

- LRU cache: hit rate under 2% at realistic sizes. associativity sweep (2026-09-02): wall clock monotonically worse with more ways (4-way -0.40%, 64-way +3.86%, worst +80% on sample_targeted T=1), later attributed to allocation / first-touch cost plus atomics (2-3x artifact); noatomics binaries never benchmarked.
- S3.4 full db x thread benchmark: S0 = S2-baseline = S2-final within noise (cv mostly under 1%). null.
- S4.0: S2SetIndex used a raw low-bit mask (max/mean set load 225.42); murmur mixing gave an 8.9x hit rate (0.4035% to 3.5758%) but no wall-clock effect, and flipped pinning eviction from +25.2% to -3.9%. the old pinning result is dead.
- the old "22x / 85% slowdown cliff" was mostly S3.0 (static-TLS bug), not S3.3; superseded.

### which of these matter for a cache / eviction / storage-structure question

1. the software kmer cache has no measured real-hardware value: ablated to zero (S6), null at all dbs and threads (S3.4), eviction result reversed (S4.0). any claim that a cache or eviction policy helps must beat this.
2. the real wins on big tables are latency hiding and tlb (S9, S14, S16), not reuse. 103GB: S14 35 to 13-20 s, S16 another -10%. that says lookups are mostly unique-key dram misses, the opposite of the reuse a cache needs.
3. on 50MB with a 105 MB L3 the table fits in cache and cpu dominates (NextMinimizer 38.5%). on 8GB and 16GB it does not. luna LLC-miss rate 80.03% at T=1 and 83.87% at T=32 on 8GB, IPC 1.95 to 1.69, aggregate 6.03 to 20.5 billion instr/s (3.4x for 32x threads) [simulator brief, from a saved perf stat].
4. the ceiling on any lookup-structure change is small on 50MB: 1.24x best case.
5. fixed costs dominate small inputs: load 56-58 s stock on 103GB, exit 3.9-4.7 s. a structure that shrinks the file mostly helps load and exit, not classify.

---

## 3. sir's trie / dictionary question (Meeting 13, 2026-10-21)

- the meeting_minutes.md entry was written 2026-10-26 from ck's recollection; only this topic is recorded. a [MISSING] note says whether E1-E5 got an ok, orin access, and sir's answers to four asks are not recorded.
- sir asked: can the database structure itself change (a trie instead of the flat hash table, or a dictionary) so search is easier and faster; is the lookup a function or inline; how much algorithm change, code and time.
- brief: plan_paper/research_brief_db_structure_trie_dictionary_2026-10-21.md (209 lines). predictions only, nothing run on luna.
  - function vs inline: a real function. GetAt and PrefetchIndex are virtual in KeyValueStore and appear as separate symbols in the S19 profile (12.5% and 7.0%). side benefit: a new structure is a subclass plus a builder. choose at compile time or LTO loses inlining (E3 may give 2 to 8%).
  - ceiling: lookup is 19.5% of cpu on 50MB, so 1.24x at most for a free lookup. the big-db share is unmeasured (stage 0c would measure it).
  - the flat table is the one-access floor (1.07 to 1.32 lines at load 0.70).
  - A, plain trie: 24 dependent reads for 48-bit keys, about 12 with path compression at 50MB. dead.
  - B, radix tree: 3 to 6 reads, 20 to 52 bytes per key, 100 to 455 MB at 50MB (100 to 170 MB if built for exactly 8.75M keys). about 15 to 25% slower overall [guess].
  - C, exact flat dictionary (8-byte slot): 1.15 / 1.63 lines, 91 bits per key, 222 GB at 103GB, 100 MB at 50MB. 2x memory, same reads.
  - D, prefix directory plus sorted bucket (kraken 1 shape): 2 to 3 reads, about 95-100 GB. strongest variant: an L3-sized directory (2^24 entries x 5 B = 84 MB) with interpolation search, maybe within reach of the hash table.
  - E, mphf plus fingerprint: 85 GB (-23%), 2 to 3 reads. F, Elias-Fano sorted keys: 77 GB (-31%), 2 to 3 reads, exact.
  - verdict: every structure predicted to lose on speed. the real payoff is space (23-31%) and zero false positives (the far end of the thesis 2 cell-width curve). on 103GB the size win is worth about 3 s of a 20 s run [arith in the brief].
  - no db can be converted from hash.k2d (it stores a fingerprint only); each structure needs a rebuild from library genomes. 103GB cannot be rebuilt on luna (35 GB free vs a 111 GB table). 8GB/16GB genomes on luna unverified.
  - cost: 200-600 lines per structure plus 250-550 shared; 3-6 days to a first 50MB result; 3-4 weeks to a defensible 16-cell result.
  - stage 0 (about 2 days, then a gate): grep for the file list, nm/objdump for symbols, perf record on 8GB for the big-db ceiling, then structbench.cpp (single thread, batch-16 prefetch; current vs C vs D vs radix at 8.75M / 1B / 4B random 48-bit keys; also measure real L2/L3/ram latency on luna). gate fixed in advance: stop if the 50MB ceiling is under 25% and the best alternative is over 1.3x slower per lookup at 1B keys; go if some structure is within 1.15x at every size and 20% smaller.
- status: stage 0 not run (portable_kraken2/00_context.md says "also not run"). unresolved in the brief: key width 48 vs 62 bits, and what sir meant by "inline".

---

## 4. sim-vs-real discrepancies

1. software cache value. sim (old cache_simulation, laptop.cfg): 4-way vs S0 cycles 0.704x, 0.831x, 0.957x, 1.031x, 1.092x at 10, 25, 50, 100, 500 long reads [log longread_scaling], so a 30% win that decays to a 9% loss. real: the same cache is null at 32 threads on every db (S3.4) and ablated to zero in S6. the sim win at tiny inputs looks like a startup or binary difference, not reuse: the S0 10-read laptop run has 16.3M instr and IPC 0.89 vs 7.3M instr and IPC 1.45 for 1-way [csv laptop_sweep], and a cache cannot remove half the instructions [guess].
2. cache design mismatch inside the old simulator work. per the 2026-09-19 correction, the width/assoc sweeps used the original S2 (4,096 sets fixed, LRU, raw low-bit index with the broken hash, 96 KB to 1.5 MB static TLS) while the size sweep used the current design (calloc, 16 B entries, round-robin, murmur index). "S2" in the two sweeps is not the same cache. the audit also found fig14 mixes 10-read and 50-read panels.
3. hardware associativity sweep is null in the simulator. hw_assoc_sweep_2026-09-14.csv: at 100 reads cycles span 869.8 to 877.3 M across associativity 1 to 30 (0.9% spread [arith]); at 500 reads 4523.2 to 4537.9 M (0.3%). unique lines are identical. expected at 99% L1d hit. a real associativity effect on luna is untested.
4. flat vs nuca topology moves cycles more than any associativity knob. flatl3_comparison: 50mb nuca 24.4M vs flat 31.9M cycles (1.31x); 8gb nuca 51.8M vs flat 60.4M (1.17x). the topology assumption matters more than the knob being studied.
5. latency model. cleanstart caveat: sniper latency does not scale with cache size, so a size sweep favors big caches artificially.
6. contention is absent. real luna: IPC 1.95 to 1.69 and LLC-miss 80.03% to 83.87% from T=1 to T=32. the cleanstart 4-core sim reports aggregate IPC 3.3 to 3.6 at 100 reads with DRAM fixed at an uncontended 45 ns, and only 3 busy threads. no 8-core data.
7. scale mismatch. simulated runs are 10 to 100 reads (0.37M to 5.3M bases, 0.1 to 1.9 billion instructions). real work is 1.87M reads, about 6,036 Mbp. at 10 reads the sim is dominated by db-load startup (log: 125M instr for 0.37M bases), so db-size trends there are not real.
8. db-size ordering. sim 1-core: 8gb fastest, 50mb and 16gb slower at all read counts. real luna S0 at 1.87M reads: 50MB 16.71 s, 8GB 21.17 s, 16GB 25.81 s, 103GB 95.62 s (monotonic). they disagree. real includes load time and 32 threads; sim is 1 core. the near-full-table hypothesis for 50mb is untested.
9. thread scaling. sim 4-core speedup is 0.95x to 2.26x depending on read count (batching); real S0 classify scales near ideal to 32 threads on 1.87M reads. consistent only if read count is large, so sim multicore numbers on 10 to 100 reads say little about thread scaling.
10. target machine. cleanstart models the laptop (5800H, 16 MB L3); all real kraken2 numbers are luna (105 MB L3 per socket). orin: only sizes are confirmed (64 KB L1d and L1i, 256 KB L2, 2 MB L3 per cluster, 4 MB SLC); the "8-way L2" claim was retracted. there are no real laptop or orin kraken2 timings in the repo (orin unreachable; laptop has only 2.9-3.8 GB free).

---

## 5. open questions

1. did cleanstart's 8-core runs and the 4c r50 16gb retry ever finish on luna? (needs queue_progress.log.) if not, the baseline is 17 of 27.
2. what is the first hardware knob, and what question does it answer, given under 1 percent of loads leave L1d? an L3-size sweep from 16 MB would likely move almost nothing at these read counts [guess]; the real signal may need the large dbs and far more reads.
3. is it acceptable that cleanstart runs 10 to 100 reads, where startup dominates, when the real regime (1.87M reads) is pipeline- and latency-bound? what instruction window makes cache size visible?
4. why is 8gb faster than 50mb in the sim at every read count? needs a load-factor or probe-count check on the tables.
5. can sniper reproduce S14's tlb effect and S16's prefetch effect? both moved real runtime more than any cache change; the sim may be unable to test the thing that actually moved real runtime [guess].
6. E1 (`-M` vs S19) never run. it decides whether hugepages or `-M` is the right storage layout, and so what a trie or dictionary must beat. the `-M` numbers came from an older build.
7. trie stage 0 never run: the 8GB lookup ceiling and structbench numbers are open. the gate is already written.
8. double hashing: any measurement at all? coprimality of step and capacity unchecked.
9. meeting 13 is partly [MISSING]: did sir approve E1-E5, and does the trie question replace or sit beside the cache thesis?
10. which question is the paper? real data says cache reuse is near zero (S6 ablation, S3.4) while the wins are pipeline, prefetch and tlb. the cleanstart question (best hardware cache for kraken2) may be a characterization result, not an optimization. needs a decision from sir.
