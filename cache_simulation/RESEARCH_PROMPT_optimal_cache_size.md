# Research prompt: is there a software cache SIZE that actually helps kraken2?

## Context (what's already been tested, so this doesn't repeat it)

Every experiment run so far in `cache_simulation/` varied **associativity** (how many
"ways"/slots per set the cache checks per lookup: 1/4/8/16/30-way) while the cache's
**total capacity was held at whatever kraken2's own sizing formula produces by default**
for a given DB. Nobody has yet varied raw cache SIZE (number of entries / bytes) as an
independent variable, holding associativity fixed. That is the open question this
prompt is for.

**Established findings so far (all in `cache_simulation/command_log.md` and
`cache_simulation/charts/`, cycles-based, not wallclock):**

1. **Small DB (50MB, `sample_targeted`)**: software cache (any width, S0-frequency scan
   through 2000 reads) is WORSE than no cache at every read count tested (10 through
   2000 reads) and every associativity (1/4/8/16-way). 4-way is the least-bad width.
   Root cause (confirmed by the hardware-only sweep, item 2 below): almost nothing on
   this DB is ever resolved at any cache level past L1 in the first place (L2/LLC hit
   rates under 2% everywhere) - there's no room for a lookup cache to help when misses
   overwhelmingly go straight to DRAM regardless.

2. **Hardware LLC associativity alone (no software cache)**, same 50MB DB: NULL result
   at every workload size (10-500 reads) - confirms almost nothing reaches the LLC layer
   on this DB, so neither hardware nor software cache organization has much to act on.

3. **Large DBs (8GB/16GB/103GB)**, but only tested at 50 reads (the original "fair
   batch"): software cache (4-way) shows a genuine ~2x speedup over no-cache. This is
   the one regime where the cache has actually won. It has NEVER been tested at larger
   read counts (the currently-running `laptop_sweep` job will get 10/50/100/500 reads on
   8GB/16GB, but still varies associativity at whatever kraken2's DEFAULT size formula
   picks, not size itself).

4. Kraken2's own S2 cache sizing formula (`f=0.25`, clamped to `[4096, 262144]` entries)
   was found in real-hardware testing (Aug 2026, commit `84436dd`) to produce a cache
   with under 2% hit rate "regardless of implementation" at the sizes that formula
   actually picks for realistic thread counts/DB sizes - i.e. the DEFAULT formula may
   already be picking too-small a cache to ever show a large effect, independent of
   associativity.

**The gap:** capacity (cache SIZE) has never been swept independently. It's entirely
possible the formula's default sizing is simply wrong for some DB/workload combos - too
small to capture enough repeat k-mer hits on the big DBs, or (per finding 1) irrelevant
on the small DB no matter how large it gets, because almost nothing repeats there at all.

## The research question

**For a fixed associativity (use 4-way, since every experiment so far found it optimal
or tied-optimal), does varying the SOFTWARE cache's total capacity reveal a size where
real gains appear (or disappear) - and does the answer depend on database size?**

Concretely:
- Is there a cache size on the SMALL (50MB) DB, large enough to actually capture
  meaningful hit-rate, where the cache finally beats no-cache? Or is finding 1 (cache
  always loses on this DB) robust to size - i.e. is the problem structural (too little
  reuse in the access pattern) rather than a sizing problem?
- On the LARGE (8GB+) DBs where cache already wins at the default size, does making the
  cache BIGGER buy more speedup (more capacity -> more hits), or does it plateau/reverse
  past some point (per-lookup comparison overhead scaling faster than hit-rate gains,
  the same mechanism that made 8-way/16-way lose to 4-way in the associativity sweep)?
- Is there a single "best" cache size across DB sizes, or does the optimum shift with
  DB size (i.e. does the cache need to be sized as a FRACTION of the DB, an ABSOLUTE
  entry count, or something else entirely)?

## Suggested methodology

1. **Pick a fixed associativity**: 4-way (established optimal in every associativity
   sweep run so far - see `fig1`-`fig3`, `fig9`-`fig11`).

2. **Sweep cache SIZE directly**, bypassing kraken2's own sizing formula if possible
   (check whether the `-DLINEAR_PROBING`/cache-size compile flags or a runtime override
   exist - see `dorado-kraken-research/CLAUDE.md` and the S2/S3 patch history in
   `[[project_double_hashing_already_implemented_aug2026]]`/`[[project_s3_3_landed...]]`
   memory for how the existing sizing formula is wired in). A sensible sweep: an
   order-of-magnitude ladder (e.g. 4096, 16384, 65536, 262144, 1048576 entries - the
   current formula's own clamp bounds, 4096-262144, plus one point below and one above
   to see if the clamp itself is limiting anything).

3. **Cross this with DB size**: at minimum the 50MB DB (where cache currently loses) and
   one large DB (8GB, where cache currently wins) - ideally also 16GB/103GB if time
   allows, to see if the optimal size scales with DB size or stays constant.

4. **Keep workload size fixed and modest** (50 or 100 reads) for this sweep - the
   associativity/read-count relationship is already characterized (findings 1-3 above),
   so this experiment doesn't need to re-cover that axis; keeping read count small keeps
   each run fast (~3-30 min based on precedent) so the size x DB grid is affordable.

5. **Same metrics/methodology as everything else**: cycles (not wallclock) for the
   real-hardware-equivalent comparison, plus L1/L2/LLC hit rates and unique_cache_lines
   to see WHY a size wins or loses, not just whether it does. Sanity-check every row
   (cycles/instructions should equal reported IPC) before trusting it, per the standing
   practice in `command_log.md`.

## What "gains at all" would look like, concretely

- **On the small DB**: any cache size that beats S0 (no cache) in cycles. If NO size
  does, that's a strong, well-supported negative result (structural, not a sizing bug) -
  worth stating plainly rather than continuing to chase it.
- **On the large DB**: whether bigger-than-default sizes push the existing ~2x speedup
  higher, and where (if anywhere) it plateaus or reverses - i.e. finding the actual
  optimum, not just confirming "cache > no cache" at one arbitrary default size.

## Deliverable

A cycles-based size x DB-size grid (small multiples or a heatmap, matching the existing
`fig1`-`fig13` visual style: grayscale/hatched bars or a clean line/heatmap, cycles as
the metric, explicit caption on which axis is software cache SIZE vs. the associativity
already characterized elsewhere), plus a written verdict on whether an optimal cache
size exists and whether it's DB-size-dependent - directly extending
`cache_simulation/command_log.md`'s existing "To-do" list.
