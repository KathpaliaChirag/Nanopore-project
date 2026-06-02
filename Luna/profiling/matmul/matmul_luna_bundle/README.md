# matmul_luna_bundle

Self-contained matrix-multiply benchmark suite for Luna (Sapphire Rapids).
Send this whole folder, run `./run_all.sh`, pull `perf_results_luna/` back.

## Contents

**Sources** (12 variants, double-precision):
naive_ijk, ikj_order, kij_order, transpose_B, tiled, omp_parallel, omp_tiled,
unrolled_ikj, avx2_manual, auto_vec_O3, tiled_avx2, prefetch_ikj

**Build:** `Makefile` — `make all`, `make tile32`, `make clean`

**Scripts:**
| Script | Purpose | Runtime |
|---|---|---|
| `run_all.sh` | Orchestrator — builds and runs everything below | ~60 min |
| `run_perf_luna.sh N THREADS` | Pipeline + SPR stall events per binary at one size | 5-40 min |
| `run_cache_hierarchy_luna.sh` | Intel `mem_load_retired.*` per-level cache stats | ~5 min |
| `run_tma_luna.sh` | TMA Level-1/2 for naive_ijk vs tiled_avx2 | ~5 min |
| `run_tile32_luna.sh` | TILE=32 rebuild + sweep | ~10 min |

## How to run on Luna

```bash
# from local machine:
rsync -av matmul_luna_bundle/ student@luna.cse.iitd.ac.in:~/matmul/

# on Luna:
ssh student@luna.cse.iitd.ac.in
cd ~/matmul
chmod +x *.sh
./run_all.sh 2>&1 | tee run_all.log

# back on local:
rsync -av student@luna.cse.iitd.ac.in:~/matmul/perf_results_luna/ ./perf_results_luna/
```

## What this captures that WSL2 could not

- **Accurate IPC** — WSL2/Hyper-V throttled the cycles counter (inflated IPC 4-14x)
- **`cycle_activity.stalls_l3_miss`** — proves naive_ijk is DRAM-bound
- **TMA breakdown** — single-percentage answer for memory_bound vs core_bound
- **`mem_load_retired.l2/l3_*`** — PEBS works on Luna (paranoid <= 0)

Note: `stalled-cycles-backend` is unsupported on Sapphire Rapids — scripts use
`cycle_activity.stalls_total` instead. See `events_reference.md` in the parent
profiling folder for details.

## NUMA caveat

Luna is dual-socket. Default `run_all.sh` does NOT pin — gives realistic
multi-socket numbers. For clean single-socket comparison:

```bash
numactl --cpunodebind=0 --membind=0 ./run_all.sh
```

## Outputs

```
perf_results_luna/
  N1024/   {binary}_pipe.txt   {binary}_stall.txt
  N2048/   same
  N10000/  same (naive_ijk skipped — would take ~4 hrs)
  cache_hierarchy/   {binary}_N{size}.txt
  tma/               {binary}_N{size}_tma.txt
  tile32/            {binary}_N{size}.txt
```
