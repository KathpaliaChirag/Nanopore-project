#!/bin/bash
# usage: bench.sh LOGNAME REPS "DBS" "BINS" [extra kraken2 flags]   (env vars pass through, e.g. K2_B)
LOGF=~/chirag_K/results/s6plus/$1.log; REPS=$2; DBL=$3; BINL=$4; EXTRA=${5:-}
declare -A DB=([50MB]=~/AccuracyDrift/databases/sample_targeted [8GB]=~/AccuracyDrift/databases/standard_8gb [16GB]=~/AccuracyDrift/databases/standard_16gb [103GB]=~/AccuracyDrift/databases/pluspf_103gb)
READS=$(ls ~/chirag_K/results/per_pod5_fastq/pod5_*.fastq | sort)
: > $LOGF
for r in $(seq 1 $REPS); do for d in $DBL; do for b in $BINL; do
  bin=${b%%@*}; kb=""; [ "$b" != "$bin" ] && kb=${b##*@}
  K2_B=${kb:-${K2_B:-}} /usr/bin/time -f %e -o /tmp/bench_t.$$ ~/tools/$bin/kraken2 --db ${DB[$d]} --threads 32 $EXTRA --output /dev/null $READS >/dev/null 2>&1
  echo "$d $b rep$r $(tail -1 /tmp/bench_t.$$)" >> $LOGF
done; done; done
echo DONE >> $LOGF
