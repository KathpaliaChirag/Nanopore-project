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
