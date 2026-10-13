# Thread / perf sweep — `pod5_2`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.76 | 14.24 | 2.57 | 3.25 | 36.189 | 35.912 | 36.586 | 1.00x | 2.52 |
| 2 | 85.76 | 14.24 | 2.52 | 3.24 | 19.050 | 18.998 | 19.101 | 1.90x | 2.50 |
| 4 | 85.76 | 14.24 | 2.85 | 3.49 | 10.688 | 10.654 | 10.740 | 3.39x | 2.49 |
| 6 | 85.76 | 14.24 | 3.06 | 3.66 | 8.938 | 8.916 | 8.970 | 4.05x | 2.48 |
| 8 | 85.76 | 14.24 | 3.51 | 4.05 | 7.989 | 7.982 | 8.000 | 4.53x | 2.43 |
| 10 | 85.76 | 14.24 | 4.48 | 4.84 | 8.488 | 8.477 | 8.503 | 4.26x | 2.02 |
| 12 | 85.76 | 14.24 | 4.79 | 4.99 | 9.319 | 9.311 | 9.324 | 3.88x | 1.73 |
| 14 | 85.76 | 14.24 | 5.38 | 5.49 | 10.463 | 10.432 | 10.480 | 3.46x | 1.51 |
| 16 | 85.76 | 14.24 | 5.92 | 6.07 | 11.628 | 11.609 | 11.656 | 3.11x | 1.35 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 84.26 | 15.74 | 59.43 | 54.53 | 23.611 | 22.969 | 24.808 | 1.00x | 1.39 |
| 2 | 84.26 | 15.74 | 59.59 | 55.01 | 12.517 | 12.214 | 13.089 | 1.89x | 1.35 |
| 4 | 84.26 | 15.74 | 60.02 | 55.32 | 6.517 | 6.361 | 6.778 | 3.62x | 1.32 |
| 6 | 84.26 | 15.74 | 60.54 | 56.00 | 5.223 | 5.121 | 5.414 | 4.52x | 1.39 |
| 8 | 84.26 | 15.74 | 60.84 | 56.25 | 4.377 | 4.293 | 4.533 | 5.39x | 1.42 |
| 10 | 84.26 | 15.74 | 60.99 | 56.38 | 3.922 | 3.801 | 4.136 | 6.02x | 1.30 |
| 12 | 84.26 | 15.74 | 61.60 | 57.80 | 3.358 | 3.051 | 3.577 | 7.03x | 1.20 |
| 14 | 84.26 | 15.74 | 61.60 | 58.37 | 3.144 | 3.110 | 3.209 | 7.51x | 1.17 |
| 16 | 84.26 | 15.74 | 61.44 | 59.23 | 2.920 | 2.888 | 2.982 | 8.09x | 1.13 |
