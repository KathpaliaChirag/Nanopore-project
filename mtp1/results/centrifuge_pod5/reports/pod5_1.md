# Thread / perf sweep — `pod5_1`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.52 | 14.48 | 2.25 | 2.93 | 32.497 | 32.298 | 32.820 | 1.00x | 2.53 |
| 2 | 85.52 | 14.48 | 2.19 | 2.91 | 17.083 | 17.050 | 17.105 | 1.90x | 2.52 |
| 4 | 85.52 | 14.48 | 2.78 | 3.43 | 9.266 | 8.990 | 9.655 | 3.51x | 2.49 |
| 6 | 85.52 | 14.48 | 3.30 | 3.89 | 8.113 | 8.087 | 8.143 | 4.01x | 2.47 |
| 8 | 85.52 | 14.48 | 3.87 | 4.41 | 7.231 | 7.192 | 7.252 | 4.49x | 2.42 |
| 10 | 85.52 | 14.48 | 4.22 | 4.62 | 7.644 | 7.633 | 7.652 | 4.25x | 2.02 |
| 12 | 85.52 | 14.48 | 4.76 | 5.02 | 8.384 | 8.372 | 8.404 | 3.88x | 1.73 |
| 14 | 85.52 | 14.48 | 5.44 | 5.62 | 9.402 | 9.384 | 9.412 | 3.46x | 1.51 |
| 16 | 85.52 | 14.48 | 6.19 | 6.37 | 10.475 | 10.467 | 10.481 | 3.10x | 1.35 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 84.05 | 15.95 | 59.09 | 54.10 | 21.297 | 20.662 | 22.423 | 1.00x | 1.38 |
| 2 | 84.05 | 15.95 | 59.38 | 54.60 | 11.282 | 11.008 | 11.800 | 1.89x | 1.35 |
| 4 | 84.05 | 15.95 | 60.21 | 55.68 | 5.883 | 5.755 | 6.084 | 3.62x | 1.32 |
| 6 | 84.05 | 15.95 | 60.82 | 56.17 | 4.295 | 4.222 | 4.345 | 4.96x | 1.31 |
| 8 | 84.05 | 15.95 | 60.85 | 56.19 | 3.907 | 3.646 | 4.183 | 5.45x | 1.39 |
| 10 | 84.05 | 15.95 | 61.47 | 57.04 | 3.059 | 3.027 | 3.104 | 6.96x | 1.23 |
| 12 | 84.05 | 15.95 | 61.76 | 57.75 | 2.699 | 2.686 | 2.722 | 7.89x | 1.15 |
| 14 | 84.05 | 15.95 | 61.55 | 58.33 | 2.765 | 2.476 | 2.984 | 7.70x | 1.13 |
| 16 | 84.05 | 15.95 | 61.33 | 59.12 | 2.640 | 2.598 | 2.716 | 8.07x | 1.11 |
