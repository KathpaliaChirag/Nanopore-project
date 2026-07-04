# Orion — NVIDIA Jetson AGX Orin 64GB

## SSH

```
ssh jetsonagx@10.154.233.173
```

On IITD campus network only (WiFi module, no external access).

## Hardware

| Component | Spec |
|-----------|------|
| Machine | NVIDIA Jetson AGX Orin 64GB |
| OS | Ubuntu 20.04.6 LTS |
| JetPack | R35.4.1 (released Aug 2023) |
| Kernel | 5.10.120-tegra (aarch64) |
| CPU | 12-core ARM Cortex-A78AE, 3 clusters × 4 cores, no hyperthreading |
| SLC (L3) | 4 MB System Level Cache (shared across all 12 cores) |
| RAM | 64 GB LPDDR5 unified memory (CPU + GPU share same pool) |
| GPU | Ampere, 2048 CUDA cores (shares unified memory) |
| Storage | 57 GB eMMC |
| Architecture | ARM64 (aarch64) |

## Storage Status (as of 2026-06-12)

Total: 57 GB eMMC — 46 GB used (85%), 8.5 GB free.

Top space consumers in home:

| Path | Size |
|------|------|
| dorado-0.5.3-linux-arm64 | 3.7 GB |
| internal_tools | 2.0 GB |
| Desktop | 1.2 GB |
| jetson-inference | 952 MB |
| Downloads | 606 MB |
| Documents | 424 MB |

Remaining ~37 GB is system: CUDA toolkit, JetPack libraries, Ubuntu base — cannot be safely removed.

## AccuracyDrift Notes

**All DBs are post-cliff on Orion.** The SLC is 4 MB. Every AccuracyDrift database is far larger than 4 MB — even the smallest (sample_targeted at 50 MB) is 12.5x the SLC size. This means Orion operates entirely in the DRAM-dominated regime for all databases. There is no "pre-cliff" comparison available on this machine. LLC miss rates cluster at 68–84% across all DBs and all thread counts. See RESULTS.md section 1.4 for full data.

**perf events on ARM.** Verified on this kernel (5.10.120-tegra, 5.4 perf binary):

- `LLC-loads`, `LLC-load-misses` — available and working (use these for LLC miss rate)
- `cache-references` — maps to L1D/L2 accesses on this ARM, NOT LLC; values (~47B per run) are not comparable to Luna's cache-references (~LLC-level). Cache Miss Rate% column on Orion is therefore not comparable to Luna.

The consistent cross-machine metric is: LLC-load-misses / LLC-loads (LLC Miss Rate%).

The Cortex-A78 SLC is a system-level cache. A miss goes to the same LPDDR5 pool the GPU uses (unified memory).

**Thread count ceiling.** 12 cores, no hyperthreading. Thread counts tested: 1, 2, 4, 6, 8, 10, 12. No point going beyond 12T.

**DB size constraint (as of 2026-06-12).** Only 8.5 GB free. All 5 AccuracyDrift databases fit because the largest (standard_16gb, 15 GB) was transferred after clearing space. PlusPF (103 GB) cannot run on Orion — 64 GB RAM is insufficient to hold the DB in memory.

**Kraken2 install.** Installed at `~/tools/kraken2/kraken2` (version 2.1.3). Must use explicit path when running under sudo because sudo strips PATH.

```bash
~/tools/kraken2/kraken2 --version
```

## tegrastats Reference

`tegrastats` output fields explained:

- `RAM 2079/62802MB` — RAM used / total (OS view)
- `lfb 14293x4MB` — largest free block: 14293 contiguous 4 MB pages available
- `CPU [0%@729, ...]` — per-core utilization % @ current frequency in MHz
- `EMC_FREQ 0%` — external memory controller (LPDDR5) utilization
- `GR3D_FREQ 0%` — GPU utilization
- `CPU@40C` — CPU cluster temperature
- `GPU@-256C` — GPU sensor offline (GPU powered down at idle, normal)
- `Tboard@29C` — board temperature
- `tj@40C` — junction temperature (thermal throttle reference point)
