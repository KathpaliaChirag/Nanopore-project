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

### 31
```bash
grep -n "mmap\|MAP_FAILED\|valid_ = true" ~/tools/kraken2-src/src/mmap_file.cc
```
**Why:** locate the real `mmap()` call and `valid_ = true;` line in `mmap_file.cc` for Patch 2 (huge-page `madvise()` hints), rather than trusting the patch's stated line ~52 given everything found so far.
**Result:** `57: mmap(...)`, `58: if (fptr_ == MAP_FAILED) {`, `61: valid_ = true;` — matches the patch's assumed structure almost exactly, unlike everything else so far.

---

### 32
```bash
sed -n '54,62p' ~/tools/kraken2-src/src/mmap_file.cc
```
**Why:** confirm full context before inserting.
**Result:** confirmed clean match to patch's assumption — `mmap()` → `if (MAP_FAILED) { err(...); }` → `valid_ = true;`.

---

### 33
```bash
cat > /tmp/mmap_insert1.txt <<'EOF'
  // Hints: try 2 MB pages (cuts DTLB pressure on the 8 GB hash table),
  // start populating now (avoid first-touch faults in hot path),
  // skip kernel readahead (access is random not sequential).
  (void) madvise(fptr_, filesize_, MADV_HUGEPAGE);
  (void) madvise(fptr_, filesize_, MADV_WILLNEED);
  (void) madvise(fptr_, filesize_, MADV_RANDOM);
EOF
```
**Why:** stage the three madvise() hints (Patch 2).
**Result:** staged successfully.

---

### 34
```bash
sed -i '60r /tmp/mmap_insert1.txt' ~/tools/kraken2-src/src/mmap_file.cc
```
**Why:** insert after line 60 (closing brace of the MAP_FAILED check), before `valid_ = true;`.
**Result:** silent success.

---

### 35
```bash
sed -n '54,67p' ~/tools/kraken2-src/src/mmap_file.cc
```
**Why:** verify.
**Result:** confirmed correct — three madvise() calls sit between the MAP_FAILED check and `valid_ = true;`. **Patch 2 complete. All three source-file edits (Patch 2, 3, 4) done.**

---

### 36
```bash
grep -n "CXXFLAGS\|CXX =" ~/tools/kraken2-src/src/Makefile
```
**Why:** confirm Makefile line numbers before editing (file untouched since command 4's `cat`).
**Result:** `1: CXX = g++`, `3: CXXFLAGS =$(KRAKEN2_SKIP_FOPENMP)...`, `4: CXXFLAGS += -DLINEAR_PROBING` — matches earlier full-file `cat`. Also noticed all six link recipes (lines 37-52) use `$(CXX) $(CXXFLAGS) -o $@ $^` and **never reference `$(LDFLAGS)`**.
**Finding:** the patch's `LDFLAGS += -flto=auto -fuse-linker-plugin` would be dead code in this Makefile — nothing reads `$(LDFLAGS)`. Since `$(CXXFLAGS)` is reused for linking here, folded the LTO/linker flags directly into `CXXFLAGS` instead.

---

### 37
```bash
sed -i '3s/.*/CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -march=sapphirerapids -mtune=sapphirerapids -flto=auto -funroll-loops -fno-plt -fuse-linker-plugin/' ~/tools/kraken2-src/src/Makefile
```
**Why:** replace line 3 wholesale with the augmented flags (all folded into CXXFLAGS, no separate LDFLAGS).
**Result:** silent success.

---

### 38
```bash
cat ~/tools/kraken2-src/src/Makefile | head -6
```
**Why:** verify.
**Result:** confirmed — `CXXFLAGS` now includes `-march=sapphirerapids -mtune=sapphirerapids -flto=auto -funroll-loops -fno-plt -fuse-linker-plugin`, `CXXFLAGS += -DLINEAR_PROBING` untouched. **Patch 1 complete. All four patches now applied.**

---

## Baseline reconstruction (commands 39-43)

CK chose the "duplicate tree, reconstruct clean baseline" option: rather than disturb the now-fully-patched live tree, duplicate it and reconstruct a fair "stock + fprintf fix only" baseline in the copy, since building baseline straight from the raw `.pre_opt_v1` backups would unfairly include the fprintf bug (inflating the apparent patch benefit).

### 39
```bash
cp -r ~/tools/kraken2-src ~/tools/kraken2-src-baseline
```
**Why:** duplicate the whole source tree so baseline reconstruction never touches the validated patched tree.
**Result:** silent success.

### 40
```bash
cp ~/tools/kraken2-src-baseline/src/Makefile.pre_opt_v1 ~/tools/kraken2-src-baseline/src/Makefile && cp ~/tools/kraken2-src-baseline/src/classify.cc.pre_opt_v1 ~/tools/kraken2-src-baseline/src/classify.cc && cp ~/tools/kraken2-src-baseline/src/mmap_file.cc.pre_opt_v1 ~/tools/kraken2-src-baseline/src/mmap_file.cc
```
**Why:** restore the 3 backed-up files in the baseline copy only (undoes Patch 1, 2, 4 there). `classify.cc` temporarily has the raw uncommented fprintf bug again at this point.
**Result:** silent success.

### 41
```bash
grep -n "PF_STRIDE\|pf_idx\|while (true)" ~/tools/kraken2-src-baseline/src/compact_hash.cc
```
**Why:** confirm exact line numbers before reversing the (unbacked-up) Patch 3 insertion in the baseline copy.
**Result:** `117: PF_STRIDE`, `118: while (true) {`, `119-121: pf_idx block`, `143: while (true) {` (unrelated — that's `FindIndex()`). Matches command 30 exactly, confirming `cp -r` was byte-faithful.

### 42
```bash
sed -i '119,122d' ~/tools/kraken2-src-baseline/src/compact_hash.cc && sed -i '115,117d' ~/tools/kraken2-src-baseline/src/compact_hash.cc
```
**Why:** delete the two inserted blocks (higher range first) to reconstruct stock `Get()` in the baseline copy.
**Result:** silent success.

### 43
```bash
sed -n '109,127p' ~/tools/kraken2-src-baseline/src/compact_hash.cc
```
**Why:** verify the reconstruction is byte-for-byte correct.
**Result:** confirmed — matches the original stock `Get()` from command 25 exactly. Baseline `compact_hash.cc` correctly reconstructed.

---

## Building baseline and patched binaries (commands 44-52)

### 44
```bash
grep -n "MMK" ~/tools/kraken2-src-baseline/src/classify.cc
```
**Result:** `534: fprintf(...)`. Confirms 549 (patched tree) − 534 (stock) = 15 = exact size of the LRU cache struct inserted in command 10. Confirms baseline copy is a true unmodified original.

### 45
```bash
sed -i '534s/fprintf/\/\/ fprintf/' ~/tools/kraken2-src-baseline/src/classify.cc
```
**Why:** apply the same fprintf fix to baseline so it's equal on both sides.
**Result:** silent success.

### 46
```bash
sed -n '530,536p' ~/tools/kraken2-src-baseline/src/classify.cc
```
**Result:** confirmed commented out correctly. Baseline tree fully ready: stock + fprintf fix only, no optimization patches.

### 47
```bash
cd ~/tools/kraken2-src-baseline/src && make clean && make classify -j 96
```
**Result:** clean build, zero errors/warnings. Baseline `classify` binary built.

### 48
```bash
cd ~/tools/kraken2-src/src && make clean && make classify -j 96
```
**Result:** clean build, zero errors/warnings — including with the new `-march=sapphirerapids -flto=auto -funroll-loops -fno-plt -fuse-linker-plugin` flags and all hand-edits. Patched `classify` binary built.

### 49
```bash
ls -la ~/data/kraken2_db && ~/tools/kraken2-src/src/classify --help 2>&1 | head -20
```
**Result:** `~/data/kraken2_db` doesn't exist — the documented standard-8GB DB path is stale, same pattern as the Centrifuge session's missing ESKAPE databases.

### 50
```bash
ls -la ~/data/ 2>&1 && echo --- && ls -la ~/AccuracyDrift/databases/ 2>&1
```
**Result:** `standard_8gb`, `standard_16gb`, `pluspf_103gb`, `sample_targeted` all still present under `~/AccuracyDrift/databases/`. `eskape_650mb`/`eskape_human_4gb` directories are entirely gone (not just their `.k2d` files), confirming the Centrifuge session's finding.

### 51
```bash
ls -la ~/AccuracyDrift/databases/standard_8gb/
```
**Result:** `hash.k2d` (8,000,000,032 bytes), `taxo.k2d`, `opts.k2d` all present and correctly sized. This is the benchmark DB (replacing the stale `~/data/kraken2_db` path).

### 52
```bash
~/tools/kraken2-src/src/classify 2>&1 | head -30
```
**Result:** usage message confirms `-H`, `-t`, `-o`, `-p`, `-R`, `-O`, `-M` flags all match the unrun script's assumptions.

---

## Major finding — `-M` (memory mapping) has never been used in this project

### 53
```bash
grep -n "\-M\|use_memory_mapping\|MMapFile" ~/tools/kraken2-src/src/classify.cc | head -20
```
**Result:** `use_memory_mapping` defaults to `false` (line 135), only set `true` by `-M` (line 832), passed into the `CompactHashTable` constructor (line 154).

### 54
```bash
cat ~/tools/kraken2/kraken2 | grep -n "classify\|-M"
```
**Result:** the `kraken2` wrapper only passes `-M` to `classify` `if $memory_mapping`.

### 55
```bash
grep -n "memory_mapping" ~/tools/kraken2/kraken2
```
**Result:** `$memory_mapping` defaults to `0`, only set via an explicit `--memory-mapping` wrapper flag.

**Finding:** every "standard profiling command" in this project's history (`kraken2 --db ... --threads 32 ...`, used for M1-M7, all of AccuracyDrift, the `4.405s` README figure) never included `--memory-mapping`. This means **`-M` was never passed to `classify`, and `MMapFile::OpenFile` — the function Patch 2 edits — has never executed in any measurement this project has ever taken.** The hash table is loaded via some other (non-mmap) path by default. Patch 3 (prefetch in `Get()`) and Patch 4 (LRU cache) are unaffected by this — they apply regardless of how `table_` was populated — but Patch 2's huge-page hints have been structurally inert this whole time.

**Decision (CK):** benchmark both ways — once matching standard practice (no `-M`, comparable to all historical numbers; Patch 2 expected to show ~0% effect here, which is itself the reportable finding) and once with `-M` (to test Patch 2 on its own terms).

---

## Benchmark: baseline, no -M (command 57)

```bash
BIN=~/tools/kraken2-src-baseline/src/classify
DB=~/AccuracyDrift/databases/standard_8gb
IN=~/results/basecalling/reads_hac.fastq
# 3 warm-up runs, then 3 timed runs with perf stat + /usr/bin/time
```
Full command and output saved to `~/results/profiling/opt_v1_manual/base_noM.txt` on Luna.

| Run | Wall time | Cache-miss % | LLC-load-miss % | IPC |
|---|---|---|---|---|
| 1 | 4.435s | 88.19% | 83.09% | 1.88 |
| 2 | 4.432s | 88.29% | 83.05% | 1.88 |
| 3 | 4.472s | 88.15% | 83.11% | 1.85 |
| **avg** | **~4.446s** | **~88.2%** | **~83.1%** | **~1.87** |

**Sanity check — matches project history:** wall time within ~1% of the documented `4.405s` baseline (README.md), IPC matches M2's own `1.85` figure for this exact DB/thread config almost exactly. Confirms the baseline reconstruction (stock source + fprintf fix only) is faithful, not skewed by our process.

---

## Benchmark: patched, no -M (command 58)

Same DB/threads/perf-events, `$BIN` pointed at the patched tree instead (Patches 1, 3, 4 active; Patch 2 inert, no `-M`).

| Run | Wall time | Cache-miss % | LLC-load-miss % | Instructions | Cycles | IPC |
|---|---|---|---|---|---|---|
| 1 | 4.446s | 87.76% | 80.88% | 103.37B | 57.37B | 1.80 |
| 2 | 4.439s | 87.61% | 80.98% | 103.34B | 57.23B | 1.81 |
| 3 | 4.432s | 87.95% | 81.01% | 103.33B | 57.38B | 1.80 |
| **avg** | **~4.439s** | **~87.8%** | **~80.96%** | **~103.35B** | **~57.33B** | **~1.80** |

## Baseline vs patched (no -M) — comparison

| Metric | Baseline | Patched | Delta |
|---|---|---|---|
| Wall time | ~4.446s | ~4.439s | **−0.16% — statistically noise** (both ranges overlap heavily) |
| Instructions | ~111.6B | ~103.35B | **−7.4%** |
| Cycles | ~59.74B | ~57.33B | **−4.0%** |
| IPC | ~1.87 | ~1.80 | −3.7% (fewer total instructions but slightly less overlap-efficient mix) |
| Cache-miss % | ~88.2% | ~87.8% | −0.4pp |
| LLC-load-miss % | ~83.1% | ~81.0% | −2.1pp (prefetch converting some future misses to hits) |
| LLC-loads | ~118.2M | ~122.2M | +3.4% (prefetch itself issues extra speculative loads) |

**The real finding: wall-clock time didn't move, despite genuine instruction/cycle-level improvements.** Why: `classify`'s own self-reported line — `"104918 sequences ... processed in 0.68Xs"` — is nearly identical across every single run, baseline and patched alike. The actual classification loop (where Patch 3's prefetch and Patch 4's LRU cache operate) takes well under 0.7s. The remaining **~3.7 of ~4.4 total seconds is spent loading the 8GB hash table into memory before classification starts** — a phase none of Patch 1, 3, or 4 touch. Patch 2 (huge pages via `madvise`) is the one patch aimed at load-time cost, and it's the one that's inert here without `-M`.

**Implication:** this patch's expected gains (per M1-M7) were reasoned about in terms of per-lookup cache-miss cost during classification — but classification is only ~15% of this workload's wall-clock on `standard_8gb`. Even a large relative improvement there caps out at a small absolute one. This makes the `-M` run below not just "does Patch 2 work" but "does Patch 2 attack the part of the runtime that actually dominates here."

---

## Benchmark: baseline, WITH -M (command 59) — major independent finding

Same DB/threads, `-M` added (added `dTLB-load-misses`/`dTLB-loads` to the event list too, since huge pages are a TLB-pressure fix per M2's original reasoning).

| Run | Wall time | Cache-miss % | LLC-load-miss % | dTLB-miss % | Instructions | Cycles | IPC |
|---|---|---|---|---|---|---|---|
| 1 | 0.949s | 75.05% | 60.04% | 0.05% | 102.22B | 50.41B | 2.03 |
| 2 | 0.984s | 75.40% | 60.14% | 0.05% | 102.47B | 52.09B | 1.97 |
| 3 | 0.944s | 75.76% | 60.80% | 0.05% | 102.06B | 49.67B | 2.05 |
| **avg** | **~0.96s** | **~75.4%** | **~60.3%** | **0.05%** | **~102.25B** | **~50.7B** | **~2.02** |

**Major finding, independent of the patch itself:** `-M` alone (baseline binary, zero optimization patches) drops wall time from ~4.45s (no `-M`) to **~0.96s — a ~4.5x speedup**, just from switching the hash-table load mechanism. Explanation: without `-M`, `classify` reads the whole 8GB file into a heap buffer eagerly, paying the full load cost up front (the ~3.7s inferred earlier). With `-M`, `mmap()` is used and pages fault in lazily as classification actually touches them — the "load" cost gets absorbed into and mostly hidden by the classification phase itself. LLC-load-miss rate drops from ~83% to ~60%, IPC rises from ~1.87 to ~2.02, despite doing the same classification work.

**Implication:** this project's standard invocation (`kraken2 --db ... --threads N ...`, no `--memory-mapping`) has never used this ~4.5x lever, on top of and separate from anything in `kraken2_opt_v1.patch`. Worth flagging to Kolin sir as its own finding regardless of how the patch itself performs.

---

## Known gap — no backup of `compact_hash.cc`

Command 6's backup loop only covered the four files the patch file names (`Makefile`, `classify.cc`, `compact_hash.h`, `mmap_file.cc`). Command 24 discovered the real `Get()` implementation lives in `compact_hash.cc`, not `.h` — and that file was edited (commands 28-29) **without ever being backed up first**. There is no `compact_hash.cc.pre_opt_v1`.

Recovery path if needed: the exact insertions are fully documented in commands 27-30 above (two blocks, at the same two insertion points, fully reproducible from this log) — reversible by deleting the specific added lines, just without a byte-exact backup file to fall back on. Not blocking, but a real process gap worth naming rather than glossing over.

## Deviations from the patch file found so far

1. **Wrong source path** in `run_kraken2_opt_v1.sh` (`~/kraken2-src` vs. real `~/tools/kraken2-src`).
2. **No git repository** in the source tree — script's `git apply`/`git reset --hard` approach would have failed outright.
3. **Makefile drift**: missing `-fPIC -g`, no `CFLAGS` line, `CXX =` instead of `CXX ?=` — patch's Makefile hunk will not apply via `git apply`/`patch`, requires hand-editing.
4. **Stray debug instrumentation**: unconditional `fprintf(stderr, "MMK ...)` in the per-minimizer hot loop in `classify.cc`, unrelated to the patch, likely leftover from the M5 k-mer-reuse measurement. Disabled (commented out) before any benchmarking.
5. **`CompactHashTable` is not a template class** in this source tree — the patch's Patch 3 code (`sizeof(Cell)`) assumes a `template <typename Cell>` class that doesn't exist here. Adapted using `sizeof(*table_)` instead, matching an idiom already used elsewhere in `compact_hash.cc`.
6. **Patch's `LDFLAGS += ...` would be dead code**: this Makefile's link recipes use `$(CXX) $(CXXFLAGS) -o $@ $^` and never reference `$(LDFLAGS)`. Folded the LTO/linker flags into `CXXFLAGS` instead.
7. **`compact_hash.cc` was never backed up** before editing — only the four files the patch names were backed up in command 6; the real edit target turned out to be a fifth file. No `.pre_opt_v1` exists for it; see "Known gap" above.

None of these are patch-blocking — every edit has been achievable by hand once the real structure is understood — but they mean **this patch file was written against a different, either older or hypothetical version of the source tree than what's actually deployed on Luna.** Worth mentioning to Kolin sir alongside the eventual benchmark results.
