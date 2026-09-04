# Research brief - Track A pivot point (2026-08-30)

## Research question

Given today's (2026-08-30) hands-on findings on the Kraken2 adaptive k-mer cache thesis (Track A), what is the highest-leverage next step for the remaining ~13 days before the Sept 13 submission, and is continuing to engineer the S2 cache itself (sizing, hashing, eviction policy) still the right lever at all, versus alternatives?

## How to run this

5-10 independent agents, at least 3 rounds:
- **Round 1:** fully independent research against primary sources, zero cross-visibility.
- **Round 2+:** each agent reads all other agents' prior-round papers, challenges specific claims with evidence, revises its own position.
- **Final round:** locked consensus positions plus a synthesized recommendation.

Iterate until the group is actually satisfied it has converged, not just until a round count is hit, the same standard as this project's prior debate exercises (`plan_paper/s3_s4_debate_report_2026-08-27.md`, `plan_paper/two_thesis_strategy_debate_2026-08-30.md`).

## Repo

`C:\Users\user\OneDrive\Desktop\Nanopore-project` (also https://github.com/KathpaliaChirag/Nanopore-project), a Kraken2 (CPU taxonomic classifier) optimization thesis project on a Xeon Sapphire Rapids machine ("Luna", 2-socket, 105MB L3/socket, 96c/192t).

## Required primary-source reading - verify every number yourselves, don't trust the summary below as gospel

1. `plan_paper/command_log.md`, read the whole file, especially every 2026-08-30 entry (S3.0 through the final S4.0 hash-mix/pinning-reversal entry). this is the dated receipt of everything actually measured today.
2. `plan_paper/s3_s4_debate_report_2026-08-27.md`, prior technical design debate for S3 (sizing) and S4 (eviction).
3. `plan_paper/two_thesis_strategy_debate_2026-08-30.md`, prior broad strategic debate (ran *before* today's session, doesn't know today's findings).
4. `planning/week6plan.md` for any S3/S4 context not superseded by #2.
5. **New, not previously considered in any prior debate:** https://github.com/KathpaliaChirag/Nanopore-project/blob/hobbbit/mtp1/reports/PREFETCH.md (note: lives on branch `hobbbit/mtp1`, not `main`, fetch from that branch specifically). this documents a software-prefetching optimization on `CompactHashTable::Get()` itself (batching minimizer lookups so the CPU can overlap ~4 outstanding memory requests instead of serializing them) achieving an already-measured **11.77% speedup**, with memory-level parallelism going from 1.24 to near hardware capacity (~12) and cycles/lookup dropping from 868.5 to 736.0 at batch size 4 (`-B 29`). directly relevant because it speeds up the *real* hash table lookup that today's findings show dominates everything, a fundamentally different lever than caching in front of it.
6. `dorado-kraken-research/docs/reports/kraken2_get_optimizations.md` and `kraken2_get_optimizations_v2.md`, related prior prefetch/optimization analysis already on `main`, for cross-reference against #5.

## What happened today (2026-08-30), condensed - re-derive and verify from `command_log.md`, don't just cite this

- S3.0: fixed a real crash bug (thread_local array vs. static-TLS/stack-budget). S3.1/S3.2: built a dynamic, LLC-topology-aware sizing formula. S3.3: fixed a real slowdown bug (eager sentinel writes vs. lazy zero-pages). all verified, committed, tagged (`safe/S3.0`, `safe/S3.1-S3.2`, `safe/S3.3`).
- **S3.4** (full benchmark, 3 DBs x 6 thread counts x 3 runs): zero measurable wall-clock difference between no-cache, the original fixed-size cache, and the fully-fixed dynamic cache, anywhere. root cause: hit rate never exceeds ~1.5% even at the largest safely-tested size (262,144 sets), so the cache's absolute contribution to total work is too small to clear ~1-5% measurement noise.
- **S4.0 diagnostic:** found `S2SetIndex` (the function picking which cache "set" a minimizer goes into) was a raw low-bit mask with zero hash-mixing, catastrophically broken (one set absorbed 225x the average load across 4,096 sets, another was never touched, on `standard_8gb`/T=1).
- **S4.0b/c fix:** mixed the minimizer through Kraken2's own `MurmurHash3` (already used elsewhere in the codebase) before masking. hit rate went from 0.4035% to **3.5758%** (~8.9x) at the identical capacity; occupancy max/mean dropped from 225.42 to 3.95. committed, tagged `safe/S4.0-hashmix`.
- but still no wall-clock win, same root cause as S3.4, just a smaller total gap now (95,377 additional hits out of ~3M lookups is still only ~3.2% of the lookup stream).
- **The critical reversal:** re-running the one previously-promising eviction-policy result (a "protect any entry hit once" pinning rule, +25.2% relative hit-rate gain over round-robin, measured 2026-08-26) on the now-fixed hash flips it to **-3.9% relative**, the original win was an artifact of a few catastrophically overloaded sets, not a real property of the eviction problem. this undermines the planned next step (a saturating-counter eviction design, a direct refinement of the same now-disproven idea).

**One correction already found by an earlier single-agent pass on this exact question, worth starting from rather than re-discovering:** the reuse-distance histogram logged today does NOT need to be re-measured on the fixed hash, it tracks the raw minimizer stream via its own independent `unordered_map`, with no dependency on `S2SetIndex`'s hashing at all. it would reproduce identically. don't spend a round re-deriving this.

## Specific questions to answer, with reasoning, not hedges

1. Is there a genuinely different eviction policy, not a refinement of "protect proven-useful entries", with a real chance of helping on a now-correctly-hashed cache? consider real prior art (LLM KV-cache eviction, CDN/OS page-replacement, database buffer-pool eviction) against this specific access pattern.
2. Does raising cache capacity deserve a second look, now that hit rate is ~3.5x higher at the same small size than when S3.4's "capacity doesn't matter" conclusion was reached? was the original diminishing-returns size-sweep data (2026-08-26) also measured on the broken hash?
3. Given PREFETCH.md's already-measured 11.77% real speedup on the actual bottleneck, should remaining effort pivot from "cache in front of `Get()`" toward "make `Get()` itself faster" (prefetch-batching), either instead of or alongside further S4 eviction work? is this synergistic with the cache work, competing with it for engineering time, or should it simply replace the S2 cache thesis angle?
4. Is Track A (the adaptive cache) still the right use of ~13 remaining days versus shifting more effort to Track B (double hashing + bitmask cell, currently paused per the user's own sequencing choice)?
5. Anything else in the primary sources that changes the picture, unprompted.

## Deliverable

A single synthesized report (not per-agent dumps) with a clear, specific, actionable recommendation for the next working session on Luna, what to build/measure first, in what order, and why, plus an honest statement of what remains genuinely unresolved.
