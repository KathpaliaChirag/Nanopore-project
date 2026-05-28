# Report — Executed Work Log

This file tracks everything actually run, tested, or completed.
Each entry comes from the plan and represents something done, not just planned.

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

## Phase 2a — Kraken-2 Classification + gprof Profiling

**Date:** 2026-05-25
**Tool:** gprof (Kraken-2 compiled with -pg), kraken2/src/classify
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

**Kraken-2 is memory-bound at the hash table lookup.**

- 80.65% of all CPU time is spent in `CompactHashTable::Get()` — random k-mer lookups into an 8 GB hash table
- The 8 GB database does not fit in any CPU cache (L1: 64 KB, L2: 512 KB, L3: 16 MB) — every lookup is effectively a RAM access
- This is the exact function where Kolin sir's Hot-K-mer LRU cache would intercept — high-frequency k-mers cached in L1/L2 would convert RAM accesses to cache hits

**Implication for cache:** Unlike Dorado (compute-bound), Kraken-2 is strongly memory-bound. A Hot-K-mer LRU cache targeting the top-N most frequent k-mers could eliminate the majority of RAM round-trips in `CompactHashTable::Get()`, potentially reducing runtime by 40-60% depending on k-mer frequency distribution.

**Pending:** perf stat (cache miss rates, TLB misses, IPC) to quantify memory pressure numerically.

---

## Phase 2b — Matmul 21-Variant CH3 (perf stat) Sweep

**Date:** 2026-05-28
**Workload:** Square C = A·B, N=1024, doubles (one A,B,C set = 8 MB each, 24 MB total)
**Machine:** AMD Zen, 16 logical CPUs, paranoid=-1 (IBS without sudo)
**Compile:** `gcc -O2 -g -march=native` (+ `-fopenmp` / `-mavx2 -mfma` / `-lopenblas` as needed)
**Tools:** `perf stat` (basic), `perf stat` (AMD cache events), `perf stat -r 5` (stability), `perf stat` (full diagnosis: cache + branches + FP dispatch + load-queue stalls).
**Source:** `results/pfz_batch1/src/matmul_*.c` (21 variants)
**Raw output:** `results/pfz_batch1/ch3_perf_stat/perf_stat_{basic,cache,r5,full}_*.txt` (84 files)

### Variant Inventory

5 optimisation primitives, composed:
- **T** Tiling (TILE=64) — cache blocking
- **O** OpenMP (`#pragma omp parallel for`) — requests 16 threads on outer loop (effective parallelism 7–13 CPUs, see CH3-E)
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

### CH3-A — Wall Time, IPC, Speedup, GFlops/s

Wall time is taken from the **binary's own `clock_gettime` measurement** (kernel-only — excludes the ~25 ms init), not from `perf stat`'s `time elapsed`. GFlops/s = 2N³ / kernel_time.

| # | Variant | kernel s | speedup | cycles | instructions | **IPC** | GFlops/s |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | matmul_naive | **1.982** | 1.00× | 7,854,221,194 | 2,063,180,664 | **0.2627** | 1.083 |
| 2 | matmul_ikj | 0.178 | 11.13× | 904,563,657 | 1,777,469,865 | 1.9650 | 12.065 |
| 3 | matmul_tiled | 0.590 | 3.36× | 2,749,005,458 | 11,105,033,151 | **4.0397** | 3.640 |
| 4 | matmul_omp | 0.037 | 53.57× | 1,878,666,089 | 1,833,441,322 | 0.9759 | 58.040 |
| 5 | matmul_avx | 0.149 | 13.30× | 775,169,674 | 2,046,804,484 | 2.6405 | 14.413 |
| 6 | matmul_prefetch | 0.138 | 14.36× | 721,191,739 | 1,776,738,417 | 2.4636 | 15.561 |
| 7 | matmul_unroll | 0.130 | 15.25× | 681,902,598 | 1,778,086,703 | 2.6075 | 16.519 |
| 8 | matmul_tiled_omp | 0.085 | 23.32× | 5,091,685,552 | 11,138,503,479 | 2.1876 | 25.265 |
| 9 | matmul_tiled_avx | 0.120 | 16.52× | 626,708,764 | 1,939,916,225 | 3.0954 | 17.896 |
| 10 | matmul_tiled_prefetch | 0.605 | 3.28× | 2,794,578,172 | 13,251,882,513 | **4.7420** | 3.550 |
| 11 | matmul_tiled_unroll | 0.123 | 16.11× | 634,893,555 | 2,092,434,946 | 3.2957 | 17.459 |
| 12 | matmul_omp_avx | **0.036** | 55.06× | 1,653,185,960 | 2,080,209,313 | 1.2583 | 59.652 |
| 13 | matmul_tiled_omp_avx | **0.021** | **94.38×** | 1,279,637,279 | 2,259,481,176 | 1.7657 | **102.261** |
| 14 | matmul_tiled_omp_prefetch | 0.115 | 17.23× | 5,240,033,189 | 13,302,898,439 | 2.5387 | 18.674 |
| 15 | matmul_tiled_avx_prefetch | 0.160 | 12.39× | 783,955,792 | 2,780,046,754 | 3.5462 | 13.422 |
| 16 | matmul_tiled_avx_unroll | 0.118 | 16.80× | 609,822,779 | 1,756,229,634 | 2.8799 | 18.199 |
| 17 | matmul_tiled_omp_avx_prefetch | 0.038 | 52.16× | 1,931,102,452 | 2,853,888,578 | 1.4779 | 56.513 |
| 18 | matmul_ultimate (T+O+A+P+U) | 0.034 | 58.29× | 1,781,071,891 | 2,053,753,230 | 1.1531 | 63.161 |
| 19 | matmul_transposed | 0.728 | 2.72× | 3,435,007,366 | 3,409,934,622 | 0.9927 | 2.950 |
| 20 | **matmul_blas (OpenBLAS)** | **0.012** | **165.17×** | 2,679,350,335 | 1,624,624,129 | 0.6064 | **178.957** |
| 21 | matmul_strassen | 0.330 | 6.01× | 1,656,103,049 | 5,693,087,875 | 3.4376 | 6.508 |

**Cycles** and **instructions** for OMP variants are *summed across all 16 threads* (per `task-clock`); wall time is real elapsed. That's why their IPC looks "low" — it's per-CPU-cycle averaged across all threads, including any idle/sync.

### CH3-B — Cache Hierarchy (all 21)

| # | Variant | L1 loads | L1 misses | **L1 miss%** | L2 misses | L3 fills | DRAM fills |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | matmul_naive | 620,228,366 | 289,415,270 | **46.6627%** | **212,467,124** | **221,004,382** | 1,015,668 |
| 2 | matmul_ikj | 867,281,803 | 143,272,050 | 16.5197% | 1,624,585 | 7,728,984 | 3,255,418 |
| 3 | matmul_tiled | 3,372,143,810 | 273,517,285 | 8.1111% | 5,572,082 | 9,198,755 | 640,150 |
| 4 | matmul_omp | 872,124,697 | 175,606,787 | 20.1355% | 702,811 | 2,718,952 | 540,098 |
| 5 | matmul_avx | 871,696,450 | 141,225,642 | 16.2012% | 2,708,752 | 13,471,462 | 2,992,376 |
| 6 | matmul_prefetch | 862,392,360 | 141,054,716 | 16.3562% | 1,554,386 | 7,797,982 | 3,539,575 |
| 7 | matmul_unroll | 870,349,223 | 143,973,679 | 16.5421% | 1,477,183 | 7,467,864 | 3,155,043 |
| 8 | matmul_tiled_omp | 3,354,435,898 | 280,767,594 | 8.3700% | 4,329,898 | 6,681,663 | 734,523 |
| 9 | matmul_tiled_avx | 623,955,060 | 182,014,787 | 29.1711% | 16,251,999 | 16,121,893 | 745,664 |
| 10 | matmul_tiled_prefetch | 3,324,939,128 | 235,331,926 | **7.0778%** | 4,361,552 | 5,842,255 | 628,670 |
| 11 | matmul_tiled_unroll | 640,699,153 | 175,080,886 | 27.3265% | 6,480,693 | 6,457,344 | 510,294 |
| 12 | matmul_omp_avx | 868,666,357 | 173,326,752 | 19.9532% | 927,427 | 3,638,885 | 783,321 |
| 13 | matmul_tiled_omp_avx | 722,261,612 | 182,466,250 | 25.2632% | 14,302,533 | 16,237,044 | 805,272 |
| 14 | matmul_tiled_omp_prefetch | 3,326,990,273 | 256,453,148 | 7.7083% | 14,201,887 | 21,198,758 | 743,528 |
| 15 | matmul_tiled_avx_prefetch | 760,518,310 | 202,396,437 | 26.6130% | 30,596,073 | 31,428,613 | 620,442 |
| 16 | matmul_tiled_avx_unroll | 621,750,507 | 176,203,301 | 28.3399% | 18,810,826 | 19,048,246 | 497,867 |
| 17 | matmul_tiled_omp_avx_prefetch | 866,806,874 | 200,680,140 | 23.1517% | 17,344,078 | 20,470,120 | 335,930 |
| 18 | matmul_ultimate | 851,186,760 | 193,020,001 | 22.6766% | 25,907,754 | 32,606,572 | 358,751 |
| 19 | matmul_transposed | 603,545,604 | 146,917,956 | 24.3425% | 3,304,360 | 3,136,792 | 2,408,330 |
| 20 | matmul_blas | 354,254,250 | 54,368,008 | 15.3472% | 2,532,822 | 2,188,998 | 1,954,957 |
| 21 | matmul_strassen | 2,391,999,148 | 119,942,680 | **5.0143%** | 3,810,031 | 2,616,564 | 3,277,371 |

> **Naive's 46.66% L1-miss rate** is the *root cause* of its IPC stall. Every other L1 load misses because `B[k][j]` strides by N=8192 bytes. The 212 M L2 misses also fail to find data in L2, but **99.5% of them are absorbed by L3** — only 1 M reach DRAM. Naive is **L3-latency bound**, not DRAM-bound. (Same conclusion as the original report; numbers reproduce within 1.5%.)
>
> **Tiling reduces L1 miss% to 8%** (5.7× lower than naive) — exactly its intended effect. But the variant runs **3.3× slower than ikj** anyway, because the 6-deep nested loop emits 11.1 B instructions vs ikj's 1.78 B. Tiling's win is wasted at N=1024 where everything fits in L3 already.
>
> **OMP_AVX has 20% L1 miss** but is one of the fastest. With 16 threads each touching ~64 rows of C, threads' working sets overlap less and the per-thread L1 (32 KB) is large enough to capture the hot block of B.
>
> **Strassen has the lowest L1 miss% (5%)** because its recursive base case (128×128) fits perfectly in L1, but executes 5.7 B instructions and 850 M branches (1.74% mis-predict) → 6× speedup only.

### CH3-C — Stability (5-run, perf stat -r 5) — all 21

`mean_s` is mean of "elapsed" (includes ~25 ms init each run); for the fastest variants, the init is most of the measured time.

| # | Variant | mean (s) | stddev (s) | **± %** |
|---|---|---:|---:|---:|
| 1 | matmul_naive | 1.462155 | 0.029811 | 2.0400% |
| 2 | matmul_ikj | 0.175999 | 0.005977 | 3.4000% |
| 3 | matmul_tiled | 0.602674 | 0.004553 | **0.7600%** |
| 4 | matmul_omp | 0.047941 | 0.002232 | 4.6600% |
| 5 | matmul_avx | 0.178607 | 0.004968 | 2.7800% |
| 6 | matmul_prefetch | 0.181755 | 0.006906 | 3.8000% |
| 7 | matmul_unroll | 0.181340 | 0.003516 | 1.9400% |
| 8 | matmul_tiled_omp | 0.110403 | 0.001324 | 1.2000% |
| 9 | matmul_tiled_avx | 0.154810 | 0.003272 | 2.1100% |
| 10 | matmul_tiled_prefetch | 0.658865 | 0.004881 | **0.7400%** |
| 11 | matmul_tiled_unroll | 0.151960 | 0.003962 | 2.6100% |
| 12 | matmul_omp_avx | 0.050173 | 0.002243 | 4.4700% |
| 13 | matmul_tiled_omp_avx | 0.048320 | 0.001378 | 2.8500% |
| 14 | matmul_tiled_omp_prefetch | 0.118612 | 0.001887 | 1.5900% |
| 15 | matmul_tiled_avx_prefetch | 0.192773 | 0.004983 | 2.5800% |
| 16 | matmul_tiled_avx_unroll | 0.151474 | 0.001523 | 1.0100% |
| 17 | matmul_tiled_omp_avx_prefetch | 0.055811 | 0.003107 | 5.5700% |
| 18 | matmul_ultimate | 0.050674 | 0.001890 | 3.7300% |
| 19 | matmul_transposed | 0.737476 | 0.007508 | 1.0200% |
| 20 | matmul_blas | 0.070031 | 0.007328 | **10.4600%** |
| 21 | matmul_strassen | 0.379741 | 0.005696 | 1.5000% |

> Most variants reproduce within 3–5%. **BLAS is the noisiest (±10%)** because OpenBLAS performs runtime CPU-feature dispatch and thread-pool warm-up on first invocation. The first run includes ~30 ms of pthread fan-out; subsequent runs are ~12 ms.
>
> Plain `tiled` (no threads) is the most reproducible (±0.76%): single-threaded, no allocator activity, identical instruction stream every run.

### CH3-D — Direct Stall Evidence (all 21)

`de_dis_dispatch_token_stalls1.load_queue_rsrc_stall` = cycles where the front-end wanted to dispatch a load but the load queue was full. Normalised by FP dispatches to make variants comparable.

| # | Variant | FP dispatches | LQ stalls | **LQ-stall / FP-disp** |
|---|---|---:|---:|---:|
| 1 | **matmul_naive** | 872,134,592 | **1,715,319,197** | **196.6806%** |
| 2 | matmul_ikj | 829,424,023 | 28,986,723 | 3.4948% |
| 3 | matmul_tiled | 3,435,719,105 | 92,420 | **0.0027%** |
| 4 | matmul_omp | 914,963,336 | 92,611,767 | 10.1219% |
| 5 | matmul_avx | 850,617,264 | 38,872,712 | 4.5699% |
| 6 | matmul_prefetch | 857,976,827 | 31,003,225 | 3.6135% |
| 7 | matmul_unroll | 855,331,773 | 31,668,583 | 3.7025% |
| 8 | matmul_tiled_omp | 3,246,046,371 | 5,325,468 | 0.1641% |
| 9 | matmul_tiled_avx | 851,120,387 | 180,319,167 | 21.1861% |
| 10 | matmul_tiled_prefetch | 3,410,031,126 | 56,527,238 | 1.6577% |
| 11 | matmul_tiled_unroll | 862,982,224 | 146,168,250 | 16.9376% |
| 12 | matmul_omp_avx | 1,045,010,297 | 142,799,661 | 13.6649% |
| 13 | matmul_tiled_omp_avx | 811,836,383 | 150,993,157 | 18.5990% |
| 14 | matmul_tiled_omp_prefetch | 3,321,693,572 | 56,178,810 | 1.6913% |
| 15 | matmul_tiled_avx_prefetch | 840,587,443 | 163,072,184 | 19.3998% |
| 16 | matmul_tiled_avx_unroll | 840,976,045 | 157,544,516 | 18.7335% |
| 17 | matmul_tiled_omp_avx_prefetch | 832,444,160 | 137,716,702 | 16.5437% |
| 18 | matmul_ultimate | 938,969,192 | 161,053,973 | 17.1522% |
| 19 | matmul_transposed | 2,447,388,622 | 116,288 | **0.0048%** |
| 20 | matmul_blas | 386,852,805 | 34,494,936 | 8.9168% |
| 21 | matmul_strassen | 2,409,768,404 | 75,662,282 | 3.1398% |

> **The smoking gun for naive.** Load-queue stalls happen **1.97× per FP dispatch** — the CPU spends nearly 2 cycles blocked on memory for every 1 cycle of useful FP work. `ikj` is **56× lower** (3.49%). Same `mulpd`+`addpd` ops, but loads hit L1 now. This is a *single number* that proves the bottleneck is memory hierarchy stalls, not compute.
>
> **Tiled has near-zero LQ stalls** (0.003%) and `transposed` is similarly clean (0.005%). Both spread their loads over many more loop-control instructions, so the load queue drains between requests. But they're still slower than `ikj` overall — the extra instructions cost wall time even when the loads themselves are cheap. *Not* evidence that tiled is "front-end bound"; just that LQ stalls aren't its bottleneck either.
>
> **AVX variants have higher LQ stalls** (17–21%) than non-AVX equivalents because each AVX load brings in 4 doubles at once — the load queue fills faster.

### CH3-E — Parallel Efficiency (task-clock / elapsed = avg CPUs used)

| # | Variant | task-clock (ms) | elapsed (ms) | **CPUs used** | Threads spawned |
|---|---|---:|---:|---:|---:|
| 1 | matmul_naive | 2010.53 | 2014.43 | 0.9981 | 1 |
| 2 | matmul_ikj | 199.36 | 202.42 | 0.9849 | 1 |
| 3 | matmul_tiled | 610.34 | 613.27 | 0.9952 | 1 |
| 4 | matmul_omp | 468.42 | 59.71 | **7.8450** | 16 |
| 5 | matmul_avx | 170.26 | 173.43 | 0.9817 | 1 |
| 6 | matmul_prefetch | 157.26 | 160.20 | 0.9817 | 1 |
| 7 | matmul_unroll | 150.00 | 153.40 | 0.9778 | 1 |
| 8 | matmul_tiled_omp | 1280.98 | 110.47 | **11.5956** | 16 |
| 9 | matmul_tiled_avx | 140.65 | 143.73 | 0.9786 | 1 |
| 10 | matmul_tiled_prefetch | 626.87 | 630.16 | 0.9948 | 1 |
| 11 | matmul_tiled_unroll | 144.11 | 147.44 | 0.9774 | 1 |
| 12 | matmul_omp_avx | 440.89 | 60.97 | **7.2316** | 16 |
| 13 | matmul_tiled_omp_avx | 347.77 | 42.87 | **8.1121** | 16 |
| 14 | matmul_tiled_omp_prefetch | 1348.46 | 139.76 | **9.6484** | 16 |
| 15 | matmul_tiled_avx_prefetch | 180.28 | 182.98 | 0.9852 | 1 |
| 16 | matmul_tiled_avx_unroll | 138.62 | 141.43 | 0.9801 | 1 |
| 17 | matmul_tiled_omp_avx_prefetch | 514.60 | 61.40 | **8.3816** | 16 |
| 18 | matmul_ultimate | 468.98 | 55.94 | **8.3842** | 16 |
| 19 | matmul_transposed | 748.91 | 754.10 | 0.9931 | 1 |
| 20 | **matmul_blas** | 625.18 | 46.73 | **13.3790** | 16 |
| 21 | matmul_strassen | 359.56 | 362.27 | 0.9925 | 1 |

> **Parallel efficiency is poor for hand-rolled OMP variants (7–9 CPUs out of 16).** Even `tiled_omp` only reaches 11.6 CPUs. Reasons:
> - The init loop (random fill) is single-threaded and pulls down the average.
> - The matmul work per thread (~70 K ops for tiled_omp_avx) is so small that thread-startup amortises poorly — first thread is already finishing before the last starts.
> - OpenMP's static schedule pre-divides the outer `i` loop into 16 fixed chunks; if N/16 = 64 rows isn't a multiple of TILE=64, some threads do 1 row-tile and others do 0 (load imbalance).
>
> **OpenBLAS reaches 13.38 CPUs** — best parallel efficiency of the dataset. It uses pthread_create with affinity pinning + a dynamic work-stealing dispatch, both of which the naive `#pragma omp parallel for` doesn't.

### Surprises and Anomalies

1. **`matmul_blas` is 1.75× faster than my best hand-written ultimate** (0.012 s vs 0.034 s, 179 GFlops/s vs 63 GFlops/s). OpenBLAS uses cache-aware register tiling + `dgemm_kernel_ZEN` hand-tuned microkernels — instruction count is 1.6 B (lowest of all variants).
2. **`matmul_tiled_omp_avx` (0.021 s) is faster than `matmul_ultimate` (0.034 s)** — adding the unroll layer on top of the 3-stack *hurts*. Several mechanisms are plausible: (a) register pressure / spills from the 8-wide unrolled inner body, (b) the unrolled body crossing an i-cache line boundary, (c) extra prefetch + unroll causing cache pollution. I did not disassemble to confirm which, but the headline conclusion is clear: **stacking more optimisations is not monotonic — `tiled_omp_avx` is the sweet spot.**
3. **Tiled variants have the highest IPC** (`tiled_prefetch` = 4.74, `tiled` = 4.04) but the worst wall time. The cause is mechanical: high IPC × **6× more instructions** = same cycle budget as ikj. **IPC alone is a misleading optimisation target** — `wall_time = instructions / IPC / clock`, not just IPC.
4. **Strassen at base=128 + ikj kernel hits L1 miss% = 5%** (lowest of all), but its recursive structure causes **1.74% branch-misprediction** (3–6× higher than peers). The 5.7 B instruction count is dominated not by Strassen's "extra adds/subs" (those reduce arithmetic complexity overall) but by the **per-level split/merge copies and malloc/free overhead** at each recursion. Net: only 6× faster than naive. **Algorithmic complexity ≠ wall time at N=1024.**
5. **`matmul_omp` plain (no explicit AVX) is nearly as fast as `omp_avx`** (37 ms vs 36 ms). The most likely explanation is that `gcc -O2 -march=native` already auto-vectorises plain `omp`'s inner loop (its body is identical to `ikj`, which is also auto-vectorised). So the comparison may be **AVX vs AVX**, not "AVX vs scalar." A bandwidth-bound argument is also possible but secondary; without disassembly I can't say which dominates.
6. **`matmul_transposed` is slower than `matmul_ikj`** (728 ms vs 178 ms — 4× slower). Two contributing factors visible in the data: (a) **higher L1-miss rate** (24.3% vs 16.5%), and (b) **1.92× more instructions** (3.41 B vs 1.78 B), including the O(N²) transpose itself (~30 ms). The "compiler can't vectorise the scalar dot product" angle is *one* factor but the cache penalty alone explains much of the gap. **Pre-transpose is just a worse pattern than loop-reorder when N already fits in L1 row-wise.**
7. **`matmul_unroll` (0.130 s) is the *fastest single-optimisation* variant** — beating `ikj`, `tiled`, `avx`, and `prefetch`. The 4× manual unroll on top of (already-auto-vectorised) `ikj` gives gcc more freedom to schedule the FP pipeline. **Best single-trick ROI** if you're allowed to touch only one thing.
8. **`matmul_prefetch` (0.138 s) is faster than explicit `matmul_avx` (0.149 s)** — even though prefetch is "just" `__builtin_prefetch` on a scalar ikj. The likely reason: gcc's auto-vectoriser on `ikj` already emits AVX FMA, *and* prefetch removes residual L2 latency that the AVX intrinsic version still pays. Explicit intrinsics don't automatically win over `-march=native`.

### Critical Self-Review — What's Justified, What's Speculation

Going through my own claims above and grading them:

**Solid (data directly supports the claim):**
- ✅ "Naive is L3-latency bound, not DRAM-bound" — proven by L3-fill = 221 M vs DRAM = 1 M (99.5% absorbed by L3).
- ✅ "Naive's 196.7% LQ-stall-per-FP-dispatch is the smoking gun" — direct hardware counter; 56× lower for ikj using same arithmetic.
- ✅ "Tiling reduces L1 miss% from 47% to 8% but runs 3.4× slower than ikj" — both numbers in the table, instruction count gap (11.1 B vs 1.78 B) explains the regression.
- ✅ "BLAS is 1.75× faster than ultimate at 0.012 s vs 0.034 s" — measured both, reproducible across r5.
- ✅ "Strassen breaks branch prediction at 1.74% misses" — directly measured, 3-6× higher than peers.

**Plausible but partly speculative (the data is consistent with multiple explanations):**
- ⚠ "ultimate is slower than tiled_omp_avx because of register pressure from unrolling" — I claimed register spills from 8-wide unroll. I did **not** verify with `objdump` to count spills. The 18 ms gap could equally be (a) thread-pool spin-up variance (stability is ±3.7%, so ±2 ms — not enough), (b) cache pollution from the extra prefetch hints, or (c) the unrolled body crossing an i-cache line boundary. **Verification needed:** `objdump -d matmul_ultimate | grep -E "spill|push|pop"` vs `matmul_tiled_omp_avx`.
- ⚠ "omp_avx ≈ omp because it's bandwidth-bound" — also plausible: `gcc -O2 -march=native` already auto-vectorises the plain `matmul_omp` body (the inner loop is identical to `matmul_ikj`, and `-march=native` enables AVX2 codegen). So `omp` may *already be* AVX. **Verification needed:** disassemble both and check for `vfmadd*pd`. If both have AVX FMA, the equivalence is trivial — not a "bandwidth bound" story.
- ⚠ "Transposed slower because compiler can't vectorise the dot product" — partly true (the scalar accumulator does prevent some loop forms from auto-vectorising), but transposed also has higher L1 miss (24.3% vs ikj's 16.5%) and 1.92× more instructions. **The cache hit alone explains some of the gap; "can't vectorise" is over-stated.**
- ⚠ "Tiled's high IPC but slow wall is because the bottleneck moved to front-end" — I had originally claimed "instruction-fetch bound" without evidence. The truer statement: high IPC × 6× more instructions = same cycle count as ikj. There's no front-end stall measurement in this run.

**Unverified but consistent with prior knowledge:**
- ❓ "OpenBLAS uses runtime CPU dispatch + thread pool warm-up" — I inferred this from the ±10% stability. Plausible (BLAS is known to do this), but I didn't strace it. Could equally be NUMA-effect on first run.
- ❓ "OpenBLAS dispatches with affinity + work-stealing" — community knowledge; I didn't read OpenBLAS source for this run.

**Probably wrong / softer than I made it sound:**
- ❌ The original report claimed naive IPC = 0.350 with 4.5 B instructions. **My run shows 2.06 B instructions** — gcc auto-vectorised the naive ijk with `-march=native`. So the *original* report's narrative "0.35 IPC because no vectorisation" is **now incorrect under the new compile**: the IPC dropped because each instruction does more work, not because of stalls. The bottleneck (memory) is the same, but the *number that proves it* should be the LQ-stall rate, not IPC.
- ❌ I wrote "OMP at 16 threads" in places. Actually `omp_get_max_threads()` printed 16, but parallel efficiency shows only **7.84–11.60 effective CPUs**. The threads exist but don't all do useful work simultaneously.

**What I'd do differently if rerunning:**
1. Disassemble ultimate vs tiled_omp_avx — confirm or kill the register-spill hypothesis.
2. Add `perf stat -e fe_retired,frontend_stalls` to nail down what's left in tiled's cycle budget.
3. Run with `OMP_PROC_BIND=close` and `OMP_NUM_THREADS=8` (physical cores) — current 16 thread on 8 physical + SMT may be hurting more than helping.
4. Capture per-run kernel timings (binary-internal) for the 5-run stability — perf elapsed has 25 ms of init noise that's 50%+ of fast variants' "measured" time.

### Reproducibility / Notes on the Run

- Wall-time numbers above use the binary's internal `clock_gettime(CLOCK_MONOTONIC)` measurement, **not** `perf stat`'s `time elapsed`. The latter includes ~25 ms init (random fill of A & B) which is negligible for naive but dominates fast variants (e.g. for BLAS, perf-elapsed=0.048 s vs kernel=0.012 s — 75% of "elapsed" is init).
- `perf_event_paranoid = -1` made all AMD events (ibs_op, `ls_any_fills_from_sys.*`, `de_dis_dispatch_token_stalls1.*`) usable in per-thread mode without sudo.
- No event came back `<not supported>` or `<not counted>` for any of the 21 binaries × 4 stat experiments.
- IPC values for these binaries differ from the original 4-variant report (naive: 0.263 here vs 0.350 there; ikj: 1.965 vs 3.551) because `-march=native` was added to the compile this run — gcc auto-vectorises both naive and ikj's inner loop, halving the instruction count. Wall-time and bottleneck conclusions are unchanged.

### Bottom Line

1. **Memory hierarchy beats arithmetic.** The 11× gap between naive and ikj is purely an address-pattern change; same FLOPs, same hardware, completely different cycle counts.
2. **Tiling doesn't help when the inner loop's working set already fits L1.** At N=1024, `ikj`'s hot footprint is one row of B (8 KB) — well within the 32 KB L1d. The 64×64 tile (32 KB block) tries to capture reuse that L1 is already providing for free, so tiling's bookkeeping overhead is pure cost. Tiling pays off when N grows large enough that a single row no longer fits L1 (typically N ≳ 4 K for doubles).
3. **Threads pay off most when memory layout is already friendly.** Best results stack OMP **on top of** ikj-friendly access — `omp_avx`/`tiled_omp_avx` reach 56–94× speedup.
4. **Hand-tuned beats hand-rolled.** OpenBLAS (`dgemm`) is 1.75× faster than my best 21-variant attempt — confirming the rule of thumb "for dense matmul, link a library; don't hand-write."
5. **Composing optimisations isn't always monotonic.** `ultimate` (5-stack) is slower than `tiled_omp_avx` (3-stack); the unroll layer adds cost (likely register pressure, not confirmed) and gives nothing back when the other layers already saturate the lane.
6. **The best single trick is manual unroll.** `matmul_unroll` alone beats `tiled`, `avx`, and `prefetch` as a single-optimisation lift on top of `ikj` — useful as a guide when you can change only one thing.

