# Minerva — Dorado GPU Profiling Results

> Server: minerva | GPU: 2× NVIDIA A40 (45 GB VRAM each) | CUDA: 12.9 | Driver: 575.64.03
> Dorado: 1.4.0 | Model: fast + hac comparison
> Pod5 file: [fill in path]

WSL2 baselines: 82% GEMM, `cudaStreamSynchronize` = 98.9% of CUDA API time (GTX 1650).

**Prerequisite check:** confirm pod5 file path on Minerva before running.

---

## 4.2 nsys — GPU Timeline (fast model)

**Command run:**
```bash
nsys profile --output ~/results/dorado_fast_profile --trace cuda,nvtx --stats true \
  -- $DORADO basecaller fast $POD5 --output-dir ~/results/bam_fast
```

**Stats output:**
```
[paste nsys stats output here]
```

| Metric | WSL2 (GTX 1650) | Minerva (A40) |
|---|---|---|
| Total runtime | | |
| Top kernel | GEMM | |
| GEMM % of GPU time | 82% | |
| cudaStreamSynchronize % | 98.9% | |
| H2D transfer % | | |
| D2H transfer % | | |

---

## 4.3 ncu — Per-Kernel Metrics on A40

**Command run:**
```bash
ncu --metrics sm__throughput...,dram__throughput...,sm__warps_active... \
  --output ~/results/ncu_report \
  -- $DORADO basecaller fast $POD5 --output-dir ~/results/bam_ncu
```

**Top kernel identified from nsys:** _______________

**ncu output for top kernel:**
```
[paste ncu report here]
```

| Metric | Value | Meaning |
|---|---|---|
| SM throughput % | | >70% = compute-bound |
| DRAM throughput % | | Low while SM high = good |
| Warp occupancy % | | Higher on A40 expected |

---

## 4.4 DCGM — Power + Thermal During Run

**Output:**
```
[paste dcgmi stats JSON here]
```

| Metric | GPU 0 | GPU 1 |
|---|---|---|
| Peak power draw (W) | | |
| Average power draw (W) | | |
| Peak temperature (°C) | | |
| Throttling detected | | |
| Memory bandwidth (GB/s) | | |

---

## 4.5 fast vs hac Comparison (nsys)

**hac model stats:**
```
[paste nsys stats for hac run here]
```

| Metric | fast | hac |
|---|---|---|
| Total runtime | | |
| GEMM % of GPU time | | |
| Top kernel | | |
| SM throughput % (ncu) | | |

**Conclusion:** Same GEMM bottleneck? Yes / No — [fill in]

---

## Summary

| Tool | Key Finding |
|---|---|
| nsys (fast) | |
| ncu (fast) | |
| DCGM | |
| nsys fast vs hac | |
