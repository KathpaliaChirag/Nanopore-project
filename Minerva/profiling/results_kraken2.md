# Minerva — Kraken-2 Profiling Results

> Server: minerva | OS: Ubuntu 22.04.4 LTS | CPU: 2× Xeon Gold 6330 (112 logical CPUs) | RAM: 251 GB
> DB: k2_standard_08gb (8 GB) | Input: barcode02.fastq (687 MB, 104,829 reads)
> Binary: ~/kraken2-build-pg/classify (built with -pg -g)

WSL2 baselines for comparison: cache miss rate 34.24%, IPC 0.55 (AMD uProf), 67% in `CompactHashTable::Get()` (gprof).

---

## 3.1 perf stat — Hardware Counters

**Command run:**
```bash
pv ~/barcode02.fastq | perf stat \
  -e cycles,instructions,cache-misses,cache-references,LLC-load-misses,LLC-loads,branch-misses \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d -R ~/report_perf.txt - > /dev/null
```

**Output:**
```
[paste perf stat output here]
```

| Metric | WSL2 | Minerva |
|---|---|---|
| cache miss rate | 34.24% | |
| LLC-load-misses | `<not supported>` | |
| LLC miss rate (LLC-load-misses / LLC-loads) | — | |
| IPC (instructions / cycles) | unreliable | |
| branch miss rate | — | |
| total runtime | 105.87 s | |

---

## 3.2 perf record — Hotspot Functions

**Top functions:**
```
[paste perf report --stdio output here]
```

Flame graph: `kraken2_flame.svg` (committed to repo)

---

## 3.3 gprof — Flat Profile

**Output:**
```
[paste gprof flat profile here]
```

| % time | self (s) | calls | function | WSL2 baseline |
|---|---|---|---|---|
| | | | `CompactHashTable::Get()` | 67.35% |
| | | | `MinimizerScanner::NextMinimizer()` | 18.74% |
| | | | `ClassifySequence()` | 5.53% |

Total runtime: _____ seconds

---

## 3.4 Intel VTune — CPI Waterfall + Memory Stall

**Command run:**
```bash
vtune -collect memory-access -result-dir ~/vtune_mem -- [...]
vtune -report summary -result-dir ~/vtune_mem
```

**Summary output:**
```
[paste vtune summary here]
```

| Metric | Value |
|---|---|
| CPI | |
| Memory Bound % | |
| LLC Miss Penalty (cycles) | |
| NUMA remote access % | |

---

## 3.5 LIKWID — Memory Bandwidth

**Output:**
```
[paste likwid-perfctr output here]
```

| Metric | Value |
|---|---|
| Memory bandwidth (GB/s) | |
| Xeon 6330 theoretical ceiling | ~230 GB/s (dual-socket) |
| % of ceiling used | |

---

## 3.6 gperftools/pprof — Sampling Profile

**Top functions:**
```
[paste pprof --text output here]
```

Call graph SVG: `gperf_callgraph.svg`

---

## 3.7 heaptrack — Heap Allocations

**Summary:**
```
[paste heaptrack_print output here]
```

| Metric | Value |
|---|---|
| Peak heap usage | |
| Top allocation function | |
| Total allocations | |

---

## 3.8 cachegrind — Per-Function LLC Miss Rates

**Command run:**
```bash
pv ~/barcode02.fastq | valgrind --tool=cachegrind --cachegrind-out-file=$HOME/cg.out [...]
cg_annotate --auto=yes ~/cg.out > ~/cachegrind_report.txt
```

**Summary header:**
```
[paste cachegrind summary here — first 80 lines of cachegrind_report.txt]
```

**Key function — CompactHashTable::Get():**

| Counter | Value | Meaning |
|---|---|---|
| Ir (instructions read) | | |
| D1mr (L1 data miss reads) | | |
| DLmr (LLC miss reads) | | |
| DLmr miss rate | | % of reads that miss LLC |

---

## 3.9 perf mem — Memory Latency (optional)

**Output:**
```
[paste perf mem report here]
```

---

## Cross-Tool Summary

| Tool | Key Finding | Confirms |
|---|---|---|
| perf stat | | Memory-bound: IPC ~0.5 |
| perf record | | `CompactHashTable::Get()` hotspot |
| gprof | | 67% in Get() — hardware-independent |
| VTune | | CPI waterfall — memory stall % |
| LIKWID | | Memory BW vs ceiling |
| cachegrind | | DLmr count for Get() |
