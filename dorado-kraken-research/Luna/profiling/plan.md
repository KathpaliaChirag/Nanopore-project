# Luna — Profiling Plan

> **STATUS NOTE (2026-06-15):** This 4-phase plan was written on 2026-05-28.
> Phase 2 (Kraken2) is complete through Step 12 (Steps 1–51 in bash_history.md).
> Phase 3 (Dorado GPU) and Phase 4 (AMX matmul) are DEPRIORITIZED — summer focus is Kraken2 optimisation only (decided at Meeting 4, 2026-05-28).
> Phase 1 (matmul re-run on Luna) was completed — perf stat results for all 12 N=1024 variants and N=2048 wall times are in `profiling/results_matmul_luna.md`.
> AccuracyDrift experiment (2026-05-30 to 2026-06-13) ran between Phase 2 completion and the next optimisation phase. See `AccuracyDrift/` directory.
> Next active work: Kraken2 source optimisation (proposals A/D/E/F from docs/reports/).

> Same pipeline as Minerva but with full hardware counters + AVX-512 + AMX
> Luna advantages over Minerva: bigger L3, faster CPU, more cores, L40S GPUs

---

## What Luna Fixes vs WSL2 / Minerva

| Limitation on WSL2 | Status on Luna |
|---|---|
| IPC unreliable (Hyper-V throttles cycles) |  **Accurate IPC** |
| `LLC-load-misses` = not supported |  **Works** |
| `stalled-cycles-backend` = not supported |  **Works** |
| TMA metrics unavailable |  **Full TMA (Sapphire Rapids)** |
| NUMA analysis impossible |  **2-socket NUMA available** |
| AVX-512 not on Ryzen |  **AVX-512 + AMX** |

---

## Phase 1 — Matrix Multiply Benchmarks (re-run from WSL2)

Re-run the full `All_Matric_Mul_perf_stats/` suite with:
- Full LLC miss rates
- Accurate IPC
- stalled-cycles-backend (memory stall %)
- TMA breakdown
- AVX-512 auto-vectorisation (compiler picks it up with -march=native)

**Priority runs:**
```bash
# 1. naive_ijk — confirm IPC is really < 0.5 (WSL2 showed 0.23 but unreliable)
perf stat -e cycles,instructions,LLC-load-misses,stalled-cycles-backend ./naive_ijk 1024

# 2. tiled_avx2 — confirm IPC is really 3-5 (compute-bound with tiles in L2)
perf stat -e cycles,instructions,LLC-load-misses,stalled-cycles-backend ./tiled_avx2 1024

# 3. TMA breakdown on naive_ijk vs tiled_avx2 — the key comparison
perf stat -e tma_memory_bound,tma_core_bound,tma_l1_bound,tma_l2_bound,\
tma_l3_bound,tma_dram_bound ./naive_ijk 2048

# 4. NUMA-pinned run to eliminate cross-socket noise
numactl --cpunodebind=0 --membind=0 ./tiled_avx2 2048
```

---

## Phase 2 — Kraken-2 Profiling

Same as Minerva plan but with:
- LLC miss rates now working — direct comparison with cachegrind
- Accurate IPC — confirm AMD uProf's 0.55 reading from WSL2
- TMA: `tma_dram_bound` should be high for hash table lookups
- NUMA: DB likely allocated on one socket — check cross-socket traffic with `ocr.*` events

```bash
pv ~/barcode02.fastq | perf stat \
  -e cycles,instructions,\
     cache-misses,cache-references,\
     LLC-load-misses,LLC-loads,\
     stalled-cycles-backend,\
     tma_memory_bound,tma_dram_bound \
  ~/kraken2-build-pg/classify \
  -H ~/k2_standard_08gb/hash.k2d \
  -t ~/k2_standard_08gb/taxo.k2d \
  -o ~/k2_standard_08gb/opts.k2d \
  -R ~/report_luna.txt - > /dev/null
```

---

## Phase 3 — Dorado GPU Profiling

> **DEPRIORITIZED as of Meeting 4 (2026-05-28).** No runs will be done. See STATUS NOTE at top.

Same as Minerva but on L40S (Ada Lovelace) instead of A40 (Ampere).
L40S has higher FP32 throughput — expect faster basecalling.

```bash
nsys profile --output ~/results/dorado_luna_fast \
  --trace cuda,nvtx --stats true \
  -- $DORADO basecaller fast $POD5 --output-dir ~/results/bam_luna_fast
```

Key comparison: A40 GEMM % vs L40S GEMM % — same bottleneck, different throughput ceiling.

---

## Phase 4 — AMX Matrix Multiply (Luna-exclusive)

> **DEPRIORITIZED as of Meeting 4 (2026-05-28).** No runs will be done. See STATUS NOTE at top.

The Xeon Platinum 8468 has AMX (Advanced Matrix Extensions) — a dedicated
tile-based matrix multiply unit for INT8 and BF16. This is the hardware
acceleration behind Intel's optimised GEMM libraries (oneMKL).

```bash
# Check AMX is enabled
grep amx /proc/cpuinfo | head -1

# Build AMX variant (write amx_matmul.c first)
gcc -O3 -march=sapphirerapids -mamx-bf16 -mamx-tile -mamx-int8 \
    -o amx_matmul amx_matmul.c

# Compare vs tiled_avx2 on Luna
perf stat -e cycles,instructions,stalled-cycles-backend ./amx_matmul 1024
perf stat -e cycles,instructions,stalled-cycles-backend ./tiled_avx2 1024
```

---

## Results Files

| File | Contents |
|---|---|
| `profiling/results_matmul_luna.md` | Matrix multiply re-run with full counters |
| `profiling/results_kraken2.md` | Kraken-2 profiling on Luna |
| `profiling/results_dorado.md` | Dorado profiling on L40S |
