# Verification Report — S1/S2 Adaptive-Cache Work (2026-08-25/26)

**Process:** 5-agent, 3-round independent research-and-debate audit, run per `plan_paper/verification_audit_brief.md`. Round 1: five agents (A–E) independently investigated all 8 questions against the primary sources, with no cross-visibility. Round 2: each agent read all five Round 1 write-ups and explicitly challenged, defended, or revised its own conclusions. Round 3 (this report): consensus synthesis.

**Methodology note / limitation:** Round 2 was interrupted mid-run by an account-wide session rate limit. Agents A, B, D, and E completed full Round 2 challenge/defend passes (preserved in full in the scratch files this report draws from). Agent C's Round 2 pass did not complete — only its Round 1 write-up exists. Where Agent C's Round 1 position was a minority view later contradicted by the other four agents (notably Q1), the coordinating session independently re-verified the disputed primary-source text directly (quoted below) rather than leaving the disagreement unresolved. This report is that verification's synthesis, not a sixth independent pass.

**Standing limitation that bounds every correctness-adjacent verdict below (raised independently by 4 of 5 agents — B, C, D, E):** `plan_paper/command_log.md` contains **no actual source diffs or C++ code** — every code fence in the file is a bash command block, never a diff of `classify.cc`. Verified directly: all 11 fenced blocks in the file are `bash` command listings. The audit brief's own claim that the log has "real diffs/code embedded" is inaccurate. Every verdict touching `S2Entry`/`S2Lookup`/`S2SetIndex`'s actual implementation is therefore bounded by "consistent with the prose description," never "independently verified against the code" — this sandbox has no Luna access and no committed source to check against.

---

## Q1 — Does S1/S2's design match what sir asked for?

**Verdict: CONCERN FOUND** (revised consensus — 4 of 5 agents, with the fifth's original reading directly contradicted by the primary source on independent re-check).

**Reasoning:** `command_log.md` line 200 states S2 was implemented by wrapping "only the `hash->Get()` call **inside the existing** `if (*minimizer_ptr != s1_last_minimizer)` **block**." This is a direct quote, independently re-verified by this report against the file. It means S2's 4-way cache is only ever consulted on lookups that already survived S1's single-slot adjacent-repeat filter — S2 is **nested behind S1's gate**, not a standalone structure sitting directly in front of `hash->Get()` on the full lookup stream.

Agents A and E independently reached this reading in Round 1 from the same line. Agents B and D initially read the same line as "standalone... in front of `Get()`" and revised to CONCERN FOUND in Round 2 after re-checking the source and conceding the misreading. Agent C's Round 1 write-up quoted the first half of the same sentence ("wraps only the `hash->Get()` call site") but dropped the "inside the existing if-block" clause — the operative clause establishing the nesting — and reached CONFIRMED. This report's own direct re-read of line 200 confirms the nesting reading is the textually correct one; Agent C's Round 2 pass (which could have engaged with this challenge) did not complete due to the rate-limit failure.

`planning/week4plan.md`'s own `[!IMPORTANT]` callout (lines 39–40) specifically frames sir's ask as a starting point, "not something to build up to across two steps" — arguably a fair description of what happened at the code-structure level, even though S1 and S2 were separate commits. Agent D adds a real, load-bearing nuance: S1's own measured hit rate is ~0% on the two DBs that anchor the S2.4 "no benefit" conclusion (`standard_8gb`, `pluspf_103gb` — S1.2 showed no measurable benefit there per `command_log.md` line 182), so on those two DBs specifically, S2 is likely receiving nearly the full unfiltered lookup stream regardless of the nesting. The architectural concern is real; its practical bite on the specific "no benefit" result is DB-dependent, per D's analysis — strongest on `sample_targeted` (where S1 does show a real effect), weaker on the two DBs the conclusion mostly rests on.

**Dissent:** Agent C's original CONFIRMED verdict stands as a documented minority position, but it rests on an incomplete quotation of the deciding sentence — not a genuine alternative reading of ambiguous text.

**Recommended action: fix now.** Run one additional binary variant with S1's gate bypassed (S2 alone, against the full lookup stream) using the existing validated 3-run interleaved methodology. Cheap, reuses infrastructure already built. Add one sentence to any eventual paper/report text clarifying S1 ≠ Patch 4 (different mechanism, per Agent C's Q1 finding) to avoid conflation with the earlier project's cache design.

---

## Q2 — Is the S2 correctness argument (decoupling cache hit/miss from stats-counting) sound?

**Verdict: CONCERN FOUND** (substance unanimous across all 5 agents; verdict *label* split roughly 2 CONFIRMED-with-caveat / 2 CONCERN FOUND / 1 partial — this report adopts the more cautious label since the underlying finding is identical either way).

**Reasoning:** All five agents independently re-derived the same structure. The decoupling logic itself — keeping the `s1_last_minimizer` adjacent-check as the sole gate for `minimizer_hit_groups`/`curr_taxon_counts`, using S2's cache only to decide whether `hash->Get()` needs to re-run — is sound *as narrated* and doesn't touch classification-report-visible state on its own. It rests on two unverified preconditions: (1) `Get()` is side-effect-free (reasonable given a static, mmap'd, read-only hash table — asserted, not demonstrated, in the sources), and (2) `S2Lookup`'s tag/key comparison can never alias two different minimizers into a false hit.

Precondition (2) is the load-bearing one, and it cannot be checked from any source available to this audit — no `S2Entry` struct definition or `S2Lookup` comparison code is committed anywhere. Agents C and D independently made the same forward link to Q3: a tag-aliasing bug wouldn't just be a latent risk, it's a candidate *explanation* for the "no benefit" result, since a wrong-but-fast cache hit produces zero LLC-miss or wall-clock signal — indistinguishable from "cache rarely hits" in every metric actually collected. Agent A's arithmetic check (4,194,304 × 4 × 16 = 268,435,456 bytes, confirming the log's own 256MB/thread figure) shows the implied 16 bytes/entry is consistent with storing a full key plus taxon ID rather than a narrow truncated tag — a partial, not dispositive, mitigating data point.

**Recommended action: fix now**, same fix as Q5 below (they resolve together): run one real (non-`/dev/null`) classification output diff between the existing `kraken2-fresh-bin-s0` and `kraken2-fresh-bin-s2` binaries on a small DB.

---

## Q3 — Is "no measurable benefit from S1/S2 at reasonable sizes" a real finding, or could it be a bug?

**Verdict: CANNOT VERIFY** (converged consensus by end of Round 2 — 3 of 5 final positions CANNOT VERIFY, 1 CONCERN FOUND, all agreeing the conclusion is currently unsupportable as stated).

**Reasoning:** Three genuinely distinct, still-open candidate explanations survived Round 2 scrutiny, and no single existing measurement can distinguish between them:

1. **S1-gating starves S2 of traffic** (Q1's finding) — a confound outside the brief's own candidate list (round-robin eviction, small fastq, mundane bug), independently found by Agents A and E, partially softened by Agent D's point that S1 barely fires on the two DBs anchoring the conclusion.
2. **No internal hit/miss instrumentation exists.** Agent C's central finding, independently echoed by Agent D: every "no benefit" conclusion in `command_log.md` rests entirely on *external* proxies (wall-clock, hardware LLC-miss%), never a software-level counter inside `S2Lookup` itself. This means the log cannot currently distinguish "cache legitimately rarely hits" (benign, capacity/locality-limited) from "cache hits at a healthy rate but the win is offset by compare overhead" from "cache never hits due to a logic bug in `S2SetIndex`/`S2Lookup`" — all three look identical in every metric actually collected.
3. **Round-robin eviction at small-but-tested sizes.** Agent B's cross-DB size-sweep data (added wall-clock ~11.5–11.9s, DB-invariant, monotonically worse from 65,536 sets upward) is real evidence *against* "S2 just needs more capacity" — but Agent E's Round 2 challenge holds: those larger-size data points are, by Agent A/B's own Q4 analysis, dominated by the memory-init cliff, so they don't actually test the round-robin/capacity question either way. The only clean, unconfounded data point is 65,536 sets (flat vs. baseline) — one point, not the full sweep.

This project's own prior M5 finding (90.7% k-mer reuse rate, cited in `week4plan.md`) creates a real, unaddressed tension with "zero measured benefit" that `command_log.md` never reconciles — high global reuse can coexist with near-zero cache hit rate if repeats are separated by more distinct intervening minimizers than the cache's capacity, but this was never tested, only inferable.

**Recommended action: fix now.** Add a thread-local hit/miss counter inside `S2Lookup`, printed at process exit (cheapest, most direct — Agent C's proposal). Combine with the Q1 standalone-S2 rerun and, if time allows, one run against a larger fastq than the ~31k-read file used throughout (Agent B's point — all S0/S1/S2 and the size sweep used the smallest available file). These three are complementary, not redundant, and none require new infrastructure.

---

## Q4 — Is the "memory-initialization cliff" diagnosis for the size sweep correct?

**Verdict: CONFIRMED as the leading, well-corroborated hypothesis** — not fully proven, and one agent's dissent usefully refines rather than overturns it.

**Reasoning:** Verified independently: 4,194,304 sets × 4 ways × 16 bytes = 268,435,456 bytes = exactly 256 MB/thread; × 96 threads ≈ 24 GB — the log's arithmetic is correct. Agent B's cross-DB analysis (independently re-verified by Agent A from the raw published artifact) is the strongest evidence: the *added* wall-clock time at the largest size is close to DB-invariant (~11.5–11.9s) across three DBs whose baseline runtimes span 0.6s to 52s — a signature consistent with a fixed per-thread cost, not a workload-scaled effect (TLB pressure or capacity thrashing from actual lookup traffic should scale with each DB's very different access volume, and doesn't). False sharing is structurally ruled out (`thread_local` means no cross-core write contention); NUMA effects are weakened by `numactl --cpunodebind=0 --membind=0` pinning both compute and memory to one node.

Agent A's Round 1 dissent — that a one-time init cost should show as extra wall-clock, not an elevated *steady-state* LLC-miss rate — was resolved in Round 2 by two independent, convergent arguments (Agent D and Agent E reached the same resolution separately): `perf stat`'s miss-rate ratio is aggregated over the *entire* process lifetime, not phase-separated. On the worst-case cell (`sample_targeted`, 96T), the added cost (~11.9s) is ~95% of total wall-clock (baseline classification is only 0.56s) — so the reported 85% aggregate miss rate is overwhelmingly a measurement of the memory-touching phase, not steady-state classification behavior. This does not fully rule out a residual steady-state TLB-pressure contribution (the strongest remaining alternative, per Agents C and E) — Agent A's synthesis, that a DB-size-dependent capacity-displacement effect plausibly contributes on `sample_targeted` specifically (the one DB that fits in LLC at baseline and has a cache-friendly working set the new array can evict) while the fixed per-thread cost dominates uniformly — is a real, unrebutted refinement worth carrying into S3's design, not a competing theory to be voted down.

This project's own prior M3 finding (`dorado-kraken-research/CLAUDE.md` line 145 — page-fault/page-walk handling already dominates LLC misses at baseline on this exact machine) is independent, pre-existing corroboration.

**Single cheapest follow-up experiment (5-of-5 convergent recommendation):** pre-touch/warm the `thread_local` arrays outside the timed region, then re-run the worst-case cell. If the cliff mostly disappears, first-touch cost is confirmed dominant. Combine with adding a `page-faults` counter to the existing `perf stat -e` list (no new binary needed) to directly quantify the fault-handling burst. Both are cheap and complementary.

**Recommended action: defer with reason** — acceptable to treat as the leading hypothesis for S3 planning purposes now, but run the pre-touch experiment before S3's topology-aware sizing formula is finalized, since which mitigation is correct (huge pages / avoid first-touch vs. cap total footprint against LLC-fitting DBs specifically) depends on confirming the two-mechanism picture.

---

## Q5 — Does the correctness-verification gap (never diffing real classification output) matter enough to block S3?

**Verdict: CONCERN FOUND — fix now, not a hard block.** Full 5-of-5 consensus, the strongest agreement of all 8 questions, no genuine dissent to record.

**Reasoning:** `week4plan.md` line 359 (B3.4) already designates output-correctness as a formal gate — just scheduled at the final merge step, not each intermediate step. All five agents independently argued this is too late: every step between now and B3 (S3, S4, B1, B2) is currently validated only by performance parity, never output correctness, so any silent correctness bug (the exact scenario constructed in Q2/Q3) would ride undetected through the rest of the roadmap and surface bundled with whatever else accumulated by B3.4, where it would be far more expensive to isolate.

The fix is nearly free: `kraken2-fresh-bin-s0` and `kraken2-fresh-bin-s2` already exist. One additional run with real `--output`/`--report` (not `/dev/null`) on a small DB, diffed between the two binaries, directly resolves Q2's unverified precondition and helps disambiguate Q3.

Agents C and E both independently refine exactly where the gate should sit: S3's pure *design* sub-steps (S3.1–S3.3 — topology detection, trace capture/synthesis, simulator work) don't touch the lookup/insert code path and don't need to wait. S3.4 (the first new *measured* number built on S2) and S4 (which rewrites S2's eviction logic — another place a bug could hide) should not proceed without this check first.

**Recommended action: fix now.** Sequence with S2's still-outstanding commit (Q8.1) — fix correctness and commit together, before S2 is treated as a citable safe zone.

---

## Q6 — Does switching from v2.1.3 to v2.17.1 create a real problem?

**Verdict: CONCERN FOUND — adequately logged as an open question, but not adequately scoped or resolved. Needs an actual decision today (2026-08-26 is the scheduled meeting date this was flagged for).** Converged to full 5-of-5 agreement by end of Round 2 (three agents revised upward from an initial "adequately captured" reading).

**Reasoning:** `week5plan.md` documents this transparently as a deliberate, informed user choice, and already flags it as open question 5 for today's meeting — this is not an oversight. But two independent extensions, found by different agents from different angles, argue the risk is broader than currently written down:

1. **Scope of what's split.** Per Meeting 11 (`git show bd437be`), cell-width reduction and the adaptive cache are two of the paper's *three* claimed contributions. The version split isn't an internal engineering-hygiene footnote — it's two of three results sections built on non-comparable baselines by construction, inside the same submission.
2. **Scope of what changed.** Agents C and D independently raised the same point without coordination: `week5plan.md`'s risk framing focuses only on the v2.1.4 kseq parser rewrite (an ingestion-path concern). But Thesis 2's actual subject matter — probe length, load factor, false-positive rate — depends on `kraken2-build`'s minimizer-selection and hash-table-construction logic, not the read parser. Across five releases and ~2.5 years, nothing in any source checks whether that logic changed too.

**Recommended action: fix now (today).** Escalate as a decision item, not a re-flagged open question — spot-check a handful of cells on v2.17.1 against the published v2.1.3 numbers before more Track B work builds on the fresh clone. A footnote alone is not enough if the underlying construction logic drifted.

---

## Q7 — Pacing check: is the current rate sustainable against Sept 13?

**Verdict: CONCERN FOUND — current pace is not sustainable as demonstrated, and this is the second consecutive week missing its own explicit self-set target.** Full 5-of-5 consensus throughout both rounds.

**Reasoning:** `week5plan.md` line 18 sets an explicit goal: every S1–S3 (Track A) and B1 (Track B) row in the safe-zone ledger real, pushed, and tagged before today's (2026-08-26) meeting. Actual state: S1 done+tagged (2 sub-steps), S2 implemented+measured but **not committed/tagged** (4 sub-steps), S3 (4 sub-steps) and B1 (5 sub-steps) **zero entries**. Roughly 6 of 15 targeted sub-steps done. This is the second week in a row this exact target was missed — the identical target was set for 2026-08-19 (per `week4plan.md`) and also went unmet.

Agent D's dual burn-rate reconstruction (independently re-verified against commit timestamps by this report) is the sharpest framing: active work time between the two relevant commits is ~30h24m (~1.25 days), not the brief's "~2 full days." Whole-week rate including the 5-day idle gap before work started (Aug 19→24): ~0.86 sub-steps/day, implying 38 more days for the remaining scope. Active-time-only rate: ~4.8 sub-steps/day, implying ~6.9 more days — which would fit the 18 remaining days to Sept 13, *only if no further multi-day idle gap recurs* (one already has, once) and if the remaining steps (S3's simulator, S4's novel eviction design, B1's independence-tested hash pair, B2's from-scratch collision math, B3 explicitly the riskiest step) take no longer per-step than S1/S2 did — optimistic, since S1/S2 reused a near-identical pattern and the remaining steps don't.

**Recommended action: fix now (today).** Given two consecutive missed weekly targets, use today's meeting to actually cut scope rather than re-flag it a third time: cut S5 and B1b, default S3.3 straight to its fixed-fraction-of-LLC fallback (already sanctioned in both weekly plans) rather than attempting the full topology-trace simulator, and resolve the still-open question of whether double hashing (B1) is even a confirmed paper claim — Meeting 11 didn't explicitly name it, only the report's own §5 future-work list does, and Track B currently has zero commits.

---

## Q8 — Anything else representing a real risk to the Sept 13 submission

Convergent findings, corroborated by 2 or more agents independently (elevated confidence) unless noted:

1. **S2 sits uncommitted on a shared Luna account with a live precedent for data loss.** (B, C, D, E independently) The `student` account is shared with at least one labmate; two ESKAPE databases were already lost from it with an unresolved root cause (`week5plan.md` line 12). Per the project's own rule (`week4plan.md` line 155), uncommitted work is not a safe zone. **This should be the very next action, regardless of what else follows from this report.**

2. **The `-M`/`--memory-mapping` flag was never used in any S0/S1/S2 benchmark or the size sweep.** (A, C independently; verified directly by this report — zero occurrences of `-M`/`memory-mapping` anywhere in `command_log.md`) This project's own prior finding records `-M` as a 12–14× effect on large DBs. This does not invalidate the S0-vs-S1-vs-S2 relative comparisons (both sides omit it equally) but is a real fairness risk if any absolute number gets quoted in the paper, or if the week-7 comparator sweep runs Kraken2 without `-M` against other tools' own default I/O strategy. **Resolve before the comparator sweep, not discovered there.**

3. **`planning/week4plan.md`'s own safe-zone ledger is stale.** (D, independently re-verified by E and by this report) Lines 413–416 still show all four S2 sub-steps as `⬜ not started` despite `command_log.md` documenting S2.1–S2.4 as complete. The ledger's stated purpose (line 399) is to be the fast answer to "what's our last known-good state" without digging through the log — right now it would actively mislead anyone, including sir, who trusts it over `command_log.md`.

4. **The brief's "diffs/code embedded" claim about `command_log.md` is false.** (B, C, D, E independently; confirmed directly by this report — see Standing Limitation above.) Already stated as a standing caveat on the whole audit's confidence.

5. **A ~5.5-hour systematic gap between `command_log.md`'s embedded entry timestamps and the git commit timestamps that introduced them.** (E, independently re-verified by B and D, and by this report against `git log --date=iso`) Commits `0753992` (14:00:55), `268e175` (14:09:44), and `bc3dad1` (14:42:02) each predate the event times their own log entries describe by ~5.5 hours, consistently in the same direction. Bounded specifically to the five early entries that carry explicit `HH:MM` headers (Agent D's refinement) — entry *ordering* is internally consistent throughout the log; only literal time-of-day labels in that narrow window are unreliable. No action needed beyond noting that log chronology should be trusted at the ordering level, not the literal clock-time level, when reasoning about sequencing (relevant to Q6/Q7).

6. **The audit brief's own "~13% to ~85–89%" LLC-miss figure is only partially supported.** (C, independently corroborated by D — both directly re-checked; confirmed again by this report) `command_log.md` line 211 states "~13%" to "85%" — the "89%" endpoint appears nowhere in the file itself; it may originate from the external artifact or Luna-only raw data, neither accessible from this sandbox. Treat "89%" as unverified until confirmed from Luna/artifact access.

7. **Two ESKAPE-specific databases are missing** (`eskape_650mb`, `eskape_human_4gb` — already flagged as an open question for sir in `week5plan.md`). Not blocking S1/S2, but directly relevant to B2 (bitmask cell, framed around the ESKAPE panel), and a genuine scheduling risk compounding Q7's pacing concern given no rebuild has started.

8. **Whether double hashing (B1/Track B) is even a confirmed paper claim is unresolved**, and Track B currently has zero commits of any kind — time-competitive with everything else on the Sept 13 timeline (see Q7's recommended action).

---

## Summary table

| Q | Verdict | Consensus strength | Recommended action |
|---|---|---|---|
| 1 | CONCERN FOUND | 4/5, dissent resolved by primary-source re-check | Fix now — standalone-S2 rerun |
| 2 | CONCERN FOUND | 5/5 substance, label varied | Fix now — real-output diff (shared w/ Q5) |
| 3 | CANNOT VERIFY | 4/5 converged by Round 2 | Fix now — hit/miss counter + standalone rerun |
| 4 | CONFIRMED (leading hypothesis) | 4/5, one refining dissent incorporated | Defer with reason — pre-touch experiment before S3 sizing finalized |
| 5 | CONCERN FOUND | 5/5, no dissent | Fix now — cheapest, most decisive item |
| 6 | CONCERN FOUND | 5/5 by Round 2 | Fix now (today) — sir decision needed |
| 7 | CONCERN FOUND | 5/5, unanimous both rounds | Fix now (today) — cut scope at the meeting |
| 8 | 8 items named | Each 2+ agent corroborated except #6/#7 | Mostly cheap/fix-now; see items above |

---

## Overall go / no-go

**Not a clean go to S3's measured sub-steps or S4 as currently positioned. Conditional go: S3's design-only sub-steps (S3.1–S3.3) can proceed in parallel starting now — they don't touch the cache's lookup/insert code path and don't depend on resolving anything below.**

Before S3.4 (the first new measured number built on S2) or S4 (which rewrites S2's eviction logic) proceeds, close this checklist — every item is cheap, reuses existing infrastructure, and none individually costs more than a day:

1. Commit + tag S2 on Luna immediately (Q8.1 — overdue, sitting on a shared account with a data-loss precedent).
2. Add a thread-local hit/miss counter inside `S2Lookup`, printed at exit (Q3).
3. Re-run S2 standalone, bypassing S1's gate, same validated methodology (Q1/Q3).
4. Run one real-output diff between `kraken2-fresh-bin-s0` and `-s2` on a small DB (Q2/Q5).
5. Run the pre-touch/page-faults-counter experiment before finalizing S3's sizing formula (Q4).
6. Fix `week4plan.md`'s stale S2 ledger rows (Q8.3).

And get explicit decisions from sir at today's meeting on:

7. Version-split spot-check vs. footnote for v2.1.3→v2.17.1 (Q6) — including whether `kraken2-build`'s own logic needs checking, not just the kseq parser.
8. Scope cut given two consecutive missed weekly targets (Q7) — cut S5/B1b now, default S3.3 to its fallback.
9. Whether double hashing (B1) is actually a confirmed paper claim (Q8.8).

None of these are individually large, but they compound if carried forward silently — closing them now, before S3's measured work and S4 stack more on top of an unverified S2, is cheaper than discovering a problem at B3.4 against a much larger diff.
