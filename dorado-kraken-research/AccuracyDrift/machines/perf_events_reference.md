# perf Event Reference — Cross-Machine Comparison

## Luna (x86-64, Sapphire Rapids, kernel 5.15.x)

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads <T> \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Event | Maps to |
|-------|---------|
| `cache-misses` | L1/L2/L3 misses (hardware cache-miss counter) |
| `cache-references` | All cache accesses |
| `LLC-loads` | Last-level cache (L3) load accesses |
| `LLC-load-misses` | Last-level cache (L3) load misses → goes to DRAM |
| `instructions` | Total instructions retired |
| `cycles` | CPU cycles |

Derived metrics:
- Cache Miss Rate% = cache-misses / cache-references × 100
- LLC Miss Rate% = LLC-load-misses / LLC-loads × 100
- IPC = instructions / cycles

---

## Orion (ARM64, Cortex-A78AE, kernel 5.10.120-tegra)

perf binary: `/usr/lib/linux-tools-5.4.0-26/perf` (5.4 binary works on 5.10 kernel)
Must run with sudo. Alias set in ~/.bashrc: `alias perf='sudo /usr/lib/linux-tools-5.4.0-26/perf'`

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads <T> \
  --output /dev/null --report /dev/null \
  ~/reads/reads_hac.fastq
```

Note: `numactl` omitted — Orion has unified memory (single NUMA node, no binding needed).
Thread counts to test: 1, 2, 4, 6, 8, 10, 12 (12-core CPU, no hyperthreading).

| Event | Maps to on ARM Cortex-A78 |
|-------|--------------------------|
| `cache-misses` | Maps to L1D cache refills (ARM PMU: L1D_CACHE_REFILL) |
| `cache-references` | Maps to L1D cache accesses (ARM PMU: L1D_CACHE) |
| `LLC-loads` | System-level cache (SLC) read accesses |
| `LLC-load-misses` | SLC read misses → goes to LPDDR5 unified memory |
| `instructions` | Instructions retired |
| `cycles` | CPU cycles |

Derived metrics: same formulas as Luna.

**Important:** On ARM, `cache-misses/cache-references` reflects L1D behavior, not L3.
On x86 (Luna), it reflects the overall cache hierarchy. Both are valid for
cross-machine comparison but measure slightly different levels. LLC-load-misses
is the directly comparable metric — it measures DRAM pressure on both machines.

**Confirmed working** (tested 2026-06-12): all 6 events return real hardware values with sudo.

---

## Event Availability Summary

| Event | Luna (x86) | Orion (ARM64) |
|-------|-----------|---------------|
| cache-misses | yes | yes |
| cache-references | yes | yes |
| LLC-loads | yes | yes |
| LLC-load-misses | yes | yes |
| instructions | yes | yes |
| cycles | yes | yes |
| branches | yes | not supported (5.4 perf on 5.10 kernel) |

---

## numactl on Orion

```bash
numactl --hardware
```

Orion has unified LPDDR5 memory — likely single NUMA node. The `--cpunodebind=0 --membind=0`
flags from Luna's command are unnecessary but harmless if present.
