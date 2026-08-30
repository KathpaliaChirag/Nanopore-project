# What we changed — running log

Newest first. Plain words. Every entry says **what** changed, **why**, and
**what it means**.

---

## 2026-08-30 — prefetch results across every batch size 1-32

**What:** Swept `-B` through every value from 1 to 32, three interleaved runs
each (99 runs), recording plain `perf stat` counters for each. Raw files:
`../results/prefetch/perf/` (99 files). Full 33-row table:
`../results/prefetch/TABLE.txt`.

**Measured values** (no comparisons - these are the raw figures):

| -B | clsfd% | elapsed | sd | LLC-loads | LLC-ld-miss | llc% | instructions | IPC | cycles | DRAM/lk | ins/lk | cyc/lk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock | 84.26 | 2.893 | 0.007 | 258,717,057 | 150,734,517 | 58.26 | 157,994,819,090 | 1.13 | 139,495,392,141 | 0.938 | 983.6 | 868.5 |
| 1 | 84.26 | 2.908 | 0.288 | 94,469,202 | 29,837,313 | 31.58 | 185,786,274,993 | 1.21 | 153,284,452,944 | 0.186 | 1156.6 | 954.3 |
| 2 | 84.26 | 2.748 | 0.284 | 88,164,247 | 25,389,678 | 28.80 | 180,823,712,284 | 1.26 | 143,278,819,196 | 0.158 | 1125.8 | 892.0 |
| 3 | 84.26 | 2.657 | 0.280 | 83,867,494 | 23,237,304 | 27.71 | 179,148,955,704 | 1.31 | 137,181,707,867 | 0.145 | 1115.3 | 854.0 |
| 4 | 84.26 | 2.572 | 0.284 | 83,284,261 | 22,863,265 | 27.45 | 178,289,451,484 | 1.35 | 131,984,616,072 | 0.142 | 1110.0 | 821.7 |
| 5 | 84.26 | 2.579 | 0.296 | 80,644,443 | 22,807,542 | 28.28 | 177,822,104,624 | 1.36 | 131,495,215,604 | 0.142 | 1107.1 | 818.6 |
| 6 | 84.26 | 2.684 | 0.083 | 80,800,087 | 22,565,329 | 27.93 | 177,503,796,587 | 1.38 | 128,710,434,851 | 0.140 | 1105.1 | 801.3 |
| 8 | 84.26 | 2.678 | 0.020 | 79,616,559 | 22,255,630 | 27.95 | 177,077,050,548 | 1.41 | 125,638,176,113 | 0.139 | 1102.4 | 782.2 |
| 12 | 84.26 | 2.623 | 0.035 | 80,686,632 | 22,306,938 | 27.65 | 176,632,175,696 | 1.45 | 121,791,935,700 | 0.139 | 1099.7 | 758.2 |
| 16 | 84.26 | 2.612 | 0.047 | 79,592,032 | 22,438,701 | 28.19 | 176,475,057,425 | 1.45 | 121,763,190,952 | 0.140 | 1098.7 | 758.1 |
| 20 | 84.26 | 2.578 | 0.017 | 78,149,542 | 22,492,987 | 28.78 | 176,309,583,824 | 1.48 | 119,343,045,440 | 0.140 | 1097.6 | 743.0 |
| 24 | 84.26 | 2.563 | 0.021 | 80,395,019 | 22,497,725 | 27.98 | 176,221,588,458 | 1.48 | 118,891,378,518 | 0.140 | 1097.1 | 740.2 |
| 28 | 84.26 | 2.566 | 0.025 | 78,196,314 | 22,569,789 | 28.86 | 176,168,238,628 | 1.49 | 118,668,872,564 | 0.141 | 1096.8 | 738.8 |
| 29 | 84.26 | 2.553 | 0.006 | 79,200,878 | 22,592,668 | 28.53 | 176,159,715,697 | 1.49 | 118,222,050,946 | 0.141 | 1096.7 | 736.0 |
| 32 | 84.26 | 2.561 | 0.015 | 80,446,021 | 22,656,315 | 28.16 | 176,122,459,462 | 1.49 | 118,207,438,668 | 0.141 | 1096.5 | 735.9 |

Workload: pod5_2.fastq, 151,591 reads, 499.98 Mbp, 160,625,038 lookups.
Database eskape_32bit_fork (48.8 MB). `-p 16 -g 2 -T 0`. Mean of 3 reps.
`sd` is the standard deviation of elapsed time across those 3 runs.

**What the numbers say:**

1. **The classification result never changes.** `clsfd%` is 84.26 on every row
   including stock. Batching is invisible in the output, as it should be.

2. **Nearly all the memory benefit arrives by a batch of 4.** Memory trips per
   lookup fall 0.938 -> 0.186 at `-B 1`, then 0.142 by `-B 4`, and stay flat
   after that. Going from 4 to 32 changes it by 0.001.

3. **What keeps improving past 4 is IPC, slowly** - 1.35 at `-B 4` up to 1.49 at
   `-B 29`. That is worth roughly another 0.7% of runtime, no more.

4. **The `sd` column is the one to read.** At `-B` 1 to 5 the spread across
   three runs is 0.28-0.30 seconds. From `-B 6` onward it collapses to
   0.006-0.047. Small batches are still waiting on memory and so are at the
   mercy of whatever else the machine is doing; large batches are steady. At
   `-B 29` the spread is 0.006 s - steadier than stock.

   This matters for reading rows 1-5: their timings look good but carry an
   uncertainty forty times larger than the rows below them.

5. **`-B 1` costs about 17% more instructions than stock** (1156.6 vs 983.6 per
   lookup) while doing exactly the same work. That is the price of the buffering
   itself, and every batch size pays it. It is why a batch of one is no faster
   than stock despite already cutting memory trips by 80%.

**Best setting:** `-B 29` at 2.553 s, though anything from 16 to 32 is within
noise of it and all are steady. `-B 4` reaches nearly the same time with far
less buffer, but with a spread wide enough that the figure should not be quoted
on its own.

The curve is flat by 32 (735.9 vs 736.0 cycles per lookup at 29), so raising the
batch limit further is not worth trying.

---

## 2026-08-30 — software prefetch: the first change that actually helps

**What:** Reworked the inner classification loop to look up minimizers in
batches instead of one at a time. New flag `-B NUM` (default 1 = the original
behaviour). Binary: `scratch_lookaside/bin/classify_prefetch`.

The loop used to do: get a minimizer, look it up, wait for memory, repeat. Now
it does two passes — first it scans NUM minimizers, hashes them, and asks the
CPU to start fetching each one's memory *without waiting*; then it goes back and
resolves them in the same order as before. By the time it needs each answer the
memory has usually already arrived.

**Why:** Measured memory-level parallelism was **1.24** outstanding memory
requests where the processor can hold about **12**. Every memory wait was being
paid in full, one after another, because each lookup depended on the previous
one finishing. Prefetching does not remove any memory access — it just starts
them earlier so they overlap.

**Three files changed:**
- `kv_store.h` — one new method, `Prefetch(hc)`
- `compact_hash.h` — implements it (`__builtin_prefetch` on the slot the hash
  lands on), plus `GetWithHash` so the hash is computed once, not twice
- `classify.cc` — the two-pass loop and the `-B` flag

**Results** (pod5_2, 16 threads, mean of 3):

| setting | time | vs stock | memory trips per lookup | IPC |
|---|---|---|---|---|
| stock | 2.700 s | — | 0.942 | 1.10 |
| `-B 1` | 2.922 s | +8.2% | 0.186 | 1.21 |
| `-B 8` | 2.663 s | −1.4% | 0.138 | 1.41 |
| `-B 16` | 2.575 s | −4.6% | 0.139 | 1.46 |
| **`-B 32`** | **2.538 s** | **−6.0%** | 0.141 | **1.49** |

**Correctness: byte-identical to stock** at every batch size, at 1 and 16
threads, on both pod5_15 and pod5_2 — 16 checks, all exact. Unlike the cache
work, there is no accuracy trade here at all.

**Two things worth knowing:**

1. **Memory trips per lookup fell 85%** (0.942 → 0.14). We expected overlapping,
   not removal. The explanation is that the prefetch brings the line in early
   enough that the real lookup finds it already there, so it stops being counted
   as a miss. The work still happens; it has just moved off the critical path.

2. **`-B 1` is 8% slower than stock even though it does the same thing.** That
   is the cost of the restructuring itself: 1,156 instructions per lookup versus
   984 — the buffering, the saved flags, the extra loop. Batching has to earn
   that back before it wins, which is why small batches still lose. Measured
   against the same code path, `-B 1` to `-B 32` is a **13%** improvement; about
   6% of it survives once the overhead is paid.

Timings are also far steadier than stock: `-B 32` gave 2.542 / 2.537 / 2.536
across three runs, where stock swung 2.360-2.879. Less waiting on memory means
less sensitivity to what else the machine is doing.

**Still open:** try a larger `-B` (the gain had not flattened at 32, and the cap
is 64); check whether the instruction overhead can be trimmed; confirm on the
other pod5 files and on the 24-bit database.

---

## 2026-08-30 — simplified to one cache, one policy

**What:** Threw away most of the lookaside code. There is now **one table**, not
three tiers, and **one behaviour**, not four modes. Three flags:

```
-L <MB>    turn the cache on, size in MB (power of two)
-N <ways>  how many slots a minimizer may use (default 4)
-J <n>     admit one miss in n (default 8; 1 admits every miss)
```

Removed: the L1 and L2 tiers, `-Y` and its four learning modes, `-F` (the cache
is always the 4-byte format), `-W` (it wrote files nothing read). Also gave back
`-K`, which is kraken2's own flag for minimizer data in reports — the new code
had taken it over by mistake. Admission moved to `-J`.

**Why:** The L1 and L2 tiers were measured to contribute 0.44% and 1.02% of hits
out of 12.32% — about 12% of the benefit for two extra checks on every miss. And
the four modes were not really four policies: one was on/off, one only existed
because there were three tiers, and the only genuine policy knob (replacement)
was not adjustable at all.

**A bug found while doing this.** The old admission filter did nothing. It was a
table of 4.19 million bits used to remember which minimizers had been seen
before — but there are 42.8 million distinct minimizers, so after about 20
million the table is 99.2% full and reports "seen before" for everything. That
is why the `admit` mode measured the same as plain `learn` (12.32% vs 12.20%):
the filter had been switched off by its own saturation the whole time.

**The replacement policy we chose, and why.** Random, within the set. Reasons,
all from our own measurements:

1. The table is about **43x too small** for the data — 1 million slots against
   42.8 million distinct minimizers. Whatever you throw out was unlikely to be
   needed soon, so being clever about *which* entry to throw out buys very little.
2. **Recency is a weak signal here.** Simulating true LRU on this data gives
   14.97% hits where picking by frequency gives 25.28%. Reads arrive in random
   genome order, so the same minimizer usually reappears millions of lookups
   later — far beyond anything a small table remembers.
3. LRU or LFU need bookkeeping updated on every **hit**. That would turn a table
   all 16 threads only read into one they all write, which is expensive. And the
   4-byte entry is already full (26 bits of fingerprint + 6 bits of value), so
   there is nowhere to put a counter anyway.

**The admission policy, and why it matters more.** 63.4% of distinct minimizers
appear **exactly once** — sequencing errors that never come back. They are 29.9%
of all lookups. Letting them in pushes useful entries out, and no replacement
policy can undo that, because by the time you are choosing what to evict the
junk is already inside. So we only let in one miss out of every `-J`. A
minimizer that appears often gets many chances and almost certainly gets in; one
that appears once usually does not. At the default `-J 8`, something seen once
gets in 12.5% of the time, something seen ten times 74%, something seen a
hundred times essentially always. This costs no memory and cannot saturate the
way the old bit table did.

**What it means:** measured on the big file, every setting is still **7.5% to
9.6% slower** than plain kraken2. Selective admission is better than admitting
everything (`-J 8` +7.50% vs `-J 1` +9.60%) and the ordering matches the
reasoning — but the run-to-run spread on this machine is about twice that gap,
so the difference is suggestive rather than proven.

**Honest limitation:** we deleted `-Z` earlier today, which was the only way to
see the hit rate. So we can measure that one setting is faster than another but
not show *why*. Validating the policy properly needs a throwaway build with a
hit counter.

---

## 2026-08-30 — full audit of the kraken2 tree

**What:** Went through the whole project looking for changes we had not written
down. Wrote `KRAKEN2_CHANGES.md` describing how kraken2 works and every part we
touched. Found and fixed four things.

**What we found:**

1. **A second copy of the cell-size work exists.** `kraken2_laptop/` is a
   separate fork, on an older upstream base (14 May), with its own binaries in
   `kraken2_laptop_bin/`. It implements the *same* five cell widths
   (16/20/24/32/40), accepts the same `--cell-size` values, and has the same
   critical `build_db.h` fix. It differs only in comments and struct layout.
   **`kraken2/src/classify` matches `kraken2_bin/classify` byte for byte**, so
   `kraken2/` is the fork that built everything we measure. The laptop copy is
   used for nothing. Nobody had written this down.

2. **Three documents contained commands that no longer run.** The reproduce
   snippets in `LOOKASIDE_REPORT.md`, `CACHE_TABLE_ANALYSIS.md` and
   `../results/lookaside_sweep/REPORT.md` all used `-A` and `-Z`, which we deleted earlier
   today. Each now carries a note saying so, rather than looking runnable.

3. **`scripts/kraken2_lookaside.patch` is stale.** Confirmed: zero references to
   the runtime-learning work, nine references to the removed `-A`/`-Z`. It is a
   snapshot of an older state, not the live code.

4. **`-W` is confirmed orphaned.** It still writes frequency profile files, but
   nothing reads them any more. Zero readers in the source.

**What it means:** Only three source files are modified for the lookaside work —
`classify.cc`, `compact_hash.h`, `kv_store.h` — and that is now verified by
comparing whole directories, not assumed. The second fork is accounted for. The
project has no undocumented changes left that we can find.

**Still open:** remove `-W`; decide whether to keep `kraken2_laptop/` (50 MB) or
delete it now that we know it is redundant.

---

## 2026-08-30 — removed `-A` (profile) and `-Z` (statistics)

**What:** Deleted both flags from the source completely. 3,000 characters of
code gone; no leftover references. Also deleted the backup patch, as asked, so
this is not reversible from a file — only by rewriting the code.

**Why:** The lookaside now learns at runtime, so it no longer needs a
pre-computed profile handed to it.

**What it means:**
- `-L` now **requires** `-Y`. Without runtime learning the tables would start
  empty and stay empty, so that combination is refused instead of silently
  doing nothing.
- We can no longer measure the **hit rate** — that was `-Z`. Every hit-rate
  number in the reports came from it.
- We can no longer measure the **oracle ceiling** — that was `-A`. That was the
  number showing the best a perfect cache could ever do (29.54%).
- Both were measurement instruments, not features. The results they produced are
  already written down in `LOOKASIDE_REPORT.md` and `../results/lookaside_sweep/REPORT.md`.

**Loose end:** `-W` still exists. It writes a frequency profile — but nothing
reads those files any more, because `-A` is gone. It should probably be removed
too. Not done yet, waiting on a decision.

---

## 2026-08-30 — fixed the `promote` bug, made learning modes combinable

**What:** Two fixes to the runtime-learning code.

1. **`promote` now moves an entry instead of copying it.** It writes the entry
   into the faster tier and then clears the slot it came from.
2. **The three learning options became combinable.** They used to be one
   either/or setting, so you could not have two at once.

**Why:** Copying let one minimizer sit in two tiers at the same time, which
wasted space and made `promote` look worse than it was. And the old either/or
design made `admit` + `promote` together impossible to test, even though that is
an obvious thing to try.

**What it means:** `-Y` now takes a comma list — `-Y learn`, `-Y admit`,
`-Y promote`, `-Y admit,promote`. Five settings instead of four, including the
one that was previously unreachable. That new combination turned out to be the
**worst** (11.25%): admission lets fewer things in, then promotion pushes those
few into tiers too small to hold them, so the two fight each other.

**Also decided:** when a promotion displaces an existing entry, that entry is
**thrown away**, not pushed down a tier. Pushing it down looks tidier but is
wrong — an entry parked in a slot it does not hash to can never be found again
and can still cause a wrong answer.

---

## 2026-08-30 — added runtime learning (`-Y`)

**What:** The lookaside tables can now fill themselves while classifying,
starting completely empty. Three switches: `learn` (add every minimizer we had
to look up), `admit` (only add one we have missed before), `promote` (move an
entry to a faster tier when it gets used).

**Why:** Everything before this used a profile built by counting the answer in
advance — useful for finding the ceiling, impossible to ship. This is the
version that could actually run in production.

**What it means:** Runtime learning reaches about **12%** where the profile
version reached **29.5%** on the same setup — roughly 40% of what perfect
knowledge gives you. Since the profile version already loses to plain kraken2,
the learning version loses by more.

**How it stays safe with 16 threads:** every write is a single 4-byte store that
the CPU does in one go. A reader sees either the old entry or the new one, never
half of each. No locks. If two threads write at once one simply loses, which
costs a future lookup, not a wrong answer. This is also why `-Y` only works with
`-F compact` — a 16-byte `exact` entry cannot be written in one go.

---

## 2026-08-30 — stacked the tiers into a hierarchy

**What:** L1 (4 KB), L2 (256 KB) and L3 (4 MB) can now all be active at once,
checked in order L1 → L2 → L3 → the real hash table. Flag: `-L l1=2,l2=4,l3=8`.

**Why:** To test the original idea properly — small fast table in front of a
bigger slower one, like a real CPU cache.

**What it means:** Measured all 60 combinations. **All 60 are slower than plain
kraken2**, from +3.7% to +28%. The tables do work — up to 26.2% of lookups are
answered without touching main memory — but the extra checking costs more than
the memory it saves. Full numbers in `../results/lookaside_sweep/REPORT.md`.

---

## 2026-08-30 — added set-associativity (`-N`)

**What:** A minimizer can now live in any of N slots instead of exactly one.
`-N 1|2|4|8|16`.

**Why:** With one slot each, two useful minimizers landing on the same slot means
one gets thrown away even when the table is half empty.

**What it means:** It fixes exactly what it was meant to fix — the L3 hit rate
went from 25.1% to 28.5%, nearly the theoretical best of 28.9%. But runtime got
**worse**, because checking 16 slots costs more than the extra hits are worth.
L1 and L2 barely changed, because their problem is being too small, not slot
collisions.

---

## 2026-08-30 — made the tier a runtime flag

**What:** One binary instead of six. `-L l1|l2|l3` picks the cache level.

**Why:** Rebuilding for every size was slow and error-prone.

**What it means:** The flag itself costs about 0.6%, because the table size is
now a variable the CPU reads rather than a constant baked into the code.

---

## 2026-08-30 — first lookaside implementation

**What:** A small table holding minimizer → taxon, checked before the main hash
table. Two entry formats: `exact` (16 bytes, keeps the whole minimizer) and
`compact` (4 bytes, keeps a short fingerprint like kraken2 does).

**Why:** To test the idea that frequently used minimizers could be kept in cache
instead of being fetched from main memory every time.

**What it means:** Best case was about 1.5% faster, which is inside this
machine's measurement noise, so **no speedup was ever proven**. The reason is
that the extra check costs 3–5 cycles on every lookup while only paying off on
the small share that hit.

**A bug worth remembering:** the first version picked the table slot using bits
that overlapped the fingerprint bits. That left only ~12 bits to tell
minimizers apart and gave wrong answers on 9.6% of reads. kraken2's own table
takes the slot from the low bits and the fingerprint from the high bits;
matching that fixed it. **Any table like this must keep the two bit ranges
separate.**

**Cell-size compatibility:** `exact` works with 16/20/24/32-bit databases and
always gives identical results. `compact` is only safe on 32-bit — on 16-bit it
gets 53% of reads wrong, because the fingerprint is only 10 bits there.

---

## 2026-08-30 — added `GetWithHash()` to the hash table

**What:** A second way to look up a key when you have already computed its hash.

**Why:** The lookaside computes the hash to find its slot, and the old `Get()`
computed it again — paying twice for the same work.

**What it means:** No change to results (verified byte-for-byte). It is also the
hook a future prefetching change would need, since prefetching means computing
addresses first and fetching values later.

---

## 2026-08-30 — cleanup

**What:** Deleted 21 GB of per-read output files from `result/`, and the
`standard_16gb` and `standard_8gb` databases (22 GB).

**Why:** The output files were 100% of `result/` by size; everything of value —
reports, perf counters, logs — is 17 MB and was kept. The two databases were
downloads, not local builds, and nothing since June referenced them.

**What it means:** The project went from 63 GB to 20 GB. Every command needed to
regenerate a deleted output file is still in its matching `*_log.txt`. A record
of the two databases is in `archive/deleted_db_manifests.txt`.
