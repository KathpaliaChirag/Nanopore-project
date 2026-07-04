# Luna Matmul Profiling — Runbook

Source matrix-multiply benchmarks live in `All_Matric_Mul_perf_stats/` on the local repo. WSL2 runs are complete (see `All_Matric_Mul_perf_stats/PERF_REPORT.md`). This directory holds the **Luna re-run scripts** that capture what WSL2 could not: accurate IPC, native Sapphire Rapids stall events, and TMA breakdown.

CPU: 2x Xeon Platinum 8468 (Sapphire Rapids), 503 GB RAM, native Linux (no Hyper-V throttling).

## Sequence

1. **Send the bundle to Luna** — from local repo root:
   ```bash
   rsync -av Luna/profiling/matmul/matmul_luna_bundle/ student@luna.cse.iitd.ac.in:~/matmul/
   ```
2. **SSH to Luna and run everything:**
   ```bash
   ssh student@luna.cse.iitd.ac.in
   cd ~/matmul
   chmod +x *.sh
   ./run_all.sh 2>&1 | tee run_all.log
   ```
3. **Pull results back:**
   ```bash
   rsync -av student@luna.cse.iitd.ac.in:~/matmul/perf_results_luna/ Luna/profiling/matmul/perf_results_luna/
   ```
4. Fill the tables in `../results_matmul_luna.md` from `perf_results_luna/`.

## Scripts in this directory

| Script | What it does | Runtime |
|---|---|---|
| `run_all.sh` | Orchestrator — builds, then runs steps 2-5 below | ~60 min |
| `run_perf_luna.sh N THREADS` | Pipeline + stall passes per binary at one size | 5-40 min depending on N |
| `run_cache_hierarchy_luna.sh` | Intel per-level cache (replaces AMD-event script) | ~5 min |
| `run_tma_luna.sh` | TMA Level-1/2 for naive_ijk vs tiled_avx2 | ~5 min |
| `run_tile32_luna.sh` | Rebuilds tiled variants with TILE=32 and sweeps | ~10 min |

## What this captures that WSL2 could not

| Metric | WSL2 status | Why Luna fixes it |
|---|---|---|
| **IPC** | wrong — Hyper-V throttles cycles counter to 7-23% of real, inflating IPC 4-14x | Native Linux, real cycle counts |
| **cycle_activity.stalls_l3_miss** | unsupported | Sapphire Rapids native event — fills the "is this DRAM-bound" question for naive_ijk |
| **tma_memory_bound / tma_dram_bound** | unsupported | Sapphire Rapids TMA Level-1/2 — single-percentage answer for where cycles are wasted |
| **mem_load_retired.l2/l3_hit/miss** | unsupported (PEBS) | paranoid <= 0 on Luna, PEBS works |

Note: `stalled-cycles-backend` (the standard generic event) is **NOT supported on Sapphire Rapids** — Intel dropped it. `run_perf_luna.sh` uses `cycle_activity.stalls_total` and per-level stall events instead. See `../events_reference.md` for the full story.

## NUMA caveat

Luna is dual-socket. Kraken2 profiling showed a 16.3% wall-time penalty from cross-socket memory traffic. For clean matmul numbers, consider pinning to one socket:

```bash
numactl --cpunodebind=0 --membind=0 ./run_all.sh
```

The default run does NOT pin — gives the "realistic" multi-socket number. If you want both, run twice and diff.

## What to fill in afterwards

`../results_matmul_luna.md` already has the table templates. Each row needs:

- **Time (ms)** — from `task-clock` line in `*_pipe.txt`
- **IPC** — `instructions / cycles` from the same file (now accurate)
- **LLC miss%** — `LLC-load-misses / LLC-loads * 100`
- **Stall-BE%** — `cycle_activity.stalls_total / cycles * 100` from `*_stall.txt`

For the TMA table, read `perf_results_luna/tma/<bin>_N<size>_tma.txt` and copy the percentage next to each `tma_*` row.

## Negative result hypothesis to confirm

WSL2 showed `prefetch_ikj` is 2-2.3x slower than `ikj_order` because of a 9.3x instruction blowup from per-iteration `__builtin_prefetch`. Luna should reproduce this — and the TMA breakdown should show `prefetch_ikj` is **core-bound** (instruction issue), not memory-bound. This is the cleanest evidence to bring to Kolin sir that motivates the Kraken2 NN-prefetcher: blind prefetch hurts sequential access, learned prefetch is needed for irregular access.
