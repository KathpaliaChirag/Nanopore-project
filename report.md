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

### Phase 1h — Dorado Fast vs HAC GPU Utilisation (`nvidia-smi dmon`, full 4 GB file)

> Full profiling data and per-metric breakdown: [results/dorado/prof/gpu_profile_report.md](results/dorado/prof/gpu_profile_report.md)

**Input:** `FBE01990_24778b97_03e50f91_7.pod5` (4 GB) | **GPU:** RTX 4050 Laptop, 6 GB VRAM, 60W

| Metric | Fast (118s) | HAC (293s) |
|---|---|---|
| SM avg (CUDA cores) | **97.6%** | **99.5%** |
| SM max | 100% | 100% |
| Mem BW avg | 84.7% | 32.4% |
| Mem BW max | 100% | 52% |
| VRAM avg / max | 3.2 GB / 3.5 GB | 3.6 GB / 3.6 GB |
| Throughput | ~33.9 MB/s | ~13.7 MB/s |

- **Fast:** compute + memory bound simultaneously — small model weights reloaded frequently, driving Mem BW to 84.7%; SM at 97.6%
- **HAC:** purely compute bound — large model weights sit in VRAM and are reused heavily (high arithmetic intensity); low Mem BW (32.4%) is a sign of efficiency, not waste; SM at 99.5%
- **No CPU/disk bottleneck** in either run — flat 97–99% SM with no inter-batch sag confirms GPU was never starved
- **VRAM headroom:** ~2.5 GB unused — safe margin before adding `--modified-bases` or increasing `--batchsize`
- **Verdict:** GPU is at physical capacity; no software tuning will improve throughput; a larger GPU is required to go faster

[→ Full report](results/dorado/prof/gpu_profile_report.md)

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

## Phase 2c — Per-Thread Profiling Report with per-table observations

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

## Phase 3 — Kraken2 Optimization Design (full-stack, latency-attack)

> Full design document (5 stackable layers + broader speedup menu, exact + optional
> approximate paths, Ultraplan-merged): **[reports/plandoc.md](reports/plandoc.md)**

Design only — no source/Makefile/binary changes this pass. Headline points:

- **Verdict:** memory-bound — gprof `CompactHashTable::Get()` = **80.65%** of CPU; T8 clean baseline IPC **1.40**, cache-miss **15.91%**, wall **8.39 s**; DB ≈ 500× L3.
- **5 layers:** (1) per-thread 4-way set-associative k-mer→taxon LRU cache wrapping `Get()` (exact, bit-identical), (2) software prefetch for cold k-mers, (3) build flags `-march=native -mtune=native -flto`, (4) transparent huge pages for the 8 GB table, (5) run at the T8 bandwidth sweet spot.
- **Optional approximate fast-path:** 16-bit key tag (2× cache capacity, ~1/65536 false-hit/way), validated against `kraken2_report.txt`.
- **Projected:** cache-miss → 9–12%, IPC → 1.8–2.3, wall → 5.5–6.5 s.
- **Broader menu:** AMAC probe-pipelining, rolling 2-bit minimizer scanning, PGO/LTO/BOLT, bucketized DB layout, static hot sub-table, 1 GB huge pages, index-param tuning, I/O path, GPU offload.

---

## Phase 4 — ESKAPE Targeted Bitmask DB (design + source verification)

> Full plan + source-verified analysis (5 corrections, mechanism trace, OpenMP, accuracy/speed verdicts): **[reports/eskape_bitmask_plan.md](reports/eskape_bitmask_plan.md)**

Alternative direction to Phase 3: instead of caching the 8 GB DB, **replace it** with a 6-organism ESKAPE-only DB whose cell value is a **6-bit bitmask** (1 bit/organism) — one `Get()` answers all 6. Design only, no code changes. Verified against local source 2026-06-01.

| Question | Verdict |
|---|---|
| Implementable? | **Yes** — no showstopper; core mechanism traced & confirmed |
| Reduces lookup time? | **Yes** — DRAM probe (~100 ns) → L2/L3 hit; bounded (NextMinimizer cost unchanged) |
| Cache-friendly? | **Likely** — tens of MB vs 8 GB; confirm L3-residency via `estimate_capacity` |
| Improves accuracy? | **Scoped yes** (collision FP ~2⁻³⁴ + unique-hit rule); loses sub-species + non-ESKAPE; sensitivity bounded by reference panel |
| OpenMP usable? | **Yes, both sides** — zone-locked build (order-independent), `org_read_counts[6]` reduction at classify |

- **Mechanism (verified):** OR-accumulate via `CompareAndSet` (≤2 iters, same shape as LCA loop); self-describing file round-trip (`key_bits+value_bits`); 40-bit `CompactHashCell40` → **key=34 / value=6**; over-capacity is a hard `errx` (size via `estimate_capacity`).
- **3 critical inconsistencies (all fixable):** (1) cell is 40-bit not 32 — key=34; (2) detection must count **single-bit unique** hits, not any set bit, or shared minimizers cause false positives; (3) `load_index` always loads a taxonomy → needs stub or gate. +5 moderate/minor (taxonomy-derived value_bits, `ProcessSequenceFast` coupling, `ResolveTree` misuse, output format, confidence threshold).
- **Scope note:** classify.cc edit is ~100 lines — the output tail (`:898`, `:923`) and caller (`:607-622`) index the taxonomy unconditionally and must be gated, not just the accumulation.
- **Baseline ground-truth run** (`reads_fast.fastq`, 8 GB DB, p8, measured): 104,832 reads, **93.18% classified**, 2.398 s, RSS 8.5 GB. ESKAPE: **P. aeruginosa 54,122 (51.63%)** + **K. pneumoniae 8,193 (7.82%)** strong; trace E. cloacae 28 / A. baumannii 6 / S. aureus 1; E. faecium absent. Non-ESKAPE background (E. coli 18.19%, human 0.57%) must be rejected. Outputs in `results/kraken2/manual_run/`.

---

## AccuracyDrift — Minerva (Intel Xeon Gold 6330, 112T, 251 GB RAM)

> ⚠️ **RESULTS NOT VALID — needs re-run on idle server.** Runs were done while Minerva was fully loaded by other users' processes (heavy context switching). Timings, speedups, IPC, and cache/LLC miss rates are unreliable. Classified%/Unclassified% are unaffected (deterministic); all performance metrics below are suspect.

> Full tables, per-combo observations, and final findings: **[reports/accuracydrift_minerva.md](reports/accuracydrift_minerva.md)**

**Setup:** 3 reads (fast/hac/sup) × 4 DBs (eskape_650mb, eskape_human_4gb, standard_8gb, standard_16gb) × 5 thread counts (1,2,4,8,16) × 3 runs each = 180 runs. Values are 3-run averages.

Key findings:

- **Scaling governed by LLC miss rate** — eskape_650mb scales 13–14× at 16T (LLC miss drops with threads); standard DBs plateau at 3–5× (fully DRAM-bound at 1T, no improvement with more threads)
- **Minerva is ~10× slower than Luna at 1T on eskape_650mb** ⚠️ *gap inflated by Minerva contention — unreliable until re-run* — root cause: Minerva L3 ~42 MB cannot hold the 142 MB DB; Luna L3 = 210 MB fits it almost entirely (Luna LLC miss 30.70% vs Minerva 68.58%)
- **eskape_human_4gb has the highest LLC miss rate (83%) despite not being the largest DB** — ESKAPE + human k-mer space is highly diverse and non-repetitive; standard DBs have lower miss rates (~51%) due to repetitive common-organism k-mers
- **standard_8gb is the practical sweet spot** — 95.77% (hac) / 97.09% (sup) classified; standard_16gb adds only 2 pp for 38% longer runtime
- **Read model matters more on standard DBs** — fast vs hac gap is 14.4 pp on standard_8gb but only 4.1 pp on eskape_650mb; DB coverage is the bottleneck for ESKAPE-targeted DBs, not read quality
- **All runs IPC < 1.2** — Minerva is entirely memory-bound across all DB sizes; no run approaches compute saturation

| DB | LLC Miss% (hac, 1T) | Speedup at 16T (hac) | hac Classified% |
|----|--------------------:|---------------------:|----------------:|
| eskape_650mb | 68.58 | 13.97× | 65.28 |
| eskape_human_4gb | 83.25 | 7.91× | 66.13 |
| standard_8gb | 50.70 | 4.59× | 95.77 |
| standard_16gb | 50.36 | 3.39× | 97.77 |

---

## AccuracyDrift — Dell OptiPlex 5090 (Intel Core i7-11700, 8c/16T, 16 MB L3)

> Full tables, per-combo observations, and final findings: **[reports/accuracydrift_dell_optiplex.md](reports/accuracydrift_dell_optiplex.md)**

**Setup:** identical matrix to Minerva — 3 reads × 4 DBs × 5 thread counts × 3 runs = 180 runs (3-run averages). Same fastq files and read counts (104,832 / 104,918 / 104,980), so **Classified% is byte-for-byte identical to Minerva** — accuracy is hardware-independent.

Key findings:

- **Scaling capped by 8 physical cores** — best case eskape_650mb 8.11× (hac, 16T) vs Minerva's 13.97×; 16T runs on hyperthreads (2/core)
- **Hyperthreading is selective** — 8T→16T gains 1.35–1.46× on latency-bound small DBs (HT hides memory stalls) but only 1.04–1.10× on bandwidth-bound standard DBs (8 cores already saturate DRAM)
- **~10–13× faster than Minerva at 1T** (18.2 s vs 233.3 s, hac/eskape_650mb) ⚠️ *Minerva timing INVALID (loaded server) — gap inflated, re-run needed* — 4.9 GHz boost + Rocket Lake IPC
- **IPC set by access pattern, not miss rate** — standard_8gb posts the highest IPC (2.17) despite a 63% miss rate (well-pipelined, high MLP), while eskape_human_4gb is worst (1.20) on serialised misses
- **HT cuts per-thread IPC 15–29% at 16T** — flat 1T→8T, then drops as two hyperthreads share each core's execution units

| DB | LLC Miss% (hac, 1T) | Speedup at 16T (hac) | hac Classified% |
|----|--------------------:|---------------------:|----------------:|
| eskape_650mb | 56.50 | 8.11× | 65.28 |
| eskape_human_4gb | 72.51 | 6.42× | 66.13 |
| standard_8gb | 63.29 | 3.37× | 95.77 |
| standard_16gb | 69.08 | 2.51× | 97.77 |

**Observation:** the two machines tell complementary stories — Minerva is core-rich but per-thread slow (scales to 56 cores, IPC < 1.2), Dell is core-poor but per-thread fast (caps at 8 cores, IPC up to 2.2). Same DB + reads give identical accuracy on both; only throughput and the scaling ceiling change with hardware. On Dell's smaller 16 MB L3 every DB is fully DRAM-bound from 1T, so the practical recipe is unchanged: **standard_8gb at the 8-core sweet spot** — past 8 threads you pay an IPC penalty for little throughput.

---

## AccuracyDrift — ESKAPE 51 MB custom DB (Dell OptiPlex)

> Full tables and per-read observations: **[reports/accuracydrift_dell_optiplex.md](reports/accuracydrift_dell_optiplex.md)** (§ "ESKAPE 51MB database")

**Setup:** custom 51 MB Kraken2 DB built from **six ESKAPE-panel reference genomes** (no *A. baumannii*, no host) — *P. aeruginosa* PAO1, *E. coli* K-12 MG1655, *K. pneumoniae* HS11286, *Enterobacter cloacae* ATCC 13047, *S. aureus* NCTC 8325, *E. faecium* DO. This sample contains mainly the first three; the others are trace hits. Same reads + thread sweep as the other DBs on Dell; 3-run averages.

Key findings:

- **84.80% (hac) / 85.40% (sup) classified from a 51 MB DB** — ~19–20 pp above the general eskape_650mb (~65%) and eskape_human_4gb (~66%), because it carries dedicated references for the sample's dominant organisms. *Focused-panel result, not a general "small ESKAPE DB is better" claim.*
- **Detection breakdown (hac):** *P. aeruginosa* 52.5% · *E. coli* 21.8% · *K. pneumoniae* 9.9% · *E. cloacae* 0.5% · *S. aureus*/*E. faecium* ~0.0% · higher-rank 0.1% (= 84.8% total)
- **Best detection-per-MB by far** — within ~11–12 pp of standard_8gb (95.77%) at 1/150th the DB size; the gap is reads from organisms not in the 6-genome panel
- **Scales 7.4–7.6× at 16T** (wall-clock, close behind eskape_650mb) — latency-bound small DB, HT helps; IPC 1.43–1.47 at 1T (highest of the ESKAPE DBs), drops to ~1.1 at 16T
- ⚠️ classified% = DB↔sample k-mer match, **not** precision — no ground-truth or host-read filtering

### Detection (classified%) by database — all DBs used

| Database | Size | fast | hac | sup |
|----------|-----:|-----:|----:|----:|
| eskape_51mb (custom, 6-genome) | 51 MB | 80.94 | 84.80 | 85.40 |
| eskape_650mb | 142 MB | 61.77 | 65.28 | 65.87 |
| eskape_human_4gb | 3.8 GB | 62.27 | 66.13 | 66.68 |
| standard_8gb | 7.6 GB | 82.66 | 95.77 | 97.09 |
| standard_16gb | 15 GB | 90.44 | 97.77 | 98.48 |

**Takeaway:** standard_16gb detects the most (97–98%) but at 15 GB; the 51 MB panel DB out-detects both general ESKAPE DBs by ~19–20 pp and trails the standard DBs by only ~11–12 pp — when the expected organisms are known, a tiny focused-panel DB is the cheapest route to high detection.

### Per-pathogen detection by database (hac, clade % of all reads)

Sample = 3 dominant ESKAPE pathogens. Species-level shown; *(G nn)* = genus-level where it exceeds species.

| Database | *P. aeruginosa* | *E. coli* | *K. pneumoniae* | host (human) | classified |
|----------|----------------:|----------:|----------------:|-------------:|-----------:|
| eskape_51mb (6-genome) | 52.50 | 21.79 | 9.92 | — | 84.80 |
| eskape_650mb | 65.28 | **0.00** | **0.00** | — | 65.28 |
| eskape_human_4gb | 64.82 | **0.00** | **0.00** | 1.28 | 66.13 |
| standard_8gb | 31.41 *(G 56.17)* | 14.45 | 4.52 *(G 9.13)* | 0.66 | 95.77 |
| standard_16gb | 35.62 *(G 57.67)* | 16.54 | 5.50 *(G 9.56)* | 0.77 | 97.77 |

- **eskape_650mb / eskape_human_4gb find ONLY P. aeruginosa** — zero E. coli, zero K. pneumoniae (those reads go unclassified); they act as Pseudomonas-only DBs and over-call P. aeruginosa (65% vs the targeted DB's 52.5%)
- **Standard DBs detect all 3 but dilute species calls** — high classified% (95–98%) yet only ~50–58% pins to the 3 exact species; LCA ambiguity pushes ~25 pp of *Pseudomonas* up to genus level
- **Host/human reads appear only in human-containing DBs** (eskape_human_4gb, standard_8/16gb); the two pure-ESKAPE DBs leave host reads unclassified
- **51 MB panel DB is the cleanest** — ~84% pinned directly to the 3 dominant species (species% = genus%); only ~0.6% trace hits to the panel's other genomes + a little family/class-level

---

## Phase 5 — ESKAPE Compact-Hash Cell-Size Reduction (16 / 24-bit)

**Date:** 2026-06-27 — implemented + built + verified (not design-only).

> Full report (implementation, size proof, FP model, accuracy, commands, artifacts): **[reports/eskape_cellsize.md](reports/eskape_cellsize.md)**
> GitHub: [reports/eskape_cellsize.md](https://github.com/KathpaliaChirag/Nanopore-project/blob/hobbbit/reports/eskape_cellsize.md)
>
> Deviation sweep (3 basecallers × 3 widths × 2 thresholds + table-fill audit): **[reports/eskape_cellsize_sweep.md](reports/eskape_cellsize_sweep.md)**
> GitHub: [reports/eskape_cellsize_sweep.md](https://github.com/KathpaliaChirag/Nanopore-project/blob/hobbbit/reports/eskape_cellsize_sweep.md)

Narrowed the Kraken2 compact-hash **cell** (CHT — Compact Hash Table) below the stock 32 bits, exploiting that an ESKAPE-only DB needs only `value_bits = 6` (35 taxonomy nodes) — the other 26 bits are wasted collision-check (FP — false positive — ~1 in 30 M). Added `CompactHashCell16` (2 B) + `CompactHashCell24` (3 B) to the templated `CompactHashTable<Cell>` (same pattern as the existing 40-bit cell); selected by `-C {16|24|32|40}`, width self-described in the DB header and auto-detected on load. Built all 3 DBs from identical inputs with **no download** (taxonomy reconstructed from the on-disk 47k-node `standard_8gb/taxo.k2d`; seqid2taxid generated from the genome headers).

Key findings:

- **Size scales exactly with cell width** (size = 32 B header + capacity × cell_bytes; verified to the byte): 32→**48.80 MB**, 24→**36.60 MB** (−25%), 16→**24.40 MB** (−50%). `value_bits=6` auto-derived in all.
- **Correctness:** self-classifying the 6 reference genomes → each calls its own species, **identical across all cell widths**; `dump_table` round-trips all 3 DBs; reported taxon sets identical (35 taxa, none missing/extra).
- **16-bit needs a confidence threshold; 24-bit does not.** On long reads (`reads_fast/hac/sup`), 16-bit at `-T 0` over-classifies by **+16–21%** — hash-collision FP, proven by cross-phylum hits (E. coli/host reads inflating Gram-positive *S. aureus* ×48, *E. faecium* ×1476, which share no 31-mers with Gram-negatives). A `-T ≥ 0.05` confidence threshold collapses this to <0.6% of 32-bit. **24-bit at `-T 0` is already within +0.3–0.45%** of 32-bit.

| DB | size | FP @ `-T 0` | runtime requirement |
|----|-----:|------------:|---------------------|
| 32-bit | 48.80 MB | baseline | — |
| 24-bit | 36.60 MB (−25%) | +0.3–0.45% | none |
| 16-bit | 24.40 MB (−50%) | +16–21% | `-T ≥ 0.05` mandatory |

- **Table fill (load factor):** all 3 DBs are **~70% full / ~30% empty** (built at the same `-c 12200000` capacity; emptiness costs the same bytes at any width, so only the cell shrinks the file). 16-bit holds **9,626 fewer** occupied cells than 32-bit (8,525,857 vs 8,535,483) — distinct minimizers merging under 10-bit key collisions, the measurable root of its FP.
- **Deviation sweep (vs 32-bit, all 3 basecallers):** 24-bit deviates **+0.3–0.45%** at `-T 0` and **0–4 reads / ~105 k** at `-T 0.05` (a true drop-in); 16-bit deviates **+16–21%** at `-T 0` (unusable) but converges to **+0.3–0.6%** at `-T 0.05`.

**Recommendation:** `eskape_24bit` for a drop-in −25% (no threshold); `eskape_16bit` + `-T 0.05` for −50% (species-equivalent to 32-bit). DBs in `data/database/eskape_{16,24,32}bit/`; reports + `findings.md` in `results/eskape_16bit/`; full deviation + fill data in [reports/eskape_cellsize_sweep.md](reports/eskape_cellsize_sweep.md).

---
