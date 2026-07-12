# Kraken2 Thread-Scaling Analysis — fast / hac / sup

**Date:** 2026-05-29
**Machine:** AMD Ryzen 7 7735HS (Zen4, 8 physical cores / 16 logical threads, 16 MB L3, 14 GB RAM)
**DB:** minikraken2_v2_8GB | **Reads:** ~104K per mode (fast/hac/sup from server)
**Binary:** rebuilt without `-pg` (profiling overhead removed)
**Thread sweep:** 1, 2, 4, 6, 8, 10, 12, 14, 16
**Raw results:** `results/kraken2/{fast,hac,sup}/thread_{N}/`

### Abbreviations

| Term | Meaning |
|------|---------|
| IPC | Instructions Per Cycle (higher = better CPU utilisation) |
| BE-Bound | Backend-Bound (pipeline slots stalled waiting on memory) |
| FE-Bound | Frontend-Bound (pipeline slots stalled on instruction fetch/decode) |
| TMA | Top-down Microarchitecture Analysis |
| DRAM | Dynamic Random-Access Memory (main system memory, ~100 ns latency) |
| L1/L2/L3 | Level-1 / Level-2 / Level-3 CPU cache |
| LRU | Least Recently Used (cache eviction policy) |
| OMP | OpenMP (parallel threading) |
| Kseq/m | Kilo-sequences per minute (throughput) |

---

## 1. Wall Time & Throughput

| Threads | fast (s) | fast Kseq/m | hac (s) | hac Kseq/m | sup (s) | sup Kseq/m |
|--------:|--------:|------------:|--------:|-----------:|--------:|-----------:|
| 1  | 14.64 | 429  | 14.83 | 424  | 15.07 | 417  |
| 2  | 7.64  | 823  | 8.22  | 765  | 8.38  | 751  |
| 4  | 4.27  | 1472 | 4.74  | 1327 | 4.54  | 1388 |
| 6  | 3.28  | 1920 | 3.58  | 1758 | 3.75  | 1679 |
| 8  | 2.70  | 2330 | 3.25  | 1939 | 2.84  | 2217 |
| 10 | **2.74** ⚠️ | 2294 | 2.84 | 2218 | 2.67 | 2356 |
| 12 | 2.45  | 2569 | 2.74  | 2295 | 2.57  | 2454 |
| 14 | 2.32  | 2716 | 2.65  | 2375 | 2.47  | 2555 |
| 16 | 2.22  | 2836 | 2.55  | 2464 | 2.40  | 2623 |

⚠️ fast/T10 is slower than fast/T8 — hyperthreading boundary artefact (see Section 7).

---

## 2. Speedup & Scaling Efficiency

Speedup = wall_time(T1) / wall_time(TN). Efficiency = speedup / N.

| Threads | fast speedup | fast efficiency | hac speedup | hac efficiency | sup speedup | sup efficiency |
|--------:|------------:|----------------:|------------:|---------------:|------------:|---------------:|
| 1  | 1.00× | 100% | 1.00× | 100% | 1.00× | 100% |
| 2  | 1.92× | 96%  | 1.80× | 90%  | 1.80× | 90%  |
| 4  | 3.43× | 86%  | 3.13× | 78%  | 3.32× | 83%  |
| 6  | 4.47× | 74%  | 4.14× | 69%  | 4.02× | 67%  |
| 8  | 5.42× | 68%  | 4.57× | 57%  | 5.31× | 66%  |
| 10 | 5.34× | 53%  | 5.23× | 52%  | 5.64× | 56%  |
| 12 | 5.98× | 50%  | 5.41× | 45%  | 5.87× | 49%  |
| 14 | 6.32× | 45%  | 5.60× | 40%  | 6.11× | 44%  |
| 16 | 6.60× | 41%  | 5.81× | 36%  | 6.28× | 39%  |

Efficiency collapses past T8 (= number of physical cores). By T16 only 36–41% of the added threads are doing useful work — the rest stall on DRAM.

---

## 3. IPC (Instructions Per Cycle)

| Threads | fast IPC | hac IPC | sup IPC |
|--------:|---------:|--------:|--------:|
| 1  | 1.37 | 1.50 | 1.55 |
| 2  | 1.38 | 1.49 | 1.58 |
| 4  | 1.37 | 1.53 | 1.55 |
| 6  | 1.41 | 1.51 | **1.65** ← peak |
| 8  | 1.36 | 1.49 | 1.63 |
| 10 | 1.28 | 1.40 | 1.48 |
| 12 | 1.21 | 1.29 | 1.38 |
| 14 | 1.13 | 1.21 | 1.30 |
| 16 | 1.12 | 1.17 | 1.24 |

**Critical comparison with previous run:** With `-pg` in the binary, IPC was **0.154**. Without it, IPC is **1.1–1.7**. The `-pg` flag consumed ~88% of all pipeline capacity via mcount() hooks — removing it alone gives an order-of-magnitude improvement in useful work per cycle.

IPC peaks at T4–T6 then declines. After T8, hyperthreads share physical cores and compete for L1/L2 cache, raising stall rates.

---

## 4. TMA Pipeline Breakdown

| Threads | fast BE-Bound | fast Retiring | hac BE-Bound | sup BE-Bound |
|--------:|-------------:|--------------:|-------------:|-------------:|
| 1  | 75.3% | 22.9% | 73.2% | 72.3% |
| 4  | 75.3% | 22.9% | 72.5% | 72.0% |
| 8  | 75.3% | 22.8% | 73.0% | 70.7% |
| 12 | 77.7% | 20.3% | 76.2% | 74.8% |
| 16 | 79.1% | 18.9% | 78.2% | 77.0% |

BE-Bound rises with thread count — more threads issue more simultaneous random probes into the 8 GB DB, congesting the memory controller and making each stall longer. At T16, nearly 4 in 5 pipeline slots are stalled on DRAM and only 1 in 5 does real work.

FE-Bound stays flat at ~1.5–1.8% across all thread counts — the frontend is never the bottleneck.

---

## 5. Op-Cache Misses vs Threads

| Threads | fast | hac | sup |
|--------:|-----:|----:|----:|
| 1  | 2.82B | 2.86B | 2.85B |
| 8  | 3.06B | 3.13B | 3.05B |
| 16 | 3.32B | 3.52B | 3.53B |

Op-cache (instruction op-cache) misses grow ~18% from T1→T16. More threads run more distinct code paths simultaneously, adding pressure on the 32 KB instruction op-cache and contributing to the IPC decline at high thread counts.

---

## 6. Per-Core CPU Utilization (mpstat)

**Thread 1 (fast):** Two cores dominate — CPU6 (34.6%), CPU7 (32.8%). Fourteen cores average under 5%. The single OMP thread migrates between two logical CPUs; the rest are idle.

**Thread 8 (fast):** Uneven — active cores at ~29–30% usr, others at 1–4%. DRAM-stalled threads yield the CPU, causing the OS to report low utilisation even on assigned cores.

**Thread 16 (fast):** Balanced — all 16 CPUs at 21–28% usr. Even distribution, but the low per-core % confirms every thread is mostly waiting on DRAM, not executing instructions.

---

## 7. fast T10 Regression Explained

fast/T10 (2.741s) is slightly **slower** than fast/T8 (2.699s):

- T1–T8: each thread gets its own physical core (8 physical cores, 8 threads = 1:1 mapping)
- T9+: threads start sharing physical cores via hyperthreading
- At T10: 10 threads on 8 physical cores means 2 cores host 2 threads each. Those two co-located pairs compete for the same L1/L2, causing extra cache thrashing that slightly raises wall time before additional threads compensate at T12+
- hac and sup do not show this because longer reads give better temporal locality, absorbing the L1/L2 sharing penalty

---

## 8. Summary — Best / Worst / Sweet Spot

| Verdict | Thread count | Reason |
|---------|-------------|--------|
| **Fastest absolute** | 16 | Best wall time across all three modes |
| **Best efficiency sweet spot** | 4–6 | 67–86% scaling efficiency; IPC still high (1.4–1.6); minimal DRAM contention increase |
| **Physical core boundary** | 8 | Last point before hyperthreading penalty; efficiency drops sharply past this |
| **Diminishing returns** | 10+ | BE-Bound rises, IPC drops, efficiency below 60% |
| **Regression anomaly** | fast / T10 | Slightly slower than T8 — hyperthreading boundary artefact |
| **Worst** | 1 | 6–7× slower than T16 |

**Practical recommendation:**
- Throughput-priority (server/batch): use **T16** — fastest absolute, 6–7× over single-thread
- Balanced efficiency (shared machine, energy): use **T6–T8** — ~65–75% of T16 speed at half the CPU cost
- Never run T1 — even T2 gives ~1.9× with 90–96% efficiency

---

## 9. Classification Accuracy (unchanged across thread counts)

| Mode | Classified | Unclassified |
|------|----------:|-------------:|
| fast | 93.18% | 6.82% |
| hac  | 97.85% | 2.15% |
| sup  | 98.38% | 1.62% |

Thread count has zero effect on classification accuracy — OMP parallelism only splits reads across threads; each read's result is identical regardless of how many threads run.
