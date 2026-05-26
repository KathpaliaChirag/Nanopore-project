# Nanopore Project - Knowledge Base

Full deep-dive notes. For a quick reference see `summary.md`.

- 1st meeting with **mam**: 2026-05-11
- Next meeting: **2026-05-18** (Monday)

---

## 0. Pipeline Overview (read this first)

This is the full picture before diving into details. Everything in sections 1-10 is explaining one piece of this:

```
Patient sample (blood / swab)
        │
        ▼  wet lab: DNA extraction + adapter ligation
DNA fragments with adapters
        │
        ▼  nanopore sequencer (MinION / PromethION)
           - voltage pulls DNA through protein pore
           - current blocked differently by each k-mer (5-6 letters at once)
           - 512-3000 channels reading in parallel
POD-5 file  <-- raw electrical signal, ~GBs, binary (Apache Arrow)
        │
        ▼  Dorado basecaller (GPU, transformer NN)
           - normalise signal → CNN downsample → Transformer → CTC decode
           - also demultiplexes barcodes (separates patient samples)
BAM files  <-- one per barcode (patient), ATGC reads + quality scores
        │
        ▼  samtools fastq  (format conversion only)
FASTQ files  <-- same reads, plain text
        │
        ▼  Kraken-2 (CPU, k-mer hash lookup)
           - chops reads into 35-mer windows
           - looks each up in DB → taxon ID
           - majority vote per read
Species report  <-- "barcode02: 100% Pseudomonas aeruginosa"
```

**Why each step exists:**
- POD-5: signal is too big for plain files, needs compression + random access
- Dorado: can't directly read current → letter because 6 letters are in pore at once + irregular timing - need a neural network
- samtools: Kraken-2 takes text (FASTQ), Dorado outputs binary (BAM)
- Kraken-2: aligning each read to every genome is too slow - k-mer hashing does the same thing in milliseconds

**The research problem:** this pipeline works but is slow and memory-hungry at scale. Kraken-2 DB = 180 GB. Dorado recomputes everything even for near-identical reads. Kolin sir's project adds a caching layer to fix both.

The sections that follow unpack each box in the diagram above: what format the data is in, what computation happens, and why the design choices were made this way.

---

## 1. Nanopore sequencing

- How nanopore sequencing works (2 minutes - must watch): https://youtu.be/RcP85JHLmnI?si=S_2spAh13R-XsRiZ

### 1.1 The physical idea (DNA through a hole, current as signal)

DNA is made up of long strands of 4 chemical letters - **A, T, G, C** - called **nucleotides**. The process of reading these strands is called **sequencing**. We sequence to figure out what species are present in a sample (useful for diagnosing infections, environmental monitoring, etc.).

Two popular technologies:
- **Illumina** - uses chemistry + fluorescent dyes + cameras; reads short strands (~150 letters each).
- **Nanopore** - uses electrical signals. A **voltage is held across a membrane** that has a tiny pore in it. When a DNA strand passes *through* the pore, the letters inside partially block the **current**, and different letters block by different amounts. We decode that current signal back into ATGC.

In short, a nanopore device is a **molecular electrical sensor**: DNA in, wobbling current out, computer recovers the letters.

The key advantage of nanopore over Illumina is **read length**. Illumina reads are ~150 letters; nanopore reads are typically 1,000-100,000 letters. Longer reads carry more context per read, which matters for both species identification (more k-mers per read) and the caching work (more redundancy to exploit).

### 1.2 Device structure - flow cell, channels, pores

The device has 3 nested things to keep track of:

- **Flow cell** - a cartridge-like consumable that plugs into the sequencer and can be swapped out. The DNA sample is loaded into it.
- **Membrane** - inside the flow cell, a thin synthetic membrane that holds many **channels**.
- **Channel** - one independent DNA reader. Each channel = **one pore** (a hollow protein tube wide enough for a single DNA strand) + the membrane patch around it + its own electrodes + its own electronics measuring the current over time.

DNA passes *through* the pore. The big win of nanopore is **parallelism** - all channels read at the same time, each on a different DNA strand.

Rough numbers:
- **MinION** flow cell: approximately 512 channels
- **PromethION** flow cell: approximately 2,675 channels (one machine runs many flow cells)

Caveat: not all pores stay healthy through a run - some clog, some die. So channel count is a **theoretical max**; the number actually sequencing at any moment is lower.

### 1.3 K-mer window (5-6 bp), 4096 patterns, "ionic current = voice"

Each pore is long enough that **5-6 nucleotides fit inside it at once**. So the current at any moment does not report a single letter - it reports the **whole 5-mer or 6-mer window** currently inside the pore. A "k-mer" is just "a string of k consecutive letters."

- For k = 6, there are 4^6 = **4,096 possible windows**, each producing its own characteristic current level.
- As DNA ratchets through, the window **shifts by one letter per step** - if window N is `ATGCGA`, window N+1 might be `TGCGAC`. So consecutive readings are overlapping patterns, not isolated ones.
- Each window is like a distinct "tone." A long DNA strand produces a long stream of tones - this is why mam called the ionic current the **"voice" of DNA**.

Think of it like audio: the signal is a continuous waveform, not a sequence of discrete symbols. Recovering the original sequence from the waveform is the basecalling problem (Section 3).

**Why a neural network is needed (basecalling):**

A simple lookup table of "current value → letter" won't work because:
1. The signal encodes a 6-letter window, not one letter at a time.
2. DNA moves through the pore irregularly - the timing of each step is not uniform.
3. Some k-mers produce similar current values.

So the basecaller's neural network must do two jobs simultaneously:
- **Segmentation** - when did the window step from one k-mer to the next?
- **Classification** - which k-mer was inside during each step?

The **basecaller** is the software running this neural network (on CPU/GPU). It reads in the current trace and outputs strings of ATGC called **reads**. Downstream tools like **Kraken-2** consume these reads.

**Q: Why don't we just make the pore small enough to fit only one nucleotide?**

1. **Sensing zone is a volume, not a point.** The current is influenced by everything within the Debye length (~1 nm) around the constriction - not just the single base at the narrowest point. So neighboring nucleotides always affect the signal.
2. **Pores are proteins.** Common ONT pores (CsgG, MspA, alpha-hemolysin) have a reading-head length set by amino-acid folding - typically ~5 nucleotides thick. They cannot be arbitrarily shrunk.
3. **Solid-state alternatives** (graphene, MoS2) could theoretically be single-base wide, but they have much higher noise and no motor protein to slow DNA down, so DNA shoots through too fast to read.
4. **4,096 patterns is more informative than 4** - richer fingerprints, more noise-robust signal.
5. **Decoding works.** Modern basecallers hit >99% accuracy; no incentive to redesign the physics.

### 1.4 POD-5 raw signal format, squiggle visualization

**POD-5 - what it is**

POD-5 is Oxford Nanopore Technologies' current file format for storing the **raw electrical signal** captured by a flow cell during a run. It replaces an older format called **FAST5** (which was built on HDF5).

Why a special format exists at all:
- Signal data is huge - ~4,000 samples/sec x hundreds of channels x hours of runtime = **GBs to TBs per run**.
- POD-5 uses better compression, producing smaller files.
- Faster **random access** - a basecaller can pull out a specific read's signal without scanning the entire file.
- Cleaner schema, based on **Apache Arrow** (a columnar binary format - think of it as Parquet for signal data).

What's inside a POD-5 file:
- **Per-read signal arrays** - the time-series of raw current values for each DNA strand that passed through a pore.
- **Metadata** - channel number, pore ID, run ID, timestamps, calibration values (to convert raw integer samples to picoamperes), sample rate, etc.

**Squiggle - what it is**

A **squiggle** is the **plot of raw current (in picoamperes) versus time** for a single read. It looks like a noisy wavy line with plateaus and transitions:

- **Plateaus** = DNA paused briefly with one k-mer inside the pore.
- **Transitions** = the window shifted by one letter.

Why we look at squiggles:
- Sanity-check signal quality (is the current in a normal range? is the pore healthy?).
- Spot the **adapter region** at the start of each read - the adapter molecule (Section 2) produces a distinctive signal.
- Debug failed basecalling - eyeball where things went wrong (a pore stall, a bubble, etc.).
- Detect **modified bases** (e.g., methylation) which shift current slightly compared to unmodified DNA.

**Where POD-5 sits in the full pipeline**

```
flow cell  →  POD-5 (raw signal, viewable as squiggles)
                            │
                            ▼
                  Dorado / Guppy / Bonito  (basecaller, GPU or CPU)
                            │
                            ▼
                  FASTQ / BAM  (ATGC reads)
                            │
                            ▼
                       Kraken-2  (species ID)
```

POD-5 is the **input** to all Section 3 (basecalling) work - when we run experiments, we'll be opening real POD-5 files and visualizing the squiggles.

---

## 2. Sample preparation pipeline

This section covers the wet-lab steps that happen *before* the sequencer. From a CSE perspective, think of this as the **data ingestion layer** - it transforms a raw biological sample into a structured input format (DNA fragments with adapters) that the sequencer can actually process. Understanding what the adapter looks like physically explains why the squiggle signal looks the way it does.

### 2.1 DNA extraction, fragmentation, and adapter ligation

**Why prep exists at all**

A raw biological sample (patient swab, bacterial culture) can't be loaded into a flow cell directly. The DNA must be extracted, cleaned, broken into manageable fragments, and fitted with engineered "handles" (adapters) before the sequencer can read it.

The three big prep steps:

1. **Extraction and purification** - break cells open, free the DNA, wash away proteins, RNA, and debris. Standard commercial kits handle this.
2. **Fragmentation** - break long DNA into pieces (typically **1 kb to 100 kb** for nanopore, far longer than Illumina's ~150 bp). Long reads are part of nanopore's appeal.
3. **Adapter ligation** - attach an engineered molecule (the "adapter") to each end of each fragment. This is the key step: it makes the DNA pore-compatible.

**The Y-adapter - structure**

Each adapter is a small piece of engineered nucleic acid shaped like a Y:

```
            motor protein  ╲       ╱  leader sequence + tether
            (one Y arm)     ╲     ╱   (the other Y arm)
                             ╲   ╱
                              ╲ ╱
                               │
                            ═══════
                            ═══════   ← double-stranded "stem"
                            ═══════     (this end ligates to fragment)
                               │
                          [DNA fragment]
```

**The three key features of the adapter:**

1. **Motor protein** - a helicase enzyme bound to one arm of the Y.
   - Once threading starts, it sits on top of the pore.
   - Unzips the double-stranded DNA into a single strand (only one strand fits in the pore).
   - **Ratchets DNA through the pore one base at a time, at a controlled rate** (~400 bases/sec for modern chemistries).
   - This is the single most critical component. Without it, DNA's natural electrophoretic speed would shoot it through the pore in microseconds - far too fast to read. The motor protein is the "speed governor," and its rate directly determines the density of signal samples per base.

2. **Leader sequence** - a short, known, single-stranded sequence at the tip of the other Y-arm.
   - It is the first thing that enters the pore.
   - Like all DNA it is negatively charged, so the voltage across the membrane **pulls it in** (electrophoresis).
   - Its sequence is known, so the basecaller uses it as a **start marker** - you can literally see the leader as a distinct early portion of every squiggle.

3. **Docking point (tether)** - a hydrophobic anchor attached to the adapter (typically a cholesterol or lipid tag).
   - Inserts into the membrane near the pores.
   - Holds the adapter (and its attached DNA) close to the membrane surface.
   - **Greatly increases the chance of finding a pore** - without it, DNA would float around in bulk solution and rarely encounter a pore before the run ends.

**Kit names you will encounter**

- **LSK** (Ligation Sequencing Kit) - the standard. Uses ligation as described. Higher accuracy, longer prep time.
- **RAD / Rapid Sequencing Kit** - uses a transposase enzyme that both fragments DNA and inserts adapters in one shot. Prep time drops to ~10 min, but at slightly lower efficiency.

**Why this matters for our project:** every basecalling experiment runs on data that came through this exact adapter mechanism. The **leader signal** at the start of each squiggle is what the basecaller uses to align. The **motor protein's speed** determines how dense each k-mer step is in the signal.

### 2.2 How the adapter gets DNA into the pore

Three forces stacked together get a fragment from "floating in solution" to "threading through a specific pore":

1. **Tether** - the hydrophobic tail on the adapter inserts into the membrane. This biases DNA toward the membrane surface instead of letting it float in bulk solution. Think of it as a load-balancer for DNA-finds-pore events: it increases the effective arrival rate.
2. **Voltage** - DNA is negatively charged. The voltage across the membrane (cis side negative, trans side positive) electrostatically pulls the single-stranded leader sequence into the pore first.
3. **Motor protein** - as the leader threads in, the motor protein (on the other Y-arm) parks on top of the pore. It unzips the double strand and ratchets DNA through one base at a time. The squiggle starts being recorded.

When DNA exits the pore, the pore becomes free and the next adapter+DNA is captured. This is a stochastic process - at any moment only a fraction of channels are actively sequencing, so **effective throughput is less than the theoretical channel count**.

CSE framing: it is a queueing system. Tether = arrival-rate boost, voltage = the driving force, motor protein = service-rate cap.

### 2.3 A-T / G-C base pairing

DNA in nature is mostly a **double helix** - two complementary strands held together by base pairing:

- **A pairs with T** - adenine and thymine (2 hydrogen bonds)
- **G pairs with C** - guanine and cytosine (3 hydrogen bonds)

If one strand reads `5'-ATGCGA-3'`, the other reads `3'-TACGCT-5'` - note the direction reverses (DNA strands run **antiparallel**).

Why this matters for nanopore:

1. **The pore only fits one strand at a time.** Prep uses the motor protein to unzip the double helix and feed a single strand through.
2. **Prep enzymes recognize specific base-pair patterns** (the motor protein, ligases, polymerases all depend on predictable A-T/G-C chemistry).
3. **GC-rich regions are harder to separate** (3 H-bonds vs 2). This causes small accuracy dips in GC-rich stretches of the genome.

### 2.4 MinION, PromethION (and GridION)

Same chemistry, three product scales from ONT:

| Device | Channels / flow cell | Output / run | Form factor | Use case |
|---|---|---|---|---|
| **MinION** | ~512 | ~10-30 GB | USB stick, ~$1k | Field work, small experiments |
| **GridION** | 5 x MinION flow cells | ~150 GB | Desktop box | Lab-scale parallel |
| **PromethION** | ~3,000 x 24-48 flow cells | up to ~10 TB | Rack-mount, ~$100k+ | Production / clinical |

Project-relevant: most public nanopore datasets we will use come from MinION or PromethION runs.

### 2.5 AMR, MBR (terms used in prep / context)

- **AMR = Antimicrobial Resistance.** Bacteria/fungi/parasites evolving resistance to drugs that used to kill them. WHO ranks AMR among the top 10 global health threats. This is the clinical reason nanopore + Kraken-2 matters - fast identification of resistant strains at the point of care. Section 5 goes deeper.
- **MBR** - still unclear what mam specifically meant. Most likely "Multi-drug Bacterial Resistance" (informal, related to MDR - multidrug resistance). Could also refer to a specific resistance-gene database or a kit name. **To clarify with mam at the 2026-05-18 meeting.**

---

## 3. Basecalling

Basecalling is the computational core of the pipeline. It takes the raw electrical signal from POD-5 and produces the ATGC strings that everything downstream depends on. This section covers the problem framing, the neural network architecture, and the signal-processing ideas behind it - the parts most relevant from a CSE perspective.

### 3.0 Basecalling as a machine learning problem

**Input/output:**

```
INPUT  : current(t) — 1-D time-series of float values, sampled ~4 kHz,
         length 10^4 to 10^7 samples per read
OUTPUT : ATGC string, variable length 10^2 to 10^5 bases per read
```

This is a **sequence-to-sequence** problem with three structural challenges:
1. **Variable-length input** - every read is a different number of samples.
2. **Variable-length output** - every read produces a different number of bases.
3. **No fixed input-to-output alignment** - DNA moves through the pore unevenly; one base might span 10 samples, the next 100. There is no constant "samples per base" ratio.

This is structurally **almost identical to speech-to-text** (audio waveform -> words). Modern basecallers borrow directly from speech-recognition architectures. *Useful mental model: nanopore basecalling = speech recognition for DNA.*

**Why it is hard:**
- No fixed alignment - need an algorithm that learns segmentation + classification jointly. This is what **CTC loss** (Connectionist Temporal Classification) solves - same idea as DeepSpeech.
- Each signal moment encodes a **6-mer context** (Section 1), so the network has to deconvolve overlapping windows.
- Noise: pore wear, ionic fluctuations, modified bases (methylation), pore-to-pore variability.
- Scale: a single PromethION run can generate up to ~100 TB of signal; real-time inference during the run is the target.

**Training:**
Labeled data comes from running samples with **known sequences** (from Sanger sequencing or synthetic constructs) through the device, producing `(squiggle, known_sequence)` pairs. Modern training sets contain millions of such pairs across species and pore chemistries. Training is offline, expensive, and GPU-cluster scale.

**Where inference runs:**
- **GPU-first.** Dorado is GPU-native; a CPU fallback exists but is 10-100x slower.
- A modern NVIDIA GPU (A100, H100) basecalls a PromethION run in hours; without GPU it takes days to weeks.
- This is the surface where **`perf` + Nsight profiling** matters (Exp-3, Kolin sir's mail) - SM utilization, memory bandwidth, kernel occupancy.

**One-line summary:** basecalling is real-time speech recognition for DNA, running on GPU, where the "speaker" is a noisy nanopore and the "language" is ATGC.

### 3.1 Dorado, Guppy, Bonito - what each is

Three basecallers from ONT, different generations:

**Bonito** - open-source research basecaller, started ~2019.
- First to use deep learning (CNN + LSTM + CTC) for basecalling, replacing the older HMM-based methods.
- Proof-of-concept that deep learning beats HMM. Still maintained but mainly for research/experimentation.
- Python, PyTorch, hackable - good for academic experiments.
- GitHub: `nanoporetech/bonito`.

**Guppy** - legacy production basecaller (~2017-2023).
- Closed-source binary distribution.
- Evolved from HMM to CNN+RNN+CTC over the years.
- Model flavors: **fast** / **hac** (high accuracy) / **sup** (super accuracy).
- **Deprecated** - being replaced by Dorado.

**Dorado** - current production basecaller (~2022 onward), the one we will use.
- Open source (MPL), C++ with PyTorch under the hood.
- Modern architecture - **transformer-based** (different from the CNN+RNN of older tools).
- Supports:
  - **Simplex** basecalling (one strand at a time, normal mode)
  - **Duplex** basecalling (combine both strands of a fragment for higher accuracy)
  - **Modified base detection** (5mC, 6mA methylation)
- Runs on NVIDIA CUDA and Apple Silicon (Metal).
- Reads POD-5 (and legacy FAST5). Outputs SAM/BAM/FASTQ.
- GitHub: `nanoporetech/dorado`.

| Tool | Status | License | Architecture | GPU support |
|---|---|---|---|---|
| Bonito | Research / open | Open (MIT-like) | CNN + LSTM + CTC | CUDA |
| Guppy | Deprecated | Closed | CNN + RNN + CTC | CUDA, CPU |
| Dorado | Current production | Open (MPL) | Transformer-based | CUDA, Metal |

**For our experiments:** Dorado is the default. We will benchmark one of its models (likely **hac** or **sup**) for speed + accuracy.

### 3.2 Neural network: squiggle to ATGC

The inside of a modern basecaller, viewed as a 5-stage pipeline:

**Stage 1 - Input normalization**
- Raw signal arrives as int16 values from the ADC; convert to picoamperes using per-channel calibration (scale + offset stored in POD-5).
- Optionally normalize per-read (median, MAD scaling) to reduce pore-to-pore variability.
- CSE analogy: this is like normalizing audio volume before feeding it to a speech recognizer.

**Stage 2 - CNN feature extractor (front-end)**
- A stack of **1-D convolutional layers** (typically 3-5 layers) with `stride > 1`.
- Job: downsample the time axis. Raw signal is at ~4 kHz; bases occur at ~400 Hz (approximately 10 samples/base on average). The conv layers compress 10^4-10^7 samples down to a manageable 10^2-10^5 feature vectors.
- Each conv layer learns local patterns: signal-level transitions, plateau shapes, slope features.
- **Output**: a sequence of d-dimensional embedding vectors at the lower rate.
- CSE analogy: this is the same role as a mel-spectrogram front-end in audio processing - it compresses redundant raw samples into informative feature vectors.

**Stage 3 - Sequence backbone (RNN or Transformer)**
- Captures context across time. Needed because each base's signature depends on neighboring 6-mers and on motor-protein pause patterns.
- **Older models** (Bonito, early Guppy): bidirectional LSTM.
- **Modern Dorado**: **Transformer**.
  - Better parallelism (no recurrence) - faster GPU inference.
  - Better long-range context handling via self-attention.
- **Output**: another sequence of d-dim embeddings, now context-aware.

**Stage 4 - Output projection**
- Linear layer projects each time-step embedding to a vocabulary of labels.
- Vocab = `{A, T, G, C, blank}` for standard CTC basecalling.
- **Output**: at each time step, a probability distribution over the label vocabulary.

**Stage 5 - CTC decoding**
- The output is a `T x V` matrix (`T` time-steps x `V` labels).
- CTC algorithm: find the most likely *output sequence* by considering all possible alignments (which time-steps emit which letter, with `blank` handling "no base emitted yet"). The `blank` token is CTC's way of saying "still in the middle of the previous base, don't emit yet" - it handles the variable-duration problem.
- Two decoding modes:
  - **Greedy** - pick argmax at each step; fast, less accurate.
  - **Beam search** - explore top-K hypotheses; slower, higher accuracy. The `sup` models use this.

**Full pipeline:**

```
raw signal (int16, ~10^6 samples)
        │
        ▼
  normalize → float
        │
        ▼
  CNN front-end (stride>1, downsample)
        │
        ▼
  embedding sequence (e.g., 10^4 × 512-d)
        │
        ▼
  Transformer backbone (context mixing)
        │
        ▼
  context-aware embeddings (10^4 × 512-d)
        │
        ▼
  linear projection
        │
        ▼
  label probs (10^4 × 5)   [A, T, G, C, blank]
        │
        ▼
  CTC decoding (greedy / beam search)
        │
        ▼
  ATGC string (~10^3 bases)
```

**Model sizes:**
- `fast`: ~10^7 parameters
- `hac`: ~5x10^7 parameters
- `sup`: ~10^8+ parameters, beam search at inference

Tradeoff: bigger = more accurate, slower, more GPU memory.

**Where the bottleneck is (relevant for Nsight profiling, Exp-3):**
- **Memory bandwidth** - loading weights for each batch is the dominant cost; modern inference is bandwidth-bound, not compute-bound.
- **SM occupancy** - keeping all GPU streaming multiprocessors busy.
- **KV-cache** for transformer attention is memory-heavy.
- **Mixed precision** (FP16 / BF16) is standard for inference.
- These are exactly the metrics you will probe with Nsight Compute / Nsight Systems.

### 3.3 Signal compression - vector quantization, Shannon source coding, Euclidean vectors

This is what mam called the "signal compression angle." Three signal-processing and information-theory ideas that appear inside modern basecallers.

**Vector Quantization (VQ)**

- **Concept**: take a continuous-valued vector and **snap it to the nearest entry in a discrete codebook** of representative vectors. The codebook is learned to minimize reconstruction error.
- **Where used**: in modern neural codecs (VQ-VAE, SoundStream, EnCodec), continuous embeddings get quantized into discrete codes.
- **In basecalling**:
  - The network's internal embeddings live in continuous R^d.
  - VQ can discretize these into cleaner state representations, making it easier to map to discrete base outputs.
  - Also used for signal compression - store/transmit fewer bits per time-step.

**Shannon Source Coding**

- **Concept**: Shannon's source coding theorem - any source can be losslessly compressed to its entropy H(X), and no further.
- **Connection to basecalling**:
  - The nanopore signal has heavy redundancy - consecutive 6-mer windows share 5 of 6 bases, so the signal stream is highly correlated.
  - Raw signal: ~4 kHz x 16 bits = **64 kbps** of raw data.
  - Actual information rate: ~400 bp/sec x 2 bits/base = **~800 bps**.
  - So there is an information-theoretic ceiling: the signal is ~80x redundant. POD-5 compression and downstream representations exploit this.

**Euclidean Vector Representation**

- **Concept**: represent each k-mer (or signal context) as a fixed-dim vector in R^d, where similar contexts are close in Euclidean distance. The classic "embedding" idea familiar from NLP.
- **In basecalling**:
  - The network's intermediate embeddings are Euclidean vectors.
  - The output projection acts as nearest-codeword classification - each output class is an "anchor" vector in embedding space.
  - Euclidean distance is the natural similarity measure here: two 6-mers with similar current values should map to nearby embeddings.

**How the three fit together - the basecaller as a lossy compressor:**

```
raw signal              (high entropy, 64 kbps, noisy)
   │
   │  CNN front-end → lossy compression to embeddings
   ▼
embeddings              (Euclidean vectors, R^512 per step)
   │
   │  Transformer → context mixing in Euclidean space
   ▼
context-aware embeddings
   │
   │  output projection / VQ → discretization
   ▼
label distribution     (discrete, 5 classes)
   │
   │  CTC decoding
   ▼
ATGC string            (discrete, ~800 bps — close to information floor)
```

The journey is: **continuous noisy signal to information-bounded discrete sequence**. Vector quantization is the bridge between continuous embeddings and discrete output. Shannon source coding bounds how much compression is theoretically possible. Euclidean vectors are the language the network thinks in.

---

## 4. Kraken-2

With basecalling done, we have ATGC reads. The next problem is: which species did these reads come from? That is taxonomic classification, and Kraken-2 is the tool that does it. This section covers how it works and why its memory footprint is the bottleneck our research targets.

### 4.1 K-mer hashing to species identification

**The problem Kraken-2 solves:**
Given a read (ATGC string, length ~10^2-10^5), figure out **which species it came from**. This is *taxonomic classification*.

**The naive approach (do not use):**
Align each read against every known reference genome and pick the best match. With ~10^5 reference genomes and ~10^6 reads per sample, you are looking at billions of alignments - computationally hopeless.

**Kraken-2's approach: k-mer matching against a precomputed index.**

Pipeline:

```
read: ATCGATCGATCGATCG...   (length 1000)
       │
       │  split into k-mers (sliding window, k=35 default)
       ▼
   k-mer set: {ATCGATCG..., TCGATCGA..., ...}  (~1000 k-mers)
       │
       │  for each k-mer, hash-lookup in DB
       ▼
   k-mer → species/taxon mapping
       │
       │  aggregate hits, take LCA
       ▼
   classified read: "E. coli (95% confidence)"
```

**Why k-mers work:**
- Two reads from the **same organism** share many k-mers.
- Two reads from **different organisms** share very few k-mers - random-chance overlap is ~4^-35 per k-mer, which is negligibly small.
- So k-mer overlap is a very strong species signal.

**The index (database):**
- Built once from reference genomes (RefSeq, GTDB, etc.).
- Maps `k-mer -> LCA (Lowest Common Ancestor) in NCBI taxonomy`.
- **LCA logic**: if a k-mer appears in both *E. coli* and *Shigella* (close relatives), it maps to their common ancestor (genus level), not to either species. Reads with such k-mers get classified at the genus level - this avoids overconfident false species calls. Think of it as a conservative disambiguation strategy.

**Hashing scheme - minimizers (Kraken-2's key optimization):**
- Naive: store every k-mer in a giant hash table. Too big.
- **Minimizer trick**: for each window of `L` consecutive k-mers, store only the lexicographically smallest k-mer of the window (the "minimizer"). At query time, compute the minimizer for each window of the read and look it up.
- Result: ~10x DB shrinkage with minimal accuracy loss. (Default `k=35`, `m=31` - minimizer is a 31-mer inside each 35-mer window.)

**Output:**
- Per-read classification (taxon ID + confidence)
- Per-sample abundance summary
- Standard Kraken report formats (`.kraken` / `.report`)

### 4.2 Why the database is huge

The Kraken-2 **standard database is ~180 GB** loaded in memory. The size math:

- ~10^5 reference genomes x ~10^6 bp/genome = approximately **10^11 bp** of reference sequence.
- Unique k-mers extracted (k=35, with minimizers, m=31) = approximately **10^10 entries**.
- Each entry: hash + taxon ID = approximately **8 bytes**.
- Total: hash table + auxiliary tables (LCA tree, taxonomy nodes) = **~180 GB**.

**Why the size is a problem:**
- Does not fit in RAM on most laptops/workstations (typical 16-64 GB).
- **Kraken-2 loads the entire DB into memory at startup** - there is no on-disk fallback for the hot lookup path. If you cannot fit it, you cannot run it (at least not with the standard DB).
- For **point-of-care clinical use** (e.g., a device in a hospital triage room), 180 GB is a non-starter.
- For **cloud deployment**, the per-instance memory cost is significant.
- For **field / outbreak response** in low-resource settings, it is completely impractical.

**Practical reduction target (from meeting 2):**
Kraken-2 has a built-in utility (`kraken2-build`) to build a custom DB from any subset of reference genomes. By restricting to ESKAPE pathogen sequences only, the DB can be brought down to **8-16 GB** - fitting in Colab or a standard workstation. Accuracy vs size trade-off must be measured.

This is why memory efficiency is the bottleneck - and your research angle.

### 4.3 Memory efficiency - my research angle

**The question:** can we make Kraken-2 (or a Kraken-2-equivalent classifier) run in **less than 10 GB or even less than 1 GB of memory**, without giving up too much accuracy?

**Approaches in the literature:**

1. **Smaller k / smaller alphabet**
   - Reduce k from 35 to e.g. 25 - smaller k-mer space, smaller DB.
   - Cost: more collisions, lower specificity.

2. **Better minimizer schemes**
   - Optimize the minimizer window size or hash function for tighter packing.
   - Research area: "universal hitting sets," "syncmers."

3. **Approximate membership data structures** - strong candidate direction
   - Use a **Bloom filter** or **Cuckoo filter** instead of an exact hash table.
   - Bloom filter: small false-positive rate, no false negatives, much smaller memory.
   - Research projects: **BIGSI**, **COBS**, **Bloom Filter Trie**.
   - Tradeoff: false positives cause spurious k-mer hits and noisier classification.

4. **Hierarchical / compressed databases**
   - **Centrifuge** uses an **FM-index** (compressed BWT) - smaller than Kraken-2's hash, slower lookups.
   - Kraken-uniq uses HyperLogLog counters for unique-k-mer counting.

5. **Streaming / partial classification**
   - Do not hold the full DB in RAM; stream queries against an on-disk index.
   - Trades latency for memory.

6. **Learned indexes / neural classifiers**
   - Replace the hash table with a neural network that maps k-mer -> taxon.
   - Active research; not yet production-quality but an interesting direction.

**Where you might land:**
Pick one direction - probably **Bloom-filter-based** or **learned-index-based** - and benchmark on real nanopore data (Dorado-called reads). Metrics:
- Memory footprint (peak RSS)
- Classification accuracy (precision/recall vs full-DB Kraken-2)
- Query throughput (reads/sec)

**Why nanopore data specifically helps your angle:**
- Nanopore reads are **long** (10^3-10^5 bp), so each read contains many k-mers.
- Even a noisier (lower-recall) classifier can still get a confident species call by **majority voting across the k-mers in a single long read**.
- This noise tolerance gives a smaller, lossier index room to work - which is the lever your research can pull on.

Exp-2 (Kraken-2 internals) + Exp-3 (end-to-end Dorado to Kraken benchmark) are the experimental scaffolding for this.

---

## 5. ESKAPE + AMR

### 5.1 ESKAPE pathogens

ESKAPE is an acronym for six bacterial pathogens that are especially good at *escaping* the effects of antibiotics. WHO lists them as priority threats:

- **E** - *Enterococcus faecium*
- **S** - *Staphylococcus aureus* (MRSA is the famous resistant variant)
- **K** - *Klebsiella pneumoniae*
- **A** - *Acinetobacter baumannii*
- **P** - *Pseudomonas aeruginosa*
- **E** - *Enterobacter* species

They are common in hospital-acquired infections, have evolved resistance to most antibiotics, and leave doctors with few treatment options. They are the "headline" organisms our pipeline is built to identify quickly.

### 5.2 AMR / MBR - why the crisis is growing

**Drivers of AMR:**
- Overuse of antibiotics in clinical settings.
- Massive use in agriculture (livestock).
- Antibiotic residues in the environment (wastewater).
- **Horizontal gene transfer** - resistance genes spread between bacteria via plasmids, not just inherited; AMR can jump species.

**Impact:**
- WHO projection: AMR could cause **~10 million deaths/year by 2050** if unchecked.
- Treating resistant infections costs thousands more per patient.
- "Last-line" antibiotics like colistin are losing effectiveness.

**MBR** - still to be clarified with mam at the next meeting. Most likely "Multi-drug Bacterial Resistance" (informal abbreviation, related to MDR). See open question flagged in section 2.5.

### 5.3 Kraken-2's role in detection

**The clinical workflow we are building toward:**

1. Patient sample (blood, swab) - DNA extraction
2. Nanopore sequencing - POD-5 raw signal
3. **Dorado** basecalling - ATGC reads
4. **Kraken-2** classification - which bacterial species are present
5. (Parallel step: identify resistance genes via tools like **CARD** / **ResFinder**)
6. Doctor gets: "Patient has K. pneumoniae, resistant to carbapenems."
7. Targeted antibiotic prescribed within **hours** instead of days.

**Speed matters:**
- Traditional culture-based ID takes **24-72 hours**.
- Nanopore + Kraken-2 can do this in **1-4 hours**.
- For sepsis patients, faster ID = lives saved.

**Why memory matters (research angle, again):**
- Point-of-care devices have limited RAM (often 16 GB).
- Hospital servers need to run many concurrent samples.
- Field deployment (low-resource clinics, outbreak response) needs lightweight tools.
- Your work could enable Kraken-2-class classification on a laptop or even Raspberry-Pi-class hardware.

---

## 6. Experiments

### Exp-2 - components
- Study Kraken-2 internals - k-mer hashing
- Test basecalling models on available data; measure accuracy + inference time
- Understand Dorado mechanics
- CPU/GPU memory model

### Exp-3 - end-to-end
- Dorado + Kraken end-to-end accuracy measurement
- Profile with `perf` + Nsight (per Kolin sir's mail)

---

## 7. Setup and Installation

### 7.1 Installing Dorado on Windows

**What Dorado is:** the current production basecaller from ONT. Takes POD-5 raw signal files as input, outputs BAM/FASTQ reads. GPU-accelerated (CUDA on NVIDIA).

**Where to get it:**

ONT no longer distributes Dorado binaries via GitHub release assets (they show 0 assets). The actual download lives on ONT's CDN:

```
https://cdn.oxfordnanoportal.com/software/analysis/dorado-<version>-win64.zip
```

For v1.4.0 (current as of 2026-05-16):
```
https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-win64.zip
```

**Installation steps:**

1. Download the zip (~2.8 GB):
```powershell
curl -L "https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-win64.zip" -o dorado-1.4.0-win64.zip
```

2. Extract:
```powershell
Expand-Archive -Path dorado-1.4.0-win64.zip -DestinationPath dorado\
```

3. Binary is at:
```
dorado\dorado-1.4.0-win64\bin\dorado.exe
```

4. Verify:
```powershell
.\dorado\dorado-1.4.0-win64\bin\dorado.exe --version
# Output: 1.4.0+ba44a013
```

**Installed location (this machine):**
```
C:\Users\chira\OneDrive\Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe
```

**GPU:** Dorado auto-detects NVIDIA GPU via `--device auto` (default). No extra config needed.

**Running basecalling (basic command):**
```powershell
.\dorado.exe basecaller hac path\to\data.pod5 --output-dir results\
```

Model options: `fast` (quickest), `hac` (high accuracy, standard), `sup` (super accuracy, slowest). Model version is auto-selected based on flow cell metadata in the POD-5 file.

---

## 8. Kolin sir's Project - Caching Layer + Profiling

### 8.0 The core idea

Genomic pipelines (Dorado + Kraken-2) often process **repetitive sequences** - same species, same genomic regions, technical replicates. Right now, every read goes through the full expensive computation even if it is near-identical to something already processed.

Think of it as the classic "memoization" optimization in programming: if you have already computed the answer for an input, cache it and return immediately on the next call instead of recomputing from scratch. The challenge in the genomic context is that inputs are never exactly identical (noise), so the cache must support **approximate (fuzzy) matching**.

**The fix:** build a **caching layer** at two points in the pipeline:
1. **Signal-level cache** inside Dorado (GPU side) - cache basecalling results for signal windows that are similar to previously seen ones
2. **K-mer frequency cache** inside Kraken-2 (CPU side) - cache k-mer to taxon lookups for hot (frequently accessed) entries

Cache hit = skip the expensive computation entirely. Cache miss = run normally and store the result.

Once both caches exist, the next step is a **genomic-aware cache replacement policy** - smarter than generic LRU, tuned to how DNA reads repeat in clinical metagenomics datasets.

---

### 8.1 Project 1 - Kraken-2 CPU-side cache (Hot-K-mer LRU)

**The bottleneck:**
Kraken-2's k-mer database is ~180 GB. It does not fit in RAM on most machines. Even the portion that is in RAM gets constantly evicted from L3 cache because the lookup pattern is random (hash table access = unpredictable memory addresses). Result: frequent **page faults** and **L3 cache misses** dominate runtime.

From a systems perspective, this is the classic "random access to a large hash map" problem. The data structure is a hash table, which gives O(1) average lookup, but the random memory access pattern defeats hardware prefetching and cache locality - so practical throughput is much lower than the theoretical O(1) suggests.

**The solution Kolin sir wants:**
A **Hot-K-mer LRU cache** - identify the most frequently accessed k-mer to taxon ID entries and pin them in L3 cache (or locked physical memory). When a lookup hits the cache, skip the full hash table lookup entirely.

In clinical metagenomics, a single patient sample is dominated by one or two species (e.g., Pseudomonas aeruginosa). This means a small set of k-mers accounts for the majority of lookups - exactly the regime where a cache pays off. The "hot" k-mers are the ones belonging to the dominant species, and once they are cached the tail of cold lookups (rare k-mers) becomes a smaller fraction of total runtime.

**Tech stack:**
- **Intel TBB (Threading Building Blocks)** - library for lock-free, high-concurrency data structures. Multiple threads can query/update the cache simultaneously without blocking each other (no mutex locks). Think of it as concurrent hash map with atomic operations instead of coarse-grained locking.
- **AVX-512 SIMD intrinsics** - batch 8-16 k-mer lookups into a single CPU instruction instead of one at a time. This amortizes memory latency across a vector width - instead of issuing 16 separate loads, you issue one wide load and process all 16 in parallel.
- **ARM + NEON** - same caching logic ported to ARM processors (for edge/hospital devices that run on ARM chips). NEON is ARM's equivalent of AVX-512.
- **Profiling tools:** VTune or `perf` - measure cache hit rate vs remaining I/O overhead to quantify the gain.

**Expected outcome:** measurable throughput gain on high-redundancy datasets (the exact regime in clinical metagenomics - same patient, same bacteria, many reads).

---

### 8.2 Project 2 - Dorado GPU-side cache (Signal-to-Base cache)

**The bottleneck:**
Dorado runs a full Transformer forward pass for every signal window - even when the input signal is nearly identical to one it processed moments ago (same species, same genomic region). This is wasteful: you are burning GPU TFLOPs on computation whose answer you already have.

This is structurally identical to the Kraken-2 problem, but on the GPU side and with an additional complication: signal windows are never *exactly* identical (electrical noise), so an **exact-match cache** would have a near-zero hit rate. The cache must support **approximate nearest-neighbor lookup**.

**The solution Kolin sir wants:**
A **Signal-to-Base (S2B) cache** in CUDA shared memory. Before sending a signal window through the neural network, check: "have I seen something *similar* to this before?" If yes - return the cached basecall. If no - run the network, store result in cache.

**The key challenge:** signal windows are never exactly identical (noise), so you need **fuzzy matching**, not exact matching.

**Tech stack:**
- **LSH (Locality Sensitive Hashing)** - a hashing technique where *similar* input vectors hash to the *same bucket* with high probability. Allows fast approximate nearest-neighbour search on the GPU. Similar signals hash to the same bucket, and that bucket is the cache key. This is the same family of techniques used in document similarity search and recommendation systems.
- **CUDA Shared Memory** - fast on-chip GPU memory (much faster than VRAM/global memory). The rolling cache buffer lives here for low-latency retrieval. Shared memory is per-SM and has ~100 GB/s bandwidth vs ~2 TB/s for global VRAM for sequential access, but for small random lookups shared memory wins decisively.
- **NanoMambaNet** - the edge inference pipeline this cache will be deployed alongside (mentioned by Kolin sir).

**What needs to be measured (from the mail):**
- Fraction of signal windows that fall within LSH collision threshold (i.e., cache-hit-able)
- Accuracy vs speed trade-off curve - how much accuracy do you lose for how much speedup?
- The "practical operating envelope" - at what level of read redundancy does the cache give net positive throughput?

---

### 8.3 Immediate deliverable - 2-page profile report

**Deadline: ~2026-05-25** (2 weeks from first meeting on 2026-05-11)

> *"The first step is to use tools like perf and Nsight and produce a 2-page profile report in the first 2 weeks or so."*

You cannot design a cache without first knowing *where the time is actually going*. The profile report establishes the baseline - it answers: what are the bottlenecks, and how much headroom does a cache have to recover?

The profiling workflow mirrors how any systems optimization project starts: measure first, then optimize. Do not guess where the bottleneck is.

**Report needs to cover:**

For **Dorado (Nsight):**
- Which CUDA kernels dominate runtime (Transformer attention, conv layers, CTC decoding)?
- Memory transfer overhead (CPU to GPU)?
- SM (Streaming Multiprocessor) occupancy - are all GPU cores being used?
- Memory bandwidth saturation?

For **Kraken-2 (perf):**
- L3 cache miss rate on k-mer lookups
- Memory bandwidth consumption
- Hotspot functions (which lines of Kraken-2 code burn the most CPU time)
- Page fault rate (disk to RAM transfers)

---

### 8.4 Profiling setup - where and how to run

**Why Google Colab will not work:**
- `perf` needs root/kernel-level access - Colab does not give this
- Nsight needs direct GPU access and GUI - not available on Colab
- Kraken-2 standard DB is ~100 GB - will not fit in Colab storage

**Options ranked:**

| Option | Dorado (Nsight) | Kraken-2 (perf) | Notes |
|---|---|---|---|
| **WSL2 on your machine** | CUDA passthrough works | perf works (built from WSL2 kernel source — see §15.3); LLC counters blocked by Hyper-V, use cachegrind for those | Best local option |
| **Your Windows machine (native)** | Nsight works on Windows | perf is Linux-only | Partial |
| **University HPC / lab server** | if NVIDIA GPU available | Linux + root | Ideal - ask mam/Kolin sir |
| **Google Colab** | Not viable | Not viable | Not viable for profiling |

**Best path:** Set up **WSL2** on your Windows machine. It gives a full Linux environment, your NVIDIA GPU passes through via CUDA, and both `perf` + Nsight work.

**Profiling commands:**

Dorado with Nsight Systems:
```bash
nsys profile dorado basecaller hac data.pod5 --output-dir results/
# Produces a .nsys-rep file → open in Nsight Systems GUI
```

Kraken-2 with perf:
```bash
perf stat -e cache-misses,cache-references,instructions,cycles,branches,branch-misses \
    kraken2 --db /path/to/db reads.fastq
# Prints hardware counter table after run completes
# Note: LLC-loads and LLC-load-misses show <not supported> on WSL2 (Hyper-V blocks them)
# Use cachegrind for per-function LLC miss data instead
```

**The profiling workflow:**
```
POD-5 data → Dorado (Nsight watching) → BAM reads → Kraken-2 (perf watching)
                     ↓                                        ↓
             GPU profile report                      CPU profile report
                                    ↓
                           2-page combined report
```

---

### 8.5 Connection to the memory-efficiency research angle (section 4.3)

Both the research angle and Kolin sir's project target the same root problem - Kraken-2's random memory access pattern:

- **Research angle (section 4.3):** reduce the DB size (Bloom filters, learned indexes) so more fits in RAM
- **Kolin sir's project (section 8.1):** keep the hot entries in L3 cache so frequent lookups skip RAM entirely

These are complementary, not competing. A smaller DB (from section 4.3) + a hot cache (from section 8.1) together could bring Kraken-2's memory footprint to a point where it is viable on edge hardware. The profile report from section 8.3 gives the numbers that will tell us which lever - DB size or cache - gives the bigger gain for a given engineering effort.

---

## 9. First Inference Run - 2026-05-16

### 9.1 Hardware specs (this machine)

| Component | Spec | Implication for Dorado |
|---|---|---|
| GPU | NVIDIA GeForce GTX 1650 | 4 GB VRAM - tight for hac, too small for sup |
| RAM | 14 GB | ~10 GB free after Windows; 8 GB Kraken-2 DB is risky |
| CPU | AMD Ryzen 7 5800H | 8 cores, good for Kraken-2 CPU work |
| OS | Windows 11 | Dorado works natively; perf needs WSL2 |

**Key takeaway:** GTX 1650 can run Dorado `fast` and `hac` (with reduced batch size), but `sup` is likely OOM. For Kraken-2 with the reduced ESKAPE DB (8-16 GB), Colab is safer than local RAM.

---

### 9.2 The POD-5 file - metadata

Inspected using the `pod5` Python library:

```python
import pod5
with pod5.Reader('file.pod5') as r:
    read = next(r.reads())
    print(read.run_info.flow_cell_product_code)  # FLO-MIN114
    print(read.run_info.sequencing_kit)           # sqk-nbd114-24
    print(read.run_info.experiment_name)          # AIIMS_Shreshtha_1_301025
    print(read.run_info.sample_rate)              # 5000
    print(r.num_reads)                            # 104478
```

| Field | Value | What it means |
|---|---|---|
| Flow cell | FLO-MIN114 | MinION with R10.4.1 pores - latest chemistry |
| Sequencing kit | SQK-NBD114-24 | Native Barcoding Kit, 24 barcodes - **data is multiplexed** |
| Experiment | AIIMS_Shreshtha_1_301025 | Real clinical data from AIIMS (All India Institute of Medical Sciences) |
| Sample rate | 5000 Hz | 5kHz - newer chemistry, Dorado auto-selects 5kHz models |
| Total reads | 104,478 | Substantial dataset across all barcodes |

**Model Dorado auto-selected:** `dna_r10.4.1_e8.2_400bps_hac@v5.2.0`

---

### 9.3 Barcoding and demultiplexing

**What barcoding means:**

The SQK-NBD114-24 kit allows up to 24 different DNA samples to be loaded into a single flow cell run - each sample gets a unique short DNA tag (a "barcode") attached to its adapters. All samples sequence together and get separated ("demultiplexed") computationally afterward.

In clinical terms: one MinION run = up to 24 patient samples simultaneously. Cost-efficient for hospital settings.

**What Dorado does with `--kit-name`:**

When you pass `--kit-name SQK-NBD114-24`, Dorado does basecalling + demultiplexing in one step. Output is automatically sorted into per-barcode BAM files:

```
results/
  bam_pass/
    barcode01/  ← patient/sample 1
    barcode02/  ← patient/sample 2
    ...
    unclassified/  ← reads where barcode couldn't be identified
```

**Why unclassified is the largest chunk:**

In our run, `unclassified` (3.9 MB) was bigger than any individual barcode. Reasons this happens:
- Reads too short for confident barcode detection
- Degraded barcode sequence (pore damage, sample quality)
- Some samples had very few reads (barcodes 07, 11 only 128K)
- `fast` mode basecalling is less accurate, leading to more uncertain barcode calls

Running `hac` mode should reduce the unclassified fraction because better basecalling leads to more confident barcode detection.

---

### 9.4 Dorado inference results - fast vs hac

**fast mode - completed successfully**

Command:
```powershell
dorado.exe basecaller fast data.pod5 --kit-name SQK-NBD114-24 --output-dir results/fast
```

Result: completed quickly, all 12 barcodes + unclassified produced.

| Barcode | BAM size |
|---|---|
| barcode02 | 1.9 MB |
| barcode04, 06, 13 | ~896 KB |
| barcode01, 03, 05, 09, 10, 14 | ~384 KB |
| barcode07, 11 | 128 KB |
| barcode12 | 0 (empty) |
| unclassified | 3.9 MB |

**hac mode - needs forced batch size**

Default run (auto batch size): Dorado benchmarks the GPU to find optimal batch size. On GTX 1650 with 4 GB VRAM, this process OOM-crashed during benchmarking.

Fix - force a small batch size:
```powershell
dorado.exe basecaller hac data.pod5 --kit-name SQK-NBD114-24 --output-dir results/hac --batchsize 16
```

With `--batchsize 16`, Dorado settled on `chunk size 9996, batch size 64` and started processing. Slower than fast but fits in VRAM.

**sup mode** - not attempted yet. Expected to OOM even with reduced batch size on 4 GB VRAM.

---

### 9.5 What the BAM output contains

Each BAM file contains the basecalled reads for one barcode - the ATGC sequences Dorado decoded from the raw signal. BAM is a compressed binary format; to view/work with it you need `samtools`.

Pipeline position:
```
POD-5 (raw signal)
    │
    ▼ Dorado basecaller
BAM files (per barcode — ATGC reads)
    │
    ▼ Kraken-2
Species classification report
```

Next step: feed the per-barcode BAM files into Kraken-2 to identify which ESKAPE pathogens are in each patient sample.

---

### 9.6 fast vs hac - comparison

Both modes ran on the same 104,478-read POD-5 file. Key results:

| Metric | fast | hac |
|---|---|---|
| Time | ~4-5 minutes | ~60+ minutes |
| GPU batch size | auto | forced `--batchsize 16` (4 GB VRAM) |
| unclassified reads | 6.5 MB | 896 KB |
| barcode02 | 2.0 MB | 384 KB |

**Most important finding:** unclassified dropped from 6.5 MB to 896 KB in hac mode. Better basecalling = more confident barcode detection = far fewer reads left unassigned. The per-barcode BAMs are smaller in hac not because there are fewer reads, but because the quality filtering is stricter - only high-confidence reads pass.

**sup mode:** not attempted - expected OOM on GTX 1650 (4 GB VRAM).

---

## 10. Kraken-2 - First Classification Run (Google Colab)

### 10.0 Why Colab for Kraken-2

Kraken-2 is Linux-only. Running it locally on Windows requires WSL2 (not set up yet). Colab gives a free Linux VM with ~12 GB RAM - enough for our small custom DB. The standard 180 GB DB would not fit, but our ESKAPE-only DB at 650 MB fits easily.

---

### 10.1 Setting up Colab environment

**Step 1 - Install condacolab**

Colab uses pip by default and does not have conda/mamba. `condacolab` installs mamba on the Colab VM:

```python
!pip install condacolab -q
import condacolab
condacolab.install()   # runtime restarts automatically after this — normal
```

**Important:** after `condacolab.install()` the runtime restarts. Any variables or installations from before the restart are wiped. Always run install cells *after* the restart, not before.

**Step 2 - Fix Python pin conflict and install tools**

Colab has a Python version pin file that conflicts with mamba. Remove it first:

```python
!rm -f /usr/local/conda-meta/pinned
!mamba install -c bioconda -c conda-forge kraken2 samtools -y -q
```

- `rm -f /usr/local/conda-meta/pinned` - deletes the conflicting pin file (harmless)
- `mamba install -c bioconda -c conda-forge kraken2 samtools` - installs both tools from bioconda (bioinformatics conda channel)
- `-y` - auto-confirm, `-q` - quiet mode

**Verify:**
```python
!kraken2 --version
!samtools --version | head -1
```

---

### 10.2 Downloading ESKAPE reference genomes from NCBI

NCBI provides a command-line tool called `datasets` to download reference genomes by species name. We download one reference genome per ESKAPE pathogen:

```python
!pip install ncbi-datasets-pylib -q

species = {
    "efaecium":    "Enterococcus faecium",
    "saureus":     "Staphylococcus aureus",
    "kpneumoniae": "Klebsiella pneumoniae",
    "abaumannii":  "Acinetobacter baumannii",
    "paeruginosa": "Pseudomonas aeruginosa",
    "enterobacter":"Enterobacter cloacae"
}

for name, taxon in species.items():
    !datasets download genome taxon "{taxon}" --reference --include genome --filename {name}.zip
    !unzip -o {name}.zip -d {name}_genome -q
```

- `--reference` - downloads only the NCBI reference genome (1 per species, high quality)
- `--include genome` - only the FASTA sequence, not annotations
- Each genome is a `.fna` file (FASTA nucleotide) inside the zip

**What we got:**

| Species | Accession | Size |
|---|---|---|
| Enterobacter cloacae | GCF_905331265.2 | ~5 MB |
| Acinetobacter baumannii | GCF_009035845.1 | ~4 MB |
| Enterococcus faecium | GCF_009734005.1 | ~3 MB |
| Staphylococcus aureus | GCF_000013425.1 | ~3 MB |
| Klebsiella pneumoniae | GCF_000240185.1 | ~6 MB |
| Pseudomonas aeruginosa | GCF_000006765.1 | ~7 MB |

Total: ~28 MB of reference sequence (vs ~10 TB for the full RefSeq DB).

---

### 10.3 Building the custom Kraken-2 database

Kraken-2 DB construction has 3 steps: taxonomy download, add sequences to library, build hash table.

**Problem encountered:** `kraken2-build --download-taxonomy` uses rsync to fetch taxonomy files from NCBI. The rsync server was blocked on Colab:
```
@ERROR: Unknown module 'pub'
rsync error: error starting client-server protocol (code 5)
```

**Fix:** manually download only the needed parts of the taxonomy via HTTPS, and create a minimal accession to taxon ID map for just our 6 genomes:

```python
import glob, os

# NCBI taxon IDs — every species in NCBI taxonomy has a unique integer ID
taxon_ids = {
    "GCF_905331265": 550,   # Enterobacter cloacae
    "GCF_009035845": 470,   # Acinetobacter baumannii
    "GCF_009734005": 1352,  # Enterococcus faecium
    "GCF_000013425": 1280,  # Staphylococcus aureus
    "GCF_000240185": 573,   # Klebsiella pneumoniae
    "GCF_000006765": 287,   # Pseudomonas aeruginosa
}

os.makedirs("eskape_db/taxonomy", exist_ok=True)

# Download just nodes.dmp + names.dmp — the taxonomy tree (~60 MB)
# Full download would also grab nucl_gb.accession2taxid.gz which is ~10 GB — we skip that
!wget -q https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -O eskape_db/taxonomy/taxdump.tar.gz
!cd eskape_db/taxonomy && tar -xzf taxdump.tar.gz nodes.dmp names.dmp
```

- `nodes.dmp` - the taxonomy tree (parent-child relationships between taxon IDs)
- `names.dmp` - human-readable names for each taxon ID
- Together these define the full NCBI taxonomy hierarchy (bacteria to genus to species)

```python
# Build minimal accession2taxid for just our 6 genomes
# Kraken-2 uses this to map sequence IDs from the FASTA headers → taxon IDs
with open("eskape_db/taxonomy/nucl_gb.accession2taxid", "w") as out:
    out.write("accession\taccession.version\ttaxid\tgi\n")  # required header
    for fna in glob.glob("*_genome/**/*.fna", recursive=True):
        taxid = None
        for acc, tid in taxon_ids.items():
            if acc in fna:
                taxid = tid
                break
        if taxid is None:
            continue
        with open(fna) as f:
            for line in f:
                if line.startswith(">"):         # FASTA header line
                    seqid = line[1:].split()[0]  # e.g. "NC_002516.2"
                    base = seqid.split(".")[0]   # e.g. "NC_002516"
                    out.write(f"{base}\t{seqid}\t{taxid}\t0\n")
```

This file maps each chromosome/contig accession to a taxon ID. Kraken-2 uses it during DB build to label k-mers with the correct species.

**Add sequences to library and build:**

```python
# Add sequences first (must be done before --download-taxonomy fix)
!mkdir -p eskape_db
for fna in glob.glob("*_genome/**/*.fna", recursive=True):
    !kraken2-build --add-to-library {fna} --db eskape_db
```

- `--add-to-library` - processes the FASTA file, masks low-complexity regions (repeats that would cause false matches), and stages it for the DB build

```python
# Build the hash table
!kraken2-build --build --db eskape_db
!du -sh eskape_db/
```

**Build output:**
```
Found 17/17 targets, searched through 17 accession IDs
Estimated hash table: 47,825,188 bytes
Completed processing of 34 sequences, 53,419,720 bp
Database construction complete. [30.773s]
650M    eskape_db/
```

**Result: 650 MB custom DB** - vs 180 GB standard. **277x smaller.** Built in 30 seconds.

The 17 sequences = chromosomes + plasmids across all 6 reference genomes. 53 million bp of reference sequence total.

---

### 10.4 Converting BAM to FASTQ with samtools

Kraken-2 takes FASTQ (text) as input. Dorado outputs BAM (binary). `samtools fastq` converts between them:

```bash
samtools fastq barcode02.bam > barcode02.fastq
```

- `samtools fastq` - reads each BAM record and writes it as a FASTQ entry (`@header`, sequence, `+`, quality scores)
- `>` - redirects output to a file

**Important:** if the filename has spaces or parentheses (e.g. `file (3).bam` from repeated Colab uploads), the shell will break. Always rename first:
```python
os.rename("file (3).bam", "barcode02.bam")
```

**Truncation warning we saw:**
```
[W::bam_hdr_read] EOF marker is absent. The input is probably truncated
```
This means the BAM file was cut off mid-upload (Colab's 2 MB upload limit). We still got 44 reads out of ~2 MB - enough to test the pipeline.

---

### 10.5 Running Kraken-2 classification

```python
import time
start = time.time()
!kraken2 --db eskape_db --report report.txt barcode02.fastq > output.kraken
elapsed = time.time() - start
print(f"Time: {elapsed:.1f}s")
!cat report.txt
```

- `--db eskape_db` - path to the custom DB folder
- `--report report.txt` - human-readable summary report per taxon (the main output we care about)
- `barcode02.fastq` - input reads
- `> output.kraken` - per-read classification (one line per read with taxon ID)

**Output format of report.txt** (tab-separated):
```
% reads    reads    reads    rank    taxID    name
100.00     44       0        R       1        root
100.00     44       0        D       2          Bacteria
...
100.00     44       44       S       287          Pseudomonas aeruginosa
```

Columns:
1. % of reads rooted at this taxon
2. reads at this taxon + all descendants
3. reads assigned *directly* to this taxon (not a descendant)
4. rank code (R=root, D=domain, P=phylum, C=class, O=order, F=family, G=genus, S=species)
5. NCBI taxon ID
6. name (indented to show hierarchy)

---

### 10.6 First classification result

**Input:** barcode02 from AIIMS run (fast mode basecalling, ~44 reads after truncation)

**Result:**
```
100.00%  →  Pseudomonas aeruginosa  (taxid 287)
```

Full taxonomy path identified:
```
Bacteria → Pseudomonadota → Gammaproteobacteria → Pseudomonadales
→ Pseudomonadaceae → Pseudomonas → P. aeruginosa group → P. aeruginosa
```

- **44/44 reads classified (100%), 0 unclassified**
- **Time: 0.6 seconds**

**Caveats:**
- Only 44 reads (file truncated at 2 MB during upload)
- DB only contains 6 ESKAPE species - reads from any other organism would be forced into the nearest ESKAPE match. 100% classification rate is partly because there is no "other" category
- With the full 180 GB DB, some reads might land elsewhere or be unclassified

**Clinical interpretation:** barcode02 from this AIIMS run appears to be *Pseudomonas aeruginosa* - a dangerous hospital-acquired ESKAPE pathogen, resistant to many antibiotics.

---

### 10.7 End-to-end pipeline - complete

```
POD-5 (raw signal, 4 GB, 104,478 reads, AIIMS clinical data)
    │
    ▼  Dorado basecaller (fast mode, GTX 1650, ~5 min)
BAM files — demultiplexed by barcode (12 patient samples)
    │
    ▼  samtools fastq
FASTQ files (text format, readable by Kraken-2)
    │
    ▼  Kraken-2 (650 MB ESKAPE custom DB, 0.6s for 44 reads)
Species report — Pseudomonas aeruginosa (barcode02)
```

**Next steps:**
- Upload full (non-truncated) BAM files to get classification on all reads
- Run all 12 barcodes through Kraken-2 to identify all patient samples
- Compare fast vs hac BAM results in Kraken-2 (accuracy difference)
- Run `sup` mode on Colab (better VRAM) for highest accuracy comparison

---

---

## 11. Full Colab Run - Dorado + Kraken-2 (2026-05-18)

**Colab notebook:** https://colab.research.google.com/drive/1mj3lRxxIFS_qCeStrXszhIYHlJ2Z36bw?usp=sharing

This section documents the complete, working end-to-end pipeline run on Google Colab using a T4 GPU. Follow these steps exactly to reproduce it.

---

### 11.1 Setup - before you start

- Upload your POD-5 file to Google Drive (any folder, e.g. `nanopore data/`)
- Open a new notebook at colab.research.google.com
- Go to **Runtime - Change runtime type - Hardware accelerator - T4 GPU - Save**

---

### 11.2 Mount Google Drive

```python
# Connect Colab to your Google Drive so it can read the POD-5 file
from google.colab import drive
drive.mount('/content/drive')
```

Confirm the file is visible:

```python
import os
os.path.exists("/content/drive/MyDrive/nanopore data/FBE01990_24778b97_03e50f91_10.pod5")
# Should print: True
```

---

### 11.3 Install Dorado

Run each cell separately:

```python
# Download Dorado for Linux (Colab runs Ubuntu Linux, not Windows)
!wget -q https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-linux-x64.tar.gz
```

```python
# Extract the archive
!tar -xzf dorado-1.4.0-linux-x64.tar.gz
```

```python
# Verify installation - should print: 1.4.0+ba44a013
!./dorado-1.4.0-linux-x64/bin/dorado --version
```

**Why Linux binary:** Colab VMs run Ubuntu. The Windows `.exe` will not work here.

**Why separate cells:** the URL is long and wraps across lines if pasted into a `%%bash` block - splitting into `!` cells avoids this.

---

### 11.4 Run Dorado fast mode basecalling

```python
%%time
# Run basecalling + barcode demultiplexing on the POD-5 file
# fast = fastest model, good enough for species ID
# --kit-name = barcoding kit used during wet lab prep (tells Dorado how to demux)
# --output-dir = folder where per-barcode BAM files will be saved
!./dorado-1.4.0-linux-x64/bin/dorado basecaller fast \
    "/content/drive/MyDrive/nanopore data/FBE01990_24778b97_03e50f91_10.pod5" \
    --kit-name SQK-NBD114-24 \
    --output-dir results/fast
```

**Expected output:**
```
[info] Using CUDA devices:
[info] cuda:0 - Tesla T4
[info] cuda:0 using chunk size 9996, batch size 640
[info] Simplex reads basecalled: 104441
[info] Finished in (ms): 177832
Wall time: 3min 58s
```

**Key numbers vs local GTX 1650:**

| | Colab T4 | Local GTX 1650 |
|---|---|---|
| Wall time | ~4 min | ~5 min |
| Batch size (auto) | 640 | 64 |
| Reads processed | 104,441 | 104,441 |

T4 uses 10x larger batch size because it has 15 GB VRAM vs 4 GB on the GTX 1650.

---

### 11.5 Find the output BAM files

Dorado nests output inside experiment/run subdirectories:

```python
# Walk down to find where the per-barcode BAMs actually are
bam_dir = "results/fast/AIIMS_Shreshtha_1_301025/AIIMS_Shreshtha_1_301025/20251030_1420_MD-103113_FBE01990_24778b97/bam_pass"

# Set this variable once - used in all cells below
import os, glob
print(os.listdir(bam_dir))
```

Output: 14 barcode folders + unclassified (barcode08, 15, 16, 17, 18 absent - those reads didn't demux cleanly).

Each barcode folder contains one BAM file, e.g.:
```
bam_pass/barcode02/FBE01990_pass_barcode02_24778b97_03e50f91_0.bam  (31 MB)
```

---

### 11.6 Install Kraken-2 and samtools

```python
# Install condacolab first - adds mamba/conda to Colab
!pip install -q condacolab
import condacolab
condacolab.install()
# Kernel will restart automatically - this is expected
```

After restart:

```python
# Remove pin conflict that condacolab leaves behind, then install
!rm -f /usr/local/conda-meta/pinned
!mamba install -c bioconda -c conda-forge kraken2 samtools -y -q
```

Verify:

```python
!kraken2 --version   # should print: Kraken version 2.x.x
!samtools --version  # should print: samtools 1.x.x
```

**Why condacolab:** Kraken-2 and samtools are bioinformatics tools not available via pip. They live in the `bioconda` conda channel.

---

### 11.7 Build the ESKAPE Kraken-2 database

This is a custom 6-species database - 650 MB vs the standard 180 GB.

**Step 1 - Download taxonomy:**

```python
# Kraken-2 needs the NCBI taxonomy tree to build its index
!mkdir -p eskape_db/taxonomy
!mkdir -p eskape_db/library/added
!wget -q https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -O eskape_db/taxonomy/taxdump.tar.gz
!cd eskape_db/taxonomy && tar -xzf taxdump.tar.gz nodes.dmp names.dmp
```

**Step 2 - Download ESKAPE reference genomes:**

```python
# One complete reference genome per ESKAPE pathogen from NCBI RefSeq
!wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/174/395/GCF_000174395.2_Ente_faec_62415_V1/GCF_000174395.2_Ente_faec_62415_V1_genomic.fna.gz" -O eskape_db/library/added/e_faecium.fna.gz
!wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/013/425/GCF_000013425.1_ASM1342v1/GCF_000013425.1_ASM1342v1_genomic.fna.gz" -O eskape_db/library/added/s_aureus.fna.gz
!wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/240/185/GCF_000240185.1_ASM24018v2/GCF_000240185.1_ASM24018v2_genomic.fna.gz" -O eskape_db/library/added/k_pneumoniae.fna.gz
!wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/012/085/GCF_000012085.1_ASM1208v1/GCF_000012085.1_ASM1208v1_genomic.fna.gz" -O eskape_db/library/added/a_baumannii.fna.gz
!wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/006/765/GCF_000006765.1_ASM676v1/GCF_000006765.1_ASM676v1_genomic.fna.gz" -O eskape_db/library/added/p_aeruginosa.fna.gz
!wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/025/565/GCF_000025565.1_ASM2556v1/GCF_000025565.1_ASM2556v1_genomic.fna.gz" -O eskape_db/library/added/e_cloacae.fna.gz
```

**Step 3 - Tag each genome with its taxon ID:**

Kraken-2 identifies sequences by taxon ID. We embed the ID directly in the FASTA header using the `|kraken:taxid|XXXX` tag format:

```python
import gzip

taxids = {
    "e_faecium.fna.gz":    1352,  # Enterococcus faecium
    "s_aureus.fna.gz":     1280,  # Staphylococcus aureus
    "k_pneumoniae.fna.gz":  573,  # Klebsiella pneumoniae
    "a_baumannii.fna.gz":   470,  # Acinetobacter baumannii
    "p_aeruginosa.fna.gz":  287,  # Pseudomonas aeruginosa
    "e_cloacae.fna.gz":     550,  # Enterobacter cloacae
}

for fname, taxid in taxids.items():
    inpath = f"eskape_db/library/added/{fname}"
    outpath = inpath.replace(".fna.gz", "_tagged.fna")
    with gzip.open(inpath, "rt") as fin, open(outpath, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                line = line.rstrip() + f"|kraken:taxid|{taxid}\n"
            fout.write(line)
    print(f"Tagged {fname} -> taxid {taxid}")
```

**Step 4 - Add to library:**

```python
import glob
for fna in glob.glob("eskape_db/library/added/*_tagged.fna"):
    !kraken2-build --add-to-library {fna} --db eskape_db
```

**Step 5 - Create accession-to-taxid map:**

The taxonomy download uses rsync which is blocked on Colab - so we create this map manually using the accession IDs from the reference genomes:

```python
accession_map = {
    "NC_016847": 1352, "NC_016841": 1352, "NC_016845": 1352,
    "NC_016840": 1352, "NC_016846": 1352, "NC_016838": 1352,
    "NC_016839": 1352,  # E. faecium chromosomes + plasmids
    "NC_007795": 1280,  # S. aureus
    "NC_014108": 573, "NC_014107": 573, "NC_014121": 573,  # K. pneumoniae
    "NC_008710": 470,   # A. baumannii
    "NC_002516": 287,   # P. aeruginosa
}

with open("eskape_db/taxonomy/nucl_gb.accession2taxid", "w") as f:
    f.write("accession\taccession.version\ttaxid\tgi\n")
    for acc, taxid in accession_map.items():
        f.write(f"{acc}\t{acc}.1\t{taxid}\t0\n")
print("accession2taxid map created")
```

**Step 6 - Build the index:**

```python
# Remove any stale cache files first, then build
!rm -f eskape_db/hash.k2d eskape_db/seqid2taxid.map
!kraken2-build --build --db eskape_db
```

Expected output:
```
Found 13/13 targets...
Completed processing of 26 sequences, 42568426 bp
Database construction complete. [Total: 20.787s]
```

**How to verify it worked:** "Found 13/13 targets" and "26 sequences" - not 0. If you see 0, the accession map has wrong IDs. Check `eskape_db/unmapped.txt` to see which accessions Kraken-2 couldn't find and add them to the map.

---

### 11.8 Run all barcodes through Kraken-2

```python
%%time
import os, glob

bam_dir = "results/fast/AIIMS_Shreshtha_1_301025/AIIMS_Shreshtha_1_301025/20251030_1420_MD-103113_FBE01990_24778b97/bam_pass"
barcodes = sorted([b for b in os.listdir(bam_dir) if b.startswith("barcode")])

for barcode in barcodes:
    bam_file = glob.glob(f"{bam_dir}/{barcode}/*.bam")[0]
    
    # Convert BAM (binary) to FASTQ (text) - Kraken-2 needs text input
    os.system(f"samtools fastq {bam_file} > {barcode}.fastq")
    
    # Classify reads against ESKAPE DB
    os.system(f"kraken2 --db eskape_db --report report_{barcode}.txt {barcode}.fastq > output_{barcode}.kraken 2>/dev/null")
    
    # Print species-level hits only (rank code S)
    print(f"--- {barcode} ---")
    with open(f"report_{barcode}.txt") as f:
        for line in f:
            if "\tS\t" in line:
                parts = line.strip().split("\t")
                print(f"  {parts[5].strip()}: {parts[0]}% ({parts[1]} reads)")
    print()
```

Total time: **39.5 seconds** for all 14 barcodes.

---

### 11.9 Results - AIIMS run barcode classification

All 14 barcodes from the AIIMS_Shreshtha_1_301025 run (fast mode basecalling):

| Barcode | Primary species | % | Secondary | Notes |
|---|---|---|---|---|
| 01 | P. aeruginosa | 82% | - | clear |
| 02 | P. aeruginosa | 84% | - | clear |
| 03 | P. aeruginosa | 60% | - | lower confidence |
| 04 | P. aeruginosa | 83% | - | clear, most reads (17k) |
| 05 | P. aeruginosa | 80% | - | clear |
| 06 | P. aeruginosa | 81% | - | clear |
| 07 | P. aeruginosa | 76% | E. faecium 5% | mostly clear |
| 09 | K. pneumoniae | 22% | E. faecium 17% | mixed, high unclassified |
| 10 | K. pneumoniae | 27% | E. faecium 21% | mixed, high unclassified |
| 11 | K. pneumoniae | 16% | E. faecium 13% | mixed, high unclassified |
| 12 | K. pneumoniae | 23% | E. faecium 17% | mixed, high unclassified |
| 13 | E. faecium | 63% | P. aeruginosa 16% | mostly clear |
| 14 | P. aeruginosa | 43% | E. faecium 40% | genuinely mixed |
| 19 | P. aeruginosa | 100% | - | only 1 read - ignore |

**Observations:**
- Barcodes 01-07: all predominantly *P. aeruginosa* - likely same patient population or sample type
- Barcodes 09-12: ~50-60% unclassified - the dominant pathogen may not be in our 6-species DB, OR these are host DNA reads
- Barcode 14: two pathogens at near-equal levels - genuine polymicrobial infection or contamination
- Low-% secondary hits (e.g. 0.21% K. pneumoniae in barcode02) are likely noise - below 5% treat as cross-contamination
- Barcode 08 and 15-18 absent from output - those reads failed demultiplexing entirely

**Caveat on 100% classification in earlier test:** when we ran on only 44 reads with a truncated BAM, we got 100% P. aeruginosa. With the full 7105-read BAM we get 84% - the 14% unclassified are likely human host DNA or bacterial sequences not in our 6-species DB. The ESKAPE-only DB forces every classified read into one of 6 species - it cannot say "other bacteria".

---

---

### 11.10 Basecalling mode benchmarks - all 3 modes on T4

All 3 Dorado modes run on Colab T4 GPU, same POD-5 file (104k reads):

| Mode | Wall time | Batch size | Samples/s | Reads basecalled |
|---|---|---|---|---|
| fast | 3 min 58s | 640 | 2.85 x 10^7 | 104,441 |
| hac | 19 min 8s | 1664 | 4.75 x 10^6 | 104,443 |
| sup | 2h 5min 38s | 96 | 6.76 x 10^5 | 104,441 |

- sup batch size is 96 vs 1664 for hac - the sup model is much larger and barely fits on T4
- sup is 32x slower than fast, 6.5x slower than hac
- all 3 basecall the same number of reads - mode affects quality, not quantity

---

### 11.11 Kraken-2 results - fast vs hac vs sup comparison

All barcodes run through Kraken-2 with the 650 MB ESKAPE DB for all 3 modes. Species calls are **identical** across all modes - the pathogen identified never changes. Only the classification percentage improves.

| Barcode | fast | hac | sup | Primary pathogen |
|---|---|---|---|---|
| 01 | 82.3% | 85.4% | 85.5% | P. aeruginosa |
| 02 | 84.2% | 86.8% | 87.1% | P. aeruginosa |
| 03 | 59.7% | 67.2% | 68.5% | P. aeruginosa |
| 04 | 83.0% | 85.8% | 86.1% | P. aeruginosa |
| 05 | 80.3% | 85.1% | 85.5% | P. aeruginosa |
| 06 | 80.9% | 83.1% | 83.4% | P. aeruginosa |
| 07 | 75.7% | 79.0% | 79.2% | P. aeruginosa |
| 09 | 21.7% | 27.8% | 28.7% | K. pneumoniae (mixed) |
| 10 | 26.8% | 34.3% | 35.2% | K. pneumoniae (mixed) |
| 11 | 15.8% | 21.6% | 22.5% | K. pneumoniae (mixed) |
| 12 | 23.2% | 29.2% | 30.4% | K. pneumoniae (mixed) |
| 13 | 63.4% | 65.7% | 66.1% | E. faecium |
| 14 | 43.3% | 44.1% | 43.9% | mixed P.aer + E.fae |

**Key findings:**
- fast to hac: +3-8% improvement, biggest gains in barcodes 03, 09-12 (lower confidence samples)
- hac to sup: only +0.1-1% - marginal improvement for 6.5x more compute time
- **hac is the clinical sweet spot** - near-sup accuracy at a fraction of the time
- barcodes 09-12 remain ~50% unclassified even in sup mode - the missing reads are likely human host DNA or organisms not in the 6-species ESKAPE DB, not a basecalling quality issue

---

### 11.12 Visualizations

4 charts generated in the Colab notebook (saved as `mode_comparison.png`):

1. **Grouped bar chart** - classification % per barcode for all 3 modes, with exact values on top of each bar
2. **Improvement chart** - gain from fast→hac and hac→sup per barcode. Shows fast→hac jump is large; hac→sup jump is tiny
3. **Heatmap** - all barcodes × all modes in one grid, color-coded by % classified. Immediately shows barcodes 09-12 as the weak cluster
4. **Time vs accuracy scatter** - x-axis = basecalling time, y-axis = avg % classified with std dev error bars. Visualizes the diminishing returns of sup

Notebook link: https://colab.research.google.com/drive/1mj3lRxxIFS_qCeStrXszhIYHlJ2Z36bw?usp=sharing

---

---

## 13. Deep Dives — K-mers, Kraken-2 Architecture, Full Pipeline Walkthrough

---

### 13.1 K-mers — Complete Definition

**What is a k-mer:**

A k-mer is a substring of length k from a DNA sequence. Every possible contiguous window of k letters.

Example with k=4 on sequence `ATGCATGC`:
```
ATGC  <- k-mer 1 (position 0)
TGCA  <- k-mer 2 (position 1)
GCAT  <- k-mer 3 (position 2)
CATG  <- k-mer 4 (position 3)
ATGC  <- k-mer 5 (position 4)
```

From a sequence of length L you get **L - k + 1** k-mers.

**How many possible k-mers exist:**

With 4 bases (A, T, G, C) and length k:
- k=4: 4^4 = 256
- k=21: 4^21 = ~4.4 trillion
- k=31: 4^31 = ~4.6 x 10^18
- k=35: 4^35 = ~1.2 x 10^21

At k=35 the space is astronomically large. Most k-mers never appear in any real genome. The ones that do appear are like fingerprints — species-specific.

**Why k-mers are powerful for species ID:**

A k-mer of length 35 that appears in P. aeruginosa is overwhelmingly likely to ONLY appear in P. aeruginosa and its close relatives — not in S. aureus or humans. The longer k, the more species-specific each k-mer becomes. At k=35 the probability of a random k-mer appearing in two unrelated species by chance is essentially zero.

**Where k-mers are used across the pipeline:**

| Stage | Tool | k-mer use |
|---|---|---|
| Basecalling | Dorado | NOT used - works on raw signal not sequence |
| Species ID | Kraken-2 | k=35 windows slid across reads, hashed, looked up |
| DB building | kraken2-build | Every k-mer from reference genomes extracted and hashed |
| Minimizers | Kraken-2 | m=31 minimizers selected from k=35 windows to reduce DB |

**K-mers vs alignment:**

Full alignment (Smith-Waterman) is O(n x m) per read — hours/days for 100k reads against thousands of genomes. K-mer hashing is O(L) per read — 7105 reads classified in 3.8 seconds in our run.

**K-mers in the nanopore context:**

Nanopore reads are long (thousands of bases) but error-prone (~5% error rate). At k=35 a single error affects at most 35 consecutive k-mers — but a read has thousands of k-mers total so the majority still match correctly.

---

### 13.2 Kraken-2 — Full Architecture and Mathematics

**The core data structure — Compact Hash Table (CHT):**

Kraken-2 stores all k-mers in a purpose-built compact hash table. Standard hash maps store the full k-mer string (35 bases = 70 bits) + taxon ID — wasteful. Kraken-2 eliminates this:

```
k-mer (35-mer)
    ↓
extract minimizer (31-mer) → used as hash table index
    ↓
remaining bits → stored as key in bucket
    ↓
taxon ID → stored as value (minimum bits needed, e.g. 6 bits for 64 species)
```

Taxon ID storage: if you have 10 species you only need 4 bits (2^4 = 16 > 10). CHT uses exactly as many bits as needed. Collision handling uses open addressing with linear probing — if bucket occupied, check next bucket. Table sized to stay under ~70% full for performance.

**Minimizers — the math:**

A minimizer is the lexicographically smallest m-mer within a k-mer window.

```
k-mer (k=35): ATGCGATCGGCTAGCTAGCTAGCATGCGATCGGCT
slide m=31 window inside it
pick the lex. smallest 31-mer = minimizer
```

Two adjacent k-mers (shifted by 1 base) contain almost identical sub-sequences. With high probability they share the same minimizer — so they map to the same bucket instead of storing two entries. Reduction factor = k - m + 1 = 35 - 31 + 1 = 5x theoretical, ~10x in practice.

Canonical k-mers: DNA is double-stranded. Kraken-2 always takes the lexicographically smaller of (k-mer, reverse_complement(k-mer)) so it doesn't matter which strand the read came from.

**Database build — step by step:**

Step 1 - Extract k-mers:
```
For each genome G in reference set:
    For each position i in G:
        kmer = G[i : i+k]
        canon_kmer = min(kmer, reverse_complement(kmer))
        minimizer = get_minimizer(canon_kmer, m)
        emit (minimizer, taxon_id)
```

Step 2 - LCA assignment: multiple species may share a k-mer. For each k-mer appearing in multiple taxa:
```
assigned_taxon = LCA(taxon_1, taxon_2, ..., taxon_n)
```

LCA computed on NCBI taxonomy tree (nodes.dmp):
```
root (1)
└── Bacteria (2)
    ├── Pseudomonadota (1224)
    │   └── Gammaproteobacteria (1236)
    │       ├── Pseudomonas aeruginosa (287)
    │       └── Klebsiella pneumoniae (573)
    └── Bacillota (1239)
        └── Enterococcus faecium (1352)
```

A k-mer shared by P. aeruginosa (287) and K. pneumoniae (573) → LCA = Gammaproteobacteria (1236).

Step 3 - Build hash table:
```
n_kmers = total unique minimizers across all genomes
load_factor = 0.7
table_size = n_kmers / load_factor
```

Our ESKAPE DB: estimated hash table = 39,267,472 bytes (~37 MB). Rest of 650 MB is taxonomy data and sequence ID maps.

**Classification — step by step:**

Given read R of length L:

Step 1 - Extract k-mers and vote:
```
For i in range(L - k + 1):
    kmer = R[i : i+k]
    canon = min(kmer, revcomp(kmer))
    minimizer = get_minimizer(canon, m)
    taxon = CHT.lookup(minimizer)
    votes[taxon] += 1
```

Step 2 - Hit vector (one vote per k-mer position):
```
position:  1    2    3    4     5    6    7    8    9    10
taxon:    287  287  287  1236  287  287  573  287  287  287
```
Most k-mers hit P. aeruginosa (287), one ambiguous hit Gammaproteobacteria (1236), one noise hit K. pneumoniae (573).

Step 3 - Tree traversal (not simple majority vote):
```
For each node in taxonomy tree:
    score(node) = votes at node + votes at all descendant nodes

Pick leaf node with highest score that passes confidence threshold
```

Confidence score:
```
confidence = votes_at_winning_clade / total_k-mers_in_read
```

If confidence < threshold → read classified at higher taxonomic level or unclassified. Default threshold = 0.

Step 4 - Output:

Per-read `.kraken` file:
```
C  read_id  287  1500|287  287:142 1236:3 287:8 ...
```

Report `.txt` file:
```
84.22%  5984  5984  S  287    Pseudomonas aeruginosa
```

**Why Kraken-2 is fast:**
1. Hash lookup is O(1) - no alignment, no dynamic programming
2. Minimizers reduce work ~10x
3. Memory-mapped DB - OS pages in only what's needed
4. Multi-threaded - each read classified independently
5. No false positives by design - every k-mer came from a real genome

---

### 13.3 Full Walkthrough — DNA to Species Report

**Stage 0 - The patient sample:**

Doctor takes blood, sputum, or wound swab. Contains:
- Patient's human cells (majority of DNA)
- Bacterial cells (the pathogen)
- Possibly other microbes

Everything goes into wet lab together.

**Stage 1 - Wet lab preparation:**

- **DNA extraction:** cells lysed, DNA released, proteins/membranes removed
- **Fragmentation:** long DNA broken into 1-10 kb fragments
- **End prep:** fragment ends cleaned up for adapter attachment
- **Adapter ligation:** Y-adapter attached to each fragment
  - Leader sequence: single-stranded overhang, enters pore first
  - Motor protein (helicase): controls speed through pore (~400-500 bases/sec)
  - Tether: anchors adapter near the membrane
- **Barcoding:** if multiplexing, a unique 12-24 base barcode tag added per patient sample
- **Loading:** prepared DNA library pipetted onto flow cell

**Stage 2 - The flow cell and sequencer:**

```
Flow cell
├── Membrane (synthetic lipid bilayer)
├── ~512 channels (MinION) - each an independent measurement circuit
│   └── Each channel: one protein nanopore (R10.4.1 chemistry in our case)
└── Electronics beneath each pore - measuring current at 5000 Hz
```

What happens per DNA fragment:
1. Leader sequence captured by pore first
2. Voltage (~180 mV) pulls DNA through
3. Motor protein ratchets DNA at ~400-500 bases/sec
4. 5-6 bases in pore simultaneously - their combined effect changes ionic current
5. Electronics sample current 5000x/second

Different k-mers block current by different amounts:
```
...ATGCGA...  →  87.3 pA
...ATGCGT...  →  91.1 pA
...ATGCGG...  →  84.7 pA
```

Output - POD-5 file:
- Raw int16 signal arrays (one per read), Apache Arrow binary format
- Metadata: flow cell ID, run ID, sample rate, calibration values
- Our file: 4 GB, 104,478 reads, FLO-MIN114, R10.4.1

**Stage 3 - Basecalling (Dorado):**

```
POD-5 raw signal (int16, 5000 Hz)
    ↓  [1] Normalisation
       int16 → picoamperes using calibration constants
       removes inter-device variation
    ↓  [2] CNN (1D convolutions)
       downsamples 5000 Hz → ~400 steps/sec
       one feature vector per ~12 signal samples ≈ one base
       analogy: raw audio → mel-spectrogram
    ↓  [3] Transformer encoder
       multi-head self-attention: each position attends to all others
       captures long-range context
       multiple layers deep
    ↓  [4] Linear projection
       maps each time step → probability over {A, T, G, C, blank}
       output: T x 5 matrix
    ↓  [5] CTC decoding
       T time steps but only L << T actual bases
       blank token handles variable timing
       AAAA_TTT__GG → ATG (collapse repeats, remove blanks)
       output: ATGC string + per-base quality score
    ↓  [6] Demultiplexing
       reads barcode from each read
       sorts into per-barcode BAM files
```

Output - BAM files (one per barcode):
- ATGC reads + quality scores (Phred: Q10=90% accuracy, Q20=99%)
- Tags: barcode, model used, read duration

**Stage 4 - Format conversion (samtools):**

```bash
samtools fastq barcode02.bam > barcode02.fastq
```

FASTQ (4 lines per read):
```
@read_id
ATGCGATCGG...
+
IIIHHGGG...
```

**Stage 5 - Species classification (Kraken-2):**

```
barcode02.fastq (7105 reads, 31 MB)
    ↓  For each read:
       slide k=35 window → extract k-mers
       compute minimizer (m=31)
       hash → CHT lookup → taxon vote
       shared k-mers → LCA
    ↓  Per read: tree traversal → highest scoring clade
    ↓  Report
```

Output:
```
84.22%  5984  S  287   Pseudomonas aeruginosa
 1.29%    92  S  1352  Enterococcus faecium
 0.21%    15  S  573   Klebsiella pneumoniae
14.26%  1013  U  0     unclassified
```

Clinical interpretation: barcode02 = patient 2 = predominantly P. aeruginosa. Total time POD-5 to species: ~4 min (fast) to ~20 min (hac) on Colab T4.

**Complete pipeline:**
```
Patient sample
    ↓  wet lab: extraction + fragmentation + adapter + barcode
DNA fragments with Y-adapters
    ↓  nanopore sequencer: voltage + pore + motor protein
POD-5  (raw int16 signal, GBs, binary Arrow)
    ↓  Dorado: CNN + Transformer + CTC + demux  (GPU, minutes)
BAM files  (ATGC reads + quality, one per barcode)
    ↓  samtools fastq  (format conversion, seconds)
FASTQ files  (plain text, 4 lines per read)
    ↓  Kraken-2: k-mer hash + CHT + LCA + vote  (CPU, seconds)
Species report  (% reads per taxon, clinical diagnosis)
```

---

## 12. Viva Preparation - 20 Questions

---

**Q1. You have a 4 GB POD-5 file. What is actually stored inside it, and why is it not just a plain text file with ATGC letters?**

POD-5 stores raw electrical signal - arrays of int16 numbers, 5000 values per second per channel. This is the current measurement as DNA passes through the pore. No ATGC yet - just numbers. Also stores metadata per read: flow cell ID, run ID, sample rate, calibration values to convert int16 to picoamperes. It is binary (Apache Arrow format) not plain text because the signal is massive (5000 readings/sec x 512 channels x hours = billions of numbers) and needs compression + random access. ATGC letters don't exist at this stage - Dorado computes them in the next step.

---

**Q2. Walk me through what happens inside Dorado - what are the 5 stages and what does each one do?**

1. **Normalise** - raw int16 signal converted to picoamperes using calibration values from POD-5 metadata. Removes hardware variation between flow cells.
2. **CNN** - 1D convolutions downsample signal from 5000 Hz to ~400 Hz. Like compressing audio - removes noise, keeps the pattern. One output step roughly = one DNA base.
3. **Transformer** - looks at context across time. Each position attends to neighbors so the model understands what came before and after. Same architecture as LLMs.
4. **Linear projection** - outputs probability over {A, T, G, C, blank} at each time step.
5. **CTC decoding** - finds the most likely ATGC sequence from those probabilities. Handles the fact that signal steps don't map 1-to-1 to bases.

Output = one read = one ATGC string decoded from one DNA strand through one pore.

---

**Q3. What is a k-mer and how does Kraken-2 use k-mers to identify species?**

A k-mer is a substring of fixed length k. Kraken-2 uses k=35. It slides a 35-letter window across each read, hashes each k-mer (O(1) lookup), and looks it up in the database which maps hash → taxon ID. Each k-mer votes for a species. If a k-mer matches multiple species (conserved sequence), LCA is used - it assigns that k-mer to the lowest common ancestor in the taxonomy tree rather than guessing. Majority vote across all k-mers in the read gives the final species call.

---

**Q4. Why is the standard Kraken-2 DB 180 GB and how did we build a 650 MB custom DB?**

Standard DB is 180 GB because it contains every known organism - thousands of species, all their k-mers hashed and stored. More species = more k-mers = bigger DB. Our ESKAPE DB is 650 MB because we only put in 6 species (~42 MB of genome data total). We built it by: downloading 6 reference genomes from NCBI RefSeq, tagging each sequence header with `|kraken:taxid|XXXX`, downloading NCBI taxonomy, creating an accession2taxid map manually (rsync blocked on Colab), then running `kraken2-build --build`. Builds in 20 seconds, runs in <1 GB RAM.

---

**Q5. We got 14-26% unclassified reads even in sup mode. Give two reasons why a read might be unclassified.**

1. **Species not in DB** - our DB only has 6 ESKAPE species. Human host DNA, other bacteria, contaminants have no match - forced unclassified. Main reason for 14-26% unclassified.
2. **Sequencing errors** - nanopore has ~5% base error rate even in sup mode. If enough bases in k-mers are wrong, the hash won't match anything in the DB. This is why sup reduces unclassified slightly vs fast - better base accuracy = more k-mers match.
3. (Bonus) **Very short reads** - too short to generate enough k-mers for a confident majority vote.

---

**Q6. Why is it impossible to use a simple lookup table to decode nanopore signal to ATGC?**

5-6 letters are in the pore at once, giving 4^5 to 4^6 = 1024 to 4096 possible current levels. Each level is a combined signal from all bases together, not one base. The window slides - as one base exits and a new one enters, current changes but you can't isolate which base caused it. On top of that, the same k-mer produces slightly different current values each time due to electrical noise. A lookup table would need 4096 overlapping noisy entries - not cleanly separable. A neural network learns the mapping from messy signal patterns to ATGC, same way speech recognition handles messy audio.

---

**Q7. What is CTC and why does Dorado need it?**

CTC = Connectionist Temporal Classification. After the Transformer, Dorado has say 1000 time steps but only 200 actual bases. Simple argmax at each step gives `AAAAATTTTT` instead of `AT` because one base spans many time steps and DNA moves at irregular speed. CTC introduces a blank token and a collapsing rule: remove blanks and collapse repeats. So `A A A _ T T _ G` → `ATG`. Multiple raw sequences map to the same final output - CTC finds the most likely final sequence by summing over all valid alignments. Solves the variable-length alignment problem without knowing in advance when each base starts. Invented for speech-to-text, adopted for nanopore basecalling.

---

**Q8. What is the difference between BAM and FASTQ? Why do we need samtools to convert?**

FASTQ is plain text - 4 lines per read: read ID, ATGC sequence, separator, quality scores. That's it. BAM is binary compressed format storing everything FASTQ has plus: alignment position, mapping quality, CIGAR string, and extra tags (barcode, model used, methylation calls, signal quality). Dorado outputs BAM by default because it's the standard for downstream analysis and smaller than FASTQ. Kraken-2 is old and only accepts plain text (FASTQ/FASTA) - it doesn't understand BAM. Hence `samtools fastq` to convert. Dorado also has `--emit-fastq` flag to skip BAM entirely, but you lose the extra metadata.

---

**Q9. What is multiplexing/barcoding and why is it done?**

Flow cells are expensive (~$500-900) with limited lifespan. Running one patient sample per flow cell wastes capacity. Multiplexing mixes multiple patient samples into one run. In wet lab, each patient's DNA gets a unique short synthetic DNA tag (barcode) attached. All samples are loaded onto one flow cell together. Pores read everything randomly - one read from patient 3, next from patient 11. Dorado demultiplexes: reads the barcode tag at the start of each read and sorts them into separate BAM files. Our kit SQK-NBD114-24 supports 24 barcodes. Unclassified folder = reads where Dorado couldn't confidently identify the barcode.

---

**Q10. What is the difference between MinION and PromethION?**

| | MinION | PromethION |
|---|---|---|
| Channels | ~512 | ~3000 |
| Output | 10-30 GB | up to 10 TB |
| Use case | portable, clinical | high-throughput lab |

PromethION has ~6x more parallel channels. Our 4 GB file from MinION would be ~24 GB minimum on PromethION for the same duration, and in practice much more since PromethION runs are longer. This makes the memory bottleneck in Kraken-2 even more critical at PromethION scale.

---

**Q11. What are minimizers in Kraken-2 and why are they used?**

Instead of hashing every k-mer, Kraken-2 slides a window and only keeps the lexicographically smallest k-mer within that window as a representative (the minimizer). Adjacent windows usually share the same minimizer, so instead of one hash per base you store one hash per ~10 bases - ~10x DB size reduction. Kraken-2 uses k=35, m=31. Without minimizers the 180 GB DB would be ~1.8 TB. Our ESKAPE DB goes from ~6 GB to 650 MB for the same reason.

---

**Q12. What is LCA and when does Kraken-2 use it? Give a concrete example.**

LCA = Lowest Common Ancestor. When a k-mer appears in two different species' genomes (conserved sequence), Kraken-2 can't pick one. Instead it assigns the k-mer to the lowest node in the taxonomy tree that is an ancestor of both. Example: a k-mer matching both P. aeruginosa and K. pneumoniae gets assigned to Gammaproteobacteria (their common ancestor), not either species. This is conservative - never makes a false species call. Majority vote across all k-mers still works because most k-mers are species-specific. The 15 K. pneumoniae reads in barcode02 are likely k-mers that hit an LCA node, not real K. pneumoniae.

---

**Q13. Why does Kraken-2 need 180 GB of RAM, not just disk space?**

Classification requires random access into the hash table per k-mer - each lookup jumps to an unpredictable position. If DB is on disk: each random lookup = disk seek = ~10ms. 100k reads x thousands of k-mers x 10ms = hours. If DB is in RAM: each lookup = ~100ns. Same reads = seconds. Even in RAM, random lookups cause L3 cache misses - CPU goes to DRAM (100ns) instead of L3 (10ns). This is exactly what Kolin sir's Hot-K-mer LRU cache targets: pin frequent k-mers in L3 so most lookups never reach DRAM. `perf` measures the baseline cache miss rate before adding the cache.

---

**Q14. What is architecturally different between fast, hac, and sup models?**

All 3 use the same CNN + Transformer + CTC pipeline. The difference is Transformer size - number of layers, attention heads, and parameters. fast = small, hac = medium, sup = large. Bigger model = more matrix multiplications per read = more GPU memory per read = fewer reads fit in VRAM = smaller batch size. We saw this: fast batch 640, hac batch 1664 (T4 optimized), sup batch 96. sup is 32x slower than fast not because of window size but because of model weight count. On GTX 1650 (4 GB VRAM) sup OOM crashes - the model alone barely fits.

---

**Q15. What is POD-5 and why did ONT switch from FAST5?**

POD-5 stores per-read raw signal arrays (int16, 5000 Hz) + metadata, using Apache Arrow binary format. FAST5 used HDF5 format - poor compression, slow random access, hard to parallelize. POD-5 gives ~4x better compression, true random access (jump directly to any read by index), columnar storage, and parallel reading support. Dorado needs to jump to specific reads quickly and load them in parallel for GPU batching - POD-5's design directly speeds up the data loading stage before inference starts.

---

**Q16. What are the trade-offs of our 650 MB ESKAPE DB vs the standard 180 GB DB in a real clinical setting?**

| | ESKAPE DB | Standard DB |
|---|---|---|
| Size | 650 MB | 180 GB |
| RAM needed | <1 GB | 180 GB |
| Species covered | 6 | All known |
| Unclassified rate | 14-26% | Much lower |
| Build time | 20 sec | Hours |

ESKAPE DB advantage: runs on any machine, edge/clinical devices, no expensive server needed. Disadvantage: can only identify 6 species - everything else is unclassified. In a real clinical setting you might miss a non-ESKAPE infection entirely. Standard DB catches everything but needs a 180 GB RAM server. The research goal is to get the accuracy of the standard DB at the memory footprint of the custom DB - using Bloom filters or learned indexes.

---

**Q17. What is the role of the motor protein in the Y-adapter and why is it needed?**

Without the motor protein, DNA would fly through the pore too fast to measure - at free diffusion speed the bases pass in microseconds, far faster than the 5000 Hz sampling rate can capture. The motor protein (a helicase enzyme) attached to the Y-adapter grips the DNA and ratchets it through the pore one base at a time in a controlled stepwise manner, slowing it to ~400-500 bases per second. This is what makes the electrical signal measurable and decodable.

---

**Q18. What is the sample rate of 5000 Hz and what does it mean in terms of bases per second?**

5000 Hz means 5000 current measurements per second per channel. DNA passes through at ~400-500 bases per second (controlled by the motor protein). So there are roughly 5000/450 ≈ 10-12 signal measurements per base. This is why the CNN downsampling stage in Dorado is needed - it compresses those 10-12 measurements per base down to roughly 1 output step per base before the Transformer processes it.

---

**Q19. In our results, barcodes 09-12 had ~50% unclassified even in sup mode while barcodes 01-07 had only 14-20% unclassified. What does this tell you about those samples?**

Barcodes 01-07 are predominantly P. aeruginosa at 75-87% - the dominant pathogen fills most reads. Barcodes 09-12 show K. pneumoniae at 16-35% and E. faecium at 13-24% - together only ~40-50% of reads. The ~50% unclassified is too high to be just sequencing error. Most likely those samples contain significant human host DNA or another organism not in our 6-species DB. This also means the patient samples may not be pure bacterial cultures - they could be direct clinical samples (blood, sputum) with mixed content.

---

**Q20. Why is hac the clinical sweet spot and not sup?**

From our benchmarks: fast→hac gives +3-8% classification improvement. hac→sup gives only +0.1-1% improvement. But sup takes 32x longer than fast and 6.5x longer than hac. In a clinical setting, time matters - a doctor needs results in hours not days. The marginal 1% accuracy gain from sup does not justify 6.5x more compute time and cost. hac gives near-sup accuracy at a fraction of the time. sup is useful for research where maximum accuracy is needed and time is not critical.

---

### 9.6 CROC - tool found in project folder

A Python package called `CROC-1.2.6` was found in the project directory alongside the POD-5 files. CROC = **Concentrated ROC** - a method for evaluating early recognition performance in ranked lists (related to ROC curve analysis). It also contains two POD-5 files identical to the ones in `pod5 data/`.

Likely provided by mam for evaluating classification accuracy - CROC metrics (BEDROC) are used to assess how well a classifier ranks true positives early, which is relevant for evaluating Kraken-2's species identification performance. To be clarified at next meeting.

---

## 14. Meeting 3 Directions — Time & Accuracy Improvement (2026-05-18)

Assigned by Kolin sir in the third meeting. Two improvement axes for the POD-5 → Dorado → Kraken-2 pipeline.

---

### 14.1 GitHub repository structure

Two repos to be maintained and kept accessible to Kolin sir at all times:

| Repo | Maintainers | Contents |
|---|---|---|
| Repo 1 | Chirag K + Chirag S | Code, experiments, meeting minutes |
| Repo 2 | Rishabh + Rohit | Their work and contributions |

---

### 14.2 Time improvement — finding and fixing the bottlenecks

The goal is to reduce end-to-end wall-clock time for the pipeline by improving storage access patterns and compute efficiency.

#### Step 1 — Profile first, optimize second

Do not guess where the bottleneck is. Use profiling tools to find it:

| Tool | What it measures | How to use |
|---|---|---|
| `gprof` | CPU call graph — which functions consume the most time | Compile with `-pg`, run binary, run `gprof` on output |
| `Valgrind / cachegrind` | Cache miss rates, memory access patterns at instruction level | `valgrind --tool=cachegrind ./kraken2 ...` |
| `perf stat` | Hardware counters — L1/L2/L3 cache misses, branch mispredictions | `perf stat -e cache-misses,LLC-load-misses kraken2 ...` |
| `perf record + report` | Hotspot functions with annotated source lines | `perf record ./kraken2 ...; perf report` |

Look for:
- Functions with high self-time (gprof) — these are the hotspots
- High LLC (Last Level Cache) miss rates (perf, cachegrind) — memory bottleneck
- High instruction counts in inner loops — compute bottleneck

#### Step 2 — Cache reuse: identify hot k-mer lookups

Once hotspots are identified, check: is the same data being loaded repeatedly?

In Kraken-2, the inner loop does:
```
for each read:
    for each 35-mer window in read:
        hash(k-mer) → look up in compact hash table → taxon ID
```

For a patient sample dominated by one species (e.g., *Pseudomonas aeruginosa*), a small fraction of k-mers accounts for the vast majority of lookups. These "hot" k-mers are always for the same species. If they are evicted from L3 cache between lookups, you pay a cache miss penalty every time.

**Cache reuse opportunity:** pin the hot k-mer → taxon entries in L3 cache (or a software cache in front of the hash table). This is Kolin sir's Hot-K-mer LRU idea (§8.1) — section 14 now gives the profiling basis for it.

#### Step 3 — Find matrix/vector compute blocks

Both Dorado (Transformer) and Kraken-2 (hash table construction) contain linear algebra kernels. Look for:

| Pattern | Where | What to look for in source |
|---|---|---|
| Matrix-vector multiply | Dorado attention, linear projections | `Ax` patterns, `cblas_sgemv`, `torch::mm` |
| Vector-matrix multiply | Same — transposed form | `x^T A` patterns |
| Matrix-matrix multiply | Dorado batched attention | `AB` patterns, `torch::bmm`, `cublasSgemm` |

These are the blocks where cache blocking and SIMD apply.

#### Step 4 — Cache blocking (tiling)

**The problem with naive matrix multiply:**
```
for i in rows:
    for j in cols:
        for k in inner:
            C[i][j] += A[i][k] * B[k][j]   # B[k][j] jumps in memory — cache miss every step
```

B is accessed column-by-column but stored row-by-row → every `B[k][j]` access is a cache miss.

**Cache blocking fix — tile the loops:**
```
for i in 0..rows step TILE:
    for j in 0..cols step TILE:
        for k in 0..inner step TILE:
            # process TILE×TILE subblock — fits in L1/L2 cache
            for ii in i..i+TILE:
                for jj in j..j+TILE:
                    for kk in k..k+TILE:
                        C[ii][jj] += A[ii][kk] * B[kk][jj]
```

TILE is chosen so the working set (A tile + B tile + C tile) fits in L1 or L2 cache. This converts random wide-stride accesses into sequential accesses within a small block — hardware prefetcher can keep up, cache miss rate drops drastically.

**Where to apply in this project:**
- Dorado's transformer linear layers (if accessing source)
- Kraken-2's k-mer hash table construction (if batch processing k-mers)

#### Step 5 — SIMD / MMX2 / AVX2 / AVX-512

**What SIMD is:**
Single Instruction, Multiple Data. One CPU instruction processes multiple data elements in parallel using wide registers.

| Instruction set | Register width | Floats per op | Ints per op |
|---|---|---|---|
| MMX / SSE2 | 128-bit | 4x float32 | 16x int8 |
| AVX2 | 256-bit | 8x float32 | 32x int8 |
| AVX-512 | 512-bit | 16x float32 | 64x int8 |

**For Kraken-2 k-mer hashing:**
Instead of hashing one 35-mer at a time:
```c
// Scalar — one at a time
for (int i = 0; i < n_kmers; i++) {
    result[i] = hash(kmers[i]);
}
```
Use AVX2 to process 8 k-mers per iteration:
```c
// Vectorized — 8 at a time with AVX2
__m256i kmer_vec = _mm256_loadu_si256((__m256i*)&kmers[i]);
__m256i hash_vec = avx2_hash(kmer_vec);  // custom vectorized hash
_mm256_storeu_si256((__m256i*)&result[i], hash_vec);
```

This is exactly what Kolin sir's AVX-512 plan in §8.1 targets. Profiling first (gprof/Valgrind) will confirm whether this loop is hot enough to justify the implementation effort.

**Ryzen 7 5800H supports:** SSE4.2, AVX2 — does NOT support AVX-512 (that is Intel Skylake-X and above).

---

### 14.3 Accuracy improvement

Direction from Kolin sir: improve classification accuracy through the full pipeline.

Specific methods and metrics to be discussed in the next meeting. Likely involves:
- Comparing fast vs hac vs sup basecalling accuracy
- Measuring Kraken-2 classification accuracy against known ground-truth (golden dataset from §10)
- Possibly tuning k-mer length, confidence thresholds, or the Kraken-2 DB composition

---

### 14.4 Immediate next steps (post-Meeting 3)

1. Set up 2 GitHub repos — share links with Kolin sir
2. Profile Kraken-2 with `gprof` and `Valgrind/cachegrind` under WSL2
3. Identify matrix/vector blocks in Kraken-2 source code
4. Document cache miss rate baseline (the number that will justify the caching work)

---

## 15. perf — Profiling Tool Deep Dive

### 15.1 What perf is

`perf` is Linux's built-in profiling tool. It reads hardware performance counters (PMU — Performance Monitoring Unit) that are physically built into every modern CPU. These counters are tiny registers that increment automatically every time a certain event happens: a cache miss, a branch misprediction, a clock cycle, an instruction completing.

Think of it as a flight recorder for the CPU. While your program runs, perf counts exactly what the CPU was doing at the hardware level. After the run, it prints a table of those counts.

The key advantage over tools like Valgrind is that perf adds almost zero overhead — it reads real hardware, it doesn't simulate anything. Valgrind slows your program down 10–50x because it intercepts every memory access. perf: near-zero overhead, real execution speed.

### 15.2 Event Types

perf has three classes of events:

**Hardware events** — read from CPU PMU registers. The most precise, real hardware counts.
Examples: `cycles`, `instructions`, `cache-misses`, `cache-references`, `branches`, `branch-misses`

**Hardware cache events** — a specialised subset of hardware events for the cache hierarchy specifically.
Examples: `L1-dcache-loads`, `L1-dcache-load-misses`, `LLC-loads`, `LLC-load-misses`, `dTLB-loads`, `dTLB-load-misses`

**Software events** — tracked by the Linux kernel in software, not hardware. Always work everywhere including WSL2 and virtual machines.
Examples: `task-clock`, `page-faults`, `context-switches`, `cpu-migrations`

Run `perf list` to see everything available on your system. Run `perf list | grep cache` to filter just cache events.

### 15.3 Getting perf Working on WSL2

WSL2 uses a Microsoft-custom kernel (`6.6.87.2-microsoft-standard-WSL2`). Ubuntu's `linux-tools-generic` package only ships perf for Ubuntu's own kernels — there is no package for Microsoft's kernel. Running `perf stat ls` will show:
```
WARNING: perf not found for kernel 6.6.87.2-microsoft
```

**The fix: build perf from the WSL2 kernel source.**

Microsoft open-sources their WSL2 kernel at `github.com/microsoft/WSL2-Linux-Kernel`. The `tools/perf` directory inside it is the perf tool for that exact kernel. Building it yourself takes ~15 minutes.

```bash
# 1. Install build dependencies
sudo apt install -y flex bison libelf-dev libdw-dev libaudit-dev \
    libslang2-dev python3-dev libunwind-dev libbpf-dev \
    libcap-dev libnuma-dev libzstd-dev libtraceevent-dev

# 2. Clone matching kernel source (--depth=1 = only latest snapshot, saves ~3 GB of history)
git clone --depth=1 \
    --branch linux-msft-wsl-6.6.87.2 \
    https://github.com/microsoft/WSL2-Linux-Kernel.git \
    ~/WSL2-Linux-Kernel

# 3. Build perf (-j$(nproc) = use all CPU cores in parallel, ~15 min)
cd ~/WSL2-Linux-Kernel/tools/perf
make -j$(nproc)

# 4. Install to /usr/local/bin (on PATH, takes precedence over Ubuntu's wrapper at /usr/bin/perf)
sudo cp perf /usr/local/bin/perf

# 5. Clear zsh command cache (zsh caches command locations — rehash forces a fresh lookup)
rehash
which perf   # should now print /usr/local/bin/perf

# 6. Verify
perf stat ls
```

Common build issue: if `make` fails with `libtraceevent is missing` — run `sudo apt install libtraceevent-dev` and re-run `make`. The other warnings in the build output (missing libbabeltrace, JDK, libpfm4) are harmless — they only disable optional features.

**WSL2 hardware counter limitation — verified 2026-05-26 by running perf list + perf stat live:**

Hyper-V (the Windows hypervisor running WSL2) does not expose all PMU counters to the VM. Tested on AMD Ryzen 7 5800H, WSL2 kernel 6.6.87.2-microsoft-standard-WSL2.

| Counter | Status | Notes |
|---|---|---|
| `cycles`, `instructions` | ✓ works | IPC ratio is valid; clock freq reported (~0.734 GHz) is wrong — TSC virtualized |
| `cache-misses`, `cache-references` | ✓ works | overall L3 miss rate — the most useful metric |
| `branches`, `branch-misses` | ✓ works | |
| `stalled-cycles-frontend` | ✓ works | instruction fetch stalls visible |
| `task-clock`, `page-faults`, `context-switches` | ✓ always works | software events, no PMU needed |
| `L1-dcache-loads`, `L1-dcache-load-misses` | ✓ works | L1 data cache visible |
| `L1-icache-load-misses` | ✓ works | L1 instruction cache visible |
| `dTLB-load-misses`, `iTLB-load-misses` | ✓ works | TLB misses visible |
| `l2_pf_miss_l2_l3` | ✓ works | AMD native event — L2 prefetch misses going to L3 |
| `l2_pf_miss_l2_hit_l3` | ✓ works | AMD native event — L2 misses that hit L3 |
| `LLC-loads`, `LLC-load-misses`, `LLC-stores` | ✗ `<not supported>` | Hyper-V blocks the generic PMU alias for L3 |
| `stalled-cycles-backend` | ✗ `<not supported>` | backend stall counter blocked |

**Key insight from live testing:** the generic `LLC-*` aliases are blocked, but AMD-native event names `l2_pf_miss_l2_l3` and `l2_pf_miss_l2_hit_l3` work fine. these give L3 visibility through a different PMU register path that Hyper-V doesn't block. use these instead of `LLC-load-misses` for L3 miss data.

---

### 15.3a The Clock Frequency Problem — What Exactly Is Wrong

**verified 2026-05-26 by running `perf stat sleep 1` and cross-checking against `/proc/cpuinfo`.**

Hyper-V virtualizes the PMU cycle counter. the `cycles` register that perf reads is being throttled to a fraction of real hardware rate. it is not consistent — it varies with CPU power state:

```
sleep 1 run:
  perf reported:  833,353 cycles over 3.63 ms task-clock → 0.230 GHz
  real CPU speed: 3,193 MHz (from /proc/cpuinfo)
  cycles counted at: 833K / (3.63ms × 3193MHz) = ~7% of real rate

kraken-2 run:
  perf reported:  68.8B cycles over 93.8s task-clock → 0.734 GHz
  real CPU speed: ~3.2 GHz
  cycles counted at: ~23% of real rate
```

the cycle counter is physically wrong. it counts a virtualized/throttled value, not real CPU cycles.

**what this breaks — exactly:**

| number | formula | reliable? | reason |
|---|---|---|---|
| reported GHz | cycles ÷ task-clock | **no** | cycles are throttled |
| IPC | instructions ÷ cycles | **no** | denominator (cycles) is wrong |
| any "time from cycles" estimate | cycles × ns/cycle | **no** | cycles aren't real |
| cache miss rate | cache-misses ÷ cache-references | **yes** | ratio of two real PMU events, no cycles involved |
| task-clock (ms) | OS software timer | **yes** | kernel clock, not PMU |
| wall time / user / sys | OS timers | **yes** | no PMU involved |
| branch miss rate | branch-misses ÷ branches | **yes** | ratio, no cycles |
| raw cache-miss count | real PMU event | **yes** | 301M misses is the real number |
| raw instruction count | real PMU event | **yes** | instructions counter is not throttled |

**the IPC correction:** in the kraken-2 run, perf showed IPC = 2.26. that's wrong. real cycles = 68.8B × (3.2 / 0.734) ≈ 300B. real IPC = 155B instructions / 300B cycles ≈ 0.52. that makes far more sense for a memory-bound workload (IPC < 1.0 = CPU stalling on memory). the 2.26 figure should not be reported.

**what is safe to report from our kraken-2 perf run:**
- cache miss rate: 34.24% ✓
- total cache misses: 301 million ✓
- task-clock, wall time, user time, sys time ✓
- raw instruction count: 156 billion ✓
- IPC: do not report — discard it

---

### 15.3b AMD uProf — What It Is and What It Adds

AMD uProf (micro profiler) is AMD's own profiling tool for Ryzen CPUs. free download from `developer.amd.com/amd-uprof`. installs a Windows driver (`AMDPowerProfiler.sys`) that talks to the Ryzen PMU directly, potentially bypassing Hyper-V's throttling of the cycle counter.

**what uProf gives that perf cannot on our machine:**

| metric | perf on WSL2 | uProf |
|---|---|---|
| real cycle counts | throttled (~7–23% of real) | AMD driver reads PMU directly |
| correct IPC | wrong | should be correct |
| `stalled-cycles-backend` | `<not supported>` | available via AMD IBS (Instruction Based Sampling) |
| DRAM bandwidth (GB/s) | not available | yes — actual memory bus utilization |
| memory access latency | not available | histogram of cache miss latency in ns |
| TMAM breakdown | not available | full hierarchy (see below) |
| L3 miss rate per function | not available | yes |

**TMAM (Top-down Microarchitecture Analysis)** — the key uProf feature:
```
retiring              ← useful work
bad speculation       ← branch mispredictions
frontend bound        ← instruction fetch stalls
backend bound
  ├── memory bound
  │   ├── L1 bound
  │   ├── L2 bound
  │   ├── L3 bound
  │   └── DRAM bound  ← expected for kraken-2
  └── core bound      ← compute stalls
```
right now we know kraken-2 is "memory bound" from the 34.24% miss rate. TMAM would say exactly which level — almost certainly DRAM bound. that's the difference between a vague claim and a precise one.

**whether uProf works in WSL2:** unknown until tested. the driver installs on Windows. it definitely works for Windows-native binaries. for WSL2 binaries, it depends on whether the driver can sample across the Hyper-V boundary. installation and test results logged in §15.3c.

For per-function L3 miss breakdown without uProf, use cachegrind — it simulates the full cache hierarchy in software so Hyper-V cannot block it.

### 15.3c AMD uProf — Installation and Test Results

**download situation (verified 2026-05-26):** AMD gates all uProf downloads behind a browser EULA acceptance page. every direct CDN URL (e.g. `download.amd.com/developer/eula/uprof/...`) redirects back to the product page. cannot be automated — requires manual browser download.

**to download:**
1. open browser, go to: `https://www.amd.com/en/developer/uprof.html`
2. click the download button, accept the EULA
3. get either the Windows installer (`.exe`) or the Linux tarball (`.tar.bz2`)
4. for WSL2 profiling, the Linux version is more useful — it runs natively inside WSL2

**Windows installer — silent install once downloaded:**
```powershell
# run as administrator
.\AMDuProf_x.y.z_Setup.exe /S
# installs to C:\Program Files\AMD\AMDuProf\
# CLI tool at: C:\Program Files\AMD\AMDuProf\bin\AMDuProfCLI.exe
```

**Linux tarball — install into WSL2:**
```bash
tar -xjf AMDuProf_Linux_x64_x.y.z.tar.bz2
cd AMDuProf_Linux_x64_x.y.z
sudo ./install.sh
# CLI at: /opt/AMDuProf/bin/AMDuProfCLI
```

**checks to run once installed (WSL2 Linux version):**
```bash
# 1. verify install
AMDuProfCLI --version

# 2. list available events — compare to perf list
AMDuProfCLI collect --list-events

# 3. test IPC on ls (compare against perf's wrong IPC)
AMDuProfCLI collect --event IPC ls

# 4. test if backend stall counter works (blocked in perf)
AMDuProfCLI collect --event BackendBound ls

# 5. full TMAM profile on kraken-2
AMDuProfCLI collect --config tbp \
    --output-dir /tmp/uprof_kraken \
    -- ./kraken2 --db /path/to/db reads.fastq

# 6. memory access profile (DRAM bandwidth)
AMDuProfCLI collect --config memory \
    --output-dir /tmp/uprof_mem \
    -- ./kraken2 --db /path/to/db reads.fastq
```

**what to look for in output:**
- IPC number — compare to perf's 2.26 (wrong). real should be ~0.5 for a memory-bound workload
- BackendBound % — should be high for kraken-2 (CPU waiting on memory)
- DRAM bandwidth (GB/s) — how much of the memory bus is being used
- TMAM breakdown — which level (L1/L2/L3/DRAM bound) kraken-2 sits at

---

**actual test results — verified 2026-05-26 on AMD Ryzen 7 5800H, Windows 11, uProf 5.3.518.0**

### what uProf told us about our hardware first

running `AMDuProfCLI.exe info --system` before anything else:

```
[PERF Features Availability]
  Core PMC   : Yes (6 counters per core)
  L3 PMC     : No
  DF PMC     : No
  UMC PMC    : No
  PERF TS    : No

[IBS Features Availability]
  IBS        : No

[RAPL/CEF Features Availability]
  RAPL       : Yes
  APERF & MPERF : Yes
```

this is the ground truth. Hyper-V blocks everything above core-level PMC. specific implications:
- **L3 PMC: No** — no per-core L3 cache miss counters in uProf either. same block as perf.
- **DF PMC: No** — Data Fabric PMC monitors AMD's memory interconnect (the path to DRAM). blocked. means **no DRAM bandwidth numbers** from uProf.
- **UMC PMC: No** — Unified Memory Controller PMC. also blocked. this would have given memory latency and bandwidth. gone.
- **IBS: No** — Instruction Based Sampling is AMD's most powerful feature. it samples at instruction granularity, giving precise memory latency, backend stalls, pipeline state per instruction. blocked entirely by Hyper-V.
- **APERF & MPERF: Yes** — these measure actual effective CPU frequency (MPERF counts at base freq, APERF at actual freq, ratio gives real operating freq). available — but only through the `timechart` command.

### what configs actually run vs what fails

tested every config:

| config | result | what it gives |
|---|---|---|
| `tbp` | ✓ works (deprecated, use hotspots) | CPU_TIME sampling, hotspot functions by wall time |
| `hotspots` | ✓ works | same as tbp, current name |
| `branch` | ✓ works | CYCLES_NOT_IN_HALT, RETIRED_INST, CPI, branch misprediction rates |
| `assess` | ✗ `driver failed to start (0x80070021)` | needs IBS or L3 PMC — both blocked |
| `cache` | ✗ `not supported` | needs L3 PMC — blocked |
| `memory` | ✗ needs IBS — blocked | would give memory access latency |
| `ibs` | ✗ needs IBS — blocked | instruction-level sampling |
| `ipc` | ✗ `not supported` | needs TMAM counters — blocked |
| `ebp` | ✗ `not supported` | generic EBP — blocked |
| `timechart --event power` | ✓ works | per-core and socket power in Watts (RAPL) |
| `timechart --event freq/cef/cpu` | ✗ invalid event name | APERF/MPERF available in hardware but not exposed via this CLI path |

### the one thing uProf gives that perf cannot — real CPI

the `branch` config uses `CYCLES_NOT_IN_HALT (PMCx076)` — AMD's own cycle counter that counts only when the thread is not sleeping. this is NOT the TSC. it is not virtualized by Hyper-V in the same way perf's cycle counter is.

from a ping.exe test run:
```
ping.exe process:
  CYCLES_NOT_IN_HALT : 22
  RETIRED_INST       : 12
  CPI                : 1.83   (IPC = 0.55)
  branch mispredicts : 5.26%
```

compare to running the same binary under perf in WSL2 — perf would show IPC ~2.26 (wrong because cycles are throttled to ~7–23% of real rate). uProf's 0.55 IPC for a short network program doing mostly I/O waiting is believable. perf's 2.26 was not.

**so: uProf gives us correct IPC. perf does not.**

### the key limitation uProf did NOT solve

uProf is a Windows tool. it profiles Windows processes. kraken-2 runs inside WSL2 (a Hyper-V VM). uProf cannot attach to or profile WSL2 processes. the tools don't overlap on the target binary.

this means:
- for kraken-2: perf (WSL2) is still the only viable CPU profiler
- for any Windows-native binary: uProf gives correct IPC + branch metrics

### uProf bonus: real power measurements (RAPL)

`timechart --event power` works and gives per-core and socket power in Watts at 1-second intervals:

```
socket0-package-power: 2.24 W (idle)
core0-power: 0.32 W
core1–7-power: ~0.01–0.06 W each
```

this is from RAPL (Running Average Power Limit), which reads from CPU internal power counters. accurate to within a few percent. useful for understanding power cost of kraken-2 vs dorado runs. not something perf can give at all.

### perf vs uProf — full comparison table (our machine, WSL2 + Windows)

| metric | perf (WSL2) | uProf (Windows) | notes |
|---|---|---|---|
| **can profile kraken-2 (WSL2 binary)** | ✓ yes | ✗ no | uProf is Windows-only |
| **cache miss rate (overall)** | ✓ 34.24% — correct | ✗ not available (L3 PMC blocked) | perf wins here |
| **IPC** | ✗ wrong (~2.26, cycles throttled) | ✓ correct via CYCLES_NOT_IN_HALT | uProf wins here |
| **CPI per function** | partial (perf record) | ✓ branch config gives per-function CPI | uProf more detailed |
| **branch miss rate** | ✓ correct ratio | ✓ correct + per-function breakdown | both work |
| **L3 miss rates** | ✗ LLC-* blocked | ✗ L3 PMC blocked | neither works |
| **DRAM bandwidth** | ✗ not available | ✗ DF/UMC PMC blocked | neither works |
| **backend stall breakdown** | ✗ blocked | ✗ IBS blocked | neither works |
| **TMAM hierarchy** | ✗ not available | ✗ needs IBS — blocked | neither works |
| **real CPU frequency** | ✗ reports 0.23–0.73 GHz (wrong) | partial (APERF/MPERF in hardware but CLI path broken) | neither reliable |
| **power consumption (Watts)** | ✗ not available | ✓ RAPL, per-core, 1-second intervals | uProf only |
| **function hotspots** | ✓ perf record | ✓ hotspots/tbp config | both work |
| **overhead** | near zero | low (sampling-based) | both fine |

### what this means for our kraken-2 profiling

for kraken-2 running in WSL2:
- **cache miss rate (34.24%)**: from perf — correct and trustworthy
- **IPC**: from perf — wrong. do not report this number. real IPC probably ~0.5 based on how uProf measures similar programs.
- **branch miss rate**: from perf — correct ratio
- **function hotspots**: need `perf record` in WSL2 — not yet run
- **per-function cache miss rates**: need cachegrind — not yet run

for anything that needs correct IPC or power measurements, uProf on a Windows binary is the tool.

### commands reference (uProf)

```powershell
$uprof = "C:\Program Files\AMD\AMDuProf\bin\AMDuProfCLI.exe"

# system hardware check — always run first
& $uprof info --system

# hotspot functions (what's taking time)
& $uprof collect --config hotspots -o C:\Temp\uprof_out target.exe [args]
& $uprof report -i C:\Temp\uprof_out\AMDuProf-*

# IPC + branch analysis (correct CPI per function)
& $uprof collect --config branch -o C:\Temp\uprof_out target.exe [args]
& $uprof report -i C:\Temp\uprof_out\AMDuProf-*

# power consumption over time (RAPL, 1s intervals)
& $uprof timechart --event power -d 30 -o C:\Temp\uprof_power

# one-shot profile + report combined
& $uprof profile --config branch -o C:\Temp\uprof_out target.exe [args]
```

### 15.4 The Important Counters for This Project

These are the numbers that matter for the profiling report and Kolin sir's caching work:

**IPC — Instructions Per Cycle**
```
IPC = instructions / cycles
```
This is the single most important diagnostic number.
- IPC < 1.0 → **memory-bound** — CPU is stalling, waiting for data from RAM. Fix: caching, better data layout.
- IPC 1.0–2.0 → mixed
- IPC > 2.0 → **compute-bound** — CPU is doing lots of arithmetic. Fix: SIMD, better algorithms.

For Kraken-2 doing random hash table lookups into a 650 MB DB: we expect IPC well below 1.0 — every lookup is a random jump that misses all cache levels and forces a ~100ns wait for RAM. That's the evidence for Kolin sir's LRU cache.

**Cache miss rate**
```
miss rate = cache-misses / cache-references × 100%
```
This is the overall fraction of cache lookups that missed — the data wasn't in any cache level and had to be fetched from RAM. Above 5% is notable. Above 20% is severe for a lookup-heavy program.

**Page faults**
Every page fault means the program accessed memory that wasn't loaded from disk yet — the OS paused the program, read a 4 KB page from disk into RAM, then resumed. For Kraken-2 with a 650 MB database: first run will have thousands of page faults (loading DB into RAM). Second run will have far fewer (OS kept the pages in RAM). Run twice and compare — the difference shows how much of the slowness is disk I/O vs actual computation.

**Branch miss rate**
```
branch miss rate = branch-misses / branches × 100%
```
The CPU predicts which way an if/else will go. A miss means it predicted wrong, threw away work, and had to redo it. Above 5% is high. For Kraken-2's hash lookup inner loop, the branch predictor has a hard time because hash table lookups have unpredictable hit/miss patterns.

**Stalled cycles frontend**
The CPU frontend fetches and decodes instructions. Stalls here mean the CPU ran out of instructions to execute — usually due to instruction cache misses or branch mispredictions creating bubbles in the pipeline. High frontend stalls (>30%) combined with low IPC confirms memory-bound behaviour.

### 15.5 First perf Run on our Machine (ls — baseline)

To establish what perf output looks like on our WSL2 setup, we ran it on `ls` first:

```
Performance counter stats for 'ls':

              3.50 msec task-clock:u              #  0.613 CPUs utilized
                 0      context-switches:u
                 0      cpu-migrations:u
               105      page-faults:u             #  29.972 K/sec
            836864      cycles:u                  #  0.239 GHz
            281233      stalled-cycles-frontend:u #  33.61% frontend cycles idle
            936476      instructions:u            #  1.12  insn per cycle
                                                  #  0.30  stalled cycles per insn
            191591      branches:u                #  54.690 M/sec
              9811      branch-misses:u           #  5.12% of all branches

       0.005715004 seconds time elapsed
```

And for cache counters specifically:
```
             12786      cache-misses:u            #  26.73% of all cache refs
             47832      cache-references:u
   <not supported>      LLC-load-misses:u
   <not supported>      LLC-loads:u
```

What this tells us:
- IPC = 1.12 — ls is mildly compute-bound (expected — it's doing string sorting and formatting)
- 26.73% cache miss rate — high for ls, but it's a short-lived program loading cold code and libraries
- LLC-specific counters blocked by Hyper-V — confirmed limitation on WSL2
- 105 page faults — ls loading its own code + shared libraries for the first time

For **Kraken-2** we expect: IPC much lower (likely 0.3–0.6), cache miss rate much higher (possibly 50–80%), page faults in the thousands (first run loading the 650 MB DB). Those numbers are the bottleneck evidence that justifies the caching work.

### 15.6 Key perf Commands Reference

```bash
# Basic stat — run program and print counter summary
perf stat <program> [args]

# Specify exact counters with -e
perf stat -e cycles,instructions,cache-misses,cache-references,branches,branch-misses \
    <program> [args]

# Add page faults and task-clock (software events — always work)
perf stat -e task-clock,page-faults,context-switches \
    <program> [args]

# Record samples for hotspot analysis (which functions are hot)
perf record -g <program> [args]
perf report   # opens interactive view — arrow keys to navigate, 'a' to annotate source

# List all available events
perf list
perf list | grep cache     # filter to cache events only
perf list | grep branch    # filter to branch events only
```

The `:u` suffix on counter names (e.g., `cycles:u`) means user-space only — kernel time is excluded. This is the default in WSL2 because kernel-space hardware counters are blocked by Hyper-V. For our purpose (profiling Kraken-2's user-space code) this is fine.

---

## 16. Dorado GPU Profile — Nsight Systems Results (2026-05-21)

### 16.1 Setup

| Item | Detail |
|---|---|
| Tool | Nsight Systems 2024.2.3 (Windows) |
| Command | `nsys profile -o dorado_fast_profile --trace cuda,nvtx dorado.exe basecaller fast <pod5> --batchsize 64` |
| Input | FBE01990_24778b97_03e50f91_10.pod5 — 104,478 reads, 4 GB |
| Mode | fast |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| Output | dorado_fast_profile.nsys-rep + .sqlite |

---

### 16.2 NVTX Range Summary — Wall-clock breakdown by stage

NVTX annotations are markers Dorado places in its own code to label what it is doing at each point. nsys records when each annotation starts and ends.

| % Time | Stage | What it means |
|---|---|---|
| 39.8% | basecall_current_batch | Outer loop — one batch of reads going through the full pipeline |
| 39.8% | call_chunks | Inner loop — chunking each read into signal windows and processing them |
| 19.6% | cuda_thread_fn_device_0 | Actual GPU execution time — CUDA kernels running on the GPU |
| 0.2% | nn_forward | Neural network forward pass annotation |
| 0.1% | cpu_decode | CTC decoding on CPU |
| 0.1% | lstm_stack | LSTM layers |
| 0.1% | gpu_decode | CTC decoding on GPU |
| 0.1% | conv | Convolutional layers |

`basecall_current_batch` and `call_chunks` are nested annotations (same wall time, different scope). `cuda_thread_fn_device_0` at 19.6% represents how much of the total annotated time was actual GPU kernel execution — the rest is overhead, synchronisation, and data movement.

9,085–9,087 instances = number of batches processed for 104,478 reads.

---

### 16.3 CUDA GPU Kernel Summary — Where GPU time actually goes

This is the most important table. It shows what the GPU was actually computing.

| % GPU Time | Kernel | What it does |
|---|---|---|
| **68.5%** | `cutlass_70_tensorop_h884gemm_128x64_nn_align8` | Matrix multiply (GEMM) using Tensor Cores, FP16, 128×64 tile |
| **13.5%** | `cutlass_70_tensorop_h884gemm_128x128_nn_align8` | Matrix multiply (GEMM) using Tensor Cores, FP16, 128×128 tile |
| 4.7% | `beam_search_step` | CTC beam search decoding |
| 4.5% | `lstm (forward)` | LSTM forward pass, 96 channels |
| 3.0% | `lstm (backward)` | LSTM backward pass, 96 channels |
| 1.6% | `convolution_ntc` | CNN feature extraction |
| 1.3% | `decode_step` | Viterbi-style decode |
| 1.3% | `compute_posts_step` | Posterior probability computation |

**82% of all GPU time is GEMM (matrix multiply).** These are the Transformer attention and linear projection layers — the core neural network arithmetic. They use CUTLASS (CUDA Templates for Linear Algebra Subroutines), NVIDIA's optimised GEMM library. `h884` = half-precision (FP16) Tensor Core tile 8×8×4.

The LSTM kernels (7.5% combined) are the recurrent layers in Dorado's architecture. The convolution (1.6%) is the CNN front-end that extracts features from the raw signal before the LSTM/Transformer.

---

### 16.4 CUDA API Summary — What the CPU does

| % Time | Calls | Avg | API |
|---|---|---|---|
| **98.9%** | 27,283 | 56.6 ms | cudaStreamSynchronize |
| 0.5% | 190,891 | 43.5 μs | cudaLaunchKernel |
| 0.3% | 27,304 | 186 μs | cudaMemcpyAsync |

`cudaStreamSynchronize` taking 98.9% of CUDA API time means: the CPU launches a batch of GPU kernels, then immediately calls `cudaStreamSynchronize` and **blocks** — it does nothing until the GPU finishes. The CPU is a spectator while the GPU works. This is a synchronous pipeline design.

27,283 sync calls at 56.6 ms average = ~1,544 seconds of CPU blocking = the bulk of total runtime.

This confirms the GPU is the bottleneck. The CPU is idle most of the time waiting.

---

### 16.5 Memory Transfer Summary

| % Time | Total | Per batch | Direction |
|---|---|---|---|
| 59.9% | 11,427 MB | ~1.25 MB | Host→Device (CPU RAM → GPU VRAM) — signal data going in |
| 25.1% | 11,427 MB | ~1.25 MB | Device→Device (GPU internal copies) |
| 15.0% | 2,856 MB | ~0.31 MB | Device→Host (GPU VRAM → CPU RAM) — basecalls coming out |

Total data moved: ~25.7 GB across the full run. Memory transfers are a minority of total time — the GPU is not being starved of data. The bottleneck is compute, not bandwidth.

---

### 16.6 Verdict — Compute-bound

**Dorado fast mode on GTX 1650 is compute-bound.**

| Evidence | Value | Interpretation |
|---|---|---|
| GEMM % of GPU time | 82% | GPU is doing math, not waiting |
| cudaStreamSynchronize % | 98.9% | CPU is waiting on GPU — GPU is the bottleneck |
| Memory transfer % | ~15% of transfer time | Data movement is not the constraint |

The GPU is fully occupied doing matrix multiply. It is not idle, not waiting for data. This is exactly what "compute-bound" means.

---

### 16.7 Implications for Kolin sir's Signal-to-Base (S2B) Cache

The S2B cache (§8.2) aims to skip the neural network forward pass for signal windows similar to previously seen ones. The profiling numbers tell us exactly what the cache would save:

- If a cache hit skips the GEMM kernels entirely → saves 82% of GPU time for that batch
- At 30% cache hit rate → ~25% total GPU time saved
- At 50% cache hit rate → ~41% total GPU time saved

The cache lookup must be faster than running the GEMM. On GTX 1650: one GEMM call averages 19.6 ms. The LSH lookup + shared memory read must complete in well under that to be worth it.

The synchronous pipeline (CPU blocks on cudaStreamSynchronize) means there is no CPU-side parallelism to hide cache lookup latency — the lookup must happen on the GPU itself, which is why CUDA shared memory is the right storage for the cache (per §8.2).

**Key number for the report:** 82% of Dorado's GPU time is GEMM. A cache that avoids recomputation has up to 82% of GPU time as recoverable headroom.

---

## 17. Kraken-2 Database Build — WSL2 Attempt Log (2026-05-23)

This section documents every issue hit while trying to replicate the Colab ESKAPE database build natively in WSL2. Kept as a reference so we don't repeat mistakes.

---

### 17.1 Goal

Build a small (~650 MB) custom Kraken-2 database containing only the 6 ESKAPE pathogen reference genomes, run it natively in WSL2, then compare profiling numbers against the 8 GB pre-built standard database.

---

### 17.2 Setup that worked

**Kraken-2 binary (CRLF fix):**

The Kraken-2 build was cloned and built from source on Windows/WSL2. All Perl scripts and shell scripts had Windows line endings (`\r\n`) which broke execution. Fix applied to all scripts:

```bash
sed -i 's/\r//' ~/kraken2-build/kraken2
sed -i 's/\r//' ~/kraken2-build/kraken2-build
sed -i 's/\r//' ~/kraken2-build/*.sh ~/kraken2-build/*.pl
```

**Taxonomy download (rsync blocked — use wget instead):**

`kraken2-build --download-taxonomy` uses rsync which fails with `@ERROR: Unknown module 'pub'` on NCBI's current servers. Workaround — download manually:

```bash
mkdir -p ~/eskape_db/taxonomy
cd ~/eskape_db/taxonomy
wget https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz
tar -xzf taxdump.tar.gz

# Create placeholder accession files (see §17.4 for why this is wrong)
touch nucl_gb.accession2taxid
touch nucl_wgs.accession2taxid
```

**Genome downloads:**

The Colab notebook had a wrong folder name for E. faecium (`GC_000174395.2` instead of `GCF_000174395.2`). Correct URLs verified by browsing the NCBI FTP directory listing:

```bash
# E. faecium — corrected folder name
wget "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/174/395/GCF_000174395.2_ASM17439v2/GCF_000174395.2_ASM17439v2_genomic.fna.gz" -O ~/eskape_db/library/added/e_faecium.fna.gz

wget "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/013/425/GCF_000013425.1_ASM1342v1/GCF_000013425.1_ASM1342v1_genomic.fna.gz" -O ~/eskape_db/library/added/s_aureus.fna.gz
wget "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/240/185/GCF_000240185.1_ASM24018v2/GCF_000240185.1_ASM24018v2_genomic.fna.gz" -O ~/eskape_db/library/added/k_pneumoniae.fna.gz
wget "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/012/085/GCF_000012085.1_ASM1208v1/GCF_000012085.1_ASM1208v1_genomic.fna.gz" -O ~/eskape_db/library/added/a_baumannii.fna.gz
wget "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/006/765/GCF_000006765.1_ASM676v1/GCF_000006765.1_ASM676v1_genomic.fna.gz" -O ~/eskape_db/library/added/p_aeruginosa.fna.gz
wget "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/025/565/GCF_000025565.1_ASM2556v1/GCF_000025565.1_ASM2556v1_genomic.fna.gz" -O ~/eskape_db/library/added/e_cloacae.fna.gz
```

**Header tagging (Python — run from Windows path accessible to WSL2):**

Script saved to project folder and run via `/mnt/c/...` path to avoid terminal heredoc indentation issues:

```python
# tag_genomes.py
import gzip

taxids = {
    "e_faecium.fna.gz":    1352,
    "s_aureus.fna.gz":     1280,
    "k_pneumoniae.fna.gz":  573,
    "a_baumannii.fna.gz":   470,
    "p_aeruginosa.fna.gz":  287,
    "e_cloacae.fna.gz":     550,
}

for fname, taxid in taxids.items():
    inpath = f"/home/chira/eskape_db/library/added/{fname}"
    outpath = inpath.replace(".fna.gz", "_tagged.fna")
    with gzip.open(inpath, "rt") as fin, open(outpath, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                line = line.rstrip() + f"|kraken:taxid|{taxid}\n"
            fout.write(line)
    print(f"Tagged {fname} -> taxid {taxid}")
```

```bash
python3 "/mnt/c/Users/chira/OneDrive/Desktop/Nanopore project/Nanopore project/tag_genomes.py"
```

**Add to library:**

```bash
for fna in ~/eskape_db/library/added/*_tagged.fna; do
    ~/kraken2-build/kraken2-build --add-to-library $fna --db ~/eskape_db
done
```

---

### 17.3 The build failure — why `|kraken:taxid|` tags were ignored

After `--add-to-library`, the prelim_map files (which Kraken-2 uses to map sequence IDs to taxon IDs) showed `ACCNUM` entries instead of `TAXID` entries:

```
ACCNUM  NC_017960.1     NC_017960   ← taxid NOT found
ACCNUM  NC_007795.1     NC_007795
...
```

The `|kraken:taxid|` tags WERE correctly written into the FASTA headers — confirmed by inspecting the stored masked files:

```
>NC_008710.1 Borrelia turicatae 91E135, complete genome|kraken:taxid|470
```

The tag was present but `scan_fasta_file.pl` (the Perl script that creates the prelim_map) did not recognize it. Root cause not fully diagnosed — likely a Perl script CRLF or version issue. Result: all 17 sequences had no taxon ID → `build --db` completed with 0 sequences in the database.

---

### 17.4 The correct approach (what Colab did differently)

Looking at §11.7 step 5, the Colab did NOT use `|kraken:taxid|` header tags at all. Instead it manually created the `nucl_gb.accession2taxid` file with real entries for every accession:

```python
accession_map = {
    "NC_016847": 1352, "NC_016841": 1352, "NC_016845": 1352,
    "NC_016840": 1352, "NC_016846": 1352, "NC_016838": 1352,
    "NC_016839": 1352,  # E. faecium
    "NC_007795": 1280,  # S. aureus
    "NC_014108": 573, "NC_014107": 573, "NC_014121": 573,  # K. pneumoniae
    "NC_008710": 470,   # A. baumannii
    "NC_002516": 287,   # P. aeruginosa
}

with open("eskape_db/taxonomy/nucl_gb.accession2taxid", "w") as f:
    f.write("accession\taccession.version\ttaxid\tgi\n")
    for acc, taxid in accession_map.items():
        f.write(f"{acc}\t{acc}.1\t{taxid}\t0\n")
```

This is the correct WSL2 approach. The `touch` placeholder files we used (empty files) caused `mmap` to fail. The accession2taxid file needs a proper header line AND real entries.

**To replicate the Colab build correctly in WSL2:**
1. Download taxonomy (wget approach above — rsync is blocked)
2. Download genome .fna.gz files (no header tagging needed)
3. Add to library WITHOUT tagging
4. Create `nucl_gb.accession2taxid` with the accession map above (check `unmapped.txt` after any failed build to find missing accessions)
5. Build

---

### 17.5 What we did to partially work around it

Built `seqid2taxid.map` and fixed prelim_maps manually using Python scripts (`fix_seqid_map.py`, `fix_prelim_maps.py`). The build then processed 24 sequences correctly but hung indefinitely after `Processed 24 sequences (37392452 bp)...` — `taxo.k2d.tmp` was created but never grew. Root cause unknown — possibly WSL2 specific issue with the `build_db` binary on this Kraken-2 version (2.17.1).

---

### 17.6 Decision — use pre-built 8 GB database

After 3 separate blockers (rsync, prelim_map parsing, build hang), we moved to the pre-built standard 8 GB database:

```bash
mkdir ~/eskape_db_8gb
cd ~/eskape_db_8gb
wget https://genome-idx.s3.amazonaws.com/kraken/k2_standard_08gb_20250402.tar.gz
tar -xzvf k2_standard_08gb_20250402.tar.gz -C ~/eskape_db_8gb/
```

**Why this is actually better for profiling:**
- 650 MB database fits easily in 14 GB RAM → few cache misses → profiling shows nothing interesting
- 8 GB database puts real pressure on the CPU cache → cache misses appear → the bottleneck Kolin sir's project targets becomes visible in the numbers
- No building required — guaranteed to work
- Covers all ESKAPE pathogens (they are all common bacteria in the standard DB)
