# Matrix Multiplication — N=2048 — CH3 (perf stat) Sweep

**Date:** 2026-05-28
**Workload:** Square C = A·B, N=2048, doubles (one A,B,C set = 32 MB each, 96 MB total — **6× L3**, DRAM traffic begins)
**Machine:** AMD Zen, 16 logical CPUs, paranoid=-1
**Compile:** `gcc -O2 -g -march=native` (+ `-fopenmp` / `-mavx2 -mfma` / `-lopenblas` as needed)
**Source:** `results/pfz_batch1/src/matmul_*.c` (21 variants)
**Raw output:** `results/pfz_batch1/ch3_perf_stat_N2048/perf_stat_{basic,cache,r5,full}_*.txt` (84 files)

### Abbreviations

| Term | Meaning |
|------|---------|
| L1 | Level-1 cache (closest to CPU core, fastest, smallest ~64 KB) |
| L2 | Level-2 cache (per-core, ~512 KB) |
| L3 | Level-3 cache (shared across cores, ~16 MB on this machine) |
| DRAM | Dynamic Random-Access Memory (main system memory, ~100 ns latency) |
| IPC | Instructions Per Cycle (higher = better CPU utilisation; stalled pipelines show <0.5) |
| OMP | OpenMP (API for shared-memory parallel programming via compiler directives) |
| AVX2 | Advanced Vector Extensions 2 (Intel/AMD CPU SIMD instruction set, 256-bit wide) |
| SIMD | Single Instruction Multiple Data (CPU feature that processes multiple data elements at once) |
| BLAS | Basic Linear Algebra Subprograms (standard library for matrix/vector operations) |
| GFlops/s | Giga Floating-point Operations per second (throughput measure) |
| LQ-stall | Load Queue stall (pipeline slot waiting for a memory load to complete) |
| FP-disp | Floating-Point dispatch slots (pipeline slots used for floating-point operations) |
| TMA | Top-down Microarchitecture Analysis (Intel/AMD method to classify pipeline slot usage) |
| BE-Bound | Backend-Bound (pipeline slots stalled waiting on memory or execution units) |
| FE-Bound | Frontend-Bound (pipeline slots stalled because the decoder can't supply micro-ops fast enough) |

---

### Variant Inventory

5 optimisation primitives, composed:
- **T** Tiling (TILE=64) — cache blocking
- **O** OpenMP — requests 16 threads on outer loop
- **A** AVX2 SIMD — `_mm256_fmadd_pd`, 4 doubles/instr
- **P** Software prefetch — `__builtin_prefetch` 8 elements ahead
- **U** Manual unroll — 4× (or 2× when combined with AVX = 8 doubles/iter)

| Tier | Variants |
|------|----------|
| Baseline | naive (ijk) |
| Loop-reorder | ikj |
| Singles | tiled, omp, avx, prefetch, unroll |
| Doubles | tiled_omp, tiled_avx, tiled_prefetch, tiled_unroll, omp_avx |
| Triples | tiled_omp_avx, tiled_omp_prefetch, tiled_avx_prefetch, tiled_avx_unroll |
| Quad | tiled_omp_avx_prefetch |
| Ultimate | tiled+omp+avx+prefetch+unroll |
| Reference | transposed, blas (OpenBLAS dgemm), strassen |

### CH3-A — Wall Time, IPC, GFlops/s

Kernel time from binary-internal `clock_gettime`. GFlops/s = 2N³ / kernel_time.

| # | Variant | kernel s | speedup | cycles | instructions | **IPC** | GFlops/s |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | matmul_naive | **14.262** | 1.00× | 66,551,394,308 | 15,841,165,697 | **0.2380** | 1.205 |
| 2 | matmul_ikj | 2.506 | 5.69× | 11,895,456,241 | 13,572,468,426 | 1.1410 | 6.855 |
| 3 | matmul_tiled | 4.814 | 2.96× | 21,759,417,693 | 88,222,361,067 | **4.0544** | 3.569 |
| 4 | matmul_omp | 0.487 | 29.29× | 25,515,931,705 | 13,640,168,924 | 0.5346 | 35.277 |
| 5 | matmul_avx | 2.768 | 5.15× | 13,118,340,664 | 15,742,993,737 | 1.2001 | 6.207 |
| 6 | matmul_prefetch | 2.609 | 5.47× | 12,328,451,359 | 13,581,912,128 | 1.1017 | 6.585 |
| 7 | matmul_unroll | 2.669 | 5.34× | 12,569,977,390 | 13,573,054,145 | 1.0798 | 6.437 |
| 8 | matmul_tiled_omp | 0.716 | 19.92× | 38,947,712,410 | 88,292,381,721 | 2.2669 | 23.994 |
| 9 | matmul_tiled_avx | 1.115 | 12.79× | 5,218,037,835 | 14,889,811,883 | 2.8535 | 15.408 |
| 10 | matmul_tiled_prefetch | 5.436 | 2.62× | 24,348,453,599 | 105,417,259,364 | **4.3295** | 3.160 |
| 11 | matmul_tiled_unroll | 1.234 | 11.56× | 5,802,688,614 | 16,112,114,865 | 2.7767 | 13.922 |
| 12 | matmul_omp_avx | 0.402 | 35.48× | 22,355,414,334 | 15,788,624,027 | 0.7063 | 42.736 |
| 13 | matmul_tiled_omp_avx | **0.189** | **75.46×** | 10,432,589,810 | 17,340,935,080 | 1.6622 | **90.899** |
| 14 | matmul_tiled_omp_prefetch | 0.752 | 18.97× | 40,095,766,867 | 105,459,156,611 | 2.6302 | 22.846 |
| 15 | matmul_tiled_avx_prefetch | 1.591 | 8.96× | 7,278,044,548 | 21,614,967,593 | 2.9699 | 10.798 |
| 16 | matmul_tiled_avx_unroll | 1.302 | 10.95× | 6,070,555,731 | 13,418,828,544 | 2.2105 | 13.195 |
| 17 | matmul_tiled_omp_avx_prefetch | 0.233 | 61.21× | 12,907,139,631 | 21,934,886,103 | 1.6994 | 73.733 |
| 18 | matmul_ultimate | 0.219 | 65.12× | 11,882,531,204 | 15,598,387,291 | 1.3127 | 78.447 |
| 19 | matmul_transposed | 5.818 | 2.45× | 27,878,256,662 | 26,549,624,828 | 0.9523 | 2.953 |
| 20 | **matmul_blas** | **0.136** | **104.87×** | 14,845,867,619 | 10,462,824,333 | 0.7048 | **126.323** |
| 21 | matmul_strassen | 2.145 | 6.65× | 10,424,643,712 | 38,722,460,574 | 3.7145 | 8.009 |

### CH3-B — Cache Hierarchy

| # | Variant | L1 loads | L1 misses | **L1 miss%** | L2 misses | L3 fills | DRAM fills |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | **matmul_naive** | 8,173,832,421 | 3,917,871,031 | **47.93%** | **1,762,780,138** | 1,319,348,245 | **666,487,472** |
| 2 | matmul_ikj | 6,706,457,652 | 1,484,001,941 | 22.13% | 6,409,434 | 2,915,739 | 761,804,965 |
| 3 | matmul_tiled | 26,813,789,302 | 2,192,355,131 | **8.18%** | 79,865,045 | 155,614,764 | 6,494,900 |
| 4 | matmul_omp | 8,421,808,206 | 2,067,121,363 | 24.54% | 10,025,800 | 132,592,018 | 57,215,230 |
| 5 | matmul_avx | 6,707,870,371 | 1,346,789,345 | 20.08% | 10,193,180 | 4,839,584 | 750,010,096 |
| 6 | matmul_prefetch | 6,706,116,567 | 1,482,519,258 | 22.11% | 6,916,160 | 3,092,776 | 769,465,981 |
| 7 | matmul_unroll | 6,714,167,999 | 1,494,999,522 | 22.27% | 7,144,553 | 3,457,767 | 771,642,375 |
| 8 | matmul_tiled_omp | 26,601,183,619 | 2,241,495,835 | 8.43% | 244,651,894 | 371,969,458 | 15,052,426 |
| 9 | matmul_tiled_avx | 4,800,924,759 | 1,507,443,160 | 31.40% | 507,525,756 | 655,130,646 | 4,489,791 |
| 10 | matmul_tiled_prefetch | 26,473,645,368 | 1,975,772,145 | **7.46%** | 196,725,022 | 290,862,299 | 8,376,183 |
| 11 | matmul_tiled_unroll | 4,962,064,729 | 1,426,598,472 | 28.75% | 443,104,926 | 502,313,319 | 4,943,271 |
| 12 | matmul_omp_avx | 8,570,273,718 | 2,010,856,446 | 23.46% | 14,999,997 | 165,050,623 | 108,126,513 |
| 13 | matmul_tiled_omp_avx | 5,576,614,439 | 1,755,006,847 | 31.47% | 927,803,791 | 955,232,758 | 24,029,167 |
| 14 | matmul_tiled_omp_prefetch | 26,386,097,264 | 2,077,185,100 | 7.87% | 195,323,019 | 283,517,436 | 10,065,199 |
| 15 | matmul_tiled_avx_prefetch | 5,875,617,042 | 1,612,141,223 | 27.44% | 274,144,860 | 293,752,198 | 6,621,340 |
| 16 | matmul_tiled_avx_unroll | 4,769,262,264 | 1,418,766,031 | 29.75% | 326,712,402 | 353,196,842 | 5,943,128 |
| 17 | matmul_tiled_omp_avx_prefetch | 6,757,146,785 | 1,688,345,041 | 24.99% | 371,342,267 | 382,710,980 | 18,723,253 |
| 18 | matmul_ultimate | 6,220,618,844 | 1,616,413,663 | 25.98% | 287,693,557 | 283,917,794 | 17,676,647 |
| 19 | matmul_transposed | 4,575,558,171 | 1,403,799,190 | 30.68% | 15,132,993 | 13,103,888 | 84,386,353 |
| 20 | matmul_blas | 2,206,240,889 | 377,945,090 | 17.13% | 14,321,806 | 10,718,227 | 32,440,132 |
| 21 | matmul_strassen | 16,556,588,146 | 824,346,501 | **4.98%** | 20,734,911 | 14,251,130 | 23,616,244 |

> **Naive's DRAM fills jumped from 1 M (at N=1024) to 666 M** — a 666× increase against only 8× more compute. Naive has crossed from L3-latency-bound to mixed L3+DRAM-bound. **Tiled keeps DRAM fills at 6.5 M** — tiling does its job. **ikj also takes 762 M DRAM fills** — its inner row of B (16 KB) still fits L1, but the column accesses of A cross over.

### CH3-C — Stability (5-run, perf stat -r 5)

| # | Variant | mean (s) | stddev (s) | ± % |
|---|---|---:|---:|---:|
| 1 | matmul_naive | 15.660940 | 2.100695 | **13.4100%** |
| 2 | matmul_ikj | 2.453736 | 0.008782 | 0.3600% |
| 3 | matmul_tiled | 4.682098 | 0.038553 | 0.8200% |
| 4 | matmul_omp | 0.480646 | 0.011310 | 2.3500% |
| 5 | matmul_avx | 2.549070 | 0.003226 | **0.1300%** |
| 6 | matmul_prefetch | 2.448972 | 0.001871 | **0.0800%** |
| 7 | matmul_unroll | 2.472953 | 0.009247 | 0.3700% |
| 8 | matmul_tiled_omp | 0.786841 | 0.004116 | 0.5200% |
| 9 | matmul_tiled_avx | 1.136030 | 0.032776 | 2.8900% |
| 10 | matmul_tiled_prefetch | 4.961977 | 0.037857 | 0.7600% |
| 11 | matmul_tiled_unroll | 1.101931 | 0.005885 | 0.5300% |
| 12 | matmul_omp_avx | 0.479117 | 0.007954 | 1.6600% |
| 13 | matmul_tiled_omp_avx | 0.281641 | 0.004905 | 1.7400% |
| 14 | matmul_tiled_omp_prefetch | 0.842650 | 0.010487 | 1.2400% |
| 15 | matmul_tiled_avx_prefetch | 1.396639 | 0.035211 | 2.5200% |
| 16 | matmul_tiled_avx_unroll | 1.135077 | 0.022865 | 2.0100% |
| 17 | matmul_tiled_omp_avx_prefetch | 0.309743 | 0.003326 | 1.0700% |
| 18 | matmul_ultimate | 0.287512 | 0.005804 | 2.0200% |
| 19 | matmul_transposed | 5.939265 | 0.007656 | 0.1300% |
| 20 | matmul_blas | 0.261211 | 0.005295 | 2.0300% |
| 21 | matmul_strassen | 2.296993 | 0.004275 | 0.1900% |

> **Naive is the wild outlier (±13.4%)** — 15.66 s mean with 2.10 s stddev. Individual runs vary from 13 s to 18 s. Thermal throttling kicks in during the long run. Single-threaded `prefetch` and `avx` are the most stable (±0.08–0.13%): full instruction throughput, no thread spawning.

### CH3-D — Direct Stall Evidence (LQ-stalls / FP-dispatches)

| # | Variant | FP dispatches | LQ stalls | **LQ-stall / FP-disp** |
|---|---|---:|---:|---:|
| 1 | **matmul_naive** | 10,985,156,564 | **15,024,002,674** | **136.77%** |
| 2 | matmul_ikj | 6,570,312,118 | 1,657,170,097 | 25.22% |
| 3 | matmul_tiled | 27,478,894,932 | 1,837,403 | **0.007%** |
| 4 | matmul_omp | 8,653,198,112 | 7,673,340,590 | **88.68%** |
| 5 | matmul_avx | 6,602,336,997 | 388,916,579 | 5.89% |
| 6 | matmul_prefetch | 6,623,073,086 | 1,635,262,116 | 24.69% |
| 7 | matmul_unroll | 6,611,207,623 | 1,664,384,522 | 25.18% |
| 8 | matmul_tiled_omp | 26,861,994,894 | 51,640,467 | 0.19% |
| 9 | matmul_tiled_avx | 6,715,054,914 | 1,527,050,238 | 22.74% |
| 10 | matmul_tiled_prefetch | 27,321,399,399 | 526,539,175 | 1.93% |
| 11 | matmul_tiled_unroll | 6,870,994,770 | 1,245,362,002 | 18.12% |
| 12 | matmul_omp_avx | 8,453,833,188 | 6,973,363,922 | **82.49%** |
| 13 | matmul_tiled_omp_avx | 6,674,332,162 | 1,061,798,451 | 15.91% |
| 14 | matmul_tiled_omp_prefetch | 26,853,146,489 | 422,150,042 | 1.57% |
| 15 | matmul_tiled_avx_prefetch | 6,768,106,868 | 1,809,269,884 | 26.73% |
| 16 | matmul_tiled_avx_unroll | 6,740,246,713 | 1,765,192,320 | 26.19% |
| 17 | matmul_tiled_omp_avx_prefetch | 6,639,615,203 | 1,163,279,271 | 17.52% |
| 18 | matmul_ultimate | 6,626,089,675 | 1,328,560,824 | 20.05% |
| 19 | matmul_transposed | 19,425,164,948 | 503,316 | **0.003%** |
| 20 | matmul_blas | 3,510,528,188 | 765,770,569 | 21.81% |
| 21 | matmul_strassen | 16,218,808,699 | 597,197,200 | 3.68% |

> **Naive's LQ stalls = 136.77% of FP dispatches** — still memory-bound but lower than 196.7% at N=1024, because at larger N more loads simply fail-fast (DRAM) rather than queue-block (L3 wait). **`matmul_omp` and `matmul_omp_avx` show LQ-stall ratios of 82–89%** — at N=2048, parallel threads start to contend for DRAM bandwidth. New failure mode begins to appear.

### CH3-E — Parallel Efficiency

| # | Variant | task-clock (ms) | elapsed (ms) | **CPUs used** | Threads spawned |
|---|---|---:|---:|---:|---:|
| 1 | matmul_naive | 14337.20 | 14352.94 | 0.9989 | 1 |
| 2 | matmul_ikj | 2585.66 | 2595.43 | 0.9962 | 1 |
| 3 | matmul_tiled | 4893.63 | 4904.46 | 0.9978 | 1 |
| 4 | matmul_omp | 6346.07 | 579.28 | **10.96** | 16 |
| 5 | matmul_avx | 2847.97 | 2857.80 | 0.9966 | 1 |
| 6 | matmul_prefetch | 2692.60 | 2704.01 | 0.9958 | 1 |
| 7 | matmul_unroll | 2748.12 | 2758.37 | 0.9963 | 1 |
| 8 | matmul_tiled_omp | 10333.08 | 807.00 | **12.80** | 16 |
| 9 | matmul_tiled_avx | 1194.72 | 1203.72 | 0.9925 | 1 |
| 10 | matmul_tiled_prefetch | 5512.96 | 5524.79 | 0.9979 | 1 |
| 11 | matmul_tiled_unroll | 1311.28 | 1319.54 | 0.9937 | 1 |
| 12 | matmul_omp_avx | 5652.02 | 489.93 | **11.54** | 16 |
| 13 | matmul_tiled_omp_avx | 2864.20 | 279.08 | **10.26** | 16 |
| 14 | matmul_tiled_omp_prefetch | 11003.28 | 839.84 | **13.10** | 16 |
| 15 | matmul_tiled_avx_prefetch | 1668.76 | 1676.95 | 0.9951 | 1 |
| 16 | matmul_tiled_avx_unroll | 1380.68 | 1389.32 | 0.9938 | 1 |
| 17 | matmul_tiled_omp_avx_prefetch | 3559.64 | 321.49 | **11.07** | 16 |
| 18 | matmul_ultimate | 3299.51 | 309.43 | **10.66** | 16 |
| 19 | matmul_transposed | 5895.26 | 5908.82 | 0.9977 | 1 |
| 20 | **matmul_blas** | 3454.09 | 253.54 | **13.62** | 16 |
| 21 | matmul_strassen | 2262.80 | 2272.04 | 0.9959 | 1 |

> Hand-rolled OMP variants improve to 10–13 CPUs (was 7–12 at N=1024). Larger per-thread work amortises better against thread-spawn overhead. **BLAS still leads at 13.62 CPUs.**

### Cross-N Scaling vs N=1024 Baseline

Ideal scaling for O(N³) compute under N-doubling is **8×**. Anything worse means the memory hierarchy is fighting back.

| Variant | N=1024 (s) | N=2048 (s) | Ratio | vs ideal 8× |
|---|---:|---:|---:|---|
| matmul_naive | 1.982 | 14.262 | **7.20×** | ≈ ideal (L3 still mostly contains it) |
| matmul_ikj | 0.178 | 2.506 | **14.08×** | **1.76× worse than ideal** — L1 falls off |
| matmul_tiled | 0.590 | 4.814 | **8.16×** | ≈ ideal — tiling holds its cache contract |
| matmul_omp | 0.037 | 0.487 | **13.16×** | DRAM contention begins across threads |
| matmul_tiled_omp_avx | 0.021 | 0.189 | **9.00×** | nearly ideal |
| matmul_ultimate | 0.034 | 0.219 | **6.44×** | better than ideal — amortising overhead |
| matmul_blas | 0.012 | 0.136 | **11.33×** | first-run warm-up cost smaller relative now |
| matmul_strassen | 0.330 | 2.145 | **6.50×** | better than ideal — O(N^2.807) begins to show |

> Two variants stand out: **ikj scales 14×** (vs ideal 8×) because its row-of-B (16 KB at N=2048) now competes with A's column footprint for L1 — L1 miss% climbs from 16.52% to 22.13%. **omp scales 13×** for a different reason — threads now contend for DRAM bandwidth (see CH3-D below).

### Surprises and Anomalies

1. **OMP's load-queue stall ratio jumped an order of magnitude** in one N-doubling: 10% (N=1024) → **88.68%** (N=2048). At N=1024, OMP threads stayed in their L1 caches; at N=2048, the 32-MB-per-matrix working set forces threads to compete for DRAM. **Same code, completely different bottleneck.**
2. **Prefetch *hurts* `tiled_omp`** at N=2048: `tiled_omp` = 0.716 s, `tiled_omp_prefetch` = 0.752 s (+5%). At single-threaded tiled (4.81 s vs 5.44 s for tiled_prefetch), prefetch was also a slight regression. The tile-bookkeeping inner loop is already L1-resident, so prefetch hints just add instruction count.
3. **`matmul_tiled_avx` jumped to 31% L1 miss** (from 29% at N=1024) but is now 2.5× faster than plain `matmul_tiled` (1.115 s vs 4.81 s). The AVX inner loop has 4× fewer iterations, exposing fewer L1 misses per unit time.
4. **`matmul_unroll` is still the fastest single-optimisation variant** at 2.669 s — beating ikj, avx, prefetch — same finding as N=1024. The 4× manual unroll on top of auto-vectorised ikj remains the best single-trick ROI.
5. **BLAS lead over my best variant *narrowed*** from 1.75× (N=1024) to 1.39× (N=2048). At N=1024 BLAS pays a ~30 ms thread-pool warm-up that's a big fraction of 12 ms kernel; at N=2048 the warm-up is invisible against 136 ms of compute. **My hand-written `tiled_omp_avx` is closing the relative gap as problem size grows.** (Reversal at N=4096 — see that report.)
6. **`tiled` is now the most-instructions variant** at 88 B (vs ikj's 13.6 B and BLAS's 10.5 B). Tiled's IPC = 4.05 is best in show, yet wall time is 4.81 s — proof that IPC alone is a misleading optimisation target.

### Headline Findings — N=2048

1. **Tiling still loses on wall time** despite cutting L1 miss% to 8.18% (vs ikj's 22.13%). Tiled needs 88 B instructions vs ikj's 13.6 B — 6.5× more bookkeeping. Tiled at 4.81 s is still 1.9× slower than ikj at 2.51 s.
2. **DRAM enters the picture for naive.** L1 miss% (47.93%) is similar to N=1024, but DRAM fills jump 666× to 666 M. Naive becomes mixed L3+DRAM bound.
3. **Best variant: `matmul_tiled_omp_avx` at 0.189 s, 91 GFlops/s, 75× speedup.** Ultimate is close behind at 0.219 s.
4. **BLAS leads: 0.136 s, 126 GFlops/s, 105× speedup.** Lead over my best **narrowed** to 1.39× (from 1.75× at N=1024).
5. **OMP starts to show bandwidth contention** — `matmul_omp` LQ-stall/FP-disp = 88.68% (vs ~10% at N=1024). Multiple threads simultaneously hit DRAM.

### Critical Self-Review — What's Justified, What's Speculation

**Solid (data directly supports):**
- ✅ "Tiling's L1 miss% stays at 8.18% at N=2048" — direct hardware counter, matches the 8.11% at N=1024 within 0.07 pp.
- ✅ "ikj scales 14× per doubling, worse than ideal 8×" — direct wall-time ratio.
- ✅ "OMP LQ-stalls jumped from ~10% to 88.68%" — direct counter, order-of-magnitude.
- ✅ "BLAS lead narrowed to 1.39×" — both kernel times measured directly.

**Plausible but partly speculative:**
- ⚠ "OMP threads compete for DRAM bandwidth" — the LQ stall jump is consistent with this, but it could also be that the static schedule's 64-row chunks at N=2048 are no longer well-aligned with DRAM channel interleaving. Not verified without `numactl --hardware`.
- ⚠ "Prefetch hurts because the inner loop is already L1-resident" — measured (5% regression) but the *mechanism* is inferred; could also be the prefetch instructions themselves crossing an i-cache line.

**What I'd verify next:**
1. Disassemble `tiled_omp` vs `tiled_omp_prefetch` to confirm prefetch is adding cost via instruction count, not via i-cache pressure.
2. Run with `OMP_NUM_THREADS=8` (physical cores only) — current 16-thread on 8 physical + SMT may be the cause of DRAM contention, not the OMP layer itself.

### Bottom Line for N=2048

- **L1 working set begins to matter.** ikj's row of B is 16 KB at N=2048; A's columns cause additional L1 traffic. L1 miss% climbs to 22% from 16% at N=1024.
- **Tiling proves its cache claim but still loses its wall claim.** Tile working set (32 KB) caps L1 miss at 8% — exactly its design intent — but the 6× instruction overhead is too steep.
- **BLAS lead *narrows* at N=2048** (1.39× vs 1.75× at N=1024) because its thread-pool warm-up cost is now a smaller fraction of the larger kernel. (This reverses at N=4096.)
- **OMP variants approach scaling efficiency** of 11–13 CPUs out of 16 (vs 7–8 at N=1024), but pay a new cost in DRAM-bandwidth contention (LQ stalls 82–89%).
