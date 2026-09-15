#!/bin/bash
# Software cache SIZE sweep, redirected to pluspf_103gb only.
#
# Why this exists as a separate script instead of editing run_size_sweep.sh in
# place: a peer session (also working this repo for CK) reported CK's explicit
# instruction to stop queuing more 50MB (sample_targeted) size-sweep runs - that
# DB was already established (hw_assoc_sweep, fig12/fig13, every prior
# associativity/read-count sweep) to structurally never benefit from any
# software cache, regardless of organization, so further size points there add
# confirmation but not new signal. The peer's own script
# (run_cache_size_sweep.sh, results_cache_size_sweep/) was already redirected
# to cover standard_8gb + standard_16gb concurrently - to avoid duplicating
# that work, this script covers the one remaining DB regime neither sweep had
# reached: pluspf_103gb (104GB), completing the brief's suggested "6 sizes x
# 2-4 DBs" cross per the methodology section.
#
# run_size_sweep.sh's original 50mb queue was stopped after size=65536 (3
# points: 2048/4096/16384 complete, 65536 in flight at redirect time) - those
# 4 real 50MB rows stand as-is in results_size_sweep/live_summary.csv,
# reconfirming (not superseding) the existing 50MB null finding. 262144 and
# 1048576 on 50mb were deliberately dropped, per the new instruction.
cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_size_sweep_103gb
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'size,db,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

WORKLOAD=/home/student/cache_simulation/workloads/tiny_10reads.fastq

declare -A BINS
BINS[2048]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-2048/classify
BINS[4096]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-4096/classify
BINS[16384]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-16384/classify
BINS[65536]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-65536/classify
BINS[262144]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-262144/classify
BINS[1048576]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-1048576/classify

DB=/home/student/chirag_K/AccuracyDrift/databases/pluspf_103gb
dbname=103gb

for size in 2048 4096 16384 65536 262144 1048576; do
  BIN=${BINS[$size]}
  OUTDIR=$OUTBASE/size${size}_${dbname}
  LOG=$OUTBASE/size${size}_${dbname}.log
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running size_sweep_103gb size=${size} db=${dbname} ===" >> $OUTBASE/progress.log
  WSTART=$(date +%s)
  ./run-sniper -c address_translation_schemes/baseline -c luna -n 1 -d $OUTDIR -- \
    $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
    -p 1 -T 0 -O $OUTBASE/size${size}_${dbname}_out.txt -Q 0 -R $OUTBASE/size${size}_${dbname}_report.txt -g 2 \
    $WORKLOAD > $LOG 2>&1
  WEND=$(date +%s)
  WALLCLOCK=$((WEND - WSTART))

  INSTR=$(grep -oP 'Simulated \K[0-9.]+(?=M instructions)' $LOG)
  CYCLES=$(grep -oP 'Simulated [0-9.]+M instructions, \K[0-9.]+(?=M cycles)' $LOG)
  IPC=$(grep -oP '[0-9.]+M cycles, \K[0-9.]+(?= IPC)' $LOG)
  LINES=$(grep -oP 'accessed \K[0-9]+(?= unique data cache lines)' $LOG)
  ELAPSED=$(grep -oP 'Elapsed time: \K[0-9.]+' $LOG)

  STATS=$OUTDIR/simulation/sim.stats
  if [ -f $STATS ]; then
    L1D_LOADS=$(grep '^L1-D.loads-data ' $STATS | awk '{print $3}')
    L1D_HITS=$(grep '^L1-D.loads-where-data-L1 ' $STATS | awk '{print $3}')
    L2_HITS=$(grep '^L1-D.loads-where-data-L2 ' $STATS | awk '{print $3}')
    NUCA_HITS=$(grep '^L1-D.loads-where-data-nuca-cache ' $STATS | awk '{print $3}')
    if [ -n "$L1D_LOADS" ] && [ "$L1D_LOADS" != "0" ]; then
      L1D_PCT=$(echo "scale=2; $L1D_HITS * 100 / $L1D_LOADS" | bc)
      L2_PCT=$(echo "scale=2; $L2_HITS * 100 / $L1D_LOADS" | bc)
      NUCA_PCT=$(echo "scale=4; $NUCA_HITS * 100 / $L1D_LOADS" | bc)
    else
      L1D_PCT=NA; L2_PCT=NA; NUCA_PCT=NA
    fi
  else
    L1D_LOADS=NA; L1D_PCT=NA; L2_PCT=NA; NUCA_PCT=NA
  fi

  echo "$size,$dbname,$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$NUCA_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done size_sweep_103gb size=${size} db=${dbname} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
