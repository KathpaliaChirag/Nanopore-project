# Nanopore Project

This repo covers two pieces of work:

## Current focus: Mamba as MHA

Can **Mamba** (a state-space sequence model) be reformulated to run as an **MHA (multi-head attention)**-shaped computation, so it rides the same hardware-optimised path (GEMM/tensor cores) that chips already build for attention, instead of Mamba's own slower custom scan kernel?

Start here: **[`MAMBA_MHA_EXPLAINER.md`](MAMBA_MHA_EXPLAINER.md)** — a long-form, code-embedded study document written for zero ML background. Covers sequence models from first principles up through the Mamba-2 "State Space Duality" proof, with runnable numerical demonstrations.

## Prior work: Dorado + Kraken2 profiling

**[`dorado-kraken-research/`](dorado-kraken-research/)** — profiling and optimising a clinical diagnostic pipeline for ESKAPE antibiotic-resistant pathogens from nanopore sequencing data (Dorado GPU basecaller + Kraken2 CPU k-mer classifier). Paused as of 2026-07-04, not abandoned — M1-M7 measurements and Dorado L40S profiling are complete; applying the Kraken2 optimisation patch was the last open item. See `dorado-kraken-research/README.md` for the full writeup.

---

Supervisor: **Kolin sir** (Prof. Kolin Paul).
