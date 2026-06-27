# ESKAPE Kraken2 — Compact-Hash Cell-Size Reduction (16 / 24-bit)

**Date:** 2026-06-27 · **Status:** implemented, built, verified (code + 3 DBs + accuracy runs).
Shrinks the ESKAPE Kraken2 hash table by narrowing the compact-hash **cell** below the stock
32 bits, exploiting that an ESKAPE-only DB needs only `value_bits = 6`.

---

## 1. Motivation

A compact-hash cell packs `key_bits (hash fragment) + value_bits (taxon) = cell_width`.
For the ESKAPE DB the taxon side is tiny and the rest is wasted:

- `value_bits = 6` (6 species + lineage = 35 taxonomy nodes → ⌈log₂35⌉ = 6).
- Stock 32-bit cell → `key_bits = 26` → false-positive ≈ **1 in 30 M** per foreign minimizer —
  absurd overkill for a 6-organism panel.
- Narrowing the cell turns those wasted check-bits into smaller files: **size ∝ cell_width**.

---

## 2. Implementation

The fork's `CompactHashTable<Cell>` is **templated on the cell type** and already shipped
`CompactHashCell` (32 b) + `CompactHashCell40` (40 b), selected by `-C`, with the width
self-described in the DB header and auto-detected on load (`kv_store.h` switches on
`key_bits+value_bits`). Added two more cells in the same pattern:

| New cell | bytes | layout | ESKAPE key/val |
|---|---|---|---|
| `CompactHashCell16` | 2 | `uint16_t` | 10 / 6 |
| `CompactHashCell24` | 3 | `uint16_t`+`uint8_t`, packed | 18 / 6 |

**Files changed** (`tools/kraken2/src/`): `compact_hash.h` (2 new structs), `kv_store.h`
(enum + `GetKVStoreCellType` cases 16/24), `build_db.cc` (`-C` validation + dispatch + a
`bits_for_taxid >= cell_size` guard), `classify.cc` + `dump_table.cc` (load dispatch),
`scripts/k2` (`--cht-cell-size` choices `16/24/32/40`). No algorithm/hot-path change; `Get()`
is width-generic. Recompiled (g++ 15.2, OpenMP) + installed to `kraken2-build/`.

**Inputs — zero download:**
- Genomes: 6 GCF ESKAPE assemblies already on disk (`data/eskape_genomes/`, 17 contigs).
- Taxonomy: reconstructed `nodes.dmp`/`names.dmp` from the on-disk 47,011-node
  `data/database/standard_8gb/taxo.k2d` (K2TAXDAT binary), pruned by `build_db` to 35 nodes.
- `seqid2taxid.map`: generated from the genome headers (each contig → species taxid).

---

## 3. Size — exactly tracks cell width (proven)

`hash.k2d = 32 B header + capacity × cell_bytes`; header negligible ⇒ **file ratio = cell-byte
ratio**. Verified to the byte (32-bit: `32 + 12,200,000×4 = 48,800,032`).

| DB | cell | key/val | hash.k2d | vs 32-bit |
|---|---|---|---|---|
| `eskape_32bit` | 4 B | 26 / 6 | 48.80 MB | 1.00× |
| `eskape_24bit` | 3 B | 18 / 6 | 36.60 MB | 0.75× |
| `eskape_16bit` | 2 B | 10 / 6 | 24.40 MB | **0.50×** |

Same 8.53 M distinct minimizers, capacity 12.2 M (~70% load), `value_bits=6` auto-derived in all.

---

## 4. False-positive model

`FP ≈ (probe length) × 2^(−key_bits)`. Build uses **`LINEAR_PROBING`** → ~6-cell probe runs at
70% load (not ~2 as for double hashing). Each key-bit halves/doubles FP.

| cell | key_bits | FP / foreign minimizer |
|---|---|---|
| 16-bit | 10 | ~1 in 170 |
| 24-bit | 18 | ~1 in 43,000 |
| 32-bit | 26 | ~1 in 11 M |

Per **long read** (hundreds of minimizers) the 16-bit per-minimizer rate compounds to a large
per-read FP; 24/32-bit stay negligible (see §5).

---

## 5. Accuracy (measured)

`classify` on `results/dorado/reads_{fast,hac,sup}.fastq` (~105 k long reads, ~3.4 kb avg).

### 5a. Classified % — 16-bit needs a confidence threshold, 24-bit does not

| readset | 32-bit `T0` | 24-bit `T0` | 16-bit `T0` | 16-bit `T0.05` (vs 32-bit `T0.05`) |
|---|---|---|---|---|
| fast | 67.70% | 68.15% (+0.45) | 88.82% (**+21.1**) | 54.27% vs 53.65% (+0.62) |
| hac | 73.10% | 73.43% (+0.33) | 90.39% (**+17.3**) | 61.76% vs 61.47% (+0.29) |
| sup | 73.85% | 74.14% (+0.29) | 90.37% (**+16.5**) | 62.78% vs 62.45% (+0.33) |

- **16-bit at `T0` over-classifies long reads by +16–21%** (false positives).
- **24-bit at `T0` is within +0.3–0.45%** of 32-bit — no threshold needed.
- **16-bit at `T ≥ 0.05`** converges to 32-bit within ~0.6% (FP is a tiny *fraction* of a long
  read's minimizers, so fraction-based filtering removes it).

### 5b. Per-species at `-T 0` (reads_fast) — the FP signature

| species (taxid) | 32-bit (truth) | 24-bit | 16-bit |
|---|---|---|---|
| P. aeruginosa (287) | 52,231 | 52,352 | 57,783 |
| K. pneumoniae (573) | 13,302 | 13,369 | 16,490 |
| E. cloacae (550) | 4,891 | 5,010 | 10,302 |
| A. baumannii (470) | 81 | 135 | 2,740 |
| S. aureus (1280) | 33 | 66 | 1,592 |
| E. faecium (1352) | 1 | 60 | 1,476 |
| unclassified (0) | 33,856 | 33,392 | 11,723 |

- 100% of the 16-bit "extra" reads (−22,133 unclassified) are false positives.
- **Cross-phylum proof:** E. coli/host reads inflating *S. aureus* (×48) and *E. faecium* (×1476)
  — Gram-positive Bacillota that share **no** 31-mers with Gram-negative Proteobacteria — can
  only be hash collisions, not biology. 24-bit barely moves these (1→60, 33→66).

### 5c. Correctness
Self-classifying the 6 genomes → every genome calls **its own species, identical across all cell
widths** (E.fae→1352, S.aur→1280, K.pneu→573, A.bau→470, P.aer→287, E.clo→550). `dump_table`
round-trips all 3 DBs; reported taxon sets identical (35 taxa, none missing/extra).

---

## 6. The size-vs-safety dial — recommendation

| DB | size | FP @ `T0` | runtime requirement |
|---|---|---|---|
| 32-bit | 48.80 MB | baseline | — |
| **24-bit** | **36.60 MB (−25%)** | +0.3–0.45% (negligible) | **none** |
| **16-bit** | **24.40 MB (−50%)** | +16–21% (large) | **`-T ≥ 0.05` mandatory** |

- **Max shrink:** `eskape_16bit` **+ `-T 0.05`** → ½ size, species-equivalent to 32-bit.
- **No-threshold safety:** `eskape_24bit` → −25%, drop-in, nothing to remember at runtime.

---

## 7. Commands

```bash
# build (per width W in 16/24/32):
cat data/eskape_genomes/eskape_all.fna | tools/kraken2/src/build_db \
  -k 35 -l 31 -c 12200000 -C $W \
  -H <out>/hash.k2d -o <out>/opts.k2d -t <out>/taxo.k2d \
  -m data/eskape_seqid2taxid.map -n data/eskape_tax -p 8

# classify (16-bit REQUIRES -T 0.05; 24/32-bit fine without):
tools/kraken2/src/classify -H <db>/hash.k2d -t <db>/taxo.k2d -o <db>/opts.k2d \
  -T 0.05 -R <report.txt> -O <out.txt> -p 8 <reads.fastq>
```

---

## 8. Artifacts

- DBs: `data/database/eskape_{16,24,32}bit/`
- Reports: `results/eskape_16bit/report_{16,24,32}bit_T{0,0.05}_{fast,hac,sup}.txt`
- Data summary: `results/eskape_16bit/findings.md`
- Build inputs: `data/eskape_tax/{nodes,names}.dmp`, `data/eskape_seqid2taxid.map`
