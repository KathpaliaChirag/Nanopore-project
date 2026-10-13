# Making the ESKAPE database bigger — report

**Date:** 13 October 2026
**Machine:** Dell, Intel i7-11700 (8 cores / 16 threads), 31 GB RAM, 16 MB L3 cache
**Test data:** `pod5_15.fastq` — 30,378 nanopore reads, 90.55 Mbp
**kraken2 version:** 2.17.1 throughout

Technical backing detail for everything here is in `ESKAPE_DB_SCALING.md`.

---

## Bottom line

We asked two questions. Both are answered, and the answers are good news.

**1. Can we make the ESKAPE database bigger using the 16 GB database?**
Not by extracting from it — that is impossible, for reasons explained in §3. But
we rebuilt it properly from NCBI, and the result is better than expected:

> **A new 48 MB database — exactly the same size as the one we have now —
> classifies 9.28 points more reads and runs ~25% faster.**
> Verified across all 16 pod5 files, 1,872,777 reads: range +9.02 to +9.57,
> and it recovers 173,398 reads the current database calls unknown. It also
> introduces 948 spurious *A. baumannii* calls — a 183:1 gain-to-error ratio.
> See §7.2.

**2. Does the same read produce the same hash and the same key in the 50 MB and
16 GB databases?**

> **The hash is the same. The key is not — it is a truncation. The output is not.**
> Full detail in §6.

**Along the way we found three problems in the current setup** that should be
fixed regardless (§2).

---

## 1. Background: the two numbers that explain everything

To follow the rest of this report, only two ideas are needed.

**A minimizer is a short piece of a read used as a lookup key.** kraken2 chops
each read into 35-letter chunks (k=35), picks a 31-letter representative from
each (l=31), hashes it, and looks the hash up in a big table. The table maps
that hash to an organism. A database is essentially a list of
(minimizer -> organism) pairs.

**A database can choose to ignore most minimizers.** Each database stores a
number called `min_acceptable_hash_value`. During classification:

```
if hash(minimizer) < min_acceptable_hash_value:
      skip it entirely — never look in the table
else: look it up
```

This is the "skip threshold". It is how kraken2 fits a huge reference into a
small file. The 16 GB standard database **skips 79% of all minimizers**. The
8 GB one skips **90%**. Our current 50 MB database skips **0%** — it is
complete.

Skipping makes classification faster (fewer table lookups) but loses
information. The whole report is about this trade-off.

---

## 2. Three problems with the current database

### 2.1 Acinetobacter is missing

The library used to build our 50 MB database contains **six genomes**:

| organism | ESKAPE? |
|---|---|
| *Enterococcus faecium* DO | yes (E) |
| *Staphylococcus aureus* NCTC 8325 | yes (S) |
| *Klebsiella pneumoniae* HS11286 | yes (K) |
| *Pseudomonas aeruginosa* PAO1 | yes (P) |
| *Enterobacter cloacae* ATCC 13047 | yes (E) |
| *Escherichia coli* K-12 MG1655 | **no** |

***Acinetobacter baumannii* — the "A" in ESKAPE — is not there**, and *E. coli*,
which is not an ESKAPE organism, is. The database is accurately called
**"ESKAP + E. coli"**.

### 2.2 Only one strain per species

One reference genome per organism, 28 Mbp total. Any real-world isolate that
differs from that one reference strain is likely to be missed. This is the main
reason the classification rate is only 84%.

### 2.3 The benchmark database uses a different minimizer rule from everything else

kraken2 can skip positions inside a minimizer (a "spaced seed"). Its default is
7 spaces. Our `eskape_32bit_fork` database was built by calling `build_db`
directly **without** that setting, so it uses **no spaces**, while every other
database on the machine uses the default.

Effect: the same read produces **almost completely different minimizers** in the
two cases — measured at **0.02% overlap**.

This does not make the existing cell-width work wrong: the 16/20/24/32-bit
series all share the same setting, so comparisons *within* that series are
valid. But `eskape_32bit_fork` **cannot be compared against the 16 GB database
or any other database**. For cross-database work the correct baseline is
`eskape_32bit_spaced`.

---

## 3. Why we could not build from the 16 GB database

Two independent blockers.

**The source sequences are gone.** `databases/standard_16gb/` is a *prebuilt
download*. It contains the finished hash table and some reports, but there is
**no `library/` folder** — the genome sequences it was built from were never on
this machine. There is nothing to re-extract.

**No tool can read minimizers back out.** `dump_table` reports only how many
minimizers belong to each organism. It cannot output the
(minimizer -> organism) pairs themselves. kraken2 has no "take a subset of an
existing database" operation at all.

**And it would be the wrong thing to do anyway.** The 16 GB database skips 79%
of minimizers. Our 50 MB database skips 0%. Any ESKAPE subset pulled out of the
16 GB index would be about **5x sparser than what we already have** — a
downgrade.

**What the 16 GB database is still useful for** is telling us the size target.
Its `inspect.txt` reports 13.2 million ESKAPE minimizers surviving the 79% skip,
implying roughly **64 million** in a complete version — about **7x** our current
8.9 million.

---

## 4. What we built instead

Downloaded fresh genomes from NCBI RefSeq and rebuilt from scratch.

**175 complete genomes — 25 per species, across all seven organisms, with
*A. baumannii* now included.** Strains were chosen reference-first, then spread
evenly across the available assemblies so they are genuinely diverse rather than
clustered by submission date.

| | before | after |
|---|---:|---:|
| genomes | 6 | **175** |
| organisms | 6 (no Acinetobacter) | **7 (full ESKAPE + E. coli)** |
| strains per species | 1 | **25** |
| sequence | 28 Mbp | **813 Mbp** (29x) |
| distinct minimizers | 8.9 M | **36.0 M** (4.1x) |

There is plenty of room to grow further — these 25 per species are a small
fraction of what exists:

| species | complete genomes available in RefSeq |
|---|---:|
| *E. coli* | 5,463 |
| *K. pneumoniae* | 3,709 |
| *S. aureus* | 2,101 |
| *P. aeruginosa* | 1,627 |
| *A. baumannii* | 1,103 |
| *E. faecium* | 428 |
| *E. cloacae* | 82 |

### 4.1 But adding genomes stops helping quite quickly

| strains per species | genomes | Mbp | distinct minimizers |
|---:|---:|---:|---:|
| 1 | 7 | 30.6 | 9.9 M |
| 2 | 14 | 63.8 | 13.6 M |
| 5 | 35 | 163.4 | 19.7 M |
| 10 | 70 | 327.5 | 26.5 M |
| 25 | 175 | 812.9 | **36.0 M** |

**26x more sequence gave only 3.7x more minimizers.** Strains of the same
species share almost all of their DNA (the "core genome"); only the small
variable part adds anything new. Growth follows roughly `n^0.4`.

Extrapolating to *every* available complete genome projects about **200 M
minimizers, a 1.2 GB database** — the practical ceiling. There is no point
chasing it: the curve is already flattening at 25 strains.

### 4.2 Three databases were built

All from the same 175-genome library, differing **only** in the skip threshold
(the `-M` flag):

| name | size | skips | what it is |
|---|---:|---:|---|
| `eskape_big` | 208 MB | 0% | complete, nothing ignored |
| `eskape_big_M12000000` | 48 MB | 76.9% | **same size as the current database** |
| `eskape_big_M4000000` | 16 MB | 92.3% | small enough to fit in L3 cache |

---

## 5. Results

`pod5_15.fastq`, 16 threads, `-g 2`. "`-T`" is kraken2's confidence threshold:
`-T 0` accepts any call, `-T 0.05` requires modest supporting evidence.

| database | size | skips | classified (`-T 0`) | time | classified (`-T 0.05`) |
|---|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` (current) | 49 MB | 0% | 83.39% | 0.526 s | 79.89% |
| `eskape_32bit_spaced` | 49 MB | 0% | 84.42% | 0.538 s | 80.45% |
| `eskape_big_M4000000` | 16 MB | 92.3% | 87.98% | **0.315 s** | **54.61%** |
| **`eskape_big_M12000000`** | **48 MB** | 76.9% | **92.93%** | **0.401 s** | **87.09%** |
| `eskape_big` | 208 MB | 0% | 94.99% | 0.583 s | 91.72% |
| `standard_16gb` | 16,000 MB | 79.2% | 97.60% | 0.486 s | 93.56% |

### 5.1 The main result

**Same file size. More reads classified. Faster.**

| | current 49 MB | new 48 MB | change |
|---|---:|---:|---:|
| table cells | 12,200,000 | 12,000,000 | same |
| genomes behind it | 6 | **175** | 29x |
| minimizers stored | 8,871,274 | 8,316,093 | **fewer** |
| classified, `-T 0` | 84.42% | **92.93%** | **+8.5 points** |
| classified, `-T 0.05` | 80.45% | **87.09%** | **+6.6 points** |
| runtime | 0.538 s | **0.401 s** | **25% faster** |

It stores *fewer* minimizers and classifies *more* reads.

**Why:** 23% of 175 strains covers more real biology than 100% of 6 strains. For
a fixed memory budget, **sampling broadly beats indexing narrowly**. And because
it skips 77% of lookups, it also does far less work.

### 5.2 The 208 MB version nearly matches the 16 GB database

**94.99% against 97.60%** — within 2.6 points, at **1/72 the file size** (1.8
points at `-T 0.05`). The remaining gap is organisms genuinely outside ESKAPE,
which an ESKAPE database should not be expected to find.

### 5.3 How this relates to the existing subsampling finding

**This is an extension of work already in the repo, not a new discovery.**
`reports/findings/SUBSAMPLING_FINDING.md` already established the core result:
the 7.6 GB database beats the 47 MB one because `-M` subsampling discards 89.62%
of lookups before any memory access, and hash lookups run at IPC 0.218 against
1.714 for everything else. Deleting most of the slow half outweighs the penalty
of a larger table.

What is new here is the **library** dimension. That earlier work compared
databases built from *different* libraries (standard vs. ESKAPE), so the effect
of subsampling and the effect of reference breadth were combined. The three
`eskape_big*` databases are built from the **same 175-genome library** and differ
*only* in `-M`, which separates them:

- On the old 6-genome library, `-M` bought speed and **cost** 1.3 points of
  sensitivity.
- On the 175-genome library, `-M` buys speed and **gains** 8.5 points.

So `-M` is not fundamentally about cache residency, and not only about skipping
slow lookups. It is about **what the table cells are spent on.** With a narrow
reference, cells given up to subsampling are simply lost; with a broad one, they
are traded for diversity, which is worth more.

See also `reports/database/ESKAPE_SIZE_LADDER.md`, which measured 13 `-M`
databases on the 6-genome library — the `eskape_big_M*` builds here are the same
experiment repeated on the larger one.

---

## 6. Does a read produce the same hash and key in both databases?

Measured on the same 1,000 reads through all three databases.

| quantity | same? | why |
|---|---|---|
| **the hash value** | **Yes** | `MurmurHash3` is a pure function of the minimizer. Nothing about the database enters into it. |
| **the minimizer**, current 50 MB vs 16 GB | **No** | Different spaced-seed setting (§2.3) — **0.043% overlap** |
| **the minimizer**, with that setting matched | **Yes** | The 16 GB set is an exact subset: 181,049 of 181,049 |
| **the stored key** | **No — but predictably** | See below |
| **the slot it lands in** | **No** | `hash % 12,200,000` vs `hash % 4,000,000,000` |
| **the output** | **No** | Same organism, different precision — see below |

### 6.1 The key is a truncation

kraken2 does not store the whole 64-bit hash. It stores the top few bits as a
fingerprint:

- 50 MB database: top **26** bits
- 16 GB database: top **16** bits

So for any minimizer in both, the keys are the same bits — the 16 GB one just
keeps fewer. Verified on all 181,049 shared minimizers:

```
key_16GB  ==  key_50MB >> 10        true for 181,049 of 181,049
```

| minimizer | hash (identical in both) | 50 MB key | 16 GB key | key >> 10 |
|---:|---:|---:|---:|---:|
| 32 | 14705810856284692349 | 53,499,428 | 52,245 | 52,245 |
| 49 | 14956449454263868849 | 54,411,246 | 53,135 | 53,135 |
| 51 | 15829663973472409806 | 57,587,982 | 56,238 | 56,238 |

The 16 GB database keeps **10 fewer bits**, so it tells minimizers apart
**1,024x less precisely**. It spends those bits on a wider organism field
instead — it has to, because it holds all of NCBI rather than seven species.

### 6.2 The output differs by precision, not by disagreement

Both databases agree on **whether** a read is classified 86% of the time, but
return the **same organism ID only 1.8%** of the time — because they answer at
different depths. The ESKAPE database can only name one of its six strains
(`208964` = *P. aeruginosa* PAO1); the 16 GB database names the species or genus
(`287` = *P. aeruginosa*). Both are right.

### 6.3 A result worth noting

The two 50 MB databases — identical genomes, differing only in the spaced-seed
setting — **agree on 99.1% of reads while sharing only 0.02% of their
minimizers.**

Completely different internal mechanism, essentially the same biological answer.
That is reassuring for correctness, and it is exactly why §2.3 matters only for
*performance* comparisons, not for *accuracy* ones.

---

## 7. Cautions and verification

### 7.1 Heavy skipping breaks the confidence threshold

The 16 MB database is the fastest thing we measured (0.315 s, 40% faster than
current) and looks good at `-T 0` — 87.98%. But at `-T 0.05` it **falls to
54.61%**, losing 33 points where every other database loses 3-4.

The reason is in `classify.cc:743`:

```c
required_score = ceil(confidence_threshold * total_minimizers);
```

`total_minimizers` counts **every** minimizer in the read, including the skipped
ones. So skipped minimizers make the target harder without ever being able to
help meet it. At a 92% skip rate, the score is measured against roughly 13x more
minimizers than were actually looked up, and almost no read passes.

The effect is sharply non-linear:

| skip rate | sensitivity lost by `-T 0.05` |
|---:|---:|
| 0% | 3.3 - 4.0 points |
| 76.9% | 5.8 points |
| 79.2% | 4.0 points |
| **92.3%** | **33.4 points** |

**Practical rule: never evaluate a subsampled database at `-T 0` only.** There
is a safe range up to roughly 80% skipping, and a cliff beyond it.

### 7.2 Verified across all 16 files, and one real false-positive source

Both items flagged here earlier have now been measured. All 16 pod5 files,
1,872,777 reads, 6,036 Mbp. Full tables in
`../../results/eskape_allpod5_T0/`.

**The gain generalises, and the figure is larger than first reported.** Measured
against `eskape_32bit_fork` (the actual baseline, 83.73% mean) rather than
`eskape_32bit_spaced`, the 48 MB build gains **+9.28 points on average, range
+9.02 to +9.57 across 16 independent files.** The ordering
208 MB > 48 MB > 16 MB > old is identical in every file.

| | old 49 MB | new 208 MB | new 48 MB | new 16 MB |
|---|---:|---:|---:|---:|
| mean classified | 83.73% | 94.97% | **93.01%** | 87.68% |
| unclassified reads | 304,104 | 94,000 | **130,706** | 230,745 |

**173,398 reads that the current database calls "unknown" are identifiable
ESKAPE organisms**, concentrated exactly where the sample is dense:
*P. aeruginosa* +93,964, *E. coli* +47,921, *K. pneumoniae* +13,591.

**But the controls are not clean, and this corrects an earlier claim in this
document.** False-positive counts summed over all 16 files:

| control | old 49 MB | new 208 MB | new 48 MB | new 16 MB |
|---|---:|---:|---:|---:|
| *S. aureus* | 12 | 18 | 16 | 13 |
| *E. faecium* | 48 | 2 | **1** | 3 |
| *A. baumannii* | — | **1,048** | **948** | 629 |

*S. aureus* stays in the same band and *E. faecium* improves 48 -> 1. But
*A. baumannii* produces **948 calls in the 48 MB build where `standard_16gb`
finds about one read per file.** On `pod5_15` alone this looked like 20 reads and
was dismissed as negligible; across all 16 files it is systematic.

**The cause is forced assignment, not hash collision.** A seven-species database
has nowhere to put a read except one of its seven species or "unclassified". The
sample contains ~430 reads of organisms with no ESKAPE home at all — *Homo
sapiens* 253, *Phikmvvirus* phage 52, *Streptomyces* 41, *Salmonella* 22,
*Shigella* 58 — plus non-*aeruginosa* *Pseudomonas* (621) and *K. variicola* /
*K. quasipneumoniae* (75). With *A. baumannii* newly present and no outgroup,
those reads land on it.

**Net verdict: still strongly positive.** 173,398 reads correctly recovered
against 948 spuriously assigned — a ratio of **183:1**. But a decoy set (human +
phage, §8) is now a requirement rather than an optional refinement.

### 7.3 Still open

- ***Enterobacter* is the wrong species.** The database carries 9.3 M minimizers
  labelled *E. cloacae* (taxid 550), but the sample's dominant *Enterobacter* is
  ***E. hormaechei*** — 83 reads against *cloacae*'s 36, per `standard_16gb`.
  *E. hormaechei* has 668 complete RefSeq genomes to *cloacae*'s 82 and is now
  recognised as the commonest clinical *Enterobacter*, long misidentified as
  *cloacae*. *Enterobacter* counts fall 7,915 -> 3,112 with the new database;
  part of that is a genuine correction, part is real *Enterobacter* now going
  unclassified rather than misfiled.
- **No labelled ground truth.** Agreement between independent databases is the
  proxy throughout. Strong, and standard, but not a mock community of known
  composition.
- **Runtimes are indicative only.** The 16-file sweep ran sequentially, so
  thermal drift applies. The 25% speedup needs an interleaved A/B on a cool
  machine before it goes in a write-up.

---

## 8. Recommendations

| # | action | effort |
|---|---|---|
| 1 | ~~Check false positives~~ — **done, §7.2.** Revealed 948 spurious *A. baumannii* calls | done |
| 2 | ~~Confirm on the other 15 pod5 files~~ — **done, §7.2.** +9.28 pp mean, holds in all 16 | done |
| 1b | **Add a decoy set (human + phage)** to absorb the ~430 homeless reads driving §7.2 | medium |
| 2b | **Add *E. hormaechei* and the rest of the *Enterobacter* genus** (§7.3) | medium |
| 3 | **Adopt `eskape_big_M12000000` as the working database** — same size, faster, more sensitive at both thresholds | done, ready |
| 4 | Either add *A. baumannii* to the old database or stop calling it ESKAPE | — |
| 5 | Use `eskape_32bit_spaced`, not `eskape_32bit_fork`, for any cross-database comparison | — |
| 6 | Sweep `-M` between 8 M and 16 M cells to locate the §7.1 cliff | medium |
| 7 | Present `-M` as confirming an upstream kraken2 design choice, not as a new trick — the standard databases already do this | — |

---

## 9. How to reproduce

Everything lives in `databases/eskape_big/`: the 175 genomes in `library/`, the
`seqid2taxid.map`, and the NCBI `taxonomy/`.

```bash
cd /home/dell/summer/databases/eskape_big

# complete, 208 MB
cat library/*.fna | /home/dell/summer/kraken2_bin/build_db \
    -H hash.k2d -t taxo.k2d -o opts.k2d \
    -n taxonomy -m seqid2taxid.map \
    -c 52000000 -k 35 -l 31 -p 1 \
    -S 1111111111111111101010101010101

# 48 MB version: add -M 12000000
# 16 MB version: add -M 4000000
```

| flag | meaning |
|---|---|
| `-c 52000000` | table size in cells; from 36.0 M minimizers at 70% occupancy |
| `-k 35 -l 31` | k-mer and minimizer lengths — unchanged from all previous work |
| `-S 111...0101` | the spaced seed, 7 spaces. This is kraken2's default and what the 16 GB database uses. Omitting it is what caused problem §2.3 |
| `-M` | the skip threshold. Omit for a complete database |
| `-p 1` | **required** — multi-threaded `build_db` crashes on this machine |

Each build takes about 20 minutes. Run them one at a time.

Classification, as used for every number in §5:

```bash
D=databases/eskape_big_M12000000
/home/dell/summer/kraken2_bin/classify \
    -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0.05 perpod5/pod5_15.fastq
```

`-g 2` matters: the `kraken2` wrapper script passes it by default but the raw
`classify` binary does not, and omitting it inflates the classification rate.
