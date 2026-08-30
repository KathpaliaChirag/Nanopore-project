# Centrifuge vs Kraken2 perf thread-sweep — cache / LLC-miss analysis

> **Generated on the Dell OptiPlex 5090 lab desktop.** Every number in this report was collected on that machine (Intel i7-11700, 8c/16t, 16 MB L3); do not compare absolute timings against other hosts.

**Machine:** Dell OptiPlex 5090 lab desktop — Intel Core i7-11700 (Rocket Lake), **8 physical cores / 16 threads**, 16 MB shared L3, dual-channel DDR4-3200 (~51 GB/s peak), 31 GiB RAM, 1 NUMA node.
**Workload:** Centrifuge classifying ESKAPE ONT reads (16 pod5 FASTQ files, 1,872,777 reads, 6,036.16 Mbp total) against `centrifuge_eskape/cf_base`.
**Matrix:** 16 pod5 × threads {1,2,4,6,8,10,12,14,16} × 3 runs = **432 timed `perf stat` runs**, zero failures (see `FAILURES.txt`). Page cache dropped cold once per file.
**This report** re-parses all `raw/*_perf.txt` (432 valid runs) directly from the perf counters. Kraken2 columns re-parsed from `kraken2opti/results/perf_threadsweep/raw/eskape_32bit_stock_*` (432 valid runs).

**Metric definitions**
- **Cache Miss Rate** = `cache-misses / cache-references` (last-level-cache miss rate).
- **LLC Miss Rate** = `LLC-load-misses / LLC-loads` (fraction of L3 load lookups that go to DRAM).
- **IPC** = `instructions / cycles`.  **Time** = wall-clock `seconds time elapsed`.
- **GHz** = `cycles / elapsed / threads` — effective per-thread clock, revealing turbo behaviour.
- **Speedup / Eff%** vs 1T (Eff = speedup / threads).  **Mbp/s** = Mbp classified per second.
- **DRAM (GB/s)** = `cache-misses × 64 B / time` — actual DRAM read traffic from L3 misses.
- **sys%** = `sys / (user + sys)` CPU time — kernel share, a futex/lock-contention indicator.
- Each cell = mean over 16 pods of the per-pod 3-run mean.

## Setup

| | Centrifuge | Kraken2 |
|---|---|---|
| Version / build | 1.0.5, GCC 11.4, `-O3 -msse2 -g3` | 2.x, `eskape_32bit_stock` |
| Database | `centrifuge_eskape/cf_base` — FM-index, 21 MB | `eskape_32bit_stock/hash.k2d` — 47 MB |
| Reference | 6 ESKAPE genomes, 17 seqs, 28,061,107 bp | **identical** (same `eskape_cs/library`) |
| Reads | 16 pod5 files, 1,872,777 reads, 6,036.16 Mbp | **identical** |
| Counters | `cache-misses, cache-references, LLC-loads, LLC-load-misses, instructions, cycles` | **identical** |

The reference sets are byte-identical: `build_cellsize_dbs.sh` built the Kraken2 DB from the same library, and both builds report 17 sequences / 28,061,107 bp. This is a true like-for-like comparison, not an approximation. Read counts agree three independent ways — Kraken2's own `N sequences (M Mbp) processed` line, a direct `wc -l` on the local FASTQ copies, and Centrifuge's `class/*_class.txt` totals.

**One methodological difference to keep in the record.** The Kraken2 captures (June) used root `drop_caches`, evicting the whole system cache. This sweep had no root available, so it used targeted `posix_fadvise(POSIX_FADV_DONTNEED)` on the reads *and* the index (`scripts/drop_file_cache.py`). Both drop once per file, so run 1 is cold and runs 2–3 warm in each case. The eviction is narrower here but covers everything either tool reads. Verified in the data: at 1T run 1 is the slowest of the three in **16/16** files; at every other thread count the slowest run is randomly distributed. The cold-start eviction did what it claims.

## Headline findings

1. **Centrifuge peaks at 8 threads, on every single file — 16/16, not "mostly".** Past 8T wall time degrades 41%. The peak lands exactly at the physical core count, so the regression begins precisely where hyperthreading starts. Kraken2 on the same hardware improves monotonically to 7.92x at 16T.
2. **The turbo clock drop is common-mode and must be removed before comparing scaling.** Effective clock falls 4.87→3.07 GHz (0.63x) for Centrifuge and 4.77→2.95 GHz (0.62x) for Kraken2 — near-identical, because it is a property of the *machine*, not the tool. Raw speedup numbers understate both tools. After removing it, the divergence is stark: at 16T Kraken2 still achieves **80%** of its clock-adjusted ceiling, Centrifuge only **32%**.
3. **Centrifuge's residual loss is wasted instructions, not just cache pressure.** It executes **+69%** more instructions at 16T than at 1T to do the same work; Kraken2's count is flat (**+1.7%**). The work is being multiplied, not divided.
4. **Kernel time is the smoking gun.** Centrifuge's sys share rises 0.4% → 9.4% → **39.9%** (1/8/16T) — at 16T, 56 of 140 CPU-seconds are in the kernel. Kraken2 stays at 1.0% → 2.3%. This points at **futex contention (spin-then-park)**, not pure userspace spinning, and is more actionable than the instruction count alone.
5. **Centrifuge is compute-bound, Kraken2 is memory-bound.** LLC miss rate 2.71% vs 54.39% at 1T; IPC 2.51 vs 1.38; DRAM traffic 0.2 vs 2.0 GB/s. **Yet Kraken2 wins on wall time at every thread count**, because it executes 2.9x fewer instructions. Better cache behaviour does not rescue 3x the work.
6. **This contradicts the Week-1 plan's Step 5 hypothesis**, which predicted *worse* cache behaviour for Centrifuge on FM-index locality grounds. Measured across 432 runs the opposite holds at this database size, on both rate and absolute count.

## Centrifuge (`centrifuge_eskape`)

| Threads | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | GHz | Time (s) | Speedup | Eff% | Mbp/s | DRAM GB/s | sys% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 85.30 | 2.15 | 2.71 | 2.51 | 4.87 | 28.237 | 1.00x | 100.0 | 14 | 0.2 | 0.4 |
| 2 | 85.30 | 2.15 | 2.74 | 2.50 | 4.70 | 14.887 | 1.90x | 94.8 | 26 | 0.3 | 1.3 |
| 4 | 85.30 | 2.63 | 3.15 | 2.47 | 4.45 | 8.154 | 3.46x | 86.6 | 47 | 0.7 | 3.5 |
| 6 | 85.30 | 3.09 | 3.55 | 2.45 | 3.55 | 7.057 | 4.00x | 66.7 | 54 | 1.0 | 6.2 |
| **8** | 85.30 | 3.55 | 3.96 | 2.40 | 3.20 | **6.257** | **4.51x** | 56.4 | **61** | 1.4 | 9.4 |
| 10 | 85.30 | 4.16 | 4.49 | 2.00 | 3.17 | 6.595 | 4.28x | 42.8 | 58 | 1.3 | 16.5 |
| 12 | 85.30 | 4.66 | 5.07 | 1.71 | 3.14 | 7.170 | 3.94x | 32.8 | 53 | 1.2 | 24.9 |
| 14 | 85.30 | 5.09 | 5.56 | 1.50 | 3.11 | 7.972 | 3.54x | 25.3 | 47 | 1.1 | 33.2 |
| 16 | 85.30 | 5.59 | 6.23 | 1.35 | 3.07 | 8.823 | 3.20x | 20.0 | 43 | 0.9 | 39.9 |

## Kraken2 32-bit (`eskape_32bit_stock`)

Re-parsed from `results/perf_threadsweep/raw/`. Same six ESKAPE genomes, same reads, same counters. Note these were taken with root `drop_caches` (whole-system) rather than the targeted `posix_fadvise` eviction used above.

| Threads | Classified% | Cache Miss Rate% | LLC Miss Rate% | IPC | GHz | Time (s) | Speedup | Eff% | Mbp/s | DRAM GB/s | sys% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 83.73 | 59.42 | 54.39 | 1.38 | 4.77 | 17.830 | 1.00x | 100.0 | 21 | 2.0 | 1.0 |
| 2 | 83.73 | 59.54 | 54.91 | 1.35 | 4.63 | 9.435 | 1.89x | 94.5 | 40 | 3.8 | 1.2 |
| 4 | 83.73 | 60.06 | 55.51 | 1.34 | 4.31 | 5.082 | 3.51x | 87.7 | 74 | 7.2 | 1.4 |
| 6 | 83.73 | 60.40 | 55.77 | 1.39 | 3.59 | 3.961 | 4.50x | 75.0 | 95 | 9.5 | 1.6 |
| 8 | 83.73 | 60.70 | 56.01 | 1.40 | 3.18 | 3.252 | 5.48x | 68.5 | 116 | 11.5 | 1.8 |
| 10 | 83.73 | 60.99 | 56.54 | 1.29 | 3.15 | 2.917 | 6.11x | 61.1 | 128 | 11.2 | 2.0 |
| 12 | 83.73 | 61.17 | 57.22 | 1.21 | 3.10 | 2.626 | 6.79x | 56.6 | 142 | 10.8 | 2.1 |
| 14 | 83.73 | 61.16 | 57.87 | 1.16 | 3.02 | 2.422 | 7.36x | 52.6 | 154 | 10.3 | 2.2 |
| 16 | 83.73 | 60.99 | 58.58 | 1.12 | 2.95 | 2.253 | 7.92x | 49.5 | 166 | 9.9 | 2.3 |

## Result 1 — Centrifuge peaks at 8 threads, on every single file

**16 files, 16 times the optimum was 8 threads.** Per-file 16T/8T ratios run 1.21–1.48, so the degradation is universal, not driven by an outlier.

Run-to-run spread is very tight: per-file coefficient of variation at 8T is ≤1.93%, and below 0.5% in 13 of 16 files. The worst CV anywhere in the sweep is pod5_15 @6T (17.7%), which is noise on a 1.4-second run of the smallest file. This is far outside noise.

> **Correction to the earlier draft of this analysis.** It stated "at 8 threads: min 6.227 s, max 6.280 s across 48 runs — under 1%". Those two figures are the *mean across files of the per-file min and max*, not the range of 48 runs. The true 8T range over 48 individual runs is **1.437 – 9.630 s**, because the files differ ~4.4x in size. The tightness claim survives on a per-file basis, as stated above; the original phrasing did not.

## Result 2 — remove the clock drop before reading any scaling number

Effective per-thread clock, and scaling measured against the ceiling that clock permits:

| Threads | GHz (C) | GHz (K2) | clock vs 1T (C) | clock vs 1T (K2) | ceiling (C) | actual (C) | % of ceiling (C) | ceiling (K2) | actual (K2) | % of ceiling (K2) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.87 | 4.77 | 1.00x | 1.00x | 1.00x | 1.00x | 100% | 1.00x | 1.00x | 100% |
| 2 | 4.70 | 4.63 | 0.96x | 0.97x | 1.93x | 1.90x | 98% | 1.94x | 1.89x | 97% |
| 4 | 4.45 | 4.31 | 0.91x | 0.90x | 3.66x | 3.46x | 95% | 3.61x | 3.51x | 97% |
| 6 | 3.55 | 3.59 | 0.73x | 0.75x | 4.38x | 4.00x | 91% | 4.52x | 4.50x | 100% |
| 8 | 3.20 | 3.18 | 0.66x | 0.67x | 5.26x | 4.51x | **86%** | 5.33x | 5.48x | **103%** |
| 12 | 3.14 | 3.10 | 0.64x | 0.65x | 7.74x | 3.94x | 51% | 7.80x | 6.79x | 87% |
| 16 | 3.07 | 2.95 | 0.63x | 0.62x | 10.10x | 3.20x | **32%** | 9.89x | 7.92x | **80%** |

4.87 GHz at 1T is the i7-11700's rated 4.9 GHz single-core turbo; ~3.0 GHz is its all-core state. Two consequences:

**The clock drop is not a Centrifuge problem.** Both tools lose the same ~37%. Any statement of the form "Centrifuge only reaches 4.51x on 8 cores, so it parallelises badly" is partly measuring Intel's turbo table. At 8T, Centrifuge's clock-adjusted ceiling is 5.26x and it hits 4.51x — 86% of what the silicon allows, which is respectable. The genuine collapse is at 10T and beyond.

**Kraken2 exceeds 100% of its clock-adjusted ceiling at 8T.** That is not an error: a memory-bound workload spends much of its time stalled on DRAM, and stall cycles do not shrink when the clock rises, so the naive clock-proportional ceiling under-predicts it. This is itself a clean confirmation of Result 4 — the two tools respond to frequency differently *because* one is compute-bound and one is memory-bound.

## Result 3 — the residual is wasted instructions and kernel time

Summing counters across all 48 runs per thread count:

| | 1 thread | 8 threads | 16 threads | growth 1→16 |
|---|---:|---:|---:|---:|
| **Centrifuge instructions** | 1.659e13 | 1.845e13 | 2.805e13 | **+69%** |
| Kraken2 instructions | 5.654e12 | 5.584e12 | 5.751e12 | +1.7% |
| **Centrifuge LLC misses** | 1.247e09 | 2.029e09 | 3.065e09 | **+146%** |
| Kraken2 LLC misses | 4.805e09 | 4.917e09 | 5.471e09 | +14% |

Kraken2's instruction count being flat is what correct parallelisation looks like — the work is divided, not multiplied. Centrifuge is burning the extra on synchronisation, not on classification.

The CPU-time breakdown localises it further:

| Threads | user (s) | sys (s) | sys share | CPU-s ÷ wall |
|---:|---:|---:|---:|---:|
| 1 | 28.07 | 0.11 | 0.4% | 1.00 |
| 8 | 45.08 | 4.69 | 9.4% | 7.95 |
| 16 | 84.34 | 56.06 | **39.9%** | 15.91 |

Two things to read here. CPU-seconds ÷ wall time tracks the thread count almost exactly at every point (1.00, 2.00, 3.99 … 15.91), so **the threads are never idle** — at 16T all sixteen are pegged at 100% while delivering 3.20x. And sys time grows **500x** while user time grows only 3x. Pure userspace spinning would show up as user time; a 40% kernel share is the signature of futex wake/wait traffic. `perf record -g` on a 16T run should land directly in the lock path.

The mechanism follows from the algorithms. FM-index backward search (LF-mapping) is a **serial dependency chain** — each step needs the previous step's result — so two hyperthreads on one core contend for execution resources rather than overlapping. Kraken2's per-k-mer hash probes are **independent**, so under SMT one thread's memory stall becomes the other thread's issue opportunity. Same silicon, opposite response, traceable directly to the data structure.

## Result 4 — Centrifuge is compute-bound, Kraken2 is memory-bound

| | Centrifuge | Kraken2 |
|---|---:|---:|
| LLC miss rate (1T) | **2.71%** | 54.39% |
| LLC miss rate (16T) | 6.23% | 58.58% |
| Absolute LLC misses (1T) | **1.247e09** | 4.805e09 |
| DRAM read traffic (1T) | **0.2 GB/s** | 2.0 GB/s |
| DRAM read traffic (16T) | **0.9 GB/s** | 9.9 GB/s |
| IPC (1T) | **2.51** | 1.38 |
| Instructions (1T) | 1.659e13 | **5.654e12** |

Centrifuge's LLC miss rate is 10–20x lower, and — unlike the single-file probe run earlier in this project — its **absolute** miss count is genuinely lower too, by 3.9x at one thread. The advantage is real, not a denominator artifact. Its IPC of 2.51 versus 1.38 says the same thing from the CPU's side: Centrifuge keeps the pipeline fed, Kraken2 stalls on memory. Kraken2's 54–59% LLC miss rate is the memory-bound signature this project already documented (96.24% of misses in `CompactHashTable::Get()`).

Neither tool is close to the ~51 GB/s the memory controller can supply — Kraken2 peaks at 9.9 GB/s. Both are **latency**-bound, not bandwidth-bound; Kraken2 just has far more latency to be bound by.

**And yet Kraken2 wins on wall time at every thread count**, because it executes 2.9x fewer instructions. Centrifuge walks the FM-index character by character across the read; Kraken2 does a handful of hash probes per read.

## Head-to-head (Centrifuge ÷ Kraken2)

| Threads | Time ratio | LLC miss-rate ratio | IPC ratio |
|---:|---:|---:|---:|
| 1 | 1.58x | 0.05x | 1.82x |
| 4 | 1.60x | 0.06x | 1.84x |
| 8 | 1.92x | 0.07x | 1.71x |
| 12 | 2.73x | 0.09x | 1.41x |
| 16 | 3.92x | 0.11x | 1.20x |

Centrifuge is slower everywhere, and the gap widens with thread count as its scaling fails. Even at its own best operating point it takes 6.26 s against Kraken2's 3.25 s at the same 8 threads.

## The caveat that governs how far these conclusions travel

**L3 is 16 MiB. The Centrifuge index is 21 MB. Kraken2's table is 47 MB.**

Centrifuge's working set nearly fits in last-level cache; Kraken2's is 2.9x too large and thrashes. So this comparison may be measuring **index size** as much as **access pattern**, and the cache-behaviour gap could shrink or invert once Centrifuge's index also exceeds L3.

That makes the database-size sweep the load-bearing next experiment, not a Week-2 nicety. It needs the larger reference set — which requires re-downloading, since `eskape_genomes/` (1,149 assemblies) was deleted after the 6 June Kraken2 build.

Note also that on Luna's 210 MB LLC **both** indexes fit entirely in cache, so this comparison would measure almost nothing there. The 16 MiB L3 on this desktop is what makes the memory hierarchy visible at all.

## What is not established here

**Classified% is not accuracy.** Centrifuge 85.30%, Kraken2 83.73%. These reads carry no ground-truth labels, and Kraken2's confidence threshold and Centrifuge's score cutoff have not been reconciled. Both numbers are **unvalidated — threshold/rank mismatch, not directly comparable**, and cannot become accuracy figures without either simulated reads or a mock community of known composition.

**Only one database size was tested.** See the caveat above.

**Centrifuge's own tuning was not explored** beyond thread count — `--min-hitlen` was left at its default of 22.

**Frequency was not pinned.** The turbo behaviour in Result 2 is measured, not controlled. A confirmation run with the governor fixed at a constant frequency would separate clock from contention directly rather than by arithmetic attribution.

## Recommendations

1. **Report Centrifuge at 8 threads, not 16.** Any prior 16-thread figure measured it at its worst operating point above 4 threads, and understates it by 41%.
2. **Quote clock-adjusted scaling efficiency, not raw speedup.** Raw speedup on this machine silently includes a 37% turbo drop that affects both tools equally and is not a property of either.
3. **Investigate the synchronisation directly.** `perf record -g` on a 16-thread run, targeting the 39.9% kernel share — that is a concrete, attributable inefficiency and a more actionable finding than the wall-clock number.
4. **Run the database-size sweep next.** It is the only way to tell whether Centrifuge's cache advantage is structural or an artifact of a 21 MB index against a 16 MiB L3.
5. **Resolve ground truth before any accuracy work.** Without labels there is nothing to compute.

## Data provenance

Every figure in this report was parsed from the raw perf captures in `raw/` (Centrifuge) and `kraken2opti/results/perf_threadsweep/raw/` (Kraken2). Per-file base counts come from Kraken2's own `N sequences (M Mbp) processed` output line, cross-checked against `wc -l` on the local FASTQ copies in `kraken2opti/results/fast1/` and against `class/*_class.txt`; all three agree. Classification output was confirmed thread-count independent — all 27 `report.tsv` per file hash identically. No value here is estimated, interpolated, or simulated.

## Reproducing

```bash
bash   scripts/perf_centrifuge_pod5.sh      # 432 runs, ~75 min, resumable
python3 scripts/analyze_centrifuge_pod5.py  # regenerates reports/ + summary
```

`THREADS`, `FILES`, `RUNS`, `COLD` and `IDX` are all overridable by environment variable. `COLD=run` drops the cache before every run rather than once per file — stricter, but no longer matching the Kraken2 methodology.

## Layout

```
centrifuge_pod5/
├── FAILURES.txt                  # 0 failures (mirrors perf_threadsweep/FAILURES.txt)
├── centrifuge_pod5_report.md     # this file
├── centrifuge_pod5_summary.md    # compact per-thread tables
├── raw/                          # 432 *_perf.txt + 432 *_report.tsv
├── reports/                      # per-pod5 tables (16 files)
├── class/                        # per-file classified/total counts + abundance TSVs
└── sweep.log                     # run log
```

`class/` has no counterpart in `perf_threadsweep/` — Kraken2 prints its classified counts into the perf capture itself, whereas Centrifuge does not, so these counts are the only record of them and are kept.
