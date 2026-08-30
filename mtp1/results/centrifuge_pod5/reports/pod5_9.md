# Thread / perf sweep — `pod5_9`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.51 | 14.49 | 2.55 | 3.22 | 24.358 | 24.231 | 24.569 | 1.00x | 2.49 |
| 2 | 85.51 | 14.49 | 2.36 | 3.11 | 12.819 | 12.802 | 12.849 | 1.90x | 2.48 |
| 4 | 85.51 | 14.49 | 2.45 | 3.12 | 7.133 | 6.761 | 7.478 | 3.41x | 2.48 |
| 6 | 85.51 | 14.49 | 3.14 | 3.75 | 6.100 | 6.069 | 6.139 | 3.99x | 2.45 |
| 8 | 85.51 | 14.49 | 3.51 | 4.09 | 5.406 | 5.398 | 5.410 | 4.51x | 2.40 |
| 10 | 85.51 | 14.49 | 4.36 | 4.76 | 5.768 | 5.764 | 5.773 | 4.22x | 1.99 |
| 12 | 85.51 | 14.49 | 4.93 | 5.20 | 6.381 | 6.370 | 6.390 | 3.82x | 1.70 |
| 14 | 85.51 | 14.49 | 5.42 | 5.62 | 7.171 | 7.149 | 7.191 | 3.40x | 1.49 |
| 16 | 85.51 | 14.49 | 5.91 | 6.07 | 8.008 | 7.999 | 8.012 | 3.04x | 1.33 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 84.00 | 16.00 | 59.60 | 54.45 | 16.295 | 15.867 | 17.144 | 1.00x | 1.38 |
| 2 | 84.00 | 16.00 | 59.62 | 54.99 | 8.672 | 8.464 | 9.060 | 1.88x | 1.34 |
| 4 | 84.00 | 16.00 | 59.75 | 55.02 | 4.767 | 4.674 | 4.945 | 3.42x | 1.35 |
| 6 | 84.00 | 16.00 | 60.37 | 55.87 | 3.755 | 3.669 | 3.880 | 4.34x | 1.40 |
| 8 | 84.00 | 16.00 | 60.60 | 55.88 | 3.080 | 3.027 | 3.183 | 5.29x | 1.41 |
| 10 | 84.00 | 16.00 | 60.97 | 56.66 | 2.728 | 2.692 | 2.800 | 5.97x | 1.31 |
| 12 | 84.00 | 16.00 | 61.09 | 57.36 | 2.485 | 2.450 | 2.542 | 6.56x | 1.23 |
| 14 | 84.00 | 16.00 | 61.07 | 57.92 | 2.284 | 2.243 | 2.343 | 7.13x | 1.18 |
| 16 | 84.00 | 16.00 | 60.81 | 58.22 | 2.100 | 2.071 | 2.156 | 7.76x | 1.13 |
