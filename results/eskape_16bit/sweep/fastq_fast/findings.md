# ESKAPE cell-width sweep — `fastq_fast` (per-pod5 fast basecalls)

**Date:** 2026-06-29 · 16 per-pod5 fast-model fastq from Luna (`results/fast1/*.fastq`, ~12 GB),
classified as one dataset against `data/database/eskape_{16,24,32}bit/` at `-T 0` and `-T 0.05`.
**Processed: 1,872,777 reads** (≈18× the earlier 104 k `reads_fast` set — same pattern at scale).

---

## 1. Per-pathogen detection (% of 1,872,777 reads)

Each ESKAPE species as a fraction of all reads — the detection answer for this sample.

### `-T 0` (no threshold)
| species (taxid) | 32-bit | 24-bit | 16-bit |
|---|---:|---:|---:|
| *P. aeruginosa* (287) | 52.54 % | 52.62 % | **56.69 %** |
| *K. pneumoniae* (573) | 13.90 % | 13.94 % | **16.21 %** |
| *E. cloacae* (550) | 6.20 % | 6.28 % | **10.40 %** |
| *A. baumannii* (470) | 0.09 % | 0.11 % | **2.15 %** |
| *S. aureus* (1280) | 0.05 % | 0.07 % | **1.27 %** |
| *E. faecium* (1352) | 0.00 % | 0.04 % | **1.14 %** |
| **classified** | 73.09 % | 73.38 % | **89.96 %** |
| unclassified | 26.91 % | 26.62 % | 10.04 % |

### `-T 0.05` (confidence filter — converged)
| species (taxid) | 32-bit | 24-bit | 16-bit |
|---|---:|---:|---:|
| *P. aeruginosa* (287) | 49.71 % | 49.71 % | 49.74 % |
| *K. pneumoniae* (573) | 9.62 % | 9.62 % | 9.63 % |
| *E. cloacae* (550) | 0.87 % | 0.87 % | 0.88 % |
| *A. baumannii* (470) | 0.05 % | 0.05 % | 0.05 % |
| *S. aureus* (1280) | 0.04 % | 0.04 % | 0.04 % |
| *E. faecium* (1352) | 0.00 % | 0.00 % | 0.00 % |
| **classified** | 61.21 % | 61.21 % | 61.53 % |
| unclassified | 38.79 % | 38.79 % | 38.47 % |

**Detection breakdown (32-bit, `-T 0.05` = the real answer):** *P. aeruginosa* **49.71 %** ·
*K. pneumoniae* **9.62 %** · *E. cloacae* 0.87 % · *A. baumannii*/*S. aureus*/*E. faecium* ~0 %.
Sample is dominated by P. aeruginosa + K. pneumoniae + E. cloacae; the other three are trace.

---

## 2. Classified % and deviation from 32-bit

| cell | `-T 0` | Δ vs 32 | `-T 0.05` | Δ vs 32 |
|---|---:|---:|---:|---:|
| 32-bit | 73.09 % | — | 61.21 % | — |
| 24-bit | 73.38 % | **+0.29** | 61.21 % | **+0.00** |
| 16-bit | 89.96 % | **+16.87** | 61.53 % | **+0.32** |

In reads (of 1,872,777): 24-bit +5,431 @T0 / **+22 @T0.05**;
16-bit **+315,937 @T0** (false positives) / +5,993 @T0.05.

---

## 3. Per-species counts, `-T 0` — the 16-bit FP signature

| species (taxid) | 32-bit (truth) | 24-bit | 16-bit | 16-bit inflation |
|---|---:|---:|---:|---:|
| *P. aeruginosa* (287) | 983,897 | 985,406 | 1,061,599 | ×1.08 |
| *K. pneumoniae* (573) | 260,236 | 261,068 | 303,565 | ×1.17 |
| *E. cloacae* (550) | 116,195 | 117,672 | 194,795 | ×1.68 |
| *A. baumannii* (470) | 1,617 | 2,078 | 40,301 | **×25** |
| *S. aureus* (1280) | 902 | 1,280 | 23,877 | **×26** |
| *E. faecium* (1352) | 3 | 745 | 21,355 | **×7,118** |
| unclassified (0) | 504,031 | 498,504 | 187,981 | −316,050 |

- All 316 k of the 16-bit "extra" reads come straight out of unclassified (−316,050 ≈ +315,937).
- **Cross-phylum proof:** *E. faecium* ×7,118 and *S. aureus* ×26 (Gram-positive, share no 31-mers
  with the Gram-negative Proteobacteria that dominate this sample) — only possible as hash
  collisions. 24-bit barely moves them (3→745, 902→1,280).

---

## 4. Per-species counts, `-T 0.05` — converged

| species (taxid) | 32-bit | 24-bit | 16-bit |
|---|---:|---:|---:|
| *P. aeruginosa* (287) | 931,042 | 931,042 | 931,516 |
| *K. pneumoniae* (573) | 180,075 | 180,076 | 180,352 |
| *E. cloacae* (550) | 16,279 | 16,279 | 16,548 |
| *A. baumannii* (470) | 922 | 922 | 935 |
| *S. aureus* (1280) | 787 | 787 | 803 |
| *E. faecium* (1352) | 2 | 2 | 12 |

24-bit is **identical** to 32-bit; 16-bit differs by ≤474 reads/species (<0.05 %).

---

## 5. Verdict (consistent with the 104 k sweep, now at 1.87 M reads)

- **24-bit = drop-in for 32-bit:** +0.29 % @T0, **+22 reads @T0.05** — no threshold needed, −25 % size.
- **16-bit needs `-T ≥ 0.05`:** +16.87 % FP @T0 (unusable) → +0.32 % @T0.05 — species-equivalent, −50 % size.

Artifacts in this folder: `report_{16,24,32}bit_T{0,0.05}.txt`, `stderr_*.txt`, `summary.tsv`, `run.log`.
