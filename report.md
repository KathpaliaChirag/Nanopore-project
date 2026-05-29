# Report — Executed Work Log

This file tracks everything actually run, tested, or completed.
Full phase details live in [`reports/phase1_dummytesting_dorado_kraken2.md`](reports/phase1_dummytesting_dorado_kraken2.md).

---

## Phase 1 — Dorado GPU Profiling

> Full run data, tables, and commands: [phase1_dummytesting_dorado_kraken2.md](reports/phase1_dummytesting_dorado_kraken2.md)

### Phase 1a — Dorado Fast Model (nsys — Nsight Systems, NVIDIA GPU profiler)
- Compute-bound: `beam_search` 26%, GEMM (General Matrix Multiply) 17%, LSTM (Long Short-Term Memory) 23% = **84.5% GPU time**
- Memory transfers large and regular (~1.28 MB/call) — not a bottleneck
- CPU blocks 98.4% of CUDA API (Application Programming Interface) time on `cudaStreamSynchronize` → GPU is the pacing unit
- **Cache verdict:** Signal-to-base cache saves <5% runtime — wrong target

[→ Full Phase 1a](reports/phase1_dummytesting_dorado_kraken2.md#phase-1a--dorado-fast-model-gpu-profiling-nsight-systems)

### Phase 1b — Dorado HAC (High Accuracy) Model (nsys, 2.69× slower than fast)
- `cutlass::LstmKernel` alone = **69.8% of all GPU time** (vs fast model's simpler LSTM at 23%)
- HtoD (Host-to-Device memory transfer) calls 14× more fragmented than fast (128K vs 9K) but still not bottleneck
- CPU sync time rises to 99.1% — HAC keeps GPU busier than fast

[→ Full Phase 1b](reports/phase1_dummytesting_dorado_kraken2.md#phase-1b--dorado-hac-model-gpu-profiling-nsight-systems)

### Phase 1c — Optimization Analysis
- CUTLASS (NVIDIA GPU linear algebra template library) already implements tiling, blocking, Tensor Cores internally — textbook opts already done
- Realistic targets: **INT8 (8-bit integer precision) quantization** (~2× on Tensor Cores), **beam search rewrite** (26% of fast GPU time)
- Larger `--batchsize` (128/256) is a free 10–30% gain

[→ Full Phase 1c](reports/phase1_dummytesting_dorado_kraken2.md#phase-1c--dorado-optimization-analysis)

### Phase 1d — CPU vs GPU (35× speedup)
- CPU bottleneck: tensor gather/index (5.7%), serial `cat_serial_kernel`, **~10% cycles in page faults**
- GPU wins via FP16 (16-bit floating point) Tensor Cores + parallel LSTM; no allocation overhead
- `beam_search` is the consistent bottleneck on **both** CPU and GPU — will dominate as NN (Neural Network) gets faster

[→ Full Phase 1d](reports/phase1_dummytesting_dorado_kraken2.md#phase-1d--cpu-vs-gpu-comparison-dorado-fast-model)

### Phase 1e — CPU vs GPU Scaling (200 / 400 / 600 MB)
- Both scale ~linearly; CPU ≈ 1.7 s/MB, GPU ≈ 0.055 s/MB
- Speedup widens 24×→31× with file size — GPU amortizes fixed startup cost over more reads

[→ Full Phase 1e](reports/phase1_dummytesting_dorado_kraken2.md#phase-1e--cpu-vs-gpu-scaling-across-file-sizes-dorado-fast)

### Phase 1f / 1g — Re-profiling Post Ubuntu Reinstall
- Fast (_15.pod5): 44.95 s, 30,275 reads — kernel distribution **identical** to Phase 1a ✓
- HAC (_15.pod5): 116.6 s, 30,275 reads — LstmKernel 70.0% **confirmed** ✓
- `LD_PRELOAD=/tmp/fake_tty.so` required under nsys on Ubuntu 26.04 to restore Dorado progress bar

[→ Full Phase 1f/1g](reports/phase1_dummytesting_dorado_kraken2.md#phase-1f--dorado-fast-model-re-profiling-post-ubuntu-reinstall)

---

## Phase 2a — Kraken2 CPU Profiling (gprof — GNU profiler)

> Full run data, tables, and commands: [phase1_dummytesting_dorado_kraken2.md § Phase 2a](reports/phase1_dummytesting_dorado_kraken2.md#phase-2a--kraken2-classification--gprof-profiling)

- **`CompactHashTable::Get()` = 80.65% of all CPU time** — random k-mer lookups into 8 GB DB (database)
- 8 GB DB >> 16 MB L3 (Level-3 cache) → every lookup is effectively a DRAM (Dynamic Random-Access Memory) access (~100 ns stall)
- 93% reads classified; 30,362 reads in 42.2 s = 43.2K reads/min
- Unlike Dorado, Kraken2 is **memory-bound** — a Hot-K-mer LRU (Least Recently Used) cache directly targets the dominant bottleneck and could reduce runtime 40–60%

## Phase 2a (cont.) — Kraken2 perf Profiling & K-mer→Taxon Associativity Table

> Full details: [kraken2_perf_lru_cache.md](reports/kraken2_perf_lru_cache.md)

- **BE-Bound (Backend-Bound) 95.6%, IPC (Instructions Per Cycle) 0.16, Cache-Miss 24%** — pipeline stalled on DRAM ~94% of the time with the `-pg` binary; only 3% of slots did real work
- **`-pg` flag cost ~18% CPU** — removing it from the Makefile raised IPC from 0.154 → 1.1–1.7 (8–10× improvement in useful work per cycle)
- **K-mer→Taxon associativity table planned:** 4-way set-associative, 512 KB per thread (8 MB total, fits in 16 MB L3); maps minimizer/k-mer → taxon ID with LRU eviction; expected to reduce Cache-Miss% from ~24% to ~10–15%

[→ Full details](reports/kraken2_perf_lru_cache.md)

---

## Phase 2b — Matrix Multiplication 21-Variant CH3 Sweep (N=1024, N=2048, N=4096)

**Date:** 2026-05-28
**Workload:** Square C = A·B (doubles), 21 implementations spanning tiling / OpenMP (parallel threading) / AVX2 (Advanced Vector Extensions 2 — CPU SIMD instruction set) / prefetch / unroll + OpenBLAS (open-source Basic Linear Algebra Subprograms library), transposed, and Strassen references.
**Tools:** `perf stat` (basic, AMD cache, 5-run stability, full diagnosis).
**Raw outputs:** `results/pfz_batch1/ch3_perf_stat_N{1024,2048,4096}/` — 84 perf_stat files per N.

Three detailed per-N reports live in `matrix_mul/`:

- [`report_n1024.md`](matrix_mul/report_n1024.md) — N=1024 (24 MB total, fits L1 (Level-1 cache) row-wise; tiling has nothing to add)
- [`report_n2048.md`](matrix_mul/report_n2048.md) — N=2048 (96 MB total, 6× L3; DRAM traffic begins, OMP (OpenMP) bandwidth contention starts)
- [`report_n4096.md`](matrix_mul/report_n4096.md) — N=4096 (384 MB total, 24× L3; naive takes 11.5 min, `omp_avx` LQ-stall (Load Queue stall — pipeline slot waiting on a memory load) = 368%)

### Visual Summary

![21-variant matmul sweep — 4-panel summary](matrix_mul/matmul_summary.svg)

*x-axis: 21 variants sorted slowest→fastest (left to right). One line per N value. Panels: (top-left) wall time log-scale, (top-right) GFlops/s (Giga Floating-point Operations per second) log-scale, (bottom-left) L1 dcache miss%, (bottom-right) load-queue-stall / FP-dispatch (Floating-Point dispatch slots) (symlog). PNG version also available: [`matmul_summary.png`](matrix_mul/matmul_summary.png).*

Headline cross-N summary (best of 21 vs naive):

| N | naive | best hand-written | BLAS | naive→BLAS |
|---|---:|---:|---:|---:|
| 1024 | 1.982 s | `tiled_omp_avx` 0.021 s, 102 GFlops/s | 0.012 s, 179 GFlops/s | 165× |
| 2048 | 14.262 s | `tiled_omp_avx` 0.189 s, 91 GFlops/s | 0.136 s, 126 GFlops/s | 105× |
| 4096 | 691.171 s | `tiled_omp_avx` 2.173 s, 63 GFlops/s | 0.933 s, 147 GFlops/s | **741×** |

Key findings (across all N):
1. **Tiling's L1 miss% is N-independent at ~8%** across 64× of N scaling — exactly its design intent.
2. **But ikj's L1 miss% climbs from 16.5% → 33%** as N grows; tiled never beats ikj wall-clock on this hardware because tiling has 6× the instruction count.
3. **Naive's failure mode changes with N:** L3-latency-bound at N=1024 (LQ stall = 196.7%) → mixed at N=2048 (137%) → DRAM-bound at N=4096 (106%, IPC = 0.041).
4. **OMP (OpenMP) develops a new failure mode at N=4096:** `matmul_omp_avx` LQ-stall/FP-disp (Load Queue stall vs Floating-Point dispatch ratio) = **368%** — parallel-amplified DRAM bandwidth contention exceeds even single-threaded naive.
5. **BLAS lead widens with N:** 1.75× → 1.39× → 2.33× over my best hand-written variant.
6. **Strassen finally shows O(N^2.807)** at N=4096 (6.81× per N-doubling vs ideal 8×), but absolute time still 15× slower than BLAS.

See per-N reports for full tables (CH3-A wall/IPC (Instructions Per Cycle)/GFlops, CH3-B cache, CH3-C stability, CH3-D LQ-stalls (Load Queue stalls), CH3-E parallel efficiency — all with exact-precision numbers for all 21 variants).

---

## Phase 2c — Kraken2 Thread-Scaling Sweep (T1→T16, fast/hac/sup)

> Full analysis: [kraken2_thread_scaling.md](reports/kraken2_thread_scaling.md)

**Date:** 2026-05-29 — sweep across 9 thread counts (1,2,4,6,8,10,12,14,16) × 3 modes using `perf stat -d -d`, TMA (Top-down Microarchitecture Analysis) events, and mpstat per-core utilization. Binary rebuilt without `-pg`.

- **T16 is fastest** (2.2–2.6 s, 2464–2836 Kseq/m) but only **36–41% efficient** — 16 threads on a memory-bound workload gives 6–7× speedup instead of the theoretical 16×
- **T4–T6 is the efficiency sweet spot** — 67–86% scaling efficiency, IPC still 1.4–1.6, DRAM contention not yet severe; gives ~65–75% of T16 speed at half the CPU cost
- **IPC without `-pg`: 1.1–1.7** vs 0.154 with it — removing profiling overhead recovered ~88% of wasted pipeline capacity
- **BE-Bound rises with threads** (75% at T1 → 79% at T16) — more threads = more simultaneous random probes into the 8 GB DB = memory controller congestion; the bottleneck gets worse as threads increase
- **fast/T10 regresses vs T8** — hyperthreading boundary artefact: 10 threads on 8 physical cores forces 2 cores to share L1/L2, slightly raising wall time before more threads compensate at T12+
- **Classification accuracy unchanged** across all thread counts (fast 93.18%, hac 97.85%, sup 98.38%) — parallelism only splits reads, never changes results

[→ Full analysis with all tables](reports/kraken2_thread_scaling.md)

### Phase 2c (full) — Per-Thread Profiling Report with per-table observations

> Full per-thread breakdown (all 27 combinations, exact raw values, per-table observations):
> **[kraken2_thread_scaling_full.md](reports/kraken2_thread_scaling_full.md)**
> GitHub: [reports/kraken2_thread_scaling_full.md](https://github.com/KathpaliaChirag/Nanopore-project/blob/hobbbit/reports/kraken2_thread_scaling_full.md)

Key findings extracted from the full report:

- **Instructions retired are flat (±1.8% T1→T16)** — definitively proves no algorithmic overhead from multi-threading; the same computation is done at every thread count. IPC drops because stall *cycles* grow, not because more work is added.
- **Bandwidth saturation at T=10, not T=8** — `ls_not_halted_cyc` (total stall cycles) is stable T1–T8 (~85 B cycles), then jumps +13.9% at T10 and climbs to +24.5% at T16. The T10 cliff appears simultaneously in IPC, BE-Bound, and `ic_fetch_stall` for all three modes.
- **Cache-miss count is constant (~375–400 M for fast), but cache-miss% declines (16.5%→14.6%)** — this is a ratio artefact: references grow (+6.5%) as more threads issue events while actual DRAM misses are flat. No real cache improvement occurs with more threads.
- **fast mode has ~3–4 pp higher cache-miss% than hac/sup at every thread count** — lower-quality reads probe a wider range of hash-table buckets, generating more cold DRAM accesses.
- **Op-cache misses grow +15% (fast) to +25% (sup) T1→T16** — secondary pressure from concurrent threads evicting each other's decoded micro-ops from the 32 KB op-cache; hac/sup grow faster because they execute more instructions per read.
- **Optimal thread count: T8** — delivers 5.36× speedup with IPC 1.4017 and BE-Bound 74.6%. T16 adds only 23% more throughput over T8 at the cost of a 20% IPC drop and 4.6 pp more BE-Bound.
- **sup mpstat anomaly at T14/T16** — overall %usr appears low (12–13%) vs fast/hac (~25%) because sup completes faster (~2.3 s), capturing fewer 2-second mpstat intervals; the DB-loading samples dominate the average.

---
