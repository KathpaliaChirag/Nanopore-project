# Kraken2 — Thread-Scaling Profiling Report (Per-Thread)

**Date:** 2026-05-29
**CPU:** AMD Ryzen 7 7735HS (Zen4, 8c/16t, 6-wide dispatch)
**DB:** minikraken2_v2_8GB
**Context:** Thread sweep across 9 thread counts (1, 2, 4, 6, 8, 10, 12, 14, 16) for
all three basecalling modes (fast / hac / sup). Each section covers one thread count
with the same metrics as the single-mode perf report: run summary, CPU performance,
TMA pipeline breakdown, raw event counts, and per-core utilisation. Binary rebuilt
without `-pg` — no mcount overhead in any of these results.

### Abbreviations

| Term | Meaning |
|------|---------|
| IPC | Instructions Per Cycle (higher = better; stalled memory-bound pipelines show <0.5) |
| TMA | Top-down Microarchitecture Analysis (AMD method to classify pipeline slot usage) |
| BE-Bound | Backend-Bound (pipeline slots stalled waiting on memory or execution units) |
| FE-Bound | Frontend-Bound (pipeline slots stalled on instruction fetch/decode) |
| DRAM | Dynamic Random-Access Memory (main system memory, ~100 ns latency) |
| L1/L2/L3 | Level-1 / Level-2 / Level-3 CPU cache |
| OMP | OpenMP (parallel threading via compiler directives) |
| Kseq/m | Kilo-sequences per minute (classification throughput) |
| mpstat | multiprocessor statistics (Linux per-core CPU utilisation tool) |
| op-cache | Instruction op-cache (32 KB decoded micro-op cache on Zen4) |

---

## Thread 1

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 14.643 s | 429.6 Kseq/m |
| hac | 104918 | 97.85% | 14.827 s | 424.6 Kseq/m |
| sup | 104980 | 98.38% | 15.072 s | 417.9 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 21.191575857 | 88,515,778,372 | 118,671,361,437 | 1.3 | 2.1% | 3.1% | 0.9 |
| hac | 20.871019781 | 88,610,005,357 | 135,282,771,797 | 1.5 | 1.8% | 2.8% | 0.9 |
| sup | 21.086550165 | 89,609,235,372 | 142,417,019,275 | 1.6 | 1.7% | 2.7% | 0.9 |

### Key Numbers

- **IPC 1.30–1.60** (fast→sup) — moderate memory pressure — pipeline partially stalled.
- **BE-Bound 72.3–75.3%** — majority of pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 0.9–0.9** of 1 requested — 90–90% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 1.7–2.1%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 22.9% | 1.5% | 75.3% | 0.2% | 1.374 |
| hac | 25.1% | 1.5% | 73.2% | 0.2% | 1.498 |
| sup | 26.0% | 1.5% | 72.3% | 0.2% | 1.549 |

> **BE-Bound 72.3–75.3%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 22.9–26.0%** — only 24.7% of pipeline slots do real work on average.

### TMA Bucket Meanings

| Bucket | Meaning | Good value |
|--------|---------|-----------|
| Retiring | Fraction of pipeline slots doing useful work | High (>60%) |
| FE-Bound | Frontend starvation — decoder can't supply micro-ops fast enough | Low (<15%) |
| BE-Bound | Backend bottleneck — memory latency or execution unit pressure | Low (<20%) |
| Bad-Spec | Slots wasted on mispredicted/cancelled paths | Low (<5%) |

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 85,826,004,256 | 89,852,651,841 | 90,868,753,118 |
| `ex_ret_ops` | 118,062,508,819 | 135,251,868,863 | 141,625,070,965 |
| `ex_ret_instr` | 117,939,809,749 | 134,588,669,202 | 140,799,275,502 |
| `de_dis_uop_queue_empty_di0` | 7,706,559,900 | 8,083,425,945 | 7,986,296,283 |
| `ex_ret_near_ret_mispred` | 306,984,882 | 309,813,088 | 308,238,733 |
| `op_cache_hit_miss.op_cache_miss` | 2,815,435,231 | 2,862,630,810 | 2,853,363,952 |
| `ic_fetch_stall.ic_stall_any` | 50,372,663,364 | 51,530,543,555 | 51,446,476,004 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 6.3% usr — peak cores: CPU6 (34.6%), CPU7 (32.8%), CPU2 (8.8%). 12 of 16 CPUs averaged under 5%.
**hac:** overall avg 5.5% usr — peak cores: CPU2 (30.5%), CPU6 (22.6%), CPU3 (16.6%). 12 of 16 CPUs averaged under 5%.
**sup:** overall avg 5.4% usr — peak cores: CPU7 (37.8%), CPU6 (33.2%), CPU2 (4.4%). 14 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 2

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 7.638 s | 823.5 Kseq/m |
| hac | 104918 | 97.85% | 8.223 s | 765.5 Kseq/m |
| sup | 104980 | 98.38% | 8.383 s | 751.3 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 13.473921210 | 85,880,956,318 | 118,847,208,688 | 1.4 | 2.0% | 3.1% | 1.5 |
| hac | 14.260545742 | 89,822,587,336 | 134,621,157,328 | 1.5 | 1.8% | 2.8% | 1.5 |
| sup | 14.435852140 | 90,689,013,313 | 141,325,069,722 | 1.6 | 1.7% | 2.7% | 1.5 |

### Key Numbers

- **IPC 1.40–1.60** (fast→sup) — reasonable utilisation — memory pressure manageable at this thread count.
- **BE-Bound 71.7–75.2%** — majority of pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 1.5–1.5** of 2 requested — 75–75% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 1.7–2.0%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 23.0% | 1.5% | 75.2% | 0.2% | 1.380 |
| hac | 25.0% | 1.5% | 73.2% | 0.2% | 1.494 |
| sup | 26.5% | 1.5% | 71.7% | 0.2% | 1.583 |

> **BE-Bound 71.7–75.2%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 23.0–26.5%** — only 24.9% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 85,657,131,266 | 90,229,670,562 | 89,164,535,941 |
| `ex_ret_ops` | 118,391,547,193 | 135,379,170,052 | 141,980,716,970 |
| `ex_ret_instr` | 118,208,033,998 | 134,764,914,824 | 141,155,762,737 |
| `de_dis_uop_queue_empty_di0` | 7,850,830,233 | 8,246,614,400 | 7,994,067,568 |
| `ex_ret_near_ret_mispred` | 310,307,895 | 313,495,628 | 312,244,266 |
| `op_cache_hit_miss.op_cache_miss` | 2,870,041,083 | 2,913,705,894 | 2,906,701,821 |
| `ic_fetch_stall.ic_stall_any` | 50,115,777,466 | 51,717,988,904 | 49,664,159,381 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 7.8% usr — peak cores: CPU2 (37.1%), CPU6 (33.5%), CPU3 (16.9%). 11 of 16 CPUs averaged under 5%.
**hac:** overall avg 9.6% usr — peak cores: CPU7 (34.4%), CPU3 (31.3%), CPU6 (27.6%). 10 of 16 CPUs averaged under 5%.
**sup:** overall avg 9.6% usr — peak cores: CPU2 (43.0%), CPU7 (30.6%), CPU6 (28.6%). 11 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 4

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 4.273 s | 1472.1 Kseq/m |
| hac | 104918 | 97.85% | 4.741 s | 1327.7 Kseq/m |
| sup | 104980 | 98.38% | 4.537 s | 1388.3 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 10.446401841 | 87,014,051,262 | 118,545,998,588 | 1.4 | 2.1% | 3.1% | 2.1 |
| hac | 10.826863218 | 90,154,481,220 | 134,960,037,690 | 1.5 | 1.8% | 2.8% | 2.2 |
| sup | 10.455208695 | 89,499,166,867 | 141,558,909,117 | 1.6 | 1.8% | 2.7% | 2.2 |

### Key Numbers

- **IPC 1.40–1.60** (fast→sup) — reasonable utilisation — memory pressure manageable at this thread count.
- **BE-Bound 72.0–75.3%** — majority of pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 2.1–2.2** of 4 requested — 52–55% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 1.8–2.1%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 22.9% | 1.6% | 75.3% | 0.2% | 1.371 |
| hac | 25.7% | 1.6% | 72.5% | 0.2% | 1.527 |
| sup | 26.1% | 1.7% | 72.0% | 0.2% | 1.551 |

> **BE-Bound 72.0–75.3%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 22.9–26.1%** — only 24.9% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 86,485,258,399 | 88,387,716,995 | 91,247,454,626 |
| `ex_ret_ops` | 118,653,819,211 | 136,050,580,686 | 142,731,818,877 |
| `ex_ret_instr` | 118,547,041,115 | 134,940,508,835 | 141,532,011,901 |
| `de_dis_uop_queue_empty_di0` | 8,256,075,273 | 8,416,144,951 | 9,318,429,843 |
| `ex_ret_near_ret_mispred` | 318,246,000 | 318,775,850 | 318,123,250 |
| `op_cache_hit_miss.op_cache_miss` | 2,954,967,581 | 2,948,810,762 | 3,555,204,721 |
| `ic_fetch_stall.ic_stall_any` | 50,766,082,461 | 49,687,959,983 | 50,687,465,992 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 12.7% usr — peak cores: CPU8 (45.2%), CPU7 (30.9%), CPU3 (28.9%). 9 of 16 CPUs averaged under 5%.
**hac:** overall avg 13.5% usr — peak cores: CPU3 (35.3%), CPU6 (32.5%), CPU0 (32.0%). 6 of 16 CPUs averaged under 5%.
**sup:** overall avg 11.9% usr — peak cores: CPU7 (36.9%), CPU2 (34.3%), CPU0 (33.6%). 8 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 6

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 3.276 s | 1920.1 Kseq/m |
| hac | 104918 | 97.85% | 3.580 s | 1758.6 Kseq/m |
| sup | 104980 | 98.38% | 3.752 s | 1679.0 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 9.464018424 | 87,372,605,122 | 119,378,281,146 | 1.4 | 2.1% | 3.1% | 2.6 |
| hac | 9.542903919 | 89,949,567,009 | 135,561,250,523 | 1.5 | 2.0% | 2.8% | 2.7 |
| sup | 9.739613106 | 90,181,395,538 | 142,359,060,227 | 1.6 | 1.8% | 2.7% | 2.8 |

### Key Numbers

- **IPC 1.40–1.60** (fast→sup) — reasonable utilisation — memory pressure manageable at this thread count.
- **BE-Bound 70.5–74.5%** — majority of pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 2.6–2.8** of 6 requested — 43–47% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 1.8–2.1%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 23.6% | 1.6% | 74.5% | 0.3% | 1.409 |
| hac | 25.5% | 1.6% | 72.7% | 0.2% | 1.513 |
| sup | 27.7% | 1.6% | 70.5% | 0.3% | 1.650 |

> **BE-Bound 70.5–74.5%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 23.6–27.7%** — only 25.6% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 84,458,583,946 | 89,551,226,942 | 86,000,054,751 |
| `ex_ret_ops` | 119,414,244,366 | 136,847,741,590 | 142,905,023,398 |
| `ex_ret_instr` | 119,026,958,235 | 135,478,475,696 | 141,881,559,563 |
| `de_dis_uop_queue_empty_di0` | 8,298,275,844 | 8,731,743,079 | 8,177,972,004 |
| `ex_ret_near_ret_mispred` | 324,450,930 | 322,712,205 | 324,403,082 |
| `op_cache_hit_miss.op_cache_miss` | 3,017,449,215 | 3,035,926,924 | 3,013,458,262 |
| `ic_fetch_stall.ic_stall_any` | 48,395,223,202 | 50,638,162,155 | 46,123,754,833 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 12.6% usr — peak cores: CPU4 (27.9%), CPU8 (27.5%), CPU7 (26.0%). 4 of 16 CPUs averaged under 5%.
**hac:** overall avg 13.6% usr — peak cores: CPU13 (29.0%), CPU2 (26.0%), CPU4 (25.6%). 4 of 16 CPUs averaged under 5%.
**sup:** overall avg 14.8% usr — peak cores: CPU3 (33.1%), CPU4 (30.4%), CPU0 (26.8%). 3 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 8

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 2.699 s | 2330.8 Kseq/m |
| hac | 104918 | 97.85% | 3.246 s | 1939.4 Kseq/m |
| sup | 104980 | 98.38% | 2.841 s | 2217.0 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 8.785329460 | 86,127,270,130 | 119,480,035,168 | 1.4 | 2.2% | 3.1% | 2.9 |
| hac | 9.593603522 | 96,092,791,416 | 136,758,186,069 | 1.4 | 2.0% | 2.9% | 3.2 |
| sup | 8.528873573 | 87,865,863,218 | 142,321,638,562 | 1.6 | 1.8% | 2.7% | 3.1 |

### Key Numbers

- **IPC 1.40–1.60** (fast→sup) — moderate memory pressure — pipeline partially stalled.
- **BE-Bound 70.7–75.3%** — majority of pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 2.9–3.2** of 8 requested — 36–40% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 1.8–2.2%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 22.8% | 1.7% | 75.3% | 0.3% | 1.359 |
| hac | 25.1% | 1.7% | 73.0% | 0.2% | 1.486 |
| sup | 27.5% | 1.6% | 70.7% | 0.2% | 1.634 |

> **BE-Bound 70.7–75.3%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 22.8–27.5%** — only 25.1% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 87,769,592,314 | 91,317,042,511 | 87,052,749,981 |
| `ex_ret_ops` | 119,962,791,392 | 137,428,595,450 | 143,427,887,040 |
| `ex_ret_instr` | 119,286,894,736 | 135,742,308,256 | 142,284,582,426 |
| `de_dis_uop_queue_empty_di0` | 8,938,749,117 | 9,262,441,827 | 8,331,602,912 |
| `ex_ret_near_ret_mispred` | 329,786,420 | 336,443,081 | 325,230,037 |
| `op_cache_hit_miss.op_cache_miss` | 3,057,610,026 | 3,127,954,928 | 3,054,269,532 |
| `ic_fetch_stall.ic_stall_any` | 51,956,405,370 | 52,445,033,852 | 47,198,594,995 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 15.7% usr — peak cores: CPU4 (30.2%), CPU14 (29.2%), CPU7 (29.2%). 6 of 16 CPUs averaged under 5%.
**hac:** overall avg 16.8% usr — peak cores: CPU6 (34.6%), CPU12 (29.6%), CPU1 (27.3%). 2 of 16 CPUs averaged under 5%.
**sup:** overall avg 16.7% usr — peak cores: CPU1 (33.5%), CPU10 (32.0%), CPU14 (29.2%). 3 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 10

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 2.741 s | 2294.5 Kseq/m |
| hac | 104918 | 97.85% | 2.837 s | 2218.6 Kseq/m |
| sup | 104980 | 98.38% | 2.673 s | 2356.1 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 9.115300319 | 98,732,376,696 | 119,524,366,444 | 1.2 | 2.4% | 3.2% | 3.5 |
| hac | 9.032520470 | 100,103,030,387 | 136,065,130,751 | 1.4 | 2.0% | 2.9% | 3.6 |
| sup | 8.377199103 | 96,767,516,507 | 142,827,474,396 | 1.5 | 1.9% | 2.7% | 3.7 |

### Key Numbers

- **IPC 1.20–1.50** (fast→sup) — moderate memory pressure — pipeline partially stalled.
- **BE-Bound 73.2–76.6%** — majority of pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 3.5–3.7** of 10 requested — 35–37% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 1.9–2.4%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 21.4% | 1.7% | 76.6% | 0.2% | 1.276 |
| hac | 23.7% | 1.7% | 74.4% | 0.2% | 1.404 |
| sup | 24.9% | 1.6% | 73.2% | 0.2% | 1.481 |

> **BE-Bound 73.2–76.6%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 21.4–24.9%** — only 23.4% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 93,718,502,196 | 96,748,481,179 | 96,161,151,998 |
| `ex_ret_ops` | 120,525,019,438 | 137,582,782,156 | 143,816,631,746 |
| `ex_ret_instr` | 119,555,835,593 | 135,873,002,844 | 142,400,989,472 |
| `de_dis_uop_queue_empty_di0` | 9,810,840,102 | 9,823,648,990 | 9,518,258,494 |
| `ex_ret_near_ret_mispred` | 338,692,017 | 336,692,566 | 332,745,225 |
| `op_cache_hit_miss.op_cache_miss` | 3,169,216,591 | 3,230,942,322 | 3,212,791,004 |
| `ic_fetch_stall.ic_stall_any` | 59,251,712,690 | 59,273,636,756 | 57,472,481,417 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 20.3% usr — peak cores: CPU12 (28.7%), CPU7 (28.5%), CPU10 (28.3%). 0 of 16 CPUs averaged under 5%.
**hac:** overall avg 20.9% usr — peak cores: CPU8 (33.1%), CPU10 (31.0%), CPU3 (28.9%). 1 of 16 CPUs averaged under 5%.
**sup:** overall avg 19.8% usr — peak cores: CPU7 (31.7%), CPU1 (31.0%), CPU9 (30.5%). 1 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 12

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 2.448 s | 2569.8 Kseq/m |
| hac | 104918 | 97.85% | 2.743 s | 2295.3 Kseq/m |
| sup | 104980 | 98.38% | 2.566 s | 2454.7 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 8.705884330 | 101,740,126,165 | 119,937,913,005 | 1.2 | 2.4% | 3.2% | 3.8 |
| hac | 8.776263947 | 107,808,666,168 | 135,688,432,092 | 1.3 | 2.1% | 2.9% | 4.1 |
| sup | 8.337066533 | 104,421,149,239 | 142,430,080,622 | 1.4 | 2.0% | 2.8% | 4.1 |

### Key Numbers

- **IPC 1.20–1.40** (fast→sup) — moderate memory pressure — pipeline partially stalled.
- **BE-Bound 74.8–77.7%** — most pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 3.8–4.1** of 12 requested — 32–34% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 2.0–2.4%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 20.3% | 1.8% | 77.7% | 0.2% | 1.207 |
| hac | 21.8% | 1.7% | 76.2% | 0.2% | 1.292 |
| sup | 23.3% | 1.7% | 74.8% | 0.2% | 1.381 |

> **BE-Bound 74.8–77.7%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 20.3–23.3%** — only 21.8% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 99,175,183,081 | 105,448,764,015 | 103,208,508,906 |
| `ex_ret_ops` | 120,768,570,211 | 137,949,317,613 | 144,080,538,672 |
| `ex_ret_instr` | 119,720,286,887 | 136,204,464,083 | 142,504,752,105 |
| `de_dis_uop_queue_empty_di0` | 10,589,526,566 | 10,985,005,184 | 10,365,375,481 |
| `ex_ret_near_ret_mispred` | 337,086,335 | 337,552,524 | 334,030,276 |
| `op_cache_hit_miss.op_cache_miss` | 3,223,913,522 | 3,356,522,300 | 3,321,013,272 |
| `ic_fetch_stall.ic_stall_any` | 65,898,374,381 | 69,230,274,607 | 65,459,548,605 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 21.9% usr — peak cores: CPU8 (31.7%), CPU2 (29.0%), CPU0 (28.5%). 0 of 16 CPUs averaged under 5%.
**hac:** overall avg 25.6% usr — peak cores: CPU10 (32.0%), CPU9 (31.5%), CPU13 (31.3%). 0 of 16 CPUs averaged under 5%.
**sup:** overall avg 22.2% usr — peak cores: CPU9 (29.7%), CPU1 (28.8%), CPU8 (28.6%). 1 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 14

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 2.315 s | 2716.6 Kseq/m |
| hac | 104918 | 97.85% | 2.650 s | 2375.3 Kseq/m |
| sup | 104980 | 98.38% | 2.465 s | 2555.1 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 8.460003230 | 105,957,251,188 | 120,576,620,361 | 1.1 | 2.5% | 3.2% | 4.2 |
| hac | 8.757239698 | 113,943,287,373 | 136,871,130,425 | 1.2 | 2.2% | 2.9% | 4.5 |
| sup | 8.173313309 | 110,236,095,680 | 143,156,030,027 | 1.3 | 2.1% | 2.8% | 4.6 |

### Key Numbers

- **IPC 1.10–1.30** (fast→sup) — moderate memory pressure — pipeline partially stalled.
- **BE-Bound 76.2–78.9%** — most pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 4.2–4.6** of 14 requested — 30–33% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 2.1–2.5%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 19.1% | 1.8% | 78.9% | 0.2% | 1.134 |
| hac | 20.4% | 1.8% | 77.7% | 0.2% | 1.206 |
| sup | 21.9% | 1.7% | 76.2% | 0.2% | 1.299 |

> **BE-Bound 76.2–78.9%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 19.1–21.9%** — only 20.5% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 105,826,481,304 | 113,094,474,680 | 109,787,994,268 |
| `ex_ret_ops` | 121,224,276,321 | 138,193,126,646 | 144,450,356,860 |
| `ex_ret_instr` | 120,034,136,561 | 136,342,621,732 | 142,647,976,722 |
| `de_dis_uop_queue_empty_di0` | 11,531,325,576 | 12,062,432,371 | 11,283,942,151 |
| `ex_ret_near_ret_mispred` | 340,886,598 | 340,942,865 | 335,338,921 |
| `op_cache_hit_miss.op_cache_miss` | 3,271,899,644 | 3,436,150,966 | 3,446,154,252 |
| `ic_fetch_stall.ic_stall_any` | 73,590,961,619 | 77,792,515,465 | 73,060,359,869 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 23.6% usr — peak cores: CPU8 (29.0%), CPU10 (27.0%), CPU4 (26.9%). 0 of 16 CPUs averaged under 5%.
**hac:** overall avg 28.2% usr — peak cores: CPU2 (32.5%), CPU7 (30.7%), CPU3 (30.5%). 0 of 16 CPUs averaged under 5%.
**sup:** overall avg 24.7% usr — peak cores: CPU6 (30.1%), CPU2 (29.5%), CPU4 (28.3%). 0 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Thread 16

### Run Summary

| Mode | Reads | Classified | Wall Time | Throughput |
|------|------:|-----------:|----------:|-----------:|
| fast | 104832 | 93.18% | 2.218 s | 2836.0 Kseq/m |
| hac | 104918 | 97.85% | 2.554 s | 2464.5 Kseq/m |
| sup | 104980 | 98.38% | 2.401 s | 2623.7 Kseq/m |

### General CPU Performance

| Mode | Elapsed (s) | Cycles | Instructions | IPC | L1-Miss% | Branch-Miss% | CPUs Utilized |
|------|------------:|-------:|-------------:|----:|---------:|-------------:|--------------:|
| fast | 8.396427379 | 109,182,712,232 | 120,822,636,452 | 1.1 | 2.6% | 3.2% | 4.4 |
| hac | 8.980483706 | 117,835,416,485 | 137,760,302,492 | 1.2 | 2.2% | 3.0% | 4.6 |
| sup | 8.088566598 | 115,685,566,304 | 143,254,631,402 | 1.2 | 2.1% | 2.8% | 4.9 |

### Key Numbers

- **IPC 1.10–1.20** (fast→sup) — moderate memory pressure — pipeline partially stalled.
- **BE-Bound 77.0–79.1%** — most pipeline slots stalled in the backend waiting on memory.
- **CPUs Utilized 4.4–4.9** of 16 requested — 28–31% of threads doing active compute; the rest stall on DRAM.
- **L1-Miss 2.1–2.6%** — demand not served from L1; propagates to L2/L3/DRAM.

### TMA Pipeline Breakdown (AMD Zen4 Topdown)

Pipeline width = 6 micro-ops/cycle. Total slots = `ls_not_halted_cyc × 6`.

| Mode | Retiring% | FE-Bound% | BE-Bound% | Bad-Spec% | IPC (TMA) |
|------|----------:|----------:|----------:|----------:|----------:|
| fast | 18.9% | 1.8% | 79.1% | 0.2% | 1.117 |
| hac | 19.8% | 1.8% | 78.2% | 0.2% | 1.170 |
| sup | 21.0% | 1.8% | 77.0% | 0.2% | 1.243 |

> **BE-Bound 77.0–79.1%** — the pipeline is waiting on memory, not stalling on frontend decode or branch mispredicts.
> **Retiring 18.9–21.0%** — only 19.9% of pipeline slots do real work on average.

### Raw TMA Event Counts

| Event | fast | hac | sup |
|-------|-----:|----:|----:|
| `ls_not_halted_cyc` | 107,663,550,744 | 116,667,198,854 | 114,999,438,737 |
| `ex_ret_ops` | 121,825,939,222 | 138,635,342,292 | 144,902,970,644 |
| `ex_ret_instr` | 120,299,878,294 | 136,504,825,010 | 143,000,710,322 |
| `de_dis_uop_queue_empty_di0` | 11,822,014,384 | 12,550,757,147 | 12,100,766,943 |
| `ex_ret_near_ret_mispred` | 346,991,663 | 347,723,859 | 343,047,588 |
| `op_cache_hit_miss.op_cache_miss` | 3,321,241,601 | 3,515,837,594 | 3,528,129,314 |
| `ic_fetch_stall.ic_stall_any` | 75,920,078,656 | 81,584,578,484 | 78,739,480,058 |

> **IC-Stall% note:** high `ic_fetch_stall` values are a backend artifact —
> when BE-Bound stalls the pipeline the fetch stage backs up too. FE-Bound
> (1.5–1.8%) is the real frontend figure; the frontend is not the bottleneck.

### Per-Core CPU Utilization (mpstat)

**fast:** overall avg 24.8% usr — peak cores: CPU3 (28.6%), CPU2 (27.1%), CPU12 (26.5%). 0 of 16 CPUs averaged under 5%.
**hac:** overall avg 26.8% usr — peak cores: CPU6 (33.2%), CPU8 (29.8%), CPU3 (29.1%). 0 of 16 CPUs averaged under 5%.
**sup:** overall avg 26.6% usr — peak cores: CPU6 (28.6%), CPU3 (28.1%), CPU9 (27.6%). 0 of 16 CPUs averaged under 5%.

> Low per-core averages with high peaks = threads stalling on DRAM and yielding
> the CPU, not genuine idleness. The OS reports low utilisation because stalled
> threads are in kernel wait, not executing user-space instructions.

---

## Cross-Thread Summary

| Threads | fast wall (s) | fast IPC | fast BE-Bound | hac wall (s) | sup wall (s) |
|--------:|--------------:|---------:|--------------:|-------------:|-------------:|
| 1 | 14.643 | 1.3 | 75.3% | 14.827 | 15.072 |
| 2 | 7.638 | 1.4 | 75.2% | 8.223 | 8.383 |
| 4 | 4.273 | 1.4 | 75.3% | 4.741 | 4.537 |
| 6 | 3.276 | 1.4 | 74.5% | 3.580 | 3.752 |
| 8 | 2.699 | 1.4 | 75.3% | 3.246 | 2.841 |
| 10 | 2.741 | 1.2 | 76.6% | 2.837 | 2.673 |
| 12 | 2.448 | 1.2 | 77.7% | 2.743 | 2.566 |
| 14 | 2.315 | 1.1 | 78.9% | 2.650 | 2.465 |
| 16 | 2.218 | 1.1 | 79.1% | 2.554 | 2.401 |

_Generated by generate_thread_report.py — 2026-05-29_