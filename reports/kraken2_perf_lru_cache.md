# Kraken2 — perf Profiling & K-mer→Taxon Associativity Table (LRU)

**Date:** 2026-05-29
**CPU:** AMD Ryzen 7 7735HS (Zen4, 8c/16t, 6-wide dispatch)
**DB:** minikraken2_v2_8GB
**Context:** Follow-up to Phase 2a gprof results. Goal: quantify the memory-bound bottleneck
numerically (cache-miss%, IPC, TMA), understand the `-pg` profiling overhead, and design
a small set-associative table that maps frequent k-mer (minimizer) accesses directly to
their taxon IDs — keeping hot k-mers resident in L3 and using LRU to evict cold ones.

---

## 1. Perf Stat Profiling (perf stat -d -d)

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104,832 | 89.25% | 17.651 s | 356.3 Kseq/m |
| hac  | 104,918 | 97.18% | 18.828 s | 334.4 Kseq/m |
| sup  | 104,980 | 97.9%  | 19.506 s | 322.9 Kseq/m |

### General CPU Performance

| Mode | Wall (s) | Cycles | Instructions | IPC | Cache-Miss% | Branch-Miss% |
|------|--------:|---------:|-------------:|----:|------------:|-------------:|
| fast | 24.34 | 1,071,664,130,119 | 164,810,508,057 | 0.154 | 24.42% | 3.05% |
| hac  | 25.77 | 1,129,319,087,575 | 185,409,948,546 | 0.164 | 24.59% | 2.91% |
| sup  | 25.97 | 1,162,582,602,427 | 193,221,040,664 | 0.166 | 24.72% | 2.79% |

> **Cache-Miss% is process-wide aggregate across all active threads/cores**, not a
> single-core figure. `perf stat` sums `cache-misses` and `cache-references` across
> every thread the process ran on, then computes the ratio. The ~1T cycle counts
> (vs ~96B for a single core over 24s at 4 GHz) confirm this is a 16-thread aggregate.

### Key Numbers

- **IPC ~0.16** — extremely low. A healthy CPU-bound workload runs IPC 2–4. This means the pipeline is stalled ~94% of the time waiting for memory.
- **Cache-Miss% ~24%** — 1 in 4 cache reference operations misses L3 and goes to DRAM. With an 8 GB DB vs 16 MB L3 this is expected: the working set is 500× larger than L3.
- **Branch-Miss% ~3%** — low, not contributing significantly to stalls.

---

## 2. TMA L1 Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 2.8% | 1.5% | 95.6% | 0.0% | 0.153 |
| hac  | 3.0% | 1.5% | 95.5% | 0.0% | 0.162 |
| sup  | 3.0% | 1.5% | 95.5% | 0.0% | 0.164 |

**BE-Bound 95.6%** confirms the pipeline is almost entirely stalled in the backend —
waiting on memory, not frontend decode or branch mispredicts.

### TMA Bucket Meanings

| Bucket | Meaning | Good value |
|--------|---------|-----------|
| Retiring | Fraction of slots doing useful work | High (>60%) |
| FE-Bound | Frontend starvation (i-cache miss, decode stall) | Low (<15%) |
| BE-Bound | Backend bottleneck (memory latency, execution pressure) | Low (<20%) |
| Bad-Spec | Slots wasted on mispredicted paths | Low (<5%) |

**Retiring is only 2.8–3.0%.** The pipeline is doing real work less than 3% of the time.
Every other slot is stalled waiting on DRAM.

### Frontend IC-Stall Note

IC-Stall% = ~95% sounds alarming but is a **backend artifact**. When the backend stalls
on DRAM (95.6% BE-Bound), the entire pipeline backs up including the fetch stage — so
IC-Stall fires too. FE-Bound (1.5%) is the real frontend metric; the frontend is fine.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc`            | 1,074,798,706,839 | 1,134,835,248,575 | 1,171,655,712,100 |
| `ex_ret_ops`                   | 182,104,316,300   | 202,744,401,695   | 211,848,270,738   |
| `ex_ret_instr`                 | 164,381,770,853   | 183,317,374,925   | 191,909,813,349   |
| `de_dis_uop_queue_empty_di0`   | 16,582,833,769    | 17,442,183,691    | 17,784,778,882    |
| `ex_ret_near_ret_mispred`      | 435,688,254       | 438,373,715       | 442,058,888       |
| `op_cache_hit_miss.op_cache_miss` | 3,938,963,302  | 4,137,789,874     | 4,256,597,901     |
| `ic_fetch_stall.ic_stall_any`  | 1,026,066,762,895 | 1,082,030,083,513 | 1,116,268,507,326 |

---

## 3. Top Functions by CPU Time (perf record -g)

Consistent across all three modes:

| Rank | % CPU | Function |
|-----:|------:|----------|
| 1 | ~34% | `kraken2::MinimizerScanner::NextMinimizer()` |
| 2 | ~17% | `kraken2::MinimizerScanner::reverse_complement()` |
| 3 | ~14% | `ClassifySequence()` |
| 4 | ~7%  | `_mcount` |
| 5 | ~7%  | `kraken2::MinimizerScanner::canonical_representation()` |
| 6 | ~6%  | `__mcount_internal` |
| 7 | ~5%  | `mcount@plt` |
| 8 | ~1%  | `kraken2::CompactHashTable::Get()` |

> **Note on mcount:** Ranks 4, 6, 7 (`_mcount`, `__mcount_internal`, `mcount@plt`) are
> **gprof profiling instrumentation overhead** from the `-pg` flag in `Makefile` line 3.
> Combined they account for ~18% of all CPU time. This is waste, not real work.
> See Section 5 below.

> **Note on CompactHashTable::Get() at only ~1%:** perf record under `-pg` is unreliable
> for attribution — `mcount` wrapping distorts sample counts. The gprof flat profile
> (Phase 2a) correctly shows `Get()` at 80.65% of CPU time. The perf record ranking
> here reflects sampling bias introduced by profiling overhead.

---

## 4. Per-Core CPU Utilization (mpstat, every 2s)

All 16 logical CPUs active, average utilization ~25% per core, peaks at 99–100%.

| Mode | Overall Avg %usr | Most Loaded Core |
|------|----------------:|----------------:|
| fast | 25.3% | CPU0 99.5% |
| hac  | 26.0% | CPU1 100.0% |
| sup  | 25.7% | CPU10 100.0% |

Low average (~25%) with high peaks means: a few cores are doing most of the work
at full speed, while others idle. This is consistent with a memory-latency-bound workload —
threads stall on DRAM and yield CPU time, giving the appearance of low utilization.

---

## 5. Finding: -pg Flag Causes ~18% Overhead

**File:** `tools/kraken2/src/Makefile` line 3 — the `-pg` flag in `CXXFLAGS` enables gprof instrumentation by inserting an `mcount()` hook at every function entry and exit. perf record shows:
- `_mcount`           ~7% CPU
- `__mcount_internal` ~6% CPU
- `mcount@plt`        ~5% CPU
- **Total: ~18% of all CPU time is profiling overhead**

**Fix:** Remove `-pg` from CXXFLAGS, `make clean && make`. This is a one-line change with
~18% wall-time reduction and zero correctness risk. `-g` (debug symbols) can stay — it
has no runtime cost.

---

## 6. K-mer→Taxon Associativity Table (LRU) for CompactHashTable::Get()

### What It Maps

Every minimizer lookup in Kraken2 is a direct mapping of **minimizer (k-mer hash, 64-bit) → taxon ID (32-bit)**. `CompactHashTable::Get()` performs this mapping by probing the 8 GB DB at a random DRAM address. The associativity table intercepts that call and serves the result from L3 when the k-mer has been seen before:

- Read sequence → `MinimizerScanner` generates k-mer hashes (minimizers)
- Each minimizer is looked up in the set-associative table first
  - **HIT:** taxon ID returned from L3 (~10 ns, no DRAM)
  - **MISS:** `CompactHashTable::Get()` hits DRAM (~100 ns, 8 GB random probe), result stored back into table
- Taxon ID feeds into `ClassifySequence()`

LRU ensures the **most frequently accessed k-mers stay resident**. K-mers from common
organisms repeat across thousands of reads and stay warm. Rare k-mers get evicted.
This is the Hot-K-mer LRU cache concept from Kolin sir (Phase 2a).

### Why Frequent K-mers Have Temporal Locality

- Classification rates: fast 89%, hac 97%, sup 98% — most reads hit DB organisms
- Reads from the same organism produce the same minimizers → same k-mer→taxon mappings repeat across reads
- The LRU table keeps the hot mappings in L3; cold/rare k-mers naturally fall out

### Design: 4-Way Set-Associative Table Per Thread

**New file:** `tools/kraken2/src/minimizer_cache.h`

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Sets | 8192 | Power of 2 — fast modulo via bitwise AND |
| Ways | 4 | 4-way associativity absorbs hot-spot collisions |
| Entry | k-mer (64-bit) + taxon ID (32-bit) + LRU tick (32-bit) = 16 bytes | Cache-line aligned |
| Size per thread | 8192 × 4 × 16 = **512 KB** | Fits in per-core L3 slice |
| Total (16 threads) | **8 MB** | Half of 16 MB shared L3 |

Entry states:
- Empty slot — k-mer not yet seen by this thread
- taxon ID = 0 — k-mer confirmed absent from DB (avoids re-hitting DRAM for known misses)
- taxon ID > 0 — k-mer maps to this taxon

LRU eviction: each entry tracks an access timestamp; on a set collision the least-recently-used entry is evicted. Per-thread with no locking.

### Integration Point

The single call to `CompactHashTable::Get()` inside `ClassifySequence()` is wrapped with a table lookup. On a hit the taxon ID is returned from L3 without touching DRAM. On a miss the DB is queried as before and the k-mer→taxon mapping is stored in the table for future reads.

The existing consecutive-duplicate check (skips the DB entirely when the same minimizer appears in back-to-back windows) is complementary and stays in place. The associativity table handles non-consecutive repeats within and across reads.

### Expected Impact

| Metric | Before | Expected After |
|--------|--------|----------------|
| Cache-Miss% | ~24% | ~10–15% |
| IPC | ~0.16 | ~0.25+ |
| Wall time reduction | — | 20–40% (combined with -pg removal) |

### Files to Change

| File | Change |
|------|--------|
| `src/minimizer_cache.h` | New file — `MinimizerCache` struct |
| `src/classify.cc` | Add `#include`, add `MinimizerCache mcache` per thread, update `ClassifySequence` signature and body |
| `src/Makefile` line 3 | Remove `-pg` |
| `src/Makefile` line 30 | Add `minimizer_cache.h` to `classify.o` deps |

---

## 7. Alternative: Software Prefetch (Latency Hiding vs Elimination)

The associativity table *eliminates* DRAM accesses for repeated k-mers. Prefetching instead *hides* the latency — it issues the next k-mer's DB fetch early so it overlaps with current computation, but the DRAM access still happens either way.

**Pros:** Helps even for cold/non-repeated k-mers — effective where the table has no entry yet.
**Cons:** Requires looking one minimizer ahead in the scanner (more invasive change); only one step of lookahead possible.
**Verdict:** The associativity table is the cleaner first step. Prefetching is a follow-on if miss rate stays high after the table is in place.
