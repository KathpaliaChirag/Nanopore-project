# Nanopore Project — Updates Log

Chronological journal of what we covered each session.

---

## 2026-05-11 — 1st mentor meeting (3–5 pm)

Topics introduced briefly by **mam**:
1. Nanopore sequencing — physical mechanism, device structure, k-mer window, signal/squiggle, POD-5
2. Sample prep pipeline — DNA prep, adaptor ligation, MinION/PromethION, AMR/MBR terms
3. Basecalling tools — Dorado, Guppy, Bonito; neural inference on squiggles; signal compression (VQ, Shannon, Euclidean)
4. Kraken-2 — k-mer hashing for species ID; memory cost; **my research angle**
5. ESKAPE pathogens, AMR/MBR, Kraken-2's diagnostic role
6. Planned experiments (Exp-2, Exp-3); review **Kolin sir's** mail on `perf` + Nsight

Next meeting / deadline: **2026-05-17**.

---

## 2026-05-12 — Study session 1

- Set up `knowledge_base.md` and `updates.md`.
- Started **Topic 1: Nanopore sequencing**.
  - Chunk 1/4  — what sequencing means + how nanopore reads DNA electrically (KB §1.1)
  - Chunk 2/4  — device structure: flow cell → membrane → channels → pores; parallel reads (KB §1.2)
  - Chunk 3/4  — k-mer window (5–6 bp), 4096 patterns, "voice" of DNA, why NN is needed (segmentation + classification) (KB §1.3)
  - Chunk 4/4  — POD-5 raw signal format, squiggle visualization (KB §1.4 — Claude wrote, user to review later)
  - **Topic 1 complete.** Ready for Topic 2 (sample prep pipeline).
- Started **Topic 2: Sample preparation pipeline**.
  - Chunk 1/4  — why prep exists + A-T/G-C pairing recap (KB §2.1 intro + §2.3 — Claude wrote)
  - **Workflow shift:** Claude writes KB directly from now on; user asks questions / adds notes; Claude checks in each chunk.
  - Chunk 2/4  — fragmentation, end prep, Y-adapter structure (motor protein, leader, tether/docking), ligation, kit names LSK/RAD (KB §2.1 deep dive)
  - Chunk 3/4 — how the adapter actually gets DNA into the pore (mechanics of capture) — *deferred to day 2*

---

## 2026-05-16 — Study session 3 (day 3) — Inference setup

- **Goal for today:** run basecalling inference on POD-5 data from mam.
- **Dorado installation — complete.**
  - Found that ONT no longer hosts binaries on GitHub (0 assets on all releases).
  - Located the actual CDN download URL: `cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-win64.zip`
  - Downloaded (~2.8 GB), extracted, verified: `dorado.exe --version` → `1.4.0` 
  - Installed at: `Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe`
  - GPU (NVIDIA) will be auto-detected at runtime — no extra config needed.
  - Installation details added to KB §7.1.
- **POD-5 data from mam:** downloading — pending.
- **POD-5 data from mam arrived** — `FBE01990_24778b97_03e50f91_10.pod5` (4 GB, 104,478 reads).
  - Flow cell: FLO-MIN114 (R10.4.1), Kit: SQK-NBD114-24 (barcoded), Experiment: AIIMS_Shreshtha_1_301025, 5kHz
  - Real clinical data from AIIMS — kept off GitHub via .gitignore
- **fast mode basecalling — complete.** 12 barcodes + unclassified BAMs produced. GTX 1650 handled it fine.
- **hac mode** — default auto-batchsize OOM-crashed on 4 GB VRAM. Fixed with `--batchsize 16`, currently running.
- **sup mode** — not attempted, expected OOM on GTX 1650.
- **CROC tool** found in project folder — likely for accuracy evaluation (BEDROC metric). To clarify with mam.
- KB §9 added: hardware specs, POD-5 metadata, barcoding explanation, inference results, BAM output structure.
- **Reviewed Kolin sir's mail** — fully understood and added to KB §8.
  - Two sub-projects: Hot-K-mer LRU cache (Kraken-2, CPU) + Signal-to-Base cache (Dorado, GPU)
  - Key tech: Intel TBB, AVX-512, LSH, CUDA shared memory
  - **Immediate deliverable: 2-page profile report using perf + Nsight by ~2026-05-25**
  - Profiling plan: WSL2 on local machine is the best option (Colab won't work — no root/Nsight access)
  - Open question for mam/Kolin sir tomorrow: is there a lab server we can SSH into?

---

## 2026-05-13 — Study session 2 (day 2)

- **Calibration update:** user is a CSE student. Bio is context, not core. Lightening bio depth in remaining Topic 2; leaning hard into Topic 3 (basecaller NN) and Topic 4 (Kraken-2 hashing + memory) which are the CSE-relevant parts.
- Topic 2 remaining (Chunks 3 + 4): condensed into a single wrap-up — pore capture mechanics, MinION/PromethION specs, AMR/MBR terminology. (KB §2.2, §2.4, §2.5)
- **Open question for mam:** what specifically does "MBR" stand for in this context? (Flagged in KB §2.5)
- **Topic 2 complete.** Ready for Topic 3 (basecalling) — the first CSE-heavy topic.
- Started **Topic 3: Basecalling**.
  - Chunk 1/4  — basecalling as ML problem: seq2seq framing, CTC analogy to speech, training data source, GPU runtime / Nsight hook (KB §3.0)
  - Chunk 2/4 — NN architecture deep-dive (CNN + RNN/Transformer + CTC) → batched into KB §3.2
- **Batch write** (user requested efficient mode): all remaining KB sections written in one pass for self-paced reading.
  - §3.1 Dorado/Guppy/Bonito tool comparison
  - §3.2 NN architecture (5-stage pipeline, model sizes, GPU bottlenecks for Nsight)
  - §3.3 VQ + Shannon source coding + Euclidean vectors (basecaller as lossy compressor)
  - §4.1 K-mer hashing, minimizers, LCA classification
  - §4.2 Why DB is 100 GB
  - §4.3 Memory-efficiency research angle (Bloom filters, learned indexes, nanopore long-read advantage)
  - §5.1 ESKAPE pathogens
  - §5.2 AMR drivers, MBR still flagged
  - §5.3 Clinical workflow + why memory matters
- **All theory topics (1–5) now in KB.** Topic 6 (experiments) is the remaining piece — that's hands-on, not theory; will start when user is ready.

---

## 2026-05-18 - Study session 4 - Full Colab pipeline run (all 3 modes)

- **Goal:** run Dorado fast mode on Colab, then extend to hac and sup for benchmarking.
- **Dorado on Colab T4 - all 3 modes complete:**
  - fast: 3 min 58s, batch 640
  - hac: 19 min 8s, batch 1664
  - sup: 2h 5min 38s, batch 96 (barely fits on T4)
- **ESKAPE Kraken-2 DB rebuilt from scratch on Colab** - same 650 MB DB as before, 13/13 accessions mapped
- **All 14 barcodes classified for all 3 modes** - species calls identical across modes, only % classified improves
- **Key finding:** hac is the clinical sweet spot - fast→hac gives +3-8%, hac→sup gives only +0.1-1%
- **Barcode summary:** bc01-07 = P. aeruginosa, bc09-12 = mixed K.pneumoniae + E.faecium, bc13 = E.faecium, bc14 = mixed
- **Visualizations:** 4 charts (grouped bar, improvement bar, heatmap, time vs accuracy scatter) in Colab notebook
- **Colab notebook:** https://colab.research.google.com/drive/1mj3lRxxIFS_qCeStrXszhIYHlJ2Z36bw?usp=sharing
- KB §11 added with complete step-by-step Colab guide + all results

---

## 2026-05-20/21 — Study session 5 — Profiling setup + Dorado GPU profile

- **Goal:** run perf on Kraken-2 and nsys on Dorado, produce profiling report
- **perf on WSL2 — resolved:**
  - `linux-tools-generic` does not cover Microsoft's custom WSL2 kernel
  - Fix: built perf from WSL2 kernel source (`github.com/microsoft/WSL2-Linux-Kernel`, tag `linux-msft-wsl-6.6.87.2`)
  - Key dependency: `libtraceevent-dev` (not installed by default, causes build failure)
  - After build: `sudo cp perf /usr/local/bin/perf` + `rehash` (zsh command cache)
  - Working counters: cycles, instructions, cache-misses, cache-references, branches, branch-misses
  - Blocked by Hyper-V: LLC-loads, LLC-load-misses — use cachegrind instead for per-function LLC data
  - KB §15 added: full perf deep dive
- **Nsight Systems — installed and working:** version 2024.2.3 on Windows
  - Several command-line issues resolved: `--` separator not supported in nsys 2024.2.3, `osrt` not a valid trace type, `--stats` flag ambiguous — fixed with `-o`, `--trace cuda,nvtx`, no `--`
  - Must run as Administrator for full tracing
  - Run took ~3 hours total with nsys overhead on GTX 1650
- **Dorado GPU profile — complete:**
  - 82% of GPU time is GEMM (matrix multiply, Tensor Cores) — compute-bound
  - cudaStreamSynchronize = 98.9% of CUDA API time — CPU blocks waiting on GPU
  - Memory transfers not the bottleneck
  - Full results in KB §16 and report1.md Page 2
- **Kraken-2 build — complete:**
  - Cloned from GitHub, added `-pg` to CXXFLAGS in `src/Makefile` (not top-level Makefile)
  - Fixed Windows line endings with `sed -i 's/\r//' install_kraken2.sh`
  - Built with `./install_kraken2.sh ~/kraken2-build` — binaries at `~/kraken2-build/kraken2`
- **FASTQ for Kraken-2 profiling — pending:**
  - Local fast/hac BAM files are truncated (Dorado runs were interrupted)
  - nsys BAM is complete — need to convert to FASTQ with samtools
  - samtools installed in WSL2

---

## 2026-05-26 — Study session 6 — gprof run + hotspot confirmed

- **Goal:** run gprof on Kraken-2 to get function-level time breakdown
- **gprof run — complete:**
  - Input: `barcode02.fastq` (720 MB, 104,829 reads), database: 8 GB standard k2 DB
  - Binary: `~/kraken2-build/classify` (not `kraken2` — which is a shell wrapper, causes "not in executable format" error)
  - Used `pv ... | classify ... -` for stdin piping with a progress indicator
  - Total runtime: 105.87 seconds
- **Key finding: 67% of all runtime is in `CompactHashTable::Get()`**
  - 9,871,933 calls — the k-mer hash table lookup
  - Each call is a random access into the 8 GB database → cache miss → ~100 ns RAM stall
  - Directly where Kolin sir's Hot-K-mer LRU cache intercepts
- **Secondary finding: 18.74% in `MinimizerScanner::NextMinimizer()`**
  - 354,164,193 calls — pure CPU arithmetic, SIMD target
- **Three-tool confirmation of memory-bound verdict:**
  - perf stat: 34.24% cache miss rate
  - gprof: 67% in hash lookup
  - AMD uProf: IPC = 0.55 (accurate, not the WSL2 clock artefact)
- KB §18 added with full results and interpretation
- report.md updated: tool 3 section added, summary table updated
- **Next to run:** cachegrind (per-function LLC miss rates) + ncu (Dorado SM throughput)

---

## 2026-05-27 — Study session 7 — Matrix multiply perf benchmarks (WSL2)

- **Goal:** build a suite of matrix multiply implementations to study cache behaviour with `perf stat`
- **12 C implementations written and built** (`All_Matric_Mul_perf_stats/`):
  - `naive_ijk` — baseline, column-stride B access (worst cache)
  - `ikj_order` — hoist A[i][k], stream B-row sequentially (25× speedup, zero complexity)
  - `kij_order` — outer k loop; good at small N, degrades at large N
  - `transpose_B` — copies B^T so both rows stream; lowest L3 miss rate, slow due to setup cost
  - `tiled` — 64×64 cache blocking; sub-linear scaling (tiles stay in L2)
  - `omp_parallel` — 4-thread outer-i parallelism
  - `omp_tiled` — 4-thread tiled with `collapse(2)`
  - `unrolled_ikj` — manual 4× unroll of j-loop
  - `avx2_manual` — `_mm256_fmadd_pd` intrinsics, 32-byte aligned alloc, 4 doubles/instruction
  - `auto_vec_O3` — compiler auto-vectorisation with `-O3 -march=native`
  - `tiled_avx2` — tiling + AVX2 combined (fastest at large N)
  - `prefetch_ikj` — `__builtin_prefetch` on B; demonstrates software prefetch hurts sequential access
- **Makefile:** `SIZE ?= 1024`, `THREADS ?= 4`, `make run_perf`, `make tile32` targets
- **perf stat runs completed for N=1024 and N=2048** — timing pass + cache hierarchy pass (separate to avoid PMU multiplexing dropout)
  - Working events on WSL2: cache-misses, L1-dcache-loads/misses, L2 AMD-specific events, branches
  - Blocked by Hyper-V: LLC-load-misses, stalled-cycles-backend — confirmed same issue as Kraken-2/Dorado
  - IPC unreliable on WSL2 (same Hyper-V clock throttle as before, marked † throughout)
- **N=10000 background run launched** — naive_ijk excluded (~4 hrs), 11 remaining binaries × 2 passes
- **PERF_REPORT.md written** with:
  - IPC warning section (Hyper-V throttle, same as KB §15.4)
  - RAM requirements table: N=1024→24MB, 2048→96MB, 10000→2.24GB
  - Tables 1-A/B (N=1024 timing + cache hierarchy), Tables 2-A/B (N=2048)
  - Cross-size comparison: wall time slowdown, L3 miss growth, L2/L3 rates, branch miss %
  - Analysis sections A–G covering each variant
- **Key N=1024/2048 findings:**
  - `naive_ijk` is 29.7× slower than `tiled_avx2` at N=1024, widens to 48.2× at N=2048
  - `omp_parallel` is *slower* than single-thread `ikj_order` at both sizes — memory bus is the bottleneck, not compute
  - `tiled` and `tiled_avx2` scale sub-8× (7.4–7.5×) vs expected O(N³) 8× — tiling amortises cache cost
  - `kij_order` degrades super-linearly (18.1× slowdown 1024→2048) — C-row write conflicts
  - `prefetch_ikj` has highest IPC† but 2.3× slower than plain `ikj_order` — software prefetch adds 9× instruction blowup for sequential access that the hardware prefetcher already handles

---

## 2026-05-28 — Study session 8 — N=10000 results + Luna server setup

### N=10000 results (completed overnight)
- **All 11 binaries completed** — 22 raw result files in `perf_results/N10000/`
- **Table 3-A filled in PERF_REPORT.md** — complete results for all binaries
- **Key N=10000 findings:**
  - `omp_tiled` is the winner at N=10000 (**112,506ms**) — only 29× slowdown from N=2048 vs expected 116×; tiling + 4 threads finally pays off with 2.4 GB working set
  - `tiled_avx2` is 2nd (236,546ms) but L3 miss rate jumps to **18.53%** (from 15.9% at N=2048) — tile footprint causing L3 eviction at large N; `TILE=32` recommended
  - `prefetch_ikj` has the **lowest L3 miss% (1.23%)** and lowest L1 miss% (8.34%) — prefetches genuinely work — but emits **9.3× more instructions** than `ikj_order`, making it 2.2× slower
  - `kij_order` degrades super-linearly: 137.6× slowdown vs expected 116.4×
  - `omp_parallel` finally helps at large N: 47.1× slowdown vs 116× expected (4 threads can pipeline DRAM at 2.4 GB scale)
- Comparison Table 1 updated with N=10000 column and 2048→10000 slowdown ratios

### Luna server (dell-R760) — fully documented
- **Specs captured** (`Luna/luna_stats.md`):
  - CPU: 2× Intel Xeon Platinum 8468 (Sapphire Rapids) — 96 cores / 192 logical CPUs @ 3.8 GHz
  - Cache: L2 2 MB/core, **L3 210 MB total** (3.2× Minerva's 66 MB)
  - RAM: **503 GB** (2× Minerva)
  - GPU: **2× NVIDIA L40S** (Ada Lovelace, 46 GB VRAM each, ~91.6 TFLOPS FP32 — 2.5× Minerva's A40)
  - SIMD: AVX-512 + **AMX** (hardware tile matrix multiply — unique to Sapphire Rapids)
  - Disk: 938 GB root, 236 GB free (74%) — healthy vs Minerva's critical 100%
  - `perf_event_paranoid = 1` confirmed (2026-05-28 22:19 UTC) — hardware counters enabled for all users
- **`Luna/install_tools.md`** — btop locale fix, perf paranoid fix, numactl, LIKWID, VTune, DCGM, valgrind; Luna-specific AVX-512 + AMX build flags
- **`Luna/user_guide.md`** — login, key differences vs Minerva, first-login checks, how to copy and run matmul benchmarks
- **`Luna/user_management.md`** — how to create `student` account with restricted access (same process as Minerva: `useradd`, `passwd`, `chmod 700`); Luna-specific: resource limits, disk quota, GPU access notes
- **`Luna/profiling/plan.md`** — 4-phase profiling plan: matmul re-run (full hardware counters), Kraken-2 with LLC+TMA+NUMA, Dorado on L40S, AMX matrix multiply
- **`Luna/profiling/results_*.md`** — empty result templates for matmul, Kraken-2, Dorado with WSL2/Minerva baselines pre-filled

### Luna vs Minerva comparison
- **`Luna_vs_Minerva.md`** created — full side-by-side: CPU, cache, RAM, GPU, storage, profiling readiness
- **Verdict: Luna wins on every hardware dimension** — higher clock (3.8 vs 2.0 GHz), bigger L3 (210 vs 66 MB), more RAM (503 vs 251 GB), faster GPUs (L40S vs A40), healthy disk (Luna at 74%, Minerva at 100%)
- Only current edge for Minerva: nsys/ncu already in PATH (Luna needs same fix applied to Minerva)
- **Tool audit from Luna (chayanika, 2026-05-28 22:19 UTC):** gcc/g++/python3/make/perl/perf all in PATH; valgrind/nvcc/nsys/ncu/numactl/likwid not in PATH — same install queue as Minerva had

### GitHub
- All new files committed and pushed to `KathpaliaChirag/Nanopore-project` (main)
- `.gitignore` updated: compiled binaries excluded, AMDuProf profiling sessions excluded, `gmon.out` excluded
