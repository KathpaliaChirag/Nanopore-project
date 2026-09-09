#!/bin/bash
# Hardware LLC associativity sweep - base kraken2 (S0, no software cache) only.
# Waits for the 2000reads job to finish, then sweeps Luna's real NUCA associativity
# (1/4/8/15[real]/16/30-way) at fixed slice size (1125KB), across FOUR workload sizes
# (10/50/100/500 reads) to see whether the effect (if any) holds/changes with scale.
# Counterpart to every other sweep in this project, which varied the SOFTWARE S2 cache's
# width while holding hardware fixed - this holds software fixed (none) and varies hardware.
while pgrep -f 'run_2000reads_standalone.sh' > /dev/null; do
  sleep 60
done

cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_hw_assoc_sweep
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'reads,associativity,sets,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

BIN=/home/student/chirag_K/tools/kraken2-src-baseline/src/classify
DB=/home/student/chirag_K/AccuracyDrift/databases/sample_targeted

declare -A FASTQ
FASTQ[10]=/home/student/cache_simulation/workloads/tiny_10reads.fastq
FASTQ[50]=/home/student/cache_simulation/workloads/50reads.fastq
FASTQ[100]=/home/student/cache_simulation/workloads/reads_100.fastq
FASTQ[500]=/home/student/cache_simulation/workloads/reads_500.fastq

declare -A SETS
SETS[1]=18000
SETS[4]=4500
SETS[8]=2250
SETS[15]=1200
SETS[16]=1125
SETS[30]=600

for reads in 10 50 100 500; do
  WORKLOAD=${FASTQ[$reads]}
  for assoc in 1 4 8 15 16 30; do
    sets=${SETS[$assoc]}
    OUTDIR=$OUTBASE/r${reads}_assoc${assoc}
    LOG=$OUTBASE/r${reads}_assoc${assoc}.log
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running hw_assoc_sweep reads=${reads} associativity=${assoc} ===" >> $OUTBASE/progress.log
    WSTART=$(date +%s)
    ./run-sniper -c address_translation_schemes/baseline -c luna -c hw_assoc/luna_assoc${assoc} -n 1 -d $OUTDIR --       $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d       -p 1 -T 0 -O $OUTBASE/r${reads}_assoc${assoc}_out.txt -Q 0 -R $OUTBASE/r${reads}_assoc${assoc}_report.txt -g 2       $WORKLOAD > $LOG 2>&1
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

    echo "$reads,$assoc,$sets,$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$NUCA_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done hw_assoc_sweep reads=${reads} associativity=${assoc} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
  done
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
