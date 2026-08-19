#!/bin/bash
# Collect L1 / L2 / L3 cache stats separately from timing stats
# to avoid counter-multiplexing dropout.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

BINS=(naive_ijk ikj_order kij_order transpose_B tiled
      omp_parallel omp_tiled unrolled_ikj avx2_manual
      auto_vec_O3 tiled_avx2 prefetch_ikj)

# --- pass 1: cache hierarchy ---
CACHE_EVENTS='L1-dcache-loads:u,L1-dcache-load-misses:u,l2_request_g1.all_no_prefetch:u,l2_cache_misses_from_dc_misses:u,cache-references:u,cache-misses:u'

# --- pass 2: timing + pipeline ---
PIPE_EVENTS='task-clock:u,instructions:u,cycles:u,branches:u,branch-misses:u,stalled-cycles-frontend:u'

collect() {
    local bin=$1
    local N=$2
    local pass=$3
    local events=$4
    OMP_NUM_THREADS=4 perf stat -e "$events" "./$bin" "$N" 2>&1
}

print_header() {
    local N=$1
    echo ""
    echo "========================================================================"
    echo "  CACHE HIERARCHY — N = $N"
    echo "========================================================================"
    printf '%-18s %10s %9s %10s %9s %10s %9s\n' \
        'Binary' 'L1-loads' 'L1-miss%' 'L2-req' 'L2-miss%' 'L3-refs' 'L3-miss%'
    echo "------------------------------------------------------------------------"
}

run_cache_size() {
    local N=$1
    print_header "$N"
    for bin in "${BINS[@]}"; do
        if [[ ! -x "./$bin" ]]; then
            printf '%-18s  *** not built ***\n' "$bin"; continue
        fi
        RAW=$(collect "$bin" "$N" cache "$CACHE_EVENTS")

        L1L=$(echo "$RAW"  | awk '/L1-dcache-loads:u/{gsub(/,/,"",$1); print $1}')
        L1M=$(echo "$RAW"  | awk '/L1-dcache-load-misses:u/{gsub(/,/,"",$1); print $1}')
        L2R=$(echo "$RAW"  | awk '/l2_request_g1.all_no_prefetch:u/{gsub(/,/,"",$1); print $1}')
        L2M=$(echo "$RAW"  | awk '/l2_cache_misses_from_dc_misses:u/{gsub(/,/,"",$1); print $1}')
        L3R=$(echo "$RAW"  | awk '/cache-references:u/{gsub(/,/,"",$1); print $1}')
        L3M=$(echo "$RAW"  | awk '/cache-misses:u/{gsub(/,/,"",$1); print $1}')

        L1P=$(awk "BEGIN{l=${L1L:-1}; m=${L1M:-0}; printf \"%.1f\", m/(l>0?l:1)*100}")
        L2P=$(awk "BEGIN{r=${L2R:-1}; m=${L2M:-0}; printf \"%.1f\", m/(r>0?r:1)*100}")
        L3P=$(awk "BEGIN{r=${L3R:-1}; m=${L3M:-0}; printf \"%.1f\", m/(r>0?r:1)*100}")

        printf '%-18s %10s %8s%% %10s %8s%% %10s %8s%%\n' \
            "$bin" "$L1L" "$L1P" "$L2R" "$L2P" "$L3R" "$L3P"
    done
}

run_cache_size 1024
run_cache_size 2048
