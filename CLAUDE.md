# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Repo layout (pivoted back 2026-07-25)

The project pivoted to Mamba-as-MHA on 2026-07-04, then pivoted back to the kraken2/dorado thesis work on 2026-07-25 after Kolin sir's email asking to continue the summer work toward two thesis pieces. Both directions are real; only one is active at a time.

```
MAMBA_MHA_EXPLAINER.md      <- PAUSED, not abandoned (paused again 2026-07-25, was active 2026-07-04 to
                                2026-07-25). Mamba reformulated as MHA/attention for hardware efficiency.
                                Long-form study document, written for zero ML background, code embedded inline.
dorado-kraken-research/      <- CURRENT FOCUS (as of 2026-07-25): Dorado (GPU basecaller) + Kraken2 (CPU
                                k-mer classifier) profiling and optimisation, now extending into two thesis
                                directions per Kolin sir - see "Project purpose (current)" below.
  CLAUDE.md                  <- the full old project-instructions file (machines, paths, commands,
                                critical facts, patch status) - still accurate, just scoped to that subfolder now.
  CLAUDE_RECAP.md            <- session recap for the old work.
  README.md                  <- old project's master summary.
  AccuracyDrift/, Luna/, Minerva/, WSL2/, docs/, scripts/, reports/, presentation(s)/  <- old project's data/docs.
```

**If you are asked to work on Dorado, Kraken2, Luna, Orion/Jetson profiling, perf commands, the optimisation patch, AccuracyDrift, the k-mer cache thesis, cell-width/double-hashing, or Centrifuge comparisons** - go read `dorado-kraken-research/CLAUDE.md` first. All of that file's machine list, key paths, standard profiling commands, and critical facts are still correct; only the location moved.

**If you are asked to work on Mamba, MHA, state space models, or anything ML-architecture related** - that direction is paused, not gone. It lives at repo root, starting with `MAMBA_MHA_EXPLAINER.md`.

---

## Project purpose (current, as of 2026-07-25)

Kolin sir emailed 2026-07-25 asking to continue the summer kraken2 work toward **two thesis pieces** ("smaller database + smarter cache"), both benchmarked against **Centrifuge** (not previously evaluated in this repo - only mentioned in passing as background in `dorado-kraken-research/docs/knowledge_base.md`):

1. **Hardware-aware Adaptive K-mer Cache** - extends Patch 4 (the thread-local k-mer cache, sir's own design, see `dorado-kraken-research/CLAUDE.md`): baseline it as 4-way set-associative, add LLC-topology-aware cache sizing, add a biology-dependent (access-pattern-driven) adaptive eviction policy.
2. **Cell-Width Reduction + Double Hashing** - extends the completed cell-width experiment (32/24/16-bit cells, formalised with an exponential false-positive law and a 1,728-run cross-hardware sweep in `dorado-kraken-research/docs/reports/kraken2opti_report.tex`, joint with Chirag Suthar). "Complete the three items of future work" is §5 of that report: (1) a latency-hiding lookup cache - merge with Thesis 1's cache, (2) switch linear probing to double hashing to shrink the false-positive cliff, (3) a 6-bit-per-organism bitmask cell. None are implemented yet.

Sir also suggested asking LLMs for additional ideas on both pieces.

**Mamba-as-MHA direction (paused 2026-07-25):** exploring whether Mamba (a state-space sequence model) can be reformulated as an MHA-shaped computation for hardware efficiency, based on the Mamba-2 State Space Duality result (Dao & Gu, 2024). The user has zero ML background - any explanation/doc/comment aimed at them must define terms on first use. Target hardware was never decided (Luna vs Orion vs both). Resume from `MAMBA_MHA_EXPLAINER.md` §6 when picked back up.

---

## Supervisor / people

- Project supervisor is **Kolin sir** (Prof. Kolin Paul) - always use "sir".
- Other names, machine accounts, and collaborators are documented in `dorado-kraken-research/CLAUDE.md`.

---

## What Is Not Done Yet (current direction: kraken2 thesis work)

- Thesis 1 (Adaptive K-mer Cache): 4-way set-associative baseline, LLC-topology-aware sizing, biology-dependent adaptive eviction - none started, all extend Patch 4.
- Thesis 2 (Cell-Width Reduction + Double Hashing): the three future-work items from `kraken2opti_report.tex` §5 (merged lookup cache, linear→double hashing, bitmask cell) - none implemented yet.
- Centrifuge comparison baseline - not set up yet, needed for both theses.
- Still outstanding from before the Mamba pivot, per `dorado-kraken-research/CLAUDE.md` "What Is Not Done Yet": applying `kraken2_opt_v1.patch` and measuring the real delta (M1-M7 done, patch itself never run) is still the top-priority item underneath the new thesis work.
- Ask LLMs for additional ideas on both thesis pieces, per sir's email.

## Mamba-as-MHA direction (paused 2026-07-25, was active 2026-07-04 to 2026-07-25)

- Phase 1: small numerical proof that a toy Mamba block computes the same output as a recurrence and as an attention-shaped matmul (embedded as runnable code inside `MAMBA_MHA_EXPLAINER.md`, never run on the user's machine).
- Phase 2: real-scale implementation.
- Phase 3: benchmark on target chip (chip TBD).
- Phase 4: write-up.

See `MAMBA_MHA_EXPLAINER.md` §6 for the full roadmap and open questions. Paused, not abandoned - same status the kraken2 work had before this second pivot.
