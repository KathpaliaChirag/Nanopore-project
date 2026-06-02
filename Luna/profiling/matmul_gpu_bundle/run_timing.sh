#!/usr/bin/env bash
# run_timing.sh - basic wall-time + GFLOPS sweep across all sizes.
# Each binary prints its own line; we just collect stdout.
#
# Usage: ./run_timing.sh  (runs N=1024, 2048, 4096, 10000)

set -euo pipefail

BINS=(naive_gpu coalesced_gpu shared_tiled shared_tiled_2d
      cublas_sgemm cublas_tensor wmma_manual)
SIZES=(1024 2048 4096 10000)

OUT="gpu_results/timing"
mkdir -p "$OUT"
LOG="$OUT/all_timing.txt"
: > "$LOG"

echo "============================================================" | tee -a "$LOG"
echo " Luna GPU matmul timing sweep" | tee -a "$LOG"
echo " GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -1)" | tee -a "$LOG"
echo " Started: $(date -Iseconds)" | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

for N in "${SIZES[@]}"; do
    echo "" | tee -a "$LOG"
    echo "--- N=$N ---" | tee -a "$LOG"
    for bin in "${BINS[@]}"; do
        if [[ ! -x "./$bin" ]]; then
            echo "skip $bin (not built)" | tee -a "$LOG"; continue
        fi
        # naive_gpu at N=10000 is the only one likely to be painful (~minutes).
        if [[ "$bin" == "naive_gpu" && "$N" -ge 10000 ]]; then
            echo "skip naive_gpu at N=$N (slow)" | tee -a "$LOG"; continue
        fi
        ./"$bin" "$N" | tee -a "$LOG"
    done
done

echo "" | tee -a "$LOG"
echo "Done. Summary in $LOG" | tee -a "$LOG"
