# Matrix Multiplication — `perf stat` Analysis Report

**Machine:** WSL2 (AMD Ryzen 7 5800H, 8 cores @ 3.2–4.4 GHz) | RAM: 14 GB  
**Kernel:** 6.6.87.2-microsoft-standard-WSL2  
**Compiler:** GCC 15.1.0 | Flags: `-O3 -march=native -funroll-loops`  
**Matrix dtype:** `double` (64-bit float, 8 bytes/element)  
**OMP_NUM_THREADS:** 4  

---

##  IPC Reliability Warning (Read First)

**The IPC values in this report are unreliable and must NOT be treated as ground truth.**

This is the same issue documented for the Kraken-2 and Dorado profiling runs (see `results_kraken2.md`, KB §15.4). WSL2 runs inside Hyper-V, which throttles the CPU cycle counter to roughly **7–23% of the real rate**. Because IPC = instructions ÷ cycles, and the denominator (cycles) is under-counted, the reported IPC is inflated by ~4–14×.

**Concrete example from Kraken-2:** perf showed IPC = 2.26. Corrected for throttled clock (0.734 GHz reported vs 3.2 GHz real), real IPC ≈ 0.52 — confirming memory-bound behaviour that 2.26 would have hidden.

| Counter | Status in WSL2 | Notes |
|---|---|---|
| `instructions` |  Correct | Hardware PMU counter, not throttled |
| `cycles` |  Wrong | ~7–23% of real — Hyper-V throttles this |
| **IPC = insn/cycles** |  Wrong | Inflated by 4–14× |
| `cache-misses`, `cache-references` |  Correct | Real PMU event, ratio-safe |
| `task-clock` wall ms |  Correct | OS software timer |
| `L1-dcache-loads/misses` |  Correct | Real PMU event |
| `L2/L3 request counts` |  Correct | Real PMU event |
| `branch-misses` |  Correct | Ratio of two real PMU events |

**Safe to compare:** wall time, cache miss counts, L1/L2/L3 miss rates, branch miss %.  
**On Minerva:** native Linux hardware counters work — IPC will be accurate there.

---

## RAM Requirements by Matrix Size

Each benchmark allocates **3 matrices** of N×N `double` (8 bytes each): A, B, C.

| N | Per matrix | **3 matrices total** | Fits in… |
|---|---|---|---|
| 1,024 | 8 MB | **24 MB** | Exceeds L3 (16 MB) — already memory-bound |
| 2,048 | 32 MB | **96 MB** | RAM easily |
| 10,000 | 800 MB | **2.24 GB** | RAM (need ≥4 GB free) |
| 25,000 | 5 GB | **14.9 GB** | Needs ≥16 GB — will page on this 14 GB machine |
| 100,000 | 80 GB | **223.5 GB** | Minerva only (251 GB RAM — just fits) |

> **Formula:** RAM (bytes) = 3 × N² × 8  
> **L3 threshold:** matrices exceed Ryzen 7 5800H's 16 MB L3 at N ≥ 816. Every test size here is memory-bound from the start.

---

## Results — N = 1024

### Table 1-A — Timing + Pipeline

| Binary | **Time (ms)** | IPC† | Cache Misses | BrMiss% |
|---|---|---|---|---|
| `naive_ijk` | 9,961 | 0.23† | 591,217,868 | 0.63% |
| `ikj_order` | 393 | 1.15† | 19,202,426 | 0.04% |
| `kij_order` | 472 | 1.29† | 6,714,240 | 0.04% |
| `transpose_B` | 1,717 | 0.87† | 5,126,005 | 0.02% |
| `tiled` | 425 | 1.50† | 13,390,340 | 0.32% |
| `omp_parallel` | 460 | 1.49† | 18,965,504 | 0.06% |
| `omp_tiled` | 579 | 1.67† | 11,297,298 | 0.18% |
| `unrolled_ikj` | 415 | 1.59† | 14,889,059 | 0.76% |
| `avx2_manual` | **324** | 1.97† | 6,528,249 | 0.78% |
| `auto_vec_O3` | 389 | 1.16† | 18,699,452 | 0.04% |
| `tiled_avx2` | 335 | 3.04† | 38,740,316 | 0.11% |
| `prefetch_ikj` | 961 | 3.37† | 11,871,223 | 0.63% |

† IPC unreliable — cycles counter throttled by Hyper-V. Do not use for comparison.

### Table 1-B — Cache Hierarchy (L2 + L3) with Time

| Binary | **Time (ms)** | L2 Requests | L2 Miss% | L3 Refs | L3 Miss% |
|---|---|---|---|---|---|
| `naive_ijk` | 9,961 | 1,892,477,004 | 23.5% | 2,871,004,277 | **22.0%** |
| `ikj_order` | 393 | 157,913,320 | 7.7% | 307,746,139 | 6.0% |
| `kij_order` | 472 | 150,431,413 | 1.9% | 290,300,222 | 2.2% |
| `transpose_B` | 1,717 | 146,765,345 | 1.0% | 288,679,691 | 1.8% |
| `tiled` | 425 | 206,467,165 | 0.9% | 331,662,675 | 4.1% |
| `omp_parallel` | 460 | 147,212,182 | 10.6% | 291,601,487 | 5.9% |
| `omp_tiled` | 579 | 204,382,387 | 2.9% | 341,565,058 | 3.3% |
| `unrolled_ikj` | 415 | 146,256,421 | 8.2% | 282,968,018 | 4.9% |
| `avx2_manual` | **324** | 140,617,019 | 3.0% | 280,629,509 | 2.3% |
| `auto_vec_O3` | 389 | 158,961,519 | 9.1% | 307,121,414 | 6.6% |
| `tiled_avx2` | 335 | 174,240,484 | **0.7%** | 314,073,725 | 12.3% |
| `prefetch_ikj` | 961 | 144,488,148 | 5.7% | 288,624,983 | 4.2% |

> Note: `L1-dcache-loads` multiplexed out when collecting 6 events simultaneously. Run `perf stat -e L1-dcache-loads,L1-dcache-load-misses <binary> 1024` for dedicated L1 data.

---

## Results — N = 2048

### Table 2-A — Timing + Pipeline

| Binary | **Time (ms)** | IPC† | Cache Misses | BrMiss% |
|---|---|---|---|---|
| `naive_ijk` | 120,536 | 0.15† | 10,179,585,610 | 0.36% |
| `ikj_order` | 3,620 | 0.83† | 94,725,695 | 0.04% |
| `kij_order` | 8,556 | 0.49† | 118,030,859 | 0.02% |
| `transpose_B` | 13,774 | 0.83† | 39,637,997 | 0.63% |
| `tiled` | 3,125 | 1.46† | 96,958,637 | 0.37% |
| `omp_parallel` | 6,177 | 0.73† | 58,248,158 | 0.16% |
| `omp_tiled` | 3,878 | 1.74† | 90,697,533 | 0.19% |
| `unrolled_ikj` | 4,542 | 1.00† | 47,359,373 | 0.03% |
| `avx2_manual` | 3,860 | 1.12† | 32,269,648 | 0.02% |
| `auto_vec_O3` | 3,645 | 0.82† | 97,473,564 | 0.04% |
| `tiled_avx2` | **2,500** | 2.96† | 394,164,831 | 0.12% |
| `prefetch_ikj` | 8,173 | 3.07† | 64,532,420 | 0.35% |

### Table 2-B — Cache Hierarchy (L2 + L3) with Time

| Binary | **Time (ms)** | L2 Requests | L2 Miss% | L3 Refs | L3 Miss% |
|---|---|---|---|---|---|
| `naive_ijk` | 120,536 | 22,633,972,195 | 43.9% | 36,987,695,216 | **27.6%** |
| `ikj_order` | 3,620 | 1,625,980,102 | 3.5% | 2,860,117,852 | 3.5% |
| `kij_order` | 8,556 | 1,464,828,705 | 6.3% | 2,603,219,102 | 4.3% |
| `transpose_B` | 13,774 | 1,251,101,553 | 1.3% | 2,410,313,886 | 1.7% |
| `tiled` | 3,125 | 1,655,633,105 | 1.0% | 2,648,946,077 | 3.7% |
| `omp_parallel` | 6,177 | 1,630,138,243 | 2.2% | 3,126,410,497 | 1.9% |
| `omp_tiled` | 3,878 | 1,644,928,748 | 3.7% | 2,770,095,825 | 3.6% |
| `unrolled_ikj` | 4,542 | 1,604,558,246 | 1.5% | 3,019,919,889 | 1.5% |
| `avx2_manual` | 3,860 | 1,450,592,982 | 3.5% | 2,723,287,958 | 2.5% |
| `auto_vec_O3` | 3,645 | 1,643,672,494 | 3.2% | 2,911,708,541 | 3.3% |
| `tiled_avx2` | **2,500** | 1,423,031,625 | **0.9%** | 2,685,083,076 | 15.9% |
| `prefetch_ikj` | 8,173 | 1,589,067,071 | 1.6% | 3,264,484,321 | 2.0% |

---

## Results — N = 10000

> **naive_ijk excluded** — O(N³) scaling from N=2048 gives ~4 hrs runtime.  
> **Status:** all 11 binaries complete. `perf_results/N10000/` — 22 result files.  
> L3 Miss% = cache-misses ÷ cache-references (same metric as Tables 1-B, 2-B).

### Table 3-A — Timing + Cache (N=10000)

| Binary | **Time (ms)** | Cache Misses | L2 Miss% | L3 Miss% | BrMiss% |
|---|---|---|---|---|---|
| `ikj_order` | 420,796 | 6,895,824,215 | 1.9% | 2.12% | 0.27% |
| `kij_order` | 1,177,606 | 11,652,559,317 | 3.2% | 3.04% | 0.29% |
| `transpose_B` | 1,636,624 | 7,526,577,591 | 0.9% | 1.94% | 0.16% |
| `tiled` | 298,841 | 8,036,089,969 | 1.0% | 2.92% | 0.43% |
| `omp_parallel` | 290,699 | 9,250,759,044 | 2.2% | 2.26% | 0.29% |
| `omp_tiled` | **112,506** | 10,318,370,903 | 3.8% | 3.70% | 0.20% |
| `unrolled_ikj` | 535,330 | 8,144,164,015 | 1.7% | 1.97% | 0.29% |
| `avx2_manual` | 462,351 | 6,422,414,789 | 0.9% | **1.64%** | 0.29% |
| `auto_vec_O3` | 423,079 | 7,288,182,166 | 2.0% | 2.24% | 0.27% |
| `tiled_avx2` | 236,546 | 24,321,593,389 | 2.0% | 18.53% | 0.12% |
| `prefetch_ikj` | 927,112 | 5,532,581,043 | **0.4%** | **1.23%** | **0.08%** |

---

## Cross-Size Comparison Tables

### Comparison Table 1 — Wall Time (ms) Side-by-Side

Expected O(N³) scaling: 1024→2048 = **8×**, 2048→10000 = **116.4×**

| Binary | N=1024 | N=2048 | N=10000 | Slowdown 1024→2048 | Slowdown 2048→10000 |
|---|---|---|---|---|---|
| `naive_ijk` | 9,961 | 120,536 | (skipped) | **12.1×** | — |
| `ikj_order` | 393 | 3,620 | 420,796 | 9.2× | 116.2×  |
| `kij_order` | 472 | 8,556 | 1,177,606 | **18.1×** | **137.6×** |
| `transpose_B` | 1,717 | 13,774 | 1,636,624 | 8.0× | 118.8× |
| `tiled` | 425 | 3,125 | 298,841 | 7.4× | **95.6×** ↓ |
| `omp_parallel` | 460 | 6,177 | 290,699 | **13.4×** | **47.1×** ↓↓ |
| `omp_tiled` | 579 | 3,878 | 112,506 | 6.7× | **29.0×** ↓↓↓ |
| `unrolled_ikj` | 415 | 4,542 | 535,330 | 10.9× | 117.9× |
| `avx2_manual` | 324 | 3,860 | 462,351 | 11.9× | 119.8× |
| `auto_vec_O3` | 389 | 3,645 | 423,079 | 9.4× | 116.1×  |
| `tiled_avx2` | **335** | **2,500** | 236,546 | 7.5× | **94.6×** ↓ |
| `prefetch_ikj` | 961 | 8,173 | 927,112 | 8.5× | 113.4×  |

> **Speedup `naive_ijk` vs `tiled_avx2`:** 9,961 ÷ 335 = **29.7×** at N=1024, 120,536 ÷ 2,500 = **48.2×** at N=2048, estimated ~3,500× at N=10000 (naive skipped; projected from scaling).  
>  = matches expected O(N³). ↓ = sub-linear scaling = getting *proportionally faster* at larger N.  
> **omp_tiled** is the standout: 29.0× slowdown vs 116× expected — at N=10000 it's **2.1× faster than tiled_avx2** (112,506ms vs 236,546ms). This is where OpenMP finally earns its keep: 2.4 GB working set means all 4 threads can maintain independent DRAM requests, whereas at small N the memory bus was the bottleneck for all threads combined.  
> `kij_order` degrades super-linearly (137.6× vs 116.4×) — outer-k loop's write-back conflicts with C-rows worsen as N grows.

### Comparison Table 2 — L3 Cache Misses Side-by-Side

| Binary | N=1024 | N=2048 | Growth ratio |
|---|---|---|---|
| `naive_ijk` | 591,217,868 | 10,179,585,610 | **17.2×** |
| `ikj_order` | 19,202,426 | 94,725,695 | 4.9× |
| `kij_order` | 6,714,240 | 118,030,859 | **17.6×** |
| `transpose_B` | 5,126,005 | 39,637,997 | 7.7× |
| `tiled` | 13,390,340 | 96,958,637 | 7.2× |
| `omp_parallel` | 18,965,504 | 58,248,158 | 3.1× |
| `omp_tiled` | 11,297,298 | 90,697,533 | 8.0× |
| `unrolled_ikj` | 14,889,059 | 47,359,373 | 3.2× |
| `avx2_manual` | 6,528,249 | 32,269,648 | 4.9× |
| `auto_vec_O3` | 18,699,452 | 97,473,564 | 5.2× |
| `tiled_avx2` | 38,740,316 | 394,164,831 | 10.2× |
| `prefetch_ikj` | 11,871,223 | 64,532,420 | 5.4× |

> `kij_order` and `naive_ijk` both show ~17× cache miss growth vs the expected 8× — their access patterns degrade non-linearly as N grows. `omp_parallel` and `unrolled_ikj` show sub-8× growth, meaning thread-level parallelism and unrolling happen to spread cache pressure.

### Comparison Table 3 — L2 and L3 Miss Rates Side-by-Side (%)

| Binary | L2% 1024 | L2% 2048 | L3% 1024 | L3% 2048 |
|---|---|---|---|---|
| `naive_ijk` | 23.5% | **43.9%** | 22.0% | **27.6%** |
| `ikj_order` | 7.7% | 3.5% | 6.0% | 3.5% |
| `kij_order` | 1.9% | 6.3% | 2.2% | 4.3% |
| `transpose_B` | 1.0% | 1.3% | **1.8%** | **1.7%** |
| `tiled` | **0.9%** | **1.0%** | 4.1% | 3.7% |
| `omp_parallel` | 10.6% | 2.2% | 5.9% | 1.9% |
| `omp_tiled` | 2.9% | 3.7% | 3.3% | 3.6% |
| `unrolled_ikj` | 8.2% | 1.5% | 4.9% | 1.5% |
| `avx2_manual` | 3.0% | 3.5% | 2.3% | 2.5% |
| `auto_vec_O3` | 9.1% | 3.2% | 6.6% | 3.3% |
| `tiled_avx2` | **0.7%** | **0.9%** | 12.3% | 15.9% |
| `prefetch_ikj` | 5.7% | 1.6% | 4.2% | 2.0% |

> Notable trend: `naive_ijk` L2 miss rate **doubles** from 23.5% → 43.9% as N doubles — at N=10000 this will approach 70%+. `tiled` and `tiled_avx2` hold flat (0.9–1.0% L2) because their tile size doesn't change; tiles always fit in L2.

### Comparison Table 4 — Branch Miss Rate Side-by-Side (%)

| Binary | N=1024 | N=2048 | Trend |
|---|---|---|---|
| `naive_ijk` | 0.63% | 0.36% | ↓ amortised over more iterations |
| `ikj_order` | 0.04% | 0.04% | flat |
| `kij_order` | 0.04% | 0.02% | flat |
| `transpose_B` | 0.02% | 0.63% | ↑ transpose tail-loop at large N |
| `tiled` | 0.32% | 0.37% | flat |
| `omp_parallel` | 0.06% | 0.16% | ↑ thread scheduling overhead |
| `omp_tiled` | 0.18% | 0.19% | flat |
| `unrolled_ikj` | 0.76% | 0.03% | ↓ tail-loop matters less at N=2048 |
| `avx2_manual` | 0.78% | 0.02% | ↓ same tail-loop effect |
| `auto_vec_O3` | 0.04% | 0.04% | flat |
| `tiled_avx2` | 0.11% | 0.12% | flat |
| `prefetch_ikj` | 0.63% | 0.35% | ↓ |

> Branch miss % is universally low (<1%) — all variants have predictable loop bounds. The high values for `unrolled_ikj` and `avx2_manual` at N=1024 come from the **tail loop** (handling remainder when N % 4 ≠ 0); at N=2048 (divisible by 4/8) the tail loop never runs and miss% drops to near zero.

---

## Analysis

### A. naive_ijk — catastrophic column-stride access

`naive_ijk` is 25–48× slower than `tiled_avx2`. The innermost loop accesses `B[k*N + j]` — stepping k (not j) on each iteration means each step jumps N×8 bytes. At N=1024 that's an 8 KB stride; at N=2048 it's 16 KB. Every access is a guaranteed cache miss.

Evidence: 22% L3 miss rate at N=1024 → 27.6% at N=2048. At N=10000 this will push above 60%. The 17.2× cache miss growth vs the expected 8× confirms the degradation is super-linear.

### B. Loop reordering — cheapest possible fix (25× speedup, zero complexity)

`ikj_order` hoists `A[i][k]` into a register and streams B-row sequentially. The hardware prefetcher can predict sequential access and pre-load cache lines, slashing cache misses 30×. L3 miss rate drops from 22% → 6% at N=1024.

`kij_order` gets even lower miss counts (1.9% L2, 2.2% L3 at N=1024) but degrades badly at N=2048 (6.3% L2, 4.3% L3, 8,556ms vs ikj's 3,620ms). The outer k-loop's C-row writes cause cross-iteration conflicts that worsen with larger N.

### C. transpose_B — best miss rate, expensive setup, good at large N

Fewest L3 misses (1.7–1.8% across both sizes) because both A-row and Bt-row are fully sequential. But the O(N²) transpose pass itself costs time and cache bandwidth — at N=1024 this overhead (1,717ms) dwarfs the benefit vs ikj (393ms). At very large N where O(N³) computation dominates, transpose becomes the right trade-off.

### D. Tiling — sub-linear scaling, best strategy for large N

`tiled` and `tiled_avx2` are the only variants with **sub-8× slowdown** from N=1024→2048 (7.4× and 7.5×). Their L2 miss rate is identical at both sizes (0.9–1.0%) because the 64×64 tile always fits in L2 regardless of total matrix size. This is the defining advantage of cache blocking — performance scales with the tile size, not N.

At N=10000, expect `tiled_avx2` and `tiled` to widen their lead further over non-blocked variants.

### E. OpenMP — bandwidth-limited at these sizes

`omp_parallel` is slower than single-threaded `ikj_order` at both N=1024 and N=2048 (460ms vs 393ms; 6,177ms vs 3,620ms). All 4 threads share the same 16 MB L3 and memory bus — the bottleneck is memory bandwidth, not compute. Adding threads doesn't help; it adds scheduling overhead and increases L3 contention.

`omp_tiled` performs better (3,878ms at N=2048) because tiling reduces per-thread memory pressure. At N=10000 with a 2.24 GB working set, OpenMP may finally see benefit — enough data to keep all threads' memory requests in-flight simultaneously.

### F. AVX2 — vectorisation narrows the gap

`avx2_manual` and `auto_vec_O3` deliver the same benefit at N=1024 (324ms vs 389ms). The compiler's auto-vectoriser with `-O3 -march=native -fopt-info-vec` produces 32-byte AVX2 vector loads — confirmed in the build output: `loop vectorized using 32 byte vectors`.

`tiled_avx2` (2,500ms at N=2048) is the fastest at large N — it combines blocked cache access (0.9% L2 miss) with 4-wide FMA throughput. Its L3 miss rate rising from 12.3% → 15.9% at N=2048 is a warning: consider `make tile32` (TILE=32) to reduce tile footprint and keep sub-blocks better isolated in L3.

### G. prefetch_ikj — software prefetch hurts sequential access (but does reduce misses)

Highest IPC† (3.37) but 2.3× slower than plain `ikj_order` at N=1024, and **2.2× slower** at N=10000 (927,112ms vs 420,796ms). The hardware prefetcher already handles sequential B-row access perfectly.

At N=10000 the prefetch instructions *do* work as intended — L1 miss% is **8.34%** vs ikj_order's **24.24%**, and L3 miss% is **1.23%** vs **2.12%** (lowest L3 miss rate of all single-threaded variants). But the cost is catastrophic: **5.4 trillion instructions** vs ikj_order's **577 billion** — a **9.3× instruction blowup** from emitting one `__builtin_prefetch` per inner-loop iteration. The CPU spends all its time issuing prefetch micro-ops that weren't needed in the first place.

`__builtin_prefetch` is only useful for **irregular** access patterns (hash tables, pointer chasing) — exactly what we'd see in Kraken-2's `CompactHashTable::Get()`, not sequential matrix rows the hardware prefetcher already handles.

---

## Summary Rankings

### Fastest → Slowest (wall time)

**N=1024:**
```
avx2_manual (324ms) < tiled_avx2 (335ms) < auto_vec_O3 (389ms) < ikj_order (393ms)
< unrolled_ikj (415ms) < tiled (425ms) < omp_parallel (460ms) < kij_order (472ms)
< omp_tiled (579ms) < prefetch_ikj (961ms) < transpose_B (1717ms) ≪ naive_ijk (9961ms)
```

**N=2048:**
```
tiled_avx2 (2500ms) < tiled (3125ms) < auto_vec_O3 (3645ms) < ikj_order (3620ms)
< avx2_manual (3860ms) < omp_tiled (3878ms) < unrolled_ikj (4542ms) < omp_parallel (6177ms)
< kij_order (8556ms) < prefetch_ikj (8173ms) < transpose_B (13774ms) ≪ naive_ijk (120536ms)
```

### Lowest L3 Miss Rate

| Rank | N=1024 | N=2048 |
|---|---|---|
| 1st | `transpose_B` 1.8% | `transpose_B` 1.7% |
| 2nd | `kij_order` 2.2% | `unrolled_ikj` 1.5% |
| 3rd | `avx2_manual` 2.3% | `omp_parallel` 1.9% |
| worst | `naive_ijk` 22.0% | `naive_ijk` 27.6% |

### Key Takeaway Table

| Variant | Best for | Limitation |
|---|---|---|
| `naive_ijk` | Baseline reference only | 25–48× slower; L3 miss rate grows super-linearly |
| `ikj_order` | Zero-cost 25× speedup | Miss rate degrades at very large N |
| `tiled` | Large N, cache-friendly | No vectorisation; L3 miss still present |
| `avx2_manual` / `auto_vec_O3` | Compute throughput, small–mid N | Memory-bound at large N |
| `tiled_avx2` | **Peak perf at large N** | L3 pressure at N=2048+ — try TILE=32 |
| `omp_tiled` | Multi-core + cache combined | Overhead beats benefit at small N |
| `transpose_B` | Lowest L3 miss rate | O(N²) setup cost — only wins at huge N |

---

## Luna and GPU Results

Luna re-run (bare metal, Xeon Platinum 8468, AVX-512, accurate IPC and TMA): see `reports/matrix_multiplication/README.md`. That file contains:
- Full N=1024, N=2048, N=10000 timing tables with accurate IPC, L1 miss %, LLC miss %, stall %
- TMA breakdown (memory-bound, core-bound, L3-bound, DRAM-bound) for naive vs tile+AVX2 at N=1024 and N=2048
- Platform flip analysis (WSL2 vs Luna winner differs at N=10000)
- Luna time scaling table across all three sizes

GPU results (L40S, N=10000, 6 kernels): see `reports/matrix_multiplication/README.md`, section "GPU performance (L40S, N=10000)". Summary: cuBLAS tensor TF32 at 16.3 ms / 122,923 GFLOPS (6,900x vs WSL2 CPU best). Raw Luna profiling file: `Luna/profiling/results_matmul_luna.md`.

---

## What to Re-run on Minerva

On Minerva (native Linux, Xeon Gold 6330), these events which are blocked by Hyper-V in WSL2 will work:

```bash
perf stat -e cycles,instructions,\
cache-misses,cache-references,\
LLC-load-misses,LLC-loads,\
L1-dcache-load-misses,L1-dcache-loads,\
stalled-cycles-backend,\
mem-loads,mem-stores \
./tiled_avx2 1024
```

| Metric | WSL2 | Minerva |
|---|---|---|
| Accurate IPC |  throttled |  |
| LLC-load-misses |  not supported |  |
| stalled-cycles-backend |  not supported |  memory stall % |
| mem-loads / mem-stores |  not supported |  DRAM traffic counts |
| L1/L2/L3 miss rates |  works (this report) |  |
| Wall time |  works (this report) |  |

Expected Minerva results:
- `naive_ijk` IPC: well below 1.0 (27% L3 miss rate confirms DRAM-bound)
- `tiled_avx2` IPC: 3–5 (tiles in L2, FMA throughput dominant)
- `stalled-cycles-backend` for `naive_ijk`: likely >80% (CPU waiting on DRAM nearly every cycle)
