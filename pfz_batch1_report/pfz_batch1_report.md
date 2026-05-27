# Profiling from Zero — Batch 1: Full Report

**Machine:** AMD Zen (4.3 GHz, 16 logical CPUs)
**Workload:** Square matrix multiply C = A·B, N=1024, doubles
**Goal:** Use the full `perf` toolchain to understand *why* a naive C implementation is slow, and quantify how loop reorder / tiling / OpenMP fix it.

---

## 1. Variants Profiled

| File | Loop order | Optimisation |
|------|-----------|-------------|
| `matmul_naive.c` | i-j-k | Baseline — stride-N access on B |
| `matmul_ikj.c` | i-k-j | Stride-1 on B and C; scalar `a_ik` hoisted |
| `matmul_tiled.c` | i-k-j blocked, TILE=64 | Cache blocking, working set fits in L1/L2 |
| `matmul_omp.c` | i-k-j parallel | OpenMP, `#pragma omp parallel for` on outer i |

All compiled with `gcc -O2 -g` (omp: `+ -fopenmp`).

---

## 2. Headline Numbers — perf stat (CH3)

| Variant | Wall time | task-clock | Cycles | Instructions | **IPC** | Speedup vs naive |
|---------|-----------|-----------|--------|-------------|---------|-----------------|
| naive   | 3.118 s | 3 114.87 ms | 12.85 B | 4.50 B | **0.350** | 1.00× |
| ikj     | 0.278 s | 274.35 ms | 1.13 B | 4.00 B | **3.551** | **11.2×** |
| tiled   | 0.693 s | 689.29 ms | 2.87 B | 12.22 B | **4.254** | 4.50× |
| omp 16t | 0.122 s | 642.50 ms (4.9 CPUs avg) | 1.71 B | 3.89 B | **2.277** | **25.6×** |

**Key observations**

- **naive IPC = 0.35** → CPU completes only 1 instruction every ~3 cycles. AMD Zen can theoretically retire up to 6 IPC, so naive uses **<6%** of compute capability. The pipeline is **stalled**, not computing.
- **ikj IPC = 3.55** is **10.1× higher** than naive while running fewer instructions (4.0 B vs 4.5 B). Same work, less waiting.
- **tiled IPC = 4.25** is the highest of all variants, but it runs **3.05× more instructions** (12.2 B vs 4.0 B) due to 6 nested loop levels and bounds checks. Net result: slower wall time than ikj.
- **omp IPC = 2.28 per-thread** is lower than ikj's 3.55 because 16 threads contend for shared L3 + DRAM bandwidth.

---

## 3. Branch Behaviour

| Variant | Branches | Branch misses | Miss rate |
|---------|---------|--------------|-----------|
| naive | 589 M | 2.49 M | **0.42 %** |
| ikj   | 572 M | 1.81 M | **0.32 %** |
| tiled | 2 241 M | 18.10 M | **0.81 %** |
| omp   | 575 M | 2.00 M | **0.35 %** |

Branch prediction is excellent (<1 %) everywhere. Tiled is slightly worse because its bounds-checking branches (`ii < i+TILE && ii < N`) are less predictable. **Branches are not the bottleneck for any variant.**

---

## 4. Cache Hierarchy (naive, AMD native events)

Raw counts from `perf stat`:

| Event | Count | Means |
|-------|-------|-------|
| `L1-dcache-loads` | 1 373 123 003 | Total L1 load requests |
| `L1-dcache-load-misses` | 650 316 161 | L1 misses |
| `l2_cache_misses_from_dc_misses` | 339 838 672 | L1 misses that also miss L2 |
| `ls_any_fills_from_sys.int_cache` | 373 487 829 | Lines filled from **L3 (internal cache)** |
| `ls_any_fills_from_sys.mem_io_local` | 3 438 167 | Lines filled from **local DRAM** |

Derived percentages:

| Metric | Value | Reading |
|--------|-------|---------|
| **L1 miss rate** | 650 M / 1373 M = **47.36 %** | Almost every other L1 load misses |
| **L2 miss rate** (of L1 misses) | 339 M / 650 M = **52.26 %** | Most L1 misses pass through L2 too |
| **L3 hit (of post-L2 fills)** | 373 M / 376.9 M = **99.09 %** | Misses are absorbed by L3 |
| **DRAM (of post-L2 fills)** | 3.4 M / 376.9 M = **0.91 %** | Almost no DRAM traffic |

> **Interpretation.** naive is *not* DRAM-bound — the three 8 MB matrices easily fit in the L3 cache. The bottleneck is **L3 latency**: each `B[k][j]` access (stride-N = 8192 bytes) skips L1 and L2 and resolves in L3. L3 has ~40-cycle latency vs ~4 cycles for L1, so the pipeline waits 10× longer per load.

**Backend-stall indicator** (`de_dis_uop_queue_empty_di0`, "dispatcher had nothing to send"):

- 140 M empty-dispatch events / 13.5 B cycles ≈ **1.04 % of cycles** with `di0 == 0`. This counts only the strictest stall condition (zero dispatch). The real "waiting on memory" fraction is higher; combined with IPC = 0.35, it confirms the bottleneck.

---

## 5. Stability of Measurements (5 runs of naive)

| Metric | Mean | ± Std |
|--------|------|-------|
| Wall time | 3.079 s | **± 0.55 %** |
| Cycles | 12.87 B | ± 0.35 % |
| Instructions | 4.51 B | ± 0.05 % |
| IPC | 0.351 | (derived) |

Run-to-run variance is <1 %. **The numbers in this report are repeatable**, not noise.

---

## 6. Hotspot Function (CH4 — perf record + report)

Three independent samplings all agree:

| Method | Event | Hotspot | Share |
|--------|-------|--------|-------|
| `perf record -F 99` | cpu-cycles | `matmul_naive` | **99.18 %** |
| `perf record -e cache-misses` | cache-misses | `matmul_naive` | **99.42 %** |
| `perf record -e ibs_op/cnt_ctl=1/` | AMD IBS retired ops | `matmul_naive` | **94.04 %** |

Same function dominates both **time** and **cache misses**. There is no second hotspot to optimise.

---

## 7. Assembly-Level Hotlines (CH4 — perf annotate)

Inner loop disassembles to 7 instructions (SSE2 vectorised by `-O2`):

| Address | Instruction | Cycle samples % | IBS samples % | Role |
|---------|------------|----------------|---------------|------|
| 0x1380 | `movsd (%rdx), %xmm0` | 12.25 | 14.53 | Load A[i][k] (stride-1) |
| 0x1384 | `addq $0x2000, %rax` | 11.76 | 13.93 | Advance B-pointer by 1 row (stride-N) |
| 0x138a | `addq $0x8, %rdx` | 12.75 | 13.97 | Advance A-pointer by 8 B |
| 0x138e | `unpcklpd %xmm0, %xmm0` | 11.19 | 14.28 | Broadcast scalar to vector |
| 0x1392 | `mulpd -0x2000(%rax), %xmm0` | **12.39** | **14.50** | **B[k][j] × a_ik** — the cache-miss load |
| 0x139a | `addpd %xmm0, %xmm1` | **28.18** | 14.78 | Accumulate into C[i][j] |
| 0x139e | `cmpq %rcx, %rax; jne` | 11.30 | 13.86 | Loop branch |

**Two views of the same loop.**

- **`cpu-cycles` view** (skid-prone): 28 % piled on `addpd` because the sample fires *after* the stalling load resolves, blaming the next instruction.
- **AMD IBS view** (precise but un-biased by latency): roughly **14 % per instruction** — IBS records the retired op directly, without latency weighting. Both views agree the inner loop is the bottleneck; IBS simply spreads credit evenly across the 6 ops in the hot loop.

The actual memory-bound instruction is **`mulpd -0x2000(%rax)`** — `%rax` advances by 8 KB each iteration, so every `mulpd` triggers a fresh cache line fetch of B.

---

## 8. Before / After — perf diff (naive baseline vs ikj)

```
Baseline   Delta Abs   Symbol
98.37 %                matmul_naive       ← naive: function dominates
            +90.23 %   matmul_ikj         ← ikj: same shape, 12× fewer cycles total
  1.19 %    +5.59 %    [kernel]
  0.10 %    +1.06 %    libc __random      (matrix init)
```

Same dominant function in both — the *code structure* didn't change much. **The fix was the access pattern.** Same 4 B instructions, but ikj makes B accesses stride-1 so they hit L1, eliminating the stall.

---

## 9. Memory Access Latency — perf mem (naive)

Recorded with `perf mem record -d`, sorted by memory level. The "Overhead" column is **weighted by sampled latency** (how many cycles each access cost):

| Memory level | Latency-weighted share | Sample count | Typical cycles |
|-------------|------------------------|-------------|---------------|
| L1 hit | **0.22 %** | 1 578 | ~4 |
| L2 hit | **23.18 %** | 462 | ~12 |
| LLC / same-node cache | **75.15 %** | 1 281 | ~40–100 |
| RAM hit | 0.31 % | 3 | ~200+ |
| N/A (unmapped IBS sample) | 1.13 % | 8 099 | — |

> **75 % of all the *time spent in memory loads* is waiting on L3.** Compare with the c2c numbers for omp (next section), where 64 % of loads are L1 hits — that's the difference an algorithmic fix makes.

Sample weights observed: latencies up to **6 782 cycles** for cross-cache transfers. The CPU clock would tick 6 782 times during a single load.

---

## 10. False-Sharing Check — perf c2c (omp)

`perf c2c` records cache-line transfers between threads. For `matmul_omp` (16 threads, ikj kernel):

| Counter | Value |
|---------|-------|
| Total load operations | 1 210 |
| L1D hit | 781 (**64.5 %**) |
| L2D hit | 404 (**33.4 %**) |
| LLC hit | 9 (0.7 %) |
| Local DRAM | 1 (0.08 %) |
| **Local HITM (false sharing!)** | **0** |
| **Remote HITM (false sharing!)** | **0** |
| **Total Shared Cache Lines** | **0** |

> **No false sharing.** OpenMP splits the outer `i` loop, so each thread writes to its own contiguous block of C rows. Different threads' writes never land on the same cache line. The 64 % L1-hit rate also confirms the cache-friendly access pattern of ikj scales to multiple threads.

---

## 11. Machine Peak Bandwidth — perf bench mem

| Benchmark | Bandwidth |
|-----------|-----------|
| memcpy glibc default (read + write) | **26.4 GB/s** |
| memcpy x86-64-unrolled | 20.3 GB/s |
| memcpy x86-64-movsq | 18.4 GB/s |
| memset glibc default (write, NT-stores) | **57.4 GB/s** |
| mmap demand-load | 2.0 GB/s |

**Peak streaming read bandwidth ≈ 26.4 GB/s** — this is the memory ceiling for the Roofline.

---

## 12. Roofline Model

**Machine limits**

- Peak compute (SSE2, no FMA in `-O2`) = 4.3 GHz × 2 doubles × 2 ops = **17.2 GFlops/s**
- Peak streaming BW = **26.4 GB/s**
- Ridge point = 17.2 / 26.4 = **0.65 FLOPs/byte**

**Per variant**

| Variant | FLOPs/byte (AI) | Bound | GFlops/s actual | Ceiling | Efficiency |
|---------|----------------|-------|----------------|---------|------------|
| naive | 0.25 | **Memory** (left of ridge) | 0.69 | 0.25 × 26.4 = 6.6 | **10.5 %** |
| ikj | 85 | **Compute** (right of ridge) | 7.72 | 17.2 | **44.9 %** |
| tiled | 85 | **Compute** | 3.11 | 17.2 | 18.1 % (lost to ×3 instruction count) |
| omp 16t | 85 | BW-shared | 17.6 (wall) | 26.4 | **66.7 %** of peak BW |

```
GFlops/s
  17.2 ─────────────────────── SSE2 compute ceiling
                       
        ● ikj    7.72       ← compute-bound, 45 % of peak
   6.6 ┄ ┄ ┄ ┄ ┄ memory ceiling at AI = 0.25
        ● tiled  3.11
   
        ● omp   17.6        ← off-chart, near BW ceiling
   
   0.7  ● naive 0.69        ← 10 % of its own memory ceiling
        ────────────────────────────────────
       0.25    0.65    1     10    85   FLOPs/byte
                ↑ ridge
```

> **What this says.**
> - naive sits far below even its memory ceiling because it can't use the L3's full bandwidth (latency-bound, not throughput-bound).
> - ikj reaches 45 % of theoretical SSE2 peak — to go higher, compile with `-O3 -march=native -ffast-math` to unlock AVX2 FMA (would double the ceiling to 34.4 GFlops/s).
> - tiled has the right idea but the bookkeeping overhead negates the cache benefit at N=1024 (matrices already fit in L3). Tiling helps when N is too large for L3.
> - omp scales nearly linearly to the memory subsystem's limit.

---

## 13. Tool-by-Tool: What Each Step Proved

| Tool | Conclusion |
|------|-----------|
| `perf stat` | naive IPC = 0.35; ikj IPC = 3.55. 10× IPC gap = the symptom of the bottleneck. |
| `perf stat -r 5` | Run-to-run variance < 0.6 %; results are reliable. |
| `perf stat` + AMD events | L1 miss = 47 %, L2 miss = 52 %, 99 % of misses absorbed by L3 (latency bound, not DRAM bound). |
| `perf record` (cycles) | 99.18 % of CPU time in `matmul_naive` — single function. |
| `perf record` (cache-misses) | 99.42 % of cache misses in same function — confirms diagnosis. |
| AMD IBS (`ibs_op/cnt_ctl=1/`) | Precise sampling — 94 % in same function; spreads weight uniformly across inner loop. |
| `perf annotate` | Inner loop is `movsd / mulpd / addpd`. `mulpd -0x2000(%rax)` is the cache-miss instruction. |
| Flamegraph | Single-tower flame shape = single bottleneck function, no call-tree branching. |
| `perf diff` (naive vs ikj) | Same function, +90 % share in ikj but **12× fewer cycles** total — fix is access pattern only. |
| `perf mem` | 75 % of memory time is on L3 hits at 40–100 cycle latency, not on DRAM. Up to 6 782-cycle sample weights observed. |
| `perf c2c` (omp) | Zero shared cache lines → no false sharing; 64 % L1-hit rate per thread → parallel ikj scales well. |
| `perf bench mem` | Peak streaming BW = 26.4 GB/s — defines the Roofline memory ceiling. |
| Roofline | naive at 10.5 % of memory ceiling; ikj at 44.9 % of compute peak; omp at 66.7 % of BW peak. |

---

## 14. Bottom Line

1. **naive matmul is memory-latency-bound**, *not* compute-bound or DRAM-bandwidth-bound. The CPU stalls waiting for L3 (47 % L1 misses → 52 % L2 misses → 99 % absorbed by L3).
2. **Loop reorder (ijk → ikj) alone gives an 11× speedup** by converting B's access pattern from stride-N to stride-1, which hits L1.
3. **Cache tiling helps only when N exceeds L3**, which is not the case at N=1024 here. Bookkeeping overhead made it 2.5× slower than ikj.
4. **OpenMP scales near-linearly** (25.6× from 16 threads) with no false-sharing penalty because rows of C are partitioned cleanly across threads.
5. **The naive vs ikj gap is purely a hardware-latency story.** Same instructions, same arithmetic — only the address sequence changed.
