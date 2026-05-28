# Matrix Multiplication Performance Benchmark Suite

A collection of matrix multiplication implementations designed for `perf stat` analysis. Each variant isolates a specific optimisation technique so you can directly compare cache behaviour, IPC, vectorisation, and parallelism.

---

## Implementations

| Binary | Source | Technique | Key perf insight |
|---|---|---|---|
| `naive_ijk` | `naive_ijk.c` | Plain ijk loop order | Baseline. B is accessed column-by-column (strided) — worst LLC miss rate |
| `ikj_order` | `ikj_order.c` | Loop reordered to ikj | A[i][k] held in a register; B-row streamed sequentially → big drop in cache misses |
| `kij_order` | `kij_order.c` | Loop reordered to kij | Both C and B rows streamed; A has strided access across outer k loop |
| `transpose_B` | `transpose_B.c` | Pre-transpose B, then ijk | Both A-row and Bt-row fully sequential; reveals cost of the extra O(N²) transpose pass |
| `tiled` | `tiled.c` | Cache blocking (default 64×64 tiles) | Sub-matrices fit in L2; compare L1/LLC miss% vs ikj |
| `omp_parallel` | `omp_parallel.c` | OpenMP ikj, outer loop parallelised | Scales linearly with cores; watch for false sharing and memory bandwidth saturation |
| `omp_tiled` | `omp_tiled.c` | OpenMP + cache blocking | Best combination for multi-core + cache hierarchy |
| `unrolled_ikj` | `unrolled_ikj.c` | 4× manual inner-loop unroll | Reduces loop overhead; more ILP exposed — compare IPC and branch-miss% |
| `avx2_manual` | `avx2_manual.c` | Explicit AVX2 `_mm256_fmadd_pd` | Forces 4-wide SIMD FMA; compare throughput vs compiler auto-vec |
| `auto_vec_O3` | `auto_vec_O3.c` | `restrict` pointers + `-O3 -march=native` | Compiler-generated SIMD; check if GCC matches the hand-written AVX2 version |
| `tiled_avx2` | `tiled_avx2.c` | Cache blocking + explicit AVX2 FMA | Peak single-thread throughput target |
| `prefetch_ikj` | `prefetch_ikj.c` | IKJ + `__builtin_prefetch` | Compares software prefetch vs hardware prefetcher — look at `hw-prefetch-misses` |

---

## Requirements

- GCC (7+) with AVX2/FMA support (`-mavx2 -mfma`)
- OpenMP (`libgomp`, usually bundled with GCC)
- `perf` (Linux kernel perf tools)
- CPU: Haswell / Zen 2 or newer for AVX2 + FMA

Check your CPU supports AVX2:
```bash
grep -m1 avx2 /proc/cpuinfo
```

---

## Build

### Build everything (default)
```bash
make
```

### Build with a specific tile size (for the tiled variants)
```bash
make tile32          # builds tiled_t32, omp_tiled_t32, tiled_avx2_t32 with TILE=32
```

### Clean
```bash
make clean
```

---

## Running

Matrix size `N` is passed as a runtime argument. Default is **1024** if no argument is given.

```bash
./naive_ijk           # N=1024
./naive_ijk 2048      # N=2048
OMP_NUM_THREADS=8 ./omp_parallel 1024
```

---

## perf stat

### Run all binaries via Makefile
```bash
make run_perf                        # N=1024, 4 threads
make run_perf SIZE=2048 THREADS=8   # N=2048, 8 threads
```
Individual results saved to `perf_results/<binary>.txt`.

### Run all binaries via the shell script (summary table)
```bash
chmod +x run_perf_all.sh
./run_perf_all.sh              # N=1024, 4 threads
./run_perf_all.sh 2048 8       # N=2048, 8 threads
```

The script prints a side-by-side summary table:

```
================================================================
 Matrix Multiplication perf stat  N=1024  OMP_NUM_THREADS=4
================================================================
Binary              Time(ms)          IPC    L1-miss%    LLC-miss%    Br-miss%
----------------------------------------------------------------
naive_ijk               4821         0.87       12.34%       8.21%       0.03%
ikj_order               1102         2.41        1.05%       0.42%       0.02%
...
================================================================
```

Full raw perf output for each binary is saved in `perf_results/*_raw.txt`.

### Run a single binary manually
```bash
perf stat -e cache-misses,cache-references,L1-dcache-load-misses,L1-dcache-loads,\
LLC-load-misses,LLC-loads,instructions,cycles,branches,branch-misses \
./ikj_order 1024
```

---

## What to look for

| Metric | What it tells you |
|---|---|
| **LLC miss %** | How well the access pattern fits in cache. High = lots of DRAM traffic |
| **L1 miss %** | Inner-loop cache behaviour. High in naive_ijk due to column-stride access on B |
| **IPC** | Instructions per cycle. Low IPC = stalls (memory-bound). High = compute-bound |
| **Branch miss %** | Should be near zero for all variants — confirms loop structure is predictable |
| **Time (ms)** | Wall-clock execution time — the bottom line |

### Expected ranking (fastest → slowest, single thread)
```
tiled_avx2 ≈ avx2_manual > auto_vec_O3 ≈ tiled > unrolled_ikj ≈ ikj_order > kij_order ≈ transpose_B > naive_ijk
```

### Expected LLC miss ranking (lowest → highest)
```
tiled_avx2 ≈ tiled ≈ omp_tiled < ikj_order ≈ kij_order ≈ auto_vec_O3 < transpose_B < naive_ijk
```

---

## File layout

```
All_Matric_Mul_perf_stats/
├── naive_ijk.c
├── ikj_order.c
├── kij_order.c
├── transpose_B.c
├── tiled.c
├── omp_parallel.c
├── omp_tiled.c
├── unrolled_ikj.c
├── avx2_manual.c
├── auto_vec_O3.c
├── tiled_avx2.c
├── prefetch_ikj.c
├── Makefile
├── run_perf_all.sh
└── README.md
```
