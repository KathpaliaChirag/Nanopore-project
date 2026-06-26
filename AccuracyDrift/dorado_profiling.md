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

## Baseline Wall Times (no profiler overhead)

| Model | Wall time | Dorado internal (ms) | Reads | Throughput (samples/s) | Batch size | Chunk size |
|---|---|---|---|---|---|---|
| fast | 33.9s | 21,612 | 104,478 | 2.35 × 10⁸ | 320 | 9,996 |
| hac  | 55.0s | 24,945 | 104,476 | 2.03 × 10⁸ | 2,944 | 9,996 |
| sup  | 4m 26s | 256,570 | 104,478 | 1.98 × 10⁷ | 96 | 12,288 |

**Key observations:**
- fast → hac: 1.6× slower wall time, throughput barely drops (2.35 → 2.03 × 10⁸ samples/s)
- hac → sup: **10× throughput drop** (2.03 × 10⁸ → 1.98 × 10⁷). Batch size collapses from 2,944 → 96 — sup model is far larger, VRAM-per-batch is the bottleneck.
- Both GPUs used (cuda:0 + cuda:1) across all three models.

---

## GPU Kernel Profiling (ncu)

> ncu re-runs each kernel to collect hardware counters — runs will be much slower than baseline.

**Command (fast model):**
```bash
ncu --set basic -o ~/results/ncu_luna_fast \
  ~/tools/dorado/bin/dorado basecaller fast \
  ~/data/pod5/fbe/FBE01990_24778b97_03e50f91_10.pod5 \
  --output-dir ~/results/bam_ncu_fast 2>&1 | head -100
```

| Metric | fast | hac | sup |
|---|---|---|---|
| Top kernel | | | |
| GEMM % of GPU time | | | |
| SM throughput % | | | |
| DRAM throughput % | | | |
| cudaStreamSynchronize % | | | |

---

## Cross-Machine Comparison

| Metric | WSL2 GTX 1650 | Luna L40S fast | Luna L40S hac | Luna L40S sup |
|---|---|---|---|---|
| Wall time | — | 33.9s | 55.0s | 4m 26s |
| Throughput (samples/s) | — | 2.35 × 10⁸ | 2.03 × 10⁸ | 1.98 × 10⁷ |
| GEMM % of GPU time | 82% | | | |
| cudaStreamSynchronize % | 98.9% | | | |
| Architecture | Turing | Ada Lovelace | Ada Lovelace | Ada Lovelace |
| FP32 TFLOPS | ~2.9 | ~91.6 | ~91.6 | ~91.6 |
