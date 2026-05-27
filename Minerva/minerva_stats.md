# Minerva — Server Specifications & Diagnostics

> Last updated: 2026-05-27
> Captured by: chayanika (sudo account)
> Server name: minerva | OS: Ubuntu 22.04.4 LTS

---

## CPU

**Command:**
```bash
lscpu | grep -E "Model name|Socket|Core|Thread|CPU\(s\)"
```
**What it does:** Reads CPU architecture info from the kernel — model, socket count, cores, threads.

**Output (Minerva):**
```
CPU(s):               112
Model name:           Intel(R) Xeon(R) Gold 6330 CPU @ 2.00GHz
Thread(s) per core:   2
Core(s) per socket:   28
Socket(s):            2
```

| Property             | Value                           |
|----------------------|---------------------------------|
| Model                | Intel Xeon Gold 6330 @ 2.00 GHz |
| Sockets              | 2                               |
| Cores per socket     | 28                              |
| Total physical cores | 56                              |
| Threads per core     | 2 (Hyper-Threading enabled)     |
| Total logical CPUs   | 112                             |
| NUMA nodes           | 2 (node0: even, node1: odd)     |
| Architecture         | x86_64                          |

---

## RAM

**Command:**
```bash
free -h
```
**What it does:** Shows total, used, and available RAM and swap in human-readable units.

**Output (Minerva):**
```
               total   used    free    shared  buff/cache  available
Mem:           251Gi   30Gi    23Gi    7.0Mi   197Gi       219Gi
Swap:           59Gi   1.5Gi   58Gi
```

| Property    | Value  |
|-------------|--------|
| Total RAM   | 251 GB |
| Used        | 30 GB  |
| Free        | 23 GB  |
| Buff/Cache  | 197 GB |
| Available   | 219 GB |
| Swap Total  | 59 GB  |
| Swap Used   | 1.5 GB |

> `available` is what actually matters — RAM that can be given to a new process right now.

---

## GPU

**Command:**
```bash
nvidia-smi
```
**What it does:** Queries the NVIDIA driver for GPU model, VRAM usage, temperature, power draw, and running processes.

**Output (Minerva):**
```
NVIDIA-SMI 575.64.03   Driver Version: 575.64.03   CUDA Version: 12.9
GPU  Name        VRAM Used / Total     GPU-Util  Temp   Power
0    NVIDIA A40   14MiB / 46068MiB      0%       27C    23W / 300W
1    NVIDIA A40   14MiB / 46068MiB      0%       29C    22W / 300W
```

| Property       | GPU 0            | GPU 1            |
|----------------|------------------|------------------|
| Model          | NVIDIA A40       | NVIDIA A40       |
| VRAM           | ~45 GB (46068 MiB) | ~45 GB (46068 MiB) |
| Total VRAM     | ~90 GB combined  | —                |
| Power Cap      | 300W             | 300W             |
| CUDA Version   | 12.9             | 12.9             |
| Driver Version | 575.64.03        | 575.64.03        |

---

## Storage — Partitions

**Command:**
```bash
df -h
```
**What it does:** Shows disk space per partition — total size, used, free, and mount point.

**Output (Minerva):**
```
Filesystem      Size  Used  Avail  Use%  Mounted on
/dev/sda3       3.4T  3.2T  9.1G   100%  /
/dev/sda1       4.7G  6.1M  4.7G     1%  /boot/efi
tmpfs           126G  8.0K  126G    ~0%  /dev/shm
tmpfs            26G  4.0M   26G     1%  /run
```

| Filesystem | Size  | Used  | Available | Use% | Mount Point |
|------------|-------|-------|-----------|------|-------------|
| /dev/sda3  | 3.4T  | 3.2T  | 9.1G      | 100% | / (root)    |
| /dev/sda1  | 4.7G  | 6.1M  | 4.7G      | 1%   | /boot/efi   |
| tmpfs      | 126G  | ~0    | 126G      | ~0%  | /dev/shm    |

> **WARNING: Root partition is at 100%. Space being cleared by admin (2026-05-27).**

---

## Storage — Per User

**Command:**
```bash
sudo du -sh /home/*/ 2>/dev/null
```
**What it does:** `du` = disk usage. `-s` = summary (one total per folder, not every subfolder). `-h` = human readable. Shows how much each user's home folder is occupying.

**Output (Minerva, 2026-05-27):**
```
1.8T    /home/chayanika/
1.3T    /home/srikanta/
67G     /home/nikki/
57G     /home/vijay/
56G     /home/srijan/
20G     /home/harshit/
7.3G    /home/kolin/
1.1G    /home/sharath/
1.1G    /home/shashank/
219M    /home/hakima/
106M    /home/dell/
664K    /home/chirag/
676K    /home/rishabh/
16K     /home/CK/
16K     /home/rohit/
```

| User      | Usage  | Notes                        |
|-----------|--------|------------------------------|
| chayanika | 1.8 TB | Admin account — largest user |
| srikanta  | 1.3 TB | Second largest               |
| nikki     | 67 GB  |                              |
| vijay     | 57 GB  |                              |
| srijan    | 56 GB  |                              |
| harshit   | 20 GB  |                              |
| kolin     | 7.3 GB |                              |
| sharath   | 1.1 GB |                              |
| shashank  | 1.1 GB |                              |
| hakima    | 219 MB |                              |
| dell      | 106 MB |                              |
| chirag    | 664 KB | Near-empty (new account)     |
| rishabh   | 676 KB | Near-empty (new account)     |
| CK        | 16 KB  | Near-empty (new account)     |
| rohit     | 16 KB  | Near-empty (new account)     |

> chayanika + srikanta = ~3.1 TB out of 3.2 TB used. These two are the primary cause of full disk.

---

## Operating System

**Command:**
```bash
uname -a && cat /etc/os-release | head -5
```
**What it does:** `uname -a` prints kernel version and architecture. `os-release` has the distro name and version.

**Output (Minerva):**
```
Linux minerva 6.8.0-65-generic #68~22.04.1-Ubuntu SMP x86_64 GNU/Linux
PRETTY_NAME="Ubuntu 22.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.4 LTS (Jammy Jellyfish)"
```

| Property  | Value                          |
|-----------|--------------------------------|
| OS        | Ubuntu 22.04.4 LTS             |
| Codename  | Jammy Jellyfish                |
| Kernel    | 6.8.0-65-generic               |
| Arch      | x86_64                         |

---

## Users on the System

**Command:**
```bash
awk -F: '$3 >= 1000 && $3 < 65534 {print $1, $3, $6}' /etc/passwd
```
**What it does:** Reads `/etc/passwd` and prints only human users (UID 1000+), showing username, UID, and home directory.

**Known users (2026-05-27):**
chayanika, chirag, CK, dell, hakima, harshit, kolin, nikki, rishabh, rohit, sharath, shashank, srijan, srikanta, vijay

---

## Who is Currently Logged In

**Command:**
```bash
w
```
**What it does:** Shows who is logged in, from where, and what they are running right now.

---

## Running Processes (Top Memory Users)

**Command:**
```bash
ps aux --sort=-%mem | head -15
```
**What it does:** Lists all running processes sorted by memory usage, highest first. Good for seeing if a job is running or something is hogging RAM.

---

## Profiling Tool Inventory

> Audited: 2026-05-27

### Already Installed and Working

| Tool | Version | Use |
|---|---|---|
| perf | 6.8.12 | Hardware counters, call graphs, flame graphs |
| gprof | GNU Binutils 2.38 | Function-level % time and call counts |
| ncu (Nsight Compute) | 2021.3.1.0 | Per-kernel GPU metrics |
| nvprof | 2021 | Legacy CUDA profiler — deprecated on CUDA 12, skip |
| g++ | 11.4.0 | Build tool |
| linux-tools-6.8.0-65-generic | kernel-matched | perf kernel support |

**perf_event_paranoid:** was 4 (blocks all hardware counters for non-root). Set to 1 via sudo — allows hardware events for regular users. Persisted in `/etc/sysctl.d/99-perf.conf`.

### Installed, PATH Was Broken (fixed)

| Tool | Path | Fix applied |
|---|---|---|
| nsys (Nsight Systems) | `/usr/lib/nsight-systems/bin/nsys` | Added to PATH via `/etc/profile.d/nsys.sh` |

### Installed via sudo (system-level config, no apt)

| Action | Command | Status |
|---|---|---|
| perf_event_paranoid → 1 | `sudo sysctl -w kernel.perf_event_paranoid=1` | Pending |
| nsys PATH fix | `/etc/profile.d/nsys.sh` | Pending |
| LIKWID msr module | `sudo modprobe msr` + `/etc/modules` | Pending (after LIKWID install) |
| VTune | standalone `.sh` installer → `/opt/intel/vtune/` | Pending |
| DCGM | `sudo dpkg -i dcgm.deb` + systemctl | Pending |

VTune env (after install): sourced via `/etc/profile.d/vtune.sh`

### Installed per user (conda or source — no sudo needed)

| Tool | Install method | What it gives |
|---|---|---|
| valgrind | `conda install -c conda-forge valgrind` | cachegrind (per-function LLC miss rates), massif (heap) |
| heaptrack | `conda install -c conda-forge heaptrack` | Heap allocation tracking — allocation hotspots |
| gperftools/pprof | `conda install -c conda-forge gperftools` | Low-overhead CPU + heap sampling |
| LIKWID | source build (`make PREFIX=$HOME/local install`) | Hardware counter access, memory bandwidth per NUMA node |
| FlameGraph | `git clone` | SVG call graph from perf record output |

See `Minerva/install_tools.md` for full per-user install commands.

### Not Installed (not needed for our scope)

| Tool | Reason |
|---|---|
| nvprof | Officially deprecated on CUDA 12 — use ncu instead |
| Score-P / TAU | HPC tracing frameworks, overkill |

---

## Quick Full Re-check (Run All at Once)

```bash
echo "=== CPU ===" && lscpu | grep -E "Model name|Socket|Core|Thread|CPU\(s\)"
echo "=== RAM ===" && free -h
echo "=== GPU ===" && nvidia-smi
echo "=== DISK (partitions) ===" && df -h
echo "=== DISK (per user) ===" && sudo du -sh /home/*/ 2>/dev/null | sort -rh
echo "=== WHO IS ON ===" && w
echo "=== OS ===" && uname -a && cat /etc/os-release | head -5
```
