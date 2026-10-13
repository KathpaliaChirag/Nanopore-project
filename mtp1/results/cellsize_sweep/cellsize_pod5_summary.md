# Cell-width comparison on pod5 reads (24-bit & 16-bit vs 32-bit stock)

Per-file classification of all 16 `perpod5/*.fastq` against three cell-width DBs at `-T 0` and `-T 0.05`. Baseline = `eskape_32bit_stock`.

## Aggregate roll-up (all 16 files)

| DB | -T | classified % | Δ vs 32-bit | classified / total |
|---|---|---:|---:|---|
| eskape_32bit_stock | 0 | 83.76 | — | 1,568,673 / 1,872,777 |
| eskape_24bit | 0 | 83.78 | +0.02 | 1,569,044 / 1,872,777 |
| eskape_16bit | 0 | 90.96 | +7.20 | 1,703,502 / 1,872,777 |
| | | | | |
| eskape_32bit_stock | 0.05 | 79.83 | — | 1,495,001 / 1,872,777 |
| eskape_24bit | 0.05 | 79.83 | +0.00 | 1,495,015 / 1,872,777 |
| eskape_16bit | 0.05 | 80.10 | +0.27 | 1,500,034 / 1,872,777 |
| | | | | |

## Gram-positive false-positive indicators (clade reads, summed over 16 files)

Reads assigned to Gram-positive DB taxa in a Gram-negative-dominated sample — these should stay flat unless collisions inflate them.

| DB | -T | S. aureus (1280) | E. faecium (1352) |
|---|---|---:|---:|
| eskape_32bit_stock | 0 | 12 | 48 |
| eskape_24bit | 0 | 31 | 102 |
| eskape_16bit | 0 | 7,071 | 10,014 |
| | | | |
| eskape_32bit_stock | 0.05 | 10 | 47 |
| eskape_24bit | 0.05 | 10 | 47 |
| eskape_16bit | 0.05 | 13 | 47 |
| | | | |

## Build-time occupied cells (collision signal)

| DB | occupied cells |
|---|---:|
| eskape_32bit_stock | 8903388 |
| eskape_24bit | 8903335 |
| eskape_16bit | 8891740 |

## Per-file classified %

### -T 0

| file | eskape_32bit_stock | eskape_24bit | eskape_16bit |
|---|---:|---:|---:|
| pod5_0 | 83.97 | 84.00 | 90.60 |
| pod5_1 | 84.05 | 84.07 | 90.88 |
| pod5_2 | 84.26 | 84.27 | 91.29 |
| pod5_3 | 83.77 | 83.80 | 91.10 |
| pod5_4 | 83.84 | 83.86 | 91.15 |
| pod5_5 | 83.30 | 83.31 | 90.81 |
| pod5_6 | 83.50 | 83.52 | 91.15 |
| pod5_7 | 83.88 | 83.90 | 91.27 |
| pod5_8 | 84.06 | 84.08 | 91.18 |
| pod5_9 | 84.00 | 84.03 | 91.12 |
| pod5_10 | 83.85 | 83.88 | 91.26 |
| pod5_11 | 83.18 | 83.20 | 90.52 |
| pod5_12 | 83.49 | 83.50 | 90.75 |
| pod5_13 | 83.87 | 83.89 | 90.89 |
| pod5_14 | 83.25 | 83.26 | 90.30 |
| pod5_15 | 83.39 | 83.42 | 90.93 |

### -T 0.05

| file | eskape_32bit_stock | eskape_24bit | eskape_16bit |
|---|---:|---:|---:|
| pod5_0 | 80.56 | 80.56 | 80.79 |
| pod5_1 | 80.46 | 80.46 | 80.70 |
| pod5_2 | 80.61 | 80.61 | 80.83 |
| pod5_3 | 79.53 | 79.53 | 79.83 |
| pod5_4 | 79.40 | 79.40 | 79.70 |
| pod5_5 | 78.98 | 78.98 | 79.28 |
| pod5_6 | 79.16 | 79.17 | 79.45 |
| pod5_7 | 79.65 | 79.65 | 79.96 |
| pod5_8 | 79.65 | 79.65 | 79.90 |
| pod5_9 | 80.36 | 80.36 | 80.61 |
| pod5_10 | 80.28 | 80.29 | 80.55 |
| pod5_11 | 79.14 | 79.14 | 79.41 |
| pod5_12 | 79.58 | 79.58 | 79.87 |
| pod5_13 | 80.31 | 80.31 | 80.57 |
| pod5_14 | 79.65 | 79.65 | 79.91 |
| pod5_15 | 79.89 | 79.89 | 80.17 |
