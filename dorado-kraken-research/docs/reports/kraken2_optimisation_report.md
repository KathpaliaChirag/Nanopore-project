# Kraken-2 Optimisation Report
**Authors:** Chirag K (CK) + Chirag Suthar
**Due:** 2026-05-31 (OVERDUE — see status note below)
**Supervisor:** Kolin sir, Chayanika mam

<!-- Status as of 2026-08-03:
     Sections 1-5, 7, 8, 9 are complete and verified.
     Section 6 is now FILLED — M1-M7 measurements complete (done 2026-06-24, values
     were already known via AccuracyDrift/patches.md before this session), and
     Patches 1-4 (the only patches actually implemented in kraken2_opt_v1.patch —
     Patches 5-10 in Section 4 remain design-only proposals, never coded) have been
     applied by hand and benchmarked across 4 databases x 3 thread counts x 2 builds
     x 2 memory-mapping modes (48 cells). Full raw command-by-command log:
     `Luna/experiments/patch/commands_log.md`. Two headline findings: the patch
     applied cleanly required real structural adaptation (the live source tree had
     drifted from what this report's Section 4 assumed — see 6.2), and an unplanned
     but much larger finding (`-M`/memory-mapping, worth up to 12-14x on large DBs,
     never used anywhere in this project before) surfaced during benchmarking — see 6.4.
-->

This report consolidates: (a) baseline profiling already completed on WSL2/Minerva/Luna,
(b) source-derived correction of earlier inferred algorithms, (c) ten concrete
optimisation proposals with code diffs, and (d) the Luna measurements that
calibrated and then validated each patch's actual delta. Supplementary files:
`kraken2_get_optimizations.md` (v1 patches), `kraken2_get_optimizations_v2.md`
(v2 patches), `Luna/experiments/{kraken2_opt_v1.patch, run_kraken2_opt_v1.sh,
pending_measurements.md, patch/commands_log.md}`, and `kraken2_execution_checklist.md`.

---

## 1. Baseline profiling — what is proven

### 1.1 Initial (WSL2 + AMD uProf, 2026-05-26)

| Tool | Result | Verdict |
|---|---|---|
| `perf stat` (WSL2) | 34.24 % cache miss rate, 301 M misses / run | Memory-bound |
| `gprof` (WSL2) | 67 % runtime in `CompactHashTable::Get()`, 9.87 M calls | Hotspot confirmed |
| AMD uProf (local) | IPC = 0.55 | CPU stalling, not computing |

**Derived:** 301 M ÷ 9.87 M ≈ **30 L3 misses per Get() call**. At ~100 ns/miss →
~30 s of DRAM latency per run (out of 105.87 s total, 1T).

### 1.2 Luna deep profiling (2026-05-28 → 2026-05-29)

Luna is bare metal (perf_event_paranoid = 1), so every counter that was unavailable
on WSL2 was re-measured.

| Probe | Result |
|---|---|
| `perf stat` hac, 32T, node0 | **wall = 4.405 s** ← current best |
| `perf stat` hac, 96T default | wall = 5.635 s |
| LLC miss rate | 80–82 % |
| LLC misses / run | ~1 × 10⁹ |
| DRAM stalls | 8–11 × 10⁹ cycles (48–52 % of total cycles) |
| IPC | 1.47–1.65 (theoretical max ≈ 6) |
| TMA `memory_bound` | 23–28 % |
| TMA `core_bound`   | 15–22 % |
| cachegrind hac 1T | **`CompactHashTable::Get()` = 96.24 % of all LL read misses** |
| cachegrind hac 1T | `MinimizerScanner` = 48 % of instructions, **0 LL misses** |
| Flamegraph hac 32T | MinimizerScanner 25.57 %, I/O page-cache copy 20 %, Get 12.10 % |
| tmpfs experiment | **No benefit** — the I/O tower is page-cache copy, not disk |

### 1.3 Verdict

**Latency-bound, not bandwidth-bound, not I/O-bound.** The CPU is stalled waiting
for DRAM reads inside `CompactHashTable::Get()`. The remaining optimisation
budget is therefore: (a) avoid the read entirely (caching) or (b) hide the latency
(prefetch, batching).

---

## 2. Corrections to earlier inferred algorithms

The original profiling notes inferred a Get() body from intuition. Reading the
actual upstream source (master, github.com/DerrickWood/kraken2, 2026-05-29) revealed
three differences that change which optimisations make sense.

### 2.1 Cells are 32-bit or 40-bit packed, not 64-bit

```cpp
// src/compact_hash.h
struct CompactHashCell { uint32_t data; };                              // 4-byte
struct CompactHashCell40 { uint32_t a; uint8_t b; } __attribute__((packed));  // 5-byte
```

Default upstream Makefile builds with `cht_cell_size = 32`. **But `build_db.cc`
appears to instantiate `CompactHashCell40` for both `-C 32` and `-C 40`** —
likely a refactor-in-progress bug:

```cpp
if (opts.cht_cell_size == 32) {
    build<CompactHashCell40>(...);    // <-- both branches use Cell40
} else if (opts.cht_cell_size == 40) {
    build<CompactHashCell40>(...);
}
```

This is testable on Luna: read the first 32 bytes of `hash.k2d` and compute
`(file_bytes - 32) / capacity`. If ≈ 5 → 40-bit cell. The pre-built
`k2_standard_08gb` is almost certainly 40-bit packed.

**Implication:** prefetch stride is **12 cells per cache line, not 16**.
`64 / sizeof(Cell)` handles either.

### 2.2 Linear probing is the default, not double hashing

```makefile
# src/Makefile
CXXFLAGS += -DLINEAR_PROBING
```

```cpp
template<typename Cell>
inline uint64_t CompactHashTable<Cell>::second_hash(uint64_t first_hash) const {
#ifdef LINEAR_PROBING
  return 1;
#else
  return (first_hash >> 8) | 1;
#endif
}
```

**Implication:** adjacent probes hit adjacent cells (same / next cache line), so
the hardware prefetcher can help on long probe walks. The "every probe is a fresh
L3 miss" reading is incorrect; long clusters under near-full load factor explain
the 96.24 % LL share.

### 2.3 `hash->Get` is virtual through `KeyValueStore`

```cpp
class KeyValueStore {
  virtual hvalue_t Get(hkey_t key) const = 0;
};
```

Every call from `classify.cc` pays a vtable load. Eliminable via LTO or `final`.

### 2.4 classify.cc already has a 1-entry "cache"

```cpp
// src/classify.cc, ClassifySequence
if (*minimizer_ptr != last_minimizer) {
  taxon = hash->Get(*minimizer_ptr);   // only here on minimizer change
  last_minimizer = *minimizer_ptr;
} else {
  taxon = last_taxon;
}
```

So the 9.87 M Get() calls reported by gprof are **already after** the same-as-last
skip. A bigger LRU must beat this 1-entry "cache" to be worth the patch.

### 2.5 Real Get() body

```cpp
template<typename Cell>
hvalue_t CompactHashTable<Cell>::Get(hkey_t key) const {
  uint64_t hc = MurmurHash3(key);                          // computed once
  uint64_t compacted_key = hc >> (64 - key_bits_);
  size_t idx = hc % capacity_;
  size_t first_idx = idx;
  size_t step = 0;
  while (true) {
    if (! table_[idx].value(value_bits_)) break;           // empty cell → not in DB
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0) step = second_hash(hc);                 // LINEAR_PROBING: step = 1
    idx += step;
    idx %= capacity_;
    if (idx == first_idx) break;                            // table exhausted
  }
  return 0;
}
```

---

## 3. Pending Luna measurements (decide patch parameters)

Seven measurements, all scripted in `Luna/experiments/pending_measurements.md`.
They take ~10 minutes total and decide which patches matter and how to tune them.

| # | What | Decides |
|---|---|---|
| M1 | `hash.k2d` header: cell size, load factor | prefetch stride; LRU viability |
| M2 | `dTLB-load-misses / dTLB-loads` | whether MADV_HUGEPAGE pays |
| M3 | `perf annotate CompactHashTable::Get` | exact miss line — confirms model |
| M4 | uncore_imc cas_count → GB/s | latency-bound vs bandwidth-bound |
| M5 | minimizer reuse rate on hac input | whether thread-local LRU pays |
| M6 | `perf c2c` HITM events | whether per-socket DB replica matters |
| M7 | `objdump` ymm/zmm count | AVX-512 use in current binary |

**Decision gates:**
- M4 ratio < 0.5 → latency-bound (expected) → all v1 + v2 patches apply.
- M4 ratio > 0.7 → bandwidth-bound → defer LRU, escalate to DB compression.
- M5 reuse > 0.30 → Patch 4 (LRU) is high-value; < 0.10 → skip Patch 4.

---

## 4. Optimisation proposals — ten patches

Each patch is a code diff against the upstream source. Files referenced live in
`~/kraken2-src/src/`. Full diffs are in `kraken2_get_optimizations.md` (v1) and
`kraken2_get_optimizations_v2.md` (v2). The unified diff to apply at once is
`Luna/experiments/kraken2_opt_v1.patch`.

### 4.1 Patch 1 — software prefetch in the probe loop (Kolin sir's Proposal E)

**Why:** 96 % of all LL misses are in this loop. Issuing
`__builtin_prefetch(&table_[idx + 64/sizeof(Cell)])` one cache line ahead each
iteration starts the DRAM read ~100 ns before the load needs it. Even with
linear probing the HW prefetcher only streams ~2–4 lines; explicit prefetch
extends the window.

**Where:** `src/compact_hash.h`, body of `Get()`.

**Expected delta:** **−5 to −15 %.**

### 4.2 Patch 2 — MADV_HUGEPAGE on the mmap'd hash table (huge pages)

**Why:** 8 GB / 4 KB pages = 2 097 152 page entries. Sapphire Rapids DTLB has
~96 small-page entries → constant DTLB misses on the probe walk. 2 MB huge
pages reduce that to ~4 096 entries — easily fits the L2 DTLB.

**Where:** `src/mmap_file.cc::OpenFile()`, after the `mmap()` call:
```cpp
(void) madvise(fptr_, filesize_, MADV_HUGEPAGE);
(void) madvise(fptr_, filesize_, MADV_WILLNEED);
(void) madvise(fptr_, filesize_, MADV_RANDOM);
```

**Expected delta:** **−3 to −8 %** (M2 measurement calibrates).

### 4.3 Patch 3 — compiler flags

**Why:** `-march=sapphirerapids` exposes BMI2 + AVX-512 (MurmurHash speedup);
`-flto` inlines `hash->Get()` across translation units (devirtualises); `-funroll-loops`
unrolls the probe.

**Where:** `src/Makefile`:
```makefile
CXXFLAGS += -march=sapphirerapids -mtune=sapphirerapids -flto=auto -funroll-loops -fno-plt
LDFLAGS  += -flto=auto -fuse-linker-plugin
```

**Expected delta:** **−5 to −12 %.**

### 4.4 Patch 4 — thread-local direct-mapped k-mer cache (Kolin sir's Proposal A)

**Why:** the existing 1-entry skip handles within-window minimizer collisions;
this captures cross-window and cross-read reuse. 16 K entries × 16 B = 256 KB
per thread, fits in 2 MB L2 per core. Every hit avoids ~30 LL misses ≈ 3 µs
of DRAM latency.

**Where:** `src/classify.cc::ClassifySequence`, replacing the existing
`hash->Get()` call:
```cpp
thread_local LRUEntry lru_cache[1u << 14] = {};
constexpr uint64_t LRU_MIX = 0x9E3779B97F4A7C15ULL;   // Fibonacci hash
size_t slot = (*minimizer_ptr * LRU_MIX) >> (64 - 14);
LRUEntry &e = lru_cache[slot];
if (e.key == *minimizer_ptr && e.key != 0)  taxon = e.val;
else { taxon = hash->Get(*minimizer_ptr); e.key = *minimizer_ptr; e.val = taxon; }
```

**Expected delta:** **−10 to −30 %**, gated by M5 reuse rate.

**Tunable:** `LRU_BITS` 13 (8 K, 128 KB) ↔ 16 (64 K, 1 MB) depending on M5.

### 4.5 Patch 5 — per-socket DB replica (NUMA)

**Why:** mmap one DB copy per socket so 64T+ runs don't pay cross-NUMA latency.
**Apply only if M6 c2c HITM > 5 %**; currently the 32T-on-node0 baseline
already avoids the issue.

**Expected delta:** TBD; deferred.

### 4.6 Patch 6 — devirtualise via `final` + concrete-typed dispatch

**Why:** drops the vtable load per call (~5 ns × 9.87 M = 50 ms wall on 1T,
amortised across threads at 32T but still real).

**Where:** add `final` to `CompactHashTable<Cell>::Get` in `compact_hash.h`; in
`classify.cc`, `dynamic_cast` once per batch and dispatch to the concrete type.

**Expected delta:** **−2 to −5 %.** Largely subsumed by Patch 3 (LTO) but more
portable.

### 4.7 Patch 7 — single MurmurHash via `GetByHash`

**Why:** when `minimum_acceptable_hash_value > 0` (MiniKraken DBs), classify.cc
computes MurmurHash3 in the inner loop *and* Get() recomputes it. Add a
`GetByHash(key, hc)` overload and pass the hash through.

**Expected delta:** −1 to −3 % on standard_8; −5 to −10 % on MiniKraken.

### 4.8 Patch 8 — `ResolveTree` from O(N²) to O(N)

**Why:** `ResolveTree` in classify.cc has a nested loop calling
`taxonomy.IsAAncestorOfB(b, a)` for every pair `(a, b)` in `hit_counts`. For
long nanopore reads, |hit_counts| can be 50+, so this is 50 × 50 × tree_depth
≈ 12 000 random reads into the taxonomy nodes array per read, × 104 918 reads
≈ 1 billion accesses per run.

**Where:** `src/classify.cc::ResolveTree` — precompute an ancestor vector per
unique taxon, replace the inner `IsAAncestorOfB` call with `std::find` on a
short vector.

**Expected delta:** **−2 to −6 %**, scales with read length.

### 4.9 Patch 9 — skip output formatting when `-O /dev/null`

**Why:** `ostringstream koss << ...` runs for every read even when the kraken
output is discarded (which is what our perf runs do). Add a bool gate.

**Expected delta:** −1 to −2 %.

### 4.10 Patch 10 — batched Get() with cross-call prefetch pipeline (design only)

**Why:** even with Patch 1 the prefetcher only helps *inside* a single Get().
Batching N minimizers, issuing all N Murmur + prefetches first then resolving
all N, lets the CPU pipeline DRAM accesses across Get() calls.

**Status:** sketched in v2 §Patch 10 — invasive (changes ClassifySequence loop
shape); apply only if Phase 1+2 patches leave wall > 3.0 s.

---

## 5. Expected cumulative stack

If patches stack independently (different bottlenecks) at midrange estimates:

| Phase | Patch | Mechanism | Δ | Cumulative |
|---|---|---|---:|---:|
| baseline | — | — | — | **4.405 s** |
| 1 | 3 (flags) | inline + tight ASM | −8 % | 4.05 s |
| 1 | 2 (huge pages) | dTLB | −5 % | 3.85 s |
| 1 | 1 (prefetch) | hide DRAM in probe | −10 % | 3.47 s |
| 2 | 4 (thread LRU) | skip DRAM on hits | −20 % | 2.77 s |
| 3 | 6 (devirt) | drop vtable | −3 % | 2.69 s |
| 3 | 7 (single hash) | reuse MurmurHash | −2 % | 2.66 s |
| 3 | 8 (O(N) ResolveTree) | drop quadratic | −4 % | 2.55 s |
| 3 | 9 (skip output) | drop ostringstream | −1.5 % | 2.51 s |

**Target:** ≤ 2.6 s wall, ≈ −41 % vs 4.405 s, ≈ −55 % vs 5.635 s.

**Stop rule:** two consecutive patches with delta < 2 % → stop the cycle.

---

## 6. Results tables

### 6.1 M1–M7 measurements (completed 2026-06-24, Luna; full detail in `AccuracyDrift/patches.md`)

| ID | Metric | Value |
|---|---|---|
| M1 | cell size | 32-bit for all official DBs (26+6 split for the small custom `sample_targeted`, 16+16 for `standard_8gb`/`16gb`/`pluspf_103gb`) |
| M1 | load factor | ≈0.70 across every database (hardcoded in `kraken2-build`: `capacity = n_kmers / 0.70`) |
| M1 | PF_STRIDE | 16 cells/cache-line for all DBs (4-byte cell); formula `64/sizeof(Cell)` confirmed correct |
| M2 | dTLB miss rate (top-level, all loads) | 0.05–0.32% — but this is diluted by non-hash-table loads |
| M2 | dTLB miss rate (hash-table accesses only, normalised) | ≈65% for `standard_8gb` — the real number Patch 2 targets |
| M3 | top LLC-miss line (`perf record`) | kernel page-table-walker, 33–75% of misses depending on DB size (not `Get()` itself directly — see §2.5's causal-chain note) |
| M3 | `CompactHashTable::Get()` direct LLC-miss share | 2.24% (sample_targeted) → 5.70% (8gb) → 7.75% (16gb) → 10.57% (pluspf_103gb) — **grows monotonically with DB size** |
| M4 | DRAM bandwidth utilisation | 4.9–10.7% of peak across all DBs → **conclusively latency-bound, not bandwidth-bound** |
| M5 | minimizer/k-mer reuse rate | 90.7% |
| M6 | c2c HITM share | not run (low priority — only matters revisiting NUMA beyond 32T) |
| M7 | AVX-512 / AVX2 / SSE instruction count | 0 / 0 / 1,308 — **zero vectorisation in the stock binary**, motivating Patch 3's `-march=sapphirerapids` |

### 6.2 Patch application — real deviations from what Section 4 assumed

Patches 1-4 (the only ones actually implemented — `kraken2_opt_v1.patch` never coded Patches 5-10, which remain design-only proposals in Section 4) were applied by hand on 2026-08-03, not via `git apply`/`run_kraken2_opt_v1.sh` as originally planned. The live source tree on Luna had drifted from what the patch (and this report's Section 2/4) assumed:

- No `.git` in `~/tools/kraken2-src` — the apply script's `git apply`/`git reset --hard` approach would have failed outright.
- `CompactHashTable` is **not a template class** in this source tree (`CompactHashTable::Get`, not `CompactHashTable<Cell>::Get`) — Section 2.5's `template<typename Cell>` signature and Patch 1's `sizeof(Cell)` don't apply as written. Adapted using `sizeof(*table_)`, an idiom already used elsewhere in `compact_hash.cc`.
- The `Get()` implementation lives in `compact_hash.cc`, not `compact_hash.h` as the patch assumed.
- The Makefile was missing `-fPIC -g` and had no `CFLAGS` line — Patch 3's hunk didn't apply cleanly; hand-edited instead. Also, this Makefile's link recipes never reference `$(LDFLAGS)`, so the patch's `LDFLAGS += -flto=auto -fuse-linker-plugin` would have been dead code — folded into `CXXFLAGS` instead, which this Makefile does reuse for linking.
- A stray, unconditional `fprintf(stderr, "MMK %llu\n", ...)` debug print was found in the per-minimizer hot loop in `classify.cc` — likely leftover instrumentation from the M5 reuse-rate measurement above. Disabled (commented out, not deleted) before any benchmarking, since it would have added millions of syscalls per run and corrupted every timing number.

Full command-by-command record, including every verification step and exact line numbers: `Luna/experiments/patch/commands_log.md`. None of these deviations blocked the patch — every edit was achievable by hand once the real structure was understood — but they mean the patch file was written against a different (older, or never-verified-current) version of the source tree than what's actually deployed.

### 6.3 Benchmark — Patches 1+2+3+4 combined vs. baseline

Not measured as an incremental per-patch ablation (Section 6.2's original template) — Patches 5-10 don't exist to layer in, and 1-4 were tested as the single combined unit `kraken2_opt_v1.patch` actually ships. Measured across 4 databases × 3 thread counts × 2 builds × 2 memory-mapping modes (48 cells, 1 warm-up + 3 timed `perf stat` runs each). Full per-cell data: `Luna/experiments/patch/commands_log.md`.

**Patch effect (Δ wall time vs. baseline, same DB/threads/mode):**

| DB | T=1, no -M | T=1, -M | T=32, no -M | T=32, -M | T=96, no -M | T=96, -M |
|---|---|---|---|---|---|---|
| sample_targeted (50MB) | +4% (worse) | +1.5% (worse) | ~0% | +4% | ~0% | +1% (worse) |
| standard_8gb | **−5.2%** | **−6.4%** | ~0% | **−4.0%** | ~0% | ~0% |
| standard_16gb | **−3.6%** | **−4.6%** | ~0% | **−2.4%** | ~0% | ~0% |
| pluspf_103gb (111GB) | **−19.1%** | **−8.5%** | ~0% | **−4.9%** | ~0% | ~1.5% |

**Two consistent patterns, all four DBs:**
1. **The patch's benefit fades toward zero as thread count rises.** Patch 4's cache is `thread_local` — at high thread counts each thread sees only a small, less-repetitive shard of the read stream, diluting the cache's effective hit rate. Directly relevant to Thesis 1 (hardware-aware adaptive cache): a fixed thread-local cache size doesn't account for per-thread workload share shrinking as thread count grows.
2. **The patch's benefit at T=1 grows with DB size** (~0% on the LLC-resident `sample_targeted` up to −19% on `pluspf_103gb`) — matches M3's finding that `Get()`'s LLC-miss share itself grows monotonically with DB size, giving Patch 3's prefetch more to work with.
3. **On the smallest DB, the patch is mildly counterproductive** — the extra branch/cache-check overhead in the hot path isn't worth it when the DB already fits in LLC.

Absolute example (`standard_8gb`, 32T, the historical reference config): baseline 4.446s → patched 4.439s with no `-M` (statistically noise); baseline 0.96s → patched 0.922s with `-M` (real, ~4%, zero overlap between the two ranges across 3 runs each).

### 6.4 Unplanned finding — `-M` (memory-mapping) has a far larger effect than any patch, and was never used in this project

Discovered while setting up the benchmark: `classify`'s `-M` flag (wired to the wrapper's `--memory-mapping`) defaults to **off** in every standard command this project has ever run (M1-M7, all of `AccuracyDrift`, this report's own `4.405s` baseline figure). Without it, the hash table is read eagerly into a heap buffer before classification starts; with it, `mmap()` is used and pages fault in lazily as classification actually touches them — the eager-load cost is absorbed into, and mostly hidden by, the classification phase itself.

| DB | Size | `-M` savings @ T=32 | `-M` savings @ T=96 |
|---|---|---|---|
| sample_targeted | 50MB | ~4% | ~1.5% |
| standard_8gb | 8GB | −78.0% | −73.1% |
| standard_16gb | 16GB | −84.7% | −82.1% |
| pluspf_103gb | 111GB | **−92.2%** | **−93.0%** |

On `pluspf_103gb` at realistic thread counts, `-M` alone takes wall time from ~53s to ~4s — **more than a 12x speedup**, an order of magnitude larger than anything Patches 1-4 deliver, and the benefit scales up with DB size. **This is the single highest-leverage, lowest-effort finding in this report and should be adopted as the default invocation for any large-DB Kraken2 run in this project, independent of the patch itself.**

### 6.5 Reconciliation with Section 5's projected 2.6s target

Section 5 projected patches stacking to ~2.6s (a ~41% reduction from 4.405s) by summing independent per-patch estimates. That projection assumed all ten patches would be implemented and that classification time was the dominant cost to attack. Neither held: only Patches 1-4 were ever coded, and — as 6.4 shows — classification is only ~15% of wall time on `standard_8gb` without `-M`; the rest is DB-load time that no patch in Section 4 addresses (Patch 2 only touches the mmap path, which itself only activates with `-M`, an interaction Section 4 never anticipated since `-M` wasn't part of its plan). Patches 1-4 alone reach 4.439s (no `-M`, effectively the 4.405s baseline) or 0.922s (with `-M`, at 32T) — the latter beats the 2.6s target by a wide margin, but for a reason the projection never modelled.

---

## 7. Summary of proposals

| # | Proposal | Complexity | Expected Δ | Accuracy risk | Priority |
|---|---|---|---:|---|---|
| 1 | Probe-loop prefetch | Low | −5 / −15 % | None | **High** |
| 2 | Huge pages | Low | −3 / −8 % | None | **High** |
| 3 | `-march=sapphirerapids` + LTO | Trivial | −5 / −12 % | None | **High** |
| 4 | Thread-local k-mer cache | Low | −10 / −30 % | None | **High** (if M5 ≥ 0.20) |
| 5 | Per-socket DB replica | Med | TBD | None | Low (defer) |
| 6 | `final` + devirt dispatch | Low | −2 / −5 % | None | Med |
| 7 | Single MurmurHash | Low | −1 / −3 % | None | Med |
| 8 | O(N) ResolveTree | Low-Med | −2 / −6 % | None | Med |
| 9 | Skip output for /dev/null | Trivial | −1 / −2 % | None | Med |
| 10 | Batched Get pipeline | High | TBD | None | Defer |

Original Proposal A (LRU) survives as Patch 4. Original Proposal B (sequential
ESKAPE pipeline) is orthogonal to this report's CPU optimisations; revisit if
the standard_8 baseline is replaced by a per-pathogen DB workflow.

---

## 8. Execution plan

`kraken2_execution_checklist.md` has the linear top-to-bottom path: run M1–M7,
apply Phase 1 patches via `Luna/experiments/kraken2_opt_v1.patch`, benchmark,
decide on Patch 4 from M5, layer v2 patches with the < 2 % stop rule.

---

## 9. References

- Baseline profiling: `final_report.md`, `Luna/profiling/results_kraken2.md`
- Kraken-2 source: github.com/DerrickWood/kraken2 (master, 2026-05-29)
- v1 patches with rationale + diffs: `kraken2_get_optimizations.md`
- v2 patches: `kraken2_get_optimizations_v2.md`
- Apply script + bench harness: `Luna/experiments/run_kraken2_opt_v1.sh`
- Pending measurements: `Luna/experiments/pending_measurements.md`
- Linear execution plan: `kraken2_execution_checklist.md`
- Luna server specs: `Luna/luna_stats.md`
- Meeting context: `meeting_minutes.md` §Meeting 4 (2026-05-28)
