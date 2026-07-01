# Why 16-bit fails and 24-bit matches 32-bit — the false-positive mechanism

**Date:** 2026-07-01 · Analytical companion to the ESKAPE cell-width work
([`eskape_cellsize.md`](eskape_cellsize.md), [`eskape_cellsize_sweep.md`](eskape_cellsize_sweep.md)).
Explains *why*, across identical inputs, the **24-bit DB reproduces 32-bit but the 16-bit DB
over-classifies by +16–21 %** at `-T 0`. Grounded in the measured 1.87 M-read `fastq_fast` sweep.

---

## 0. The result to explain

At `-T 0` (no confidence filter), classified % vs the 32-bit baseline:

| cell | classified % | Δ vs 32-bit |
|---|---:|---:|
| 32-bit | 73.09 % | — |
| 24-bit | 73.38 % | **+0.29** (negligible) |
| 16-bit | 89.96 % | **+16.87** (all false positives) |

The +16.87 % is not real detection — it is foreign/host reads being mislabelled (proven by
cross-phylum hits: *E. faecium* 3→21,355, *S. aureus* 902→23,877, organisms that share no 31-mers
with the Gram-negative Proteobacteria dominating the sample). The question is why 16-bit does this
and 24-bit does not.

---

## 1. The only variable that changes: `key_bits`

All three DBs are built from the same genomes, same capacity (`-c 12200000`), same ~70 % load,
same probe length (~6 under `LINEAR_PROBING`), same `value_bits = 6`. A compact-hash cell packs
`key_bits + value_bits = cell_width`, so the **only** difference is how many bits are left for the
key after the fixed 6-bit taxon:

| cell | value_bits | **key_bits (check bits)** |
|---|---:|---:|
| 32-bit | 6 | **26** |
| 24-bit | 6 | **18** |
| 16-bit | 6 | **10** |

## 2. What `key_bits` are — and why fewer means more false hits

Kraken2 does **not** store the full minimizer in a cell. It stores a **truncated hash fragment**
of width `key_bits`. At lookup, a queried minimizer is declared a *hit* if its fragment **equals**
the stored fragment. Because the fragment is only `key_bits` wide, **two different minimizers can
share the same fragment by chance** — a foreign minimizer (not in the DB) then matches a stored
fragment and is falsely assigned that taxon. Fewer check bits ⇒ more accidental matches.

## 3. The exponential law — each bit removed *doubles* the FP rate

Probability that a random foreign minimizer falsely matches:

```
FP_per_minimizer ≈ probe_length × 2^(−key_bits)      (probe ≈ 6 at 70% load)
```

| cell | key_bits | FP per foreign **minimizer** |
|---|---:|---:|
| 32-bit | 26 | 6 / 2²⁶ ≈ **1 in 11,000,000** |
| 24-bit | 18 | 6 / 2¹⁸ ≈ **1 in 44,000** |
| 16-bit | 10 | 6 / 2¹⁰ ≈ **1 in 170** |

It is base-2, so the damage is concentrated in the last bits removed. 32→24 drops 8 bits
(FP ×256) but stays microscopic; 24→16 drops **another** 8 bits (×256 again) and lands in a
completely different regime (1-in-170).

## 4. The amplifier — a long read has ~1,000 minimizers

A single 1-in-170 event is harmless in isolation, but a multi-kb nanopore read carries **hundreds
to ~1,000+ minimizers** (a ~3.4 kb read at `k=35, l=31` ⇒ order 10³ minimizer lookups), each an
independent chance to collide. Expected false hits in one *foreign* read:

```
false_hits_per_read ≈ N_minimizers × FP_per_minimizer     (N ≈ 1,000)
```

| cell | FP/minimizer | × ~1,000 minimizers = false hits per foreign read | outcome |
|---|---:|---:|---|
| 32-bit | 1/11M | ~0.0001 (1 in ~11,000 reads) | never |
| 24-bit | 1/44k | ~0.023 (1 in ~44 reads) | negligible |
| **16-bit** | 1/170 | **~6 false hits in *every* foreign read** | **catastrophic** |

## 5. The cliff — why 24 ≈ 32 but 16 fails

A foreign read gets falsely classified once it accumulates ≳1 false hit, i.e. once

```
FP_per_minimizer ≳ 1 / N ≈ 1/1,000      ("noise floor" of a long read)
```

Solving `probe × 2^(−key_bits) = 1/N` gives the break-even at **key_bits ≈ 13**. So there is a
cliff around 13 check bits:

- **16-bit → 10 check bits → *below* the cliff** ⇒ every foreign read collects several false hits
  ⇒ the +16.87 % over-classification.
- **24-bit → 18 check bits → well *above* the cliff** ⇒ <1 false hit per ~44 reads ⇒ matches 32-bit.
- **32-bit → 26 check bits → far above** ⇒ astronomically safe.

**That is the whole answer:** 24 and 32 both sit on the safe side of the ~13-bit cliff (both at
"<1 false hit per foreign read"), so they are indistinguishable; 16 sits on the wrong side. The 8
extra check bits 32-bit has over 24-bit are real but unobservable overkill.

## 6. Why the confidence threshold rescues 16-bit (and 24-bit never needed it)

The ~6 false hits in a 16-bit foreign read are **isolated** — a handful out of ~1,000 k-mers. The
confidence score = (k-mers on the winning taxon's path) / (total k-mers) ≈ 6/1,000 ≈ 0.006, so
`-T 0.05` filters them while keeping genuine reads (whose k-mers overwhelmingly agree). Measured:
16-bit `-T 0` +16.87 % → `-T 0.05` **+0.32 %**. 24-bit produces almost no false hits to begin with,
so it needs no threshold (`-T 0.05` deviation vs 32-bit: **+22 reads out of 1.87 M**).

## 7. The same collisions are visible at build time

Independent confirmation, before any read is classified: the 16-bit table holds **~9,600 fewer
occupied cells** than 32-bit (8,525,857 vs 8,535,483) — distinct real minimizers colliding onto
the same 10-bit fragment and merging during build. Same root cause (too few check bits), 24-bit
loses only 35 cells.

---

## 8. Conclusion

```
FP per foreign read ≈ N_minimizers × probe × 2^(−key_bits)
                    ≈ 1,000        × 6     × 2^(−key_bits)
```

The term that moves is `2^(−key_bits)`, and a long read multiplies it by ~1,000. 24-bit
(18 check bits) keeps the product far below 1 (≈0.02) → clean, like 32-bit. 16-bit (10 check bits)
pushes it to ≈6 → nearly every foreign read is mislabelled. The transition is sharp (a cliff at
~13 check bits) because FP is *exponential* in key_bits while the long-read amplifier is a fixed
~10³. Hence: **24-bit is a safe drop-in for 32-bit; 16-bit is only safe with `-T ≥ 0.05`.**
