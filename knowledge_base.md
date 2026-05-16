# Nanopore Project — Knowledge Base

What I've learned, **in my own words**. Claude teaches a chunk, I paraphrase it back, and that paraphrase lives here.

- 1st meeting with **mam**: 2026-05-11
- Profiling tools mail from **Kolin sir** (perf, Nsight) — to be reviewed
- Next meeting / deadline: **2026-05-17**

---

## 1. Nanopore sequencing

### 1.1 The physical idea (DNA through a hole, current as signal)

DNA is made up of long strands of 4 chemical letters — **A, T, G, C** — called **nucleotides**. The process of reading these strands is called **sequencing**. We sequence to figure out what species are present in a sample (useful for diagnosing infections, environmental monitoring, etc.).

Two popular technologies:
- **Illumina** — uses chemistry + fluorescent dyes + cameras; reads short strands (~150 letters each).
- **Nanopore** — uses electrical signals. A **voltage is held across a membrane** that has a tiny pore in it. When a DNA strand passes *through* the pore, the letters inside partially block the **current**, and different letters block by different amounts. We decode that current signal back into ATGC.

In short, a nanopore device is a **molecular electrical sensor**: DNA in → wobbling current out → computer recovers the letters.

### 1.2 Device structure — flow cell, channels, pores

The device has 3 nested things to keep track of:

- **Flow cell** — a cartridge-like consumable that plugs into the sequencer and can be swapped out. The DNA sample is loaded into it.
- **Membrane** — inside the flow cell, a thin synthetic membrane that holds many **channels**.
- **Channel** — one independent DNA reader. Each channel = **one pore** (a hollow protein tube wide enough for a single DNA strand) + the membrane patch around it + its own electrodes + its own electronics measuring the current over time.

DNA passes *through* the pore. The big win of nanopore is **parallelism** — all channels read at the same time, each on a different DNA strand.

Rough numbers:
- **MinION** flow cell ≈ 512 channels
- **PromethION** flow cell ≈ 2,675 channels (one machine runs many flow cells)

Caveat: not all pores stay healthy through a run — some clog, some die. So channel count is a **theoretical max**; the number actually sequencing at any moment is lower.

### 1.3 K-mer window (5–6 bp), 4096 patterns, "ionic current = voice"

Each pore is long enough that **5–6 nucleotides fit inside it at once**. So the current at any moment doesn't report a single letter — it reports the **whole 5-mer or 6-mer window** currently inside the pore. A "k-mer" is just "a string of k consecutive letters."

- For k = 6, there are 4⁶ = **4,096 possible windows**, each producing its own characteristic current level.
- As DNA ratchets through, the window **shifts by one letter per step** — if window N is `ATGCGA`, window N+1 might be `TGCGAC`. So consecutive readings are overlapping tones, not isolated ones.
- Each window is like a distinct "tone." A long DNA strand produces a long stream of tones — this is why mam called the ionic current the **"voice" of DNA**.

**Why a neural network is needed (basecalling):**

A simple lookup of "current → letter" won't work because:
1. The signal encodes a 6-letter window, not one letter.
2. DNA moves through the pore irregularly — timing of each step isn't uniform.
3. Some k-mers produce similar current values.

So the basecaller's NN must do two jobs at once:
- **Segmentation** — when did the window step from one k-mer to the next?
- **Classification** — which k-mer was inside during each step?

The **basecaller** is the software running this NN (on CPU/GPU). It reads in the current trace and outputs strings of ATGC called **reads**. Downstream tools like **Kraken-2** consume these reads.

**Q: Why don't we just make the pore small enough to fit only one nucleotide?**

1. **Sensing zone is a volume, not a point.** The current is influenced by everything within the Debye length (~1 nm) around the constriction — not just the single base at the narrowest point. So neighboring nucleotides always affect the signal.
2. **Pores are proteins.** Common ONT pores (CsgG, MspA, α-hemolysin) have a reading-head length set by amino-acid folding — typically ~5 nucleotides thick. Can't be arbitrarily shrunk.
3. **Solid-state alternatives** (graphene, MoS₂) could theoretically be single-base wide, but they have much higher noise and no motor protein to slow DNA down, so DNA shoots through too fast to read.
4. **4,096 patterns is *more* informative than 4** — richer fingerprints, more noise-robust signal.
5. **Decoding works.** Modern basecallers hit >99% accuracy; no incentive to redesign the physics.

### 1.4 POD-5 raw signal format, squiggle visualization

**POD-5 — what it is**

POD-5 is Oxford Nanopore Technologies' current file format for storing the **raw electrical signal** captured by a flow cell during a run. It replaces an older format called **FAST5** (which was built on HDF5).

Why a special format exists at all:
- Signal data is huge — ~4,000 samples/sec × hundreds of channels × hours of runtime = **GBs to TBs per run**.
- POD-5 uses better compression → smaller files.
- Faster **random access** — a basecaller can pull out a specific read's signal without scanning the entire file.
- Cleaner schema, based on **Apache Arrow** (a columnar binary format).

What's inside a POD-5 file:
- **Per-read signal arrays** — the time-series of raw current values for each DNA strand that passed through a pore.
- **Metadata** — channel number, pore ID, run ID, timestamps, calibration values (to convert raw integer samples to picoamperes), sample rate, etc.

**Squiggle — what it is**

A **squiggle** is the **plot of raw current (in picoamperes) versus time** for a single read. It looks like a noisy wavy line with plateaus and transitions:

- **Plateaus** = DNA paused briefly with one k-mer inside the pore.
- **Transitions** = the window shifted by one letter.

Why we look at squiggles:
- Sanity-check signal quality (is the current in a normal range? is the pore healthy?).
- Spot the **adapter region** at the start of each read — the adapter molecule (Topic 2) produces a distinctive signal.
- Debug failed basecalling — eyeball where things went wrong (a pore stall, a bubble, etc.).
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

POD-5 is the **input** to all Topic 3 (basecalling) work — when we run experiments, we'll be opening real POD-5 files and visualizing the squiggles.

---

## 2. Sample preparation pipeline

### 2.1 DNA → fragment → adaptor ligation (motor protein, leader, docking point)

**Why prep exists at all**

A raw biological sample (patient swab, bacterial culture, soil) can't be loaded into a flow cell directly. The DNA in that sample is:
- locked inside cells,
- tangled with proteins, RNA, debris, salts,
- in double-stranded form (the pore reads one strand at a time),
- of wildly varying length — sometimes whole chromosomes,
- has no "handle" for the pore to grab onto.

So **sample prep = the wet-lab pipeline that turns raw sample into DNA fragments ready to be threaded through a nanopore.** It's the gate between biology and the sequencer.

**The three big prep steps (overview)**

1. **Extraction & purification** — break cells open, free the DNA, wash away proteins, RNA, debris. Standard kits (e.g., Qiagen) do this.
2. **Fragmentation** — break long DNA into manageable pieces (typically **1 kb – 100 kb** for nanopore, far longer than Illumina's ~150 bp). Long reads are part of nanopore's appeal.
3. **Adapter ligation** — attach an engineered molecule (the "adapter") to each end of each fragment. This is the **key step** — it makes the DNA pore-compatible.

**Deep dive — fragmentation + the adapter**

After fragmentation, each piece of DNA looks like:

```
5'-ATGCGATCGGCTA...TGCACGTA-3'
3'-TACGCTAGCCGAT...ACGTGCAT-5'
```

A bare double-stranded fragment **cannot enter a pore on its own** — it has no handle, the pore reads single strands, and DNA in free solution rarely finds a pore in time. The fix is to attach an engineered molecule — the **adapter** — to each end.

**End prep (cleanup before ligation)**

DNA ends from fragmentation are messy (jagged, partially single-stranded). Before ligation, ends are cleaned up:
- **Blunting** — fill in or chew back overhangs so ends are flat.
- **A-tailing** — add a single `A` overhang on the 3' end so the adapter's complementary `T` overhang fits perfectly.

This makes ligation efficient and directional.

**The Y-adapter — structure**

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

**The three key features (the ones mam mentioned):**

1. **Motor protein** — a **helicase enzyme** bound to one arm of the Y.
   - Once threading starts, it sits on top of the pore.
   - **Unzips** the double-stranded DNA into a single strand (only one strand fits in the pore).
   - **Ratchets DNA through the pore one base at a time, at a controlled rate** (~400 bases/sec for modern chemistries).
   - **This is the single most critical component.** Without it, DNA's natural electrophoretic speed would shoot it through the pore in microseconds — far too fast to read. The motor protein is the "speed governor."

2. **Leader sequence** — a short, **known**, single-stranded sequence at the tip of the other Y-arm.
   - It's the first thing that enters the pore.
   - Like all DNA it's negatively charged, so the voltage across the membrane **pulls it in** (electrophoresis).
   - Its sequence is known, so the basecaller uses it as a **start marker** — you can literally see the leader as a distinct early portion of every squiggle.

3. **Docking point (tether)** — a **hydrophobic anchor** attached to the adapter (typically a cholesterol or lipid tag).
   - Inserts into the membrane near the pores.
   - Holds the adapter (and its attached DNA) close to the membrane surface.
   - **Hugely increases the chance of finding a pore** — without it, DNA would float around in bulk solution and rarely encounter a pore before the run ends.

**Ligation step**

A **ligase enzyme** covalently joins the adapter's double-stranded stem to each cleaned-up DNA fragment end. Result: every fragment has an adapter at each end.

**Kit names you'll encounter**

- **LSK** (Ligation Sequencing Kit) — the standard. Uses ligation as described. Higher accuracy, longer prep time.
- **RAD / Rapid Sequencing Kit** — uses a **transposase** enzyme that both fragments DNA and inserts adapters in one shot. Prep time drops to ~10 min, but at slightly lower efficiency.
- These names appear constantly in ONT wet-lab discussions.

**Why this design matters for our project**

Every Topic 3 (basecalling) experiment runs on data that came through this exact adapter mechanism. The **leader signal** at the start of each squiggle is what the basecaller uses to align. The **motor protein's speed** determines how dense each k-mer step is in the signal. Understanding the adapter is foundational to understanding why the signal looks the way it does.

### 2.2 How the adaptor gets DNA into the pore

Three forces stacked together get a fragment from "floating in solution" to "threading through a specific pore":

1. **Tether** — the hydrophobic tail on the adapter inserts into the membrane. This **biases DNA toward the membrane surface** instead of letting it float in bulk solution. Effectively a load-balancer for DNA-finds-pore events.
2. **Voltage** — DNA is negatively charged. The voltage across the membrane (cis side −, trans side +) **electrostatically pulls the single-stranded leader sequence into the pore first**.
3. **Motor protein** — as the leader threads in, the motor protein (on the other Y-arm) parks on top of the pore. It **unzips** the double strand and **ratchets DNA through one base at a time**. The squiggle starts being recorded.

When DNA exits the pore → pore becomes free → next adapter+DNA captured. Stochastic process — at any moment only a fraction of channels are actively sequencing, so **effective throughput < theoretical channel count**.

CSE framing: it's a queueing system. Tether = arrival-rate boost, voltage = the driving force, motor protein = service-rate cap.

### 2.3 A–T / G–C pairing recap

DNA in nature is mostly a **double helix** — two complementary strands held together by base pairing:

- **A pairs with T** — adenine ↔ thymine (2 hydrogen bonds)
- **G pairs with C** — guanine ↔ cytosine (3 hydrogen bonds)

If one strand reads `5'-ATGCGA-3'`, the other reads `3'-TACGCT-5'` — note the direction reverses (DNA strands run **antiparallel**).

Why this matters for nanopore:

1. **The pore only fits one strand at a time.** Prep has to either separate the two strands (denaturation) or use adapters that let one strand thread through while the other comes along behind.
2. **Prep enzymes recognize specific base-pair patterns** (the motor protein, ligases, polymerases all depend on predictable A-T/G-C chemistry).
3. **GC-rich regions are harder to denature** (3 H-bonds vs 2). This causes small accuracy dips in GC-rich stretches of the genome.

### 2.4 MinION, PromethION (and GridION)

Same chemistry, three product scales from ONT:

| Device | Channels / flow cell | Output / run | Form factor | Use case |
|---|---|---|---|---|
| **MinION** | ~512 | ~10–30 GB | USB stick, ~$1k | Field work, small experiments |
| **GridION** | 5 × MinION flow cells | ~150 GB | Desktop box | Lab-scale parallel |
| **PromethION** | ~3,000 × 24–48 flow cells | up to ~10 TB | Rack-mount, ~$100k+ | Production / clinical |

Project-relevant: most public nanopore datasets we'll use come from MinION or PromethION runs.

### 2.5 AMR, MBR (terms used in prep / context)

- **AMR = Antimicrobial Resistance.** Bacteria/fungi/parasites evolving resistance to drugs that used to kill them. WHO ranks AMR among the top 10 global health threats. *This is the clinical reason nanopore + Kraken-2 matters — fast identification of resistant strains at the point of care.* Topic 5 goes deeper.
- **MBR** — *unclear what mam specifically meant*. Most likely "**Multi-drug Bacterial Resistance**" (informal, related to MDR — multidrug resistance). Could also refer to a specific resistance-gene database or a kit name. **To clarify with mam at the 2026-05-17 meeting.**

---

## 3. Basecalling

### 3.0 Basecalling as a Machine Learning problem (framing)

**Input/output:**

```
INPUT  : current(t) — 1-D time-series of float values, sampled ~4 kHz,
         length 10⁴ to 10⁷ samples per read
OUTPUT : ATGC string, variable length 10² to 10⁵ bases per read
```

This is a **sequence-to-sequence** problem with three structural challenges:
1. **Variable-length input** — every read is a different number of samples.
2. **Variable-length output** — every read produces a different number of bases.
3. **No fixed input-to-output alignment** — DNA moves through the pore unevenly; one base might span 10 samples, the next 100. No constant "samples per base" ratio.

This is structurally **almost identical to speech-to-text** (audio waveform → words). Modern basecallers borrow directly from speech-recognition architectures. *Useful mental model: nanopore basecalling = speech recognition for DNA.*

**Why it's hard:**
- No fixed alignment → need an algorithm that learns segmentation + classification jointly. This is what **CTC loss** (Connectionist Temporal Classification) solves — same idea as DeepSpeech.
- Each signal moment encodes a **6-mer context** (Topic 1), so the network has to deconvolve overlapping windows.
- Noise: pore wear, ionic fluctuations, modified bases (methylation), pore-to-pore variability.
- Scale: a single PromethION run = up to ~100 TB of signal; real-time inference during the run is the target.

**Training:**
Labeled data comes from running samples with **known sequences** (from Sanger or synthetic constructs) through the device, producing `(squiggle, known_sequence)` pairs. Modern training sets contain millions of such pairs across species and pore chemistries. Training is offline, expensive, GPU-cluster scale.

**Where inference runs:**
- **GPU-first.** Dorado is GPU-native; CPU fallback exists but is 10–100× slower.
- A modern NVIDIA GPU (A100, H100) basecalls a PromethION run in hours; without GPU, days-to-weeks.
- This is the surface where **`perf` + Nsight profiling** matters (Exp-3, Kolin sir's mail) — SM utilization, memory bandwidth, kernel occupancy.

**One-line summary:** Basecalling is real-time speech recognition for DNA, running on GPU, where the "speaker" is a noisy nanopore and the "language" is ATGC.

### 3.1 Dorado, Guppy, Bonito — what each is

Three basecallers from ONT, different generations:

**Bonito** — open-source research basecaller, started ~2019.
- First to use deep learning (CNN + LSTM + CTC) for basecalling, replacing the older HMM-based methods.
- Proof-of-concept that DL beats HMM. Still maintained but mainly for research/experimentation.
- Python, PyTorch, hackable — good for academic experiments.
- GitHub: `nanoporetech/bonito`.

**Guppy** — legacy production basecaller (~2017–2023).
- Closed-source binary distribution.
- Evolved from HMM → CNN+RNN+CTC over the years.
- Model flavors: **fast** / **hac** (high accuracy) / **sup** (super accuracy).
- **Deprecated** — being replaced by Dorado.

**Dorado** — current production basecaller (~2022 onward), the one we'll use.
- Open source (MPL), C++ with PyTorch under the hood.
- Modern architecture — **transformer-based** (different from CNN+RNN of older tools).
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

**For our experiments:** Dorado is the default. We'll benchmark one of its models (likely **hac** or **sup**) for speed + accuracy.

### 3.2 Neural network: squiggle → ATGC

The inside of a modern basecaller, viewed as a 5-stage pipeline:

**Stage 1 — Input normalization**
- Raw signal arrives as int16 values from the ADC; convert to picoamperes using per-channel calibration (scale + offset stored in POD-5).
- Optionally normalize per-read (median, MAD scaling) to reduce pore-to-pore variability.

**Stage 2 — CNN feature extractor (front-end)**
- A stack of **1-D convolutional layers** (typically 3–5 layers) with `stride > 1`.
- Job: downsample the time axis. Raw signal is at ~4 kHz; bases occur at ~400 Hz (≈10 samples/base average). The conv layers crunch 10⁴–10⁷ samples down to a manageable 10²–10⁵ feature vectors.
- Each conv layer learns local patterns: signal-level transitions, plateau shapes, slope features.
- **Output**: a sequence of d-dimensional embedding vectors at the lower rate.

**Stage 3 — Sequence backbone (RNN or Transformer)**
- Captures context across time. Why needed: each base's signature depends on neighboring 6-mers and on motor-protein pause patterns.
- **Older models** (Bonito, early Guppy): bidirectional LSTM.
- **Modern Dorado**: **Transformer**.
  - Better parallelism (no recurrence) → faster GPU inference.
  - Better long-range context handling.
- **Output**: another sequence of d-dim embeddings, now context-aware.

**Stage 4 — Output projection**
- Linear layer projects each time-step embedding to a vocabulary of labels.
- Vocab = `{A, T, G, C, blank}` for standard CTC basecalling.
- **Output**: at each time step, a probability distribution over the label vocabulary.

**Stage 5 — CTC decoding**
- The output is a `T × V` matrix (`T` time-steps × `V` labels).
- CTC algorithm: find the most likely *output sequence* by considering all possible alignments (which time-steps emit which letter, with `blank` handling "no base emitted yet").
- Two decoding modes:
  - **Greedy** — pick argmax at each step; fast, less accurate.
  - **Beam search** — explore top-K hypotheses; slower, higher accuracy. The `sup` models use this.

**Full pipeline:**

```
raw signal (int16, ~10⁶ samples)
        │
        ▼
  normalize → float
        │
        ▼
  CNN front-end (stride>1, downsample)
        │
        ▼
  embedding sequence (e.g., 10⁴ × 512-d)
        │
        ▼
  Transformer backbone (context mixing)
        │
        ▼
  context-aware embeddings (10⁴ × 512-d)
        │
        ▼
  linear projection
        │
        ▼
  label probs (10⁴ × 5)   [A, T, G, C, blank]
        │
        ▼
  CTC decoding (greedy / beam search)
        │
        ▼
  ATGC string (~10³ bases)
```

**Model sizes:**
- `fast`: ~10⁷ parameters
- `hac`: ~5×10⁷ parameters
- `sup`: ~10⁸+ parameters, beam search at inference

Tradeoff: bigger = more accurate, slower, more GPU memory.

**Where the bottleneck is (relevant for Nsight profiling, Exp-3):**
- **Memory bandwidth** — loading weights for each batch.
- **SM occupancy** — keeping all GPU compute units busy.
- **KV-cache** for transformer attention is memory-heavy.
- **Mixed precision** (FP16 / BF16) is standard for inference.
- These are exactly the metrics you'll be probing with Nsight Compute / Nsight Systems.

### 3.3 Signal compression — vector quantization, Shannon source coding, Euclidean vectors

This is what mam called the "signal compression angle." Three signal-processing / information-theory ideas that show up inside modern basecallers.

**Vector Quantization (VQ)**

- **Concept**: take a continuous-valued vector and **snap it to the nearest entry in a discrete codebook** of representative vectors. The codebook is learned to minimize reconstruction error.
- **Where used**: in modern neural codecs (VQ-VAE, SoundStream, EnCodec), continuous embeddings get quantized into discrete codes.
- **In basecalling**:
  - The NN's internal embeddings live in continuous ℝᵈ.
  - VQ can discretize these → cleaner state representations → easier to map to discrete base outputs.
  - Also used for signal compression — store/transmit fewer bits per time-step.

**Shannon Source Coding**

- **Concept**: Shannon's source coding theorem — any source can be losslessly compressed to its entropy H(X), and no further.
- **Connection to basecalling**:
  - The nanopore signal has heavy redundancy — consecutive 6-mer windows share 5 of 6 bases, so the signal stream is highly correlated.
  - Raw signal: ~4 kHz × 16 bits = **64 kbps** of raw data.
  - Actual information rate: ~400 bp/sec × 2 bits/base = **~800 bps**.
  - So there's an information-theoretic ceiling: the signal is ~80× redundant. POD-5 compression and downstream representations exploit this.

**Euclidean Vector Representation**

- **Concept**: represent each k-mer (or signal context) as a fixed-dim vector in ℝᵈ, where similar contexts are close in Euclidean distance. The classic "embedding" idea.
- **In basecalling**:
  - The NN's intermediate embeddings ARE Euclidean vectors.
  - The output projection acts as nearest-codeword classification — each output class is an "anchor" vector in embedding space.
  - Euclidean distance is the natural similarity measure here: two 6-mers with similar current values should map to nearby embeddings.

**How the three fit together — the basecaller as a lossy compressor:**

```
raw signal              (high entropy, 64 kbps, noisy)
   │
   │  CNN front-end → lossy compression to embeddings
   ▼
embeddings              (Euclidean vectors, ℝ^512 per step)
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

The journey: **continuous noisy signal → information-bounded discrete sequence**. Vector quantization is the bridge between continuous embeddings and discrete output. Shannon source coding bounds how much compression is theoretically possible. Euclidean vectors are the language the NN thinks in.

---

## 4. Kraken-2

### 4.1 K-mer hashing → species identification

**The problem Kraken-2 solves:**
Given a read (ATGC string, length ~10²–10⁵), figure out **which species it came from**. This is *taxonomic classification*.

**The naive approach (don't):**
Align each read against every known reference genome and pick the best match. With ~10⁵ reference genomes and ~10⁶ reads per sample, you're looking at billions of alignments — computationally hopeless.

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
- Two reads from **different organisms** share very few k-mers — random-chance overlap is ~4⁻³⁵ ≈ 10⁻²¹ per k-mer.
- So k-mer overlap is a very strong species signal.

**The index (database):**
- Built once from reference genomes (RefSeq, GTDB, etc.).
- Maps `k-mer → LCA (Lowest Common Ancestor) in NCBI taxonomy`.
- **LCA logic**: if a k-mer appears in both *E. coli* and *Shigella* (close relatives), it maps to their common ancestor (genus level), not to either species. Reads with such k-mers get classified at the genus level — this avoids overconfident false species calls.

**Hashing scheme — minimizers (Kraken-2's key optimization):**
- Naive: store every k-mer in a giant hash table. Too big.
- **Minimizer trick**: for each window of `L` consecutive k-mers, store only the lexicographically smallest k-mer of the window (the "minimizer"). At query time, compute the minimizer for each window of the read and look it up.
- Result: ~10× DB shrinkage with minimal accuracy loss. (Default `k=35`, `m=31` — minimizer is a 31-mer inside each 35-mer window.)

**Output:**
- Per-read classification (taxon ID + confidence)
- Per-sample abundance summary
- Standard Kraken report formats (`.kraken` / `.report`)

### 4.2 Why the database is huge

The Kraken-2 **standard database is ~100 GB** loaded in memory. The size math:

- ~10⁵ reference genomes × ~10⁶ bp/genome ≈ **10¹¹ bp** of reference sequence.
- Unique k-mers extracted (k=35, with minimizers, m=31) ≈ **10¹⁰ entries**.
- Each entry: hash + taxon ID ≈ **8 bytes**.
- Total: ~80 GB hash table + auxiliary tables (LCA tree, taxonomy nodes) → **~100 GB**.

**Why the size is a problem:**
- Doesn't fit in RAM on most laptops/workstations (typical 16–64 GB).
- **Kraken-2 loads the entire DB into memory at startup** — there's no on-disk fallback for the hot lookup path. So if you can't fit it, you can't run it (at least not with the standard DB).
- For **point-of-care clinical use** (e.g., a device in a hospital triage room), 100 GB is a non-starter.
- For **cloud deployment**, the per-instance memory is expensive.
- For **field / outbreak response** in low-resource settings, completely impractical.

This is why memory efficiency is the bottleneck — and your research angle.

### 4.3 Memory efficiency — **my research angle**

**The question:** can we make Kraken-2 (or a Kraken-2-equivalent classifier) run in **<10 GB or even <1 GB of memory**, without giving up too much accuracy?

**Approaches in the literature:**

1. **Smaller k / smaller alphabet**
   - Reduce k from 35 to e.g. 25 → smaller k-mer space, smaller DB.
   - Cost: more collisions, lower specificity.

2. **Better minimizer schemes**
   - Optimize the minimizer window size or hash function for tighter packing.
   - Research area: "universal hitting sets," "syncmers."

3. **Approximate membership data structures** ← *strong candidate direction*
   - Use a **Bloom filter** or **Cuckoo filter** instead of an exact hash table.
   - Bloom: small false-positive rate, no false negatives, much smaller memory.
   - Research projects: **BIGSI**, **COBS**, **Bloom Filter Trie**.
   - Tradeoff: false positives → spurious k-mer hits → noisier classification.

4. **Hierarchical / compressed databases**
   - **Centrifuge** uses an **FM-index** (compressed BWT) — smaller than Kraken-2's hash, slower lookups.
   - Kraken-uniq uses HyperLogLog counters for unique-k-mer counting.

5. **Streaming / partial classification**
   - Don't hold the full DB in RAM; stream queries against an on-disk index.
   - Trades latency for memory.

6. **Learned indexes / neural classifiers**
   - Replace the hash table with a neural net that maps k-mer → taxon.
   - Active research; not yet production-quality but interesting angle.

**Where you might land:**
Pick one direction — probably **Bloom-filter-based** or **learned-index-based** — and benchmark on real nanopore data (Dorado-called reads). Metrics:
- Memory footprint (peak RSS)
- Classification accuracy (precision/recall vs full-DB Kraken-2)
- Query throughput (reads/sec)

**Why nanopore data specifically helps your angle:**
- Nanopore reads are **long** (10³–10⁵ bp), so each read contains many k-mers.
- Even a noisier (lower-recall) classifier can still get a confident species call by **majority voting across the k-mers in a single long read**.
- This noise tolerance gives a smaller, lossier index room to work — which is the lever your research can pull on.

Exp-2 (Kraken-2 internals) + Exp-3 (end-to-end Dorado→Kraken benchmark) are the experimental scaffolding for this.

---

## 5. ESKAPE + AMR

### 5.1 ESKAPE pathogens

ESKAPE is an acronym for six bacterial pathogens that are especially good at *escaping* the effects of antibiotics. WHO lists them as priority threats:

- **E** — *Enterococcus faecium*
- **S** — *Staphylococcus aureus* (MRSA is the famous resistant variant)
- **K** — *Klebsiella pneumoniae*
- **A** — *Acinetobacter baumannii*
- **P** — *Pseudomonas aeruginosa*
- **E** — *Enterobacter* species

They're common in hospital-acquired infections, have evolved resistance to most antibiotics, and leave doctors with few treatment options. They're the "headline" organisms our pipeline is built to identify quickly.

### 5.2 AMR / MBR — why the crisis is growing

**Drivers of AMR:**
- Overuse of antibiotics in clinical settings.
- Massive use in agriculture (livestock).
- Antibiotic residues in the environment (wastewater).
- **Horizontal gene transfer** — resistance genes spread between bacteria via plasmids, not just inherited; AMR can jump species.

**Impact:**
- WHO projection: AMR could cause **~10 million deaths/year by 2050** if unchecked.
- Treating resistant infections costs thousands more per patient.
- "Last-line" antibiotics like colistin are losing effectiveness.

**MBR** — *still to be clarified with mam at the next meeting.* Most likely "Multi-drug Bacterial Resistance" (informal abbreviation, related to MDR). See open question flagged in §2.5.

### 5.3 Kraken-2's role in detection

**The clinical workflow we're building toward:**

1. Patient sample (blood, swab) → DNA extraction
2. Nanopore sequencing → POD-5 raw signal
3. **Dorado** basecalling → ATGC reads
4. **Kraken-2** classification → which bacterial species are present
5. (Parallel step: identify resistance genes via tools like **CARD** / **ResFinder**)
6. Doctor gets: *"Patient has K. pneumoniae, resistant to carbapenems."*
7. Targeted antibiotic prescribed within **hours** instead of days.

**Speed matters:**
- Traditional culture-based ID takes **24–72 hours**.
- Nanopore + Kraken-2 can do this in **1–4 hours**.
- For sepsis patients, faster ID = lives saved.

**Why memory matters (research angle, again):**
- Point-of-care devices have limited RAM (often 16 GB).
- Hospital servers need to run many concurrent samples.
- Field deployment (low-resource clinics, outbreak response) needs lightweight tools.
- Your work could enable Kraken-2-class classification on a laptop or even Raspberry-Pi-class hardware.

---

## 6. Experiments

### Exp-2 — components
- Study Kraken-2 internals — k-mer hashing
- Test basecalling models on available data; measure accuracy + inference time
- Understand Dorado mechanics
- CPU/GPU memory model

### Exp-3 — end-to-end
- Dorado + Kraken end-to-end accuracy measurement
- Profile with `perf` + Nsight (per Kolin sir's mail)

---

## 7. Setup & Installation

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
