#!/bin/bash
# sn_job.sh <set: short|long> <cores> <variant> <reads> <db: 8gb|16gb>
# one Sniper run of one cache variant; appends one row to ~/e1/sn/results.csv
set=$1; cores=$2; variant=$3; reads=$4; dbn=$5
SN=$HOME/cache_simulation/snipersim; E=$HOME/e1/sn; DBR=$HOME/chirag_K/AccuracyDrift/databases
case $dbn in 8gb) DB=$DBR/standard_8gb;; 16gb) DB=$DBR/standard_16gb;; *) echo bad db; exit 1;; esac
case $set in short) IN=$E/wl/r$reads.fastq;; long) IN=$HOME/cache_simulation/workloads/long_$reads.fastq;; *) echo bad set; exit 1;; esac
BIN=$E/bin/classify_$variant
name=${set}_${cores}c_${variant}_r${reads}_${dbn}
SO=/dev/shm/sn_out; mkdir -p $SO $E/logs $E/done
[ -f $E/done/$name ] && exit 0
OUT=$SO/$name; LOG=$SO/$name.log; STATS=$OUT/simulation/sim.stats
BLK=""; [ $cores -gt 1 ] && BLK="K2_BLOCK=10000"
cd $SN; rm -rf $OUT
WS=$(date +%s)
env $BLK timeout 14400 ./run-sniper -c address_translation_schemes/baseline -c luna2 -c general/total_cores=$cores -n $cores -d $OUT -- $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d -p $cores -T 0 -O $SO/$name.txt -Q 0 -R $SO/$name.rep -g 2 $IN > $LOG 2>&1 < /dev/null
rc=$?
WALL=$(( $(date +%s) - WS ))
stat_sum() { grep -a -m1 "^$1 " $STATS 2>/dev/null | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{s=0;for(i=1;i<=NF;i++)s+=$i;printf "%.0f",s}'; }
stat_max() { grep -a -m1 "^$1 " $STATS 2>/dev/null | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{m=0;for(i=1;i<=NF;i++)if($i+0>m)m=$i+0;printf "%.0f",m}'; }
INSTR=$(grep -aoP 'Simulated \K[0-9.]+(?=M instructions)' $LOG | tail -1)
CYC=$(grep -aoP 'Simulated [0-9.]+M instructions, \K[0-9.]+(?=M cycles)' $LOG | tail -1)
IPC=$(grep -aoP '[0-9.]+M cycles, \K[0-9.]+(?= IPC)' $LOG | tail -1)
LINES=$(grep -aoP 'accessed \K[0-9]+(?= unique data cache lines)' $LOG | paste -sd+ | bc 2>/dev/null)
EL=$(grep -aoP 'Elapsed time: \K[0-9.]+' $LOG | tail -1)
TM=$(stat_max performance_model.elapsed_time)
L1L=$(stat_sum L1-D.loads-data); L1H=$(stat_sum L1-D.loads-where-data-L1); L2H=$(stat_sum L1-D.loads-where-data-L2); NH=$(stat_sum L1-D.loads-where-data-nuca-cache)
P1=NA; P2=NA; P3=NA
if [ -n "$L1L" ] && [ "$L1L" != "0" ]; then
  P1=$(echo "scale=3; $L1H*100/$L1L" | bc); P2=$(echo "scale=3; $L2H*100/$L1L" | bc); P3=$(echo "scale=4; $NH*100/$L1L" | bc); fi
HDR="set,cores,variant,reads,db,instr_M,cycles_M,ipc,sim_time_fs,unique_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,sniper_elapsed_s,rc,wall_s"
(flock 9; [ -s $E/results.csv ] || echo $HDR > $E/results.csv; echo "$set,$cores,$variant,$reads,$dbn,${INSTR:-NA},${CYC:-NA},${IPC:-NA},${TM:-NA},${LINES:-NA},${L1L:-NA},$P1,$P2,$P3,${EL:-NA},$rc,$WALL" >> $E/results.csv) 9>$E/results.lock
cp $LOG $E/logs/$name.log 2>/dev/null
cmp -s /dev/null /dev/null; [ $rc -eq 0 ] && touch $E/done/$name
rm -rf $OUT
