# Thread / perf sweep — `pod5_6`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.17 | 14.83 | 1.36 | 1.36 | 36.004 | 35.459 | 36.781 | 1.00x | 2.53 |
| 2 | 85.17 | 14.83 | 1.28 | 1.31 | 18.896 | 18.854 | 18.960 | 1.91x | 2.52 |
| 4 | 85.17 | 14.83 | 1.73 | 1.66 | 10.494 | 10.023 | 10.876 | 3.43x | 2.51 |
| 6 | 85.17 | 14.83 | 2.17 | 2.03 | 8.820 | 8.801 | 8.855 | 4.08x | 2.47 |
| 8 | 85.17 | 14.83 | 2.67 | 2.42 | 7.778 | 7.767 | 7.788 | 4.63x | 2.42 |
| 10 | 85.17 | 14.83 | 2.86 | 2.91 | 8.082 | 8.045 | 8.110 | 4.45x | 2.01 |
| 12 | 85.17 | 14.83 | 2.99 | 3.74 | 8.535 | 8.481 | 8.593 | 4.22x | 1.75 |
| 14 | 85.17 | 14.83 | 3.19 | 4.77 | 9.302 | 9.267 | 9.338 | 3.87x | 1.53 |
| 16 | 85.17 | 14.83 | 3.14 | 5.33 | 10.187 | 10.180 | 10.196 | 3.53x | 1.37 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.50 | 16.50 | 59.06 | 54.13 | 20.036 | 19.507 | 21.010 | 1.00x | 1.39 |
| 2 | 83.50 | 16.50 | 59.73 | 55.21 | 10.389 | 10.339 | 10.459 | 1.93x | 1.37 |
| 4 | 83.50 | 16.50 | 60.21 | 55.44 | 5.654 | 5.603 | 5.718 | 3.54x | 1.37 |
| 6 | 83.50 | 16.50 | 60.60 | 55.88 | 4.531 | 4.446 | 4.657 | 4.42x | 1.42 |
| 8 | 83.50 | 16.50 | 61.00 | 56.22 | 3.711 | 3.651 | 3.816 | 5.40x | 1.43 |
| 10 | 83.50 | 16.50 | 61.43 | 56.94 | 3.323 | 3.282 | 3.398 | 6.03x | 1.32 |
| 12 | 83.50 | 16.50 | 61.39 | 57.17 | 3.004 | 2.957 | 3.086 | 6.67x | 1.24 |
| 14 | 83.50 | 16.50 | 61.49 | 58.01 | 2.755 | 2.724 | 2.815 | 7.27x | 1.18 |
| 16 | 83.50 | 16.50 | 61.40 | 58.80 | 2.547 | 2.515 | 2.597 | 7.87x | 1.13 |
