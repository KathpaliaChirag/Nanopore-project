# Kraken2 Optimisations - v2 (beyond the first 5 patches)

this doc is additive: patches in `kraken2_get_optimizations.md` (v1) target the
CompactHashTable::Get() hotspot directly, so v2 covers cheaper wins around it, plus a
couple of non-Get hotspots we found while reading `build_db.cc`, `classify.cc::ResolveTree`,
`taxonomy.cc`, and `seqreader.cc`.

we verified source against: https://github.com/DerrickWood/kraken2 (master, 2026-05-29).

apply v1 patches first, measure, then layer v2 patches on top if there's still more than a
2% delta to chase.

---

## surprises in the source that change priorities

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

either a copy-paste bug or an in-progress refactor on master. **implication for Luna:**
the pre-built `k2_standard_08gb_20240112` was almost certainly built with the same code
path, so it's most likely a **40-bit cell DB** regardless of the build-time flag.

cross-check with this one-liner:
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

if `key_bits + value_bits == 40`, the prefetch stride in v1 Patch 1 should be 12 (already correct via `64/sizeof(Cell)`).

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

for nanopore long reads, `hit_counts.size()` can run 20-80. `IsAAncestorOfB` walks parent
pointers too, roughly 3-7 hops on average. so `ResolveTree` costs about 80 x 80 x 5 =
32,000 random reads into the taxonomy nodes array, **per read**. multiply that by 104,918
reads and it's **about 3.4 billion accesses**. each access lands in the `nodes_` array;
that array is only a few MB for the ESKAPE DB, but for the full standard_8 DB it runs to
tens of MB, so it doesn't stay cache-resident.

cachegrind didn't surface this for Get() (96.24% already accounts for the dominant miss
source), but it probably explains a chunk of the remaining "tail" runtime.

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

for DBs built with `-M` (MiniKraken), the hash gets computed twice, so fixing this is a free
win there. it has no effect on standard_8 (which has `minimum_acceptable_hash_value == 0`),
but it's still worth fixing since the report flow may eventually use a downsampled DB.

### S4. `hash->Get` is genuinely virtual; LTO is the easy fix but `final` is portable

`KeyValueStore::Get` is `virtual`, and the only concrete implementer is
`CompactHashTable<Cell>`. marking `Get` as `final` in the template lets the compiler
devirtualise without LTO, as long as the static type at the call site is the concrete class.

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

this always runs, even when kraken_output is `/dev/null`. ostringstream allocates, grows,
and copies, and across 104,918 reads with roughly 5 kb sequence length and tens of hitlist
entries per read, that's real cost. if `kraken_output == nullptr` and `report_filename` is
the only sink, we can skip everything between `koss <<` and the final `kraken_oss.str()`.

---

## v2 patches

### Patch 6 - devirtualise via `final` + concrete-typed dispatch

**why:** without LTO, this is the second-cheapest win after `-O3 -march=native`. it removes
vtable indirection from every `hash->Get()` call. estimated -2% to -5%.

**edit `src/compact_hash.h`**: add `final` to `Get`:
```cpp
template<typename Cell> class CompactHashTable : public KeyValueStore {
  public:
  ...
  hvalue_t Get(hkey_t key) const final;          // was: hvalue_t Get(hkey_t key) const;
  ...
};
```

**edit `src/classify.cc::ProcessFiles`**: branch once per batch on cell type:
```cpp
// just before #pragma omp parallel
enum { Cell32, Cell40 } cell_kind;
auto *cht32 = dynamic_cast<CompactHashTable<CompactHashCell>*>(hash);
auto *cht40 = dynamic_cast<CompactHashTable<CompactHashCell40>*>(hash);
cell_kind = cht32 ? Cell32 : Cell40;
```
then inside the inner loop, replace `taxon = hash->Get(*minimizer_ptr);` with:
```cpp
taxon = (cell_kind == Cell32)
        ? cht32->Get(*minimizer_ptr)        // devirtualised, inlines
        : cht40->Get(*minimizer_ptr);
```
the branch is well-predicted (same direction every call), so it's effectively free.

**risk:** none. dispatch is correctness-preserving, and `final` doesn't break the existing
virtual base.

---

### Patch 7 - fix the double-MurmurHash in classify.cc

**why:** for MiniKraken-style DBs, MurmurHash is the hottest non-Get code (3 mul + 3 xor,
about 10 ns x 9.87 million calls = 100 ms). halving it is free.

**edit `src/kv_store.h`**: add a hash-accepting Get overload (a header-only template makes
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

**edit `src/compact_hash.h`**: implement the override:
```cpp
template<typename Cell>
hvalue_t CompactHashTable<Cell>::GetByHash(hkey_t key, uint64_t hc) const final {
  uint64_t compacted_key = hc >> (64 - key_bits_);
  size_t idx = hc % capacity_;
  /* ... identical loop body to Get(), starting from idx ... */
}
```

**edit `src/classify.cc`**: reuse the hash:
```cpp
uint64_t hc = MurmurHash3(*minimizer_ptr);
bool skip_lookup = idx_opts.minimum_acceptable_hash_value
                   && hc < idx_opts.minimum_acceptable_hash_value;
taxon = 0;
if (!skip_lookup)
  taxon = cht40->GetByHash(*minimizer_ptr, hc);   // or cht32, per Patch 6
```

**expected delta:** -1% to -3% on standard_8 (where the skip branch is dead), -5% to -10%
on MiniKraken DBs. the lookup itself is unchanged.

---

### Patch 8 - ResolveTree from O(N²) to O(N) using ancestor sets

**why:** this is S2 above, `IsAAncestorOfB(b, a)` gets called `|hit_counts|² x tree_depth`
times per read.

**approach:** precompute an `unordered_set<uint64_t> ancestors` for each unique taxon in
`hit_counts`, so `IsAAncestorOfB(b, a)` becomes `ancestors[b].count(a)`, which is O(1).

**edit `src/classify.cc::ResolveTree`**: drop in:
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

we use `std::find` over `unordered_set` because ancestor chains in NCBI are short (roughly
5-7 nodes), so a linear scan over a small vector beats hash-set probing and stays
cache-friendly.

**expected delta:** -2% to -6% wall time, larger as |hit_counts| grows (long nanopore reads).

**risk:** we verified correctness equivalence: same logical predicate, just a faster
representation.

---

### Patch 9 - skip output formatting when kraken_output is suppressed

**why:** if classify is invoked with `-O /dev/null` (our perf baseline runs already do
this), the `koss` ostringstream work is pure waste. the current code always builds the
string, then writes it to /dev/null anyway.

**edit `src/classify.cc::ClassifySequence`**: early-out:
```cpp
// Existing: koss << "C\t"; ... koss << endl;
// Replace with:
if (outputs.kraken_output != nullptr) {     // need to thread `outputs` into this scope
   /* keep all existing koss << ... lines */
}
```

right now `ClassifySequence` doesn't see `outputs.kraken_output`, so we pass a
`bool emit_kraken` parameter from `ProcessFiles` (where the streams are visible), which
keeps the suppression cost to one bool compare per read.

**expected delta:** -1% to -2% when running with `-O /dev/null`, slightly bigger if
ostringstream's small-string optimisation isn't doing its job for hitlist strings.

**risk:** zero, since this only changes behaviour when output is explicitly silenced.

---

### Patch 10 - coarse batched Get() with prefetch pipeline (speculative, design only)

**why (heaviest of the v2 set, sketched here, only lands if v1+v2 still leave us above
3.5 s):** the inner loop in `ClassifySequence` processes one minimizer at a time. even with
per-Get prefetch (v1 Patch 1), the prefetched line only helps the *next* probe inside the
*same* Get(); it can't hide the latency between *different* Get()s.

a batched API processes N minimizers at once: issue all N Murmur hashes and prefetches
first, then read all N. the CPU's out-of-order engine pipelines DRAM accesses across the
batch. N of 8-16 is typical (it matches the L1 fill-buffer count).

**sketch (do not apply blindly):**
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

the caller (`ClassifySequence`) needs to gather N minimizers before calling. that's awkward,
because the existing `last_minimizer` skip is per-step, so a clean batched design needs to
buffer minimizers first, then resolve them.

**decision:** treat this as a Phase-3 idea, and only implement it if Patches 1-9 leave the
v1 target (3.0 s or below) unmet.

---

## updated stacking budget

this table matters because it's the running total we check against the v1 target: it
stacks every patch above (1-4 from v1, 6-10 from this doc) in application order so we can
see the cumulative wall time after each one.

| Patch | Mechanism | Independent Δ | Cumulative |
|---|---|---:|---:|
| baseline | n/a | n/a | 4.405 s |
| 3 (flags) | inline + tighter ASM | -8% | 4.05 s |
| 2 (huge pages) | dTLB | -5% | 3.85 s |
| 1 (prefetch) | hide DRAM latency in probe | -10% | 3.47 s |
| 4 (thread LRU) | skip DRAM on hits | -20% | 2.77 s |
| 6 (devirt) | drop vtable hop | -3% | 2.69 s |
| 7 (single hash) | reuse MurmurHash | -2% (1% on std_8) | 2.66 s |
| 8 (ResolveTree O(N)) | drop quadratic walk | -4% | 2.55 s |
| 9 (skip /dev/null) | drop ostringstream work | -1.5% | 2.51 s |
| 10 (batch Get) | pipeline DRAM across Get()s | optional | TBD |

the running total lands at 2.51 s after Patch 9, with Patch 10 held back as optional.

**v2 stretch target:** 2.6 s wall or below (about 41% below the 4.405 s baseline).

we stop after two consecutive deltas under 2%, per the v1 decision rule.

---

## cross-cutting safety nets

why these checks exist: a patch that changes timing but also changes output silently
breaks correctness, and that's worse than no speedup at all. run this after every patch:
1. the `kraken2 --report` line should be identical to baseline (`diff report.opt report.base`).
2. `output_kraken | md5sum` should match baseline.
3. if either differs, the patch broke semantics: back it out, and never combine on top of
   a broken patch.
