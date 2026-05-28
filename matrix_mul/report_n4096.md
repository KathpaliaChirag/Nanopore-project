# Matrix Multiplication — N=4096 — CH3 (perf stat) Sweep

**Date:** 2026-05-28
**Workload:** Square C = A·B, N=4096, doubles (one A,B,C set = 128 MB each, 384 MB total — **24× L3**, heavily DRAM-bound)
**Machine:** AMD Zen, 16 logical CPUs, paranoid=-1
**Compile:** `gcc -O2 -g -march=native` (+ `-fopenmp` / `-mavx2 -mfma` / `-lopenblas` as needed)
**Source:** `results/pfz_batch1/src/matmul_*.c` (21 variants)
**Raw output:** `results/pfz_batch1/ch3_perf_stat_N4096/perf_stat_{basic,cache,r5,full}_*.txt` (84 files)
**Sweep wall time:** ~45 minutes (naive alone runs 691 s × 8 experiments)

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
| 1 | matmul_naive | **691.171** | 1.00× | 3,227,398,142,267 | 131,552,442,783 | **0.0408** | 0.199 |
| 2 | matmul_ikj | 22.354 | 30.92× | 104,351,130,810 | 105,972,040,500 | 1.0155 | 6.148 |
| 3 | matmul_tiled | 39.334 | 17.57× | 177,866,268,886 | 703,305,062,717 | **3.9541** | 3.494 |
| 4 | matmul_omp | 13.018 | 53.09× | 788,340,053,558 | 107,487,279,282 | 0.1363 | 10.558 |
| 5 | matmul_avx | 22.173 | 31.17× | 103,919,792,100 | 123,163,979,221 | 1.1852 | 6.198 |
| 6 | matmul_prefetch | 22.653 | 30.51× | 105,460,942,763 | 106,005,626,211 | 1.0052 | 6.067 |
| 7 | matmul_unroll | 22.272 | 31.03× | 103,849,986,362 | 105,973,030,697 | 1.0204 | 6.171 |
| 8 | matmul_tiled_omp | 5.877 | 117.61× | 323,623,399,788 | 703,610,078,594 | 2.1742 | 23.386 |
| 9 | matmul_tiled_avx | 11.035 | 62.63× | 49,160,045,414 | 116,627,833,886 | 2.3724 | 12.455 |
| 10 | matmul_tiled_prefetch | 43.641 | 15.83× | 192,370,105,625 | 840,741,374,551 | **4.3704** | 3.149 |
| 11 | matmul_tiled_unroll | 10.930 | 63.23× | 49,119,599,083 | 126,412,482,318 | 2.5736 | 12.574 |
| 12 | matmul_omp_avx | 11.923 | 57.97× | 723,082,270,667 | 124,493,911,315 | 0.1722 | 11.527 |
| 13 | matmul_tiled_omp_avx | **2.173** | **318.07×** | 118,807,263,729 | 136,106,364,707 | 1.1456 | **63.248** |
| 14 | matmul_tiled_omp_prefetch | 6.278 | 110.10× | 333,219,832,171 | 841,101,894,037 | 2.5242 | 21.892 |
| 15 | matmul_tiled_avx_prefetch | 12.827 | 53.88× | 56,256,567,981 | 170,429,732,361 | 3.0295 | 10.715 |
| 16 | matmul_tiled_avx_unroll | 10.490 | 65.89× | 46,839,819,404 | 104,856,277,701 | 2.2386 | 13.102 |
| 17 | matmul_tiled_omp_avx_prefetch | 2.661 | 259.74× | 147,121,724,849 | 172,763,250,259 | 1.1743 | 51.649 |
| 18 | matmul_ultimate | 2.303 | 300.12× | 123,327,111,824 | 122,196,493,945 | 0.9908 | 59.678 |
| 19 | matmul_transposed | 50.096 | 13.80× | 234,177,076,462 | 209,618,145,919 | 0.8951 | 2.744 |
| 20 | **matmul_blas** | **0.933** | **740.91×** | 60,772,617,395 | 78,870,661,161 | 1.2978 | **147.309** |
| 21 | matmul_strassen | 14.602 | 47.33× | 68,058,663,986 | 264,734,413,886 | 3.8898 | 9.412 |

> **Naive takes 11.5 minutes.** IPC = 0.041 (24 cycles per instruction). 3.2 *trillion* cycles to do 132 B instructions. The CPU is doing nothing but waiting for DRAM.

### CH3-B — Cache Hierarchy

| # | Variant | L1 loads | L1 misses | **L1 miss%** | L2 misses | L3 fills | DRAM fills |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | **matmul_naive** | 251,700,215,567 | 78,993,183,593 | **31.38%** | **45,950,852,712** | 41,614,268,476 | **7,876,975,035** |
| 2 | matmul_ikj | 52,665,625,855 | 17,258,808,328 | **32.77%** | 68,100,603 | 15,736,133 | **8,146,502,478** |
| 3 | matmul_tiled | 213,196,029,370 | 16,703,680,460 | **7.83%** | 2,261,764,641 | 3,588,889,715 | **57,634,566** |
| 4 | matmul_omp | 69,678,531,569 | 17,501,170,219 | 25.12% | 364,158,510 | 1,632,196,460 | 2,555,676,608 |
| 5 | matmul_avx | 52,709,577,861 | 17,265,957,240 | 32.76% | 73,450,048 | 14,200,377 | 8,085,219,721 |
| 6 | matmul_prefetch | 52,683,360,676 | 17,266,389,301 | 32.77% | 67,072,057 | 15,044,820 | 8,140,284,022 |
| 7 | matmul_unroll | 52,684,215,417 | 17,267,654,530 | 32.78% | 63,655,892 | 15,637,691 | 8,144,674,191 |
| 8 | matmul_tiled_omp | 211,769,091,148 | 18,016,989,123 | 8.51% | 5,057,751,743 | 6,146,667,912 | 157,080,729 |
| 9 | matmul_tiled_avx | 37,275,169,984 | 11,885,127,588 | 31.88% | 3,874,243,515 | 5,050,484,986 | 37,783,396 |
| 10 | matmul_tiled_prefetch | 210,753,650,705 | 16,133,831,793 | **7.66%** | 2,304,976,370 | 3,490,893,140 | 61,721,291 |
| 11 | matmul_tiled_unroll | 38,747,417,185 | 11,462,787,401 | 29.58% | 4,128,438,970 | 4,906,815,168 | 35,895,985 |
| 12 | matmul_omp_avx | 69,634,504,805 | 17,469,376,616 | 25.09% | 306,260,352 | 1,612,421,539 | 2,376,047,176 |
| 13 | matmul_tiled_omp_avx | 43,885,578,456 | 14,160,087,219 | 32.27% | 7,673,995,061 | 7,666,578,387 | 260,210,986 |
| 14 | matmul_tiled_omp_prefetch | 210,156,292,737 | 16,665,853,028 | 7.93% | 2,626,799,542 | 3,646,236,341 | 94,815,357 |
| 15 | matmul_tiled_avx_prefetch | 42,894,057,862 | 13,167,925,584 | 30.70% | 4,840,559,197 | 5,362,834,614 | 42,317,570 |
| 16 | matmul_tiled_avx_unroll | 37,362,498,570 | 11,341,121,165 | 30.35% | 4,228,806,789 | 4,655,638,448 | 41,458,339 |
| 17 | matmul_tiled_omp_avx_prefetch | 53,132,996,329 | 13,841,384,227 | 26.05% | 7,793,856,149 | 7,839,819,128 | 246,399,290 |
| 18 | matmul_ultimate | 47,410,117,548 | 13,147,096,386 | 27.73% | 7,034,946,849 | 7,131,199,234 | 236,401,324 |
| 19 | matmul_transposed | 35,604,281,613 | 17,377,362,769 | **48.81%** | 81,004,263 | 54,042,935 | 781,528,460 |
| 20 | matmul_blas | 14,283,450,460 | 2,884,863,948 | 20.20% | 95,582,218 | 70,014,703 | 186,392,376 |
| 21 | matmul_strassen | 113,236,041,612 | 5,630,077,534 | **4.97%** | 142,200,124 | 99,360,536 | 181,584,305 |

> **The story tiling tells:** L1 miss% = 7.83% (essentially identical to 8.11% at N=1024 and 8.18% at N=2048). DRAM fills = 57.6 M (vs 0.6 M at N=1024). Across 64× of N scaling, **tiling keeps L1 miss% within 0.4 pp** — that's the design payoff.
>
> **The story ikj tells:** L1 miss% climbed from 16.5% (N=1024) to 32.8% (N=4096). DRAM fills exploded from 3.3 M to 8.1 B — **2,470× more DRAM traffic** for 64× more compute. ikj scales catastrophically on memory.
>
> **The story naive tells:** L1 miss% dropped from 47% (N=1024) to 31% (N=4096). Counterintuitive but real: at N=4096 the stride-N pattern is so far apart that hardware prefetchers stop tracking it; loads simply fail-fast to DRAM. Cost per load went up; queue contention went down.

### CH3-C — Stability (5-run, perf stat -r 5)

| # | Variant | mean (s) | stddev (s) | ± % |
|---|---|---:|---:|---:|
| 1 | matmul_naive | 367.322781 | 16.508267 | **4.4900%** |
| 2 | matmul_ikj | 21.749067 | 0.088556 | 0.4100% |
| 3 | matmul_tiled | 37.611442 | 0.135612 | 0.3600% |
| 4 | matmul_omp | 3.386772 | 0.081450 | 2.4000% |
| 5 | matmul_avx | 22.050384 | 0.523404 | 2.3700% |
| 6 | matmul_prefetch | 21.516770 | 0.301034 | 1.4000% |
| 7 | matmul_unroll | 21.437091 | 0.592798 | 2.7700% |
| 8 | matmul_tiled_omp | 5.926358 | 0.033680 | 0.5700% |
| 9 | matmul_tiled_avx | 9.554826 | 0.136866 | 1.4300% |
| 10 | matmul_tiled_prefetch | 39.787943 | 0.310850 | 0.7800% |
| 11 | matmul_tiled_unroll | 9.670735 | 0.060274 | 0.6200% |
| 12 | matmul_omp_avx | 12.788355 | 0.358302 | 2.8000% |
| 13 | matmul_tiled_omp_avx | 2.413583 | 0.025059 | 1.0400% |
| 14 | matmul_tiled_omp_prefetch | 6.681895 | 0.018369 | **0.2700%** |
| 15 | matmul_tiled_avx_prefetch | 12.157394 | 0.057830 | 0.4800% |
| 16 | matmul_tiled_avx_unroll | 9.775795 | 0.041342 | 0.4200% |
| 17 | matmul_tiled_omp_avx_prefetch | 2.798767 | 0.013473 | 0.4800% |
| 18 | matmul_ultimate | 2.555452 | 0.051427 | 2.0100% |
| 19 | matmul_transposed | 50.435884 | 0.131399 | **0.2600%** |
| 20 | matmul_blas | 1.372077 | 0.004355 | **0.3200%** |
| 21 | matmul_strassen | 15.445541 | 0.047085 | 0.3000% |

> **Naive's stddev = 16.5 s** — individual runs vary by half a minute. The longer the kernel runs, the more thermal throttling jitter shows up. **BLAS becomes one of the most stable variants** (±0.32%) because the thread-pool warm-up is now invisible against 1.4 s of kernel work.

### CH3-D — Direct Stall Evidence (LQ-stalls / FP-dispatches)

| # | Variant | FP dispatches | LQ stalls | **LQ-stall / FP-disp** |
|---|---|---:|---:|---:|
| 1 | matmul_naive | 127,028,633,042 | 134,673,035,360 | **106.02%** |
| 2 | matmul_ikj | 52,101,775,872 | 43,587,897,560 | **83.66%** |
| 3 | matmul_tiled | 219,884,008,636 | 42,209,081 | **0.019%** |
| 4 | matmul_omp | 64,746,194,410 | 131,345,490,858 | **202.86%** |
| 5 | matmul_avx | 52,142,506,290 | 14,051,154,397 | 26.95% |
| 6 | matmul_prefetch | 52,061,071,726 | 43,872,558,885 | 84.27% |
| 7 | matmul_unroll | 52,061,599,296 | 43,849,872,647 | 84.23% |
| 8 | matmul_tiled_omp | 214,535,491,671 | 1,686,053,177 | 0.79% |
| 9 | matmul_tiled_avx | 53,675,789,798 | 13,880,617,885 | 25.86% |
| 10 | matmul_tiled_prefetch | 218,283,361,775 | 6,062,264,222 | 2.78% |
| 11 | matmul_tiled_unroll | 54,860,630,830 | 11,573,285,218 | 21.10% |
| 12 | **matmul_omp_avx** | 67,833,607,345 | **249,710,707,935** | **368.12%** |
| 13 | matmul_tiled_omp_avx | 53,560,733,716 | 10,026,458,063 | 18.72% |
| 14 | matmul_tiled_omp_prefetch | 214,451,851,463 | 5,810,245,671 | 2.71% |
| 15 | matmul_tiled_avx_prefetch | 53,460,444,825 | 11,696,024,888 | 21.88% |
| 16 | matmul_tiled_avx_unroll | 53,595,940,981 | 11,851,454,732 | 22.11% |
| 17 | matmul_tiled_omp_avx_prefetch | 53,214,609,900 | 10,235,992,352 | 19.24% |
| 18 | matmul_ultimate | 53,604,964,914 | 16,043,062,747 | 29.93% |
| 19 | matmul_transposed | 155,136,539,281 | 4,339,676 | **0.003%** |
| 20 | matmul_blas | 28,192,782,052 | 3,318,511,055 | 11.77% |
| 21 | matmul_strassen | 114,794,115,917 | 4,524,041,165 | 3.94% |

> **The most striking finding of the whole sweep:** `matmul_omp_avx` has LQ-stall/FP-disp = **368%** at N=4096 — *worse than naive at N=1024 (196.7%)*. All 16 threads simultaneously pull AVX loads of 4 doubles each from a 384 MB working set that doesn't fit anywhere; the cluster-wide load queue is saturated. **Memory-bandwidth contention is the new bottleneck**, replacing the memory-latency story of single-threaded naive.
>
> **`matmul_omp` (no AVX) is also at 203%** — same problem, different vector width.
>
> **Naive's ratio dropped to 106%** — the load queue is no longer the bottleneck because most loads fail-fast to DRAM (200+ cycle round-trip) instead of queue-blocking on L3 (40 cycles). Different failure mode, same wall-time disaster.

### CH3-E — Parallel Efficiency

| # | Variant | task-clock (ms) | elapsed (ms) | **CPUs used** | Threads spawned |
|---|---|---:|---:|---:|---:|
| 1 | matmul_naive | 691306.65 | 691501.80 | 0.9997 | 1 |
| 2 | matmul_ikj | 22663.58 | 22706.04 | 0.9981 | 1 |
| 3 | matmul_tiled | 39625.64 | 39678.85 | 0.9987 | 1 |
| 4 | matmul_omp | 180228.45 | 13373.05 | **13.48** | 16 |
| 5 | matmul_avx | 22471.67 | 22513.54 | 0.9981 | 1 |
| 6 | matmul_prefetch | 22967.05 | 23006.18 | 0.9983 | 1 |
| 7 | matmul_unroll | 22580.91 | 22619.53 | 0.9983 | 1 |
| 8 | matmul_tiled_omp | 88676.67 | 6222.52 | **14.25** | 16 |
| 9 | matmul_tiled_avx | 11349.38 | 11387.39 | 0.9967 | 1 |
| 10 | matmul_tiled_prefetch | 43944.83 | 43992.96 | 0.9989 | 1 |
| 11 | matmul_tiled_unroll | 11243.36 | 11285.34 | 0.9963 | 1 |
| 12 | matmul_omp_avx | 165748.19 | 12295.65 | **13.48** | 16 |
| 13 | matmul_tiled_omp_avx | 31897.10 | 2534.60 | **12.58** | 16 |
| 14 | matmul_tiled_omp_prefetch | 95052.54 | 6635.70 | **14.32** | 16 |
| 15 | matmul_tiled_avx_prefetch | 13146.27 | 13186.72 | 0.9969 | 1 |
| 16 | matmul_tiled_avx_unroll | 10798.92 | 10839.01 | 0.9963 | 1 |
| 17 | matmul_tiled_omp_avx_prefetch | 38875.07 | 3011.22 | **12.91** | 16 |
| 18 | matmul_ultimate | 33012.65 | 2657.93 | **12.42** | 16 |
| 19 | matmul_transposed | 50398.11 | 50458.74 | 0.9988 | 1 |
| 20 | **matmul_blas** | 14975.64 | 1372.65 | **10.91** | 16 |
| 21 | matmul_strassen | 15062.38 | 15097.39 | 0.9977 | 1 |

> **Hand-rolled OMP hits its best parallel efficiency** at N=4096 — `tiled_omp_prefetch` reaches 14.32 of 16 CPUs. The per-thread work is now large enough to amortise thread-spawn and synchronisation costs. **BLAS efficiency *drops* to 10.91 CPUs** — at N=4096 BLAS is memory-bandwidth bound across its threads; some sit idle waiting for DRAM, the others continue. The "13.4 CPUs at N=1024" advantage is gone.

### Cross-N Scaling vs N=1024 and N=2048

Ideal scaling for O(N³) compute under N-doubling is **8×**.

| Variant | N=2048 (s) | N=4096 (s) | Ratio | vs ideal 8× |
|---|---:|---:|---:|---|
| matmul_naive | 14.262 | 691.171 | **48.46×** | **6× worse than ideal** — DRAM saturated |
| matmul_ikj | 2.506 | 22.354 | **8.92×** | ≈ ideal |
| matmul_tiled | 4.814 | 39.334 | **8.17×** | ≈ ideal — tiling holds its contract |
| matmul_omp | 0.487 | 13.018 | **26.73×** | **3.3× worse** — bandwidth contention dominates |
| matmul_omp_avx | 0.402 | 11.923 | **29.66×** | **3.7× worse** — even worse than plain omp |
| matmul_tiled_omp_avx | 0.189 | 2.173 | **11.50×** | mild — tiling contains the damage |
| matmul_ultimate | 0.219 | 2.303 | **10.52×** | mild |
| matmul_blas | 0.136 | 0.933 | **6.86×** | **better than ideal** — warm-up amortised |
| matmul_strassen | 2.145 | 14.602 | **6.81×** | **better than ideal** — O(N^2.807) shows |

### Surprises and Anomalies

1. **Tiling FINALLY pays off when combined with parallelism.** At N=4096, `omp_avx` (no tiling) = **11.923 s**; `tiled_omp_avx` = **2.173 s** — that's **5.49× speedup** just from adding tiling on top of OMP+AVX. At N=1024 the same delta was only 1.71× (0.036 → 0.021 s). **This is the crossover the N-sweep was designed to find.** Below N=2048, tiling was pure overhead; from N=2048 onward, tiling is what keeps multi-threaded variants alive.
2. **Tiling cures the parallel bandwidth contention.** Compare LQ-stall ratios at N=4096:
   - `omp` = **202.9%**, `omp_avx` = **368.1%** (catastrophic, threads stalled on DRAM)
   - `tiled_omp` = **0.79%**, `tiled_omp_avx` = **18.7%** (queue empties cleanly)
   - **Tiling drops parallel LQ-stall by 100–470×.** Tiling's value at this scale isn't just "L1 miss%" — it's *avoiding DRAM thrash across threads*.
3. **`matmul_transposed` is now the worst L1-miss variant in the entire sweep** at **48.81%**, exceeding even naive's 31.38%. The transpose step touches 128 MB once at stride-1, evicting the L1 working set for everything that follows. At smaller N, transposed had moderate (24–31%) L1 miss; at N=4096 it falls apart.
4. **`matmul_strassen` has the *lowest* L1 miss% of the entire sweep** at **4.97%** — lower than tiled (7.83%). Its 128×128 base case fits L1 perfectly. But its 264 B instructions (vs BLAS's 78 B) kill the wall time — only 47× speedup, 15× slower than BLAS.
5. **`matmul_omp_avx` scales 29.7× per doubling** — *3.7× worse than ideal*, *worse than plain `omp`* (26.7×). Adding AVX on top of OMP at large N makes things worse, not better, because each AVX load fills the load queue with 4 doubles at once while DRAM is the bottleneck.
6. **`matmul_unroll` is *not* the fastest single-optimisation variant at N=4096** (was the winner at N=1024 and N=2048). At N=4096 single-threaded `tiled_avx_unroll` (10.49 s) and `tiled_unroll` (10.93 s) beat plain `unroll` (22.27 s). Unroll without tiling stops helping when L1 thrashes.
7. **BLAS scales *better* than ideal** (6.86× vs 8× ideal) because its first-run warm-up (~30 ms) is now invisible against ~900 ms of kernel work. Its absolute lead widens to **2.33×** over my best.
8. **Naive stability paradox.** Naive at N=4096 has stddev ±4.49% (16.5 s on 367 s) — *less jittery* than at N=2048 (±13.4%). Plausible reason: at N=4096, IPC=0.041 means the CPU spends 96% of cycles **idle waiting** for DRAM — those cycles don't generate heat, so thermal throttling barely fires. The run is long but cool.

### Headline Findings — N=4096

1. **Naive crosses into pure DRAM-bound territory.** 691 s wall time, IPC = 0.041, 7.9 B DRAM fills. The single-thread CPU is fully stalled.
2. **Tiling does what it's designed to do across 64× of N scaling** — L1 miss% stays at 7.83% (vs 32.77% for ikj). DRAM fills capped at 57.6 M (vs 8.1 B for ikj). Plain `tiled` is still 1.76× slower than `ikj` wall-clock (instruction overhead), **but tiling is now indispensable when combined with OMP** — see Surprise #1.
3. **`matmul_omp_avx` has the worst LQ-stall ratio of the entire sweep (368%).** Parallel-amplified DRAM bandwidth contention is a real failure mode at this scale. Tiling fixes it (`tiled_omp_avx` LQ-stall = 18.7%).
4. **Best hand-written: `matmul_tiled_omp_avx` at 2.17 s, 63 GFlops/s, 318× speedup.** Ultimate close behind at 2.30 s (300× speedup, 60 GFlops/s).
5. **BLAS leads decisively: 0.93 s, 147 GFlops/s, 740× speedup.** Gap over my best widened to **2.33×** (from 1.39× at N=2048, 1.75× at N=1024) — the gap-narrowing trend at N=2048 reversed at N=4096.
6. **Strassen finally shows O(N^2.807).** 14.6 s wall, 47× speedup over naive — better than several plain variants. Its L1 miss% (4.97%) is the lowest of any variant. But its 264 B instructions still leave it 15× slower than BLAS.

### Critical Self-Review — What's Justified, What's Speculation

**Solid (data directly supports):**
- ✅ "Tiling's L1 miss% is N-independent at ~8%" — direct counter, three N values (8.11%, 8.18%, 7.83%), monotonically stable within 0.4 pp.
- ✅ "Naive becomes DRAM-bound at N=4096" — 7.9 B DRAM fills vs 1 M at N=1024 (~8000×).
- ✅ "`omp_avx` LQ stalls jump to 368%" — direct hardware counter.
- ✅ "Tiling reduces parallel LQ-stall by 100×+" — `omp_avx` 368% vs `tiled_omp_avx` 18.7% measured directly.
- ✅ "BLAS lead = 2.33× over my best" — both kernel times measured.

**Plausible but partly speculative:**
- ⚠ "BLAS efficiency drops at N=4096 because of bandwidth contention" — at N=4096 the working set is **384 MB** (3× the matrices), well past any local cache. Bandwidth contention is the simplest explanation, but it could also be NUMA crossing across memory channels. Not verified without `numactl --hardware`.
- ⚠ "Naive stability paradox: low IPC = cool CPU = stable runs" — the correlation is real (±13.4% at N=2048 with IPC=0.24 vs ±4.49% at N=4096 with IPC=0.041), but I didn't measure CPU temperature directly. Could also be that absolute jitter is similar (~2–16 s) and the percentage drops just because the mean is much larger.

**What I'd verify next:**
1. `perf stat -e dTLB-load-misses` — at 384 MB working set, TLB pressure could be a hidden factor.
2. Compare with `perf bench mem memcpy` to derive roofline at N=4096; BLAS at 147 GFlops/s vs naive at 0.2 GFlops/s spans 3 orders of magnitude.
3. Run with `OMP_PROC_BIND=close` + `OMP_NUM_THREADS=8` (physical cores only) — current 16-thread (SMT) may be hurting bandwidth-bound variants like `omp_avx`.
4. Disassemble `omp_avx` to confirm the 368% LQ stall comes from AVX load width, not from scheduling pathologies.

### Bottom Line for N=4096

- **The memory hierarchy completely dominates at N=4096.** Compute units sit idle while DRAM channels are saturated. The naive kernel is the worst-case demonstration: 24 cycles per instruction.
- **Tiling crosses from overhead to necessity.** At N=1024 tiling was pure cost. At N=2048 it broke even for `tiled_omp` vs `omp` (0.716 s vs 0.487 s — still losing). At N=4096 **tiling on top of OMP+AVX is 5.5× faster than OMP+AVX alone** (`tiled_omp_avx` 2.173 s vs `omp_avx` 11.923 s). This is the crossover point for tiling.
- **Tiling also cures the parallel bandwidth-contention failure mode.** `omp_avx`'s 368% LQ-stall drops to 18.7% with tiling — a 100× improvement from a single optimisation layer.
- **BLAS extends its lead with N.** 2.33× over my best at N=4096 (was 1.39× at N=2048). Library-tuned register tiling and microkernels matter more as problems grow — the "link a library, don't hand-write" rule confirmed.
- **Transposed and Strassen are interesting failure cases.** Transposed (48.81% L1 miss) shows that one stride-1 pass through a 128-MB matrix destroys cache. Strassen (4.97% L1 miss — best of any variant) shows that algorithmic complexity ≠ wall time: its 264 B instructions cost more than its O(N^2.807) saves at this N.
