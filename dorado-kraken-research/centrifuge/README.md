# Centrifuge Baseline — MTP Week 1

Both thesis pieces (adaptive k-mer cache, cell-width + double hashing) need a real comparison point, not just Kraken2's own numbers. This folder is where that comparison point gets built: Centrifuge, installed and run the same way Kraken2 was, on the same machines, against the same ESKAPE genomes.

Full week plan lives at `../../mtpweek1plan.md`. This folder is the working log while that plan gets executed.

## Files

| File | What's in it |
|---|---|
| `WEEK1_FINDINGS.md` | **Start here** — readable summary: how Centrifuge works, why the genome database had to be rebuilt, comparison tables, and the actual conclusion |
| `commands_log.md` | Every command run, in order, with a one-line reason and the result |
| `observations.md` | Findings, gotchas, decisions — with flowcharts/tables as they come up |

## Status

Started 2026-08-01. Steps 1, 3, and 4 of the week plan are done (Luna) — see `WEEK1_FINDINGS.md` for results. **Orion install (Step 2) dropped for now** — Centrifuge is already 5.5-18x slower than Kraken2 on Luna's 96-core server, so porting to a much weaker ARM64 edge device isn't a good use of time right now (reasoning in `WEEK1_FINDINGS.md`). Fibonacci hashing reading (Step 6) still open.
