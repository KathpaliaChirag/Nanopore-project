# Profiling from Zero — Batch 1 Report
**Machine:** AMD Zen, 4.3 GHz · **Workload:** Matrix multiply N=1024 · **Date:** 2026-05-27

---

## 1. Performance Summary

| Variant | Wall Time | IPC | Instructions | Speedup |
|---------|-----------|-----|-------------|---------|
| `matmul_naive` (ijk) | 3.12 s | 0.35 | 4.5B | 1× |
| `matmul_ikj` | 0.28 s | 3.6 | 4.0B | **11×** |
| `matmul_tiled` (TILE=64) | 0.69 s | 4.2 | 12.2B | 4.5× |
| `matmul_omp` (16 threads) | 0.12 s | 2.2 | 3.9B | **26×** |

- naive IPC=0.35 → CPU stalled waiting on memory, not computing
- tiled has best IPC (4.2) but runs **3× more instructions** → slower than ikj
- omp IPC drops to 2.2 because 16 threads contend on shared DRAM bandwidth

---

## 2. Cache Hierarchy (naive, AMD native events)

| Level | Miss rate | Implication |
|-------|-----------|-------------|
| L1-dcache | 47.4% | Nearly every other access misses |
| L2 (from L1 miss) | 52.2% | Most L1 misses fall through to L3 |
| LLC fills | 373M | Data lives in L3, not DRAM |
| DRAM fills | 3.4M | DRAM traffic is low — L3 latency is the bottleneck |

> stride-N access on B[k][j] means every inner-loop load misses L1/L2 and hits L3 (~40 cycle latency). IPC collapses.

**Stability:** 5-run mean = 3.079 s ± 0.55% — measurements are reliable.

---

## 3. Hotspot (perf record)

| Method | Result |
|--------|--------|
| `perf report` — cycles | **99.18%** in `matmul_naive` |
| `perf report` — cache-misses | **99.42%** in `matmul_naive` |
| AMD IBS precise | **94.04%** in `matmul_naive` |
| Flamegraph | `_start → main → matmul_naive (99.87%)` |

All three tools agree — single function, no ambiguity.

---

## 4. Assembly Hotlines (perf annotate)

Inner loop (6 instructions, SSE2 vectorised):

| Instruction | % | Role |
|-------------|---|------|
| `addpd %xmm0, %xmm1` | 28.2% | Accumulate C[i][j] |
| `mulpd -0x2000(%rax)` | 12.4% | Multiply — **B accessed stride-N** |
| `movsd (%rdx)` | 12.3% | Load A[i][k] |

AMD IBS distributes ~14% evenly across all 6 inner-loop instructions (expected — IBS doesn't pin weight to the stalling instruction like Intel PEBS).

---

## 5. Before / After — perf diff (naive vs ikj)

```
98.37%  [baseline only]  matmul_naive   ← consumes naive entirely
+90.23% [ikj only]       matmul_ikj     ← same function, 12× fewer total cycles
```

Same function, same arithmetic — fix was **loop order only** (ijk → ikj), eliminating stride-N on B.

---

## 6. Memory Latency — perf mem (naive)

| Level | % weighted accesses | Latency |
|-------|---------------------|---------|
| L1 hit | 0.22% | ~4 cycles |
| L2 hit | 23.18% | ~12 cycles |
| LLC / same-node | **75.15%** | ~40–100 cycles |
| RAM | 0.31% | ~200+ cycles |

75% of loads served from LLC — not DRAM, but still 10–25× slower than L1. Stall time dominates.

---

## 7. False Sharing — perf c2c (matmul_omp)

```
Total Shared Cache Lines : 0
```

No false sharing. Outer-loop parallelism gives each thread exclusive rows of C — threads never write to the same cache line. OMP scales cleanly.

---

## 8. Roofline Model

**Machine limits:** Peak compute = 17.2 GFlops/s (SSE2) · Peak BW = 26.4 GB/s · Ridge = 0.65 FLOPs/B

```
GFlops/s
  17.2 ──────────────────── SSE2 peak
       
       ● ikj  7.67  (compute-bound, 45% peak)
   6.6 · · ·  memory ceiling for naive
       ● tiled 3.11
   0.7 ● naive
       ──────────────────────────────────
      0.25  0.65   1    10   85   FLOPs/B
            ↑ ridge
```

| Variant | AI (FLOPs/B) | Bound | Efficiency |
|---------|-------------|-------|------------|
| naive | 0.25 | Memory | 10.5% of BW ceiling |
| ikj | 85 | Compute | 44.6% of SSE2 peak |
| tiled | 85 | Compute | 18.1% (instruction bloat) |
| omp 16t | 85 | BW saturated | 94.6% of peak BW |

---

## 9. Tool → Insight Map

| Tool | Question answered |
|------|------------------|
| `perf stat` | IPC=0.35 vs 3.6 — 10× gap, root = memory stalls |
| `perf stat` AMD events | L1 47% miss, L2 52% miss, data lives in LLC |
| `perf stat -r 5` | ±0.55% variance — measurements trustworthy |
| `perf record` + report | 99% time in one function — no ambiguity |
| `perf annotate` | Inner `mulpd` on B[k][j] stride-N is the stall source |
| AMD IBS | Same conclusion as annotate, on AMD hardware |
| Flamegraph | Single tower = single bottleneck, no call-tree branching |
| `perf diff` | Same function 12× cheaper after loop reorder |
| `perf mem` | 75% loads from LLC at 40–100 cycle latency |
| `perf c2c` | Zero shared lines — OMP false-sharing ruled out |
| `perf bench` | 26.4 GB/s peak BW — machine ceiling confirmed |
| Roofline | naive 10× below memory ceiling; ikj at 45% compute peak |
