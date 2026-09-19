# cleanstart

started 2026-09-19. a from-scratch redo of the hardware cache simulation, done by hand by CK, one step at a time.
the old cache_simulation/ folder stays untouched as history. nothing in it is trusted here until re-measured.

## the one question

what hardware cache (L1d / L2 / L3 size and associativity) is best for running kraken2?

## fixed rules

- binary: S0 only (`kraken2-src-baseline`, no software cache). the software cache is out of scope here.
- reads: `~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_10.fastq` (104,980 reads, 723 MB, dorado sup basecall, already on Luna, no new basecalling needed). each simulator run uses a nested-prefix slice of it: 10, 50 or 100 reads (`~/cleanstart/workloads/reads_{10,50,100}.fastq`).
- databases (3, one at a time): 50 MB = `sample_targeted`, 8 GB = `standard_8gb`, 16 GB = `standard_16gb`, all under `~/chirag_K/AccuracyDrift/databases/`.
- simulator: Sniper, detailed mode (no `--fast-forward`), `-n 1`.
- change exactly one hardware knob per run (L3 size, then L2, L1d, associativity). everything else stays fixed.
- after every step: explain the result, log it in command_log.md, commit, push.

## files

- `command_log.md` - every command actually run, in order, with why and result.
