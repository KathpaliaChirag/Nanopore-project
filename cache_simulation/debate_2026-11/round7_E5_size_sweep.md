# E5 size sweep: hll guard vs stock S19, 7 read counts x 4 databases (luna, 2026-11-23)

setup: T=32, plain --report (stock and guard) plus a third variant, stock without --report (the floor). read counts 10, 100, 1,000, 10,000, 104,918, 500,000, 1,872,777 (100, 10,000 and 500,000 are nested prefixes of the real read files, built in /dev/shm). three repetitions per cell, interleaved, median wall time in seconds. raw rows: e5/sweep.csv (252 timed runs). correctness: e5/sweep_correct.txt.

## correctness: 28 of 28 cells pass

in every database x read-count cell the per-read classification output is byte-identical to stock (cmp) and the sorted report is identical. only the line order of tied siblings in the plain report differs, as documented in round6.

## timing (stock -> guard, speedup)

| reads | 50 MB | 8 GB | 16 GB | 103 GB |
|---|---|---|---|---|
| 10 | 0.06 -> 0.05 s, 1.20x | 0.28 -> 0.26 s, 1.08x | 0.48 -> 0.43 s, 1.12x | 3.37 -> 3.04 s, 1.11x |
| 100 | 0.17 -> 0.17 s, 1.00x | 0.36 -> 0.35 s, 1.03x | 0.55 -> 0.54 s, 1.02x | 3.23 -> 3.21 s, 1.01x |
| 1,000 | 0.23 -> 0.22 s, 1.05x | 0.41 -> 0.39 s, 1.05x | 0.62 -> 0.59 s, 1.05x | 3.28 -> 3.19 s, 1.03x |
| 10,000 | 0.34 -> 0.34 s, 1.00x | 0.52 -> 0.49 s, 1.06x | 0.75 -> 0.70 s, 1.07x | 3.41 -> 3.31 s, 1.03x |
| 104,918 | 0.79 -> 0.77 s, 1.03x | 1.00 -> 0.91 s, 1.10x | 1.26 -> 1.16 s, 1.09x | 4.27 -> 3.83 s, 1.11x |
| 500,000 | 2.46 -> 2.33 s, 1.06x | 2.64 -> 2.36 s, 1.12x | 3.23 -> 2.78 s, 1.16x | 7.72 -> 5.70 s, 1.35x |
| 1,872,777 | 8.39 -> 7.90 s, 1.06x | 8.64 -> 7.54 s, 1.15x | 10.02 -> 8.56 s, 1.17x | 19.73 -> 12.21 s, 1.62x |

## what it shows

- the gain grows with the number of reads, because the counting cost scales with lookups that hit. it is largest on the biggest database (1.62x at 1.87M reads on 103 GB, 1.35x at 500k).
- the guard matches the stock-without-report floor in every cell (for example 103 GB at 1.87M reads: guard 12.21 s, stock without report 12.27 s). so the whole report-related overhead is gone.
- on tiny inputs (10 to 10,000 reads) the differences are 0.01 to 0.4 s and mostly inside run-to-run noise on a shared machine. do not read the 1.20x at 50 MB / 10 reads (0.06 vs 0.05 s) as a real speedup. the one tiny-input cell that looks real is 103 GB at 10 reads (3.37 vs 3.04 s, floor 2.99 s), which suggests the exit cost of the counters shows up even then, but it is a single median of three runs.
- no cell is slower with the guard.
- speedups quoted earlier (1.64x at 103 GB) came from 4 interleaved repetitions. this sweep's 1.62x median is consistent with it.
