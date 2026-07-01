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
| Kraken2 50 MB wall time | 4.405s (reads_hac, 32T) | ??? | ??? |
| Kraken2 103 GB wall time | ??? (not measured for single) | ??? | ??? |
| Kraken2 LLC miss rate (50 MB) | 14.64% | ??? | — |
| Kraken2 LLC miss rate (103 GB) | ??? | ??? | — |

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

## Kraken2 Results — Merged Dataset

### Fast Model

**50 MB DB (sample_targeted):**

| Metric | Value |
|---|---|
| Wall time | ??? |
| LLC-loads | ??? |
| LLC-load-misses | ??? |
| LLC miss rate | ??? |
| Instructions | ??? |
| Cycles | ??? |
| IPC | ??? |

**8 GB DB (standard_8gb):**

| Metric | Value |
|---|---|
| Wall time | ??? |
| LLC-loads | ??? |
| LLC-load-misses | ??? |
| LLC miss rate | ??? |
| Instructions | ??? |
| Cycles | ??? |
| IPC | ??? |

---

### HAC Model

**50 MB DB (sample_targeted):**

| Metric | Value |
|---|---|
| Wall time | ??? |
| LLC-loads | ??? |
| LLC-load-misses | ??? |
| LLC miss rate | ??? |
| Instructions | ??? |
| Cycles | ??? |
| IPC | ??? |

**8 GB DB (standard_8gb):**

| Metric | Value |
|---|---|
| Wall time | ??? |
| LLC-loads | ??? |
| LLC-load-misses | ??? |
| LLC miss rate | ??? |
| Instructions | ??? |
| Cycles | ??? |
| IPC | ??? |

---

### SUP Model

**50 MB DB (sample_targeted):**

| Metric | Value |
|---|---|
| Wall time | ??? |
| LLC-loads | ??? |
| LLC-load-misses | ??? |
| LLC miss rate | ??? |
| Instructions | ??? |
| Cycles | ??? |
| IPC | ??? |

**8 GB DB (standard_8gb):**

| Metric | Value |
|---|---|
| Wall time | ??? |
| LLC-loads | ??? |
| LLC-load-misses | ??? |
| LLC miss rate | ??? |
| Instructions | ??? |
| Cycles | ??? |
| IPC | ??? |

---

## Notes

- Space rule enforced: only one FASTQ on disk at a time; each deleted before next model basecalls.
- nsys .nsys-rep binaries not transferred (large); only *_stats.txt extracted.
- SUP basecalling expected ~80 min for 1.87M reads.
