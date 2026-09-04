# Minerva: Dorado GPU profiling results

Server: minerva | GPU: 2x NVIDIA A40 (45 GB VRAM each) | CUDA: 12.9 | Driver: 575.64.03
Dorado: 1.4.0 | Model: fast + hac comparison
Pod5 file: [fill in path]

> [!NOTE]
> Minerva AccuracyDrift runs have not started yet (disk was full as of 2026-05-28; verify disk status before starting, see Minerva/to_do_by_sudo.md Check 2).

WSL2 baselines: 82% GEMM, `cudaStreamSynchronize` = 98.9% of CUDA API time (GTX 1650).

**Prerequisite check:** confirm the pod5 file path on Minerva before running.

---

## 4.2 nsys: GPU timeline (fast model)

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

## 4.3 ncu: per-kernel metrics on the A40

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

## 4.4 DCGM: power + thermal during the run

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

## 4.5 fast vs. hac comparison (nsys)

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

**Conclusion:** same GEMM bottleneck? Yes / No, [fill in]

---

## Summary

| Tool | Key Finding |
|---|---|
| nsys (fast) | |
| ncu (fast) | |
| DCGM | |
| nsys fast vs hac | |
