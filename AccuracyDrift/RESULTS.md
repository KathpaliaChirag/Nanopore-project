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
- [ ] Fix reads_sup.fastq permissions
- [x] reads_hac × sample_targeted × 1T (baseline done; 2T–96T pending)
- [ ] reads_fast × eskape_650mb × all thread counts
- [ ] reads_fast × eskape_human_4gb × all thread counts
- [ ] reads_fast × standard_8gb × all thread counts
- [ ] reads_fast × standard_16gb × all thread counts
- [x] reads_hac × eskape_650mb × all thread counts
- [x] reads_hac × eskape_human_4gb × all thread counts
- [x] reads_hac × standard_8gb × all thread counts
- [x] reads_hac × standard_16gb × all thread counts
- [ ] reads_sup × eskape_650mb × all thread counts
- [ ] reads_sup × eskape_human_4gb × all thread counts
- [ ] reads_sup × standard_8gb × all thread counts
- [ ] reads_sup × standard_16gb × all thread counts
- [ ] Species breakdown for all Luna runs

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
- [ ] Transfer remaining DBs (standard_8gb, standard_16gb)
- [ ] reads_hac × all remaining DBs × all thread counts
- [ ] reads_fast × all DBs × all thread counts
- [ ] reads_sup × all DBs × all thread counts
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
| 1  | - | - | - | - | - | - | - |
| 2  | - | - | - | - | - | - | - |
| 4  | - | - | - | - | - | - | - |
| 8  | - | - | - | - | - | - | - |
| 16 | - | - | - | - | - | - | - |
| 32 | - | - | - | - | - | - | - |
| 64 | - | - | - | - | - | - | - |
| 96 | - | - | - | - | - | - | - |

#### reads_sup — eskape_human_4gb

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

#### reads_sup — standard_8gb

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

#### reads_sup — standard_16gb

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

---

## Section 2: Cross-Machine Comparison

Comparison at 1T and max-T across all machines. Fixed read model and DB to isolate machine effect.

### 2.1 LLC Miss Rate% at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 10.19 | - | - | 78.92 |
| eskape_650mb (150 MB) | 30.70 | - | - | 80.75 |
| eskape_human_4gb (3.8 GB) | 56.85 | - | - | 77.28 |
| standard_8gb (7.6 GB) | 76.59 | - | - | - |
| standard_16gb (15 GB) | 80.15 | - | - | - |

### 2.2 LLC Miss Rate% at Max Thread — reads_hac

| DB | Luna (96T) | Minerva (TBD) | Lab Desktop (TBD) | Orion (12T) |
|----|-----------|---------------|------------------|------------|
| sample_targeted (50 MB) | - (TBD) | - | - | 82.80 |
| eskape_650mb (150 MB) | 32.56 | - | - | 83.61 |
| eskape_human_4gb (3.8 GB) | 58.94 | - | - | 80.42 |
| standard_8gb (7.6 GB) | 82.58 | - | - | - |
| standard_16gb (15 GB) | 84.93 | - | - | - |

### 2.3 Time (s) at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 19.729 | - | - | 47.53 |
| eskape_650mb (150 MB) | 21.981 | - | - | 47.05 |
| eskape_human_4gb (3.8 GB) | 29.818 | - | - | 45.82 |
| standard_8gb (7.6 GB) | 16.778 | - | - | - |
| standard_16gb (15 GB) | 23.914 | - | - | - |

### 2.4 Classified% at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 84.80 | - | - | 84.80 |
| eskape_650mb (150 MB) | 65.28 | - | - | - |
| eskape_human_4gb (3.8 GB) | 66.13 | - | - | - |
| standard_8gb (7.6 GB) | 95.77 | - | - | - |
| standard_16gb (15 GB) | 97.77 | - | - | - |

*(Repeat sections 2.1–2.4 for reads_fast and reads_sup once data is collected)*

---

## Section 3: DB Size vs Classified% Summary

How classification rate changes as DB grows. Expected: more classified with larger DB.

### reads_hac — all machines, 32T (or max available)

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| sample_targeted (50 MB) | 84.80% | - | - | - |
| eskape_650mb (150 MB) | 65.28% | - | - | - |
| eskape_human_4gb (3.8 GB) | 66.13% | - | - | - |
| standard_8gb (7.6 GB) | 95.77% | - | - | - |
| standard_16gb (15 GB) | 97.77% | - | - | - |

*(Repeat for reads_fast and reads_sup)*

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
| *Pseudomonas aeruginosa* | - (TBD) | 65.28% (68,493) | 64.82% (68,008) | 31.41% (32,956) | 35.62% (37,373) |
| *Escherichia coli* | - (TBD) | — | — | 14.45% (15,159) | 16.54% (17,350) |
| *Klebsiella pneumoniae* | - (TBD) | — | — | 4.52% (4,739) | 5.50% (5,774) |
| *Pseudomonas* sp. p1(2021b) | — | — | — | 2.13% (2,237) | 2.21% (2,315) |
| *Homo sapiens* | — | — | 1.28% (1,344) | 0.66% (695) | 0.77% (803) |
| Other classified (<1% each) | - (TBD) | 0% (0) | ~0% (28) | 42.60% (44,695) | 37.14% (38,965) |
| Unclassified | 15.20% (15,945) | 34.72% (36,425) | 33.87% (35,538) | 4.23% (4,437) | 2.23% (2,338) |

*(Repeat for each machine × read model combination)*
