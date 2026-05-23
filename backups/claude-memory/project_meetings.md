---
name: Meeting Minutes Summary
description: Key decisions and open action items from Nanopore project meetings 1–3 (May 2026)
type: project
originSessionId: e7e2edb7-b73c-4a06-bf1d-41333e9c9c80
---
## Meeting 1 — 2026-05-11
Introductory. Covered: nanopore basics, sample prep, basecalling tools (Dorado/Guppy/Bonito), Kraken-2 intro, ESKAPE pathogens + AMR/MBR.
- MBR meaning was to be clarified at next meeting.
- Three planned experiments: (1) CPU/GPU data flow study, (2) Kraken-2 internals + basecalling benchmarking, (3) end-to-end Dorado→Kraken pipeline + perf/Nsight profiling.

## Meeting 2 — 2026-05-15
- Golden dataset: pull ESKAPE sequences from NCBI
- Build reduced Kraken-2 DB (8–16 GB) using Kraken-2's built-in utility (Chayanika mam has done this before)
- Run pipeline on Colab
- Measure accuracy + runtime at each DB size
- Study Kraken-2 internals/source code

## Meeting 3 — 2026-05-18
- **GitHub repos mandatory** — both repos must be viewable by Kolin sir at all times
- Research directions confirmed: cache reuse profiling, hotspot analysis (gprof, Valgrind/cachegrind), matrix op identification, cache blocking + SIMD optimization
- Next meeting: TBD

## Current open action items (as of 2026-05-18)
- Set up and share 2 GitHub repos
- Pull ESKAPE sequences from NCBI
- Build reduced Kraken-2 DB
- Run Dorado → Kraken-2 on golden data in Colab
- Profile Kraken-2 with gprof + Valgrind/cachegrind
- Identify matrix/vector blocks in Kraken-2 source
- Research cache blocking and SIMD opportunities
- Document findings in knowledge base (§14 onwards)
