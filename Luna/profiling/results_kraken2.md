# Luna — Kraken2 Profiling Results

> Server: luna (dell-R760) | CPU: 2x Xeon Platinum 8468 (192 logical CPUs, 96 physical) | RAM: 503 GB
> Database: k2_standard_08gb (8GB pre-built, standard bacteria/archaea/viral/human)
> Input: FBE01990_24778b97_03e50f91_10.pod5 basecalled with Dorado 1.4.0

---

## Step 1 — Dorado Basecalling Results

**Command:**
```bash
dorado basecaller fast ~/data/pod5/FBE01990_24778b97_03e50f91_10.pod5 --emit-fastq > ~/results/basecalling/reads_fast.fastq
dorado basecaller hac  ~/data/pod5/FBE01990_24778b97_03e50f91_10.pod5 --emit-fastq > ~/results/basecalling/reads_hac.fastq
dorado basecaller sup  ~/data/pod5/FBE01990_24778b97_03e50f91_10.pod5 --emit-fastq > ~/results/basecalling/reads_sup.fastq
```

| Model | Reads | Total Bases |
|---|---|---|
| fast | 104,832 | 357.62 Mbp |
| hac | 104,918 | 355.36 Mbp |
| sup | 104,980 | 365.84 Mbp |

---

## Step 2 — Kraken2 Classification Results

**Command:**
```bash
kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/classification/report_<model>.txt \
  --output ~/results/classification/output_<model>.txt \
  ~/results/basecalling/reads_<model>.fastq
```

| Model | Reads | Classified | Unclassified | Time | Throughput |
|---|---|---|---|---|---|
| fast | 104,832 | 82.66% | 17.34% | 1.095s | 19,597 Mbp/m |
| hac | 104,918 | 95.77% | 4.23% | 1.097s | 19,444 Mbp/m |
| sup | 104,980 | 97.09% | 2.91% | 1.072s | 20,485 Mbp/m |

**Observation:** Classification rate jumps from 82.7% (fast) to 97.1% (sup). Read quality directly affects how many k-mers match the database. Kraken2 runtime is nearly identical across all three models — it depends on read length and thread count, not read quality.

---

## Step 3 — perf stat Baseline (hac model)

**Command:**
```bash
perf stat \
  -e cycles,instructions \
  -e cache-misses,cache-references \
  -e LLC-load-misses,LLC-loads \
  -e L1-dcache-load-misses,L1-dcache-loads \
  -e branch-misses,branch-instructions \
  -e cycle_activity.stalls_total \
  -e cycle_activity.stalls_l1d_miss \
  -e cycle_activity.stalls_l2_miss \
  -e cycle_activity.stalls_l3_miss \
  -e memory_activity.stalls_l3_miss \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/profiling/perf_report_hac_full.txt \
  --output ~/results/profiling/perf_output_hac_full.txt \
  ~/results/basecalling/reads_hac.fastq
```

**Raw output:**
```
 Performance counter stats for 'kraken2 ... reads_hac.fastq':

   71,67,29,23,288      cycles                                                        (54.30%)
 1,13,16,36,95,604      instructions              #  1.58  insn per cycle             (60.94%)
      46,69,09,819      cache-misses              # 85.39% of all cache refs          (60.76%)
      54,67,68,361      cache-references                                              (60.51%)
       9,86,97,718      LLC-load-misses           # 81.89% of all LL-cache accesses   (60.32%)
      12,05,25,987      LLC-loads                                                     (60.10%)
      20,69,20,846      L1-dcache-load-misses     #  0.66% of all L1-dcache accesses  (59.79%)
   31,36,35,10,334      L1-dcache-loads                                               (52.87%)
      29,49,96,843      branch-misses             #  1.48% of all branches            (59.71%)
   19,92,32,41,816      branch-instructions                                           (59.76%)
   34,93,69,00,638      cycle_activity.stalls_total                                   (53.27%)
    4,49,12,15,713      cycle_activity.stalls_l1d_miss                                (53.53%)
    3,99,75,94,888      cycle_activity.stalls_l2_miss                                 (53.79%)
                 0      cycle_activity.stalls_l3_miss                                 (53.97%)
    8,34,48,21,177      memory_activity.stalls_l3_miss                                (54.17%)

       4.998554800 seconds time elapsed
      19.319690000 seconds user
       5.897515000 seconds sys
```

**Cleaned metrics:**

| Metric | Value | Notes |
|---|---|---|
| Cycles | 71.7 billion | — |
| Instructions | 113.2 billion | — |
| IPC | **1.58** | Theoretical max ~6 — CPU at 26% efficiency |
| Cache miss rate | **85.4%** | Extremely high — almost every cache access misses |
| LLC miss rate | **81.9%** | 8GB hash table far exceeds 210MB L3 — nearly every lookup goes to DRAM |
| LLC loads | 1.21 billion | — |
| LLC load misses | 987 million | — |
| L1 miss rate | 0.66% | L1 is fine — problem is deeper in hierarchy |
| Branch miss rate | 1.48% | Acceptable — not a bottleneck |
| Total stall cycles | 34.9 billion | — |
| Stall % of total cycles | **48.7%** | Almost half the time CPU is doing nothing |
| L1 miss stalls | 4.49 billion | — |
| L2 miss stalls | 4.0 billion | — |
| L3 miss stalls (cycle_activity) | 0 | Event not counting correctly on this CPU |
| Memory stalls (DRAM) | **8.34 billion** | Cycles waiting for DRAM to return data |
| Wall time | 5.0s | — |
| User time | 19.3s | ~3.9x CPU utilization — 96 threads underutilised |

---

## Step 4 — TMA Breakdown (hac model)

**Command:**
```bash
perf stat -M tma_memory_bound,tma_core_bound \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```

**Raw output:**
```
 4,25,92,63,69,482      TOPDOWN.SLOTS           # 25.4 %  tma_memory_bound
                                                # 21.7 %  tma_core_bound
 1,14,55,76,68,740      topdown-retiring
   40,65,68,20,209      topdown-fe-bound
 1,08,79,36,10,532      topdown-mem-bound
 2,01,66,30,63,483      topdown-be-bound
   71,98,75,32,747      topdown-bad-spec

       5.004310138 seconds time elapsed
```

**TMA slot breakdown:**

| Category | Slots | % | Meaning |
|---|---|---|---|
| Retiring (good work) | 114.6 billion | ~26.9% | Useful instructions executed |
| Memory bound | 108.8 billion | **25.4%** | Stalled waiting for memory |
| Core bound | — | **21.7%** | Stalled on execution units |
| Bad speculation | 72.0 billion | ~16.9% | Wasted on wrong-path instructions |
| Frontend bound | 40.7 billion | ~9.6% | Stalled fetching instructions |

**Total TOPDOWN slots: 425.9 billion**

---

## Core Findings

### 1. Memory is the primary bottleneck

81.9% LLC miss rate means almost every hash table lookup misses the 210MB L3 cache
and goes to DRAM. The 8GB database simply cannot fit in cache. Every classified read
requires multiple DRAM round trips. This is the dominant bottleneck.

### 2. CPU efficiency is poor

IPC of 1.58 against a theoretical max of ~6 means the CPU is running at 26% of its
potential. 48.7% of all cycles are stall cycles — the CPU is idle waiting for memory.

### 3. The wall time is misleading

Kraken2 reports "processed in 1.06s" but wall time is 5.0s. The other ~4 seconds is
loading the 8GB database from disk into RAM. The actual classification work takes 1
second. Profiling is dominated by the database load phase unless the database is
already in the OS page cache from a previous run.

### 4. Thread utilisation is low

User time (19.3s) / wall time (5.0s) = ~3.9x CPU multiplier across 96 threads.
Effective utilisation is roughly 4 cores worth of work despite 96 being available.
Kraken2 is not scaling well to 96 threads for this input size — the dataset may be
too small to saturate all threads, or lock contention in the hash table limits parallelism.

### 5. Branch prediction is fine

1.48% branch miss rate is not a concern. Optimisation effort should focus on memory,
not branches.

---

## Optimisation Targets

| Priority | Target | Expected Gain |
|---|---|---|
| 1 | Reduce LLC misses — prefetching or hash table restructuring | High |
| 2 | Improve thread scaling — remove bottlenecks limiting parallelism | Medium |
| 3 | Separate database load time from classification time in benchmarks | Low (measurement) |

---

## WSL2 vs Luna Comparison

| Metric | WSL2 | Luna | Notes |
|---|---|---|---|
| IPC | 2.26 (wrong) / ~0.55 (uProf) | **1.58** | Luna native PMU — more reliable |
| LLC miss rate | not supported | **81.9%** | First reliable measurement |
| Cache miss rate | 34.24% | **85.4%** | Larger database loaded on Luna |
| stalled-cycles-backend | not supported | **replaced by cycle_activity.stalls_*** | Event removed on Sapphire Rapids |
| Total stall % | unknown | **48.7%** | — |
| TMA memory bound | unknown | **25.4%** | — |
| TMA core bound | unknown | **21.7%** | — |
| Hotspot function | CompactHashTable::Get() 67% | not yet measured | perf record pending |

---

## Next Steps

- Run perf record + flamegraph to confirm CompactHashTable::Get() as hotspot on Luna
- Run second Kraken2 pass after database is in page cache to isolate classification-only time
- NUMA analysis — check if hash table memory crosses socket boundary
- Run fast and sup models through same perf stat for comparison
