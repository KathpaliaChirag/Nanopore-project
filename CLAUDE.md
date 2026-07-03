# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Purpose

Research project profiling and optimising a clinical diagnostic pipeline for ESKAPE antibiotic-resistant pathogens from nanopore sequencing data. Two tools are profiled: **dorado** (GPU basecaller) and **kraken2** (CPU k-mer classifier). The primary optimisation target is `CompactHashTable::Get()` inside kraken2 - it generates 96.24% of all LLC misses despite being only 0.65% of instructions.

All authoritative perf numbers come from **Luna** (bare metal Sapphire Rapids). WSL2 hardware counters are unreliable (Hyper-V inflates IPC 4–14×; LLC-load-misses unsupported).

---

## Machines

| Machine | SSH | Notes |
|---|---|---|
| Luna | `student@luna.cse.iitd.ac.in` | Primary. Xeon Platinum 8468, 96c/192t, 210 MB LLC, 503 GB RAM, 2× L40S |
| Orion | `jetsonagx@10.154.233.173` | ARM64 Jetson AGX Orin 64 GB, campus network only |
| Minerva | CK account | Blocked - disk 100% full |

Luna account is **student** (shared). Orion account is **jetsonagx**. Our Minerva account is **CK** (not "chirag" - that is Chirag Suthar, a different person).

`perf_event_paranoid` on Luna is currently 0 - all hardware events available without root.

---

## Key Paths on Luna

```
~/results/basecalling/reads_hac.fastq       # 104,918 reads, 703 MB - primary test input
~/results/basecalling/reads_sup.fastq       # 104,980 reads, 723 MB
~/results/basecalling/reads_fast.fastq      # 104,832 reads, 708 MB
~/AccuracyDrift/databases/                  # all 6 kraken2 databases (eskape_650mb etc.)
~/data/kraken2_db/                          # standard 8 GB DB (Steps 1-51 profiling)
~/tools/kraken2-src/                        # kraken2 source clone (NOT ~/kraken2-src/ - that doesn't exist)
~/tools/kraken2/                            # compiled binaries: classify, kraken2 wrapper
~/tools/kraken2-pg/                         # gprof-instrumented build (classify binary)
~/results/profiling/pending/                # M1-M7 measurement outputs
```

Database actual sizes: sample_targeted=50 MB, eskape_650mb=142 MB, eskape_human_4gb=3.8 GB, standard_8gb=7.6 GB, standard_16gb=15 GB, pluspf_103gb=103.4 GB.

---

## Standard Kraken2 Profiling Command (Luna)

```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads 32 \
  --output /dev/null --report /dev/null \
  /home/student/results/basecalling/reads_hac.fastq
```

Optimal config: **32T + numactl node0** (baseline 4.405s). This gives 21.8% free improvement over 96T no-pin. Thread sweet spot is 32T - beyond that, cache thrashing and contention outweigh parallelism.

Key derived metrics:
- `LLC Miss Rate% = LLC-load-misses / LLC-loads × 100`
- `IPC = instructions / cycles`
- Do NOT use `stalled-cycles-backend` - unsupported on Sapphire Rapids. Use `cycle_activity.stalls_l3_miss` instead.

---

## Standard Kraken2 Profiling Command (Orion)

```bash
sudo /usr/lib/linux-tools-5.4.0-26/perf stat \
  -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  ~/tools/kraken2/kraken2 --db ~/AccuracyDrift/databases/<DB> \
  --threads <T> \
  --output /dev/null --report /dev/null \
  ~/reads/reads_hac.fastq
```

Orion thread counts: 1, 2, 4, 6, 8, 10, 12. No numactl (single NUMA node). Requires sudo for perf. On Orion, `cache-references` maps to L1D (not LLC) - `Cache Miss Rate%` column is not comparable to Luna. Use `LLC Miss Rate%` for cross-machine comparison.

---

## Matmul Benchmark (on Luna)

```bash
# Transfer bundle
rsync -av Luna/profiling/matmul/matmul_luna_bundle/ student@luna.cse.iitd.ac.in:~/matmul/

# On Luna: run everything
cd ~/matmul && chmod +x *.sh && ./run_all.sh 2>&1 | tee run_all.log

# Run a single variant with perf
perf stat -e cycles,instructions,LLC-load-misses,LLC-loads,cycle_activity.stalls_l3_miss \
  numactl --cpunodebind=0 --membind=0 ./tiled_avx2 2048

# Pull results back
rsync -av student@luna.cse.iitd.ac.in:~/matmul/perf_results_luna/ Luna/profiling/matmul/matmul_luna_bundle/perf_results_luna/
```

GPU variants (in `Luna/profiling/matmul_gpu_bundle/`): build with `nvcc`, run `./run_timing.sh`.

---

## Applying the Kraken2 Optimisation Patch

The patch is at `Luna/experiments/kraken2_opt_v1.patch`. It implements 4 patches:
1. Makefile: `-march=sapphirerapids -flto -funroll-loops`
2. `mmap_file.cc`: `MADV_HUGEPAGE + MADV_WILLNEED + MADV_RANDOM`
3. `compact_hash.h Get()`: `__builtin_prefetch` one cache line ahead
4. `classify.cc`: thread-local 16K-entry direct-mapped k-mer cache (256 KB/thread, fits L2)

Apply and benchmark:
```bash
# On Luna
bash ~/run_kraken2_opt_v1.sh
```

Or manually:
```bash
cd ~/kraken2-src
git apply --whitespace=nowarn kraken2_opt_v1.patch
cd src && make -s clean && make -s -j 96
```

**M1–M7 are done (as of 2026-06-26), except M6.** Results: `Luna/profiling/pending/*.txt`, decisions in `AccuracyDrift/patches.md`, summary in `README.md` §12a. All four patches are a **go**, two revised upward from original estimates:
- M1: load factor ≈0.70 all DBs, 32-bit cells (sample_targeted is 26+6), PF_STRIDE=16 confirmed correct
- M2: dTLB-load-miss 0.05–0.32% - Patch 2 (huge pages) still worth applying, smaller win than feared
- M3: top LLC-miss line is the kernel page-fault/page-walk handler (33–75% of misses depending on DB size), not `Get()` itself (2–11%) - motivates huge pages more than expected
- M4: DRAM bandwidth 4.9–10.7% of peak → conclusively latency-bound
- M5: k-mer reuse rate **90.7%** → Patch 4 (Kolin sir's LRU cache) revised **−20% → −40–50%**
- M6: **not run** - low priority (only matters if revisiting NUMA beyond 32T)
- M7: 0 AVX-512, 0 AVX2, 1308 SSE instructions in the binary - no vectorisation at all → Patch 1 (compile flags) revised **−8% → −15–25%**

**The patch itself has NOT been applied or benchmarked yet.** `run_kraken2_opt_v1.sh` has never been executed - the wall-time numbers in README.md §12a (4.405s → 1.92s) are projected from the M1–M7 estimates above, not measured. `docs/reports/kraken2_optimisation_report.md` Section 6 is still a TBD stub. Running the patch and filling Section 6 is the single highest-priority remaining task on the Kraken2 side.

---

## Building the Custom ESKAPE Database (scripts/)

The three scripts in `scripts/` were used for the original 650 MB ESKAPE database on WSL2. Current databases on Luna are rebuilt - use `AccuracyDrift/README.md` for the current build procedure (requires `ncbi-genome-download`; rsync is blocked on Luna so taxonomy must be downloaded via wget).

```bash
# Tag genomes with taxids (old WSL2 workflow, kept for reference)
python3 scripts/tag_genomes.py
python3 scripts/fix_seqid_map.py
python3 scripts/fix_prelim_maps.py
```

---

## Repository Architecture

This is a **research documentation repo**, not a software project. There is no build system at the repo root and no tests to run locally. Source code (.c, .cu, .py, .patch) is included for reference and to be deployed to Luna/Orion via rsync/scp.

Key document relationships:

```
README.md                          ← master summary (Sections 1-11 + repo map)
docs/Luna_vs_Minerva.md            ← three-machine hardware comparison (Luna/Minerva/Orion)
docs/updates.md                    ← chronological session log (source of truth for timeline)
docs/meeting_minutes.md            ← Kolin sir meeting notes
docs/reports/kraken2_optimisation_report.md  ← consolidated report (Section 6 unfilled - needs M1-M7)

AccuracyDrift/
  README.md        ← databases, machine list, setup commands
  RESULTS.md       ← all raw numbers (classified%, LLC miss rate, time, IPC)
  OBSERVATIONS.md  ← analysis - four behavioral classes, cache cliff, Orion comparison
  COMMANDS.md      ← exact commands run (Luna fully logged; Orion has template)
  AccuracyChase.md ← PlusPF 103 GB gold-standard ceiling
  patches.md       ← M1-M7 measured values + go/no-go decision per patch
  dorado_profiling.md         ← Dorado GPU profiling on Luna L40S (fast/hac/sup, nsys breakdowns)
  merged_pod5_profiling.md    ← all 16 FBE pod5 files merged into one dataset, dorado+kraken2
  pod5_classification_comparison.md ← per-pod5 (16 files) ESKAPE species breakdown, HAC only
  runs/fbe_pod5_hac/          ← raw per-pod5 perf/report dumps backing the comparison above
  machines/
    Orion.md               ← Orion hardware, perf event notes, tegrastats reference
    perf_events_reference.md ← cross-machine event mapping (x86 vs ARM64)
    Luna.md                 ← does not exist yet

Luna/
  luna_stats.md              ← hardware inventory
  profiling/
    events_reference.md      ← Sapphire Rapids-specific perf events (stalled-cycles-backend broken)
    results_kraken2.md       ← full profiling data Steps 1-51+
  experiments/
    kraken2_opt_v1.patch     ← the patch (4 optimisations in one)
    run_kraken2_opt_v1.sh    ← apply + benchmark script
    pending_measurements.md  ← M1-M7 pre-patch measurements (none run yet)
```

---

## Four Behavioral Classes (AccuracyDrift)

| Class | DBs | Bottleneck |
|---|---|---|
| Pre-cliff | sample_targeted 50 MB | Fits in LLC, near-linear scaling to ~21× at 32T |
| Bandwidth-saturated | eskape_650mb 142 MB, eskape_human_4gb 3.8 GB | DRAM bandwidth wall, 10–22× peak |
| Amdahl-limited | standard_8gb, standard_16gb | Serial DB mmap load dominates, 3–3.5× ceiling |
| DRAM-saturated | pluspf_103gb 103 GB | >90% LLC miss at any thread count, ~1.71× peak - near-zero headroom |

Cache cliff on Luna is between 50 MB and 142 MB (LLC is 210 MB but random hash access exhausts effective capacity earlier). Every DB is post-cliff on Orion (SLC = 4 MB).

---

## Critical Facts (do not get these wrong)

- Luna RAM = **503 GB** (not 504)
- eskape_650mb actual hash table size = **142 MB** (not 150, not 650 MB - the name is the DB build size cap)
- Orion SLC = **4 MB** System Level Cache
- Orion Kraken2 path = `~/tools/kraken2/kraken2` (explicit path needed under sudo)
- Behavioral class name is **"pre-cliff"** (not "post-cliff") for the DB that fits in LLC
- `stalled-cycles-backend` is **not supported** on Sapphire Rapids - use `cycle_activity.stalls_l3_miss`
- Luna `perf_event_paranoid` is currently **0** (set 2026-05-29), not 1 or 4
- Patch 4 (thread-local LRU cache) was Kolin sir's design - credit him when describing it
- The project supervisor is **Kolin sir** (Prof. Kolin Paul) - always use "sir"

---

## What Is Not Done Yet

- **Applying `kraken2_opt_v1.patch` and measuring the real delta** (M1–M7 are done and all say "apply" - this is now the top-priority remaining task)
- `docs/reports/kraken2_optimisation_report.md` Section 6 - still a TBD stub, waiting on the patch run above
- M6 (perf c2c false sharing) - not run; low priority, only matters if revisiting NUMA beyond 32T
- AccuracyDrift: Orion `reads_fast` × all 5 DBs × all thread counts - not started
- AccuracyDrift: Luna `reads_fast` × eskape_650mb and × eskape_human_4gb - missing (other 3 DBs done)
- AccuracyDrift: species breakdown for `reads_fast` (Section 4 of RESULTS.md) - not done
- `AccuracyDrift/machines/Luna.md` does not exist yet
- `AccuracyDrift/merged_pod5_profiling.md` nsys/CUDA sections - placeholder, not filled
- Minerva runs - blocked by disk
- Lab Desktop runs

**Done, despite earlier notes to the contrary:**
- Dorado GPU profiling on Luna L40S - **complete** (2026-06-27): fast=33.9s, hac=55.0s, sup=4m26s wall-time, full nsys kernel breakdowns, CPU/GPU/Orion comparison. Results in `AccuracyDrift/dorado_profiling.md` (NOT `Luna/profiling/results_dorado.md` - that file is a stale unfilled template, still headed "DEPRIORITIZED", left over from the Meeting 4 decision that was later reversed in practice)
- M1–M7 pre-patch measurements - see patch section above
