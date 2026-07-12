# 16-bit Compact Hash Cell — ESKAPE DB (results)

Added `CompactHashCell16` (2-byte) and `CompactHashCell24` (3-byte) cells to the Kraken2 fork;
rebuilt the ESKAPE DB at 16/24/32-bit from **identical inputs** (6 ESKAPE genomes, reconstructed
47k-node taxonomy, no download). Build: `build_db -k 35 -l 31 -c 12200000 -C {16|24|32}`.

## Size — exactly tracks cell width (as proven)

| DB | cell | key/val bits | hash.k2d | vs 32-bit |
|---|---|---|---|---|
| eskape_32bit | 4 B | 26 / 6 | 48.80 MB | 1.00× |
| eskape_24bit | 3 B | 18 / 6 | 36.60 MB | 0.75× |
| eskape_16bit | 2 B | 10 / 6 | 24.40 MB | 0.50× |

Size = 32 B header + capacity × cell_bytes; ratio = cell-byte ratio. `value_bits=6` auto-derived
(35 taxonomy nodes). 16-bit is exactly 2× smaller.

## The size-vs-safety dial (FP at `-T 0`, no threshold; reads_fast)

| DB | size | classified (32-bit=67.70%) | abs-species FP (E.fae 1 / S.aur 33) | needs `-T`? |
|---|---|---|---|---|
| 32-bit | 48.80 MB | 67.70% | 1 / 33 | no |
| **24-bit** | **36.60 MB** | **68.15% (+0.45%)** | **60 / 66** | **NO** |
| 16-bit | 24.40 MB | 88.82% (+21.1%) | 1476 / 1592 | **YES** (`-T ≥ 0.05`) |

**24-bit is the no-threshold sweet spot**: 25% smaller, FP +0.3–0.45% across fast/hac/sup at
`-T 0` (24→68.15/73.43/74.14% vs 32→67.70/73.10/73.85%). **16-bit is 50% smaller but must run
with `-T ≥ 0.05`.**

## Accuracy — equivalent ONLY with a confidence threshold

`classify` on `results/dorado/reads_fast.fastq` (104,832 long reads, ~3.4 kb avg):

| `-T` | 32-bit classified | 16-bit classified | Δ |
|---|---|---|---|
| 0 (none) | 67.70% | 88.82% | **+21.1% (false positives)** |
| 0.05 | 53.65% | 54.27% | +0.62% |
| 0.10 | 47.46% | 47.98% | +0.52% |

Per-species at `-T 0.10` (reads): P.aer 41,481 vs 41,578 · K.pneu 7,599 vs 7,608 ·
E.clo 253 vs 256 · A.bau 13 vs 13 — within 0.3%.

### Generalizes across basecalling models (fast / hac / sup, ~105k reads each)

| readset | `-T 0`: 32→16-bit | Δ | `-T 0.05`: 32→16-bit | Δ |
|---|---|---|---|---|
| fast | 67.70 → 88.82% | +21.1% | 53.65 → 54.27% | +0.62% |
| hac  | 73.10 → 90.39% | +17.3% | 61.47 → 61.76% | +0.29% |
| sup  | 73.85 → 90.37% | +16.5% | 62.45 → 62.78% | +0.33% |

Same pattern everywhere: +16–21% FP at `-T 0`, converges to <0.7% at `-T 0.05`. FP gap is
largest for `fast` (most basecalling errors → most spurious minimizers), smallest for `sup`.

### Correctness (self-classify the 6 genomes)
Both DBs call every genome → its own species, **identical** (E.fae→1352, S.aur→1280,
K.pneu→573, A.bau→470, P.aer→287, E.clo→550). 16-bit returns correct taxa for true hits;
only foreign-read FP differs.

## Key points

- At **`-T 0`** the 16-bit DB over-classifies long reads by 21% — spurious hits inflate every
  species (worst on absent ones: E. faecium 1→1476, S. aureus 33→1592, A. baumannii 81→2740).
- Cause: key_bits=10 → ~1/170 FP per foreign minimizer under **LINEAR_PROBING** (build default,
  ~6-cell probe runs) × hundreds of minimizers/long-read → ≥2 spurious hits is common.
- A **confidence threshold (`-T ≥ 0.05`)** collapses it: spurious hits are a tiny *fraction* of a
  long read's minimizers, so fraction-based filtering removes them while keeping true calls. The
  two DBs then match within ~0.5%.

## Recommendation

- **16-bit DB is viable and halves RAM/disk (24.4 MB), but MUST be run with `-T ≥ 0.05`** on
  long reads. Do not use it at `-T 0`.
- If zero threshold-reliance is wanted: build at **`-C 24`** (key=18, FP ~1/250k, 38.6 MB) —
  add a 3-byte `CompactHashCell24` (same pattern as `CompactHashCell40`).

Reports: `report_{16,32}bit_T{0,0.05,0.10}.txt`. DBs: `data/database/eskape_{16,32}bit/`.
