# Kraken2 Cell-Size Port — Adding 16 / 24-bit Cells to a Fresh `DerrickWood/kraken2` Clone

**Date:** 2026-07-03 · **Purpose:** on another desktop where Kraken2 is a **plain clone of
`github.com/DerrickWood/kraken2`**, add `-C 16` / `-C 24` support so `hash.k2d` can shrink below
the stock 4 B/cell. Verified against stock `master` on 2026-07-03.

---

## 0. Key insight — stock already does most of it

I diffed the current upstream `DerrickWood/kraken2/master` against this project's fork. **Stock
already ships** the whole variable-cell framework — it just stops at 32 and 40:

| Already in stock master | Missing (what you add) |
|---|---|
| `CompactHashTable<Cell>` is **templated** | — |
| structs `CompactHashCell` (32 B/4) + `CompactHashCell40` | structs `CompactHashCell16`, `CompactHashCell24` |
| `enum CellType { CompactHash32, CompactHash40, … }` | enumerators `CompactHash16`, `CompactHash24` |
| `GetKVStoreCellType()` detector (cases 32, 40) | detector cases `16`, `24` |
| `build_db` `-C` flag, default 32, dispatch for 32/40 | dispatch + `-C` validation for 16/24 |
| `classify` / `dump_table` auto-detect + dispatch 32/40 | their 16/24 arms |
| `build_db.h`: `Options.cht_cell_size`, `-r`, `build<Cell>` uses `sizeof(Cell)*8` | **nothing — no change to `build_db.h`** |
| taxid-vs-cell safety guard | **absent in stock — you add it** (matters at 16-bit) |

So this is **not** a refactor. It is: *"wherever stock handles the `40` case, add a `16` and a
`24` case beside it,"* plus one new guard. **5 files, all additive.**

> **Do NOT touch** stock's `posix_memalign` + `MADV_HUGEPAGE` allocation, the parallel-`pread`
> loader, or `GetBatch()` prefetch in `compact_hash.h` — those are stock perf features (newer than
> this project's fork). Leave them; only insert the two structs.

---

## 1. `src/compact_hash.h` — add two structs

Stock has `CompactHashCell` then `CompactHashCell40`. Insert `CompactHashCell16` after the 32-bit
struct, and `CompactHashCell24` after the 40-bit struct (mirrors the fork layout).

**`CompactHashCell16`** (single `uint16_t`):

```cpp
struct CompactHashCell16 {
  inline hkey_t   hashed_key(size_t value_bits) { return (hkey_t)(data >> value_bits); }
  inline hvalue_t value(size_t value_bits)      { return (hvalue_t)(data & ((1 << value_bits) - 1)); }

  void populate(hkey_t compacted_key, hvalue_t val, size_t key_bits, size_t value_bits) {
    if (key_bits + value_bits != 16)
      errx(EX_SOFTWARE, "key len of %u and value len of %u don't sum to 16",
           (unsigned)key_bits, (unsigned)value_bits);
    if (!key_bits || !value_bits) errx(EX_SOFTWARE, "key len and value len must be nonzero");
    uint64_t max_value = (1llu << value_bits) - 1;
    if (max_value < val) errx(EX_SOFTWARE, "value len of %u too small for value of %llu",
                              (unsigned)value_bits, (unsigned long long)val);
    data = (uint16_t)((compacted_key << value_bits) | val);
  }
  uint16_t data;
};
```

**`CompactHashCell24`** (`uint16_t a; uint8_t b;` — packed; key straddles the two fields):

```cpp
struct CompactHashCell24 {
  uint16_t a;
  uint8_t  b;

  inline hkey_t hashed_key(size_t value_bits) {
    size_t key_bits = 16 - value_bits;
    return (a >> value_bits | b << key_bits);
  }
  inline hvalue_t value(size_t value_bits) { return (hvalue_t)(a & ((1 << value_bits) - 1)); }

  void populate(hkey_t compacted_key, hvalue_t val, size_t key_bits, size_t value_bits) {
    if (key_bits + value_bits != sizeof(CompactHashCell24) * 8)
      errx(EX_SOFTWARE, "key len of %u and value len of %u don't sum to %d",
           (unsigned)key_bits, (unsigned)value_bits, (unsigned)(sizeof(CompactHashCell24) * 8));
    if (!key_bits || !value_bits) errx(EX_SOFTWARE, "key len and value len must be nonzero");
    uint64_t max_value = (1llu << value_bits) - 1;
    if (max_value < val) errx(EX_SOFTWARE, "value len of %u too small for value of %llu",
                              (unsigned)value_bits, (unsigned long long)val);
    size_t value_mask = (1 << value_bits) - 1;
    val = val & value_mask;
    size_t a_bits = 16 - value_bits;
    b = compacted_key >> a_bits;
    a = ((compacted_key & ((1 << a_bits) - 1)) << value_bits) | val;
  }
} __attribute__((packed));
```

Keep `__attribute__((packed))` — without it `sizeof(CompactHashCell24)` rounds to 4 and both the
file size and the `total_bits = sizeof(Cell)*8` math break.

---

## 2. `src/kv_store.h` — extend the enum + detector

Stock enum has `CompactHash32, CompactHash40`. Add the two twins **and keep the ordering by width**
(the detector switches on `key_bits + value_bits`, so the enum order is cosmetic but keep it tidy):

```cpp
enum CellType {
  CompactHash16,   // add
  CompactHash24,   // add
  CompactHash32,
  CompactHash40,
  Unknown,
};
```

In `GetKVStoreCellType()`, add the two cases beside the existing 32/40:

```cpp
  switch (key_bits + value_bits) {
    case 16: return CompactHash16;   // add
    case 24: return CompactHash24;   // add
    case 32: return CompactHash32;
    case 40: return CompactHash40;
    default: return Unknown;
  }
```

---

## 3. `src/build_db.cc` — dispatch, `-C` validation, and the new guard

**(a) Dispatch** — stock has the 32/40 `if/else`. Add the 16/24 arms:

```cpp
  if (opts.cht_cell_size == 16) {
    build<CompactHashCell16>(taxonomy, ID_to_taxon_map, opts, actual_capacity, bits_for_taxid);
  } else if (opts.cht_cell_size == 24) {
    build<CompactHashCell24>(taxonomy, ID_to_taxon_map, opts, actual_capacity, bits_for_taxid);
  } else if (opts.cht_cell_size == 32) {
    build<CompactHashCell>(taxonomy, ID_to_taxon_map, opts, actual_capacity, bits_for_taxid);
  } else if (opts.cht_cell_size == 40) {
    build<CompactHashCell40>(taxonomy, ID_to_taxon_map, opts, actual_capacity, bits_for_taxid);
  } else {
    errx(EX_DATAERR, "Unsupported CHT cell size");
  }
```

**(b) `-C` validation** — stock accepts only 32/40. Widen it:

```cpp
    case 'C':
      sig = atoll(optarg);
      if (sig != 16 && sig != 24 && sig != 32 && sig != 40)
        errx(EX_USAGE, "CHT cell size should be 16, 24, 32, or 40 bits");
      opts.cht_cell_size = sig;
      break;
```

**(c) New safety guard** — stock has **no** check that the taxid fits the cell. Harmless at 32/40,
but at 16-bit a DB with too many taxa would silently overflow the value field. Add, right after
`bits_for_taxid` is finalised (just before the dispatch block):

```cpp
  if (bits_for_taxid >= opts.cht_cell_size)
    errx(EX_DATAERR,
         "taxid needs %u bits but CHT cell size is only %u bits; use a larger -C",
         (unsigned)bits_for_taxid, (unsigned)opts.cht_cell_size);
```

No other `build_db.cc` change — default `cht_cell_size = 32`, the `-r` flag, and `-C`/`-r` in the
getopt string are all already in stock.

---

## 4. `src/classify.cc` — add two load arms

Stock's `load_index()` already `switch`es on `GetKVStoreCellType()` for 32/40. Add:

```cpp
  case CompactHash16:
    cht = new CompactHashTable<CompactHashCell16>(opts.index_filename, opts.use_memory_mapping);
    break;
  case CompactHash24:
    cht = new CompactHashTable<CompactHashCell24>(opts.index_filename, opts.use_memory_mapping);
    break;
```

`classify` still needs **no** cell-size flag — the width is read from the DB header.

---

## 5. `src/dump_table.cc` — add two dump arms

Beside the existing 32/40 cases:

```cpp
  case CompactHash16: {
    CompactHashTable<CompactHashCell16> ht(opts.hashtable_filename, opts.memory_mapping);
    dump_table<CompactHashCell16>(ht, opts); break; }
  case CompactHash24: {
    CompactHashTable<CompactHashCell24> ht(opts.hashtable_filename, opts.memory_mapping);
    dump_table<CompactHashCell24>(ht, opts); break; }
```

---

## 6. Wrappers

- **`scripts/build_kraken2_db.sh`** — its `build_db …` line does not pass `-C` (always 32). Add
  `-C $CELL` there only if you drive builds through this shell wrapper.
- **`scripts/kraken2-build`** (perl) / **`k2`** (python) — stock master's `k2` may lack
  `--cht-cell-size`. Building `build_db` **directly** with `-C 16` needs no wrapper edit; that's the
  simplest path for a quick DB.

---

## 7. Build & verify

```bash
# in the cloned repo root
make -C src            # or ./install_kraken2.sh <dest> to install the wrappers+binaries

build_db --help | grep -- '-C'          # shows the cell-size option
```

Build the same tiny DB at three widths and confirm size ∝ bytes/cell:

```bash
for C in 16 24 32; do
  build_db -C $C -H hash_$C.k2d -o opts_$C.k2d -t taxo.k2d -n taxonomy/ \
           -m seqid2taxid.map -k 35 -l 31 -c <capacity> ...
  ls -l hash_$C.k2d          # expect ratio 2 : 3 : 4 bytes per cell at equal capacity
done

dump_table -H hash_16.k2d | head        # loads with NO flag → detector works
classify --db <dir_with_hash_16> reads.fq > out16   # 16-bit DB classifies
```

**Expect** `hash_16 : hash_24 : hash_32 = 2 : 3 : 4` bytes/cell; `classify` gives taxid assignments
identical to 32-bit **when key_bits still clears the collision floor** (ESKAPE: `value_bits = 6`, so
16-bit leaves 10 key bits — safe; verify accuracy, don't assume — see
[`eskape_cellsize_fp_analysis.md`](eskape_cellsize_fp_analysis.md)).

---

## 8. Gotchas

- **Taxid must fit:** `bits_for_taxid < cell_width`. A many-taxon DB won't build at `-C 16`
  (that's the `-C 40` use case). ESKAPE-scale (6 taxa → `value_bits = 6`) is fine at 16.
- **Narrower cell ⇒ fewer key bits ⇒ higher false-positive rate** (`FP ≈ probe_len × 2^−key_bits`).
  16-bit is the aggressive end.
- **Fill stays ~70 %** — cell width changes *bytes per slot*, never slot count; probe behavior
  is unchanged. Shrinking `-c` (capacity) is the *worse* lever (fill rises → super-linear probe/FP
  blow-up). See [`eskape_cellsize_sweep.md`](eskape_cellsize_sweep.md) §2.
- **Leave stock's perf code alone** — hugepage alloc, parallel `pread` load, `GetBatch` prefetch in
  `compact_hash.h` are unrelated to cell width; don't strip them while adding the structs.
- **One binary reads all widths** — `classify`/`dump_table` auto-detect from the header; no per-DB
  rebuild, no flag.

---

### Appendix — full-file reference (this project's fork)

If you'd rather copy finished files than hand-edit, this project's already-modified copies live in
`tools/kraken2/src/{compact_hash.h,kv_store.h,build_db.cc,build_db.h,classify.cc,dump_table.cc}`.
**Caveat:** the fork is an *older* base and does **not** contain stock master's hugepage/parallel-load/
`GetBatch` perf work — so copy the *cell-size additions*, not whole files, onto a fresh stock clone.
