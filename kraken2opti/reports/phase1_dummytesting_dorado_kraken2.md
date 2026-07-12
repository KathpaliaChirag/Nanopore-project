# Phase 1 & 2a — Dorado & Kraken2 Profiling: Full Details

**Dorado GPU profiling (fast, HAC, CPU vs GPU, scaling) + Kraken2 gprof.**
This file contains the complete run data, tables, and verdicts for Phases 1a–2a.

### Abbreviations

| Term | Meaning |
|------|---------|
| nsys | Nsight Systems (NVIDIA GPU profiler) |
| CUDA | Compute Unified Device Architecture (NVIDIA GPU programming platform) |
| API | Application Programming Interface |
| GEMM | General Matrix Multiply |
| LSTM | Long Short-Term Memory (type of recurrent neural network) |
| CTC | Connectionist Temporal Classification (loss/decoding algorithm used in sequence-to-sequence tasks like basecalling) |
| HtoD | Host-to-Device (CPU RAM → GPU VRAM memory transfer) |
| DtoH | Device-to-Host (GPU VRAM → CPU RAM memory transfer) |
| DtoD | Device-to-Device (within GPU memory) |
| FP16 | 16-bit floating point (half precision) |
| INT8 | 8-bit integer precision (used in quantised neural networks) |
| HAC | High Accuracy (Dorado basecalling model tier) |
| CUTLASS | NVIDIA's GPU linear algebra template library (used internally by PyTorch/Dorado) |
| NN | Neural Network |
| MKL | Intel Math Kernel Library (optimised math routines) |
| DNNL | Deep Neural Network Library (Intel's neural network primitives, also called oneDNN) |
| JIT | Just-In-Time compilation |
| gprof | GNU profiler (function-level CPU profiling tool) |
| L3 | Level-3 cache (shared across cores, ~16 MB on this machine) |
| DRAM | Dynamic Random-Access Memory (main system memory, ~100 ns latency) |
| LRU | Least Recently Used (cache eviction policy) |

---

## Phase 1a — Dorado Fast Model GPU Profiling (Nsight Systems)

**Date:** 2026-05-21
**Tool:** nsys 2026.2.1 (run with sudo — required due to Dorado's bundled CUDA runtime)
**Input:** `FBE01990_24778b97_03e50f91_10.pod5`
**Model:** `dna_r10.4.1_e8.2_400bps_fast@v5.2.0`
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
**Command:**
```bash
sudo nsys profile --output ~/results/nsight/dorado_fast_profile \
  --trace cuda --stats true --resolve-symbols=false --force-overwrite true \
  -- /opt/dorado/bin/dorado basecaller \
  dna_r10.4.1_e8.2_400bps_fast@v5.2.0 FBE01990_24778b97_03e50f91_10.pod5 \
  --output-dir ~/results/nsight/bam --batchsize 64
```

### Run Summary

| Metric | Value |
|---|---|
| Total runtime | 186.8 seconds (186,855 ms) |
| Reads basecalled | 104,478 |
| Throughput | 27.2M samples/sec |
| Batch size | 64 |

---

### Top GPU Kernels

| Rank | % Time | Total Time | Instances | Kernel |
|---|---|---|---|---|
| 1 | 26.2% | 48.1 s | 9,082 | `beam_search_step` |
| 2 | 16.6% | 30.4 s | 61,726 | `ampere_h16816gemm_128x64` (Tensor Core GEMM) |
| 3 | 13.9% | 25.4 s | 27,246 | `lstm` (forward, 96-dim) |
| 4 | 9.9% | 18.2 s | 9,082 | `decode_step` |
| 5 | 9.3% | 17.0 s | 18,164 | `lstm` (reverse, 96-dim) |
| 6 | 8.6% | 15.7 s | 9,082 | `compute_posts_step` |

Top 6 kernels account for **84.5%** of total GPU time.

---

### Memory Transfers

| Operation | % of Transfer Time | Total Data | Avg per Call |
|---|---|---|---|
| Host → Device | 74.1% | 11,424 MB | 1.254 MB |
| Device → Host | 18.3% | 2,855 MB | 0.314 MB |
| Device → Device | 7.6% | 11,424 MB | 1.255 MB |

Transfers are large and regular (~1.28 MB per call) — efficient, not fragmented.

---

### CUDA API Breakdown

| % Time | Calls | API Call |
|---|---|---|
| 98.4% | 27,268 | `cudaStreamSynchronize` |
| 1.1% | 254,360 | `cudaLaunchKernel` |
| 0.5% | 27,289 | `cudaMemcpyAsync` |

`cudaStreamSynchronize` dominates API time — CPU is blocking on GPU completion, confirming the GPU is the pacing unit.

---

### Verdict

**Dorado fast model is compute-bound.**

- GPU time is dominated by neural network inference: LSTM layers + Tensor Core GEMM + beam search = ~76% of total GPU time
- Memory transfers are large and efficient — HtoD/DtoH is not a bottleneck
- CPU is spending 98.4% of its CUDA API time waiting on the GPU (`cudaStreamSynchronize`), meaning the GPU is the bottleneck, not the CPU pipeline

**Implication for cache:** A signal-to-base cache would not significantly speed up Dorado. The GPU is already running at capacity doing neural net inference. Speedup requires algorithmic changes (smaller model, quantization, or faster decoding) — not caching.

---

### Setup Note

nsys cannot intercept Dorado's CUDA runtime without `sudo`. Dorado bundles its own private `libcudart.so.12` in `dorado/lib/`, which ignores nsys's standard `CUDA_INJECTION64_PATH` injection. Running as root bypasses this restriction. All future nsys runs on Dorado require `sudo`.

---

## Phase 1b — Dorado HAC Model GPU Profiling (Nsight Systems)

**Date:** 2026-05-21
**Tool:** nsys 2026.2.1 (sudo)
**Input:** `FBE01990_24778b97_03e50f91_10.pod5`
**Model:** `dna_r10.4.1_e8.2_400bps_hac@v5.2.0`
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
**Command:**
```bash
sudo nsys profile --output ~/results/nsight/dorado_hac_profile \
  --trace cuda --stats true --resolve-symbols=false --force-overwrite true \
  -- /opt/dorado/bin/dorado basecaller \
  dna_r10.4.1_e8.2_400bps_hac@v5.2.0 FBE01990_24778b97_03e50f91_10.pod5 \
  --output-dir ~/results/nsight/bam_hac --batchsize 64
```

### Run Summary

| Metric | Fast Model | HAC Model |
|---|---|---|
| Total runtime | 186.8 s | 502.0 s |
| Reads basecalled | 104,478 | 104,477 (1 filtered) |
| Throughput | 27.2M samples/sec | 10.1M samples/sec |
| Slowdown vs fast | — | **2.69×** |
| Batch size | 64 | 64 |

---

### Top GPU Kernels

| Rank | % Time | Total Time | Instances | Kernel |
|---|---|---|---|---|
| 1 | **69.8%** | 347.9 s | 59,906 | `cutlass::LstmKernel` (CUTLASS LSTM) |
| 2 | 8.6% | 42.7 s | 8,558 | `beam_search_step` |
| 3 | 5.9% | 29.5 s | 8,558 | `cutlass::LinearLayer` (GEMM) |
| 4 | 4.3% | 21.2 s | 8,558 | `compute_posts_step` |
| 5 | 3.9% | 19.3 s | 8,558 | `decode_step` |
| 6 | 3.0% | 15.2 s | 8,558 | `back_guide_step` |

Top 6 kernels account for **95.5%** of total GPU time.

**Key difference from fast model:** HAC uses a much larger CUTLASS LSTM kernel (69.8% of time vs fast model's simpler `lstm` at 23.2%). The HAC LSTM alone accounts for more GPU time than the entire fast model run proportionally.

---

### Memory Transfers

| Operation | % of Transfer Time | Total Data | Avg per Call | Calls |
|---|---|---|---|---|
| Host → Device | 87.2% | 25,137 MB | 0.196 MB | 128,403 |
| Device → Host | 8.9% | 2,694 MB | 0.315 MB | 8,556 |
| Device → Device | 3.8% | 10,642 MB | 1.239 MB | 8,587 |

**Notable:** HAC has 128,403 HtoD transfers vs fast's 9,107 — 14× more calls but smaller average size (0.196 MB vs 1.254 MB). More fragmented data movement, consistent with a larger, more complex model architecture.

---

### CUDA API Breakdown

| % Time | Calls | API Call |
|---|---|---|
| 99.1% | 51,378 | `cudaStreamSynchronize` |
| 0.5% | 299,649 | `cudaLaunchKernel` |
| 0.4% | 145,546 | `cudaMemcpyAsync` |

CPU blocking on GPU even more dominant than fast model (99.1% vs 98.4%) — HAC model keeps the GPU busier for longer per synchronization point.

---

### Fast vs HAC Comparison

| Metric | Fast | HAC |
|---|---|---|
| Runtime | 186.8 s | 502.0 s |
| Top kernel | `beam_search_step` (26.2%) | `LstmKernel` (69.8%) |
| LSTM % of GPU time | ~23% | ~70% |
| Memory transfer calls (HtoD) | 9,107 | 128,403 |
| `cudaStreamSynchronize` % | 98.4% | 99.1% |
| Throughput | 27.2M samples/s | 10.1M samples/s |

---

### Verdict

**HAC is even more strongly compute-bound than fast.**

- The CUTLASS LSTM kernel alone consumes 69.8% of all GPU time — this is a large transformer-style recurrent layer with no equivalent in the fast model
- Beam search drops from #1 bottleneck (fast) to #2 (HAC), because the LSTM now dominates
- Memory transfers are more fragmented (14× more HtoD calls) but still not the bottleneck
- GPU is saturated: CPU spends 99.1% of CUDA API time in `cudaStreamSynchronize`

**Implication for cache:** Same conclusion as fast model — HAC is compute-bound, not memory-bound. A cache targeting data movement would recover <5% of runtime. The CUTLASS LSTM kernel is the target for any real speedup (quantization, pruning, or a smaller model variant).

---

## Phase 1c — Dorado Optimization Analysis

**Date:** 2026-05-21
**Based on:** nsys profiling results from Phase 1a (fast) and Phase 1b (HAC)

---

### What Dorado Already Uses

Dorado is not a naive implementation. It uses NVIDIA's highest-level GPU math libraries:

**CUTLASS (NVIDIA's GPU Linear Algebra Templates):**
- `cutlass::LstmKernel` and `cutlass::LinearLayer` are the dominant kernels in HAC (69.8% + 5.9%)
- CUTLASS internally implements: tiled matrix multiply, shared memory blocking, register blocking, double buffering (software pipelining), warp-level Tensor Core operations
- Strided MM, blocking, tiling — **already done at the library level**

**Tensor Cores (Ampere architecture):**
- `ampere_h16816gemm` (fast model) — FP16 matrix multiply on hardware Tensor Cores
- CUTLASS LSTM (HAC) — also runs on Tensor Cores via FP16
- RTX 4050 Laptop GPU has 20 Tensor Core units — Dorado is using them

**Conclusion:** Standard textbook GPU optimizations (blocking, tiling, shared memory, SIMD) are already implemented by CUTLASS. Hand-writing these would not beat the library.

---

### What Could Actually Make Dorado Faster

| Optimization | Potential Speedup | Difficulty | Current Status |
|---|---|---|---|
| INT8 quantization | ~2× on Tensor Cores | Medium | Not used (FP16 only) |
| 2:4 structured sparsity | Up to 2× on Ampere+ | Hard | Not used |
| Larger batch size | 10–30% | Easy | Tunable (`--batchsize`) |
| Beam search kernel rewrite | 10–20% | Hard | Custom but unoptimized |
| Replace LSTM → Mamba/S4 | Architecture-level | Very hard | Research area |
| FP8 precision | ~2× over FP16 | Medium | Requires Hopper GPU (H100) |

---

### Most Realistic Optimizations on RTX 4050

**1. Larger batch size (immediate, zero code change)**

Batchsize 64 was used. Larger batches improve Tensor Core utilization:
```bash
dorado basecaller ... --batchsize 128
# or
dorado basecaller ... --batchsize 256
```
Expected 10–30% throughput gain.

**2. INT8 quantization (significant, research gap)**

Dorado uses FP16 throughout. INT8 would double Tensor Core throughput on Ampere (RTX 4050 supports INT8 Tensor Cores). Oxford Nanopore has not implemented this — open research opportunity. Accuracy impact on basecalling needs evaluation.

**3. Beam search kernel (tractable target)**

`beam_search_step` is 26.2% of fast model GPU time. CTC beam search has GPU-unfriendly access patterns — sequential, branchy, irregular memory access. This is a custom Dorado kernel (not CUTLASS) and the most realistic target for a new optimized implementation without changing the model architecture.

---

### Why a Cache Does Not Help Dorado

Dorado is **compute-bound** (confirmed by both fast and HAC profiles):
- 98–99% of CUDA API time is `cudaStreamSynchronize` — CPU waiting on GPU
- GPU is saturated with LSTM and GEMM computation
- Memory transfers are efficient and not the bottleneck

A signal-to-base cache would target data movement — but data movement is <5% of total runtime. Even eliminating all memory transfers would save ~9 seconds on the 187s fast run. The LSTM and beam search kernels cannot be cached because every read produces unique signal data.

---

## Phase 1d — CPU vs GPU Comparison (Dorado Fast Model)

**Date:** 2026-05-22
**Input:** `200.pod5` (Merged_files, ~200 MB)
**Model:** `dna_r10.4.1_e8.2_400bps_fast@v5.2.0`
**CPU:** AMD Ryzen 7 7735HS (16 threads)
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU
**Profiler (CPU):** `perf record --call-graph dwarf,512 -F 50`
**Profiler (GPU):** `nsys profile --trace cuda --stats true`

---

### Run Summary

| Metric | CPU | GPU | Speedup |
|--------|-----|-----|---------|
| Wall time | 340,235 ms | 9,622 ms | **~35x** |
| Throughput | 8.02 × 10⁵ samples/s | 2.84 × 10⁷ samples/s | **~35x** |
| Reads basecalled | 1861 | 1861 | — |
| Batch size | 16 | 64 (Dorado auto-adjusted) | — |

---

### CPU Profiling (`perf`) — Top Hotspots by Self Time

**Samples:** 283K of `cpu/cycles/P` (~12.5 × 10¹² cycles)

| % | Thread | Symbol | Notes |
|---|--------|--------|-------|
| 5.72% | `cpu_beam_search` | `cpu_index_kernel` | Tensor gather/index — memory-bandwidth bound |
| 2.44% | `cpu_beam_search` | `beam_search` | Dorado CTC beam decoder |
| 2.38% | `cpu_beam_search` | `cat_serial_kernel` | **Serial** tensor concat — no parallelism |
| 2.01% | `cpu_beam_search` | `add_kernel` AVX2 | Vectorized float add |
| 1.58% | `cpu_beam_search` | `max_values_kernel_impl` AVX2 | Vectorized max reduction |
| 1.45% | `cpu_beam_search` | `mkl_vml_sExp` | MKL exp |
| 1.44% | `bscl_worker` | `kernel_init_pages` | Page fault — memory zeroing on first touch |
| 1.15% | `bscl_worker` | `mkl_blas_def_sgemm_kernel_0_zen` | SGEMM (AMD Zen-optimized, FP32) |
| ~0.7% | `cpu_beam_search` | `TensorIteratorBase` ctor/dtor + `malloc` | Tensor allocation churn |

**Thread types:** `bscl_worker` (neural net inference via JIT + DNNL), `cpu_beam_search` (CTC decoding)

**Memory pressure:** Top-level perf showed **~10% of cycles** in `asm_exc_page_fault` → `do_anonymous_page` — Dorado demand-pages large buffers instead of pre-allocating.

---

### GPU Profiling (`nsys`) — Kernel Breakdown

**Chunk sizes:** 9996 and 4998 (two model heads), batch size 64

| % | Kernel | What |
|---|--------|------|
| 25.9% | `beam_search_step` | CTC beam decoder — dominant GPU kernel |
| 16.9% | `ampere_h16816gemm_128x64` | FP16 GEMM (Ampere tensor cores) |
| 13.9% | `lstm` (fwd, 96 units, int8 input) | LSTM forward pass |
| 9.9% | `decode_step` | CTC path decoding |
| 9.3% | `lstm` (bidirectional, 96 units) | LSTM reverse pass |
| 8.6% | `compute_posts_step` | Posterior probability computation |
| 6.4% | `convolution_ntc` (stride 16, ReLU) | CNN feature extraction |
| 3.8% | `back_guide_step` | CTC backward guide |
| 3.7% | `window_ntwc_f16` | FP16 windowing for chunked inference |

**CUDA API:** 97.2% of time in `cudaStreamSynchronize` — CPU is idle, GPU is the pacing unit.

**Memory transfers:** 590 MB H→D (input chunks), 147 MB D→H (basecall results), 592 MB D→D (activations).

---

### CPU vs GPU Side-by-Side

| Aspect | CPU | GPU |
|--------|-----|-----|
| Top bottleneck | Tensor gather/index (5.7%) | Beam search kernel (25.9%) |
| NN compute | FP32 SGEMM (MKL/DNNL) | FP16 GEMM + int8 LSTM (tensor cores) |
| Memory behavior | ~10% cycles in page faults | Clean, async pre-allocated transfers |
| Parallelism | Serial `cat_serial_kernel` is a bottleneck | Fully parallel GPU pipeline |
| CPU utilization | Fully loaded | Idle (97% waiting on GPU) |

---

### Key Findings

1. **35x speedup** from FP16 tensor cores (vs FP32 SGEMM), parallel LSTM execution, and no memory allocation overhead.
2. **Beam search is the consistent bottleneck** on both devices — 2.44% self time on CPU, 25.9% on GPU. As NN gets faster, decoding becomes proportionally more dominant.
3. **CPU memory management is costly** — ~10% of cycles lost to page faults and tensor allocation churn; GPU avoids this entirely.
4. **GPU CPU-side overhead is negligible** — 97% of CUDA API time is waiting, confirming GPU is the bottleneck on the GPU run.

---

### Profiling Commands

```bash
# CPU
sudo perf record -g --call-graph dwarf,512 -F 50 \
    -o /tmp/perf.data \
    /opt/dorado/bin/dorado basecaller --device cpu \
    <model> <pod5> --output-dir /tmp/bam_cpu_fast --batchsize 16
sudo perf report --input /tmp/perf.data --stdio --no-children

# GPU
sudo nsys profile --output ~/results/nsight/dorado_gpu_fast \
    --trace cuda --stats true --resolve-symbols=false --force-overwrite true \
    -- /opt/dorado/bin/dorado basecaller \
    <model> <pod5> --output-dir /tmp/bam_gpu_fast --batchsize 16
```

---

## Phase 1e — CPU vs GPU Scaling Across File Sizes (Dorado Fast)

**Date:** 2026-05-22
**Model:** `dna_r10.4.1_e8.2_400bps_fast@v5.2.0`
**Inputs:** `Merged_files/{200,400,600}.pod5` (219 / 419 / 620 MB)
**Profilers:** CPU `perf record --call-graph dwarf,512 -F 50`; GPU `nsys profile --trace cuda`
**Batch size:** 16

### Wall-Clock Results

| File | CPU | GPU | Speedup |
|------|-----|-----|---------|
| 200.pod5 | 364.0 s | 14.9 s | **24×** |
| 400.pod5 | 705.2 s | 24.4 s | **29×** |
| 600.pod5 | 1030.3 s | 33.7 s | **31×** |

Graph: `~/results/cpu_vs_gpu.svg` (log-scale grouped bars).

### Findings

- Both devices scale ~linearly with input size; CPU ≈ 1.7 s/MB, GPU ≈ 0.055 s/MB.
- **Speedup widens with size (24× → 31×)** — GPU amortizes fixed startup (model load, batch-size benchmarking) over more reads, while CPU has no such fixed cost to hide.
- Consistent with Phase 1d: GPU wins via FP16 tensor cores + parallel LSTM and avoids the CPU's page-fault / allocation overhead.

### Automation

Reusable scripts in `~/Desktop/summer_project/`:
- `benchmark_cpu_gpu.sh [fast|hac]` — loops POD5 files, runs perf (CPU) + nsys (GPU), appends wall times to `~/results/timing_cpu_gpu.csv`.
- `plot_cpu_gpu.py` — reads the CSV, emits log-scale CPU-vs-GPU bar chart (matplotlib PNG, or dependency-free SVG fallback).

**Pending:** add 800.pod5 and 1000.pod5 to complete the scaling curve.

---

## Phase 1f — Dorado Fast Model Re-profiling (Post Ubuntu Reinstall)

**Date:** 2026-05-25
**Tool:** nsys 2026.2.1 (sudo + LD_PRELOAD fake_tty.so)
**Input:** `FBE01990_24778b97_03e50f91_15.pod5`
**Model:** `dna_r10.4.1_e8.2_400bps_fast@v5.2.0`
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
**Command:**
```bash
sudo LD_PRELOAD=/tmp/fake_tty.so nsys profile \
  --output ~/Desktop/summer_project/results/fast/nsight/dorado_fast_profile \
  --trace cuda --stats true --resolve-symbols=false --force-overwrite true \
  -- ~/Desktop/summer_project/tools/dorado/bin/dorado basecaller \
  dna_r10.4.1_e8.2_400bps_fast@v5.2.0 \
  ~/Desktop/summer_project/data/pod5/FBE01990_24778b97_03e50f91_15.pod5 \
  --output-dir ~/Desktop/summer_project/results/fast/nsight/bam_fast --batchsize 64
```

### Run Summary

| Metric | Value |
|---|---|
| Total runtime | 44.95 s (44,950 ms) |
| Reads basecalled | 30,275 |
| Throughput | 26.7M samples/sec |
| Batch size | 64 |

### Top GPU Kernels

| Rank | % Time | Instances | Kernel |
|---|---|---|---|
| 1 | 26.0% | 2,186 | `beam_search_step` |
| 2 | 16.5% | 14,822 | `ampere_h16816gemm_128x64` (Tensor Core GEMM) |
| 3 | 13.9% | 6,558 | `lstm` (forward, 96-dim) |
| 4 | 10.1% | 2,186 | `decode_step` |
| 5 | 9.3% | 4,372 | `lstm` (reverse, 96-dim) |
| 6 | 8.6% | 2,186 | `compute_posts_step` |

**Verdict:** Identical kernel distribution to Phase 1a — results confirmed on new Ubuntu 26.04 setup.

**Setup note:** `LD_PRELOAD=/tmp/fake_tty.so` required to restore dorado progress bar under nsys on Ubuntu 26.04. nsys intercepts child process stderr, causing `isatty()` to return false. The fake_tty.so override forces fd 2 to report as TTY.

---

## Phase 1g — Dorado HAC Model Re-profiling (Post Ubuntu Reinstall)

**Date:** 2026-05-25
**Tool:** nsys 2026.2.1 (sudo + LD_PRELOAD fake_tty.so)
**Input:** `FBE01990_24778b97_03e50f91_15.pod5`
**Model:** `dna_r10.4.1_e8.2_400bps_hac@v5.2.0`
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)

### Run Summary

| Metric | Fast (Phase 1f) | HAC (Phase 1g) |
|---|---|---|
| Total runtime | 44.95 s | 116.6 s |
| Reads basecalled | 30,275 | 30,275 |
| Throughput | 26.7M samples/sec | 10.3M samples/sec |
| Slowdown vs fast | — | **2.59×** |

### Top GPU Kernels

| Rank | % Time | Instances | Kernel |
|---|---|---|---|
| 1 | **70.0%** | 14,175 | `cutlass::LstmKernel` |
| 2 | 8.3% | 2,025 | `beam_search_step` |
| 3 | 5.9% | 2,025 | `cutlass::LinearLayer` (GEMM) |
| 4 | 4.3% | 2,025 | `compute_posts_step` |
| 5 | 3.9% | 2,025 | `decode_step` |

**Verdict:** Consistent with Phase 1b — LstmKernel dominates at 70%, results validated.

---

## Phase 2a — Kraken2 Classification + gprof Profiling

**Date:** 2026-05-25
**Tool:** gprof (Kraken2 compiled with -pg), kraken2/src/classify
**Input:** 30,362 reads (FASTQ converted from fast model BAM via samtools)
**Database:** minikraken2_v2_8GB_201904_UPDATE
**Command:**
```bash
# Convert BAM to FASTQ
samtools fastq results/fast/nsight/bam_fast/.../bam_pass/FBE01990_pass_24778b97_03e50f91_0.bam \
  > results/fast/nsight/reads.fastq

# Run classification with gprof instrumented binary
~/Desktop/summer_project/tools/kraken2/src/classify \
  -H data/minikraken2_v2_8GB_201904_UPDATE/hash.k2d \
  -t data/minikraken2_v2_8GB_201904_UPDATE/taxo.k2d \
  -o data/minikraken2_v2_8GB_201904_UPDATE/opts.k2d \
  -R results/kraken2/kraken2_report.txt \
  -O results/kraken2/kraken2_output.txt \
  results/fast/nsight/reads.fastq

# Generate gprof report
gprof tools/kraken2/src/classify tools/kraken2/src/gmon.out > results/kraken2/gprof_report.txt
```

### Classification Summary

| Metric | Value |
|---|---|
| Reads processed | 30,362 |
| Runtime | 42.2 s |
| Classified | 28,236 (93.0%) |
| Unclassified | 2,126 (7.0%) |
| Throughput | 43.2K reads/min |

### gprof Flat Profile — Top Hotspots

| % Time | Cumulative (s) | Function |
|---|---|---|
| **80.65%** | 9.50 | `CompactHashTable::Get()` — k-mer DB lookup |
| 9.51% | 10.62 | `MinimizerScanner::NextMinimizer()` — minimizer generation |
| 3.48% | 11.03 | `ClassifySequence()` — main classification logic |
| 1.02% | 11.15 | `canonical_representation()` — DNA strand canonicalization |
| 1.02% | 11.27 | `HyperLogLogPlusMinus::insert()` — cardinality estimation |
| 1.02% | 11.39 | `AddHitlistString()` — hit accumulation |

### Verdict

**Kraken2 is memory-bound at the hash table lookup.**

- 80.65% of all CPU time is spent in `CompactHashTable::Get()` — random k-mer lookups into an 8 GB hash table
- The 8 GB database does not fit in any CPU cache (L1: 64 KB, L2: 512 KB, L3: 16 MB) — every lookup is effectively a RAM access
- This is the exact function where Kolin sir's Hot-K-mer LRU cache would intercept — high-frequency k-mers cached in L1/L2 would convert RAM accesses to cache hits

**Implication for cache:** Unlike Dorado (compute-bound), Kraken2 is strongly memory-bound. A Hot-K-mer LRU cache targeting the top-N most frequent k-mers could eliminate the majority of RAM round-trips in `CompactHashTable::Get()`, potentially reducing runtime by 40–60% depending on k-mer frequency distribution.
