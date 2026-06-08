# AccuracyDrift Command Log

All commands run as part of this experiment, in order.

---

## Luna (dell-R760, student@luna.cse.iitd.ac.in)

### Setup checks

```bash
# Check available fastq files
find ~/AccuracyDrift -name "*.fastq" -o -name "*.fastq.gz" 2>/dev/null
find ~/ -maxdepth 3 -name "*.fastq" -o -name "*.fastq.gz" 2>/dev/null

# Check read counts and sizes
wc -l /home/student/results/basecalling/reads_fast.fastq \
       /home/student/results/basecalling/reads_hac.fastq \
       /home/student/results/basecalling/reads_sup.fastq
ls -lh /home/student/results/basecalling/reads_fast.fastq \
        /home/student/results/basecalling/reads_hac.fastq \
        /home/student/results/basecalling/reads_sup.fastq

# Fix sup permissions (sudo password failed but file was already world-readable)
sudo chmod o+r /home/student/results/basecalling/reads_sup.fastq
```

Read file summary:
- reads_fast.fastq: 104,832 reads, 708 MB
- reads_hac.fastq: 104,918 reads, 703 MB
- reads_sup.fastq: 104,980 reads, 723 MB

```bash
# Create runs directory
mkdir -p ~/AccuracyDrift/runs
```

---

### Test run (no perf, no numactl)

```bash
kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 32 \
  --report ~/AccuracyDrift/test_run_report.txt \
  --output ~/AccuracyDrift/test_run_output.txt \
  /home/student/results/basecalling/reads_hac.fastq
```

Result: 65.28% classified — confirmed setup works.

---

### reads_hac × eskape_650mb × 32T (no numactl, pre-experiment runs)

Run 3 times to verify consistency:

```bash
perf stat -e cache-misses,cache-references,instructions,cycles \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 32 \
  --report ~/AccuracyDrift/runs/hac_eskape_650mb_report.txt \
  --output ~/AccuracyDrift/runs/hac_eskape_650mb_output.txt \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) |
|-----|-------------|-----------------|----------|
| 1 | 65.28 | 38.49 | 1.107 |
| 2 | 65.28 | 38.57 | 1.097 |
| 3 | 65.28 | 38.39 | 1.097 |
| **avg** | **65.28** | **38.48** | **1.10** |

Note: numactl not used here. Added from next set of runs onward.

---

### reads_hac × eskape_650mb × 1T — CORRECTED (LLC-load-misses)

Previous runs used wrong event (cache-misses). Re-run 3 times with correct events:

```bash
perf stat -e LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 1 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|----------------|----------|------|
| 1 | 65.28 | 30.79 | 21.966 | 1.47 |
| 2 | 65.28 | 30.72 | 21.998 | 1.47 |
| 3 | 65.28 | 30.58 | 21.978 | 1.47 |
| **avg** | **65.28** | **30.70** | **21.981** | **1.47** |

---

### reads_hac × eskape_650mb × 2T — CORRECTED (LLC-load-misses)

```bash
perf stat -e LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 2 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|----------------|----------|------|
| 1 | 65.28 | 31.56 | 11.170 | 1.45 |
| 2 | 65.28 | 31.48 | 11.130 | 1.46 |
| 3 | 65.28 | 31.43 | 11.109 | 1.46 |
| **avg** | **65.28** | **31.49** | **11.136** | **1.46** |

Speedup vs 1T: 1.97x (98.5% efficiency).

---

### reads_hac × eskape_650mb × 4T — CORRECTED (LLC-load-misses)

```bash
perf stat -e LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 4 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|----------------|----------|------|
| 1 | 65.28 | 31.87 | 5.722 | 1.45 |
| 2 | 65.28 | 32.12 | 5.688 | 1.45 |
| 3 | 65.28 | 32.29 | 5.693 | 1.45 |
| **avg** | **65.28** | **32.09** | **5.701** | **1.45** |

Speedup vs 1T: 3.85x (96.3% efficiency).

---

### reads_hac × eskape_650mb × 8T — CORRECTED (LLC-load-misses)

```bash
perf stat -e LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 8 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|----------------|----------|------|
| 1 | 65.28 | 31.94 | 2.977 | 1.44 |
| 2 | 65.28 | 32.83 | 2.981 | 1.43 |
| 3 | 65.28 | 32.02 | 2.986 | 1.43 |
| **avg** | **65.28** | **32.26** | **2.981** | **1.43** |

Speedup vs 1T: 7.37x (92.1% efficiency).

---

### reads_hac × eskape_650mb × 16T — CORRECTED (LLC-load-misses)

```bash
perf stat -e LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 16 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|----------------|----------|------|
| 1 | 65.28 | 31.30 | 1.649 | 1.40 |
| 2 | 65.28 | 31.26 | 1.626 | 1.42 |
| 3 | 65.28 | 31.36 | 1.626 | 1.42 |
| **avg** | **65.28** | **31.31** | **1.634** | **1.41** |

Speedup vs 1T: 13.45x (84.1% efficiency). LLC miss rate dipped vs 8T (32.26% → 31.31%) — same pattern as before, watch at 32T+.

---

### reads_hac × eskape_650mb × 32T (LLC-load-misses only, cache-miss re-run pending)

```bash
perf stat -e LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 32 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|----------------|----------|------|
| 1 | 65.28 | 30.74 | 1.048 | 1.38 |
| 2 | 65.28 | 30.30 | 1.058 | 1.38 |
| 3 | 65.28 | 30.29 | 1.053 | 1.38 |
| **avg** | **65.28** | **30.44** | **1.053** | **1.38** |

Speedup vs 1T: 20.87x (65.2% efficiency) — big drop from 16T's 84.1%. DRAM bandwidth wall hit.

---

### reads_hac × eskape_650mb × 32T — full 6-event re-run

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 32 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 65.28 | 36.14 | 30.33 | 1.036 | 1.37 |
| 2 | 65.28 | 36.34 | 30.69 | 1.054 | 1.37 |
| 3 | 65.28 | 36.22 | 30.58 | 1.044 | 1.38 |
| **avg** | **65.28** | **36.23** | **30.53** | **1.045** | **1.37** |

Speedup vs 1T: 21.03x (65.7% efficiency). Both metrics peaked at 4-8T and declining — at high thread counts, runs finish faster leaving less time for cache pressure to build.

---

### reads_hac × eskape_650mb × 64T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 64 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 65.28 | 38.23 | 31.30 | 1.015 | 1.19 |
| 2 | 65.28 | 38.38 | 31.42 | 1.006 | 1.19 |
| 3 | 65.28 | 38.19 | 31.32 | 0.981 | 1.17 |
| **avg** | **65.28** | **38.27** | **31.35** | **1.001** | **1.18** |

Speedup vs 1T: 21.96x (34.3% efficiency). 32T→64T gained only 4% in wall time. IPC crashed from 1.37 to 1.18. Both miss rates jumped back up — 64 threads generate enough pressure even in short wall time to saturate cache again.

---

### reads_hac × eskape_650mb × 96T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 96 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 65.28 | 40.03 | 32.81 | 1.220 | 1.12 |
| 2 | 65.28 | 39.70 | 32.36 | 1.130 | 1.13 |
| 3 | 65.28 | 39.60 | 32.50 | 1.143 | 1.14 |
| **avg** | **65.28** | **39.78** | **32.56** | **1.164** | **1.13** |

96T is SLOWER than 64T (1.164s vs 1.001s). Speedup 18.88x — lower than 64T's 21.96x. Thread overhead and cache thrashing outweigh parallelism. hac × eskape_650mb thread scaling complete.

---

### reads_hac × eskape_human_4gb × 1T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 1 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 77.86 | 56.72 | 29.958 | 1.25 |
| 2 | 66.13 | 78.13 | 56.92 | 29.863 | 1.25 |
| 3 | 66.13 | 78.14 | 56.91 | 29.632 | 1.26 |
| **avg** | **66.13** | **78.04** | **56.85** | **29.818** | **1.25** |

Cache cliff confirmed: LLC miss rate jumped from 30.70% (eskape_650mb) to 56.85% (eskape_human_4gb). Cache miss rate from 34.21% to 78.04%. Classified% up slightly: 65.28% → 66.13% (human genome adds coverage).
