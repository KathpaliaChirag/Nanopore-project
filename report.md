# Report — Executed Work Log

This file tracks everything actually run, tested, or completed.
Each entry comes from the plan and represents something done, not just planned.

---

## Phase 1 — Dorado GPU Profiling (Nsight Systems)

**Date:** 2026-05-21
**Tool:** nsys 2026.2.1 (run with sudo — required due to Dorado's bundled CUDA runtime)
**Input:** `FBE01990_24778b97_03e50f91_10.pod5`
**Model:** `dna_r10.4.1_e8.2_400bps_fast@v5.2.0`
**GPU:** NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
**Command:**
```bash
sudo nsys profile --output ~/results/nsight/dorado_fast_profile \
  --trace cuda --stats true --resolve-symbols=false --force-overwrite true \
  -- ~/dorado/dorado-1.4.0-linux-x64/bin/dorado basecaller \
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

**Dorado is compute-bound.**

- GPU time is dominated by neural network inference: LSTM layers + Tensor Core GEMM + beam search = ~76% of total GPU time
- Memory transfers are large and efficient — HtoD/DtoH is not a bottleneck
- CPU is spending 98.4% of its CUDA API time waiting on the GPU (`cudaStreamSynchronize`), meaning the GPU is the bottleneck, not the CPU pipeline

**Implication for cache:** A signal-to-base cache would not significantly speed up Dorado. The GPU is already running at capacity doing neural net inference. Speedup requires algorithmic changes (smaller model, quantization, or faster decoding) — not caching.

---

### Setup Note

nsys cannot intercept Dorado's CUDA runtime without `sudo`. Dorado bundles its own private `libcudart.so.12` in `dorado/lib/`, which ignores nsys's standard `CUDA_INJECTION64_PATH` injection. Running as root bypasses this restriction. All future nsys runs on Dorado require `sudo`.

---
