#!/usr/bin/env bash
# run_all.sh - top-level GPU matmul orchestrator.
# Builds everything, runs the timing sweep, then ncu + nsys profiling.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================================"
echo " Luna GPU matmul full run"
echo " Host: $(hostname)"
echo " Started: $(date -Iseconds)"
echo "============================================================"

echo ""
echo ">>> Step 0/4  GPU sanity check"
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv

echo ""
echo ">>> Step 1/4  build all variants"
make clean
make all

echo ""
echo ">>> Step 2/4  timing sweep (N=1024,2048,4096,10000)"
"$SCRIPT_DIR/run_timing.sh"

echo ""
echo ">>> Step 3/4  Nsight Compute kernel metrics (N=2048)"
"$SCRIPT_DIR/run_ncu.sh" 2048

echo ""
echo ">>> Step 4/4  Nsight Systems timeline (N=2048)"
"$SCRIPT_DIR/run_nsys.sh" 2048

echo ""
echo "============================================================"
echo " DONE: $(date -Iseconds)"
echo " Results: gpu_results/"
echo "   timing/   timing + GFLOPS sweep"
echo "   ncu/      kernel-level metrics (.ncu-rep + _summary.txt)"
echo "   nsys/     system timeline (.nsys-rep + _stats.txt)"
echo "============================================================"
