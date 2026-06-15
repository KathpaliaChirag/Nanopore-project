# AccuracyChase

Goal: establish a gold-standard classification accuracy for each read model (reads_fast, reads_hac, reads_sup) using the largest practical Kraken2 database, then use those numbers as the accuracy ceiling when evaluating smaller or custom databases.

---

## Available Kraken2 Pre-Built Databases

All hosted at `https://genome-idx.s3.amazonaws.com/kraken/`. Sizes are post-extraction. Dated 2026-02-26 unless noted.

| Database | Contents | Size (GB) |
|----------|----------|-----------|
| Viral | RefSeq viral | 0.6 |
| MinusB | Archaea, viral, plasmid, human, UniVec | 11.1 |
| Standard-8 | Standard capped at 8 GB | 7.5 |
| Standard-16 | Standard capped at 16 GB | 14.9 |
| PlusPF-8 | PlusPF capped at 8 GB | 7.5 |
| PlusPF-16 | PlusPF capped at 16 GB | 14.9 |
| PlusPFP-16 | PlusPFP capped at 16 GB | 14.9 |
| Standard | Archaea, bacteria, viral, plasmid, human, UniVec | 96.8 |
| **PlusPF** | **Standard + protozoa + fungi** | **103.4** |
| PlusPFP | Standard + protozoa + fungi + plant | 221.8 |
| core_nt | GenBank, RefSeq, TPA, PDB (dated 2025-10-15) | 316.2 |
| GTDB v226 | Bacterial + archaeal genomes only (dated 2025-06-09) | 644.0 |

---

## Target Database: PlusPF (103.4 GB)

**Why PlusPF:** Standard covers the bacterial/viral/human scope already tested in AccuracyDrift. PlusPF adds protozoa and fungi — only 6.6 GB larger than Standard but ensures any fungal reads (e.g. Candida, common in nosocomial infections matching this sample's profile) are correctly classified rather than left unclassified or misassigned. For a gold-standard accuracy ceiling, missing an entire kingdom is not acceptable.

**Contents:** archaea, bacteria, viral, plasmid, human, UniVec, protozoa, fungi (all from RefSeq).

**Download command (run on Luna):**

```bash
wget https://genome-idx.s3.amazonaws.com/kraken/k2_pluspf_20260226.tar.gz
```

Download size: 79.8 GB compressed. Extract with:

```bash
tar -xzf k2_pluspf_20260226.tar.gz -C ~/AccuracyDrift/databases/pluspf_103gb/
```

---

## Results

### Classification Accuracy — Gold Standard (Luna, 32T, cold run)

| Read model | Classified% | Unclassified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Wall time (s) |
|------------|-------------|---------------|-----------------|----------------|-----|---------------|
| reads_fast | 96.79 | 3.21 | 93.79 | 90.11 | 0.90 | 57.75 |
| reads_hac  | 98.86 | 1.14 | 94.18 | 91.07 | 0.97 | 57.17 |
| reads_sup  | 99.24 | 0.76 | 94.16 | 91.21 | 1.00 | 57.00 |

**Cold-run caveat:** sys time was ~56s ≈ wall time across all three runs. With 32 threads and ~57s wall, only ~100 CPU-seconds were active — the other ~1,700 CPU-seconds of available thread time were idle, waiting on I/O. The 103 GB DB was being paged from disk during each run (first access after extraction). Wall times here reflect I/O-dominated cold starts. Warm repeats needed for steady-state classification speed (expect ~10–15s wall at 32T once 103 GB is page-cached in Luna's 503 GB RAM).

LLC miss rate 90–91% is the highest of any DB in the experiment, 9–10 pp above standard_16gb's 80–81%. IPC 0.90–1.00 is the lowest, confirming the most severe DRAM saturation observed.

### Comparison to standard_16gb (AccuracyDrift largest DB)

| Read model | standard_16gb | pluspf_103gb | Gain |
|------------|---------------|--------------|------|
| reads_fast | — (not collected in AccuracyDrift) | 96.79% | — |
| reads_hac  | 97.77% | 98.86% | +1.09 pp (+1,146 reads classified) |
| reads_sup  | 98.48% | 99.24% | +0.76 pp (+797 reads classified) |

Note: reads_fast × standard_16gb was not run during AccuracyDrift thread-scaling experiments, so no direct gain figure is available. The PlusPF reads_fast result (96.79%) is the gold-standard floor for reads_fast accuracy.

The ~1 pp gain from adding protozoa and fungi confirms a fraction of the standard_16gb unclassified reads are genuinely fungal/protozoan. The remaining 0.76–1.14% unclassified in PlusPF is likely truly novel sequence not in any RefSeq reference — this is the hard floor.

### Species Breakdown — PlusPF 103 GB (Luna, 32T)

Extracted with:
```bash
awk '$4=="S"' reads_<model>_pluspf_103gb_32T_report.txt | \
  grep -E "Pseudomonas aeruginosa$|Escherichia coli$|Klebsiella pneumoniae$|Acinetobacter baumannii$|Enterobacter cloacae$|Staphylococcus aureus$|Enterococcus faecium$"
```

| Species | reads_hac | reads_sup | reads_fast |
|---------|-----------|-----------|------------|
| *Pseudomonas aeruginosa* | 41.58% (43,630) | 40.73% (42,757) | 40.91% (42,890) |
| *Escherichia coli* | 20.60% (21,609) | 19.80% (20,784) | 21.19% (22,214) |
| *Klebsiella pneumoniae* | 9.22% (9,677) | 9.14% (9,599) | 7.95% (8,330) |
| *Acinetobacter baumannii* | 0.33% (341) | 0.36% (382) | 0.16% (165) |
| *Enterobacter cloacae* | 0.07% (76) | 0.09% (94) | 0.02% (26) |
| *Staphylococcus aureus* | 0.00% (1) | 0.00% (1) | — |
| *Enterococcus faecium* | — | — | — |

Key findings:
- **A. baumannii confirmed at 0.16–0.36%** — was in the standard DB long tail but never tabulated (below 1% threshold). Its presence here confirms a small but real A. baumannii component, which was invisible in sample_targeted because the NCBI genome was suppressed and could not be added to that DB.
- **S. aureus essentially absent** — 1 read across 104,918 (hac) and 104,980 (sup), 0 for fast. Not a meaningful clinical signal.
- **E. faecium absent** — 0 reads in all three models.
- **Major species counts are higher than standard_16gb** — P. aeruginosa 43,630 (PlusPF) vs 37,373 (standard_16gb), E. coli 21,609 vs 17,350, K. pneumoniae 9,677 vs 5,774. The extra reads come from the "long tail" pool, which shrank from ~37% to ~27%. PlusPF's different reference set shifts some LCA calls from genus/family-level ambiguous assignments to specific species — a reshuffling within classified reads, not just new classifications from unclassified.

### Next Steps

**Done:**
- [x] reads_fast × pluspf_103gb × 32T cold run (Luna)
- [x] reads_hac × pluspf_103gb × 32T cold run (Luna)
- [x] reads_sup × pluspf_103gb × 32T cold run (Luna)

**Pending:**
- [ ] Warm run for all three read models (103 GB should be page-cached in Luna's 503 GB RAM after cold runs; expect ~10–15s wall at 32T vs ~57s cold)
- [ ] Thread scaling for pluspf_103gb: 1T, 8T, 16T, 32T (done), 64T, 96T — to characterize Amdahl+DRAM behavior at 103 GB scale
