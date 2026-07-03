# Claude Recap - Nanopore Project

> **Purpose:** Read this at the start of every session to get up to speed instantly. Update with `/recapupdate` at the end of each session or when a significant milestone is hit.
> **Last updated:** 2026-07-03

---

## One-line status

M1–M7 pre-patch measurements are **done** (M1–M5, M7; M6 skipped, low priority) - all four patches are a go, two revised upward. The patch itself is **still unapplied/unbenchmarked** - that's the top-priority next step. Dorado GPU profiling on Luna L40S is **complete** (contradicts the earlier "deprioritised" note). AccuracyDrift grew a new per-pod5 / merged-pod5 dimension; Orion `reads_fast` and 2 Luna `reads_fast` DBs are still open.

---

## What happened last (2026-06-24 → 2026-07-02)

Six sessions' worth of work landed without session-log entries (docs/updates.md had a 2.5-week gap, now backfilled):

- **M1–M4 patch characterisation** (`AccuracyDrift/patches.md`, 2026-06-24): load factor ≈0.70 all DBs, dTLB miss 0.05–0.32%, DRAM bandwidth 4.9–10.7% of peak → latency-bound confirmed.
- **README 5-agent overhaul + M1-M7 completion + Dorado L40S** (2026-06-26): README expanded to 15 numbered sections. M5 k-mer reuse = 90.7% (Patch 4 revised −20%→−40-50%). M7: zero AVX-512/AVX2 in the binary (Patch 1 revised −8%→−15-25%). Dorado L40S profiled: fast=33.9s, hac=55s, sup=4m26s.
- **Dorado CPU/GPU/Orion comparison + pod5 ESKAPE tables** (2026-06-27): Luna CPU fast=9m40s(28.6×)/hac=43m26s(107×)/sup~9days(FP8→FP32 fallback, no CPU has native FP8); Orion GPU fast=6m44s, hac~1 day.
- **Merged-pod5 full-dataset profiling** (2026-07-01): all 16 FBE pod5 files merged into one dataset - GPU throughput identical to single-file baseline (already saturated). Kraken2 classification jumps with the 103GB DB (fast 80.67%→96.53%, sup 85.46%→99.32%).
- **Presentation deck + recap command** (2026-07-02): `presentations/june.pptx` (26 slides), `.claude/commands/recapupdate.md` added.

Full detail backfilled into `docs/updates.md`.

---

## Pending - ordered by urgency

### Top priority: apply and benchmark the patch
M1–M7 all say "apply" (see Key numbers below). `Luna/experiments/run_kraken2_opt_v1.sh` has **never been run**. The wall-time numbers in `README.md` §12a (4.405s → 1.92s projected) are estimates, not measurements.
- [ ] Run `bash ~/run_kraken2_opt_v1.sh` on Luna
- [ ] Fill `docs/reports/kraken2_optimisation_report.md` Section 6 (still 100% TBD) with real before/after deltas
- [ ] M6 (perf c2c) - optional, only matters if revisiting NUMA beyond 32T

### AccuracyDrift remaining
- [ ] Orion `reads_fast` × all 5 DBs × all thread counts - not started
- [ ] Luna `reads_fast` × eskape_650mb, × eskape_human_4gb - missing (sample_targeted/standard_8gb/standard_16gb/pluspf_103gb done)
- [ ] Species breakdown for `reads_fast` (RESULTS.md §4, "repeat 4.1-4.3 for reads_fast")
- [ ] `AccuracyDrift/machines/Luna.md` - still doesn't exist
- [ ] `AccuracyDrift/merged_pod5_profiling.md` nsys/CUDA sections - placeholder `???`
- [ ] AccuracyChase next step: build optimised sample-specific ESKAPE DB using pluspf per-pod5 output as ground truth

### Not started / blocked
- Minerva runs - blocked, disk 100% full
- Lab Desktop runs - not started

---

## Key numbers (do not get these wrong)

| Fact | Value |
|---|---|
| Luna RAM | 503 GB |
| Luna LLC | 210 MB total (105 MB/socket) |
| Luna perf_event_paranoid | 0 (set 2026-05-29) |
| Optimal Kraken2 config | 32T + numactl --cpunodebind=0 --membind=0 |
| Baseline wall time (hac, 32T, node0) | 4.405 s - **measured** |
| Patch projected wall time (all 4 applied) | ~1.92 s - **estimated, not yet measured** |
| CompactHashTable::Get() LLC share | 96.24% of all LL read misses (cachegrind) |
| M3: actual top LLC-miss line | kernel page-fault/page-walk handler (33-75% depending on DB), not Get() itself (2-11%) |
| M5: k-mer reuse rate | 90.7% (32.8M unique / 351.8M lookups) - Patch 4 ROI confirmed high |
| M7: vectorisation in classify binary | 0 AVX-512, 0 AVX2, 1308 SSE - no vectorisation at all |
| Dorado L40S wall times | fast=33.9s, hac=55.0s, sup=4m26s |
| Dorado Luna CPU wall times | fast=9m40s, hac=43m26s, sup≈9 days (FP8→FP32 fallback) |
| Cache cliff on Luna | between 50 MB (sample_targeted) and 142 MB (eskape_650mb) |
| eskape_650mb actual size | 142 MB (not 150, not 650 MB - name is build cap) |
| PlusPF accuracy ceiling | reads_sup 99.24% classified (pluspf_103gb, 32T) |
| Merged-pod5 dataset | 16 FBE pod5 files, ~1.87M reads total, classification jumps to 96-99%+ on 103GB DB |
| Orion SLC | 4 MB - every DB in experiment is post-cliff on Orion |

---

## Four behavioral classes (Kraken2 × DB size)

| Class | DBs | Bottleneck | Peak speedup (Luna) |
|---|---|---|---|
| Pre-cliff | sample_targeted 50 MB | Compute/bandwidth headroom | 21.26× at 32T |
| Bandwidth-saturated | eskape_650mb 142 MB, eskape_human_4gb 3.8 GB | DRAM bandwidth wall | 10–22× |
| Amdahl-limited | standard_8gb 7.6 GB, standard_16gb 15 GB | Serial DB mmap load | 3–3.5× |
| DRAM-saturated (103 GB) | pluspf_103gb 103 GB | >90% LLC miss, near-zero headroom | ~1.71× at any T |

---

## Key file locations

| What | Where |
|---|---|
| All raw profiling data | `AccuracyDrift/RESULTS.md` |
| Analysis / observations | `AccuracyDrift/OBSERVATIONS.md` |
| Gold-standard accuracy (pluspf) | `AccuracyDrift/AccuracyChase.md` |
| M1-M7 measured values + patch decisions | `AccuracyDrift/patches.md` |
| Dorado L40S GPU profiling results | `AccuracyDrift/dorado_profiling.md` (NOT Luna/profiling/results_dorado.md - that's a stale template) |
| Merged-pod5 (16 files) profiling | `AccuracyDrift/merged_pod5_profiling.md` |
| Per-pod5 ESKAPE species comparison | `AccuracyDrift/pod5_classification_comparison.md` |
| Raw per-pod5 perf/report dumps | `AccuracyDrift/runs/fbe_pod5_hac/` |
| The optimisation patch | `Luna/experiments/kraken2_opt_v1.patch` |
| Pre-patch measurement commands | `Luna/experiments/pending_measurements.md` |
| Apply-and-benchmark script (unrun) | `Luna/experiments/run_kraken2_opt_v1.sh` |
| Optimisation report (Section 6 still TBD) | `docs/reports/kraken2_optimisation_report.md` |
| Luna profiling steps 1–51+ | `Luna/profiling/results_kraken2.md` |
| Presentation deck | `presentations/june.pptx` (26 slides, 2026-07-02) |
| Session log (source of truth) | `docs/updates.md` |

---

## Machines quick-ref

| Machine | SSH | Status |
|---|---|---|
| Luna | `student@luna.cse.iitd.ac.in` | Primary. perf_event_paranoid=0. AccuracyDrift mostly complete; reads_fast gaps remain. |
| Orion | `jetsonagx@10.154.233.173` | ARM64. Campus only. reads_hac + reads_sup done; reads_fast entirely pending. |
| Minerva | CK account | Blocked - disk 100% full. |

---

## Project context

- Supervisor: **Kolin sir** (Prof. Kolin Paul). Always "sir".
- Patch 4 (thread-local LRU k-mer cache) is **Kolin sir's design** - credit him. M5 (90.7% reuse rate) validates it strongly.
- This is a **documentation + research repo**, not a software project. No local build system.
- Source files (.patch, .sh, .py, .c) are deployed to Luna/Orion via rsync/scp.
- `stalled-cycles-backend` unsupported on Sapphire Rapids - use `cycle_activity.stalls_l3_miss`.
- Docs can drift out of sync with git history for weeks at a time (happened 2026-06-16 → 2026-07-02) - when in doubt, check `git log` against what CLAUDE.md/this recap claims before trusting either.
