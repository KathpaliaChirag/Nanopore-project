# Research Brief — Associativity Case Study Groundwork (2026-09-02)

## Research question

CK's hypothesis: the current S2 N-way cache (`plan_paper/scripts/s2_lru_*way_patch.py`) is "more of a simulation than an actual cache," and a genuinely hardware-realistic implementation could prove 4-way set-associativity is a real win — where the 2026-09-02 associativity sweep found the opposite (more ways = better hit rate, worse wall-clock). 5 read-only agents (no code changes, no execution) researched: (1) cache-realism diagnosis + profiling plan, (2) literature on fast associative-cache techniques, (3) prior history/failure synthesis, (4) Orion (ARM) applicability, (5) adjacent speedup avenues. Full agent reports are in this session's transcript, not reproduced verbatim here — this file is the synthesized action plan.

## Confirmed facts about the current implementation

- `S2Entry{tag: uint64_t, taxon: taxid_t(uint64_t)}` = exactly 16 bytes, zero padding → 4-way round-robin sets are **exactly one cache line (64B)**, by accident, already hardware-shaped.
- The LRU variant adds `last_used(uint64_t)` → 24 bytes/entry → 4-way LRU sets = 96B = 1.5 cache lines. Real, previously-unflagged footprint growth on top of whatever eviction-policy delta is being measured.
- `S2Lookup` is an unconditional linear scan over all `S2_WAYS` entries **on every call, including misses** (72-96% of lookups even at 64-way).
- `s2_lru_{4,8,16,32,64}way_noatomics_patch.py` and `s2_rr_noatomics_patch.py` already exist on disk, removing the `std::atomic` hit/miss counters that were separately confirmed to cause a real ~2-3x contention artifact on `sample_targeted`. **`command_log.md` has zero mentions of "noatomics" — these binaries were written but never built or benchmarked.** Every number in the associativity sweep table is atomics-contaminated.

## Diagnosis: scan-cost vs allocation-cost (the sweep's own explicitly open question)

Both are real, not mutually exclusive; allocation/first-touch cost likely dominates, based on the DB/thread-dependence pattern already measured: `sample_targeted`/T=1 loses 80% at 64-way (short run, allocation cost not amortized) vs `pluspf_103gb`/T=32-96 losing ~0% (long run, allocation cost amortized away). Pure per-lookup scan cost should scale with lookup volume, not run length, so it doesn't explain this shape as cleanly as first-touch cost does. Not confirmed — needs the profiling plan below.

## Literature: two established techniques address this directly

1. **SIMD/SoA fingerprint matching** (Abseil SwissTable, folly F14, HPI's vectorized-hash-tables VLDB'23 paper): pack a 1-byte fingerprint per way into a contiguous array (fits one cache line for 4-16 ways), compare all ways in one `_mm_cmpeq_epi8`+movemask instruction, only chase the full 64-bit tag on a candidate hit. On a genuine miss this is O(1) SIMD compares, not O(ways) branches — the direct fix for the measured slowdown. M7 already found the current binary uses **zero AVX-512/AVX2**, only legacy SSE — real, unclaimed headroom on Sapphire Rapids.
2. **Skewed-associative caches** (Seznec 1993, ACM): index each way with a different hash function so a given key's conflict set differs per way — gets most of high-associativity's hit-rate benefit at low-associativity's lookup cost. Directly targets "more ways helps hit-rate, hurts wall-clock" without the AoS/scan overhead being the whole story.
3. **Real novelty gap confirmed**: no prior work combines vectorized/skewed multi-way tag matching with a k-mer/minimizer cache layer sitting in front of an existing classifier's hash table. kache-hash (Iceberg hashing + minimizer-aware primary table) and the "sparse and skew hashing of k-mers" paper are the closest adjacent work, but both redesign the primary table, not a cache layer — worth citing as related-but-distinct, not as prior art for this exact idea.

## History: what NOT to cite without caveats

- The original "22× slower / 85% LLC-miss" size-sweep cliff (2026-08-26) is **superseded** — later diagnosis (S3.0, 2026-08-30) showed most of it was a `thread_local` static-array TLS/stack-budget bug, not a generic large-array cost; S3.0 alone dropped the "old" baseline from 12.51s to ~1.18s.
- The pinning-eviction "+25.2% win" (2026-08-26) **reversed to −3.9%** once the `S2SetIndex` hash-mixing bug was fixed (S4.0, 2026-08-30) — it was an artifact of a few catastrophically overloaded sets under a broken raw-bitmask hash, not a real eviction-policy property. `research_brief_s3_s4_2026-08-26.md` and the 2026-08-27 debate report predate this reversal.
- "210MB LLC" (whole 2-socket machine) vs the corrected **105MB per socket** (what every `numactl --cpunodebind=0` benchmark actually sees) — any pre-2026-08-27 doc using 210MB in a sizing calculation is using the wrong constant.
- The current, load-bearing, non-superseded dataset is the 2026-09-02 sweep, run on the fixed (MurmurHash3-mixed) hash. Anything compared against it must also be on the fixed hash.

## Orion (ARM): not worth prioritizing now

Unreachable from this session (campus-network-only). This exact experiment was never attempted on Orion — blocked at the planning stage (`planning/plan_2026-07-25.md`) by an unresolved `-march=sapphirerapids` build-flag coupling, never revisited. Orion's 4MB shared SLC (vs Luna's 105MB/socket) means the "more cache hurts wall-clock" effect would very likely amplify, not reverse, but every AccuracyDrift DB is already past Orion's cache-capacity cliff, so the interesting Luna DB-size-dependence story can't reproduce 1:1 there anyway. Given the Sept 13 deadline and an explicitly Luna-centric paper target, skip. If time permits later: decouple the cache patch from the x86-only compile flag and run one DB/one small thread-count cell for a single LLC-miss-rate go/no-go data point — not a full sweep.

## Adjacent findings worth folding in (don't block the cache case study, but cheap and high-value)

1. **`-M`/`--memory-mapping` flag** — already measured (2026-08-03 session) at **12-14x** on `pluspf_103gb`, 78-85% on `standard_8gb`/`standard_16gb` — dwarfs every cache result to date, but was never adopted as the project's standard baseline flag. Any future case-study benchmark should decide explicitly whether `-M` is on for the baseline, or the comparison is measuring the wrong thing.
2. **Double hashing** — `second_hash()` already fully implemented in Kraken2 v2.17.1, dead behind `-DLINEAR_PROBING`. Flipping it is a compile-flag change, but requires a DB rebuild (real but bounded cost) — never measured on Luna. Near-zero engineering cost for a paper-relevant number.
3. **S5.0 prefetch batching** (`s5_0_prefetch_batch_patch.py` / `compare_s5_0_prefetch_sweep.py`) — written, never run (zero mentions in `command_log.md`). Mechanistically distinct from every cache lever (overlaps DRAM latency instead of avoiding it) — targets exactly the reuse-distance wall (81% of repeats land 10,000-1,000,000 lookups apart) that limited S2/S3/S4's ceiling. A separate branch (`hobbbit/mtp1/reports/PREFETCH.md`, per the 2026-08-30 debate) already measured 11.77% on a related batched-prefetch idea elsewhere — worth running S5.0 on Luna for a real number.
4. Compile flags (Patch 1) alone were never isolated from Patch 3+4 in the 2026-08-03 bundle run — plausibly a real independent win still uncredited, given M7's zero-vectorization finding.

## Proposed sequence (cheapest / highest-confidence first)

0. Decide `-M` as the standard baseline flag going forward, given it dwarfs every other lever measured so far — every step below should state explicitly whether `-M` is on.
1. Rebuild + rerun the **already-existing, never-benchmarked noatomics** binaries (4/8/16/32/64-way) on the same `standard_8gb`/T=1 sweep — zero new code, isolates the atomics-contention confound from the associativity conclusion.
2. Build a standalone synthetic microbenchmark that only allocates + first-touches a `S2_NUM_SETS × S2_WAYS` thread-local array and exits (no kraken2, no hash table) — sweep ways 4→64 to get a clean allocation-cost curve, subtract from step 1's deltas to estimate the scan-cost residual.
3. `perf record -g`/`perf annotate` on `S2Lookup`/`S2Insert`, plus `page-faults`/`minor-faults`/`cycle_activity.stalls_l3_miss` counters, on the noatomics binaries at T=1 and T=96 — confirms which cost actually dominates.
4. Implement the SIMD/SoA redesign (1-byte fingerprint array per set, SSE2/AVX2 compare, no atomics) — informed by SwissTable/F14 — and/or a skewed-associative index variant, as the "real hardware-realistic 4-way cache."
5. Three-way case study: S0 (no cache) vs. current AoS/atomics simulated 4-way (already documented) vs. the new SIMD/SoA 4-way, across the DB/thread grid already known to matter (small DB is the stress case). **Supports the thesis** if (c) beats (a) with a real low-CV wall-clock win at 4-way *and* profiling shows lower per-lookup cost than (b) at equal capacity. **Undermines it** if (c) still loses to (a), or only wins on DBs already flattered by low first-touch amortization (`pluspf_103gb`) — which would instead point back to S3's sizing/first-touch domain, not an associativity/hardware-realism argument.
6. Only after 0-5: revisit LRU vs. round-robin vs. skewed-associative eviction on the corrected fast implementation.

## Debate outcome (2026-09-02, same day) — 5 agents, 5 rounds, unanimous lock

CK asked for a second pass: 5 fresh agents (Alpha-Epsilon) independently debated the two open questions above — the scan-cost vs. allocation-cost diagnosis, and the highest-leverage next action — through 5 rounds (round 1 fully independent, round 2 cross-critique, round 3 locked positions, rounds 4-5 confirmation). Full 5/5 unanimous, stable through 3 confirmation rounds:

**Q1 (diagnosis) — locked:** (b) per-thread first-touch/allocation cost is the dominant cause of "more ways, worse wall-clock" (medium/medium-high confidence) — the DB/thread-count shape (worst on `sample_targeted`/T=1, vanishing on `pluspf_103gb`/T=32-96) is an amortization signature, matching this project's own S3.0/S3.3 precedent, not a per-lookup-volume signature. (a) O(ways) linear scan cost is real but secondary. (c) the atomics-contention artifact is real but concentrated in multithreaded cells (Beta's point: the T=1 `sample_targeted` cell is contention-immune by construction and still shows the worst penalty, ruling out (c) as the primary driver of the worst case) — it likely inflates the T=32/96 `sample_targeted` cells specifically, stacked on top of a smaller real (b) effect there.

**Q2 (action) — locked:** **(i) rebuild+run the already-existing noatomics binaries → (iii) adopt `-M`/`--memory-mapping` as the project's standard baseline and re-measure headline S1/S3/S4 numbers against it → (iv) flip double hashing (`-DLINEAR_PROBING` off) and measure the false-positive-cliff shift. Stop there for this cycle.**

**(ii) the SIMD/SoA hardware-realistic cache redesign — dropped from this cycle's plan, revisit post-Sept-13.** This was the substantive fault line: Epsilon argued from S3.4 (full-grid null: S0=S2-baseline=S2-final everywhere) and S4.0 (an 8.9x hit-rate fix produced zero wall-clock win, only ~3.2% of the lookup stream) that the cache subsystem's total contribution to runtime is architecturally too small to matter — a ceiling that's about hit-rate/benefit, not implementation overhead — so a SIMD/SoA rewrite most likely still nets to zero even if it cleanly explains away the associativity penalty. Alpha/Beta/Gamma/Delta initially countered that this argument targets the *benefit* side, not the *cost* side (the associativity sweep's 80% penalty is an overhead effect, a different budget from S4.0's hit-rate benefit), and proposed a tightly scoped, timeboxed, single-cell go/no-go version. By round 3 all 5 converged that this distinction doesn't survive contact with the 11-day budget: a "conditional, only-if-time-remains" item competing behind three already-committed, higher-certainty items is not actually a plan, and this project's own command log already shows multi-day stretches where planned-but-unscheduled items never got built. Unanimous: drop (ii) explicitly rather than carry it as a phantom fourth item.

Also resolved along the way: Epsilon initially argued to also drop (iv) double hashing alongside (ii), using the same ceiling logic — but conceded in round 2 this over-extended the argument: double hashing changes the *primary* hash table's probe sequence (100% of lookups), not a capacity-limited cache layer in front of it, so the S3.4/S4.0 ceiling (about the k-mer cache specifically) doesn't transfer. All 5 agree (iv) stays in scope.

## Status

Planning only — nothing above has been built, run, or measured. This brief, plus the debate outcome above, exists to hand off to whichever work session actually executes it.
