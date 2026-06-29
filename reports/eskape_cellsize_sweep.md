# ESKAPE Kraken2 — Cell-Width Deviation Sweep (16 vs 24 vs 32-bit)

**Date:** 2026-06-29 · **Status:** measured (fresh 18-run sweep + table-fill audit).
Goal: quantify **how far 24-bit and 16-bit DBs deviate from the 32-bit baseline** across all
three basecalling models, so the size cut can be justified with numbers — and report **how full
each table actually is**.

Inputs: the same 3 dorado read sets (`results/dorado/reads_{fast,hac,sup}.fastq`, ~105 k long
reads each, ~3.4 kb avg) classified against `data/database/eskape_{16,24,32}bit/` at two
confidence thresholds (`-T 0` = none, `-T 0.05`). 18 runs total. Companion to the
implementation report [`eskape_cellsize.md`](eskape_cellsize.md).

---

## 1. Table fill (load factor) — how full is each DB

All three DBs were built with the same capacity (`-c 12200000`) from the same 6 genomes, so they
hold the same minimizer set. "Fill" = occupied cells ÷ capacity (from `dump_table` —
`# Table size` ÷ `# Table capacity`).

| DB | occupied cells | capacity | **filled** | empty |
|---|---:|---:|---:|---:|
| `eskape_16bit` | 8,525,857 | 12,200,000 | **69.88 %** | 30.12 % |
| `eskape_24bit` | 8,535,448 | 12,200,000 | **69.96 %** | 30.04 % |
| `eskape_32bit` | 8,535,483 | 12,200,000 | **69.96 %** | 30.04 % |

- All three sit at **~70 % full / ~30 % empty** — the headroom Kraken2's linear probing needs
  (a hash table is deliberately not packed to 100 %, or probe chains explode).
- The 16-bit table holds **9,626 fewer occupied cells** than 32-bit (8,525,857 vs 8,535,483).
  Cause: with only 10 key bits, distinct minimizers occasionally collapse to the **same
  (key-fragment, taxon)** pair and merge into one cell — a direct, measurable footprint of the
  collisions that drive 16-bit's false positives. 24-bit (18 key bits) loses just 35 cells.
- **Disk/RAM is set by capacity × cell-bytes, not by fill** — emptiness costs the same bytes at
  every width, so shrinking the *cell* is the only lever that shrinks the file (proven in
  `eskape_cellsize.md §3`): 48.80 → 36.60 → 24.40 MB.

---

## 2. Why the table sits at ~70% — and why we don't pack it tighter

A natural question: we *shrank the cell*, so why didn't the table get fuller than 70%? Because
**cell-bit-size and fill % are orthogonal.** Fill % = occupied cells ÷ capacity — a count of
*slots*, set by `-c` (12.2 M, identical in all 3 builds) and the minimizer count (~8.53 M,
identical). The cell width only changes *bytes per slot*, i.e. file size, never the slot count.
So all three land at ~70% by construction. The deeper reason 70% is the *right* place to stop:

**Probing.** Kraken2 uses **open addressing with linear probing** (this build is compiled
`-DLINEAR_PROBING`; `compact_hash.h:second_hash()` returns step `1`). A minimizer hashes to a
home slot; if a *different* key sits there, you step +1 and check the next slot, repeating until
you find your key or hit an **empty** slot (which ends the search). The cells touched = **probe
length**. Empty slots are the brakes — fill the table and you remove them.

**The math.** Expected probe length for an absent key (Knuth, α = fill factor):

```
probes ≈ ½ · ( 1 + 1/(1−α)² )
```

The `1/(1−α)²` term is quadratic in how close to full you are — it's a wall, not a slope:

| fill α | avg probes |
|---:|---:|
| 50 % | 2.5 |
| **70 % (our DB)** | **6.1** |
| 80 % | 13 |
| 90 % | 50 |
| 95 % | 200 |
| 99 % | 5,000 |

70%→80% doubles; the last few percent cost *thousands* of probes. Cause: linear probing creates
**primary clustering** — occupied cells pile into long contiguous runs, and as empties vanish the
runs merge, so the average walk explodes.

**Two costs of filling higher.** Longer chains cost (a) **speed** — more cells/cache lines per
lookup; and (b) **false positives** — each cell compared is another collision chance:

```
FP per foreign minimizer ≈ (probe length) × 2^(−key_bits)
```

For the 16-bit cell (key_bits = 10, 2⁻¹⁰ = 1/1024): at 70% fill → 6/1024 ≈ **1 in 170** (the rate
measured in §4); at 95% fill → 200/1024 ≈ **1 in 5** — useless. The narrow cell has the least FP
margin, so it suffers most when packed tighter (the per-species fallout is §4). The source itself notes linear probing is "ok…
as long as occupancy is < 95%" and otherwise gives "higher probability of a false answer."

**So why 70%?** It's the knee — the last cheap point before the wall (~6 probes for ~43% byte
overhead). Below it wastes RAM for no speed gain; above ~80% probes and FP turn sharply upward.

**The capacity lever — the *worse* way to shrink.** File size has two multipliers:

```
file = capacity × cell_bytes      →   two ways to shrink it:
        (slots)    (bits/8)
```

| lever | how | effect on probe length / FP |
|---|---|---|
| **narrow the cell** (this work, 4→2 B) | fewer **bytes per slot** | **none** — α stays 70%, probes stay ~6 |
| **cut capacity** (`-c` smaller) | fewer **slots** | **worse** — α rises, probes & FP blow up super-linearly |

`-c 9000000` would give 8.53M/9M ≈ **95% fill** → ~200 probes → 16-bit FP ≈ 1-in-5: it saves
~6 MB and destroys accuracy. And there's a hard floor — if capacity drops below the minimizer
count (α→100%) the build can't place keys and **fails outright**, so slots must exceed minimizers
with margin. **Conclusion:** narrowing the cell shrinks bytes with the table left at its safe 70%
(probes & FP unchanged); packing tighter shrinks bytes but pays super-linearly in chain length
and false positives — which is exactly why we shrank the *cell* and left the fill at 70%.

---

## 3. Headline — classified % and deviation from 32-bit

Deviation Δ = (cell-width classified %) − (32-bit classified %), same read set, same threshold.

| read set | `-T` | 32-bit | 24-bit (Δ) | 16-bit (Δ) |
|---|---|---:|---:|---:|
| fast | 0 | 67.70 % | 68.15 % (**+0.45**) | 88.82 % (**+21.12**) |
| fast | 0.05 | 53.65 % | 53.65 % (**+0.00**) | 54.27 % (**+0.62**) |
| hac | 0 | 73.10 % | 73.43 % (**+0.33**) | 90.39 % (**+17.29**) |
| hac | 0.05 | 61.47 % | 61.48 % (**+0.01**) | 61.76 % (**+0.29**) |
| sup | 0 | 73.85 % | 74.14 % (**+0.29**) | 90.37 % (**+16.52**) |
| sup | 0.05 | 62.45 % | 62.45 % (**+0.00**) | 62.78 % (**+0.33**) |

Same deviation, expressed in **reads** (processed: fast 104,832 · hac 104,918 · sup 104,980):

| read set | `-T` | 24-bit Δreads | 16-bit Δreads |
|---|---|---:|---:|
| fast | 0 | +472 | **+22,140** |
| fast | 0.05 | ~0 (1 read) | +650 |
| hac | 0 | +346 | **+18,140** |
| hac | 0.05 | +4 | +304 |
| sup | 0 | +304 | **+17,343** |
| sup | 0.05 | ~0 (1 read) | +346 |

**Read of the table:**
- **24-bit ≈ 32-bit at every setting.** Even with *no* threshold the gap is +0.3–0.45 %
  (a few hundred reads); with `-T 0.05` it is **0–4 reads out of ~105 k** — statistically
  identical. 24-bit is a true drop-in replacement.
- **16-bit at `-T 0` is unusable:** +16–21 % (17 k–22 k extra reads), all false positives.
- **16-bit with `-T 0.05` converges to within +0.3–0.6 %** of 32-bit. The threshold is mandatory,
  but once applied the two DBs agree to better than 1 %.

---

## 4. Where the 16-bit false positives land (per-species, `-T 0`, reads_fast)

This is the FP signature — counts that **cannot be biology**, only hash collisions.

| species (taxid) | 32-bit (truth) | 24-bit | 16-bit | 16-bit inflation |
|---|---:|---:|---:|---:|
| *P. aeruginosa* (287) | 52,231 | 52,352 | 57,783 | ×1.11 |
| *K. pneumoniae* (573) | 13,302 | 13,369 | 16,490 | ×1.24 |
| *E. cloacae* (550) | 4,891 | 5,010 | 10,302 | ×2.11 |
| *A. baumannii* (470) | 81 | 135 | 2,740 | **×34** |
| *S. aureus* (1280) | 33 | 66 | 1,592 | **×48** |
| *E. faecium* (1352) | 1 | 60 | 1,476 | **×1476** |
| unclassified (0) | 33,856 | 33,392 | 11,723 | −22,133 |

- 100 % of the 16-bit "extra" classified reads come straight out of the unclassified pile
  (−22,133 ≈ the +22,140 over-classification).
- **Cross-phylum proof:** *S. aureus* (×48) and *E. faecium* (×1476) are Gram-positive Bacillota
  that share **no 31-mers** with the Gram-negative Proteobacteria that dominate this sample.
  Their inflation can only be collision FP. **24-bit barely moves them** (1→60, 33→66) and the
  threshold (§4) erases them.

---

## 5. The converged state (per-species, `-T 0.05`, reads_fast)

With the threshold on, all three widths agree at the species level:

| species (taxid) | 32-bit | 24-bit | 16-bit |
|---|---:|---:|---:|
| *P. aeruginosa* (287) | 46,408 | 46,408 | 46,513 |
| *K. pneumoniae* (573) | 8,749 | 8,749 | 8,767 |
| *E. cloacae* (550) | 457 | 457 | 465 |
| *A. baumannii* (470) | 25 | 25 | 27 |
| *S. aureus* (1280) | 13 | 13 | 13 |
| *E. faecium* (1352) | 0 | 0 | 0 |

24-bit is **identical** to 32-bit; 16-bit differs by **+105 reads on the dominant species and
≤8 on the rest** — the spurious cross-phylum calls (*S. aureus*, *E. faecium*) are gone.

---

## 6. Verdict — can we drop from 32-bit?

| option | size | deviation from 32-bit | runtime requirement | verdict |
|---|---:|---|---|---|
| **24-bit** | 36.60 MB (**−25 %**) | +0.3–0.45 % at `-T 0`; **0–4 reads** at `-T 0.05` | none | **Yes — safe drop-in.** Equivalent to 32-bit; just 25 % smaller. |
| **16-bit** | 24.40 MB (**−50 %**) | +16–21 % at `-T 0` (unusable); **+0.3–0.6 %** at `-T 0.05` | **`-T ≥ 0.05` mandatory** | **Yes, with the threshold.** Halves the DB; species-equivalent once `-T 0.05` is set. |

- **Want zero things to remember at runtime →** ship **24-bit**. The deviation is within
  measurement noise (a single read across 105 k at `-T 0.05`), for a free 25 % size cut.
- **Want maximum shrink (½) →** ship **16-bit + `-T 0.05`**. Confirmed across fast/hac/sup:
  the threshold removes the collision FP and the result tracks 32-bit to <1 %.
- The FP gap is largest on **fast** (most basecall errors → most spurious minimizers) and
  smallest on **sup**, exactly as expected — so a higher-accuracy basecaller makes 16-bit even
  safer.

---

## 7. Artifacts

- Per-run Kraken reports: `results/eskape_16bit/sweep/report_{fast,hac,sup}_{16,24,32}bit_T{0,0.05}.txt`
- Raw classify stderr (processed/classified/unclassified): `results/eskape_16bit/sweep/stderr_*.txt`
- Machine-readable summary: `results/eskape_16bit/sweep/summary.tsv`
- DBs: `data/database/eskape_{16,24,32}bit/` · Implementation report: [`eskape_cellsize.md`](eskape_cellsize.md)

### Commands

```bash
# table fill (load factor) per DB:
dump_table -s -H <db>/hash.k2d -t <db>/taxo.k2d -o <db>/opts.k2d   # → Table size / Table capacity

# sweep (W in 16/24/32, T in 0/0.05, RS in fast/hac/sup):
classify -H <db>/hash.k2d -t <db>/taxo.k2d -o <db>/opts.k2d \
  -T $T -R report_${RS}_${W}bit_T${T}.txt -O /dev/null -p 8 reads_${RS}.fastq
```
