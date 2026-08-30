# Thread / perf sweep — `pod5_8`

Average of the per-thread runs (page cache dropped once before this file, via `posix_fadvise` on the reads and the index — see `scripts/drop_file_cache.py`). Cache Miss Rate = cache-misses/cache-references; LLC Miss Rate = LLC-load-misses/LLC-loads; IPC = instructions/cycles.

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.71 | 14.29 | 2.17 | 2.86 | 28.457 | 28.025 | 28.830 | 1.00x | 2.53 |
| 2 | 85.71 | 14.29 | 2.35 | 3.07 | 15.032 | 14.987 | 15.072 | 1.89x | 2.51 |
| 4 | 85.71 | 14.29 | 2.71 | 3.36 | 8.115 | 7.868 | 8.488 | 3.51x | 2.48 |
| 6 | 85.71 | 14.29 | 3.25 | 3.86 | 7.134 | 7.094 | 7.197 | 3.99x | 2.46 |
| 8 | 85.71 | 14.29 | 3.72 | 4.31 | 6.335 | 6.330 | 6.343 | 4.49x | 2.42 |
| 10 | 85.71 | 14.29 | 4.40 | 4.80 | 6.728 | 6.716 | 6.743 | 4.23x | 2.01 |
| 12 | 85.71 | 14.29 | 4.83 | 5.09 | 7.417 | 7.407 | 7.424 | 3.84x | 1.72 |
| 14 | 85.71 | 14.29 | 5.51 | 5.65 | 8.334 | 8.326 | 8.339 | 3.41x | 1.50 |
| 16 | 85.71 | 14.29 | 6.21 | 6.39 | 9.269 | 9.266 | 9.271 | 3.07x | 1.34 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Existing captures from `result/perf_threadsweep/raw/` — same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 84.06 | 15.94 | 59.38 | 54.25 | 18.928 | 18.385 | 19.885 | 1.00x | 1.38 |
| 2 | 84.06 | 15.94 | 59.69 | 55.13 | 10.028 | 9.788 | 10.487 | 1.89x | 1.34 |
| 4 | 84.06 | 15.94 | 60.15 | 55.61 | 5.454 | 5.335 | 5.648 | 3.47x | 1.35 |
| 6 | 84.06 | 15.94 | 60.46 | 55.80 | 4.306 | 4.222 | 4.455 | 4.40x | 1.40 |
| 8 | 84.06 | 15.94 | 60.83 | 56.03 | 3.532 | 3.470 | 3.644 | 5.36x | 1.41 |
| 10 | 84.06 | 15.94 | 61.02 | 56.54 | 3.143 | 3.100 | 3.224 | 6.02x | 1.31 |
| 12 | 84.06 | 15.94 | 61.15 | 56.85 | 2.837 | 2.801 | 2.908 | 6.67x | 1.23 |
| 14 | 84.06 | 15.94 | 61.10 | 57.55 | 2.602 | 2.562 | 2.670 | 7.27x | 1.17 |
| 16 | 84.06 | 15.94 | 61.25 | 58.92 | 2.398 | 2.365 | 2.457 | 7.89x | 1.13 |
