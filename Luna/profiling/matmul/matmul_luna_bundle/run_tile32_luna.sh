#!/usr/bin/env bash
# run_tile32_luna.sh — Tile-32 sweep on Luna.
#
# Hypothesis (from PERF_REPORT.md analysis F): tiled_avx2's L3 miss% climbs
# 12.3% -> 15.9% as N goes 1024 -> 2048. Smaller tiles (TILE=32) should keep
# sub-blocks better isolated in L3.
#
# Rebuilds tiled, omp_tiled, tiled_avx2 with -DTILE=32 then runs perf stat
# at N=1024, 2048, 10000. Compare against the default TILE=64 results.
#
# Usage: ./run_tile32_luna.sh

set -euo pipefail

echo ">>> Rebuilding tiled variants with TILE=32"
make tile32

T32_BINS=(tiled_t32 omp_tiled_t32 tiled_avx2_t32)
SIZES=(1024 2048 10000)

EVENTS="task-clock,cycles,instructions,\
cache-references,cache-misses,\
LLC-loads,LLC-load-misses,\
L1-dcache-loads,L1-dcache-load-misses"

OUT="perf_results_luna/tile32"
mkdir -p "$OUT"

for N in "${SIZES[@]}"; do
    echo ""
    echo "============================================================"
    echo " TILE=32 sweep | N=$N"
    echo "============================================================"
    for bin in "${T32_BINS[@]}"; do
        if [[ ! -x "./$bin" ]]; then
            echo "  skip $bin (build failed?)"; continue
        fi
        echo ">>> $bin  N=$N"
        OMP_NUM_THREADS=4 perf stat -e "$EVENTS" \
            -o "$OUT/${bin}_N${N}.txt" ./"$bin" "$N" >/dev/null 2>&1
        grep -E "task-clock|cycles|instructions|cache" "$OUT/${bin}_N${N}.txt" | sed 's/^/    /'
    done
done

echo ""
echo "Done. Compare against perf_results_luna/N<size>/{tiled,omp_tiled,tiled_avx2}_pipe.txt"
