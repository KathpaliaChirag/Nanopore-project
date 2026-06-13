# AccuracyDrift Results

## cache-misses vs LLC-load-misses: Why They Are Different

Two perf events that sound similar but measure very different things:

| Event | What it counts | Includes speculative loads? | Includes prefetches? |
|-------|---------------|----------------------------|----------------------|
| `cache-misses` | All LLC miss events (LONGEST_LAT_CACHE.MISS on Intel) | Yes | Yes |
| `cache-references` | All LLC lookup attempts | Yes | Yes |
| `LLC-load-misses` | Only retired demand load instructions that missed LLC (MEM_LOAD_RETIRED.L3_MISS) | No | No |
| `LLC-loads` | Only retired demand load instructions that accessed LLC | No | No |

On this machine (Luna, 1T run): `cache-misses` = 317M vs `LLC-load-misses` = 57M — ~5.6x difference. The extra ~260M in `cache-misses` are speculative loads (fetched by CPU but never actually used by the program) and hardware prefetcher activity.

**We use `LLC-load-misses / LLC-loads` throughout this experiment** because it measures actual program-driven DRAM accesses — the ones we want to minimize with a prefetcher. Speculative and prefetch activity is not what we are optimizing.

---

## Experiment Overview

Goal: Understand how Kraken2 classification accuracy and cache behavior change across database sizes and machines.

- **Read files:** reads_fast.fastq (104,832 reads, 708 MB), reads_hac.fastq (104,918 reads, 703 MB), reads_sup.fastq (104,980 reads, 723 MB)
- **Databases:** eskape_650mb (150 MB), eskape_human_4gb (3.8 GB), standard_8gb (7.6 GB), standard_16gb (15 GB), sample_targeted (50 MB)
- **Machines:** Luna (dell-R760), Minerva, Lab Desktop, Orion (Jetson, last)
- **Threads tested:** powers of 2 from 1 up to machine max
- **Metrics per run:** classified%, unclassified%, cache miss rate% (LLC), time (s)
- **Species breakdown:** collected after all runs on each machine

**Note:** "Accuracy" here = % classified. True accuracy (correct species assignment) requires ground truth — species-level breakdown is a separate analysis done after all runs complete.

---

## Perf Command (standard across all x86 machines)

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads <T> \
  --report ~/AccuracyDrift/runs/<READ>_<DB>_<T>T_report.txt \
  --output ~/AccuracyDrift/runs/<READ>_<DB>_<T>T_output.txt \
  /home/student/results/basecalling/<READ>.fastq
```

Both metrics tracked:
- **Cache Miss Rate%** = cache-misses / cache-references × 100 (includes speculative + prefetch activity)
- **LLC Miss Rate%** = LLC-load-misses / LLC-loads × 100 (retired demand loads only — the real DRAM traffic)

---

## Run Checklist

### Luna
- [x] Fix reads_sup.fastq permissions
- [x] reads_hac × sample_targeted × 1T (baseline done; 2T–96T pending)
- [ ] reads_fast × eskape_650mb × all thread counts
- [ ] reads_fast × eskape_human_4gb × all thread counts
- [ ] reads_fast × standard_8gb × all thread counts
- [ ] reads_fast × standard_16gb × all thread counts
- [x] reads_hac × eskape_650mb × all thread counts
- [x] reads_hac × eskape_human_4gb × all thread counts
- [x] reads_hac × standard_8gb × all thread counts
- [x] reads_hac × standard_16gb × all thread counts
- [x] reads_sup × all DBs × 1T (species/report only, no perf stat — quick model comparison)
- [x] reads_sup × all DBs × 1T perf stat — DONE 2026-06-13
- [ ] reads_sup × sample_targeted × all thread counts (perf stat) — 1T–8T done
- [ ] reads_sup × eskape_650mb × all thread counts (perf stat) — 1T–8T done
- [ ] reads_sup × eskape_human_4gb × all thread counts (perf stat) — 1T–8T done
- [ ] reads_sup × standard_8gb × all thread counts (perf stat) — 1T–8T done
- [ ] reads_sup × standard_16gb × all thread counts (perf stat) — 1T–8T done
- [ ] Species breakdown for all Luna runs (full perf runs)

### Minerva
- [ ] Transfer databases + reads from Luna
- [ ] Check machine specs (threads, RAM)
- [ ] reads_fast × all DBs × all thread counts
- [ ] reads_hac × all DBs × all thread counts
- [ ] reads_sup × all DBs × all thread counts
- [ ] Species breakdown

### Lab Desktop
- [ ] Transfer databases + reads from Luna
- [ ] Check machine specs (threads, RAM)
- [ ] reads_fast × all DBs × all thread counts
- [ ] reads_hac × all DBs × all thread counts
- [ ] reads_sup × all DBs × all thread counts
- [ ] Species breakdown

### Orion (Jetson AGX Orin 64GB)
- [x] SSH setup, storage cleanup, Kraken2 2.1.3 install
- [x] perf verified working (sudo /usr/lib/linux-tools-5.4.0-26/perf)
- [x] reads_hac transferred (703 MB)
- [x] sample_targeted DB transferred
- [x] reads_hac × sample_targeted × 1T
- [x] reads_hac × sample_targeted × 2T,4T,6T,8T,10T,12T
- [x] Transfer eskape_650mb
- [x] reads_hac × eskape_650mb × all thread counts
- [x] Transfer eskape_human_4gb
- [x] reads_hac × eskape_human_4gb × all thread counts
- [x] Transfer remaining DBs (standard_8gb, standard_16gb)
- [x] reads_hac × standard_8gb × all thread counts
- [x] reads_hac × standard_16gb × all thread counts
- [ ] reads_fast × all DBs × all thread counts
- [x] reads_sup × all DBs × 1T and 2T (Orion, 2026-06-13)
- [ ] reads_sup × all DBs × 4T,6T,8T,10T,12T
- [ ] Species breakdown

---

## Sample-Targeted Database Construction

After analyzing the species breakdown, we built a custom Kraken2 DB containing only the organisms present in this sample. This gives a 5th data point — smaller than eskape_650mb but with much better accuracy.

**Motivation:** eskape_650mb (150 MB) classifies 65.28% of reads but misassigns ~33k E. coli/K. pneumoniae reads as P. aeruginosa (no competing references). We know from standard DBs exactly what species are present, so we can build a minimal but correct DB.

**Reference genomes included (6 total):**

| Accession | Species | Role in sample |
|-----------|---------|---------------|
| GCF_000006765.1 | *Pseudomonas aeruginosa* PAO1 | Dominant pathogen (~35%) |
| GCF_000005845.2 | *Escherichia coli* K-12 MG1655 | 2nd most common (~16%) |
| GCF_000240185.1 | *Klebsiella pneumoniae* HS11286 | 3rd most common (~5%) |
| GCF_000174395.2 | *Enterococcus faecium* 62415 | ESKAPE member, present |
| GCF_000013425.1 | *Staphylococcus aureus* MRSA252 | ESKAPE member, present |
| GCF_000025565.1 | *Enterobacter cloacae* ATCC 13047 | ESKAPE member, present |

Note: *Acinetobacter baumannii* (GCF_000012085.1) was suppressed on NCBI and could not be downloaded.

**Build process on Luna:**
```bash
# 1. Download genomes via ncbi-genome-download
ncbi-genome-download bacteria -A <accessions> -F fasta -o .../library/added/ --flat-output

# 2. Download taxonomy (rsync blocked by IITD proxy — used wget instead)
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdmp.zip          # ~60 MB
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/nucl_gb.accession2taxid.gz   # 13 GB compressed
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/nucl_wgs.accession2taxid.gz  # 38 GB compressed

# 3. Add genomes and build
for f in library/added/*.fna; do kraken2-build --add-to-library $f --db sample_targeted; done
kraken2-build --build --db sample_targeted --threads 32  # completes in 22s
```

**Result:** hash.k2d = 50 MB. Scanned 231M accession IDs to map 17 sequences. The 51 GB taxonomy files are build-only — deleted after construction.

---

## Section 1: Per-Machine Thread Scaling

One table per machine × read model × database.
Columns: threads | classified% | unclassified% | cache miss rate% | time (s)

---

### 1.1 Luna

**Specs:** 504 GB RAM, 96 threads (dell-R760)
**Thread counts tested:** 1, 2, 4, 8, 16, 32, 64, 96

#### reads_hac — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 65.28 | 34.72 | 34.21 | 30.70 | 21.981 | 1.00x  | 1.47 |
| 2  | 65.28 | 34.72 | 36.18 | 31.49 | 11.136 | 1.97x  | 1.46 |
| 4  | 65.28 | 34.72 | 37.11 | 32.09 | 5.701  | 3.85x  | 1.45 |
| 8  | 65.28 | 34.72 | 37.07 | 32.26 | 2.981  | 7.37x  | 1.43 |
| 16 | 65.28 | 34.72 | 36.70 | 31.31 | 1.634  | 13.45x | 1.41 |
| 32 | 65.28 | 34.72 | 36.23 | 30.53 | 1.045  | 21.03x | 1.37 |
| 64 | 65.28 | 34.72 | 38.27 | 31.35 | 1.001  | 21.96x | 1.18 |
| 96 | 65.28 | 34.72 | 39.78 | 32.56 | 1.164  | 18.88x | 1.13 |

Note: all runs use numactl --cpunodebind=0 --membind=0. Cache Miss Rate% = cache-misses/cache-references (includes speculative+prefetch). LLC Miss Rate% = LLC-load-misses/LLC-loads (retired demand loads only).

#### reads_hac — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 66.13 | 33.87 | 78.04 | 56.85 | 29.818 | 1.00x | 1.25 |
| 2  | 66.13 | 33.87 | 78.77 | 57.44 | 15.949 | 1.87x | 1.25 |
| 4  | 66.13 | 33.87 | 80.24 | 58.41 | 8.966  | 3.33x | 1.24 |
| 8  | 66.13 | 33.87 | 82.46 | 59.27 | 5.490  | 5.43x | 1.22 |
| 16 | 66.13 | 33.87 | 83.17 | 59.34 | 3.761  | 7.93x | 1.21 |
| 32 | 66.13 | 33.87 | 82.97 | 59.03 | 2.976  | 10.02x | 1.16 |
| 64 | 66.13 | 33.87 | 81.70 | 58.73 | 2.823  | 10.57x | 1.03 |
| 96 | 66.13 | 33.87 | 81.48 | 58.94 | 2.947  | 10.12x | 0.98 |

#### reads_hac — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 95.77 | 4.23 | 76.57 | 76.59 | 16.778 | 1.00x | 2.11 |
| 2  | 95.77 | 4.23 | 77.06 | 77.78 | 10.571 | 1.59x | 2.08 |
| 4  | 95.77 | 4.23 | 77.94 | 79.60 | 7.419  | 2.26x | 2.06 |
| 8  | 95.77 | 4.23 | 81.10 | 82.32 | 5.836  | 2.87x | 2.02 |
| 16 | 95.77 | 4.23 | 86.30 | 83.34 | 5.096  | 3.29x | 1.95 |
| 32 | 95.77 | 4.23 | 88.01 | 82.90 | 4.830  | 3.47x | 1.82 |
| 64 | 95.77 | 4.23 | 87.08 | 82.93 | 4.949  | 3.39x | 1.57 |
| 96 | 95.77 | 4.23 | 86.00 | 82.58 | 5.119  | 3.28x | 1.50 |

#### reads_hac — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 97.77 | 2.23 | 82.00 | 80.15 | 23.914 | 1.00x | 1.86 |
| 2  | 97.77 | 2.23 | 82.46 | 81.61 | 15.827 | 1.51x | 1.83 |
| 4  | 97.77 | 2.23 | 83.52 | 83.81 | 11.707 | 2.04x | 1.80 |
| 8  | 97.77 | 2.23 | 86.94 | 86.04 | 9.618  | 2.49x | 1.76 |
| 16 | 97.77 | 2.23 | 89.98 | 85.73 | 8.575  | 2.79x | 1.74 |
| 32 | 97.77 | 2.23 | 90.58 | 85.03 | 8.153  | 2.93x | 1.67 |
| 64 | 97.77 | 2.23 | 89.63 | 85.04 | 8.253  | 2.90x | 1.43 |
| 96 | 97.77 | 2.23 | 88.98 | 84.93 | 8.385  | 2.85x | 1.37 |

#### reads_hac — sample_targeted

Custom DB built from 6 reference genomes (E. coli K-12, P. aeruginosa PAO1, K. pneumoniae HS11286, E. faecium 62415, S. aureus MRSA252, E. cloacae ATCC 13047). hash.k2d = 50 MB. Built using taxonomy from standard_8gb build; no Amdahl overhead (sys time ~0.2s).

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 84.80 | 15.20 | 7.23 | 10.19 | 19.729 | 1.00x | 1.78 |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_fast — sample_targeted

Custom DB built from 6 reference genomes (same as reads_hac). hash.k2d = 50 MB.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | - | - | - | - | - | - | - |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_fast — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | - | - | - | - | - | - | - |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_fast — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | - | - | - | - | - | - | - |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_fast — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | - | - | - | - | - | - | - |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_fast — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | - | - | - | - | - | - | - |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_sup — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 65.87 | 34.13 | 33.94 | 30.83 | 21.638 | 1.00x | 1.53 |
| 2  | 65.87 | 34.13 | 36.43 | 31.92 | 11.020 | 1.96x | 1.51 |
| 4  | 65.87 | 34.13 | 37.78 | 32.78 | 5.685 | 3.81x | 1.49 |
| 8  | 65.87 | 34.13 | 38.10 | 32.80 | 2.981 | 7.26x | 1.47 |
| 16 | 65.87 | 34.13 | 38.14 | 32.34 | 1.626 | 13.31x | 1.46 |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_sup — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 66.68 | 33.32 | 76.05 | 55.85 | 31.294 | 1.00x | 1.25 |
| 2  | 66.68 | 33.32 | 77.02 | 56.69 | 15.966 | 1.86x† | 1.30 |
| 4  | 66.68 | 33.32 | 78.68 | 57.86 | 9.019 | 3.29x† | 1.28 |
| 8  | 66.68 | 33.32 | 81.43 | 58.91 | 5.485 | 5.42x† | 1.28 |
| 16 | 66.68 | 33.32 | 82.15 | 58.90 | 3.748 | 7.93x† | 1.26 |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_sup — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 97.09 | 2.91 | 75.49 | 75.24 | 16.982 | 1.00x | 2.19 |
| 2  | 97.09 | 2.91 | 75.87 | 76.58 | 10.697 | 1.59x | 2.15 |
| 4  | 97.09 | 2.91 | 76.80 | 78.42 | 7.464 | 2.28x | 2.12 |
| 8  | 97.09 | 2.91 | 80.16 | 81.46 | 5.870 | 2.89x | 2.07 |
| 16 | 97.09 | 2.91 | 85.66 | 82.85 | 5.094 | 3.33x | 2.02 |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_sup — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 98.48 | 1.52 | 81.05 | 78.68 | 24.240 | 1.00x | 1.92 |
| 2  | 98.48 | 1.52 | 81.59 | 80.25 | 15.936 | 1.52x | 1.90 |
| 4  | 98.48 | 1.52 | 82.61 | 82.53 | 11.768 | 2.06x | 1.87 |
| 8  | 98.48 | 1.52 | 86.20 | 85.22 | 9.661 | 2.51x | 1.83 |
| 16 | 98.48 | 1.52 | 89.61 | 85.34 | 8.606 | 2.82x | 1.80 |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_sup — sample_targeted

Custom DB built from 6 reference genomes (same as reads_hac). hash.k2d = 50 MB.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 85.40 | 14.60 | 7.86 | 10.55 | 19.797 | 1.00x | 1.83 |
| 2  | 85.40 | 14.60 | 8.44 | 10.89 | 10.104 | 1.96x | 1.80 |
| 4  | 85.40 | 14.60 | 9.88 | 11.67 | 5.228 | 3.79x | 1.78 |
| 8  | 85.40 | 14.60 | 12.26 | 13.03 | 2.652 | 7.46x | 1.79 |
| 16 | 85.40 | 14.60 | 15.17 | 14.46 | 1.440 | 13.74x | 1.76 |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

Note (eskape_human_4gb): run 2 = 34.471s vs runs 1+3 = 29.675s/29.736s — system load spike on shared Luna machine. LLC miss rates were identical across all 3 runs (55.83/55.85/55.88%), confirming no cache effect. Average of all 3 runs = 31.294s.

---

### 1.2 Minerva

**Specs:** TBD
**Thread counts tested:** TBD (powers of 2 up to max)

*(same table structure as Luna — fill in after specs confirmed)*

---

### 1.3 Lab Desktop

**Specs:** TBD
**Thread counts tested:** TBD (powers of 2 up to max)

*(same table structure as Luna — fill in after specs confirmed)*

---

### 1.4 Orion (Jetson AGX Orin 64GB)

**Specs:** 64 GB LPDDR5 unified memory (CPU+GPU share), 12-core ARM Cortex-A78AE, no hyperthreading
**JetPack:** R35.4.1, Ubuntu 20.04, kernel 5.10.120-tegra
**Thread counts tested:** 1, 2, 4, 6, 8, 10, 12
**perf binary:** `sudo /usr/lib/linux-tools-5.4.0-26/perf` (5.4 binary works on 5.10 kernel, requires sudo)
**No numactl** — single NUMA node (unified memory), binding flags not applicable
**kraken2:** `~/tools/kraken2/kraken2` (2.1.3, explicit path required — sudo strips PATH)

Perf command:
```bash
sudo /usr/lib/linux-tools-5.4.0-26/perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  ~/tools/kraken2/kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads <T> \
  --output /dev/null --report /dev/null \
  ~/reads/reads_hac.fastq
```

#### reads_hac — sample_targeted

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 84.80 | 15.20 | 0.643 | 78.92 | 47.53  | 1.00x  | 1.00 |
| 2  | 84.80 | 15.20 | 0.637 | 78.97 | 23.44  | 2.03x  | 1.02 |
| 4  | 84.80 | 15.20 | 0.635 | 79.87 | 11.81  | 4.02x  | 1.02 |
| 6  | 84.80 | 15.20 | 0.637 | 80.78 | 7.96   | 5.97x  | 1.02 |
| 8  | 84.80 | 15.20 | 0.639 | 81.60 | 6.01   | 7.91x  | 1.02 |
| 10 | 84.80 | 15.20 | 0.640 | 82.28 | 4.93   | 9.64x  | 1.02 |
| 12 | 84.80 | 15.20 | 0.640 | 82.80 | 4.15   | 11.44x | 1.01 |

sys time: 1T=0.274s, 2T=0.269s, 4T=0.318s, 6T=0.347s, 8T=0.430s, 10T=0.399s, 12T=0.461s.
cache-references ~47B (L1D accesses, not LLC — not comparable to Luna). LLC-loads ~588M per run regardless of thread count.

#### reads_hac — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 65.28 | 34.72 | 0.632 | 80.75 | 47.05  | 1.00x  | 0.93 |
| 2  | 65.28 | 34.72 | 0.635 | 80.04 | 23.30  | 2.02x  | 0.94 |
| 4  | 65.28 | 34.72 | 0.637 | 80.68 | 11.85  | 3.97x  | 0.94 |
| 6  | 65.28 | 34.72 | 0.637 | 81.48 | 7.96   | 5.91x  | 0.94 |
| 8  | 65.28 | 34.72 | 0.637 | 82.55 | 6.02   | 7.82x  | 0.94 |
| 10 | 65.28 | 34.72 | 0.638 | 83.05 | 4.91   | 9.58x  | 0.94 |
| 12 | 65.28 | 34.72 | 0.640 | 83.61 | 4.15   | 11.34x | 0.93 |

sys time: 1T=0.307s, 2T=0.299s, 4T=0.361s, 6T=0.386s, 8T=0.377s, 10T=0.417s, 12T=0.453s.

#### reads_hac — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 66.13 | 33.87 | 0.598 | 77.28 | 45.82  | 1.00x  | 1.07 |
| 2  | 66.13 | 33.87 | 0.598 | 76.77 | 23.19  | 1.98x  | 1.08 |
| 4  | 66.13 | 33.87 | 0.597 | 77.25 | 12.21  | 3.75x  | 1.08 |
| 6  | 66.13 | 33.87 | 0.600 | 78.05 | 8.54   | 5.37x  | 1.08 |
| 8  | 66.13 | 33.87 | 0.599 | 79.18 | 6.65   | 6.89x  | 1.08 |
| 10 | 66.13 | 33.87 | 0.601 | 79.77 | 5.60   | 8.18x  | 1.08 |
| 12 | 66.13 | 33.87 | 0.602 | 80.42 | 4.88   | 9.39x  | 1.07 |

sys time: 1T=1.226s, 2T=1.207s, 4T=1.168s, 6T=1.280s, 8T=1.255s, 10T=1.291s, 12T=1.355s.
DB loading (~1.2s constant) is the Amdahl floor. Classification-phase-only speedup at 12T: (45.82-1.23)/(4.88-1.36) = 44.59/3.52 = 12.67x — near-ideal.

#### reads_hac — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 95.77 | 4.23 | 0.494 | 68.19 | 21.19  | 1.00x  | 2.24 |
| 2  | 95.77 | 4.23 | 0.484 | 68.56 | 11.12  | 1.91x  | 2.24 |
| 4  | 95.77 | 4.23 | 0.484 | 70.35 | 6.745  | 3.14x  | 2.20 |
| 6  | 95.77 | 4.23 | 0.486 | 72.13 | 5.277  | 4.02x  | 2.17 |
| 8  | 95.77 | 4.23 | 0.486 | 74.08 | 4.555  | 4.65x  | 2.14 |
| 10 | 95.77 | 4.23 | 0.486 | 75.30 | 4.107  | 5.16x  | 2.12 |
| 12 | 95.77 | 4.23 | 0.486 | 76.55 | 3.823  | 5.54x  | 2.10 |

sys time: 1T=2.35s, 2T=2.18s, 4T=2.26s, 6T=2.23s, 8T=2.24s, 10T=2.28s, 12T=2.34s.
Note: 1T run 1 cold (23.17s wall); runs 2–3 warm averaged 20.20s. Average of all 3 = 21.19s. Amdahl ceiling: 21.19/2.35 ≈ 9.0x max wall speedup. IPC ~2.24 is markedly higher than ESKAPE DBs (0.93–1.08) — standard DB has more compute-intensive lookup patterns.

#### reads_hac — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 97.77 | 2.23 | 0.603 | 71.36 | 28.42  | 1.00x  | 1.92 |
| 2  | 97.77 | 2.23 | 0.592 | 72.27 | 16.15  | 1.76x  | 1.91 |
| 4  | 97.77 | 2.23 | 0.592 | 73.67 | 10.22  | 2.78x  | 1.89 |
| 6  | 97.77 | 2.23 | 0.593 | 75.18 | 8.304  | 3.42x  | 1.86 |
| 8  | 97.77 | 2.23 | 0.596 | 76.58 | 7.340  | 3.87x  | 1.84 |
| 10 | 97.77 | 2.23 | 0.594 | 77.76 | 6.741  | 4.22x  | 1.82 |
| 12 | 97.77 | 2.23 | 0.595 | 78.64 | 6.323  | 4.50x  | 1.80 |

sys time: 1T=4.23s, 2T=4.03s, 4T=4.04s, 6T=4.06s, 8T=4.16s, 10T=4.19s, 12T=4.17s.
All 3 runs at every thread count consistent — 15 GB DB page-cached in 64 GB RAM from prior runs. Amdahl ceiling: 28.42/4.23 ≈ 6.7x max wall speedup. Peak 4.50x at 12T — lowest of all DBs on Orion.

#### reads_sup — sample_targeted

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 85.40 | 14.60 | 0.617 | 79.01 | 47.43  | 1.00x  | 1.04 |
| 2  | 85.40 | 14.60 | 0.610 | 78.68 | 23.51  | 2.02x  | 1.05 |
| 4  | -     | -     | -     | -     | -      | -      | -    |
| 6  | -     | -     | -     | -     | -      | -      | -    |
| 8  | -     | -     | -     | -     | -      | -      | -    |
| 10 | -     | -     | -     | -     | -      | -      | -    |
| 12 | -     | -     | -     | -     | -      | -      | -    |

3 runs averaged per thread count. LLC-loads ~585M per run, consistent with reads_hac.

#### reads_sup — eskape_650mb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 65.87 | 34.13 | 0.611 | 80.13 | 46.70  | 1.00x  | 0.96 |
| 2  | 65.87 | 34.13 | 0.611 | 79.86 | 23.34  | 2.00x  | 0.96 |
| 4  | -     | -     | -     | -     | -      | -      | -    |
| 6  | -     | -     | -     | -     | -      | -      | -    |
| 8  | -     | -     | -     | -     | -      | -      | -    |
| 10 | -     | -     | -     | -     | -      | -      | -    |
| 12 | -     | -     | -     | -     | -      | -      | -    |

#### reads_sup — eskape_human_4gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 66.68 | 33.32 | 0.567 | 77.44 | 45.86  | 1.00x  | 1.12 |
| 2  | 66.68 | 33.32 | 0.568 | 76.72 | 23.21  | 1.98x  | 1.13 |
| 4  | -     | -     | -     | -     | -      | -      | -    |
| 6  | -     | -     | -     | -     | -      | -      | -    |
| 8  | -     | -     | -     | -     | -      | -      | -    |
| 10 | -     | -     | -     | -     | -      | -      | -    |
| 12 | -     | -     | -     | -     | -      | -      | -    |

sys time: ~1.1–1.2s constant (DB loading). Pattern matches reads_hac eskape_human_4gb.

#### reads_sup — standard_8gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 97.09 | 2.91 | 0.464 | 67.95 | 20.31  | 1.00x  | 2.32 |
| 2  | 97.09 | 2.91 | 0.467 | 67.70 | 11.23  | 1.81x  | 2.32 |
| 4  | -     | -     | -     | -     | -      | -      | -    |
| 6  | -     | -     | -     | -     | -      | -      | -    |
| 8  | -     | -     | -     | -     | -      | -      | -    |
| 10 | -     | -     | -     | -     | -      | -      | -    |
| 12 | -     | -     | -     | -     | -      | -      | -    |

sys time: ~2.1–2.2s constant (DB loading). All 3 runs at 1T warm — DB already page-cached from reads_hac runs. IPC=2.32 highest of all DBs, same as reads_hac.

#### reads_sup — standard_16gb

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Speedup vs 1T | IPC  |
|---------|-------------|---------------|-----------------|----------------|----------|---------------|------|
| 1  | 98.48 | 1.52 | 0.580 | 71.15 | 32.75  | 1.00x  | 1.99 |
| 2  | 98.48 | 1.52 | 0.576 | 72.14 | 16.37  | 2.00x  | 1.98 |
| 4  | -     | -     | -     | -     | -      | -      | -    |
| 6  | -     | -     | -     | -     | -      | -      | -    |
| 8  | -     | -     | -     | -     | -      | -      | -    |
| 10 | -     | -     | -     | -     | -      | -      | -    |
| 12 | -     | -     | -     | -     | -      | -      | -    |

Note: 1T run 1 cold (40.91s wall); runs 2–3 warm (28.83s, 28.52s). Average of all 3 = 32.75s. sys time: 1T avg ~5.4s (run1 8.0s cold, runs 2–3 ~4.1s), 2T avg ~4.0s.

---

## Section 2: Cross-Machine Comparison

Comparison at 1T and max-T across all machines. Fixed read model and DB to isolate machine effect.

### 2.1 LLC Miss Rate% at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 10.19 | - | - | 78.92 |
| eskape_650mb (150 MB) | 30.70 | - | - | 80.75 |
| eskape_human_4gb (3.8 GB) | 56.85 | - | - | 77.28 |
| standard_8gb (7.6 GB) | 76.59 | - | - | 68.19 |
| standard_16gb (15 GB) | 80.15 | - | - | 71.36 |

### 2.2 LLC Miss Rate% at Max Thread — reads_hac

| DB | Luna (96T) | Minerva (TBD) | Lab Desktop (TBD) | Orion (12T) |
|----|-----------|---------------|------------------|------------|
| sample_targeted (50 MB) | - (TBD) | - | - | 82.80 |
| eskape_650mb (150 MB) | 32.56 | - | - | 83.61 |
| eskape_human_4gb (3.8 GB) | 58.94 | - | - | 80.42 |
| standard_8gb (7.6 GB) | 82.58 | - | - | 76.55 |
| standard_16gb (15 GB) | 84.93 | - | - | 78.64 |

### 2.3 Time (s) at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 19.729 | - | - | 47.53 |
| eskape_650mb (150 MB) | 21.981 | - | - | 47.05 |
| eskape_human_4gb (3.8 GB) | 29.818 | - | - | 45.82 |
| standard_8gb (7.6 GB) | 16.778 | - | - | 21.19 |
| standard_16gb (15 GB) | 23.914 | - | - | 28.42 |

### 2.4 Classified% at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 84.80 | - | - | 84.80 |
| eskape_650mb (150 MB) | 65.28 | - | - | 65.28 |
| eskape_human_4gb (3.8 GB) | 66.13 | - | - | 66.13 |
| standard_8gb (7.6 GB) | 95.77 | - | - | 95.77 |
| standard_16gb (15 GB) | 97.77 | - | - | 97.77 |

### 2.5 Classified% at 1 Thread — reads_sup

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 85.40 | - | - | 85.40 |
| eskape_650mb (150 MB) | 65.87 | - | - | 65.87 |
| eskape_human_4gb (3.8 GB) | 66.68 | - | - | 66.68 |
| standard_8gb (7.6 GB) | 97.09 | - | - | 97.09 |
| standard_16gb (15 GB) | 98.48 | - | - | 98.48 |

reads_sup classification rates are 0.6–1.3 pp higher than reads_hac across all DBs, consistent with the higher-quality basecalling producing k-mers that more precisely match reference sequences. Orion matches Luna exactly — classification is machine-independent.

### 2.6 LLC Miss Rate% at 1 Thread — reads_sup

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 10.55 | - | - | 79.01 |
| eskape_650mb (150 MB) | 30.83 | - | - | 80.13 |
| eskape_human_4gb (3.8 GB) | 55.85 | - | - | 77.44 |
| standard_8gb (7.6 GB) | 75.24 | - | - | 67.95 |
| standard_16gb (15 GB) | 78.68 | - | - | 71.15 |

reads_sup LLC miss rates match reads_hac within 1–2 pp on both machines. The basecalling model does not meaningfully change Kraken2's LLC access pattern. The Luna vs Orion contrast is identical to reads_hac: small DBs that fit Luna's L3 (sample_targeted, eskape_650mb) run at 10–31% miss on Luna but 79–80% on Orion.

*(Repeat sections 2.1–2.4 for reads_fast and reads_sup perf stat runs once data is collected)*

---

## Section 3: DB Size vs Classified% Summary

How classification rate changes as DB grows. Expected: more classified with larger DB.

### reads_hac — all machines, 32T (or max available)

| DB | Luna (32T) | Minerva | Lab Desktop | Orion (12T) |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 84.80% | - | - | 84.80% |
| eskape_650mb (150 MB) | 65.28% | - | - | 65.28% |
| eskape_human_4gb (3.8 GB) | 66.13% | - | - | 66.13% |
| standard_8gb (7.6 GB) | 95.77% | - | - | 95.77% |
| standard_16gb (15 GB) | 97.77% | - | - | 97.77% |

### reads_sup — all machines, 1T

| DB | Luna (1T) | Minerva | Lab Desktop | Orion (1T) |
|----|-----------|---------|-------------|------------|
| sample_targeted (50 MB) | 85.40% | - | - | 85.40% |
| eskape_650mb (150 MB) | 65.87% | - | - | 65.87% |
| eskape_human_4gb (3.8 GB) | 66.68% | - | - | 66.68% |
| standard_8gb (7.6 GB) | 97.09% | - | - | 97.09% |
| standard_16gb (15 GB) | 98.48% | - | - | 98.48% |

*(Repeat for reads_fast)*

---

## Section 4: Species-Level Breakdown

Done after all runs on each machine complete. Uses the kraken2 --report files.
Shows: for each DB run, what fraction of classified reads mapped to each major taxonomic group.

ESKAPE species taxids for reference:
- Enterococcus faecium: 1352
- Staphylococcus aureus: 1280
- Klebsiella pneumoniae: 573
- Acinetobacter baumannii: 470
- Pseudomonas aeruginosa: 287
- Enterobacter spp.: 547

### Luna — reads_hac (32T)

Only species reaching >1% in at least one DB get a row. Homo sapiens included because it hits 1.28% in eskape_human_4gb; sub-1% values shown for completeness. "—" means the species is not in that DB's reference set.

| Species | sample_targeted | eskape_650mb | eskape_human_4gb | standard_8gb | standard_16gb |
|---------|----------------|-------------|-----------------|--------------|---------------|
| *Pseudomonas aeruginosa* | 52.50% (55,077) | 65.28% (68,493) | 64.82% (68,008) | 31.41% (32,956) | 35.62% (37,373) |
| *Escherichia coli* | 21.79% (22,860) | — | — | 14.45% (15,159) | 16.54% (17,350) |
| *Klebsiella pneumoniae* | 9.92% (10,411) | — | — | 4.52% (4,739) | 5.50% (5,774) |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.13% (2,237) | 2.21% (2,315) |
| *Homo sapiens* | — | — | 1.28% (1,344) | 0.66% (695) | 0.77% (803) |
| Other classified (<1% each) | 0.59% (625) | 0% (0) | ~0.03% (28) | 42.60% (44,695) | 37.14% (38,965) |
| Unclassified | 15.20% (15,945) | 34.72% (36,425) | 33.87% (35,538) | 4.23% (4,437) | 2.23% (2,338) |

sample_targeted "other classified" breakdown: *E. cloacae* ATCC 13047 = 0.48% (503), *S. aureus* NCTC 8325 = 0.01% (7), *E. faecium* DO = <0.01% (5), unresolved at higher ranks (Bacteria/Gammaproteobacteria/Enterobacteriaceae) = 0.10% (110).

---

### 4.2 Cross-DB Species Comparison — % of All Reads (Luna, reads_hac, 32T)

How the apparent composition of the same read pool changes purely as a function of which reference database is used.

| Species | sample_targeted | eskape_650mb | eskape_human_4gb | standard_8gb | standard_16gb |
|---------|:--------------:|:-----------:|:---------------:|:-----------:|:------------:|
| *P. aeruginosa* | 52.50% | 65.28% | 64.82% | 31.41% | 35.62% |
| *E. coli* | 21.79% | — | — | 14.45% | 16.54% |
| *K. pneumoniae* | 9.92% | — | — | 4.52% | 5.50% |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.13% | 2.21% |
| *Homo sapiens* | — | — | 1.28% | 0.66% | 0.77% |
| Other classified | 0.59% | 0% | ~0.03% | 42.60% | 37.14% |
| Unclassified | 15.20% | 34.72% | 33.87% | 4.23% | 2.23% |

### 4.3 Cross-DB Species Comparison — % of Classified Reads (Luna, reads_hac, 32T)

Normalises out the unclassified fraction so DB width effects on apparent composition are visible directly.

| Species | sample_targeted (88,973 cl.) | eskape_650mb (68,493 cl.) | eskape_human_4gb (69,380 cl.) | standard_8gb (100,481 cl.) | standard_16gb (102,580 cl.) |
|---------|:---------------------------:|:------------------------:|:----------------------------:|:-------------------------:|:--------------------------:|
| *P. aeruginosa* | 61.90% | 100.00% | 98.02% | 32.80% | 36.43% |
| *E. coli* | 25.69% | — | — | 15.09% | 16.91% |
| *K. pneumoniae* | 11.70% | — | — | 4.72% | 5.63% |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.23% | 2.26% |
| *Homo sapiens* | — | — | 1.94% | 0.69% | 0.78% |
| Other classified | 0.70% | 0% | 0.04% | 44.48% | 38.00% |

Key insight: in eskape_650mb, 100% of classified reads are called P. aeruginosa — a complete artefact of the narrow DB having no competing references. In standard_8gb, P. aeruginosa drops to 32.80% of classified reads, which is closer to its true abundance. The classified-reads view makes the artefact unmistakable.

*(Repeat sections 4.1–4.3 for reads_fast once data is collected)*

---

### Luna — reads_sup (1T, single run, no perf stat)

Quick 1-thread run to compare species calls across DBs under the highest-quality basecalling model. Same read pool as reads_hac (104,980 reads, 723 MB).

| Species | sample_targeted | eskape_650mb | eskape_human_4gb | standard_8gb | standard_16gb |
|---------|----------------|-------------|-----------------|--------------|---------------|
| *Pseudomonas aeruginosa* | 52.86% (55,495) | 65.87% (69,149) | 65.35% (68,603) | 32.06% (33,655) | 36.03% (37,824) |
| *Escherichia coli* | 21.94% (23,028) | — | — | 14.17% (14,879) | 16.13% (16,931) |
| *Klebsiella pneumoniae* | 10.01% (10,512) | — | — | 4.52% (4,746) | 5.42% (5,688) |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.17% (2,275) | 2.23% (2,337) |
| *Homo sapiens* | — | — | 1.31% (1,372) | 0.66% (696) | 0.75% (786) |
| Other classified (<1% each) | 0.53% (561) | 0% (0) | ~0.02% (22) | 43.51% (45,671) | 38.52% (40,454) |
| Unclassified | 14.60% (15,322) | 34.13% (35,831) | 33.32% (34,983) | 2.91% (3,058) | 1.52% (1,600) |

sample_targeted "other classified" breakdown: *E. cloacae* ATCC 13047 = 0.48% (508), *S. aureus* NCTC 8325 = 0.01% (7), *E. faecium* DO = <0.01% (3), unresolved at higher ranks = 0.04% (43).

---

### 4.5 Cross-DB Species Comparison — % of All Reads (Luna, reads_sup, 1T)

| Species | sample_targeted | eskape_650mb | eskape_human_4gb | standard_8gb | standard_16gb |
|---------|:--------------:|:-----------:|:---------------:|:-----------:|:------------:|
| *P. aeruginosa* | 52.86% | 65.87% | 65.35% | 32.06% | 36.03% |
| *E. coli* | 21.94% | — | — | 14.17% | 16.13% |
| *K. pneumoniae* | 10.01% | — | — | 4.52% | 5.42% |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.17% | 2.23% |
| *Homo sapiens* | — | — | 1.31% | 0.66% | 0.75% |
| Other classified | 0.53% | 0% | ~0.02% | 43.51% | 38.52% |
| Unclassified | 14.60% | 34.13% | 33.32% | 2.91% | 1.52% |

### 4.6 Cross-DB Species Comparison — % of Classified Reads (Luna, reads_sup, 1T)

| Species | sample_targeted (89,658 cl.) | eskape_650mb (69,149 cl.) | eskape_human_4gb (69,997 cl.) | standard_8gb (101,922 cl.) | standard_16gb (103,380 cl.) |
|---------|:---------------------------:|:------------------------:|:----------------------------:|:-------------------------:|:--------------------------:|
| *P. aeruginosa* | 61.90% | 100.00% | 98.01% | 33.02% | 36.58% |
| *E. coli* | 25.69% | — | — | 14.60% | 16.38% |
| *K. pneumoniae* | 11.73% | — | — | 4.66% | 5.50% |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.23% | 2.26% |
| *Homo sapiens* | — | — | 1.96% | 0.68% | 0.76% |
| Other classified | 0.63% | 0% | 0.03% | 44.81% | 39.13% |

Key insight: reads_sup classified-reads pattern is essentially identical to reads_hac (e.g., P. aeruginosa in standard_16gb: 36.43% hac vs 36.58% sup). The basecalling model (hac vs sup) has negligible effect on species composition calls at the Kraken2 level — the small gain in classification rate (98.48% vs 97.77%) does not shift which species get credited.
