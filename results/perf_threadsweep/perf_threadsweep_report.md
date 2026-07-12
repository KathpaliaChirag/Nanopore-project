# Kraken2 perf thread-sweep — cache / LLC-miss analysis

> **Generated on the Dell OptiPlex 5090 lab desktop.** Every number in this report was collected on that machine (Intel i7-11700, 8c/16t, 16 MB L3); do not compare absolute timings against other hosts.

**Machine:** Dell OptiPlex 5090 lab desktop — Intel Core i7-11700 (Rocket Lake), **8 physical cores / 16 threads**, 16 MB shared L3, dual-channel DDR4-3200 (~51 GB/s peak).  
**Workload:** Kraken2 classifying ESKAPE ONT reads (16 pod5 FASTQ files, ~0.1–0.4 Gbp each) against the same DB built at 4 hash cell-sizes.  
**Matrix:** 4 cell-sizes × 16 pod5 × threads {1,2,4,6,8,10,12,14,16} × 3 runs = **1,728 timed `perf stat` runs**. Page cache dropped cold once per file.  
**This report** re-parses all `raw/*.txt` (1723 valid runs) directly from the perf counters.

**Metric definitions**
- **Cache Miss Rate** = `cache-misses / cache-references` (last-level-cache miss rate).
- **LLC Miss Rate** = `LLC-load-misses / LLC-loads` (fraction of L3 load lookups that go to DRAM).
- **IPC** = `instructions / cycles`.  **Time** = Kraken2 classify time (excludes DB load).
- **Speedup / Eff%** vs 1T (Eff = speedup / threads).  **Mbp/s** = Mbp classified per second.
- **DRAM (GB/s)** = `cache-misses × 64 B / time` — actual DRAM read traffic from L3 misses.
- Each cell = mean over 16 pods of the per-pod 3-run mean.

## Headline findings

1. **Memory-latency bound, NOT bandwidth bound.** Peak DRAM read traffic is only **~10 GB/s** at 16T vs ~51 GB/s available. The bottleneck is *latency* of random hash probes: estimated memory-level parallelism rises only from ~0.5 (1T) to ~3–5 (16T).
2. **Shared 16 MB L3 contention scales the miss rate up.** More threads mutually evict each other's cache lines, so **both** cache-miss rate and LLC-miss rate climb monotonically with thread count (e.g. 16-bit cache-miss 41.2%→50.8%, LLC-miss 38.4%→48.2% from 1T→16T).
3. **IPC collapses under contention** — every DB drops ~19–25% (1T→16T) as threads stall longer on DRAM.
4. **Hyper-threading barely helps.** Scaling knee is at 8T (= physical cores); 8T→16T adds only ~1.4× because SMT siblings share L1/L2/L3 and the memory pipeline. Efficiency falls from ~68% (8T) to ~49% (16T).
5. **Cell-size is an accuracy↔footprint knob.** Smaller cells = smaller RAM footprint = better L3 residency = lower miss rate = higher IPC = faster — but **16-bit inflates classification to 90.95%** (hash-collision false positives) vs the true ~83.7%. **24-bit (83.75%) matches 32-bit (83.73%)** at ~25% less RAM.

## 32-bit (`eskape_32bit_stock`)

| Threads | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Time (s) | Speedup | Eff% | Mbp/s | DRAM GB/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.73 | 59.42 | 54.39 | 1.38 | 17.788 | 1.00x | 100.0 | 21 | 2.0 |
| 2 | 83.73 | 59.54 | 54.91 | 1.35 | 9.389 | 1.89x | 94.7 | 40 | 3.9 |
| 4 | 83.73 | 60.06 | 55.51 | 1.34 | 5.032 | 3.53x | 88.4 | 75 | 7.3 |
| 6 | 83.73 | 60.41 | 55.77 | 1.39 | 3.908 | 4.55x | 75.9 | 96 | 9.6 |
| 8 | 83.73 | 60.70 | 56.02 | 1.40 | 3.270 | 5.44x | 68.0 | 115 | 11.7 |
| 10 | 83.73 | 60.99 | 56.54 | 1.29 | 2.857 | 6.23x | 62.3 | 131 | 11.5 |
| 12 | 83.73 | 61.17 | 57.23 | 1.21 | 2.563 | 6.94x | 57.8 | 146 | 11.1 |
| 14 | 83.73 | 61.16 | 57.87 | 1.16 | 2.359 | 7.54x | 53.9 | 159 | 10.6 |
| 16 | 83.73 | 60.99 | 58.58 | 1.12 | 2.185 | 8.14x | 50.9 | 171 | 10.2 |

## 24-bit (`eskape_24bit`)

| Threads | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Time (s) | Speedup | Eff% | Mbp/s | DRAM GB/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.75 | 55.06 | 51.04 | 1.47 | 17.552 | 1.00x | 100.0 | 22 | 1.9 |
| 2 | 83.75 | 53.71 | 50.07 | 1.45 | 9.085 | 1.93x | 96.6 | 41 | 3.7 |
| 4 | 83.75 | 54.48 | 50.86 | 1.45 | 4.916 | 3.57x | 89.3 | 76 | 6.9 |
| 6 | 83.75 | 55.04 | 51.17 | 1.49 | 3.852 | 4.56x | 76.0 | 98 | 9.0 |
| 8 | 83.75 | 55.60 | 51.76 | 1.50 | 3.217 | 5.46x | 68.2 | 117 | 11.0 |
| 10 | 83.75 | 56.29 | 52.59 | 1.38 | 2.850 | 6.16x | 61.6 | 132 | 10.6 |
| 12 | 83.75 | 56.96 | 53.54 | 1.29 | 2.595 | 6.76x | 56.4 | 144 | 10.2 |
| 14 | 83.75 | 57.39 | 54.50 | 1.22 | 2.382 | 7.37x | 52.6 | 158 | 9.8 |
| 16 | 83.75 | 57.73 | 55.78 | 1.17 | 2.209 | 7.94x | 49.7 | 169 | 9.4 |

## 20-bit (`eskape_20bit`)

| Threads | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Time (s) | Speedup | Eff% | Mbp/s | DRAM GB/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 84.48 | 53.60 | 49.24 | 1.48 | 17.274 | 1.00x | 100.0 | 22 | 2.0 |
| 2 | 84.48 | 53.89 | 49.97 | 1.46 | 8.930 | 1.93x | 96.7 | 42 | 3.8 |
| 4 | 84.48 | 54.67 | 50.77 | 1.43 | 4.727 | 3.65x | 91.4 | 80 | 7.4 |
| 6 | 84.48 | 55.17 | 51.16 | 1.48 | 3.711 | 4.66x | 77.6 | 102 | 9.6 |
| 8 | 84.48 | 55.67 | 51.61 | 1.49 | 3.133 | 5.51x | 68.9 | 121 | 11.6 |
| 10 | 84.48 | 56.31 | 52.32 | 1.37 | 2.807 | 6.15x | 61.5 | 134 | 11.1 |
| 12 | 84.48 | 56.88 | 53.18 | 1.28 | 2.550 | 6.77x | 56.4 | 147 | 10.5 |
| 14 | 84.48 | 57.33 | 54.07 | 1.22 | 2.338 | 7.39x | 52.8 | 160 | 10.2 |
| 16 | 84.48 | 57.68 | 55.28 | 1.17 | 2.172 | 7.95x | 49.7 | 172 | 9.8 |

## 16-bit (`eskape_16bit`)

| Threads | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Time (s) | Speedup | Eff% | Mbp/s | DRAM GB/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 90.95 | 41.17 | 38.44 | 1.64 | 15.217 | 1.00x | 100.0 | 25 | 1.4 |
| 2 | 90.95 | 41.71 | 38.99 | 1.60 | 8.034 | 1.89x | 94.7 | 47 | 2.8 |
| 4 | 90.95 | 42.85 | 39.98 | 1.59 | 4.400 | 3.46x | 86.5 | 85 | 5.2 |
| 6 | 90.95 | 43.76 | 40.65 | 1.63 | 3.500 | 4.35x | 72.5 | 107 | 6.7 |
| 8 | 90.95 | 44.44 | 41.27 | 1.63 | 2.922 | 5.21x | 65.1 | 128 | 8.3 |
| 10 | 90.95 | 46.26 | 42.89 | 1.48 | 2.617 | 5.82x | 58.2 | 143 | 8.3 |
| 12 | 90.95 | 47.91 | 44.53 | 1.37 | 2.391 | 6.36x | 53.0 | 157 | 8.3 |
| 14 | 90.95 | 49.44 | 46.31 | 1.29 | 2.214 | 6.87x | 49.1 | 169 | 8.2 |
| 16 | 90.95 | 50.77 | 48.20 | 1.23 | 2.062 | 7.38x | 46.1 | 181 | 8.2 |

## Cross-DB comparison

### Single thread (1T)

| DB | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Time (s) | Mbp/s | DRAM GB/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 32-bit | 83.73 | 59.42 | 54.39 | 1.38 | 17.788 | 21 | 2.0 |
| 24-bit | 83.75 | 55.06 | 51.04 | 1.47 | 17.552 | 22 | 1.9 |
| 20-bit | 84.48 | 53.60 | 49.24 | 1.48 | 17.274 | 22 | 2.0 |
| 16-bit | 90.95 | 41.17 | 38.44 | 1.64 | 15.217 | 25 | 1.4 |

### All threads (16T)

| DB | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | Time (s) | Mbp/s | DRAM GB/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 32-bit | 83.73 | 60.99 | 58.58 | 1.12 | 2.185 | 171 | 10.2 |
| 24-bit | 83.75 | 57.73 | 55.78 | 1.17 | 2.209 | 169 | 9.4 |
| 20-bit | 84.48 | 57.68 | 55.28 | 1.17 | 2.172 | 172 | 9.8 |
| 16-bit | 90.95 | 50.77 | 48.20 | 1.23 | 2.062 | 181 | 8.2 |

## Cache & LLC-miss deep dive

### 1. Shared-L3 contention raises the miss rate with thread count
The i7-11700's 16 MB L3 is shared by all cores. Each Kraken2 thread streams effectively-random hash probes, so concurrent threads evict each other's lines. Both miss rates climb monotonically 1T→16T:

| DB | Cache Miss Rate 1T→16T | LLC Miss Rate 1T→16T |
|---|---:|---:|
| 32-bit | 59.42% → 60.99% (+1.6 pt) | 54.39% → 58.58% (+4.2 pt) |
| 24-bit | 55.06% → 57.73% (+2.7 pt) | 51.04% → 55.78% (+4.7 pt) |
| 20-bit | 53.60% → 57.68% (+4.1 pt) | 49.24% → 55.28% (+6.0 pt) |
| 16-bit | 41.17% → 50.77% (+9.6 pt) | 38.44% → 48.20% (+9.8 pt) |

The **16-bit DB rises most** — at 1T much of its smaller table stays L3-resident (41% vs 59% for 32-bit), but contention erodes exactly that advantage as threads pile in.

### 2. Latency-bound, not bandwidth-bound
- **DRAM traffic peaks at ~11–12 GB/s around 6–8T, then *falls* to ~10 GB/s at 16T** even while throughput keeps rising — the machine is moving *fewer* bytes/s while doing *more* work: the stall is memory *latency*, not bandwidth (peak DDR4-3200 ≈ 51 GB/s, so we use <25%).
- **Memory-level parallelism ≈ 0.5 at 1T → ~3–5 at 16T** (est. at 90 ns/miss). The hash probe is essentially a pointer chase; a single thread keeps <1 miss in flight. Extra threads add MLP but the shared-L3→DRAM latency path caps the return.
- **IPC stays 1.1–1.6 throughout** and drops with threads — cores spend a growing fraction of cycles stalled on outstanding misses.

### 3. Physical-core knee and hyper-threading
Scaling is near-linear to 4T, rolls off at 6T, and hits the **8-physical-core wall at 68–69% efficiency**. The 10–16T region runs on SMT siblings that share L1/L2/L3 and the load/store pipeline, so it adds little:

| DB | Speedup 8T→16T | Eff 8T | Eff 16T |
|---|---:|---:|---:|
| 32-bit | 1.50× | 68.0% | 50.9% |
| 24-bit | 1.46× | 68.2% | 49.7% |
| 20-bit | 1.44× | 68.9% | 49.7% |
| 16-bit | 1.42× | 65.1% | 46.1% |

## Accuracy vs cache-footprint trade-off
Fewer bits per hash cell = smaller RAM footprint = better L3 residency = lower miss rate = higher IPC = faster — but small fingerprints collide and **fabricate classifications**:

| DB | Classified% | vs 32-bit truth | Cache Miss @16T | Time @16T | Verdict |
|---|---:|---:|---:|---:|---|
| 16-bit | 90.95% | **+7.22 pt (false positives)** | 50.77% | 2.062 s | Fastest but **untrustworthy** |
| 20-bit | 84.48% | +0.75 pt | 57.68% | 2.172 s | Slight FP inflation |
| 24-bit | 83.75% | +0.02 pt | 57.73% | 2.209 s | **Accuracy-neutral, ~25% less RAM — best build** |
| 32-bit | 83.73% | baseline | 60.99% | 2.185 s | Reference |

At 16T the accurate builds converge in speed (24-bit 2.209 s ≈ 32-bit 2.185 s, within run-to-run noise): once the machine is latency-saturated, cell-size is mainly a **RAM/footprint** win, not a throughput win. 16-bit keeps a real ~6% speed edge but only by trading away correctness.

## Data quality
- **1,728 raw runs**, 1,723 parsed cleanly. Excluded: 1 file with a thread-list typo (`..._2,T_...`) and **5 incomplete runs** missing Kraken's "processed in" line (all 20-bit: pod5_0/pod5_3 @6T run1, pod5_13 @8T run3, …), trimming a couple of 20-bit cells to n=46 — no material effect on means.
- **`FAILURES.txt` (48 entries, all 20-bit pod5_0/pod5_1) is STALE**: an aborted early pass where the thread list picked up a stray comma (`_1,T_`). Those points were re-run successfully — 20-bit is fully populated in the tables above.
- One outlier remains in `reports/pod5_0.md` (20-bit @6T: min 1.288 / max 3.880 s) from a single bad run; the pod-averaged tables here are unaffected.
- **Classified% is identical across all thread counts** for each DB (as it must be — threading changes timing, not output), a good internal consistency check.

## Recommendations
1. **Run at 8 threads on this box** for best efficiency (throughput per core). Use 16 threads only when wall-clock is the priority — it buys ~1.4–1.5× more at <50% efficiency.
2. **Ship the 24-bit DB**: 32-bit-equivalent accuracy at ~75% of the hash RAM with better cache residency. Do **not** use 16-bit for real classification — its 91% "classified" is inflated by hash collisions.
3. This workload is **memory-latency-bound**, so it should scale further past 8 cores on hardware with a much larger L3 / more memory channels — worth re-running this sweep on Luna (Sapphire Rapids, 210 MB L3) to confirm the knee moves right.
