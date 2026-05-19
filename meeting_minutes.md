# Meeting Minutes — Nanopore Project

---

## Meeting 1 — 2026-05-11 (3–5 pm)

**Attendees:** chayanika mam, chirag K, rohit, rishab, chirag S   
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
**important update :** Next meeting shifted to monday i.e, 18-05-26 
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
TBD
