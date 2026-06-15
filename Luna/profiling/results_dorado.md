# Luna — Dorado GPU Profiling Results

> **STATUS: DEPRIORITIZED as of Meeting 4 (2026-05-28).** Summer focus is Kraken2 optimisation only.
> Dorado/GPU work (Rohit + Rishabh SNN track) is a separate research thread, not part of CK's deliverables.
> This file is a template — no runs have been done on Luna. The sections below are placeholders.

> Server: luna (dell-R760) | GPU: 2× NVIDIA L40S (46 GB VRAM each)
> CUDA: 12.9 | Driver: 575.64.03 (from nvidia-smi; no Dorado runs done on Luna)
> L40S is Ada Lovelace — newer than Minerva's A40 (Ampere), ~2.5× more FP32 throughput
> Last updated: 2026-06-15

---

## WSL2 Baselines (GTX 1650, for comparison)

> Source: WSL2 GTX 1650 run (CK laptop). Minerva A40 Dorado profiling not yet done.

| Metric | WSL2 GTX 1650 | Minerva A40 (expected) | Notes |
|---|---|---|---|
| Top kernel | GEMM | | |
| GEMM % of GPU time | 82% | not yet measured | GTX 1650 run via Nsight Systems |
| cudaStreamSynchronize % | 98.9% CUDA API time | not yet measured | |
| FP32 throughput | ~2.9 TFLOPS | ~37.4 TFLOPS | L40S ≈ 91.6 TFLOPS (2.5× A40) |

---

## nsys — GPU Timeline (fast model)

**Command:**
```bash
nsys profile --output ~/results/dorado_luna_fast \
  --trace cuda,nvtx --stats true \
  -- $DORADO basecaller fast $POD5 \
  --output-dir ~/results/bam_luna_fast
```

**Output:** No runs completed — template only.

| Metric | WSL2 GTX 1650 | **Luna L40S** |
|---|---|---|
| Total runtime | | |
| Top kernel | GEMM | |
| GEMM % of GPU time | | |
| cudaStreamSynchronize % | | |
| H2D transfer % | | |
| D2H transfer % | | |

---

## ncu — Per-Kernel Metrics on L40S

**Command:**
```bash
ncu --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,\
dram__throughput.avg.pct_of_peak_sustained_elapsed,\
sm__warps_active.avg.pct_of_peak_sustained_active \
  --output ~/results/ncu_luna \
  -- $DORADO basecaller fast $POD5 \
  --output-dir ~/results/bam_ncu_luna
```

**Top kernel identified:** No runs completed — template only.

| Metric | Value | Meaning |
|---|---|---|
| SM throughput % | | >70% = compute-bound |
| DRAM throughput % | | |
| Warp occupancy % | | L40S has more SMs than A40 |

---

## DCGM — Power + Thermal During Run

**Command:**
```bash
dcgmi stats -e                              # enable stats collection
dcgmi stats -g 0 -s [jobid]               # start recording for GPU 0
# run dorado here
dcgmi stats -g 0 -x [jobid]               # stop and print
```

No runs completed — template only.

No runs completed — template only.

| Metric | GPU 0 | GPU 1 |
|---|---|---|
| Peak power draw (W) | | (cap: 350W) |
| Average power draw (W) | | |
| Peak temperature (°C) | | |
| Throttling detected | | |
| Memory bandwidth (GB/s) | | |

---

## fast vs hac Comparison

No runs completed — template only.

| Metric | fast | hac |
|---|---|---|
| Total runtime | | |
| GEMM % of GPU time | | |
| Top kernel | | |
| SM throughput % | | |

---

## Cross-Machine GPU Comparison

| Metric | WSL2 GTX 1650 | Minerva A40 | **Luna L40S** |
|---|---|---|---|
| FP32 TFLOPS | ~2.9 | ~37.4 | **~91.6** |
| VRAM | 4 GB | 45 GB | **46 GB** |
| GEMM % | 82% | | |
| Total fast runtime | | | |
| Architecture | Turing | Ampere | **Ada Lovelace** |
