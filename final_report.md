# Nanopore Pipeline — Profiling Report
**Chirag Kathpalia | IIT Delhi | Under Prof. Kolin Paul**
**Date: 2026-05-28**

---

## The Pipeline (30 seconds)

```
Patient sample → POD-5 file → Dorado (GPU, basecaller) → BAM → samtools → FASTQ → Kraken-2 (CPU, species ID) → Report
```

**Research goal:** build a caching layer that makes this pipeline faster and less memory-hungry.  
**Profiling goal:** find exactly where time goes so the cache targets the right place.

---

## Headline Numbers

| Stage | Tool | Key Number | Verdict |
|---|---|---|---|
| Kraken-2 (CPU) | perf stat | **34.24% cache miss rate**, 301M misses | memory-bound |
| Kraken-2 (CPU) | gprof | **67% of runtime in `CompactHashTable::Get()`**, 9.87M calls | exact hotspot |
| Kraken-2 (CPU) | AMD uProf | **IPC = 0.55** | CPU stalling on memory |
| Dorado (GPU) | Nsight Systems | **82% of GPU time is GEMM** (Tensor Cores, FP16) | compute-bound |
| Dorado (GPU) | Nsight Systems | **cudaStreamSynchronize = 98.9% of CUDA API time** | synchronous pipeline |

---

## Part 1 — Kraken-2 CPU Profile

### Hardware & Setup

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |
| Input | barcode02.fastq — 104,829 reads, 357.62 Mbp |
| Database | k2_standard_08gb (8 GB pre-built standard DB) |

WSL2 caveat: Hyper-V blocks LLC-specific hardware counters (`LLC-load-misses`). IPC from perf is unreliable (clock reports 0.734 GHz vs real 3.2 GHz). IPC from AMD uProf (native Ryzen profiler, runs outside Hyper-V) is accurate.

---

### Tool 1 — perf stat

```bash
perf stat -e task-clock,cache-misses,cache-references,instructions,cycles \
    kraken2 --db k2_standard_08gb --report report.txt barcode02.fastq
```

| Counter | Value | Notes |
|---|---|---|
| task-clock | 93,832 ms | CPU time |
| cache-misses | **301,288,020** | 301 million misses |
| cache-references | 879,854,514 | 880 million total accesses |
| **cache miss rate** | **34.24%** | 1 in 3 accesses goes to RAM |
| instructions | 155,949,518,373 | 156 billion |
| cycles | 68,853,332,412 | 69 billion |
| IPC (perf) | 2.26 | unreliable — Hyper-V clock |
| wall time | 159.4 s | ~2.7 minutes |
| sys time | 52.5 s | 33% kernel — heavy memory mapping |

**Normal cache miss rate: 1–5%. We got 34.24%.**

Why: the 8 GB hash table is 500× larger than the Ryzen L3 cache (16 MB). Every k-mer lookup is a random jump into RAM. The CPU issues the lookup and stalls for ~100 ns waiting for the data. With 301M misses per run, this dominates runtime.

---

### Tool 2 — gprof (function-level time breakdown)

Kraken-2 compiled from source with `-pg`. barcode02.fastq + 8 GB standard DB.

| % time | self (s) | calls | function |
|---|---|---|---|
| **67.35%** | 71.30 | **9,871,933** | `CompactHashTable::Get()` |
| 18.74% | 19.84 | 354,164,193 | `MinimizerScanner::NextMinimizer()` |
| 5.53% | 5.85 | — | `ClassifySequence()` |
| 2.23% | 2.36 | 354,478,588 | `MinimizerScanner::reverse_complement()` |
| 1.71% | 1.81 | 3,220,914 | `HyperLogLogPlusMinus::insert()` |
| 1.06% | 1.12 | 209,658 | `ks_getuntil2()` (FASTQ parsing) |

**Total runtime: 105.87 seconds**

**`CompactHashTable::Get()` = the exact target.**

67% of all runtime, 9.87 million calls. This is the k-mer hash table lookup function. Each call: hash the 35-mer → compute bucket address → read from RAM. gprof combined with perf tells us exactly where the 301M cache misses land.

`MinimizerScanner::NextMinimizer()` = 18.74%, 354M calls. Pure CPU arithmetic (rolling hash, bit manipulation). Secondary target for SIMD/AVX-512.

**Top two functions = 86% of runtime.**

---

### Tool 3 — AMD uProf (accurate IPC)

AMD uProf is a native Ryzen profiler that bypasses Hyper-V. It reads hardware counters directly from the CPU without going through WSL2's virtualization layer.

| Metric | Value | Notes |
|---|---|---|
| **IPC** | **0.55** | accurate — no Hyper-V distortion |
| Interpretation | < 1.0 | **memory-bound** (CPU stalls waiting for data) |

IPC = instructions per cycle. A value of 0.55 means the CPU is executing less than one instruction per clock tick — it spends most of its time stalled, waiting for RAM to respond to a cache miss.

Contrast: perf reported IPC = 2.26 (unreliable). AMD uProf gives the real number: 0.55. The pipeline is memory-bound.

---

### Kraken-2 — Three-Tool Summary

| Tool | Finding | Implication |
|---|---|---|
| perf stat | 34.24% cache miss rate, 301M misses | Memory-bound — RAM is the bottleneck, not CPU |
| gprof | 67% of time in `CompactHashTable::Get()`, 9.87M calls | Exact function to cache |
| AMD uProf | IPC = 0.55 | CPU stalls on every hash lookup |

**Cache design justification:**
- One LRU hit = one RAM lookup avoided = ~100 ns saved
- Clinical samples have dominant species → same k-mers repeat heavily across reads in one barcode
- At 9.87M lookups/run, a 20% hit rate skips ~2M RAM accesses ≈ **~6 seconds saved per run**
- Cache lives in front of `CompactHashTable::Get()`. Hot k-mers stay in L3 cache. Cold k-mers fall through to the hash table as normal.

---

## Part 2 — Dorado GPU Profile

### Hardware & Setup

| Component | Spec |
|---|---|
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| Mode | fast |
| Input | FBE01990_24778b97_03e50f91_10.pod5 — 104,478 reads, 4 GB |
| Batchsize | 64 |
| Tool | Nsight Systems 2024.2.3 |

---

### CUDA GPU Kernels — Where GPU Time Goes

| % GPU time | total time | avg/call | kernel |
|---|---|---|---|
| **68.5%** | 1,069 s | 19.6 ms | cutlass GEMM 128×64 (Tensor Cores, FP16) |
| **13.5%** | 211 s | 23.3 ms | cutlass GEMM 128×128 (Tensor Cores, FP16) |
| 4.7% | 73.8 s | 8.1 ms | beam_search_step |
| 4.5% | 71.0 s | 2.6 ms | LSTM forward (96 channels) |
| 3.0% | 47.3 s | 2.6 ms | LSTM backward |
| 1.6% | 24.3 s | 2.7 ms | convolution_ntc |
| 1.3% | 20.7 s | 2.3 ms | decode_step |
| 1.3% | 20.2 s | 2.2 ms | compute_posts_step |

**GEMM = 82% of all GPU time.** (68.5% + 13.5%)

These are the transformer attention and linear projection layers running on CUTLASS-optimized Tensor Core kernels (FP16, 8×8×4 tiles). This is the neural network doing the actual basecalling math.

---

### CUDA API — What the CPU Does

| % time | calls | avg/call | API |
|---|---|---|---|
| **98.9%** | 27,283 | 56.6 ms | `cudaStreamSynchronize` |
| 0.5% | 190,891 | 43.5 µs | `cudaLaunchKernel` |
| 0.3% | 27,304 | 186 µs | `cudaMemcpyAsync` |

The CPU launches each batch of kernels then immediately calls `cudaStreamSynchronize` and blocks for 56.6 ms. The CPU is idle the entire time the GPU is computing. 27,283 × 56.6 ms = ~1,544 s of CPU sitting idle. This is an expected synchronous pipeline design — GPU is the bottleneck.

---

### Memory Transfers

| % time | data | direction |
|---|---|---|
| 59.9% | 11,427 MB | CPU RAM → GPU VRAM (signal data in) |
| 25.1% | 11,427 MB | GPU internal |
| 15.0% | 2,856 MB | GPU VRAM → CPU RAM (reads out) |

~25.7 GB total. ~1.25 MB per batch in, ~0.31 MB out. **Transfers are a small fraction of total time. GPU is not memory-starved.**

---

### Dorado — Verdict

| Evidence | Value | Meaning |
|---|---|---|
| GEMM % | 82% | GPU working flat out on matrix math |
| Memory transfers | minor | GPU not waiting for data |
| `cudaStreamSynchronize` | 98.9% CUDA API | CPU waiting on GPU, not the other way around |

**Compute-bound.** The neural network is the bottleneck.

**Signal-to-Base cache justification:**
- If the cache recognises a signal window it has seen before, it skips the entire GEMM forward pass
- GEMM = 82% of GPU time → 30% cache hit rate ≈ **~25% total GPU time saved**
- Cache lookup must be faster than one GEMM call (avg 19.6 ms) — otherwise no benefit
- Must run GPU-side (CUDA shared memory + LSH) — CPU is blocked waiting on GPU, no CPU-side window
- GTX 1650: 64 KB shared memory per SM — cache must stay small and hot

---

## Part 3 — Matrix Multiply Benchmark Study

Built 12 C implementations in `All_Matric_Mul_perf_stats/` to empirically validate cache-blocking theory. Profiled with `perf stat` (WSL2) at N=1024, 2048, and 10000.

### N=10000 Results (wall time, ranked)

| Binary | Wall time | L3 miss% | Strategy |
|---|---|---|---|
| **omp_tiled** | **112,506 ms** | 3.70% | 4-thread OpenMP + tiling — winner |
| tiled_avx2 | 236,546 ms | **18.53%** | AVX2 + tiling — high L3 pressure |
| omp_parallel | 290,699 ms | 2.26% | 4 threads, no tiling |
| tiled | 298,841 ms | 2.92% | Tiling only (TILE=64) |
| ikj_order | 420,796 ms | 2.12% | Cache-friendly loop reorder |
| auto_vec_O3 | 423,079 ms | 2.24% | Compiler auto-vectorize (-O3) |
| avx2_manual | 462,351 ms | 1.64% | AVX2, no tiling |
| unrolled_ikj | 535,330 ms | 1.97% | 4× manual unroll + ikj |
| prefetch_ikj | 927,112 ms | 1.23% | Software prefetch — slowest despite best miss rate |
| kij_order | 1,177,606 ms | 3.04% | kij loop order |
| transpose_B | 1,636,624 ms | 1.94% | Explicit B transpose + ijk |

### Key Findings

**1. omp_tiled wins at large N — but only at large N:**
- N=1024/2048: OpenMP is *slower* than single-thread (thread spawn overhead exceeds benefit)
- N=10000 (2.4 GB working set): 2.1× faster than tiled_avx2 — 4 threads pipeline independent DRAM requests

**2. tiled_avx2 at N=10000: TILE=64 causes L3 overflow (18.53% miss rate)**
- TILE=64 means 3 tiles (A, B, C) × 64² × 4B ≈ 49 KB per core → exceeds 48 KB L1 → L3 eviction at large N
- Fix: TILE=32 keeps all three tiles in L1

**3. The prefetch paradox:**
- `prefetch_ikj` has the *lowest* L3 miss rate (1.23%) but is 2.2× *slower* than ikj_order
- Reason: 9.3× more instructions (5.39 trillion vs 579 billion) — `__builtin_prefetch()` for stride-1 sequential access adds overhead the hardware prefetcher already handles
- **Lesson: reducing miss rate ≠ going faster if instruction overhead exceeds the latency savings**

**4. O(N³) scaling observed:**
- 1024→2048: tiled shows ~4.6× slowdown (vs expected 8×) — tile stays in L2
- 2048→10000: omp_tiled shows only 29× slowdown (vs expected 116×) — parallelism hides DRAM latency

### Relevance to Kraken-2 cache design

`CompactHashTable::Get()` is a *random* access pattern — hash → RAM address is unpredictable. Software prefetch could help here (unlike the sequential matmul case). The benchmark confirms: keeping the hot working set in L2/L3 is the decisive factor. The LRU cache achieves exactly this by keeping recently-seen k-mers in fast memory instead of going to the 8 GB hash table.

---

## Part 4 — Lab Servers

Both servers are documented and accessible. Luna is the primary server going forward.

| Server | CPU | L3 | RAM | GPU | Disk | perf counters |
|---|---|---|---|---|---|---|
| **Minerva** | Xeon Gold 6330, 56c/112t @ 2 GHz | 66 MB | 251 GB | 2× A40 (45 GB) | **100% full** | ✓ (set paranoid=1) |
| **Luna** | Xeon Platinum 8468, 96c/192t @ 3.8 GHz | **210 MB** | **503 GB** | **2× L40S (46 GB)** | 74% (236 GB free) | ✓ paranoid=1 confirmed |

Luna advantages: 3.2× larger L3 cache (210 MB — can potentially hold much of the Kraken-2 working set), AVX-512 + AMX (hardware tile matrix multiply unit on Sapphire Rapids), full TMA (Top-down Microarchitecture Analysis) hardware events available natively.

**Next steps on Luna:**
1. Re-run matmul benchmark suite — get accurate IPC (no Hyper-V), compare Intel Sapphire Rapids vs AMD Zen3 cache behaviour
2. Run Kraken-2 perf + gprof + TMA — confirm IPC ≈ 0.55, get real LLC miss rate, classify bottleneck tier (L1/L2/L3/DRAM)
3. Run Nsight Compute on Dorado GEMM kernel on L40S — SM throughput %, arithmetic intensity

---

## Summary: What We Know and What It Justifies

### Kraken-2 (CPU)

| What we know | Number | Justifies |
|---|---|---|
| Cache miss rate | 34.24% | Memory-bound — caching is the right fix |
| Exact hotspot | `CompactHashTable::Get()`, 67% of runtime | Exactly where the LRU cache sits |
| True IPC | 0.55 | Confirms CPU stalls — cache hits remove stalls |
| Hit rate estimate | 20% → ~6s saved per run | Quantified ROI for cache implementation |

### Dorado (GPU)

| What we know | Number | Justifies |
|---|---|---|
| GEMM dominance | 82% of GPU time | S2B cache skips GEMM entirely on a hit |
| Pipeline type | synchronous | Cache must run GPU-side |
| Potential saving | 30% hit rate → ~25% GPU time | Quantified ROI for S2B cache |
| Constraint | lookup < 19.6 ms (avg GEMM time) | Cache design must be fast enough |

---

*Full raw data and commands: `report.md` (detailed narrative) · `report1.md` (original 2-page)*  
*Lab server comparison: `Luna_vs_Minerva.md`*  
*Matrix multiply full results: `All_Matric_Mul_perf_stats/PERF_REPORT.md`*
