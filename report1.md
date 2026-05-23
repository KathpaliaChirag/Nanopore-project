# Profiling Report — Nanopore Pipeline
**Prepared by:** Chirag Kathpalia

---

## System Setup

| Component | Detail |
|---|---|
| OS | Windows 11 Home |
| WSL2 Kernel | 6.6.87.2-microsoft-standard-WSL2 |
| Linux Distro | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Architecture | x86_64 |
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |

## Tools Installed

| Tool | Version |
|---|---|
| Valgrind | 3.22.0 |
| build-essential | 12.10ubuntu1 |
| git | 2.43.0 |
| cmake | 3.28.3 |
| perf | Built from WSL2-Linux-Kernel source (tag linux-msft-wsl-6.6.87.2). Hardware counters work (cycles, instructions, cache-misses, branches). LLC-specific counters (LLC-loads, LLC-load-misses) show `<not supported>` — Hyper-V does not expose them. Per-function LLC data covered by cachegrind. |
| Nsight Systems | 2024.2.3.38 (Windows) |
| samtools | Installed via apt in WSL2 |

---

## Page 1 — Kraken-2 CPU Profile (perf stat)

**Input:** barcode02.fastq — 104,829 reads, 357.62 Mbp  
**Database:** k2_standard_08gb (8 GB pre-built standard database)  
**Tool:** perf stat -e task-clock,cache-misses,cache-references,instructions,cycles  
**Environment:** WSL2 (Ubuntu 24.04), AMD Ryzen 7 5800H, 14 GB RAM

---

### 1.1 perf stat Results

| Counter | Value | Notes |
|---|---|---|
| task-clock | 93,832 ms | CPU time used |
| cache-misses | 301,288,020 | 301 million cache misses |
| cache-references | 879,854,514 | 880 million total cache accesses |
| **cache miss rate** | **34.24%** | 1 in 3 cache accesses goes to RAM |
| instructions | 155,949,518,373 | 156 billion instructions |
| cycles | 68,853,332,412 | 69 billion cycles |
| IPC | 2.26 insn/cycle | *see caveat below* |
| wall time | 159.4 s | total elapsed time |
| user time | 39.7 s | CPU in user space |
| sys time | 52.5 s | CPU in kernel (memory management) |

**WSL2 caveat on IPC:** the clock frequency reported (0.734 GHz) is far below the real Ryzen 5800H speed (~3.2 GHz). This is a Hyper-V hardware counter limitation — the IPC and cycle numbers are unreliable. The **cache miss rate (34.24%) is the reliable metric** as it is a ratio and does not depend on clock accuracy.

---

### 1.2 Verdict — Memory-Bound

**Kraken-2 with the 8 GB database is severely memory-bound.**

| Evidence | Value | Interpretation |
|---|---|---|
| Cache miss rate | 34.24% | 1 in 3 accesses goes to slow RAM (normal: 1-5%) |
| Cache misses total | 301 million | Each miss costs ~100 ns RAM latency |
| sys time | 52.5 s (33% of wall time) | High kernel time = heavy memory mapping overhead |
| Database size | 8 GB | Does not fit in L3 cache (~16 MB on Ryzen 5800H) |

**Why this happens:** Kraken-2 hashes each read's k-mers and looks them up in the database hash table. The table is 8 GB — 500× larger than the L3 cache. Every lookup lands in a random location in RAM, causing a cache miss almost every time. The CPU spends most of its time waiting for RAM, not computing.

---

### 1.3 Implications for Kolin sir's Hot-K-mer LRU Cache

The 34.24% cache miss rate is the direct justification for the LRU k-mer cache:

- If the cache keeps recently-seen k-mers in fast memory, repeated lookups hit cache instead of RAM
- 1 cache hit saved = 100 ns gained (RAM latency avoided)
- At 301 million misses per run — even a 20% hit rate = 60 million fewer RAM accesses = ~6 seconds saved
- The cache does not need to be large: k-mer accesses are not uniformly random — clinical samples have dominant species whose k-mers repeat heavily across reads

**Key number for the report:** 34.24% cache miss rate. Kraken-2 misses cache on 1 in 3 memory accesses — confirming it is memory-bound and that a k-mer cache directly targets the bottleneck.

---

---

## Page 2 — Dorado GPU Profile (Nsight Systems)

**Input:** FBE01990_24778b97_03e50f91_10.pod5 — 104,478 reads, 4 GB  
**Mode:** fast  
**Batchsize:** 64  
**Tool:** nsys profile --trace cuda,nvtx  

---

### 2.1 NVTX Range Summary — What Dorado spends time on

| % Time | Total Time | Instances | Avg per call | Stage |
|---|---|---|---|---|
| 39.8% | 3,180 s | 9,085 | 350 ms | basecall_current_batch |
| 39.8% | 3,179 s | 9,085 | 350 ms | call_chunks |
| 19.6% | 1,569 s | 9,086 | 173 ms | cuda_thread_fn_device_0 |
| 0.2% | 19.5 s | 9,087 | 2.1 ms | nn_forward |
| 0.1% | 8.9 s | 9,085 | 0.98 ms | cpu_decode |
| 0.1% | 8.1 s | 9,087 | 0.89 ms | lstm_stack |
| 0.1% | 7.5 s | 9,087 | 0.83 ms | gpu_decode |
| 0.1% | 6.1 s | 27,261 | 0.22 ms | conv |

`basecall_current_batch` and `call_chunks` are nested (same wall time). `cuda_thread_fn_device_0` represents actual GPU execution time per batch — 19.6% of total annotated time.

9,085 batches processed = 104,478 reads / ~11.5 reads per batch at batchsize 64.

---

### 2.2 CUDA GPU Kernel Summary — Where GPU time actually goes

| % GPU Time | Total Time | Instances | Avg per call | Kernel |
|---|---|---|---|---|
| **68.5%** | 1,069 s | 54,522 | 19.6 ms | cutlass GEMM 128x64 (matrix multiply, Tensor Cores) |
| **13.5%** | 211 s | 9,087 | 23.3 ms | cutlass GEMM 128x128 (matrix multiply, Tensor Cores) |
| 4.7% | 73.8 s | 9,087 | 8.1 ms | beam_search_step |
| 4.5% | 71.0 s | 27,261 | 2.6 ms | lstm (forward, 96 channels) |
| 3.0% | 47.3 s | 18,174 | 2.6 ms | lstm (backward, 96 channels) |
| 1.6% | 24.3 s | 9,087 | 2.7 ms | convolution_ntc |
| 1.3% | 20.7 s | 9,087 | 2.3 ms | decode_step |
| 1.3% | 20.2 s | 9,087 | 2.2 ms | compute_posts_step |

**GEMM dominates: 68.5% + 13.5% = 82% of all GPU time is matrix multiplication.**

These GEMM kernels are the Transformer attention and linear projection layers. They use CUDA Tensor Cores (half-precision, `h884` = FP16 8×8×4 tile). This is the neural network forward pass doing actual basecalling math.

---

### 2.3 CUDA API Summary — What the CPU does with CUDA

| % Time | Calls | Avg per call | API Call |
|---|---|---|---|
| **98.9%** | 27,283 | 56.6 ms | cudaStreamSynchronize |
| 0.5% | 190,891 | 43.5 μs | cudaLaunchKernel |
| 0.3% | 27,304 | 186 μs | cudaMemcpyAsync |

**cudaStreamSynchronize = 98.9% of all CUDA API time.**

This means the CPU calls `cudaStreamSynchronize` 27,283 times (once per batch) and blocks for an average of 56.6 ms each time waiting for the GPU to finish. The CPU is idle while the GPU runs. This is expected for a synchronous inference pipeline — GPU is the bottleneck, not CPU.

---

### 2.4 Memory Transfer Summary

| % Time | Total Data | Count | Operation |
|---|---|---|---|
| 59.9% | 11,427 MB | 9,112 | Host→Device (CPU RAM → GPU VRAM) |
| 25.1% | 11,427 MB | 9,107 | Device→Device (GPU internal) |
| 15.0% | 2,856 MB | 9,085 | Device→Host (GPU VRAM → CPU RAM) |

Total data moved: ~25.7 GB across the full run.  
Per batch: ~1.25 MB CPU→GPU, ~0.31 MB GPU→CPU.

Memory transfers account for a minority of total time compared to compute — the GPU is not starved of data.

---

### 2.5 Verdict — Compute-bound or Memory-bound?

**Dorado (fast mode) on GTX 1650 is compute-bound.**

Evidence:
- 82% of GPU time is GEMM (matrix multiply) — pure arithmetic
- `cudaStreamSynchronize` takes 98.9% of CPU CUDA time — CPU is waiting on GPU, not the other way around
- Memory transfers are ~15% of transfer time, not dominant
- GPU is doing real Tensor Core math, not waiting for data

**What this means for Kolin sir's Signal-to-Base (S2B) cache:**
- If the cache avoids re-running the neural network for similar signal windows, it skips the GEMM kernels entirely
- Since GEMM = 82% of GPU time, even a 30% cache hit rate would save ~25% of total GPU time
- The cache lookup itself must be fast (CUDA shared memory + LSH) — slower than a GEMM call = no benefit
- On GTX 1650 (4 GB VRAM), shared memory per SM = 64 KB — cache must be small and hot
