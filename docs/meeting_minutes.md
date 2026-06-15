# Meeting Minutes — Nanopore Project

---

## Meeting 1 — 2026-05-11 (3–5 pm)

**Attendees:** Chayanika mam, Chirag K, Rohit, Rishabh, Chirag S   
**Format:** First introductory meeting

### Topics covered

1. **Nanopore sequencing basics**
   - Physical mechanism — DNA through a pore, current as signal
   - Device structure — flow cell → membrane → channels → pores
   - K-mer window (5–6 bp), 4096 patterns
   - Ionic current as the "voice" of DNA
   - POD-5 raw signal format and squiggle visualization

2. **Sample preparation pipeline**
   - DNA extraction, fragmentation, adapter ligation
   - Y-adapter structure — motor protein, leader sequence, docking point/tether
   - Kit names: LSK (ligation), RAD (rapid)
   - MinION vs PromethION specs
   - AMR and MBR terminology introduced *(MBR meaning to be clarified)*

3. **Basecalling tools introduced**
   - Dorado (current), Guppy (deprecated), Bonito (research)
   - Neural inference on squiggles — seq2seq framing, CTC
   - Signal compression angle: VQ, Shannon source coding, Euclidean vectors

4. **Kraken-2 introduced**
   - K-mer hashing for species identification
   - Database size (~100 GB) as the core bottleneck
   - **Research angle identified:** memory-efficient classification

5. **ESKAPE pathogens + AMR/MBR**
   - Clinical motivation for the project
   - Kraken-2's role in point-of-care diagnostics

6. **Planned experiments**
   - EXP 1: study internals of cpu gpu how data goes etc
   - Exp-2: Kraken-2 internals + basecalling model benchmarking
   - Exp-3: end-to-end Dorado → Kraken pipeline + perf/Nsight profiling

### Action items / open questions
- Review **Kolin sir's mail** on `perf` and Nsight profiling tools
- Clarify what **MBR** stands for (next meeting)
- Start reading through all topics and building knowledge base

### Next meeting
**2026-05-17**

---

## Meeting 2 — 2026-05-15

**Attendees:** Chayanika mam, Chirag K, Chirag S  
**Format:** Discussion / planning
**Important update:** Next meeting shifted to Monday, i.e., 2026-05-18
### Topics covered

1. **Golden data — ESKAPE toy dataset**
   - Use a small curated dataset of ESKAPE pathogen sequences as a "golden dataset" — a toy database to experiment with rather than the full 100 GB Kraken-2 DB
   - Source: **NCBI** — sequences to be pulled from there

2. **Run Kraken-2 on the golden data**
   - Plan to run it on **Colab or similar** (cloud environment) — feasible here because we're using a small custom DB, not the full 100 GB standard DB
   - Goal: get the pipeline actually running end-to-end on real ESKAPE data

3. **Reduce the Kraken-2 database size**
   - mam mentioned she has done this before using a **utility section** in Kraken-2
   - Kraken-2 has built-in tools to build a custom, smaller database from a subset of reference genomes
   - This is the practical path to running Kraken-2 without needing 100 GB RAM
   - **Action item:** find and study this utility in Kraken-2's docs/source

4. **Study Kraken-2 properly**
   - Break it down internally — understand the code, not just the concept
   - Connects to Kolin sir's caching project (KB §8.1) — need to understand internals before adding a cache layer


### Metrics to measure
- **Accuracy** — how correct are the species classifications vs ground truth (golden data gives us the ground truth since sequences are known)
- **Time** — how long does classification take at each DB size
- Together these give the accuracy vs speed vs memory trade-off curve that Kolin sir's caching project needs as a baseline

### Action items
- Pull ESKAPE pathogen sequences from NCBI
- Build a reduced Kraken-2 database (target 8–16 GB) using the built-in utility mam mentioned
- Run Dorado → Kraken-2 pipeline on this golden data in Colab
- Measure accuracy and runtime at each DB size
- Study Kraken-2 internals / source code

---

## Meeting 3 — 2026-05-18

**Attendees:** Kolin sir, Chayanika mam, Chirag K, Chirag S, Rohit, Rishabh
**Format:** Task assignment + research direction

### Topics covered

1. **GitHub documentation (mandatory)**
   - Maintain **2 GitHub repositories** covering all work done and all meeting discussions
   - Both repos must be viewable by Kolin sir at any time — treat them as the living record of the project
   - **Repo 1 (Chirag K + Chirag S):** maintained jointly by both Chirags 
   - **Repo 2 (Rishabh + Rohit):** maintained jointly by Rishabh and Rohit 

2. **Performance improvement research — POD-5 → Dorado → Kraken-2 pipeline**

   Two axes of improvement were identified:

   **a) Time improvement (storage access + compute)**
   - Investigate **cache reuse** opportunities along the pipeline — where are the same data structures or lookups repeated?
   - Use **hotspot profiling tools** to find bottlenecks:
     - `gprof` — CPU-level call graph profiling
     - `Valgrind` (especially `cachegrind`) — cache miss analysis, memory access patterns
   - Identify **compute-heavy blocks** in Kraken-2 and Dorado:
     - Look for **matrix-vector**, **vector-matrix**, and **matrix-matrix** multiplication blocks
     - Apply **cache blocking / tiling** to improve data locality for these blocks
     - Explore **MMX2 / SIMD** (e.g., AVX2, AVX-512) intrinsics to vectorize inner loops
   - Goal: reduce memory latency + increase compute throughput on the same hardware

   **b) Accuracy improvement**
   - Improve classification accuracy through the full POD-5 → Dorado → Kraken-2 flow
   - Specific methods to be explored in follow-up meetings

### Key tools to investigate
| Tool | Purpose |
|---|---|
| `gprof` | CPU call-graph profiling — find which functions take the most time |
| `Valgrind / cachegrind` | Cache miss rates, memory access pattern analysis |
| `perf` | Linux hardware counter profiling (hotspots, cache misses, branch mispredictions) |
| SIMD / AVX2 / AVX-512 | Vectorized arithmetic — parallelize inner loop math |
| Cache blocking (tiling) | Restructure matrix ops to keep data in L1/L2 cache |

### Action items
- Set up and share **2 GitHub repos** (code + docs/minutes) — accessible to Kolin sir
- Profile Kraken-2 with `gprof` and `Valgrind/cachegrind` to find cache miss hotspots
- Identify matrix/vector computation blocks in Kraken-2 source
- Research cache blocking and SIMD opportunities in those blocks
- Document findings in the knowledge base (§14 onwards)

### Next meeting
2026-05-28

---

## Meeting 4 — 2026-05-28

**Attendees:** Kolin sir, Chayanika mam, Chirag K (CK), Chirag Suthar, Rishabh, Rohit
**Format:** Progress review + summer direction assignment

### Profiling results presented

CK presented the baseline profiling report covering both pipeline stages:

**Kraken-2 (CPU) — 3-tool verdict: memory-bound**

| Tool | Finding |
|---|---|
| perf stat | 34.24% cache miss rate, 301M misses per run |
| gprof | 67% of runtime in `CompactHashTable::Get()`, 9.87M calls |
| AMD uProf | IPC = 0.55 — CPU stalling, not computing |

**Dorado (GPU) — verdict: compute-bound** *(source: WSL2 GTX 1650 run — Minerva/Luna Dorado profiling not yet done as of this meeting)*

| Tool | Finding |
|---|---|
| Nsight Systems | GEMM = 82% of GPU time (Tensor Cores FP16) |
| Nsight Systems | cudaStreamSynchronize = 98.9% of CUDA API time |

Matrix multiply benchmark study (12 C implementations, N up to 10000) also presented to show empirical validation of cache-blocking theory.

### Discussion — Kraken-2 optimisation ideas

Two early ideas were discussed in the meeting:

**Idea 1 — Sequential ESKAPE query pipeline**
Instead of loading one large DB and querying everything at once, query each of the 6 ESKAPE pathogens (E, S, K, A, P, E) one at a time. Benefits: smaller active DB per query fits better in cache; can short-circuit once a dominant match is found; reduces working set per lookup. Needs: accuracy vs speed trade-off analysis.

**Idea 2 — L3 cache pinning / frequency-aware partitioning**
Pre-compute the most frequent k-mers for each ESKAPE pathogen from real clinical samples. Pin or pre-load these hot k-mers into L3 so lookups for the dominant species hit L3 instead of RAM. Basis: clinical samples tend to be dominated by one pathogen (barcode02 from the AIIMS POD-5 dataset classifies as 100% P. aeruginosa by reads_sup Kraken2), so k-mer access is not uniformly random — a hot set exists. `CompactHashTable::Get()` is confirmed at 67% of runtime and ~30 L3 misses per call.

More ideas to be proposed by both Chirags in the 3-day deliverable.

### Summer goal — decided

**Primary focus for summer: Kraken-2 optimisation only.**

Dorado / GPU work is deprioritised for now. The memory-bound nature of Kraken-2 and the clear hotspot (`CompactHashTable::Get()`) make it the right target.

### Work split

| Team | Task | Deliverable | Deadline |
|---|---|---|---|
| Chirag K + Chirag S | Deep Kraken-2 analysis: CPU/memory/IO stats, confirm memory-bound vs IO-bound, propose 2–3 concrete optimisation ideas | Written report | 2026-05-31 |
| Rohit + Rishabh | Spiking neural network approach for Dorado — track spikes in electrical signal, explore speedup vs Dorado basecaller | No report yet — research phase | TBD |

### Action items

**Chirag K + Chirag S (due 2026-05-31):**
- Run deeper Kraken-2 profiling: distinguish memory-bound vs I/O-bound (page fault analysis, DRAM bandwidth measurement, `perf mem` or `numactl` on Luna)
- Get per-function LLC miss rates via `cachegrind` on Luna (Minerva disk full)
- Run `perf record` / `perf report` for source-line hotspot inside `CompactHashTable::Get()`
- Measure k-mer reuse distribution from barcode02.fastq — quantify actual hit rate potential
- Propose 2–3 specific, implementable optimisation ideas with complexity and expected speedup estimates
- Write `kraken2_optimisation_report.md` and push to GitHub

**Rohit + Rishabh:**
- Research SNN (spiking neural networks) as a replacement or accelerator for Dorado basecalling
- Goal: can spike timing from raw nanopore signal replace some or all of the Transformer forward pass?
- No written report required at this stage

### Next meeting
2026-06-02

---

## Meeting 5 — 2026-06-02

**Attendees:** Kolin sir, Chirag Suthar, Chirag Kathpalia
**Format:** Direction setting + new experiments

### Topics covered

1. **MHA in NVIDIA GPUs — research item**
   - Kolin sir asked the team to read about MHA (Multi-Head Attention, the core operation in transformer models — for each token, it computes attention scores against all other tokens using Q, K, V matrices)
   - Specific question: is NVIDIA GPU hardware designed to accelerate MHA, or does MHA happen to map well to existing GEMM units?
   - Context: Dorado is a transformer-based basecaller, so understanding MHA hardware support is relevant to Dorado profiling

2. **Neural data prefetcher — new research direction**
   - Current Kraken-2 work uses `__builtin_prefetch` (explicit software prefetch hints, as in Patch 1 of the optimisation series)
   - New direction: replace or augment this with a small neural network that learns access patterns from a sequence of historical memory reads and predicts the next address to prefetch
   - The NN observes a window of recent read addresses and outputs a predicted next address
   - The model should be lightweight enough to run alongside the application without adding overhead
   - Target accuracy: **70-80%** — a miss prediction still falls back to hardware prefetch, so partial accuracy is useful

3. **End goal: LLC miss rate to near zero**
   - Current Kraken-2 LLC miss rate on Luna is approximately 80% (confirmed from `perf stat` profiling)
   - If LLC miss rate reaches near 0, the prefetcher has succeeded and can be considered complete
   - If LLC miss rate is already near 0 (e.g., data fits entirely in cache), no prefetcher is needed at all
   - This gives a clear stopping criterion: keep improving the prefetcher until LLC miss drops to an acceptable level

4. **Documentation on multiple machines**
   - All experiments must be properly documented across different hardware
   - Systems to cover: Minerva (CK account), Luna (Intel Xeon), Chirag Suthar's system, lab Linux desktop
   - Reason: LLC miss rates are hardware-dependent — same workload behaves differently on 16 MB Ryzen L3 vs 105 MB Xeon L3

5. **Key experiment — Kraken-2 LLC miss rate vs dataset size (most important action item)**
   - Run Kraken-2 with multiple database/dataset sizes: 650 MB, 8 GB, 16 GB, and others as available
   - Record LLC miss rate at each size, on all four systems
   - The expected finding: as dataset size exceeds L3 capacity, LLC miss rate should jump sharply
   - Output: clean tables and graphs comparing miss rate vs dataset size across machines
   - This gives direct empirical data on where the cache cliff is for each system

### Action items

| owner | task | notes |
|---|---|---|
| Chirag K | research MHA in NVIDIA — what is MHA, does Hopper/Ada hardware have dedicated MHA units, how does Flash Attention exploit memory hierarchy | write a short summary doc |
| Chirag K + Chirag S | design neural prefetcher concept — pick a simple NN architecture (e.g., LSTM or MLP on recent access delta sequence), define input window, output prediction, accuracy metric | idea sketch first, no code yet |
| Chirag K + Chirag S | **run Kraken-2 LLC miss rate vs dataset size** on Minerva, Luna, Chirag S's system, lab Linux desktop — sizes: 650 MB, 8 GB, 16 GB minimum | produce tables + graphs, push report to GitHub |
| Chirag K + Chirag S | documentation: ensure profiling results on all four machines are captured with system specs and dataset sizes | needed before the neural prefetcher phase |

### Key numbers to track

| system | L3 cache | expected cliff size |
|---|---|---|
| Luna (Xeon Platinum 8468, dual-socket) | 105 MB | ~100 MB dataset |
| Minerva (account: CK) | ~66 MB | ~66 MB dataset |
| Chirag Suthar's system | TBD | TBD |
| Lab Linux desktop | TBD | TBD |

### Next meeting
TBD
