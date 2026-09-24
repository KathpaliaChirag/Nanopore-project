#!/bin/bash
# usage: cores.sh LOG "CORELIST" "DBS" "BINS" : pins to first N cores, threads=N, 1.87M reads
LOGF=~/chirag_K/results/s6plus/$1.log; : > $LOGF
declare -A DB=([50MB]=~/AccuracyDrift/databases/sample_targeted [8GB]=~/AccuracyDrift/databases/standard_8gb [16GB]=~/AccuracyDrift/databases/standard_16gb)
READS=$(ls ~/chirag_K/results/per_pod5_fastq/pod5_*.fastq | sort)
for n in $2; do for d in $3; do for b in $4; do
  /usr/bin/time -f %e -o /tmp/cores_t.$$ taskset -c 0-$((n-1)) ~/tools/$b/kraken2 --db ${DB[$d]} --threads $n --output /dev/null $READS >/dev/null 2>&1
  echo "cores=$n $d $b $(tail -1 /tmp/cores_t.$$)" >> $LOGF
done; done; done; echo DONE >> $LOGF
