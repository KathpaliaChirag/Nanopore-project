# Luna — User Guide

> Server: dell-R760 | hostname: `dell-R760`
> OS: Ubuntu 22.04 LTS | Kernel: 6.8.0-78-generic

---

## Logging In

```bash
# Fill in once confirmed:
ssh <your-username>@<luna-ip-or-hostname>
```

> Ask chayanika for the IP/hostname and your account credentials.

---

## Key Differences vs Minerva

| Feature | Minerva | Luna |
|---|---|---|
| CPU | Xeon Gold 6330 @ 2 GHz | **Xeon Platinum 8468 @ 3.8 GHz** |
| Cores | 56 physical / 112 logical | **96 physical / 192 logical** |
| L2 per core | 1 MB | **2 MB** |
| L3 total | ~66 MB | **210 MB** |
| RAM | 251 GB | **503 GB** |
| GPU | 2× A40 (45 GB) | **2× L40S (46 GB)** |
| SIMD | AVX-512 | **AVX-512 + AMX** |
| perf IPC | ✓ accurate | ✓ accurate |
| Root disk free | ~9 GB (critical) | 238 GB (fine) |

---

## First Things to Check When You Log In

```bash
# Who else is using the machine right now
w

# GPU utilisation — is anyone using the L40S?
nvidia-smi

# RAM — is there enough free?
free -h

# Is perf working with hardware counters?
cat /proc/sys/kernel/perf_event_paranoid   # want ≤1
perf stat ls                               # quick smoke test

# Disk space
df -h
```

---

## Running the Matrix Multiply Benchmarks on Luna

The source files are in `All_Matric_Mul_perf_stats/` on your local machine.
Copy them to Luna:

```bash
# From your local machine / WSL:
scp -r "All_Matric_Mul_perf_stats/" <user>@<luna>:~/matmul/
```

On Luna:
```bash
cd ~/matmul
make clean && make          # rebuilds with Luna's GCC + -march=native (picks up AVX-512!)
chmod +x run_wsl_perf.sh    # still works on Luna, despite the name

# Run with full hardware counters (LLC-load-misses works here!)
make run_perf SIZE=1024 THREADS=8
make run_perf SIZE=2048 THREADS=8
make run_perf SIZE=10000 THREADS=8
```

> When rebuilt on Luna with `-march=native`, the compiler will auto-generate AVX-512 instructions instead of AVX2 — `auto_vec_O3` will be faster without any code changes.

---

## perf Commands That Work Here But Not on WSL2

```bash
# Full LLC miss rate (was <not supported> on WSL2)
perf stat -e LLC-load-misses,LLC-loads ./ikj_order 1024

# Memory stall % — what fraction of time CPU waited for RAM
perf stat -e stalled-cycles-backend ./naive_ijk 1024

# TMA breakdown — memory-bound vs compute-bound directly
perf stat -e tma_memory_bound,tma_core_bound,tma_l1_bound,\
tma_l2_bound,tma_l3_bound,tma_dram_bound \
./naive_ijk 1024

# NUMA-aware run — pin to one socket to avoid cross-socket traffic
numactl --cpunodebind=0 --membind=0 ./tiled_avx2 2048
```

---

## btop

```bash
btop --utf-force    # locale workaround until UTF-8 locale is set
```

Permanent fix:
```bash
echo 'export LANG=en_US.UTF-8' >> ~/.bashrc && source ~/.bashrc
btop
```
