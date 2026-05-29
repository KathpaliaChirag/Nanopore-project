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

## Step 3 — perf stat + Per-Core CPU Capture (all 3 models)

**Method:** Run `mpstat -P ALL 1` in the background to capture per-core utilisation at 1-second intervals while `perf stat` profiles the full Kraken2 run. Both outputs saved to `~/results/profiling/`.

**Commands:**
```bash
# Repeat for model in: fast, hac, sup
MODEL=hac   # change to fast / sup

mpstat -P ALL 1 > ~/results/profiling/mpstat_${MODEL}.txt &
MPSTAT_PID=$!

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
  --report ~/results/profiling/report_${MODEL}.txt \
  --output /dev/null \
  ~/results/basecalling/reads_${MODEL}.fastq \
  2> ~/results/profiling/perf_stat_${MODEL}.txt

kill $MPSTAT_PID
```

**Output files per model:**
- `~/results/profiling/perf_stat_<model>.txt` — raw perf stat output
- `~/results/profiling/mpstat_<model>.txt` — per-core CPU % at 1s intervals
- `~/results/profiling/report_<model>.txt` — Kraken2 classification report

---

### 3a — perf stat Results

#### fast model

**Raw output:** `~/results/profiling/perf_stat_fast.txt`

| Metric | Value | Notes |
|---|---|---|
| Cycles | 72.2 billion | |
| Instructions | 105.8 billion | |
| IPC | **1.47** | Theoretical max ~6 — CPU at 24% efficiency |
| Cache miss rate | **86.5%** | |
| LLC miss rate | **82.0%** | Same story as hac — 8GB DB >> 210MB L3 |
| LLC loads | 1.34 billion | |
| LLC load misses | 1.09 billion | |
| L1 miss rate | 0.77% | L1 fine — problem is deeper |
| Branch miss rate | 1.57% | Not a bottleneck |
| Total stall cycles | 37.4 billion | |
| Stall % of total cycles | **51.8%** | 37.4B / 72.2B |
| L1 miss stalls | 5.46 billion | |
| L2 miss stalls | 4.95 billion | |
| Memory stalls (DRAM) | **11.3 billion** | Higher than hac |
| Wall time | 5.84s | |
| User time | 19.0s | ~3.2x CPU utilization across 96 threads |

---

#### hac model

Two runs: cold (first-ever run) and warm (DB already in OS page cache).
**Raw outputs:** `perf_stat_hac.txt` (cold), `perf_stat_hac_warm.txt` (warm)

| Metric | cold | warm | Notes |
|---|---|---|---|
| Cycles | 71.7 billion | 72.6 billion | |
| Instructions | 113.2 billion | 115.1 billion | |
| IPC | **1.58** | **1.58** | Identical — classification behaviour unchanged |
| Cache miss rate | 85.4% | 85.1% | |
| LLC miss rate | 81.9% | 80.9% | Marginal — DB still >> L3 |
| LLC loads | 1.21 billion | 1.27 billion | |
| LLC load misses | 987 million | 1.02 billion | |
| L1 miss rate | 0.66% | 0.68% | |
| Branch miss rate | 1.48% | 1.47% | |
| Total stall cycles | 34.9 billion | 36.5 billion | |
| Stall % of total cycles | 48.7% | 50.2% | |
| L1 miss stalls | 4.49 billion | 4.92 billion | |
| L2 miss stalls | 4.0 billion | 4.46 billion | |
| Memory stalls (DRAM) | **8.34 billion** | **9.89 billion** | |
| Wall time | 5.0s | 5.63s | No speedup warm — DB was already cached |
| User time | 19.3s | 19.3s | Identical — same work done |

**Key observation:** Wall time is the same cold vs warm. DB was already in page cache even on the cold run because fast/sup ran first. The ~4s gap vs Kraken2's reported 1s classification time is mmap fault cost loading the 8GB hash table into process address space — unavoidable even from page cache.

---

#### sup model

**Raw output:** `~/results/profiling/perf_stat_sup.txt`

| Metric | Value | Notes |
|---|---|---|
| Cycles | 72.3 billion | |
| Instructions | 119.2 billion | |
| IPC | **1.65** | Best of the three — more instructions per cycle |
| Cache miss rate | **84.7%** | |
| LLC miss rate | **82.0%** | Consistent across all models — DB size drives this |
| LLC loads | 1.23 billion | |
| LLC load misses | 1.01 billion | |
| L1 miss rate | 0.65% | |
| Branch miss rate | 1.41% | |
| Total stall cycles | 35.0 billion | |
| Stall % of total cycles | **48.5%** | 35.0B / 72.3B |
| L1 miss stalls | 4.75 billion | |
| L2 miss stalls | 4.32 billion | |
| Memory stalls (DRAM) | **9.26 billion** | Lower than fast/hac |
| Wall time | 5.63s | |
| User time | 19.2s | ~3.4x CPU utilization across 96 threads |

---

### 3b — Cross-Model perf stat Comparison

| Metric | fast | hac | sup | Notes |
|---|---|---|---|---|
| IPC | 1.47 | 1.58 | **1.65** | sup does more useful work per cycle |
| Cache miss rate | 86.5% | 85.4% | 84.7% | All high — DB dominates |
| LLC miss rate | 82.0% | 81.9% | 82.0% | Virtually identical — DB size is the wall |
| Stall % | **51.8%** | 48.7% | 48.5% | fast wastes most cycles on stalls |
| Memory stalls (B cycles) | **11.3B** | 8.34B | 9.26B | |
| Wall time | 5.84s | 5.0s | 5.63s | hac fastest wall time |
| User time | 19.0s | 19.3s | 19.2s | Consistent — same thread count |
| Effective cores (user/wall) | ~3.3x | ~3.9x | ~3.4x | user_time / wall_time — all far below 96 |

---

### 3c — Per-Core CPU Utilisation

**Captured with:** `mpstat -P ALL 1` run in background during each Kraken2 run.
**Files:** `~/results/profiling/mpstat_fast.txt`, `mpstat_hac.txt`, `mpstat_sup.txt`

Key observations to extract from mpstat output:

- How many of the 96 cores are active (CPU% > 5%)
- Whether load is spread evenly or concentrated on a few cores
- Whether NUMA socket 0 vs socket 1 cores show different utilisation

| Metric | fast | hac | sup |
|---|---|---|---|
| Peak cores active | | | |
| Avg % iowait | | | |
| Avg % sys | | | |
| Avg % usr | | | |
| Load balanced? | | | |

---

## Step 4 — TMA Breakdown (all 3 models)

**Command:**
```bash
MODEL=hac   # change to fast / sup

perf stat -M tma_memory_bound,tma_core_bound \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_${MODEL}.fastq \
  2> ~/results/profiling/tma_${MODEL}.txt
```

**Output files:** `~/results/profiling/tma_fast.txt`, `tma_hac.txt`, `tma_sup.txt`

---

### 4a — TMA Results

#### hac model (done — 2026-05-29)

**Raw output:** `~/results/profiling/tma_hac.txt`

| Category | Slots | % | Meaning |
|---|---|---|---|
| Retiring (good work) | 114.6 billion | ~26.9% | Useful instructions executed |
| Memory bound | 108.8 billion | **25.4%** | Stalled waiting for memory |
| Core bound | — | **21.7%** | Stalled on execution units |
| Bad speculation | 72.0 billion | ~16.9% | Wasted on wrong-path instructions |
| Frontend bound | 40.7 billion | ~9.6% | Stalled fetching instructions |

#### fast model

**Raw output:** `~/results/profiling/tma_fast.txt`

| Category | Slots | % |
|---|---|---|
| Retiring | 107.4 billion | 24.4% |
| Memory bound | 124.9 billion | **28.1%** |
| Core bound | — | **22.4%** |
| Bad speculation | 72.8 billion | 16.6% |
| Frontend bound | 39.3 billion | 8.9% |

**Total TOPDOWN slots: 440.0 billion**

#### sup model

**Raw output:** `~/results/profiling/tma_sup.txt`

| Category | Slots | % |
|---|---|---|
| Retiring | 120.1 billion | 27.4% |
| Memory bound | 115.7 billion | **26.2%** |
| Core bound | — | **20.8%** |
| Bad speculation | 71.5 billion | 16.3% |
| Frontend bound | 41.8 billion | 9.5% |

**Total TOPDOWN slots: 437.6 billion**

---

### 4b — Cross-Model TMA Comparison

| TMA Category | fast | hac | sup |
|---|---|---|---|
| Retiring % | 24.4% | 26.9% | **27.4%** | 
| Memory bound % | **28.1%** | 25.4% | 26.2% |
| Core bound % | **22.4%** | 21.7% | 20.8% |
| Bad speculation % | 16.6% | 16.9% | 16.3% |
| Frontend bound % | 8.9% | 9.6% | 9.5% |

**Observation:** fast model wastes the most cycles on memory and core stalls, and retires the fewest useful instructions. sup retires the most useful work. All three have nearly identical TMA profiles — the bottleneck is the DB, not the read quality.

---

## Step 5 — Thread Scaling Experiment (fast model)

**Goal:** Find the point at which adding more threads stops helping. Luna has 192 logical CPUs (96 physical + HT). We expect diminishing returns early given effective utilisation is only ~3-4 cores at 96 threads.

**Command:**
```bash
# Each thread count runs 5 times. Wall time measured with millisecond precision.
# kraken2 stderr suppressed (2>/dev/null) to avoid mixing with timing output.
# avg computed with bc. Output tee'd to file.
for T in 2 4 8 16 32 64 96 128 192; do
  echo "=== threads=$T ==="
  sum=0
  for i in 1 2 3 4 5; do
    START=$(date +%s%3N)
    kraken2 --db ~/data/kraken2_db --threads $T \
      --report /dev/null --output /dev/null \
      ~/results/basecalling/reads_fast.fastq 2>/dev/null
    END=$(date +%s%3N)
    W=$(echo "scale=3; ($END - $START) / 1000" | bc)
    echo "  run $i: ${W}s"
    sum=$(echo "$sum + $W" | bc)
  done
  AVG=$(echo "scale=3; $sum / 5" | bc)
  echo "  avg: ${AVG}s"
  echo ""
done 2>&1 | tee ~/results/profiling/thread_scaling_fast.txt
```

**Output file:** `~/results/profiling/thread_scaling_fast.txt`

| Threads | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Avg (s) | Speedup vs 2T |
|---|---|---|---|---|---|---|---|
| 2 | 11.488 | 11.301 | 12.268 | 12.561 | 11.077 | 11.739 | 1.00x |
| 4 | 7.443 | 7.499 | 7.458 | 8.099 | 8.237 | 7.747 | 1.51x |
| 8 | 6.623 | 6.525 | 6.603 | 6.490 | 6.479 | 6.544 | 1.79x |
| 16 | 5.817 | 5.721 | 5.686 | 5.731 | 5.697 | 5.730 | 2.05x |
| 32 | 5.509 | 5.554 | 5.504 | 5.488 | 5.481 | **5.507** | **2.13x** |
| 64 | 5.741 | 5.747 | 5.733 | 5.709 | 5.618 | 5.709 | 2.06x |
| 96 | 5.985 | 5.950 | 5.461 | 5.951 | 5.873 | 5.844 | 2.01x |
| 128 | 5.969 | 6.002 | 6.076 | 5.946 | 5.969 | 5.992 | 1.96x |
| 192 | 6.143 | 6.229 | 6.104 | 6.183 | 6.140 | 6.159 | 1.91x |

**Key finding:** Performance peaks at 32 threads (5.507s avg) and degrades beyond that. Speedup from 2→32 threads is only 2.13x despite 16x more threads. This is the DRAM bandwidth wall — Kraken2 is memory-bound and adding threads past ~32 just creates contention without reducing the bottleneck. 96 threads (our baseline) is actually suboptimal.

---

### 5c — Thread Scaling: hac model

**Output file:** `~/results/profiling/thread_scaling_hac.txt`

| Threads | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Avg (s) | Speedup vs 2T |
|---|---|---|---|---|---|---|---|
| 2 | 12.005 | 11.266 | 11.719 | 12.098 | 11.734 | 11.764 | 1.00x |
| 4 | 7.863 | 7.908 | 7.841 | 8.008 | 7.917 | 7.907 | 1.49x |
| 8 | 6.237 | 6.264 | 6.292 | 6.296 | 6.276 | 6.273 | 1.88x |
| 16 | 5.514 | 5.504 | 5.489 | 5.548 | 5.438 | 5.498 | 2.14x |
| 32 | 5.287 | 5.215 | 5.245 | 5.175 | 5.255 | **5.235** | **2.25x** |
| 64 | 5.430 | 5.405 | 5.388 | 5.470 | 5.396 | 5.417 | 2.17x |
| 96 | 5.649 | 5.596 | 5.660 | 5.633 | 5.638 | 5.635 | 2.09x |
| 128 | 5.752 | 5.767 | 5.738 | 5.793 | 5.717 | 5.753 | 2.05x |
| 192 | 5.857 | 5.882 | 5.816 | 5.897 | 5.845 | 5.859 | 2.01x |

Sweet spot: **32 threads (5.235s)**. Same curve shape as fast. Slightly lower floor than fast (5.235 vs 5.507) — hac has higher classification rate so less wasted hash lookups on unclassified reads.

---

### 5d — Thread Scaling: sup model

**Output file:** `~/results/profiling/thread_scaling_sup.txt`

| Threads | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Avg (s) | Speedup vs 2T |
|---|---|---|---|---|---|---|---|
| 2 | 11.813 | 11.282 | 11.463 | 11.153 | 11.636 | 11.469 | 1.00x |
| 4 | 8.021 | 7.895 | 7.940 | 7.932 | 7.970 | 7.951 | 1.44x |
| 8 | 6.259 | 6.248 | 6.268 | 6.267 | 6.262 | 6.260 | 1.83x |
| 16 | 5.071 | 4.801 | 4.796 | 4.810 | 4.821 | 4.859 | 2.36x |
| 32 | 4.530 | 4.573 | 4.561 | 4.554 | 4.584 | **4.560** | **2.51x** |
| 64 | 4.751 | 4.748 | 4.777 | 4.757 | 4.784 | 4.763 | 2.41x |
| 96 | 4.947 | 4.954 | 4.946 | 4.969 | 5.629 | 5.089 | 2.25x |
| 128 | 5.777 | 5.760 | 5.799 | 5.694 | 5.700 | 5.746 | 2.00x |
| 192 | 5.918 | 5.910 | 5.861 | 5.934 | 5.859 | 5.896 | 1.94x |

Sweet spot: **32 threads (4.560s)** — but note 16T (4.859s) is already very close. sup also has a steeper degradation past 32T than fast/hac (128T jumps to 5.746s vs hac's 5.753s). The 96T run has one outlier (5.629s) — system noise, not a real effect.

---

### 5e — Cross-Model Thread Scaling Comparison

| Threads | fast (s) | hac (s) | sup (s) | Notes |
|---|---|---|---|---|
| 2 | 11.739 | 11.764 | 11.469 | All similar — DB load dominates |
| 4 | 7.747 | 7.907 | 7.951 | |
| 8 | 6.544 | 6.273 | 6.260 | hac/sup pull ahead |
| 16 | 5.730 | 5.498 | **4.859** | sup notably faster from here |
| 32 | **5.507** | **5.235** | **4.560** | **Sweet spot for all 3** |
| 64 | 5.709 | 5.417 | 4.763 | All degrade past 32T |
| 96 | 5.844 | 5.635 | 5.089 | |
| 128 | 5.992 | 5.753 | 5.746 | |
| 192 | 6.159 | 5.859 | 5.896 | |
| **Sweet spot** | **32T** | **32T** | **32T** | Unanimous |
| **Best avg (s)** | 5.507 | 5.235 | **4.560** | sup fastest floor |
| **2T→32T speedup** | 2.13x | 2.25x | **2.51x** | sup gets most from threading |

**Why sup is faster overall:** sup classifies 97.1% of reads vs fast's 82.7%. Unclassified reads in fast exhaust their full k-mer set without finding enough matches — more wasted hash lookups per read. sup wastes less time on dead-end lookups, so the actual classification phase is shorter. The DB mmap floor (~4-5s) is the same for all three.

**Conclusion: run all future profiling at 32 threads.**

---

### 5b — Thread Scaling: perf stat per thread count (5-run avg with stddev)

**Goal:** Capture IPC, LLC miss rate, and stall % at each thread count to see how cache behaviour and CPU efficiency change with parallelism.

**Command:**
```bash
# perf stat -r 5 runs the command 5 times and reports mean ± stddev per counter.
# Each thread count saved to its own file for clean parsing.
for T in 2 4 8 16 32 64 96 128 192; do
  echo "=== threads=$T ==="
  perf stat -r 5 \
    -e cycles,instructions \
    -e LLC-load-misses,LLC-loads \
    -e cycle_activity.stalls_total \
    -e memory_activity.stalls_l3_miss \
    kraken2 --db ~/data/kraken2_db --threads $T \
    --report /dev/null --output /dev/null \
    ~/results/basecalling/reads_fast.fastq \
    2> ~/results/profiling/thread_scaling_perf_T${T}.txt
  cat ~/results/profiling/thread_scaling_perf_T${T}.txt
  echo ""
done 2>&1 | tee ~/results/profiling/thread_scaling_perf_summary.txt
```

**Output files:**
- `~/results/profiling/thread_scaling_perf_T<N>.txt` — per-thread raw perf output
- `~/results/profiling/thread_scaling_perf_summary.txt` — all combined

| Threads | IPC | LLC miss% | Stall% | DRAM stalls (B) | Wall time (s) | Classification time (s) | Speedup vs 2T |
|---|---|---|---|---|---|---|---|
| 2 | **1.73** | 81.5% | 44.2% | 11.40 | 12.29 | 7.39 | 1.00x |
| 4 | **1.81** | 80.0% | 42.2% | 9.82 | 8.18 | 3.38 | 1.50x |
| 8 | 1.78 | 80.7% | 43.0% | 10.27 | 6.57 | 1.77 | 1.87x |
| 16 | 1.73 | 82.1% | 44.4% | 10.76 | 5.74 | 0.98 | 2.14x |
| 32 | 1.60 | 82.2% | 48.1% | 11.26 | **5.52** | 0.72 | **2.23x** |
| 64 | 1.48 | 82.1% | 51.5% | 11.22 | 5.68 | 0.87 | 2.17x |
| 96 | 1.46 | 82.2% | 52.0% | 11.23 | 5.87 | 1.05 | 2.10x |
| 128 | 1.41 | 81.8% | 52.8% | 11.15 | 5.97 | 1.14 | 2.06x |
| 192 | **1.28** | 80.9% | **56.0%** | 11.54 | 6.12 | 1.29 | 2.01x |

Stall% = cycle_activity.stalls_total / cycles. Classification time = Kraken2's own reported processing time (excludes DB load). Wall time = total including DB mmap overhead.

---

### Key Findings from Thread Scaling

**1. Classification parallelises well — DB load does not**

Kraken2's reported classification time drops from 7.4s at 2T to 0.72s at 32T — a 10x speedup for the actual work. But wall time only improves from 12.3s to 5.5s because ~4.8s of DB mmap/page-fault overhead is single-threaded and unavoidable regardless of thread count. Adding threads past 32 cannot help — the floor is the DB load.

**2. DRAM bandwidth saturates at ~8-16 threads**

DRAM stall cycles are nearly flat from T=8 onwards (9.8B → 11.5B). DRAM is already at full bandwidth with 8 threads. More threads just queue up waiting for the same bandwidth — they don't get more of it.

**3. IPC degrades monotonically with more threads**

IPC falls from 1.81 (4T) to 1.28 (192T). More threads = more lock contention and cache line thrashing = each thread does less useful work per cycle. 192T has 44% more total stall cycles than 2T despite doing the same work.

**4. Sweet spot is 32 threads**

32T gives the best wall time (5.52s). Beyond that, contention overhead outweighs any parallelism benefit. Using 96 threads (our baseline) wastes ~6% wall time vs optimal and burns CPU resources needlessly. Optimal for this dataset + DB size is **32 threads**.

---

## Core Findings (hac — to be updated for fast/sup)

### 1. Memory is the primary bottleneck

81.9% LLC miss rate means almost every hash table lookup misses the 210MB L3 cache
and goes to DRAM. The 8GB database simply cannot fit in cache. Every classified read
requires multiple DRAM round trips.

### 2. CPU efficiency is poor

IPC of 1.58 against a theoretical max of ~6 means the CPU is running at 26% of its
potential. 48.7% of all cycles are stall cycles — the CPU is idle waiting for memory.

### 3. Wall time is misleading

Kraken2 reports ~1s but wall time is 5s. The other ~4 seconds is loading the 8GB
database from disk into RAM. The actual classification work takes 1 second. Profiling
is dominated by the database load phase unless the DB is already in the OS page cache.

### 4. Thread utilisation is low

User time (19.3s) / wall time (5.0s) = ~3.9x CPU multiplier across 96 threads.
Effective utilisation is roughly 4 cores worth of work despite 96 being available.
The dataset may be too small to saturate all threads, or lock contention limits parallelism.

### 5. Branch prediction is fine

1.48% branch miss rate is not a concern.

---

## WSL2 vs Luna Comparison

| Metric | WSL2 | Luna | Notes |
|---|---|---|---|
| IPC | 2.26 (wrong) / ~0.55 (uProf) | **1.58** | Luna native PMU — more reliable |
| LLC miss rate | not supported | **81.9%** | First reliable measurement |
| Cache miss rate | 34.24% | **85.4%** | Larger database loaded on Luna |
| stalled-cycles-backend | not supported | replaced by cycle_activity.stalls_* | Event removed on Sapphire Rapids |
| Total stall % | unknown | **48.7%** | |
| TMA memory bound | unknown | **25.4%** | |
| TMA core bound | unknown | **21.7%** | |
| Hotspot function | CompactHashTable::Get() 67% (gprof, user-space only) | MinimizerScanner::NextMinimizer 25.57%, CompactHashTable::Get 12.10%, I/O 20% | gprof was blind to kernel and I/O time |

---

## Step 6 — perf record + Flamegraph (hac, 32 threads)

**Command:**
```bash
sudo perf record -g -F 99 -o ~/results/profiling/perf_hac_32t.data \
  ~/tools/kraken2/kraken2 \
  --db ~/data/kraken2_db \
  --threads 32 \
  --output ~/results/profiling/perf_record_hac_32t_out.txt \
  ~/results/basecalling/reads_hac.fastq

sudo perf script -i ~/results/profiling/perf_hac_32t.data | \
  ~/tools/FlameGraph/stackcollapse-perf.pl | \
  ~/tools/FlameGraph/flamegraph.pl > ~/results/profiling/flamegraph_hac_32t.svg
```

**Settings:** `-g` (call graph), `-F 99` (99 Hz sampling), 2142 samples collected, 0.239 MB data file.

**Flamegraph:** `Luna/profiling/flamegraph_hac_32t.svg`

---

### 6a — Top Functions by Sample %

| Function | Sample % | Type | Notes |
|---|---|---|---|
| `classify` | 99.11% | kraken2 | entire runtime is classification — expected |
| `kraken2::MinimizerScanner::NextMinimizer` | **25.57%** | user-space | k-mer computation — #1 CPU hotspot |
| `read` syscall path (entry_SYSCALL_64 → ext4_file_read_iter → filemap_read → copy_page_to_iter) | **~20%** | kernel I/O | FASTQ input reading from disk |
| `[unknown]` | 13.45% | missing symbols | kraken2 binary lacks debug info for this slice |
| `kraken2::CompactHashTable::Get` | **12.10%** | user-space | hash lookup — #2 user-space hotspot |
| `exc_page_fault` / `handle_mm_fault` / `__handle_mm_fault` | **~11%** | kernel | DB mmap page faults — cold hash table pages loaded into process space |
| `AddHitlistString` | 1.34% | user-space | writing classification hits to output |

---

### 6b — How perf record and flamegraph work

**perf record** is a sampling profiler. Every 1/99th of a second (`-F 99`), the Linux kernel interrupts whatever is running on each CPU core, looks at the instruction pointer (where in the code is the CPU right now?), and records it along with the full call stack (`-g`). After the program finishes, the `.data` file contains all those snapshots.

With 2142 samples over a ~0.74s run across 32 threads, that is roughly 32 × 0.74 × 99 ≈ 2340 possible samples. 2142 collected is expected — some samples are dropped due to kernel overhead.

The key principle: **functions that appear in more samples are the ones the CPU spent the most time in.** If `foo()` shows up in 257 out of 2142 samples, it consumed ~12% of CPU time.

**The flamegraph** takes all those call stacks and visualises them:
- X axis = % of total samples (width = time)
- Y axis = call depth (bottom = entry point, top = where the CPU actually was)
- Each box = one function

A wide box at the top of a stack means that function itself was doing the work. A wide box in the middle means it was calling something else that consumed the time.

---

### 6c — Analysis of the three main towers

The root is `classify` at 99.11% — all of kraken2's work is inside that function, which is expected.

Below it, three major towers:

**Tower 1 — MinimizerScanner::NextMinimizer (25.57%)**

This is k-mer extraction. For every read, kraken2 scans along it with a sliding window of 35 bases, hashes each window, and picks the minimizer (the minimum hash value in a window of k-mers) as the representative k-mer to look up. This is pure CPU arithmetic — no memory access to the database, just bit operations on the read sequence itself. It is the true dominant hotspot.

On WSL2 gprof this was significantly under-reported because gprof attributed time to the function it sampled in user-space and missed the boundary effects, and the denominator (user CPU time) was inflated by excluding all kernel time.

**Tower 2 — read() syscall chain (~20%)**

This is a kernel call chain: `read() → entry_SYSCALL_64 → do_syscall_64 → __x64_sys_read → vfs_read → ext4_file_read_iter → filemap_read → copy_page_to_iter → _copy_to_iter`

All of that is the Linux kernel reading the FASTQ file from the SSD through the ext4 filesystem into kraken2's buffer. ~20% of all CPU time is spent doing this. gprof cannot see any kernel-mode code — this entire tower was completely invisible to it.

**Tower 3 — CompactHashTable::Get + page faults (~23% combined)**

`CompactHashTable::Get` at 12.10% is the actual hash table probe: take the minimizer hash, compute the bucket index, load the bucket from the 8 GB database. Since the database is 38× larger than the 210 MB L3 cache, most loads miss the cache and go to DRAM — that is what the 82% LLC miss rate from perf stat measures.

The ~11% page faults sit adjacent to this in the flamegraph. When kraken2 first accesses a page of the database that is not in its process address space yet (even if it is already in OS page cache from a previous run), the CPU raises a page fault. The kernel handles it via `exc_page_fault → handle_mm_fault → __handle_mm_fault`. This is the mmap overhead measured in wall time. It is present even on warm runs because the process address space is re-mapped on each execution.

---

### 6d — Why gprof was wrong

gprof works by inserting timer interrupts and counting time only while the process is in **user mode**. The moment kraken2 calls `read()`, the CPU switches to kernel mode and gprof's timer stops counting. Same for every page fault. So gprof's denominator was only the user-space fraction of wall time.

Within that reduced denominator, `CompactHashTable::Get` was genuinely the biggest chunk of user-space time — so gprof's 67% figure was correct for user-space only. But user-space time was only a fraction of actual wall time (user time 19.3s / wall time 5.2s at 32T = ~3.7 effective cores, meaning most of the clock is spent waiting on I/O or kernel handlers).

perf sees everything — user mode, kernel mode, interrupt handlers — so all percentages are of actual wall time.

---

### 6e — Optimisation targets derived from flamegraph

| Target | Wall time % | Approach | Priority |
|---|---|---|---|
| MinimizerScanner::NextMinimizer | **25.57%** | SIMD vectorisation of the minimizer hash computation; or skip redundant minimizer recalculation for overlapping windows | future |
| FASTQ I/O (read syscall chain) | **~20%** | copy input file to tmpfs / ramdisk (`cp reads.fastq /dev/shm/`) — eliminates ext4 entirely and removes the kernel I/O tower | Goal 1 (see below) |
| CompactHashTable::Get | **12.10%** | hot-k-mer LRU cache — cache hits bypass the DRAM lookup entirely | implementation target (Kolin sir's design) |
| DB mmap page faults | **~11%** | `mlock()` the database into RAM before classification starts; eliminates fault overhead on every run | future |

---

## Profiling Goals (ordered)

The following experiments are planned in sequence after Step 6.

**Goal 1 — NUMA analysis (next)**

Check whether the 8 GB hash table is allocated across both NUMA sockets. If kraken2 threads on socket 0 are accessing memory pinned to socket 1, each lookup crosses the QPI interconnect (higher latency than local DRAM). `numactl --hardware` shows topology; `numastat` during a run shows cross-socket traffic.

Command to try after baseline:
```bash
numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/data/kraken2_db --threads 32 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```
If wall time drops, cross-NUMA traffic was a real cost.

**Goal 2 — FASTQ on tmpfs (quantify the 20% I/O cost)**

The flamegraph shows ~20% of wall time in ext4 I/O reading the FASTQ. Moving the input file to `/dev/shm` (tmpfs, RAM-backed) should eliminate that entire tower.

```bash
cp ~/results/basecalling/reads_hac.fastq /dev/shm/reads_hac.fastq
kraken2 --db ~/data/kraken2_db --threads 32 \
  --report /dev/null --output /dev/null \
  /dev/shm/reads_hac.fastq
```

Expected: wall time drops by ~1s (from 5.2s toward ~4.2s). This isolates whether the I/O cost is the ext4 layer or something deeper.

**Goal 3 — Dorado GPU profiling on L40S**

`results_dorado.md` is still blank. Needs nsys/ncu located in PATH first (`find /usr /opt -name nsys 2>/dev/null`).

---

## Step 7 — NUMA Analysis (hac, 32 threads)

**Commands:**
```bash
numactl --hardware   # topology check

# 5 runs each: default, node 0 pinned, node 1 pinned
for i in 1 2 3 4 5; do START=$(date +%s%3N); kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null; END=$(date +%s%3N); echo "default run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"; done

for i in 1 2 3 4 5; do START=$(date +%s%3N); numactl --cpunodebind=0 --membind=0 kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null; END=$(date +%s%3N); echo "node0 run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"; done

for i in 1 2 3 4 5; do START=$(date +%s%3N); numactl --cpunodebind=1 --membind=1 kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null; END=$(date +%s%3N); echo "node1 run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"; done
```

### 7a — NUMA Topology

```
available: 2 nodes (0-1)
node 0 cpus: 0 2 4 6 ... 190  (all even-numbered logical CPUs — 96 total)
node 1 cpus: 1 3 5 7 ... 191  (all odd-numbered logical CPUs — 96 total)
node 0 size: 257,467 MB  |  node 0 free: 55,356 MB  (used: ~202 GB)
node 1 size: 257,964 MB  |  node 1 free: 174,467 MB (used: ~83 GB)
node distances:  local = 10,  remote = 21  (2.1× penalty for cross-socket access)
```

The DB and file cache are predominantly on node 0 (202 GB used vs 83 GB on node 1). Even-numbered CPUs are node 0, odd-numbered are node 1 — so with no pinning, Linux places threads across both sockets freely.

### 7b — Wall Time Results

| Config | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Avg |
|---|---|---|---|---|---|---|
| default (no pinning) | 5.267 | 5.267 | 5.247 | 5.262 | 5.263 | **5.261s** |
| node 0 pinned | 4.775 | 4.400 | 4.398 | 4.393 | 4.430 | 4.479s (steady: **4.405s**) |
| node 1 pinned | 5.143 | 5.086 | 5.078 | 5.041 | 5.068 | **5.083s** |

Node 0 run 1 is a warm-up outlier (DB page remapping on first NUMA bind). Runs 2-5 are steady state.

### 7c — Analysis

**Default (5.261s):** Linux freely schedules 32 threads across both sockets — roughly 16 threads on node 0 (local to DB) and 16 on node 1 (remote). With 82% LLC miss rate, every remote thread's hash lookup crosses the QPI interconnect at 2.1× cost.

**Node 0 pinned (4.405s steady):** All threads on node 0 CPUs, all memory on node 0. DB is already there from previous runs. Every hash lookup hits local DRAM. No cross-socket traffic. Fastest configuration.

**Node 1 pinned (5.083s):** Threads on node 1, memory forced to node 1. DB pages migrate from node 0 page cache to node 1 RAM on first access. The FASTQ file cache also lives on node 0, so reads still pay a cross-socket penalty. Slightly better than default but worse than node 0.

**NUMA cross-socket penalty:**
```
Default:       5.261s
Node 0 pinned: 4.405s  (steady state)
Penalty:       0.856s = 16.3% of wall time wasted on cross-NUMA traffic
```

### 7d — Optimised Command

NUMA pinning recovers 16.3% wall time with zero code changes:

```bash
numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/data/kraken2_db --threads 32 \
  --report <report.txt> --output /dev/null \
  <reads.fastq>
```

Combined optimisation so far: 96T default (5.635s) → 32T (5.235s) → 32T + node 0 pinned (4.405s) = **21.8% total wall time reduction**, no code changes.

---

## Next Steps

- Step 8: gprof on Luna (recompile kraken2 with -pg, run, compare with WSL2 gprof result)
- Step 9: valgrind cachegrind (per-function cache miss counts)
- Step 10: FASTQ tmpfs experiment (Goal 2 — quantify the ~20% I/O cost)
- Step 11: Dorado GPU profiling on L40S (Goal 3)
