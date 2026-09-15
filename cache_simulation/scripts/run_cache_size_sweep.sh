#!/bin/bash
# Cache-SIZE sweep - the axis nobody has tested yet (see
# cache_simulation/RESEARCH_PROMPT_optimal_cache_size.md). Holds associativity
# FIXED at 4-way (established optimal in every prior sweep) and instead varies
# the SOFTWARE S2 cache's total capacity: 2048/4096/16384/65536/262144/1048576
# entries - anchored on kraken2's own default sizing formula's clamp bounds
# (4096-262144), plus one point below and above to see if the clamp itself is
# limiting anything. Binaries were pre-built by a parallel session executing
# the research brief's Step 0 (source located, compile-time size pins built).
#
# Crossed with DB size: BIG DBs ONLY (8GB standard_8gb, 16GB standard_16gb) -
# CK explicitly scoped this to big DBs 2026-09-15, since the 50MB DB has
# already been established (hardware-associativity-only sweep, fig12/fig13,
# plus every prior associativity/read-count sweep) to structurally never
# benefit from a software cache regardless of size - almost nothing on it
# ever reaches L2/LLC in the first place, so no size there would plausibly
# change the outcome. Fixed at 50 reads to keep this sweep fast and
# comparable to the original fair batch's own 50-read baseline.
#
# Launched to run IN PARALLEL with run_laptop_sweep.sh (not queued behind it) -
# Luna is a 96-cores-per-socket server, contention isn't a real concern, and
# cycles data (the metric this project actually trusts) isn't affected by host
# contention regardless - only wallclock/turnaround time would be.
cd ~/cache_simulation/snipersim
OUTBASE=/home/student/cache_simulation/results_cache_size_sweep
mkdir -p $OUTBASE
SUMMARY=$OUTBASE/live_summary.csv
echo 'db,size,instructions_M,cycles_M,ipc,unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s' > $SUMMARY

FASTQ=/home/student/cache_simulation/workloads/50reads.fastq

declare -A DBS
DBS[8gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_8gb
DBS[16gb]=/home/student/chirag_K/AccuracyDrift/databases/standard_16gb

SIZES="2048 4096 16384 65536 262144 1048576"

for dbname in 8gb 16gb; do
  DB=${DBS[$dbname]}
  for size in $SIZES; do
    BIN=/home/student/chirag_K/tools/kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-${size}/classify
    OUTDIR=$OUTBASE/${dbname}_size${size}
    LOG=$OUTBASE/${dbname}_size${size}.log
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Running cache_size_sweep db=${dbname} size=${size} ===" >> $OUTBASE/progress.log
    WSTART=$(date +%s)
    ./run-sniper -c address_translation_schemes/baseline -c luna -n 1 -d $OUTDIR --       $BIN -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d       -p 1 -T 0 -O $OUTBASE/${dbname}_size${size}_out.txt -Q 0 -R $OUTBASE/${dbname}_size${size}_report.txt -g 2       $FASTQ > $LOG 2>&1
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

    echo "$dbname,$size,$INSTR,$CYCLES,$IPC,$LINES,$L1D_LOADS,$L1D_PCT,$L2_PCT,$NUCA_PCT,$ELAPSED,$WALLCLOCK" >> $SUMMARY
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') Done cache_size_sweep db=${dbname} size=${size} wallclock=${WALLCLOCK}s ===" >> $OUTBASE/progress.log
  done
done
echo "ALL DONE $(date '+%Y-%m-%d %H:%M:%S')" >> $OUTBASE/progress.log
