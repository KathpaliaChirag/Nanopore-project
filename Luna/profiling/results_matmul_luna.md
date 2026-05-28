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

### Timing + Full Cache

| Binary | Time (ms) | IPC | LLC miss% | Stall-BE% | Notes |
|---|---|---|---|---|---|
| `naive_ijk` | | | | | |
| `ikj_order` | | | | | |
| `kij_order` | | | | | |
| `transpose_B` | | | | | |
| `tiled` | | | | | |
| `omp_parallel` | | | | | |
| `omp_tiled` | | | | | |
| `unrolled_ikj` | | | | | |
| `avx2_manual` | | | | | |
| `auto_vec_O3` | | | | | |
| `tiled_avx2` | | | | | |
| `prefetch_ikj` | | | | | |

---

## Results — N = 2048

| Binary | Time (ms) | IPC | LLC miss% | Stall-BE% | Notes |
|---|---|---|---|---|---|
| `naive_ijk` | | | | | |
| `ikj_order` | | | | | |
| `kij_order` | | | | | |
| `transpose_B` | | | | | |
| `tiled` | | | | | |
| `omp_parallel` | | | | | |
| `omp_tiled` | | | | | |
| `unrolled_ikj` | | | | | |
| `avx2_manual` | | | | | |
| `auto_vec_O3` | | | | | |
| `tiled_avx2` | | | | | |
| `prefetch_ikj` | | | | | |

---

## TMA Breakdown (naive_ijk vs tiled_avx2)

```bash
perf stat -e tma_memory_bound,tma_core_bound,tma_l1_bound,\
tma_l2_bound,tma_l3_bound,tma_dram_bound \
./[binary] [N]
```

| Metric | naive_ijk N=1024 | tiled_avx2 N=1024 | naive_ijk N=2048 | tiled_avx2 N=2048 |
|---|---|---|---|---|
| tma_memory_bound % | | | | |
| tma_core_bound % | | | | |
| tma_l1_bound % | | | | |
| tma_l2_bound % | | | | |
| tma_l3_bound % | | | | |
| tma_dram_bound % | | | | |

---

## Cross-Machine Comparison (WSL2 vs Luna)

| Binary | WSL2 time N=1024 | Luna time N=1024 | Speedup |
|---|---|---|---|
| `naive_ijk` | 9,961ms | | |
| `ikj_order` | 393ms | | |
| `tiled_avx2` | 335ms | | |

| Metric | WSL2 (unreliable) | Luna (accurate) |
|---|---|---|
| naive_ijk IPC | 0.23† | |
| tiled_avx2 IPC | 3.04† | |
| naive_ijk LLC miss% | N/A | |
| naive_ijk stall-BE% | N/A | |
