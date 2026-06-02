# ESKAPE Bitmask DB — Implementation Plan

**Goal:** Replace the 8 GB standard Kraken2 DB with a single cache-friendly ESKAPE-targeted
DB where each minimizer slot stores a **6-bit bitmask** (one bit per organism).
One lookup → all 6 ESKAPE organisms answered simultaneously.

> **Status:** design doc. Source-verified on 2026-06-01 (two passes); 6 reference genomes
> downloaded and the gate measurement run. **No code edited.**
> **Headline result:** 8,533,848 distinct minimizers (k=35, l=31) → full DB **~61 MB** (5-byte
> cell, 70% load). This **does not fit the 16 MB L3** (~3.8× over), but is **~130× smaller than
> the 8 GB DB**. L3-residency is reachable by subsampling to ~27.5% of minimizers (`-M`).
> Cross-organism minimizer sharing is **0.23%** — which decides bitmask vs taxon-ID (§9).

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

### Second-pass corrections (2026-06-01, after reading every hot-path source body)

4. **`estimate_capacity` and `build_db` read FASTA from STDIN, not a filename argument.**
   Both use a default-constructed `BatchSequenceReader`, which opens `fileno(stdin)` when no
   filename is given (`seqreader.h:59-62`); `estimate_capacity`'s `ProcessSequences` never
   passes one. The first draft's `estimate_capacity … eskape_all.fna` would hang on stdin and
   ignore the file. **Correct form:** `cat eskape_all.fna | estimate_capacity -k 35 -l 31 -p 8`
   (or `… < eskape_all.fna`). Same applies to the bitmask builder's input.
5. **Only `classify` is compiled** in `tools/kraken2/src/`. `build_db`, `estimate_capacity`,
   `dump_table` are source-only. `estimate_capacity` builds from the existing Makefile target
   with **no source edits** (`make estimate_capacity`) — done 2026-06-01.
6. **Correction 3 is lighter than first stated.** The classify hot path (`Get()` →
   `hit_counts[mask]++`, `classify.cc:838,859`) is **taxonomy-free** — `hit_counts` is keyed by
   the raw returned value, i.e. our mask. Taxonomy is touched in only ~5 places
   (`ResolveTree` `:878`, `ext_call` `:898`, `AddHitlistString` `:923/949/965`, caller
   `tax.nodes()[call]` `:609-610`). So C3 = **reuse the existing 1.75 MB `taxo.k2d`** to satisfy
   the `load_index` constructor (`:275`, loads in ms) + gate those 5 lines behind `eskape_mode`.
   **No stub taxonomy file needs to be authored.**

### DB size — NOW MEASURED (was unverified)

`estimate_capacity -k 35 -l 31 -n 1024` (exact, no sampling) over the 6 reference genomes
(26.7 Mbp) → **8,533,848 distinct minimizers** (§2). At 5 bytes/cell, 70% load → **~61 MB**.
That **spills the 16 MB L3** (~3.8×), but is ~130× smaller than 8 GB. Keep ~27.5% of minimizers
(`build_db -M`, honored by classify at `:832-834`) → ~15 MB → **L3-resident**. The first draft's
"~1M → 7 MB fits L3" bracket was optimistic by ~8×.

**Build↔classify minimizer compatibility — confirmed (silent-failure risk closed):** the
scanner's default `revcom_version == CURRENT_REVCOM_VERSION == 1` (`mmscanner.h:19,36`), build
writes that to the opts file (`build_db.cc:102`), classify reads it back (`classify.cc:521-523`).
Same k/l/toggle/spaced-seed ⇒ identical minimizers between build and classify.

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
| DB size | 8,000 MB (capped/subsampled) | **~61 MB full** (measured); **~15 MB** at 27.5% subsample |
| Cache behavior | 8 GB >> 16 MB L3 → 15.91% miss | full 61 MB still spills L3; subsample → ~15 MB **L3-resident** |
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

## 2. Reference Genome Data — DOWNLOADED & MEASURED (2026-06-01)

One **designated reference genome per organism** (NCBI RefSeq, `refseq_category = reference
genome`, Complete Genome level), resolved via the NCBI Datasets REST API and pulled from the
NCBI FTP (no CLI tool installed). Files live in `data/eskape_genomes/`, named by bit:

| bit | Organism | Taxid | Accession | Assembly | bp | contigs |
|---|---|---|---|---|---|---|
| 0 | *E. faecium* | 1352 | GCF_009734005.1 | ASM973400v2 | 2,919,198 | 2 |
| 1 | *S. aureus* | 1280 | GCF_000013425.1 | ASM1342v1 (NCTC 8325) | 2,821,361 | 1 |
| 2 | *K. pneumoniae* | 573 | GCF_000240185.1 | ASM24018v2 (HS11286) | 5,682,322 | 7 |
| 3 | *A. baumannii* | 470 | GCF_009035845.1 | ASM903584v1 | 3,999,136 | 3 |
| 4 | *P. aeruginosa* | 287 | GCF_000006765.1 | ASM676v1 (PAO1) | 6,264,404 | 1 |
| 5 | *E. cloacae* | 550 | GCF_905331265.2 | AI2999v1_cpp | 5,023,439 | 3 |
| | **combined** | | | `eskape_all.fna` | **26,709,860** | 17 |

Reproduce the download (resolve accession + assembly, build FTP URL, fetch `.fna.gz`):
```bash
# per (bit,taxid,acc,asm): URL = .../genomes/all/GCF/<3>/<3>/<3>/<acc>_<asm>/<acc>_<asm>_genomic.fna.gz
acc=$(curl -s "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/287/dataset_report?filters.assembly_source=RefSeq&filters.reference_only=true&page_size=1" \
      | jq -r '.reports[0].accession')
```
Total compressed ~7.8 MB. **kseq reads raw bytes — it does NOT decompress**, so `gunzip` before
building/estimating.

### Distinct minimizers (the gate) — MEASURED

```bash
cat eskape_all.fna | tools/kraken2/src/estimate_capacity -k 35 -l 31 -n 1024 -p 8
# 8,533,848   (exact; n=1024 makes every minimizer qualify. n=4 sample gave 8,518,144 — agrees)
```

| Organism | distinct minimizers |
|---|---|
| *E. faecium* | 896,648 |
| *S. aureus* | 914,325 |
| *K. pneumoniae* | 1,817,267 |
| *A. baumannii* | 1,294,551 |
| *P. aeruginosa* | 2,007,830 |
| *E. cloacae* | 1,623,085 |
| **sum of individuals** | **8,553,706** |
| **combined (measured)** | **8,533,848** |

**Cross-organism sharing = sum − combined = 19,858 = 0.23%.** 99.77% of minimizers are unique to
one organism. (These are phylogenetically diverse species — 2 Firmicutes, 4 Proteobacteria — so
they barely share 31-mers.) This number is the crux of the bitmask-vs-taxon-ID decision (§9).

### DB size (5-byte `CompactHashCell40`)

```
DB ≈ distinct_minimizers / load_factor × 5 bytes
  load 80% → 10,647,680 cells → 53.2 MB
  load 70% → 12,191,211 cells → 61.0 MB   ← reference point
  load 60% → 14,196,907 cells → 71.0 MB
  load 50% → 17,036,288 cells → 85.2 MB
(4-byte CompactHashCell32 @70% → ~48.8 MB, at the cost of a 26-bit vs 34-bit key.)

L3 = 16 MB → max 3,355,443 cells → max 2,348,810 distinct @70%.
  ⇒ keep ~27.5% of minimizers (build_db -M) → ~15 MB → L3-resident.
```
**Verdict:** the full DB is ~130× smaller than 8 GB but **not** L3-resident; full L3-residency
needs ~27.5% subsampling (orthogonal to taxon-vs-bitmask; §9). The lookup-latency win over 8 GB
holds in both cases.

---

## 3. Implementability Check — YES, with caveats

~250 lines of new C++, 2 modified files. **No changes to `compact_hash.h`** — `CompareAndSet`
/ `Get` are value-agnostic; passing `value_bits=6` to the constructor is enough.

| File | Action | Lines | Notes |
|---|---|---|---|
| `tools/kraken2/src/build_eskape_db.cc` | NEW | ~200 | bitmask builder, `bits_for_taxid=6` |
| `tools/kraken2/src/classify.cc` | MODIFY | ~100 | eskape mode + unique-hit path + **gate output tail** + report + skip taxonomy |
| `tools/kraken2/src/Makefile` | MODIFY | ~5 | new build target |
| seqid→bit mapping | optional | — | not needed if the builder maps each file→bit by argument order |
| (taxonomy) | **reuse** | 0 | point `-t` at the existing `taxo.k2d` to satisfy `load_index:275` — **no stub authored** (§0 correction 6) |

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

### 🟠 MODERATE 3 — Taxonomy always loaded (lighter than first stated — §0 correction 6)
`load_index` (`classify.cc:275`) unconditionally `new Taxonomy(...)`. **Reuse the existing
1.75 MB `taxo.k2d`** (`-t …`) to satisfy the constructor — it loads in ms and the hot path never
queries it — then gate the ~5 taxonomy-using lines (`:878/:898/:923/:609-610`) behind
`eskape_mode`. No stub taxonomy needs authoring.

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

### Phase 1 — Download genomes ✅ DONE (2026-06-01)
6 reference genomes (1 per organism) in `data/eskape_genomes/`, concatenated to `eskape_all.fna`
(26.7 Mbp), measured at 8,533,848 distinct minimizers / ~61 MB DB (§2). Multi-strain panels can
be added later for sensitivity (re-measure capacity if so). The build maps each FASTA → its bit
directly (file-order), so no `seqid2bit` map is strictly required.

### Phase 2 — Build tool `build_eskape_db.cc`
```
1. estimate_capacity (DONE, §2) → 8,533,848 distinct → capacity ≈ 12.2M @70%
   (`cat eskape_all.fna | estimate_capacity …` — reads STDIN, §0 correction 4)
2. CompactHashTable<CompactHashCell40>(capacity, key_bits=34, value_bits=6)
   (bits_for_taxid = 6 hardcoded — NOT from taxonomy.node_count(); cf. build_db.h:60-62)
3. for organism i in 0..5:
     for each sequence: ProcessSequenceBitmask(seq, i, hash, scanner, ...)
4. hash.WriteTable("data/eskape_bitmask.k2d")
5. write eskape.k2opts (k=35, l=31, value_bits=6, revcom=CURRENT_REVCOM_VERSION); NO taxonomy file
   (classify reuses an existing taxo.k2d for its loader — §0 correction 6)
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
# Full 61 MB DB:   RSS ~tens of MB, cache-miss reduced but still elevated (spills 16 MB L3)
# Subsampled ~15 MB (-M, ~27.5%): RSS ~15 MB, cache-miss → near 0 (L3-resident)
# Both: ~130× smaller RSS than 8 GB; processing dominated by NextMinimizer once Get() is cheap
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
| Cache-friendly? | **Partly** — full DB 61 MB still spills 16 MB L3; ~27.5% subsample → ~15 MB L3-resident; either way ~130× smaller than 8 GB |
| OpenMP usable? | **Yes, both sides** — already the model; zone-locked build (order-independent), `org_read_counts[6]` reduction at classify; bitmask scales the fine-grained combine best (§10) |
| Improves accuracy? | **Scoped yes** with unique-hit rule; loses sub-species + non-ESKAPE; sensitivity bounded by panel. vs taxon-ID: ~tie (slight taxon-ID edge, §9) |
| Code scope | new build tool ~200 lines; **classify.cc ~100** (output tail + caller must be gated, not just accumulation) |
| DB size | **~61 MB measured** (8,533,848 minimizers × 5 B / 0.70); ~15 MB at 27.5% subsample |
| Download | **~7.8 MB** compressed (1 ref genome/organism); reuse existing `taxo.k2d` for the loader — no stub authored |
| Bitmask vs Taxon-ID? | **Taxon-ID** for the project (zero code, validated, equal on the metrics that matter, §9); bitmask for fine-grained-parallel elegance (§10) |
| Biggest risk | (1) any-bit FP if unique-hit rule omitted; (2) diverged strains outside panel; (3) full DB not L3-resident without subsampling |

Original build/classify pipelines (`build_db.*`, `compact_hash.h`, `ResolveTree`) untouched;
eskape mode is additive.

---

## 9. Bitmask vs Taxon-ID — evidence-based decision (2026-06-01)

**The deciding measurement: cross-organism minimizer sharing = 0.23%** (§2). The first draft's
case for the bitmask was *"a combined DB maximizes cross-organism sharing, so taxon-ID's LCA
collapse is lossy."* The data refutes the premise — 99.77% of minimizers are unique to one
organism, so the bitmask's only unique advantage (lossless multi-membership) applies to **0.23%
of cells**. Both schemes ride on the same 99.77% unique minimizers.

**Both schemes share the substrate:** identical 8,533,848 minimizers, identical
`CompactHashTable`, identical `Get()`. The label (taxon id vs 6-bit mask) is a thin layer. So
three of the four axes are ties:

| Axis | Taxon-ID | Bitmask | Winner |
|---|---|---|---|
| **Data storage** | 61 MB (Cell40); ~5 value bits → 35 key bits | 61 MB (Cell40); 6 value bits → 34 key bits | **Tie.** Size = `distinct_mm × cell_size`; label-independent. Cell width (4 vs 5 B) is the only lever, open to both. |
| **Cache utilization** | 61 MB hash + few-KB taxonomy (6-species taxo is KB, not the 8 GB DB's 1.75 MB) | 61 MB hash | **Tie.** Hash dominates; both spill 16 MB L3 identically. The real lever (subsample → 15 MB) is shared. |
| **Speedup vs 8 GB** | same DB shrink; `ResolveTree` O(taxa²) over ≤~6 taxa/read = <1% | same shrink; `popcount`+6-int = cheaper post-lookup | **Near-tie.** `Get()` (≈80% CPU, DRAM-bound) is identical. Bitmask saves ~1–3%, visible only once not memory-bound (post-subsample). |
| **Accuracy** | validated Kraken2 `ResolveTree`+confidence+min-hit-groups; +1 key bit → ~2× fewer collision FPs | custom `eskape_min_hits` unique-hit rule (unproven, needs tuning) | **Slight taxon-ID.** Same fundamentals (same minimizers); taxon-ID inherits validated thresholding + marginally cleaner keys. |

Shared risk, identical for both: **within-Enterobacteriaceae false positives** — *E. coli* reads
(18% of the baseline, §7) hitting *K. pneumoniae* / *E. cloacae* minimizers. Defended the same
way in both schemes by the hit-count threshold.

**Practical asymmetry that breaks the tie:** taxon-ID needs **zero new code** — stock `build_db`
+ a 6-species `seqid2taxid` map + an NCBI taxonomy (full taxdump, or a hand-built minimal
`nodes.dmp`/`names.dmp`), then stock `classify` with a standard, validated, Bracken-compatible
report directly comparable to the 8 GB baseline. The bitmask needs new, unproven C++ on both the
build and classify sides plus its own validation.

> **Recommendation:** for the project goal (prove a small DB fixes the DRAM-latency bottleneck),
> **taxon-ID is the better engineering choice** — equal on the metrics that matter, validated
> output, no code risk. The bitmask is the more elegant *end state* for a fixed presence/absence
> panel, but with 0.23% sharing its concrete edge here is marginal (a ~1–3% post-lookup speedup
> that only the fine-grained-parallel design in §10 can cash in). The 130× shrink and the
> subsample-to-L3 win are **identical for both and orthogonal to this choice.**

---

## 10. l-mer-level (fine-grained) parallelism — which scales better?

If parallelism moves from the current read/block level (`classify.cc:519`) down to the
**per-minimizer** level (distribute the `Get()` lookups + their aggregation across threads), the
two phases behave very differently:

**Phase 1 — the lookup (`Get()` per l-mer): TIE.** `Get()` is `const`, lock-free, read-only
(`compact_hash.h:258-280`); the table is never mutated during classify (`zone_locks_` are
build-only, `:320-339`). Any number of threads look up concurrently with zero synchronization —
*for both schemes, on the same table*. This is ~80% of CPU and **DRAM-latency bound**; parallelism
helps by overlapping independent loads (memory-level parallelism), but that benefit is
label-independent and capped by two ceilings that apply equally: **bandwidth saturates ~T10**
(measured), and read-level threading already extracts most of the MLP. Finer granularity adds
OpenMP dispatch overhead per ~100–300-cycle load; within-thread **prefetch batching**
(`__builtin_prefetch` upcoming minimizers) is usually the better latency tool, and is also
scheme-independent.

**Phase 2 — the combine (aggregate l-mer results → call): BITMASK WINS.**

| | Bitmask | Taxon-ID (default) |
|---|---|---|
| per-l-mer result | 6-bit mask | taxon id |
| aggregation | OR / `popcount` into a **fixed 6-int array** | build `unordered_map` histogram |
| cross-thread merge | per-thread `int[6]`, summed at end — **lock-free, zero contention, O(log T)** | map-merge in `#pragma omp critical` (`classify.cc:660`) + allocation |
| final resolve | `popcount==1` tally + threshold | **`ResolveTree`** — O(taxa²) tree walk, data-dependent (`classify.cc:729-781`) |
| reduction algebra | commutative + associative + fixed-width | tree-structured LCA + variable-size histogram |

The bitmask's combine is the textbook parallel reduction; taxon-ID's default has a higher serial
fraction (critical-section merge) and a tree resolution that doesn't parallelize cleanly.

**Two honest bounds:**
1. **Amdahl.** The combine is the minority of work; the dominant ~80% lookup is identical and
   bandwidth-capped. So the bitmask's edge improves the cheaper part — modest, and *visible* only
   after subsampling makes lookups cheap (L3-resident).
2. **It's really "flat fixed histogram vs taxonomy-tree resolution," not "bitmask vs taxon."**
   Give taxon-ID a flat 6-bucket per-species counter + threshold (skip `ResolveTree`) and it
   reduces *the same way* — differing only on the 0.23% shared minimizers (flat-taxon collapses
   K∩E to root and loses them; bitmask keeps {K,E}). The bitmask just bakes the flat scheme into
   the data structure.

> **Verdict (§10):** for fine-grained parallel classification the **bitmask scales the combine
> best** (lock-free fixed-width reduction), stock-`ResolveTree` taxon-ID scales it worst, and
> **flattened** taxon-ID ≈ bitmask. The lookup — the actual bottleneck — is identical in all
> three. The real lesson: *keep the taxonomy tree out of the hot path*, which the bitmask enforces
> structurally.

---

## 11. Worked Example — build & use the bitmask DB

### 11.1 Build (conceptual CLI — `build_eskape_db` not yet written)
```
build_eskape_db -k 35 -l 31 -c 12200000 -C 40 -H eskape.k2d -o eskape.k2opts \
  0:bit0_Efaecium_*.fna 1:bit1_Saureus_*.fna 2:bit2_Kpneumoniae_*.fna \
  3:bit3_Abaumannii_*.fna 4:bit4_Paeruginosa_*.fna 5:bit5_Ecloacae_*.fna
```
`-c 12.2M` = 8.53M distinct ÷ 0.70 (§2). Loops over `(file, bit)` pairs; for each minimizer it
ORs that organism's bit into the cell via `CompareAndSet` (modeled on `build_db.h:196-214`):
```cpp
hvalue_t existing = 0, newval = (1u << org_bit);
while (! hash.CompareAndSet(m, newval, &existing))   // ≤2 iters
    newval = (1u << org_bit) | existing;             // OR in what's already there
```

**Trace — a conserved minimizer `m2` in both K. pneumoniae (bit2=4) and E. cloacae (bit5=32),**
**processed K before E:**
```
K.pneumoniae:  cell[m2] empty(0). CAS(m2,new=4,old=0): 0==old → populate. cell[m2]=4   (0b000100 {K})
E.cloacae:     existing=0,newval=32. CAS(m2,32,&existing=0): cell=4≠0 → existing=4, false
               loop: newval=(1<<5)|4=36. CAS(m2,36,&existing=4): cell=4==4 → populate.
               cell[m2]=36  (0b100100 {K,E})
```
OR is commutative → order-independent → the parallel build is deterministic in result. Resulting
cells (low 6 bits = mask; upper 34 = `MurmurHash3(m)>>30`):
```
 m1 | 000100 (=4)  | K.pneumoniae only        (unique)
 m2 | 100100 (=36) | K.pneumoniae + E.cloacae (shared)
 m3 | 010000 (=16) | P.aeruginosa only        (unique)
 m4 | 111111 (=63) | all six (rRNA-like)      (universal)
```
Measured reality: of 8,533,848 cells, **~99.77% are single-bit** (popcount==1), **~19,858 (0.23%)
multi-bit**. Output = `eskape.k2d` (~61 MB) + `eskape.k2opts` (k=35,l=31,revcom=1) — **no taxonomy
file**. `GetKVStoreCellType` reads `34+6=40 → CompactHash40` on load (`kv_store.h:34-56`).

### 11.2 Use (classify a sample)
```
classify --eskape --eskape-min-hits 3 -H eskape.k2d -o eskape.k2opts \
         -t <any taxo.k2d, only to satisfy the loader> results/dorado/reads_sup.fastq
```
Per read, scan minimizers (same k/l) and `Get()` each → a mask or 0. **A real P. aeruginosa read
(~200 minimizers):**
```
 Get() result | count | popcount | action
   16 (P)     |  185  |   1      | UNIQUE → unique_hits[P.aeruginosa] += 185
   48 (P|E)   |    8  |   2      | shared → confirmatory only, skip
   63 (all)   |    2  |   6      | universal → skip
    0 (miss)  |    5  |   -      | not in DB (seq error / single-ref gap)
```
Detection rule (replaces `ResolveTree`):
```cpp
hvalue_t v = hash->Get(m);
if (v == 0 || v == 0x3F) continue;            // skip empty + universal
if (__builtin_popcount(v) == 1) unique_hits[__builtin_ctz(v)]++;   // single organism
// popcount > 1 → shared → confirmatory only
```
This read: `unique_hits[P.aeruginosa]=185 ≥ 3` → supports *P. aeruginosa*.

**An E. coli read** (not in DB): nearly all minimizers → `Get()=0`; a few hit
Enterobacteriaceae-conserved minimizers → `unique_hits[K]≈2` < 3 → **does not** falsely promote
*K. pneumoniae*. The threshold is the false-positive guard, and matters most inside the
Gram-negative groups (highest sharing).

**Aggregate over ~105k reads → per-sample panel** (reproduces the §7 baseline from a ~61 MB DB,
one `Get()`+`popcount` per minimizer, no taxonomy walk):
```
 E. faecium       0   NOT_DETECTED      A. baumannii     6   NOT_DETECTED
 S. aureus        1   NOT_DETECTED      P. aeruginosa  high  DETECTED
 K. pneumoniae  high  DETECTED          E. cloacae      28   NOT_DETECTED (trace)
```

**Mental model:** *build* = each organism paints its bit onto its minimizers (shared ones become
multi-colored via OR); *use* = each read's minimizers vote, only single-color votes count, and an
organism is called if it clears the hit threshold.
