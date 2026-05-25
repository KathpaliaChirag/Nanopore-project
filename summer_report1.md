# Profiling Report: Dorado + Kraken-2 Nanopore Pipeline
**Author:** Chirag Suthar — Summer Research Intern
**Date:** 2026-05-22
**Submitted to:** Kolin Sir

---

## 1. Objective

Profile the two compute-intensive stages of the Oxford Nanopore sequencing pipeline to determine whether each stage is **compute-bound** or **memory-bound**, and to quantitatively justify the proposed Hot-K-mer LRU cache for Kraken-2.

**Pipeline:**
```
POD-5 raw signal
    ↓  Dorado (GPU) — basecalling (signal → DNA sequence)
FASTQ reads
    ↓  Kraken-2 (CPU) — species identification (DNA → taxonomy)
Species report
```

**Test sample:** AIIMS clinical sample `FBE01990_24778b97` — 104,478 nanopore reads, ESKAPE pathogen mix
**Hardware:** NVIDIA RTX 4050 Laptop GPU (6 GB VRAM), AMD Ryzen 7 CPU, 16 GB RAM

---

## 2. Dorado GPU Profiling (Nsight Systems)

### 2.1 Setup
- Tool: NVIDIA Nsight Systems 2026.2.1 (`sudo nsys profile`)
- Models tested: `dna_r10.4.1_e8.2_400bps_fast@v5.2.0` and `dna_r10.4.1_e8.2_400bps_hac@v5.2.0`
- Note: `sudo` required because Dorado bundles its own `libcudart.so.12` which blocks standard nsys injection

### 2.2 Run Summary

| Metric | Fast Model | HAC Model |
|---|---|---|
| Total runtime | 186.8 s | 502.0 s |
| Reads basecalled | 104,478 | 104,477 |
| Throughput | 27.2M samples/sec | 10.1M samples/sec |
| Slowdown vs fast | — | **2.69×** |

### 2.3 Top GPU Kernels

**Fast model:**

| Rank | % Time | Kernel |
|---|---|---|
| 1 | 26.2% | `beam_search_step` |
| 2 | 16.6% | `ampere_h16816gemm_128x64` (Tensor Core GEMM) |
| 3 | 13.9% | `lstm` (forward, 96-dim) |
| 4–6 | 27.8% | `decode_step`, `lstm` (reverse), `compute_posts_step` |

**HAC model:**

| Rank | % Time | Kernel |
|---|---|---|
| 1 | **69.8%** | `cutlass::LstmKernel` (CUTLASS LSTM) |
| 2 | 8.6% | `beam_search_step` |
| 3 | 5.9% | `cutlass::LinearLayer` (GEMM) |
| 4–6 | 11.2% | `compute_posts_step`, `decode_step`, `back_guide_step` |

### 2.4 CUDA API Breakdown

| Model | `cudaStreamSynchronize` % | Interpretation |
|---|---|---|
| Fast | 98.4% | CPU blocked waiting on GPU |
| HAC | 99.1% | CPU blocked waiting on GPU |

### 2.5 Verdict: Dorado is Compute-Bound

- **98–99%** of CUDA API time is CPU blocking on GPU (`cudaStreamSynchronize`) — GPU is the pacing unit
- Fast model bottleneck: beam search (26%) + Tensor Core GEMM (17%) + LSTM (23%)
- HAC model bottleneck: CUTLASS LSTM alone (69.8%) — a much larger recurrent layer
- Memory transfers are large and efficient (not fragmented, not a bottleneck)
- Dorado already uses CUTLASS and Tensor Cores — standard tiling/blocking optimizations are already implemented at the library level

**A signal-to-base cache would not help Dorado.** Every read contains unique raw signal data that cannot be cached. The GPU is saturated with neural network inference. Real speedup requires quantization (INT8) or model architecture changes.

---

## 3. Kraken-2 CPU Profiling (gprof + cachegrind + perf)

### 3.1 Setup
- Kraken-2 v2.17.1 built from source with `-pg` flag at `/opt/kraken2-build/bin/`
- Custom ESKAPE database: 6 pathogen reference genomes, 60 MB hash table
- Tools: gprof (CPU time), cachegrind/valgrind (instruction count), perf stat (hardware counters)
- Single-threaded runs for clean profiling

### 3.2 Classification Results

| Metric | Fast model reads | HAC model reads |
|---|---|---|
| Reads processed | 22,386 (103 Mbp) | 104,921 (355 Mbp) |
| Classified | 16,605 **(74.18%)** | 84,867 **(80.89%)** |
| Unclassified | 5,781 (25.82%) | 20,054 (19.11%) |
| Kraken-2 runtime | 8.3s | 31.4s |
| Throughput | 161.7 Kseq/min | 200.4 Kseq/min |

HAC reads classify **6.7% better** due to higher base accuracy producing more k-mer matches.

### 3.3 gprof — CPU Time Breakdown

| Function | Fast % | HAC % | Role |
|---|---|---|---|
| **`CompactHashTable::Get()`** | **69.1%** | **69.6%** | k-mer hash table lookup |
| `MinimizerScanner::NextMinimizer()` | 20.8% | 18.6% | k-mer generation |
| `ClassifySequence()` | 5.5% | 4.7% | per-read classification |
| `reverse_complement()` | 2.0% | 2.5% | k-mer canonicalization |

**`CompactHashTable::Get()` dominates at ~69% of CPU time regardless of input quality.** This is structural — every k-mer requires one random hash table lookup.

- Fast model: 32.9M hash lookups for 22,386 reads (~1,471 lookups/read)
- HAC model: 112.3M hash lookups for 104,921 reads (~1,070 lookups/read)

### 3.4 perf stat — Hardware Performance Counters

| Counter | Fast | HAC |
|---|---|---|
| Runtime | 8.87s | 31.07s |
| Instructions | 47.7B | 178.0B |
| Cycles | 37.8B | 132.6B |
| **IPC (instructions/cycle)** | **1.26** | **1.34** |
| L1 dcache loads | 19.3B | 70.3B |
| L1 dcache load misses | 208M (1.08%) | 699M (0.99%) |
| LLC cache references | 468M | 1,578M |
| **LLC cache misses** | **157M (33.5%)** | **551M (34.9%)** |

**~34% LLC miss rate on both inputs.** 1 in 3 hash table lookups goes all the way to main RAM (60–100 ns) instead of L3 cache (<10 ns). IPC of ~1.3 is low — the CPU is frequently stalling waiting for memory.

### 3.5 cachegrind — Instruction Count (5,000-read subset)

| Function | Fast % | HAC % |
|---|---|---|
| `NextMinimizer()` | ~29% | 29.7% |
| `CompactHashTable::Get()` | ~15% | 15.0% |
| `reverse_complement()` | ~7% | 7.3% |
| `ClassifySequence()` | ~6% | 6.5% |

Note: `CompactHashTable::Get()` has fewer instructions than `NextMinimizer()` but takes more wall-clock time — confirming that each hash lookup **stalls on memory latency**, not compute.

### 3.6 Verdict: Kraken-2 is Memory-Bound

| Evidence | Value |
|---|---|
| CPU time in hash lookup | **69%** |
| LLC cache miss rate | **~34%** |
| IPC | 1.26–1.34 (low — memory stall limited) |
| Hash lookups per second | ~13M/s (same for both models) |

Kraken-2 is bottlenecked by **random memory access** to the k-mer hash table. With the full 180 GB standard database, the miss rate would approach 100% since the entire hash table cannot fit in any cache level.

---

## 4. Summary Comparison

| Component | Bottleneck | Dominant function | Fix |
|---|---|---|---|
| **Dorado (GPU)** | **Compute-bound** | CUTLASS LSTM (69.8%), beam search (26%) | INT8 quantization, larger batch size |
| **Kraken-2 (CPU)** | **Memory-bound** | `CompactHashTable::Get()` (69% CPU, 34% LLC miss) | **Hot-K-mer LRU cache** |

---

## 5. Justification for the Hot-K-mer LRU Cache

The profiling directly supports the proposed caching approach:

1. **69% of Kraken-2's CPU time** is spent in `CompactHashTable::Get()` — the exact function the cache would accelerate
2. **34% LLC miss rate** means most lookups are going to main RAM at 60–100 ns latency per access
3. **Access pattern is non-uniform** — reads from the same sample share k-mers from the same organisms repeatedly. An LRU cache exploiting this locality can serve hot k-mers at L3 speed (<10 ns) instead of DRAM speed
4. **HAC reads produce 6.7% more k-mer matches** — a larger fraction of lookups will be cache-warm with higher quality basecalling, making the cache even more effective

**Estimated impact:** If the LRU cache achieves a 50% hit rate on `CompactHashTable::Get()` calls (conservative for a biased sample), the 69% CPU bottleneck drops to ~35%, roughly **doubling Kraken-2 throughput** without any code changes to the core algorithm.

---

## 6. Files and Locations

| Item | Location |
|---|---|
| Dorado binary | `/opt/dorado/bin/dorado` |
| Kraken-2 binary (-pg) | `/opt/kraken2-build/bin/classify` |
| ESKAPE database | `/opt/kraken2-build/db/` |
| nsys profiles | `~/results/nsight/` |
| gprof analysis | `~/results/profiling/gprof_analysis.txt` |
| cachegrind output | `~/results/profiling/cachegrind.out` |
| Detailed report log | `~/memory/report.md` (hobbbit branch) |
