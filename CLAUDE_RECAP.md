# Claude Recap — Nanopore Project

> **Purpose:** Read this at the start of every session to get up to speed instantly. Update with `/recapupdate` at the end of each session or when a significant milestone is hit.
> **Last updated:** 2026-06-24

---

## One-line status

AccuracyDrift **Luna runs are complete** (all 6 DBs × 3 models × all thread counts + per-pod5 done 2026-06-22). Orion reads_fast still pending. M1–M7 pre-patch measurements **not started** — they gate the optimisation patch and Section 6 of the report.

---

## What happened last (2026-06-22)

Five commits completing remaining AccuracyDrift Luna runs (no docs sessions this time — pure experiment data):

- reads_hac × sample_targeted × 2T–96T thread scaling (peak **21.26× at 32T**)
- pluspf_103gb warm + thread scaling for all 3 models (peak ~1.71× — near-flat, >90% LLC miss throughout)
- reads_fast × all 6 DBs × all thread counts (std_16gb 1T has cold-start outlier, footnoted)
- Per-pod5 classification: 16 pod5 files × 3 models × 2 DBs = 96 runs at 1T each
- AccuracyChase.md updated: per-pod5 / warm / thread-scaling items marked done

---

## Pending — ordered by urgency

### Blocker: M1–M7 pre-patch measurements (Luna)
Run these **before** applying `kraken2_opt_v1.patch`. All commands in `Luna/experiments/pending_measurements.md`.
- **M1** — hash table header (cell width, load factor, cells/cache-line) → decides prefetch stride
- **M2** — dTLB miss rate → decides if MADV_HUGEPAGE patch is worth it
- **M3** — perf annotate on CompactHashTable::Get() → confirms which line causes the LL misses
- **M4** — uncore IMC DRAM bandwidth → confirms latency-bound vs bandwidth-bound
- **M5** — k-mer minimizer reuse rate → validates LRU cache ROI (Patch 4, Kolin sir's design)
- **M6** — perf c2c false sharing → only needed if revisiting NUMA beyond 32T
- **M7** — objdump AVX-512/AVX2 usage → decides if -march=sapphirerapids rebuild helps

After M1–M7: run `bash ~/run_kraken2_opt_v1.sh` on Luna → fill Section 6 of `docs/reports/kraken2_optimisation_report.md`.

### AccuracyDrift remaining (Luna complete; Orion partial)
- [ ] reads_fast × all DBs × all thread counts (Orion — reads_hac + reads_sup done, reads_fast pending)
- [ ] Species breakdown for all runs (reads_fast full perf)
- [ ] AccuracyDrift/machines/Luna.md — file doesn't exist yet

### Not started / deprioritised
- Dorado GPU profiling on Luna L40S (deprioritised after Meeting 4)
- Minerva runs (blocked: disk 100% full)

---

## Key numbers (do not get these wrong)

| Fact | Value |
|---|---|
| Luna RAM | 503 GB |
| Luna LLC | 210 MB total (105 MB/socket) |
| Luna perf_event_paranoid | 0 (set 2026-05-29) |
| Optimal Kraken2 config | 32T + numactl --cpunodebind=0 --membind=0 |
| Baseline wall time (hac, 32T, node0) | 4.405 s |
| CompactHashTable::Get() LLC share | 96.24% of all LL read misses (cachegrind) |
| MinimizerScanner LLC misses | 0 (pure compute) |
| Cache cliff on Luna | between 50 MB (sample_targeted) and 142 MB (eskape_650mb) |
| eskape_650mb actual size | 142 MB (not 150, not 650 MB — name is build cap) |
| PlusPF accuracy ceiling | reads_sup 99.24% classified (pluspf_103gb, 32T) |
| Orion SLC | 4 MB — every DB in experiment is post-cliff on Orion |

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
| The optimisation patch | `Luna/experiments/kraken2_opt_v1.patch` |
| Pre-patch measurement commands | `Luna/experiments/pending_measurements.md` |
| Apply-and-benchmark script | `Luna/experiments/run_kraken2_opt_v1.sh` |
| Optimisation report (Section 6 empty) | `docs/reports/kraken2_optimisation_report.md` |
| Luna profiling steps 1–51+ | `Luna/profiling/results_kraken2.md` |
| Session log (source of truth) | `docs/updates.md` |

---

## Machines quick-ref

| Machine | SSH | Status |
|---|---|---|
| Luna | `student@luna.cse.iitd.ac.in` | Primary. perf_event_paranoid=0. AccuracyDrift complete. |
| Orion | `jetsonagx@10.154.233.173` | ARM64. Campus only. reads_hac + reads_sup done; reads_fast pending. |
| Minerva | CK account | Blocked — disk 100% full. |

---

## Project context

- Supervisor: **Kolin sir** (Prof. Kolin Paul). Always "sir".
- Patch 4 (thread-local LRU k-mer cache) is **Kolin sir's design** — credit him.
- This is a **documentation + research repo**, not a software project. No local build system.
- Source files (.patch, .sh, .py, .c) are deployed to Luna/Orion via rsync/scp.
- `stalled-cycles-backend` unsupported on Sapphire Rapids — use `cycle_activity.stalls_l3_miss`.
