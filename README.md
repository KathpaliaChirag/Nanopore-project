# nanopore pipeline — ESKAPE pathogen profiling

**chirag kathpalia** | research project under Prof. Kolin Paul

---

## what this project is about

i'm working on making a clinical diagnostic pipeline faster and less memory-hungry.

the pipeline identifies dangerous antibiotic-resistant bacteria (ESKAPE pathogens) from patient DNA samples. it currently works but has two big bottlenecks — one in the GPU basecalling step and one in the CPU classification step. my job is to profile both, find exactly where time is going, and build a caching layer that targets the bottlenecks.

the pipeline looks like this:

```
patient sample (blood / swab)
        ↓  DNA extraction + adapter ligation (wet lab)
flow cell → POD-5 file (raw electrical signal, GBs)
        ↓  dorado (GPU, neural network basecaller)
BAM files (one per patient barcode — ATGC reads)
        ↓  samtools (format conversion)
FASTQ files
        ↓  kraken-2 (CPU, k-mer hash lookup)
species report → "patient has Pseudomonas aeruginosa"
```

why these tools:
- **dorado** — the sequencer outputs raw current readings (squiggles). dorado runs a transformer neural network to decode those into ATGC letters. can't skip it.
- **kraken-2** — instead of aligning every read to every genome (too slow), it hashes 35-letter windows (k-mers) and looks them up in a prebuilt database. fast but memory-intensive.

---

## the 6 ESKAPE pathogens

these are the bacteria this pipeline is built to detect. each one is dangerous because it resists most or all available antibiotics.

| pathogen | taxon ID | why it matters |
|---|---|---|
| Enterococcus faecium | 1352 | vancomycin-resistant |
| Staphylococcus aureus | 1280 | MRSA — resists most antibiotics |
| Klebsiella pneumoniae | 573 | carbapenem-resistant (last resort drug) |
| Acinetobacter baumannii | 470 | multi-drug resistant, common in ICUs |
| Pseudomonas aeruginosa | 287 | found in our AIIMS data (barcode02) |
| Enterobacter cloacae | 550 | broad resistance, gut infections |

---

## what i've done so far

### 1. ran the full pipeline on real AIIMS patient data

the input was `FBE01990_24778b97_03e50f91_10.pod5` — 4 GB, 104,478 reads from 12 barcodes (12 patient samples), from an AIIMS run. real clinical data.

ran dorado in all 3 modes to benchmark speed vs accuracy:

| mode | time (colab T4) | time (GTX 1650) | accuracy gain over prev |
|---|---|---|---|
| fast | 3 min 58s | ~5 min | baseline |
| hac | 19 min 8s | ~71 min | +3–8% classified reads |
| sup | 2h 5min | OOM on GTX 1650 | +0.1–1% |

hac is the sweet spot. fast→hac gives meaningful improvement. hac→sup barely moves the needle and takes 6x longer.

classified all 14 barcodes against our custom ESKAPE DB:
- barcodes 01–07: Pseudomonas aeruginosa
- barcodes 09–12: mixed Klebsiella pneumoniae + Enterococcus faecium
- barcode 13: Enterococcus faecium
- barcode 14: mixed

### 2. built a custom ESKAPE kraken-2 database

the standard kraken-2 DB is 180 GB — doesn't fit in RAM on most edge devices. i built a 650 MB custom DB with only the 6 ESKAPE reference genomes. runs on Colab's free tier. built in ~30 seconds.

scripts for this are in `scripts/`.

### 3. profiled both pipeline stages

this is the core deliverable. two tools, two stages:

**kraken-2 — `perf stat` (CPU profiling)**

ran on WSL2 (Ubuntu 24.04) with the 8 GB standard DB and 104,829 reads.

| metric | value |
|---|---|
| cache miss rate | **34.24%** |
| total cache misses | 301 million |
| wall time | 159.4 s |
| sys time | 52.5 s (33% of total) |

verdict: **memory-bound**. the 8 GB hash table is 500x bigger than L3 cache. every k-mer lookup goes to RAM. the CPU is mostly waiting, not computing.

**dorado — nsight systems (GPU profiling)**

ran on GTX 1650, fast mode, 104,478 reads.

| metric | value |
|---|---|
| GEMM (matrix multiply) % of GPU time | **82%** |
| cudaStreamSynchronize % of CUDA API time | **98.9%** |
| memory transfers | minor (~15% of transfer time) |

verdict: **compute-bound**. 82% of GPU time is pure matrix math (transformer attention + linear layers using FP16 Tensor Cores). the CPU sits idle blocking on `cudaStreamSynchronize` while the GPU works.

---

## why these numbers matter

the profiling results directly justify Kolin sir's caching design:

**kraken-2 (CPU):** a hot k-mer LRU cache keeps recently-seen k-mers in fast memory. clinical samples have dominant species — the same k-mers repeat heavily. each cache hit saves one ~100 ns RAM lookup. at 301 million misses per run, even a 20% hit rate saves ~6 seconds.

**dorado (GPU):** a signal-to-base (S2B) cache in CUDA shared memory skips the neural network forward pass for signal windows similar to ones already decoded. GEMM is 82% of GPU time — a 30% cache hit rate would save ~25% of total GPU time. the cache lookup must happen GPU-side (CUDA shared memory + LSH) and must be faster than one GEMM call (~19.6 ms avg).

---

## hardware i'm running on

| component | spec |
|---|---|
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |

WSL2 note: Hyper-V blocks LLC-specific perf counters. perf also needs to be built from source for the Microsoft WSL2 kernel (linux-tools-generic doesn't cover it). full build instructions in `knowledge_base.md §15.3`.

---

## repo structure

```
├── README.md               ← this file
├── report.md               ← full meeting prep summary (all profiling results)
├── report1.md              ← detailed profiling report (tables + raw numbers)
├── knowledge_base.md       ← deep-dive notes on everything (pipeline, tools, results)
├── summary.md              ← quick reference — what goes in, what comes out
├── updates.md              ← chronological session log
├── meeting_minutes.md      ← notes from meetings with mam and Kolin sir
├── plan.md                 ← research plan and next steps
├── scripts/
│   ├── tag_genomes.py      ← tags ESKAPE genome FASTAs with kraken taxon IDs
│   ├── fix_seqid_map.py    ← builds seqid2taxid.map from tagged FASTAs
│   └── fix_prelim_maps.py  ← fixes ACCNUM→TAXID in kraken prelim_map files
└── resources/
    └── profiling_from_zero_part1.pdf   ← profiling reference material
```

---

## what's next

- run `gprof` on kraken-2 (already compiled with `-pg`) to get function-level time breakdown
- run `cachegrind` to get per-function LLC miss rates (compensates for Hyper-V blocking LLC counters in perf)
- run `perf record` for hotspot function + source line mapping
- try AMD uProf (native Ryzen profiler) for DRAM bandwidth and TMAM breakdown
- run Nsight Compute on the GEMM kernel specifically — SM occupancy, arithmetic intensity, Tensor Core utilization
- start implementing the LRU cache layer for kraken-2

---

## colab notebook

full pipeline run (dorado fast/hac/sup + kraken-2 classification for all barcodes):  
https://colab.research.google.com/drive/1mj3lRxxIFS_qCeStrXszhIYHlJ2Z36bw?usp=sharing
