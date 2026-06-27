# Pod5 Classification Comparison — 50 MB vs 103 GB DB

ESKAPE pathogen species breakdown per pod5 file. HAC model. 96 Kraken2 runs done 2026-06-22 on Luna.

**Databases compared:**
- **50 MB DB** — `sample_targeted` (6 ESKAPE reference genomes; A. baumannii genome suppressed in NCBI, absent from DB)
- **103 GB DB** — `pluspf_103gb` (Standard RefSeq + protozoa + fungi; gold-standard ceiling)

**Row order:** ESKAPE acronym sequence. E. coli is not an ESKAPE pathogen — counted in "Other classified".  
**Percentages** = % of all reads for that pod5 file (classified + unclassified denominator).  
**Note on pod5 10:** report totals (104,918) match the old reads_hac.fastq reference run — likely mis-run with the single-FASTQ instead of per-pod5 file. Data included as-is.

---

## Aggregate — All 16 Pod5 Files Combined (HAC Model, 2026-06-22)

Total reads processed: **1,872,777**

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (48) | 0.00% (2) |
| *Staphylococcus aureus* | 0.00% (86) | 0.00% (7) |
| *Klebsiella pneumoniae* | 9.73% (182,236) | 9.02% (168,902) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.31% (5,717) |
| *Pseudomonas aeruginosa* | 52.62% (985,446) | 41.61% (779,200) |
| *Enterobacter cloacae* | 0.49% (9,269) | 0.08% (1,423) |
| Other classified | 21.87% (409,636) | 47.82% (895,608) |
| **Unclassified** | **15.28% (286,056)** | **1.17% (21,918)** |

"Other classified" in 50 MB DB is almost entirely E. coli (~22%). In 103 GB DB it is E. coli (~20%) + human reads + environmental bacteria.

---

## Per-Pod5 Tables (HAC Model, 2026-06-22)

---

### Pod5 0 — FBE01990_24778b97_03e50f91_0.pod5
Total reads: 132,074

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (1) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (3) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.41% (12,434) | 8.62% (11,388) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.28% (375) |
| *Pseudomonas aeruginosa* | 53.25% (70,327) | 40.95% (54,082) |
| *Enterobacter cloacae* | 0.45% (589) | 0.07% (99) |
| Other classified | 21.77% (28,757) | 49.11% (64,860) |
| **Unclassified** | **15.12% (19,963)** | **0.96% (1,270)** |

---

### Pod5 1 — FBE01990_24778b97_03e50f91_1.pod5
Total reads: 141,195

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (4) | 0.00% (1) |
| *Staphylococcus aureus* | 0.00% (6) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.49% (13,393) | 8.86% (12,507) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.30% (420) |
| *Pseudomonas aeruginosa* | 53.03% (74,876) | 41.40% (58,457) |
| *Enterobacter cloacae* | 0.47% (669) | 0.07% (104) |
| Other classified | 21.98% (31,037) | 48.41% (68,349) |
| **Unclassified** | **15.02% (21,210)** | **0.96% (1,357)** |

---

### Pod5 2 — FBE01990_24778b97_03e50f91_2.pod5
Total reads: 151,591

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (5) | 0.00% (1) |
| *Staphylococcus aureus* | 0.01% (11) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.67% (14,664) | 8.94% (13,558) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.33% (495) |
| *Pseudomonas aeruginosa* | 52.92% (80,221) | 41.99% (63,652) |
| *Enterobacter cloacae* | 0.48% (732) | 0.07% (110) |
| Other classified | 22.11% (33,515) | 47.61% (72,171) |
| **Unclassified** | **14.80% (22,443)** | **1.06% (1,603)** |

---

### Pod5 3 — FBE01990_24778b97_03e50f91_3.pod5
Total reads: 141,365

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (5) | 0.00% (0) |
| *Staphylococcus aureus* | 0.01% (12) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.79% (13,843) | 9.08% (12,838) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.33% (461) |
| *Pseudomonas aeruginosa* | 52.47% (74,170) | 41.56% (58,752) |
| *Enterobacter cloacae* | 0.52% (735) | 0.09% (123) |
| Other classified | 21.98% (31,077) | 47.79% (67,556) |
| **Unclassified** | **15.23% (21,523)** | **1.16% (1,634)** |

---

### Pod5 4 — FBE01990_24778b97_03e50f91_4.pod5
Total reads: 131,822

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (4) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (4) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.76% (12,865) | 9.12% (12,028) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.29% (385) |
| *Pseudomonas aeruginosa* | 52.41% (69,087) | 42.05% (55,435) |
| *Enterobacter cloacae* | 0.56% (732) | 0.07% (93) |
| Other classified | 22.13% (29,175) | 47.20% (62,215) |
| **Unclassified** | **15.14% (19,955)** | **1.26% (1,665)** |

---

### Pod5 5 — FBE01990_24778b97_03e50f91_5.pod5
Total reads: 130,448

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (6) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (4) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.75% (12,720) | 8.88% (11,583) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.28% (368) |
| *Pseudomonas aeruginosa* | 52.27% (68,186) | 41.85% (54,594) |
| *Enterobacter cloacae* | 0.50% (647) | 0.08% (100) |
| Other classified | 21.77% (28,397) | 47.49% (61,950) |
| **Unclassified** | **15.71% (20,488)** | **1.42% (1,853)** |

---

### Pod5 6 — FBE01990_24778b97_03e50f91_6.pod5
Total reads: 120,965

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (0) | 0.00% (0) |
| *Staphylococcus aureus* | 0.01% (7) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.85% (11,918) | 9.06% (10,955) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.30% (363) |
| *Pseudomonas aeruginosa* | 52.41% (63,395) | 42.10% (50,931) |
| *Enterobacter cloacae* | 0.48% (585) | 0.07% (85) |
| Other classified | 21.78% (26,348) | 47.19% (57,089) |
| **Unclassified** | **15.47% (18,712)** | **1.27% (1,542)** |

---

### Pod5 7 — FBE01990_24778b97_03e50f91_7.pod5
Total reads: 119,216

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (1) | 0.00% (0) |
| *Staphylococcus aureus* | 0.01% (7) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.96% (11,878) | 9.22% (10,989) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.30% (357) |
| *Pseudomonas aeruginosa* | 52.53% (62,621) | 41.88% (49,924) |
| *Enterobacter cloacae* | 0.52% (621) | 0.07% (84) |
| Other classified | 21.87% (26,071) | 47.34% (56,432) |
| **Unclassified** | **15.11% (18,017)** | **1.20% (1,429)** |

---

### Pod5 8 — FBE01990_24778b97_03e50f91_8.pod5
Total reads: 122,764

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.01% (7) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (2) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.84% (12,085) | 9.14% (11,216) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.29% (360) |
| *Pseudomonas aeruginosa* | 52.58% (64,544) | 41.86% (51,391) |
| *Enterobacter cloacae* | 0.49% (607) | 0.09% (109) |
| Other classified | 22.14% (27,182) | 47.37% (58,152) |
| **Unclassified** | **14.94% (18,337)** | **1.25% (1,536)** |

---

### Pod5 9 — FBE01990_24778b97_03e50f91_9.pod5
Total reads: 109,728

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (2) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (4) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.79% (10,738) | 9.06% (9,943) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.29% (323) |
| *Pseudomonas aeruginosa* | 52.85% (57,988) | 41.51% (45,545) |
| *Enterobacter cloacae* | 0.46% (505) | 0.09% (96) |
| Other classified | 21.84% (23,961) | 47.87% (52,525) |
| **Unclassified** | **15.06% (16,530)** | **1.18% (1,295)** |

---

### Pod5 10 — FBE01990_24778b97_03e50f91_10.pod5
Total reads: 104,918 ⚠️ totals match old reads_hac.fastq reference run — likely mis-run with single-FASTQ instead of per-pod5 file

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (5) | 0.00% (0) |
| *Staphylococcus aureus* | 0.01% (7) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.92% (10,411) | 9.22% (9,677) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.33% (341) |
| *Pseudomonas aeruginosa* | 52.50% (55,077) | 41.58% (43,630) |
| *Enterobacter cloacae* | 0.48% (503) | 0.07% (76) |
| Other classified | 21.89% (22,970) | 47.66% (50,002) |
| **Unclassified** | **15.20% (15,945)** | **1.14% (1,191)** |

---

### Pod5 11 — FBE01990_24778b97_03e50f91_11.pod5
Total reads: 123,458

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (4) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (3) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.66% (11,929) | 8.99% (11,093) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.31% (383) |
| *Pseudomonas aeruginosa* | 52.42% (64,712) | 41.49% (51,228) |
| *Enterobacter cloacae* | 0.47% (577) | 0.07% (84) |
| Other classified | 21.67% (26,758) | 47.73% (58,921) |
| **Unclassified** | **15.77% (19,475)** | **1.42% (1,749)** |

---

### Pod5 12 — FBE01990_24778b97_03e50f91_12.pod5
Total reads: 109,020

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (0) | 0.00% (0) |
| *Staphylococcus aureus* | 0.01% (8) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.86% (10,746) | 9.09% (9,914) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.32% (351) |
| *Pseudomonas aeruginosa* | 52.22% (56,927) | 41.26% (44,979) |
| *Enterobacter cloacae* | 0.53% (574) | 0.07% (77) |
| Other classified | 21.79% (23,750) | 48.07% (52,405) |
| **Unclassified** | **15.61% (17,015)** | **1.19% (1,294)** |

---

### Pod5 13 — FBE01990_24778b97_03e50f91_13.pod5
Total reads: 106,781

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (0) | 0.00% (0) |
| *Staphylococcus aureus* | 0.01% (6) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.65% (10,302) | 9.04% (9,655) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.33% (353) |
| *Pseudomonas aeruginosa* | 52.87% (56,459) | 41.68% (44,502) |
| *Enterobacter cloacae* | 0.51% (547) | 0.08% (82) |
| Other classified | 21.69% (23,163) | 48.00% (51,256) |
| **Unclassified** | **15.27% (16,304)** | **0.87% (933)** |

---

### Pod5 14 — FBE01990_24778b97_03e50f91_14.pod5
Total reads: 97,054

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (3) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (2) | 0.00% (1) |
| *Klebsiella pneumoniae* | 9.58% (9,301) | 8.98% (8,715) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.29% (280) |
| *Pseudomonas aeruginosa* | 52.41% (50,863) | 40.66% (39,467) |
| *Enterobacter cloacae* | 0.50% (487) | 0.08% (79) |
| Other classified | 21.63% (20,992) | 48.74% (47,309) |
| **Unclassified** | **15.87% (15,406)** | **1.24% (1,203)** |

---

### Pod5 15 — FBE01990_24778b97_03e50f91_15.pod5
Total reads: 30,378 (last chunk — pore activity trailing off, expected low count)

| Species | 50 MB DB | 103 GB DB |
|---------|----------|-----------|
| *Enterococcus faecium* | 0.00% (1) | 0.00% (0) |
| *Staphylococcus aureus* | 0.00% (0) | 0.00% (0) |
| *Klebsiella pneumoniae* | 9.91% (3,009) | 9.36% (2,843) |
| *Acinetobacter baumannii* | 0.00% (0) — absent from DB | 0.34% (102) |
| *Pseudomonas aeruginosa* | 52.65% (15,993) | 41.58% (12,631) |
| *Enterobacter cloacae* | 0.52% (159) | 0.07% (22) |
| Other classified | 21.34% (6,483) | 47.45% (14,416) |
| **Unclassified** | **15.58% (4,733)** | **1.20% (364)** |

---

## Notes

- **A. baumannii** is always 0% in the 50 MB DB — the reference genome was suppressed on NCBI and could not be included at build time. Present at 0.28–0.34% per pod5 in the 103 GB DB (aggregate: 0.31%, 5,717 reads).
- **E. faecium / S. aureus** are effectively absent from this AIIMS ICU sample — single-digit read counts per pod5 in both DBs. The infection is dominated by P. aeruginosa, K. pneumoniae, and E. coli (non-ESKAPE).
- **E. coli** (~22% of reads) is the main driver of "Other classified" in the 50 MB DB — it is included in the sample_targeted reference set but is not an ESKAPE pathogen.
- **"Other classified" in 103 GB DB** (~48%) is E. coli (~20%) + human reads + environmental bacteria that the 50 MB DB cannot see — these reads go to Unclassified in the small DB instead.
- **Species proportions are highly stable** across all 16 pod5 files: P. aeruginosa holds at 52–53% (50 MB) / 40–42% (103 GB), K. pneumoniae at 9.4–10.0% / 8.6–9.4%, Unclassified at 14.8–15.9% / 0.87–1.42%. No temporal drift in sample composition.
- **Pod5 10** totals (104,918) match the old reads_hac.fastq reference run — likely mis-run with single-FASTQ instead of per-pod5 file. Flag for re-run if per-pod5 breakdown of file _10 is needed.
- **Verification method:** totals checked for sample_targeted/pluspf consistency in each directory (all 16 matched); P. aeruginosa counts spot-checked against raw report files for dirs 0, 7, 15.
