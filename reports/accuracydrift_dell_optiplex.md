# AccuracyDrift — Dell OptiPlex 5090 Results

**Date:** 2026-06-12
**Machine:** Dell OptiPlex 5090 — Intel Core i7-11700 @ 2.5 GHz (4.9 GHz boost), 16 threads (1-socket, 8c + HT), 16 MB L3 (shared)
**Databases:** eskape_51mb (51 MB, custom sample-targeted), eskape_650mb (142 MB), eskape_human_4gb (3.8 GB), standard_8gb (7.6 GB), standard_16gb (15 GB)
**Reads:** reads_fast (104,832), reads_hac (104,918), reads_sup (104,980)
**Thread sweep:** 1, 2, 4, 8, 16
**Runs per combo:** 3 (values are averages)
**Note:** Single socket, 1 NUMA node — no cross-socket traffic. 8 physical cores; **16T runs on hyperthreads (2 threads/core)**. Dedicated desktop, warmup run discarded before each sweep.

---

## Section 1: Per-Read × Per-DB Thread Scaling

### reads_fast — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 61.77 | 38.23 | 69.22 | 56.11 | 18.651 | 1.00x | 1.22 |
| 2  | 61.77 | 38.23 | 69.46 | 56.50 |  9.998 | 1.87x | 1.20 |
| 4  | 61.77 | 38.23 | 70.51 | 57.40 |  5.489 | 3.40x | 1.17 |
| 8  | 61.77 | 38.23 | 70.10 | 56.85 |  3.034 | 6.15x | 1.22 |
| 16 | 61.77 | 38.23 | 67.13 | 57.02 |  2.400 | 7.77x | 1.00 |

**Observations:**
- Near-linear to 8T (6.15x); 8T→16T adds only 6.15x→7.77x — the 8-physical-core ceiling, with hyperthreading giving the last bit
- LLC miss rate flat ~56-57% across all thread counts — the 16 MB L3 cannot hold the 142 MB DB, so partitioning the read set does not lower per-thread miss rate (contrast Minerva's larger L3, where it dropped)
- IPC holds ~1.20 from 1T→8T then drops to 1.00 at 16T — two hyperthreads per core compete for execution units
- Only 61.77% classified — fast basecalling model produces lower-quality reads, harder to match k-mers

---

### reads_fast — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 62.27 | 37.73 | 78.30 | 77.49 | 22.701 | 1.00x | 1.08 |
| 2  | 62.27 | 37.73 | 78.34 | 77.52 | 12.547 | 1.81x | 1.06 |
| 4  | 62.27 | 37.73 | 78.48 | 77.29 |  7.120 | 3.19x | 1.05 |
| 8  | 62.27 | 37.73 | 78.87 | 77.91 |  4.783 | 4.75x | 1.09 |
| 16 | 62.27 | 37.73 | 72.38 | 72.28 |  3.472 | 6.54x | 0.95 |

**Observations:**
- Scales worse than eskape_650mb — 6.54x at 16T — higher memory pressure from a more diverse k-mer space
- Highest cache-miss (~78%) and LLC-miss (~77%) of all fast runs — combined ESKAPE + human k-mer space gives random, non-repetitive DRAM access
- Miss rate only drops at 16T (77.9%→72.3%); below that it is flat — partitioning helps only once 16 threads slice the read set finely enough
- Lowest IPC of the fast runs (~1.05-1.08), collapsing to 0.95 at 16T — most memory-stalled DB

---

### reads_fast — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 82.66 | 17.34 | 64.67 | 65.19 | 11.416 | 1.00x | 2.04 |
| 2  | 82.66 | 17.34 | 65.10 | 65.16 |  7.057 | 1.62x | 2.02 |
| 4  | 82.66 | 17.34 | 66.38 | 67.76 |  4.745 | 2.41x | 1.98 |
| 8  | 82.66 | 17.34 | 67.70 | 71.00 |  3.811 | 3.00x | 1.95 |
| 16 | 82.66 | 17.34 | 66.22 | 69.71 |  3.409 | 3.35x | 1.42 |

**Observations:**
- Poor scaling — 3.35x at 16T; plateaus after 8T (3.00x→3.35x), hyperthreading adds almost nothing
- Despite a ~65% cache-miss rate, IPC is the highest of the fast runs (2.04 at 1T) — standard-DB k-mer lookups pipeline well (high memory-level parallelism), so misses overlap instead of serialising
- Fastest 1T runtime of all fast runs (11.4s) even though it is a 7.6 GB DB — efficiency comes from access pattern, not cache residency
- IPC collapses 1.95→1.42 from 8T→16T — bandwidth saturated, HT only adds contention

---

### reads_fast — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 90.44 | 9.56 | 65.94 | 68.36 | 18.079 | 1.00x | 1.63 |
| 2  | 90.44 | 9.56 | 66.49 | 69.13 | 11.838 | 1.53x | 1.62 |
| 4  | 90.44 | 9.56 | 67.06 | 69.85 |  8.614 | 2.10x | 1.59 |
| 8  | 90.44 | 9.56 | 67.75 | 71.38 |  7.198 | 2.51x | 1.55 |
| 16 | 90.44 | 9.56 | 67.45 | 71.31 |  6.607 | 2.74x | 1.24 |

**Observations:**
- Worst scaling of all fast runs — 2.74x at 16T; bandwidth-bound from 1T
- LLC miss rate flat ~68-71% — 15 GB working set blows the 16 MB L3 entirely, threads cannot reduce it
- Classified% 90.44% vs standard_8gb's 82.66% — 16 GB DB captures more species, but 1T runtime is 58% longer (18.1s vs 11.4s) for a 7.8 pp gain
- IPC lower than standard_8gb (1.63 vs 2.04) — larger DB lowers MLP

---

### reads_hac — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 65.28 | 34.72 | 66.14 | 56.50 | 18.155 | 1.00x | 1.30 |
| 2  | 65.28 | 34.72 | 66.84 | 57.02 |  9.449 | 1.92x | 1.27 |
| 4  | 65.28 | 34.72 | 67.30 | 57.29 |  5.209 | 3.49x | 1.26 |
| 8  | 65.28 | 34.72 | 67.11 | 57.01 |  3.271 | 5.55x | 1.36 |
| 16 | 65.28 | 34.72 | 63.98 | 56.75 |  2.238 | 8.11x | 1.08 |

**Observations:**
- Best scaling on Dell — 8.11x at 16T; the clearest hyperthreading win (8T 5.55x → 16T 8.11x, a 1.46x jump)
- HT pays off here because this small DB is latency-bound, not bandwidth-bound — the second hyperthread hides memory stalls of the first
- LLC miss rate flat ~56-57% — no partitioning benefit, just better latency hiding
- HAC classifies slightly better than fast (65.28% vs 61.77%) — higher basecalling quality, cleaner k-mers

---

### reads_hac — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 66.13 | 33.87 | 74.26 | 72.51 | 21.756 | 1.00x | 1.20 |
| 2  | 66.13 | 33.87 | 74.45 | 72.78 | 11.974 | 1.82x | 1.18 |
| 4  | 66.13 | 33.87 | 74.78 | 73.10 |  6.785 | 3.21x | 1.17 |
| 8  | 66.13 | 33.87 | 75.05 | 73.56 |  4.569 | 4.76x | 1.22 |
| 16 | 66.13 | 33.87 | 69.51 | 69.83 |  3.391 | 6.42x | 1.04 |

**Observations:**
- 6.42x at 16T — limited by the high LLC miss rate (highest of the hac runs)
- Miss rate only drops at 16T (73.6%→69.8%) — diverse k-mer space resists cache reuse until reads are finely partitioned
- Only 0.85 pp gain in classified% over eskape_650mb (66.13% vs 65.28%) — adding the human genome barely helps classify ESKAPE reads
- IPC ~1.20, lowest of the hac small/medium DBs — memory-stalled

---

### reads_hac — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 95.77 | 4.23 | 63.13 | 63.29 | 11.524 | 1.00x | 2.17 |
| 2  | 95.77 | 4.23 | 64.10 | 64.75 |  7.069 | 1.63x | 2.14 |
| 4  | 95.77 | 4.23 | 64.99 | 66.62 |  4.730 | 2.44x | 2.11 |
| 8  | 95.77 | 4.23 | 66.11 | 69.14 |  3.755 | 3.07x | 2.07 |
| 16 | 95.77 | 4.23 | 65.20 | 67.04 |  3.421 | 3.37x | 1.46 |

**Observations:**
- Scaling plateaus at 3.37x (16T) — bandwidth ceiling reached by 8 cores
- 95.77% classified — dramatic jump from eskape DBs (~65%), standard DB covers ESKAPE species well
- Highest IPC of all hac runs (2.17 at 1T) despite a 63% miss rate — repetitive standard k-mers pipeline efficiently
- IPC collapses 2.07→1.46 at 16T — the hyperthreading penalty on a bandwidth-bound DB

---

### reads_hac — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 97.77 | 2.23 | 66.01 | 69.08 | 18.042 | 1.00x | 1.81 |
| 2  | 97.77 | 2.23 | 65.82 | 69.40 | 11.842 | 1.52x | 1.77 |
| 4  | 97.77 | 2.23 | 65.99 | 69.27 |  8.825 | 2.04x | 1.74 |
| 8  | 97.77 | 2.23 | 66.43 | 70.84 |  7.463 | 2.42x | 1.72 |
| 16 | 97.77 | 2.23 | 65.68 | 68.49 |  7.188 | 2.51x | 1.33 |

**Observations:**
- Worst scaling of all hac runs — 2.51x at 16T; 8T→16T essentially flat (2.42x→2.51x), HT useless
- LLC miss rate flat ~69-71% — pure memory-bandwidth wall
- Classified% 97.77% — only 2 pp over standard_8gb (95.77%) for a 2x larger DB and 57% longer 1T runtime
- Diminishing returns: standard_16gb buys marginal accuracy at a large time/memory cost

---

### reads_sup — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 65.87 | 34.13 | 65.55 | 56.89 | 18.057 | 1.00x | 1.34 |
| 2  | 65.87 | 34.13 | 65.58 | 56.87 |  9.275 | 1.95x | 1.33 |
| 4  | 65.87 | 34.13 | 66.11 | 57.32 |  4.883 | 3.70x | 1.30 |
| 8  | 65.87 | 34.13 | 66.38 | 57.27 |  3.149 | 5.73x | 1.38 |
| 16 | 65.87 | 34.13 | 63.14 | 56.60 |  2.254 | 8.01x | 1.12 |

**Observations:**
- 8.01x at 16T — near-best Dell scaling, with the same HT latency-hiding benefit as hac on this DB (5.73x→8.01x)
- LLC miss rate flat ~57% — latency-bound, not bandwidth-bound, so HT helps
- SUP classified% (65.87%) only marginally above HAC (65.28%) — DB coverage, not read quality, is the limiter here

---

### reads_sup — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 66.68 | 33.32 | 73.09 | 71.49 | 21.609 | 1.00x | 1.26 |
| 2  | 66.68 | 33.32 | 73.25 | 71.70 | 11.898 | 1.82x | 1.25 |
| 4  | 66.68 | 33.32 | 73.59 | 72.01 |  6.732 | 3.21x | 1.23 |
| 8  | 66.68 | 33.32 | 73.94 | 72.69 |  4.546 | 4.75x | 1.28 |
| 16 | 66.68 | 33.32 | 69.03 | 69.65 |  3.429 | 6.30x | 1.09 |

**Observations:**
- 6.30x at 16T — held back by the second-highest LLC miss rate of the sup runs
- Miss rate again only drops at 16T (72.7%→69.7%) — diverse k-mer space
- Classified% 66.68% — only 0.81 pp above hac on the same DB
- IPC ~1.25, well below the standard DBs — serialised misses

---

### reads_sup — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 97.09 | 2.91 | 62.81 | 62.88 | 11.720 | 1.00x | 2.22 |
| 2  | 97.09 | 2.91 | 63.71 | 64.42 |  7.195 | 1.63x | 2.20 |
| 4  | 97.09 | 2.91 | 64.74 | 66.06 |  4.783 | 2.45x | 2.17 |
| 8  | 97.09 | 2.91 | 65.53 | 68.94 |  3.782 | 3.10x | 2.12 |
| 16 | 97.09 | 2.91 | 65.05 | 66.75 |  3.461 | 3.39x | 1.52 |

**Observations:**
- 3.39x at 16T — best of the standard-DB runs, plateauing after 8T
- Highest IPC of any run on Dell (2.22 at 1T) — sup reads generate the most k-mers per read and standard k-mers pipeline best
- 97.09% classified — near-complete; standard_8gb is sufficient for sup reads
- IPC drops 2.12→1.52 at 16T — the now-familiar hyperthreading penalty

---

### reads_sup — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 98.48 | 1.52 | 65.61 | 68.99 | 18.655 | 1.00x | 1.85 |
| 2  | 98.48 | 1.52 | 65.71 | 69.64 | 12.072 | 1.55x | 1.86 |
| 4  | 98.48 | 1.52 | 65.90 | 69.63 |  8.996 | 2.07x | 1.81 |
| 8  | 98.48 | 1.52 | 66.02 | 70.41 |  7.742 | 2.41x | 1.77 |
| 16 | 98.48 | 1.52 | 65.83 | 68.50 |  7.187 | 2.60x | 1.36 |

**Observations:**
- Slowest 1T run on Dell (18.655s) — largest DB + longest reads = maximum DRAM traffic
- Scaling only 2.60x at 16T — memory bandwidth fully saturated
- 98.48% classified — only 1.39 pp over standard_8gb for a 59% longer 1T runtime
- IPC flat ~1.8 then drops to 1.36 at 16T — bandwidth wall plus HT contention

---

### ESKAPE 51MB database (custom, sample-targeted)

Custom Kraken2 DB built from exactly the three ESKAPE reference genomes present in the sample — **Pseudomonas aeruginosa PAO1**, **Escherichia coli K-12 MG1655**, **Klebsiella pneumoniae HS11286** — 51 MB on disk. No host/human genome, no off-target species. Same reads and thread sweep as the other DBs (3 runs averaged).

**What it detected** (hac, 1T — fraction of all reads):

| Organism | Detected% |
|----------|----------:|
| *Pseudomonas aeruginosa* PAO1 | 52.50 |
| *Escherichia coli* K-12 MG1655 | 21.79 |
| *Klebsiella pneumoniae* HS11286 | 9.92 |
| **Total classified** | **84.80** |
| Unclassified | 15.20 |

**reads_fast — eskape_51mb**

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 80.94 | 19.06 | 60.82 | 53.05 | 17.348 | 1.00x | 1.35 |
| 2  | 80.94 | 19.06 | 61.10 | 53.13 |  9.204 | 1.88x | 1.33 |
| 4  | 80.94 | 19.06 | 62.17 | 54.64 |  4.839 | 3.58x | 1.30 |
| 8  | 80.94 | 19.06 | 63.40 | 56.11 |  3.116 | 5.57x | 1.33 |
| 16 | 80.94 | 19.06 | 62.62 | 56.87 |  2.272 | 7.63x | 1.06 |

**reads_hac — eskape_51mb**

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 84.80 | 15.20 | 59.74 | 52.56 | 17.750 | 1.00x | 1.43 |
| 2  | 84.80 | 15.20 | 60.73 | 54.06 |  9.174 | 1.93x | 1.41 |
| 4  | 84.80 | 15.20 | 61.60 | 55.16 |  5.018 | 3.54x | 1.40 |
| 8  | 84.80 | 15.20 | 62.63 | 56.26 |  3.286 | 5.40x | 1.46 |
| 16 | 84.80 | 15.20 | 61.71 | 57.32 |  2.301 | 7.72x | 1.11 |

**reads_sup — eskape_51mb**

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|-----|
| 1  | 85.40 | 14.60 | 59.83 | 52.99 | 17.782 | 1.00x | 1.47 |
| 2  | 85.40 | 14.60 | 60.56 | 54.30 |  9.223 | 1.93x | 1.45 |
| 4  | 85.40 | 14.60 | 61.44 | 55.19 |  4.805 | 3.70x | 1.41 |
| 8  | 85.40 | 14.60 | 62.40 | 56.28 |  3.251 | 5.47x | 1.50 |
| 16 | 85.40 | 14.60 | 61.27 | 57.20 |  2.345 | 7.58x | 1.14 |

**Observations:**
- **Classifies far better than the general eskape_650mb (~85% vs ~65%) despite being ~3× smaller** — because it holds exactly this sample's three organisms. This is a *sample-targeted* result, not a claim that small ESKAPE DBs generally win.
- **Cheapest DB to reach standard-DB-level detection on this sample** — 84.80% (hac) / 85.40% (sup) for 51 MB vs standard_8gb's 95.77% / 97.09% for 7.6 GB; the ~11–12 pp gap is reads from organisms not in the 3-genome DB.
- **Best Dell scaling alongside eskape_650mb** — 7.6–7.7× at 16T; latency-bound small DB, so hyperthreading helps (8T→16T ≈ 1.37×).
- **Highest IPC of the ESKAPE DBs** (1.43–1.47 at 1T) — small, repetitive 3-genome k-mer space pipelines well; drops to ~1.1 at 16T from HT execution-unit sharing.
- **LLC miss ~53→57% rises slightly with threads** — 16 MB L3 cannot hold even this DB's hash, so partitioning gives no cache benefit (same pattern as eskape_650mb on Dell).
- ⚠️ **Caveat:** classified% measures DB↔sample k-mer match, not precision — with no ground truth / host-read filtering we cannot call this "more accurate" than standard, only far cheaper for detecting the sample's known organisms.

---

## Section 2: Final Observations

### F1 — Scaling is capped by 8 physical cores; hyperthreading only helps latency-bound DBs

| DB (hac) | Speedup 8T | Speedup 16T | HT gain (8T→16T) |
|----------|-----------:|------------:|-----------------:|
| eskape_650mb     | 5.55x | 8.11x | 1.46x |
| eskape_human_4gb | 4.76x | 6.42x | 1.35x |
| standard_8gb     | 3.07x | 3.37x | 1.10x |
| standard_16gb    | 2.42x | 2.51x | 1.04x |

- Dell has only 8 physical cores, so 16T runs two hyperthreads per core — best-case speedup tops out near 8x
- Small / cache-friendly DBs are **latency-bound**: the second hyperthread hides memory stalls → real 8T→16T gain (1.35–1.46x)
- Large DBs are **bandwidth-bound**: 8 cores already saturate DRAM → HT adds almost nothing (1.04–1.10x)
- Unlike Minerva (56c/socket), Dell cannot ride scaling past 8x — fewer, faster cores

---

### F2 — Dell is ~10–13× faster than Minerva at 1T despite far fewer cores

> ⚠️ **Comparison unreliable — Minerva side invalid.** The Minerva 1T timing used here was collected while that server was loaded by other users' processes (heavy context switching), so the "~10–13×" gap is inflated by contention and overstates the true hardware difference. Re-run Minerva idle before quoting this figure. See `accuracydrift_minerva.md` validity note.

| Machine | Clock | IPC (hac eskape_650mb 1T) | Time 1T (s) |
|---------|-------|--------------------------:|------------:|
| Minerva (Xeon 6330, 56c/sock) | 2.0 GHz | 0.93 | 233.34 |
| Dell (i7-11700, 8c) | 2.5–4.9 GHz | 1.30 | 18.16 |

- Higher boost clock (up to 4.9 GHz) + higher IPC (Rocket Lake) give far greater per-thread throughput
- Part of the gap is also load: Dell is a dedicated desktop, Minerva a shared 112-thread server — Minerva's 1T wall-clock includes contention and cross-NUMA memory traffic
- Trade-off: Dell wins single-thread and small-DB throughput; Minerva wins at high core counts (scales to 56 physical cores vs Dell's 8)

---

### F3 — DB size vs classified%: standard_8gb is the practical sweet spot (machine-independent)

| DB | hac classified% | sup classified% |
|----|----------------:|----------------:|
| eskape_51mb (custom) | 84.80 | 85.40 |
| eskape_650mb     | 65.28 | 65.87 |
| eskape_human_4gb | 66.13 | 66.68 |
| standard_8gb     | 95.77 | 97.09 |
| standard_16gb    | 97.77 | 98.48 |

- Classified% is identical to Minerva — accuracy depends on DB + reads, not hardware
- eskape → eskape_human: +0.85 pp for a ~20x larger DB — not worth it
- standard_8gb → standard_16gb: +2.0 pp (hac) / +1.39 pp (sup) for 2x the DB and ~58% more runtime — marginal
- standard_8gb gives the best **general** accuracy-to-cost ratio; but for a *known-organism* sample the custom **eskape_51mb** reaches 85% at 1/150th the DB size — the sweet spot shifts to a targeted DB when the expected organisms are known

---

### F4 — Read model matters more for small DBs than large DBs

| DB | fast | hac | sup | Range |
|----|-----:|----:|----:|------:|
| eskape_650mb     | 61.77 | 65.28 | 65.87 | 4.1 pp |
| eskape_human_4gb | 62.27 | 66.13 | 66.68 | 4.4 pp |
| standard_8gb     | 82.66 | 95.77 | 97.09 | 14.4 pp |
| standard_16gb    | 90.44 | 97.77 | 98.48 | 8.0 pp |

- Fast reads are heavily penalised on standard DBs (14.4 pp gap vs hac/sup on standard_8gb)
- For ESKAPE-targeted DBs the gap is small (~4 pp) — DB coverage is the bottleneck, not read quality
- SUP and HAC are near-equivalent on large DBs — HAC is sufficient, SUP offers marginal gain

---

### F5 — On Dell's 16 MB L3 even standard DBs thrash cache, yet IPC is governed by access pattern, not miss rate

| DB (hac, 1T) | Cache Miss% | LLC Miss% | IPC |
|--------------|------------:|----------:|----:|
| eskape_650mb     | 66.14 | 56.50 | 1.30 |
| eskape_human_4gb | 74.26 | 72.51 | 1.20 |
| standard_8gb     | 63.13 | 63.29 | 2.17 |
| standard_16gb    | 66.01 | 69.08 | 1.81 |

- Dell's 16 MB L3 is far smaller than Minerva's ~42 MB — standard DBs now miss ~63-69% (vs ~34-51% on Minerva); no DB fits even partially
- Despite a *higher* miss rate than Minerva, standard_8gb still posts the highest IPC (2.17) — its repetitive k-mers pipeline well (high memory-level parallelism), so misses overlap
- eskape_human_4gb has the worst IPC (1.20) even though its miss rate is only slightly higher — its diverse ESKAPE+human k-mers serialise misses (low MLP)
- Conclusion: throughput is set by *how* misses overlap, not by the raw miss rate — eskape_human_4gb remains the worst DB per classified read

---

### F6 — Hyperthreading at 16T cuts per-thread IPC sharply

| DB (hac) | IPC 8T | IPC 16T | Drop |
|----------|-------:|--------:|-----:|
| eskape_650mb     | 1.36 | 1.08 | -21% |
| eskape_human_4gb | 1.22 | 1.04 | -15% |
| standard_8gb     | 2.07 | 1.46 | -29% |
| standard_16gb    | 1.72 | 1.33 | -23% |

- IPC stays nearly flat from 1T→8T (one thread per physical core) then drops 15-29% at 16T
- Two hyperthreads per core share one set of execution units → lower per-thread IPC
- The drop is largest for high-IPC standard DBs (more execution-unit pressure to share) and smallest for already memory-stalled eskape_human_4gb
- Net runtime still improves at 16T only where HT hides latency (small DBs, F1); on bandwidth-bound DBs the IPC drop nearly cancels the extra threads

---

### F7 — Detection (classified%) by database: how much each DB classified

| Database | Size on disk | fast | hac | sup |
|----------|-------------:|-----:|----:|----:|
| eskape_51mb (custom, sample-targeted) | 51 MB | 80.94 | 84.80 | 85.40 |
| eskape_650mb | 142 MB | 61.77 | 65.28 | 65.87 |
| eskape_human_4gb | 3.8 GB | 62.27 | 66.13 | 66.68 |
| standard_8gb | 7.6 GB | 82.66 | 95.77 | 97.09 |
| standard_16gb | 15 GB | 90.44 | 97.77 | 98.48 |

- **standard_16gb detects the most** (97–98% on hac/sup) but at 15 GB; standard_8gb is within ~1–2 pp at half the size
- **The 51 MB custom DB punches far above its size** — it out-detects both general ESKAPE DBs (650 MB, 3.8 GB) by ~19–20 pp because it contains exactly the sample's three organisms; it trails the standard DBs by ~11–12 pp (the missing reads belong to organisms not in the 3-genome DB)
- **Detection rate is hardware-independent** — these values match Minerva exactly; only throughput differs by machine
- ⚠️ classified% = fraction of reads that received any label (DB↔sample k-mer match), not a precision/accuracy measure — no ground-truth or host-read filtering was applied

---

### F8 — Per-pathogen detection: which organism each database actually found

Clade % of all reads (hac, deterministic — identical across runs/threads/machines). The sample contains three ESKAPE pathogens; species-level = reads pinned to the exact species, genus-level given where the two diverge.

| Database | *P. aeruginosa* | *E. coli* | *K. pneumoniae* | *H. sapiens* (host) | 3-pathogen sum (species) | Total classified |
|----------|----------------:|----------:|----------------:|--------------------:|-------------------------:|-----------------:|
| eskape_51mb (custom, targeted) | 52.50 | 21.79 | 9.92 | — | 84.21 | 84.80 |
| eskape_650mb | 65.28 | 0.00 | 0.00 | — | 65.28 | 65.28 |
| eskape_human_4gb | 64.82 | 0.00 | 0.00 | 1.28 | 64.82 | 66.13 |
| standard_8gb | 31.41 *(G 56.17)* | 14.45 *(G 15.49)* | 4.52 *(G 9.13)* | 0.66 | 50.38 | 95.77 |
| standard_16gb | 35.62 *(G 57.67)* | 16.54 *(G 17.55)* | 5.50 *(G 9.56)* | 0.77 | 57.66 | 97.77 |

*(G nn) = genus-level clade % where it exceeds the species figure.*

- **Only the targeted DB and the standard DBs detect all three pathogens.** **eskape_650mb and eskape_human_4gb detect *only* P. aeruginosa** — they classify **zero** E. coli and **zero** K. pneumoniae (those reads go unclassified). For this sample these "ESKAPE" DBs behave as Pseudomonas-only references.
- **eskape_650mb over-calls P. aeruginosa** — 65.28% vs the targeted DB's 52.50% on the same reads, while finding none of the other two species; with no competing references, E. coli / K. pneumoniae reads that share k-mers are likely lumped into P. aeruginosa.
- **Standard DBs classify the most overall (95–98%) but dilute species-level calls** — standard_8gb pins only 31.41% to *P. aeruginosa* species although 56.17% reach genus *Pseudomonas*; LCA ambiguity across thousands of references pushes ~25 pp up to genus/group/sibling. The three target species sum to only ~50–58% of the 95–98% "classified"; the rest is genus/family/order-level spread.
- **Host (human) reads surface only in DBs that include the human genome** — eskape_human_4gb 1.28%, standard_8gb 0.66%, standard_16gb 0.77%; eskape_51mb and eskape_650mb have no human reference, so host reads stay unclassified rather than being identified.
- **The 51 MB targeted DB gives the cleanest species-level profile** — every classified read pins to species (species% = genus% for all three), 84% concentrated on exactly the three known pathogens, no taxonomic spread.
- hac shown; the structure holds for fast/sup (the eskape DBs lack E. coli / K. pneumoniae references regardless of read model).
