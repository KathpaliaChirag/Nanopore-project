# Luna — Server Specifications & Diagnostics

> Last updated: 2026-05-28 (tool audit 22:19 UTC)
> Server name: luna (dell-R760) | hostname: `dell-R760`
> OS: Ubuntu 22.04 LTS | User seen: chayanika (uid=1003, sudo)

---

## CPU

**Command:**
```bash
lscpu | grep -E "Model name|Socket|Core|Thread|CPU\(s\)"
```

**Output (Luna):**
```
CPU(s):               192
Model name:           Intel(R) Xeon(R) Platinum 8468
Thread(s) per core:   2
Core(s) per socket:   48
Socket(s):            2
```

| Property | Value |
|---|---|
| Model | Intel Xeon Platinum 8468 (Sapphire Rapids) |
| Sockets | 2 |
| Cores per socket | 48 physical |
| Total physical cores | 96 |
| Threads per core | 2 (Hyper-Threading) |
| Total logical CPUs | **192** |
| Max clock | 3.8 GHz (min 800 MHz) |
| Architecture | x86_64 |
| SIMD | AVX2, **AVX-512F/DQ/BW/VL/IFMA/VNNI/BF16/FP16** |
| **Special** | **AMX** (amx_bf16, amx_tile, amx_int8) — hardware matrix multiply unit |

**vs Minerva (Xeon Gold 6330):** 96 vs 56 physical cores, 3.8 vs 2.0 GHz base, AVX-512 + AMX vs AVX-512 only.

---

## Cache Hierarchy

**Command:**
```bash
lscpu | grep -E "L1|L2|L3|cache"
```

**Output (Luna):**
```
L1d:    4.5 MiB (96 instances)
L1i:    3 MiB   (96 instances)
L2:     192 MiB (96 instances)
L3:     210 MiB (2 instances)
```

| Level | Total | Per core | Per socket | Notes |
|---|---|---|---|---|
| L1d | 4.5 MiB | **48 KB** | 2.25 MiB | 96 instances |
| L1i | 3 MiB | **32 KB** | 1.5 MiB | 96 instances |
| L2 | **192 MiB** | **2 MB** | 96 MiB | 96 instances — 4× Minerva's L2 |
| L3 | **210 MiB** | — | **105 MB/socket** | 2 instances — huge LLC |

> **Impact on matrix multiply benchmarks:** N=1024 (24 MB) and N=2048 (96 MB) matrices both fit in L3 here (210 MB). On WSL2 (16 MB L3) both were memory-bound. Luna will show very different (lower) L3 miss rates for the same benchmarks.

---

## NUMA Topology

**Command:**
```bash
numactl --hardware    # install: sudo apt install numactl
```

**From lscpu:**
```
NUMA node(s):   2
NUMA node0:     0,2,4,6,...190   (even CPUs — socket 0)
NUMA node1:     1,3,5,7,...191   (odd CPUs  — socket 1)
```

| Property | Value |
|---|---|
| NUMA nodes | 2 |
| CPUs per node | 96 logical (48 physical) |
| Interleaved assignment | Yes — even=node0, odd=node1 |

> **Note:** numactl not installed as of 2026-05-28. Install with `sudo apt install numactl` to get memory bandwidth per node and NUMA-aware pinning.

---

## RAM

**Command:**
```bash
free -h
```

**Output (Luna):**
```
               total    used    free   shared  buff/cache  available
Mem:           503Gi    46Gi   223Gi    21Mi      233Gi      451Gi
Swap:           59Gi   430Mi    59Gi
```

| Property | Value |
|---|---|
| Total RAM | **503 GB** |
| Used | 46 GB |
| Free | 223 GB |
| Buff/Cache | 233 GB |
| **Available** | **451 GB** |
| Swap total | 59 GB |
| Swap used | 430 MB |

> **vs Minerva:** 503 GB vs 251 GB — twice the RAM. Entire Kraken-2 standard DB (180 GB) fits in RAM with room to spare.

---

## GPU

**Command:**
```bash
nvidia-smi
```

**Output (Luna, 2026-05-28):**
```
NVIDIA-SMI 575.64.03   Driver Version: 575.64.03   CUDA Version: 12.9
GPU  Name         VRAM Used/Total       GPU-Util  Temp   Power
0    NVIDIA L40S  488MiB / 46068MiB     0%        42°C   86W / 350W
1    NVIDIA L40S  14MiB  / 46068MiB     0%        36°C   33W / 350W
```

| Property | GPU 0 | GPU 1 |
|---|---|---|
| Model | **NVIDIA L40S** | **NVIDIA L40S** |
| Architecture | Ada Lovelace | Ada Lovelace |
| VRAM | **46 GB GDDR6** | **46 GB GDDR6** |
| Combined VRAM | **~92 GB** | — |
| Power cap | 350W | 350W |
| Current power | 86W | 33W |
| GPU util | 0% | 0% |
| Current VRAM use | 488 MiB (python3) | 14 MiB |
| CUDA Version | 12.9 | 12.9 |
| Driver | 575.64.03 | 575.64.03 |

> **vs Minerva (A40):** L40S is newer Ada Lovelace (vs Ampere A40). L40S has ~91.6 TFLOPS FP32 vs A40's ~37.4 TFLOPS — roughly 2.5× more compute per card. Both have 46 GB VRAM.

---

## Storage

**Command:**
```bash
df -h
```

**Output (Luna):**
```
Filesystem      Size   Used  Avail  Use%  Mounted on
/dev/sda3       938G   653G  238G    74%  /
/dev/sda1       4.7G   6.1M  4.7G     1%  /boot/efi
tmpfs            51G   4.1M   51G     1%  /run
tmpfs           252G   108K  252G    ~0%  /dev/shm
```

| Filesystem | Size | Used | Available | Use% | Mount |
|---|---|---|---|---|---|
| /dev/sda3 | 938 GB | 653 GB | **238 GB** | 74% | / root |
| /dev/sda1 | 4.7 GB | 6.1 MB | 4.7 GB | 1% | /boot/efi |
| tmpfs (shm) | 252 GB | ~0 | 252 GB | ~0% | /dev/shm |

> Root at 74% (238 GB free). Fine for now. /dev/shm is 252 GB — large in-memory scratch space.

---

## Operating System

**Output (Luna):**
```
Linux dell-R760 6.8.0-78-generic #78~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC x86_64 GNU/Linux
```

| Property | Value |
|---|---|
| OS | Ubuntu 22.04 LTS |
| Kernel | 6.8.0-78-generic |
| Architecture | x86_64 |

---

## perf Hardware Counter Status

**Native Linux — no Hyper-V, full PMU access in hardware.**
** perf_event_paranoid = 1 — hardware counters ENABLED for all users (verified 2026-05-28 22:19 UTC).**

```
perf_event_paranoid = 1   ← verified 2026-05-28 22:19 UTC
```

| Value | Meaning |
|---|---|
| -1 | All events allowed for all users |
| 0 | All hardware events allowed for all users |
| **1** | **Hardware events allowed — recommended for profiling** |
| 2 | Only software events for non-root |
| **4** | **Current value — blocks ALL hardware events for non-root** |

**Already applied (2026-05-28):** value confirmed at 1. No action needed.

**Once fixed, these all work (native Linux, Sapphire Rapids PMU):**

| Counter | Status | Notes |
|---|---|---|
| `cycles`, `instructions`, IPC |  Accurate | No virtualisation throttling |
| `cache-misses`, `cache-references` |  Works | |
| `LLC-load-misses`, `LLC-loads` |  **Works** | Was blocked on WSL2 |
| `stalled-cycles-backend` |  **Works** | Memory stall % — key metric |
| `L1-dcache-load-misses` |  Works | |
| `mem-loads`, `mem-stores` |  Works | DRAM traffic counts |
| TMA metrics (`tma_*`) |  **Full TMA** | Sapphire Rapids native TMAM |
| Uncore events (`unc_cha_*`) |  Available | Cross-socket snoops |
| PEBS precise events |  Available | Supports address |

---

## Profiling Tool Inventory

> Audited: 2026-05-28

| Tool | Version / Path | Status | Notes |
|---|---|---|---|
| **perf** | `/usr/bin/perf` |  Installed | paranoid=1  — full hardware counters enabled |
| **gcc** | `/usr/bin/gcc` |  Installed | |
| **g++** | `/usr/bin/g++` |  Installed | |
| **python3** | `/usr/bin/python3` |  Installed | |
| **make** | `/usr/bin/make` |  Installed | |
| **perl** | `/usr/bin/perl` |  Installed | |
| **btop** | installed 2026-05-28 |  Installed | Use `btop --utf-force` |
| nvcc (CUDA compiler) | — |  Not in PATH | Check: `find /usr /opt -name nvcc 2>/dev/null` |
| nsys (Nsight Systems) | — |  Not in PATH | Check: `find /usr /opt -name nsys 2>/dev/null` |
| ncu (Nsight Compute) | — |  Not in PATH | Check: `find /usr /opt -name ncu 2>/dev/null` |
| valgrind | — |  Not installed | `sudo apt install valgrind` |
| likwid-perfctr | — |  Not installed | See install_tools.md |
| numactl | — |  Not installed | `sudo apt install numactl` |
| VTune | — | Unknown | Check: `find /opt /usr -name vtune 2>/dev/null` |

> **nvcc/nsys/ncu missing from PATH** — these may be installed but not on PATH (same issue as Minerva with nsys). Check:
> ```bash
> find /usr /opt -name "nvcc" 2>/dev/null
> find /usr /opt -name "nsys" 2>/dev/null
> find /usr /opt -name "ncu"  2>/dev/null
> ```

---

## Quick Full Re-check

```bash
echo "=== CPU ===" && lscpu | grep -E "Model name|Socket|Core|Thread|CPU\(s\)"
echo "=== RAM ===" && free -h
echo "=== GPU ===" && nvidia-smi
echo "=== DISK ===" && df -h
echo "=== PERF PARANOID ===" && cat /proc/sys/kernel/perf_event_paranoid
echo "=== TOOLS ===" && which gcc g++ python3 perf nvcc nsys ncu valgrind likwid-perfctr 2>/dev/null
echo "=== WHO IS ON ===" && w
echo "=== OS ===" && uname -a
```
