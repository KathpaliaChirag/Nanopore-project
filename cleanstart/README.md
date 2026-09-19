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

## baseline definition (redefined 2026-09-19, supersedes the first 10-read run)

- hardware: `laptop.cfg` (Ryzen 7 5800H) + `configs/cleanstart_laptop.cfg`: instruction cache modeling ON, L1 TLBs 64 entries fully associative, L2 TLB 2048 entries 8-way.
- core counts 1, 4, 8 (`classify -p N`, forced `general/total_cores=N`). **total L3 stays 16 MB at every core count** (per-slice size = 16 MB / cores), so core count never changes L3 capacity.
- L1d 32 KB 8-way, L2 512 KB 8-way private, L3 16 MB 16-way (NUCA slices), LRU everywhere, no prefetchers, DRAM 45 ns / 57.6 GB/s (Sniper default, not measured).

## test naming

every config is named by all its knobs, e.g. the baseline is
`L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`
(L3/L2/L1 sizes, then L1/L2/L3 ways). "L3" size is the TOTAL across slices. "L1" means L1d only. results live in `results/<name>/<cores>c_r<reads>_<db>` and one row per run goes to `results/summary_all.csv`. sweeps change one term of the name at a time.

## scripts

- `scripts/run_one.sh <cores> <reads> <db>` - one run, knobs via env vars (L3_KB, L2_KB, L1_KB, L1W, L2W, L3W).
- `scripts/run_baseline_queue.sh` - the 27-run baseline queue (3 core counts x 3 read counts x 3 dbs).
