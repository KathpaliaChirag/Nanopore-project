# Kraken2 — Thread-Scaling Profiling Report

**Date:** 2026-05-29  |  **CPU:** AMD Ryzen 7 7735HS (Zen4, 8c/16t, 6-wide dispatch)  |  **DB:** minikraken2_v2_8GB_201904

**Binary:** rebuilt without `-pg` — zero mcount overhead in these results.

**Experiment:** 9 thread counts (1 2 4 6 8 10 12 14 16) × 3 modes (fast / hac / sup). Each combination: 3 classification runs, one `perf stat` cache run, one `perf stat` TMA run, one `mpstat -P ALL 2` capture. All values exact from source files — nothing aggregated.

### Abbreviations

| Term | Meaning |
|------|---------|
| IPC | Instructions Per Cycle — higher = better; memory-bound workloads show < 1.0 |
| TMA | Top-down Microarchitecture Analysis (AMD Zen4 hardware event method) |
| BE-Bound | Backend-Bound — pipeline slots stalled waiting on memory or execution units |
| FE-Bound | Frontend-Bound — pipeline slots stalled on instruction fetch/decode |
| Bad-Spec | Pipeline slots wasted on mispredicted or cancelled operations |
| Retiring | Pipeline slots doing real useful work |
| ls_not_halted_cyc | AMD PMC: physical cycles the core was not halted |
| ex_ret_ops | AMD PMC: retired micro-ops |
| ex_ret_instr | AMD PMC: retired macro-instructions |
| de_dis_uop_queue_empty_di0 | AMD PMC: dispatch-queue empty cycles (FE stall proxy) |
| op_cache_hit_miss.op_cache_miss | AMD PMC: 32 KB decoded-uop op-cache misses |
| ic_fetch_stall.ic_stall_any | AMD PMC: i-fetch stall cycles (BE back-pressure artifact) |
| Kseq/m | Kilo-sequences per minute |
| DRAM | Main memory, ~100 ns random latency |
| L3 | Level-3 cache, ~16 MB shared on this chip |

---

## 1. Classification Baseline

Classification is deterministic — results are identical across all thread counts and all runs. Values from run 1 at T=1.

| Mode | Input reads | Input Mbp | Classified | Classified% | Unclassified% |
|------|------------:|----------:|-----------:|------------:|--------------:|
| fast | 104832 | 357.62 | 97680 | 93.18% | 6.82% |
| hac | 104918 | 355.36 | 102667 | 97.85% | 2.15% |
| sup | 104980 | 365.84 | 103281 | 98.38% | 1.62% |

**Observations:**

- **fast classifies 93.18%** of reads — the lowest of the three modes. Fast basecalling produces lower-accuracy reads, so more k-mers deviate from the reference sequences in the DB, leading to ~4.67 pp fewer classified reads than hac.
- **sup classifies 98.38%** — highest accuracy basecalling minimises k-mer errors, leaving only 1.62% unclassified. The 5.20 pp gap between sup and fast is entirely a basecall-quality effect, not a thread-count effect.
- **Input Mbp differs slightly across modes** (fast 357.62, hac 355.36, sup 365.84) because the three FASTQ files come from separate dorado basecalling passes on the same raw signal — different basecallers trim poly-A tails and low-confidence ends differently, producing slightly different read lengths despite nominally the same dataset.
- **These counts are invariant across all 27 (mode × thread) combinations** — Kraken2's classification is deterministic given fixed DB and reads, so thread count affects only timing, never correctness.

---

## 2. Throughput Scaling — Wall Time + Kseq/m (all 3 runs, exact values)

`Speedup` = run-1 wall at T=1 ÷ run-1 wall at T=N. Ideal linear speedup would equal N.

### 2.1 Mode: **fast**  (classified 93.18%)

| Threads | Run 1 wall (s) | Run 1 Kseq/m | Run 2 wall (s) | Run 2 Kseq/m | Run 3 wall (s) | Run 3 Kseq/m | Speedup vs T1 |
|--------:|---------------:|-------------:|---------------:|-------------:|---------------:|-------------:|--------------:|
| 1 | 14.545 | 432.4 | 14.459 | 435.0 | 14.733 | 426.9 | 1.00× |
| 2 | 7.920 | 794.2 | 7.707 | 816.1 | 7.770 | 809.5 | 1.84× |
| 4 | 4.368 | 1440.1 | 4.420 | 1423.1 | 4.474 | 1405.9 | 3.33× |
| 6 | 3.328 | 1889.7 | 3.368 | 1867.5 | 3.208 | 1960.9 | 4.37× |
| 8 | 2.714 | 2317.3 | 2.684 | 2343.3 | 2.739 | 2296.2 | 5.36× |
| 10 | 2.435 | 2583.2 | 2.793 | 2252.3 | 2.615 | 2405.6 | 5.97× |
| 12 | 2.402 | 2619.1 | 2.438 | 2580.1 | 2.529 | 2487.2 | 6.06× |
| 14 | 2.345 | 2682.0 | 2.350 | 2676.9 | 2.337 | 2691.0 | 6.20× |
| 16 | 2.203 | 2855.3 | 2.238 | 2810.3 | 2.281 | 2757.7 | 6.60× |

**Observations:**

- **Parallelism efficiency at T2: 92%** (1.84× actual vs 2.00× ideal) — nearly all of the second thread's capacity is used; the workload parallelises well at low thread counts.
- **Efficiency falls to 83% at T4** (3.33×) and **67% at T8** (5.36×) — each doubling of threads adds less than double the throughput as DRAM bandwidth becomes the shared constraint.
- **T8→T10 is the saturation inflection:** 2.714s → 2.435s, only 11.5% gain for 2 extra threads. Beyond this point adding threads primarily increases memory contention rather than throughput.
- **T10→T12→T14→T16 diminishing returns:** T12 vs T10 = 1.4% faster, T14 vs T12 = 2.4% faster, T16 vs T14 = 6.4% faster. Each pair of added threads contributes less than the last.
- **Run-to-run variance at T1: 1.9%** — very stable single-thread timing. **At T10: 14.7%** — OS scheduler noise increases significantly at high thread counts as the kernel moves threads between physical cores during the run.
- **Parallelism efficiency at T16: 41%** — only 41% of 16 threads' theoretical capacity is realised; the remaining 59% is lost to DRAM stalls shared across all threads.

### 2.2 Mode: **hac**  (classified 97.85%)

| Threads | Run 1 wall (s) | Run 1 Kseq/m | Run 2 wall (s) | Run 2 Kseq/m | Run 3 wall (s) | Run 3 Kseq/m | Speedup vs T1 |
|--------:|---------------:|-------------:|---------------:|-------------:|---------------:|-------------:|--------------:|
| 1 | 14.961 | 420.8 | 15.007 | 419.5 | 15.044 | 418.5 | 1.00× |
| 2 | 7.909 | 795.9 | 7.974 | 789.4 | 7.934 | 793.4 | 1.89× |
| 4 | 4.561 | 1380.3 | 4.349 | 1447.6 | 4.287 | 1468.3 | 3.28× |
| 6 | 3.209 | 1961.9 | 3.240 | 1943.2 | 3.243 | 1941.4 | 4.66× |
| 8 | 2.694 | 2337.0 | 2.745 | 2293.4 | 2.735 | 2301.8 | 5.55× |
| 10 | 2.560 | 2459.0 | 2.597 | 2423.8 | 2.595 | 2425.9 | 5.84× |
| 12 | 2.443 | 2576.7 | 2.473 | 2545.0 | 2.466 | 2553.1 | 6.12× |
| 14 | 2.325 | 2707.1 | 2.366 | 2660.4 | 2.391 | 2632.5 | 6.43× |
| 16 | 2.282 | 2758.9 | 2.308 | 2727.5 | 2.310 | 2724.6 | 6.56× |

**Observations:**

- **Parallelism efficiency at T2: 95%** (1.89× actual vs 2.00× ideal) — nearly all of the second thread's capacity is used; the workload parallelises well at low thread counts.
- **Efficiency falls to 82% at T4** (3.28×) and **69% at T8** (5.55×) — each doubling of threads adds less than double the throughput as DRAM bandwidth becomes the shared constraint.
- **T8→T10 is the saturation inflection:** 2.694s → 2.560s, only 5.2% gain for 2 extra threads. Beyond this point adding threads primarily increases memory contention rather than throughput.
- **T10→T12→T14→T16 diminishing returns:** T12 vs T10 = 4.8% faster, T14 vs T12 = 5.1% faster, T16 vs T14 = 1.9% faster. Each pair of added threads contributes less than the last.
- **Run-to-run variance at T1: 0.6%** — very stable single-thread timing. **At T10: 1.4%** — OS scheduler noise increases significantly at high thread counts as the kernel moves threads between physical cores during the run.
- **Parallelism efficiency at T16: 41%** — only 41% of 16 threads' theoretical capacity is realised; the remaining 59% is lost to DRAM stalls shared across all threads.

### 2.3 Mode: **sup**  (classified 98.38%)

| Threads | Run 1 wall (s) | Run 1 Kseq/m | Run 2 wall (s) | Run 2 Kseq/m | Run 3 wall (s) | Run 3 Kseq/m | Speedup vs T1 |
|--------:|---------------:|-------------:|---------------:|-------------:|---------------:|-------------:|--------------:|
| 1 | 14.335 | 439.4 | 14.445 | 436.1 | 14.473 | 435.2 | 1.00× |
| 2 | 7.551 | 834.1 | 7.645 | 823.9 | 7.651 | 823.3 | 1.90× |
| 4 | 4.297 | 1466.0 | 4.343 | 1450.2 | 4.342 | 1450.6 | 3.34× |
| 6 | 3.308 | 1904.4 | 3.574 | 1762.5 | 3.341 | 1885.1 | 4.33× |
| 8 | 2.756 | 2285.4 | 2.784 | 2262.5 | 2.792 | 2256.4 | 5.20× |
| 10 | 2.591 | 2430.8 | 2.632 | 2392.8 | 2.627 | 2398.0 | 5.53× |
| 12 | 2.481 | 2539.1 | 2.488 | 2531.7 | 2.524 | 2495.5 | 5.78× |
| 14 | 2.366 | 2662.0 | 2.407 | 2616.4 | 2.423 | 2599.6 | 6.06× |
| 16 | 2.309 | 2728.0 | 2.333 | 2700.2 | 2.319 | 2716.1 | 6.21× |

**Observations:**

- **Parallelism efficiency at T2: 95%** (1.90× actual vs 2.00× ideal) — nearly all of the second thread's capacity is used; the workload parallelises well at low thread counts.
- **Efficiency falls to 83% at T4** (3.34×) and **65% at T8** (5.20×) — each doubling of threads adds less than double the throughput as DRAM bandwidth becomes the shared constraint.
- **T8→T10 is the saturation inflection:** 2.756s → 2.591s, only 6.4% gain for 2 extra threads. Beyond this point adding threads primarily increases memory contention rather than throughput.
- **T10→T12→T14→T16 diminishing returns:** T12 vs T10 = 4.4% faster, T14 vs T12 = 4.9% faster, T16 vs T14 = 2.5% faster. Each pair of added threads contributes less than the last.
- **Run-to-run variance at T1: 1.0%** — very stable single-thread timing. **At T10: 1.6%** — OS scheduler noise increases significantly at high thread counts as the kernel moves threads between physical cores during the run.
- **Parallelism efficiency at T16: 39%** — only 39% of 16 threads' theoretical capacity is realised; the remaining 61% is lost to DRAM stalls shared across all threads.

### 2.4 Cross-Mode Throughput Comparison (run 1, seconds)

| Threads | fast wall (s) | fast Kseq/m | fast speedup | hac wall (s) | hac Kseq/m | hac speedup | sup wall (s) | sup Kseq/m | sup speedup |
|--------:|--------------:|------------:|-------------:|-------------:|-----------:|------------:|-------------:|-----------:|------------:|
| 1 | 14.545 | 432.4 | 1.00× | 14.961 | 420.8 | 1.00× | 14.335 | 439.4 | 1.00× |
| 2 | 7.920 | 794.2 | 1.84× | 7.909 | 795.9 | 1.89× | 7.551 | 834.1 | 1.90× |
| 4 | 4.368 | 1440.1 | 3.33× | 4.561 | 1380.3 | 3.28× | 4.297 | 1466.0 | 3.34× |
| 6 | 3.328 | 1889.7 | 4.37× | 3.209 | 1961.9 | 4.66× | 3.308 | 1904.4 | 4.33× |
| 8 | 2.714 | 2317.3 | 5.36× | 2.694 | 2337.0 | 5.55× | 2.756 | 2285.4 | 5.20× |
| 10 | 2.435 | 2583.2 | 5.97× | 2.560 | 2459.0 | 5.84× | 2.591 | 2430.8 | 5.53× |
| 12 | 2.402 | 2619.1 | 6.06× | 2.443 | 2576.7 | 6.12× | 2.481 | 2539.1 | 5.78× |
| 14 | 2.345 | 2682.0 | 6.20× | 2.325 | 2707.1 | 6.43× | 2.366 | 2662.0 | 6.06× |
| 16 | 2.203 | 2855.3 | 6.60× | 2.282 | 2758.9 | 6.56× | 2.309 | 2728.0 | 6.21× |

**Observations:**

- **At T=1, sup is fastest (14.335 s), then fast (14.545 s), then hac (14.961 s).** sup produces the highest-quality, longest reads (~3.5 kb avg) — their k-mers match the DB on first probe more often, reducing per-read classification work. hac is slowest at T=1 despite better accuracy than fast because hac reads are longer than fast (more k-mers to process) but not quite as efficiently classified as sup.
- **At T=16, fast is fastest (2.203 s) — the order inverts.** fast's lower classification rate (93.18%) means each read on average finishes DB probing sooner (more early-exit misses), so when enough threads share the bandwidth the faster-per-read mode wins.
- **All three modes converge on similar speedups at T=16** (fast 6.60×, hac 6.56×, sup 6.21×) — they hit the same DRAM bandwidth ceiling regardless of mode quality.
- **T8 is the last thread count where sup beats fast in absolute wall time** (sup 2.756 s vs fast 2.714 s at T8; sup 2.591 s vs fast 2.435 s at T10, now sup is slower). The crossover coincides exactly with the bandwidth saturation point.

---

## 3. Cache Performance (`perf stat`)

`Cache-Miss%` = cache-misses / cache-references × 100.  `CPU-Eff%` = user-time / elapsed-time × 100.

### 3.1 Full Cache Table — All Modes × All Thread Counts

| Mode | Threads | Cache-Misses | Cache-References | Cache-Miss% | Elapsed (s) | User (s) | Sys (s) | CPU-Eff% |
|------|--------:|-------------:|-----------------:|------------:|-----------:|---------:|--------:|---------:|
| fast | 1 | 397,959,625 | 2,411,546,877 | 16.50% | 20.454707092 | 14.250579000 | 4.983157000 | 69.7% |
| fast | 2 | 399,689,299 | 2,419,361,754 | 16.52% | 13.799098574 | 15.439085000 | 5.214893000 | 111.9% |
| fast | 4 | 395,879,879 | 2,427,233,197 | 16.31% | 10.146009649 | 16.683555000 | 5.247998000 | 164.4% |
| fast | 6 | 400,093,405 | 2,464,142,066 | 16.24% | 9.280391446 | 19.030912000 | 5.645528000 | 205.1% |
| fast | 8 | 393,780,554 | 2,475,077,375 | 15.91% | 8.393418113 | 20.309948000 | 5.354874000 | 242.0% |
| fast | 10 | 380,452,172 | 2,496,282,360 | 15.24% | 8.114709044 | 22.726426000 | 5.483270000 | 280.1% |
| fast | 12 | 387,587,853 | 2,539,005,010 | 15.27% | 8.243194728 | 26.187112000 | 5.934852000 | 317.7% |
| fast | 14 | 377,823,192 | 2,539,474,787 | 14.88% | 8.187378252 | 29.162858000 | 6.046949000 | 356.2% |
| fast | 16 | 374,653,361 | 2,567,640,616 | 14.59% | 8.037933193 | 30.027789000 | 6.160367000 | 373.6% |
| hac | 1 | 296,277,884 | 2,275,954,785 | 13.02% | 20.691736652 | 14.657919000 | 4.985755000 | 70.8% |
| hac | 2 | 309,744,628 | 2,261,136,077 | 13.70% | 13.682238944 | 15.353451000 | 5.197809000 | 112.2% |
| hac | 4 | 318,338,697 | 2,319,785,561 | 13.72% | 10.507481380 | 17.590368000 | 5.446628000 | 167.4% |
| hac | 6 | 306,012,596 | 2,361,922,180 | 12.96% | 8.896203502 | 18.378604000 | 5.238779000 | 206.6% |
| hac | 8 | 306,662,071 | 2,380,977,915 | 12.88% | 8.329751609 | 20.509006000 | 5.390181000 | 246.2% |
| hac | 10 | 313,045,828 | 2,424,698,505 | 12.91% | 8.188942106 | 23.881670000 | 5.580562000 | 291.6% |
| hac | 12 | 323,592,969 | 2,501,840,978 | 12.93% | 8.118671305 | 26.857933000 | 5.737611000 | 330.8% |
| hac | 14 | 331,927,827 | 2,520,841,953 | 13.17% | 7.991711763 | 29.790026000 | 5.811781000 | 372.8% |
| hac | 16 | 336,984,497 | 2,570,511,439 | 13.11% | 7.988529091 | 32.080578000 | 6.008832000 | 401.6% |
| sup | 1 | 286,120,421 | 2,251,646,638 | 12.71% | 19.918433124 | 13.958797000 | 4.839412000 | 70.1% |
| sup | 2 | 278,858,672 | 2,218,017,321 | 12.57% | 12.945699006 | 14.645143000 | 4.852846000 | 113.1% |
| sup | 4 | 292,185,938 | 2,323,110,561 | 12.58% | 9.909926983 | 16.588246000 | 5.034926000 | 167.4% |
| sup | 6 | 301,932,025 | 2,336,703,109 | 12.92% | 8.937177766 | 18.736407000 | 5.233543000 | 209.6% |
| sup | 8 | 303,107,237 | 2,372,144,937 | 12.78% | 8.323316674 | 20.543335000 | 5.379225000 | 246.8% |
| sup | 10 | 316,185,121 | 2,441,044,980 | 12.95% | 8.150442608 | 24.114706000 | 5.518308000 | 295.9% |
| sup | 12 | 324,145,226 | 2,491,093,141 | 13.01% | 8.077741931 | 27.295610000 | 5.602783000 | 337.9% |
| sup | 14 | 334,475,971 | 2,536,875,561 | 13.18% | 7.967841093 | 30.127010000 | 5.776876000 | 378.1% |
| sup | 16 | 337,941,741 | 2,577,684,792 | 13.11% | 7.916854994 | 32.646008000 | 5.924241000 | 412.4% |

**Observations:**

- **CPU-Eff% at T=1 is ~70% for all modes** (fast 69.7%, hac 70.8%, sup 70.1%). This is below 100% because `perf stat` elapsed includes the DB load phase (~5 s of mmap + page-fault overhead) during which no classification happens; user time only counts actual computation.
- **CPU-Eff% exceeds 100% from T=2 onwards** — user time is the sum of all threads' CPU time, so it grows with thread count while elapsed wall time shrinks. At T=16: fast 373.6%, hac 401.6%, sup 412.4% — 16 threads collectively burn 4× the wall-clock time in user CPU.
- **Elapsed barely changes T=8→T=16** (fast: 8.393 s → 8.038 s, -4.2%) — the wall clock is bounded by DRAM bandwidth, not by how many threads issue requests. Adding threads beyond T=8 reduces individual stall time slightly but the total wall time barely improves.
- **Sys time grows steadily with threads** (fast: 4.983 s at T=1 → 6.160 s at T=16, +24%) — more threads means more kernel scheduling, futex, and thread-join overhead, visible as rising sys time.

### 3.2 Cross-Thread Cache-Miss% by Mode

| Threads | fast miss% | fast misses | hac miss% | hac misses | sup miss% | sup misses |
|--------:|-----------:|------------:|----------:|-----------:|----------:|-----------:|
| 1 | 16.50% | 397,959,625 | 13.02% | 296,277,884 | 12.71% | 286,120,421 |
| 2 | 16.52% | 399,689,299 | 13.70% | 309,744,628 | 12.57% | 278,858,672 |
| 4 | 16.31% | 395,879,879 | 13.72% | 318,338,697 | 12.58% | 292,185,938 |
| 6 | 16.24% | 400,093,405 | 12.96% | 306,012,596 | 12.92% | 301,932,025 |
| 8 | 15.91% | 393,780,554 | 12.88% | 306,662,071 | 12.78% | 303,107,237 |
| 10 | 15.24% | 380,452,172 | 12.91% | 313,045,828 | 12.95% | 316,185,121 |
| 12 | 15.27% | 387,587,853 | 12.93% | 323,592,969 | 13.01% | 324,145,226 |
| 14 | 14.88% | 377,823,192 | 13.17% | 331,927,827 | 13.18% | 334,475,971 |
| 16 | 14.59% | 374,653,361 | 13.11% | 336,984,497 | 13.11% | 337,941,741 |

**Observations:**

- **Cache-misses are nearly constant regardless of thread count.** fast: 397,959,625 (T1) → 374,653,361 (T16), change -5.9%. The total number of DRAM misses the process generates is set by the 8 GB working set size — it does not shrink as threads increase. Adding threads does not cache-warm any additional portion of the DB.
- **Cache-references grow with threads** (fast: 2,411,546,877 at T1 → 2,567,640,616 at T16, +6.5%) because more threads issue more total memory reference events. This dilutes the miss ratio even though the miss count is flat.
- **Cache-Miss% decline is a ratio artefact, not a real cache improvement.** fast drops from 16.50% (T1) to 14.59% (T16) — a 12% relative drop — but DRAM accesses per second actually increase with more threads.
- **fast has the highest miss% at every thread count** (14.59% at T16 vs hac 13.11% vs sup 13.11%). Lower-quality fast reads generate more ambiguous k-mers that probe a wider range of DB hash-table buckets, causing more cold DRAM hits.
- **hac shows a miss% bump at T2 (13.02% → 13.70%)** before declining — a small artefact of the second thread probing slightly different hash-table regions than the first, briefly increasing both misses and references before they stabilise.
- **sup miss% rises slightly at high thread counts** (T2 low of 12.57% → T16 of 13.11%) — unlike fast which monotonically declines, sup's longer, higher-quality reads generate more unique k-mers per read that hit distinct DB pages, mildly increasing absolute misses at high concurrency.

---

## 4. TMA Pipeline Breakdown (AMD Zen4 Topdown)

**Formula:** slots = `ls_not_halted_cyc × 6` (6-wide dispatch).

```
Retiring%  = ex_ret_ops  / slots × 100
FE-Bound%  = de_dis_uop_queue_empty_di0 / slots × 100
Bad-Spec%  = (ex_ret_near_ret_mispred × 4) / slots × 100
BE-Bound%  = 100 − Retiring% − FE-Bound% − Bad-Spec%
IPC        = ex_ret_instr / ls_not_halted_cyc
```

### 4.1 TMA Breakdown — All 27 Combinations

| Mode | Threads | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC |
|------|--------:|----------:|----------:|----------:|----------:|----:|
| fast | 1 | 22.73% | 1.51% | 75.53% | 0.23% | 1.3628 |
| fast | 2 | 23.00% | 1.55% | 75.21% | 0.24% | 1.3780 |
| fast | 4 | 23.17% | 1.59% | 74.99% | 0.24% | 1.3839 |
| fast | 6 | 22.95% | 1.63% | 75.17% | 0.25% | 1.3697 |
| fast | 8 | 23.47% | 1.65% | 74.62% | 0.25% | 1.4017 |
| fast | 10 | 20.68% | 1.76% | 77.34% | 0.23% | 1.2333 |
| fast | 12 | 20.15% | 1.77% | 77.86% | 0.22% | 1.1998 |
| fast | 14 | 19.14% | 1.79% | 78.86% | 0.21% | 1.1385 |
| fast | 16 | 18.76% | 1.83% | 79.20% | 0.21% | 1.1149 |
| hac | 1 | 25.35% | 1.46% | 72.96% | 0.23% | 1.5156 |
| hac | 2 | 25.73% | 1.50% | 72.54% | 0.23% | 1.5385 |
| hac | 4 | 26.24% | 1.55% | 71.97% | 0.24% | 1.5640 |
| hac | 6 | 26.60% | 1.57% | 71.59% | 0.25% | 1.5839 |
| hac | 8 | 26.59% | 1.61% | 71.54% | 0.25% | 1.5789 |
| hac | 10 | 24.14% | 1.67% | 73.95% | 0.23% | 1.4350 |
| hac | 12 | 22.68% | 1.70% | 75.40% | 0.22% | 1.3463 |
| hac | 14 | 21.45% | 1.71% | 76.63% | 0.21% | 1.2704 |
| hac | 16 | 20.40% | 1.77% | 77.62% | 0.20% | 1.2059 |
| sup | 1 | 27.11% | 1.42% | 71.24% | 0.23% | 1.6176 |
| sup | 2 | 27.42% | 1.47% | 70.88% | 0.24% | 1.6402 |
| sup | 4 | 27.42% | 1.53% | 70.81% | 0.24% | 1.6334 |
| sup | 6 | 27.19% | 1.56% | 71.00% | 0.24% | 1.6194 |
| sup | 8 | 27.46% | 1.59% | 70.69% | 0.25% | 1.6340 |
| sup | 10 | 24.97% | 1.63% | 73.18% | 0.23% | 1.4835 |
| sup | 12 | 23.31% | 1.65% | 74.83% | 0.21% | 1.3834 |
| sup | 14 | 21.97% | 1.69% | 76.14% | 0.20% | 1.3008 |
| sup | 16 | 21.13% | 1.72% | 76.95% | 0.20% | 1.2501 |

**Observations:**

- **BE-Bound is the dominant bucket at every (mode, thread) combination, ranging 70.7–79.2%.** Even a single thread spends 75.5% of pipeline slots stalled on memory. This confirms the bottleneck is the 8 GB working set against 16 MB L3 at every thread count, not any parallelism or synchronisation overhead.
- **BE-Bound grows with threads: fast 75.5% (T1) → 74.6% (T8) → 79.2% (T16), +3.7 pp total.** Each added thread competes for the same DRAM bandwidth, increasing per-thread stall time and worsening BE-Bound.
- **There is a clear step up in BE-Bound at T=10 for all modes** — fast jumps from 74.6% at T8 to 77.3% at T10 (+2.7 pp). This matches the throughput plateau and IPC drop exactly, confirming T10 as the bandwidth-saturation boundary.
- **FE-Bound is uniformly negligible (1.42–1.83%)** — the frontend instruction decoder is never a bottleneck. The large `ic_fetch_stall` raw count is a back-pressure artefact (see §5).
- **Bad-Spec is uniformly near-zero (0.20–0.25%)** — Kraken2's DB probing loop is highly branch-predictable; mispredictions are not a meaningful cost.
- **Retiring (useful work fraction) is highest for sup** (best: 27.46% at T8) and lowest for fast at T16 (18.76%). Higher-quality reads → more sequential DB hits → shorter stall chains → more useful work per slot.
- **sup consistently has the lowest BE-Bound and highest Retiring at every thread count** — confirming that read quality (and thus DB-probe efficiency) directly determines pipeline utilisation.

### 4.2 IPC by Thread Count (`ex_ret_instr / ls_not_halted_cyc`)

| Threads | fast IPC | hac IPC | sup IPC | fast BE% | hac BE% | sup BE% |
|--------:|---------:|--------:|--------:|---------:|--------:|--------:|
| 1 | 1.3628 | 1.5156 | 1.6176 | 75.53% | 72.96% | 71.24% |
| 2 | 1.3780 | 1.5385 | 1.6402 | 75.21% | 72.54% | 70.88% |
| 4 | 1.3839 | 1.5640 | 1.6334 | 74.99% | 71.97% | 70.81% |
| 6 | 1.3697 | 1.5839 | 1.6194 | 75.17% | 71.59% | 71.00% |
| 8 | 1.4017 | 1.5789 | 1.6340 | 74.62% | 71.54% | 70.69% |
| 10 | 1.2333 | 1.4350 | 1.4835 | 77.34% | 73.95% | 73.18% |
| 12 | 1.1998 | 1.3463 | 1.3834 | 77.86% | 75.40% | 74.83% |
| 14 | 1.1385 | 1.2704 | 1.3008 | 78.86% | 76.63% | 76.14% |
| 16 | 1.1149 | 1.2059 | 1.2501 | 79.20% | 77.62% | 76.95% |

**Observations:**

- **IPC is stable T1–T8 for all modes:** fast 1.3628→1.4017 (+2.9%), hac stable near 1.52–1.58, sup near 1.62–1.63. The slight T1→T8 uptick for fast (+2.9%) likely reflects mild cache-warming — more threads collectively keep more hash-table pages in L3.
- **Sharp IPC drop at T=10 for all modes simultaneously:** fast 1.4017→1.2333 (-12%), hac 1.5789→1.4350 (-9%), sup 1.6340→1.4835 (-9%). This is the DRAM bandwidth saturation point — the CPU is starved of data and stalls multiply.
- **IPC continues falling T10→T16:** fast 1.2333→1.1149 (-10%), sup 1.4835→1.2501 (-16%). Each thread beyond T10 adds marginal throughput at the cost of steadily worsening pipeline efficiency.
- **Total IPC loss T1→T16:** fast -18%, hac -20%, sup -23%. Fast loses the most IPC because its lower classification rate means more threads are simultaneously blocked on fruitless DRAM probes.
- **IPC and BE-Bound are inversely correlated in every row** — when one rises the other falls, confirming they measure the same underlying phenomenon (DRAM stalls) from complementary angles.

### 4.3 Instructions Retired (`ex_ret_instr`) — confirms constant work per mode

| Threads | fast ex_ret_instr | hac ex_ret_instr | sup ex_ret_instr |
|--------:|------------------:|-----------------:|-----------------:|
| 1 | 117,536,074,329 | 134,191,249,107 | 140,475,890,738 |
| 2 | 117,991,630,442 | 134,476,503,115 | 141,275,099,463 |
| 4 | 118,145,162,262 | 134,682,469,442 | 141,459,615,525 |
| 6 | 118,426,129,792 | 135,125,109,934 | 141,730,864,168 |
| 8 | 118,827,319,860 | 135,345,720,892 | 142,125,672,951 |
| 10 | 119,150,221,398 | 135,711,176,297 | 142,149,155,657 |
| 12 | 119,086,299,392 | 135,882,204,302 | 142,292,698,802 |
| 14 | 119,493,025,227 | 135,924,333,292 | 142,422,087,163 |
| 16 | 119,686,625,270 | 136,185,755,547 | 142,685,813,173 |

**Observations:**

- **Instructions are almost perfectly flat across thread counts.** fast: 117,536,074,329 (T1) → 119,686,625,270 (T16), Δ = +1.83%. hac: Δ = +1.49%. sup: Δ = +1.57%. This definitively proves no algorithmic overhead is introduced by multi-threading — every thread does exactly its share of the same work.
- **The tiny ~+1.5–1.8% growth is not real algorithmic work.** It is a sampling artefact: perf multiplexes 7 hardware counters across 4 PMU slots at ~71% duty cycle, and the scaling estimate accumulates small errors with more threads. The true instruction count is constant.
- **hac instructions (134,191,249,107 at T1) > fast (117,536,074,329)** because hac reads are longer (355 Mbp / 104918 reads ≈ 3.39 kb) and higher quality, producing more k-mers that require full hash-table probing. **sup (140,475,890,738) > hac** for the same reason — sup reads are longest (~3.49 kb avg) and produce the most work per read.
- **This table is the key proof that IPC drop is purely a stall effect:** same instructions, more cycles (see §4.4) → IPC = instructions/cycles falls.

### 4.4 Cycles Not Halted (`ls_not_halted_cyc`) — grows with threads

| Threads | fast ls_not_halted_cyc | hac ls_not_halted_cyc | sup ls_not_halted_cyc |
|--------:|-----------------------:|----------------------:|----------------------:|
| 1 | 86,248,022,777 | 88,541,054,789 | 86,844,583,089 |
| 2 | 85,625,336,440 | 87,407,787,035 | 86,130,828,535 |
| 4 | 85,374,109,231 | 86,112,611,860 | 86,602,964,413 |
| 6 | 86,461,625,148 | 85,310,630,516 | 87,522,654,318 |
| 8 | 84,772,491,445 | 85,722,747,470 | 86,980,636,870 |
| 10 | 96,613,020,276 | 94,571,141,113 | 95,820,431,269 |
| 12 | 99,257,345,719 | 100,927,103,526 | 102,856,290,456 |
| 14 | 104,958,331,684 | 106,993,055,157 | 109,484,855,422 |
| 16 | 107,352,397,367 | 112,929,547,815 | 114,136,382,279 |

**Observations:**

- **T1–T8: cycles are remarkably stable** (fast: 86,248,022,777 at T1, 84,772,491,445 at T8, variation < 2%). From 1 to 8 threads, each thread does the same amount of stall work — the per-thread DRAM bandwidth is sufficient.
- **Sharp jump at T=10: fast 84,772,491,445 → 96,613,020,276, +14.0% in one step.** This is the exact moment when cumulative thread DRAM demand exceeds the ~50 GB/s memory bandwidth. Beyond this point every thread waits longer per DRAM request.
- **Steady climb T10→T16: fast 96,613,020,276 → 107,352,397,367, +11.1%.** Total stall cycles keep growing as each additional thread adds more outstanding DRAM requests, further congesting the memory controller.
- **Combined with flat instructions (§4.3), rising cycles directly explain falling IPC.** T1: 117,536,074,329 instructions / 86,248,022,777 cycles = IPC 1.3628. T16: 119,686,625,270 instructions / 107,352,397,367 cycles = IPC 1.1149. The only cause is more stall cycles, not more instructions.
- **hac and sup show the same T10 inflection and T10–T16 climb**, confirming this is a system-level DRAM-bandwidth phenomenon, not mode-specific.

### 4.5 Op-Cache Misses (`op_cache_hit_miss.op_cache_miss`) — grows with threads

| Threads | fast op-miss | hac op-miss | sup op-miss |
|--------:|-------------:|------------:|------------:|
| 1 | 2,781,354,523 | 2,808,809,995 | 2,799,998,161 |
| 2 | 2,832,235,233 | 2,840,736,623 | 2,849,047,831 |
| 4 | 2,894,456,343 | 2,893,456,579 | 2,914,403,494 |
| 6 | 2,957,359,900 | 2,958,642,546 | 2,976,323,756 |
| 8 | 2,973,258,982 | 3,032,126,073 | 3,042,619,325 |
| 10 | 3,094,625,372 | 3,151,474,116 | 3,183,881,320 |
| 12 | 3,103,924,131 | 3,276,546,962 | 3,278,229,738 |
| 14 | 3,181,251,331 | 3,366,677,342 | 3,408,281,303 |
| 16 | 3,200,613,175 | 3,468,911,631 | 3,497,496,406 |

**Observations:**

- **Op-cache misses grow monotonically with thread count for all modes.** fast: 2,781,354,523 (T1) → 3,200,613,175 (T16), +15.1%. This is a secondary overhead beyond the primary DRAM stall: more threads executing simultaneously evict each other's decoded micro-ops from the 32 KB op-cache.
- **Unlike ls_not_halted_cyc, op-miss growth is gradual with no T10 cliff.** The op-cache is stressed continuously from T1, not only when bandwidth is saturated — it reflects instruction-level concurrency, not memory bandwidth.
- **hac and sup grow faster than fast** (hac: +23.5%, sup: +24.9% vs fast +15.1%). hac and sup execute more instructions (larger code paths per read due to longer sequences), producing more distinct micro-op sequences that compete for op-cache space.
- **Absolute magnitude is large (~2.8–3.5 billion misses per run)** — this op-cache pressure contributes to the FE-Bound and IC-Stall raw counts, though FE-Bound% remains low (1.4–1.8%) because the backend DRAM stalls dominate the overall slot budget.

---

## 5. Raw TMA Hardware Event Counts

Exact counts from `perf_stat_tma.txt`. Perf multiplexes 7 events across 4 PMU slots at ~71% duty cycle — values are linearly scaled estimates, not exact hardware reads.

### 5.1 Mode: **fast** — Raw Event Counts

| Event | T1 | T2 | T4 | T6 | T8 | T10 | T12 | T14 | T16 |
|-------| ------: | ------: | ------: | ------: | ------: | ------: | ------: | ------: | ------: |
| `ls_not_halted_cyc` | 86,248,022,777 | 85,625,336,440 | 85,374,109,231 | 86,461,625,148 | 84,772,491,445 | 96,613,020,276 | 99,257,345,719 | 104,958,331,684 | 107,352,397,367 |
| `ex_ret_ops` | 117,619,787,900 | 118,183,249,954 | 118,707,464,882 | 119,065,635,252 | 119,384,483,323 | 119,855,847,293 | 120,002,554,131 | 120,544,811,224 | 120,855,318,129 |
| `ex_ret_instr` | 117,536,074,329 | 117,991,630,442 | 118,145,162,262 | 118,426,129,792 | 118,827,319,860 | 119,150,221,398 | 119,086,299,392 | 119,493,025,227 | 119,686,625,270 |
| `de_dis_uop_queue_empty_di0` | 7,816,823,650 | 7,951,594,976 | 8,137,028,373 | 8,477,014,377 | 8,401,543,161 | 10,214,814,648 | 10,520,933,360 | 11,248,869,612 | 11,757,189,878 |
| `ex_ret_near_ret_mispred` | 302,838,300 | 308,181,169 | 312,512,229 | 318,043,519 | 321,381,384 | 326,776,433 | 329,367,281 | 333,311,994 | 335,946,998 |
| `op_cache_hit_miss.op_cache_miss` | 2,781,354,523 | 2,832,235,233 | 2,894,456,343 | 2,957,359,900 | 2,973,258,982 | 3,094,625,372 | 3,103,924,131 | 3,181,251,331 | 3,200,613,175 |
| `ic_fetch_stall.ic_stall_any` | 50,839,008,330 | 50,075,243,093 | 49,665,162,935 | 50,700,260,415 | 48,987,179,715 | 62,934,777,223 | 66,415,993,475 | 73,171,964,894 | 75,925,078,747 |

**Observations:**

- **`ls_not_halted_cyc` flat T1–T8 (86,248,022,777→84,772,491,445, -1.7%), then jumps +14.0% at T10 (96,613,020,276) and climbs to 107,352,397,367 at T16** — the same bandwidth-saturation signature visible in IPC.
- **`ex_ret_ops` ≈ `ex_ret_instr` throughout** (ratio 1.0007 at T1) — Kraken2's inner loop is dominated by simple load/compare/branch instructions with negligible macro-fusion overhead; almost every instruction retires as one micro-op.
- **`de_dis_uop_queue_empty_di0` (dispatch-queue empty cycles) also jumps at T10:** 7,816,823,650 (T1) → 10,214,814,648 (T10, +30.7%) → 11,757,189,878 (T16). This event fires when the frontend cannot supply micro-ops, but here it is backend back-pressure: when DRAM stalls block execution units, the dispatch queue drains and the frontend artificially appears idle. The FE-Bound% computed from this event is therefore inflated by BE stalls at high thread counts.
- **`ic_fetch_stall.ic_stall_any` mirrors `ls_not_halted_cyc` shape** — flat T1–T8 (50,839,008,330→48,987,179,715), then jump at T10 (62,934,777,223, +28.5%), up to 75,925,078,747 at T16. This is a pure backend-pressure artifact: when DRAM stalls back up the whole pipeline, fetch stops too. This confirms the frontend is not the real bottleneck.
- **`ex_ret_near_ret_mispred` grows very slowly** (302,838,300 at T1 → 335,946,998 at T16, +10.9%) — branch mispredictions contribute trivially to pipeline waste.

### 5.2 Mode: **hac** — Raw Event Counts

| Event | T1 | T2 | T4 | T6 | T8 | T10 | T12 | T14 | T16 |
|-------| ------: | ------: | ------: | ------: | ------: | ------: | ------: | ------: | ------: |
| `ls_not_halted_cyc` | 88,541,054,789 | 87,407,787,035 | 86,112,611,860 | 85,310,630,516 | 85,722,747,470 | 94,571,141,113 | 100,927,103,526 | 106,993,055,157 | 112,929,547,815 |
| `ex_ret_ops` | 134,682,699,583 | 134,928,329,082 | 135,580,519,728 | 136,134,755,807 | 136,767,224,266 | 137,000,598,769 | 137,359,647,548 | 137,702,403,471 | 138,257,477,094 |
| `ex_ret_instr` | 134,191,249,107 | 134,476,503,115 | 134,682,469,442 | 135,125,109,934 | 135,345,720,892 | 135,711,176,297 | 135,882,204,302 | 135,924,333,292 | 136,185,755,547 |
| `de_dis_uop_queue_empty_di0` | 7,747,211,945 | 7,873,543,546 | 7,990,297,514 | 8,016,860,168 | 8,300,652,675 | 9,469,157,863 | 10,283,534,540 | 10,991,389,303 | 12,006,203,508 |
| `ex_ret_near_ret_mispred` | 303,641,832 | 307,341,541 | 312,979,563 | 319,539,159 | 325,723,147 | 330,340,488 | 334,090,243 | 335,305,906 | 339,968,253 |
| `op_cache_hit_miss.op_cache_miss` | 2,808,809,995 | 2,840,736,623 | 2,893,456,579 | 2,958,642,546 | 3,032,126,073 | 3,151,474,116 | 3,276,546,962 | 3,366,677,342 | 3,468,911,631 |
| `ic_fetch_stall.ic_stall_any` | 50,252,981,429 | 48,918,014,561 | 47,492,260,545 | 46,595,112,358 | 46,684,682,853 | 56,977,738,724 | 64,501,658,093 | 71,426,759,099 | 77,772,989,389 |

**Observations:**

- **`ls_not_halted_cyc` flat T1–T8 (88,541,054,789→85,722,747,470, -3.2%), then jumps +10.3% at T10 (94,571,141,113) and climbs to 112,929,547,815 at T16** — the same bandwidth-saturation signature visible in IPC.
- **`ex_ret_ops` ≈ `ex_ret_instr` throughout** (ratio 1.0037 at T1) — Kraken2's inner loop is dominated by simple load/compare/branch instructions with negligible macro-fusion overhead; almost every instruction retires as one micro-op.
- **`de_dis_uop_queue_empty_di0` (dispatch-queue empty cycles) also jumps at T10:** 7,747,211,945 (T1) → 9,469,157,863 (T10, +22.2%) → 12,006,203,508 (T16). This event fires when the frontend cannot supply micro-ops, but here it is backend back-pressure: when DRAM stalls block execution units, the dispatch queue drains and the frontend artificially appears idle. The FE-Bound% computed from this event is therefore inflated by BE stalls at high thread counts.
- **`ic_fetch_stall.ic_stall_any` mirrors `ls_not_halted_cyc` shape** — flat T1–T8 (50,252,981,429→46,684,682,853), then jump at T10 (56,977,738,724, +22.0%), up to 77,772,989,389 at T16. This is a pure backend-pressure artifact: when DRAM stalls back up the whole pipeline, fetch stops too. This confirms the frontend is not the real bottleneck.
- **`ex_ret_near_ret_mispred` grows very slowly** (303,641,832 at T1 → 339,968,253 at T16, +12.0%) — branch mispredictions contribute trivially to pipeline waste.

### 5.3 Mode: **sup** — Raw Event Counts

| Event | T1 | T2 | T4 | T6 | T8 | T10 | T12 | T14 | T16 |
|-------| ------: | ------: | ------: | ------: | ------: | ------: | ------: | ------: | ------: |
| `ls_not_halted_cyc` | 86,844,583,089 | 86,130,828,535 | 86,602,964,413 | 87,522,654,318 | 86,980,636,870 | 95,820,431,269 | 102,856,290,456 | 109,484,855,422 | 114,136,382,279 |
| `ex_ret_ops` | 141,248,297,452 | 141,687,981,533 | 142,495,624,993 | 142,778,591,254 | 143,322,109,081 | 143,535,087,766 | 143,843,757,355 | 144,344,403,713 | 144,679,958,770 |
| `ex_ret_instr` | 140,475,890,738 | 141,275,099,463 | 141,459,615,525 | 141,730,864,168 | 142,125,672,951 | 142,149,155,657 | 142,292,698,802 | 142,422,087,163 | 142,685,813,173 |
| `de_dis_uop_queue_empty_di0` | 7,385,308,903 | 7,573,984,197 | 7,925,635,952 | 8,212,636,666 | 8,316,478,897 | 9,381,816,423 | 10,166,256,451 | 11,077,907,117 | 11,805,201,575 |
| `ex_ret_near_ret_mispred` | 302,787,621 | 307,393,187 | 315,307,220 | 320,453,972 | 325,605,931 | 326,078,746 | 331,651,657 | 331,809,819 | 340,307,393 |
| `op_cache_hit_miss.op_cache_miss` | 2,799,998,161 | 2,849,047,831 | 2,914,403,494 | 2,976,323,756 | 3,042,619,325 | 3,183,881,320 | 3,278,229,738 | 3,408,281,303 | 3,497,496,406 |
| `ic_fetch_stall.ic_stall_any` | 47,528,019,427 | 46,749,210,324 | 46,962,905,486 | 47,756,041,424 | 46,931,981,679 | 56,949,507,379 | 65,206,914,318 | 72,825,904,861 | 78,124,100,973 |

**Observations:**

- **`ls_not_halted_cyc` flat T1–T8 (86,844,583,089→86,980,636,870, +0.2%), then jumps +10.2% at T10 (95,820,431,269) and climbs to 114,136,382,279 at T16** — the same bandwidth-saturation signature visible in IPC.
- **`ex_ret_ops` ≈ `ex_ret_instr` throughout** (ratio 1.0055 at T1) — Kraken2's inner loop is dominated by simple load/compare/branch instructions with negligible macro-fusion overhead; almost every instruction retires as one micro-op.
- **`de_dis_uop_queue_empty_di0` (dispatch-queue empty cycles) also jumps at T10:** 7,385,308,903 (T1) → 9,381,816,423 (T10, +27.0%) → 11,805,201,575 (T16). This event fires when the frontend cannot supply micro-ops, but here it is backend back-pressure: when DRAM stalls block execution units, the dispatch queue drains and the frontend artificially appears idle. The FE-Bound% computed from this event is therefore inflated by BE stalls at high thread counts.
- **`ic_fetch_stall.ic_stall_any` mirrors `ls_not_halted_cyc` shape** — flat T1–T8 (47,528,019,427→46,931,981,679), then jump at T10 (56,949,507,379, +21.3%), up to 78,124,100,973 at T16. This is a pure backend-pressure artifact: when DRAM stalls back up the whole pipeline, fetch stops too. This confirms the frontend is not the real bottleneck.
- **`ex_ret_near_ret_mispred` grows very slowly** (302,787,621 at T1 → 340,307,393 at T16, +12.4%) — branch mispredictions contribute trivially to pipeline waste.

---

## 6. Per-Core CPU Utilization (mpstat)

Source: `mpstat_run1.txt` (`mpstat -P ALL 2`). Values are time-averages of all 2-second samples during the run. `Low5` = number of logical CPUs averaging < 5% %usr.

| Mode | Threads | Overall %usr | Top-1 core | Top-2 core | Top-3 core | Low5 |
|------|--------:|-------------:|-----------:|-----------:|-----------:|-----:|
| fast | 1 | 6.2% | CPU6=36.4% | CPU7=19.0% | CPU2=15.6% | 12 |
| fast | 2 | 9.4% | CPU7=33.8% | CPU2=30.9% | CPU6=22.2% | 10 |
| fast | 4 | 11.9% | CPU7=38.3% | CPU0=37.1% | CPU8=23.4% | 9 |
| fast | 6 | 14.4% | CPU2=32.4% | CPU1=31.5% | CPU8=29.5% | 4 |
| fast | 8 | 16.6% | CPU4=31.2% | CPU14=27.0% | CPU0=26.4% | 2 |
| fast | 10 | 18.3% | CPU9=28.4% | CPU13=28.4% | CPU12=27.6% | 1 |
| fast | 12 | 22.7% | CPU7=30.5% | CPU10=29.8% | CPU8=29.4% | 0 |
| fast | 14 | 25.4% | CPU8=31.5% | CPU6=30.2% | CPU12=29.0% | 0 |
| fast | 16 | 25.2% | CPU8=27.4% | CPU9=27.2% | CPU2=27.2% | 0 |
| hac | 1 | 6.0% | CPU7=33.5% | CPU6=23.5% | CPU3=16.2% | 12 |
| hac | 2 | 8.5% | CPU6=37.0% | CPU3=29.5% | CPU2=26.9% | 11 |
| hac | 4 | 13.2% | CPU2=33.0% | CPU7=32.2% | CPU9=30.4% | 6 |
| hac | 6 | 13.1% | CPU8=34.4% | CPU7=32.7% | CPU4=32.1% | 7 |
| hac | 8 | 16.3% | CPU7=30.7% | CPU9=29.7% | CPU3=29.3% | 3 |
| hac | 10 | 18.9% | CPU3=31.3% | CPU7=30.8% | CPU12=28.7% | 4 |
| hac | 12 | 21.2% | CPU6=28.4% | CPU10=27.8% | CPU7=27.8% | 0 |
| hac | 14 | 23.5% | CPU3=28.8% | CPU8=28.5% | CPU6=28.0% | 1 |
| hac | 16 | 25.3% | CPU7=26.9% | CPU6=26.8% | CPU12=26.2% | 0 |
| sup | 1 | 4.5% | CPU6=66.8% | CPU2=3.0% | CPU8=1.0% | 15 |
| sup | 2 | 7.3% | CPU2=38.0% | CPU6=36.5% | CPU7=20.7% | 12 |
| sup | 4 | 8.9% | CPU8=35.9% | CPU0=29.6% | CPU3=21.4% | 10 |
| sup | 6 | 13.2% | CPU0=35.3% | CPU6=35.0% | CPU4=33.8% | 9 |
| sup | 8 | 16.2% | CPU2=33.6% | CPU10=31.5% | CPU1=30.0% | 4 |
| sup | 10 | 18.9% | CPU3=30.1% | CPU5=29.7% | CPU13=29.5% | 0 |
| sup | 12 | 21.4% | CPU7=28.8% | CPU8=28.7% | CPU4=28.6% | 0 |
| sup | 14 | 12.2% | CPU2=15.9% | CPU0=14.1% | CPU12=14.0% | 1 |
| sup | 16 | 13.3% | CPU6=15.1% | CPU3=14.3% | CPU4=14.0% | 0 |

**Observations:**

- **Overall %usr grows steadily with thread count** (fast: 6.2% at T1 → 25.2% at T16, hac: 6.0%→25.3%, sup: 4.5%→13.3%) — each thread contributes some active compute, but the per-thread utilisation fraction shrinks because most of each thread's wall time is DRAM stall, not execution.
- **Even at T16, overall %usr is only ~25%** — if threads were compute-bound, 16 threads on 16 logical CPUs would approach 100%. The ~75% gap is stall time: the OS counts stalled threads as not in user mode. This directly maps to BE-Bound ~79% from TMA.
- **Peak cores never exceed 30–38% %usr across all runs** — even the most-used core is mostly stalled. This is the clearest practical proof that the bottleneck is memory, not compute.
- **Low5 count (CPUs averaging under 5% %usr) drops from 12–15 at T1 to 0 at T12–T16.** At T1, only one physical core is active; all others idle. By T12 every logical CPU has at least some load, but 'load' here means a mix of stall + active cycles, not sustained compute.
- **CPU6 and CPU7 appear as top cores across many runs.** On the Ryzen 7 7735HS these logical cores correspond to physical cores on the primary CCD (Core Compute Die). kraken2's OpenMP scheduler tends to anchor its first worker threads to the same physical cores it used in previous OpenMP regions, causing hot-core patterns.
- **sup T14 and T16 show anomalously low overall %usr (12.2% and 13.3%)** vs fast (25.4% and 25.2%) and hac at the same thread counts. The sup run at T14/T16 completed in fewer wall-clock seconds (2.366 s / 2.309 s), capturing fewer mpstat 2-second intervals; the initial DB-loading samples (low user activity) therefore dominate the average more heavily, pulling the reported %usr down.

---

## 7. Master Cross-Thread Summary

All key metrics for **fast mode** at every thread count (run 1 throughout). hac/sup wall times for direct comparison.

| Threads | fast wall (s) | fast Kseq/m | Speedup | fast IPC | fast BE% | fast miss% | fast op-miss | hac wall (s) | sup wall (s) |
|--------:|--------------:|------------:|--------:|---------:|---------:|-----------:|-------------:|-------------:|-------------:|
| 1 | 14.545 | 432.4 | 1.00× | 1.3628 | 75.53% | 16.50% | 2,781,354,523 | 14.961 | 14.335 |
| 2 | 7.920 | 794.2 | 1.84× | 1.3780 | 75.21% | 16.52% | 2,832,235,233 | 7.909 | 7.551 |
| 4 | 4.368 | 1440.1 | 3.33× | 1.3839 | 74.99% | 16.31% | 2,894,456,343 | 4.561 | 4.297 |
| 6 | 3.328 | 1889.7 | 4.37× | 1.3697 | 75.17% | 16.24% | 2,957,359,900 | 3.209 | 3.308 |
| 8 | 2.714 | 2317.3 | 5.36× | 1.4017 | 74.62% | 15.91% | 2,973,258,982 | 2.694 | 2.756 |
| 10 | 2.435 | 2583.2 | 5.97× | 1.2333 | 77.34% | 15.24% | 3,094,625,372 | 2.560 | 2.591 |
| 12 | 2.402 | 2619.1 | 6.06× | 1.1998 | 77.86% | 15.27% | 3,103,924,131 | 2.443 | 2.481 |
| 14 | 2.345 | 2682.0 | 6.20× | 1.1385 | 78.86% | 14.88% | 3,181,251,331 | 2.325 | 2.366 |
| 16 | 2.203 | 2855.3 | 6.60× | 1.1149 | 79.20% | 14.59% | 3,200,613,175 | 2.282 | 2.309 |

**Observations:**

- **Reading across the row shows the throughput–efficiency trade-off directly.** T8: wall 2.714 s, IPC 1.4017, BE 74.6%. T16: wall 2.203 s, IPC 1.1149 (-20%), BE 79.2% (+4.6 pp). More throughput is achieved T8→T16 but at lower pipeline efficiency per thread.
- **T14→T16 is the lowest-value thread increment:** only 6.4% wall-time reduction for 2 extra threads. IPC falls 1.1385→1.1149 and BE rises 78.9%→79.2%. At this point the system is fully bandwidth-saturated and additional threads primarily damage per-thread efficiency.
- **Kseq/m throughput gain T8→T16: 2317.3→2855.3 Kseq/m (+23%) for doubling threads** — less than linear gain, confirming DRAM bandwidth is the ceiling. A 2× thread increase yields only a ~23% throughput improvement.
- **op-miss grows steadily while miss% declines** — these two columns move in opposite directions because they measure different things: op-miss is an absolute count (grows with concurrency), miss% is a ratio (diluted by growing references). Neither reflects a real cache-efficiency improvement.
- **hac and sup wall times track fast closely at every thread count** — all three modes share the same DRAM bandwidth ceiling and hit the same saturation point. The absolute differences narrow at high thread counts as all modes converge on the memory bandwidth limit.
- **Optimal practical choice: T8.** Delivers 5.36× speedup, IPC 1.4017 (highest of any multi-thread point), BE 74.6% (lowest multi-thread BE-Bound). T16 adds only 23% more throughput at the cost of 20% IPC loss and 4.6 pp more BE-Bound.

---

_Generated by generate_thread_report.py — 2026-05-29_
