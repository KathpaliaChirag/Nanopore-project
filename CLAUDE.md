# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Purpose

Research project profiling and optimising a clinical diagnostic pipeline for ESKAPE antibiotic-resistant pathogens from nanopore sequencing data. Two tools are profiled: **dorado** (GPU basecaller) and **kraken2** (CPU k-mer classifier). The primary optimisation target is `CompactHashTable::Get()` inside kraken2 — it generates 96.24% of all LLC misses despite being only 0.65% of instructions.

All authoritative perf numbers come from **Luna** (bare metal Sapphire Rapids). WSL2 hardware counters are unreliable (Hyper-V inflates IPC 4–14×; LLC-load-misses unsupported).

---

## Machines

| Machine | SSH | Notes |
|---|---|---|
| Luna | `student@luna.cse.iitd.ac.in` | Primary. Xeon Platinum 8468, 96c/192t, 210 MB LLC, 503 GB RAM, 2× L40S |
| Orion | `jetsonagx@10.154.233.173` | ARM64 Jetson AGX Orin 64 GB, campus network only |
| Minerva | CK account | Blocked — disk 100% full |

Luna account is **student** (shared). Orion account is **jetsonagx**. Our Minerva account is **CK** (not "chirag" — that is Chirag Suthar, a different person).

`perf_event_paranoid` on Luna is currently 0 — all hardware events available without root.

---

## Key Paths on Luna

```
~/results/basecalling/reads_hac.fastq       # 104,918 reads, 703 MB — primary test input
~/results/basecalling/reads_sup.fastq       # 104,980 reads, 723 MB
~/results/basecalling/reads_fast.fastq      # 104,832 reads, 708 MB
~/AccuracyDrift/databases/                  # all 6 kraken2 databases (eskape_650mb etc.)
~/data/kraken2_db/                          # standard 8 GB DB (Steps 1-51 profiling)
~/kraken2-src/                              # kraken2 source clone
~/kraken2-build/                            # compiled binaries (classify, kraken2)
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

Optimal config: **32T + numactl node0** (baseline 4.405s). This gives 21.8% free improvement over 96T no-pin. Thread sweet spot is 32T — beyond that, cache thrashing and contention outweigh parallelism.

Key derived metrics:
- `LLC Miss Rate% = LLC-load-misses / LLC-loads × 100`
- `IPC = instructions / cycles`
- Do NOT use `stalled-cycles-backend` — unsupported on Sapphire Rapids. Use `cycle_activity.stalls_l3_miss` instead.

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

Orion thread counts: 1, 2, 4, 6, 8, 10, 12. No numactl (single NUMA node). Requires sudo for perf. On Orion, `cache-references` maps to L1D (not LLC) — `Cache Miss Rate%` column is not comparable to Luna. Use `LLC Miss Rate%` for cross-machine comparison.

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

**Run M1–M7 measurements before applying the patch.** These gate which patches are worth applying. Commands are in `Luna/experiments/pending_measurements.md`. None of M1–M7 have been run yet (as of 2026-06-15).

---

## Building the Custom ESKAPE Database (scripts/)

The three scripts in `scripts/` were used for the original 650 MB ESKAPE database on WSL2. Current databases on Luna are rebuilt — use `AccuracyDrift/README.md` for the current build procedure (requires `ncbi-genome-download`; rsync is blocked on Luna so taxonomy must be downloaded via wget).

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
docs/reports/kraken2_optimisation_report.md  ← consolidated report (Section 6 unfilled — needs M1-M7)

AccuracyDrift/
  README.md        ← databases, machine list, setup commands
  RESULTS.md       ← all raw numbers (classified%, LLC miss rate, time, IPC)
  OBSERVATIONS.md  ← analysis — three behavioral classes, cache cliff, Orion comparison
  COMMANDS.md      ← exact commands run (Luna fully logged; Orion has template)
  AccuracyChase.md ← PlusPF 103 GB gold-standard ceiling
  machines/
    Orion.md               ← Orion hardware, perf event notes, tegrastats reference
    perf_events_reference.md ← cross-machine event mapping (x86 vs ARM64)

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

## Three Behavioral Classes (AccuracyDrift)

| Class | DBs | Bottleneck |
|---|---|---|
| Pre-cliff | sample_targeted 50 MB | Fits in LLC, near-linear scaling to ~22× at 64T |
| Bandwidth-saturated | eskape_650mb 142 MB, eskape_human_4gb 3.8 GB | DRAM bandwidth wall, 10–22× peak |
| Amdahl-limited | standard_8gb, standard_16gb | Serial DB mmap load dominates, 3–4× ceiling |

Cache cliff on Luna is between 50 MB and 142 MB (LLC is 210 MB but random hash access exhausts effective capacity earlier). Every DB is post-cliff on Orion (SLC = 4 MB).

---

## Critical Facts (do not get these wrong)

- Luna RAM = **503 GB** (not 504)
- eskape_650mb actual hash table size = **142 MB** (not 150, not 650 MB — the name is the DB build size cap)
- Orion SLC = **4 MB** System Level Cache
- Orion Kraken2 path = `~/tools/kraken2/kraken2` (explicit path needed under sudo)
- Behavioral class name is **"pre-cliff"** (not "post-cliff") for the DB that fits in LLC
- `stalled-cycles-backend` is **not supported** on Sapphire Rapids — use `cycle_activity.stalls_l3_miss`
- Luna `perf_event_paranoid` is currently **0** (set 2026-05-29), not 1 or 4
- Patch 4 (thread-local LRU cache) was Kolin sir's design — credit him when describing it
- The project supervisor is **Kolin sir** (Prof. Kolin Paul) — always use "sir"

---

## What Is Not Done Yet

- M1–M7 pre-patch measurements on Luna (`Luna/experiments/pending_measurements.md`)
- Applying `kraken2_opt_v1.patch` and measuring delta
- `docs/reports/kraken2_optimisation_report.md` Section 6 (waiting on M1–M7 + patch results)
- `AccuracyDrift/machines/Luna.md` does not exist yet
- Dorado GPU profiling on Luna L40S (Step 13) — deprioritised
- Minerva runs — blocked by disk
- Lab Desktop runs
