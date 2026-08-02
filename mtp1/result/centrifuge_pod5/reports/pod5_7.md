# Thread / perf sweep — `pod5_7`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.53 | 14.47 | 2.38 | 3.08 | 28.022 | 27.680 | 28.447 | 1.00x | 2.51 |
| 2 | 85.53 | 14.47 | 2.42 | 3.14 | 14.742 | 14.704 | 14.775 | 1.90x | 2.50 |
| 4 | 85.53 | 14.47 | 2.91 | 3.57 | 8.011 | 7.786 | 8.371 | 3.50x | 2.47 |
| 6 | 85.53 | 14.47 | 3.23 | 3.86 | 7.012 | 6.964 | 7.104 | 4.00x | 2.46 |
| 8 | 85.53 | 14.47 | 3.86 | 4.44 | 6.222 | 6.211 | 6.240 | 4.50x | 2.41 |
| 10 | 85.53 | 14.47 | 4.22 | 4.61 | 6.617 | 6.600 | 6.632 | 4.23x | 2.01 |
| 12 | 85.53 | 14.47 | 4.83 | 5.07 | 7.300 | 7.291 | 7.313 | 3.84x | 1.72 |
| 14 | 85.53 | 14.47 | 5.45 | 5.57 | 8.194 | 8.184 | 8.203 | 3.42x | 1.50 |
| 16 | 85.53 | 14.47 | 6.25 | 6.41 | 9.145 | 9.136 | 9.158 | 3.06x | 1.34 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.88 | 16.12 | 59.43 | 54.40 | 18.631 | 18.127 | 19.611 | 1.00x | 1.38 |
| 2 | 83.88 | 16.12 | 59.53 | 54.89 | 9.892 | 9.652 | 10.362 | 1.88x | 1.34 |
| 4 | 83.88 | 16.12 | 60.04 | 55.55 | 5.351 | 5.242 | 5.548 | 3.48x | 1.35 |
| 6 | 83.88 | 16.12 | 60.14 | 55.33 | 4.191 | 4.102 | 4.317 | 4.45x | 1.40 |
| 8 | 83.88 | 16.12 | 60.88 | 56.22 | 3.503 | 3.434 | 3.629 | 5.32x | 1.41 |
| 10 | 83.88 | 16.12 | 61.06 | 56.62 | 3.114 | 3.052 | 3.226 | 5.98x | 1.31 |
| 12 | 83.88 | 16.12 | 61.08 | 57.05 | 2.923 | 2.765 | 3.230 | 6.37x | 1.24 |
| 14 | 83.88 | 16.12 | 61.23 | 57.97 | 2.572 | 2.541 | 2.632 | 7.24x | 1.17 |
| 16 | 83.88 | 16.12 | 60.90 | 58.21 | 2.372 | 2.341 | 2.432 | 7.85x | 1.13 |
