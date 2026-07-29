# Meeting Minutes — Nanopore Project

---

## Meeting 1 — 2026-05-11 (3–5 pm)

**Attendees:** Chayanika ma'am, Chirag K, Rohit, Rishabh, Chirag S   
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
**2026-05-15**

---

## Meeting 2 — 2026-05-15

**Attendees:** Chayanika ma'am, Chirag K, Chirag S  
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
   - Chayanika ma'am mentioned she has done this before using a **utility section** in Kraken-2
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
- Build a reduced Kraken-2 database (target 8–16 GB) using the built-in utility Chayanika ma'am mentioned
- Run Dorado → Kraken-2 pipeline on this golden data in Colab
- Measure accuracy and runtime at each DB size
- Study Kraken-2 internals / source code

---

## Meeting 3 — 2026-05-18

**Attendees:** Kolin sir, Chayanika ma'am, Chirag K, Chirag S, Rohit, Rishabh
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

**Attendees:** Kolin sir, Chayanika ma'am, Chirag K (CK), Chirag S, Rishabh, Rohit
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

**Attendees:** Kolin sir, Chirag K, Chirag S
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
2026-07-04 (became the Mamba-as-MHA pivot meeting, below)

---

> **Note on Meetings 6–8 below:** no live minutes were taken for this stretch — `meeting_minutes.md` went unmaintained from 2026-06-02 to 2026-07-29 while the project pivoted to Mamba-as-MHA (2026-07-04) and then back to the kraken2 thesis work (2026-07-25). These three entries are **reconstructed** from commit history, doc content, and two whiteboard photos supplied by CK on 2026-07-29 — not from a contemporaneous note-taker. Dates are best-effort from git timestamps; attendee lists assume Kolin sir + Chirag K unless evidence says otherwise. **Confirm/correct exact dates, attendees, and any discussion not reflected in committed files.**

## Meeting 6 — 2026-07-04 *(date inferred from commit `cda8aee`/`10a98fc`; confirm)*

**Attendees:** Kolin sir, Chirag K *(confirm if Chirag S / Rishabh / Rohit were present)*
**Format:** Direction pivot + curriculum assignment

### Topics covered

1. **Pivot: Dorado/Kraken2 profiling → Mamba-as-MHA**
   - Direction changed from the summer's Dorado (GPU basecaller) / Kraken2 (CPU classifier) profiling work to a new research question: can **Mamba** (a state-space sequence model) be reformulated to run as an **MHA (multi-head attention)**-shaped computation, so it can ride the hardware/kernel paths (GEMM, tensor cores, FlashAttention-style kernels) chips already optimise for attention?
   - Motivation: newer chips have increasingly dedicated hardware/software paths for MHA (tensor cores, transformer engines, FP8 attention support) — a decade of vendor tuning Mamba's bespoke selective-scan kernel doesn't get.
   - Theoretical basis: the Mamba-2 **State Space Duality (SSD)** result (Dao & Gu, 2024, *"Transformers are SSMs"*) — a structured SSM and masked attention are the same computation viewed two ways.
   - Open question raised, left unresolved: does this connect to **NanoMambaNet** (an edge-inference pipeline sir mentioned previously re: an LSH neural-cache idea), or is it a standalone exercise?
   - Target hardware **not decided** — Luna (L40S GPU) vs Orion (Jetson edge) vs both — explicitly left open for exploration.
   - Noted: Chirag K has zero ML background going in — everything downstream (explainer doc, this curriculum) had to be built for that.

2. **ML fundamentals curriculum assigned** (whiteboard)

   | # | Topic |
   |---|---|
   | 1 | Linear Algebra |
   | 2 | Matrix / Vector operations |
   | 3 | O.D.E. — Differential equations |
   | 4 | Single-layer perceptron |
   | 5 | MLP (multi-layer perceptron) — gradient, loss function, activation function, feedforward, backprop, dense layers |

   Then, building toward Transformers — a sequence-model chain:
   **vanilla RNN → problems of vanilla RNN → BiRNN → LSTM → BiLSTM → problems of LSTM → vanilla attention → Transformer encoder → Transformer encoder+decoder**

   Items 1–5 bracketed on the board under **ANN / NN** — i.e. these are general neural-network foundations, not Mamba-specific, meant to be covered before the sequence-model chain.

3. **Roadmap set: 5 phases** (per `MAMBA_MHA_EXPLAINER.md` §6 / project memory)
   1. Explainer doc, written for zero-ML-background reader (Phase 0)
   2. Toy numerical proof (recurrence = attention-shaped matmul)
   3. Real-scale implementation
   4. Benchmark on target chip
   5. Write-up

### Action items
- Write the zero-background explainer doc — **done same day**, `MAMBA_MHA_EXPLAINER.md` (later restyled to CK's writing-style guide, then rewritten professor-voice, same session)
- Work through ML curriculum topics 1–5 and the RNN→Transformer sequence-model chain
- Decide target chip (Luna vs Orion vs both) — left open
- Resolve whether this connects to NanoMambaNet — left open

### Next meeting
2026-07-06 *(became Meeting 7, below — confirm)*

---

## Meeting 7 — 2026-07-06 *(date inferred from commit `c14b7b4`; confirm)*

**Attendees:** Kolin sir, Chirag K *(confirm if others present)*
**Format:** SSM deep-dive / reading list

### Topics covered

Whiteboard titled **"Update Rules"** — the different ways a state-space model's update step can be derived/viewed, assigned as the next study block:

| Topic | Status (cross-checked against `MAMBA_MHA_EXPLAINER.md` on 2026-07-29) |
|---|---|
| Convolution (SSM as one big convolution) | **not yet written up** |
| Continuous (control-theory A/B/C formulation) | covered — explainer Ch. 4 |
| HiPPO (long-range-memory init. theory behind S4/Mamba) | **not yet written up** |
| Discretization (continuous ODE → discrete recurrence) | covered — explainer Ch. 4 |
| Mamba (selective scan, input-dependent A/B/C) | covered — explainer Ch. 4 |
| Mamba-2 (State Space Duality — SSM = masked attention) | covered — explainer Ch. 5 |
| Transformer + Mamba variation (hybrid attention/SSM architectures) | **not yet written up** |
| Zamba (specific hybrid Mamba+attention architecture) | **not yet written up** |

Same-day commit `c14b7b4` overhauled the explainer with a 5-expert multi-agent review (ML/DL, biology/nanopore, systems, visualization, pedagogy) and added 9 awk-generated SVG figures — consistent with this being the session that pushed Chapters 4–5 (control theory → discretization → selective scan → SSD proof) into their current form. The **convolution view, HiPPO, and hybrid architectures (Transformer+Mamba, Zamba) are the items from this list that never got written up** before the 2026-07-25 pivot back — they're the concrete gap if Mamba work resumes.

### Action items
- Write up the convolution view of SSMs
- Write up HiPPO and why it enables long-range memory
- Research hybrid Transformer+Mamba architectures, incl. Zamba specifically
- (carried from Meeting 6) decide target chip — still open

### Next meeting
Not recorded — next entry in this file is the 2026-07-25 pivot back (Meeting 8)

---

## Meeting 8 — 2026-07-25

**Attendees:** Kolin sir (via email), Chirag K
**Format:** Email — direction reversal *(not a live meeting; recorded here to keep the timeline complete — confirm if a call/meeting also happened around this)*

### Topics covered

1. **Pivot back: Mamba-as-MHA (paused, not abandoned) → Kraken2/Dorado thesis work**
   - Kolin sir emailed asking to continue the summer kraken2 work toward **two thesis pieces**, both benchmarked against **Centrifuge** — not evaluated anywhere in this repo before this point.
   - Mamba-as-MHA is paused where Meetings 6–7 left it (explainer through Ch. 5/6; convolution view, HiPPO, and hybrid architectures still unwritten) — the same "paused, not abandoned" status the kraken2 work held from 2026-07-04 to 2026-07-25.

2. **Thesis 1 — Hardware-Aware Adaptive K-mer Cache**
   - Extends Patch 4 (sir's own thread-local k-mer cache design; 90.7% measured reuse rate, M5)
   - Baseline it as 4-way set-associative
   - Add LLC-topology-aware cache sizing
   - Add a biology-dependent (access-pattern-driven) adaptive eviction policy

3. **Thesis 2 — Cell-Width Reduction + Double Hashing**
   - Extends the completed cell-width experiment (32/24/16-bit cells, exponential false-positive law, 1,728-run cross-hardware sweep — joint work with Chirag Suthar, written up in `kraken2opti_report.tex`)
   - Resolves the report's §5 "three items of future work":
     1. Latency-hiding lookup cache — merge Patch 4's thread-local design with the report's 4-way set-associative LRU design (feeds Thesis 1)
     2. Switch Kraken2's default linear probing → double hashing (cuts expected probe length ≈6 → ≈2.5, shifts the false-positive cliff down ≈1.3 bits)
     3. A 6-bit-per-organism bitmask cell — one `Get()` answers all six ESKAPE panel members at once

4. **Centrifuge baseline** — not set up yet; needed as the comparison point for both theses

5. **Ask LLMs for more ideas** — sir suggested asking LLMs for additional ideas on both thesis pieces

### Action items
- Set up Centrifuge as the comparison baseline for both theses — not started
- Apply `kraken2_opt_v1.patch` and measure the real delta — still the top-priority item carried over from before the Mamba pivot (M1–M7 all say "go", patch itself never run)
- Ask LLMs for more ideas on both thesis pieces — **in progress**, `plan_2026-07-25.md` idea catalog started same day, syncmers/strobemers/PGO/GPU ideas added over the following two days (through `14a77fc`, 2026-07-27)
- Begin Thesis 1 (4-way set-associative baseline) and Thesis 2 (double hashing) implementation

### Next meeting
2026-07-29, 4–5 pm (see Meeting 9 — a standing weekly slot was set here)

---

## Meeting 9 — 2026-07-29 (Wednesday, 4–5 pm)

**Attendees:** Kolin sir, Chirag K
**Format:** Weekly check-in (first of a new recurring slot)

> **Standing meeting going forward: every Wednesday, 4–5 pm.** Add each week's entry below in the same format so this file stays current in real time instead of drifting again like it did between Meetings 5 and 8.

### Topics covered

1. **Execution planning for both thesis pieces**
   - Discussed how to actually sequence the work on Thesis 1 (adaptive k-mer cache) and Thesis 2 (cell-width + double hashing) — turning `plan_2026-07-25.md` from an idea catalog into an execution order.

2. **Fibonacci hashing — reading item**
   - Read up a little on Fibonacci hashing (multiply-and-shift hashing using a fixed constant derived from the golden ratio to spread values evenly across slots).
   - Already in use in Patch 4's thread-local cache design (`plan_2026-07-25.md` line 29 — slot lookup is "multiply the k-mer's 64-bit value by a fixed constant... take the top bits"); this reading connects directly to Thesis 1's cache work, and possibly to the Thesis 2 hashing scheme too.

3. **Centrifuge — start running in parallel**
   - Begin running Centrifuge on the side (alongside thesis implementation work), so the comparison baseline is being built up concurrently instead of as a separate blocking step later.

### Action items
- Write a concrete execution plan/order for Thesis 1 and Thesis 2 (turn `plan_2026-07-25.md` into sequenced steps)
- Read further on Fibonacci hashing and note how/where it applies to Thesis 1 (cache) and Thesis 2 (hashing scheme)
- Get Centrifuge running (setup + first data) in parallel with thesis implementation work
- Continue applying `kraken2_opt_v1.patch` and measuring the real delta — still outstanding

### Next meeting
2026-08-05, 4–5 pm (standing Wednesday slot)
