#!/bin/bash
# cleanstart baseline queue: S0 (no software cache), laptop.cfg hardware UNCHANGED.
# 2 core counts (1 and 8) x 3 read counts (10/50/100) x 3 databases (50mb/8gb/16gb) = 18 runs,
# strictly one after another, smallest first. detailed mode (no --fast-forward).
# core count N means: sniper -n N AND classify -p N (simulated cores = kraken2 threads).
# writes ~/cleanstart/results/baseline_summary.csv, one row per finished run.
# a run is skipped if its sim.stats already exists, so re-launching resumes the queue.
R=$HOME/cleanstart/results
SNIPER=$HOME/cache_simulation/snipersim
BIN=$HOME/chirag_K/tools/kraken2-src-baseline/src/classify
W=$HOME/cleanstart/workloads
DBROOT=$HOME/chirag_K/AccuracyDrift/databases
declare -A DB=( [50mb]=$DBROOT/sample_targeted [8gb]=$DBROOT/standard_8gb [16gb]=$DBROOT/standard_16gb )
SUMMARY=$R/baseline_summary.csv
PROG=$R/queue_progress.log
mkdir -p $R
[ -f $SUMMARY ] || echo 'cores,reads,db,instructions_M,cycles_M,ipc,unique_cache_lines,sim_time_max_fs,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

# wait for the already-running first run (base_r10_50mb) to finish, then adopt it as 1c_r10_50mb
while pgrep -f "run-sniper" > /dev/null; do sleep 10; done
if [ -d $R/base_r10_50mb ] && [ ! -d $R/1c_r10_50mb ]; then
  for f in $R/base_r10_50mb*; do mv "$f" "${f/base_r10_50mb/1c_r10_50mb}"; done
fi

# sum a per-core stat across all cores (sim.stats lines look like: name = v0, v1, ...)
stat_sum() { grep -m1 "^$1 " $STATS | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{s=0;for(i=1;i<=NF;i++)s+=$i;printf "%d",s}'; }
stat_max() { grep -m1 "^$1 " $STATS | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{m=0;for(i=1;i<=NF;i++)if($i+0>m)m=$i+0;printf "%d",m}'; }

parse_row() {  # args: cores reads dbname wallclock
  local c=$1 r=$2 d=$3 wall=$4 name=${1}c_r${2}_${3}
  local LOG=$R/$name.log; STATS=$R/$name/simulation/sim.stats
  local INSTR CYC IPC LINES ELAPSED
  INSTR=$(grep -oP 'Simulated \K[0-9.]+(?=M instructions)' $LOG)
  CYC=$(grep -oP 'Simulated [0-9.]+M instructions, \K[0-9.]+(?=M cycles)' $LOG)
  IPC=$(grep -oP '[0-9.]+M cycles, \K[0-9.]+(?= IPC)' $LOG)
  LINES=$(grep -oP 'accessed \K[0-9]+(?= unique data cache lines)' $LOG)
  ELAPSED=$(grep -oP 'Elapsed time: \K[0-9.]+' $LOG)
  local L1L=NA L1H=NA L2H=NA NH=NA TM=NA P1=NA P2=NA P3=NA
  if [ -f $STATS ]; then
    L1L=$(stat_sum L1-D.loads-data); L1H=$(stat_sum L1-D.loads-where-data-L1)
    L2H=$(stat_sum L1-D.loads-where-data-L2); NH=$(stat_sum L1-D.loads-where-data-nuca-cache)
    TM=$(stat_max performance_model.elapsed_time)
    if [ -n "$L1L" ] && [ "$L1L" != "0" ]; then
      P1=$(echo "scale=2; $L1H*100/$L1L" | bc); P2=$(echo "scale=2; $L2H*100/$L1L" | bc); P3=$(echo "scale=4; $NH*100/$L1L" | bc)
    fi
  fi
  echo "$c,$r,$d,$INSTR,$CYC,$IPC,$LINES,$TM,$L1L,$P1,$P2,$P3,$ELAPSED,$wall" >> $SUMMARY
}

cd $SNIPER
for cores in 1 8; do
  for reads in 10 50 100; do
    for dbname in 50mb 8gb 16gb; do
      name=${cores}c_r${reads}_${dbname}
      if [ -f $R/$name/simulation/sim.stats ]; then
        grep -q "^$cores,$reads,$dbname," $SUMMARY || parse_row $cores $reads $dbname NA
        echo "=== $(date '+%F %T') skip $name (already done) ===" >> $PROG
        continue
      fi
      echo "=== $(date '+%F %T') START $name ===" >> $PROG
      WS=$(date +%s)
      ./run-sniper -c address_translation_schemes/baseline -c laptop -n $cores -d $R/$name -- \
        $BIN -H ${DB[$dbname]}/hash.k2d -t ${DB[$dbname]}/taxo.k2d -o ${DB[$dbname]}/opts.k2d \
        -p $cores -T 0 -O $R/${name}_out.txt -Q 0 -R $R/${name}_report.txt -g 2 $W/reads_$reads.fastq \
        > $R/$name.log 2>&1 < /dev/null
      WALL=$(( $(date +%s) - WS ))
      parse_row $cores $reads $dbname $WALL
      echo "=== $(date '+%F %T') DONE $name wall=${WALL}s ===" >> $PROG
    done
  done
done
echo "ALL DONE $(date '+%F %T')" >> $PROG
