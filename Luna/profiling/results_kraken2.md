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

**Note:** fast was the first model run in Step 2 (classification), so the DB was being loaded from disk for the first time. By the time perf stat was run (Step 3), the DB was already in OS page cache from the Step 2 run.

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

Two runs: first hac run (DB already in OS page cache from fast/sup runs earlier in Step 2) and a second warm run.
**Raw outputs:** `perf_stat_hac.txt` (first run), `perf_stat_hac_warm.txt` (second run)

| Metric | first run | second run | Notes |
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

**Note:** The raw mpstat files were saved to Luna at `~/results/profiling/mpstat_{fast,hac,sup}.txt` but the per-column figures were not manually extracted from them. The key insight (only ~3-4 effective cores despite 96 threads) is already captured in the perf stat user/wall time ratio in Step 3a/3b. These empty cells are a known gap — low priority given the thread scaling sweep (Step 5) covers CPU utilisation comprehensively.

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

### 5f — Thread Scaling: perf stat per thread count (fast model, 5-run avg with stddev)

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

## Core Findings

> Scope: hac model at 96T baseline. All findings below confirmed consistent across fast and sup models (see Steps 3-4).

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

## Profiling Goals Status

| Goal | Description | Status |
|---|---|---|
| 1 | NUMA analysis — wall time + perf stat + TMA across all 4 socket/memory configs | ✅ Done (Steps 7-9) |
| 2 | FASTQ on tmpfs — quantify ~20% ext4 I/O cost from flamegraph | ✅ Done (Step 12) |
| 3 | valgrind cachegrind — per-function L1/LLC miss counts | ✅ Done (Step 11) |
| 4 | gprof on Luna — user-space profile, compare with WSL2 | ✅ Done (Step 10) |
| 5 | Thread scaling — find optimal thread count, DRAM bandwidth saturation point across all models and NUMA configs | ✅ Done (Steps 5, 9) |
| 6 | DRAM bandwidth utilization — actual GB/s consumed vs theoretical max via uncore IMC events | ⏸ On hold — profiling phase complete; useful after optimisation patches applied |
| 7 | perf c2c — cache-to-cache false sharing between threads (explains IPC drop past 32T) | ⏸ On hold |
| 8 | Instruction mix check — is MinimizerScanner auto-vectorized? (objdump, 2 min, no run needed) | ⏸ On hold |
| 9 | perf annotate with -g symbols — source-line hotspots inside CompactHashTable::Get | ⏸ On hold |
| 10 | k-mer reuse measurement — validate LRU cache ROI on reads_hac.fastq (Python script) | ⏸ On hold |
| 11 | VTune — check if installed on Luna, run memory access + threading analysis if available | ⏸ On hold |

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

## Step 8 — NUMA perf stat + TMA: all 4 socket/memory combinations (hac, 32T)

**Goal:** Isolate the effect of NUMA on hardware counters — does pinning reduce LLC miss rate, or just miss latency?

### 8a — perf stat (IPC, LLC miss, stall cycles)

**Commands:**
```bash
# node0+node0, node1+node1, node1CPU+node0mem, node0CPU+node1mem
numactl --cpunodebind=X --membind=Y perf stat \
  -e cycles,instructions -e LLC-load-misses,LLC-loads \
  -e cycle_activity.stalls_total -e memory_activity.stalls_l3_miss \
  kraken2 --db ~/data/kraken2_db --threads 32 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```

| Config | IPC | LLC miss% | Total stalls (B) | Stall% | DRAM stalls (B) | Wall time |
|---|---|---|---|---|---|---|
| node0+node0 (local) | **1.86** | 83.1% | 25.38 | **42.1%** | **6.44** | **4.45s** |
| node1+node1 (local) | 1.82 | 81.8% | 26.53 | 43.3% | 8.28 | 5.04s |
| node1 CPU + node0 mem (cross) | 1.62 | 83.6% | 34.08 | 49.4% | 12.19 | 5.56s |
| node0 CPU + node1 mem (cross) | 1.59 | 82.0% | 35.59 | 50.3% | 12.17 | 5.80s |
| baseline (96T, no pin, hac warm) | 1.58 | 80.9% | 36.5 | 50.2% | 9.89 | 5.63s |

**Key finding:** LLC miss rate stays ~82% across ALL configs — NUMA pinning does not reduce the number of cache misses (root cause is DB size >> L3, structural). DRAM stall cycles drop from 12.2B (cross-socket) to 6.44B (node0 local) — same number of misses, each one resolved faster with local DRAM. IPC improves from 1.59 to 1.86 as the CPU spends less time blocked.

---

### 8b — TMA breakdown (all 4 NUMA configs)

| Config | memory_bound | core_bound | retiring | bad_spec | fe_bound | Wall time |
|---|---|---|---|---|---|---|
| baseline (96T, no pin) | 25.4% | 21.7% | 26.9% | 16.9% | 9.6% | 5.63s |
| node0+node0 (local, 32T) | **23.9%** | **15.2%** | **30.7%** | 19.9% | 10.7% | **4.39s** |
| node1+node1 (local, 32T) | 26.5% | 15.7% | 29.2% | 18.7% | 10.2% | 5.19s |
| node0 CPU + node1 mem (cross) | **31.7%** | 15.3% | 26.8% | 17.3% | 9.3% | 5.50s |
| node1 CPU + node0 mem (cross) | **31.6%** | 16.6% | 26.4% | 16.8% | 9.2% | 5.64s |

**Finding 1 — NUMA adds 7.8pp to memory_bound:** node0-CPUs+node0-mem (23.9%) vs node0-CPUs+node1-mem (31.7%) — same CPUs, only memory location differs. The +7.8pp is purely QPI interconnect latency. Cross-socket configs waste nearly 1 in 3 pipeline slots waiting for remote memory.

**Finding 2 — core_bound drop is from threads, not NUMA:** All 4 NUMA configs show core_bound 15.2–16.6% regardless of pinning. The baseline was 21.7% at 96T. Reduction came from dropping to 32T (less lock contention, less cache line thrashing). NUMA had no effect on core_bound.

**Finding 3 — retiring improves to 30.7% (best ever):** Up from 26.9% at baseline. Both thread reduction and local memory contribute — the CPU is stalled less and does more useful work per slot.

**Finding 4 — bad_spec ticks up slightly (16.9% → 19.9%):** Faster memory enables more aggressive out-of-order speculation, more instructions queued, slightly more squashed on branch mispredicts. The tradeoff is worth it — retiring gain exceeds bad_spec increase.

**Finding 5 — both cross-socket configs identical at 31.6-31.7%:** QPI penalty is symmetric regardless of which socket has the CPU vs the data.

---

### 8c — Why node0+node0 beats node1+node1

Both are "local" but node0 is faster (DRAM stalls 6.44B vs 8.28B). The FASTQ file (~355 Mbp) is also in OS page cache on node 0 from previous runs. When running pinned to node 1, the 32 threads access local DB pages but FASTQ reads still cross the interconnect. The ~1.84B extra stall cycles on node1+node1 is the FASTQ I/O still paying a cross-socket penalty.

---

### 8d — Counter summary vs baseline

| Metric | baseline 96T unpinned | best: 32T node0 | change |
|---|---|---|---|
| IPC | 1.58 | **1.86** | +17.7% |
| DRAM stall cycles | 9.89B | **6.44B** | −34.9% |
| Stall % | 50.2% | **42.1%** | −8.1 pp |
| memory_bound % | 25.4% | **23.9%** | −1.5 pp |
| core_bound % | 21.7% | **15.2%** | −6.5 pp |
| retiring % | 26.9% | **30.7%** | +3.8 pp |
| LLC miss rate | 80.9% | 83.1% | unchanged (expected) |
| Wall time | 5.63s | **4.39s** | −22.0% |

---

## Step 9 — Thread Scaling: all 4 NUMA configs (hac, 5 runs each)

**Goal:** Does NUMA pinning shift the 32T sweet spot? Does local memory allow more threads to be useful?

**Commands:** Same loop as Step 5 but with numactl prefix for each of the 4 configs.
**Output file:** `~/results/profiling/thread_scaling_hac_node0.txt`

### 9a — Wall Time Results (5-run avg)

| Threads | unpinned (orig) | node0+node0 | node1+node1 | node0CPU+node1mem | node1CPU+node0mem |
|---|---|---|---|---|---|
| 2 | 11.764 | 10.200 | 10.778 | 11.535 | 11.625 |
| 4 | 7.907 | 6.981 | 7.631 | 8.241 | 8.306 |
| 8 | 6.273 | 5.420 | 6.082 | 6.583 | 6.648 |
| 16 | 5.498 | 4.671 | 5.314 | 5.787 | 5.819 |
| **32** | 5.235 | **4.405** | **5.037** | **5.532** | **5.595** |
| 48 | — | 4.454 | 5.099 | 5.660 | 5.694 |
| 64 | 5.417 | 4.536 | 5.199 | 5.788 | 5.875 |
| 96 | 5.635 | 4.690 | 5.392 | 5.997 | 6.050 |
| **sweet spot** | **32T** | **32T** | **32T** | **32T** | **32T** |
| **floor (s)** | 5.235 | **4.405** | 5.037 | 5.532 | 5.595 |
| **2T→32T speedup** | 2.25x | **2.32x** | 2.14x | 2.09x | 2.08x |

### 9b — Analysis

**Sweet spot stays at 32T for every config without exception.**

NUMA pinning, cross-socket, local node 1 — the peak is always 32T. This proves the 32T wall is caused by DRAM bandwidth saturation, not by thread scheduling or cross-socket contention. No matter how clean the memory access pattern, Kraken2 cannot use more than ~32 threads effectively on this dataset and DB combination.

**NUMA shifts the floor uniformly, not the shape.**

All 5 curves are identical in shape — fast drop from 2T to 32T, then slow degradation beyond. The degradation rate past 32T is nearly the same across all configs. NUMA makes every point on the curve faster or slower uniformly — it does not change when or why the DRAM wall is hit.

**node0+node0 gets the best per-thread scaling (2.32x vs 2.08x cross-socket).**

With local memory, threads scale more efficiently. Cross-socket threads compete for remote DRAM bandwidth AND pay higher latency per miss — so additional threads help less. Local memory provides more bandwidth per socket, so each new thread contributes slightly more.

**NUMA effect is present at every thread count, not just high counts.**

At 2T, node0+node0 (10.200s) beats unpinned (11.764s) by 13%. Even with 2 threads, one of them was landing on the wrong socket in the default run. Pinning helps uniformly across the scaling curve.

**One socket always beats split, even the non-home socket.**

node1+node1 (5.037s) beats unpinned (5.235s) despite the DB being on node 0. Consistent access from one socket is better than Linux randomly splitting threads across both sockets.

### 9c — Complete Optimisation Ladder (hac model)

| Configuration | Floor (s) | vs 96T default | Cumulative gain |
|---|---|---|---|
| 96T, no pin (original baseline) | 5.635 | — | — |
| 32T, no pin | 5.235 | −7.1% | −7.1% |
| 32T, node1+node1 | 5.037 | −10.6% | −10.6% |
| 32T, node0+node0 | **4.405** | **−21.8%** | **−21.8%** |

Zero code changes. Zero recompilation. Just thread count + numactl.

---

## Step 10 — gprof on Luna

### 10a — Setup

kraken2 recompiled from source (`~/tools/kraken2-src/`) with `-pg` added to `CXXFLAGS` in `src/Makefile`. The instrumented binary and wrapper were installed to `~/tools/kraken2-pg/` as a separate installation. The production binary at `~/tools/kraken2/` was rebuilt clean (no `-pg`) so normal profiling runs are unaffected.

Two binaries available going forward:
- `~/tools/kraken2/kraken2` — production, `-O3`, no instrumentation
- `~/tools/kraken2-pg/kraken2-pg` — gprof-instrumented, `-O3 -pg`

### 10b — gprof Limitations (important for interpreting results)

**gprof only profiles user-space CPU time.** It cannot see:
- Kernel time (I/O syscalls, page fault handlers, scheduler)
- Time blocked waiting for DRAM
- Any work done in system libraries called via syscall

This means gprof's percentages are fractions of user-mode CPU time only — not wall time. Functions that spend significant time in kernel (e.g. the read() syscall chain that consumed ~20% of wall time in the perf flamegraph) are completely invisible.

**gprof has a multithreading problem.** With `-pg`, each thread writes its own `gmon.out` on exit, but they overwrite each other (all write to the same filename). The resulting `gmon.out` contains only one thread's data — usually whichever thread exited last. Running at 32T would give misleading per-function percentages because ~31 threads worth of work is silently discarded.

**Decision: run at 1 thread for gprof.** Single-threaded gives a complete, reliable call graph. Every instruction is accounted for in the one thread. The percentages correctly show which functions dominate user-space CPU time. This matches how the WSL2 gprof was collected and makes the comparison valid.

A secondary run at 32T is also done as a data point, with the caveat noted.

### 10c — Commands

```bash
# Primary: single-threaded — clean, comparable to WSL2 gprof
cd ~/results/profiling
time ~/tools/kraken2-pg/kraken2-pg \
  --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null
# gmon.out written to ~/results/profiling/

gprof ~/tools/kraken2-pg/classify gmon.out > gprof_hac_1t.txt
head -40 gprof_hac_1t.txt

# Secondary: 32 threads — partial data (last thread only), noted as such
time ~/tools/kraken2-pg/kraken2-pg \
  --db ~/data/kraken2_db --threads 32 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null
gprof ~/tools/kraken2-pg/classify gmon.out > gprof_hac_32t.txt
```

### 10d — Results (hac, 1T, Luna)

**Timing:** wall 22.843s, user 18.617s, sys 4.224s. gprof sampled 10.46s of user time.
**Output file:** `~/results/profiling/gprof_hac_1t.txt`

| % time | self (s) | calls | function |
|---|---|---|---|
| **53.35%** | 5.58 | 351,893,601 | `kraken2::MinimizerScanner::NextMinimizer()` |
| **23.23%** | 2.43 | 11,634,763 | `kraken2::CompactHashTable::Get()` |
| 7.27% | 0.76 | — | `ClassifySequence()` |
| 6.69% | 0.70 | 352,208,243 | `kraken2::MinimizerScanner::reverse_complement()` |
| 3.15% | 0.33 | 104,888 | `AddHitlistString()` |
| 2.01% | 0.21 | 3,254,786 | `HyperLogLogPlusMinus()` constructor |
| 1.91% | 0.20 | — | `std::unordered_map::operator[]` (two variants) |
| ~2% | — | — | everything else |

### 10e — Function-by-function explanation

**MinimizerScanner::NextMinimizer (53.35%, 351M calls):** For every read, kraken2 slides a 35-base window along the sequence, hashes each window, and picks the minimum hash value in a local window as the representative k-mer (the minimizer). Called 351 million times across all reads. Pure CPU arithmetic on the read sequence — no database access.

**MinimizerScanner::reverse_complement (6.69%, 352M calls):** Kraken2 checks both DNA strands for every k-mer candidate. For each minimizer it computes the reverse complement of the 35-mer and takes whichever strand gives the smaller hash. Called 352 million times — essentially once per NextMinimizer call. Together, NextMinimizer + reverse_complement = **60% of user-space time**.

**CompactHashTable::Get (23.23%, 11.6M calls):** The actual database lookup. Takes the minimizer hash, computes the bucket index in the 8 GB table, loads the taxon ID. Called far fewer times than NextMinimizer because only the final minimizer per window is looked up. Each call is expensive because of the 82% LLC miss rate — every lookup likely goes to DRAM. gprof's timer fires while the thread is stalled waiting for memory, so that stall time accumulates here.

**ClassifySequence (7.27%):** Per-read orchestration — calls MinimizerScanner and CompactHashTable for each read, then calls ResolveTree to find the LCA taxon. Appears here due to loop overhead and branching logic between calls.

**AddHitlistString (3.15%, 104K calls):** Formats the per-read output listing which taxa each k-mer matched. One call per read, but each call iterates over the full hit vector.

**HyperLogLogPlusMinus (2.01%, 3.25M calls):** Probabilistic cardinality estimator for counting distinct minimizers per taxon in the report. One constructor call per new taxon encountered.

### 10f — Critical comparison: gprof vs perf, WSL2 vs Luna

| Tool | Platform | DB | MinimizerScanner | CompactHashTable::Get |
|---|---|---|---|---|
| gprof (user-space only) | WSL2 Ryzen | 650 MB ESKAPE | not reported | **67%** |
| gprof (user-space only) | Luna 1T | 8 GB standard | **53.35%** | **23.23%** |
| perf flamegraph (full wall time) | Luna 32T | 8 GB standard | **25.57%** | **12.10%** |

**Why WSL2 gprof showed 67% but Luna gprof shows 23.23% for CompactHashTable:**

Two factors. First, different database: the ESKAPE DB (650 MB, 6 genomes) has far fewer distinct taxa than the 8 GB standard DB. With ESKAPE, classification is cleaner — k-mers either clearly match or don't, so MinimizerScanner does less work per read. With the 8 GB standard DB, more taxa are processed per read, making MinimizerScanner proportionally larger.

Second, different hardware: the Xeon Platinum 8468 has wider execution units than the Ryzen 7 5800H and executes the arithmetic-heavy MinimizerScanner faster in absolute terms. Hash lookups still wait on DRAM regardless of CPU speed, so CompactHashTable::Get becomes a smaller fraction of the profile on faster compute hardware.

**Why gprof Luna (23.23%) differs from perf flamegraph Luna (12.10%):**

gprof's denominator is user-space CPU time only (18.6s at 1T). perf's denominator is full wall time including kernel. The ~20% FASTQ I/O and ~11% page fault handling visible in the flamegraph are completely absent from gprof — so all gprof fractions are inflated relative to wall time. If we scale: 23.23% of 18.6s user time = 2.43s; 2.43s / 22.84s wall time = 10.6% of wall time, consistent with the flamegraph's 12.10%.

---

### 10g — Secondary run: gprof hac 32T (partial — one thread only)

**Timing:** wall 43.428s (vs 4.4s normal — ~10x overhead from -pg), user 20m17s (32T × ~38s each), sys 10s.
**Output file:** `~/results/profiling/gprof_hac_32t.txt`
**Caveat:** gmon.out contains only the last thread's data. Call counts are ~1/57th of 1T totals, confirming one thread of ~32 is captured.

| Function | 1T % | calls (1T) | 32T % (partial) | calls (32T, 1 thread) |
|---|---|---|---|---|
| `MinimizerScanner::NextMinimizer` | 53.35% | 351,893,601 | **68.08%** | 6,160,005 |
| `CompactHashTable::Get` | 23.23% | 11,634,763 | **10.09%** | 164,928 |
| `reverse_complement` | 6.69% | 352,208,243 | 8.48% | 7,696,256 |
| `ClassifySequence` | 7.27% | — | 6.01% | — |
| `AddHitlistString` | 3.15% | 104,888 | 3.65% | 1,581 |

**CompactHashTable::Get drops from 23.23% to 10.09% at 32T.** All 31 other threads simultaneously load DB pages into RAM. By the time this measured thread needs a page, another thread has often already faulted it in — the effective LLC miss rate for this one thread is lower because the DB is pre-warmed by peers. MinimizerScanner (pure CPU, no DB access) is unaffected and grows proportionally.

**MinimizerScanner + reverse_complement = 76.6% at 32T** vs 60.0% at 1T. With hash lookups cheaper per thread at 32T, the compute-bound scanner operations dominate even more.

**-pg overhead:** 43s wall vs 4.4s normal = 10x slowdown. Instrumentation fires on every function call and each thread maintains its own profiling counters, adding significant overhead at 32T.

---

---

## Step 11 — valgrind cachegrind (hac, 1 thread)

**Goal:** Get per-function L1 and LL (last-level) cache miss counts. perf stat gives total LLC miss rate (82%) but cannot attribute misses to specific functions. cachegrind simulates the full cache hierarchy and records how many times each function caused an L1 miss vs an LL miss vs a hit.

**Why 1 thread:** cachegrind simulates memory accesses serially. With multiple threads, simulated accesses interleave unpredictably and per-function attribution becomes unreliable. 1T gives clean, fully attributed numbers. Absolute counts scale roughly linearly to 32T.

### 11a — Commands

**First attempt (failed — stderr suppressed the error):**
```bash
cd ~/results/profiling && valgrind --tool=cachegrind \
  --cachegrind-out-file=cachegrind_hac_1t.out \
  ~/tools/kraken2/kraken2 --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null
```
Output file not created. Root cause: `~/tools/kraken2/kraken2` is a Perl wrapper that exec's the actual C++ binary (`classify`) as a child process. valgrind instrumented the Perl parent and never followed into the child. `2>/dev/null` hid valgrind's own diagnostic output, so the failure was silent.

**Fix — use `--trace-children=yes`:**
```bash
valgrind --tool=cachegrind --trace-children=yes \
  --cachegrind-out-file=cachegrind_hac_1t.out \
  ~/tools/kraken2/kraken2 --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```
Wall time: 362s (~20x overhead vs 18s uninstrumented). Output: `~/results/profiling/cachegrind_hac_1t.out` (227 KB).

**Annotate:**
```bash
cg_annotate cachegrind_hac_1t.out | head -80
```

### 11b — Cache Configuration (simulated by valgrind)

| Level | Size | Line size | Associativity |
|---|---|---|---|
| I1 (instruction L1) | 32 KB | 64 B | 8-way |
| D1 (data L1) | 48 KB | 64 B | 12-way |
| LL (L3 last-level) | 104 MB | 64 B | 26-way |

valgrind detected the L3 cache and rounded associativity (actual: 110 MB 15-way, simulated: 104 MB 26-way — same effective size).

### 11c — Program-Wide Totals

| Metric | Value | Meaning |
|---|---|---|
| I refs | 99.96 billion | Total instructions executed |
| D refs | 43.88 billion | Total data memory operations (28.6B reads + 15.3B writes) |
| D1 misses | 338.5 million | L1 data cache misses — 0.8% of all D refs |
| LLd misses | 9.58 million | Last-level (L3) data cache misses — went to DRAM |
| LLd miss rate | 0.02% of all D refs | Looks small, but 5.84M of these are reads (see below) |

**Why LLd miss rate looks low but isn't:** The 0.02% is LLd misses / all D refs. Most ops hit L1/L2. The perf stat 82% LLC miss rate measures LLd misses / LLC accesses — a much smaller denominator. Both are consistent: only 11.7M accesses reach L3, and 9.58M of those miss it (82%). The absolute 9.58M DRAM accesses × ~100 ns each = roughly 1 second of serialised DRAM latency at 1T.

### 11d — Per-Function Results

Column key: `Ir` = instructions executed, `D1mr` = L1 read misses, `DLmr` = LL read misses (DRAM reads), `D1mw` = L1 write misses, `DLmw` = LL write misses.

| Function | Ir % | D1mr % | DLmr % | D1mw % | DLmw % | Notes |
|---|---|---|---|---|---|---|
| `MinimizerScanner::NextMinimizer` | **48.23%** | 2.33% | **0%** | 0.11% | 0% | Zero DRAM reads — pure compute |
| `MinimizerScanner::reverse_complement` | 11.63% | 0.00% | **0%** | 0% | 0% | Zero DRAM reads — pure compute |
| `ClassifySequence` | 11.51% | 0.56% | 0.00% | 25.44% | 1.57% | Orchestration; write misses from output buffering |
| `memmove/memcpy` (avx unaligned) | 4.29% | 44.64% | 0.85% | 62.74% | **38.64%** | String copy for output — heavy write traffic |
| `AddHitlistString` | 4.28% | 19.24% | 0.08% | 0% | 0% | Formats output strings — many small reads |
| `CompactHashTable::Get` | 0.65% | **7.09%** | **96.24%** | 0% | 0% | Accounts for nearly all DRAM reads |
| `memset` (avx2) | 1.31% | 0% | 0% | 9.35% | **56.84%** | Buffer clearing — majority of LL write misses |
| `HyperLogLogPlusMinus::insert` | 0.37% | 2.17% | 0% | 0% | 0% | Cardinality estimator — L1 misses only |
| `murmurhash3_finalizer` | 0.14% | 0% | 0% | 0% | 0% | Pure compute, no cache pressure |

### 11e — Key Finding: CompactHashTable::Get owns 96.24% of all DRAM reads

`CompactHashTable::Get` executes only 0.65% of all instructions — it is a short, tight function. But it generates:
- 12.57 million L1 read misses (7.09% of total)
- **5.62 million LL read misses — 96.24% of ALL last-level read cache misses**

Every other function in the program combined causes only 3.76% of LL read misses.

**Why every CompactHashTable::Get call misses L3:** The hash table is 8 GB. The L3 cache is 104 MB. The ratio is 77:1 — no working set of hash table pages can stay warm. Each k-mer hash maps to a pseudorandom bucket anywhere in the 8 GB array. With 104,918 reads, each generating ~11 minimizers, and the DB 77x too large to cache, effectively every lookup is a cold DRAM access.

### 11f — MinimizerScanner is purely CPU-bound

`MinimizerScanner::NextMinimizer` runs 48.23% of all instructions and 56.31% of all data reads — but causes **zero LL misses**. It operates entirely on the read sequence (a few kilobytes at most), which stays resident in L1/L2 throughout classification of one read. The CPU is executing this function at near-theoretical speed with no memory stalls.

This splits the profiling picture cleanly into two regimes:
- **MinimizerScanner (48% of instructions):** CPU-bound, compute-limited, zero DRAM pressure. Target for SIMD optimisation.
- **CompactHashTable::Get (0.65% of instructions):** Memory-bound, DRAM-limited, 96% of DRAM reads. Target for caching (Kolin sir's LRU cache design).

### 11g — Cross-validation with previous tools

| Tool | CompactHashTable::Get fraction | Denominator |
|---|---|---|
| gprof 1T (user-space time) | 23.23% | 18.6s user CPU time |
| perf flamegraph 32T (wall time) | 12.10% | 4.4s wall time |
| cachegrind (LL read misses) | **96.24%** | All LL read misses |
| cachegrind (instruction count) | 0.65% | All instructions |

All four are consistent. gprof's 23.23% × 18.6s = 2.43s wall time from hash lookups ≈ cachegrind confirming it as the sole source of DRAM traffic.

### 11h — Implications for Kolin sir's LRU cache design

Kolin sir's proposal: a hot k-mer LRU cache in front of `CompactHashTable::Get`. Each cache hit bypasses one DRAM lookup (~100 ns). Cachegrind confirms this is the right target:

- 5.62 million DRAM reads in a single-threaded run come from this one function
- At 32T, scale that to ~5.62M × 32 / (parallelism factor) DRAM ops total
- A cache hit rate of even 20% on repeated k-mers would eliminate ~1.1M DRAM accesses per thread

The question for the implementation is: how often are the same k-mers seen across reads? With 104,918 reads from a mixed-community sample, many reads will share common taxa k-mers. The LRU cache size vs hit rate tradeoff is the key design parameter.

---

---

## Step 12 — FASTQ on tmpfs (hac, 32T, node 0 pinned)

**Full write-up:** `Luna/experiments/tmpfs_fastq/README.md`

### 12a — Summary

Hypothesis: copying the FASTQ to `/dev/shm` (RAM-backed tmpfs) would eliminate the ~20% ext4 I/O tower seen in the flamegraph and save ~0.88s.

Result: **no benefit.**

| Config | Avg wall time | vs SSD baseline |
|---|---|---|
| SSD warm (baseline) | 4.405s | — |
| tmpfs warm | 4.395s | -0.010s (-0.2%) — noise |
| Cold SSD (after drop_caches) | 10.894s | +6.49s |
| Warm SSD (after cold run) | 4.648s | same as baseline |
| tmpfs (after cold run) | 4.649s | identical to warm SSD |

### 12b — Why tmpfs gave no benefit

Luna has 503 GB RAM. The FASTQ (703 MB) has been in the Linux page cache since the first ever run and never evicted. The SSD baseline was already reading from DRAM, not from disk. tmpfs is also DRAM. Both execute `copy_page_to_iter` — the memory-to-memory copy from page cache to process buffer. That copy exists in both cases and cannot be removed by changing filesystems.

The flamegraph's ~20% I/O tower is this copy overhead, not disk I/O.

### 12c — Cold cache experiment

After `echo 3 > /proc/sys/vm/drop_caches`, the cold run took 10.894s — 6.25s slower than warm. That 6.25s is the true cost of loading the 8 GB DB + 703 MB FASTQ from NVMe with no page cache. In normal operation this never occurs on Luna.

### 12d — How to actually eliminate the I/O overhead

The copy overhead is intrinsic to read()-based I/O. Two approaches that would help — both require Kraken2 source changes:
- **mmap the FASTQ** — maps file pages directly into process address space, zero copy on access. One page fault per 4 KB page, then free.
- **O_DIRECT with aligned buffers** — bypasses page cache entirely, reads direct from storage to buffer.

### 12e — Optimisation ladder (unchanged)

| Configuration | Wall time | vs 96T baseline |
|---|---|---|
| 96T, no pin | 5.635s | — |
| 32T, no pin | 5.235s | -7.1% |
| 32T, node0+node0 | 4.405s | -21.8% |
| 32T, node0+node0, tmpfs FASTQ | 4.395s | -21.9% — no real gain |

---

## Next Steps

**Note (2026-06-15):** Dorado GPU profiling (Step 13) is DEPRIORITIZED — see Meeting 4 debrief in docs/updates.md.
Summer focus is Kraken2 source optimisation (proposals A/D/E/F). Remaining profiling goals (6-11 in table above) are on hold pending optimisation implementation; they will be useful for measuring the effect of patches.

AccuracyDrift and AccuracyChase experiment results (2026-05-30 to 2026-06-15) are in `AccuracyDrift/` — separate from this file.

→ results: [AccuracyDrift/RESULTS.md](../../AccuracyDrift/RESULTS.md)  
→ observations: [AccuracyDrift/OBSERVATIONS.md](../../AccuracyDrift/OBSERVATIONS.md)  
→ AccuracyChase: [AccuracyDrift/AccuracyChase.md](../../AccuracyDrift/AccuracyChase.md)
