# Luna — Dorado GPU Profiling Results

> Server: luna (dell-R760) | GPU: 2× NVIDIA L40S (46 GB VRAM each)
> CUDA: 12.9 | Driver: 575.64.03
> L40S is Ada Lovelace — newer than Minerva's A40 (Ampere), ~2.5× more FP32 throughput

---

## Minerva Baselines (A40, for comparison)

| Metric | Minerva (A40) | Notes |
|---|---|---|
| Top kernel | GEMM | |
| GEMM % of GPU time | 82% (WSL2 GTX 1650) | fill in from Minerva run |
| cudaStreamSynchronize % | 98.9% CUDA API time | |
| L40S vs A40 FP32 | ~91.6 vs ~37.4 TFLOPS | L40S ≈ 2.5× faster |

---

## nsys — GPU Timeline (fast model)

**Command:**
```bash
nsys profile --output ~/results/dorado_luna_fast \
  --trace cuda,nvtx --stats true \
  -- $DORADO basecaller fast $POD5 \
  --output-dir ~/results/bam_luna_fast
```

**Output:**
```
[paste nsys stats output here]
```

| Metric | Minerva A40 | **Luna L40S** |
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

**Top kernel identified:**

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

| Metric | GPU 0 | GPU 1 |
|---|---|---|
| Peak power draw (W) | | (cap: 350W) |
| Average power draw (W) | | |
| Peak temperature (°C) | | |
| Throttling detected | | |
| Memory bandwidth (GB/s) | | |

---

## fast vs hac Comparison

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
