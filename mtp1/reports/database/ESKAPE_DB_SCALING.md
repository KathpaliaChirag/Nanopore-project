# Scaling the ESKAPE database, and whether 50 MB and 16 GB agree

Prepared for the project meeting. Every number here is measured on the Dell box
(i7-11700, 31 GB RAM) on 2026-10-13, not estimated, unless marked as a projection.

Databases referenced:

| name | hash.k2d | cells | occupied | load | key/value bits | spaced seed | subsampling |
|---|---:|---:|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` | 48.8 MB | 12,200,000 | 8,903,388 | 73.0% | 26 / 6 | **0 (off)** | none |
| `eskape_32bit_spaced` | 48.8 MB | 12,200,000 | 8,871,274 | 72.7% | 26 / 6 | on | none |
| `standard_16gb` | 15.0 GB | 4,000,000,000 | 2,800,427,917 | 70.0% | 16 / 16 | on | **keeps 20.75%** |

All three share `k = 35`, `l = 31`, `toggle_mask = 16392584516609989165`,
`revcom_version = 1`.

---

## 1. Two things to correct first

### 1.1 Acinetobacter is missing from the "ESKAPE" database

`databases/eskape_cs/library/` holds **six genomes, one reference strain each**:

| taxid | organism |
|---|---|
| 333849 | *Enterococcus faecium* DO |
| 93061 | *Staphylococcus aureus* subsp. aureus NCTC 8325 |
| 1125630 | *Klebsiella pneumoniae* subsp. pneumoniae HS11286 |
| 716541 | *Enterobacter cloacae* subsp. cloacae ATCC 13047 |
| 208964 | *Pseudomonas aeruginosa* PAO1 |
| 511145 | *Escherichia coli* str. K-12 substr. MG1655 |

***Acinetobacter baumannii* — the A in ESKAPE — is absent**, and *E. coli*, which
is not an ESKAPE organism, is present. The database is accurately described as
**ESKAP + E. coli**, not ESKAPE.

### 1.2 The benchmark base uses a different minimizer definition from everything else

`CELLWIDTH_DB_BUILD.md` builds the cell-width series by calling `build_db`
directly with no `-S` flag, so `spaced_seed_mask = 0`. Every database built
through the `kraken2-build` wrapper uses the default 7 minimizer spaces
(`spaced_seed_mask = 4611686018212639539`).

Consequence: the 16/20/24/32-bit series is **internally consistent** (all four
share seed 0, so the cell-width comparisons are valid), but it is **not
comparable** to `standard_16gb`, `eskape_650mb`, `target_51MB`, or even
`eskape_32bit_spaced` — which is the same capacity and same library, differing
only in the seed.

**For any 50 MB vs 16 GB comparison the correct baseline is
`eskape_32bit_spaced`.**

---

## 2. Can the ESKAPE database be made bigger using the 16 GB one?

**Not by extracting from it.** Two independent blockers:

1. **The source sequences are gone.** `standard_16gb/` is a prebuilt download —
   it has `library_report.tsv`, `inspect.txt`, `ktaxonomy.tsv` and the
   `*.kmer_distrib` files, but **no `library/` directory**. There is nothing to
   re-extract and rebuild from.
2. **No tool reads minimizers back out.** `dump_table` emits per-taxon *counts*
   only, not (minimizer, taxid) pairs. Kraken2 has no supported "subset an
   existing index" operation.

And extraction would be the wrong goal even if possible: `standard_16gb` keeps
only **20.75%** of minimizers, while the current 50 MB database is **100%
complete** (`min_acceptable_hash_value = 0`). An extracted ESKAPE subset would be
roughly 5x sparser than what already exists.

### What the 16 GB database *is* good for: establishing the ceiling

`inspect.txt` gives clade minimizer counts per taxon. For the seven species:

| species | taxid | clade minimizers (in the subsampled DB) |
|---|---:|---:|
| *P. aeruginosa* | 287 | 2,811,077 |
| *K. pneumoniae* | 573 | 2,014,176 |
| *A. baumannii* | 470 | 1,320,565 |
| *S. aureus* | 1280 | 1,001,457 |
| *E. cloacae* | 550 | 926,961 |
| *E. faecium* | 1352 | 551,418 |
| *E. coli* | 562 | 4,572,600 |
| **total** | | **13,198,254** |

Correcting for the 20.75% retention gives a projected **~63.6 M minimizers** for
a complete multi-strain build — **7.1x** the current 8,903,388.

Projected size at 70% load factor (capacity ~91 M cells):

| cell width | size |
|---|---:|
| 32-bit | **364 MB** |
| 24-bit | 273 MB |
| 16-bit | 182 MB |

### The route that does work

Download additional strains per species from NCBI RefSeq and rebuild, adding
*A. baumannii*. Build flags follow `CELLWIDTH_DB_BUILD.md`, with capacity raised:

```
-c 91000000 -k 35 -l 31 -p 1 -C 32
```

`-p 1` remains mandatory — multi-threaded `build_db` segfaults on this hardware.
Disk headroom is 118 GB and RAM is 31 GB, both ample.

---

## 3. Does the same read produce the same hash, key and output?

Measured on the same 1,000 reads from `pod5_15.fastq` through all three
databases.

| quantity | same across 50 MB and 16 GB? |
|---|---|
| **MurmurHash3 value** | **Yes** — a pure function of the minimizer, entirely independent of the database |
| **the minimizer**, fork vs 16 GB | **No** — `spaced_seed_mask` 0 vs nonzero gives **0.043% overlap** |
| **the minimizer**, seed matched | **Yes** — see below |
| **stored key (fingerprint)** | **No, but deterministically related** — see 3.2 |
| **slot index** | **No** — `hc % 12,200,000` vs `hc % 4,000,000,000` |
| **stored value** | **No** — 6 value bits vs 16, and different taxonomy namespaces |
| **output taxid** | **No** — identical on **1.8%** of reads |

### 3.1 The minimizer depends on the spaced seed, not on the database size

Same 1,016 reads, minimizer sets compared directly:

| | distinct minimizers |
|---|---:|
| `eskape_32bit_fork` (seed off) | 876,709 |
| `eskape_32bit_spaced` (seed on) | 873,286 |
| intersection | **348 (0.02% of union)** |

With the seed matched, agreement is exact. `standard_16gb`'s minimizer set is a
**perfect subset** of `eskape_32bit_spaced`'s — **181,049 of 181,049** — and
amounts to **20.73%** of it, against 20.75% predicted from
`min_acceptable_hash_value`. That gap is the subsampling filter, not any
difference in hashing.

### 3.2 The 16 GB key is a truncation of the 50 MB key

`CompactHashTable::Get` computes the stored key as `hc >> (64 - key_bits)`:

- 50 MB database: `key_bits = 26` -> `hc >> 38`
- 16 GB database: `key_bits = 16` -> `hc >> 48`

So for any minimizer present in both, the keys are related by a shift. Verified
over all 181,049 shared minimizers:

```
key_16GB == key_50MB >> 10      ->  true for 181,049 / 181,049
```

| minimizer | MurmurHash3 (identical) | 50 MB key (26 b) | 16 GB key (16 b) | 26 b >> 10 |
|---:|---:|---:|---:|---:|
| 32 | 14705810856284692349 | 53,499,428 | 52,245 | 52,245 |
| 49 | 14956449454263868849 | 54,411,246 | 53,135 | 53,135 |
| 51 | 15829663973472409806 | 57,587,982 | 56,238 | 56,238 |

The 16 GB database retains **10 fewer fingerprint bits**, so it discriminates
1,024x less per lookup — the cost of spending those bits on a 16-bit taxid field
instead.

### 3.3 The output differs, because the taxonomies differ

| database | classified (of 1,000) |
|---|---:|
| `eskape_32bit_fork` | 841 (84.1%) |
| `eskape_32bit_spaced` | 850 (85.0%) |
| `standard_16gb` | **979 (97.9%)** |

Per-read agreement:

| comparison | identical taxid | same classified/unclassified |
|---|---:|---:|
| spaced 50 MB vs 16 GB | 18 / 1,000 (1.8%) | 863 (86.3%) |
| fork 50 MB vs 16 GB | 19 / 1,000 (1.9%) | 856 (85.6%) |
| fork 50 MB vs spaced 50 MB | **991 / 1,000 (99.1%)** | 991 (99.1%) |

The 1.8% is a granularity effect, not disagreement: the ESKAPE database can only
answer within its six-strain tree and returns strain taxids (`208964` =
*P. aeruginosa* PAO1), while the 16 GB database returns species or genus (`287` =
*P. aeruginosa*, `570` = *Klebsiella*). Both are correct at different depths.

### 3.4 The result worth leading with

**`eskape_32bit_fork` and `eskape_32bit_spaced` agree on 99.1% of reads while
sharing only 0.02% of their minimizers.**

Identical genomes, almost disjoint minimizer sets, nearly identical biological
answer. The spaced seed changes the entire lookup mechanism and barely changes
the result.

The implication for this project: a seed mismatch is harmless when comparing
*sensitivity*, but this project measures *hash-level behaviour* — cell widths,
cache residency, lookup counts, TLB pressure. Those all differ. Hence the
baseline correction in 1.2.

---

## 4. Performance at 16 GB, and what it means for the optimisation work

Measured on `pod5_15.fastq`, `-p 16 -g 2 -T 0`, with the 15 GB load cost
subtracted via a load-only run on a 1,000-read input.

| | 50 MB `eskape_32bit_fork` | 15 GB `standard_16gb` |
|---|---:|---:|
| classify time | 0.511 s | **0.446 s** |
| sequences classified | 83.39% | **97.60%** |
| hash lookups | 29.05 M | **6.02 M** |
| DRAM accesses per lookup | 0.96 | **2.06** |
| TLB page walks per lookup | 0.94 | **1.00** |
| DRAM stall, % of cycles | 27.4% | 19.9% |
| page walk active, % of cycles | 40.9% | 12.4% |
| 4 KB pages to map | 11,914 | 3,906,250 |
| STLB (2,048 entries) oversubscription | 5.8x | **1,907x** |

The 16 GB database is **both faster and far more sensitive**. It is not better at
memory — per lookup it is roughly twice as expensive — but it performs **4.8x
fewer lookups**, because it keeps only 20.75% of minimizers.

**That is the same mechanism as our `-M 4000000` result (-26.7%).** Upstream
`kraken2-build` already applies it when capping capacity. This should be stated
plainly rather than presented as a novel optimisation.

Two consequences for the remaining work:

- **L3 residency does not transfer.** 15 GB against a 16 MB L3 is ~1,000x over;
  there is nothing to fit. The `-M` win is a property of a 28 Mbp reference, as
  `CACHE_TABLE_ANALYSIS.md` already noted.
- **The TLB finding gets much stronger.** Every lookup misses the TLB at 16 GB
  (exactly 1.00 walk per lookup). In 2 MB pages the database needs 7,630 pages
  instead of 3,906,250. Huge pages are a far larger lever at 16 GB than at 50 MB,
  and remain untested.

---

## 5. Recommendations

1. **Rename or re-scope the database.** Either add *A. baumannii* or stop calling
   it ESKAPE.
2. **Use `eskape_32bit_spaced` for any cross-database comparison.** Keep
   `eskape_32bit_fork` only as the base of the cell-width series.
3. **Build the ~364 MB multi-strain ESKAPE database** by downloading more RefSeq
   strains, not by extracting from the 16 GB index — which is impossible and
   would be sparser anyway.
4. **Present `-M` as confirming an upstream design choice**, not as a new trick.
5. **Test huge pages**, which is one `madvise` line and matters far more at 16 GB.

---

## 6. The bigger database, built

Not extracted from the 16 GB index (impossible, section 2) but rebuilt from
NCBI RefSeq. Downloaded **175 complete genomes — 25 per species across all seven
organisms, with *A. baumannii* now included** — selected reference/representative
first, then evenly spaced through the remaining complete assemblies for strain
diversity rather than submission-date clustering.

| | old | new |
|---|---:|---:|
| genomes | 6 | **175** |
| sequence | 28 Mbp | **812.9 Mbp** (29x) |
| distinct minimizers | 8,903,388 | **36,122,368** (4.1x) |
| capacity at 70% load | 12,200,000 | **52,000,000** |
| 32-bit `hash.k2d` | 48.8 MB | **208 MB** |

Available complete+latest RefSeq assemblies, for reference — the 25 taken per
species is a small fraction, so this can be grown further:

| species | complete genomes available |
|---|---:|
| *E. coli* | 5,463 |
| *K. pneumoniae* | 3,709 |
| *S. aureus* | 2,101 |
| *P. aeruginosa* | 1,627 |
| *A. baumannii* | 1,103 |
| *E. faecium* | 428 |
| *E. cloacae* | 82 |

### 6.1 Minimizer count saturates fast

Measured with `estimate_capacity -k 35 -l 31` and the correct spaced seed:

| strains/species | genomes | Mbp | distinct minimizers | 32-bit DB |
|---:|---:|---:|---:|---:|
| 1 | 7 | 30.6 | 9,861,888 | 56 MB |
| 2 | 14 | 63.8 | 13,583,360 | 78 MB |
| 5 | 35 | 163.4 | 19,676,672 | 112 MB |
| 10 | 70 | 327.5 | 26,487,040 | 151 MB |
| **25** | **175** | **812.9** | **36,122,368** | **206 MB** |

**26x more sequence buys only 3.7x more minimizers** — growth goes roughly as
`n^0.4` (Heaps' law). Strains of a species share their core genome; only the
accessory genome adds new minimizers. Extrapolating that exponent to every
available complete genome (~2,070 per species average) projects **~200 M
minimizers, about a 1.2 GB database** — the practical ceiling for a complete
multi-strain ESKAPE index.

That is larger than the ~63.6 M projected in section 2 from the 16 GB index, and
the difference is informative: `inspect.txt` clade counts exclude minimizers that
the standard database assigns to *higher* ranks (genus, family) because they are
shared with non-ESKAPE relatives. In a standalone ESKAPE database those same
minimizers resolve to within-ESKAPE LCAs and do get counted. So **63.6 M is a
floor, ~200 M is the ceiling.**

### 6.2 Build parameters

The spaced seed template was derived from `kraken2-build` line 347
(`"1" x (l - 2*spaces)` then `"01" x spaces`, with `spaces = 7` for nucleotide
databases) and verified to reproduce the mask stored in every wrapper-built
database on this box:

```
template "1111111111111111101010101010101"
  -> strtol base 2        = 2,147,472,725
  -> ExpandSpacedSeedMask = 4,611,686,018,212,639,539   == standard_16gb  ✓
```

```bash
cat library/*.fna | build_db \
    -H hash.k2d -t taxo.k2d -o opts.k2d \
    -n taxonomy -m seqid2taxid.map \
    -c 52000000 -k 35 -l 31 -p 1 \
    -S 1111111111111111101010101010101
```

Notes:
- **Spaced seed ON**, matching the kraken2 default and `standard_16gb`. This
  makes the new database comparable to `eskape_32bit_spaced` and the standard
  indexes. A `spaced_seed_mask = 0` variant would be needed for direct comparison
  against the `eskape_32bit_fork` cell-width series — worth building as a second
  database rather than choosing one.
- `-C` is not passed: `kraken2_bin/build_db` is the stock binary and 32-bit cells
  are its default. The patched `build_db` in `kraken2/src` is only needed for
  16/20/24-bit widths.
- `-p 1` per the known multi-threaded segfault on this hardware.
- Taxonomy is the full NCBI `taxdump` (`nodes.dmp` 232 MB, `names.dmp` 317 MB),
  not the 6-strain subset, so species-level taxids resolve correctly.
- Sequences are mapped to **species** taxids (1352, 1280, 573, 470, 287, 550,
  562), not strain taxids, so the database answers at species level.

### 6.3 What this does and does not settle

A 208 MB database still fits comfortably in RAM and still **exceeds the 16 MB L3
by 13x**, so it does not resurrect the L3-residency idea. Its value is
scientific, not architectural: seven organisms instead of six (with the actual
ESKAPE set), 25 strains instead of one, so classification is no longer restricted
to a single reference strain per species. It also gives a middle point between
50 MB and 15 GB for the cell-width and TLB measurements, which previously had a
300x gap in the middle.

---

## 7. Results: all six databases, both thresholds

`pod5_15.fastq`, `-p 16 -g 2`. "skip" is the fraction of minimizers never looked
up, from `min_acceptable_hash_value`.

| database | size | skip | `-T 0` | time | `-T 0.05` | time |
|---|---:|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` | 49 MB | 0% | 83.39% | 0.526 s | 79.89% | 0.527 s |
| `eskape_32bit_spaced` | 49 MB | 0% | 84.42% | 0.538 s | 80.45% | 0.541 s |
| `eskape_big_M4000000` | **16 MB** | 92.3% | 87.98% | **0.315 s** | **54.61%** | 0.315 s |
| **`eskape_big_M12000000`** | **48 MB** | 76.9% | **92.93%** | **0.401 s** | **87.09%** | 0.391 s |
| `eskape_big` | 208 MB | 0% | 94.99% | 0.583 s | 91.72% | 0.581 s |
| `standard_16gb` | 16,000 MB | 79.2% | 97.60% | 0.486 s | 93.56% | 0.432 s |

All `eskape_big*` variants are built from the same 175-genome library and differ
only in `-M`. Occupancy is 69.3% in all three, so the comparison is clean.

### 7.1 The headline: breadth beats completeness

**`eskape_big_M12000000` is the same 48 MB as the current database, and is both
+8.5 points more sensitive and 25% faster.**

| | `eskape_32bit_spaced` | `eskape_big_M12000000` | change |
|---|---:|---:|---:|
| file size | 48.8 MB | 48.0 MB | same |
| cells | 12,200,000 | 12,000,000 | same |
| source genomes | 6 | **175** | 29x |
| minimizers stored | 8,871,274 | 8,316,093 | slightly fewer |
| classified, `-T 0` | 84.42% | **92.93%** | **+8.51 pp** |
| classified, `-T 0.05` | 80.45% | **87.09%** | **+6.64 pp** |
| runtime | 0.538 s | **0.401 s** | **-25.5%** |

It stores *fewer* minimizers yet classifies far more reads, because **23% of 175
strains covers more biology than 100% of 6 strains**. For a fixed memory budget,
sampling a broad library beats exhaustively indexing a narrow one.

**Relationship to existing work.** `reports/findings/SUBSAMPLING_FINDING.md`
already established that `-M` is why a 7.6 GB database beats a 47 MB one, via
the IPC decomposition (lookups at IPC 0.218 vs 1.714 for everything else), and
`reports/database/ESKAPE_SIZE_LADDER.md` measured 13 `-M` databases on the
6-genome library. This section does not restate those results.

What is added here is **separation of two variables that were previously
confounded**. The earlier comparison was across different libraries, so
subsampling and reference breadth moved together. The three `eskape_big*`
databases share one 175-genome library and differ only in `-M`, isolating it:

- 6-genome library: `-M` cost 1.3 pp of sensitivity (83.39% -> 82.07%)
- 175-genome library: `-M` **gains** 8.5 pp

So the lever is neither cache residency nor lookup-skipping alone — it is what
the cells are spent on. With a narrow reference, cells surrendered to
subsampling are lost outright; with a broad one they buy diversity.

### 7.2 Aggressive subsampling is incompatible with confidence thresholding

`eskape_big_M4000000` (16 MB, L3-resident) is the fastest database measured —
**0.315 s, 40% faster than the current one** — and still more sensitive at
`-T 0` (87.98% vs 84.42%). But at `-T 0.05` it **collapses to 54.61%**, a 33
point fall where every other database loses only 3-4 points.

The cause is in `classify.cc:743`:

```c
uint32_t required_score = ceil(opts.confidence_threshold * total_minimizers);
```

with `total_minimizers = taxa.size()` (line 882). Skipped minimizers still push
`taxon = 0` into `taxa`, so they **inflate the denominator while contributing
nothing to the numerator**. At a 92.3% skip rate the confidence score is
computed over roughly 13x more minimizers than were ever looked up, and almost
no read clears the bar.

Consequences:

- **Any `-M` database must be validated at the threshold it will be used with.**
  Reporting only `-T 0` makes aggressive subsampling look far better than it is.
- The effect is strongly non-linear: 76.9% skip costs 5.8 pp (92.93 -> 87.09),
  while 92.3% skip costs 33.4 pp. There is a usable range and a cliff, and the
  cliff sits between them.
- `standard_16gb` at 79.2% skip loses 4.0 pp, consistent with the usable range.

### 7.3 Where this leaves the project

- **A 208 MB ESKAPE database reaches 94.99%, within 2.6 pp of the 15 GB standard
  index at 1/72 the size** (within 1.8 pp at `-T 0.05`). The residual gap is
  organisms genuinely outside ESKAPE.
- **For a drop-in replacement, `eskape_big_M12000000` dominates the current
  database on every axis**: same size, faster, more sensitive at both thresholds.
- The fastest option is 16 MB and L3-resident, but only usable at `-T 0`.
- Completeness and cache residency remain in tension: the complete 208 MB
  database is still 13x larger than L3 and is the slowest of the six.

### 7.4 Recommended next steps

1. Confirm 7.1 across the remaining 15 pod5 files before relying on it.
2. Measure false positives, not just classification rate — the original
   `-M 4000000` work tracked *S. aureus* FP and found 0; that check has not been
   repeated on these databases.
3. Sweep `-M` between 8 M and 16 M cells to locate the threshold cliff in 7.2.
4. Build a `spaced_seed_mask = 0` variant of `eskape_big` if the cell-width
   series is to be extended to the larger library.
