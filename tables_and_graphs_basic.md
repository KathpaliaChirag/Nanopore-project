# Tables & Graphs (Basic) — Nanopore Pipeline Profiling
**Chirag Kathpalia | IIT Delhi | All data as of 2026-05-28**

Plain ASCII bar charts and tables — no Mermaid, works in any text viewer.
All bars scale the longest value to 40 chars. See `tables_and_graphs.md` for Mermaid/chart version.

---

## Contents
1. [Kraken-2 CPU Profile](#1-kraken-2-cpu-profile)
   - 1.1 perf stat numbers
   - 1.2 gprof function breakdown (bar chart)
   - 1.3 Three-tool convergence summary
   - 1.4 Cache miss cost model
2. [Dorado GPU Profile](#2-dorado-gpu-profile)
   - 2.1 CUDA kernel breakdown (bar chart)
   - 2.2 CUDA API time (bar chart)
   - 2.3 Memory transfers
   - 2.4 NVTX stage timeline
3. [Matrix Multiply Benchmarks](#3-matrix-multiply-benchmarks)
   - 3.1 Wall time N=1024 (bar chart)
   - 3.2 Wall time N=2048 (bar chart)
   - 3.3 Wall time N=10000 (bar chart) ← main chart
   - 3.4 L3 miss rate comparison (bar chart)
   - 3.5 L2 miss rate comparison (bar chart)
   - 3.6 Scaling: N=1024→2048 vs expected 8× (bar chart)
   - 3.7 Scaling: N=2048→10000 vs expected 116× (bar chart)
   - 3.8 naive_ijk speedup factor vs each variant
   - 3.9 Branch miss rates
   - 3.10 prefetch_ikj paradox — instructions vs time
   - 3.11 Cache miss counts (raw) across N
   - 3.12 RAM working set by N
4. [Lab Server Hardware Comparison](#4-lab-server-hardware-comparison)
   - 4.1 Full spec table
   - 4.2 Relative performance bars
5. [Dorado Mode Comparison](#5-dorado-mode-comparison)
6. [AIIMS Run — Barcode Classification](#6-aiims-run--barcode-classification)
7. [Pipeline Stage Time Summary](#7-pipeline-stage-time-summary)
8. [Cache ROI Projections](#8-cache-roi-projections)

---

## 1. Kraken-2 CPU Profile

### 1.1 perf stat — Key Numbers

**Input:** barcode02.fastq (104,829 reads, 357.62 Mbp) | **DB:** k2_standard_08gb (8 GB)

| Metric | Value | Verdict |
|---|---|---|
| Wall time | 159.4 s | 2.7 minutes |
| CPU time (task-clock) | 93,832 ms | |
| Kernel time (sys) | 52.5 s | 33% — heavy memory mapping |
| Cache misses | **301,288,020** | 301 million |
| Cache references | 879,854,514 | |
| **Cache miss rate** | **34.24%** | 1 in 3 → RAM |
| Instructions | 155,949,518,373 | 156 billion |
| Cycles | 68,853,332,412 | 69 billion |
| IPC (perf) | 2.26  | unreliable — Hyper-V |
| **IPC (AMD uProf)** | **0.55 ** | accurate — memory-bound |
| DB / L3 ratio | 8 GB / 16 MB | **500× overflows cache** |

```
Cache miss rate context
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Well-optimised program  1–5%  ██
Memory-bound threshold  >10%  ████
This run               34.2%  █████████████████████████████████████
Normal ratio                  └─────────────────────────────────────
```

### 1.2 gprof — Function Time Breakdown

**Total runtime: 105.87 s** | Kraken-2 compiled with `-pg` | Same input + DB

```
Function                        % time   calls         self(s)
────────────────────────────────────────────────────────────────────
CompactHashTable::Get()         67.35%  9,871,933  71.30
████████████████████████████████████████  ← 67.35%

MinimizerScanner::NextMinimizer  18.74%  354,164,193  19.84
███████████████                           ← 18.74%  (354M calls!)

ClassifySequence()               5.53%   —            5.85
████                                      ← 5.53%

MinimizerScanner::reverse_compl  2.23%  354,478,588   2.36
██                                        ← 2.23%

HyperLogLogPlusMinus::insert()   1.71%  3,220,914     1.81
█                                         ← 1.71%

ks_getuntil2() (FASTQ parsing)   1.06%  209,658       1.12
█                                         ← 1.06%

Other                            3.38%   —             3.59
███                                       ← 3.38%
────────────────────────────────────────────────────────────────────
Scale: ████████████████████████████████████████ = 40 chars = 67.35%
```

**Detailed gprof flat profile:**

| Rank | Function | % time | Self (s) | Calls | ms/call |
|---|---|---|---|---|---|
| 1 | `CompactHashTable::Get()` | **67.35%** | 71.30 | 9,871,933 | 0.0072 |
| 2 | `MinimizerScanner::NextMinimizer()` | 18.74% | 19.84 | 354,164,193 | 0.000056 |
| 3 | `ClassifySequence()` | 5.53% | 5.85 | — | — |
| 4 | `MinimizerScanner::reverse_complement()` | 2.23% | 2.36 | 354,478,588 | 0.0000067 |
| 5 | `HyperLogLogPlusMinus::insert()` | 1.71% | 1.81 | 3,220,914 | 0.00056 |
| 6 | `ks_getuntil2()` | 1.06% | 1.12 | 209,658 | 0.0053 |
| 7+ | Everything else | 3.38% | 3.59 | — | — |
| **Σ** | **Total** | **100%** | **105.87** | | |

### 1.3 Three-Tool Convergence

```
Tool            Measures                   Result           Verdict
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
perf stat       system-wide miss rate      34.24%           memory-bound
gprof           per-function time          67% in Get()     exact hotspot
AMD uProf       true IPC (native Ryzen)    IPC = 0.55       CPU stalling
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IPC range guide:  <1.0 = memory-bound  |  1–2 = mixed  |  >2 = compute-bound
```

### 1.4 Cache Miss Cost Model

```
Latency pyramid
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L1 hit    ~1   ns  █
L2 hit    ~4   ns  ████
L3 hit    ~10  ns  ██████████
RAM       ~100 ns  ████████████████████████████████████████

k-mer lookup path for 8 GB DB:
  hash(k-mer) → random address in 8 GB table
  8 GB table >> 16 MB L3 → ALMOST EVERY ACCESS = RAM (100 ns)

301,288,020 L3 misses × ~100 ns = ~30.1 seconds in pure RAM wait
(accounts for ~32% of 93.8 s CPU time)
```

```
Hit rate → time saved (10% increments)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 10% hit rate  →  ~30M fewer RAM accesses  →  ~3.0 s saved   ████
 20% hit rate  →  ~60M fewer RAM accesses  →  ~6.0 s saved   ████████
 30% hit rate  →  ~90M fewer RAM accesses  →  ~9.0 s saved   ████████████
 40% hit rate  →  120M fewer RAM accesses  → ~12.0 s saved   ████████████████
 50% hit rate  →  150M fewer RAM accesses  → ~15.0 s saved   ████████████████████

Assumption: each LRU hit eliminates ~30 L3 misses per CompactHashTable::Get() call
(301M total misses ÷ 9.87M calls = ~30.5 misses/call)
```

---

## 2. Dorado GPU Profile

### 2.1 CUDA Kernel Breakdown — Where GPU Time Goes

**Mode:** fast | **Input:** 104,478 reads, 4 GB POD5 | **GPU:** GTX 1650

```
GPU kernel                              % GPU time   Total time
────────────────────────────────────────────────────────────────────
cutlass GEMM 128×64  (Tensor Core FP16)   68.5%    1,069 s
████████████████████████████████████████           ← 68.5%  

cutlass GEMM 128×128 (Tensor Core FP16)   13.5%      211 s
████████                                   ← 13.5%

                        GEMM TOTAL = 82.0% ━━━━━━━━━━━━━━━━━━━

beam_search_step                           4.7%     73.8 s
███

LSTM forward (96 channels)                 4.5%     71.0 s
███

LSTM backward (96 channels)                3.0%     47.3 s
██

convolution_ntc                            1.6%     24.3 s
█

decode_step                                1.3%     20.7 s
█

compute_posts_step                         1.3%     20.2 s
█

────────────────────────────────────────────────────────────────────
Scale: ████████████████████████████████████████ = 40 chars = 68.5%
```

| Kernel | % GPU time | Total time | Instances | Avg/call |
|---|---|---|---|---|
| cutlass GEMM 128×64 | **68.5%** | 1,069 s | 54,522 | **19.6 ms** |
| cutlass GEMM 128×128 | **13.5%** | 211 s | 9,087 | 23.3 ms |
| beam_search_step | 4.7% | 73.8 s | 9,087 | 8.1 ms |
| LSTM forward | 4.5% | 71.0 s | 27,261 | 2.6 ms |
| LSTM backward | 3.0% | 47.3 s | 18,174 | 2.6 ms |
| convolution_ntc | 1.6% | 24.3 s | 9,087 | 2.7 ms |
| decode_step | 1.3% | 20.7 s | 9,087 | 2.3 ms |
| compute_posts_step | 1.3% | 20.2 s | 9,087 | 2.2 ms |
| **GEMM subtotal** | **82.0%** | **1,280 s** | 63,609 | |

### 2.2 CUDA API Time — What the CPU Does

```
CUDA API call               % API time   calls     avg/call
────────────────────────────────────────────────────────────
cudaStreamSynchronize          98.9%    27,283     56.6 ms
████████████████████████████████████████  ← 98.9%

cudaLaunchKernel                0.5%   190,891     43.5 µs
                                ← 0.5%

cudaMemcpyAsync                 0.3%    27,304    186.0 µs
                                ← 0.3%
────────────────────────────────────────────────────────────
27,283 × 56.6 ms = ~1,544 s total CPU blocking time
CPU is idle for 98.9% of the time the GPU is working
```

### 2.3 Memory Transfers

```
Transfer direction           % of transfer time   total data   count
────────────────────────────────────────────────────────────────────
CPU RAM → GPU VRAM (data in)       59.9%          11,427 MB    9,112
████████████████████████████████████████

GPU internal (DtoD)                25.1%          11,427 MB    9,107
████████████████████

GPU VRAM → CPU RAM (reads out)     15.0%           2,856 MB    9,085
█████████████
────────────────────────────────────────────────────────────────────
Total transferred: ~25.7 GB over full run
Per batch: ~1.25 MB in, ~0.31 MB out (9,085 batches)
Memory transfers = minor fraction of total time → GPU is NOT memory-starved
```

### 2.4 NVTX Stage Breakdown

```
Dorado stage                    % annotated time   instances   avg/call
────────────────────────────────────────────────────────────────────────
basecall_current_batch             39.8%            9,085      350 ms
████████████████████████████████████████

call_chunks (nested)               39.8%            9,085      350 ms
████████████████████████████████████████  (same wall time as above)

cuda_thread_fn_device_0            19.6%            9,086      173 ms
████████████████████

nn_forward                          0.2%            9,087      2.1 ms
│

cpu_decode                          0.1%            9,085      0.98 ms
│

lstm_stack                          0.1%            9,087      0.89 ms
│

gpu_decode                          0.1%            9,087      0.83 ms
│

conv                                0.1%           27,261      0.22 ms
│
────────────────────────────────────────────────────────────────────────
9,085 batches total = 104,478 reads at batch size 64
```

### 2.5 Dorado Compute vs Memory — Verdict Chart

```
                  Compute-bound ◄──────────────────► Memory-bound
                  (SM working)                        (waiting for data)

GEMM % of time      82% ██████████████████████████████████████████
Transfer % of time   5% ██
CPU sync %          99% (CPU waiting on GPU — GPU is the bottleneck)

Verdict: COMPUTE-BOUND ███████████████████████████████████████████
```

---

## 3. Matrix Multiply Benchmarks

**Machine:** WSL2 | AMD Ryzen 7 5800H | 14 GB RAM | GCC 15.1.0 -O3 -march=native  
**dtype:** double (8B) | **OMP_NUM_THREADS:** 4

### 3.1 Wall Time — N = 1024

```
Binary          Time (ms)   Bar (avx2_manual=fastest, naive_ijk=worst)
──────────────────────────────────────────────────────────────────────
avx2_manual          324   ████████ (fastest)
tiled_avx2           335   ████████
auto_vec_O3          389   ██████████
ikj_order            393   ██████████
unrolled_ikj         415   ██████████
tiled                425   ██████████
omp_parallel         460   ███████████
kij_order            472   ████████████
omp_tiled            579   ██████████████
prefetch_ikj         961   ████████████████████████
transpose_B        1,717   ████████████████████████████████████████████
naive_ijk          9,961   (30.7× off-chart → 305 chars)
──────────────────────────────────────────────────────────────────────
Scale: 44 chars = 1,717 ms (transpose_B, longest shown)
naive_ijk would be 305 chars — excluded for scale
```

| Binary | ms | vs fastest (avx2) |
|---|---|---|
| avx2_manual | **324** | 1.0× |
| tiled_avx2 | 335 | 1.03× |
| auto_vec_O3 | 389 | 1.20× |
| ikj_order | 393 | 1.21× |
| unrolled_ikj | 415 | 1.28× |
| tiled | 425 | 1.31× |
| omp_parallel | 460 | 1.42× |
| kij_order | 472 | 1.46× |
| omp_tiled | 579 | 1.79× |
| prefetch_ikj | 961 | 2.97× |
| transpose_B | 1,717 | 5.30× |
| naive_ijk | 9,961 | **30.7×** |

### 3.2 Wall Time — N = 2048

```
Binary          Time (ms)   Bar (tiled_avx2=fastest)
──────────────────────────────────────────────────────────────────────
tiled_avx2       2,500   ███████ (fastest)
tiled            3,125   █████████
ikj_order        3,620   ██████████
auto_vec_O3      3,645   ██████████
avx2_manual      3,860   ███████████
omp_tiled        3,878   ███████████
unrolled_ikj     4,542   █████████████
omp_parallel     6,177   █████████████████
prefetch_ikj     8,173   ███████████████████████
kij_order        8,556   ████████████████████████
transpose_B     13,774   ████████████████████████████████████████
naive_ijk      120,536   (8.75× off-chart → 349 chars)
──────────────────────────────────────────────────────────────────────
Scale: 40 chars = 13,774 ms (transpose_B)
```

### 3.3 Wall Time — N = 10000  Main Benchmark

```
Binary          Time (ms)   Bar (omp_tiled=fastest)
──────────────────────────────────────────────────────────────────────
omp_tiled       112,506   ███  (fastest — parallelism finally pays off)
tiled_avx2      236,546   ██████
omp_parallel    290,699   ████████
tiled           298,841   ████████
ikj_order       420,796   ████████████
auto_vec_O3     423,079   ████████████
avx2_manual     462,351   █████████████
unrolled_ikj    535,330   ███████████████
prefetch_ikj    927,112   ██████████████████████████
kij_order     1,177,606   █████████████████████████████████
transpose_B   1,636,624   ████████████████████████████████████████████████
──────────────────────────────────────────────────────────────────────
Scale: 46 chars = 1,636,624 ms (transpose_B = slowest)
```

| Binary | Time (ms) | vs omp_tiled | L3 miss% |
|---|---|---|---|
| **omp_tiled** | **112,506** | **1.0×** (fastest) | 3.70% |
| tiled_avx2 | 236,546 | 2.1× | **18.53%** ← L3 overflow |
| omp_parallel | 290,699 | 2.6× | 2.26% |
| tiled | 298,841 | 2.7× | 2.92% |
| ikj_order | 420,796 | 3.7× | 2.12% |
| auto_vec_O3 | 423,079 | 3.8× | 2.24% |
| avx2_manual | 462,351 | 4.1× | **1.64%** ← lowest non-prefetch |
| unrolled_ikj | 535,330 | 4.8× | 1.97% |
| prefetch_ikj | 927,112 | 8.2× | **1.23%** ← lowest but slowest |
| kij_order | 1,177,606 | 10.5× | 3.04% |
| transpose_B | 1,636,624 | 14.5× | 1.94% |

### 3.4 L3 Cache Miss Rate — All N (%)

```
Binary          N=1024   N=2048   N=10000
────────────────────────────────────────────────────────────────────────
naive_ijk       22.0%    27.6%    (est >50%)
ikj_order        6.0%     3.5%     2.12%
kij_order        2.2%     4.3%     3.04%
transpose_B      1.8%     1.7%     1.94%
tiled            4.1%     3.7%     2.92%
omp_parallel     5.9%     1.9%     2.26%
omp_tiled        3.3%     3.6%     3.70%
unrolled_ikj     4.9%     1.5%     1.97%
avx2_manual      2.3%     2.5%     1.64%
auto_vec_O3      6.6%     3.3%     2.24%
tiled_avx2      12.3%    15.9%    18.53%  ← worsens with N (tile overflow!)
prefetch_ikj     4.2%     2.0%     1.23%  ← best rate, worst time
────────────────────────────────────────────────────────────────────────
```

```
L3 Miss Rate at N=10000 (sorted)
──────────────────────────────────────────────────
prefetch_ikj    1.23%  ██
avx2_manual     1.64%  ███
unrolled_ikj    1.97%  ████
ikj_order       2.12%  ████
auto_vec_O3     2.24%  ████
omp_parallel    2.26%  █████
transpose_B     1.94%  ████
tiled           2.92%  ██████
kij_order       3.04%  ██████
omp_tiled       3.70%  ████████
tiled_avx2     18.53%  █████████████████████████████████████████  ← outlier!
──────────────────────────────────────────────────
Scale: 40 chars = 18.53% (tiled_avx2)
```

### 3.5 L2 Cache Miss Rate at N=10000 (%)

```
prefetch_ikj    0.4%   █
avx2_manual     0.9%   ██
transpose_B     0.9%   ██
tiled           1.0%   ██
unrolled_ikj    1.7%   ████
ikj_order       1.9%   ████
tiled_avx2      2.0%   ████
auto_vec_O3     2.0%   ████
omp_parallel    2.2%   █████
kij_order       3.2%   ███████
omp_tiled       3.8%   ████████
────────────────────────────────
Scale: 40 chars = 3.8% (omp_tiled)
```

### 3.6 Scaling Ratio N=1024→2048 (vs expected 8×)

```
Expected O(N³): 8× slowdown from 1024 to 2048
  Below 8× = getting proportionally faster at larger N  (good for cache designs)
  Above 8× = getting proportionally slower              (bad — access pattern worsens)

Binary           Actual ratio    Bar
────────────────────────────────────────────────────────────────────
tiled                  7.4×   ███████████████████████████████
omp_tiled              6.7×   ████████████████████████████
tiled_avx2             7.5×   ███████████████████████████████
ikj_order              9.2×   ██████████████████████████████████████
auto_vec_O3            9.4×   ███████████████████████████████████████
prefetch_ikj           8.5×   ███████████████████████████████████
avx2_manual           11.9×   ██████████████████████████████████████████████████
unrolled_ikj          10.9×   █████████████████████████████████████████████
transpose_B            8.0×   █████████████████████████████████
omp_parallel          13.4×   ████████████████████████████████████████████████████████
kij_order             18.1×   (off chart — 76 chars)
naive_ijk             12.1×   ██████████████████████████████████████████████████
Expected 8×           ─────   ─────────────────────────────────── ← reference line

Scale: 55 chars = 13.4× (omp_parallel)
```

| Binary | 1024→2048 | vs expected 8× |
|---|---|---|
| omp_tiled | **6.7×** | **sub-linear ↓ (tiles help)** |
| tiled | 7.4× | sub-linear ↓ |
| tiled_avx2 | 7.5× | sub-linear ↓ |
| transpose_B | 8.0× | matches O(N³)  |
| prefetch_ikj | 8.5× | near O(N³) |
| ikj_order | 9.2× | slightly super-linear |
| auto_vec_O3 | 9.4× | slightly super-linear |
| unrolled_ikj | 10.9× | super-linear ↑ |
| avx2_manual | 11.9× | super-linear ↑ |
| naive_ijk | 12.1× | **super-linear ↑** |
| omp_parallel | 13.4× | **super-linear ↑** |
| kij_order | **18.1×** | **severely super-linear ↑** |

### 3.7 Scaling Ratio N=2048→10000 (vs expected 116.4×)

```
Expected O(N³): 116.4× slowdown from 2048 to 10000
  Far below 116× = massive sub-linear = parallelism or caching hides cost

Binary           Actual ratio    Bar (40 chars = 116×)
────────────────────────────────────────────────────────────────────
omp_tiled             29.0×   ██████████  ← 4.0× better than expected!
tiled_avx2            94.6×   ████████████████████████████████
tiled                 95.6×   █████████████████████████████████
prefetch_ikj         113.4×   ███████████████████████████████████████
auto_vec_O3          116.1×   ████████████████████████████████████████ 
ikj_order            116.2×   ████████████████████████████████████████ 
unrolled_ikj         117.9×   ████████████████████████████████████████
transpose_B          118.8×   █████████████████████████████████████████
omp_parallel          47.1×   ████████████████
kij_order            137.6×   ████████████████████████████████████████████████

Expected 116.4×   ──────────   ████████████████████████████████████████ ← reference

Scale: 40 chars = 116.4×
```

### 3.8 naive_ijk Speedup Factor vs Each Variant

```
naive_ijk time ÷ each variant time (higher = better variant)

                N=1024           N=2048          (N=10000 naive skipped)
─────────────────────────────────────────────────────────────────────────
tiled_avx2    29.7×             48.2×
avx2_manual   30.7×             31.2×
auto_vec_O3   25.6×             33.1×
ikj_order     25.3×             33.3×
tiled         23.4×             38.6×
unrolled_ikj  24.0×             26.5×
omp_tiled     17.2×             31.1×
omp_parallel  21.6×             19.5×
kij_order     21.1×             14.1×
transpose_B    5.8×              8.8×
prefetch_ikj  10.4×             14.8×
─────────────────────────────────────────────────────────────────────────
Key: tiled_avx2 widens lead as N grows (29.7× → 48.2×)
     kij_order SHRINKS lead (21.1× → 14.1×) — degrades super-linearly
```

```
Speedup vs naive_ijk at N=2048 (largest measured)
────────────────────────────────────────────────────────
tiled_avx2    48.2×   ████████████████████████████████████████
ikj_order     33.3×   ████████████████████████████
auto_vec_O3   33.1×   ███████████████████████████
tiled         38.6×   ████████████████████████████████
omp_tiled     31.1×   █████████████████████████
avx2_manual   31.2×   █████████████████████████
unrolled_ikj  26.5×   ██████████████████████
omp_parallel  19.5×   ████████████████
kij_order     14.1×   ████████████
prefetch_ikj  14.8×   ████████████
transpose_B    8.8×   ███████
────────────────────────────────────────────────────────
Scale: 40 chars = 48.2× (tiled_avx2)
```

### 3.9 Branch Miss Rates (%)

Low across the board — branches not the bottleneck.

| Binary | N=1024 | N=2048 | N=10000 | Notes |
|---|---|---|---|---|
| ikj_order | 0.04% | 0.04% | 0.27% | stable |
| kij_order | 0.04% | 0.02% | 0.29% | stable |
| tiled | 0.32% | 0.37% | 0.43% | slight climb |
| omp_tiled | 0.18% | 0.19% | 0.20% | stable |
| tiled_avx2 | 0.11% | 0.12% | 0.12% | stable |
| auto_vec_O3 | 0.04% | 0.04% | 0.27% | stable |
| avx2_manual | **0.78%** | 0.02% | 0.29% | tail-loop at N=1024 |
| unrolled_ikj | **0.76%** | 0.03% | 0.29% | tail-loop at N=1024 |
| prefetch_ikj | 0.63% | 0.35% | **0.08%** | lowest at N=10000 |
| transpose_B | 0.02% | 0.63% | 0.16% | increases at N=2048 |
| naive_ijk | 0.63% | 0.36% | — | |

### 3.10 The Prefetch Paradox — Instructions vs Time

```
prefetch_ikj vs ikj_order at N=10000

Metric              ikj_order          prefetch_ikj        ratio
────────────────────────────────────────────────────────────────────
Wall time           420,796 ms         927,112 ms          2.2× slower
Instructions        577 billion        5,390 billion       9.3× more ← !
L3 miss rate        2.12%              1.23%               1.7× better
L2 miss rate        1.9%               0.4%                4.8× better
Branch miss         0.27%              0.08%               3.4× better
────────────────────────────────────────────────────────────────────
Conclusion: software prefetch REDUCES miss rates but BLOWS UP instruction count
            Hardware prefetcher already handles sequential B-row access
```

```
Instruction count visualised (billions)
────────────────────────────────────────────────────────────
ikj_order          577B   ████
auto_vec_O3        589B   ████
tiled              ≈600B  ████
avx2_manual        ≈550B  ████
tiled_avx2         ≈620B  ████
prefetch_ikj      5390B   ████████████████████████████████████████ ← 9.3× MORE
────────────────────────────────────────────────────────────
Scale: 40 chars = 5,390 billion (prefetch_ikj)
```

### 3.11 Cache Miss Counts — Raw Numbers Across N

| Binary | N=1024 | N=2048 | N=10000 | Growth 1024→2048 |
|---|---|---|---|---|
| naive_ijk | 591,217,868 | 10,179,585,610 | (est ~1.3T) | **17.2×** |
| ikj_order | 19,202,426 | 94,725,695 | 6,895,824,215 | 4.9× |
| kij_order | 6,714,240 | 118,030,859 | 11,652,559,317 | **17.6×** |
| transpose_B | 5,126,005 | 39,637,997 | 7,526,577,591 | 7.7× |
| tiled | 13,390,340 | 96,958,637 | 8,036,089,969 | 7.2× |
| omp_parallel | 18,965,504 | 58,248,158 | 9,250,759,044 | 3.1× |
| omp_tiled | 11,297,298 | 90,697,533 | 10,318,370,903 | 8.0× |
| unrolled_ikj | 14,889,059 | 47,359,373 | 8,144,164,015 | 3.2× |
| avx2_manual | 6,528,249 | 32,269,648 | 6,422,414,789 | 4.9× |
| auto_vec_O3 | 18,699,452 | 97,473,564 | 7,288,182,166 | 5.2× |
| tiled_avx2 | 38,740,316 | 394,164,831 | 24,321,593,389 | **10.2×** |
| prefetch_ikj | 11,871,223 | 64,532,420 | 5,532,581,043 | 5.4× |

### 3.12 RAM Working Set by N

```
N         Per matrix   3-matrix total    Fits in
────────────────────────────────────────────────────────────────────────
   512    2 MB          6 MB             L3 (16 MB on Ryzen 5800H)
 1,024    8 MB         24 MB            > L3 → RAM-bound
 2,048   32 MB         96 MB            RAM
10,000  800 MB       2,400 MB (2.4 GB)  RAM
25,000    5 GB        15 GB             Needs 16 GB (near machine limit)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Registers │ L1 (48 KB) │ L2 (512 KB) │ L3 (16 MB) │ RAM (14 GB)
  ──────────┼────────────┼─────────────┼────────────┼──────────────────
  < 512     │ N=256      │ N=256       │ N < 730    │ N ≥ 730
  Everything in this report is RAM-bound (N ≥ 1024 > 730 threshold)
  Tiles (TILE=64): 3×64²×8 = 98 KB → fits L2 (512 KB) ← why tiling helps
  Tiles (TILE=32): 3×32²×8 = 24 KB → fits L1 (48 KB)  ← tiled_avx2 fix
```

---

## 4. Lab Server Hardware Comparison

### 4.1 Full Spec Table

| Spec | Local (Chirag) | Minerva | Luna |
|---|---|---|---|
| CPU | Ryzen 7 5800H | Xeon Gold 6330 | Xeon Platinum 8468 |
| Microarch | Zen 3 | Ice Lake | **Sapphire Rapids** |
| Sockets | 1 | 2 | 2 |
| Cores (physical) | 8 | 28+28 = 56 | 48+48 = 96 |
| Logical CPUs | 16 | 112 | **192** |
| Base clock | 3.2 GHz | 2.0 GHz | **3.8 GHz** |
| Boost clock | 4.4 GHz | 3.1 GHz | 3.8 GHz |
| L1 cache | 48 KB/core | 48 KB/core | 48 KB/core |
| L2 cache | 512 KB/core | 1 MB/core | **2 MB/core** |
| **L3 cache** | **16 MB** | **66 MB** | **210 MB** |
| **RAM** | **14 GB** | **251 GB** | **503 GB** |
| GPU | GTX 1650 | 2× A40 | **2× L40S** |
| GPU VRAM | 4 GB | 45 GB each | **46 GB each** |
| GPU FP32 | ~2.9 TFLOPS | ~37.4 TFLOPS | **~91.6 TFLOPS** |
| Disk free | ~50 GB | **0 GB (FULL!)** | 236 GB |
| ISA | AVX2 | AVX-512 | AVX-512 + **AMX** |
| perf counters | WSL2 limited |  native |  native |
| TMA support |  | partial |  full |
| NUMA | 1 node | 2 nodes | 2 nodes |

### 4.2 Relative Performance Bars

```
CPU Clock Speed
────────────────────────────────────────────
Local (Ryzen)    3.2 GHz  ████████████████████████████████████████
Minerva          2.0 GHz  █████████████████████████
Luna             3.8 GHz  ████████████████████████████████████████████████

L3 Cache Size
────────────────────────────────────────────
Local             16 MB   ███
Minerva           66 MB   █████████████
Luna             210 MB   ████████████████████████████████████████

RAM
────────────────────────────────────────────
Local             14 GB   █
Minerva          251 GB   ████████████████████
Luna             503 GB   ████████████████████████████████████████

GPU FP32 Throughput
────────────────────────────────────────────
Local GTX 1650    2.9 T   █
Minerva A40      37.4 T   ████████████████
Luna L40S        91.6 T   ████████████████████████████████████████

Logical CPU Count
────────────────────────────────────────────
Local               16    ███
Minerva            112    ████████████████████████
Luna               192    ████████████████████████████████████████

Scale: 40 chars = max in each category
```

```
Luna vs Minerva ratio (Luna ÷ Minerva)
────────────────────────────────────────────────────────────────
L3 cache         3.2×   █████████████████████████████████
RAM              2.0×   ████████████████████
GPU TFLOPS       2.5×   █████████████████████████
Logical CPUs     1.7×   █████████████████
CPU clock        1.9×   ███████████████████
Disk free        ∞      (Minerva = 0 free vs Luna = 236 GB)
────────────────────────────────────────────────────────────────
Luna wins every dimension. Luna is the primary server.
```

---

## 5. Dorado Mode Comparison

**Platform:** Google Colab T4 vs local GTX 1650 | **Input:** 104,478 reads

| Mode | Time (T4) | Time (GTX 1650) | Classified reads | vs fast |
|---|---|---|---|---|
| fast | 3 min 58 s | ~5 min | baseline | baseline |
| hac | 19 min 8 s | ~71 min | +3–8% more | +14.9× slower on GTX 1650 |
| sup | 2 h 5 min | **OOM** | +0.1–1% more | not runnable on 4 GB VRAM |

```
Runtime (GTX 1650, minutes)
──────────────────────────────────────────────────────
fast      5 min  ███
hac      71 min  █████████████████████████████████████████████████████
sup      OOM     — (out of memory, 4 GB VRAM insufficient)

Accuracy gain per mode change
──────────────────────────────────────────────────────
fast→hac   +3–8% classified reads    ████████████████████████████████
hac→sup    +0.1–1%                   ██

Verdict: hac is the sweet spot — big accuracy gain, tolerable on Colab T4
```

---

## 6. AIIMS Run — Barcode Classification Results

**Input:** FBE01990_24778b97_03e50f91_10.pod5 | **DB:** custom ESKAPE 650 MB | **Mode:** hac

| Barcode | Dominant species | Taxon ID | % classified |
|---|---|---|---|
| barcode01 | Pseudomonas aeruginosa | 287 | >90% |
| barcode02 | Pseudomonas aeruginosa | 287 | **100%** (44 reads) |
| barcode03 | Pseudomonas aeruginosa | 287 | >90% |
| barcode04 | Pseudomonas aeruginosa | 287 | >90% |
| barcode05 | Pseudomonas aeruginosa | 287 | >90% |
| barcode06 | Pseudomonas aeruginosa | 287 | >90% |
| barcode07 | Pseudomonas aeruginosa | 287 | >90% |
| barcode09 | Klebsiella pneumoniae + E. faecium | 573 + 1352 | mixed |
| barcode10 | Klebsiella pneumoniae + E. faecium | 573 + 1352 | mixed |
| barcode11 | Klebsiella pneumoniae + E. faecium | 573 + 1352 | mixed |
| barcode12 | Klebsiella pneumoniae + E. faecium | 573 + 1352 | mixed |
| barcode13 | Enterococcus faecium | 1352 | >90% |
| barcode14 | mixed | multiple | mixed |

```
Pathogen distribution across barcodes
────────────────────────────────────────────────────────────────
Pseudomonas aeruginosa    7 barcodes  ████████████████████████████
Klebsiella + E. faecium   4 barcodes  ████████████████
Enterococcus faecium      1 barcode   ████
Mixed/other               2 barcodes  ████████
────────────────────────────────────────────────────────────────

Custom ESKAPE DB vs Standard DB
────────────────────────────────────────────────────────────────
Size        Standard: 180 GB  ████████████████████████████████████████
            Custom:     650 MB █
Build time  Standard: ~hours
            Custom:    30 sec
RAM needed  Standard: 180 GB
            Custom:     <1 GB
Colab-able  Standard: No
            Custom:    Yes
```

---

## 7. Pipeline Stage Time Summary

```
End-to-end pipeline timing (GTX 1650, hac, 104,478 reads)
──────────────────────────────────────────────────────────────────────
Stage                     Tool       Time         % of total (~80 min)
──────────────────────────────────────────────────────────────────────
Basecalling (GPU)         Dorado     ~71 min      88.7%
█████████████████████████████████████████████████████████████████████

Species classification    Kraken-2   ~2.7 min      3.4%
████

BAM→FASTQ conversion      samtools   ~0.1 min      0.1%
│

Database loading (OS)     mmap       ~10 min       (Kraken-2 startup only,
                                                    included in 2.7 min)
──────────────────────────────────────────────────────────────────────
Dorado is the dominant stage (88.7%) — but Kraken-2 is the more
cacheable stage (random access pattern, known hot k-mers)
```

---

## 8. Cache ROI Projections

### Kraken-2 — Hot-K-mer LRU Cache

```
Assumptions:
  - 9.87M CompactHashTable::Get() calls per run
  - ~30 L3 misses per call (301M total ÷ 9.87M)
  - ~100 ns per L3 miss (DRAM latency)
  - Clinical sample = dominant species → k-mer locality exists

Hit rate → calls saved → misses avoided → time saved
────────────────────────────────────────────────────────────────────
5%    493K calls  × 30 × 100ns =  1.48 s  ██
10%   987K calls  × 30 × 100ns =  2.96 s  ████
15%  1.48M calls  × 30 × 100ns =  4.44 s  ██████
20%  1.97M calls  × 30 × 100ns =  5.92 s  ████████  ← target estimate
25%  2.47M calls  × 30 × 100ns =  7.41 s  ██████████
30%  2.96M calls  × 30 × 100ns =  8.88 s  ████████████
40%  3.95M calls  × 30 × 100ns = 11.84 s  ████████████████
50%  4.94M calls  × 30 × 100ns = 14.80 s  ████████████████████

Total runtime: ~159 s. Even 10% hit rate is ~1.9% speedup.
20% hit rate → 5.92s saved → ~3.7% speedup on total wall time.
```

### Dorado — Signal-to-Base (S2B) Cache

```
Assumptions:
  - GEMM = 82% of GPU time
  - Cache hit → skip entire GEMM forward pass for that batch
  - Avg GEMM call = 19.6 ms

Hit rate → GPU time saved → % of total run saved
────────────────────────────────────────────────────────────────────
5%   0.82 × 5%  =  4.1%  GPU time   ████
10%  0.82 × 10% =  8.2%  GPU time   ████████
20%  0.82 × 20% = 16.4%  GPU time   ████████████████
30%  0.82 × 30% = 24.6%  GPU time   █████████████████████████  ← target
40%  0.82 × 40% = 32.8%  GPU time   █████████████████████████████████
50%  0.82 × 50% = 41.0%  GPU time   █████████████████████████████████████████

Constraint: cache lookup must be < 19.6 ms (avg GEMM time)
            otherwise hit has no benefit (lookup costs more than it saves)
```

---

## Summary Reference — All Key Numbers

| Metric | Value | Source |
|---|---|---|
| Kraken-2 wall time (8 GB DB) | 159.4 s | perf stat |
| Cache miss rate | **34.24%** | perf stat |
| Total L3 misses | **301,288,020** | perf stat |
| True IPC (kraken-2) | **0.55** | AMD uProf |
| Hotspot function | **CompactHashTable::Get()** | gprof |
| Hotspot % time | **67.35%** | gprof |
| Hotspot call count | **9,871,933** | gprof |
| Misses per call (derived) | **~30** | 301M ÷ 9.87M |
| Next function | MinimizerScanner::NextMinimizer() | gprof |
| Next function % | 18.74% | gprof |
| GEMM % of GPU time | **82%** | Nsight Systems |
| Avg GEMM call time | **19.6 ms** | Nsight Systems |
| cudaStreamSynchronize % | **98.9%** | Nsight Systems |
| Total GPU batches | 9,085 | Nsight Systems |
| Memory transfers | 25.7 GB total | Nsight Systems |
| omp_tiled vs naive at N=2048 | 31.1× faster | perf stat matmul |
| tiled_avx2 vs naive at N=2048 | 48.2× faster | perf stat matmul |
| omp_tiled vs tiled_avx2 at N=10000 | 2.1× faster | perf stat matmul |
| prefetch_ikj instruction blowup | **9.3×** vs ikj_order | perf stat matmul |
| Luna L3 cache | 210 MB | audit |
| Minerva disk | **100% full** | audit |
