# matmul_gpu_bundle

Self-contained GPU matrix-multiply benchmark suite for Luna.
Mirrors the CPU bundle structure - send the whole folder, run `./run_all.sh`, pull `gpu_results/` back.

## Prerequisites on Luna

```bash
nvidia-smi          # confirm a GPU exists and driver is loaded
nvcc --version      # CUDA toolkit
which ncu nsys      # Nsight Compute + Nsight Systems (usually ship with CUDA)
```

If `nvidia-smi` reports no device, Luna doesn't have a GPU attached and none of this will run - skip the GPU work and use the negative result ("the production server is CPU-only") as the slide for Kolin sir.

## Variants (7 total)

| Binary | What it shows |
|---|---|
| `naive_gpu` | One thread per C[i,j], all global memory. The GPU equivalent of `naive_ijk`. Reference floor. |
| `coalesced_gpu` | Same algorithm, proper warp-coalesced access pattern. |
| `shared_tiled` | Classic 32x32 shared-memory tile. The GPU equivalent of CPU `tiled.c`. |
| `shared_tiled_2d` | Shared-mem + register tiling (each thread does 8x8). Real-kernel pattern. |
| `cublas_sgemm` | NVIDIA's hand-tuned FP32 GEMM. Upper bound for FP32. |
| `cublas_tensor` | cuBLAS with TF32 Tensor Cores (Ampere+). Expected ~8x over `cublas_sgemm`. |
| `wmma_manual` | Manual FP16 Tensor Core programming via the WMMA C++ API. Shows what cuBLAS does under the hood. |

All variants use **single-precision (float)**. CPU baseline was double - documented intentional difference; modern GPU hardware (Tensor Cores) doesn't optimise for FP64.

## How to run on Luna

```bash
# from local machine:
rsync -av Luna/profiling/matmul_gpu_bundle/ student@luna.cse.iitd.ac.in:~/matmul_gpu/

# on Luna:
ssh student@luna.cse.iitd.ac.in
cd ~/matmul_gpu
chmod +x *.sh
./run_all.sh 2>&1 | tee run_all.log

# back on local:
rsync -av student@luna.cse.iitd.ac.in:~/matmul_gpu/gpu_results/ Luna/profiling/matmul_gpu_bundle/gpu_results/
```

## Scripts

| Script | Purpose | Runtime |
|---|---|---|
| `run_all.sh` | Orchestrator - build + timing + ncu + nsys | ~15-30 min |
| `run_timing.sh` | Wall time + GFLOPS sweep across N=1024,2048,4096,10000 | ~5-10 min |
| `run_ncu.sh [N]` | Nsight Compute - per-kernel metrics (DRAM throughput, occupancy, tensor core util) | ~5 min |
| `run_nsys.sh [N]` | Nsight Systems - timeline (kernel vs memcpy vs idle) | ~3 min |

## Build configuration

Default Makefile uses `-arch=native` (CUDA 11.7+). If that fails, override:

```bash
make ARCH=sm_80   # A100
make ARCH=sm_90   # H100
make ARCH=sm_75   # T4 / RTX 20-series
make ARCH=sm_86   # RTX 30-series / A40
```

## What to compare against CPU

Once `gpu_results/timing/all_timing.txt` is filled, the headline cross-platform comparison:

| N=10000 | CPU best (Luna pending) | GPU best (cublas_tensor) | Ratio |
|---|---|---|---|
| Wall time | ~112s (omp_tiled WSL2) | ~50-200ms (estimated) | ~500-2000x |

This is the slide that justifies "why CPU optimisation matters for Kraken2 specifically": dense linalg moves to GPU and gains 1000x, but Kraken2's hash-table workload **cannot** make this jump because of scatter-gather access patterns. The GPU numbers are the foil that makes the CPU work load-bearing.

## Profiling output map

```
gpu_results/
  timing/
    all_timing.txt              flat human-readable table of all runs
  ncu/
    {bin}_N2048.ncu-rep         binary report - open in Nsight Compute GUI
    {bin}_N2048_summary.txt     text dump - grep for DRAM/L1/L2/Tensor
  nsys/
    {bin}_N2048.nsys-rep        timeline - open in Nsight Systems GUI
    {bin}_N2048_stats.txt       text kernel summary
```

For the meeting, the ncu summary lines we care about are:
- **Achieved Occupancy** - how well kernels use the SM
- **DRAM Throughput** - GB/s achieved vs peak (~2 TB/s on A100, ~3 TB/s on H100)
- **Compute (SM) Throughput** - % of peak FLOPS
- **Tensor Active** - % of time tensor cores were busy (only for cublas_tensor / wmma_manual)
