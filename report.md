# meeting prep — kolin sir (2026-05-26)
**prepared by:** chirag kathpalia

this is a full summary of everything profiled so far. what we ran, exact commands, what numbers came out, and where time is actually going.

---

## the big picture (30 seconds)

the pipeline is: pod5 → dorado (GPU, basecalling) → BAM → samtools → FASTQ → kraken-2 (CPU, species ID).

we profiled both stages. the conclusion for each:
- **kraken-2 is memory-bound.** 34.24% cache miss rate. the CPU is mostly waiting for RAM, not computing.
- **dorado is compute-bound.** 82% of GPU time is matrix multiply. the GPU is working flat out.

both conclusions directly justify the caching work.

---

## what hardware we ran on

| component | spec |
|---|---|
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |
| WSL2 kernel | 6.6.87.2-microsoft-standard-WSL2 |

the profiling setup matters because WSL2 has hardware counter limitations. Hyper-V sits between the kernel and the PMU. LLC-specific counters (`LLC-loads`, `LLC-load-misses`) show `<not supported>`. the counters we did use (cache-misses, cache-references, cycles, instructions) work fine. ratios are reliable even if raw cycle counts are not.

---

## tool 1 — perf (kraken-2 CPU profile)

### what perf is

`perf` reads hardware performance counters built into the CPU (the PMU — performance monitoring unit). it's not a simulator. while the program runs, the CPU's own registers count events: cache misses, cycles, instructions, branch mispredictions. perf reads those registers at the end and prints a table. overhead is near zero. runs at full speed.

### getting perf working on WSL2 (this took time)

WSL2 uses Microsoft's custom kernel. Ubuntu's `linux-tools-generic` ships perf only for Ubuntu's own kernels. running `perf stat ls` gave:

```
WARNING: perf not found for kernel 6.6.87.2-microsoft
```

fix: build perf from source directly from Microsoft's WSL2 kernel repo.

```bash
git clone https://github.com/microsoft/WSL2-Linux-Kernel --depth=1 --branch linux-msft-wsl-6.6.87.2
cd WSL2-Linux-Kernel/tools/perf
sudo apt install libtraceevent-dev flex bison libelf-dev libdw-dev
make
sudo cp perf /usr/local/bin/perf
```

the critical dependency is `libtraceevent-dev`. without it the build fails silently and gives a broken perf binary. everything else (missing libbabeltrace, JDK, libpfm4) is harmless.

### input

- file: `barcode02.fastq` — 104,829 reads, 357.62 Mbp
- database: `k2_standard_08gb` — 8 GB pre-built standard kraken-2 DB
- why 8 GB and not our 650 MB ESKAPE DB: we wanted to profile the realistic clinical scenario where a full standard DB is in use. also the ESKAPE WSL2 DB build failed (see §17 in KB — taxonomy mapping issue with the Perl script on WSL2). the 8 GB DB is what most labs actually run.

### exact command

```bash
perf stat -e task-clock,cache-misses,cache-references,instructions,cycles \
    kraken2 --db /path/to/k2_standard_08gb \
    --report report.txt barcode02.fastq > output.kraken
```

### results

| counter | value | notes |
|---|---|---|
| task-clock | 93,832 ms | CPU time used |
| cache-misses | 301,288,020 | 301 million misses |
| cache-references | 879,854,514 | 880 million total accesses |
| **cache miss rate** | **34.24%** | 1 in 3 accesses goes to RAM |
| instructions | 155,949,518,373 | 156 billion |
| cycles | 68,853,332,412 | 69 billion |
| IPC (unreliable) | 2.26 | clock is wrong — see caveat |
| wall time | 159.4 s | ~2.6 minutes total |
| user time | 39.7 s | CPU in user space |
| sys time | 52.5 s | CPU in kernel (memory management) |

**caveat on IPC:** perf reported the clock at 0.734 GHz. the real Ryzen 5800H runs at ~3.2 GHz. Hyper-V blocks accurate clock counters in WSL2. IPC is meaningless. the cache miss rate is a ratio and doesn't depend on clock frequency. that's what we trust.

### what the numbers mean

**cache miss rate: 34.24%**

normal for a well-cached program: 1-5%. we got 34.24%. 1 in 3 memory accesses goes all the way to RAM.

why? kraken-2 hashes each k-mer from a read and looks it up in an 8 GB hash table. that table is 500x larger than the L3 cache (~16 MB on Ryzen 5800H). so every lookup lands at a random address in RAM. almost every one misses every cache level. the CPU issues the lookup, then sits idle for ~100 ns waiting for RAM to respond. at 301 million misses, that's the dominant cost.

**sys time: 52.5 s (33% of wall time)**

33% of runtime is in kernel. that's memory mapping overhead. the OS is paging the 8 GB database into memory through the page table. this is separate from the cache miss cost — this is just the OS handling the virtual memory for the database.

**verdict: memory-bound.** the CPU is not the bottleneck. RAM is. the CPU is mostly waiting.

### why this justifies the LRU k-mer cache

one cache hit = one RAM lookup avoided = ~100 ns saved. at 301 million misses:
- 10% hit rate = 30M fewer RAM accesses = ~3 seconds saved
- 20% hit rate = 60M fewer = ~6 seconds saved

the cache doesn't need to be large. clinical samples have dominant species — the same k-mers repeat heavily across reads in the same barcode. it's not uniformly random access. a hot set exists. that's the whole argument.

---

## tool 2 — nsight systems (dorado GPU profile)

### what nsight systems is

nsys is NVIDIA's sampling profiler for GPU programs. it records:
- NVTX annotations (labels dorado puts in its own code to mark stages)
- CUDA kernel execution times (which GPU kernels ran, for how long)
- CUDA API calls (what the CPU asked the GPU to do)
- memory transfers between CPU RAM and GPU VRAM

it writes a `.nsys-rep` file you open in the nsight GUI, plus a `.sqlite` file you can query directly.

### getting nsight working

nsight 2024.2.3 on Windows. several issues hit:

1. `--` separator not supported in nsys 2024.2.3 — remove it
2. `osrt` is not a valid trace type in this version — don't include it
3. `--stats` flag is ambiguous — use `-o` for output file name instead
4. must run as Administrator for full CUDA tracing

### input

- file: `FBE01990_24778b97_03e50f91_10.pod5` — 104,478 reads, 4 GB
- dorado mode: fast
- batchsize: 64

### exact command

```bash
nsys profile -o dorado_fast_profile --trace cuda,nvtx \
    dorado.exe basecaller fast pod5_file --batchsize 64
```

output: `dorado_fast_profile.nsys-rep` and `.sqlite`. total run ~3 hours including nsys overhead on GTX 1650 (fast mode without profiling takes ~5 min).

### results — NVTX stage breakdown

NVTX annotations are labels dorado writes into its own code. nsys times each label.

| % time | total time | instances | avg per call | stage |
|---|---|---|---|---|
| 39.8% | 3,180 s | 9,085 | 350 ms | basecall_current_batch |
| 39.8% | 3,179 s | 9,085 | 350 ms | call_chunks |
| 19.6% | 1,569 s | 9,086 | 173 ms | cuda_thread_fn_device_0 |
| 0.2% | 19.5 s | 9,087 | 2.1 ms | nn_forward |
| 0.1% | 8.9 s | 9,085 | 0.98 ms | cpu_decode |
| 0.1% | 8.1 s | 9,087 | 0.89 ms | lstm_stack |
| 0.1% | 7.5 s | 9,087 | 0.83 ms | gpu_decode |
| 0.1% | 6.1 s | 27,261 | 0.22 ms | conv |

`basecall_current_batch` and `call_chunks` are nested — same wall time, different label names for the same span. `cuda_thread_fn_device_0` is the actual GPU thread work per batch.

9,085 batches = 104,478 reads / ~11.5 reads per batch at batchsize 64.

### results — CUDA GPU kernels (where GPU time actually goes)

| % GPU time | total time | avg per call | kernel |
|---|---|---|---|
| **68.5%** | 1,069 s | 19.6 ms | cutlass GEMM 128x64 (Tensor Cores, FP16) |
| **13.5%** | 211 s | 23.3 ms | cutlass GEMM 128x128 (Tensor Cores, FP16) |
| 4.7% | 73.8 s | 8.1 ms | beam_search_step |
| 4.5% | 71.0 s | 2.6 ms | LSTM forward (96 channels) |
| 3.0% | 47.3 s | 2.6 ms | LSTM backward (96 channels) |
| 1.6% | 24.3 s | 2.7 ms | convolution_ntc |
| 1.3% | 20.7 s | 2.3 ms | decode_step |
| 1.3% | 20.2 s | 2.2 ms | compute_posts_step |

**82% of all GPU time is GEMM.** 68.5% + 13.5%. these are the transformer attention and linear projection layers. they use CUTLASS (NVIDIA's optimized GEMM library). `h884` means FP16 Tensor Core operations on 8×8×4 tiles. this is the neural network doing actual basecalling math.

### results — CUDA API (what the CPU does with CUDA)

| % time | calls | avg per call | API |
|---|---|---|---|
| **98.9%** | 27,283 | 56.6 ms | cudaStreamSynchronize |
| 0.5% | 190,891 | 43.5 µs | cudaLaunchKernel |
| 0.3% | 27,304 | 186 µs | cudaMemcpyAsync |

`cudaStreamSynchronize` is 98.9% of CUDA API time. what this means: the CPU launches a batch of kernels, then immediately calls `cudaStreamSynchronize` and blocks. it does nothing until the GPU finishes. the CPU is idle the entire time the GPU works. 27,283 calls × 56.6 ms average = ~1,544 seconds of CPU just sitting there.

this is a synchronous pipeline. GPU is the bottleneck, not CPU.

### results — memory transfers

| % time | total data | count | direction |
|---|---|---|---|
| 59.9% | 11,427 MB | 9,112 | CPU RAM → GPU VRAM (signal data in) |
| 25.1% | 11,427 MB | 9,107 | GPU internal |
| 15.0% | 2,856 MB | 9,085 | GPU VRAM → CPU RAM (reads out) |

total moved: ~25.7 GB over the full run. per batch: ~1.25 MB in, ~0.31 MB out.

transfers are a small fraction of total time. the GPU is not waiting on data. it's busy computing. memory is not the bottleneck here.

### verdict: compute-bound

- 82% of GPU time is GEMM — pure matrix math
- CPU is blocking on `cudaStreamSynchronize`, waiting on the GPU
- memory transfers are minor

dorado on GTX 1650 (fast mode) is compute-bound.

### why this justifies the S2B cache

if the S2B cache hits for a batch, it skips the GEMM kernels entirely for that batch. GEMM is 82% of GPU time. even a 30% hit rate would save ~25% of total GPU time.

the cache lookup has to be faster than one GEMM call (avg 19.6 ms). if it's slower, there's no point. on GTX 1650, shared memory per SM is 64 KB — the cache has to be small and hot. LSH on the GPU in shared memory is the right design.

one constraint to note: the pipeline is synchronous (CPU blocks on `cudaStreamSynchronize`). there's no CPU-side parallelism to hide a slow lookup. the lookup has to happen GPU-side.

---

## what we haven't run yet

### gprof — CPU call graph for kraken-2

kraken-2 was compiled with `-pg` flag (added to `src/Makefile`). this instruments every function call. after the run, `gprof` reads a `gmon.out` file and produces a call graph: which functions ran, how long each took, how many times called.

we haven't actually run `gprof` yet because the FASTQ inputs for WSL2 profiling were from interrupted runs (truncated files). the nsys BAM is complete but needs converting to FASTQ first.

command when ready:
```bash
./kraken2 --db db reads.fastq > /dev/null
gprof ./kraken2 gmon.out > callgraph.txt
```
this would tell us: which specific function inside kraken-2 is the hot one. the cache miss rate from perf tells us it's memory-bound, but gprof would tell us *which function* to look at first.

### cachegrind — per-function cache miss rates

`valgrind --tool=cachegrind` simulates the full L1/L2/L3 cache hierarchy in software. it's slower than perf (10–50x overhead) but gives per-function and per-line cache miss data. this is how we compensate for LLC counters being blocked by Hyper-V in WSL2.

```bash
valgrind --tool=cachegrind ./kraken2 --db db reads.fastq
cg_annotate cachegrind.out.<pid>
```

this would tell us: not just "kraken-2 has 34% cache miss rate overall" but "function X inside kraken-2 has 80% miss rate at line Y". much more precise for targeting optimizations.

### perf record + perf report — hotspot functions

`perf stat` gives totals. `perf record` samples where the program is at 1000 Hz and builds a histogram of hot addresses. `perf report` maps those addresses to function names and source lines.

```bash
perf record -g kraken2 --db db reads.fastq
perf report
```

this would show the call chain leading to the hot code. useful after we know from perf stat that it's memory-bound — `perf record` would show us *where*.

---

## summary table — what we ran vs what's left

| tool | status | what it gave us |
|---|---|---|
| perf stat (kraken-2) | done | 34.24% cache miss rate, memory-bound verdict |
| nsight systems (dorado) | done | 82% GEMM, compute-bound verdict |
| gprof (kraken-2) | not run | would give function-level time breakdown |
| cachegrind (kraken-2) | not run | would give per-function cache miss rates |
| perf record (kraken-2) | not run | would give hotspot function + source line |
| nsight compute (dorado) | not run | would give per-kernel SM occupancy, memory bandwidth, arithmetic intensity |

the two runs we did are enough to establish the bottleneck in each stage. the remaining tools would give us precision: *which function* inside kraken-2 to patch, *which kernel* inside dorado has headroom.
