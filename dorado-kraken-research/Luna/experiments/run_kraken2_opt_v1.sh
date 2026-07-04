#!/usr/bin/env bash
# One-shot: apply kraken2_opt_v1.patch, rebuild classify, run a baseline
# (unpatched) and an optimised run, dump perf stat for each, print deltas.
#
# Usage on Luna:
#   bash ~/run_kraken2_opt_v1.sh
# Outputs go to ~/results/profiling/opt_v1/ . Paste the SUMMARY block back.
set -euo pipefail

SRC=~/kraken2-src
BUILD=~/kraken2-build
DB=~/data/kraken2_db
INPUT=~/results/basecalling/reads_hac.fastq
OUT=~/results/profiling/opt_v1
PATCH=${1:-~/kraken2_opt_v1.patch}

mkdir -p "$OUT"
cd "$SRC"

# Snapshot the current binary so we can compare against today's "best" build.
git -C "$SRC" stash -u >/dev/null 2>&1 || true
git -C "$SRC" reset --hard HEAD >/dev/null

# --- BASELINE (master, unpatched) -------------------------------------------
echo "[1/4] Building baseline (master)..."
cd "$SRC/src" && make -s clean && make -s -j 96
cp classify "$BUILD/classify.base"

# --- PATCHED build ----------------------------------------------------------
echo "[2/4] Applying $PATCH"
cd "$SRC" && git apply --whitespace=nowarn "$PATCH"
echo "[3/4] Building patched..."
cd "$SRC/src" && make -s clean && make -s -j 96
cp classify "$BUILD/classify.opt1"
cd "$SRC" && git reset --hard HEAD >/dev/null   # leave tree clean

# --- BENCHMARK helper -------------------------------------------------------
PERF_EVENTS=cycles,instructions,LLC-loads,LLC-load-misses,dTLB-load-misses,dTLB-loads
bench () {
  local bin=$1 tag=$2
  local txt=$OUT/perf_${tag}.txt
  echo "[bench $tag] $bin"
  # 3 warm runs to remove page-cache noise, then 3 timed runs.
  for _ in 1 2 3; do
    "$bin" -H "$DB/hash.k2d" -t "$DB/taxo.k2d" -o "$DB/opts.k2d" \
           -p 32 -R /dev/null -O /dev/null "$INPUT" >/dev/null 2>&1
  done
  : > "$txt"
  for i in 1 2 3; do
    /usr/bin/time -f "wall_${i}=%e" \
      numactl --cpunodebind=0 --membind=0 \
      perf stat -x, -e $PERF_EVENTS \
      "$bin" -H "$DB/hash.k2d" -t "$DB/taxo.k2d" -o "$DB/opts.k2d" \
             -p 32 -R /dev/null -O /dev/null "$INPUT" \
        >/dev/null 2>>"$txt"
  done
}

echo "[4/4] Benchmarking..."
bench "$BUILD/classify.base" base
bench "$BUILD/classify.opt1" opt1

# --- SUMMARY ----------------------------------------------------------------
extract () {
  local txt=$1 evt=$2
  grep ",$evt," "$txt" | awk -F, '{s+=$1; n++} END {if(n) printf "%.0f", s/n}'
}
wall () {
  local txt=$1
  grep '^wall_' "$txt" 2>/dev/null | awk -F= '{s+=$2;n++} END {if(n) printf "%.3f", s/n}'
}
# /usr/bin/time output appears on stderr lines starting with wall_; perf -x,
# emits CSV rows. The above commands send /usr/bin/time output to the same
# file via 2>>, so wall_ lines are present.

W_BASE=$(wall "$OUT/perf_base.txt"); W_OPT=$(wall "$OUT/perf_opt1.txt")
LLM_BASE=$(extract "$OUT/perf_base.txt" LLC-load-misses)
LLM_OPT=$(extract  "$OUT/perf_opt1.txt" LLC-load-misses)
DTLB_BASE=$(extract "$OUT/perf_base.txt" dTLB-load-misses)
DTLB_OPT=$(extract  "$OUT/perf_opt1.txt" dTLB-load-misses)
IPC_BASE=$(awk -F, '/cycles,/{c+=$1} /instructions,/{i+=$1} END{ if(c) printf "%.2f", i/c}' "$OUT/perf_base.txt")
IPC_OPT=$( awk -F, '/cycles,/{c+=$1} /instructions,/{i+=$1} END{ if(c) printf "%.2f", i/c}' "$OUT/perf_opt1.txt")

python3 - <<PY
b=float("${W_BASE:-0}"); o=float("${W_OPT:-0}")
print()
print("==================== SUMMARY (paste this back) ====================")
print(f"input:    $INPUT")
print(f"db:       $DB")
print(f"threads:  32, numactl --cpunodebind=0 --membind=0")
print()
print(f"wall  base = {b:.3f} s   opt = {o:.3f} s   delta = {((b-o)/b*100) if b else 0:+.2f}%")
print(f"vs prior best 4.405 s: delta = {((4.405-o)/4.405*100) if o else 0:+.2f}%")
print()
print(f"LLC-load-misses  base = ${LLM_BASE:-?}   opt = ${LLM_OPT:-?}")
print(f"dTLB-load-misses base = ${DTLB_BASE:-?}   opt = ${DTLB_OPT:-?}")
print(f"IPC              base = ${IPC_BASE:-?}    opt = ${IPC_OPT:-?}")
print("===================================================================")
PY

# Restore original tree state if we stashed anything.
git -C "$SRC" stash pop >/dev/null 2>&1 || true
