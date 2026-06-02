#!/usr/bin/env bash
# run_tma_luna.sh — Top-down Microarchitecture Analysis for matmul on Sapphire Rapids.
#
# Fills the TMA Breakdown table in results_matmul_luna.md.
# Captures memory_bound / core_bound / l1_bound / l2_bound / l3_bound / dram_bound
# for naive_ijk vs tiled_avx2 at both N values — the key "why is it slow" evidence.
#
# Usage: ./run_tma_luna.sh

set -euo pipefail

OUT="perf_results_luna/tma"
mkdir -p "$OUT"

# Level-1 and Level-2 TMA metrics on SPR.
TMA="tma_memory_bound,tma_core_bound,\
tma_l1_bound,tma_l2_bound,tma_l3_bound,tma_dram_bound,\
tma_branch_mispredicts,tma_machine_clears,\
tma_info_core_ilp"

PAIRS=(
    "naive_ijk 1024"
    "naive_ijk 2048"
    "tiled_avx2 1024"
    "tiled_avx2 2048"
    "tiled_avx2 10000"
    "omp_tiled 10000"
)

echo "============================================================"
echo " TMA breakdown (Sapphire Rapids) — naive_ijk vs tiled_avx2"
echo "============================================================"

for pair in "${PAIRS[@]}"; do
    read -r bin N <<<"$pair"
    if [[ ! -x "./$bin" ]]; then
        echo "  skip $bin (not built)"; continue
    fi

    echo ">>> $bin  N=$N"
    OUTFILE="$OUT/${bin}_N${N}_tma.txt"
    OMP_NUM_THREADS=4 perf stat -M "$TMA" \
        -o "$OUTFILE" ./"$bin" "$N" >/dev/null 2>&1
    # Echo the metric lines inline for quick eyeball during the run.
    grep -E "tma_" "$OUTFILE" | sed 's/^/    /'
done

echo "============================================================"
echo " Full output: $OUT/*.txt"
