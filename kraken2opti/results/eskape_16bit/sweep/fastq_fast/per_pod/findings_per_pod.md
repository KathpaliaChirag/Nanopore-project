# `fastq_fast` per-pod breakdown — pod5_0 … pod5_15

**Date:** 2026-06-30 · Each of the 16 per-pod5 fast fastq (`results/fast1/pod5_N.fastq`) classified
**individually** against `eskape_{16,24,32}bit` at `-T 0` and `-T 0.05` (16 × 3 × 2 = 96 runs).
Total reads across pods = 1,872,777 (matches the combined run).

## Classified % per pod, all 3 widths

| pod | reads | 32 T0 | 24 T0 | 16 T0 | 32 T0.05 | 24 T0.05 | 16 T0.05 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pod0 | 132,074 | 73.18 | 73.46 | 89.28 | 61.84 | 61.84 | 62.16 |
| pod1 | 141,195 | 73.27 | 73.55 | 89.74 | 61.69 | 61.70 | 61.99 |
| pod2 | 151,591 | 73.49 | 73.80 | 90.16 | 61.65 | 61.65 | 61.96 |
| pod3 | 141,365 | 73.36 | 73.68 | 90.09 | 60.86 | 60.86 | 61.22 |
| pod4 | 131,822 | 73.10 | 73.41 | 90.21 | 60.57 | 60.57 | 60.89 |
| pod5 | 130,448 | 72.94 | 73.22 | 90.04 | 60.60 | 60.60 | 60.95 |
| pod6 | 120,965 | 73.22 | 73.54 | 90.35 | 60.82 | 60.82 | 61.17 |
| pod7 | 119,216 | 73.36 | 73.67 | 90.36 | 61.17 | 61.17 | 61.54 |
| pod8 | 122,764 | 73.46 | 73.77 | 90.34 | 60.93 | 60.93 | 61.27 |
| pod9 | 109,728 | 73.29 | 73.59 | 90.12 | 61.82 | 61.82 | 62.10 |
| pod10 | 104,918 | 73.10 | 73.43 | 90.39 | 61.47 | 61.48 | 61.76 |
| pod11 | 123,458 | 72.53 | 72.81 | 89.77 | 60.73 | 60.73 | 61.04 |
| pod12 | 109,020 | 72.71 | 73.00 | 89.61 | 61.01 | 61.01 | 61.38 |
| pod13 | 106,781 | 72.88 | 73.13 | 89.62 | 61.81 | 61.81 | 62.10 |
| pod14 | 97,054 | 72.08 | 72.34 | 89.15 | 61.07 | 61.07 | 61.41 |
| pod15 | 30,378 | 72.79 | 73.06 | 90.09 | 61.60 | 61.60 | 61.88 |

## Pattern (identical in every pod)

- **24-bit vs 32-bit:** +0.25–0.31 pp at `-T 0`; **±0.01 pp** at `-T 0.05` (drop-in everywhere).
- **16-bit vs 32-bit:** +16–17 pp at `-T 0` (collision FP, every pod); **+0.3–0.4 pp** at `-T 0.05`.
- Pod-to-pod spread is tiny (32-bit `-T 0.05` ranges 60.57–61.84%) — the dataset is homogeneous;
  the cell-width effect dominates the pod-to-pod effect.

**Conclusion:** the aggregate verdict reproduces per-pod — 24-bit is a drop-in for 32-bit, 16-bit
needs `-T ≥ 0.05`. No pod behaves differently.

## Artifacts (this folder)
- `report_pod{0..15}_{16,24,32}bit_T{0,0.05}.txt` — 96 Kraken reports
- `per_pod_summary.tsv` — classified/unclassified % per pod/width/threshold (table above)
- `per_pod_species.tsv` — per-pathogen counts (287/573/550/470/1280/1352 + unclassified) per run
- `stderr_*.txt` — raw classify output per run
