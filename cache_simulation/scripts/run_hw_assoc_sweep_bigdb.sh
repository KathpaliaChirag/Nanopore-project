#!/bin/bash
# Extends run_hw_assoc_sweep.sh (which only covered the 50MB DB) to the BIG
# DBs: 8GB and 16GB (this session's territory in the DB-coverage split with
# the peer session - they own 103GB for the size-axis sweep, symmetric here).
# Same question as the original: does real HARDWARE LLC associativity alone
# (S0, no software cache) matter, now on databases large enough that the
# software-cache-size sweep already shows real effects (up to 3.59x speedup,
# laptop_sweep 2026-09-15)? The original 50MB sweep found a clean null -
# almost nothing ever reached the LLC layer there. On a big DB, more of the
# working set plausibly lives in/moves through the LLC, so this null might
# NOT hold - genuinely unknown until run.
#
# Fixed at 50 reads (not the full 10/50/100/500 ladder the 50MB version used)
# to keep this affordable - big-DB runs are already ~3-4x the 50MB DB's
# per-base cost (see command_log.md's laptop_sweep time-estimate section), so
# covering 6 associativities x 2 DBs x 4 read-counts would be a multi-day
# job; 50 reads alone answers "does associativity matter on a big DB at all"
# without that cost, and the read-count axis is already being covered
# separately (by run_laptop_sweep.sh) for the SOFTWARE-cache side of things.

cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_hw_assoc_sweep_bigdb
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'db,associativity,sets,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

BIN=/home/student/chirag_K/tools/kraken2-src-baseline/src/classify
FASTQ=/home/student/cache_simulation/workloads/50reads.fastq

declare -A DBS
DBS[8gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_8gb
DBS[16gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_16gb

declare -A SETS
SETS[1]=18000
SETS[4]=4500
SETS[8]=2250
SETS[15]=1200
SETS[16]=1125
SETS[30]=600

for dbname in 8gb 16gb; do
  DB=${DBS[$dbname]}
  for assoc in 1 4 8 15 16 30; do
    sets=${SETS[$assoc]}
    OUTDIR=$OUTBASE/${dbname}_assoc${assoc}
    LOG=$OUTBASE/${dbname}_assoc${assoc}.log
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running hw_assoc_sweep_bigdb db=${dbname} associativity=${assoc} ===" >> $OUTBASE/progress.log
    WSTART=$(date +%s)
    ./run-sniper -c address_translation_schemes/baseline -c luna -c hw_assoc/luna_assoc${assoc} -n 1 -d $OUTDIR --       $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d       -p 1 -T 0 -O $OUTBASE/${dbname}_assoc${assoc}_out.txt -Q 0 -R $OUTBASE/${dbname}_assoc${assoc}_report.txt -g 2       $FASTQ > $LOG 2>&1
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

    echo "$dbname,$assoc,$sets,$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$NUCA_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done hw_assoc_sweep_bigdb db=${dbname} associativity=${assoc} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
  done
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
