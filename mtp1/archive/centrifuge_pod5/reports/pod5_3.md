# Thread / perf sweep — `pod5_3`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.42 | 14.58 | 1.20 | 1.17 | 43.480 | 42.878 | 44.642 | 1.00x | 2.48 |
| 2 | 85.42 | 14.58 | 1.17 | 1.16 | 22.989 | 22.910 | 23.117 | 1.89x | 2.44 |
| 4 | 85.42 | 14.58 | 1.56 | 1.47 | 12.665 | 12.480 | 12.799 | 3.43x | 2.43 |
| 6 | 85.42 | 14.58 | 2.43 | 2.25 | 10.833 | 10.771 | 10.877 | 4.01x | 2.37 |
| 8 | 85.42 | 14.58 | 3.43 | 3.16 | 9.552 | 9.398 | 9.630 | 4.55x | 2.30 |
| 10 | 85.42 | 14.58 | 3.44 | 3.79 | 9.673 | 9.620 | 9.752 | 4.50x | 1.94 |
| 12 | 85.42 | 14.58 | 3.99 | 5.67 | 10.078 | 10.024 | 10.112 | 4.31x | 1.69 |
| 14 | 85.42 | 14.58 | 3.49 | 5.31 | 10.839 | 10.730 | 10.951 | 4.01x | 1.50 |
| 16 | 85.42 | 14.58 | 3.42 | 6.56 | 11.641 | 11.617 | 11.668 | 3.74x | 1.36 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.77 | 16.23 | 59.18 | 54.18 | 23.061 | 22.483 | 24.210 | 1.00x | 1.39 |
| 2 | 83.77 | 16.23 | 59.72 | 55.13 | 12.055 | 11.904 | 12.334 | 1.91x | 1.36 |
| 4 | 83.77 | 16.23 | 60.27 | 55.62 | 6.393 | 6.388 | 6.398 | 3.61x | 1.36 |
| 6 | 83.77 | 16.23 | 60.52 | 55.58 | 5.059 | 4.991 | 5.156 | 4.56x | 1.42 |
| 8 | 83.77 | 16.23 | 60.94 | 55.95 | 4.279 | 4.233 | 4.359 | 5.39x | 1.43 |
| 10 | 83.77 | 16.23 | 61.20 | 56.36 | 3.780 | 3.738 | 3.846 | 6.10x | 1.32 |
| 12 | 83.77 | 16.23 | 61.47 | 57.09 | 3.398 | 3.338 | 3.462 | 6.79x | 1.24 |
| 14 | 83.77 | 16.23 | 61.62 | 58.02 | 3.103 | 3.074 | 3.158 | 7.43x | 1.18 |
| 16 | 83.77 | 16.23 | 61.69 | 59.12 | 2.890 | 2.848 | 2.971 | 7.98x | 1.14 |
