# Profiling Report — Nanopore Pipeline
## Dorado (GPU) + Kraken-2 (CPU) Baseline Analysis

**Prepared by:** Chirag K, Chirag S  
**Date:** 2026-05-19  
**Submitted to:** Kolin sir  

---

## 1. Objective

Profile the two compute-heavy stages of the Nanopore pipeline — Dorado (GPU basecalling) and Kraken-2 (CPU species classification) — to establish a performance baseline and identify where optimizations (caching, SIMD, cache blocking) will have the most impact.

The central question: **is each stage memory-bound or compute-bound?**

---

## 2. System Setup

### 2.1 Hardware

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| GPU Architecture | Turing (compute capability 7.5) |
| OS | Windows 11 Home (WSL2 for Linux tools) |

### 2.2 Software Environment

| Component | Version |
|---|---|
| WSL2 Kernel | 6.6.87.2-microsoft-standard-WSL2 |
| Linux Distro | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Dorado | 1.4.0 (Windows binary) |
| Kraken-2 | built from source with -pg flag |
| Nsight Systems | [ VERSION — fill after install ] |
| Nsight Compute | [ VERSION — fill after install ] |
| Valgrind | [ VERSION — fill after install, run: valgrind --version ] |
| perf | [ VERSION — fill after install, run: perf --version ] |

### 2.3 Input Data

| Item | Detail |
|---|---|
| POD-5 file | FBE01990_24778b97_03e50f91_10.pod5 |
| POD-5 file size | 4 GB |
| Number of reads | 104,478 |
| Flow cell | FLO-MIN114 (R10.4.1) |
| Barcode kit | SQK-NBD114-24 |
| FASTQ used for Kraken-2 | barcode02.fastq (single barcode) |
| Kraken-2 database | Custom ESKAPE DB |
| Database size | 650 MB |
| Dorado mode | fast |

### 2.4 perf Hardware Counters Availability

| Counter type | Available? |
|---|---|
| Hardware counters (cache-misses, LLC-load-misses) | [ YES / NO — fill after running perf stat ls ] |
| Software counters (task-clock, page-faults) | Always available |
| Note | WSL2 hypervisor commonly blocks hardware PMU access |

---

## 3. Dorado GPU Profile (Nsight Systems + Nsight Compute)

### 3.1 Run Configuration

| Setting | Value |
|---|---|
| Tool | Nsight Systems |
| Mode | fast |
| Trace flags | cuda, nvtx, osrt |
| Output file | dorado_fast_profile.nsys-rep |
| Total wall-clock time | [ FILL ] seconds |

---

### 3.2 Top CUDA Kernels by Time (from nsys stats summary)

| Rank | Kernel Name | Time (%) | Total Time (ns) | Instances | Avg per call (ns) |
|---|---|---|---|---|---|
| 1 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] |
| 2 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] |
| 3 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] |
| 4 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] |
| 5 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] |

**Key observation:** [ FILL — e.g., "Top kernel accounts for X% of total GPU time, suggesting compute bottleneck in attention layers" ]

---

### 3.3 GPU Utilization (from Nsight Systems timeline)

| Metric | Value |
|---|---|
| % time GPU is actively running kernels | [ FILL ]% |
| % time GPU is idle (gaps between kernels) | [ FILL ]% |
| Observation | [ FILL — e.g., "Large idle gaps suggest CPU is bottlenecking GPU feed" ] |

---

### 3.4 Memory Transfer Analysis (from Nsight Systems timeline)

| Transfer Direction | Total Time | % of Run |
|---|---|---|
| Host to Device (HtoD) — CPU RAM → GPU | [ FILL ] | [ ]% |
| Device to Host (DtoH) — GPU → CPU RAM | [ FILL ] | [ ]% |
| Total memory transfer time | [ FILL ] | [ ]% |

**Threshold:** if total memory transfer > 20% of runtime = memory bandwidth bottleneck.  
**Observation:** [ FILL ]

---

### 3.5 Compute vs Memory Throughput (from Nsight Compute)

| Metric | Value | Interpretation |
|---|---|---|
| SM Throughput (% of peak compute) | [ FILL ]% | >80% = compute-bound |
| DRAM Throughput (% of peak bandwidth) | [ FILL ]% | >80% = memory-bound |

**Verdict:**
- [ ] Compute-bound — SM throughput high, GPU arithmetic is the bottleneck
- [ ] Memory-bound — DRAM throughput high, data movement is the bottleneck
- [ ] Mixed — both moderate, pipeline latency is the bottleneck

**Implication for caching:**  
[ FILL — e.g., "If memory-bound, Signal-to-Base cache in CUDA shared memory will reduce data movement and yield measurable speedup. If compute-bound, caching alone is insufficient — algorithmic changes needed." ]

---

## 4. Kraken-2 CPU Profile

### 4.1 Run Configuration

| Setting | Value |
|---|---|
| Kraken-2 binary | built from source with -pg |
| Database | ESKAPE DB (650 MB) |
| Input | barcode02.fastq |
| Profiling tools | gprof, Valgrind/cachegrind, perf |
| Total wall-clock time | [ FILL ] seconds |

---

### 4.2 gprof Results — Flat Profile (hotspot functions)

| Rank | Function Name | % Time | Cumulative (s) | Self (s) | Calls | Self ms/call |
|---|---|---|---|---|---|---|
| 1 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] | [ ] |
| 2 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] | [ ] |
| 3 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] | [ ] |
| 4 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] | [ ] |
| 5 | [ FILL ] | [ ]% | [ ] | [ ] | [ ] | [ ] |

**Key observation:** [ FILL — e.g., "lookup_kmer_in_db accounts for 60% of CPU time, called 3.6M times" ]

---

### 4.3 gprof Results — Call Graph (top function breakdown)

Top function: **[ FILL function name ]**

| Field | Value |
|---|---|
| Self time | [ FILL ] s |
| Children time | [ FILL ] s |
| Total time | [ FILL ] s |
| Number of calls | [ FILL ] |
| Avg time per call | [ FILL ] µs |
| Called by | [ FILL — which function calls this ] |

**Observation:** [ FILL — e.g., "Called 3.6M times at 1µs per call — tight inner loop, SIMD candidate" ]

---

### 4.4 Cachegrind Results — Cache Miss Summary

| Metric | Count | Rate |
|---|---|---|
| Total instructions (Ir) | [ FILL ] | — |
| L1 data misses (D1mr) | [ FILL ] | [ ]% |
| **Last-level data misses (LLd misses)** | **[ FILL ]** | **[ ]%** |
| L1 instruction misses | [ FILL ] | [ ]% |
| Last-level instruction misses | [ FILL ] | [ ]% |

**LLd miss rate threshold:** >5% is high, >20% is severe.  
**Result:** [ FILL — e.g., "LLd miss rate = 23% — severe. Kraken-2 is generating significant last-level cache pressure on k-mer lookups." ]

---

### 4.5 Cachegrind Results — Per-Function Cache Misses

| Rank | Function | DLmr (LLC data read misses) | DLmw (LLC data write misses) |
|---|---|---|---|
| 1 | [ FILL ] | [ FILL ] | [ FILL ] |
| 2 | [ FILL ] | [ FILL ] | [ FILL ] |
| 3 | [ FILL ] | [ FILL ] | [ FILL ] |

**Key observation:** [ FILL — e.g., "lookup_kmer_in_db has the highest DLmr — random hash table access pattern is thrashing the cache" ]

---

### 4.6 Cachegrind Line-Level Annotation (from cg_annotate --auto=yes)

**Most cache-miss-heavy line:**

| Detail | Value |
|---|---|
| File | [ FILL — e.g., kraken2.cpp ] |
| Line number | [ FILL ] |
| Code at that line | [ FILL — e.g., `val = table[hash % compact_table_size];` ] |
| Miss type | [ FILL — e.g., random read miss on hash table array ] |

**Interpretation:** [ FILL — e.g., "Hash table access at random offsets — classic pointer-chasing cache miss. Cache blocking cannot directly fix this but an LRU software cache for hot entries can." ]

---

### 4.7 perf Results

**Hardware counters available:** [ YES / NO ]

**If hardware counters available:**

| Metric | Value |
|---|---|
| cache-misses | [ FILL ] |
| LLC-load-misses | [ FILL ] |
| instructions | [ FILL ] |
| cycles | [ FILL ] |
| **IPC (instructions / cycles)** | **[ FILL ]** |
| LLC miss rate (LLC-load-misses / instructions × 100) | **[ FILL ]%** |
| Wall-clock time | [ FILL ] s |

**If hardware counters NOT available (WSL2 limitation):**

| Metric | Value |
|---|---|
| task-clock | [ FILL ] ms |
| page-faults | [ FILL ] |
| context-switches | [ FILL ] |
| Wall-clock time | [ FILL ] s |
| Note | Hardware PMU counters blocked by Hyper-V hypervisor in WSL2 |

**IPC interpretation:**
- IPC < 1.0 → memory-bound (CPU stalling on RAM fetches)
- IPC 1.0–2.0 → mixed
- IPC > 2.0 → compute-bound

**Result:** [ FILL ]

---

### 4.8 Kraken-2 Verdict

| Question | Answer |
|---|---|
| Primary bottleneck | [ Memory-bound / Compute-bound / Mixed ] |
| Evidence | gprof: [ FILL top function ]  •  cachegrind LLd miss rate: [ FILL ]%  •  IPC: [ FILL ] |
| Root cause | [ FILL — e.g., "Random hash table access on 650 MB DB causes frequent LLC evictions" ] |

**Recommended optimizations in order of expected impact:**
1. [ FILL — e.g., Hot-K-mer LRU cache — pin frequent entries above the hash table lookup ]
2. [ FILL — e.g., Cache blocking on k-mer batch processing ]
3. [ FILL — e.g., AVX2 SIMD on hash inner loop ]

---

## 5. Cross-Tool Confirmation

A finding is strong when two independent tools agree. Fill this in after all tools are run:

| Bottleneck | gprof says | cachegrind says | perf says | Agreement |
|---|---|---|---|---|
| Top hotspot function | [ FILL ] | [ FILL ] | [ FILL ] | [ YES/NO ] |
| Memory-bound? | — | LLd rate = [ ]% | IPC = [ ] | [ YES/NO ] |

**Conclusion:** [ FILL — e.g., "All three tools agree: lookup_kmer_in_db is the hotspot and is memory-bound. Hot-K-mer cache is justified." ]

---

## 6. Summary Table

| Stage | Bottleneck Type | Top Hotspot | Key Metric | Recommended Fix |
|---|---|---|---|---|
| Dorado (GPU) | [ Memory / Compute ] | [ FILL kernel ] | SM: [ ]%, DRAM: [ ]% | [ FILL ] |
| Kraken-2 (CPU) | [ Memory / Compute ] | [ FILL function ] | LLd miss: [ ]%, IPC: [ ] | [ FILL ] |

---

## 7. Next Steps

Based on the profiling results, the following work is proposed:

1. **Implement Hot-K-mer LRU cache** (Kraken-2, CPU) — if memory-bound confirmed
   - Target: `[ FILL — function name from gprof ]`
   - Tech: Intel TBB (lock-free concurrent map) + AVX2 batch lookups
   - Expected gain: [ FILL once cache miss rate is known ]

2. **Implement Signal-to-Base cache** (Dorado, GPU) — if memory-bound confirmed
   - Target: `[ FILL — kernel name from Nsight ]`
   - Tech: LSH in CUDA shared memory
   - Expected gain: [ FILL once memory transfer % is known ]

3. **Cache blocking on matrix ops** — if matrix-vector blocks identified in gprof
   - Applicable if: attention/linear layers appear in Kraken-2 or Dorado hotspots

4. **SIMD / AVX2 on k-mer hash inner loop** — if compute-bound confirmed
   - Applicable if: IPC > 2.0 and hash function appears in flat profile

---

*Report generated as part of Nanopore ESKAPE pathogen detection project under Kolin sir's guidance.*
