#!/usr/bin/env bash
# run_ncu.sh - Nsight Compute kernel-level metrics for the key variants.
# Captures: SM occupancy, DRAM throughput, L1/L2 hit rates, compute throughput,
# tensor core utilisation.
#
# ncu is the GPU equivalent of perf stat -d for a CPU kernel. Output is a detailed
# .ncu-rep file plus a human-readable summary section.
#
# Usage: ./run_ncu.sh [N=2048]

set -euo pipefail
N=${1:-2048}
OUT="gpu_results/ncu"
mkdir -p "$OUT"

# Pick a representative N - too small and kernels don't saturate the GPU,
# too large and ncu replay overhead is huge.

BINS=(naive_gpu coalesced_gpu shared_tiled shared_tiled_2d
      cublas_sgemm cublas_tensor wmma_manual)

# --set full captures everything; --set roofline gives the roofline view.
# We use detailed which covers SM, memory, instruction stats.
NCU_FLAGS="--set detailed --target-processes all --force-overwrite"

echo "============================================================"
echo " Nsight Compute - kernel metrics at N=$N"
echo "============================================================"

for bin in "${BINS[@]}"; do
    if [[ ! -x "./$bin" ]]; then echo "skip $bin"; continue; fi
    echo ">>> $bin"
    ncu $NCU_FLAGS -o "$OUT/${bin}_N${N}" ./"$bin" "$N" \
        > "$OUT/${bin}_N${N}_summary.txt" 2>&1 || true
    # Pull the most relevant lines for quick review.
    grep -E "DRAM|L1|L2|SM|Achieved|Tensor|FLOPs|Bandwidth|Occupancy" \
         "$OUT/${bin}_N${N}_summary.txt" | head -30 || true
    echo ""
done

echo "Full reports: $OUT/*.ncu-rep (open in Nsight Compute GUI)"
echo "Text summaries: $OUT/*_summary.txt"
