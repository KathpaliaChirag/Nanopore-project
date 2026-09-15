#!/bin/bash
# To-do item 1 from command_log.md: naive flat L3 vs the per-core NUCA mesh
# model every Luna experiment in this project has used so far. S0 (no
# software cache) only, isolating the hardware topology question cleanly.
# luna_flatl3.cfg mirrors luna.cfg's real L1/L2/frequency and uses the SAME
# NUCA placeholder latency values (tags_access_time=15, data_access_time=20)
# so this comparison isolates topology (flat single-bank vs. NUCA mesh), not
# a latency-assumption difference. Sanity-tested (23.9M instr/14.3M cycles/
# 1.67 IPC at 10 reads/50MB, close to the true NUCA S0 baseline of 14.1M
# cycles at the same config) before launching this comparison.
cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_flatl3_comparison
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'db,topology,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,l3_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

BIN=/home/student/chirag_K/tools/kraken2-src-baseline/src/classify
FASTQ=/home/student/cache_simulation/workloads/50reads.fastq

declare -A DBS
DBS[50mb]=/home/student/chirag_K/AccuracyDrift/databases/sample_targeted
DBS[8gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_8gb

declare -A CFGS
CFGS[nuca]=luna
CFGS[flat]=luna_flatl3

for dbname in 50mb 8gb; do
  DB=${DBS[$dbname]}
  for topo in nuca flat; do
    CFG=${CFGS[$topo]}
    OUTDIR=$OUTBASE/${dbname}_${topo}
    LOG=$OUTBASE/${dbname}_${topo}.log
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running flatl3_comparison db=${dbname} topology=${topo} ===" >> $OUTBASE/progress.log
    WSTART=$(date +%s)
    ./run-sniper -c address_translation_schemes/baseline -c $CFG -n 1 -d $OUTDIR --       $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d       -p 1 -T 0 -O $OUTBASE/${dbname}_${topo}_out.txt -Q 0 -R $OUTBASE/${dbname}_${topo}_report.txt -g 2       $FASTQ > $LOG 2>&1
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
      L3_HITS=$(grep '^L1-D.loads-where-data-L3 ' $STATS | awk '{print $3}')
      NUCA_HITS=$(grep '^L1-D.loads-where-data-nuca-cache ' $STATS | awk '{print $3}')
      L3_OR_NUCA_HITS=${L3_HITS:-$NUCA_HITS}
      if [ -n "$L1D_LOADS" ] && [ "$L1D_LOADS" != "0" ]; then
        L1D_PCT=$(echo "scale=2; $L1D_HITS * 100 / $L1D_LOADS" | bc)
        L2_PCT=$(echo "scale=2; $L2_HITS * 100 / $L1D_LOADS" | bc)
        L3_PCT=$(echo "scale=4; ${L3_OR_NUCA_HITS:-0} * 100 / $L1D_LOADS" | bc)
      else
        L1D_PCT=NA; L2_PCT=NA; L3_PCT=NA
      fi
    else
      L1D_LOADS=NA; L1D_PCT=NA; L2_PCT=NA; L3_PCT=NA
    fi

    echo "$dbname,$topo,$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$L3_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done flatl3_comparison db=${dbname} topology=${topo} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
  done
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
