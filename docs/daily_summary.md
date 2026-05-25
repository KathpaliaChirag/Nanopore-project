# Daily Summary

One dated entry per session. Append at end of each conversation.

---

## 2026-05-20
- Set up ~/memory as the hobbbit branch of KathpaliaChirag/Nanopore-project
- Established personal knowledge manager workflow: knowledge_base / plan / report / daily_summary / index
- Explored perf on native Linux (AMD Ryzen 7, paranoid level unlocked to -1)
- Understood all 6 files in the repo: knowledge_base.md, meeting_minutes.md, plan.md, report1.md, summary.md, updates.md
- What was pushed: repo structure initialized, workflow memory saved
- Pending: start adding profiling results to report.md as work progresses; 2-page profiling report due ~2026-05-25

---

## 2026-05-21

- Moved Dorado binary from `~/dorado/` to `/opt/dorado` — freed 8.4 GB from /home partition
- Diagnosed and fixed nsys + Dorado compatibility issue: Dorado bundles its own `libcudart.so.12`, nsys injection fails without sudo; fix is always run `sudo nsys profile`
- Ran nsys on fast model: 104,478 reads, 186.8s, 27.2M samples/s — compute-bound (beam_search 26%, GEMM 17%, LSTM 23%)
- Ran nsys on HAC model: 104,477 reads, 502.0s, 10.1M samples/s — more strongly compute-bound (CUTLASS LstmKernel 69.8%)
- HAC is 2.69× slower than fast; bottleneck shifts from beam_search → CUTLASS LSTM
- Documented that Dorado already uses CUTLASS + Tensor Cores — standard tiling/blocking optimizations are already done; INT8 quantization is the main remaining opportunity
- Confirmed: Dorado is compute-bound, cache won't help — Kraken-2 is the right target for Kolin sir's LRU cache
- Wrote Phases 1a, 1b, 1c in report.md — 4 commits pushed to hobbbit branch
- Pending: Phase 2 — build Kraken-2 with -pg, locate ESKAPE DB, run gprof + cachegrind + perf

---

## 2026-05-22

- Updated index.md to reflect Phase 1a/1b/1c and daily_summary 2026-05-21
- Added SessionStart hook to auto-pull ~/memory hobbbit branch on every Claude session
- Built Kraken-2 v2.17.1 from source with -pg at /opt/kraken2-build/bin/
- Downloaded 6 ESKAPE reference genomes from NCBI FTP
- Built custom ESKAPE Kraken-2 database (60 MB hash table) at /opt/kraken2-build/db/
- Ran Kraken-2 on both fast (22,386 reads, 74.18% classified) and HAC (104,921 reads, 80.89% classified)
- Ran full Phase 2 profiling: gprof + cachegrind + perf on both fast and HAC inputs
- Key result: CompactHashTable::Get() = 69% CPU time; LLC miss rate = 34% — Kraken-2 is memory-bound
- Wrote Phase 2 to report.md with full fast vs HAC comparison tables
- Ran CPU-vs-GPU scaling benchmark on Merged_files 200/400/600.pod5 (fast model, perf + nsys)
- Results: CPU 364/705/1030s vs GPU 14.9/24.4/33.7s — speedup grows 24×→31× with file size
- Wrote reusable `benchmark_cpu_gpu.sh` + `plot_cpu_gpu.py` (log-scale graph, SVG fallback); chart at ~/results/cpu_vs_gpu.svg
- Wrote Phase 1e to report.md
- Pending: add 800/1000.pod5 to scaling curve; Phase 3 (interpret results) + Phase 4 (2-page report for Kolin sir, due 2026-05-25)
