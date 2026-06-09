# AccuracyDrift — Minerva Results

**Date:** 2026-06-09
**Machine:** Minerva — Intel Xeon Gold 6330 @ 2.0 GHz, 112 threads (2-socket, 56c each), 251 GB RAM, ~42 MB L3 per socket
**Databases:** eskape_650mb (142 MB), eskape_human_4gb (3.8 GB), standard_8gb (7.6 GB), standard_16gb (15 GB)
**Reads:** reads_fast (104,832), reads_hac (104,918), reads_sup (104,980)
**Thread sweep:** 1, 2, 4, 8, 16
**Runs per combo:** 3 (values are averages)
**Note:** No numactl — not installed, no sudo. OS may schedule across both NUMA nodes at high thread counts.

---

## Section 1: Per-Read × Per-DB Thread Scaling

### reads_fast — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 61.77 | 38.23 | 67.20 | 67.73 | 240.810 | 1.00x | 0.90 |
| 2  | 61.77 | 38.23 | 66.70 | 66.53 | 120.794 | 1.99x | 0.91 |
| 4  | 61.77 | 38.23 | 65.27 | 64.85 |  61.628 | 3.91x | 0.92 |
| 8  | 61.77 | 38.23 | 63.29 | 63.30 |  31.652 | 7.61x | 0.91 |
| 16 | 61.77 | 38.23 | 60.74 | 61.21 |  17.755 | 13.56x | 0.91 |

**Observations:**
- Good near-linear scaling up to 16T (13.56x) — eskape_650mb is small enough that threads partition the read set effectively
- LLC miss rate drops from 67.73% → 61.21% as threads increase — each thread works on a smaller read slice, improving per-thread cache reuse
- IPC flat at ~0.91 across all thread counts — memory-bound but consistent
- Only 61.77% classified — fast basecalling model produces lower-quality reads, harder to match k-mers

---

### reads_fast — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 62.27 | 37.73 | 63.58 | 82.95 | 283.754 | 1.00x | 0.82 |
| 2  | 62.27 | 37.73 | 63.53 | 81.89 | 163.846 | 1.73x | 0.82 |
| 4  | 62.27 | 37.73 | 62.19 | 78.87 |  87.406 | 3.25x | 0.83 |
| 8  | 62.27 | 37.73 | 60.54 | 74.82 |  53.780 | 5.28x | 0.84 |
| 16 | 62.27 | 37.73 | 58.42 | 69.94 |  33.803 | 8.39x | 0.85 |

**Observations:**
- Scaling degrades vs eskape_650mb — only 8.39x at 16T due to higher memory pressure
- LLC miss rate is the highest of all 4 DBs (82.95% at 1T) despite not being the largest — the combined ESKAPE + human k-mer space is highly diverse, causing random DRAM access patterns
- LLC miss rate drops significantly with threads (82.95% → 69.94%) — same partitioning effect as eskape_650mb but starting from a much higher baseline
- IPC slightly improves with more threads (0.82 → 0.85) as LLC miss rate reduces

---

### reads_fast — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 82.66 | 17.34 | 34.47 | 51.69 | 188.914 | 1.00x | 1.16 |
| 2  | 82.66 | 17.34 | 35.47 | 52.63 | 127.037 | 1.49x | 1.13 |
| 4  | 82.66 | 17.34 | 34.80 | 52.13 |  70.727 | 2.67x | 1.16 |
| 8  | 82.66 | 17.34 | 34.22 | 50.33 |  57.892 | 3.26x | 1.13 |
| 16 | 82.66 | 17.34 | 34.17 | 51.19 |  51.175 | 3.69x | 1.13 |

**Observations:**
- Poor scaling — only 3.69x at 16T; speedup essentially plateaus after 8T
- LLC miss rate flat at ~51% across all thread counts — fully DRAM-bound, adding threads does not improve cache utilisation
- Despite being larger (7.6 GB), LLC miss rate is lower than eskape_human_4gb (51% vs 83%) — standard DB k-mers are more repetitive and cache-friendly
- Highest classified% for fast reads (82.66%) — standard DB covers far more species than ESKAPE-targeted DBs
- IPC ~1.13–1.16, highest of fast read runs — more compute per memory access due to better cache hit rate

---

### reads_fast — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 90.44 | 9.56 | 35.43 | 53.51 | 263.872 | 1.00x | 1.06 |
| 2  | 90.44 | 9.56 | 35.24 | 50.78 | 196.132 | 1.35x | 0.98 |
| 4  | 90.44 | 9.56 | 35.71 | 52.79 | 121.883 | 2.16x | 1.04 |
| 8  | 90.44 | 9.56 | 35.15 | 51.85 | 106.373 | 2.48x | 1.02 |
| 16 | 90.44 | 9.56 | 35.17 | 52.30 |  87.034 | 3.03x | 1.03 |

**Observations:**
- Worst scaling of all DBs — only 3.03x at 16T; speedup nearly flat from 8T → 16T (2.48x → 3.03x)
- LLC miss rate flat ~51–53% — fully memory-bandwidth limited, no improvement with more threads
- Classified% improves to 90.44% vs standard_8gb's 82.66% — 16 GB DB captures more species
- Compared to standard_8gb, runtime is longer (263s vs 188s at 1T) for a 7.8 pp accuracy gain — diminishing returns on DB size

---

### reads_hac — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 65.28 | 34.72 | 63.78 | 68.58 | 233.341 | 1.00x | 0.93 |
| 2  | 65.28 | 34.72 | 63.43 | 68.11 | 119.280 | 1.96x | 0.94 |
| 4  | 65.28 | 34.72 | 61.88 | 65.95 |  59.476 | 3.92x | 0.95 |
| 8  | 65.28 | 34.72 | 59.84 | 64.20 |  31.217 | 7.47x | 0.94 |
| 16 | 65.28 | 34.72 | 57.69 | 62.61 |  16.702 | 13.97x | 0.96 |

**Observations:**
- Best scaling on Minerva — 13.97x at 16T, near-linear
- LLC miss rate decreases steadily (68.58% → 62.61%) confirming per-thread working set shrinkage
- HAC reads classify slightly better than fast (65.28% vs 61.77%) — higher basecalling quality produces cleaner k-mers
- IPC slightly improves with threads (0.93 → 0.96) as cache pressure reduces

---

### reads_hac — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 66.13 | 33.87 | 61.89 | 83.25 | 290.837 | 1.00x | 0.87 |
| 2  | 66.13 | 33.87 | 59.75 | 79.76 | 173.964 | 1.67x | 0.85 |
| 4  | 66.13 | 33.87 | 58.60 | 77.26 |  91.464 | 3.18x | 0.86 |
| 8  | 66.13 | 33.87 | 56.35 | 72.24 |  55.849 | 5.21x | 0.88 |
| 16 | 66.13 | 33.87 | 53.68 | 66.38 |  36.756 | 7.91x | 0.91 |

**Observations:**
- Scaling limited to 7.91x at 16T — memory bandwidth bottleneck from high LLC miss rate
- Largest LLC miss rate improvement with threading of any DB (83.25% → 66.38%, 16.87 pp drop) — but still high at 16T
- Only 0.85% gain in classified% over eskape_650mb (66.13% vs 65.28%) — adding human genome to DB barely helps classify ESKAPE reads
- Lowest IPC at 1T (0.87) — most memory-stalled DB

---

### reads_hac — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 95.77 | 4.23 | 33.63 | 50.70 | 210.856 | 1.00x | 1.18 |
| 2  | 95.77 | 4.23 | 33.54 | 50.63 | 122.045 | 1.73x | 1.18 |
| 4  | 95.77 | 4.23 | 33.32 | 50.07 |  78.292 | 2.69x | 1.19 |
| 8  | 95.77 | 4.23 | 32.94 | 50.06 |  56.754 | 3.72x | 1.19 |
| 16 | 95.77 | 4.23 | 32.77 | 49.75 |  45.959 | 4.59x | 1.19 |

**Observations:**
- Scaling plateaus at 4.59x (16T) — memory-bound ceiling reached early
- LLC miss rate nearly flat (50.70% → 49.75%) — no benefit from thread partitioning; DB is too large to fit in cache regardless
- 95.77% classified — dramatic jump from eskape DBs (~65%), confirming standard DB covers ESKAPE species well
- IPC most stable of all DBs (~1.18–1.19) — consistent memory access pattern

---

### reads_hac — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 97.77 | 2.23 | 33.73 | 50.36 | 291.222 | 1.00x | 1.09 |
| 2  | 97.77 | 2.23 | 34.54 | 51.16 | 183.297 | 1.59x | 1.07 |
| 4  | 97.77 | 2.23 | 34.86 | 50.54 | 132.343 | 2.20x | 1.05 |
| 8  | 97.77 | 2.23 | 35.40 | 52.63 |  96.181 | 3.03x | 1.11 |
| 16 | 97.77 | 2.23 | 35.10 | 52.11 |  85.997 | 3.39x | 1.08 |

**Observations:**
- Worst scaling of all hac runs — 3.39x at 16T
- LLC miss rate completely flat (~50–53%) regardless of thread count — pure memory bandwidth wall
- Classified% 97.77% — only 2 pp gain over standard_8gb (95.77%) for a 2x larger DB and 38% longer runtime at 1T
- Diminishing returns: standard_16gb adds marginal accuracy at significant cost in time and memory

---

### reads_sup — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 65.87 | 34.13 | 62.07 | 68.61 | 240.432 | 1.00x | 0.94 |
| 2  | 65.87 | 34.13 | 63.37 | 71.87 | 129.464 | 1.86x | 0.93 |
| 4  | 65.87 | 34.13 | 61.52 | 67.60 |  64.046 | 3.75x | 0.95 |
| 8  | 65.87 | 34.13 | 60.02 | 65.82 |  33.934 | 7.09x | 0.94 |
| 16 | 65.87 | 34.13 | 58.71 | 65.00 |  18.366 | 13.09x | 0.95 |

**Observations:**
- Good scaling (13.09x at 16T), consistent with hac and fast on this DB
- LLC miss rate at 2T (71.87%) is slightly higher than 1T (68.61%) — minor NUMA cross-traffic effect at low thread count (no numactl)
- SUP classified% (65.87%) only marginally better than HAC (65.28%) on eskape_650mb — DB coverage is the limiting factor, not read quality

---

### reads_sup — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 66.68 | 33.32 | 59.36 | 84.75 | 335.556 | 1.00x | 0.85 |
| 2  | 66.68 | 33.32 | 58.03 | 79.31 | 182.635 | 1.84x | 0.87 |
| 4  | 66.68 | 33.32 | 56.58 | 76.48 | 101.859 | 3.29x | 0.87 |
| 8  | 66.68 | 33.32 | 53.56 | 69.12 |  54.803 | 6.12x | 0.92 |
| 16 | 66.68 | 33.32 | 51.82 | 64.44 |  40.243 | 8.34x | 0.94 |

**Observations:**
- Highest 1T runtime of all sup runs (335.556s) — sup reads are longer, more k-mers per read, more DRAM accesses on a high-miss-rate DB
- LLC miss rate drops most aggressively with threads (84.75% → 64.44%, 20 pp) — largest per-thread working set reduction
- IPC improves most with threads (0.85 → 0.94) — confirms memory pressure reduction directly translates to better CPU utilisation
- Classified% 66.68% — only 0.81% better than hac on same DB

---

### reads_sup — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 97.09 | 2.91 | 36.65 | 55.92 | 261.682 | 1.00x | 1.14 |
| 2  | 97.09 | 2.91 | 36.71 | 54.56 | 140.225 | 1.87x | 1.15 |
| 4  | 97.09 | 2.91 | 36.12 | 54.22 |  94.794 | 2.76x | 1.15 |
| 8  | 97.09 | 2.91 | 34.70 | 53.61 |  65.653 | 3.99x | 1.18 |
| 16 | 97.09 | 2.91 | 34.57 | 52.25 |  50.978 | 5.13x | 1.20 |

**Observations:**
- Best scaling among standard DB runs (5.13x at 16T) — sup reads are longer, more compute per read
- LLC miss rate shows slight improvement with threads (55.92% → 52.25%) unlike hac/standard_8gb where it was flat — sup reads generate more k-mers per read, giving more opportunity for cache reuse
- 97.09% classified — near-complete classification; standard_8gb is sufficient for sup reads

---

### reads_sup — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 98.48 | 1.52 | 36.33 | 53.05 | 364.086 | 1.00x | 1.03 |
| 2  | 98.48 | 1.52 | 37.45 | 52.90 | 224.592 | 1.62x | 1.04 |
| 4  | 98.48 | 1.52 | 36.45 | 53.02 | 145.153 | 2.51x | 1.04 |
| 8  | 98.48 | 1.52 | 35.60 | 52.33 | 115.418 | 3.15x | 1.08 |
| 16 | 98.48 | 1.52 | 35.28 | 52.41 |  95.479 | 3.81x | 1.09 |

**Observations:**
- Highest 1T runtime of any run (364.086s) — largest DB + longest reads = maximum DRAM traffic
- Scaling only 3.81x at 16T — memory bandwidth fully saturated
- 98.48% classified — only 1.39 pp gain over standard_8gb for 39% longer runtime at 1T
- IPC flat ~1.03–1.09 — memory wall is hard

---

## Section 2: Final Observations

### F1 — Thread scaling is governed entirely by LLC miss rate

| DB | LLC Miss% (1T, hac) | Speedup at 16T (hac) |
|----|--------------------:|---------------------:|
| eskape_650mb | 68.58 | 13.97x |
| eskape_human_4gb | 83.25 | 7.91x |
| standard_8gb | 50.70 | 4.59x |
| standard_16gb | 50.36 | 3.39x |

- DBs with flat LLC miss rate (standard_8gb, standard_16gb) scale poorly — memory bandwidth is already saturated at 1T
- DBs where LLC miss rate decreases with threads (eskape_650mb, eskape_human_4gb) scale better — threads partition the read set and reduce per-thread DRAM pressure
- Minerva's small L3 (~42 MB) means no DB fits in cache, making it more memory-bound than Luna

---

### F2 — Minerva is ~10x slower than Luna for cache-sensitive workloads

| Machine | LLC Miss% (hac, eskape_650mb, 1T) | Time 1T (s) |
|---------|----------------------------------:|------------:|
| Luna | 30.70 | 21.98 |
| Minerva | 68.58 | 233.34 |

- Luna's 210 MB L3 cache holds the 142 MB eskape_650mb DB almost entirely → 30% miss rate → fast
- Minerva's 42 MB L3 cannot hold any DB → all runs are DRAM-bound from the start
- For larger DBs (standard_8gb, standard_16gb) both machines are DRAM-bound — performance gap narrows

---

### F3 — DB size vs classified%: standard_8gb is the practical sweet spot

| DB | hac classified% | sup classified% |
|----|----------------:|----------------:|
| eskape_650mb | 65.28 | 65.87 |
| eskape_human_4gb | 66.13 | 66.68 |
| standard_8gb | 95.77 | 97.09 |
| standard_16gb | 97.77 | 98.48 |

- eskape → eskape_human: +0.85 pp gain for ~20x larger DB — not worth it for classification
- standard_8gb → standard_16gb: +2.0 pp (hac) / +1.39 pp (sup) for 2x larger DB and ~38% more runtime — marginal
- standard_8gb gives the best accuracy-to-cost ratio on Minerva

---

### F4 — Read model matters more for small DBs than large DBs

| DB | fast classified% | hac classified% | sup classified% | Range |
|----|----------------:|----------------:|----------------:|------:|
| eskape_650mb | 61.77 | 65.28 | 65.87 | 4.1 pp |
| eskape_human_4gb | 62.27 | 66.13 | 66.68 | 4.4 pp |
| standard_8gb | 82.66 | 95.77 | 97.09 | 14.4 pp |
| standard_16gb | 90.44 | 97.77 | 98.48 | 8.0 pp |

- Fast reads are significantly penalised on standard DBs (14.4 pp gap vs hac/sup on standard_8gb)
- For ESKAPE-targeted DBs the gap is small (~4 pp) — DB coverage is the bottleneck, not read quality
- SUP and HAC are nearly equivalent on large DBs — HAC is sufficient, SUP offers marginal gain

---

### F5 — eskape_human_4gb has anomalously high LLC miss rate

- Despite being smaller than standard_8gb (3.8 GB vs 7.6 GB), eskape_human_4gb has higher LLC miss rate (83% vs 51%)
- Standard DBs contain many common, repetitive organisms — k-mer lookups cluster in hot cache lines
- ESKAPE + human DB combines two distinct k-mer spaces — highly diverse, non-repetitive access pattern → more cache misses per lookup
- This makes eskape_human_4gb the worst-performing DB per classified read on Minerva
