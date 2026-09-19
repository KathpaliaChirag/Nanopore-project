#!/bin/bash
# cleanstart baseline queue: S0 (no software cache), laptop hardware UNCHANGED (all knobs at default).
# 3 core counts (1, 4, 8) x 3 read counts (10/50/100) x 3 databases (50mb/8gb/16gb) = 27 runs,
# strictly one after another, smallest first. detailed mode. total L3 fixed at 16MB for every core count
# (per-slice size = 16MB / cores). each run is done by run_one.sh; re-launching skips finished runs.
# progress: ~/cleanstart/results/queue_progress.log   results: ~/cleanstart/results/summary_all.csv
R=$HOME/cleanstart/results
mkdir -p $R
PROG=$R/queue_progress.log
for cores in 1 4 8; do
  for reads in 10 50 100; do
    for dbname in 50mb 8gb 16gb; do
      echo "=== $(date '+%F %T') START ${cores}c r${reads} ${dbname} ===" >> $PROG
      bash $HOME/cleanstart/run_one.sh $cores $reads $dbname >> $PROG 2>&1
    done
  done
done
echo "ALL DONE $(date '+%F %T')" >> $PROG
