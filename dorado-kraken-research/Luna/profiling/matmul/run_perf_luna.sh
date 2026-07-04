#!/usr/bin/env bash
# run_perf_luna.sh — full perf stat for every matmul binary on Luna (Sapphire Rapids)
# Captures the metrics WSL2 could not: accurate IPC, cycle_activity stalls, TMA bounds.
#
# Usage:
#   ./run_perf_luna.sh [N] [THREADS]
#     N       matrix dimension (default 1024)
#     THREADS OMP threads      (default 4)
#
# Expects: binaries built via `make` in the current directory.
# Output : perf_results_luna/N<size>/<binary>.txt — full perf stat per run.

set -euo pipefail

N=${1:-1024}
THREADS=${2:-4}
OUT="perf_results_luna/N${N}"
mkdir -p "$OUT"

BINS=(
    naive_ijk ikj_order kij_order transpose_B tiled
    omp_parallel omp_tiled unrolled_ikj avx2_manual
    auto_vec_O3 tiled_avx2 prefetch_ikj
)

# Sapphire Rapids event set — split into two passes to avoid multiplexing.
# Pass 1: timing, pipeline, IPC, generic cache hierarchy.
EVENTS_PIPE="task-clock,cycles,instructions,\
branches,branch-misses,\
cache-references,cache-misses,\
LLC-loads,LLC-load-misses,\
L1-dcache-loads,L1-dcache-load-misses"

# Pass 2: Sapphire Rapids native stall events (replaces stalled-cycles-backend
# which is unsupported on this CPU — see events_reference.md).
EVENTS_STALL="cycle_activity.stalls_total,\
cycle_activity.stalls_l1d_miss,\
cycle_activity.stalls_l2_miss,\
cycle_activity.stalls_l3_miss,\
memory_activity.stalls_l3_miss"

echo "============================================================"
echo " Luna matmul perf run | N=$N | OMP_NUM_THREADS=$THREADS"
echo " Output: $OUT/"
echo "============================================================"

for bin in "${BINS[@]}"; do
    if [[ ! -x "./$bin" ]]; then
        echo "  skip $bin (not built — run make first)"
        continue
    fi

    # naive_ijk at N>=2048 takes 2+ minutes; warn but still run.
    if [[ "$bin" == "naive_ijk" && "$N" -ge 10000 ]]; then
        echo "  skip naive_ijk at N=$N (>4 hr runtime, see PERF_REPORT.md)"
        continue
    fi

    echo ">>> $bin (N=$N)  pass 1/2  pipeline+cache"
    OMP_NUM_THREADS=$THREADS \
        perf stat -e "$EVENTS_PIPE" \
                  -o "$OUT/${bin}_pipe.txt" \
                  ./"$bin" "$N" >/dev/null 2>&1

    echo ">>> $bin (N=$N)  pass 2/2  stall events"
    OMP_NUM_THREADS=$THREADS \
        perf stat -e "$EVENTS_STALL" \
                  -o "$OUT/${bin}_stall.txt" \
                  ./"$bin" "$N" >/dev/null 2>&1
done

echo "============================================================"
echo " Done. Combine with summarise_luna.sh or read $OUT/*.txt"
echo "============================================================"
