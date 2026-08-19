#!/bin/bash
# N=10000 perf run — naive_ijk excluded (~4 hrs at this size, O(N^3) scaling)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

N=10000
OUT="perf_results/N10000"
mkdir -p "$OUT"

BINS=(ikj_order kij_order transpose_B tiled omp_parallel omp_tiled
      unrolled_ikj avx2_manual auto_vec_O3 tiled_avx2 prefetch_ikj)

TIMING='task-clock:u,instructions:u,cycles:u,branches:u,branch-misses:u,stalled-cycles-frontend:u'
CACHE='L1-dcache-loads:u,L1-dcache-load-misses:u,l2_request_g1.all_no_prefetch:u,l2_cache_misses_from_dc_misses:u,cache-references:u,cache-misses:u'

echo "========================================================================"
echo "  N = $N  |  $(date)"
echo "  naive_ijk skipped — O(N^3) scaling from N=2048 gives ~4 hrs"
echo "========================================================================"

printf '%-18s %12s %13s %9s %9s %9s\n' \
    'Binary' 'Time(ms)' 'CacheMisses' 'L2-miss%' 'L3-miss%' 'BrMiss%'
echo "------------------------------------------------------------------------"

for bin in "${BINS[@]}"; do
    if [[ ! -x "./$bin" ]]; then
        printf '%-18s  *** not built ***\n' "$bin"; continue
    fi

    T=$(OMP_NUM_THREADS=4 perf stat -e "$TIMING" "./$bin" "$N" 2>&1)
    C=$(OMP_NUM_THREADS=4 perf stat -e "$CACHE"  "./$bin" "$N" 2>&1)

    echo "$T" > "$OUT/${bin}_timing.txt"
    echo "$C" > "$OUT/${bin}_cache.txt"

    TIME_MS=$(echo "$T" | awk '/task-clock/{gsub(/,/,"",$1); print $1}')
    CMISS=$(echo "$T"   | awk '/cache-misses:u/{gsub(/,/,"",$1); print $1}')
    BRL=$(echo "$T"     | awk '/branches:u/{gsub(/,/,"",$1); print $1}')
    BRM=$(echo "$T"     | awk '/branch-misses:u/{gsub(/,/,"",$1); print $1}')

    L2R=$(echo "$C" | awk '/l2_request_g1.all_no_prefetch:u/{gsub(/,/,"",$1); print $1}')
    L2M=$(echo "$C" | awk '/l2_cache_misses_from_dc_misses:u/{gsub(/,/,"",$1); print $1}')
    L3R=$(echo "$C" | awk '/cache-references:u/{gsub(/,/,"",$1); print $1}')
    L3M=$(echo "$C" | awk '/cache-misses:u/{gsub(/,/,"",$1); print $1}')

    L2P=$(awk "BEGIN{r=${L2R:-1}; m=${L2M:-0}; printf \"%.1f\", m/(r>0?r:1)*100}")
    L3P=$(awk "BEGIN{r=${L3R:-1}; m=${L3M:-0}; printf \"%.1f\", m/(r>0?r:1)*100}")
    BRP=$(awk "BEGIN{b=${BRL:-1}; m=${BRM:-0}; printf \"%.3f\", m/(b>0?b:1)*100}")

    printf '%-18s %12s %13s %8s%% %8s%% %8s%%\n' \
        "$bin" "$TIME_MS" "$CMISS" "$L2P" "$L3P" "$BRP"
done

echo ""
echo "Done — $(date)"
echo "Raw output in $OUT/"
