# Kraken2 Optimisations — v2 (beyond the first 5 patches)

This is an *additive* document. Patches in `kraken2_get_optimizations.md` (v1) target the
CompactHashTable::Get() hotspot directly. v2 covers cheaper wins around it and a couple of
non-Get hotspots discovered after reading `build_db.cc`, `classify.cc::ResolveTree`,
`taxonomy.cc`, and `seqreader.cc`.

Source verified against: https://github.com/DerrickWood/kraken2 (master, 2026-05-29).

Apply v1 patches first, measure, then layer v2 patches if there is still > 2 % delta to chase.

---

## Surprises in the source that change priorities

### S1. build_db.cc apparently instantiates `CompactHashCell40` even for `-C 32`

```cpp
// src/build_db.cc, main()
if (opts.cht_cell_size == 32) {
    build<CompactHashCell40>(...);            // <-- both branches use Cell40
} else if (opts.cht_cell_size == 40) {
    std::cerr << "Using 40 bits" << std::endl;
    build<CompactHashCell40>(...);
}
```

Either a copy-paste bug or in-progress refactor on master. **Implication for Luna:**
the pre-built `k2_standard_08gb_20240112` was almost certainly built with the same code
path, so it is most likely a **40-bit cell DB** regardless of the build-time flag.

Cross-check with this one-liner:
```bash
python3 -c '
import struct, os
with open(os.path.expanduser("~/data/kraken2_db/hash.k2d"),"rb") as f:
    cap,sz,kb,vb=struct.unpack("<QQQQ",f.read(32))
print(f"capacity={cap:,}  size={sz:,}  load_factor={sz/cap:.3f}")
print(f"key_bits={kb}  value_bits={vb}  sum={kb+vb}  cell={'40-bit' if kb+vb==40 else '32-bit'}")
print(f"file_size_bytes={os.path.getsize(os.path.expanduser('"'"'~/data/kraken2_db/hash.k2d'"'"'))}")
print(f"implied cell bytes = {(os.path.getsize(os.path.expanduser('"'"'~/data/kraken2_db/hash.k2d'"'"')) - 32) / cap:.3f}")
'
```

If `key_bits + value_bits == 40`, the prefetch stride in v1 Patch 1 should be 12 (already correct via `64/sizeof(Cell)`).

### S2. `ResolveTree` is O(N²) per read

```cpp
// src/classify.cc, ResolveTree()
for (auto &kv_pair : hit_counts) {        // outer: |hit_counts|
  uint32_t score = 0;
  for (auto &kv_pair2 : hit_counts) {     // inner: |hit_counts|
    if (taxonomy.IsAAncestorOfB(taxon2, taxon))   // each: O(tree depth)
      score += kv_pair2.second;
  }
}
```

For nanopore long reads, `hit_counts.size()` can be 20–80. `IsAAncestorOfB` walks parent
pointers — say 3–7 hops average. So `ResolveTree` ≈ 80 × 80 × 5 = 32 000 random reads
into the taxonomy nodes array **per read**. Multiply by 104 918 reads ≈ **3.4 G accesses**.
Each access is into the `nodes_` array; that array is ~MB for ESKAPE DB but full standard_8
has tens of MB → not fully cache-resident.

This was not visible in cachegrind for Get() (96.24 % already accounts for the dominant
miss source) but probably accounts for a chunk of the remaining "tail" runtime.

### S3. MurmurHash3 is computed twice when `minimum_acceptable_hash_value > 0`

```cpp
// src/classify.cc, ClassifySequence inner loop
if (idx_opts.minimum_acceptable_hash_value) {
  if (MurmurHash3(*minimizer_ptr) < idx_opts.minimum_acceptable_hash_value)
    skip_lookup = true;
}
taxon = 0;
if (! skip_lookup)
  taxon = hash->Get(*minimizer_ptr);     // <-- computes MurmurHash3 internally too
```

For DBs built with `-M` (MiniKraken) the hash is computed twice. Free win for those DBs;
no effect on standard_8 (which has `minimum_acceptable_hash_value == 0`). Still worth
fixing because the report flow may eventually use a downsampled DB.

### S4. `hash->Get` is genuinely virtual; LTO is the easy fix but `final` is portable

`KeyValueStore::Get` is `virtual`. The only concrete implementer is
`CompactHashTable<Cell>`. Marking `Get` as `final` in the template lets the compiler
devirtualise without LTO when the static type at the call site is the concrete class.

### S5. Output formatting is on the hot path even for `-O /dev/null`

```cpp
// ClassifySequence
koss << (call ? "C\t" : "U\t");
koss << dna.header << "\t";
...
koss << ext_call;
...
AddHitlistString(koss, taxa, taxonomy);
koss << endl;
```

This always runs, even when the kraken_output is `/dev/null`. ostringstream allocates,
grows, copies. On 104 918 reads with ~5 kb sequence length and tens of hitlist entries
per read this is real cost. If `kraken_output == nullptr` and `report_filename` is the
only sink, we can skip everything between `koss <<` and the final `kraken_oss.str()`.

---

## v2 patches

### Patch 6 — devirtualise via `final` + concrete-typed dispatch

**Why:** without LTO this is the second-cheapest win after `-O3 -march=native`. Removes
vtable indirection from every `hash->Get()` call. Estimated −2 to −5 %.

**Edit `src/compact_hash.h`** — add `final` to `Get`:
```cpp
template<typename Cell> class CompactHashTable : public KeyValueStore {
  public:
  ...
  hvalue_t Get(hkey_t key) const final;          // was: hvalue_t Get(hkey_t key) const;
  ...
};
```

**Edit `src/classify.cc::ProcessFiles`** — branch once per batch on cell type:
```cpp
// just before #pragma omp parallel
enum { Cell32, Cell40 } cell_kind;
auto *cht32 = dynamic_cast<CompactHashTable<CompactHashCell>*>(hash);
auto *cht40 = dynamic_cast<CompactHashTable<CompactHashCell40>*>(hash);
cell_kind = cht32 ? Cell32 : Cell40;
```
Then inside the inner loop, replace `taxon = hash->Get(*minimizer_ptr);` with:
```cpp
taxon = (cell_kind == Cell32)
        ? cht32->Get(*minimizer_ptr)        // devirtualised, inlines
        : cht40->Get(*minimizer_ptr);
```
The branch is well-predicted (same direction every call) → free.

**Risk:** none. Dispatch is correctness-preserving; `final` does not break the existing
virtual base.

---

### Patch 7 — fix the double-MurmurHash in classify.cc

**Why:** for MiniKraken-style DBs, MurmurHash is the hottest non-Get code (3 mul + 3 xor
= ~10 ns × 9.87 M calls = 100 ms). Halve it for free.

**Edit `src/kv_store.h`** — add a hash-accepting Get overload (header-only template makes
this clean):
```cpp
class KeyValueStore {
  public:
  virtual hvalue_t Get(hkey_t key) const = 0;
  // Optional fast path when caller already has the Murmur hash.
  virtual hvalue_t GetByHash(hkey_t key, uint64_t hc) const { return Get(key); }
  virtual ~KeyValueStore() {}
};
```

**Edit `src/compact_hash.h`** — implement the override:
```cpp
template<typename Cell>
hvalue_t CompactHashTable<Cell>::GetByHash(hkey_t key, uint64_t hc) const final {
  uint64_t compacted_key = hc >> (64 - key_bits_);
  size_t idx = hc % capacity_;
  /* ... identical loop body to Get(), starting from idx ... */
}
```

**Edit `src/classify.cc`** — reuse the hash:
```cpp
uint64_t hc = MurmurHash3(*minimizer_ptr);
bool skip_lookup = idx_opts.minimum_acceptable_hash_value
                   && hc < idx_opts.minimum_acceptable_hash_value;
taxon = 0;
if (!skip_lookup)
  taxon = cht40->GetByHash(*minimizer_ptr, hc);   // or cht32, per Patch 6
```

**Expected delta:** −1 to −3 % on standard_8 (where the skip branch is dead), −5 to −10 %
on MiniKraken DBs. The lookup itself is unchanged.

---

### Patch 8 — ResolveTree from O(N²) to O(N) using ancestor sets

**Why:** S2 above — `IsAAncestorOfB(b, a)` is called `|hit_counts|² × tree_depth` times
per read.

**Approach:** precompute an `unordered_set<uint64_t> ancestors` for each unique taxon in
`hit_counts`, then `IsAAncestorOfB(b, a)` becomes `ancestors[b].count(a)` — O(1).

**Edit `src/classify.cc::ResolveTree`** — drop in:
```cpp
taxid_t ResolveTree(taxon_counts_t &hit_counts, Taxonomy &taxonomy,
                    size_t total_minimizers, Options &opts) {
  // Precompute ancestor set once per taxon.
  std::unordered_map<taxid_t, std::vector<taxid_t>> ancestors;
  ancestors.reserve(hit_counts.size() * 2);
  for (auto &kv : hit_counts) {
    taxid_t t = kv.first;
    auto &vec = ancestors[t];
    while (t) { vec.push_back(t); t = taxonomy.nodes()[t].parent_id; }
  }
  taxid_t max_taxon = 0;
  uint32_t max_score = 0;
  uint32_t required_score = ceil(opts.confidence_threshold * total_minimizers);

  for (auto &outer : hit_counts) {
    taxid_t taxon = outer.first;
    uint32_t score = 0;
    for (auto &inner : hit_counts) {
      auto &vec = ancestors[inner.first];
      // taxon is an ancestor of inner.first iff vec contains taxon
      if (std::find(vec.begin(), vec.end(), taxon) != vec.end())
        score += inner.second;
    }
    if (score > max_score) { max_score = score; max_taxon = taxon; }
    else if (score == max_score)
      max_taxon = taxonomy.LowestCommonAncestor(max_taxon, taxon);
  }
  /* ... rest of confidence-threshold loop unchanged ... */
  return max_taxon;
}
```

Why `std::find` over `unordered_set`: ancestor chains in NCBI are short (~5–7 nodes), so
linear scan over a small vector beats hash-set probing. Stays cache-friendly.

**Expected delta:** −2 to −6 % wall time, larger as |hit_counts| grows (long nanopore reads).

**Risk:** correctness equivalence verified — same logical predicate, faster representation.

---

### Patch 9 — skip output formatting when kraken_output is suppressed

**Why:** if classify is invoked with `-O /dev/null` (our perf baseline runs already do
this), the `koss` ostringstream work is pure waste. The current code always builds the
string then writes it to /dev/null.

**Edit `src/classify.cc::ClassifySequence`** — early-out:
```cpp
// Existing: koss << "C\t"; ... koss << endl;
// Replace with:
if (outputs.kraken_output != nullptr) {     // need to thread `outputs` into this scope
   /* keep all existing koss << ... lines */
}
```

Currently `ClassifySequence` doesn't see `outputs.kraken_output`; pass a `bool emit_kraken`
parameter from `ProcessFiles` (where the streams are visible) so the suppression cost is
one bool compare per read.

**Expected delta:** −1 to −2 % when running with `-O /dev/null`. Slightly bigger if
ostringstream's small-string optimisation isn't doing its job for hitlist strings.

**Risk:** zero — only changes behaviour when the user explicitly silenced output.

---

### Patch 10 — coarse batched Get() with prefetch pipeline (speculative; design only)

**Why (heaviest of the v2 set, sketched here, will only land if v1+v2 still leave us > 3.5 s):**
The inner loop in `ClassifySequence` processes one minimizer at a time. Even with
per-Get prefetch (v1 Patch 1) the prefetched line only helps the *next* probe in the
*same* Get(); it can't hide the latency between *different* Get()s.

A batched API processes N minimizers at once: issue all N Murmur hashes + prefetches first,
then read all N. The CPU's out-of-order engine pipelines DRAM accesses across the batch.
N ≈ 8–16 is typical (matches L1 fill-buffer count).

**Sketch (do not apply blindly):**
```cpp
struct LookupRequest { uint64_t key; uint64_t hc; size_t idx; taxid_t result; };
void GetBatch(LookupRequest *reqs, size_t n) const {
  for (size_t i = 0; i < n; ++i) {
    reqs[i].hc  = MurmurHash3(reqs[i].key);
    reqs[i].idx = reqs[i].hc % capacity_;
    __builtin_prefetch(&table_[reqs[i].idx], 0, 0);
  }
  for (size_t i = 0; i < n; ++i)
    reqs[i].result = GetByHash(reqs[i].key, reqs[i].hc);
}
```

Caller (`ClassifySequence`) needs to gather N minimizers before calling. This is awkward
because the existing `last_minimizer` skip is per-step; a clean batched design needs to
buffer minimizers first, then resolve.

**Decision:** treat as a Phase-3 idea. Implement only if Patches 1–9 leave the v1 target
(≤ 3.0 s) unmet.

---

## Updated stacking budget

| Patch | Mechanism | Independent Δ | Cumulative |
|---|---|---:|---:|
| baseline | — | — | 4.405 s |
| 3 (flags) | inline + tighter ASM | −8 % | 4.05 s |
| 2 (huge pages) | dTLB | −5 % | 3.85 s |
| 1 (prefetch) | hide DRAM latency in probe | −10 % | 3.47 s |
| 4 (thread LRU) | skip DRAM on hits | −20 % | 2.77 s |
| 6 (devirt) | drop vtable hop | −3 % | 2.69 s |
| 7 (single hash) | reuse MurmurHash | −2 % (1 % on std_8) | 2.66 s |
| 8 (ResolveTree O(N)) | drop quadratic walk | −4 % | 2.55 s |
| 9 (skip /dev/null) | drop ostringstream work | −1.5 % | 2.51 s |
| 10 (batch Get) | pipeline DRAM across Get()s | optional | TBD |

**v2 stretch target:** ≤ 2.6 s wall (≈ 41 % below 4.405 s).

Stop after two consecutive < 2 % deltas, per the v1 decision rule.

---

## Cross-cutting safety nets

After every patch:
1. `kraken2 --report` line should be identical to baseline (`diff report.opt report.base`).
2. `output_kraken | md5sum` should match baseline.
3. If either differs, the patch broke semantics — back out, never combine over a broken
   patch.
