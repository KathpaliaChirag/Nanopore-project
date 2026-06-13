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

*(to be filled in as runs complete)*
