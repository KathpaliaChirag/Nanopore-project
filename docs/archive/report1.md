# profiling report - nanopore pipeline
**prepared by:** chirag kathpalia

---

## system setup

| component | detail |
|---|---|
| OS | Windows 11 Home |
| WSL2 kernel | 6.6.87.2-microsoft-standard-WSL2 |
| linux distro | Ubuntu 24.04.4 LTS (Noble Numbat) |
| architecture | x86_64 |
| CPU | AMD Ryzen 7 5800H |
| RAM | 14 GB |
| GPU | NVIDIA GTX 1650, 4 GB VRAM |

## tools installed

| tool | version |
|---|---|
| valgrind | 3.22.0 |
| build-essential | 12.10ubuntu1 |
| git | 2.43.0 |
| cmake | 3.28.3 |
| perf | built from WSL2-Linux-Kernel source (tag linux-msft-wsl-6.6.87.2). hardware counters work (cycles, instructions, cache-misses, branches). LLC-specific counters (LLC-loads, LLC-load-misses) show `<not supported>` - Hyper-V doesn't expose them. per-function LLC data covered by cachegrind. |
| nsight systems | 2024.2.3.38 (Windows) |
| samtools | installed via apt in WSL2 |

---

## page 1 - kraken-2 CPU profile (perf stat)

**input:** barcode02.fastq - 104,829 reads, 357.62 Mbp  
**database:** k2_standard_08gb (8 GB pre-built standard database)  
**tool:** perf stat -e task-clock,cache-misses,cache-references,instructions,cycles  
**environment:** WSL2 (Ubuntu 24.04), AMD Ryzen 7 5800H, 14 GB RAM

---

### 1.1 perf stat results

| counter | value | notes |
|---|---|---|
| task-clock | 93,832 ms | CPU time used |
| cache-misses | 301,288,020 | 301 million cache misses |
| cache-references | 879,854,514 | 880 million total cache accesses |
| **cache miss rate** | **34.24%** | 1 in 3 cache accesses goes to RAM |
| instructions | 155,949,518,373 | 156 billion instructions |
| cycles | 68,853,332,412 | 69 billion cycles |
| IPC | 2.26 insn/cycle | unreliable - see caveat below |
| wall time | 159.4 s | total elapsed time |
| user time | 39.7 s | CPU in user space |
| sys time | 52.5 s | CPU in kernel (memory management) |

**WSL2 caveat on IPC:** perf reported the clock at 0.734 GHz. the actual Ryzen 5800H runs at ~3.2 GHz. Hyper-V doesn't pass real hardware clock counters through to WSL2, so IPC and cycle counts are not usable. i'm ignoring them. the cache miss rate is a ratio, so clock accuracy doesn't matter there. that's the number i trust.

---

### 1.2 verdict - memory-bound

kraken-2 with the 8 GB database is memory-bound. badly.

| evidence | value | what it means |
|---|---|---|
| cache miss rate | 34.24% | 1 in 3 accesses goes to slow RAM (normal: 1-5%) |
| cache misses total | 301 million | each miss costs ~100 ns RAM latency |
| sys time | 52.5 s (33% of wall time) | high kernel time = heavy memory mapping overhead |
| database size | 8 GB | doesn't fit in L3 cache (~16 MB on Ryzen 5800H) |

the reason is simple. kraken-2 hashes each read's k-mers and looks them up in an 8 GB hash table. that table is 500x larger than the L3 cache. every lookup lands at a random address in RAM, and almost every one misses cache. the CPU just sits there waiting for RAM instead of computing. 33% of wall time is kernel time - that's all the overhead from paging through an 8 GB file.

---

### 1.3 our observation on the hot-k-mer LRU cache

the 34.24% miss rate is what makes the LRU k-mer cache worth trying.

- one cache hit = one RAM lookup avoided = ~100 ns saved
- at 301 million misses per run, a 20% hit rate means 60 million fewer RAM accesses, roughly 6 seconds saved
- the cache doesn't need to be large. clinical samples have dominant species, so the same k-mers repeat heavily across reads. access isn't uniformly random.

key number: **34.24% cache miss rate**. 1 in 3 memory accesses goes to RAM. the LRU cache targets that directly.

---

---

## page 2 - dorado GPU profile (nsight systems)

**input:** FBE01990_24778b97_03e50f91_10.pod5 - 104,478 reads, 4 GB  
**mode:** fast  
**batchsize:** 64  
**tool:** nsys profile --trace cuda,nvtx

---

### 2.1 NVTX range summary - what dorado spends time on

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

`basecall_current_batch` and `call_chunks` are nested - same wall time, just different labels for the same execution. `cuda_thread_fn_device_0` is actual GPU execution time per batch, 19.6% of annotated time.

9,085 batches processed = 104,478 reads / ~11.5 reads per batch at batchsize 64.

---

### 2.2 CUDA GPU kernel summary - where GPU time actually goes

| % GPU time | total time | instances | avg per call | kernel |
|---|---|---|---|---|
| **68.5%** | 1,069 s | 54,522 | 19.6 ms | cutlass GEMM 128x64 (matrix multiply, Tensor Cores) |
| **13.5%** | 211 s | 9,087 | 23.3 ms | cutlass GEMM 128x128 (matrix multiply, Tensor Cores) |
| 4.7% | 73.8 s | 9,087 | 8.1 ms | beam_search_step |
| 4.5% | 71.0 s | 27,261 | 2.6 ms | LSTM (forward, 96 channels) |
| 3.0% | 47.3 s | 18,174 | 2.6 ms | LSTM (backward, 96 channels) |
| 1.6% | 24.3 s | 9,087 | 2.7 ms | convolution_ntc |
| 1.3% | 20.7 s | 9,087 | 2.3 ms | decode_step |
| 1.3% | 20.2 s | 9,087 | 2.2 ms | compute_posts_step |

GEMM is 82% of all GPU time (68.5% + 13.5%). these are the transformer attention and linear projection layers running on Tensor Cores (FP16, h884 tile). this is the neural network doing the actual basecalling math.

---

### 2.3 CUDA API summary - what the CPU does with CUDA

| % time | calls | avg per call | API call |
|---|---|---|---|
| **98.9%** | 27,283 | 56.6 ms | cudaStreamSynchronize |
| 0.5% | 190,891 | 43.5 µs | cudaLaunchKernel |
| 0.3% | 27,304 | 186 µs | cudaMemcpyAsync |

`cudaStreamSynchronize` is 98.9% of all CUDA API time. the CPU calls it 27,283 times, once per batch, and blocks for 56.6 ms each time waiting for the GPU to finish. the CPU is just idle during that wait. this is expected for a synchronous pipeline. GPU is the bottleneck, not CPU.

---

### 2.4 memory transfer summary

| % time | total data | count | operation |
|---|---|---|---|
| 59.9% | 11,427 MB | 9,112 | host to device (CPU RAM to GPU VRAM) |
| 25.1% | 11,427 MB | 9,107 | device to device (GPU internal) |
| 15.0% | 2,856 MB | 9,085 | device to host (GPU VRAM to CPU RAM) |

total moved: ~25.7 GB over the full run. per batch: ~1.25 MB CPU to GPU, ~0.31 MB GPU to CPU.

transfers are a small fraction of total time. the GPU isn't waiting on data - it's busy computing.

---

### 2.5 verdict - compute-bound

dorado (fast mode) on GTX 1650 is compute-bound.

- 82% of GPU time is GEMM - pure arithmetic
- CPU is blocking on `cudaStreamSynchronize`, waiting on the GPU. not the other way around.
- memory transfers are minor

**our observation on the signal-to-base (S2B) cache:**  
if the cache skips re-running the network for similar signal windows, it skips the GEMM kernels entirely. GEMM is 82% of GPU time, so even a 30% cache hit rate would probably save around 25% of total GPU time. the cache lookup itself has to be fast though - if it's slower than a GEMM call, there's no benefit. on GTX 1650, shared memory per SM is 64 KB, so the cache has to stay small and hot.
