# Research prompt: is there a software cache SIZE that actually helps kraken2?

## Context (what's already been tested, so this doesn't repeat it)

Every experiment run so far in `cache_simulation/` varied **associativity** (how many
"ways"/slots per set the cache checks per lookup: 1/4/8/16/30-way) while the cache's
**total capacity was held at whatever kraken2's own sizing formula produces by default**
for a given DB. Nobody has yet varied raw cache SIZE (number of entries / bytes) as an
independent variable, holding associativity fixed. That is the open question this
prompt is for.

### Established findings so far (all in `cache_simulation/command_log.md` and
`cache_simulation/charts/`, cycles-based, not wallclock - see that file's own
correction notes on why wallclock is the WRONG metric to trust)

1. **Small DB (50MB, `sample_targeted`)**: software cache (any width, scanned from 10
   through 2000 reads) is WORSE than no cache at every read count tested and every
   associativity (1/4/8/16-way). 4-way is the least-bad width (fig9, fig10, fig11).
   Root cause (confirmed by finding 2): almost nothing on this DB is ever resolved at
   any cache level past L1 in the first place (L2/LLC hit rates under 2% everywhere) -
   there's no room for a lookup cache to help when misses overwhelmingly go straight to
   DRAM regardless of cache organization.

2. **Hardware LLC associativity alone (no software cache), same 50MB DB**: NULL result
   at every workload size (10/50/100/500 reads, fig12, fig13) - <1% cycle spread, no
   trend. Confirms almost nothing reaches the LLC layer on this DB, so neither hardware
   nor software cache organization has much to act on there.

3. **Large DBs (8GB/16GB/103GB), tested at 50 reads (the original "fair batch",
   2026-09-09)**: software cache (4-way) shows a genuine ~2x speedup over no-cache. This
   is the one regime where the cache has actually won.

4. **NEW as of this prompt (2026-09-15, `laptop_sweep` job, first 4 rows, 10 reads on
   the 8GB DB)**: the win is even BIGGER at small read counts than the 50-read fair
   batch found - 1-way and 4-way both hit **3.59x speedup** over no-cache (S0=18.3M
   cycles, cache variants ~5.1M cycles), 8-way 3.45x. This is a stronger and DIFFERENT
   direction from the small-DB result, and it's still using kraken2's DEFAULT cache size
   - not yet a size sweep, just more evidence the large-DB regime is real and worth
   digging into further. Live data at
   `cache_simulation/measurements/laptop_sweep_*.csv` as the job progresses (32 runs
   total, 10/50/100/500 reads x S0/1way/4way/8way x 8GB/16GB, see
   `cache_simulation/scripts/run_laptop_sweep.sh`).

5. Kraken2's own S2 cache sizing formula was previously described (real-hardware
   testing, Aug 2026, commit `84436dd`) as `f=0.25`, clamped to `[4096, 262144]`
   entries, and found to produce under 2% hit rate "regardless of implementation" at the
   sizes that formula picks for realistic thread counts/DB sizes on real hardware
   (different from the Sniper-simulated single-thread runs above, but the same
   underlying sizing code) - i.e. there's prior evidence the DEFAULT formula may already
   be picking too-small a cache to show its full potential effect, independent of
   associativity.

### The gap

Capacity (cache SIZE) has never been swept independently in EITHER the Sniper-simulated
runs above or (per finding 5) conclusively on real hardware. It's entirely possible the
formula's default sizing is simply wrong for some DB/workload combos - too small to
capture enough repeat k-mer hits on the big DBs (where finding 3/4 already show a win -
could a bigger cache win MORE?), or irrelevant on the small DB no matter how large it
gets, because almost nothing repeats there at all (finding 1/2 suggest this, but it's
never been directly tested by varying size).

## Step 0 (do this FIRST, before running anything)

**Locate the actual cache-size sizing code.** A quick check on Luna
(`kraken2-src-baseline` and `kraken2-fresh-bin-s2-lru-noatomics-4way`'s install
directories) found only compiled binaries (`classify`, `kraken2`, etc.) and Perl
scripts - no `.cc`/`.h` source tree was present in either location as of 2026-09-15.
The source used to BUILD these variants (with the sizing formula, wherever it lives)
has to be found before a size sweep can happen - check:
- `dorado-kraken-research/CLAUDE.md` and `dorado-kraken-research/AccuracyDrift/patches.md`
  for the source tree path used in earlier patch work
- Whether the original kraken2 GitHub source (not the pre-built `tools/` binaries) is
  checked out anywhere under `/home/student/chirag_K/` outside the paths already
  searched (`find ... -iname '*.cc'` came back empty for the two variant dirs checked -
  try a broader `find /home/student -iname 'compact_hash.h' -o -iname 'seqreader.h'`
  across the whole home directory, not just `chirag_K/tools/`)
- Whether the formula is a compile-time constant (would need a rebuild per size, like
  the existing `-noatomics-{1,4,8,16,32,64}way` binaries were each a separate build) or
  a runtime flag/env var (much cheaper - one binary, many sizes)

**This determines the whole shape of the experiment**: if size requires a rebuild per
value, budget real build time (rebuilds+install for the existing associativity variants
appear to have taken meaningful setup effort - see `Sep 2/8` timestamps on the existing
`kraken2-fresh-bin-s2-lru-noatomics-*` directories) in addition to the Sniper run time
below. If it's a runtime flag, the size sweep becomes as cheap as the associativity
sweep was (just a new CLI arg or env var per run, same binary).

## The research question

**For a fixed associativity (use 4-way, established optimal or tied-optimal in every
sweep so far), does varying the SOFTWARE cache's total capacity reveal a size where real
gains appear (or disappear) - and does the answer depend on database size?**

Concretely:
- Is there a cache size on the SMALL (50MB) DB, large enough to actually capture
  meaningful hit-rate, where the cache finally beats no-cache? Or is finding 1 (cache
  always loses on this DB) robust to size - i.e. is the problem structural (too little
  reuse in the access pattern) rather than a sizing problem?
- On the LARGE (8GB+) DBs where cache already wins big at the default size (up to 3.59x,
  finding 4), does making the cache BIGGER buy even more speedup (more capacity -> more
  hits), or does it plateau/reverse past some point (per-lookup comparison overhead
  scaling faster than hit-rate gains, the same mechanism that made 8-way/16-way lose to
  4-way in the associativity sweep, fig9)?
- Is there a single "best" cache size across DB sizes, or does the optimum shift with DB
  size (i.e. does the cache need to be sized as a FRACTION of the DB, an ABSOLUTE entry
  count, or something else)?

## Suggested methodology

1. **Complete Step 0 above first.**

2. **Pick a fixed associativity: 4-way** (established optimal in every associativity
   sweep run so far - fig1-fig3, fig9-fig11). Binary already exists if it's a
   compile-time variant:
   `/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way/classify`.

3. **Sweep cache SIZE directly.** A sensible ladder, anchored on the known default
   formula's own clamp bounds (`4096`-`262144` entries, per finding 5) plus one point
   below and one above to see if the clamp itself is limiting anything:
   `2048, 4096, 16384, 65536, 262144, 1048576` entries (roughly a 4x step each time,
   6 sizes).

4. **Cross this with DB size**: at minimum the 50MB DB
   (`/home/student/chirag_K/AccuracyDrift/databases/sample_targeted`, where cache
   currently loses) and the 8GB DB
   (`/home/student/chirag_K/AccuracyDrift/databases/standard_8gb`, where cache currently
   wins big) - ideally also 16GB
   (`/home/student/chirag_K/AccuracyDrift/databases/standard_16gb`) and 103GB
   (`/home/student/chirag_K/AccuracyDrift/databases/pluspf_103gb`) if Step 0 shows size
   is cheap to vary, to see if the optimal size scales with DB size or stays constant.
   That's 6 sizes x 2-4 DBs = 12-24 runs for this axis alone.

5. **Keep workload size fixed and modest** (10 or 50 reads - workload files already
   exist: `cache_simulation/workloads/tiny_10reads.fastq` and `50reads.fastq` locally,
   mirrored on Luna at `~/cache_simulation/workloads/`). The associativity/read-count
   relationship is already characterized (findings 1-4 above); this experiment doesn't
   need to re-cover that axis, and keeping read count small keeps each run fast (~1-4
   min based on the `laptop_sweep` job's own 10-read timings: 52-139s per run) so the
   size x DB grid stays affordable even as a first pass.

6. **Hardware config**: reuse whichever profile is easiest to compare against existing
   data - `luna.cfg` (real Luna Xeon Platinum 8468) ties directly into findings 1-3
   above; `laptop.cfg` (CK's Ryzen 7 5800H, just added 2026-09-15) ties into finding 4.
   Either is a config-only `-c` flag, no rebuild needed for this axis.

7. **Same metrics/methodology as everything else**: cycles (never wallclock - see
   `command_log.md`'s dedicated correction on this) for the real-hardware-equivalent
   comparison, plus L1/L2/LLC hit rates and `unique_cache_lines` to see WHY a size wins
   or loses, not just whether it does. Sanity-check every row (cycles/instructions
   should equal the reported IPC, e.g. `8159.1/11829.2=0.6899 -> 1/0.6899=1.450`, matches
   fig9's 4-way row) before trusting it, per the standing practice in `command_log.md`.
   Follow the same detached-launch + `progress.log`/`live_summary.csv` pattern as
   `run_laptop_sweep.sh`/`run_hw_assoc_sweep.sh` so the job survives SSH disconnects and
   is resumable/inspectable mid-run.

## Hypotheses worth stating explicitly before running (so the result can actually
surprise you)

| Hypothesis | What would confirm it | What would refute it |
|---|---|---|
| H1: small-DB loss is structural, not a sizing problem | Cache loses to S0 at every size tested, including the largest (1M+ entries) | Cache beats S0 at some size, even if that size is impractically large |
| H2: large-DB win grows monotonically with size | Speedup keeps increasing size-over-size on 8GB/16GB DBs | Speedup plateaus or reverses past some size (comparison overhead catches up) |
| H3: optimal size is a fixed fraction of DB size, not an absolute count | The best size on 8GB scales proportionally to the best size on 16GB/103GB | Best size is roughly constant across DB sizes (an absolute-count effect, not fractional) |
| H4: kraken2's current default formula (f=0.25, clamped) is already near-optimal | No size in the sweep meaningfully beats the default | A size noticeably outside the current clamp bounds wins clearly |

## What "gains at all" would look like, concretely

- **On the small DB**: any cache size that beats S0 (no cache) in cycles. If NO size
  does across the full ladder, that's a strong, well-supported negative result
  (structural, not a sizing bug, confirming H1) - worth stating plainly rather than
  continuing to chase it.
- **On the large DB**: whether bigger-than-default sizes push the existing ~2-3.6x
  speedup higher, and where (if anywhere) it plateaus or reverses - i.e. finding the
  actual optimum, not just confirming "cache > no cache" at one arbitrary default size.

## Deliverable

Continuing the existing figure numbering (`fig1`-`fig13` already exist in
`cache_simulation/charts/`, next is `fig14`+): a cycles-based size x DB-size grid (small
multiples or a heatmap, matching the existing visual style - grayscale/hatched bars or a
clean line/heatmap, serif publication font, `pdf.fonttype=42`, cycles as the metric,
explicit caption on which axis is software cache SIZE vs. the associativity already
characterized elsewhere so nobody confuses the two the way earlier charts in this
project had to be corrected for), plus a written verdict on whether an optimal cache
size exists and whether it's DB-size-dependent (confirm/refute H1-H4 above) - directly
extending `cache_simulation/command_log.md`'s existing "To-do" list and logged with the
same why/what/result discipline every other step in that file follows.
