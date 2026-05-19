# Nanopore Project — Summary & Quick Reference

> This is the short version. Full explanations are in `knowledge_base.md`.
> Focus: what goes in, what comes out, what happens, why it matters.

---

## The Big Picture

We are building a fast, memory-efficient pipeline to identify dangerous bacteria (ESKAPE pathogens) from patient samples — in hours instead of days.

```
Patient sample
    ↓  wet lab prep
Flow cell (sequencer)
    ↓  electrical signal
POD-5 file (raw data)
    ↓  Dorado (GPU, basecaller)
BAM / FASTQ (reads = ATGC strings)
    ↓  Kraken-2 (CPU, classifier)
Species report → "Patient has P. aeruginosa"
```

---

## Stage 1 — Sequencer → POD-5

**What goes in:** DNA from patient sample (after wet lab prep)

**What happens:**
- DNA passes single-stranded through a tiny protein pore in a membrane
- Voltage across membrane drives DNA through
- Different DNA letters (A/T/G/C) partially block current by different amounts
- Electronics measure this current 5000 times per second
- 5–6 letters are inside the pore at once (k-mer window) — so each reading encodes a 6-letter pattern, not one letter
- All 512 channels (MinION) read in parallel, each on a different DNA strand

**What comes out:** POD-5 file
- Binary file (Apache Arrow format)
- Contains per-read raw signal arrays (int16 values = current over time)
- Contains metadata: flow cell ID, run ID, sample rate, calibration values
- One file can contain thousands to hundreds of thousands of reads

**Key numbers:**
- Sample rate: 5000 Hz (5000 current readings per second per channel)
- MinION: ~512 channels, ~10–30 GB output per run
- PromethION: ~3000 channels, up to 10 TB per run
- Our file: 4 GB, 104,478 reads, flow cell FLO-MIN114 (R10.4.1)

**Why POD-5 and not just text:**
- Raw signal is huge — need compression + fast random access
- POD-5 is ~4x smaller than old FAST5 format (also replaced it)
- Basecaller needs to jump to specific reads without scanning whole file

**Barcoding / multiplexing:**
- Up to 24 patient samples can be mixed into one flow cell run
- Each sample gets a unique short DNA tag (barcode) attached during prep
- All samples sequence together — reads are sorted (demultiplexed) afterward by Dorado
- Our data used kit SQK-NBD114-24 → 12 barcodes (12 patient samples) + unclassified

---

## Stage 2 — POD-5 → BAM/FASTQ (Dorado)

**What goes in:** POD-5 file (raw electrical signal)

**What happens (inside Dorado):**
1. Normalize raw int16 signal → picoamperes (using calibration from POD-5 metadata)
2. CNN front-end — 1D convolutions downsample signal from 5000 Hz → ~400 Hz (one step per base)
3. Transformer backbone — mixes context across time so each position knows its neighbors
4. Linear projection → probability over {A, T, G, C, blank} at each time step
5. CTC decoding — finds most likely ATGC sequence given all possible alignments
6. Demultiplexing — identifies barcode in each read, sorts into per-barcode BAM files

**What comes out:** BAM files (one per barcode)
- BAM = compressed binary format storing ATGC reads + quality scores
- Each read = one decoded DNA strand = one ATGC string
- Quality score per base = how confident Dorado was about each letter

**A read looks like:**
```
ATGCGATCGGCTAGCTAGCTAGCATGCGATCGGCTAGCTAGCATGCGATCG...
```
One read = one DNA strand that passed through one pore.

**Three model modes:**

| Mode | Speed (GTX 1650) | Accuracy | Use case |
|---|---|---|---|
| fast | ~5 min / 104k reads | Lower | Quick test |
| hac | ~71 min / 104k reads | High | Standard |
| sup | OOM on GTX 1650 | Highest | High-end GPU only |

**Commands:**
```powershell
# Set variables first
$dorado = "C:\Users\chira\OneDrive\Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe"
$pod5   = "pod5 data\FBE01990_24778b97_03e50f91_10.pod5"
$out    = "results\hac"

# Run basecalling + demultiplexing
& $dorado basecaller hac $pod5 --kit-name SQK-NBD114-24 --output-dir $out --batchsize 64
```

**Hardware notes (GTX 1650, 4 GB VRAM):**
- `fast` works fine
- `hac` works but slow — Dorado auto-selects batch size 64, takes ~71 min
- `sup` — OOM crash
- Progress bar shows `0%` the whole time (Dorado display bug) — check `nvidia-smi` to confirm it's running (should show 99% GPU util)
- Run in background or leave terminal open — do not close

---

## Stage 3 — BAM → FASTQ (samtools)

**Why:** Kraken-2 takes text (FASTQ), not binary (BAM). Need to convert.

**Command:**
```bash
samtools fastq barcode02.bam > barcode02.fastq
```

**FASTQ format** — 4 lines per read:
```
@read_id          ← name
ATGCGATCGG...     ← ATGC sequence
+                 ← separator
IIIHHGGG...       ← quality scores (ASCII-encoded confidence per base)
```

**Watch out for:** filenames with spaces or parentheses (e.g. `file (3).bam`) — shell will break. Rename first:
```python
os.rename("file (3).bam", "barcode02.bam")
```

---

## Stage 4 — FASTQ → Species Report (Kraken-2)

**What goes in:** FASTQ reads from one barcode (one patient sample)

**What happens:**
1. Slide a 35-letter window across each read → extract k-mers
2. Hash each k-mer → look it up in the database
3. Each k-mer maps to a taxon ID (or LCA of multiple taxa)
4. Aggregate all hits → majority vote → classify read to a species
5. Report % of reads at each taxonomy level

**What comes out:** species report
```
100.00%  44  Pseudomonas aeruginosa  (taxid 287)
```

**Report columns:** % reads | read count | rank | taxon ID | species name

**Standard DB vs our custom DB:**

| | Standard DB | Our ESKAPE DB |
|---|---|---|
| Size | 180 GB | 650 MB |
| Species | All known | 6 ESKAPE only |
| RAM needed | 180 GB | <1 GB |
| Build time | Hours | 30 seconds |
| Runs on Colab | No | Yes |

**Command:**
```bash
kraken2 --db eskape_db --report report.txt barcode02.fastq > output.kraken
```

**Our result:** barcode02 from AIIMS run → 100% *Pseudomonas aeruginosa* (44 reads, 0.6 seconds)

---

## The 6 ESKAPE Pathogens

| Letter | Species | Taxon ID | Why dangerous |
|---|---|---|---|
| E | Enterococcus faecium | 1352 | Resistant to vancomycin |
| S | Staphylococcus aureus | 1280 | MRSA — resists most antibiotics |
| K | Klebsiella pneumoniae | 573 | Resistant carbapenems (last resort) |
| A | Acinetobacter baumannii | 470 | Multi-drug resistant, hospital ICUs |
| P | Pseudomonas aeruginosa | 287 | Found in barcode02 of our AIIMS data |
| E | Enterobacter cloacae | 550 | Broad resistance, gut infections |

---

## Research Goals

### Goal 1 — Memory-efficient Kraken-2 (§4.3)
**Problem:** 180 GB DB doesn't fit in RAM on edge/clinical devices.
**Approach:** Reduce DB size using Bloom filters or learned indexes.
**Metric:** accuracy vs memory trade-off curve.

### Goal 2 — Kolin sir's Caching Layer (§8)
**Problem:** pipeline recomputes results for near-identical reads (same species, same region).
**Solution:** build two caches:
- **Kraken-2 (CPU):** Hot-K-mer LRU cache — pin frequent k-mer lookups in L3 cache. Uses Intel TBB (lock-free) + AVX-512 SIMD (batch lookups).
- **Dorado (GPU):** Signal-to-Base cache in CUDA shared memory — LSH fuzzy matching to skip NN forward pass for near-duplicate signal windows.

**Immediate deliverable:** 2-page profile report using `perf` (Kraken-2) + Nsight (Dorado) by ~2026-05-25.

### Goal 3 — Time & Accuracy Improvement (assigned 2026-05-18, §14)

**Two axes from Kolin sir's Meeting 3 direction:**

**Time improvement — storage access + compute:**
- Find **cache reuse** opportunities across the POD-5 → Dorado → Kraken-2 flow
- Profiling tools to use:
  - `gprof` — CPU call-graph, find which functions consume the most time
  - `Valgrind / cachegrind` — cache miss rates, memory access pattern analysis
- Find **matrix-vector / vector-matrix / matrix-matrix blocks** in Kraken-2 and Dorado source
- Apply **cache blocking (tiling)** — restructure loops so data stays in L1/L2 cache
- Apply **SIMD / MMX2 / AVX2 / AVX-512** — vectorize inner loops, process multiple k-mers per instruction

**Accuracy improvement:**
- Improve classification accuracy through the full pipeline (methods TBD in follow-up meetings)

### Team / GitHub Structure (assigned 2026-05-18)
- **Repo 1:** Chirag K + Chirag S — code, experiments, meeting minutes
- **Repo 2:** Rishabh + Rohit — their work and contributions
- Both repos must stay up to date and be accessible to Kolin sir at all times

---

## Hardware Constraints (This Machine)

| Component | Spec | Impact |
|---|---|---|
| GPU | GTX 1650, 4 GB VRAM | hac works (slow), sup OOM |
| RAM | 14 GB | 8 GB Kraken-2 DB is tight locally |
| CPU | Ryzen 7 5800H | Fine for Kraken-2 |
| OS | Windows 11 | perf needs WSL2, Dorado works natively |

**Use Colab for:** Kraken-2 (Linux native, small DB fits easily), future sup mode testing
**Use local for:** Dorado fast/hac, Nsight profiling

---

## Tools Reference

| Tool | Purpose | Input | Output |
|---|---|---|---|
| Dorado | Basecalling + demux | POD-5 | BAM (per barcode) |
| samtools | Format conversion | BAM | FASTQ |
| Kraken-2 | Species classification | FASTQ | Species report |
| pod5 (Python) | Inspect POD-5 metadata | POD-5 | Metadata |
| nvidia-smi | Check GPU utilization | — | GPU stats |
| perf | CPU profiling (Linux) | running process | Cache miss rates, hotspots |
| Nsight | GPU profiling | running process | Kernel timings |
| gprof | CPU call-graph profiling | compiled binary | Function-level time breakdown |
| Valgrind / cachegrind | Cache + memory analysis | running process | Cache miss rates, access patterns |

---

## Key Findings So Far

1. GTX 1650 can run Dorado `fast` (~5 min) and `hac` (~71 min) on 104k reads
2. `hac` reduces unclassified reads from 6.5 MB → 896 KB vs `fast` (better barcode detection)
3. Custom ESKAPE DB = 650 MB, built in 30 seconds, runs on Colab
4. barcode02 from AIIMS run = *Pseudomonas aeruginosa* (100%, 44 reads, 0.6s)
5. Dorado progress bar shows `0%` the whole time — use `nvidia-smi` to verify it's running
6. Dorado ignores `--batchsize` flag and runs at 64 regardless on this GPU
7. ONT no longer distributes Dorado on GitHub — download from `cdn.oxfordnanoportal.com`

---

## Open Questions

- What does **MBR** stand for exactly?
- Is there a **lab server** we can SSH into for profiling (perf + Nsight)?
- What is **CROC** tool used for in this project (BEDROC metric)?
- Which barcodes correspond to which patient samples / pathogens?
- Accuracy improvement specifics — methods to be discussed in next meeting
