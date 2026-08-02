# Thread / perf sweep — `pod5_0`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.46 | 14.54 | 2.49 | 3.21 | 29.052 | 28.675 | 29.649 | 1.00x | 2.52 |
| 2 | 85.46 | 14.54 | 2.35 | 3.08 | 15.282 | 15.257 | 15.326 | 1.90x | 2.51 |
| 4 | 85.46 | 14.54 | 2.90 | 3.54 | 8.211 | 8.018 | 8.480 | 3.54x | 2.48 |
| 6 | 85.46 | 14.54 | 3.33 | 3.91 | 7.252 | 7.223 | 7.280 | 4.01x | 2.47 |
| 8 | 85.46 | 14.54 | 3.55 | 4.11 | 6.443 | 6.431 | 6.458 | 4.51x | 2.42 |
| 10 | 85.46 | 14.54 | 4.67 | 5.09 | 6.919 | 6.855 | 6.956 | 4.20x | 1.99 |
| 12 | 85.46 | 14.54 | 4.74 | 4.99 | 7.537 | 7.528 | 7.545 | 3.85x | 1.72 |
| 14 | 85.46 | 14.54 | 5.49 | 5.62 | 8.428 | 8.420 | 8.433 | 3.45x | 1.50 |
| 16 | 85.46 | 14.54 | 6.19 | 6.37 | 9.381 | 9.365 | 9.397 | 3.10x | 1.35 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.97 | 16.03 | 59.26 | 54.38 | 19.032 | 18.491 | 20.000 | 1.00x | 1.38 |
| 2 | 83.97 | 16.03 | 59.37 | 54.80 | 10.055 | 9.816 | 10.503 | 1.89x | 1.35 |
| 4 | 83.97 | 16.03 | 60.03 | 55.45 | 5.245 | 5.123 | 5.466 | 3.63x | 1.32 |
| 6 | 83.97 | 16.03 | 60.59 | 55.66 | 3.822 | 3.742 | 3.967 | 4.98x | 1.30 |
| 8 | 83.97 | 16.03 | 61.24 | 56.55 | 3.120 | 3.070 | 3.200 | 6.10x | 1.32 |
| 10 | 83.97 | 16.03 | 61.48 | 56.94 | 2.698 | 2.675 | 2.733 | 7.05x | 1.22 |
| 12 | 83.97 | 16.03 | 61.81 | 58.10 | 2.378 | 2.355 | 2.423 | 8.00x | 1.14 |
| 14 | 83.97 | 16.03 | 61.70 | 58.36 | 2.180 | 2.159 | 2.214 | 8.73x | 1.09 |
| 16 | 83.97 | 16.03 | 61.46 | 59.10 | 1.996 | 1.972 | 2.032 | 9.53x | 1.05 |
