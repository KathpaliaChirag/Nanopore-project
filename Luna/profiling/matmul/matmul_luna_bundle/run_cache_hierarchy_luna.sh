#!/usr/bin/env bash
# run_cache_hierarchy_luna.sh — Intel Sapphire Rapids replacement for the
# AMD-only run_cache_hierarchy.sh in All_Matric_Mul_perf_stats/.
#
# Uses mem_load_retired.* (PEBS) events for per-level hit/miss accounting.
# Requires perf_event_paranoid <= 0 (already set on Luna, see events_reference.md).
#
# Usage: ./run_cache_hierarchy_luna.sh [N=1024]   (also runs N=2048 if no arg given)

set -euo pipefail
N_LIST=("${@:-1024 2048}")

BINS=(naive_ijk ikj_order kij_order transpose_B tiled
      omp_parallel omp_tiled unrolled_ikj avx2_manual
      auto_vec_O3 tiled_avx2 prefetch_ikj)

# Intel per-level hit/miss events (PEBS). These replace the AMD-only
# l2_request_g1.all_no_prefetch / l2_cache_misses_from_dc_misses.
EVENTS="L1-dcache-loads,L1-dcache-load-misses,\
mem_load_retired.l2_hit,mem_load_retired.l2_miss,\
mem_load_retired.l3_hit,mem_load_retired.l3_miss,\
cache-references,cache-misses"

OUT="perf_results_luna/cache_hierarchy"
mkdir -p "$OUT"

extract() { awk -v key="$1" '$0 ~ key { gsub(/,/,"",$1); print $1; exit }'; }
pct()     { awk "BEGIN{a=${1:-0}; b=${2:-1}; printf \"%.2f\", (b>0?a/b*100:0)}"; }

for N in $N_LIST; do
    echo ""
    echo "========================================================================"
    echo "  CACHE HIERARCHY (Intel SPR) — N = $N"
    echo "========================================================================"
    printf '%-15s %12s %8s %12s %8s %12s %8s\n' \
        'Binary' 'L1-loads' 'L1-m%' 'L2-loads' 'L2-m%' 'L3-loads' 'L3-m%'
    echo "------------------------------------------------------------------------"

    for bin in "${BINS[@]}"; do
        if [[ ! -x "./$bin" ]]; then
            printf '%-15s  *** not built ***\n' "$bin"; continue
        fi
        if [[ "$bin" == "naive_ijk" && "$N" -ge 10000 ]]; then
            printf '%-15s  *** skipped (4 hr runtime) ***\n' "$bin"; continue
        fi

        RAW="$OUT/${bin}_N${N}.txt"
        OMP_NUM_THREADS=4 perf stat -e "$EVENTS" \
            -o "$RAW" ./"$bin" "$N" >/dev/null 2>&1

        L1L=$(extract 'L1-dcache-loads'      <"$RAW")
        L1M=$(extract 'L1-dcache-load-misses' <"$RAW")
        L2H=$(extract 'mem_load_retired.l2_hit'  <"$RAW")
        L2M=$(extract 'mem_load_retired.l2_miss' <"$RAW")
        L3H=$(extract 'mem_load_retired.l3_hit'  <"$RAW")
        L3M=$(extract 'mem_load_retired.l3_miss' <"$RAW")

        L2_TOT=$(awk "BEGIN{print (${L2H:-0}+${L2M:-0})}")
        L3_TOT=$(awk "BEGIN{print (${L3H:-0}+${L3M:-0})}")

        L1P=$(pct "${L1M:-0}" "${L1L:-1}")
        L2P=$(pct "${L2M:-0}" "$L2_TOT")
        L3P=$(pct "${L3M:-0}" "$L3_TOT")

        printf '%-15s %12s %7s%% %12s %7s%% %12s %7s%%\n' \
            "$bin" "${L1L:-?}" "$L1P" "$L2_TOT" "$L2P" "$L3_TOT" "$L3P"
    done
done

echo ""
echo "Raw perf output: $OUT/*.txt"
