# Classification report — all 16 pod5 files

`-T 0 -p 16 -g 2`. 1,872,777 reads, 6,036 Mbp. 2026-10-13.
Raw per-file kraken reports: `result/eskape_allpod5_T0/rep/` (64 files).

## Where the +9.28 points come from

48 MB build vs the old 49 MB baseline, in reads:

| taxon | old 49MB | new 48MB | change |
|---|---:|---:|---:|
| P. aeruginosa | 975,003 | 1,068,967 | +93,964 |
| E. coli | 404,484 | 452,405 | +47,921 |
| K. pneumoniae | 179,332 | 192,923 | +13,591 |
| Enterobacter | 7,915 | 3,112 | -4,803 |
| A. baumannii | 0 | 948 | +948 |
| S. aureus | 12 | 16 | +4 |
| E. faecium | 48 | 1 | -47 |
| **sum of species** | | | **+151,578** |
| resolved at higher rank only | | | +21,820 |
| **total extra reads classified** | **1,568,673** | **1,742,071** | **+173,398** |

**173,398 more reads classified; 948 of them spuriously assigned to A. baumannii — a ratio of 183:1.**

## Aggregate, all four databases

| taxon | old 49MB | new 208MB | new 48MB | new 16MB |
|---|---:|---:|---:|---:|
| P. aeruginosa | 975,003 | 1,090,440 | 1,068,967 | 1,000,511 |
| E. coli | 404,484 | 458,702 | 452,405 | 431,481 |
| K. pneumoniae | 179,332 | 204,259 | 192,923 | 181,032 |
| Enterobacter | 7,915 | 4,351 | 3,112 | 2,420 |
| A. baumannii | — | 1,048 | 948 | 629 |
| S. aureus | 12 | 18 | 16 | 13 |
| E. faecium | 48 | 2 | 1 | 3 |
| Enterobacteriaceae (family) | 593,398 | 679,567 | 662,765 | 631,596 |
| Gammaproteobacteria (class) | 1,568,476 | 1,778,704 | 1,741,966 | 1,641,891 |
| **classified** | 1,568,673 | 1,778,777 | 1,742,071 | 1,642,032 |
| **unclassified** | 304,104 | 94,000 | 130,706 | 230,745 |
| **classified %** | **83.76%** | **94.98%** | **93.02%** | **87.68%** |
