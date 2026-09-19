#!/bin/bash
# Usage: ./run_longread_scaling.sh <S0|4way>
#
# Resolves a confound in laptop_sweep. That sweep's 10/50-read files are SHORT reads
# (786 / 1827 bp avg, 8K / 91K total bases) but its 100/500-read files come from
# reads_fast_2000.fastq (47 / 51 kbp avg, 4.7M / 25M total bases). The cache flipped from
# winning (10/50 reads) to losing (100+ reads), but read count, read length and total
# bases all changed together, so the sweep cannot say which one drives the flip.
#
# This holds read LENGTH roughly constant (34-37 kbp avg) by taking nested prefixes of the
# SAME source file (reads_fast_2000.fastq) at 10/25/50 reads = 0.35M / 0.9M / 1.9M bases.
# Together with laptop_sweep's existing 100/500-read rows from that same file (4.7M/25M
# bases), this gives a clean 5-point scaling curve on ONE read-length distribution.
#
# 8GB DB only (where the flip happens at 100 reads), laptop.cfg for direct comparability
# with laptop_sweep. S0 and 4way are launched as two parallel processes (one per variant).
VARIANT=$1
cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_longread_scaling_${VARIANT}
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'reads,db,variant,total_bases,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

case $VARIANT in
  S0)   BIN=/home/student/chirag_K/tools/kraken2-src-baseline/src/classify ;;
  4way) BIN=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way/classify ;;
  *) echo "unknown variant $VARIANT"; exit 1 ;;
esac
DB=/home/student/chirag_K/AccuracyDrift/databases/standard_8gb

declare -A FASTQ
FASTQ[10]=/home/student/cache_simulation/workloads/long_10.fastq
FASTQ[25]=/home/student/cache_simulation/workloads/long_25.fastq
FASTQ[50]=/home/student/cache_simulation/workloads/long_50.fastq
declare -A BASES
BASES[10]=346387
BASES[25]=900057
BASES[50]=1868769

for reads in 10 25 50; do
  OUTDIR=$OUTBASE/r${reads}
  LOG=$OUTBASE/r${reads}.log
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running longread_scaling reads=${reads} variant=${VARIANT} ===" >> $OUTBASE/progress.log
  WSTART=$(date +%s)
  ./run-sniper -c address_translation_schemes/baseline -c laptop -n 1 -d $OUTDIR -- \
    $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
    -p 1 -T 0 -O $OUTBASE/r${reads}_out.txt -Q 0 -R $OUTBASE/r${reads}_report.txt -g 2 \
    ${FASTQ[$reads]} > $LOG 2>&1
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

  echo "$reads,8gb,$VARIANT,${BASES[$reads]},$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$NUCA_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done longread_scaling reads=${reads} variant=${VARIANT} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
