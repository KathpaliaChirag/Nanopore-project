# Two-Thesis Strategy Debate — 5-Agent, 3-Round Independent Research and Consensus (2026-08-30)

**Process:** 5 agents, independent research then debate, on the full two-thesis strategy — not the narrow S3/S4 technical design already covered in [`plan_paper/s3_s4_debate_report_2026-08-27.md`](https://github.com/KathpaliaChirag/Nanopore-project/blob/main/plan_paper/s3_s4_debate_report_2026-08-27.md). Round 1: five agents independently research the entire current state (every planning doc, both prior debate/verification reports, `command_log.md`, git history) and propose a strategy, with zero cross-visibility. Round 2: each reads all five Round 1 papers, verifies specific disputed claims against primary sources, and revises. Round 3: final locked positions.

> [!NOTE]
> This ran 3 rounds, not the 5 originally requested. After Round 2, all five agents independently recommended stopping — not from fatigue, but because every agent found the same pattern: this project has now had three separate multi-day stretches where planning documents accumulated and no Luna code moved, and the two things still genuinely unresolved (see below) require sir's actual input, not more agent analysis. Given that unanimous, evidence-backed recommendation, the user chose one final round to lock a single consensus position, then stop. That tradeoff — three rounds of real convergence over five rounds risking the exact problem being diagnosed — is itself part of this report's finding.

**The headline correction, caught in Round 1 by all five agents independently:** the exercise was framed assuming "today is 2026-08-27, 17 days to Sept 13." The real date (`git log`, HEAD `9ccc5b7`) is **2026-08-29** at the time Round 1 ran — the debate itself then ran into 2026-08-30. **14 days remain, not 17**, and the three days since the last S3/S4 report produced zero Luna commits — only two more planning documents. This is a live instance of the exact governance-latency pattern flagged below.

---

## 1. Reality check — is finishing both theses at full scope achievable?

**Verdict: No. Full 5/5 independent consensus, re-derived from `git log` timestamps across two rounds, unchanged by any new evidence.**

Track A (the adaptive k-mer cache): S1/S2 done and correctness-verified; S3 and S4 are now fully *designed* (via the S3/S4 debate report) but **zero lines built**. Track B (cell-width + double hashing): **zero commits of any kind** for B1/B1b/B2/B3, confirmed directly via `git log` — not "behind schedule," literally untouched since the cell-width report was published. Applying this project's own established velocity (`verification_report_2026-08-26.md`'s own Q7 math: ~4.8 sub-steps/day of *active* engineering time, but three separate multi-day idle gaps already observed between sessions) to the ~29 remaining mandatory sub-steps across both tracks plus the comparator sweep implies 6 days in a best case that assumes zero new surprises, and realistically 10–20+ calendar days — before write-up or sir's review round even starts. Finishing both theses to the originally-envisioned full scope (through B3's merge) by Sept 13 is not realistic.

---

## 2. Sequencing — the one substantive new idea this exercise produced

**Verdict: B2 (the bitmask cell) does not need B1 (double hashing) to exist first — CONFIRMED at the source-code level, not by analogy.**

Three of five agents independently proposed this in Round 1, reusing `week5plan.md`'s own argument for why B1b doesn't gate B2 (addressing vs. value-encoding are separable design axes) one link further up the chain — B0 vs. B1 is the same separation. Round 2 moved this from "plausible analogy" to "verified fact": reading Kraken2's actual `Get()` source directly (`dorado-kraken-research/docs/reports/kraken2_get_optimizations.md`), probe-index generation (`idx`, `step`, `second_hash()`) and cell-content interpretation (`hashed_key()`, `value()`) are genuinely separate code paths operating on different data. **`second_hash()` already exists as a named, wired-in hook in upstream Kraken2 — hardcoded to `return 1` under the default `-DLINEAR_PROBING` build flag.** B1's actual code change is smaller than any prior estimate assumed: implementing one function, not designing a new probing architecture from scratch.

**A real operational cost this surfaced, previously unscheduled anywhere:** the same source file states plainly that switching `-DLINEAR_PROBING` off "would require rebuilding the DB" — testing B1 on any real database needs a full database rebuild, not just a recompile. This is a concrete instance of the abstract `kraken2-build`-construction-logic risk `verification_report_2026-08-26.md`'s Q6 already flagged, now with a specific, budgetable cost.

**This reframes B2's status entirely.** Meeting 11 (2026-08-19) named the bitmask cell as one of sir's three required items and did **not** name double hashing — only the report's own older future-work list does. Building B2 directly on B0 is not skipping a step; it's building sir's literal, most-recently-stated ask, immediately, with nothing blocking it.

**Why this isn't free — the caveat every agent converged on and insisted travel with the recommendation, not get lost in it:** B2-on-B0's measured false-positive rate will be real but genuinely *weaker* than B2-on-B1's would be, for two compounding, currently-unquantified reasons — not one:
1. **A bit-budget effect.** `key_bits + value_bits` share a fixed-width cell; the cell-width report's own ≈1.3-bit cliff-shift from switching to double hashing would, at fixed cell width, free that much headroom for `value_bits` — exactly what the bitmask needs more of.
2. **A collision-distribution effect.** The bitmask's failure mode is an OR-collision across the panel's presence bits at a shared slot; linear probing's primary clustering can distribute slot occupancy less evenly than double hashing at the same load factor, so the probing scheme affects the OR-collision rate independent of raw `key_bits` width.

**Neither effect has actually been derived for the bitmask's specific OR-collision semantics** — `week4plan.md` line 60 already flags that the original false-positive model was built for a single-taxon cell, never re-derived for a shared bitmask. Report B2-on-B0's number as real and final for this submission if B1 doesn't land, explicitly labeled "measured without double hashing; a narrower or safer cell is plausible but unconfirmed" — not as B2's ceiling performance.

**One more cheap, unverified lead worth a 10-minute check before assuming B2 needs new cell-layout engineering at all:** `dorado-kraken-research/CLAUDE.md`'s M1 finding already shows Kraken2's compact hash cell splitting 26+6 bits on an ESKAPE-scale database — 6 value-bits, which may already be exactly what a 6-bit bitmask needs with zero structural change. Unverified (no agent in this exercise had Luna access), but cheap to check first.

---

## 3. Fresh ideas, per sir's explicit "ask LLMs" invitation

- **Cite, don't build: Elastic Hashing and Funnel Hashing** (Farach-Colton, Krapivin, Kuszmaul, [arXiv:2501.02305](https://arxiv.org/abs/2501.02305), Jan 2025) — independently found by two agents, independently re-verified by three (including a direct fetch of the actual paper, not a secondhand citation). These achieve open-addressing probe bounds better than Yao's 1980 conjecture without reordering — a genuinely stronger theoretical alternative to double hashing, worth one citation strengthening the related-work section, not an implementation target under this timeline.
- **TAXICF** (a 2025 cuckoo-filter-based classifier) as an additional IBF-differentiation citation for B2's related-work paragraph, alongside the already-planned ganon/Raptor/HIBF/Taxor/COBS comparison.
- Two 2025 papers on sample-tailored minimizer libraries (NAR Genomics & Bioinformatics; SKiM, *Bioinformatics*) strengthen the "smaller database" narrative underlying the whole project — citations, not new engineering scope.
- No agent found a real, cheaper substitute for either thesis's core engineering — the honest conclusion is that the two theses as scoped are the right size; the lever available now is sequencing and honest scope-narrowing, not a fundamentally different technical approach.

---

## 4. Risks not yet flagged anywhere in the repo

1. **No Meeting 12 record exists.** Confirmed independently by all five agents via direct read of `dorado-kraken-research/docs/meeting_minutes.md`: the last entry is Meeting 11 (2026-08-19), which itself named 2026-08-26 as "Next meeting." Nothing since. This means **every open question raised in `week5plan.md` and `verification_report_2026-08-26.md` — including whether double hashing is even in scope — has zero recorded resolution from sir**, and this is the *second* occurrence of an identical gap this project's own memory system was created to prevent (Meeting 11's minutes flag an earlier, near-identical 2026-08-12 slip). **This outranks every other item below.** Nothing in this document should be presented to sir as a decision already made — it's a menu, because he hasn't seen or blessed anything produced since Aug 19.
2. **The ESKAPE gap is a permanent ceiling, not a temporary file loss.** `reports/WEEK2_REPORT.md` Part B shows only 4 of the 6 named ESKAPE species ever existed in the underlying genome pull — *E. faecium* and *Enterobacter* were never downloaded, for any tool, due to a genome-download-tool ceiling from the original Aug 10–12 data pull. This is separate from, and precedes, `week5plan.md`'s later finding that two database *files* subsequently vanished from Luna's disk. **Even a perfect file rebuild caps at 4 species.** B2's "6-organism panel" claim needs rescoping to 4, in writing, now — independent of any DB-recovery effort. (One partial silver lining: 4 organisms fits in 4 bits, not 6, slightly loosening the bit-budget coupling in §2.)
3. **The comparator sweep has never touched this summer's actual work.** The only existing four-way comparison (`WEEK2_REPORT.md`, committed 2026-08-19) predates the fresh `v2.17.1` clone and every line of S1–S4 code. Sir's one literal, twice-repeated instruction — "compare against Centrifuge" — currently has zero data behind it from anything built this summer. Whoever re-runs this must also inherit the 4-species ESKAPE scoping independently, or risk silently reintroducing the same overstated claim a second, separate time.
4. **The v2.1.3-vs-v2.17.1 version split** (`week5plan.md`'s open question 5, `verification_report_2026-08-26.md`'s "fix now, today") is still unresolved, days after being flagged as urgent.
5. **No external Sept 13 CFP was found** in three independent web searches — worth asking sir directly, neutrally, rather than assuming the date is either fixed or flexible.

---

## 5. The decision packet — recommended message to sir, verbatim

All five agents converged on sending this **today, asynchronously, before any further Luna time is spent** — not waiting for a live meeting slot, since waiting has already cost multiple days once.

> Your original email named Thesis 2 "Cell-Width Reduction + Double Hashing" — double hashing in the thesis's own title. At Meeting 11 (2026-08-19), the three pieces you named for this specific Sept 13 push were the LLC-adaptive cache, the bitmask cell, and cell-width reduction — double hashing wasn't named, and the minutes flag this as needing your confirmation. We've treated the bitmask cell as buildable now, independent of double hashing (they touch different parts of the hash table — how a slot is found vs. what's stored in it once found). Is double hashing (1) required for this submission, (2) explicit future work, or (3) something we should attempt only if the cache and the bitmask cell land with days to spare?
>
> Also: we haven't been able to confirm whether the 2026-08-26 meeting happened — nothing's recorded. Separately: the ESKAPE panel has only ever had 4 of the 6 named species in the underlying genome data (2 were never downloaded, unrelated to the 2 database files that later went missing from disk) — we're planning to report the bitmask cell against 4 organisms, in writing, unless you'd rather we prioritize rebuilding toward 6. And: is Sept 13 a hard external date, or is there real flexibility if the work needs it?

**Locked interim engineering decision while waiting for an answer: start B2-on-B0 today, unconditionally.** Do not gate it on sir's response — repeating the same governance-latency pattern that already cost this project days once.

---

## 6. Final day-by-day plan (14 days, 2026-08-30 → 2026-09-13)

One converged plan, reconciling all five agents' schedules. Day 0 is async and does not block Day 1.

| Day | Date | Track A (Luna) | Track B | Other |
|---|---|---|---|---|
| 0 | Today, 08-30 (parallel with Day 1) | — | — | Send the decision packet (§5) |
| 1 | 08-30 | P.0/P.1 pre-checks (`ulimit -s`, real per-node LLC via `lscpu -e`) + S3.0 heap-pointer fix; confirm the 262,144-set crash is gone | Tier 1, zero-Luna-cost, starts now regardless of sir's answer: B1.1 (second hash function — reuses the existing `second_hash()` stub) and B1.3 (probe-sequence design). B2.1 (OR-collision FP-formula derivation against B0's existing code) also starts now — pure math, no Luna | — |
| 2 | 08-31 | S3.1 (confirm ~105MB/socket, not 210MB) + S3.2 (reuse-distance trace, also resolves the M5 tension) | B1.2 independence/chi-square test (paper-only) continues | — |
| 3 | 09-01 | S3.3 (pre-touch experiment + fixed-fraction sweep, pick `f` empirically) + S3.4 benchmark vs. S2 | — | — |
| 4 | 09-02 | S4.0 (occupancy/reuse-distance diagnostic) + S4.1 (verify `sizeof(S2Entry)`=24, saturating counter) | — | Standing Wednesday slot — confirm Day 0's answers landed, or escalate again if it slipped a second time |
| 5 | 09-03 | S4.2 (counter-only benchmark) + S4.3 (opportunistic decay design) | — | — |
| 6 | 09-04 | S4.4/S4.5 combined benchmark + correctness diff vs. S2 — **Track A done** | — | — |
| 7 | 09-05 | Buffer — this project has already hit two independent unforeseen crash/slowdown modes building S2 alone; budget for a third | 10-minute check: real ESKAPE DB's actual `key_bits`/`value_bits` split (§2's cheap lead) | — |
| 8 | 09-06 | — | B2.2: bit-layout + set/query, on B0, at 4 organisms (using Day 7's finding if it confirms headroom already exists) | — |
| 9 | 09-07 | — | B2.3: measured FP rate vs. B2.1's derivation, written with the exact caveat from §2. **B2 done — Thesis 2's real number.** If sir confirmed B1 required and days remain, start B1 Tier 2 (B1.2 real-data independence test, B1.4 stress test) now | — |
| 10 | 09-08 | — | B1 Tier 2 continues if started; otherwise idle | Comparator sweep C1–C3 (Centrifuge at minimum, Metabuli/Centrifuger if time remains), against the actual finished build, explicitly carrying the 4-species scoping forward |
| 11 | 09-09 | — | B1.5 benchmark if still running, or explicit future-work write-up if not | C4: comparison table + narrative; version-split spot-check if Day 0 didn't already resolve it |
| 12–13 | 09-10/11 | Write Thesis 1 chapter (S0–S4, real numbers) | Write Thesis 2 chapter (B0+B2 at 4 organisms; B1/B3 framed per sir's Day-0 answer) | — |
| 14 | 09-12 | Polish, consistency pass against the safe-zone ledger; sir's read if the cadence allows | | |
| 15 | 09-13 | — | — | Submit. (B3's merge gets a hard-capped 2-day attempt **only if** every prior row finished early with real spare days — by default, it does not, and ships as named future work) |

---

## Summary table

| # | Question | Verdict | Consensus |
|---|---|---|---|
| 1 | Both theses at full scope by Sept 13? | No | 5/5, re-derived from git history twice |
| 2 | Does B2 need B1 first? | No — confirmed at source-code level | 5/5, with a locked honest-caveat requirement |
| 3 | Any cheaper substitute technique? | None found; cite Elastic/Funnel Hashing, don't build it | 5/5 |
| 4 | Real risks beyond what's already documented | Missing Meeting 12; permanent 4-of-6 ESKAPE ceiling; stale comparator baseline | 5/5, each independently source-verified |
| 5 | What to cut | B3 (future work by default, capped 2-day stretch attempt only); S5, B1b (already pre-authorized) | 5/5 |
| 6 | What to escalate to sir, unresolved by design | Meeting-12 status; double-hashing scope (his email vs. Meeting 11 conflict); ESKAPE rescoping; Sept 13 flexibility | 5/5 — correctly left open, not something further debate can close |

This document is a recommendation, not a decision — the two items in row 6 need sir's actual answer before anything above becomes final. The next real step is sending §5's message and starting Day 1 on Luna, not a further round of debate.
