# Thread / perf sweep — `pod5_5`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 84.97 | 15.03 | 2.59 | 3.34 | 31.303 | 30.954 | 31.871 | 1.00x | 2.51 |
| 2 | 84.97 | 15.03 | 2.43 | 3.15 | 16.400 | 16.358 | 16.460 | 1.91x | 2.51 |
| 4 | 84.97 | 15.03 | 3.01 | 3.72 | 9.096 | 8.643 | 9.378 | 3.44x | 2.49 |
| 6 | 84.97 | 15.03 | 3.36 | 3.95 | 7.790 | 7.709 | 7.888 | 4.02x | 2.47 |
| 8 | 84.97 | 15.03 | 3.59 | 4.19 | 6.892 | 6.885 | 6.896 | 4.54x | 2.43 |
| 10 | 84.97 | 15.03 | 4.14 | 4.54 | 7.308 | 7.287 | 7.319 | 4.28x | 2.02 |
| 12 | 84.97 | 15.03 | 5.05 | 5.32 | 8.059 | 8.052 | 8.067 | 3.88x | 1.72 |
| 14 | 84.97 | 15.03 | 5.56 | 5.74 | 9.036 | 9.034 | 9.038 | 3.46x | 1.50 |
| 16 | 84.97 | 15.03 | 6.08 | 6.29 | 10.066 | 10.059 | 10.075 | 3.11x | 1.35 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.30 | 16.70 | 59.51 | 54.55 | 20.482 | 19.905 | 21.579 | 1.00x | 1.38 |
| 2 | 83.30 | 16.70 | 59.56 | 54.97 | 10.831 | 10.576 | 11.327 | 1.89x | 1.35 |
| 4 | 83.30 | 16.70 | 60.20 | 55.73 | 5.904 | 5.764 | 6.159 | 3.47x | 1.34 |
| 6 | 83.30 | 16.70 | 60.36 | 55.74 | 4.587 | 4.519 | 4.698 | 4.47x | 1.40 |
| 8 | 83.30 | 16.70 | 60.63 | 55.76 | 3.868 | 3.792 | 4.007 | 5.30x | 1.41 |
| 10 | 83.30 | 16.70 | 61.14 | 56.72 | 3.380 | 3.324 | 3.458 | 6.06x | 1.31 |
| 12 | 83.30 | 16.70 | 61.33 | 57.34 | 3.049 | 3.012 | 3.117 | 6.72x | 1.23 |
| 14 | 83.30 | 16.70 | 61.31 | 57.75 | 2.795 | 2.763 | 2.856 | 7.33x | 1.17 |
| 16 | 83.30 | 16.70 | 61.08 | 58.23 | 2.601 | 2.563 | 2.666 | 7.87x | 1.13 |
