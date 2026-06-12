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

**perf events differ on ARM.** The standard x86 event names do not exist here:

- `LLC-loads`, `LLC-load-misses` — not available
- `cache-misses`, `cache-references` — may map to L2 or L3 depending on kernel

Run this on Orion before starting experiments to see what cache events are actually available:

```bash
perf list | grep -i cache
perf list | grep -i LLC
```

The Cortex-A78 has an L3 cache (system-level cache, SLC). The unified memory architecture means LLC miss behavior is conceptually different — a miss goes to the same LPDDR5 pool the GPU uses.

**DB size constraint.** Only 8.5 GB free currently. standard_16gb (15 GB) will not fit without clearing space first. Candidate: delete `dorado-0.5.3-linux-arm64` (3.7 GB) if not needed, freeing ~12 GB — enough for standard_8gb but still not standard_16gb. Confirm with Kolin sir before deleting anything.

**Thread count ceiling.** 12 cores, no hyperthreading. Thread counts to test: 1, 2, 4, 8, 12. No point going beyond 12T.

**Kraken2 install.** Not yet installed. ARM64 binary is available — build from source or check if a pre-built arm64 binary exists.

```bash
# Check if installed
which kraken2

# Build from source if not
sudo apt install git wget
git clone https://github.com/DerrickWood/kraken2.git
cd kraken2
./install_kraken2.sh ~/kraken2-bin
echo 'export PATH=$PATH:~/kraken2-bin' >> ~/.bashrc
source ~/.bashrc
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
