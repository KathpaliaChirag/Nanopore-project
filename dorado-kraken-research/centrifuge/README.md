# Centrifuge baseline — MTP week 1

both thesis pieces (adaptive k-mer cache, cell-width + double hashing) need a real comparison point, not just Kraken2's own numbers. this folder is where that comparison point gets built: Centrifuge, installed and run the same way Kraken2 was, on the same machines, against the same ESKAPE genomes.

the full week plan lives at `../../planning/mtpweek1plan.md`. this folder is the working log while that plan gets executed.

## Files

| File | What's in it |
|---|---|
| `WEEK1_FINDINGS.md` | **start here**: a readable summary of how Centrifuge works, why the genome database had to be rebuilt, comparison tables, and the actual conclusion |
| `commands_log.md` | every command run, in order, with a one-line reason and the result |
| `observations.md` | findings, gotchas, decisions, with flowcharts/tables as they come up |

## Status

started 2026-08-01. steps 1, 3, and 4 of the week plan are done (Luna), see `WEEK1_FINDINGS.md` for results. **Orion install (step 2) dropped for now.** Centrifuge is already 5.5-18x slower than Kraken2 on Luna's 96-core server, so porting to a much weaker ARM64 edge device isn't a good use of time right now (reasoning in `WEEK1_FINDINGS.md`). Fibonacci hashing reading (step 6) still open.
