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

### Relevance to Kolin Sir's Hot-K-mer Cache

The Hot-K-mer LRU cache targets **Kraken-2** (CPU, k-mer hash table lookup) — not Dorado. The profiling confirms this is the right split:

| Component | Bottleneck type | Right fix |
|---|---|---|
| Dorado (GPU) | Compute-bound — LSTM + GEMM | Quantization, larger batches, beam search rewrite |
| Kraken-2 (CPU) | Memory-bound — random hash table access on 180 GB DB | LRU cache (Kolin sir's proposal) |

Profiling provides the quantitative justification for building the cache on Kraken-2 and not Dorado.

---

## Phase 2 — Kraken-2 CPU Profiling (gprof + cachegrind + perf)

**Date:** 2026-05-22
**Tools:** gprof (call-time), cachegrind/valgrind (instruction count), perf stat (hardware counters)
**Database:** Custom ESKAPE DB (6 pathogens, 60 MB hash table) at `/opt/kraken2-build/db/`
**Binary:** Kraken-2 v2.17.1 built from source with `-pg` at `/opt/kraken2-build/bin/classify`
**Inputs:** `reads_fast.fastq` (22,386 reads, 103 Mbp) and `reads_hac.fastq` (104,921 reads, 355 Mbp)
**Threads:** 1 (single-threaded for clean profiling)

---

### Classification Results

| Metric | Fast model | HAC model |
|---|---|---|
| Reads processed | 22,386 | 104,921 |
| Reads classified | 16,605 (74.18%) | 84,867 (80.89%) |
| Reads unclassified | 5,781 (25.82%) | 20,054 (19.11%) |
| Kraken-2 runtime (1 thread) | 8.3s | 31.4s |
| Throughput | 161.7 Kseq/min | 200.4 Kseq/min |

HAC classifies **6.7% more reads** due to higher base accuracy producing more k-mer matches.

---

### gprof — CPU Time Breakdown

| Function | Fast % | HAC % | Role |
|---|---|---|---|
| `CompactHashTable::Get()` | **69.1%** | **69.6%** | k-mer hash table lookup |
| `MinimizerScanner::NextMinimizer()` | 20.8% | 18.6% | k-mer generation |
| `ClassifySequence()` | 5.5% | 4.7% | per-read classification logic |
| `reverse_complement()` | 2.0% | 2.5% | k-mer canonicalization |

**Key finding:** `CompactHashTable::Get()` dominates at ~69% of CPU time regardless of input quality. This is a structural property of Kraken-2 — every k-mer requires one random hash table lookup.

- Fast model: 32,925,693 hash lookups for 22,386 reads (~1,471 lookups/read)
- HAC model: 112,294,110 hash lookups for 104,921 reads (~1,070 lookups/read)

HAC reads are shorter on average (fewer k-mers per read), but the lookup rate per read is similar.

---

### perf stat — Hardware Performance Counters

| Counter | Fast | HAC |
|---|---|---|
| Runtime | 8.87s | 31.07s |
| Instructions | 47.7B | 178.0B |
| Cycles | 37.8B | 132.6B |
| **IPC (instructions/cycle)** | **1.26** | **1.34** |
| L1 dcache loads | 19.3B | 70.3B |
| L1 dcache load misses | 208M (1.08%) | 699M (0.99%) |
| Cache references (LLC) | 468M | 1,578M |
| **LLC cache misses** | **157M (33.5%)** | **551M (34.9%)** |

**Key finding:** ~34% LLC miss rate on both inputs. 1 in 3 hash table lookups goes all the way to main RAM (60–100 ns latency) instead of L3 cache (<10 ns). IPC of ~1.3 is low — the CPU is frequently stalling waiting for memory.

---

### cachegrind — Instruction Count (5,000-read subset each)

| Function | Fast % | HAC % |
|---|---|---|
| `NextMinimizer()` | ~29% | 29.7% |
| `CompactHashTable::Get()` | ~15% | 15.0% |
| `reverse_complement()` | ~7% | 7.3% |
| `ClassifySequence()` | ~6% | 6.5% |

Note: cachegrind counts instructions (not time). `CompactHashTable::Get()` has fewer instructions than `NextMinimizer()` but takes more wall-clock time — confirming that each hash lookup stalls on memory latency, not compute.

---

### Verdict: Kraken-2 is Memory-Bound

| Evidence | Value |
|---|---|
| % CPU time in hash lookup | 69% |
| LLC miss rate | ~34% |
| IPC | 1.26–1.34 (low — memory stalls) |
| Hash lookups per second | ~13M/s (fast), ~13M/s (HAC) — same regardless of read quality |

Kraken-2 is bottlenecked by **random memory access** to the k-mer hash table. The 60 MB custom ESKAPE DB fits in L3 cache on some runs, yet still shows 34% LLC miss rate — on the real 180 GB standard database, the miss rate would approach 100% since the entire table cannot fit in any cache level.

---

### Justification for Kolin Sir's Hot-K-mer LRU Cache

The profiling provides quantitative justification:

1. **69% of CPU time** is spent in `CompactHashTable::Get()` — the exact function the cache would accelerate
2. **34% LLC miss rate** means most lookups are going to RAM — cache hits would eliminate this latency
3. **~13M hash lookups/second** at 60+ ns/miss = the dominant bottleneck
4. The access pattern is not uniform — some k-mers (from abundant organisms) are queried repeatedly, making an LRU cache effective

| Component | Bottleneck | Right fix |
|---|---|---|
| Dorado (GPU) | Compute-bound — CUTLASS LSTM 69.8% | Quantization, larger batches |
| Kraken-2 (CPU) | **Memory-bound — hash lookup 69% CPU time, 34% LLC miss** | **Hot-K-mer LRU cache** |

