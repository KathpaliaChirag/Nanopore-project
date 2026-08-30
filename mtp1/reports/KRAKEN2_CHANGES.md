# kraken2: what it is, and every part we changed

Two separate layers of modification sit on top of upstream kraken2 2.17.1:

| layer | what | where it lives | status |
|---|---|---|---|
| **1. cell-size fork** | 16/20/24/32/40-bit hash cells | `kraken2/src/` (permanent) | in use — the four benchmark DBs |
| **2. lookaside cache** | single-table minimizer→taxon cache | `scratch_lookaside/src/` (experiment) | measured, **not adopted** |

Layer 1 is production code for this project. Layer 2 is an experiment that was
built, measured, and concluded against. Neither has been merged into
`kraken2_bin/`, which is still the untouched 2.17.1 build every measurement
compares against.

---

## Part 1 — how kraken2 works

### The programs

`make` produces eight binaries. Only three matter here:

| program | job |
|---|---|
| **`build_db`** | reference genomes → the hash table (`hash.k2d`) |
| **`classify`** | reads → taxon calls (the thing we benchmark) |
| `dump_table` | prints a built table as text |
| `estimate_capacity`, `k2mask`, `merge`, `lookup_accession_numbers`, `blast_to_fasta` | build-time helpers |

### The source files, by role

| file | lines | role |
|---|---:|---|
| `classify.cc` | 1185 | the classifier: CLI, threading, per-read logic |
| `compact_hash.h` | 504 | **the hash table** — cell layouts, `Get`, `LoadTable` |
| `mmscanner.cc/.h` | 222 | sliding-window minimizer extraction |
| `seqreader.h`, `kseq.h` | 429 | FASTA/FASTQ parsing |
| `taxonomy.cc/.h` | 403 | NCBI tree, LCA queries |
| `reports.cc` | 261 | the `-R` abundance report |
| `build_db.cc/.h` | 671 | database construction |
| `kv_store.h` | 79 | abstract key→value interface + `MurmurHash3` |
| `hyperloglogplus.cc` | 866 | distinct-minimizer estimates for `-K` reports |
| `aa_translate.cc` | 102 | 6-frame protein translation |

### The classification data path

```
FASTQ  →  seqreader     read a sequence
       →  MinimizerScanner::NextMinimizer()      ~1 minimizer per base
       →  MurmurHash3(minimizer)
       →  CompactHashTable::Get()   ← 43.4% of all cycles
       →  hit_counts[taxon]++
       →  ResolveTree()             walk the taxonomy, pick the call
       →  output line + report counters
```

`ClassifySequence()` (line 801) holds the hot loop. Two details of it matter
for everything below:

- a **depth-1 cache** already exists: `last_minimizer` / `last_taxon` skip the
  lookup when consecutive k-mers share a minimizer, which they usually do
- `minimizer_hit_groups++` sits inside that branch and feeds the
  `--minimum-hit-groups` rule — moving it silently changes calls

### The hash table

Open addressing, **73% load factor**, `-DLINEAR_PROBING` so the probe step is 1
and a chain walks adjacent cells (16 per 64-byte line). Each cell packs a
fingerprint and a taxid into one word:

```
32-bit cell = 26-bit fingerprint | 6-bit value
```

`Get()` is: hash → `hc % capacity_` → compare fingerprints → step by 1 on
collision. Measured **0.936 DRAM accesses per lookup** — essentially the floor.

---

## Part 2 — Layer 1: the cell-size fork

**Patch:** `scripts/kraken2_cellsize_v2.patch` (+158 lines, 6 files)
**Purpose:** let the hash cell be narrower than 32 bits, to shrink the database.

| file | what we added |
|---|---|
| `compact_hash.h` | **+99** — `CompactHashCell16/20/24/40`, each with the same `hashed_key`/`value` interface over a different word width |
| `kv_store.h` | +9 — `CompactHash16/20/24` enum values, and width detection from the file header (`key_bits + value_bits`) |
| `build_db.cc` | +16 — dispatch on `--cell-size` to the right template instantiation |
| `build_db.h` | **+4** — the critical one (below) |
| `classify.cc` | +9 — pick the right template when loading a DB |
| `dump_table.cc` | +15 — same dispatch for the dump tool |

**The one line that matters**, in `build_db.h`:

```c
size_t total_bits = opts.cht_cell_size;     // was: sizeof(Cell) * 8
```

A 20-bit cell is *stored* in a 3-byte word, so `sizeof(Cell)*8` reports 24. With
the old line, asking for 20-bit silently built a 24-bit database. This is why
`eskape_20bit` and `eskape_24bit` are the same file size but not the same file.

**Result:** four databases — 16-bit (24.4 MB), 20-bit (36.6 MB), 24-bit
(36.6 MB), 32-bit (48.8 MB). The 32-bit one is the project baseline.

---

## Part 3 — Layer 2: the lookaside cache (current, simplified)

**Where:** `scratch_lookaside/src/` — binary `scratch_lookaside/bin/classify_cache`.

| file | change | why |
|---|---|---|
| `kv_store.h` | **+1** | `virtual hvalue_t GetWithHash(hkey_t, uint64_t) const = 0;` |
| `compact_hash.h` | **+6/−1** | split `Get()` into `Get()` → `GetWithHash()` |
| `classify.cc` | **+~120/−3** | one table, one policy, three flags |

### `GetWithHash` — the only change with standalone value

The cache computes a hash to find its slot; the old `Get()` computed the same
hash again. Splitting the entry point removes the duplicate work. Verified
byte-identical output. **It is also the hook software prefetching needs** —
compute addresses in one pass, fetch values in another — so it is worth keeping
even though the cache was rejected.

### The cache

One table, sized to sit in L3, probed before the main hash table. Starts empty
and fills itself while classifying — no profile, no training pass.

```
-L <MB>    enable, power-of-two size in MB
-N <ways>  associativity, 1|2|4|8|16 (default 4)
-J <n>     admit one miss in n (default 8; 1 admits every miss)
```

**Replacement: random within the set.** Chosen as the cheapest possible option,
for three measured reasons: the table is ~43x oversubscribed (1 M slots vs
42.8 M distinct minimizers) so victim choice has little leverage; recency is a
weak predictor here (exact-LRU 14.97% vs frequency-selection 25.28% at the same
size); and LRU/LFU need metadata written on every **hit**, which would turn a
read-shared table into cache-line ping-pong across 16 threads — with no spare
bits in the 4-byte cell to hold a counter anyway.

**Admission: one miss in `-J`.** This is where the leverage is. 63.4% of
distinct minimizers occur exactly once (29.9% of lookups) and no replacement
policy can undo admitting them. Probabilistic admission is frequency-biased with
zero metadata: a minimizer seen *f* times gets ~*f* chances at 1/K, so
P(admit) = 1 − (1 − 1/K)^f — at K=8 that is 12.5% for f=1, 74% for f=10, ~100%
for f=100.

**A saturation bug this replaced.** The previous 2-hit bitmap filter used 4.19 M
bits against 42.8 M distinct minimizers. After ~20 M keys, 99.2% of bits are set,
so it reported "seen before" for everything and admitted everything. It had been
silently disabled by its own saturation, which is why `admit` and `learn`
measured the same.

**Insertion point** — inside `ClassifySequence`, replacing one line:

```c
if (! skip_lookup) {
  if (la_tab) {
    uint64_t la_hc  = MurmurHash3(*minimizer_ptr);
    uint32_t la_fp  = (uint32_t)(la_hc >> (64 - la_kbits));
    size_t   la_set = la_hc & la_setmask;
    if (! la_probe(la_set, la_fp, taxon)) {
      taxon = hash->GetWithHash(*minimizer_ptr, la_hc);
      if (la_admit_k <= 1 || (la_rnd() % (uint32_t) la_admit_k) == 0)
        la_insert(la_set, la_fp, taxon);
    }
  }
  else taxon = hash->Get(*minimizer_ptr);      // unchanged path
}
```

The depth-1 skip and `minimizer_hit_groups++` are **untouched**.

### Thread safety

Every write is a **single naturally-aligned 4-byte atomic store**, so a reader
sees the old entry or the new one, never a mixture. No locks. Racing writers
lose an insert, which costs a future lookup, not a wrong answer.

### Removed along the way

L1/L2 tiers; `-Y` and its four learning modes; `-F` (compact only now); `-W`
(orphaned); `-A` and `-Z` (the oracle profile and the hit-rate counter).
kraken2's own `-K` was briefly taken over by mistake and has been given back;
admission uses `-J`.

**Consequence of removing `-Z`:** hit rate can no longer be measured, so policy
choices rest on reasoning plus timing, not on observed hit rates.

## Part 4 — what we did NOT touch

| untouched | why it matters |
|---|---|
| `mmscanner.cc` | 17.6% of cycles, second-biggest hotspot — never modified |
| `taxonomy.cc`, `reports.cc` | calls and abundances come out identical |
| `seqreader.h`, `kseq.h` | parsing untouched |
| `hyperloglogplus.cc` | `-K` reports unaffected |
| `build_db.*` (layer 2) | no database was rebuilt for the cache work |
| `ResolveTree`, `AddHitlistString` | the call logic is stock |
| **`kraken2_bin/`** | still the Jul 8 2.17.1 build — every benchmark's baseline |

The hash table's own `Get()` logic is also unchanged: `GetWithHash` is a pure
refactor, verified byte-identical.

---

## Part 5 — what it all measured

| change | outcome |
|---|---|
| cell-size fork (layer 1) | **kept** — enables the 16/20/24-bit DBs and the `-M` work |
| `GetWithHash` | **keep** — free, and the hook prefetching needs |
| lookaside, single tier | no speedup above the ±1.5% noise floor |
| lookaside, set-associative | hit rate 25.1% → 28.5%, runtime **worse** |
| lookaside, 3-tier hierarchy | **60/60 configurations slower**, +3.7% to +28% |
| runtime learning | 12.3% hit vs the oracle's 29.5% |

The cache works — up to 26.2% of lookups avoid DRAM — and the program still gets
slower, because the probe cost grows faster than the memory saving. Full numbers
in `../results/lookaside_sweep/REPORT.md` and `LOOKASIDE_REPORT.md`.

---

## Part 6 — the second fork (`kraken2_laptop/`)

A parallel copy of the cell-size work exists and is **not** used by anything we
measure.

| | `kraken2/` | `kraken2_laptop/` |
|---|---|---|
| upstream base | `7c0eb91` | `bb1162f` (14 May) |
| cell structs | 16/20/24/32/40 | 16/20/24/32/40 — same |
| `--cell-size` accepted | 16 20 24 32 40 | 16 20 24 32 40 — same |
| `build_db.h` width fix | present | present |
| `kv_store.h`, `classify.cc`, `dump_table.cc` | — | **byte-identical** |
| `compact_hash.h`, `build_db.{cc,h}` | — | differ (comments, struct order) |
| binary | `src/classify` md5 `c1cb1c3c` | md5 `747a2cf6` |

**`kraken2/src/classify` md5 `c1cb1c3c` is identical to `kraken2_bin/classify`**,
which every benchmark in this project uses as the baseline. `kraken2_laptop_bin/`
matches its own tree and is self-consistent, but no result depends on it.

Conclusion: functionally redundant, ~50 MB with its binaries, safe to delete once
someone confirms nothing external references it.

---

## Part 7 — software prefetch (`-B`), the one change that helps

**Binary:** `scratch_lookaside/bin/classify_prefetch`. Built from pristine
sources so the effect is isolated from the cache work.

| file | change |
|---|---|
| `kv_store.h` | `+5` — `GetWithHash(key, hc)` and `Prefetch(hc)` on the interface |
| `compact_hash.h` | `+10` — `__builtin_prefetch(&table_[hc % capacity_], 0, 3)`; `Get()` becomes a wrapper over `GetWithHash` |
| `classify.cc` | the inner `while` becomes two passes over a batch, plus `-B` |

**Motivation, measured:** MLP 1.24 of ~12 sustainable; 0.933 DRAM accesses per
lookup x ~200 cycles = ~187 of 868 cycles/lookup exposed to latency.

**Results** (pod5_2, `-p 16`, mean of 3 interleaved reps):

| config | elapsed | vs stock | DRAM/lookup | cyc/lookup | ins/lookup | IPC |
|---|---:|---:|---:|---:|---:|---:|
| stock | 2.700 | — | 0.942 | 892.4 | 983.6 | 1.10 |
| `-B 1` | 2.922 | +8.22% | 0.186 | 957.8 | 1156.5 | 1.21 |
| `-B 8` | 2.663 | −1.37% | 0.138 | 780.5 | 1102.3 | 1.41 |
| `-B 16` | 2.575 | −4.62% | 0.139 | 751.9 | 1098.4 | 1.46 |
| **`-B 32`** | **2.538** | **−5.99%** | 0.141 | **735.4** | 1096.4 | **1.49** |

**Correctness: byte-identical to stock** at `-B` 1/8/16/32, `-p` 1/16, on
pod5_15 and pod5_2 — 16/16 exact.

**Invariants preserved:** the depth-1 `last_minimizer`/`last_taxon` skip;
`minimizer_hit_groups++` placement; `taxa.push_back` ordering; `quick_mode`
early exit. Two subtleties: `scanner.is_ambiguous()` is captured per-entry
because scanner state advances during pass 1, and `add_kmer()` uses the captured
minimizer rather than `scanner.last_minimizer()` for the same reason (they are
equal — `NextMinimizer()` returns `&last_minimizer_`, mmscanner.cc:146/156/188).

**Why DRAM/lookup falls 85%** (0.942 → 0.14): the prefetch lands the line before
`GetWithHash` runs, so the access no longer retires as an LLC-load-miss. The
traffic still occurs; it has left the critical path and the miss counter.

**The honest cost:** `-B 1` executes the same logic as stock and is 8.22%
slower, at 1156 vs 984 instructions/lookup. That is the batching machinery
itself. Net gain against the *same* code path is `-B 1` -> `-B 32` = **13%**;
6% survives against stock.

---

## Loose ends (whole project)

- **`-W` is orphaned.** It writes frequency profiles, but `-A` (which read them)
  was removed, so nothing consumes the files. It should probably go.
- **`scripts/kraken2_lookaside.patch` is stale.** Generated 02:02, before the
  runtime-learning work, and it still contains the removed `-A`/`-Z`. The live
  code is `scratch_lookaside/src/`.
- **`scripts/kraken2_fork_cellsize.patch` is superseded** by
  `kraken2_cellsize_v2.patch` — it lacks 20-bit support and the `build_db.h` fix.
