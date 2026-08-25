# Verification Audit Brief — S1/S2 Cache Work, 2026-08-25/26

This file exists for one purpose: brief a fresh, independent multi-agent audit (run via `/goal` from a new chat session, no prior conversation context) on what to verify about the S1/S2 adaptive-cache work done on 2026-08-25/26, and why. The audit's own `/goal` prompt is short and points here — this file carries the actual detail so nothing gets lost to a character limit.

**Read this file first, then verify everything in it against the primary sources it names — don't take this file's summary as ground truth where a primary source exists. This is a self-audit brief, not a trusted conclusion.**

## Primary sources, in the order to read them

1. `dorado-kraken-research/CLAUDE.md` — the original project purpose, sir's email framing "Hardware-aware Adaptive K-mer Cache" as extending a thread-local k-mer cache design, and "4-way set-associative" as the literal required baseline.
2. This session's project memory (auto-loaded for any chat in this project) — especially Meeting 11 (2026-08-19, sets the Sept 13 deadline), the "no Patch 4 reference" instruction (the cache is being rebuilt from scratch, not recovered from old work), and the week5plan.md pipeline history.
3. `planning/week4plan.md` — Track A's S1-S4 sub-step definitions (what S1, S2, S3, S4 are each *supposed* to be) and the safe-zone ledger (current real status).
4. `planning/week5plan.md` — this week's actual execution plan, including the v2.1.3→v2.17.1 version-pin reversal and its stated consequences.
5. `plan_paper/command_log.md` — the full, chronological record of every command actually run, every patch applied (with real diffs/code embedded), every benchmark result, and every finding from 2026-08-25/26. **This is the primary source for what was actually done — read it in full, not skimmed.**
6. `git log` in this repo, and (if the audit has Luna access) `git log`/`git tag` inside `~/tools/kraken2-src-fresh` on Luna — the actual commit history, including tags like `safe/S1.2`, is ground truth for what's really been committed vs. only claimed in the log.

## What was actually done (per command_log.md — verify this summary against the log itself)

- Cloned Kraken2 fresh on Luna, switched from a planned v2.1.3 pin to current upstream v2.17.1 (user's explicit choice after being shown the tradeoff: breaks comparability with the existing 4.405s baseline and the published cell-width report, but gets current upstream).
- Re-measured the S0 baseline on v2.17.1 (a 3-DB × 5-thread sweep, 1 run per cell).
- Implemented S1 (a thread-local single-slot minimizer cache) by promoting Kraken2's existing function-local `last_minimizer`/`last_taxon` adjacent-repeat cache to `thread_local` storage — measured (3-run interleaved, CV-checked) no benefit on real-sized DBs (`standard_8gb`, `pluspf_103gb`), a real speedup only on the tiny `sample_targeted` DB with no corresponding cache-metric change (cause unexplained).
- Implemented S2 (a 4-way set-associative cache, 4,096 sets × 4 ways initially, thread-local) in front of `hash->Get()`, with an explicit design decision to keep the cache-hit/miss decision separate from Kraken2's `minimizer_hit_groups`/`curr_taxon_counts` stats-counting logic (which must stay gated on "different from the immediately preceding minimizer" only — a decision made specifically to avoid changing the classification report's actual output, since those counters feed `--quick-mode`'s early-exit threshold and the report's per-species k-mer counts).
- Measured S2 at 4,096 sets (3-run interleaved vs S0/S1): no measurable benefit — LLC-miss% statistically flat.
- Ran a size sweep (4,096 → 65,536 → 1,048,576 → 4,194,304 sets, all 3 DBs × 5 threads, 3 runs each) and found a catastrophic cliff past ~1M entries — up to 22× slower (`sample_targeted`, 96 threads, 4,194,304 sets: 12.51s vs a 0.56s baseline), LLC-miss rate jumping from ~13% to ~85-89%. Hypothesis: `thread_local` per-thread memory-initialization cost (size × 4 ways × 16 bytes × up to 96 threads — up to ~24GB of freshly-touched memory per run at the largest size) dominates the measurement, not classification behavior.
- **All benchmarking used `--output /dev/null --report /dev/null`** — meaning classification correctness (does S1/S2 produce the same species calls as stock Kraken2?) has NOT been empirically verified, only performance.
- S1's patch is committed and tagged in `kraken2-src-fresh` (`fbf993d`, tag `safe/S1.2`). **S2's patch is applied on Luna but, as of this writing, had not yet been committed/tagged** — check the actual git log/tags on Luna (or this repo's command_log.md for a later entry) to see if that happened before this audit runs.

## Questions to verify — every one needs a specific verdict (CONFIRMED / CONCERN FOUND / CANNOT VERIFY) with reasoning citing the actual file/line, not just a gut read

1. **Does S1/S2's actual design match what sir asked for?** Does promoting Kraken2's existing adjacent-minimizer cache to `thread_local`, then building a 4-way associative structure on top, actually satisfy "Hardware-aware Adaptive K-mer Cache" as sir framed it — or is there a meaningfully different interpretation this misses?
2. **Is the S2 correctness argument (decoupling cache hit/miss from stats-counting) actually sound?** Re-derive it independently rather than checking it merely reads coherently — is there a scenario where this decoupling still changes classification output that wasn't considered?
3. **Is "no measurable benefit from S1/S2 at reasonable sizes" a real finding, or could it be a bug?** Consider: is the round-robin eviction policy plausibly the actual bottleneck, is the test fastq (30k reads, one pod5 file) too small/unrepresentative to show any cache's benefit, or is there a more mundane implementation issue not yet considered?
4. **Is the "memory-initialization cliff" diagnosis for the size sweep correct?** Is `thread_local` zero-init cost the most likely explanation, or is there a more likely alternative (TLB pressure specifically, cache-line false sharing between adjacent sets, NUMA effects, something else)? What single follow-up experiment would most cheaply distinguish between these?
5. **Does the correctness-verification gap (never diffing real classification output against stock Kraken2) matter enough to block moving to S3, or is it acceptable to defer?**
6. **Does switching from v2.1.3 to v2.17.1 create a real problem** given the already-published cell-width report was measured on v2.1.3 — is the "version split" open question (already flagged in week5plan.md for sir) adequately captured, or does it need to be escalated more urgently before more work is built on v2.17.1?
7. **Pacing check against the Sept 13 deadline:** given ~2 full days spent on S1+S2 exploration (including the size sweep), is this pace sustainable for S2's remaining work (commit+tag+correctness-verification), S3, S4, B1-B3, and the comparator sweep — or should scope be flagged for compression now?
8. **Anything else** the audit finds while reading the primary sources that doesn't fit the 7 questions above but represents a real risk to the Sept 13 submission — name it explicitly rather than only answering the assigned questions.

## Process

5 agents, 3 rounds, must reach explicit consensus or explicit documented disagreement — no hand-waving to "probably fine":

- **Round 1:** each of the 5 agents independently investigates ALL 8 items above (not divided by item — independent full passes, so genuine disagreement is visible), citing real files/lines/log entries for every claim. Write findings to a scratch file each.
- **Round 2:** each agent reads all 5 Round 1 write-ups, explicitly challenges any conclusion they disagree with (cite the specific claim and why), and defends or revises their own position in response to others' findings.
- **Round 3:** final round — each agent states, per item, whether the group has reached real consensus or where genuine disagreement remains. A well-reasoned documented split is more useful than false consensus.

## Deliverable

A written verification report at `plan_paper/verification_report_2026-08-26.md` (commit it), structured per item above: verdict, reasoning, dissent if any, concrete recommended action (fix now / defer with reason / no action needed). End with an overall go/no-go: safe to proceed to S3, or must something be fixed first?
