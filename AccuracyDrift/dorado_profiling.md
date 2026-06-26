# Dorado GPU Profiling — Luna L40S

> Machine: Luna (dell-R760) | GPU: 2× NVIDIA L40S (46 GB each, Ada Lovelace) | CUDA 12.9
> Dorado: ~/tools/dorado/bin/dorado v1.4.0+ba44a013
> Input: ~/data/pod5/fbe/FBE01990_24778b97_03e50f91_10.pod5
> Date: 2026-06-27

---

## Setup

| Item | Value |
|---|---|
| nsys | `/usr/lib/nsight-systems/bin/nsys` v2021.3.3.2 — **broken on L40S** (GLIBC_PRIVATE symbol error) |
| nvprof | `/usr/bin/nvprof` v11.5 — **rejected at runtime** (compute capability ≥ 8.0 unsupported) |
| ncu | `/usr/bin/ncu` v2021.3.1 — viable for per-kernel metrics |
| dorado path | `~/tools/dorado/bin/dorado` v1.4.0+ba44a013 |
| pod5 input | `~/data/pod5/fbe/FBE01990_24778b97_03e50f91_10.pod5` |
| models | dna_r10.4.1_e8.2_400bps_{fast,hac,sup}@v5.2.0 |

---

## Baseline Wall Times — GPU vs CPU

| Model | GPU wall time | GPU throughput (samples/s) | CPU wall time | CPU throughput (samples/s) | GPU speedup | CPU RAM |
|---|---|---|---|---|---|---|
| fast | 33.9s | 2.35 × 10⁸ | 9m 40s (616,959 ms) | 8.23 × 10⁶ | **28.6×** | 47 GB |
| hac  | 55.0s | 2.03 × 10⁸ | 43m 26s (2,694,842 ms) | 1.88 × 10⁶ | **107×** | |
| sup  | 4m 26s | 1.98 × 10⁷ | running (~8h est.) | | | |

> GPU runs: 2× L40S (cuda:0 + cuda:1). CPU runs: 650 threads, ~130 cores active.

**GPU batch sizes:** fast=320, hac=2,944, sup=96 (VRAM-limited)

> **Why SUP CPU is so slow:** The SUP model uses FP8 precision (`fp8_e4m3`) on GPU — a data type natively accelerated by Ada Lovelace tensor cores. No CPU architecture currently supports native FP8 arithmetic (Intel Xeon Platinum 8468 has AMX for BF16/INT8 but not FP8). On CPU, dorado falls back to FP32 for all FP8 ops, increasing both compute cost and memory bandwidth. The fused GPU kernels (e.g. `mm_swiglu<fp8>` = matmul + SwiGLU in one pass) also break into separate CPU ops, adding overhead. Result: the SUP GPU→CPU penalty is expected to be far worse than fast (28.6×) or hac (107×).

---

## GPU Kernel Profiling (nsys 2025.1.3)

> nsys installed via apt (cuda-nsight-systems-12-9). Path: `/opt/nvidia/nsight-systems/2025.1.3/`.
> Command used: `nsys profile -o <out> -t cuda,nvtx --stats=true <dorado cmd>`

---

### Fast Model — nsys Profile

**NVTX pipeline breakdown (% of total annotated time):**

| Stage | % Time | Notes |
|---|---|---|
| basecall_current_batch | 36.6% | outer batch loop |
| call_chunks | 36.3% | chunk inference |
| cuda_thread_fn (GPU 0+1) | ~20.4% | per-device CUDA threads |
| cpu_decode | 2.4% | CTC decode on CPU |
| nn_forward | 1.3% | neural net forward pass |

**CUDA API breakdown:**

| API call | % of CUDA API time | Calls |
|---|---|---|
| cudaStreamSynchronize | **63.1%** | 4,367 |
| cudaEventSynchronize | 33.4% | 640 |
| cudaMalloc | 1.4% | 387 |
| cudaLaunchKernel | 0.7% | 54,924 |
| **Total blocking sync** | **96.5%** | — |

**GPU kernel breakdown (% of total GPU time):**

| Kernel | % GPU time | Notes |
|---|---|---|
| `ampere_h16816gemm_128x64_ldg8_nn` | **24.8%** | GEMM (cuBLAS, FP16) |
| `lstm<int8, 96, fwd>` | 16.5% | LSTM forward |
| `beam_search_step` | 14.8% | CTC beam search |
| `lstm<int8, 96, bwd>` | 11.0% | LSTM backward/second direction |
| `ampere_h1688gemm_256x64_ldg8_nn` | **6.0%** | GEMM (cuBLAS, FP16) |
| `decode_step` | 5.6% | |
| `convolution_ntc` | 5.6% | |
| `window_ntwc_f16` | 5.3% | |
| `compute_posts_step` | 4.7% | |
| `back_guide_step` | 2.4% | |
| **Total GEMM** | **~30.8%** | vs 82% on WSL2 GTX 1650 |
| **Total LSTM** | **~27.5%** | dominant on L40S |

**Memory transfers:**

| Operation | % of transfer time | Total data |
|---|---|---|
| Host → Device | 77.5% | 11,440 MB |
| Device → Host | 15.7% | 2,859 MB |
| Device → Device | 6.9% | 22,860 MB |

---

### HAC Model — nsys Profile

**CUDA API breakdown:**

| API call | % of CUDA API time | Calls |
|---|---|---|
| cudaStreamSynchronize | **51.2%** | 2,196 |
| cudaEventSynchronize | 44.9% | 640 |
| **Total blocking sync** | **96.1%** | — |

**GPU kernel breakdown (% of total GPU time):**

| Kernel | % GPU time | Notes |
|---|---|---|
| `vcs_lstm<8>` | **46.4%** | custom vectorized LSTM (large variant) |
| `vcs_lstm<4>` | **15.9%** | custom vectorized LSTM (medium) |
| `cutlass::Kernel<LinearLayer MmaMultistage>` | **11.2%** | GEMM (CUTLASS linear layer) |
| `compute_posts_step` | 4.7% | |
| `back_guide_step` | 4.4% | |
| `cutlass::Kernel<LstmKernel>` | 3.9% | LSTM via CUTLASS |
| `cutlass::Kernel<LinearLayer MmaPipelined>` | **3.8%** | GEMM (CUTLASS) |
| `convolution_tc` | 3.0% | |
| `beam_search_step` | 2.1% | |
| `vcs_lstm<16>` | 1.8% | custom vectorized LSTM (small) |
| **Total GEMM** | **~15.0%** | down from 30.8% in fast |
| **Total LSTM** | **~68.0%** | up from 27.5% in fast |

---

### SUP Model — nsys Profile

> SUP uses a **Transformer architecture** (not LSTM), with FP8 precision — fundamentally different from fast/hac.

**CUDA API breakdown:**

| API call | % of CUDA API time | Calls |
|---|---|---|
| cudaStreamSynchronize | **97.3%** | 15,517 |
| cudaEventSynchronize | 1.4% | 128 |
| **Total blocking sync** | **~98.7%** | — |

**GPU kernel breakdown (% of total GPU time):**

| Kernel | % GPU time | Notes |
|---|---|---|
| `tiled_residual_rmsnorm` | **17.1%** | Transformer RMSNorm — runs between every layer |
| `mm_swiglu<fp8_e4m3>` | **15.1%** | FP8 FFN linear + SwiGLU fused |
| `attention<256>` | **10.4%** | Self-attention |
| `qkv_rotary<fp8_e4m3>` | **9.4%** | FP8 QKV projection + rotary embeddings |
| `mm_kernel<fp8_e4m3>` (large) | **8.9%** | FP8 output projection |
| `beam_search_step` | 8.5%  | CTC beam search (much larger than hac) |
| `ampere_fp16_s1688gemm_128x128_tn` | 5.2% | FP16 GEMM |
| `mm_kernel<fp16>` | 5.0% | FP16 linear |
| `compute_posts_step` | 4.8% | |
| `back_guide_step` | 3.1% | |
| `decode_step` | 2.9% | |
| `cudnn fp16 conv` | 1.6% | cuDNN convolution |
| `silu_kernel` | 1.2% | SwiGLU activation |
| **Total GEMM (FP8 + FP16)** | **~43.6%** | incl. attention QKV projections |
| **Total Transformer ops** | **~71%** | GEMM + attention + RMSNorm |
| **Total LSTM** | **0%** | no LSTM kernels at all |

---

## Cross-Machine Comparison

| Metric | WSL2 GTX 1650 | Luna L40S fast | Luna L40S hac | Luna L40S sup |
|---|---|---|---|---|
| Wall time | — | 33.9s | 55.0s | 4m 26s |
| Throughput (samples/s) | — | 2.35 × 10⁸ | 2.03 × 10⁸ | 1.98 × 10⁷ |
| Model architecture | RNN (GRU) | LSTM | LSTM | **Transformer** |
| Precision | FP16 | FP16 | FP16 | **FP8 + FP16** |
| GEMM % of GPU time | 82% | **30.8%** | **~15.0%** | **~43.6%** |
| LSTM % of GPU time | — | **27.5%** | **~68.0%** | **0%** |
| Attention % | — | 0% | 0% | **10.4%** |
| RMSNorm % | — | 0% | 0% | **17.1%** |
| Beam search % | — | 14.8% | 2.1% | 8.5% |
| cudaStreamSynchronize % | 98.9% | **63.1%** | **51.2%** | **97.3%** |
| Total blocking sync % | — | **96.5%** | **96.1%** | **~98.7%** |
| Architecture | Turing | Ada Lovelace | Ada Lovelace | Ada Lovelace |
| FP32 TFLOPS | ~2.9 | ~91.6 | ~91.6 | ~91.6 |

**Key insights:**
- **fast (L40S):** GEMM drops from 82% (GTX 1650) to 30.8% — L40S finishes matrix ops 31× faster, exposing LSTM and beam search.
- **hac (L40S):** Larger LSTM network (`vcs_lstm` custom kernels). LSTM explodes to 68%, GEMM halves to 15%. Almost entirely LSTM-bound.
- **sup (L40S):** Completely different architecture — a **Transformer** with FP8 precision. No LSTM at all. RMSNorm (17.1%), FP8 GEMMs (43.6%), self-attention (10.4%). Batch size collapses to 96 due to model size. cudaStreamSynchronize returns to 97.3% — CPU is almost always blocked.
- **Total blocking sync stays ~96-98%** across all models — the pipeline is always CPU-blocked on GPU regardless of model complexity.
