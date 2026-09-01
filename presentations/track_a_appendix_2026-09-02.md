# Track A — Data Appendix

Every number and table behind `track_a_progress_2026-09-02.md`, for reference during Q&A. Minimal prose. Source for each section is `plan_paper/command_log.md` unless noted. All numbers fact-checked against primary sources on 2026-09-01.

---

## S0 — rebaseline (v2.17.1, 3 DB × 5 threads, 1 run/cell — directional, not a final CV-checked number)

| DB | Threads | Elapsed | Cache-miss % | LLC-miss % | IPC |
|---|---|---|---|---|---|
| sample_targeted (50MB) | 1 | 5.110s | 6.92% | 8.26% | 1.98 |
| sample_targeted (50MB) | 16 | 0.556s | 13.66% | 12.21% | 1.85 |
| sample_targeted (50MB) | **32** | **0.576s** | 14.85% | 12.65% | 1.75 |
| sample_targeted (50MB) | 64 | 0.569s | 15.38% | 13.07% | 1.57 |
| sample_targeted (50MB) | 96 | 0.597s | 15.26% | 12.96% | 1.23 |
| standard_8gb (7.6GB) | 1 | 7.208s | 88.85% | 88.22% | 1.82 |
| standard_8gb (7.6GB) | 16 | 4.226s | 92.85% | 90.01% | 1.70 |
| standard_8gb (7.6GB) | 32 | 4.233s | 93.18% | 90.47% | 1.65 |
| standard_8gb (7.6GB) | 64 | 4.259s | 92.59% | 89.68% | 1.52 |
| standard_8gb (7.6GB) | 96 | 4.318s | 92.32% | 89.27% | 1.30 |
| pluspf_103gb (103.4GB) | 1 | 78.459s | 90.18% | 85.52% | 1.14 |
| pluspf_103gb (103.4GB) | 16 | 54.511s | 95.35% | 93.85% | 1.09 |
| pluspf_103gb (103.4GB) | 32 | 51.897s | 96.45% | 95.59% | 1.08 |
| pluspf_103gb (103.4GB) | 64 | 51.814s | 96.43% | 95.55% | 1.07 |
| pluspf_103gb (103.4GB) | 96 | 52.150s | 96.40% | 95.49% | 1.04 |

**32T `sample_targeted` (0.576s) is the anchor number** for all S1–S4 comparisons — the v2.17.1 successor to the old v2.1.3 4.405s figure. 32–64T is the sweet spot on both large DBs; 96T is worse everywhere (IPC drops with thread count past the sweet spot).

## S1 — thread-local extension of Kraken2's existing adjacent-minimizer cache

Controlled, interleaved, 3-run methodology (fixed a page-cache confound in the first naive attempt).

| DB | Result |
|---|---|
| `standard_8gb` | LLC-miss% flat (diffs <0.7pp, no direction), wall-clock within ~2% — noise |
| `pluspf_103gb` | LLC-miss% flat, wall-clock 62.03s (S0) vs 61.95s (S1) at T=1 — 0.1% diff, noise |
| `sample_targeted` | Real 5–13% wall-clock speedup at 16T–96T, but **no** corresponding cache-metric change — real, unexplained, not attributed to caching |

## S2 — 4-way set-associative cache (4,096 sets × 4 ways, ~256KB/thread)

**Initial nested read:** LLC-miss% diffs vs. S0/S1 all within ~0.5pp on `standard_8gb`/`pluspf_103gb` — flat, "no benefit."

**Verification audit (5-agent/3-round, 2026-08-26) — 8 questions, verdicts:**

| Q | Question | Verdict |
|---|---|---|
| Q1 | Nesting bug (S2 wired inside S1's gate) | CONCERN FOUND (4/5) — real, but weak practical bite since S1 fires ~0% on the two DBs the "no benefit" conclusion rests on |
| Q2 | Is the correctness argument sound | CONCERN FOUND (5/5) — sound as narrated, rests on 2 unverified preconditions |
| Q3 | Is "no benefit" real or a bug | CANNOT VERIFY (3/5) — zero internal hit/miss instrumentation existed at the time |
| Q4 | Memory-init cliff diagnosis | CONFIRMED as leading hypothesis — 256MB/thread × 96 ≈ 24GB touched at startup |
| Q5 | Does the missing correctness check block progress | CONCERN FOUND (5/5, no dissent) — strongest consensus of the 8 |
| Q6 | v2.1.3→v2.17.1 version-split risk | CONCERN FOUND (5/5 by round 2) — splits 2 of 3 paper claims on non-comparable baselines; risk broader than previously flagged (never checked `kraken2-build`'s own construction logic, only the parser) |
| Q7 | Pacing | CONCERN FOUND (5/5) — 2nd consecutive week missing its own stated target |
| Q8 | Other risks | 8 items: shared-account data-loss precedent (2 ESKAPE DBs already lost); `-M`/memory-mapping never used in any S0/S1/S2 run (project's own prior finding: 12–14× on large DBs); stale `week4plan.md` ledger; a false "diffs embedded" claim in the audit's own brief; a ~5.5hr timestamp drift in early log entries (ordering reliable, clock labels weren't); the "89%" LLC-miss endpoint was unverified (log only supports ~13%→85%); 2 ESKAPE DBs still missing; whether B1/double-hashing was even a confirmed paper claim |

**Fixes tested on a standalone binary (not merged into the committed tree — see caveats):**
- Nesting removed → changed nothing statistically on `standard_8gb`/`pluspf_103gb`. Real cause = capacity.
- Hit rate, flat across all thread counts: `standard_8gb` **0.403%**, `pluspf_103gb`/`sample_targeted` **0.141%**
- Correctness: real `--output`/`--report` diffed byte-for-byte identical vs. S0, on the actual committed nested tree
- Self-inflicted artifact found: global `std::atomic` hit/miss counters caused ~3× slowdown on `sample_targeted` specifically (cache-line contention) — that DB's counter-run wall-clock numbers are not trustworthy

**Size sweep (2026-08-26, on the pre-S3.0 build — see S3 caveat below):** 4,096 → 65,536 → 1,048,576 → 4,194,304 sets. Flat through 65,536, then a cliff. Worst case: `sample_targeted`/96T/4,194,304 sets — **12.51s vs. 0.56s baseline (22× slower)**, LLC-miss 13%→85%.

**Eviction test (single sanity run, `standard_8gb`, T=1, 4,096 sets):** round-robin 0.4035% vs. pinned ("protect any entry hit once") 0.5050% hits — **+25.2% relative gain**. *Caveat: pinned entry is 24 bytes vs. round-robin's 16 — not a perfectly isolated capacity variable.*

**Full capacity × eviction matrix (T=1, `standard_8gb`):**

| Size | RR hit rate | Pinned hit rate | Pinned's relative gain |
|---|---|---|---|
| 4,096 | 0.4035% | 0.5050% | +25.2% |
| 65,536 | 0.7675% | 0.8346% | +8.7% |
| 262,144 | 1.4229% | 1.4843% | +4.3% |

262,144 sets **segfaults at 16+ threads** (exit 139) — clean at T=1. A different failure mode from the 1,048,576+ slowdown cliff above.

## S3/S4 design debate (5-agent/3-round, 2026-08-27)

| Q | Finding |
|---|---|
| Q1 (TLS crash) | Root cause sharpened: NPTL's `allocate_stack()` computes stack size as `requested − guard_page − static_tls_size`. Heap-pointer fix removes the crash but **not** the separate slowdown cliff — both share a root cause in non-zero sentinel defaults defeating copy-on-write zero-page allocation |
| Q2 (LLC sizing) | **105 MiB/socket confirmed, not 210 MiB** (that's the 2-socket sum). Most load-bearing correction of the exercise. `f` deliberately left open (Round 1 guesses spanned 0.1–1.0, a 12× spread) |
| Q3 (S4 design) | `taxid_t` = `uint64_t`. Original `S2Entry` = **16 bytes, zero padding**. Pinned variant (adds `was_hit`) = **24 bytes** (64B→96B/set, +50%). Real free slack for a saturating counter = 7 bytes, not 3. Prior-art check, 5/5: **none** of kache-hash, MegIS, MetaCache-GPU, GPMeta implement any eviction policy for a k-mer cache |
| Q4 (M5 tension) | 90.7% global reuse (M5) vs. near-zero realized hit rate reframed as a metric-definition mismatch (unbounded-distance vs. bounded-cache-window), not fully resolved on magnitude |
| Q5 (S4 > S3) | Unanimous 5/5, 4 independent argument chains — strongest-corroborated conclusion of the exercise |

## S3 — sizing formula and the two bug fixes

**P.0 pre-check:** `ulimit -s` = 8192 KB (8MB default stack) vs. the crashing array's confirmed 16MB — the array is 2× a thread's entire stack budget. `ulimit -a`: no memory caps on the account, rules out the alternate theory.

**P.1 pre-check:** `lscpu -e` confirms strict 1:1 NUMA-node↔socket mapping, no Sub-NUMA Clustering. `lscpu`: L3 = 210 MiB total (2 instances) = **105 MiB/socket**, confirmed directly.

| Step | Fix | Verified result |
|---|---|---|
| **S3.0** | Static `thread_local` array → heap-allocated `unique_ptr`, lazy per-thread init | Crash-free at 16T (0.511s) / 32T (0.500s) / 96T (0.515s), all classify 25,645/30,378 identically; pre-fix binary segfaulted (exit 139) at all three. Byte-identical output/report vs. S0. Tagged `safe/S3.0` (`c2981a7`) |
| **S3.1/S3.2** | `N_sets(T) = floor_pow2(f × 105MiB ÷ (4 ways × 16B × T))`, `f=0.25` placeholder, clamp `[4096, 262144]` | T=1 → 262,144 sets; T=96 → 4,096 sets. Byte-identical vs. S0 at T=1; crash-free/consistent at 16T (16,384 sets)/32T (8,192 sets)/96T (4,096 sets). Tagged `safe/S3.1-S3.2` (`f686002`) |
| **S3.3** | Non-zero sentinels + `new[]` → zero-valued sentinels + `calloc` (lazy OS zero-pages) | `sizeof(S2Entry)` unchanged at 16 bytes. See forced-size comparison below. Tagged `safe/S3.3` (`b8c1ee0`) |

**S3.3 forced-size comparison** (4,194,304 sets, `sample_targeted`, 96T, interleaved old→new→old→new):

| | Wall-clock | Cache-miss | sys time |
|---|---|---|---|
| OLD (S3.0+S3.1/S3.2, no S3.3) | 1.181s / 1.184s | 41.72% / 43.15% | 4.85s / 5.32s |
| NEW (+S3.3) | 0.609s / 0.619s | 14.69% / 14.75% | 0.75s / 0.97s |

**~2× wall-clock, ~3× cache-miss improvement from S3.3 alone.** Correction to the original framing: the 22×/85%-miss number above was measured on the *pre-S3.0* build (static-TLS array, a separate and worse cost) — S3.0 was the dominant fix; S3.3 is a smaller, real, additional win on top, not an independently-stacking second 22×.

**S3.4 — full benchmark** (3 DB × 6 threads [1/8/16/32/64/96] × 3 binaries [S0 / S2-baseline / S2-final] × 3 interleaved runs): **no measurable wall-clock difference anywhere.** CV mostly <1%, a few cells up to 4.6% — low noise, trustworthy null. Best-tested config anywhere (262,144 sets + pinning) only reached 1.48% hit rate. Formula never asks for the sizes (≥262,144 crash-territory, ≥1,048,576 slowdown-territory) where S3.0/S3.3's bugs lived, at realistic thread counts (32–96T).

## S4 — the hashing bug, the fix, and the reversal

**S4.0 diagnostic** (`standard_8gb`, T=1, 4,096 sets, 3,006,550 lookups, `S2SetIndex` = raw low-bit mask, no mixing):
- Occupancy: min=0, max=165,460, mean=734.02, **max/mean = 225.42**
- Reuse-distance: 54% of all lookups are repeats; **81.3%** of repeats (bucket sums: [1e4,1e5)=341,228 + [1e5,1e6)=978,748 = 1,319,976 of ~1,623,537 total repeats) land 10,000–1,000,000 lookups apart. *Measured on `standard_8gb` at T=1 only — not yet confirmed to generalize to other DBs or thread counts.*

**S4.0b/c fix** (mix minimizer through Kraken2's own MurmurHash3 before masking — one line):

| | Old hash (raw mask) | Fixed hash (MurmurHash3) |
|---|---|---|
| Hit rate, 4,096 sets | 0.4035% | **3.5758%** (8.9×) |
| Occupancy max/mean | 225.42 | 3.95 |

Synthetic pre-check (before touching Luna): 256/4,096 sets used → 4,096/4,096, max/mean 16.06 → 1.84. Real measurement matched the direction. Byte-identical correctness, crash-free/consistent 16T/32T/96T. Tagged `safe/S4.0-hashmix` (`a240d60`).

**Still no wall-clock win:** statistically indistinguishable at T=32/96 on `sample_targeted`/`standard_8gb` (0.4–1.8% diffs, noise). One real secondary signal: `sample_targeted` LLC-load-miss% dropped ~13.2%→~9.2% (~30% relative), but 95,377 additional hits out of ~3M lookups (≈3.2% of the stream) is still under the noise floor for end-to-end time.

**The reversal** (`standard_8gb`, T=1):

| | Old hash | Fixed hash |
|---|---|---|
| Round-robin | 0.4035% | 3.5758% |
| Pinned | 0.5050% (**+25.2%** relative) | 3.4367% (**−3.9%** relative) |

*Caveat: pinned entry is 24B vs. round-robin's 16B — a real confound, doesn't undermine the reversal direction.*

## Track A pivot debate (7 agents + coordinator, 2026-08-30) — summary verdicts

| Q | Verdict | Confidence |
|---|---|---|
| Q1 (eviction, if continued) | No large-scale systems algorithm (ARC/2Q/LRU-K/CLOCK-Pro/TinyLFU sketch) fits at n=4 (7/7). Pseudo-LRU and admission control are the two genuinely new, worth-trying candidates. Reuse-distance ceiling bounds both. | High |
| Q2 (capacity re-sweep) | One bounded re-sweep worth running (fixed hash, raised clamp, T=1/8/16) — cheap, closes a real gap. No wall-clock payoff expected; 32–96T already tested post-fix, came back null. | High |
| Q3 (pivot to prefetch) | 7/7: pivot as an addition to S4, not a replacement, 2–3 day bounded Luna spike. Real number must come from Luna — none of Suthar's 3 numbers (−11.77%/−5.99%/−20.34%) transfer directly (different L3 size, different DB profile, unmerged fork). Porting is a real ~2–3 day merge, not a flag-flip. | High |
| Q4 (pace / Track B) | Track B gets bulk of remaining days; Track A closes engineering after Q2's re-sweep. **Real, unresolved 3-way disagreement** on pace (1–2 days / ~3 days / no forced pivot) and on whether today's evidence licenses overriding the user's standing sequencing instruction. `kraken2_opt_v1.patch` confirmed already applied+banked 2026-08-03 — not an available lever. | Medium — disagreement is the finding |
| Q5 (other) | Stale `CLAUDE.md:151` patch-status claim caught. Hash-mix fix stands alone as a result. `mtp1`'s own lookaside-cache experiment ("the better it works, the slower it runs," 26.2% hit rate, still lost to stock) is a real external check on the whole cache premise. A pre-registered May-2026 go/no-go gate (`reuse_rate > 0.20`) was never checked — measured hit rates top out at 3.58%, an order of magnitude under. A low-confidence provenance flag on 2026-08-30's claimed work volume (~45–55 min raw execution vs. a 3h14m commit window) — no evidence of a problem, cheap to spot-check, not yet done. | Medium-high on facts |

## Two-thesis strategy debate (5 agents, 3 of 5 rounds, 2026-08-30)

- **14 days remaining** as of 8-30 → **~12 days** as of today (2026-09-01), Sept 13 target
- Both theses at full original scope by Sept 13: **not achievable** (5/5)
- **B2 doesn't need B1**, confirmed at source level: `Get()`'s probe-index generation (`idx`, `step`, `second_hash()`) and cell-content interpretation (`hashed_key()`, `value()`) are separate code paths
- **B1's real cost:** `second_hash()` exists as a named hook, **hardcoded to `return 1`** under `-DLINEAR_PROBING` — needs a real function written (smaller than a new architecture, bigger than a flag flip), and testing it needs a **full database rebuild**
- **ESKAPE ceiling: 4 of 6 species**, structural — *E. faecium* and *Enterobacter* were never downloaded, separate from and prior to 2 other files later lost from disk
- **No Meeting 12 record exists** — last logged meeting is Meeting 11 (2026-08-19)
- Comparator sweep (vs. Centrifuge) predates the fresh v2.17.1 clone and all S1–S4 code — stale

## week5plan.md / week6plan.md — plan vs. actual

- **S1/S2:** landed as planned, correctness-verified
- **S3:** did not land in week5's window — actually built ~1 week later (8-30), after an intervening design-only doc (week6plan.md) had to be written first
- **B1 (double hashing):** zero commits during this entire window — planned as a week5 target, never executed
- **The 2026-08-26 meeting** week5plan was built around: no record it happened
- **S3.3** shipped as a different mechanism than week6plan proposed (a real sentinel/calloc bug fix, not the planned pre-touch diagnostic experiment) — same tag, same net effect
- **S4** diverged most: week6plan's S4.1–S4.5 (counter, decay, hot-threshold) assumed the existing hash was sound. An unplanned diagnostic step (S4.0, not in week6plan's table at all) found it wasn't — and that finding reversed the empirical basis the whole planned S4 sequence was built on before S4.1 was ever written

## S5.0 — status

- `plan_paper/scripts/s5_0_prefetch_batch_patch.py` (505 lines) — merges Suthar's prefetch-batching patch with S1's `thread_local` state and S4.0's hash-mixed cache; removes a duplicate `MurmurHash3` call by reusing the prefetch pass's hash for `S2SetIndex`
- `plan_paper/scripts/compare_s5_0_prefetch_sweep.py` — full DB × thread × B-value grid, B=1/4/8/16/32 (matching Suthar's own tested points; B=1 = verified stock-equivalent baseline)
- **No results file exists anywhere in the repo.** Confirmed by direct search (`s5*.txt`, `*prefetch*result*`, `*prefetch*sweep*`) — not yet run on Luna

## Known open caveats (don't present these numbers as more final than they are)

- `f=0.25` in the S3 sizing formula is a placeholder, not empirically tuned
- S2's nesting-inside-S1's-gate is still in the committed tree everything else is built on — tested and shown not to matter for the hit-rate/wall-clock conclusions, but not actually merged out
- The 81% reuse-distance figure and the pinning-confound caveat are both `standard_8gb`/T=1-specific, unconfirmed elsewhere
- Agent E's provenance flag on 2026-08-30's claimed work volume: no evidence of a problem, not yet spot-checked
- `plan_paper/track_a_pivot_debate_2026-08-30.md` is still uncommitted (`git status`, as of today)
