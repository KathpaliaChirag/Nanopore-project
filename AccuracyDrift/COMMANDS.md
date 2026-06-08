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

| Run | Classified% | Cache Miss Rate% | Time (s) |
|-----|-------------|-----------------|----------|
| 1 | 65.28 | 38.49 | 1.107 |
| 2 | 65.28 | 38.57 | 1.097 |
| 3 | 65.28 | 38.39 | 1.097 |
| **avg** | **65.28** | **38.48** | **1.10** |

Note: numactl not used here. Added from next set of runs onward.

---

### reads_hac × eskape_650mb × 1T (with numactl)

Run 3 times:

```bash
perf stat -e cache-misses,cache-references,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/eskape_650mb \
  --threads 1 \
  --report ~/AccuracyDrift/runs/hac_eskape_650mb_1T_report.txt \
  --output ~/AccuracyDrift/runs/hac_eskape_650mb_1T_output.txt \
  /home/student/results/basecalling/reads_hac.fastq
```

| Run | Classified% | Cache Miss Rate% | Time (s) |
|-----|-------------|-----------------|----------|
| 1 | 65.28 | 34.44 | 21.843 |
| 2 | 65.28 | 34.08 | 21.967 |
| 3 | 65.28 | 34.11 | 21.962 |
| **avg** | **65.28** | **34.21** | **21.924** |
