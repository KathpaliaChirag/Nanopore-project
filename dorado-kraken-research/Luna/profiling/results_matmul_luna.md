# Luna — Matrix Multiply Profiling Results

> Server: luna (dell-R760) | CPU: 2× Xeon Platinum 8468 | RAM: 503 GB
> Compiler: GCC with -O3 -march=native (auto-selects AVX-512 on this CPU)
> IPC is **accurate** here — no Hyper-V throttling

---

## Key Expected Differences vs WSL2 Results

| Metric | WSL2 (reported) | Expected on Luna |
|---|---|---|
| naive_ijk IPC | 0.23 (wrong) | < 0.5 (DRAM-bound) |
| tiled_avx2 IPC | 3.04 (wrong) | 3–6 (compute-bound, tiles in L2) |
| N=1024 L3 miss rate | 22% (naive) | much lower — 210 MB L3 fits both matrices |
| N=2048 L3 miss rate | 27.6% (naive) | lower — 96 MB < 210 MB L3 |
| stalled-cycles-backend | not available | should be >80% for naive_ijk |
| LLC-load-misses | not available | measurable directly |

---

## perf stat Full Event Set (run on Luna)

```bash
perf stat -e \
  cycles,instructions,\
  LLC-load-misses,LLC-loads,\
  L1-dcache-load-misses,L1-dcache-loads,\
  stalled-cycles-backend,stalled-cycles-frontend,\
  mem-loads,mem-stores \
  ./[binary] [N]
```

---

## Results — N = 1024

> Data collected and recorded in `reports/matrix_multiplication/README.md`, section "execution time, Luna (bare metal)" and "all metrics at N=1024 (Luna)".

Condensed table (full data in the report above):

| Binary | Time (ms) | IPC | L1 miss % | LLC miss % | Stall % |
|---|---|---|---|---|---|
| `naive_ijk` | 5,703.9 | 0.22 | 48.87 | 0.022 | 83.3 |
| `ikj_order` | 333.7 | 0.81 | 15.81 | 0.074 | 44.6 |
| `kij_order` | 400.9 | 0.99 | 9.17 | 0.295 | 41.7 |
| `transpose_B` | 717.4 | 1.29 | 0.23 | 3.997 | 17.2 |
| `tiled` | 267.1 | 1.42 | 25.68 | 0.960 | 29.0 |
| `omp_parallel` | 352.2 | 1.17 | 10.76 | 0.395 | 32.1 |
| `omp_tiled` | 426.6 | 1.32 | 19.86 | 16.36 | 37.3 |
| `unrolled_ikj` | 352.1 | 1.19 | 9.10 | 0.092 | 33.0 |
| `avx2_manual` | 330.2 | 1.14 | 10.84 | 0.019 | 35.8 |
| `auto_vec_O3` | 321.8 | 0.83 | 16.06 | 0.282 | 46.9 |
| `tiled_avx2` | **220.4** | **2.84** | 13.08 | 4.965 | **13.5** |
| `prefetch_ikj` | 501.4 | **4.00** | **0.65** | 1.581 | **6.8** |

---

## Results — N = 2048

> Data collected and recorded in `reports/matrix_multiplication/README.md`, section "scaling behaviour" (Luna wall time scaling table). N=2048 row present for all 12 variants. Detailed per-metric breakdown at N=2048 not separately tabulated here; see that table for timing and scaling ratios.

| Binary | Time (ms) | Notes |
|---|---|---|
| `naive_ijk` | 47,301.6 | data present in report |
| `ikj_order` | 2,459.7 | data present in report |
| `kij_order` | 2,975.4 | data present in report |
| `transpose_B` | 5,682.1 | data present in report |
| `tiled` | 2,005.1 | data present in report |
| `omp_parallel` | 2,618.7 | data present in report |
| `omp_tiled` | 3,126.8 | data present in report |
| `unrolled_ikj` | 2,613.7 | data present in report |
| `avx2_manual` | 2,493.8 | data present in report |
| `auto_vec_O3` | 2,493.7 | data present in report |
| `tiled_avx2` | **1,621.2** | data present in report |
| `prefetch_ikj` | 3,904.1 | data present in report |

IPC, LLC miss %, and stall % at N=2048 not separately run; only timing collected at this size on Luna.

---

## TMA Breakdown (naive_ijk vs tiled_avx2)

> Data collected and recorded in `reports/matrix_multiplication/README.md`, section "TMA: top-down microarchitecture analysis (Luna)".

Key results (see report for full narrative):

| Metric | naive N=1024 | tile+AVX2 N=1024 | naive N=2048 | tile+AVX2 N=10000 |
|---|---|---|---|---|
| tma_memory_bound % | high (L3-bound 85.4%) | low (L3-bound 1.0%) | L3-bound 85.9% | 39.1% memory-bound |
| tma_core_bound % | low | 32.4% | low | — |
| tma_dram_bound % | low (data in L3) | low | increasing | 2.3% |
| omp+tile DRAM-bound @ N=10000 | — | — | — | 14.7% |

Raw TMA event counts: data pending (not separately tabulated; narrative summary above extracted from perf output during the Luna run).

---

## Cross-Machine Comparison (WSL2 vs Luna)

| Binary | WSL2 time N=1024 | Luna time N=1024 | Speedup |
|---|---|---|---|
| `naive_ijk` | 9,961 ms | 5,703.9 ms | 1.7x |
| `ikj_order` | 393 ms | 333.7 ms | 1.2x |
| `tiled_avx2` | 335 ms | 220.4 ms | 1.5x |

| Metric | WSL2 (unreliable) | Luna (accurate) |
|---|---|---|
| naive_ijk IPC | 0.23† | 0.22 |
| tiled_avx2 IPC | 3.04† | 2.84 |
| naive_ijk LLC miss% | N/A (not supported) | 0.022% (data fits in 105 MB L3) |
| naive_ijk stall-BE% | N/A (not supported) | 83.3% |
