#!/usr/bin/env bash
# run_perf_all.sh — run perf stat on every matmul binary and emit a summary
# Usage: ./run_perf_all.sh [N] [THREADS]
#   N       matrix dimension  (default 1024)
#   THREADS OMP thread count  (default 4)

set -euo pipefail

N=${1:-1024}
THREADS=${2:-4}
OUT=perf_results
mkdir -p "$OUT"

BINS=(
    naive_ijk
    ikj_order
    kij_order
    transpose_B
    tiled
    omp_parallel
    omp_tiled
    unrolled_ikj
    avx2_manual
    auto_vec_O3
    tiled_avx2
    prefetch_ikj
)

EVENTS="cache-misses,cache-references,\
L1-dcache-load-misses,L1-dcache-loads,\
LLC-load-misses,LLC-loads,\
instructions,cycles,\
branches,branch-misses,\
task-clock"

echo "================================================================"
echo " Matrix Multiplication perf stat  N=$N  OMP_NUM_THREADS=$THREADS"
echo "================================================================"
printf "%-18s %12s %12s %12s %12s %12s\n" \
       "Binary" "Time(ms)" "IPC" "L1-miss%" "LLC-miss%" "Br-miss%"
echo "----------------------------------------------------------------"

for bin in "${BINS[@]}"; do
    if [[ ! -x "./$bin" ]]; then
        echo "  $bin not found — skipping (run make first)"
        continue
    fi

    RAW="$OUT/${bin}_raw.txt"
    OMP_NUM_THREADS=$THREADS \
    perf stat -e "$EVENTS" ./"./$bin" "$N" 2>"$RAW" >/dev/null

    # extract fields from perf output
    TIME=$(grep "task-clock"         "$RAW" | awk '{print $1}' | tr -d ',')
    CYC=$( grep "cycles"             "$RAW" | awk '{print $1}' | tr -d ',')
    INS=$( grep "instructions"       "$RAW" | awk '{print $1}' | tr -d ',')
    L1L=$( grep "L1-dcache-loads,"   "$RAW" | awk '{print $1}' | tr -d ',')
    L1M=$( grep "L1-dcache-load-miss" "$RAW" | awk '{print $1}' | tr -d ',')
    LLCL=$(grep "LLC-loads,"         "$RAW" | awk '{print $1}' | tr -d ',')
    LLCM=$(grep "LLC-load-misses"    "$RAW" | awk '{print $1}' | tr -d ',')
    BRL=$( grep "branches,"          "$RAW" | awk '{print $1}' | tr -d ',')
    BRM=$( grep "branch-misses"      "$RAW" | awk '{print $1}' | tr -d ',')

    IPC=$(awk  "BEGIN{printf \"%.2f\", ($INS+0)/($CYC+1)}")
    L1P=$(awk  "BEGIN{printf \"%.2f\", ($L1M+0)/($L1L+1)*100}")
    LLCP=$(awk "BEGIN{printf \"%.2f\", ($LLCM+0)/($LLCL+1)*100}")
    BRP=$( awk "BEGIN{printf \"%.2f\", ($BRM+0)/($BRL+1)*100}")
    MS=$(  awk "BEGIN{printf \"%.0f\", $TIME}")

    printf "%-18s %12s %12s %11s%% %11s%% %11s%%\n" \
           "$bin" "$MS" "$IPC" "$L1P" "$LLCP" "$BRP"
done

echo "================================================================"
echo "Full perf output in $OUT/*_raw.txt"
