# Merged Pod5 Full-Dataset Profiling — Luna

> Machine: Luna (dell-R760) | GPU: 2× NVIDIA L40S | Dorado v1.4.0 | Kraken2 32T + numactl node0
> Input: all 16 FBE pod5 files via directory (~/data/pod5/fbe/) — no merge needed, dorado reads directory natively
> Date: 2026-06-29/30
> Results path: ~/results/merged_pod5_profiling/

---

## Setup

| Item | Value |
|---|---|
| Pod5 files | ~/data/pod5/fbe/FBE01990_24778b97_03e50f91_{0..15}.pod5 (63 GB total) |
| Input method | Directory passed to dorado (pod5 merge skipped — v0.3.39 merge corrupted zstd blocks) |
| Total reads input | 1,872,777 (across 16 files) |
| Reads output | ~1,865,971 (25 corrupt reads in pod5_9 skipped; ~38 filtered low-quality) |
| Dorado | ~/tools/dorado/bin/dorado v1.4.0, --emit-fastq |
| Kraken2 | ~/tools/kraken2/kraken2, 32T, numactl --cpunodebind=0 --membind=0 |
| Databases | sample_targeted (50 MB), pluspf_103gb (103.4 GB) |

**Note on pod5_9 corruption:** 25 reads across FBE01990_24778b97_03e50f91_9.pod5 fail with `Invalid: Input data not compressed by zstd` on every dorado run. Same read UUIDs fail consistently — pre-existing disk corruption in the original file. Negligible (0.001% of total reads).

---

## Dorado Basecalling — Wall Times

| Model | Wall time | Throughput (samples/s) | Reads basecalled | Reads filtered |
|---|---|---|---|---|
| fast | 5m 43.5s (343.5s) | 2.345×10⁸ | 1,865,971 | 38 |
| hac  | 6m 21.1s (381.1s) | 2.114×10⁸ | 1,865,971 | 37 |
| sup  | 67m 50.8s (4070.8s) | 1.979×10⁷ | 1,865,994 | 32 |

---

## Single-File vs Merged Comparison

| Metric | pod5_10 (single, 104,918 reads) | merged (all 16, ~1.87M reads) | Scaling factor |
|---|---|---|---|
| Dorado fast wall time | 33.9s | 343.5s | 10.1× |
| Dorado fast throughput (sp/s) | 2.35×10⁸ | 2.345×10⁸ | **~1.0× (identical)** |
| Dorado hac wall time | 55.0s | 381.1s | 6.9× |
| Dorado hac throughput (sp/s) | 2.03×10⁸ | 2.114×10⁸ | **~1.04× (identical)** |
| Dorado sup wall time | 4m 26s (266s) | 67m 50.8s (4070.8s) | 15.3× |
| Dorado sup throughput (sp/s) | 1.98×10⁷ | 1.979×10⁷ | **~1.0× (identical)** |
| Kraken2 50 MB wall time (hac) | 4.405s (reads_hac, 32T) | 11.10s | 2.52× |
| Kraken2 103 GB wall time (hac) | — (not measured) | 79.97s (warm) | — |
| Kraken2 LLC miss rate 50 MB (hac) | 14.64% | 13.11% | — |
| Kraken2 LLC miss rate 103 GB (hac) | — | 73.73% | — |

---

## Kraken2 Results — Merged Dataset (summary tables)

### 50 MB DB (sample_targeted)

| Model | Sequences | Wall time | LLC-loads | LLC-load-misses | LLC miss rate | IPC | Classified |
|---|---|---|---|---|---|---|---|
| fast | 1,871,478 | 11.11s | 2,712,407,985 | 341,782,868 | **12.60%** | 1.64 | 80.67% |
| hac  | 1,872,777 | 11.10s | 2,578,452,436 | 338,128,361 | **13.11%** | 1.74 | 84.73% |
| sup  | 1,873,441 | 12.18s | 2,546,667,455 | 312,169,296 | **12.26%** | 1.72 | 85.46% |

### 103 GB DB (pluspf_103gb)

| Model | Sequences | Wall time (warm) | LLC-loads | LLC-load-misses | LLC miss rate | IPC | Classified |
|---|---|---|---|---|---|---|---|
| fast | 1,871,478 | **89.24s** | 7,529,346,628 | 5,680,289,238 | **75.44%** | 0.79 | 96.53% |
| hac  | 1,872,777 | 79.97s    | 6,440,697,444 | 4,748,802,452 | **73.73%** | 0.94 | 98.83% |
| sup  | 1,873,441 | 77.31s    | 6,159,444,719 | 4,512,937,225 | **73.27%** | 0.98 | 99.32% |

fast × 103 GB run twice: cold (168.08s, 61.96% LLC miss rate — reflects sequential disk prefetch during page fault loading, not representative) and warm (89.24s, 75.44% — authoritative random-access number). hac/sup ran warm because fast had already loaded the DB into OS page cache.

**Key observations:**
- **50 MB DB:** LLC miss rate stable at 12–13% across all models — DB fits in effective LLC, classification rate increases with model accuracy (80.67% → 85.46%).
- **103 GB DB:** LLC miss rate jumps to 62–74%, IPC drops from ~1.7 to 0.78–0.98 — memory bandwidth wall. Classification near-complete (96.5–99.3%).
- **Wall time scaling (50 MB):** single-file hac was 4.405s for 104,918 reads; merged hac is 11.10s for 1,872,777 reads (17.85× more reads, only 2.52× more time) — 32-thread parallelism + warm DB cache.

---

## Dorado nsys Profiles — Merged Dataset

### Fast Model

**CUDA API breakdown:**

| API call | % of CUDA API time | Calls |
|---|---|---|
| cudaStreamSynchronize | ??? | ??? |
| cudaEventSynchronize | ??? | ??? |
| **Total blocking sync** | ??? | — |

**GPU kernel breakdown (% of total GPU time):**

| Kernel | % GPU time | Notes |
|---|---|---|
| ??? | ??? | |

---

### HAC Model

**CUDA API breakdown:**

| API call | % of CUDA API time | Calls |
|---|---|---|
| cudaStreamSynchronize | ??? | ??? |
| cudaEventSynchronize | ??? | ??? |
| **Total blocking sync** | ??? | — |

**GPU kernel breakdown (% of total GPU time):**

| Kernel | % GPU time | Notes |
|---|---|---|
| ??? | ??? | |

---

### SUP Model

**CUDA API breakdown:**

| API call | % of CUDA API time | Calls |
|---|---|---|
| cudaStreamSynchronize | ??? | ??? |
| cudaEventSynchronize | ??? | ??? |
| **Total blocking sync** | ??? | — |

**GPU kernel breakdown (% of total GPU time):**

| Kernel | % GPU time | Notes |
|---|---|---|
| ??? | ??? | |

---

## Notes

- All three FASTQs kept on disk simultaneously (~12 GB each, ~36 GB total) — space not a concern.
- pod5 merge (v0.3.39) corrupted zstd signal blocks; switched to dorado directory input instead.
- SUP basecalling took 67m 50s for 1.87M reads (vs ~80 min estimate for merged file).
- nsys profiles not run on merged dataset (single-file profiles already captured in dorado_profiling.md).
- 103 GB DB cold-load penalty: first run took 168s; subsequent runs ~78-80s (DB warm in OS page cache).
