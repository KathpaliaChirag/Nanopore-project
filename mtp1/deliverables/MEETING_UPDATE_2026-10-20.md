# Meeting update — 20 October 2026

Two questions from the last meeting, both now answered with measurements on all
16 pod5 files (1,872,777 reads, 6,036 Mbp).

1. **Can the 50 MB database be made bigger, the way the 16 GB one is?** —
   Yes, and it was. Two useful answers came out of it, one of which is better
   than "make it bigger".
2. **Does a read from the FASTQ file produce the same hash in the 50 MB and the
   16 GB database? The same key in the table? The same output?** — Hash: yes,
   identical. Key: no, it is a *truncation* of the same hash. Output: no, and
   the reason is granularity, not disagreement. Verified on a real read, byte
   for byte.

---

# Part 1 — Making the database bigger

## 1.1 What the old 50 MB database actually was

The database we have been benchmarking all term is **48.8 MB** and is built
from **six genomes** — one strain per species, and it is **missing
*A. baumannii*** entirely. So five of the six ESKAPE letters, one strain each.

| | old 49 MB (`eskape_32bit_fork`) |
|---|---|
| genomes | 6 |
| ESKAPE letters covered | **5 / 6** (no *A. baumannii*) |
| strains per species | 1 |
| hash cells | 12,200,000 |
| minimizers stored | 8,903,388 |
| `-M` subsampling | none (0% skip) |

That is the thing being compared against everywhere below.

## 1.2 Could we just extract ESKAPE out of the 16 GB database?

This was tried first, because it is the cheapest option. **It is not possible**,
for two independent reasons:

- `standard_16gb` is a **prebuilt download**. It has **no `library/` directory**
  — the source FASTA is not on disk, so there is nothing to re-build from.
  (`ls databases/standard_16gb/` → only the `.k2d` files, taxonomy and reports.)
- The only tool that can read a built hash table, `dump_table`, emits
  **per-taxon summary counts, not minimizer→taxid pairs**. The mapping needed to
  carve out a subset is not recoverable from the file.

And even if it were: `standard_16gb` is built at **79.25% skip**, so it only
*keeps* 20.75% of its minimizers. Any ESKAPE extract from it would be ~5× sparser
than the complete 50 MB database we already have. It would be a downgrade.

## 1.3 What was built instead

**175 complete RefSeq genomes downloaded — 25 strains per species, 7 species,
including *A. baumannii* this time.** 812.9 Mbp, 577 contigs.

Strain selection: reference/representative assembly first, then evenly spaced
through the remaining complete+latest assemblies, so the 25 are not all
clustered in one clade.

Built with the project's standard recipe (spaced seed matched to kraken2's
default so it is comparable to `standard_16gb`):

```bash
cat library/*.fna | kraken2_bin/build_db -H hash.k2d -t taxo.k2d -o opts.k2d \
    -n taxonomy -m seqid2taxid.map \
    -c 52000000 -k 35 -l 31 -p 1 \
    -S 1111111111111111101010101010101     # + -M <cells> to subsample
```

Three databases came out of that one library:

| database | file size | cells | minimizers stored | skip | load |
|---|---:|---:|---:|---:|---:|
| `eskape_big` | 208,000,032 B | 52,000,000 | 36,038,357 | 0% | 69.3% |
| `eskape_big_M12000000` | **48,000,032 B** | 12,000,000 | 8,316,093 | 76.92% | 69.3% |
| `eskape_big_M4000000` | 16,000,032 B | 4,000,000 | 2,771,756 | 92.31% | 69.3% |

All three are `key_bits 26 / value_bits 6`, 4-byte cell — the same layout as the
old database, so this is a clean comparison.

`-M` does **not** change the library. All three hold the same 175 genomes; `-M`
discards minimizers at build time by a hash threshold, keeping `M/c` of them.
Verified: threshold = `(1 − M/c) × UINT64_MAX` exactly
(`0xc4ec4ec4ec4ec000` for `-M 12000000`).

## 1.4 Contents of the 48 MB build

**Same 175 genomes as the 208 MB build. 150 of them ESKAPE. 6 of 6 letters.**

| letter | organism | genomes | taxid | minimizers (48 MB) | Mbp |
|---|---|---:|---:|---:|---:|
| **E** | *Enterococcus faecium* | 25 | 1352 | 493,824 | 75.3 |
| **S** | *Staphylococcus aureus* | 25 | 1280 | 543,228 | 71.1 |
| **K** | *Klebsiella pneumoniae* | 25 | 573 | 1,126,697 | 142.7 |
| **A** | *Acinetobacter baumannii* | 25 | 470 | 1,030,992 | 100.8 |
| **P** | *Pseudomonas aeruginosa* | 25 | 287 | 1,396,453 | 167.4 |
| **E** | *Enterobacter cloacae* | 25 | 550 | 2,146,927 | 126.5 |
| | **ESKAPE subtotal** | **150** | | **6,738,121** | **684.1** |
| — | *Escherichia coli* (not ESKAPE) | 25 | 562 | 1,404,833 | 128.8 |
| — | shared across taxa (LCA) | — | — | 173,139 | — |
| | **total** | **175** | | **8,316,093** | **812.9** |

Every organism retains exactly **23.08%** of its 208 MB minimizer count. The
threshold is a plain hash comparison with no knowledge of taxonomy, so **no
organism is favoured and none is dropped.**

## 1.5 Result — all 16 files, `-T 0 -p 16 -g 2`

| file | reads | old 49 MB | new 208 MB | new 48 MB | new 16 MB | 48 vs old |
|---|---:|---:|---:|---:|---:|---:|
| pod5_0 | 132,074 | 83.97% | 95.30% | 93.43% | 87.78% | +9.46 |
| pod5_1 | 141,195 | 84.05% | 95.26% | 93.39% | 88.01% | +9.34 |
| pod5_2 | 151,591 | 84.26% | 95.25% | 93.46% | 88.27% | +9.20 |
| pod5_3 | 141,365 | 83.77% | 95.07% | 92.98% | 87.53% | +9.21 |
| pod5_4 | 131,822 | 83.84% | 95.07% | 93.03% | 87.82% | +9.19 |
| pod5_5 | 130,448 | 83.30% | 94.49% | 92.32% | 87.17% | +9.02 |
| pod5_6 | 120,965 | 83.50% | 94.82% | 92.71% | 87.50% | +9.21 |
| pod5_7 | 119,216 | 83.88% | 94.98% | 93.06% | 87.90% | +9.18 |
| pod5_8 | 122,764 | 84.06% | 95.10% | 93.09% | 87.91% | +9.03 |
| pod5_9 | 109,728 | 84.00% | 94.94% | 93.10% | 87.68% | +9.10 |
| pod5_10 | 104,918 | 83.85% | 95.03% | 93.27% | 88.13% | +9.42 |
| pod5_11 | 123,458 | 83.18% | 94.50% | 92.39% | 86.84% | +9.21 |
| pod5_12 | 109,020 | 83.49% | 94.83% | 92.93% | 87.39% | +9.44 |
| pod5_13 | 106,781 | 83.87% | 95.25% | 93.44% | 88.09% | +9.57 |
| pod5_14 | 97,054 | 83.25% | 94.63% | 92.58% | 86.88% | +9.33 |
| pod5_15 | 30,378 | 83.39% | 94.99% | 92.93% | 87.98% | +9.54 |
| **MEAN** | **1,872,777** | **83.73%** | **94.97%** | **93.01%** | **87.68%** | **+9.28** |

The ordering holds in **all 16 files** and the spread across files is only
0.55 pp, so this is not a one-file artefact.

## 1.6 The headline — and it is not "bigger is better"

| | old 49 MB | **new 48 MB** |
|---|---:|---:|
| file size | 48.8 MB | **48.0 MB** |
| ESKAPE genomes behind it | 5 | **150** |
| ESKAPE letters | 5 / 6 | **6 / 6** |
| minimizers stored | 8,903,388 | 8,316,093 |
| classified, 16 files | 83.73% | **93.01%** |

**Same file size. 30× the genomes. Slightly *fewer* minimizers stored. 9.28
points better.**

This is the real finding, and it is more interesting than the 208 MB number:
the 48 MB build holds **fewer** minimizers than the database we have been using,
and still beats it by 9 points — because **23% of 150 genomes covers more real
biology than 100% of 5**. At a fixed memory budget, **reference breadth beats
reference completeness.** Spending the 50 MB on more organisms is worth more
than spending it on more detail about fewer organisms.

Going to 208 MB buys a further 1.96 pp for 4.3× the memory. Diminishing, but
real.

### Headroom

The old database already reached 83.73%, so only 16.24 pp were available at all.
The 48 MB build takes **57.0%** of that. Measured against the practical ceiling
(`standard_16gb` at 97.60%), the achievable gain is 13.84 pp, of which the
48 MB build captures **66.9%**.

### Saturation — why 25 strains and not more

Measured on this library (strains per species → minimizers):

| strains/species | 1 | 2 | 5 | 10 | 25 |
|---|---:|---:|---:|---:|---:|
| minimizers | 9.9 M | 13.6 M | 19.7 M | 26.5 M | 36.0 M |

29× more input sequence yields 4.05× more minimizers — growth ≈ `n^0.4`
(Heaps' law). 175 genomes is 1.2% of the 14,513 complete RefSeq assemblies
available for these 7 species, yet already covers roughly 18% of the projected
~200 M-minimizer pan-genome. The curve is flattening, so strain 26 onward is
poor value; **adding a missing species is worth far more than adding a strain.**

## 1.7 Two caveats that must be stated to the prof

**(a) These are classification *rates*, not correctness.** The gain is real but
it is partly forced assignment. False positives, across all 16 files:

| control | old 49 MB | new 208 MB | new 48 MB | new 16 MB |
|---|---:|---:|---:|---:|
| *S. aureus* | 12 | 18 | 16 | 13 |
| *E. faecium* | 48 | 2 | **1** | 3 |
| *A. baumannii* | 0 | **1,048** | **948** | 629 |
| as % of 1.87 M reads | 0.0032% | 0.0570% | 0.0515% | 0.0344% |

`standard_16gb` was used to arbitrate what the sample actually contains
(pod5_15): *Pseudomonas* 17,557, *Escherichia* 5,172, *Klebsiella* 2,905,
***Homo sapiens* 253**, *Enterobacter* 143, *Shigella* 58, phage 52,
*Streptomyces* 41, *Salmonella* 22 — and ***A. baumannii*: 1 read**,
*S. aureus* 0, *E. faecium* 0.

So the ~950 *A. baumannii* calls are **wrong**. The cause is **forced
assignment, not hash collision**: a 7-species database can only answer with one
of its 7 species or "unclassified", and there are ~1,120 reads in the sample
(human, phage, *Streptomyces*, *Salmonella*, *Shigella*) with no ESKAPE home.
The proof that the fingerprint is not degrading is that *E. faecium* false
positives went **down**, 48 → 1, and *S. aureus* is flat.

In the decomposition: **+173,398 reads newly classified, 948 of them spurious —
183 : 1.** The gain is sound; the fix for the 948 is a decoy set (add human,
already on disk, plus a *Pseudomonas* phage), not a smaller database.

**(b) The 16 MB build is not usable.** At `-T 0` it looks fine (87.68%), but at
a realistic `-T 0.05` it **collapses from 87.98% to 54.61%**. Skipped minimizers
still count toward the confidence denominator (`classify.cc:743`,
`required_score = ceil(T × taxa.size())` where `taxa.size()` includes the
taxon-0 skipped entries). Working rule: **stay at or below ~80% skip**, i.e.
`-M ≥ 10,400,000` at `-c 52,000,000`. The 48 MB build at 76.92% is inside that.

---

# Part 2 — Is the hash the same in the 50 MB and the 16 GB database?

Verified end to end on one real read from `pod5_15`:
`14f8e11f-1e09-48d1-8a7b-ac43994b3bf0`, 2,274 bp, 717 distinct minimizers.

The question "is it the same" has a **different answer at each stage**, so it is
worth separating them.

```
read ─► minimizer ─► hash ─► key ─► slot ─► cell value ─► taxo.k2d ─► taxid
         STAGE 1    STAGE 2  STAGE 3 STAGE 4  STAGE 5      STAGE 6
        NOT the     IDENTICAL TRUNCA-  diff-   diff-       diff-      diff-
        same         (yes)     TION    erent   erent       erent      erent
        (if seeds differ)
```

Six stages, not five: **the value in the hash cell is not the taxid.** With 6
value bits it cannot be — 6 bits hold 63 distinct values. It is an index into
`taxo.k2d`, and the taxid comes out of a *second* table. Full diagram and the
read-level resolution in **`FLOW.md`**.

## Stage 2 — The hash: **identical. Yes.**

kraken2 hashes with MurmurHash3, which is a **pure function of the minimizer
alone**. No database state, no table size, no taxonomy enters it. Same
minimizer ⇒ same 64-bit hash, in a 50 MB database, in a 16 GB database, in any
database ever built.

This is the part the prof asked about and the answer is an unqualified yes.

## Stage 1 — The *minimizer*: not necessarily the same, and this bit us

The hash is identical **given the same minimizer** — but the two databases were
not extracting the same minimizers.

`eskape_32bit_fork` was built by calling raw `build_db` with **no `-S`**, so its
`spaced_seed_mask = 0`. `standard_16gb` uses kraken2's default 7 spaces,
mask `4611686018212639539`. A spaced seed blanks out bases before hashing, so a
different mask reads a different subsequence from the same window.

Measured on this read: **0 of 717 minimizers in common.** Over 1,000 reads:
**0.043% overlap.** Effectively disjoint.

With the seed matched (`eskape_32bit_spaced`, same mask as the 16 GB build), the
16 GB minimizer set is a **perfect subset**: **154 of 154** of the read's
minimizers present in the small database were also found in the 16 GB one —
21.5%, which matches the 20.75% retention of its `-M` threshold exactly.

**This is why every cross-database comparison in this project must use
`eskape_32bit_spaced`, never `eskape_32bit_fork`.** The 16/20/24/32-bit series
is internally consistent, but it cannot be compared against anything
wrapper-built.

## Stage 3 — The key: **the same hash, truncated.** Not equal, but derived.

From `compact_hash.h`:

```cpp
compacted_key = hc >> (64 - key_bits_);     // top key_bits_ bits of the hash
data = compacted_key << value_bits;         // CompactHashCell::populate
data |= val;
```

`key_bits = cell_width − value_bits`. So the key is just **the top N bits of the
very same hash** — N differs between the databases:

| | 50 MB | 16 GB |
|---|---|---|
| cell width | 32 bit | 32 bit |
| value bits | 6 | 16 |
| **key bits** | **26** | **16** |
| key | `hc >> 38` | `hc >> 48` |

Worked example — minimizer **#298** of this read, traced by
`scripts/trace_minimizer.cc` (which links kraken2's own `mmscanner.o`,
`compact_hash.o` and `taxonomy.o`, so these are the values `classify` itself
computes; raw output in `result/flow_trace/`):

```
minimizer   82,351,934,865,027,616  = 0x012492a600323220   ← same in both
hash        0xfefd3172357af98a      = 18,373,896,421,334,776,202
                                      ** IDENTICAL IN BOTH **

              50 MB (26 key bits)            16 GB (16 key bits)
key         hc >> 38 = 0x3fbf4c5         hc >> 48 = 0xfefd
                     = 66,843,845                 =     65,277
slot        hc % 12,000,000              hc % 4,000,000,000
                     =  2,776,202                 = 1,334,776,202
probe       -- not in table --           slot 1,334,776,202, first probe
cell value  0                            6,762
taxid       0  (miss)                    taxo.k2d[6762] -> 286  Pseudomonas
```

and `66,843,845 >> 10 == 65,277`. **Verified for all 154 of 154 minimizers that
both databases actually looked up** (of this read's 717; the rest are
`-M`-skipped on one side or the other). The relation always holds:

> `key_16GB == key_50MB >> 10`

So: not the same number, but the **same hash with 10 fewer bits kept**. The
16 GB database stores a *coarser* fingerprint of the identical hash — which is
the tradeoff it makes to buy 10 more bits for the taxid value.

## Stage 4 — The slot: different, necessarily

The slot comes from the **low** bits of the hash (the key came from the high
bits), so the two are independent parts of the same number:

```
slot = hc % capacity                                  hash 0xfefd3172357af98a
  eskape_big_M12000000  hc % 12,000,000     =     2,776,202
  eskape_32bit_spaced   hc % 12,200,000     =    11,776,202
  standard_16gb         hc % 4,000,000,000  = 1,334,776,202
```

Same hash, different table size, so a different address. Nothing to reconcile —
this is just the modulus. (Note the two 50 MB databases differ from each other
here too: 12.0 M vs 12.2 M cells.)

## Stages 5–6 — The output: different, but it is granularity, not disagreement

Same read, three databases:

| database | call |
|---|---|
| `eskape_32bit_fork` (50 MB) | `C 208964` |
| `eskape_32bit_spaced` (50 MB) | `C 208964` |
| `standard_16gb` | `C 287` (*P. aeruginosa*) |

Across reads: only **1.8%** get an identical taxid, but **86.3% agree on
classified vs unclassified**. The small database resolves to the strain taxid it
happens to hold; the 16 GB one has the whole species tree and settles on the
species LCA. Both are "*P. aeruginosa*" to a biologist.

**And per *minimizer*, the 16 GB database is LESS specific, not more.** Of the
51 minimizers of this read that reach a taxid in both databases, **only 1
returns the same taxid.** The 16 GB answers are mostly `286` *Pseudomonas*
(genus) or higher, because its LCA was computed against ~14,000 species, so a
minimizer shared by several *Pseudomonas* species collapses to the genus. The
48 MB database knows only 7 species, has nothing to collapse against, and
answers `287` — **its apparent precision is partly an artefact of its own
ignorance.** The read still comes out `287` in both, because `ResolveTree`
(`classify.cc:738`) scores each taxon as the sum of its whole root-to-leaf path:
`score(287) = 460` against `score(286) = 439`, from only 21 direct species hits.
Worked out in full in `FLOW.md` §3.

**The most striking number from this check:** `eskape_32bit_fork` and
`eskape_32bit_spaced` agree on **99.1% of reads** while sharing only **0.02% of
their minimizers**. Two almost completely disjoint sets of evidence reach the
same answer — which says the classification is robust to *which* minimizers you
sample, as long as you sample enough of them. That is, independently, the
mechanism behind the Part 1 result.

## 2.6 Summary table for the slide

| stage | same in 50 MB and 16 GB? | why |
|---|---|---|
| minimizer | **no**, unless the spaced seed matches | different `-S` reads a different subsequence |
| **hash** | **yes, identical** | MurmurHash3 is a pure function of the minimizer |
| key | **truncation of the same hash** | `hc >> (64 − key_bits)`; 26 vs 16 bits |
| slot | no | `hc % capacity`; 12.2 M vs 4.0 B |
| cell value | no | **not a taxid** — an index into `taxo.k2d`; 6 vs 16 bits |
| taxid | usually no | 38 taxonomy nodes vs 47,011; different tree depth |
| read call | **usually yes** | all four databases call the example read `287` |

---

# Part 3 — Also worth mentioning: the 16 GB database is *faster*

Counter-intuitive and it holds up:

| | 50 MB | `standard_16gb` |
|---|---:|---:|
| runtime, pod5_15 | 0.511 s | **0.446 s** |
| classified | 83.39% | **97.60%** |
| hash lookups performed | 29.05 M | **6.02 M** |
| DRAM accesses per lookup | 0.96 | 2.06 |
| TLB walks per lookup | 0.94 | 1.00 |

The 16 GB database is **twice as expensive per lookup** — every single lookup
misses the TLB (3.9 M 4 KB pages against a 2,048-entry STLB, **1,907×
oversubscribed**, exactly 1.00 page walk per lookup) — but it **does 4.8× fewer
lookups**, because its `-M` threshold skips 79.25% of minimizers before they are
ever looked up. Skipping work beats doing work faster.

This is the same mechanism as Part 1 seen from the performance side, and it is
the project's main established result: **`-M` subsampling, not database size, is
why the big databases win.** Lookups run at IPC 0.218 against 1.714 for
everything else; `CompactHashTable::Get` is 43.4% of cycles.

Runtime over the 16-file sweep: 32.94 s (old 49 MB) / 41.20 s (208 MB) /
**28.62 s (48 MB)** / 22.33 s (16 MB). The 48 MB build is ~13% faster than the
old one at the same size. **Treat these as indicative only** — the sweep ran
sequentially and this box heat-soaks; a proper interleaved A/B on a cool machine
is still outstanding.

---

# What to say in the meeting

1. **Yes, the database was made bigger** — 175 complete genomes, 25 strains per
   species, all 6 ESKAPE letters including the *A. baumannii* that was missing.
2. **The best result is not the biggest database.** A 48 MB build from those
   175 genomes beats the old 48.8 MB six-genome database by **9.28 points**
   (83.73% → 93.01%, consistent across all 16 files) while storing **fewer**
   minimizers and running faster. **At fixed memory, breadth beats
   completeness.**
3. **208 MB gets 94.97%**, i.e. +1.96 pp more for 4.3× the memory.
   **16 MB is unusable** — it collapses 33 points under a confidence threshold.
4. **The hash is identical** between the 50 MB and 16 GB databases, verified on
   a real read. The **key is the same hash truncated** — 26 bits vs 16, and
   `key_16GB == key_50MB >> 10` held for every shared minimizer tested. The
   **minimizer** is only the same if the spaced seed matches, and ours did not,
   which is a trap now documented.
5. **Honest caveat:** these are classification rates, not correctness. ~950 of
   the 173,398 newly classified reads are spuriously called *A. baumannii*
   (183:1), caused by forced assignment in a 7-species database, not by hash
   collisions. The fix is a decoy set, not a smaller database.

## Next steps

- **Decoy set** — add human (GRCh38, already on disk) and a *Pseudomonas* phage.
  Should remove most of the 948.
- **Fix the *Enterobacter* species.** 9.3 M minimizers are labelled
  *E. cloacae* (taxid 550), but the sample's dominant *Enterobacter* is
  ***E. hormaechei*** (83 reads vs 36), which has 668 complete RefSeq assemblies
  to *cloacae*'s 82 and **zero** in our database. Five lines in the species map.
- **Interleaved timing run** on a cool box, to turn the ~13% speedup from
  indicative into a result.
- **Ground truth.** Everything so far is inter-database agreement used as a
  proxy. If this sample is a known mock community, labelled truth would convert
  all of these rates into actual sensitivity and specificity.

---

## Reproducing this

```bash
# the sweep behind Part 1
bash result/eskape_allpod5_T0/run.sh          # 64 runs, -T 0 -p 16 -g 2
cat result/eskape_allpod5_T0/REPORT.md        # per-taxon decomposition
cat result/eskape_allpod5_T0/PER_FILE_TABLES.md

# the database build behind it
bash scripts/build_eskape_big.sh              # downloads 175 genomes, builds 3 DBs

# false-positive arbitration (Part 1.7a)
ls result/eskape_fp_check/                    # dump_table inspects + 16 GB reference call
```

Backing documents: `ESKAPE_DB_REPORT.md` (readable),
`ESKAPE_DB_SCALING.md` (technical, with the `-M` ladder),
`SUBSAMPLING_FINDING.md` (why subsampling wins),
`ESKAPE_SIZE_LADDER.md` (13-database size series).
