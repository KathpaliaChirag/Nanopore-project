---
name: Nanopore Project Overview
description: Research project on POD-5 → Dorado → Kraken-2 pipeline performance optimization for ESKAPE pathogen classification
type: project
originSessionId: e7e2edb7-b73c-4a06-bf1d-41333e9c9c80
---
## Core pipeline
POD-5 (raw signal) → **Dorado** (basecalling) → **Kraken-2** (species classification)

## Research goals
Two axes:
1. **Time/performance improvement** — cache reuse, hotspot profiling, cache blocking/tiling, SIMD (AVX2/AVX-512) vectorization of matrix ops in Kraken-2 and Dorado
2. **Accuracy improvement** — improve classification accuracy end-to-end (methods TBD)

## Key bottleneck
Kraken-2 standard DB is ~100 GB. Solution: build a reduced custom DB (target 8–16 GB) using Kraken-2's built-in utility tools from NCBI ESKAPE sequences.

## Golden dataset
Small curated ESKAPE pathogen sequences from NCBI — used as ground truth for accuracy measurement. Run pipeline on Colab (feasible at reduced DB size).

## Metrics
- Accuracy vs ground truth (golden dataset)
- Runtime at each DB size
- Together: accuracy vs speed vs memory trade-off curve as baseline for Kolin sir's caching project

## Profiling tools
| Tool | Purpose |
|---|---|
| `gprof` | CPU call-graph profiling |
| `Valgrind/cachegrind` | Cache miss rates, memory access patterns |
| `perf` | Linux hardware counter profiling |
| SIMD/AVX2/AVX-512 | Vectorized arithmetic for inner loops |
| Cache blocking (tiling) | Keep matrix ops in L1/L2 cache |

## GitHub repos (mandatory, viewable by Kolin sir)
- Repo 1: Chirag K + Chirag S
- Repo 2: Rishabh + Rohit

**Why:** Kolin sir requires living documentation of all work and meeting discussions at all times.
