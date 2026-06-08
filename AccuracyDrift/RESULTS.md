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
- **Databases:** eskape_650mb (142 MB), eskape_human_4gb (3.8 GB), standard_8gb (7.6 GB), standard_16gb (15 GB)
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
- [ ] reads_fast × eskape_650mb × all thread counts
- [ ] reads_fast × eskape_human_4gb × all thread counts
- [ ] reads_fast × standard_8gb × all thread counts
- [ ] reads_fast × standard_16gb × all thread counts
- [ ] reads_hac × eskape_650mb × all thread counts
- [ ] reads_hac × eskape_human_4gb × all thread counts
- [ ] reads_hac × standard_8gb × all thread counts
- [ ] reads_hac × standard_16gb × all thread counts
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

### Orion (Jetson, do last)
- [ ] Transfer databases + reads
- [ ] Check perf event names (ARM, not x86)
- [ ] Check available threads and RAM
- [ ] reads_fast × all DBs × all thread counts
- [ ] reads_hac × all DBs × all thread counts
- [ ] reads_sup × all DBs × all thread counts
- [ ] Species breakdown

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

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_hac — standard_8gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_hac — standard_16gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_fast — eskape_650mb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_fast — eskape_human_4gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_fast — standard_8gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_fast — standard_16gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_sup — eskape_650mb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_sup — eskape_human_4gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_sup — standard_8gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

#### reads_sup — standard_16gb

| Threads | Classified% | Unclassified% | LLC Miss Rate% | Time (s) |
|---------|-------------|---------------|-----------------|----------|
| 1 | - | - | - | - |
| 2 | - | - | - | - |
| 4 | - | - | - | - |
| 8 | - | - | - | - |
| 16 | - | - | - | - |
| 32 | - | - | - | - |
| 64 | - | - | - | - |
| 96 | - | - | - | - |

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

### 1.4 Orion (Jetson Orin)

**Specs:** ~64 GB unified memory, ARM architecture
**Thread counts tested:** TBD (powers of 2 up to max)
**Note:** perf event names differ on ARM — check available events before running

*(same table structure as Luna — fill in after specs confirmed and perf events verified)*

---

## Section 2: Cross-Machine Comparison

Comparison at 1T and max-T across all machines. Fixed read model and DB to isolate machine effect.

### 2.1 LLC Miss Rate% at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| eskape_650mb (142 MB) | 34.21 | - | - | - |
| eskape_human_4gb (3.8 GB) | - | - | - | - |
| standard_8gb (7.6 GB) | - | - | - | - |
| standard_16gb (15 GB) | - | - | - | - |

### 2.2 LLC Miss Rate% at Max Thread — reads_hac

| DB | Luna (96T) | Minerva (TBD) | Lab Desktop (TBD) | Orion (TBD) |
|----|-----------|---------------|------------------|------------|
| eskape_650mb (142 MB) | - | - | - | - |
| eskape_human_4gb (3.8 GB) | - | - | - | - |
| standard_8gb (7.6 GB) | - | - | - | - |
| standard_16gb (15 GB) | - | - | - | - |

### 2.3 Time (s) at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| eskape_650mb (142 MB) | 21.924 | - | - | - |
| eskape_human_4gb (3.8 GB) | - | - | - | - |
| standard_8gb (7.6 GB) | - | - | - | - |
| standard_16gb (15 GB) | - | - | - | - |

### 2.4 Classified% at 1 Thread — reads_hac

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| eskape_650mb (142 MB) | 65.28 | - | - | - |
| eskape_human_4gb (3.8 GB) | - | - | - | - |
| standard_8gb (7.6 GB) | - | - | - | - |
| standard_16gb (15 GB) | - | - | - | - |

*(Repeat sections 2.1–2.4 for reads_fast and reads_sup once data is collected)*

---

## Section 3: DB Size vs Classified% Summary

How classification rate changes as DB grows. Expected: more classified with larger DB.

### reads_hac — all machines, 32T (or max available)

| DB | Luna | Minerva | Lab Desktop | Orion |
|----|------|---------|-------------|-------|
| eskape_650mb (142 MB) | 65.28% | - | - | - |
| eskape_human_4gb (3.8 GB) | - | - | - | - |
| standard_8gb (7.6 GB) | - | - | - | - |
| standard_16gb (15 GB) | - | - | - | - |

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

| Species | eskape_650mb | eskape_human_4gb | standard_8gb | standard_16gb |
|---------|-------------|-----------------|--------------|---------------|
| Enterococcus faecium | - | - | - | - |
| Staphylococcus aureus | - | - | - | - |
| Klebsiella pneumoniae | - | - | - | - |
| Acinetobacter baumannii | - | - | - | - |
| Pseudomonas aeruginosa | - | - | - | - |
| Enterobacter spp. | - | - | - | - |
| Human (if applicable) | - | - | - | - |
| Other classified | - | - | - | - |
| Unclassified | - | - | - | - |

*(Repeat for each machine × read model combination)*
