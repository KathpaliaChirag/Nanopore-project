#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

BINS=(naive_ijk ikj_order kij_order transpose_B tiled
      omp_parallel omp_tiled unrolled_ikj avx2_manual
      auto_vec_O3 tiled_avx2 prefetch_ikj)

EVENTS='task-clock:u,cache-misses:u,instructions:u,cycles:u,branches:u,branch-misses:u,stalled-cycles-frontend:u'

run_size() {
    local N=$1
    echo "================================================================"
    echo " N = $N"
    echo "================================================================"
    printf '%-18s %10s %10s %13s %9s\n' 'Binary' 'Time(ms)' 'IPC' 'CacheMisses' 'BrMiss%'
    echo "----------------------------------------------------------------"
    for bin in "${BINS[@]}"; do
        if [[ ! -x "./$bin" ]]; then
            printf '%-18s  *** not built ***\n' "$bin"; continue
        fi
        RAW=$(OMP_NUM_THREADS=4 perf stat -e "$EVENTS" "./$bin" "$N" 2>&1)
        TIME_MS=$(echo "$RAW" | awk '/task-clock/{gsub(/,/,"",$1); print $1}')
        CYCLES=$(echo "$RAW"  | awk '/cycles:u/{gsub(/,/,"",$1); print $1}')
        INS=$(echo "$RAW"     | awk '/instructions:u/{gsub(/,/,"",$1); print $1}')
        CMISS=$(echo "$RAW"   | awk '/cache-misses:u/{gsub(/,/,"",$1); print $1}')
        BRL=$(echo "$RAW"     | awk '/branches:u/{gsub(/,/,"",$1); print $1}')
        BRM=$(echo "$RAW"     | awk '/branch-misses:u/{gsub(/,/,"",$1); print $1}')
        IPC=$(awk  "BEGIN{c=${CYCLES:-1}; i=${INS:-0}; printf \"%.2f\", i/(c>0?c:1)}")
        BRP=$(awk  "BEGIN{b=${BRL:-1}; m=${BRM:-0}; printf \"%.3f\", m/(b>0?b:1)*100}")
        printf '%-18s %10s %10s %13s %8s%%\n' "$bin" "$TIME_MS" "$IPC" "$CMISS" "$BRP"
    done
    echo ""
}

run_size 1024
run_size 2048
