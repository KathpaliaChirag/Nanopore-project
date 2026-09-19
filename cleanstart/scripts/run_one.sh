#!/bin/bash
# run ONE cleanstart Sniper run (S0, detailed mode) and append one row to results/summary_all.csv.
# usage:  [KNOB=value ...] run_one.sh <cores> <reads> <dbname>
#   cores  = sniper -n AND classify -p AND general/total_cores (forced, see below)
#   reads  = 10 | 50 | 100        dbname = 50mb | 8gb | 16gb
# knobs (env vars, default = baseline = the laptop): L3_KB=16384 (TOTAL, split over cores) L2_KB=512
#   L1_KB=32 (L1d only) L1W=8 L2W=8 L3W=16.   L4 is not implemented yet (name says L4none).
# result dir is named after the config:  results/L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16_L4none/<cores>c_r<reads>_<db>
# why total_cores is forced with -c general/total_cores=N: with only -n N, a later config layer resets it to 1
# and the "multicore" run silently simulates 1 core (found by smoke test 2026-09-19).
cores=$1; reads=$2; dbname=$3
L3_KB=${L3_KB:-16384}; L2_KB=${L2_KB:-512}; L1_KB=${L1_KB:-32}
L1W=${L1W:-8}; L2W=${L2W:-8}; L3W=${L3W:-16}
R=$HOME/cleanstart/results
SNIPER=$HOME/cache_simulation/snipersim
BIN=$HOME/chirag_K/tools/kraken2-src-baseline/src/classify
W=$HOME/cleanstart/workloads
DBROOT=$HOME/chirag_K/AccuracyDrift/databases
case $dbname in 50mb) DB=$DBROOT/sample_targeted;; 8gb) DB=$DBROOT/standard_8gb;; 16gb) DB=$DBROOT/standard_16gb;; *) echo bad db; exit 1;; esac
fmt() { if [ $1 -ge 1024 ]; then echo "$(( $1 / 1024 ))MB"; else echo "${1}KB"; fi; }
CFG="L3-$(fmt $L3_KB)_L2-$(fmt $L2_KB)_L1-$(fmt $L1_KB)_L1w${L1W}_L2w${L2W}_L3w${L3W}_L4none"
if [ $(( L3_KB % cores )) -ne 0 ]; then echo "L3_KB $L3_KB not divisible by $cores cores"; exit 1; fi
SLICE=$(( L3_KB / cores ))
name=${cores}c_r${reads}_${dbname}
OUT=$R/$CFG/$name; mkdir -p $R/$CFG
LOG=$R/$CFG/$name.log; STATS=$OUT/simulation/sim.stats
SUMMARY=$R/summary_all.csv
[ -f $SUMMARY ] || echo 'config,cores,reads,db,instructions_M,cycles_M,ipc,unique_cache_lines,sim_time_max_fs,l1d_loads,l1d_hit_pct,l2_hit_pct,l3_hit_pct,elapsed_s,wallclock_s' > $SUMMARY
[ -f $STATS ] && { echo "skip $CFG/$name (done)"; exit 0; }
rm -rf $OUT

cd $SNIPER
WS=$(date +%s)
./run-sniper -c address_translation_schemes/baseline -c laptop -c cleanstart_laptop \
  -c general/total_cores=$cores -n $cores \
  -c perf_model/l1_dcache/cache_size=$L1_KB -c perf_model/l1_dcache/associativity=$L1W \
  -c perf_model/l2_cache/cache_size=$L2_KB -c perf_model/l2_cache/associativity=$L2W \
  -c perf_model/nuca/cache_size=$SLICE -c perf_model/nuca/associativity=$L3W \
  -d $OUT -- $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
  -p $cores -T 0 -O $R/$CFG/${name}_out.txt -Q 0 -R $R/$CFG/${name}_report.txt -g 2 $W/reads_$reads.fastq \
  > $LOG 2>&1 < /dev/null
WALL=$(( $(date +%s) - WS ))

# sim.stats lines look like "name = v0, v1, ..." (one value per core): sum across cores / max across cores
stat_sum() { grep -m1 "^$1 " $STATS | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{s=0;for(i=1;i<=NF;i++)s+=$i;printf "%d",s}'; }
stat_max() { grep -m1 "^$1 " $STATS | sed 's/^[^=]*= *//' | tr ',' ' ' | awk '{m=0;for(i=1;i<=NF;i++)if($i+0>m)m=$i+0;printf "%d",m}'; }
INSTR=$(grep -oP 'Simulated \K[0-9.]+(?=M instructions)' $LOG)
CYC=$(grep -oP 'Simulated [0-9.]+M instructions, \K[0-9.]+(?=M cycles)' $LOG)
IPC=$(grep -oP '[0-9.]+M cycles, \K[0-9.]+(?= IPC)' $LOG)
LINES=$(grep -oP 'accessed \K[0-9]+(?= unique data cache lines)' $LOG | paste -sd+ | bc)
ELAPSED=$(grep -oP 'Elapsed time: \K[0-9.]+' $LOG)
L1L=NA; P1=NA; P2=NA; P3=NA; TM=NA
if [ -f $STATS ]; then
  L1L=$(stat_sum L1-D.loads-data); L1H=$(stat_sum L1-D.loads-where-data-L1)
  L2H=$(stat_sum L1-D.loads-where-data-L2); NH=$(stat_sum L1-D.loads-where-data-nuca-cache)
  TM=$(stat_max performance_model.elapsed_time)
  if [ -n "$L1L" ] && [ "$L1L" != "0" ]; then
    P1=$(echo "scale=2; $L1H*100/$L1L" | bc); P2=$(echo "scale=2; $L2H*100/$L1L" | bc); P3=$(echo "scale=4; $NH*100/$L1L" | bc)
  fi
fi
echo "$CFG,$cores,$reads,$dbname,$INSTR,$CYC,$IPC,$LINES,$TM,$L1L,$P1,$P2,$P3,$ELAPSED,$WALL" >> $SUMMARY
echo "DONE $CFG/$name wall=${WALL}s"
