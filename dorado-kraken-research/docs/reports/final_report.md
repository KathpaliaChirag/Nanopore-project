# Nanopore Pipeline: Profiling Report
**Chirag Kathpalia | IIT Delhi | Under Prof. Kolin Paul**
**Date: 2026-05-28**

> **Scope note:** this is a snapshot report as of 2026-05-28, covering WSL2 and early Luna profiling data (Steps 1-12). the WSL2 gprof numbers here (CompactHashTable::Get = 67% of runtime, IPC = 0.55) come from the 650 MB ESKAPE DB on local hardware, not from Luna. the authoritative Luna bare-metal results (cachegrind, flamegraph, NUMA, Steps 1-51+) and the AccuracyDrift experiment (2026-05-30 to 2026-06-13) are not reflected here. for current findings see `Luna/profiling/results_kraken2.md` and `AccuracyDrift/`.

---

## The Pipeline (30 seconds)

before the numbers, here's the pipeline the numbers describe:

```
Patient sample → POD-5 file → Dorado (GPU, basecaller) → BAM → samtools → FASTQ → Kraken-2 (CPU, species ID) → Report
```

**Research goal:** build a caching layer that makes this pipeline faster and less memory-hungry.  
**Profiling goal:** find exactly where time goes, so the cache targets the right place.

---

## Headline Numbers

| Stage | Tool | Key Number | Verdict |
|---|---|---|---|
| Kraken-2 (CPU) | perf stat | **34.24% cache miss rate**, 301M misses | memory-bound |
| Kraken-2 (CPU) | gprof | **67% of runtime in `CompactHashTable::Get()`**, 9.87M calls | exact hotspot |
| Kraken-2 (CPU) | AMD uProf | **IPC = 0.55** | CPU stalling on memory |
| Dorado (GPU) | Nsight Systems | **82% of GPU time is GEMM** (Tensor Cores, FP16) | compute-bound |
| Dorado (GPU) | Nsight Systems | **cudaStreamSynchronize = 98.9% of CUDA API time** | synchronous pipeline |

Kraken-2 is memory-bound, Dorado is compute-bound. that split drives the rest of this report: Part 1 digs into the CPU side, Part 2 into the GPU side.

---

## Part 1: Kraken-2 CPU Profile

### Hardware & Setup

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |
| Input | barcode02.fastq — 104,829 reads, 357.62 Mbp |
| Database | k2_standard_08gb (8 GB pre-built standard DB) |

before trusting any number below, know this: WSL2 runs on Hyper-V, and Hyper-V blocks LLC-specific hardware counters (`LLC-load-misses`) and distorts the clock. perf reports 0.734 GHz where the real clock is 3.2 GHz, so IPC from perf is unreliable here. AMD uProf is a native Ryzen profiler that runs outside Hyper-V, so its IPC number is the one to trust.

---

### Tool 1: perf stat

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

**Normal cache miss rate: 1-5%. we got 34.24%.**

why so high: the 8 GB hash table is 500 times larger than the Ryzen L3 cache (16 MB, the last on-chip pool before a lookup has to go to RAM). every k-mer lookup is a random jump into RAM, so the CPU issues the lookup and stalls for about 100 ns waiting for the data. with 301 million misses per run, this stall dominates runtime.

---

### Tool 2: gprof (function-level time breakdown)

perf stat tells us the CPU is stalling on memory, but not which function causes it. that's what gprof is for: it breaks runtime down by function. we compiled Kraken-2 from source with `-pg` (the gprof instrumentation flag) and ran it against barcode02.fastq with the 8 GB standard DB.

| % time | self (s) | calls | function |
|---|---|---|---|
| **67.35%** | 71.30 | **9,871,933** | `CompactHashTable::Get()` |
| 18.74% | 19.84 | 354,164,193 | `MinimizerScanner::NextMinimizer()` |
| 5.53% | 5.85 | — | `ClassifySequence()` |
| 2.23% | 2.36 | 354,478,588 | `MinimizerScanner::reverse_complement()` |
| 1.71% | 1.81 | 3,220,914 | `HyperLogLogPlusMinus::insert()` |
| 1.06% | 1.12 | 209,658 | `ks_getuntil2()` (FASTQ parsing) |

**Total runtime: 105.87 seconds**

**`CompactHashTable::Get()` is the exact target.**

it accounts for 67% of all runtime across 9.87 million calls. this is the k-mer hash table lookup function: each call hashes the 35-mer, computes a bucket address, then reads from RAM. gprof combined with perf tells us exactly where the 301 million cache misses land.

`MinimizerScanner::NextMinimizer()` comes second at 18.74%, 354 million calls. it's pure CPU arithmetic (rolling hash, bit manipulation), not a memory bottleneck, which makes it a secondary target for SIMD/AVX-512 rather than caching.

**the top two functions account for 86% of runtime.**

---

### Tool 3: AMD uProf (accurate IPC)

perf's IPC number is unreliable under WSL2 (see the caveat above), so we need a second tool to get the real figure. AMD uProf is a native Ryzen profiler that bypasses Hyper-V: it reads hardware counters directly from the CPU without going through WSL2's virtualization layer.

| Metric | Value | Notes |
|---|---|---|
| **IPC** | **0.55** | accurate — no Hyper-V distortion |
| Interpretation | < 1.0 | **memory-bound** (CPU stalls waiting for data) |

IPC (instructions per cycle) is the count of instructions the CPU finishes per clock tick. a value of 0.55 means the CPU executes less than one instruction per tick, so it spends most of its time stalled, waiting for RAM to respond to a cache miss.

for contrast: perf reported IPC = 2.26, and we already know that number is unreliable. AMD uProf gives the real figure, 0.55. the pipeline is memory-bound.

---

### Kraken-2: Three-Tool Summary

| Tool | Finding | Implication |
|---|---|---|
| perf stat | 34.24% cache miss rate, 301M misses | Memory-bound — RAM is the bottleneck, not CPU |
| gprof | 67% of time in `CompactHashTable::Get()`, 9.87M calls | Exact function to cache |
| AMD uProf | IPC = 0.55 | CPU stalls on every hash lookup |

**why an LRU cache is the right fix, and what it should buy us:**
- one LRU hit means one RAM lookup avoided, so about 100 ns saved
- clinical samples have a dominant species, so the same k-mers repeat heavily across reads in one barcode
- 301 million total L3 misses divided by 9.87 million calls is about 30 L3 misses per `Get()` call on average
- a 20% hit rate on 9.87 million calls skips about 2 million calls; each hit avoids about 30 L3 misses, so that's about 60 million fewer RAM accesses
- at about 100 ns per miss, 60 million times 100 ns is roughly **6 seconds saved per run** (this assumes one LRU hit eliminates all misses for that call, an assumption we still need to validate with a k-mer reuse measurement on actual FASTQ)
- the cache sits in front of `CompactHashTable::Get()`: hot k-mers stay in L3 cache, cold k-mers fall through to the hash table as normal

that's the CPU side. Part 2 does the same walk for the GPU.

---

## Part 2: Dorado GPU Profile

### Hardware & Setup

| Component | Spec |
|---|---|
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| Mode | fast |
| Input | FBE01990_24778b97_03e50f91_10.pod5 — 104,478 reads, 4 GB |
| Batchsize | 64 |
| Tool | Nsight Systems 2024.2.3 |

---

### CUDA GPU Kernels: Where GPU Time Goes

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

**GEMM (general matrix multiply) accounts for 82% of all GPU time** (68.5% + 13.5%).

these two kernels are the transformer attention and linear projection layers, running on CUTLASS-optimized Tensor Core kernels (FP16, 8x8x4 tiles). this is the neural network doing the actual basecalling math, so GEMM dominating GPU time is expected, not a bug to chase.

---

### CUDA API: What the CPU Does

| % time | calls | avg/call | API |
|---|---|---|---|
| **98.9%** | 27,283 | 56.6 ms | `cudaStreamSynchronize` |
| 0.5% | 190,891 | 43.5 µs | `cudaLaunchKernel` |
| 0.3% | 27,304 | 186 µs | `cudaMemcpyAsync` |

the CPU launches each batch of kernels, then immediately calls `cudaStreamSynchronize` and blocks for 56.6 ms. it sits idle the entire time the GPU computes: 27,283 calls times 56.6 ms is about 1,544 s of CPU idle time. that's an expected synchronous pipeline design, not a flaw, since the GPU is the bottleneck here, not the CPU.

---

### Memory Transfers

| % time | data | direction |
|---|---|---|
| 59.9% | 11,427 MB | CPU RAM → GPU VRAM (signal data in) |
| 25.1% | 11,427 MB | GPU internal |
| 15.0% | 2,856 MB | GPU VRAM → CPU RAM (reads out) |

that's about 25.7 GB total, roughly 1.25 MB per batch in and 0.31 MB out. **transfers are a small fraction of total time, so the GPU is not memory-starved.**

---

### Dorado: Verdict

| Evidence | Value | Meaning |
|---|---|---|
| GEMM % | 82% | GPU working flat out on matrix math |
| Memory transfers | minor | GPU not waiting for data |
| `cudaStreamSynchronize` | 98.9% CUDA API | CPU waiting on GPU, not the other way around |

**compute-bound.** the neural network itself is the bottleneck, not memory or the CPU-GPU handoff.

**why a Signal-to-Base cache makes sense here, and what it should buy us:**
- if the cache recognises a signal window it has already seen, it skips the entire GEMM forward pass for that window
- GEMM is 82% of GPU time, so even a 30% cache hit rate works out to roughly **25% total GPU time saved**
- the cache lookup has to be faster than one GEMM call (19.6 ms average), otherwise it costs more than it saves
- it has to run GPU-side (CUDA shared memory + LSH), because the CPU is blocked waiting on the GPU and gets no window to do lookup work of its own
- the GTX 1650 only gives 64 KB of shared memory per SM, so the cache has to stay small and hot

that closes out the GPU side. Part 3 steps back to a separate matmul benchmark that validates the cache-blocking theory both Parts 1 and 2 lean on.

---

## Part 3: Matrix Multiply Benchmark Study

Parts 1 and 2 both assume that keeping data in a fast, small cache beats going to RAM. to check that assumption empirically rather than just asserting it, we built 12 C implementations in `All_Matrix_Mul_perf_stats/` and profiled them with `perf stat` (WSL2) at N=1024, 2048, and 10000.

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

**1. omp_tiled wins at large N, but only at large N:**
- at N=1024/2048, OpenMP runs *slower* than single-thread, because thread spawn overhead exceeds the benefit
- at N=10000 (2.4 GB working set), it runs 2.1x faster than tiled_avx2, because 4 threads pipeline independent DRAM requests

**2. tiled_avx2 at N=10000: TILE=64 causes L3 overflow (18.53% miss rate)**
- TILE=64 means 3 tiles (A, B, C) at 64² x 4B come to about 49 KB per core, which exceeds the 48 KB L1 cache and forces L3 eviction at large N
- the fix: TILE=32 keeps all three tiles in L1

**3. the prefetch paradox:**
- you'd expect the lowest L3 miss rate to win, but it doesn't: `prefetch_ikj` has the *lowest* L3 miss rate (1.23%) and is still 2.2x *slower* than ikj_order
- the reason is instruction count, not cache behavior: prefetch_ikj runs 9.3x more instructions (5.39 trillion vs 579 billion), because `__builtin_prefetch()` for stride-1 sequential access adds overhead the hardware prefetcher already handles for free
- **lesson: reducing miss rate does not mean going faster, if the instruction overhead exceeds the latency savings**

**4. O(N³) scaling observed:**
- 1024 to 2048: tiled shows about 4.6x slowdown against an expected 8x, because the tile stays in L2
- 2048 to 10000: omp_tiled shows only 29x slowdown against an expected 116x, because parallelism hides DRAM latency

### Relevance to Kraken-2 Cache Design

this benchmark matters for Part 1 because it tells us which lever actually works. `CompactHashTable::Get()` has a *random* access pattern: hash to RAM address is unpredictable, unlike the sequential matmul case, so software prefetch could help here where it hurt prefetch_ikj above. the benchmark confirms the decisive factor is keeping the hot working set in L2/L3. the LRU cache proposed in Part 1 does exactly that: it keeps recently-seen k-mers in fast memory instead of going to the 8 GB hash table.

---

## Part 4: Lab Servers

the WSL2 and lab-desktop numbers above are useful for a first pass, but the real profiling work moves to dedicated lab servers. both are documented and accessible; Luna is the primary server going forward.

| Server | CPU | L3 | RAM | GPU | Disk | perf counters |
|---|---|---|---|---|---|---|
| **Minerva** | Xeon Gold 6330, 56c/112t @ 2 GHz | 66 MB | 251 GB | 2× A40 (45 GB) | **100% full** |  (set paranoid=1) |
| **Luna** | Xeon Platinum 8468, 96c/192t @ 3.8 GHz | **210 MB** | **503 GB** | **2× L40S (46 GB)** | 74% (236 GB free) |  paranoid=1 confirmed |

Luna's advantages over the WSL2 setup used above: a 3.2x larger L3 cache (210 MB, large enough to potentially hold much of the Kraken-2 working set), AVX-512 plus AMX (a hardware tile matrix multiply unit on Sapphire Rapids), and full TMA (Top-down Microarchitecture Analysis) hardware events available natively, none of which Hyper-V exposes.

**Next steps on Luna:**
1. re-run the matmul benchmark suite to get accurate IPC (no Hyper-V) and compare Intel Sapphire Rapids against AMD Zen3 cache behaviour
2. run Kraken-2 perf, gprof, and TMA together to confirm IPC is still around 0.55, get the real LLC miss rate, and classify the bottleneck tier (L1/L2/L3/DRAM)
3. run Nsight Compute on the Dorado GEMM kernel on L40S for SM throughput % and arithmetic intensity

with those three steps done, the summary below can be re-checked against Luna's real numbers instead of the WSL2 ones.

---

## Summary: What We Know and What It Justifies

everything above builds toward one thing: a case for two caches, one per pipeline stage. the tables below tie each measured number to the design decision it justifies.

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
*Matrix multiply full results: `All_Matrix_Mul_perf_stats/PERF_REPORT.md`*
