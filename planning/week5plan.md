# Week 5 Plan — Catching Up to Where Week 4 Was Supposed to End

week4plan.md's own gantt calls this week "Track A S4-S5, Track B B1b-B2" — the steps that come *after* the associative cache and the double-hash table are already built and benchmarked. They aren't. This plan covers Track A **S1-S3** and Track B **B1** instead, because that's the work week 4 was supposed to finish and didn't.

> [!WARNING]
> **Reality check.** As of today (2026-08-23), zero lines of Track A or Track B implementation code exist anywhere in this repo — committed or uncommitted. The most recent commit, `bd437be`, is Meeting 11's own minutes entry. Every commit made on 2026-08-19 (Meeting 11 day, the same day sir set the Sept 13 target) either edited `week4plan.md` itself or reorganized unrelated doc files; none touched Track A or Track B. Nothing has been committed at all in the four days since. The safe-zone ledger's own closing line — "by this week's Wednesday, every S1-S3 and B1 row should carry a real commit hash" — set 2026-08-19 as the target and was unmet the day it was written. It is still unmet. So while week4plan.md's gantt has Week 5 depending on "Week 4 leaving S1-S3 and B1 in a measured, mergeable state," that precondition doesn't hold. Week 5 has to pick up the step where week 4 never started, not the step after it.

## What else changed since week4plan.md was written

Three more facts surfaced this week that reshape scope, none of them about pacing:

- **Two of the six benchmark databases are gone.** Only `sample_targeted`, `standard_8gb`, `standard_16gb`, and `pluspf_103gb` still exist on Luna. `eskape_650mb` and `eskape_human_4gb` — the two ESKAPE-specific databases — are both gone; only their build logs remain, and the root cause of the loss is still unresolved. Any benchmark matrix this week draws from the surviving four, not six.
- **The kraken2 source tree isn't a clean baseline.** `~/tools/kraken2-src` — the tree you'd normally start a "clean before" build from — already has all four sub-patches from the earlier optimization patch applied by hand, and its would-be "baseline" sibling is a copy of that same patched tree with all four patches manually reversed (three via file-restore backups, one via manual line-deletion) — stock plus one unrelated debug-line fix, not a silently-still-patched tree, but still not a real fresh checkout: the source was originally fetched as a `v2.1.3` release tarball, not `git clone`d, so there's no `.git` directory and no `git diff`/`git stash` escape hatch either. A genuine clean build for S1 starts from a real `git clone`, in a new directory, not from either existing tree.
- **The bitmask cell needs a differentiation paragraph against Interleaved Bloom Filters.** ganon, Raptor, HIBF, Taxor, and COBS all already do a bit-vector-per-k-mer-across-multiple-bins lookup — conceptually close to what Track B's bitmask cell (B2) is doing. It doesn't kill the novelty claim — their approach is probabilistic and scales to thousands of bins, ours is exact and deliberately small (6 bits, small curated panels) — but a reviewer in this subfield will ask "why not just use an IBF" on sight, so that paragraph needs writing before submission even though B2 itself isn't this week's step.

## This week's goal

Get every S1-S3 (Track A) and B1 (Track B) row in the safe-zone ledger from ⬜ to a real, pushed, tagged commit before the 2026-08-26 meeting — the same target week4plan.md set for 2026-08-19, now four days late.

## Why we're not pre-cutting S5 and B1b this week

One line of reasoning says: cut S5 and B1b now, before week 5 even starts, because the whole roadmap is already tight against Sept 13 and both are stretch goals nobody but us asked for. We disagree, and not as a throwaway — here's the specific case against making that cut now.

First, week4plan.md's own line naming S5/B1b as droppable is written as a contingency, not a default: "if it slips... cut S5's and B1b's sub-steps first." That's a rule for what to do *if* week 5 slips, checked mid-week against real sub-step velocity. We don't have that velocity yet — not one S1-S3 or B1 sub-step has a commit against it. Pre-cutting before a single measured sub-step exists this week isn't applying the contingency, it's skipping the "if" and treating a fallback as the plan.

Second, cutting S5/B1b doesn't fix the actual problem. The same pacing argument for the cut also shows that even a zero-slippage run of the *entire* week4plan.md roadmap — all ten weeks, no blocked steps anywhere — still lands the comparator sweep three days past Sept 13, before write-up or review even starts (see open question 4 below). Trimming six sub-steps out of week 5 doesn't close a gap that big; it just quietly relabels scope without fixing the thing that's actually broken, which is that the roadmap was paced against no deadline and never re-paced after one showed up.

Third — and this is the real disagreement — the risk this week isn't S5 or B1b. It's that week 4 delivered zero of its 15 sub-steps, which means every week after it, not just week 5, is now off the pace week4plan.md assumed. That's a scope-and-schedule conversation that involves sir's own priorities (he's the one who named S4 and B2 as required, S5 and B1b as optional), and he set the Sept 13 target four days ago without seeing a single committed benchmark from either track. Deciding what gets cut before he's seen that data, at the next standing meeting on 2026-08-26 — three days away — forecloses a conversation that should happen with him in the room, not a call this document makes unilaterally on his behalf.

So: this week's ledger targets stay S1-S3 and B1, full stop, same as week4plan.md already said. S5 and B1b are not cut here. If they need cutting, that gets decided 2026-08-26, with real week-5 data on the table and sir in the room — not pre-emptively.

---

## Track A — this week's build order

week4plan.md's own gantt assumed week 5 would be Track A S4-S5. It isn't. Zero Track A commits exist anywhere in this repo since Meeting 11 (2026-08-19) — S1, S2, and S3 are still exactly where week4plan.md left them: `⬜ not started`, `_fill in_` in the safe-zone ledger. **This week's real Track A job is S1, S2, S3 — the same ten sub-steps week4plan.md scheduled for last week, now three days behind before this week even opens.** Nothing below is new scope; it's last week's scope, executed this week.

Build order is still the same strict chain from week4plan.md's own flowchart: S0 (done) → S1 → S2 → S3 → S4 → S5. You cannot skip ahead to S2 without S1 landing (or being explicitly logged "not measured" per its own fallback), and S3 needs S2's associative structure to size against.

### S1 — single-slot cache (2 sub-steps, 🟢 WE'RE ADDING — our own reference point)

Do this first because it's the cheapest possible sanity check on the whole cache-check code path before sir's actual baseline (S2) goes in on top of it.

- **S1.1 (Design).** Add a thread-local key+result slot ahead of the big hash table, with check-then-overwrite logic on every lookup. Before calling this done: verify the slot is genuinely per-thread — a race or a stale cross-thread hit here corrupts every measurement downstream of it, so fix it before S1.2 runs a single benchmark.
- **S1.2 (Measured).** Run the standard profiling command (same `perf stat` + `numactl --cpunodebind=0 --membind=0` + `kraken2 --threads 32` invocation week4plan.md's Step 0 used) against S1.1's build. Log the result next to the freshly re-measured S0 baseline on `v2.17.1` (see "S0 had to be re-measured after all," below — the old 4.405s number was v2.1.3-specific and no longer applies).
  - **If S1 is stuck:** skip straight to S2.1 and log S1 as "not measured" in the ledger. S2 does not depend on S1 landing — this is week4plan.md's own explicit carve-out, not an improvised shortcut.

### S2 — 4-way set-associative (4 sub-steps, 🟡 SIR ASKED — his literal baseline)

This is the one Track A step this week that is not optional. Sir's email names "Baseline 4-way set associative" as item one of Thesis 1 — treat S2 as the step you cannot walk away from, in contrast to S1 above and S3 below, both of which have real skip/fallback paths.

- **S2.1 (Design).** Pick the hash bits that map a k-mer to one of the 4 sets. If the bits cluster k-mers unevenly across sets, re-slice or re-mix the hash now, before benchmarking — not after.
- **S2.2 (Design).** Implement the 4-way compare: check the incoming tag against all 4 ways in the target set, return on match. A false hit or false miss here means the compare logic is misreading a way — fix it via the fallback framework's diagnose step, don't route around it.
- **S2.3 (Design).** Pick a simple interim replacement rule for which way gets evicted on a miss — round-robin is the suggested default. Don't over-invest here: S4 replaces this rule entirely later, so this is a placeholder, not a design worth polishing.
  - **If round-robin proves unstable:** drop to random replacement instead, just to unblock S2.4's benchmark.
- **S2.4 (Measured).** Run the standard profiling command, log the result against both S0 and S1.
  - **This step cannot be skipped or cut** — it's sir's named baseline. If the build itself is blocked, diagnose per the fallback framework (small diff, small search space) rather than working around it.
  - **If it measures worse than S1:** log it anyway. That's expected, not a failure — S3 and S4 need associativity to make sense regardless of whether S2 alone beats S1's simpler reference point.

### S3 — LLC-topology-aware sizing (4 sub-steps, 🟡 SIR ASKED + 🟢 WE'RE ADDING method)

Sir asked for LLC-topology-aware sizing; the trace-driven method for getting there (adapted from Bandana) is ours. Budget more time for S3.3 than the other three sub-steps combined — it's the real cost center here, not the topology detection or trace collection around it.

- **S3.1 (Design).** Query Luna's actual L3 size, associativity, and core-sharing layout — don't just read a flat L3 size and guess a fraction of it.
  - **If fine-grained sharing/associativity data isn't available:** fall back to the flat L3 size the fixed-fraction heuristic already uses (see S3.3's own fallback below).
- **S3.2 (Design).** Capture a real k-mer lookup trace, or synthesize one from the already-measured 90.7% reuse-rate and dominant-species-skew numbers from the existing report.
  - **If a real trace won't fit this week's timeline:** synthesize from those numbers instead — this is the explicitly sanctioned fallback, not a corner cut.
- **S3.3 (Design).** Feed S3.1's topology and S3.2's trace through a Bandana-style simulator: try candidate cache sizes against the trace, pick the one with the best simulated hit rate.
  - **If the simulator won't build or run in time:** skip straight to a fixed-fraction-of-LLC-size heuristic, tag the result `🟢-fallback` explicitly in the ledger, and revisit the real trace-driven method in the week-10 buffer — don't quietly present the fallback number as the real method's result.
- **S3.4 (Measured).** Parameterize the cache with whichever size S3.3 (or its fallback) chose, build, benchmark against S2.
  - **If it measures worse than S2:** log it anyway (same rule as S2.4) — S4 needs a sized cache to build on regardless of which config actually wins on wall-clock.

All ten S1-S3 sub-steps route through the same fallback framework as every other step in this plan: one change on top of the last safe zone, build, benchmark 5x, tag every Measured commit (`git tag safe/S2.4`, not just `safe/S2`), push before starting the next sub-step. Nothing about S1-S3 gets a special process this week — the process is why the ledger tracks 10 separate rows here instead of 3.

### Where S4 actually falls now — and the fallback worth remembering early

S4 (biology-dependent adaptive eviction) is not this week's build. It was never really "week 5's problem" in the first place — week4plan.md's gantt only assumed that because it assumed S1-S3 would already be done by the time week 5 opened. They aren't, so S4 falls wherever S1-S3 actually finish, which is likely to be later than the original week-5-into-week-6 boundary implied.

Worth flagging now anyway, before S4 is live work: **S4's own fallback in week4plan.md already has a named contingency** — "if decayed-importance tracking is unstable, fall back to plain LRU as interim S4, swap effort to Track B (B1/B2) while it's debugged." Two things make this worth keeping in view even while you're still on S1-S3:

1. **This is the fallback framework's own worked example.** Rule 3 (branch off a blocked step before rolling back) uses S4 by name — `parking/S4.1-decay-scoring`, `parking/S4-decayed-importance`. Rule 4 (swap, don't stall) also uses S4 by name — "if Track A's eviction step (S4) is stuck, jump to Track B's bitmask cell (B2)." S4 is the step this plan is most explicitly prepared for going sideways.
2. **A compressed schedule raises the odds that contingency gets used for real.** The more S1-S3 slip this week, the less runway S4 has whenever it does start, which is exactly the condition under which "ship LRU as interim S4 and move on" stops being a hypothetical and becomes the actual call. Knowing the fallback exists now — plain LRU, not a blocked step, swap to B2 while debugging — means that call doesn't have to get re-derived under time pressure later.

Nothing about S4 needs to be built, decided, or even fully re-read this week. This is a one-paragraph flag, not a task.

### S0 had to be re-measured after all — here's why

The original reasoning here was "S0 is done, don't rebuild it" — true as long as S1-S3 stayed on `v2.1.3`, since the existing `*(already on record — 4.405s)*` figure was measured on that exact version. That assumption broke on 2026-08-25: partway through this week's execution, the decision was made to build the fresh clone against **current upstream (`v2.17.1`) instead of `v2.1.3`** (see "Fresh Build + Test Matrix" below for the full reasoning and tradeoff). `v2.1.4` rewrote the FASTA/Q parser (kseq) in the middle of Kraken2's ingestion path, so the 4.405s number cannot be assumed to still hold on `v2.17.1` — it needs re-measuring, not reused.

**What this actually changes:** one extra required step, not a bigger rewrite. Before S1.2 logs its first benchmark, run the exact same standard profiling command from week4plan.md's Step 0 — unchanged invocation, same `sample_targeted` DB, same thread count, same 5-run/CV/CI treatment — against the freshly-built `kraken2-fresh-bin` binary on `v2.17.1`, and log that result as this week's real S0 anchor. Call it out explicitly as re-measured (not the old 4.405s) wherever it's cited, so nobody downstream mistakes it for a v2.1.3 number.

What S1-S3 still reuse from the original S0 unchanged, despite the version switch:
- **The profiling command itself.** Same invocation, same DB, same thread count — the number changes, the method doesn't.
- **The fallback framework, the safe-zone/tag discipline, the 5-run/CV/CI treatment.** None of that is tied to a specific source tree or Kraken2 version.

What genuinely does need a clean slate: **only the source tree the new cache code gets written into**, and only because `~/tools/kraken2-src` already carries an applied optimization patch, including a thread-local k-mer cache installed directly in `classify.cc`. Writing S1's thread-local single-slot cache on top of a tree that already has a different thread-local cache wired into the same hot path would confound the two — any S1/S2/S3 number measured there would reflect old-patch-plus-new-cache, not the new cache alone, breaking the "one change per step" discipline the whole fallback framework depends on.

### Where S1 attaches to the fresh clone

1. **S1's code goes into the fresh clone, not `~/tools/kraken2-src`.** Confirm it's clean (`grep -n "MMK" src/classify.cc` should come back empty), then start S1.1 there.
2. **Pinned to current upstream (`v2.17.1`), not `v2.1.3`.** week5plan.md originally planned to pin v2.1.3 for comparability with the existing 4.405s baseline and cell-width report; that decision was explicitly reversed on 2026-08-25 in favor of building on latest. See "Fresh Build + Test Matrix" below for the exact commands, the full tradeoff, and the consequence (S0 needed re-measuring on the new version).

> [!WARNING]
> The clone itself needs Luna's proxy/tmux setup active first — without it, `git clone` against GitHub hangs rather than failing outright.

---

## Track B — this week's build order

week4plan.md's own gantt names week 5 as "Track B B1b-B2" — it assumes B1 is already sitting in a "measured, mergeable state" by the time week 5 starts. That assumption doesn't hold. Zero Track B code has been committed since Meeting 11. B1's five sub-steps — B1.1 through B1.5 — are still `⬜ not started` in week4plan.md's own safe-zone ledger. So this week's real Track B work is B1, not B1b or B2.

### B1 — double hashing, five action items

B1 replaces Kraken2's linear probing with double hashing: instead of walking forward one slot at a time on a collision, you jump by a second hash function's value, which is what the cell-width report's §5 item 2 predicts will cut probe length `p` from roughly 6 down to roughly 2.5 and shift the false-positive cliff by about 1.3 bits.

1. **Write the second hash function (B1.1, Design).** `h2(key)` has to come from a hash family structurally different from `h1`'s, forced odd/nonzero. If original design stalls, borrow a hash pair from a known-good published double-hashing implementation.
2. **Prove `h1` and `h2` are actually independent, on paper, before either touches real probing code (B1.2, Measured).** Run a correlation/chi-square test over real k-mer keys, before B1.3 — a correlated pair silently collapses double hashing back into linear probing.
3. **Rewrite the probe sequence (B1.3, Design).** Swap the linear-probing stride for `slot = (h1(key) + i*h2(key)) % size`. Gate it behind a compile-time flag so linear probing stays one rebuild away.
4. **Stress-test termination, not just correctness (B1.4, Measured — pass/fail only).** Fill the table to ~95%+ load and confirm every probe sequence terminates and can reach every open slot. Force the table size to stay prime (or power-of-2 with `h2` forced odd).
5. **Run the standard benchmark and check the projection (B1.5, Measured, full 5-run/CV/CI treatment).** Compare against the ≈6→≈2.5 and ≈1.3-bit projections. If the measured shift misses, re-derive the false-positive model from what you actually measured and report the correction as the finding.

### Novelty note — bitmask cell vs. Interleaved Bloom Filters

Not this week's build step — B2 comes after B1 (see "Resolved: B2 builds on B1 directly" below) — but worth flagging now, before the write-up gets written around a gap that may not be as open as week4plan.md assumes. ganon, Raptor, HIBF, Taxor, and COBS already do something shaped like our 6-bit-per-organism bitmask cell: one probe returns a bit vector across many reference bins, not a single taxon ID. If the paper doesn't cite and differentiate against this family, a reviewer will ask "why not just use an IBF" as their first question.

- **IBF/HIBF/ganon/Taxor are probabilistic**, with a false-positive rate that has to be managed and reported. Our bitmask cell is **exact** — inside a Kraken2-style compact hash table cell, no filter false-positive rate to manage.
- **IBF/HIBF are built to scale to thousands of bins.** Our cell is deliberately small — 6 bits, sized for a curated panel of 6 ESKAPE organisms. Different point on the design curve: exactness for a small, known panel vs. probabilistic scaling to a huge one.

State both points as one explicit paragraph in the related-work section, not a passing mention.

### Resolved: B2 builds on B1 directly

week4plan.md's Track B build-order flowchart draws a strict chain: B0 → B1 → B1b → B2 → B3. Read literally, B2 can't start until B1b lands. But the document's own words elsewhere settle this the other way — B1b does not gate B2.

The strongest evidence is the document's own contrast between its two tracks, stated in plain prose right under B1b's sub-step table (week4plan.md, line 340):

> "B1b's fallback never says 'log it and continue' the way S2's does — a worse number here just means cutting it, since nothing downstream depends on it the way S3/S4 depend on S2."

That's not an inference drawn from ambiguous fallback wording — it's the document directly stating that B1b has no downstream dependents, in explicit contrast to Track A's real dependency chain (S2 → S3/S4).

The rest of the evidence holds up around that anchor:

- B1b.3's own fallback: "A worse number doesn't block B2 (unlike S2 blocking S3/S4) — cut B1b under time pressure rather than log-and-continue."
- B2.2's fallback: "If set/query doesn't round-trip, roll back to **B1/B1b's cell**" — naming both as valid bases, which only makes sense if B2 can build directly on B1 when B1b isn't there.
- B2 is explicitly not optional ("report §5 item 3, one of the three things sir asked to see completed"), while B1b is explicitly optional at the whole-plan level.

Underneath the textual case is a clean technical reason this is actually safe: B1b and B2 change different axes of the hash table, not the same one. **B1b changes slot addressing** — which of an entry's 2-4 double-hash candidate slots it lands in, decided at build time by a greedy packer. **B2 changes cell value encoding** — the 6 bits of organism presence/absence stored inside whatever cell an entry already occupies. B2.2's actual task, implementing the bitmask cell's bit layout and set/query logic, is a value-field format decision that doesn't need to consult where an entry was placed to be finalized. The one place a real coupling could hide — B2.1's collision-math derivation depending on load/placement statistics — doesn't hold up either: B2.1's own fallback already treats the derivation as provisional (carry a rough union-bound estimate forward and let benchmarking be the real answer), and B2.3 measures the real false-positive rate against it and reports any gap rather than treating a mismatch as blocking. Addressing and encoding are genuinely separable engineering concerns here, not a technical dependency hiding behind loose fallback text.

**Resolved: B2 builds on B1 directly.** B1b stays sequenced after B2 as an optional enhancement B2 can absorb later if it lands, not a prerequisite. Gating a non-optional, sir-named deliverable behind a stretch goal the plan itself says can be cut without consequence would have been a real risk — this sequencing avoids it.

---

## Fresh Build + Test Matrix

Goal: an honest "before" number from a genuinely clean Kraken2 build, on Luna, before either track's own numbers get compared against anything. `~/tools/kraken2-src` carries all 4 sub-patches from `kraken2_opt_v1.patch`, applied by hand on 2026-08-03, with no `.git`. `~/tools/kraken2-src-baseline` is a reconstruction (all 4 patches manually reversed — stock plus one unrelated debug-line fix), not a fresh checkout either. This section builds and benchmarks a third, distinctly-named tree from scratch.

### Step 1 — Luna network auth (before anything else, including the clone)

```bash
tmux new -s freshbuild
env -u http_proxy -u https_proxy -u HTTP_proxy -u HTTPS_proxy python3 ~/iitd-login.py -d
# enter your IIT Delhi kerberos ID + password when prompted
# detach WITHOUT killing: Ctrl+B, then D

export HTTP_proxy=http://proxy62.iitd.ac.in:3128
export HTTPS_proxy=http://proxy62.iitd.ac.in:3128
export https_proxy=http://proxy62.iitd.ac.in:3128
export http_proxy=http://proxy62.iitd.ac.in:3128

grep -i proxy ~/.bashrc
curl -sI https://github.com
```

### Step 2 — Fresh clone, into a third directory, pinned to current upstream (v2.17.1)

**Original decision (superseded 2026-08-25):** this section originally planned to pin `v2.1.3` for comparability with the existing 4.405s baseline, the cell-width report's 1,728-run sweep, and the 2026-08-03 patch remeasurement — all measured on that version, with `v2.1.4`'s FASTA/Q parser rewrite (kseq) flagged as a real risk to re-baselining. That reasoning was sound and is preserved here for context, but the user explicitly chose to build on current upstream instead, after being shown the tradeoff. **Actual decision: pin `v2.17.1`** (confirmed the real latest tag live via `git tag --sort=-creatordate`, not assumed from prior research).

**Consequence, paid immediately:** S0 needed re-measuring on this version before any S1 number means anything — see "S0 had to be re-measured after all" in the Track A section above. The existing cell-width report and 2026-08-03 patch remeasurement remain v2.1.3-only results; this fresh clone and everything built on it going forward is v2.17.1. Open question 5 below covers whether the paper needs to address this version split explicitly.

```bash
mkdir -p ~/tools
cd ~/tools
git clone https://github.com/DerrickWood/kraken2.git kraken2-src-fresh
cd kraken2-src-fresh
git fetch --tags
git tag --sort=-creatordate | head -5   # confirm the real latest tag live, don't assume
git checkout v2.17.1
git log -1 --format='%H %ci' > ~/tools/kraken2-src-fresh/PROVENANCE.txt
cat ~/tools/kraken2-src-fresh/PROVENANCE.txt

grep -n "MMK" src/classify.cc
# expect: no output. If it matches, this isn't actually a fresh tree — stop and investigate.

./install_kraken2.sh ~/tools/kraken2-fresh-bin

# re-measure S0 on this version before S1.2 runs — same standard profiling command as week4plan.md's Step 0:
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  ~/tools/kraken2-fresh-bin/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 32 --output /dev/null --report /dev/null \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
```

Binary lives at `~/tools/kraken2-fresh-bin/kraken2` — not `~/tools/kraken2/` or `~/tools/kraken2-pg/`.

### Step 3 — Verify DB inventory live, don't trust the docs

```bash
ls -la ~/AccuracyDrift/databases/
```

Expect exactly 4 usable DBs: `sample_targeted` (50 MB), `standard_8gb` (7.6 GB), `standard_16gb` (15 GB), `pluspf_103gb` (103.4 GB). `eskape_650mb`/`eskape_human_4gb` are gone — **flag this as a real risk**: the whole bitmask-cell pitch (Track B / B2) is framed around the ESKAPE panel, and neither ESKAPE-specific database currently exists to test against.

### Step 4 — Verify pod5-derived fastq read counts live, then pick matrix files

```bash
for i in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  f=~/data/basecalled/hac/FBE01990_24778b97_03e50f91_${i}.fastq
  n=$(wc -l < "$f")
  echo "$i $((n/4))"
done | tee ~/fastq_counts_live_hac.txt
```

Docs (pending live re-verification) put smallest = `_15` (~31k reads), largest = `_2` (~155k reads), `_6`/`_8` (~124-126k) as "medium." **Avoid `_10`** (its count suspiciously matches the legacy single-fastq total — likely mis-run). Live count wins over the docs if they disagree.

### Step 5 — Run the test matrix

Fixed: 32 threads + `numactl --cpunodebind=0 --membind=0`, `hac` model. New axis: `-M` (`--memory-mapping`) — every historical measurement in this project ran without it, and on the two largest DBs it's a 78-92% wall-clock difference (12-14x on the largest). Every cell runs twice.

| Fastq size | Source (hac) | `sample_targeted` | `standard_8gb` | `standard_16gb` | `pluspf_103gb` |
|---|---|---|---|---|---|
| Small (~31k reads) | `_15` | run × (`-M` on/off) | run × (`-M` on/off) | run × (`-M` on/off) | run × (`-M` on/off) |
| Medium (~125k reads) | `_6` or `_8` | run × (`-M` on/off) | run × (`-M` on/off) | run × (`-M` on/off) | run × (`-M` on/off) |
| Large (~155k reads) | `_2` | run × (`-M` on/off) | run × (`-M` on/off) | run × (`-M` on/off) | run × (`-M` on/off) |

3 sizes × 4 DBs × 2 `-M` states = 24 configs, 5 runs each = 120 runs. `pluspf_103gb` without `-M` will dominate total wall-clock time.

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  ~/tools/kraken2-fresh-bin/kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads 32 \
  [--memory-mapping] \
  --output /dev/null --report /dev/null \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_<i>.fastq
  # [--memory-mapping] is not literal — include the flag for "-M on" runs, omit it entirely for "-M off"
```

### Don't gate all of Track A/B on the full matrix finishing first

Don't block the start of Track A/B this week on the full 120-run matrix landing first. 24 configs × 5 runs, with `pluspf_103gb`-without-`-M` alone likely running long, is real multi-hour-to-multi-day wall-clock time on a single shared machine, in a week that's already behind. Track A's S1 (single-slot cache scaffolding) is design/interface work — writing the thread-local slot and check-then-overwrite logic touches no compiler and no `perf stat`, and can start today, fully in parallel with the sweep.

The real contention isn't S1's code-writing, and not only S1.2's benchmark, but S1.1's own **build step**. "Where S1 attaches to the fresh clone" already has S1.1 running `install_kraken2.sh` against the fresh clone before S1.2 can benchmark anything — and a multi-file C++ compile is CPU- and memory-bandwidth-hungry for several minutes on a machine whose cores share an LLC and memory controller regardless of which NUMA node the sweep is pinned to. That's exactly the kind of noisy-neighbor load that can perturb the sweep's `cache-misses` / `LLC-loads` / `LLC-load-misses` counters, on the run (`pluspf_103gb`) that's already the multi-hour outlier and the most expensive to redo if contaminated.

**The gate: S1.1's code-writing is ungated — start it today. Only the first `install_kraken2.sh` build (compile) waits on a marker file the sweep itself sets when it finishes, not on a time estimate.**

The sweep's last command, appended to the end of Step 5's matrix run, drops a marker in the home directory once every config has completed:

```bash
# last line of the Step 5 sweep script, after the final config finishes
touch ~/MATRIX_DONE
```

S1.1's build step checks for that marker before invoking the compiler:

```bash
# run this immediately before ./install_kraken2.sh in S1.1 — do NOT compile until it exits
until [ -f ~/MATRIX_DONE ]; do
  echo "$(date): fresh-build matrix still running, waiting on ~/MATRIX_DONE..."
  sleep 60
done
echo "matrix done — safe to build"
```

"The sweep should be done by now" is no longer a judgment call, it's a file that either exists or doesn't. S1.2's benchmark already waits on S1.1's build by construction, so it inherits the same gate for free. If the marker is taking implausibly long to appear, check the sweep's own progress log rather than bypassing the gate.

---

## Risk, fallback, and what Wednesday needs

### This week's fallback rule

Same decision tree as week 4: implement the step's one change on top of the last safe zone → build → if it fails, diagnose against that one change; if the fix needs more, branch off the blocked state, roll back to the last safe-zone tag, mark 🔴 blocked, swap to the next independent step. If it succeeds, benchmark 5x; log honestly either way. A safe zone is a **pushed, tagged** commit.

Rule 4 matters most this week: **blocked steps get swapped, not stalled on.** With S1-S3/B1 the actual starting point, Track A (S1→S2→S3) and Track B (B1) stay independent — if one stalls, swap into the other's next step.

### Open questions for sir at the 2026-08-26 meeting

1. **Is double hashing in scope for this specific paper push?** Meeting 11 named three pieces (LLC-adaptive cache, bitmask cell, cell-width reduction) and did not explicitly name double hashing, even though the report's own §5 does. B1 (double hashing) is still a hard prerequisite for B2 in this plan regardless — but whether B1 itself is a *paper claim* or purely infrastructure for B2 is sir's call.
2. **Does sir know `eskape_650mb` and `eskape_human_4gb` are gone, and does the bitmask cell need them rebuilt to validate against?** The bitmask cell is framed around the ESKAPE panel; if it needs the real ESKAPE DBs rather than the surviving general-purpose ones, that's a multi-hour rebuild that already hit a hard genome-download ceiling once — needs scheduling, not late discovery.
3. **Does the Interleaved Bloom Filter prior art change how the bitmask cell should be scoped or framed in the paper?** The differentiation is defensible but changes the related-work framing and possibly the abstract's novelty claim — sir should see this before a full draft exists.
4. **Does week4plan.md's week 4→10 schedule need explicit re-negotiation now, given the Sept 13 date — and specifically, should S5 (Track A, organism-blocked partitioning) and B1b (Track B, bucket placement) be cut?** Per the rebuttal above, the schedule was paced against "no calendar deadline" and already runs past Sept 13 even without slippage. S5 and B1b are the concrete candidates on the table, not an abstract "does the schedule need help" — week4plan.md's own fallback framework already names them first-to-cut under time pressure ("if it slips... cut S5's and B1b's sub-steps first"), and this week is the first real data point on whether that pressure has actually arrived. This plan isn't recommending the cut — this week's ledger stays S1-S3 and B1 — it's making explicit that these two steps specifically are what's on the table if compression turns out to be needed. Whether to cut S5/B1b, compress elsewhere, or move the target instead is sir's decision.
5. **Does the paper submission need an explicit version-caveat now that the fresh cache/hashing work (v2.17.1) and the already-published cell-width report (v2.1.3) sit on different Kraken2 versions?** The plan originally intended to pin v2.1.3 specifically to avoid this split; that decision was reversed on 2026-08-25 in favor of building on current upstream instead. The gap between the two versions is five releases (v2.1.3 → v2.17.1, three years to nine months) and includes a parser rewrite (v2.1.4, kseq) touching the ingestion path — large enough that a reviewer familiar with Kraken2 could reasonably ask whether the cell-width numbers still hold on the version everything else is measured against. Whether the paper needs a footnote disclosing the split, or whether the cell-width results should be spot-checked against v2.17.1 before Sept 13, is a submission-readiness call for sir to make.

### What Wednesday actually needs to show

Wednesday 2026-08-26 covers Track A S1-S3 and Track B B1 — whatever the ledger shows committed against those rows by meeting time. That's the real starting point this week, not S4-S5 or B1b-B2.

> [!NOTE]
> Wednesday's update reports against the S1-S3/B1 ledger rows — commit hashes where they exist, ⬜/🔴 where they don't. Realistically, expect partial completion, not all 15 sub-steps: S2 (sir's required baseline) and B1 (blocking B2) are the two that matter most if the week runs short, S1 is explicitly skippable via its own fallback, and S3.3 should drop to its fixed-fraction fallback rather than eat the rest of the week chasing the full trace-driven simulator.

### Why this can't be quietly absorbed

Someone could argue: don't raise the missed week-4 window at all, just fold it into this week's plan and catch up quietly. That's the wrong call. Sir set an external hard deadline (Sept 13) at Meeting 11 specifically so the team could plan against it; quietly absorbing a missed *internal* deadline removes exactly the information sir needs to manage that external date. Flagged now, sir has three weeks and real levers — cut scope, adjust the target, redirect effort. Surfacing it in week 8 or 9 leaves none of those levers usable. Transparency now is a cheap, one-conversation cost; a surprise later is not.
