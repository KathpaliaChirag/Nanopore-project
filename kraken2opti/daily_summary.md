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

---

## 2026-05-25

- Reinstalled nsys 2026.2.1 on Ubuntu 26.04 (post Ubuntu reinstall) via standalone .deb
- Diagnosed and fixed missing progress bar: nsys on Ubuntu 26.04 intercepts child stderr, breaking dorado's `isatty()` check; fix: `LD_PRELOAD=/tmp/fake_tty.so` (compiled fake_tty.c override)
- Set ptrace_scope=0 to allow nsys full process tracing
- Restructured project directory: tools/ (dorado, kraken2, kraken2-build), data/ (pod5, minikraken2), results/; .gitignore updated to track only .md files on hobbbit branch
- Re-ran fast model nsys profiling on `_15.pod5` (30,275 reads, 44.95s, 26.7M samples/s) — kernel distribution identical to Phase 1a: beam_search 26%, GEMM 16.5%, LSTM 23.2%
- Re-ran HAC model nsys profiling on `_15.pod5` (30,275 reads, 116.6s, 10.3M samples/s) — LstmKernel 70.0%, consistent with Phase 1b
- Converted fast model BAM → FASTQ (30,362 reads) using samtools
- Ran Kraken-2 classification: 30,362 reads, 93.0% classified, 42.2s runtime
- Ran gprof on Kraken-2: CompactHashTable::Get() = **80.65%** of CPU time — strongest evidence for Kolin sir's Hot-K-mer LRU cache
- Started perf stat setup for Kraken-2 — identified PMU multiplexing issue (15 events > 6 counters), solving with event groups
- Pending: complete perf stat (grouped), update report.md Phase 2, run cachegrind

---

## 2026-05-28

- Designed 21-variant matmul implementation set covering 5 optimization primitives (T/O/A/P/U) + 3 references (transposed, OpenBLAS, Strassen) — singles → doubles → triples → quad → ultimate → ref
- Wrote all 21 source files under `results/pfz_batch1/src/` with `gcc -O2 -g -march=native` compile + Makefile + run_ch3.sh script
- Installed `libopenblas-dev` to enable `matmul_blas.c` (cblas_dgemm reference)
- Verified `perf_event_paranoid = -1` → AMD IBS and `ls_any_fills_from_sys.*` / `de_dis_dispatch_token_stalls1.*` work in per-thread mode without sudo
- Cleared all previous CH3/CH4/CH5 batch1 results, ran fresh CH3 sweep (4 experiments × 21 variants = 84 perf_stat outputs)
- Key results: BLAS 0.012 s / 179 GFlops/s = **165× speedup over naive**; best hand-written `tiled_omp_avx` 0.021 s / 102 GFlops/s = 94×; `ultimate` (5-stack) is slower than `tiled_omp_avx` (3-stack) — stacking optimizations is not monotonic
- Naive's load-queue-stall-per-FP-dispatch = **196.7%** (vs ikj 3.5%) — direct hardware proof of memory-bound stall, single number that replaces the old IPC argument
- Identified inconsistency in my own analysis: kernel-internal time vs `perf stat` elapsed differ by ~25 ms (init), which is 75% of "elapsed" for fast variants like BLAS → fixed all tables to use binary-internal `clock_gettime`
- Wrote Phase 2b to report.md with all 5 tables at full precision (CH3-A wall/IPC, CH3-B cache, CH3-C r5 stability, CH3-D LQ stalls, CH3-E parallel efficiency); added Critical Self-Review section grading each claim ✅/⚠/❓/❌
- Surprises: `unroll` is the fastest single-optimization variant; `prefetch` beats explicit `avx`; `transposed` 4× slower than `ikj`; OMP only reaches 7-12 of 16 effective CPUs (BLAS reaches 13.4)
- Extended sweep to **N=2048 (96 MB, 6× L3)** and **N=4096 (384 MB, 24× L3)** — added `run_ch3_paramN.sh` parametric script; results in `ch3_perf_stat_N{2048,4096}/` (84 perf_stat files each)
- N=2048 takes ~6 min total sweep time; N=4096 takes ~50 min (naive alone is 691 s × 8 experiments). naive at N=4096 = 11.5 minutes wall time, IPC = **0.041** (24 cycles per instruction — fully DRAM-stalled)
- **Tiling crossover finally identified at N=4096:** plain `tiled` still loses to `ikj` wall-clock at every N, but `tiled_omp_avx` (2.17 s) is **5.5× faster than `omp_avx` (11.92 s)** — tiling becomes indispensable when combined with parallelism, because it cures the parallel-bandwidth contention failure mode (omp_avx LQ-stall=368% → tiled_omp_avx LQ-stall=18.7%, 100× reduction)
- BLAS speedup over naive: 165× (N=1024) → 105× (N=2048) → **741× (N=4096)**; gap over my best hand-written variant: 1.75× → 1.39× → 2.33× (narrowed then re-widened)
- Strassen finally shows its O(N^2.807) scaling at N=4096 (6.81× per N-doubling, better than ideal 8×) and has the **lowest L1 miss% (4.97%) of any variant**, but is still 15× slower than BLAS due to 264 B instruction count from split/merge/malloc
- Restructured the matmul section: removed Phase 2b/2c from report.md, created `matrix_mul/` folder with three self-contained per-N reports (`report_n1024.md`, `report_n2048.md`, `report_n4096.md`); report.md now has a 33-line summary linking to them
- Audited both n2048 and n4096 reports for proper analysis: fixed Bottom Line contradiction in n2048 (BLAS lead "narrowed" not "further ahead"), fixed wrong working-set number (96 MB → 384 MB) in n4096 Critical Self-Review, fixed wrong IPC numbers in retraction claim, added missing Surprises/Self-Review sections, added cross-N scaling tables to both
- Total today: 21 variants × 4 perf_stat experiments × 3 N values = **252 perf outputs**; 3 per-N reports + report.md summary + daily_summary + index updated
- Pending: CH4 (perf record cycles/cache/IBS, perf annotate, perf diff) and CH5 (perf mem `--sort mem`, perf c2c, perf bench mem) — currently only CH3 is complete across all N values

---

## 2026-05-29

- Ran `perf stat` (cache events) + `perf stat` (AMD Zen4 TMA events) + `mpstat -P ALL 2` for all 27 combinations: 9 thread counts (1,2,4,6,8,10,12,14,16) × 3 modes (fast/hac/sup); binary rebuilt without `-pg`
- Key findings: IPC stable T1–T8 (fast 1.363→1.402), drops sharply at T10 (1.233) and continues to T16 (1.115) — bandwidth saturation boundary is T=10 for all three modes
- Instructions retired flat (fast ±1.83% T1→T16) — proves zero algorithmic overhead from multi-threading; IPC drop is purely stall cycles growing
- `ls_not_halted_cyc` flat T1–T8 (~85 B cycles), jumps +13.9% at T10 — confirms T10 as the DRAM bandwidth saturation point; same inflection in all three modes simultaneously
- Cache-miss count near-constant (~375–400 M for fast) at all thread counts — 8 GB working set does not shrink with more threads; cache-miss% decline (16.5%→14.6%) is a ratio artefact, not a real improvement
- BE-Bound rises 75.5%→79.2% (fast T1→T16); FE-Bound stays 1.4–1.8% throughout — frontend never a bottleneck
- Op-cache misses grow +15% (fast) to +25% (sup) T1→T16 — secondary pressure from concurrent threads evicting each other's decoded micro-ops
- Optimal thread count: T8 — 5.36× speedup, IPC 1.4017, BE-Bound 74.6%; T16 adds only 23% more throughput at cost of 20% IPC drop
- Rewrote `generate_thread_report.py` to match actual data format (perf_stat_dd has only cache-misses/refs/elapsed, not IPC); IPC sourced from TMA events
- Generated `reports/kraken2_thread_scaling_full.md` — 494 lines, 7 sections, per-table observations after every table (18 obs blocks total)
- Updated report.md Phase 2c with GitHub link and 7 key findings; pushed commit 8f44af9 to hobbbit branch
