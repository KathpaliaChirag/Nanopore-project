# Patch Application — Command Log

Running command-by-command log for applying `kraken2_opt_v1.patch` to `~/tools/kraken2-src` on Luna. Written 2026-08-03, in the session that picked up the "actually apply the patch" task per `dorado-kraken-research/centrifuge/KT_NEXT_SESSION.md`.

Done by hand, not via `run_kraken2_opt_v1.sh` — that script assumed `~/kraken2-src` (wrong path, doesn't exist) and a git-tracked source tree (also wrong, no `.git` present). Every command below was run individually, explained before running, verified after.

---

### 1
```bash
git -C ~/kraken2-src status --short && git -C ~/kraken2-src log -1 --oneline && ls -la ~/kraken2-build 2>&1 && ls -la ~/data/kraken2_db && ls -la ~/kraken2_opt_v1.patch 2>&1 && cat /sys/kernel/mm/transparent_hugepage/enabled
```
**Why:** initial recon assuming the documented path from `run_kraken2_opt_v1.sh` (`~/kraken2-src`) was correct.
**Result:** `fatal: cannot change to '/home/student/kraken2-src': No such file or directory`
**Finding:** that path doesn't exist. `dorado-kraken-research/CLAUDE.md` actually documents `~/tools/kraken2-src/`, not `~/kraken2-src/` — the script itself had the wrong path baked in.

---

### 2
```bash
ls -la ~/tools/
```
**Why:** check the documented path instead.
**Result:**
```
drwxrwxr-x  8 student student 4096 Aug  1 17:03 .
drwxrwxr-x  9 student student 4096 Aug  1 16:40 centrifuge
drwxrwxr-x  4 student student 4096 May 29 04:09 dorado
drwxrwxr-x  6 student student 4096 Oct 21  2024 FlameGraph
drwxrwxr-x  2 student student 4096 May 29 04:06 kraken2
drwxrwxr-x  2 student student 4096 May 29 22:36 kraken2-pg
drwxrwxr-x  6 student student 4096 Jun  7  2023 kraken2-src
```
**Finding:** `kraken2-src` exists here. Also noted `kraken2-pg` (gprof build) dated May 29 22:36 — relevant later.

---

### 3
```bash
ls -la ~/tools/kraken2-src/
```
**Why:** confirm this looks like a real kraken2 clone, and check for `.git`.
**Result:** standard kraken2 repo layout (`CHANGELOG.md`, `CMakeLists.txt`, `src/`, `scripts/`, `.gitignore`, etc.), `src/` dated Jun 24 23:23.
**Finding:** `.gitignore` present but **no `.git` folder** — not a git repository despite the apply script assuming `git apply`/`git reset --hard` would work.

---

### 4
```bash
ls -la ~/tools/kraken2-src/src/
```
**Why:** confirm the four files the patch touches are present, check for stray `.orig`/`.bak` files suggesting a prior half-applied attempt.
**Result:** all four files present (`Makefile`, `classify.cc`, `compact_hash.h`, `mmap_file.cc`); `.cc`/`.h` sources dated Jun 7 2023 (original clone date); `.o` files and binaries dated Jun 24 23:23 (rebuild, presumably for M1-M7). **Makefile dated May 29 22:38** — anomalous, doesn't match either date cluster.
**Finding:** no prior patch attempt. Makefile's odd date lines up suspiciously with `kraken2-pg`'s creation (May 29 22:36), suggesting someone edited it around then (see command 32+ theory: gprof-related edit).

---

### 5
```bash
find ~ -iname "*kraken2_opt*" 2>/dev/null
```
**Why:** check if the patch file itself was ever copied to Luna.
**Result:** empty.
**Finding:** patch never existed on Luna. Decision made here: don't transfer the raw `.patch` file and fight `git apply`/`patch` context-matching — apply each of the four edits by hand instead, per CK's preference.

---

### 6
```bash
for f in Makefile classify.cc compact_hash.h mmap_file.cc; do cp ~/tools/kraken2-src/src/$f ~/tools/kraken2-src/src/$f.pre_opt_v1; done
```
**Why:** no git safety net exists here, so create manual backups before any edits.
**Result:** silent success.

---

### 7
```bash
ls -la ~/tools/kraken2-src/src/*.pre_opt_v1
```
**Why:** confirm backups actually landed.
**Result:** all four `.pre_opt_v1` files present, byte-for-byte matching original sizes (classify.cc 28680, compact_hash.h 3436, Makefile 2125, mmap_file.cc 2946).

---

### 8
```bash
sed -n '25,35p' ~/tools/kraken2-src/src/classify.cc
```
**Why:** check context around the patch's first `classify.cc` insertion point (new LRU cache struct) before editing — the Makefile had already shown context can't be trusted from the patch's stated line numbers.
**Result:** matches expected sequence (`NUM_FRAGMENTS_PER_THREAD`, `MATE_PAIR_BORDER_TAXON`, `READING_FRAME_BORDER_TAXON`, `AMBIGUOUS_SPAN_TAXON`), just offset to lines 32-35 instead of the patch's assumed 29-31.

---

### 9
```bash
cat > /tmp/classify_insert1.txt <<'EOF'

// Thread-local direct-mapped cache in front of CompactHashTable::Get().
// 16K entries * 16 B = 256 KB per thread, fits in 2 MB L2 per core.
// Existing 1-entry last_minimizer skip catches sliding-window collisions;
// this catches cross-window and cross-read reuse for redundant microbial reads.
namespace {
constexpr size_t LRU_BITS = 14;
constexpr size_t LRU_SIZE = 1u << LRU_BITS;
constexpr uint64_t LRU_MIX = 0x9E3779B97F4A7C15ULL;
struct LRUEntry {
  uint64_t key;
  taxid_t  val;
};
thread_local LRUEntry lru_cache[LRU_SIZE] = {};
}  // namespace
EOF
```
**Why:** stage the new cache struct (Patch 4, Kolin sir's design) in a scratch file before splicing it in.
**Result:** staged successfully.

---

### 10
```bash
sed -i '34r /tmp/classify_insert1.txt' ~/tools/kraken2-src/src/classify.cc
```
**Why:** insert the staged block after line 34 (`READING_FRAME_BORDER_TAXON`).
**Result:** silent success.

---

### 11
```bash
sed -n '30,50p' ~/tools/kraken2-src/src/classify.cc
```
**Why:** verify the insertion landed correctly.
**Result:** confirmed — new struct sits cleanly between `READING_FRAME_BORDER_TAXON` and `AMBIGUOUS_SPAN_TAXON`, no duplication.

---

### 12
```bash
grep -n "hash->Get(\*minimizer_ptr)" ~/tools/kraken2-src/src/classify.cc
```
**Why:** find the real line number of the `Get()` call site (the patch's stated ~714 is unreliable given prior drift, and our own insertion above already shifted numbers).
**Result:** `558:              taxon = hash->Get(*minimizer_ptr);`

---

### 13
```bash
sed -n '550,565p' ~/tools/kraken2-src/src/classify.cc
```
**Why:** confirm exact surrounding context/indentation before replacing.
**Result:** matches expected structure — `taxon = 0;` → `if (! skip_lookup) / taxon = hash->Get(...)` at lines 557-558 → `last_taxon = taxon;`.

---

### 14
```bash
cat > /tmp/classify_insert2.txt <<'EOF'
            if (! skip_lookup) {
              size_t slot = (*minimizer_ptr * LRU_MIX) >> (64 - LRU_BITS);
              LRUEntry &e = lru_cache[slot];
              if (e.key == *minimizer_ptr && e.key != 0) {
                taxon = e.val;
              } else {
                taxon = hash->Get(*minimizer_ptr);
                e.key = *minimizer_ptr;
                e.val = taxon;
              }
            }
EOF
```
**Why:** stage the cache-check replacement for the two lines being removed.
**Result:** staged successfully.

---

### 15
```bash
sed -i '557,558d' ~/tools/kraken2-src/src/classify.cc
```
**Why:** delete the old two-line `if (! skip_lookup) / taxon = hash->Get(...)`.
**Result:** silent success.

---

### 16
```bash
sed -i '556r /tmp/classify_insert2.txt' ~/tools/kraken2-src/src/classify.cc
```
**Why:** insert the staged replacement at the same spot (line 556, `taxon = 0;`, unaffected by the deletion since it's before the deleted range).
**Result:** silent success.

---

### 17
```bash
sed -n '548,572p' ~/tools/kraken2-src/src/classify.cc
```
**Why:** verify the replacement landed correctly.
**Result:** confirmed correct — but revealed a **stray debug line at 549**: `fprintf(stderr, "MMK %llu\n", (unsigned long long)*minimizer_ptr);`, unrelated to our edit, sitting in the `else` branch right where we were working.
**Finding:** this is not stock kraken2 code. Unconditional per-minimizer stderr write in the hot loop — would badly corrupt any timing measurement.

---

### 18
```bash
sed -n '520,550p' ~/tools/kraken2-src/src/classify.cc
```
**Why:** check whether the fprintf is gated behind a condition or genuinely unconditional.
**Result:** it's the unconditional `else` of `if (scanner.is_ambiguous())` — fires on every non-ambiguous minimizer, no guard.
**Working theory:** leftover instrumentation from the M5 k-mer-reuse-rate measurement (90.7% reuse, used to justify Patch 4's ROI) — dumping every minimizer value to stderr is exactly what you'd need to compute that stat, and it likely never got removed afterward. Possibly related to the same May 29 session that touched the Makefile for the `kraken2-pg` gprof build.

---

### 19
```bash
grep -n "MMK" ~/tools/kraken2-src/src/classify.cc
```
**Why:** confirm there's only one instance before editing.
**Result:** `549:        fprintf(stderr, "MMK %llu\n", (unsigned long long)*minimizer_ptr);` — exactly one.

---

### 20
```bash
sed -i '549s/fprintf/\/\/ fprintf/' ~/tools/kraken2-src/src/classify.cc
```
**Why:** disable the debug print by commenting the whole line out (not deleting — keeps it visible/reversible).
**Result:** silent success.

---

### 21
```bash
sed -n '545,551p' ~/tools/kraken2-src/src/classify.cc
```
**Why:** verify the comment-out.
**Result:** confirmed — line 549 now reads `// fprintf(stderr, "MMK ...`, brace structure intact. `classify.cc` edits complete (LRU cache struct + Get() call-site wrap + debug fprintf disabled).

---

### 22
```bash
grep -n "hvalue_t CompactHashTable<Cell>::Get" ~/tools/kraken2-src/src/compact_hash.h
```
**Why:** locate Patch 3's target (the `Get()` implementation) in `compact_hash.h`, per the patch's assumption that `CompactHashTable` is a template class.
**Result:** empty — no match.

---

### 23
```bash
grep -n "Get(" ~/tools/kraken2-src/src/compact_hash.h
```
**Why:** cast a wider net.
**Result:** `73:  hvalue_t Get(hkey_t key) const;` — only a declaration, no implementation in this file.

---

### 24
```bash
grep -n "::Get" ~/tools/kraken2-src/src/compact_hash.cc
```
**Why:** check if the implementation is actually in the `.cc` file.
**Result:** `109:hvalue_t CompactHashTable::Get(hkey_t key) const {`
**Finding:** major structural mismatch — `CompactHashTable` is **not a template class** in this source tree (no `<Cell>`). The patch's `sizeof(Cell)` reference in `PF_STRIDE` won't compile here; `Cell` doesn't exist as a type name. Implementation lives in `compact_hash.cc`, not the header.

---

### 25
```bash
sed -n '100,140p' ~/tools/kraken2-src/src/compact_hash.cc
```
**Why:** see the real `Get()` body to adapt Patch 3's logic to the actual (non-template) code.
**Result:** logic matches conceptually (`idx`, `first_idx`, `step`, `table_[idx].value(...)`, `table_[idx].hashed_key(...)`, `second_hash`). Also spotted line 105 already using the idiom `sizeof(*table_)` for cell size — the fix for the missing `Cell` type.

---

### 26
```bash
grep -n "table_" ~/tools/kraken2-src/src/compact_hash.h
```
**Why:** confirm `table_`'s declared type so `sizeof(*table_)` is meaningful.
**Result:** `102:  CompactHashCell *table_;` — concrete type, confirms `sizeof(*table_)` will correctly give the cell width M1 measured (4 bytes).

---

### 27
```bash
cat > /tmp/compact_pf1.txt <<'EOF'
  // One cache line ahead in cells (64 B / cell size); adapted from the
  // patch's Cell-template form since CompactHashTable isn't templated here.
  constexpr size_t PF_STRIDE = 64 / sizeof(*table_);
EOF
cat > /tmp/compact_pf2.txt <<'EOF'
    size_t pf_idx = idx + PF_STRIDE;
    if (pf_idx >= capacity_) pf_idx -= capacity_;
    __builtin_prefetch(&table_[pf_idx], 0, 0);

EOF
```
**Why:** stage the adapted Patch 3 (prefetch), using `sizeof(*table_)` instead of the patch's `sizeof(Cell)`.
**Result:** staged successfully.

---

### 28
```bash
sed -i '115r /tmp/compact_pf2.txt' ~/tools/kraken2-src/src/compact_hash.cc
```
**Why:** insert the prefetch block after line 115 (`while (true) {`) — done first since it's the higher line number, so it doesn't shift line 114's position for the next step.
**Result:** silent success.

---

### 29
```bash
sed -i '114r /tmp/compact_pf1.txt' ~/tools/kraken2-src/src/compact_hash.cc
```
**Why:** insert `PF_STRIDE` after line 114 (`size_t step = 0;`).
**Result:** silent success.

---

### 30
```bash
sed -n '109,133p' ~/tools/kraken2-src/src/compact_hash.cc
```
**Why:** verify both `compact_hash.cc` insertions.
**Result:** confirmed correct — `PF_STRIDE` declared right after `step`, prefetch fires as the first statement in the loop body, original probe logic untouched below it. **Patch 3 complete.**

---

### 31 (in progress)
```bash
grep -n "mmap\|MAP_FAILED\|valid_ = true" ~/tools/kraken2-src/src/mmap_file.cc
```
**Why:** locate the real `mmap()` call and `valid_ = true;` line in `mmap_file.cc` for Patch 2 (huge-page `madvise()` hints), rather than trusting the patch's stated line ~52 given everything found so far.
**Result:** pending.

---

## Deviations from the patch file found so far

1. **Wrong source path** in `run_kraken2_opt_v1.sh` (`~/kraken2-src` vs. real `~/tools/kraken2-src`).
2. **No git repository** in the source tree — script's `git apply`/`git reset --hard` approach would have failed outright.
3. **Makefile drift**: missing `-fPIC -g`, no `CFLAGS` line, `CXX =` instead of `CXX ?=` — patch's Makefile hunk will not apply via `git apply`/`patch`, requires hand-editing.
4. **Stray debug instrumentation**: unconditional `fprintf(stderr, "MMK ...)` in the per-minimizer hot loop in `classify.cc`, unrelated to the patch, likely leftover from the M5 k-mer-reuse measurement. Disabled (commented out) before any benchmarking.
5. **`CompactHashTable` is not a template class** in this source tree — the patch's Patch 3 code (`sizeof(Cell)`) assumes a `template <typename Cell>` class that doesn't exist here. Adapted using `sizeof(*table_)` instead, matching an idiom already used elsewhere in `compact_hash.cc`.

None of these are patch-blocking — every edit has been achievable by hand once the real structure is understood — but they mean **this patch file was written against a different, either older or hypothetical version of the source tree than what's actually deployed on Luna.** Worth mentioning to Kolin sir alongside the eventual benchmark results.
