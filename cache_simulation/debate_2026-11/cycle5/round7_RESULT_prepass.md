# making the exactness pre-pass cheaper (luna, 2026-11-23): overlap helps, mmap hurts

implementer I6's bin_pre (code/impl_pre.diff) adds two ideas, each behind an env switch: K2_PRESCAN_MMAP (read the pre-pass through per-chunk mmap, default ON in that build) and K2_PRESCAN_OVERLAP (start the pre-pass in main() before the database load with 16 workers, default ON). all reads, T=96, K2_BULK=1, 5 interleaved repetitions, wall seconds (data/pre.csv). byte-identity against stock S19 (T=32) at T=96 for the default config: 50 MB, 8 GB, 16 GB, 103 GB all OUT_OK and REP_BYTE_IDENTICAL (data/pre_correct.txt).

| config | 50 MB | 8 GB | 103 GB |
|---|---|---|---|
| K2_PREAD_PRESCAN=0 (no pre-pass: the floor) | 1.77 1.77 1.77 1.77 1.77 | 1.77 1.79 1.75 1.78 1.77 | 7.05 6.92 7.05 7.10 6.92 |
| old pre-pass (MMAP=0 OVERLAP=0) | 2.09 2.10 2.10 2.08 2.10 | 2.08 2.08 2.08 2.04 2.05 | 7.31 7.13 7.46 7.33 7.17 |
| overlap only (MMAP=0) | 1.99 1.99 1.99 1.99 1.99 | 1.97 1.94 1.94 1.94 1.93 | 7.05 7.11 7.22 7.17 7.21 |
| mmap only (OVERLAP=0) | 3.07 3.07 3.01 3.03 3.06 | 3.03 3.04 3.00 3.10 3.03 | 8.29 8.12 8.25 8.27 8.24 |
| mmap + overlap (the implementer's default) | 3.62 3.70 3.65 3.62 3.46 | 3.54 3.50 3.54 3.52 3.56 | 8.42 8.13 8.53 8.56 8.36 |
| mmap without MAP_POPULATE + overlap | 2.22 2.24 2.18 2.15 2.17 | 2.16 2.19 2.13 2.21 2.12 | 7.60 7.36 7.53 7.55 7.27 |
| 32 pre-pass workers (mmap + overlap) | 3.26 3.19 3.26 3.16 3.18 | 3.19 3.18 3.11 3.12 3.26 | 8.22 8.30 8.33 8.43 8.35 |

medians of the pre-pass cost over the floor: old pre-pass +0.33 s (50 MB), +0.31 s (8 GB), +0.26 s (103 GB); overlap only +0.22 s, +0.17 s, +0.12 s.

findings:
- mmap is a net loss, by 1 to 1.5 s: file-backed mappings fault in 4 KB pages (about 3 million faults for 12.5 GB) and the page-table work costs far more than the copy it saves; MAP_POPULATE serialises more of it and is worse; even without populate it is slower than plain pread. the implementer's guess that mmap would help was wrong.
- overlapping the pre-pass with the database load helps (with plain pread), cutting its cost by a third to a half, but it is not hidden on the small databases because the load (0.05 to 0.3 s) is shorter than the pre-pass.
- more workers hurt (32 workers during the load starve the load).

recommended default: K2_PRESCAN_OVERLAP on, K2_PRESCAN_MMAP off, 16 workers. cost vs no pre-pass: about +0.2 s on the small databases (about +10% of a 1.8 s run), +0.12 s (+1.7%) on 103 GB, in exchange for byte-identical behaviour on every malformed input.
