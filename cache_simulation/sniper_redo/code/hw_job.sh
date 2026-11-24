#!/bin/bash
# hw_job.sh <variant-name> <cores> <reads> <db 8gb|16gb> "<sniper -c overrides>"
# one Sniper run of the cache-off kraken2 binary on a modified HARDWARE cache; appends a row to ~/e1/sn/hw_results.csv
vn=$1; cores=$2; reads=$3; dbn=$4; ovr=$5
SN=$HOME/cache_simulation/snipersim; E=$HOME/e1/sn; DBR=$HOME/chirag_K/AccuracyDrift/databases
case $dbn in 8gb) DB=$DBR/standard_8gb;; 16gb) DB=$DBR/standard_16gb;; *) exit 1;; esac
IN=$E/wl/r$reads.fastq; BIN=$E/bin/classify_off
name=hw_${cores}c_${vn}_r${reads}_${dbn}
SO=/dev/shm/hw_out; mkdir -p $SO $E/hwlogs $E/hwdone
[ -f $E/hwdone/$name ] && exit 0
OUT=$SO/$name; LOG=$SO/$name.log; STATS=$OUT/simulation/sim.stats
BLK=""; [ $cores -gt 1 ] && BLK="K2_BLOCK=${K2B:-10000}"
cd $SN; rm -rf $OUT; WS=$(date +%s)
env $BLK timeout 43200 ./run-sniper -c address_translation_schemes/baseline -c luna2 -c general/total_cores=$cores $ovr -n $cores -d $OUT -- $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d -p $cores -T 0 -O $SO/$name.txt -Q 0 -R $SO/$name.rep -g 2 $IN > $LOG 2>&1 < /dev/null
rc=$?; WALL=$(( $(date +%s) - WS ))
ss() { grep -a -m1 "^$1 " $STATS 2>/dev/null | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{s=0;for(i=1;i<=NF;i++)s+=$i;printf "%.0f",s}'; }
sm() { grep -a -m1 "^$1 " $STATS 2>/dev/null | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{m=0;for(i=1;i<=NF;i++)if($i+0>m)m=$i+0;printf "%.0f",m}'; }
INSTR=$(grep -aoP 'Simulated \K[0-9.]+(?=M instructions)' $LOG | tail -1)
CYC=$(grep -aoP 'Simulated [0-9.]+M instructions, \K[0-9.]+(?=M cycles)' $LOG | tail -1)
IPC=$(grep -aoP '[0-9.]+M cycles, \K[0-9.]+(?= IPC)' $LOG | tail -1)
TM=$(sm performance_model.elapsed_time)
L1L=$(ss L1-D.loads-data); L1H=$(ss L1-D.loads-where-data-L1); L2H=$(ss L1-D.loads-where-data-L2); NH=$(ss L1-D.loads-where-data-nuca-cache)
P1=NA;P2=NA;P3=NA
if [ -n "$L1L" ] && [ "$L1L" != "0" ]; then P1=$(echo "scale=3;$L1H*100/$L1L"|bc); P2=$(echo "scale=3;$L2H*100/$L1L"|bc); P3=$(echo "scale=4;$NH*100/$L1L"|bc); fi
HDR="variant,cores,reads,db,instr_M,cycles_M,ipc,sim_time_fs,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,rc,wall_s"
(flock 9; [ -s $E/hw_results.csv ] || echo $HDR > $E/hw_results.csv; echo "$vn,$cores,$reads,$dbn,${INSTR:-NA},${CYC:-NA},${IPC:-NA},${TM:-NA},${L1L:-NA},$P1,$P2,$P3,$rc,$WALL" >> $E/hw_results.csv) 9>$E/hw.lock
cp $LOG $E/hwlogs/$name.log 2>/dev/null; [ $rc -eq 0 ] && touch $E/hwdone/$name; rm -rf $OUT
