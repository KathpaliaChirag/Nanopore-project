#!/bin/bash
# Laptop-hardware sweep: CK's own Ryzen 7 5800H cache config (laptop.cfg),
# S0/1way/4way/8way software cache variants, across 10/50/100/500 reads,
# against BOTH the 8GB and 16GB kraken2 databases. 32 runs total.
# Ordered smallest/fastest first (10 reads before 500, per-DB before the
# other) so early results land quickly even though the whole sweep may take
# 1-2 weeks (500-read tier on 8/16GB DBs is the expensive part - see
# command_log.md for the time estimate this was queued with).
cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_laptop_sweep
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'reads,db,variant,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

declare -A FASTQ
FASTQ[10]=/home/student/cache_simulation/workloads/tiny_10reads.fastq
FASTQ[50]=/home/student/cache_simulation/workloads/50reads.fastq
FASTQ[100]=/home/student/cache_simulation/workloads/reads_100.fastq
FASTQ[500]=/home/student/cache_simulation/workloads/reads_500.fastq

declare -A BINS
BINS[S0]=/home/student/chirag_K/tools/kraken2-src-baseline/src/classify
BINS[1way]=/home/student/chirag_K/tools/kraken2-src-1way/src/classify
BINS[4way]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way/classify
BINS[8way]=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-8way/classify

declare -A DBS
DBS[8gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_8gb
DBS[16gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_16gb

for reads in 10 50 100 500; do
  WORKLOAD=${FASTQ[$reads]}
  for dbname in 8gb 16gb; do
    DB=${DBS[$dbname]}
    for variant in S0 1way 4way 8way; do
      BIN=${BINS[$variant]}
      OUTDIR=$OUTBASE/r${reads}_${dbname}_${variant}
      LOG=$OUTBASE/r${reads}_${dbname}_${variant}.log
      echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running laptop_sweep reads=${reads} db=${dbname} variant=${variant} ===" >> $OUTBASE/progress.log
      WSTART=$(date +%s)
      ./run-sniper -c address_translation_schemes/baseline -c laptop -n 1 -d $OUTDIR --         $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d         -p 1 -T 0 -O $OUTBASE/r${reads}_${dbname}_${variant}_out.txt -Q 0 -R $OUTBASE/r${reads}_${dbname}_${variant}_report.txt -g 2         $WORKLOAD > $LOG 2>&1
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

      echo "$reads,$dbname,$variant,$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$NUCA_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
      echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done laptop_sweep reads=${reads} db=${dbname} variant=${variant} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
    done
  done
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
