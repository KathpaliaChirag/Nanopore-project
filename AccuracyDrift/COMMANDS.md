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

---

### reads_hac × eskape_human_4gb × 2T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 2 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 78.83 | 57.43 | 16.004 | 1.24 |
| 2 | 66.13 | 78.73 | 57.40 | 15.936 | 1.25 |
| 3 | 66.13 | 78.76 | 57.50 | 15.906 | 1.25 |
| **avg** | **66.13** | **78.77** | **57.44** | **15.949** | **1.25** |

Speedup vs 1T: 1.87x (93.5% efficiency).

---

### reads_hac × eskape_human_4gb × 4T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 4 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 80.36 | 58.49 | 8.929 | 1.24 |
| 2 | 66.13 | 80.18 | 58.40 | 8.982 | 1.24 |
| 3 | 66.13 | 80.19 | 58.33 | 8.989 | 1.24 |
| **avg** | **66.13** | **80.24** | **58.41** | **8.966** | **1.24** |

Speedup vs 1T: 3.33x (83.2% efficiency). Compare: eskape_650mb 4T was 3.85x (96.3%). Efficiency has dropped 13 points at just 4T — higher DRAM traffic per thread saturates bandwidth earlier post-cache-cliff.

---

### reads_hac × eskape_human_4gb × 8T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 8 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 82.45 | 59.28 | 5.499 | 1.22 |
| 2 | 66.13 | 82.45 | 59.30 | 5.495 | 1.22 |
| 3 | 66.13 | 82.47 | 59.24 | 5.476 | 1.23 |
| **avg** | **66.13** | **82.46** | **59.27** | **5.490** | **1.22** |

Speedup vs 1T: 5.43x (67.9% efficiency). Compare: eskape_650mb 8T was 7.37x (92.1%). Gap widens — DRAM bandwidth saturation hitting harder with the larger DB.

---

### reads_hac × eskape_human_4gb × 16T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 16 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 83.12 | 59.31 | 3.761 | 1.21 |
| 2 | 66.13 | 83.09 | 59.29 | 3.759 | 1.21 |
| 3 | 66.13 | 83.30 | 59.42 | 3.764 | 1.21 |
| **avg** | **66.13** | **83.17** | **59.34** | **3.761** | **1.21** |

Speedup vs 1T: 7.93x (49.5% efficiency). LLC miss rate has flatlined — 59.27% at 8T vs 59.34% at 16T, essentially no change. DRAM fully saturated; adding more threads only adds overhead.

---

### reads_hac × eskape_human_4gb × 32T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 32 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 83.01 | 59.08 | 2.975 | 1.16 |
| 2 | 66.13 | 82.98 | 59.04 | 2.977 | 1.17 |
| 3 | 66.13 | 82.93 | 58.96 | 2.977 | 1.16 |
| **avg** | **66.13** | **82.97** | **59.03** | **2.976** | **1.16** |

Speedup vs 1T: 10.02x (31.3% efficiency). 16T→32T only gained 26% (7.93x → 10.02x). LLC miss rate ticked down slightly (59.34% → 59.03%) — same 16-32T dip pattern seen with eskape_650mb.

---

### reads_hac × eskape_human_4gb × 64T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 64 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 81.54 | 58.67 | 2.841 | 1.02 |
| 2 | 66.13 | 81.78 | 58.75 | 2.816 | 1.03 |
| 3 | 66.13 | 81.79 | 58.76 | 2.812 | 1.03 |
| **avg** | **66.13** | **81.70** | **58.73** | **2.823** | **1.03** |

Speedup vs 1T: 10.57x (16.5% efficiency). 32T→64T gained only 5% (10.02x → 10.57x). Scaling ceiling essentially reached.

---

### reads_hac × eskape_human_4gb × 96T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_human_4gb \
  --threads 96 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 66.13 | 81.49 | 58.92 | 2.952 | 0.98 |
| 2 | 66.13 | 81.52 | 58.96 | 2.938 | 0.98 |
| 3 | 66.13 | 81.43 | 58.95 | 2.950 | 0.98 |
| **avg** | **66.13** | **81.48** | **58.94** | **2.947** | **0.98** |

96T is SLOWER than 64T (2.947s vs 2.823s) — same pattern as eskape_650mb. Speedup 10.12x, down from 10.57x at 64T. IPC drops below 1.0 — more stall cycles than executed instructions. hac × eskape_human_4gb thread scaling complete.

---

### reads_hac × standard_8gb × 1T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb \
  --threads 1 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 95.77 | 76.43 | 76.49 | 16.831 | 2.10 |
| 2 | 95.77 | 76.61 | 76.67 | 16.821 | 2.11 |
| 3 | 95.77 | 76.66 | 76.62 | 16.683 | 2.12 |
| **avg** | **95.77** | **76.57** | **76.59** | **16.778** | **2.11** |

Note: sys time is ~4.3s (vs ~2s for smaller DBs) — significant DB loading overhead included in wall time. Cache miss rate ≈ LLC miss rate (both ~76%) — with a DB this large, all accesses (speculative, prefetch, demand) miss at the same rate since the hardware prefetcher cannot predict random hash table accesses.

---

### reads_hac × standard_8gb × 2T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb \
  --threads 2 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 95.77 | 77.09 | 77.85 | 10.560 | 2.09 |
| 2 | 95.77 | 77.06 | 77.78 | 10.578 | 2.08 |
| 3 | 95.77 | 77.04 | 77.70 | 10.576 | 2.08 |
| **avg** | **95.77** | **77.06** | **77.78** | **10.571** | **2.08** |

Wall-time speedup: 1.59x (79.4% efficiency). Note: sys time ~4.2s is sequential DB loading overhead constant across thread counts. Classification-phase-only speedup: (16.778-4.27)/(10.571-4.19) = 12.51/6.38 = 1.96x — consistent with other DBs at 2T.

---

### reads_hac × standard_8gb × 4T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb \
  --threads 4 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 95.77 | 77.89 | 79.59 | 7.433 | 2.06 |
| 2 | 95.77 | 77.92 | 79.63 | 7.401 | 2.07 |
| 3 | 95.77 | 78.00 | 79.59 | 7.423 | 2.06 |
| **avg** | **95.77** | **77.94** | **79.60** | **7.419** | **2.06** |

Wall speedup: 2.26x (56.5% eff). Classification-phase speedup: (12.53/3.20) = 3.92x (~98% of ideal 4T). The ~4.2s DB loading overhead dominates wall time at low thread counts.

---

### reads_hac × standard_8gb × 8T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb \
  --threads 8 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 95.77 | 81.04 | 82.40 | 5.822 | 2.03 |
| 2 | 95.77 | 81.26 | 82.25 | 5.853 | 2.02 |
| 3 | 95.77 | 81.01 | 82.32 | 5.834 | 2.02 |
| **avg** | **95.77** | **81.10** | **82.32** | **5.836** | **2.02** |

Wall speedup: 2.87x (35.9% eff). Classification-phase speedup: (12.53/1.57) = 7.99x (~100% of ideal 8T). Classification scaling is near-perfect — all degradation is the DB loading serial overhead.

---

### reads_hac × standard_8gb × 16T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb \
  --threads 16 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 95.77 | 86.36 | 83.30 | 5.111 | 1.95 |
| 2 | 95.77 | 86.29 | 83.32 | 5.099 | 1.96 |
| 3 | 95.77 | 86.24 | 83.39 | 5.078 | 1.94 |
| **avg** | **95.77** | **86.30** | **83.34** | **5.096** | **1.95** |

Wall speedup: 3.29x (20.6% eff). Kraken2 classification time ~0.974s → classification speedup ~13x. Amdahl ceiling dominating — sys time ~4.4s is most of wall time.

---

### reads_hac × standard_8gb × 32T

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb \
  --threads 32 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | IPC  |
|-----|-------------|-----------------|----------------|----------|------|
| 1 | 95.77 | 87.97 | 83.01 | 4.799 | 1.83 |
| 2 | 95.77 | 88.05 | 82.84 | 4.824 | 1.85 |
| 3 | 95.77 | 88.02 | 82.86 | 4.868 | 1.79 |
| **avg** | **95.77** | **88.01** | **82.90** | **4.830** | **1.82** |

Wall speedup: 3.47x (10.8% eff). Kraken2 classification ~0.692s → classification speedup ~18x. Wall time almost entirely sys time (~4.7s). Only 0.27s gained going from 16T to 32T — Amdahl ceiling fully hit.
