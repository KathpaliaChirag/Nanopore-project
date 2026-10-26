# Handoff: find a real speedup for Kraken2's 4-way software cache (S2)

You have authority to SSH into Luna and run/build/patch things yourself. Do not ask
permission for each command — investigate, experiment, and report back what is real.

## Who is asking, and why this file exists

Chirag Kathpalia (CK), working under Prof. Kolin Paul, is building a thesis around a
hardware-aware adaptive k-mer cache for Kraken2. Today's session found that the
current 4-way cache build is **slower** than no cache at all, and traced it to a
specific, already-partially-diagnosed bug rather than a fundamental flaw in the
4-way design. This file is the full context so a fresh session can pick this up with
zero back-and-forth.

## Access

```
ssh -i ~/.ssh/luna_claude student@luna.cse.iitd.ac.in
```
(the key already exists on this machine at that path). Student account, shared with
one labmate (rohit) - do not touch anything outside `~/chirag_K/`, `~/tools/`,
`~/AccuracyDrift/` (all symlinked from `~` for convenience; real files live under
`~/chirag_K/`).

## What is already real and measured (do not re-derive these)

**S1 (1-minimizer thread-local cache, `kraken2-fresh-bin-s1`, commit `fbf993d`)**
vs **S0 (`kraken2-fresh-bin-s0`, stock v2.17.1)**, 32T, across
`sample_targeted`(50MB)/`standard_8gb`/`standard_16gb`/`pluspf_103gb`(103GB), at
10/1,000/104,918/1,872,777 reads:
- Real win on 50MB/8GB/16GB at the highest read count (17-24% faster)
- Real ~2.6% slower on 103GB at 1.87M reads
- Cache footprint: 16 bytes/thread (one uint64_t minimizer + one taxid_t
  taxon; taxid_t is `typedef uint64_t taxid_t` per `src/kraken2_data.h:27`)

**S2 (4-way set-associative cache) - measured TODAY, and it is currently bad:**
Binary used: `kraken2-fresh-bin-s2-standalone` (built 2026-08-27, from commit
`75f908e` with the nesting bug fixed - i.e. S2Lookup/S2Insert run unconditionally,
not gated inside S1's check). Same 4 DB x 4 read-count sweep, 32T:

| DB | S0 | S2-standalone | ratio |
|---|---|---|---|
| 50MB, 1.87M reads | 15.70s | 130.73s | 8.33x slower |
| 16GB, 1.87M reads | 24.27s | 39.61s | 1.63x slower |
| 103GB, 1.87M reads | 85.71s | 201.10s | 2.35x slower |
| 8GB, 1.87M reads | 19.74s | 20.84s | 1.06x slower |
| all DBs, <=1,000 reads | - | - | roughly flat/noise |

**The slowdown scales with total lookup volume (read count), not database size** -
worst at 1.87M reads on every DB, near-flat at 10-1,000 reads. This is a new
observation from today; do not assume it matches the older "invisible on large DBs"
note below without re-checking, since today's read counts are much larger than what
that note was based on.

## The known, already-diagnosed bug (root cause, most likely)

`s2-standalone`'s hit/miss instrumentation counters are global `std::atomic`
variables, incremented via `fetch_add` on every single lookup from every
thread. This is classic cache-line contention that scales with thread count and
lookup volume. This was already found and documented in an earlier session
(`plan_paper/command_log.md`, search "self-inflicted artifact"): on `sample_targeted`
specifically it was found to cause a ~3x slowdown at 16-96 threads. The fix was
identified but never implemented: "would require thread_local counters
aggregated once at exit, not global atomics."

**First thing to try**: patch the counters to thread_local, or remove them
entirely if a wall-clock-only comparison does not need hit-rate stats for this test.
Re-run the same 4x4 sweep. If the slowdown disappears, that confirms the bug fully
explains today's numbers, and you can move on to measuring the cache's real effect
cleanly.

## The second known issue: s2-standalone has the OLD, broken hash

Built 2026-08-27, before the hashmix fix (`a240d60`, 2026-08-30, "S4.0b/c: fix
S2SetIndex's bit-mixing bug"). The old hash badly mismixes minimizers into sets -
verified: only 256/4096 sets actually used, occupancy max/mean 225.42 (i.e. wildly
uneven). The fix (one line - route the minimizer through Kraken2's own
MurmurHash3, already included in `classify.cc`, before masking to pick a set)
took hit rate from 0.4035% to 3.5758% (~8.9x) at the same 4,096-set capacity,
occupancy max/mean down to 3.95. Committed as `safe/S4.0-hashmix`.

**This means s2-standalone's current numbers reflect a cache that is barely
working as a cache at all** (terrible hit distribution) on top of the atomic
contention bug. Two separate real problems stacked on one binary.

## What to actually test, in order

1. **Isolate the atomic-counter fix alone.** Patch s2-standalone's counters to
   thread_local, rebuild, re-run the same 4x4x32T sweep vs S0. This tells you how
   much of today's 8.3x/2.35x slowdowns were pure instrumentation artifact.
2. **Add the hashmix fix on top.** No existing binary combines "standalone wiring +
   hashmix fix + thread_local counters + plain round-robin eviction" - every hashmix
   binary that exists (`kraken2-fresh-bin-s2-pinned-hashmix`,
   `kraken2-fresh-bin-s2-lru-hashmix-4way`, etc.) also changed the eviction policy at
   the same time, so you cannot isolate "hashmix alone" from existing binaries. You
   will likely need to build this combo yourself (a new patch script following the
   pattern of the existing ones in `plan_paper/scripts/` - read `s2_standalone_patch.py`
   and `s4_0c_hash_mix_real_patch.py` on Luna for the exact patterns to combine).
3. **Try the already-built LRU+hashmix variant**, `kraken2-fresh-bin-s2-lru-hashmix-4way`,
   against S0 with the same sweep - this one already has both fixes, just was not
   compared against S0 with this specific 4-DB/4-read-count methodology (only ever
   benchmarked head-to-head against round-robin on standard_8gb/T=1).
4. **Consider prefetching.** `kraken2-src-1way`'s HEAD (`c4e7a0d`, "S5.0:
   software-prefetch batched lookup (-B)") adds a -B batch-prefetch flag on top of
   `safe/S4.0-hashmix`, already verified correctness-safe. Never tested combined with
   S2's cache specifically - could compound with a working cache since prefetch hides
   the hash->Get() latency the cache is trying to avoid altogether.
5. Whatever variant looks best, confirm it with a 3-run interleaved comparison
   (not single-run) before trusting any number - this project's own history has
   multiple single-run sweeps that turned out to be page-cache or noise artifacts.

## Binaries and source already on Luna (do not rebuild if these already do what you need)

```
~/tools/kraken2-fresh-bin-s0                        stock v2.17.1, baseline
~/tools/kraken2-fresh-bin-s1                         1-minimizer thread-local cache (fbf993d)
~/tools/kraken2-fresh-bin-s2                         4-way, NESTED in S1's gate (buggy wiring, avoid)
~/tools/kraken2-fresh-bin-s2-standalone              4-way, wiring fixed, OLD hash, atomic counters (today's test)
~/tools/kraken2-fresh-bin-s2-pinned-hashmix          4-way, hashmix fix + pinning eviction
~/tools/kraken2-fresh-bin-s2-lru-hashmix-4way        4-way, hashmix fix + true LRU eviction  <- try this one
~/tools/kraken2-src-1way                             full git history, HEAD = S5.0 prefetch on safe/S4.0-hashmix
```
Full commit lineage in kraken2-src-1way: fbf993d(S1.1) -> 75f908e(S2 4-way) ->
c2981a7(S3.0 heap-alloc) -> f686002(S3.1/S3.2 sizing) -> b8c1ee0(S3.3) ->
a240d60(S4.0 hashmix fix) -> c4e7a0d(S5.0 prefetch).

## Real DBs and inputs (same ones used throughout this project - stay consistent)

```
~/AccuracyDrift/databases/sample_targeted     50MB
~/AccuracyDrift/databases/standard_8gb        8GB
~/AccuracyDrift/databases/standard_16gb       16GB
~/AccuracyDrift/databases/pluspf_103gb        103GB
~/chirag_K/results/readcount_bench/reads_10.fastq         10 reads
~/chirag_K/results/readcount_bench/reads_1000.fastq       1,000 reads
~/chirag_K/results/basecalling/reads_hac.fastq             104,918 reads
~/chirag_K/results/per_pod5_fastq/pod5_*.fastq (all 16, combined)   1,872,777 reads
```

## Command pattern for a sweep cell (what today's runs used)

```
/usr/bin/time -f "WALLTIME %e" perf stat -e LLC-loads,LLC-load-misses -- \
  <binary path>/kraken2 --db <db path> --threads 32 --output /dev/null <input file(s)>
```

## Rules to follow (this project's established norms - do not break these)

- Real measured data only. Never estimate or interpolate a number and present it
  as measured. If something cannot be measured, say so plainly.
- Report honest nulls. If a fix does not help, or a variant is no better than
  S0, that is a real, valuable finding - write it up as such, do not spin it.
- Flag confounds. If you find another instrumentation artifact, page-cache
  effect, or anything else that could explain a result other than the thing you are
  testing, say so explicitly rather than presenting the number cleanly.
- 3-run interleaved + CV% for anything you would cite as a real finding (single-run
  numbers are fine for quick sanity checks, but say so).
- Never call the adaptive cache work "Patch 4" - CK is intentionally rebuilding this
  from scratch to relearn it; refer to it by its S1/S2/etc. stage names only.
- When done, report back: what you tried, what actually worked (with real numbers),
  what did not, and why - in enough detail that this could become deck slides in the
  same style as the existing S0-vs-S1/--memory-mapping comparison slides already
  in the project (paired bar charts, real data tables, honest caveats stated
  up front, not buried).
