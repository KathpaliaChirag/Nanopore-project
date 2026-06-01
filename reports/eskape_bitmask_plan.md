# ESKAPE Bitmask DB — Implementation Plan

**Goal:** Replace the 8 GB standard Kraken2 DB with a single cache-friendly ESKAPE-targeted
DB where each minimizer slot stores a **6-bit bitmask** (one bit per organism).
One lookup → all 6 ESKAPE organisms answered simultaneously.

> **Status:** design doc. Verified against local source on 2026-06-01; corrections folded in
> (see §0). No code edited.

---

## 0. Corrections from source verification (2026-06-01)

Three claims in the first draft were **wrong** and are fixed below:

1. **Cell is 40-bit, not 32-bit.** `build_db.cc:86-93` hardwires `CompactHashCell40`
   (5 bytes / 40 bits) for **both** `-c 32` and `-c 40`. So the build path gives
   **key_bits = 40 − 6 = 34**, value_bits = 6, **5 bytes/cell** — not 26/4. (A new tool
   *could* instantiate the 32-bit `CompactHashCell` for 26+6/4-byte, but must do so
   explicitly; classify auto-detects width via `GetKVStoreCellType`, `classify.cc:281`.)
2. **Detection must count single-bit (unique) hits, not any set bit.** The draft's Phase-3
   snippet incremented every set bit → shared minimizers inflate non-present organisms →
   false positives. Fixed in §1 / §5 / §6.
3. **Taxonomy is still loaded at classify time.** `load_index` (`classify.cc:275`)
   unconditionally does `new Taxonomy(...)`. "No taxonomy needed" is false — needs a stub
   taxonomy file or a code change.

DB-size / L3-residency is **unverified** — depends on distinct-minimizer count; measure with
`estimate_capacity` before claiming L3-resident (§2).

**Mechanism traced & confirmed (2026-06-01):** the OR-accumulation `CompareAndSet`, the
self-describing file round-trip, linear probing, and OpenMP thread-safety on both build and
classify were verified against the source bodies — see §3. No true showstopper.

---

## 1. Design Summary

### What Changes vs. Standard Kraken2

| Aspect | Standard Kraken2 (8 GB) | Bitmask ESKAPE DB |
|---|---|---|
| Stored value | taxon ID (~19 bits) | 6-bit bitmask (1 bit/organism) |
| Cell width | 40-bit (CompactHashCell40, 5 B) | 40-bit, **key=34 / value=6** |
| DB size | 8,000 MB (capped/subsampled) | ~tens of MB (full, **measure it**) |
| Cache behavior | 8 GB >> 16 MB L3 → 15.91% miss | likely L3-resident → near-0% miss |
| Organisms covered | ~200,000 | 6 ESKAPE only |
| Merge op at build | LCA (taxonomy walk) | bitwise OR |
| Decision at classify | `ResolveTree` tree-walk | per-bit **unique-hit** count |
| Taxonomy | required | semantically unused (but still loaded) |
| Co-infection | yes (via LCA) | yes (via per-bit counts) |
| Hash-collision FP rate | higher (fewer key bits) | lower (**1 in 2³⁴** truncated key) |

### Bit Assignment

```
Bit 0 = Enterococcus faecium    (taxid 1352)   mask 0b000001 = 1
Bit 1 = Staphylococcus aureus   (taxid 1280)   mask 0b000010 = 2
Bit 2 = Klebsiella pneumoniae   (taxid 573)    mask 0b000100 = 4
Bit 3 = Acinetobacter baumannii (taxid 470)    mask 0b001000 = 8
Bit 4 = Pseudomonas aeruginosa  (taxid 287)    mask 0b010000 = 16
Bit 5 = Enterobacter cloacae    (taxid 550)    mask 0b100000 = 32
```

Value `0` = empty slot (never stored). `1,2,4,8,16,32` = organism-**unique**.
multi-bit = **shared**. `63` (0b111111) = **universal**. (Values are always > 0, satisfying
the table's "values must be > 0" rule, `compact_hash.h:97-100`.)

### How Build Changes (new function, NOT modifying ProcessSequenceFast)

**Current** `ProcessSequenceFast` (`build_db.h:210-211`):
```cpp
while (! hash.CompareAndSet(*minimizer_ptr, new_taxid, &existing_taxid))
    new_taxid = tax.LowestCommonAncestor(new_taxid, existing_taxid);
```

**New** `ProcessSequenceBitmask` (OR accumulation, no taxonomy):
```cpp
hvalue_t existing = 0;
hvalue_t new_val = (1u << org_bit);
while (! hash.CompareAndSet(*minimizer_ptr, new_val | existing, &existing))
    new_val = (1u << org_bit) | existing;   // converges: bit | existing
```
`new_val | existing` replaces `LCA(...)`. The CompareAndSet retry loop is identical — it ORs
instead of climbing the tree.

### How Classify Changes (unique-hit rule)

**Current** (`classify.cc:838, 859`): `taxon = hash->Get(...)`; `hit_counts[taxon]++`.

**New** — single-bit hits drive detection; shared hits are confirmatory only:
```cpp
hvalue_t mask = hash->Get(*minimizer_ptr);
if (mask == 0 || mask == 0x3F) continue;          // skip empty and universal
if (__builtin_popcount(mask) == 1)                 // UNIQUE evidence
    unique_hits[__builtin_ctz(mask)]++;
else                                               // SHARED → confirmatory only
    for (int b = 0; b < 6; b++) if (mask & (1u<<b)) shared_hits[b]++;
```
**Decision:** organism `i` DETECTED iff `unique_hits[i] >= eskape_min_hits`.
Shared minimizers alone never trigger a call — this is what prevents the
co-infection / conserved-gene false positive. `ResolveTree` is not called.

---

## 2. Reference Genome Data

### Per-Organism Genome Sizes and Download Sizes

| Organism | Taxid | Genome | FASTA (raw) | .fna.gz/genome | 5-strain total |
|---|---|---|---|---|---|
| *E. faecium* | 1352 | ~2.8 Mb | ~2.8 MB | ~750 KB | ~3.7 MB |
| *S. aureus* | 1280 | ~2.9 Mb | ~2.9 MB | ~780 KB | ~3.9 MB |
| *K. pneumoniae* | 573 | ~5.5 Mb | ~5.5 MB | ~1.5 MB | ~7.5 MB |
| *A. baumannii* | 470 | ~4.0 Mb | ~4.0 MB | ~1.1 MB | ~5.5 MB |
| *P. aeruginosa* | 287 | ~6.3 Mb | ~6.3 MB | ~1.7 MB | ~8.5 MB |
| *E. cloacae* | 550 | ~5.4 Mb | ~5.4 MB | ~1.5 MB | ~7.5 MB |
| **Total (5 strains)** | | **~133 Mb** | **~133 MB** | | **~36.6 MB** |

**Reference strains (NCBI RefSeq):**

| Organism | Strains | Example accession |
|---|---|---|
| *E. faecium* | Aus0004, DO, NRRL B-2354 | GCF_000250945.1 |
| *S. aureus* | NCTC 8325, USA300, MW2, N315, Mu50 | GCF_000013425.1 |
| *K. pneumoniae* | ATCC 13883, HS11286, MGH 78578, NTUH-K2044 | GCF_000742135.1 |
| *A. baumannii* | ATCC 17978, AYE, ACICU, AB5075 | GCF_000012345.1 |
| *P. aeruginosa* | PAO1, PA14, LESB58, DK2 | GCF_000006765.1 |
| *E. cloacae* | ATCC 13047, NCTC9394 | GCF_000025565.1 |

```bash
# NCBI datasets CLI (conda install -c conda-forge ncbi-datasets-cli)
datasets download genome taxon 287 --reference --assembly-level complete \
    --filename data/eskape_genomes/paeruginosa.zip
# repeat for 1352 1280 573 470 550
```

### Expected DB Size — UNVERIFIED, must measure

```
Cell = 5 bytes (CompactHashCell40), occupancy ~70%.
DB size ≈ distinct_minimizers / 0.70 × 5 bytes.

distinct_minimizers is the unknown. Rough bracket for ~133 Mbp of 6 species
(heavy within-species, little cross-species dedup): ~1M (optimistic) to ~10M+.
  →   1M  →  ~7 MB   (fits L3)
  →  10M  →  ~70 MB  (spills 16 MB L3, still ~115× smaller than 8 GB)
```

**Action — run the existing standalone tool** (OpenMP-parallel, `estimate_capacity.cc:49,71`):
```bash
# concatenate the 6 ESKAPE FASTAs, then:
tools/kraken2/src/estimate_capacity -k 35 -l 31 -S <seed> eskape_all.fna
# distinct minimizers × (1/0.70) × 5 bytes = real DB size
#   ≲3M  → ≲21 MB  (effectively L3-resident)
#   ~10M → ~70 MB  (spills 16 MB L3, still ~115× smaller than 8 GB, mostly cache-resident)
```
Either way the lookup-time and cache wins hold; only exact L3-residency is in question.

---

## 3. Implementability Check — YES, with caveats

~250 lines of new C++, 2 modified files. **No changes to `compact_hash.h`** — `CompareAndSet`
/ `Get` are value-agnostic; passing `value_bits=6` to the constructor is enough.

| File | Action | Lines | Notes |
|---|---|---|---|
| `tools/kraken2/src/build_eskape_db.cc` | NEW | ~200 | bitmask builder, `bits_for_taxid=6` |
| `tools/kraken2/src/classify.cc` | MODIFY | ~100 | eskape mode + unique-hit path + **gate output tail** + report + skip taxonomy |
| `tools/kraken2/src/Makefile` | MODIFY | ~5 | new build target |
| `data/eskape_seqid2bit.txt` | NEW | 6 | seqid → bit (0-5) |
| `data/eskape_stub_taxonomy/` | NEW | tiny | stub taxo.k2d (or reuse 8 GB DB's taxo.k2d) so `load_index` doesn't fail |

> **Scope correction:** the classify.cc edit is **bigger than ~60 lines**. Line `classify.cc:898`
> runs `taxonomy.nodes()[call].external_id` **unconditionally**, and `AddHitlistString` (`:923`)
> walks `taxa` through the taxonomy — both fed bitmask values in eskape mode. So the eskape path
> must **early-return before `:871`** (or the whole output tail `:871-925` **and** the caller block
> `:607-622` must be gated behind `opts.eskape_mode`). Not a blocker, but it touches the output
> formatting and the caller, not just `ClassifySequence`'s accumulation.

### Mechanism verified against source (2026-06-01)

| Claim | Evidence | Result |
|---|---|---|
| OR-accumulation converges via `CompareAndSet` | `compact_hash.h:304-348` (traced) | ✓ ≤2 iters, same shape as the LCA loop |
| `new_value==0` rejected / `file_backed_` rejected | `:310`, `:308` | ✓ masks are 1-63; build uses in-RAM ctor |
| `Get()` returns 0 on miss, compares 34-bit truncated key | `:258-280` | ✓ collision FP ~2⁻³⁴ |
| File round-trip is self-describing (no cell-type byte) | `kv_store.h:34-58` switches on `key_bits+value_bits`; `WriteTable` `:247-255` | ✓ `34+6=40 → CompactHash40` loads back |
| Linear probing; over-capacity is a **hard `errx`** | `:380-385`, `:344-345` | ⚠ size capacity via `estimate_capacity` or build aborts |
| `value_bits=6` arithmetic valid in both cells | `CompactHashCell40::populate :65-84`; `CompactHashCell :26-37` | ✓ `34+6` and `26+6` both validate |

### OpenMP — usable on both sides, fits *cleaner* than today

- **Build** (`build_db.h:83-130`): already `#pragma omp parallel`; inserts are thread-safe via
  256 `omp_lock_t` zone locks (`compact_hash.h:320-339`). OR is commutative/associative → the
  final per-minimizer mask is **order-independent**, so multithreaded build is deterministic.
- **Classify** (`classify.cc:519-664`): already `#pragma omp parallel` with per-thread accumulators
  merged in `#pragma omp critical` (`:632`, `:660`). The bitmask needs only a thread-local
  `org_read_counts[6]` reduced at that same point — **simpler than the current growing `std::map`
  merge** (`thread_taxon_counters` → `total_taxon_counters`).
- `-fopenmp` is the default; `omp_hack.o` stubs it out if disabled. OpenMP is first-class.

---

## 4. Inconsistencies / Risks (severity-ranked)

### 🔴 MAJOR 1 — Cell width assumed 32-bit (FIXED in §0)
`build_db.cc:86-93` always uses `CompactHashCell40`. Use **40-bit / key=34 / value=6**, or
explicitly pick `CompactHashCell` (32-bit) in the new tool.

### 🔴 MAJOR 2 — Any-bit counting causes false positives
Counting every set bit lets shared minimizers promote absent organisms. **Fix:** detection
on `popcount(mask)==1` unique hits only (§1, §6). This is the key accuracy fix.

### 🟠 MODERATE 3 — Taxonomy always loaded
`load_index` (`classify.cc:275`) unconditionally `new Taxonomy(...)`. Provide a stub
taxonomy file, or gate the load behind `!opts.eskape_mode`.

### 🟠 MODERATE 4 — `bits_needed_for_value` from taxonomy
`build_db.cc:66-67` derives value_bits from `taxonomy.node_count()`. New tool must
**hardcode `bits_for_taxid = 6`**.

### 🟠 MODERATE 5 — `ProcessSequenceFast` is taxonomy-coupled
`build_db.h:198,211` use `tax.LowestCommonAncestor`. Add a separate
`ProcessSequenceBitmask`; do not modify the original.

### 🟠 MODERATE 6 — `ResolveTree` / `taxonomy.nodes()[call]` misuse
`classify.cc:878,898` treat the value as a taxon ID and index the NCBI tree. Bitmask values
are not taxon IDs → garbage names. Gate behind `opts.eskape_mode`.

### 🟡 MINOR 7 — Output format can't express multi-organism
Per-read `C/U taxon length kmers` is single-taxon. Write a **per-sample ESKAPE summary**
(DETECTED / NOT_DETECTED per organism) after the read loop.

### 🟡 MINOR 8 — `confidence_threshold` semantics break
`classify.cc:734` uses `confidence × total_minimizers`. Replace with integer
`--eskape-min-hits` (default 3) on the unique-hit counters.

---

## 5. Accuracy Impact

**Scoped verdict:** with the unique-hit rule, precision for the 6-target presence/absence task
is high. Without it (any-bit counting), it has real false positives. It strictly **loses**
sub-species resolution, abundance, and any non-ESKAPE detection; sensitivity is bounded by the
reference panel.

| Metric | Standard 8 GB | Bitmask (unique-hit rule) |
|---|---|---|
| FP from non-ESKAPE bacteria | high (16S etc. hit any bacterium) | low (universal mask 63 skipped) |
| FP between ESKAPE organisms | moderate (shared genes) | low (shared = confirmatory only) |
| Hash-collision FP | higher | **1 in 2³⁴** truncated key |
| Co-infection | yes | yes |
| Non-ESKAPE / sub-species | yes | **no** (out of scope) |
| Sensitivity to novel strains | broad DB | **bounded by reference panel** |

Threshold calibration: a 1000 bp P. aeruginosa read (~67 minimizers) yields ~20-30
P.aer-unique hits → clears `min_hits=3-5` easily; spurious single-bit hits from collisions
stay below it. Universal minimizers (mask 63) are skipped outright.

---

## 6. Step-by-Step Plan

### Phase 1 — Download genomes
6 organisms × ~5 strains, ~37 MB compressed (§2). Concatenate per organism into
`data/eskape_genomes/<org>_combined.fna`. Write `data/eskape_seqid2bit.txt` (seqid → bit).

### Phase 2 — Build tool `build_eskape_db.cc`
```
1. estimate_capacity over all 6 FASTAs → distinct minimizer count
2. CompactHashTable<CompactHashCell40>(capacity, key_bits=34, value_bits=6)
   (bits_for_taxid = 6 hardcoded — NOT from taxonomy.node_count())
3. for organism i in 0..5:
     for each sequence: ProcessSequenceBitmask(seq, i, hash, scanner, ...)
4. hash.WriteTable("data/eskape_bitmask.k2d")
5. write eskape.k2opts (k=35, l=31, value_bits=6); write stub taxo.k2d
```
Makefile: add `build_eskape_db` target linking `compact_hash.o mmscanner.o seqreader.o ...`.

### Phase 3 — classify.cc (~100 lines — see §3 scope correction)
1. `Options`: add `bool eskape_mode; int eskape_min_hits=3;`
2. CLI: `-E` sets eskape_mode; `--eskape-min-hits N`.
3. `load_index` (`:275`): skip `new Taxonomy(...)` when eskape_mode (or pass 8 GB DB's taxo.k2d).
4. `ClassifySequence`: in the minimizer loop (`:824-863`) reinterpret `Get` as a mask and apply the
   **unique-hit** logic from §1 into thread-local `unique_hits[6]`/`shared_hits[6]`; then
   **early-return before `:871`** (skip `ResolveTree` and the taxonomy-indexing output tail
   `:898`/`:923`). Gate the caller block `:607-622` too.
5. Reduce per-thread `org_read_counts[6]` at the existing `#pragma omp critical` (`:632`/`:660`).
6. After all reads: write per-organism DETECTED/NOT_DETECTED summary.

### Phase 4 — Correctness test (ground truth in §7)
```bash
./classify -E --eskape-min-hits 3 -H data/eskape_bitmask.k2d \
    results/dorado/reads_fast.fastq
# Expect: P. aeruginosa DETECTED, K. pneumoniae DETECTED,
#         E. faecium/S. aureus/A. baumannii/E. cloacae NOT_DETECTED,
#         E. coli + human ignored (out of scope).
```

### Phase 5 — Perf sweep
```bash
perf stat -d ./classify -E -H data/eskape_bitmask.k2d -p 8 results/dorado/reads_fast.fastq
# Baseline (8 GB DB, this machine, §7): processing 2.398s, cache-miss 15.91%, RSS 8.5 GB
# Target: cache-miss near 0, RSS tens of MB, processing < 1s
```

---

## 7. Baseline ground-truth run (measured 2026-06-01)

`classify` on `results/dorado/reads_fast.fastq` with the 8 GB MiniKraken2 DB, `-p 8`:

| Metric | Value |
|---|---|
| Reads | 104,832 (357.6 Mbp) |
| Classified | 97,680 (93.18%) |
| Unclassified | 7,152 (6.82%) |
| Processing time | 2.398 s |
| Wall (cold DB load) | 8.71 s |
| Peak RSS | 8.5 GB |

**ESKAPE organisms detected (reference truth for the bitmask DB):**

| Taxid | Organism | Reads | Signal |
|---|---|---|---|
| 287 | P. aeruginosa | 54,122 (51.63%) | **strong** |
| 573 | K. pneumoniae | 8,193 (7.82%) | **strong** |
| 550 | E. cloacae | 28 | trace |
| 470 | A. baumannii | 6 | trace |
| 1280 | S. aureus | 1 | trace |
| 1352 | E. faecium | 0 | absent |

Non-ESKAPE background present: *E. coli* 19,071 (18.19%), *P. putida* 1,784, *Homo sapiens*
594 — all must be **rejected** by the ESKAPE DB. The per-read kmer string (e.g.
`287:1 0:10 287:5 ... 286:1 ... 136841:1 ... 1224:3`) is the species/genus/phylum LCA
structure the bitmask flattens; the trace ESKAPE counts are exactly the noise that the
**unique-hit threshold** (MAJOR 2 fix) must suppress.

Outputs: `results/kraken2/manual_run/{kraken2_report.txt, kraken2_output.txt, classify_stderr.txt}`.

---

## 8. Summary

| Question | Answer |
|---|---|
| Implementable? | **Yes** — no showstopper; mechanism traced & confirmed (§3) |
| Major inconsistencies? | **3 critical** (cell width, any-bit counting, taxonomy load) + 5 moderate/minor — all fixable |
| Reduces lookup time? | **Yes** — DRAM probe (~100 ns) → L2/L3 hit (~4-14 ns); `Get()` is 80.65% of CPU. (NextMinimizer cost unchanged → bounded) |
| Cache-friendly? | **Very likely** — tens of MB vs 8 GB; confirm L3-residency via estimate_capacity |
| OpenMP usable? | **Yes, both sides** — already the model; zone-locked build (order-independent), `org_read_counts[6]` reduction at classify |
| Improves accuracy? | **Scoped yes** with unique-hit rule; loses sub-species + non-ESKAPE; sensitivity bounded by panel |
| Code scope | new build tool ~200 lines; **classify.cc ~100** (output tail + caller must be gated, not just accumulation) |
| DB size | tens of MB (measure) |
| Download | ~37 MB compressed; no taxonomy dump (stub only) |
| Biggest risk | (1) any-bit FP if unique-hit rule omitted; (2) diverged strains outside panel |

Original build/classify pipelines (`build_db.*`, `compact_hash.h`, `ResolveTree`) untouched;
eskape mode is additive.
