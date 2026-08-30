# Thread / perf sweep — `pod5_4`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.51 | 14.49 | 2.03 | 2.72 | 31.508 | 31.076 | 31.957 | 1.00x | 2.53 |
| 2 | 85.51 | 14.49 | 2.47 | 3.20 | 16.678 | 16.639 | 16.699 | 1.89x | 2.50 |
| 4 | 85.51 | 14.49 | 3.06 | 3.73 | 9.298 | 8.811 | 9.657 | 3.39x | 2.48 |
| 6 | 85.51 | 14.49 | 3.44 | 4.02 | 7.955 | 7.883 | 7.999 | 3.96x | 2.47 |
| 8 | 85.51 | 14.49 | 3.83 | 4.42 | 7.044 | 7.005 | 7.075 | 4.47x | 2.41 |
| 10 | 85.51 | 14.49 | 4.69 | 5.12 | 7.486 | 7.467 | 7.517 | 4.21x | 2.00 |
| 12 | 85.51 | 14.49 | 4.91 | 5.16 | 8.218 | 8.215 | 8.222 | 3.83x | 1.72 |
| 14 | 85.51 | 14.49 | 5.46 | 5.69 | 9.238 | 9.231 | 9.250 | 3.41x | 1.50 |
| 16 | 85.51 | 14.49 | 6.09 | 6.30 | 10.292 | 10.282 | 10.307 | 3.06x | 1.34 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.84 | 16.16 | 59.44 | 54.30 | 20.936 | 20.362 | 21.992 | 1.00x | 1.38 |
| 2 | 83.84 | 16.16 | 59.51 | 54.76 | 11.059 | 10.804 | 11.543 | 1.89x | 1.34 |
| 4 | 83.84 | 16.16 | 60.16 | 55.57 | 5.945 | 5.826 | 6.175 | 3.52x | 1.34 |
| 6 | 83.84 | 16.16 | 60.53 | 55.89 | 4.697 | 4.605 | 4.871 | 4.46x | 1.39 |
| 8 | 83.84 | 16.16 | 60.73 | 56.21 | 2.794 | 0.436 | 4.094 | 7.49x | 1.39 |
| 10 | 83.84 | 16.16 | 61.33 | 56.91 | 3.456 | 3.424 | 3.510 | 6.06x | 1.31 |
| 12 | 83.84 | 16.16 | 61.44 | 57.48 | 3.092 | 3.057 | 3.158 | 6.77x | 1.23 |
| 14 | 83.84 | 16.16 | 61.59 | 58.32 | 2.834 | 2.797 | 2.893 | 7.39x | 1.17 |
| 16 | 83.84 | 16.16 | 61.35 | 58.92 | 2.625 | 2.593 | 2.683 | 7.98x | 1.13 |
