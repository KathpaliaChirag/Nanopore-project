# Meeting Minutes — Nanopore Project

---

## Meeting 1 — 2026-05-11 (3–5 pm)

**Attendees:** Chirag, mam  
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

**Attendees:** mam, Chirag Kathpalia, Chirag Suthar  
**Format:** Discussion / planning

### Topics covered

1. **Golden data — ESKAPE toy dataset**
   - Use a small curated dataset of ESKAPE pathogen sequences as a "golden dataset" — a toy database to experiment with rather than the full 100 GB Kraken-2 DB
   - Source: **NCBI** — sequences to be pulled from there
   - This gives a controlled, manageable input to test the full pipeline without needing massive storage or RAM

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

### Key new info
- **Chirag Suthar** is also on the project (was present at this meeting)
- Using a **reduced custom Kraken-2 DB** (ESKAPE-only) instead of the full standard DB makes Colab viable for this phase
- NCBI is the data source for the golden ESKAPE sequences

### Action items
- Pull ESKAPE pathogen sequences from NCBI
- Build a reduced Kraken-2 database using the built-in utility mam mentioned
- Run Dorado → Kraken-2 pipeline on this golden data in Colab
- Study Kraken-2 internals / source code
