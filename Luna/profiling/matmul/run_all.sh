#!/usr/bin/env bash
# run_all.sh — top-level orchestrator for the Luna matmul benchmark run.
#
# Runs everything: perf stat at N=1024/2048/10000, cache hierarchy (Intel events),
# TMA breakdown, and TILE=32 sweep. Roughly 60 minutes total wall time, dominated
# by naive_ijk at N=2048 (~2 min) and ikj/kij at N=10000 (~7-20 min each).
#
# Run from the directory containing the matmul .c files and Makefile.
#
# Usage: ./run_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================================"
echo " Luna matmul full run"
echo " Host:    $(hostname)"
echo " CPU:     $(grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)"
echo " Started: $(date -Iseconds)"
echo "============================================================"

echo ""
echo ">>> Step 1/5  build all binaries"
make clean
make all

echo ""
echo ">>> Step 2/5  perf stat at N=1024"
"$SCRIPT_DIR/run_perf_luna.sh" 1024 4

echo ""
echo ">>> Step 3/5  perf stat at N=2048"
"$SCRIPT_DIR/run_perf_luna.sh" 2048 4

echo ""
echo ">>> Step 4/5  perf stat at N=10000 (long, ~20-40 min)"
"$SCRIPT_DIR/run_perf_luna.sh" 10000 4

echo ""
echo ">>> Step 5a/5  cache hierarchy (Intel mem_load_retired events)"
"$SCRIPT_DIR/run_cache_hierarchy_luna.sh" 1024 2048

echo ""
echo ">>> Step 5b/5  TMA breakdown"
"$SCRIPT_DIR/run_tma_luna.sh"

echo ""
echo ">>> Step 5c/5  TILE=32 sweep"
"$SCRIPT_DIR/run_tile32_luna.sh"

echo ""
echo "============================================================"
echo " DONE: $(date -Iseconds)"
echo " Results: perf_results_luna/"
echo "   N1024/   pipeline + stall passes per binary"
echo "   N2048/   pipeline + stall passes per binary"
echo "   N10000/  pipeline + stall passes per binary"
echo "   cache_hierarchy/   Intel per-level cache stats"
echo "   tma/               TMA Level-1/2 breakdown"
echo "   tile32/            TILE=32 sweep"
echo " Fill the tables in Luna/profiling/results_matmul_luna.md"
echo "============================================================"
