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

### 3. profiled both pipeline stages (baseline report delivered)

**kraken-2 — 3-tool CPU profile (WSL2 + Minerva):**

| tool | result |
|---|---|
| perf stat | **34.24% cache miss rate**, 301M misses, memory-bound verdict |
| gprof | **67% of runtime in `CompactHashTable::Get()`** — 9.87M calls, pinpoints the bottleneck |
| AMD uProf | **IPC = 0.55** (accurate — perf's cycle counter unreliable in WSL2/Hyper-V) |

**dorado — Nsight Systems GPU profile (GTX 1650, fast mode):**

| metric | value |
|---|---|
| GEMM % of GPU time | **82%** (Tensor Cores, FP16) |
| cudaStreamSynchronize % of CUDA API time | **98.9%** |
| memory transfers | minor — GPU is not memory-starved |

verdict: compute-bound. full details in `report.md`.

### 4. matrix multiply benchmark suite (cache blocking study)

built 12 C implementations in `All_Matric_Mul_perf_stats/` to empirically study how cache access patterns and vectorisation interact with real hardware:

| key finding | detail |
|---|---|
| naive_ijk vs tiled_avx2 | **29.7× slower** at N=1024, **48.2×** at N=2048 — gap widens with N |
| omp_tiled at N=10000 | **2.1× faster than tiled_avx2** — tiling + 4 threads finally pays off at 2.4 GB working set |
| prefetch_ikj paradox | lowest L3 miss% (1.23%) but 9.3× more instructions than ikj_order — software prefetch adds overhead when hardware prefetcher already covers sequential access |
| tiled variants | sub-8× scaling (1024→2048) vs expected O(N³) 8× — tile size stays in L2 regardless of N |

full results in `All_Matric_Mul_perf_stats/PERF_REPORT.md` (N=1024/2048/10000, 22 result files).

### 5. lab server access + documentation

access to two lab servers, both fully documented:

| server | CPU | L3 | RAM | GPU | disk |
|---|---|---|---|---|---|
| **Minerva** | Xeon Gold 6330 (56c/112t @ 2GHz) | 66 MB | 251 GB | 2× A40 | **100% full** |
| **Luna** | Xeon Platinum 8468 (96c/192t @ 3.8GHz) | **210 MB** | **503 GB** | **2× L40S** | 74% (236 GB free) |

luna's `perf_event_paranoid = 1` confirmed — hardware counters (LLC-load-misses, stalled-cycles-backend, TMA) work for all users. matmul re-run on Luna will give accurate IPC for the first time.

---

## why these numbers matter

the profiling results directly justify Kolin sir's caching design:

**kraken-2 (CPU):** a hot k-mer LRU cache keeps recently-seen k-mers in fast memory. clinical samples have dominant species — the same k-mers repeat heavily. each cache hit saves one ~100 ns RAM lookup. at 301 million misses per run, even a 20% hit rate saves ~6 seconds.

**dorado (GPU):** a signal-to-base (S2B) cache in CUDA shared memory skips the neural network forward pass for signal windows similar to ones already decoded. GEMM is 82% of GPU time — a 30% cache hit rate would save ~25% of total GPU time. the cache lookup must happen GPU-side (CUDA shared memory + LSH) and must be faster than one GEMM call (~19.6 ms avg).

---

## hardware i'm running on

**local machine:**

| component | spec |
|---|---|
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |

WSL2 note: Hyper-V blocks LLC-specific perf counters. perf also needs to be built from source for the Microsoft WSL2 kernel (linux-tools-generic doesn't cover it). full build instructions in `knowledge_base.md §15.3`.

**lab servers:**

| server | CPU | cores | L3 | RAM | GPU | disk |
|---|---|---|---|---|---|---|
| **Minerva** | Xeon Gold 6330 (Ice Lake) | 56c/112t @ 2 GHz | 66 MB | 251 GB | 2× A40 (45 GB) | **100% full** |
| **Luna** | Xeon Platinum 8468 (Sapphire Rapids) | 96c/192t @ 3.8 GHz | **210 MB** | **503 GB** | **2× L40S (46 GB)** | 74% (236 GB free) |

Luna has `perf_event_paranoid = 1` — all hardware perf counters work for all users. Luna is the primary server for future benchmarks. Minerva disk is full — no new data can be written.

---

## repo structure

```
├── README.md                    ← this file
├── report.md                    ← full profiling report (perf + nsight + gprof + AMD uProf)
├── report1.md                   ← earlier 2-page profiling report (tables + raw numbers)
├── knowledge_base.md            ← deep-dive notes on everything (§0–§21)
├── summary.md                   ← quick reference — what goes in, what comes out
├── updates.md                   ← chronological session log
├── meeting_minutes.md           ← notes from meetings with mam and Kolin sir
├── plan.md                      ← research plan and next steps
├── Luna_vs_Minerva.md           ← side-by-side hardware comparison of both lab servers
├── All_Matric_Mul_perf_stats/   ← matrix multiply benchmark suite (WSL2 perf stat)
│   ├── PERF_REPORT.md           ← full results: N=1024/2048/10000, cache analysis
│   ├── README.md                ← build/run instructions
│   ├── Makefile
│   ├── *.c                      ← 12 implementations (naive_ijk through prefetch_ikj)
│   ├── run_N10000.sh / run_wsl_perf.sh / run_cache_hierarchy.sh
│   └── perf_results/N10000/     ← raw perf stat output for all 11 binaries
├── Minerva/                     ← minerva server docs (Xeon Gold 6330, 2× A40)
│   ├── minerva_stats.md         ← CPU/RAM/GPU/disk/tool inventory
│   ├── install_tools.md         ← tool install commands (needs sudo)
│   ├── user_guide.md            ← user management (create/restrict accounts)
│   ├── internet_access.md
│   └── profiling/
│       ├── plan.md              ← Minerva profiling plan (Kraken-2 + Dorado)
│       ├── results_kraken2.md   ← result tables (templates, to fill on Minerva)
│       └── results_dorado.md
├── Luna/                        ← luna server docs (Xeon Platinum 8468, 2× L40S)
│   ├── luna_stats.md            ← CPU/RAM/GPU/disk/tool inventory
│   ├── install_tools.md         ← tool install commands (needs sudo)
│   ├── user_guide.md            ← first-login checklist, run matmul on Luna
│   ├── user_management.md       ← create/restrict accounts (student account guide)
│   └── profiling/
│       ├── plan.md              ← 4-phase Luna profiling plan
│       ├── results_matmul_luna.md
│       ├── results_kraken2.md
│       └── results_dorado.md
├── scripts/
│   ├── tag_genomes.py           ← tags ESKAPE genome FASTAs with kraken taxon IDs
│   ├── fix_seqid_map.py         ← builds seqid2taxid.map from tagged FASTAs
│   └── fix_prelim_maps.py       ← fixes ACCNUM→TAXID in kraken prelim_map files
└── resources/
    └── profiling_from_zero_part1.pdf
```

---

## what's next

**profiling (Luna):**
- re-run matmul benchmark suite on Luna — get accurate IPC (no Hyper-V noise), compare Intel vs AMD cache behaviour
- run kraken-2 perf + gprof + TMA on Luna — confirm IPC ~0.55, get real LLC miss rate
- run Nsight Compute on Dorado GEMM kernel on Luna L40S — SM occupancy, arithmetic intensity, Tensor Core utilization

**implementation:**
- start implementing the Hot-K-mer LRU cache layer for kraken-2 (`CompactHashTable::Get()` is the confirmed target)
- benchmark cache hit rate on real AIIMS barcode02 (Pseudomonas aeruginosa dominant) vs mixed-species barcodes

**profiling tools still to run:**
- `cachegrind` for per-function LLC miss rates on kraken-2 (Minerva disk full — run on Luna)
- `perf record` for source line hotspot mapping inside `CompactHashTable::Get()`

---

## colab notebook

full pipeline run (dorado fast/hac/sup + kraken-2 classification for all barcodes):  
https://colab.research.google.com/drive/1mj3lRxxIFS_qCeStrXszhIYHlJ2Z36bw?usp=sharing
