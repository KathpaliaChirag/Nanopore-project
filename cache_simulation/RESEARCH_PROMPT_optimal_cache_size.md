# Multi-agent research brief: is there a software cache SIZE that actually helps kraken2?

**Orchestration instructions for whoever runs this (a coordinating session/agent):**
Launch **5 agents**, run **3 iterations**. Each iteration has **3 phases**, run in this
strict order, and each phase's output feeds the next:

1. **Analyse** - each of the 5 agents independently reads this brief plus the linked
   source files below and produces its own analysis: what the existing data actually
   shows, what's still unknown, and what it would predict for the untested cache-SIZE
   axis. Agents should NOT talk to each other in this phase - independent first takes,
   so five different angles survive into the next phase instead of collapsing into
   premature consensus.
2. **Plan** - each agent, now aware there will be a group discussion, drafts a concrete
   experimental/analytical plan for what THIS iteration should establish (not the whole
   research question at once - one iteration's worth of progress). Plans should name
   exact files, exact commands/configs to touch, and exact numbers this iteration would
   need to produce to move the group forward.
3. **Discuss** - the 5 agents' Analyse+Plan outputs are shared with each other. They
   debate: where do the 5 analyses disagree, which plan (or merged plan) is strongest,
   what did each agent's independent read catch that the others missed. This phase ends
   with an explicit **conclusion for the iteration**: a decision, a finding, or a
   falsified/confirmed hypothesis (see H1-H4 below) - written down, not left implicit.

Carry each iteration's conclusion into the next iteration's Analyse phase as new
context. **Iteration 3's Discuss phase must end in a final, citable verdict** on the
research question below - not "more research needed" as a non-answer, but a real
position: yes there's a beneficial size (and where), or no there isn't (and why, with
evidence), for each DB-size regime tested.

**Scope constraint on Plan and Discuss, every iteration: stay on kraken2 and Sniper,
concretely.** A plan is not "investigate cache sizing further" - it is "build/locate
binary X, run it with config Y against database Z at workload size W, expect metric M to
land in range R, here is why." Every plan must name an actual `run-sniper` invocation
(or say exactly what's blocking one, per Step 0), an actual binary path or a concrete
step to produce one, an actual config file (existing or to be written, following the
`.cfg` overlay pattern already established), and an actual database path. If a plan
can't be turned into a real command against Luna's actual filesystem, it isn't specific
enough yet - send it back to Plan, don't let it reach Discuss as an abstraction.

If the coordinating agent can actually execute commands (SSH to Luna, run Sniper,
regenerate charts) rather than only reason over existing data, iterations 2-3 should
incorporate real new runs, not just re-analysis of what's already logged - see
"Suggested methodology" below for exactly what to run.

---

## Full link index (read these before Analyse phase 1 - don't skip, the whole point
of 5 independent agents is 5 people who actually did the reading, not 5 guesses)

**Repo:** https://github.com/KathpaliaChirag/Nanopore-project (branch `main`)

### The running log of everything done so far, in order, with why/what/result for each step
- `cache_simulation/command_log.md` - https://github.com/KathpaliaChirag/Nanopore-project/blob/main/cache_simulation/command_log.md
  (read this FIRST and FULLY - it contains the debugging history, the wallclock-vs-cycles
  correction, and the DB-size-vs-read-count correction, both of which are easy to get
  wrong if you only skim summaries)

### Every chart produced so far (all in `cache_simulation/charts/`, PNG+PDF each)
| Figure | What it shows | Path |
|---|---|---|
| fig1 | Software cache width vs. wall-clock, 10-read/50MB DB, isolated batch | `cache_simulation/charts/fig1_width_sweep_10reads.png` |
| fig2 | Cycles by cache width, small multiples across 4 DB sizes, 50 reads | `cache_simulation/charts/fig2_cycles_by_db_5variant.png` |
| fig3 | Speedup vs. no-cache by width and DB size (cycles-based) | `cache_simulation/charts/fig3_speedup_vs_nocache.png` |
| fig4 | Memory footprint (unique cache lines) by width and DB size | `cache_simulation/charts/fig4_memory_footprint_by_db.png` |
| fig5 | Speedup + IPC dual-axis | `cache_simulation/charts/fig5_speedup_vs_ipc_dualaxis.png` |
| fig6 | Miss-resolution breakdown (L2/LLC/DRAM), 103GB DB | `cache_simulation/charts/fig6_miss_breakdown_103gb.png` |
| fig7 | Hardware config comparison (Luna/desktop/Orion), 4-way SOFTWARE cache fixed | `cache_simulation/charts/fig7_hardware_comparison.png` |
| fig8 | Sim run-time by read count (measured 10/50/2000, estimated 10K/full) | `cache_simulation/charts/fig8_readcount_time_estimate.png` |
| fig9 | Cycles by SOFTWARE width, 2000-read/50MB DB, all 5 variants | `cache_simulation/charts/fig9_2000reads_cycles_50mb.png` |
| fig10 | 50 vs. 2000 reads on the SAME 50MB DB, cache-hurts result holds at scale | `cache_simulation/charts/fig10_readcount_scaling_same_db.png` |
| fig11 | 2000-read results as a table (all 5 variants) | `cache_simulation/charts/fig11_2000reads_results_table.png` |
| fig12 | Hardware LLC associativity alone (no SW cache) - NULL result, 4 workload sizes | `cache_simulation/charts/fig12_hw_assoc_sweep_null.png` |
| fig13 | Hardware associativity sweep, all 24 runs, full table | `cache_simulation/charts/fig13_hw_assoc_full_table.png` |

### Raw measurement CSVs (ground truth - use these, not just the charts, if doing real analysis)
- `cache_simulation/measurements/final_fair_batch_2026-09-09_5variant_all_db.csv` - the 20-row master dataset (5 SW-cache variants x 4 DB sizes, 50 reads)
- `cache_simulation/measurements/hwsize_comparison_2026-09-09.csv` - desktop/Orion hardware profiles, 50MB+8GB DBs
- `cache_simulation/measurements/associativity_sweep_2026-09-08_summary.csv` - original 10-read width sweep (4/8/16/32/64-way)
- `cache_simulation/measurements/2000reads_live_summary_2026-09-09.csv` - the 2000-read job, all 5 SW-cache variants, 50MB DB
- `cache_simulation/measurements/hw_assoc_sweep_2026-09-14.csv` - hardware-only associativity sweep, 24 rows

### Scripts (both the chart generators AND the actual Luna runners - read the runners to
### see the EXACT commands/binaries/DBs used, don't guess at invocation syntax)
- `cache_simulation/scripts/make_slide_charts.py` - fig1-fig7
- `cache_simulation/scripts/make_readcount_table.py` - fig8
- `cache_simulation/scripts/make_2000reads_charts.py` - fig9, fig10
- `cache_simulation/scripts/make_2000reads_table.py` - fig11
- `cache_simulation/scripts/make_hw_assoc_chart.py` - fig12
- `cache_simulation/scripts/make_hw_assoc_full_table.py` - fig13
- `cache_simulation/scripts/run_hw_assoc_sweep.sh` - the actual Luna shell runner for the hardware-only sweep (real `run-sniper` invocation syntax, real binary/DB paths)
- `cache_simulation/scripts/run_laptop_sweep.sh` - the actual Luna shell runner for the currently-running laptop-hardware sweep (also shows the real invocation pattern, plus the full `BINS`/`DBS`/`FASTQ` path tables)

### Hardware configs (every one is a real, working, already-tested overlay - the pattern
### to follow for anything new)
- `cache_simulation/configs/luna.cfg` - real Luna Xeon Platinum 8468 spec, heavily commented with every derivation/gotcha
- `cache_simulation/configs/desktop.cfg` - AMD Ryzen 5 5600X
- `cache_simulation/configs/orion_sizes.cfg` - Jetson AGX Orin (unverified LLC associativity, flagged)
- `cache_simulation/configs/laptop.cfg` - CK's own Ryzen 7 5800H (added 2026-09-15, real WMI-measured specs)
- `cache_simulation/configs/hw_assoc/*.cfg` - 6 overlays isolating hardware LLC associativity (1/4/8/15/16/30-way), `cache_simulation/configs/hw_assoc/README.md` explains the sizing math (why each associativity's set-count divides evenly)

### Project memory (background on how this fits the wider thesis, methodology
### preferences, prior debate-pipeline outputs to match style/rigor against)
- `[[project_simulator_pivot_sept2026]]` - why Sniper was chosen, the deadline-vs-research framing debate
- `[[project_associativity_case_study_brief_sept2026]]` - the read-only research pass that found noatomics binaries were never benchmarked, prior art matches (skewed-associative, SIMD/SoA)
- `[[project_simd_hypothesis_deferred_sept2026]]` - CK's own sequential-AoS-scan hypothesis, confirmed correct in code, exactly the mechanism behind why 8/16-way lose to 4-way
- `[[project_double_hashing_already_implemented_aug2026]]` and `[[project_s3_3_landed_and_2026_08_26_correction]]` - S2/S3 patch history, closest existing lead on where the cache-sizing code and its formula actually live
- `[[project_s3_4_null_result_aug2026]]` - the REAL-HARDWARE null result (commit `84436dd`) referenced as finding 5 below - full-matrix benchmark, 3 DBs x 6 thread counts x 3 runs, all statistically indistinguishable, "<2% hit rate at these sizes regardless of implementation"
- `[[project_two_thesis_strategy_debate_aug2026]]` and `[[project_s3_s4_debate_report_aug2026]]` - prior 5-agent/3-round debates in THIS project - match their rigor and format (explicit consensus %, explicit corrections found, explicit next-step prioritization) rather than reinventing the debate structure from scratch

---

## Full background (what's already established - read `command_log.md` for the complete
## version; this is a compressed but accurate summary, not a replacement)

1. **Small DB (50MB, `sample_targeted`)**: software cache (any width, scanned from 10
   through 2000 reads) is WORSE than no cache at every read count tested and every
   associativity (1/4/8/16-way). 4-way is the least-bad width (fig9, fig10, fig11).
   Root cause (confirmed by finding 2): almost nothing on this DB is ever resolved at
   any cache level past L1 in the first place (L2/LLC hit rates under 2% everywhere) -
   there's no room for a lookup cache to help when misses overwhelmingly go straight to
   DRAM regardless of cache organization.

2. **Hardware LLC associativity alone (no software cache), same 50MB DB**: NULL result
   at every workload size (10/50/100/500 reads, fig12, fig13) - <1% cycle spread, no
   trend. Confirms almost nothing reaches the LLC layer on this DB.

3. **Large DBs (8GB/16GB/103GB), tested at 50 reads (the original "fair batch",
   2026-09-09)**: software cache (4-way) shows a genuine ~2x speedup over no-cache -
   this is the one regime where the cache has actually won.

4. **NEW as of 2026-09-15 (`laptop_sweep` job, first rows, 10 reads on the 8GB DB)**:
   the win is even BIGGER at small read counts than the 50-read fair batch found -
   1-way and 4-way both hit **3.59x speedup** over no-cache (S0=18.3M cycles, cache
   variants ~5.1M cycles), 8-way 3.45x. Still using kraken2's DEFAULT cache size - not a
   size sweep yet, just more evidence the large-DB regime is real and strong. Live data
   growing at `cache_simulation/measurements/laptop_sweep_*.csv` as the 32-run job
   (10/50/100/500 reads x S0/1way/4way/8way x 8GB/16GB) progresses.

5. Kraken2's own S2 cache sizing formula was previously described (real-hardware
   testing, Aug 2026, commit `84436dd`, see `[[project_s3_4_null_result_aug2026]]`) as
   `f=0.25`, clamped to `[4096, 262144]` entries, and found to produce under 2% hit rate
   "regardless of implementation" at the sizes that formula picks for realistic thread
   counts/DB sizes on real hardware (a different experimental setup from the
   single-thread Sniper runs above, but the same underlying sizing code) - i.e. there's
   prior evidence the DEFAULT formula may already be picking too-small a cache to show
   its full potential effect, independent of associativity.

### The gap

Capacity (cache SIZE) has never been swept independently in EITHER the Sniper-simulated
runs above or (per finding 5) conclusively on real hardware. It's entirely possible the
formula's default sizing is simply wrong for some DB/workload combos - too small to
capture enough repeat k-mer hits on the big DBs (where findings 3/4 already show a win -
could a bigger cache win MORE?), or irrelevant on the small DB no matter how large it
gets, because almost nothing repeats there at all (findings 1/2 suggest this, but it's
never been directly tested by varying size).

## Step 0 (Iteration 1, Analyse phase should confirm or redo this)

**Locate the actual cache-size sizing code.** A quick check on Luna
(`kraken2-src-baseline` and `kraken2-fresh-bin-s2-lru-noatomics-4way`'s install
directories) found only compiled binaries (`classify`, `kraken2`, etc.) and Perl
scripts - no `.cc`/`.h` source tree was present in either location as of 2026-09-15.
The source used to BUILD these variants has to be found before a size sweep can happen:
- Check `dorado-kraken-research/CLAUDE.md` and `dorado-kraken-research/AccuracyDrift/patches.md` for the source tree path used in earlier patch work
- Search more broadly than the two paths already checked: `find /home/student -iname 'compact_hash.h' -o -iname 'seqreader.h'` across the whole home directory
- Determine whether the formula is a compile-time constant (needs a rebuild per size,
  like the existing `-noatomics-{1,4,8,16,32,64}way` binaries each were) or a
  runtime flag/env var (much cheaper - one binary, many sizes)

**This determines the whole shape of the experiment.** If size requires a rebuild per
value, budget real build time in addition to Sniper run time. If it's a runtime flag,
the size sweep becomes as cheap as the associativity sweep was.

## The research question

**For a fixed associativity (4-way, established optimal or tied-optimal in every sweep
so far), does varying the SOFTWARE cache's total capacity reveal a size where real gains
appear (or disappear) - and does the answer depend on database size?**

Concretely, three sub-questions the 5 agents should each take a position on in Analyse
phase 1, independently, before any discussion:
- Is there a cache size on the SMALL (50MB) DB, large enough to actually capture
  meaningful hit-rate, where the cache finally beats no-cache? Or is finding 1 (cache
  always loses on this DB) robust to size - i.e. is the problem structural (too little
  reuse in the access pattern) rather than a sizing problem?
- On the LARGE (8GB+) DBs where cache already wins big at the default size (up to 3.59x,
  finding 4), does making the cache BIGGER buy even more speedup, or does it
  plateau/reverse past some point (per-lookup comparison overhead scaling faster than
  hit-rate gains - the same mechanism that made 8-way/16-way lose to 4-way in the
  associativity sweep, fig9, and the exact mechanism `[[project_simd_hypothesis_deferred_sept2026]]` already confirmed in code)?
- Is there a single "best" cache size across DB sizes, or does the optimum shift with DB
  size (i.e. does the cache need to be sized as a FRACTION of the DB, an ABSOLUTE entry
  count, or something else)?

## Suggested methodology (feed this into each iteration's Plan phase)

1. Complete Step 0.
2. Fixed associativity: **4-way**. Binary already exists if it's a compile-time variant:
   `/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way/classify`.
3. Size ladder (anchored on the known default formula's own clamp bounds, `4096`-`262144`
   entries, plus one point below and one above): `2048, 4096, 16384, 65536, 262144,
   1048576` entries (roughly 4x steps, 6 sizes).
4. Cross with DB size: at minimum 50MB (`sample_targeted`, cache currently loses) and
   8GB (`standard_8gb`, cache currently wins big) - ideally also 16GB
   (`standard_16gb`) and 103GB (`pluspf_103gb`) if Step 0 shows size is cheap to vary.
   6 sizes x 2-4 DBs = 12-24 runs for this axis alone.
5. Keep workload size fixed and modest (10 or 50 reads - files already exist:
   `cache_simulation/workloads/tiny_10reads.fastq`, `50reads.fastq`, mirrored on Luna).
   The associativity/read-count relationship is already characterized; don't re-cover
   it. Small read counts keep each run fast (~1-4 min per the `laptop_sweep` job's own
   10-read timings: 52-139s/run).
6. Hardware config: `luna.cfg` (ties to findings 1-3) or `laptop.cfg` (ties to finding
   4) - config-only `-c` flag, no rebuild for this axis.
7. Metric discipline: cycles, never wallclock (see `command_log.md`'s dedicated
   correction). Sanity-check every row (cycles/instructions should equal reported IPC).
   Follow the detached-launch + `progress.log`/`live_summary.csv` pattern from
   `run_laptop_sweep.sh`/`run_hw_assoc_sweep.sh` so any real run survives disconnects.

## Hypotheses each agent must explicitly confirm or refute by the end of Iteration 3

| # | Hypothesis | Confirms | Refutes |
|---|---|---|---|
| H1 | Small-DB loss is structural, not a sizing problem | Cache loses to S0 at every size tested, including the largest | Cache beats S0 at some size, even an impractically large one |
| H2 | Large-DB win grows monotonically with size | Speedup keeps increasing size-over-size on 8GB/16GB | Speedup plateaus or reverses past some size |
| H3 | Optimal size is a fixed FRACTION of DB size, not an absolute count | Best size on 8GB scales proportionally to best size on 16GB/103GB | Best size is roughly constant across DB sizes |
| H4 | Kraken2's current default formula (f=0.25, clamped) is already near-optimal | No size in the sweep meaningfully beats the default | A size clearly outside the current clamp bounds wins |

## What a real conclusion looks like (not allowed to punt on this)

- **Small DB**: either "H1 confirmed - no size helps, here's the evidence" or "H1
  refuted - size X beats no-cache, here's the number."
- **Large DB**: either "H2 confirmed to size X, then Y happens" with the actual
  plateau/reversal point named, or "H2 refuted, here's where and why it stopped
  helping."
- **Cross-DB**: a stated position on H3 with the supporting numbers, not just "it's
  complicated."
- **Practical**: a stated position on H4 - should kraken2's real default formula change,
  and to what, based on what this project found.

## Deliverable

Continuing the existing figure numbering (`fig1`-`fig13` already exist, next is
`fig14`+): a cycles-based size x DB-size grid matching the existing visual style
(grayscale/hatched bars or a clean line/heatmap, serif publication font,
`pdf.fonttype=42`, cycles as the metric, explicit caption distinguishing software cache
SIZE from the associativity already characterized elsewhere - this project has
repeatedly had to correct chart captions for exactly this confusion, don't repeat it),
plus a written verdict on H1-H4 above - logged into `cache_simulation/command_log.md`
with the same why/what/result discipline every other entry in that file follows, and
committed/pushed to `https://github.com/KathpaliaChirag/Nanopore-project` at each real
milestone, not just at the end.
