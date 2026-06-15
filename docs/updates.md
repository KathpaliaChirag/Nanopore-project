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

---

## 2026-05-28 — Session 9 — Meeting 4 debrief + summer direction set

### Meeting 4 (2026-05-28)
All attendees: **Kolin sir**, Chayanika mam, Chirag K (CK), Chirag Suthar, Rishabh, Rohit.

**CK presented baseline profiling results:**
- Kraken-2 (CPU): perf stat → 34.24% cache miss rate, 301M misses; gprof → 67% in `CompactHashTable::Get()`, 9.87M calls; AMD uProf → IPC = 0.55; verdict: **memory-bound**
- Dorado (GPU): Nsight Systems → GEMM = 82% of GPU time (Tensor Cores FP16), cudaStreamSynchronize = 98.9% of CUDA API time; verdict: **compute-bound**
- Matrix multiply benchmark suite (12 C implementations, N up to 10000) presented as empirical cache-blocking study

**Two optimisation ideas discussed:**
1. **Sequential ESKAPE pipeline** — query E, S, K, A, P, E one at a time instead of one large DB query; smaller active working set per query fits better in cache; short-circuit once dominant match found
2. **L3 cache pinning / frequency-aware partitioning** — pre-compute most frequent k-mers per ESKAPE pathogen from real clinical samples; pin hot k-mers into L3; ~30 L3 misses per call × 9.87M calls is the target; clinical samples tend to be dominated by one pathogen (barcode02 = 100% P. aeruginosa)

**Summer direction decided: Kraken-2 optimisation only.** Dorado/GPU work deprioritised.

**Work split:**
- Chirag K + Chirag S → 3-day Kraken-2 deeper analysis + 2–3 proposals → `kraken2_optimisation_report.md` due 2026-05-31
- Rohit + Rishabh → SNN (spiking neural network) for Dorado basecalling; research phase, no report yet

### Post-meeting documentation
- `meeting_minutes.md` — Meeting 4 added (full profiling results, two ideas, work split, action items)
- `plan.md` — summer direction section added; 3-day deliverable breakdown written
- `summary.md` — Research Goals section rewritten to reflect Kraken-2-only focus and new work split
- `kraken2_optimisation_report.md` — skeleton/template created for the 3-day deliverable

---

## 2026-05-29 — Study session 10 — Luna Kraken-2 profiling complete

- **Goal:** run `perf stat` + mpstat for all 3 models, TMA for all 3, and full thread scaling sweep on Luna
- **perf stat + per-core CPU capture — all 3 models done:**
  - fast: IPC 1.47, LLC miss 82.0%, stall% 51.8%, wall 5.84s — `perf_stat_fast.txt` + `mpstat_fast.txt`
  - hac: IPC 1.58, LLC miss 81.9%, stall% 48.7%, wall 5.0s — `perf_stat_hac.txt` + `mpstat_hac.txt`
  - sup: IPC 1.65, LLC miss 82.0%, stall% 48.5%, wall 5.63s — `perf_stat_sup.txt` + `mpstat_sup.txt`
  - hac warm-cache re-run: IPC identical (1.58), wall time same (~5.6s) — proves the ~4s overhead is mmap fault cost, not disk IO
- **Key cross-model finding:** LLC miss rate is flat at ~82% for all 3 models. read quality does not change the DB miss rate — the 8 GB hash table is simply 38× the 210 MB L3, and no model fixes that. IPC improves with model quality (1.47→1.65) because better reads produce k-mers that retire more useful instructions, not because they hit cache more
- **TMA breakdown — all 3 models done:**
  - hac: memory_bound 25.4%, core_bound 21.7%, retiring 26.9%, bad_spec 16.9%, fe_bound 9.6%
  - fast: memory_bound 28.1% (worst), retiring 24.4% (worst) — lower quality = more wasted slots
  - sup: retiring 27.4% (best) — best useful work per slot
  - all three have near-identical profiles, confirming the bottleneck is the DB, not the reads
- **Thread scaling — wall time sweep (2/4/8/16/32/64/96/128/192 threads, 5 runs each):**
  - sweet spot: **32 threads** (5.507s avg) — we were running 96 which is 6% slower
  - classification time parallelises well: 7.4s→0.72s from 2T→32T (10× speedup on the actual work)
  - but ~4.8s DB mmap overhead is a fixed floor — can't be parallelised away
  - beyond 32T: contention overhead > parallelism benefit, wall time rises continuously to 192T
- **Thread scaling — `perf stat -r 5` sweep (IPC + LLC miss + stalls per thread count):**
  - DRAM stall cycles plateau at ~11B from T=8 onward — memory bandwidth saturates at 8 threads, more threads gain nothing
  - IPC degrades monotonically: 1.81 peak at 4T → 1.28 at 192T (29% collapse)
  - stall% rises: 42% at 4T → 56% at 192T — more threads = more lock contention = more stalls
  - LLC miss% stays flat ~80-82% throughout — the memory wall is structural, not a thread count artifact
- **Files saved:** `Luna/profiling/results_kraken2.md` fully populated, `bash_history.md` steps 23-29, `thread_scaling_perf_T*.txt`, `thread_scaling_fast.txt`, `thread_scaling_perf_summary.txt`
- **README updated** with section 6 — ASCII bar and segment charts for all stats with observations
- **Next:** `perf record` + flamegraph to confirm `CompactHashTable::Get()` as hotspot on Luna native PMU (was 67% on WSL2 gprof — want native confirmation); NUMA analysis

---

## 2026-05-29 (late) — Session 11 — Luna: flamegraph, NUMA, gprof

- **perf record + flamegraph (hac, 32T):**
  - SVG at `Luna/profiling/flamegraph_hac_32t.svg`
  - MinimizerScanner::NextMinimizer = 25.57% of wall time (pure CPU, no DB access)
  - FASTQ read() syscall chain (ext4 → filemap_read → copy_page_to_iter) = ~20%
  - CompactHashTable::Get = 12.10% — hash lookups hit DRAM (~82% LLC miss rate)
  - DB mmap page faults = ~11%
  - gprof's 67% WSL2 figure confirmed wrong: gprof can't see kernel or I/O time

- **NUMA analysis (hac, 32T, all 4 socket/memory configs):**
  - numactl topology: 2 nodes, even CPUs = node 0, odd = node 1, distance 10/21
  - DB resides on node 0 (202 GB used there)
  - Default 32T: 5.261s → node 0 pinned: 4.405s (−16.3%) → node 1 pinned: 5.083s
  - perf stat per NUMA config: LLC miss% stays ~82% in ALL configs — pinning doesn't reduce misses, only miss latency
  - DRAM stall cycles: 6.44B (local node 0) vs 12.2B (cross-socket) — 47% reduction from locality
  - TMA: memory_bound 23.9% (local) vs 31.7% (cross) — 7.8pp from QPI latency alone
  - Thread scaling all 4 NUMA configs: sweet spot always 32T regardless — DRAM bandwidth wall is structural

- **gprof on Luna (two binaries — gprof-instrumented + production):**
  - hac 1T: MinimizerScanner 53.35% (351M calls), CompactHashTable::Get 23.23% (11.6M calls), reverse_complement 6.69%
  - hac 32T (partial, one thread): MinimizerScanner 68.08%, CompactHashTable 10.09%
  - Cross-validation: 23.23% × 18.6s user = 2.43s = 10.6% of wall → matches flamegraph 12.10% exactly
  - Combined zero-code-change gain: 96T default 5.635s → 32T → 32T numactl node0 4.405s = **21.8% reduction**

---

## 2026-05-29–30 — Session 12 — valgrind cachegrind + tmpfs experiment

- **valgrind cachegrind (hac, 1T) — Step 11:**
  - Ran with `--trace-children=yes` (kraken2 is a Perl wrapper, needed to follow into classify binary)
  - Wall time: 362s (~20x overhead), output: `cachegrind_hac_1t.out` (227 KB)
  - **CompactHashTable::Get accounts for 96.24% of all last-level cache read misses** — 5.62M of 5.84M total LL read misses
  - MinimizerScanner::NextMinimizer: 48.23% of instructions, **zero LL misses** — pure compute, perfectly cached
  - Confirms two regimes: MinimizerScanner = CPU-bound (SIMD target), CompactHashTable = memory-bound (LRU cache target)
  - Full results: `Luna/profiling/results_kraken2.md` Step 11

- **FASTQ on tmpfs experiment — Step 12 (negative result):**
  - Hypothesis: copying FASTQ to /dev/shm would eliminate ~20% flamegraph I/O tower
  - Result: warm SSD 4.405s vs tmpfs 4.395s = 0.010s difference — within noise
  - Cold cache experiment (drop_caches): cold SSD 10.894s vs warm SSD 4.648s vs tmpfs 4.649s
  - Conclusion: the 20% tower is `copy_page_to_iter` overhead (page-cache-to-process-buffer copy), not disk I/O
  - FASTQ (703 MB) has been permanently in Luna's 503 GB page cache — tmpfs and ext4 warm are identical
  - Fix would require mmap or O_DIRECT in Kraken2 source
  - Full write-up: `Luna/experiments/tmpfs_fastq/README.md`

- **Next remaining profiling steps:**
  - DRAM bandwidth via uncore IMC events (`perf stat -e uncore_imc_*/cas_count_*`)
  - perf c2c — false sharing between threads (explains IPC degradation past 32T)
  - Instruction mix check via objdump — is MinimizerScanner already auto-vectorized?
  - perf annotate with -g debug symbols — source-line hotspots inside CompactHashTable::Get
  - VTune — check if installed on Luna
  - k-mer reuse measurement script (validate LRU cache ROI)

---

## 2026-05-30 to 2026-06-13 — AccuracyDrift experiment (Luna + Orion)

Full experiment to understand how Kraken2 classification accuracy and cache behaviour change across database sizes, thread counts, basecalling models, and machines. All data and analysis in `AccuracyDrift/`.

### Experiment design
- **Read files:** reads_fast, reads_hac, reads_sup (~104k reads each, same pod5 file, 700 MB each)
- **Databases (5):** sample_targeted (50 MB), eskape_650mb (142 MB), eskape_human_4gb (3.8 GB), standard_8gb (7.6 GB), standard_16gb (15 GB)
- **Machines:** Luna (96-core Sapphire Rapids, 503 GB RAM) and Orion (12-core ARM Cortex-A78AE, 64 GB LPDDR5, Jetson AGX Orin)
- **Metrics per run:** classified%, LLC miss rate% (LLC-load-misses/LLC-loads), wall time, IPC, speedup

### Sample-targeted DB construction
- Built a minimal 50 MB Kraken2 DB from 6 reference genomes matching exactly what is in this sample: P. aeruginosa PAO1, E. coli K-12, K. pneumoniae HS11286, E. faecium 62415, S. aureus MRSA252, E. cloacae ATCC 13047
- Taxonomy download from NCBI required wget (rsync blocked by IITD proxy); nucl_gb + nucl_wgs accession2taxid files = 51 GB combined, deleted after build
- hash.k2d = 50 MB; build time 22s at 32T; provides a 5th DB data point smaller than eskape_650mb but with correct species coverage

### Luna — reads_hac × all 5 DBs × all thread counts
- All runs with numactl --cpunodebind=0 --membind=0, 3 runs averaged
- Key findings:
  - **Cache cliff at ~100 MB on Luna** — sample_targeted (50 MB) = 10.19% LLC miss, eskape_650mb (142 MB) = 30.70%; the 105 MB L3 per socket fits the smaller DB but not the larger
  - **Pre-cliff DB (sample_targeted):** near-linear scaling to 64T peak (22x), DRAM bandwidth not the ceiling
  - **Post-cliff mid-size DB (eskape_human_4gb, 57% LLC miss):** bandwidth wall at ~16T, ceiling ~10.6x, efficiency collapses from 84% at 8T
  - **Large DBs (standard_8gb, standard_16gb):** Amdahl-limited, not bandwidth-limited — DB loading from disk takes 4.2s and 7.5s respectively (serial, non-parallelisable); wall speedup ceilings of 3.5x and 3.2x regardless of thread count
  - **IPC drops below 1.0 at 96T post-cliff** — CPU spending more than one cycle per instruction on average; DRAM stall dominant
  - **Universal 16T→32T LLC dip** across all DB sizes — shorter wall time means perf counters capture less steady-state cache pressure

### Species breakdown (Luna, reads_hac, 32T)
- **True sample composition confirmed via standard_16gb:** P. aeruginosa ~35.6%, E. coli ~16.5%, K. pneumoniae ~5.5%, Pseudomonas sp. p1(2021b) ~2.2%, Homo sapiens ~0.8%, diverse other bacteria ~37%, unclassified 2.2%
- **Classic nosocomial (hospital-acquired) profile** — ICU/ventilator-associated or cystic fibrosis pattern; all three dominant species are ESKAPE pathogens
- **eskape_650mb artefact exposed:** 100% of its classified reads are called P. aeruginosa, including ~33k reads that are actually E. coli and K. pneumoniae — narrow DB forces them onto the only available reference
- **Phikmvvirus LKD16 detected** in standard DBs — a P. aeruginosa bacteriophage, confirming active phage predation in the sample

### Orion — reads_hac × all 5 DBs × all thread counts
- Orion: ARM Cortex-A78AE, 12 cores, 4 MB SLC (system-level cache), 64 GB LPDDR5 unified memory
- **Key finding: Orion's cache cliff is below 4 MB** — the 50 MB sample_targeted DB is already 12.5x above SLC, giving 78.92% LLC miss at 1T vs Luna's 10.19% for the same DB. Every DB in the experiment is post-cliff on Orion
- **Despite 79% LLC miss, Orion scales near-perfectly to 12T for small DBs** (95.4% efficiency at 12T) — each thread generates only ~624 MB/s DRAM traffic, so 12 threads total ~7.5 GB/s, far below the 68 GB/s LPDDR5 ceiling. Scaling is latency-hiding via thread-level parallelism, not bandwidth
- **Orion vs Luna speed gap shrinks with DB size:** 2.41x slower at sample_targeted (Luna pre-cliff, Orion post-cliff) → 1.54x at eskape_human_4gb (both post-cliff) → 1.19x at standard_16gb (both ~80% LLC miss, gap is raw CPU speed only)
- **Orion eMMC is NVMe-class** (~2.5 GB/s effective) — predicted 60–90s wall time for standard_8gb was wrong; actual was 21s warm. Revised Amdahl floors accordingly
- **standard_16gb on Orion peaks at 4.50x at 12T** vs Luna's 2.93x at 32T — Orion's larger RAM (64 GB) means the 15 GB DB pages into RAM fully, no re-reads; but the 4.2s eMMC serial load is the Amdahl floor
- **IPC on standard DBs (2.24) is 2.4x higher than ESKAPE DBs (0.93) on Orion** — standard DB access pattern generates more compute between DRAM stalls regardless of DB size

### reads_sup × all DBs × all thread counts (Luna + Orion, 2026-06-13)
- **Classification rate 0.6–1.3 pp higher for reads_sup across all DBs** — sup-mode basecalling produces fewer substitution errors so more k-mers exactly match reference; effect is real but small
- **Species composition virtually identical between reads_hac and reads_sup** — e.g., P. aeruginosa in standard_16gb: 35.62% (hac) vs 36.03% (sup); differences within 0.4 pp for every species. DB choice dominates; basecalling model is a second-order effect
- **LLC miss rate essentially unchanged between models** (<1.5 pp difference at all DB sizes) — Kraken2's hash access pattern depends on DB structure and k-mer distribution, not read quality
- **Thread scaling at every thread count (1T–96T on Luna, 1T–12T on Orion) is within 0.5 pp efficiency between reads_hac and reads_sup** — basecalling model has zero effect on parallel scaling; the bottleneck is always DRAM bandwidth or Amdahl DB loading
- reads_fast expected to follow the same pattern (runs pending)

### Three behavioural classes confirmed (Luna)
1. **Pre-cliff / just-past-cliff** (sample_targeted, eskape_650mb): scales to 64T peak (~21x), LLC miss slowly rising, bandwidth headroom sustains gains
2. **Post-cliff bandwidth-saturated** (eskape_human_4gb): plateau from 16T at ~10.5x, LLC frozen at 58%, DRAM bus is the hard ceiling
3. **Amdahl-limited** (standard_8gb, standard_16gb): peaks at 32T (3.5x, 2.9x), wall time increases after due to OS thread overhead; serial DB loading is the floor

### AccuracyChase — gold-standard DB selection (2026-06-13)
- Identified that standard_16gb (15 GB) is a downsampled version of the full Standard database (96.8 GB extracted)
- Goal: run the largest practical DB on Luna to establish a true accuracy ceiling per read model, then use that ceiling when evaluating smaller or custom DBs
- **Chose PlusPF (103.4 GB extracted, 79.8 GB download)** — Standard + protozoa + fungi; only 6.6 GB larger than Standard but covers fungi (Candida is common in nosocomial infections matching this sample's profile); plants and full GTDB not needed for this sample type
- All other DBs up to PlusPFP (221.8 GB), core_nt (316.2 GB), GTDB v226 (644 GB) documented in `AccuracyDrift/AccuracyChase.md`
- Luna (503 GB RAM) can load 103.4 GB comfortably; Orion (64 GB) cannot
- Download: `wget https://genome-idx.s3.amazonaws.com/kraken/k2_pluspf_20260226.tar.gz` (run on Luna)

---

## 2026-06-15 — Project review and cleanup (multi-agent)

- AccuracyDrift/README.md: added sample_targeted (50 MB) and pluspf_103gb (103.4 GB) to databases table; updated "4 databases" to "6 databases".
- AccuracyDrift/RESULTS.md: split reads_hac × sample_targeted checklist item into 1T (done) + 2T–96T (pending); added pluspf_103gb cold-run items for all three models; added reads_fast thread scaling items for Luna; reorganized Orion checklist (added per-DB reads_fast items, updated species breakdown item).
- AccuracyDrift/OBSERVATIONS.md: fixed duplicate observation number (second "6" renumbered to "10"); restored missing body of observation 135 (three behavioral classes taxonomy) which had been accidentally pasted onto end of observation 143; removed the orphaned text from end of obs 143.
- AccuracyDrift/COMMANDS.md: added "Missing from this log" summary section and full Orion command template section.
- docs/plan.md: updated IMMEDIATE ACTIONS STATUS to 2026-06-15; marked source-reading task done (docs/reports/kraken2_get_optimizations.md confirms source read 2026-05-29); marked overdue deadline; added AccuracyDrift completion note + Phase 1 delay note to STEP 5 timeline.
- docs/reports/kraken2_optimisation_report.md: added status comment at top noting Section 6 (M1-M7 + patch benchmark tables) is unfilled and what to do to fill it.
- docs/reports/ duplication check: kraken2_get_optimizations.md (v1) and v2 are additive not duplicate; final_report.md and kraken2_optimisation_report.md cover different phases; tables_and_graphs.md (Mermaid) and tables_and_graphs_basic.md (ASCII) serve different rendering contexts. No files deleted.

---

## 2026-06-16 — Multi-agent hierarchical review and cleanup

Full sweep of the project repository using a hierarchical agent structure (R1-R7 background agents + foreground review agent + R7 consistency audit + C1-C5 coordinator agents). 25+ files audited and corrected across three commits (56afc69, d77ab66, 4c18fe7).

Key fixes applied:

- **AccuracyDrift/OBSERVATIONS.md:** duplicate observation number (#10 appeared twice — once in Thread Scaling section as the cache-misses methodology note, once as the first observation in the DB Size section). Thread Scaling instance converted to unnumbered note. Obs 10 is now unique.
- **AccuracyDrift/RESULTS.md:** eskape_650mb size corrected 150 MB → 142 MB throughout; reads_fast thread scaling checklist items added; pluspf cold-run items added.
- **AccuracyDrift/README.md, COMMANDS.md, machines/Orion.md, AccuracyChase.md:** structural fixes, companion files table added, Orion section corrected, Next Steps restructured.
- **Luna/profiling/results_kraken2.md:** hac "cold (first-ever run)" label fixed (DB was warm from fast/sup); fast model DB cache state note added; Goal 5 (thread scaling) added to Profiling Goals table; §5b renamed §5f (was out of order after §5e); Core Findings scope moved from parenthetical header to explicit blockquote.
- **Luna/profiling/results_dorado.md:** Minerva Baselines section retitled as WSL2 Baselines (GTX 1650); 82% GEMM figure correctly attributed to WSL2 not Minerva; "No runs completed — template only" notes added to all 4 empty result sections; inline "fill in from Minerva run" to-do removed; CUDA/Driver note updated (from nvidia-smi, no runs done); last-updated date added.
- **Luna/profiling/results_matmul_luna.md:** N=1024 table (12 variants) and N=2048 timing table filled from Luna bare-metal run data.
- **docs/meeting_minutes.md:** Meeting 1 attendees capitalized; Meeting 2 "Important update" formatting and date (2026-05-18) corrected; Meeting 3/4 next-meeting dates filled (2026-05-28, 2026-06-02); Dorado table WSL2 source note added; barcode02 AIIMS dataset qualifier added; Minerva L3 (~66 MB) filled from Luna_vs_Minerva.md.
- **docs/knowledge_base.md:** stale "Next meeting: 2026-05-18" header fixed; §22 AccuracyDrift+AccuracyChase stub added with accuracy results table.
- **docs/Luna_vs_Minerva.md:** expanded to Luna vs Minerva vs Orion; full Orion section (ARM64, 12-core, 64 GB LPDDR5, 4 MB SLC) added; Verdict table updated.
- **README.md:** Section 10 AccuracyDrift summary added (3 behavioral classes, cache cliff at ~100 MB, Orion comparison); Section 11 "what's next" added; Orion added to hardware table.
- **Numerical consistency (R7 agent):** Luna RAM corrected 504 → 503 GB and eskape_650mb size 150 → 142 MB across AccuracyDrift/RESULTS.md, OBSERVATIONS.md, README.md, docs/updates.md, docs/reports/summary.md.
- **Minerva/profiling/:** "AccuracyDrift not started — disk was full as of 2026-05-28, verify before starting" notes added to both Kraken2 and Dorado result files.
