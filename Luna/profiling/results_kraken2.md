# Luna — Kraken-2 Profiling Results

> Server: luna (dell-R760) | CPU: 2× Xeon Platinum 8468 (192 logical CPUs) | RAM: 503 GB
> IPC is **accurate** here — direct comparison with AMD uProf's 0.55 from WSL2
> LLC-load-misses **work** here — WSL2 showed `<not supported>`

---

## WSL2 Baselines (for comparison)

| Metric | WSL2 value | Reliability |
|---|---|---|
| Cache miss rate | 34.24% |  correct |
| IPC | 2.26 (reported) → ~0.52 (corrected) | WSL2 wrong; uProf gave 0.55 |
| LLC-load-misses | `<not supported>` | blocked by Hyper-V |
| Total runtime | 105.87 s |  correct |
| Hotspot | `CompactHashTable::Get()` 67% |  from gprof |

---

## perf stat — Full Hardware Counters

**Command:**
```bash
pv ~/barcode02.fastq | perf stat \
  -e cycles,instructions,\
     cache-misses,cache-references,\
     LLC-load-misses,LLC-loads,\
     stalled-cycles-backend,\
     branch-misses,branches \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d \
  -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d \
  -R ~/report_luna.txt - > /dev/null
```

**Output:**
```
[paste perf stat output here]
```

| Metric | WSL2 | **Luna** | Notes |
|---|---|---|---|
| IPC | 2.26 (wrong) | | Should confirm ~0.5 |
| Cache miss rate | 34.24% | | |
| LLC-load-misses | not supported | | |
| LLC miss rate | — | | |
| stalled-cycles-backend % | not supported | | Expect >70% |
| Branch miss rate | — | | |
| Total runtime | 105.87 s | | Expect faster — 3.8 GHz vs 3.2 GHz base |

---

## TMA Breakdown

**Command:**
```bash
pv ~/barcode02.fastq | perf stat \
  -e tma_memory_bound,tma_core_bound,\
     tma_l1_bound,tma_l2_bound,tma_l3_bound,tma_dram_bound \
  ~/kraken2-build-pg/classify [...] - > /dev/null
```

| Metric | Value | Meaning |
|---|---|---|
| tma_memory_bound % | | Should be high — hash table lookups |
| tma_dram_bound % | | Should be very high — random 8 GB DB access |
| tma_l3_bound % | | |
| tma_core_bound % | | Should be low |

---

## perf record — Hotspot Functions

**Command:**
```bash
pv ~/barcode02.fastq | perf record -g -F 99 \
  ~/kraken2-build-pg/classify [...] - > /dev/null
perf report --stdio | head -40
```

**Output:**
```
[paste perf report --stdio here]
```

Expected: `CompactHashTable::Get()` dominant — confirm Minerva finding.

---

## NUMA Analysis (Luna-specific)

Kraken-2 with 8 GB DB: does it cross NUMA nodes? Luna has 2 sockets.
If the DB is allocated on socket 0 but threads run on socket 1, every
hash lookup is a remote NUMA access (~2× latency penalty).

```bash
# Check which NUMA node the DB memory lands on
numactl --hardware
numactl --cpunodebind=0 --membind=0 pv ~/barcode02.fastq | \
  ~/kraken2-build-pg/classify [...] - > /dev/null

# Compare NUMA-pinned vs unpinned runtime
```

| Run | Time | Notes |
|---|---|---|
| Default (unpinned) | | |
| NUMA node 0 pinned | | |
| NUMA node 1 pinned | | |

---

## Cross-Machine Summary

| Tool | Metric | WSL2 | Minerva | **Luna** |
|---|---|---|---|---|
| perf stat | IPC | 2.26 (wrong) | | should confirm ~0.5 |
| perf stat | Cache miss rate | 34.24% | | |
| perf stat | LLC miss rate | N/A | | |
| perf stat | stall-BE % | N/A | | |
| gprof | `CompactHashTable::Get()` | 67% | | |
| TMA | dram_bound % | N/A | | |
