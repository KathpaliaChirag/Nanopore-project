# How a read becomes a taxid — the full path, with a traced example

Companion to `MEETING_UPDATE_2026-10-20.md` Part 2. Every number below was
produced by `scripts/trace_minimizer.cc`, which links kraken2's **own**
`mmscanner.o`, `compact_hash.o` and `taxonomy.o` — so nothing is reimplemented
and nothing is estimated. The same code `classify` runs produced these values.

```bash
g++ -O2 -std=c++17 -fopenmp -I kraken2/src -o trace_minimizer \
    scripts/trace_minimizer.cc kraken2/src/{mmscanner,compact_hash,taxonomy,mmap_file,utilities,omp_hack}.o
./trace_minimizer databases/eskape_big_M12000000 perpod5/pod5_15.fastq 1 999
./trace_minimizer databases/standard_16gb        perpod5/pod5_15.fastq 1 999
```

---

## 0. Key findings

| # | finding | evidence |
|---|---|---|
| 1 | **The hash is 64 bits** and is a *bijection* — 62-bit minimizer in, 64-bit out, nothing compressed, nothing lost. Max hash observed = 99.73% of 2⁶⁴. | §6 |
| 2 | **Only 48 of those bits carry entropy.** The spaced seed blanks 7 of the 31 bases, so 24 bases × 2 bits = 48. | §6 |
| 3 | **The hash does not shrink the key — it makes the key safe to shrink.** Information is lost at *truncation* to 26 or 16 bits, not at hashing. | §6, §7 |
| 4 | **The cell value is NOT the taxid.** 6 value bits hold 63 values; it is an index into `taxo.k2d`, and the taxid needs a second lookup. This stage was missing from our earlier write-ups. | §1 ⑥ |
| 5 | **The key is the same hash, truncated.** `key_16GB == key_50MB >> 10`, verified **154/154** on every minimizer both databases looked up. | §2 |
| 6 | **The hash is identical across databases** — 717/717 minimizers of a real read, bit for bit. MurmurHash3 takes only the minimizer. | §2 |
| 7 | **Per *minimizer*, the 16 GB database is LESS specific, not more** — 1 of 51 shared hits agrees; it answers genus `286` where the 48 MB answers species `287`, because its LCA ran against ~14,000 species. The small database's precision is partly an artefact of its own ignorance. | §2.1 |
| 8 | **Reads converge anyway.** `ResolveTree` sums each taxon's root-to-leaf path, so 21 direct species hits beat 353 genus hits: `score(287)=460` vs `score(286)=439`. All four databases call the example read `287`. | §3 |
| 9 | **The 16 GB database has a ~1,000× higher per-lookup collision rate** than the 48 MB one (16 key bits vs 26). It survives by skipping 79.25% of lookups and by scattering false hits over 47,011 taxa instead of 38. | §6 |
| 10 | **Hashing buys 4× better addressing.** Raw minimizers occupy 24.7% of the slots they should (χ²/dof 6.62, worst slot 25); hashed hits 100.0% of the theoretical ideal (χ²/dof 1.00, worst slot 6). `Get` is 43.4% of cycles, so this is the hot path. | §7.1 |
| 11 | **Without hashing the fingerprint fails on 17.6% of keys** — top 26 raw bits separate 82.4% of minimizers, hashed 98.0%. | §7.2 |
| 12 | **`-M` subsampling is impossible without the hash.** The threshold is 3.08× larger than any possible raw minimizer, so gating on raw skips 100% — dead database. More deeply, `-M` needs a *uniform* variate for "< X" to mean a fixed fraction. **The project's central finding rests on the hash being uniform.** | §7.3 |
| 13 | **Rejected by measurement:** slot/fingerprint independence is *not* what hashing buys — correlation is ~0.001 for raw *and* hashed. | §7.4 |

---

## 1. The pipeline

```
                      ┌──────────────────────────────────────────┐
  FASTQ               │  @14f8e11f-1e09-48d1-8a7b-ac43994b3bf0   │
  one read            │  ACGT… 2,274 bp                          │
                      └────────────────────┬─────────────────────┘
                                           │
  ① SLIDE a k=35 WINDOW, take the minimal l=31 subsequence in it
     mmscanner.cc · canonical (min of fwd / revcomp) · XOR toggle_mask
     · spaced seed blanks out bases before comparing
                                           │
                      ┌────────────────────▼─────────────────────┐
                      │  2,240 windows → 717 DISTINCT minimizers │
                      │  minimizer #1 = 3153410348141261057      │
                      │                 0x2bc32a0110003101       │
                      └────────────────────┬─────────────────────┘
                                           │
  ② HASH IT — kv_store.h:67  MurmurHash3 64-bit finalizer
       k ^= k>>33;  k *= 0xff51afd7ed558ccd;
       k ^= k>>33;  k *= 0xc4ceb9fe1a85ec53;
       k ^= k>>33;
     PURE FUNCTION of the minimizer. No table, no taxonomy, no DB state.
                                           │
                      ┌────────────────────▼─────────────────────┐
                      │   hc = 0xdae9c0fa53830f9a                │
                      │      = 15,774,351,351,217,328,026       │
                      │   ** IDENTICAL IN EVERY DATABASE **      │
                      └────────────────────┬─────────────────────┘
                                           │
  ③ THE -M GATE — classify.cc:842    ← the whole performance story
       if (hc < min_acceptable_hash_value) skip_lookup = true;
     No memory is touched at all for a skipped minimizer.
                                           │
                     ┌─────────────────────┴────────────────────┐
                 skip│                                          │pass
                     ▼                                          ▼
              taxon = 0                      ④ SPLIT hc INTO TWO INDEPENDENT PARTS
          (never looked up)                     compact_hash.h:356-358
                                                  key  = hc >> (64 - key_bits)   ← HIGH bits
                                                  slot = hc % capacity           ← LOW bits
                                                              │
                      ┌───────────────────────────────────────▼──────────────┐
                      │  the key is the FINGERPRINT stored in the cell       │
                      │  the slot is the ADDRESS the cell lives at           │
                      │  different bits of the same hash → independent       │
                      └───────────────────────────────────────┬──────────────┘
                                                              │
  ⑤ PROBE — compact_hash.h:360-373, open addressing, double hashing
       while (true) {
         if (!cell[idx].value())            break;       // empty → miss
         if (cell[idx].hashed_key() == key)  return val;  // HIT
         if (step == 0) step = (hc >> 8) | 1;            // second hash
         idx = (idx + step) % capacity;
         if (idx == first_idx)              break;       // table exhausted
       }
                                                              │
                      ┌───────────────────────────────────────▼──────────────┐
                      │  ONE 32-bit CELL  —  compact_hash.h:17-42            │
                      │                                                      │
                      │   ┌──────────────────────────┬──────────────┐        │
                      │   │  hashed_key (key_bits)   │ value (vb)   │        │
                      │   └──────────────────────────┴──────────────┘        │
                      │     data >> value_bits         data & mask           │
                      │                                                      │
                      │  48 MB : 26 key bits | 6 value bits  (max val 63)    │
                      │  16 GB : 16 key bits | 16 value bits (max 65535)     │
                      │  key_bits + value_bits == 32, always                 │
                      └───────────────────────────────────────┬──────────────┘
                                                              │
  ⑥ THE VALUE IS **NOT** THE TAXID. It is an internal node index.
     6 value bits only allow 63 distinct values — far too few for NCBI taxids.
                                                              │
                      ┌───────────────────────────────────────▼──────────────┐
                      │  taxo.k2d  —  taxonomy.h TaxonomyNode[]              │
                      │  classify.cc:907                                     │
                      │     ext = taxonomy.nodes()[value].external_id;        │
                      │                                                      │
                      │  48 MB holds    38 nodes                             │
                      │  16 GB holds 47,011 nodes                            │
                      └───────────────────────────────────────┬──────────────┘
                                                              │
                      ┌───────────────────────────────────────▼──────────────┐
                      │        NCBI TAXID for this ONE minimizer             │
                      └───────────────────────────────────────┬──────────────┘
                                                              │
  ⑦ REPEAT for all 717 minimizers → a hit-count histogram per taxon
                                                              │
  ⑧ RESOLVE THE READ — classify.cc:738 ResolveTree
     score(T) = Σ hits at every taxon that is T or an ancestor of T
     take argmax; then walk up the tree until score ≥ ceil(T_conf × 717)
                                                              │
                      ┌───────────────────────────────────────▼──────────────┐
                      │                ONE TAXID FOR THE READ                │
                      └──────────────────────────────────────────────────────┘
```

---

## 2. Worked example — the SAME minimizer in both databases

Read `14f8e11f-1e09-48d1-8a7b-ac43994b3bf0` (pod5_15, read index 1, 2,274 bp),
its **first** minimizer, traced in the 48 MB and the 16 GB database:

```
            minimizer  3,153,410,348,141,261,057      0x2bc32a0110003101
                             │                                    │
            ┌────────────────┴───────────────┐    ┌────────────────┴──────────────┐
            │  MurmurHash3 — same function   │    │  MurmurHash3 — same function  │
            └────────────────┬───────────────┘    └────────────────┬──────────────┘
                             ▼                                     ▼
            hc = 0xdae9c0fa53830f9a                 hc = 0xdae9c0fa53830f9a
                 15,774,351,351,217,328,026              15,774,351,351,217,328,026
                      ══════════════ IDENTICAL ══════════════
                             │                                     │
                 48 MB (eskape_big_M12000000)          16 GB (standard_16gb)
                 capacity   12,000,000                 capacity   4,000,000,000
                 key_bits   26                         key_bits   16
                             │                                     │
             key  = hc >> 38                       key  = hc >> 48
                  = 57,386,755                          = 56,041
                  = 0x36ba703                           = 0xdae9
                             │                                     │
                      └──────── 57,386,755 >> 10 == 56,041 ───────┘
                              SAME HASH, 10 FEWER BITS KEPT
                             │                                     │
             slot = hc % 12,000,000                slot = hc % 4,000,000,000
                  = 1,328,026                           = 3,217,328,026
                             │                                     │
                     probe → EMPTY CELL                    probe → slot 3,217,328,026
                                                           first probe, no collision
                             │                                     │
                     value = 0                            value = 37
                             │                                     │
                     TAXID 0  (miss)                taxo.k2d[37].external_id = 2
                                                     TAXID 2 — Bacteria (superkingdom)
```

The relation held for **every** minimizer that both databases looked up:

| check, on all 717 minimizers of this read | result |
|---|---|
| minimizer sets identical (same spaced seed) | **717 / 717** |
| hash identical for every shared minimizer | **717 / 717**, 0 differences |
| both databases actually performed the lookup | 154 (the rest `-M`-skipped) |
| `key_16GB == key_48MB >> 10` | **154 / 154** |

## 2.1 A minimizer that reaches a taxid in *both*

```
  minimizer 123,367,872,634,364,417   =  0x01b64a6d31112201
      hash  0xe34b4bb0801dd954  =  16,378,267,691,298,707,796   ← identical in both
      │
      ├─ 48 MB : key 0x38d2d2e (59,583,790)  slot     6,707,796
      │            value 34    → taxo.k2d[34].external_id  = 287  P. aeruginosa  (species)
      └─ 16 GB : key 0xe34b    (58,187)      slot 3,298,707,796
                   value 6762  → taxo.k2d[6762].external_id = 286  Pseudomonas    (genus)

  and 59,583,790 >> 10 == 58,187 — the key relation again.
```

51 minimizers of this read reach a taxid in both databases, and **only 1 of the
51 returns the same taxid.** This looks alarming and is in fact the opposite:

> **Per minimizer, the 16 GB database is LESS specific, not more.**

Its LCA was computed over ~14,000 species, so a minimizer shared by several
*Pseudomonas* species collapses to the **genus** 286, or further up. The 48 MB
database knows only 7 species, so the same minimizer has nothing to collapse
against and stays at **287**. The small database's confidence is partly an
artefact of its own ignorance.

---

## 3. Stage ⑦–⑧ for this read — why both still call *P. aeruginosa*

Hit counts over all 717 minimizers:

| | 48 MB | 16 GB |
|---|---|---|
| | `0: 1765` (no hit) | `0: 1780` (no hit) |
| **287** *P. aeruginosa* (S) | **475** | 21 |
| **286** *Pseudomonas* (G) | — | **353** |
| 135621 Pseudomonadaceae (F) | — | 39 |
| 72274 Pseudomonadales (O) | — | 5 |
| 1236 Gammaproteobacteria (C) | — | 12 |
| 1224 Proteobacteria (P) | — | 15 |
| 2 Bacteria (D) | — | 15 |

The 16 GB answers are scattered up and down one single lineage:

```
    2 Bacteria                      15 ─┐
    └ 1224 Proteobacteria           15  │
      └ 1236 Gammaproteobacteria    12  │  ResolveTree sums
        └ 72274 Pseudomonadales      5  │  the root-to-leaf path
          └ 135621 Pseudomonadaceae  39  │
            └ 286 Pseudomonas       353  │
              └ 287 P. aeruginosa    21 ─┘  score(287) = 460  ← argmax
                                            score(286) = 439
```

`ResolveTree` (`classify.cc:738`) scores each taxon as the **sum of its whole
root-to-leaf path**, so 287 wins with **460** against 286's 439 — and the read
is called *P. aeruginosa* even though only 21 minimizers pointed at the species
directly. The 48 MB database gets there in one step with 475 direct hits.

**Read-level calls, all four databases, this one read:**

| database | call | meaning |
|---|---|---|
| `eskape_32bit_fork` (old 49 MB) | `C 208964` | *P. aeruginosa* **PAO1** — a strain |
| `eskape_big_M12000000` (48 MB) | `C 287` | *P. aeruginosa* — species |
| `eskape_big` (208 MB) | `C 287` | *P. aeruginosa* — species |
| `standard_16gb` | `C 287` | *P. aeruginosa* — species |

All four are right. They differ in **rank**, not in answer — and the old
database's apparent extra precision (a named strain) is spurious, because PAO1
is the only *P. aeruginosa* it contains.

---

## 4. Where the four databases actually differ

| stage | 48 MB | 16 GB | same? |
|---|---|---|---|
| ① minimizer | `l=31, k=35`, mask `0x3ffffffff3333333` | identical | **yes** (once seeds match) |
| ② hash | MurmurHash3 | MurmurHash3 | **yes, always** |
| ③ `-M` gate | skip below `0xc4ec4ec4ec4ec000` → 76.9% | skip below `0xcae079d9079bb000` → 79.25% | similar |
| ④ key | `hc >> 38`, 26 bits | `hc >> 48`, 16 bits | **truncation of the same hash** |
| ④ slot | `hc % 12,000,000` | `hc % 4,000,000,000` | no |
| ⑤ probe | double hashing `(hc>>8)|1` | identical code | yes |
| ⑥ value | 6 bits, ≤63 nodes | 16 bits, ≤65,535 nodes | no |
| ⑥ taxo.k2d | 38 nodes | 47,011 nodes | no |
| ⑦ per-minimizer taxid | species, usually | **genus or higher** | no |
| ⑧ read call | `287` | `287` | **yes** |

**The only two stages that are genuinely identical are the two that contain no
database state: the minimizer extraction and the hash.** Everything downstream
is a property of how the table was shaped, and it converges again at stage ⑧.

---

## 5. One-line answers for the meeting

- **Is the hash the same?** Yes, bit for bit — 717/717 on a real read.
  MurmurHash3 takes only the minimizer.
- **Is the key the same?** No, but it is the **same hash truncated**:
  26 bits vs 16, and `key_16GB == key_48MB >> 10` held 154/154.
- **Is the slot the same?** No — `hc % capacity`, and the capacities differ
  333-fold.
- **Is the value the taxid?** **No.** It is an index into `taxo.k2d`;
  6 value bits cannot hold an NCBI taxid. The taxid comes from
  `taxonomy.nodes()[value].external_id`.
- **Is the output the same?** Per minimizer, almost never (1 of 51 here).
  Per read, yes — all four databases call this read `287`.

---

## 6. How wide is each stage? — the hash is 64 bits

The question "the minimizer is 31 long, so how big is the hash?" has a layered
answer, because the width and the *information* diverge.

```
  31 bases                                  ← what l=31 means
      │  2 bits per base (A/C/G/T)
      ▼
  62 bits   raw minimizer                     4,611,686,018,427,387,904 values
      │  spaced_seed_mask 0x3ffffffff3333333, popcount 48
      ▼
  48 bits   informative                         281,474,976,710,656 values
            = 24 of the 31 bases actually compared; 7 blanked ("spaces = 7")
      │
      ▼  MurmurHash3 64-bit finalizer — kv_store.h:67
  64 bits   hc                              18,446,744,073,709,551,616 values
      │
      ├──► 26 bits stored in the cell (48 MB DB)      67,108,864 values
      └──► 16 bits stored in the cell (16 GB DB)          65,536 values
```

**The hash is 64 bits** — `uint64_t MurmurHash3(hkey_t)`, `hkey_t = uint64_t`
(`kv_store.h:17,67`). Confirmed on the 717 real minimizers of the traced read:
the largest hash observed is **18,397,592,138,598,300,075**, i.e. **99.73% of
2⁶⁴**, `bit_length = 64`. The output uses the whole word.

But it carries only **48 bits of entropy**, because that is all the input had.
MurmurHash3's finalizer is a **bijection on 64 bits** — `k ^= k>>33` is
invertible and both multiplier constants are odd, so multiplication mod 2⁶⁴ is
invertible. It cannot add or destroy information.

### Where information is actually lost: the fingerprint

| database | keys stored | fingerprints available | keys per fingerprint |
|---|---:|---:|---:|
| 48 MB `eskape_big_M12000000` | 8,316,093 | 67,108,864 (26 bit) | **0.1** |
| 16 GB `standard_16gb` | 2,800,427,917 | 65,536 (16 bit) | **42,731** |
| 24 MB `eskape_16bit` | 8,903,388 | 1,024 (10 bit) | **8,695** |

The 16 GB database stores 2.8 billion minimizers behind only 65,536 distinct
fingerprints — ~43,000 keys share each value. On its own that fingerprint is
nearly useless; the **slot address does the discrimination**, and the
fingerprint only separates the few keys that land on the same slot out of 4
billion.

Per-lookup false-hit probability, `E[occupied cells probed] × 2^−key_bits`:

| | key bits | P(false hit) | taxa to spread over |
|---|---:|---:|---:|
| 48 MB | 26 | 3.4 × 10⁻⁸ | 38 |
| **16 GB** | **16** | **3.6 × 10⁻⁵** | **47,011** |
| `eskape_16bit` | 10 | 2.6 × 10⁻³ | 38 |

**The 16 GB database has a ~1,000× higher per-lookup collision rate than the
48 MB one** — the price of spending 10 of its 32 cell bits on the taxid value
instead of the fingerprint.

### This is confirmed by the cell-width sweep already in the project

`CELLWIDTH_DB_BUILD.md` varied `key_bits` with everything else fixed
(16 files, 1.87 M reads):

| key bits | *S. aureus* FP | *E. faecium* FP | ratio | predicted `2^Δbits` |
|---:|---:|---:|---:|---:|
| 26 | 12 | 48 | baseline | — |
| 18 | 31 | 102 | 3× / 2× | 256× |
| 10 | **7,071** | **10,014** | **228× / 98×** | **256×** |

Below ~18 bits the observed scaling tracks `2^−key_bits` closely (228× against
a predicted 256×). Above it the counts flatten at 12–48, and that floor is not
collisions at all — it is the **forced assignment** of §1.7a, which swamps the
collision term.

The 16 GB database sits at 16 key bits, inside the region where the cell-width
series exploded. It survives for two reasons the small databases lack: it
**skips 79.25% of lookups**, and its false hits scatter across **47,011 taxa**
instead of 38, so ~167 random false minimizer hits per file never accumulate
enough for `ResolveTree` to flip a read. In `eskape_16bit` the same noise
concentrated on 7 species and moved 17,000 reads.

> **For the prof:** the 16 GB database is *less* precise per lookup, not more.
> It buys back far more than it loses from reference breadth and from having
> somewhere correct to put each read.

---

## 7. Then why hash at all, if it does not shrink the key?

It does not shrink anything — 62 bits in, 64 out, bijective. It earns its place
for three other reasons, all measured here on **2,727,687 distinct real
minimizers** from 3,000 pod5_15 reads (`result/hash_uniformity/`).

### 7.1 Uniform addressing — worth 4×

```
2,727,687 distinct minimizers → 12,000,000 slots
theoretical best if perfectly uniform: 2,439,888 slots occupied

raw minimizer % CAP     602,438 slots  ( 24.7% of ideal)  max 25/slot  chi2/dof 6.62
MurmurHash3  % CAP    2,439,465 slots  (100.0% of ideal)  max  6/slot  chi2/dof 1.00
```

The hashed version hits **2,439,465 against a theoretical 2,439,888 — 99.98%**,
chi2/dof = 1.00, textbook-perfect uniformity. The raw minimizer clumps into a
quarter of the slots it should, worst slot 25 instead of 6.

**Why raw minimizers clump:** the value *is* the sequence, 2 bits per base.
Adjacent k-mers in a genome share 30 of their 31 bases, so their integers differ
by a shift; repeats, GC-skew and homopolymers map to neighbouring integers. The
distribution is structural, so `% capacity` inherits that structure.

Not academic: `CompactHashTable::Get` is **43.4% of all cycles**, so 4× clumping
means 4× longer probe chains in the hottest code in the program.

### 7.2 A fingerprint that discriminates

The cell stores the **top** bits. Taken from the raw minimizer those are the
high-order bases — the most correlated part:

| top 26 bits of… | distinct values | keys separable |
|---|---:|---:|
| raw minimizer | 2,246,682 | 82.4% |
| MurmurHash3 | 2,673,050 | **98.0%** |

Without hashing, **17.6% of minimizers are indistinguishable by fingerprint**.

### 7.3 The `-M` gate is impossible without it — the decisive one

```
max possible raw minimizer (2^62) =  4,611,686,018,427,387,904
-M threshold 0xc4ec4ec4ec4ec000   = 14,189,803,133,622,730,752   <- 3.08x larger
```

Measured: gating on the raw minimizer skips **100.00%** — zero lookups, dead
database. Gating on the hash skips **76.95%** against a 76.92% target.

And this is not a range mismatch that rescaling would fix. `-M` works by saying
*"skip every minimizer whose hash is below X"*, which only yields a predictable
fraction if the value is **uniformly distributed**. Raw minimizers are not, so
no threshold gives a known skip rate. Since `-M` subsampling is this project's
central finding — why the 16 GB database is both faster and more sensitive, and
how a 48 MB database reaches 93% — **the whole result rests on the hash being
uniform.**

### 7.4 What the hash does *not* buy

Independence of slot and fingerprint. Linear correlation between the low 26 bits
and the high 26 bits is ~0.001 for **both** raw and hashed values, so that was
never the gain. Measured and discarded.

> **One line:** the hash does not shrink the key, it makes the key **safe to
> shrink**. Truncating a structured 62-bit value keeps the most correlated bits
> and discards the most informative; truncating a uniform 64-bit value keeps 26
> bits of real entropy. Same argument for the slot, and for the `-M` threshold.
