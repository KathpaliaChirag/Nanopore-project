#!/usr/bin/env bash
# run_nsys.sh - Nsight Systems system-wide timeline profiling.
# Captures: kernel launch overhead, memcpy time vs compute time, GPU idle gaps.
# Useful for seeing whether H<->D transfers dominate over compute.
#
# nsys is the GPU equivalent of perf record - timeline, not metrics.
#
# Usage: ./run_nsys.sh [N=2048]

set -euo pipefail
N=${1:-2048}
OUT="gpu_results/nsys"
mkdir -p "$OUT"

BINS=(naive_gpu shared_tiled_2d cublas_sgemm cublas_tensor wmma_manual)

echo "============================================================"
echo " Nsight Systems - timeline profiling at N=$N"
echo "============================================================"

for bin in "${BINS[@]}"; do
    if [[ ! -x "./$bin" ]]; then echo "skip $bin"; continue; fi
    echo ">>> $bin"
    nsys profile --stats=true --force-overwrite=true \
                 -o "$OUT/${bin}_N${N}" \
                 ./"$bin" "$N" \
        > "$OUT/${bin}_N${N}_stats.txt" 2>&1 || true
    # Print the kernel summary table that nsys emits.
    grep -A 20 "CUDA Kernel Statistics" "$OUT/${bin}_N${N}_stats.txt" | head -25 || true
    echo ""
done

echo "Reports: $OUT/*.nsys-rep (open in Nsight Systems GUI for timeline)"
echo "Text stats: $OUT/*_stats.txt"
