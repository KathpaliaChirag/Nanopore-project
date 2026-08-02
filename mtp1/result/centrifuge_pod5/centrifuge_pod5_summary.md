# Centrifuge perf thread-sweep summary — averaged across all pod5 files

Each cell is the mean over files of the per-file 3-run average. Speedup is recomputed from the mean times.

Files: 16/16 · index `databases/centrifuge_eskape/cf_base` (6 ESKAPE genomes, 17 seqs, 28.06 Mbp, 21 MB on disk).

> **Classified% is not an accuracy number.** These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Treat every Classified% here as **unvalidated — threshold/rank mismatch, not directly comparable.**

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.30 | 14.70 | 2.15 | 2.71 | 28.237 | 27.932 | 28.663 | 1.00x | 2.51 |
| 2 | 85.30 | 14.70 | 2.15 | 2.74 | 14.887 | 14.849 | 14.930 | 1.90x | 2.50 |
| 4 | 85.30 | 14.70 | 2.63 | 3.15 | 8.154 | 7.921 | 8.388 | 3.46x | 2.47 |
| 6 | 85.30 | 14.70 | 3.09 | 3.55 | 7.057 | 7.001 | 7.125 | 4.00x | 2.45 |
| 8 | 85.30 | 14.70 | 3.55 | 3.96 | 6.257 | 6.227 | 6.280 | 4.51x | 2.40 |
| 10 | 85.30 | 14.70 | 4.16 | 4.49 | 6.595 | 6.573 | 6.619 | 4.28x | 2.00 |
| 12 | 85.30 | 14.70 | 4.66 | 5.07 | 7.170 | 7.154 | 7.189 | 3.94x | 1.71 |
| 14 | 85.30 | 14.70 | 5.09 | 5.56 | 7.972 | 7.950 | 7.995 | 3.54x | 1.50 |
| 16 | 85.30 | 14.70 | 5.59 | 6.23 | 8.823 | 8.813 | 8.835 | 3.20x | 1.35 |

## Kraken2 32-bit (`eskape_32bit_stock`)

| Threads | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | Time (s) | Min (s) | Max (s) | Speedup vs 1T | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.73 | 16.27 | 59.42 | 54.39 | 17.830 | 17.346 | 18.746 | 1.00x | 1.38 |
| 2 | 83.73 | 16.27 | 59.54 | 54.91 | 9.435 | 9.229 | 9.823 | 1.89x | 1.35 |
| 4 | 83.73 | 16.27 | 60.06 | 55.51 | 5.082 | 4.984 | 5.252 | 3.51x | 1.34 |
| 6 | 83.73 | 16.27 | 60.40 | 55.77 | 3.961 | 3.888 | 4.081 | 4.50x | 1.39 |
| 8 | 83.73 | 16.27 | 60.70 | 56.01 | 3.252 | 3.040 | 3.438 | 5.48x | 1.40 |
| 10 | 83.73 | 16.27 | 60.99 | 56.54 | 2.917 | 2.871 | 2.992 | 6.11x | 1.29 |
| 12 | 83.73 | 16.27 | 61.17 | 57.22 | 2.626 | 2.565 | 2.709 | 6.79x | 1.21 |
| 14 | 83.73 | 16.27 | 61.16 | 57.87 | 2.422 | 2.371 | 2.491 | 7.36x | 1.16 |
| 16 | 83.73 | 16.27 | 60.99 | 58.58 | 2.253 | 2.221 | 2.309 | 7.92x | 1.12 |

## Head-to-head (Centrifuge ÷ Kraken2, mean across files)

| Threads | Time ratio | LLC miss ratio | IPC ratio |
|---:|---:|---:|---:|
| 1 | 1.58x | 0.05x | 1.82x |
| 2 | 1.58x | 0.05x | 1.85x |
| 4 | 1.60x | 0.06x | 1.84x |
| 6 | 1.78x | 0.06x | 1.77x |
| 8 | 1.92x | 0.07x | 1.71x |
| 10 | 2.26x | 0.08x | 1.54x |
| 12 | 2.73x | 0.09x | 1.41x |
| 14 | 3.29x | 0.10x | 1.29x |
| 16 | 3.92x | 0.11x | 1.20x |
