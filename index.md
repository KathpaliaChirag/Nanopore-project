# Index

Master overview of all files in this memory repo.
Update this every time a new major topic is pushed.

---

## Index

**knowledge_base.md** →
- §0 Pipeline overview (POD-5 → Dorado → Kraken-2)
- §1 Nanopore sequencing (physical mechanism, k-mer window, POD-5 format)
- §2 Sample preparation (DNA extraction, Y-adapter, ligation kits)
- §3 Basecalling (Dorado/Guppy/Bonito, CNN+Transformer+CTC pipeline)
- §4 Kraken-2 (k-mer hashing, 180 GB DB, memory-efficiency research)
- §5 ESKAPE pathogens + AMR/MBR clinical context
- §7–9 Dorado installation, POD-5 metadata, GTX 1650 basecalling results
- §8 Kolin sir's caching project (Hot-K-mer LRU cache + Signal-to-Base cache)
- §11 Full Colab pipeline results (fast/hac/sup modes, all 14 barcodes)

**plan.md** →
- [2026-05-18] Full profiling plan: Nsight (Dorado GPU) + gprof + cachegrind + perf (Kraken-2 CPU)
- Phase 0: Setup (WSL2 vs Linux, build Kraken-2 from source with -pg)
- Phase 1: Dorado GPU profiling with Nsight Systems + Nsight Compute
- Phase 2: Kraken-2 CPU profiling (gprof / cachegrind / perf)
- Phase 3: Interpret results (memory-bound vs compute-bound verdict)
- Phase 4: 2-page report structure for Kolin sir (due ~2026-05-25)

**report.md** →
- Phase 1a: Dorado fast model nsys profiling — 186.8s, 27.2M samples/s, compute-bound (beam_search 26%, GEMM 17%, LSTM 23%)
- Phase 1b: Dorado HAC model nsys profiling — 502.0s, 10.1M samples/s, CUTLASS LstmKernel 69.8%, 2.69× slower than fast
- Phase 1c: Dorado optimization analysis — INT8 quantization and beam search rewrite are real targets; cache does not help Dorado
- Phase 1d: CPU vs GPU comparison — 35× speedup, beam_search consistent bottleneck on both
- Phase 1e: CPU vs GPU scaling (200/400/600 MB) — speedup widens 24×→31× with file size
- Phase 1f: Fast model re-profiling (post Ubuntu reinstall, _15.pod5) — 44.95s, 30,275 reads, results confirmed
- Phase 1g: HAC model re-profiling (post Ubuntu reinstall, _15.pod5) — 116.6s, 30,275 reads, LstmKernel 70.0% confirmed
- Phase 2a: Kraken-2 classification + gprof — 93% classified, CompactHashTable::Get() = 80.65% CPU time, memory-bound verdict
- Phase 2b: Matmul 21-variant CH3 perf-stat sweep at **N=1024, 2048, 4096** — full primitive matrix T/O/A/P/U + transposed/BLAS/Strassen refs. Detailed per-N reports in `matrix_mul/` (see below). report.md has only the cross-N summary now.
- Phase 2c: Kraken2 thread-scaling sweep — 9 thread counts × 3 modes, `perf stat` cache + TMA + mpstat. T8 optimal (5.36×, IPC 1.40, BE 74.6%). Bandwidth saturates at T10. Full report in `reports/kraken2_thread_scaling_full.md`.
- Phase 3: Kraken2 full-stack optimization design (cache the 8 GB DB) — 5 stackable latency-attack layers + broader menu. Full design in `reports/plandoc.md`.
- Phase 4: ESKAPE targeted **bitmask DB** (replace the 8 GB DB with a 6-organism, 6-bit-mask DB) — source-verified implementable, cache-friendly, scoped accuracy gain, OpenMP-ready, 3 critical (all fixable) inconsistencies. Full plan in `reports/eskape_bitmask_plan.md`.

**reports/eskape_bitmask_plan.md** → ESKAPE bitmask DB plan, verified against Kraken2 source (2026-06-01)
- §0 corrections (40-bit cell/key=34, unique-hit detection, taxonomy load) + mechanism-trace note
- §3 implementability: CompareAndSet OR-accumulation, self-describing file round-trip, OpenMP both sides
- §5 accuracy (collision ~2⁻³⁴, scope limits), §7 baseline ground-truth run, §8 summary

**reports/kraken2_thread_scaling_full.md** → comprehensive per-thread Kraken2 profiling report
- 7 sections, 494 lines, 18 per-table observation blocks — exact raw values, no aggregation
- §1 Classification baseline (deterministic, fast 93.18% / hac 97.85% / sup 98.38%)
- §2 Throughput scaling: all 3 runs per (mode, thread), speedup column, cross-mode comparison
- §3 Cache: full 27-row table with cache-misses, refs, miss%, CPU-Eff%; cross-thread miss% breakdown
- §4 TMA: all 27 combinations — retiring/FE/BE/bad-spec/IPC; instructions retired flat (±1.8%); ls_not_halted_cyc T10 jump; op-cache miss growth
- §5 Raw TMA event counts: 7 events × 9 threads per mode
- §6 mpstat per-core utilisation: overall avg, top-3 cores, cores below 5%
- §7 Master cross-thread summary with throughput–efficiency trade-off analysis

**matrix_mul/** → 21-variant matmul perf-stat sweep, per-N standalone reports
- `report_n1024.md` — N=1024 (24 MB working set, fits L3): naive→ikj 11× speedup is purely access-pattern; tiling has nothing to add at this size; BLAS 165× best
- `report_n2048.md` — N=2048 (96 MB, 6× L3): DRAM traffic begins, OMP LQ-stall jumps 10%→89% (parallel bandwidth contention emerges); BLAS lead narrows to 1.39×
- `report_n4096.md` — N=4096 (384 MB, 24× L3): naive takes 11.5 min (IPC=0.041); **tiling-pays-off crossover identified** — `tiled_omp_avx` is 5.5× faster than `omp_avx` because tiling cures the parallel bandwidth-contention failure mode (LQ-stall 368%→18.7%); BLAS lead 2.33×, Strassen finally shows O(N^2.807)

**daily_summary.md** →
- 2026-05-20
- 2026-05-21
- 2026-05-22
- 2026-05-25
- 2026-05-28
- 2026-05-29
