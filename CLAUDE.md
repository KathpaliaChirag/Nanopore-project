# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Repo layout (changed 2026-07-04)

This repository now has two parts:

```
MAMBA_MHA_EXPLAINER.md      <- current focus: Mamba reformulated as MHA/attention for hardware efficiency.
                                Long-form study document, written for zero ML background, code embedded inline.
dorado-kraken-research/      <- ALL prior work: Dorado (GPU basecaller) + Kraken2 (CPU k-mer classifier)
                                profiling and optimisation. This work is not being actively continued right
                                now, but nothing in it is stale/wrong - keep it as reference.
  CLAUDE.md                  <- the full old project-instructions file (machines, paths, commands,
                                critical facts, patch status) - still accurate, just scoped to that subfolder now.
  CLAUDE_RECAP.md            <- session recap for the old work.
  README.md                  <- old project's master summary.
  AccuracyDrift/, Luna/, Minerva/, WSL2/, docs/, scripts/, reports/, presentation(s)/  <- old project's data/docs.
```

**If you are asked to work on Dorado, Kraken2, Luna, Orion/Jetson profiling, perf commands, the optimisation patch, or AccuracyDrift** - go read `dorado-kraken-research/CLAUDE.md` first. All of that file's machine list, key paths, standard profiling commands, and critical facts are still correct; only the location moved.

**If you are asked to work on Mamba, MHA, state space models, or anything ML-architecture related** - that's the new direction, living at repo root. Start with `MAMBA_MHA_EXPLAINER.md`.

---

## Project purpose (current)

Research project exploring whether **Mamba** (a state-space sequence model, SSM) can be reformulated to run as an **MHA (multi-head attention)**-shaped computation, so it can use the GEMM/tensor-core hardware paths chips already optimise for attention, instead of Mamba's bespoke sequential-scan kernel. Theoretical basis: the Mamba-2 "State Space Duality" result (Dao & Gu, 2024), which proves a structured SSM and masked attention are the same computation viewed two ways.

**The user has zero ML background.** Any explanation, doc, or comment aimed at the user must define terms on first use and avoid assuming familiarity with attention, SSMs, linear algebra notation, or standard ML vocabulary. Code should be heavily commented in plain English, not just correct.

**Target hardware for eventual benchmarking is not yet decided** - could be Luna (L40S GPU, same machine as the old Dorado profiling) or Orion (Jetson edge ARM64), or both. Do not assume one without checking with the user first; this was explicitly left open as of 2026-07-04.

---

## Supervisor / people

- Project supervisor is **Kolin sir** (Prof. Kolin Paul) - always use "sir".
- Other names, machine accounts, and collaborators are documented in `dorado-kraken-research/CLAUDE.md`.

---

## What Is Not Done Yet (new direction)

- Phase 1: small numerical proof that a toy Mamba block computes the same output as a recurrence and as an attention-shaped matmul (this is embedded as runnable code inside `MAMBA_MHA_EXPLAINER.md`, but hasn't been run on the user's machine yet).
- Phase 2: real-scale implementation.
- Phase 3: benchmark on target chip (chip TBD).
- Phase 4: write-up.

See `MAMBA_MHA_EXPLAINER.md` §6 for the full roadmap and open questions.

## What Was Done (old direction, paused not abandoned)

See `dorado-kraken-research/CLAUDE.md` "What Is Not Done Yet" / "Done, despite earlier notes to the contrary" sections - as of the pivot, M1-M7 were done, Dorado L40S profiling was done, and applying `kraken2_opt_v1.patch` was the single top-priority remaining item. That work is paused, not finished, and not thrown away.
