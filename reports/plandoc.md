# Kraken2 Optimization Design — `plandoc.md`

Goal: **raise IPC, cut cache misses (raise hit rate), and use the machine properly** by
attacking DRAM latency at every layer of `kraken2 classify`.

> **Status:** design document only (no code / rebuild this pass). Merged with the remote
> Ultraplan refinement — see *Provenance* below.

---

## 0. Provenance & data corrections (Ultraplan merge)

The remote Ultraplan session ran on the **committed** git tree, where `tools/` and
`results/` are **untracked** (`?? tools/`, `?? results/`). From that clone the kraken2
source and per-thread perf data were invisible, so its "no source / those numbers don't
exist" claims are **clone artifacts** — locally both exist and were read directly.

Corrections **adopted** from Ultraplan (valid against the committed reports):

1. Lead the verdict with the **verifiable gprof headline: `Get()` = 80.65%** of CPU time.
2. `ls_not_halted_cyc` quoted against **one baseline (T8): +14.0% @T10, +26.6% @T16**
   (not the mixed-baseline "+24.5% T16-vs-T1").
3. The short `kraken2_thread_scaling.md` is a **separate run** (T8 5.42× / IPC 1.36 /
   wall 2.70 s); this doc cites the **full report** and supersedes rather than contradicts.
4. CPU is **Zen3+ (Rembrandt-R)**, not "Zen4" (earlier reports mislabelled it).
5. Fast **unclassified rate is run-dependent** (6.82% thread-scaling run vs 10.75% lru run)
   — stated once for the anchored run, not asserted as a universal "~11%".

**Kept (real locally, flagged):** clean-binary perf-record figures `NextMinimizer 17.51%`,
`Get() 16.45%` — from local untracked `results/kraken2/fast/thread_8/perf_record_report.txt`.
**Rejected (false locally):** "no `tools/kraken2/src/`". `file:line` refs were verified
against the local source but remain flagged "re-confirm at implementation time."

---

## 1. Why — the verdict from the stat/report files

Kraken2 `classify` is **DRAM-latency bound**, not compute bound.

| Evidence | Number | Source |
|---|---|---|
| `CompactHashTable::Get()` share of CPU **(headline, verifiable)** | **80.65%** | gprof Phase 2a (`report.md`, `kraken2_perf_lru_cache.md`) |
| IPC (`-pg` binary) / BE-Bound / Retiring | **0.154 / 95.6% / 2.8%** | `kraken2_perf_lru_cache.md` §1–2 |
| IPC after `-pg` removal | ~1.1–1.4 | same |
| T8 fast, clean: speedup / IPC / BE-Bound | **5.36× / 1.4017 / 74.62%** | `kraken2_thread_scaling_full.md` |
| T8 cache-miss% (clean) | **15.91%** (393,780,554 / 2,475,077,375) | `perf_stat_dd.txt` (local untracked) |
| T8 perf-stat wall | **8.393 s** | `kraken2_thread_scaling_full.md` / `perf_stat_dd.txt` |
| Top cache-miss hotspots (clean) | `NextMinimizer` 17.51%, `Get()` 16.45% | `perf_record_report.txt` (local untracked) |
| DB vs L3 | 8 GB DB ≈ **500× the 16 MB L3** → cold lookup ≈100 ns DRAM probe | — |
| Bandwidth saturation (vs T8 baseline) | `ls_not_halted_cyc` flat T1–T8, **+14.0% @T10**, **+26.6% @T16**; instructions flat ±1.8% | `kraken2_thread_scaling_full.md` |
| Sweet spot | **T8** (best IPC + lowest BE-Bound; T16 = +23% throughput for −20% IPC) | thread scaling §7 |

**Single hot call site:** `classify.cc:838` `taxon = hash->Get(*minimizer_ptr);` inside
`ClassifySequence` (`classify.cc:792-929`), in the per-thread OpenMP worker
(`ProcessFiles`, `classify.cc:519`). Each thread owns its own `MinimizerScanner` → a
per-thread cache needs **no locking**. *(line refs: re-confirm against local checkout.)*

**Baseline build** (`tools/kraken2/src/Makefile:3-4`):
`-fopenmp -Wall -std=c++11 -O3 -fPIC -g -DLINEAR_PROBING`. No `-march=native`,
`-mtune=native`, `-flto`. `-pg` already removed. CPU: **AMD Ryzen 7 7735HS, Zen3+
(Rembrandt-R), 8c/16t, 16 MB L3.**

---

## 2. The design — 5 stackable layers (ordered by impact)

Each layer is independent and can be enabled/measured on its own.

### Layer 1 — Per-thread k-mer→taxon set-associative cache  *(headline)*
- New header `tools/kraken2/src/minimizer_cache.h`, one instance per OpenMP thread,
  wrapping the single `hash->Get()` at `classify.cc:838`.
- **4-way set-associative**, 8192 sets → 32K entries. Entry = key(64b)+taxon(32b)+LRU tick
  = 16 B → **512 KB/thread** (~4 MB across 8 threads, fits L3 beside taxonomy).
- Set index = `(MurmurHash3(kmer) >> shift) & (8192-1)` → bitwise AND, no modulo.
- Three states: **empty** / **taxon=0** (confirmed-absent — avoids re-probing DRAM for
  known misses; the unclassified fraction is run-dependent, 6.8–10.8%) / **taxon>0**.
- LRU eviction within a set; per-thread, lock-free.
- **Exact**: stores the full 64-bit key → a hit returns exactly what `Get()` would →
  **bit-identical output**. This is the default.
- Complements the existing consecutive-duplicate skip (`classify.cc:830` `last_minimizer`,
  back-to-back only); the cache catches non-consecutive repeats within/across reads.
- **Expected (projection):** cache-miss 15.91% → 10–13%, IPC +15–30%, wall −15–30% on
  repeat-heavy input.

### Layer 2 — Software prefetch (latency hiding for cold k-mers)
- Cache eliminates repeats; prefetch hides latency for genuine misses.
- Hoist a read's minimizer stream into a small per-thread ring buffer; for minimizer *i*
  issue `__builtin_prefetch(&table_[idx])` for minimizer *i+P* (P≈4–8) using the same
  `hc % capacity_` math as `Get()`. Add a `Prefetch(key)` helper on `CompactHashTable` so
  the probe math lives in one place.
- Helps exactly the cold k-mers Layer 1 cannot. **Expected:** IPC +5–15%.

### Layer 3 — Build flags
- `Makefile:3`: add `-march=native -mtune=native -flto` (keep `-O3 -g`).
- Enables Zen codegen + auto-vectorization of MurmurHash3 / scanning + cross-TU inlining
  of the hot `Get()`/scanner path. `-flto` on both compile and link lines.
- Zero correctness risk; rebuild only.

### Layer 4 — Transparent huge pages for the 8 GB table (TLB pressure)
- 8 GB / 4 KB = 2M pages → constant dTLB thrash on random probes.
- Back the table (`compact_hash.h:172` `new Cell[capacity_]` / mmap path `:216`) with 2 MB
  huge pages: `posix_memalign` + `madvise(MADV_HUGEPAGE)` (or `MAP_HUGETLB` on mmap path).
  8 GB → 4096 huge pages → dTLB walks collapse.
- Runtime-only alternative (no code): THP `always`/`madvise` + optional hugetlb
  reservation (sysadmin step — hand the command to the user to run). **Expected:** IPC +5–10%.

### Layer 5 — Run at the bandwidth sweet spot (use the system properly)
- T16 wastes cores (bandwidth saturates at T10). Default **`-p 8`**, optionally pin with
  `OMP_PLACES=cores OMP_PROC_BIND=close` so 8 threads hold 8 physical cores and don't fight
  SMT siblings for L1/L2 + load queues. Pure runtime/env — no code.

### Optional approximate fast-path (opt-in, off by default)
- Store a **16-bit key tag** instead of the full key in the Layer-1 cache → entry 16 B → 8 B,
  doubling capacity in the same L3 footprint, at a ~1/65536 false-hit rate per occupied way.
- Validate the classification-rate delta against the exact run's `kraken2_report.txt`.
- Note: Kraken2's CompactHashTable is *already* probabilistic (truncated stored keys), so a
  tiny added tag-collision rate is within the tool's existing error model.

---

## 3. Expected combined impact (projection — no rebuild this pass)

| Metric | Baseline (T8, clean) | Projected (L1–L5) |
|---|---|---|
| Cache-miss% | 15.91% | 9–12% |
| IPC | ~1.40 | 1.8–2.3 |
| Wall (fast, `reads_fast.fastq`) | 8.39 s | 5.5–6.5 s |

Confirm by rebuild + re-running the perf sweep (§6).

---

## 4. Broader speedup menu (other ways to make Kraken2 faster)

The hot cost is **not only `Get()`** — `NextMinimizer()` is the #1 cache-miss hotspot, so
minimizer generation and the software pipeline are legitimate second fronts.

### High value
- **A. Group-prefetch / AMAC pipelining.** Stronger Layer 2: keep N≈8–16 probe
  state-machines in flight per thread, prefetch each cell, round-robin advance. Textbook
  hash-probe latency hiding (2–3× on probe-bound work); turns serial DRAM stalls into overlap.
- **B. Faster minimizer scanning (attacks #1 hotspot).** `MinimizerScanner` recomputes
  reverse-complement / canonical form per position. Use a **rolling 2-bit encoding** (shift
  in one base, O(1)) + incremental rolling rev-comp → a few ALU ops per step instead of a
  full k-mer recompute. Pack read to 2-bit once, then slide.
- **C. PGO + LTO + BOLT.** `-fprofile-generate`→`-fprofile-use` lays out hot branches in
  `Get()`/`NextMinimizer()`; BOLT improves I-cache layout. ~5–15%, bit-identical.

### Medium value
- **D. Bucketized / one-cache-line DB layout.** Rebuild DB so all probe candidates for a key
  live in one 64 B line (16 cells) → probe *chain* becomes one cache line. Cuckoo/bucketized.
  Build-tool change, exact.
- **E. Static hot sub-table.** Offline-build a small table of the most frequent minimizers
  (fits L3) checked before the 8 GB table — a persistent, shared, zero-warm-up Layer 1.
- **F. 1 GB huge pages** (vs 2 MB): 8 GB → 8 TLB entries, near-zero dTLB walks. Needs
  boot-time hugepage reservation.
- **G. Fewer lookups via index params.** Larger minimizer window `l` / spaced seed at
  DB-build → fewer distinct minimizers per read → fewer probes. Accuracy trade-off; measure.

### Lower value / situational
- **H. I/O & output path.** `#pragma omp critical(seqread)` (`classify.cc:542`) serializes
  input; output uses a priority queue + criticals and `sprintf`/`ostringstream` churn
  (`__memmove_avx` ~4%). For huge inputs: lock-free input batching + buffer reuse.
- **I. Skip optional work.** `HyperLogLogPlusMinus::insert` (~3.4%) only runs with
  `-R/--report`; omitting the report (or a cheaper sketch) saves it.
- **J. Hardware angle.** Bandwidth-bound at T10 → more memory channels / NUMA interleave
  lifts a ceiling no code change can.
- **K. GPU offload of probes.** Batch millions of minimizer→taxon lookups onto the GPU
  (already present for Dorado) to hide latency via massive parallelism. High effort, separate
  project.

**Recommended next wave after L1–L5:** A, B, C. Backlog: D–K, ranked by effort/payoff.

---

## 5. Files involved (local-source pointers — re-confirm at implementation time)

| File | Role |
|---|---|
| `tools/kraken2/src/minimizer_cache.h` *(new)* | Layer 1 cache |
| `tools/kraken2/src/compact_hash.h:258-277` | `Get()` — integration target (L1–L2) |
| `tools/kraken2/src/classify.cc:838` / `:792-929` / `:519` | call site / classify loop / OMP region |
| `tools/kraken2/src/kv_store.h:58` | `MurmurHash3` — probe math to mirror |
| `tools/kraken2/src/Makefile:3` | build flags (L3) |

---

## 6. How to measure (test plan)

1. Build each layer, then `make clean && make`.
2. Re-run the existing sweep: `perf stat -d` (cache) and `perf stat -d -d` TMA on
   `reads_fast.fastq` at `-p 8`.
3. Diff **IPC**, **cache-miss%**, **wall** vs the T8 baseline above.
4. **Correctness:** require **bit-identical `kraken2_report.txt`** for the exact path; for
   the optional approximate path, record the classification-rate delta vs the exact run.
