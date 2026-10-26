#!/bin/bash
# usage: threads_sweep.sh LOGNAME "THREADS" "BINS" [DB]   (default DB = 103GB)
# one run per (threads, bin), interleaved so drift hits both bins equally.
# stderr is timestamped so load time and classify time can be split afterwards.
LOGF=~/chirag_K/results/s6plus/$1.log; THL=$2; BINL=$3; DBN=${4:-103GB}
declare -A DB=([50MB]=~/AccuracyDrift/databases/sample_targeted [8GB]=~/AccuracyDrift/databases/standard_8gb [16GB]=~/AccuracyDrift/databases/standard_16gb [103GB]=~/AccuracyDrift/databases/pluspf_103gb)
READS=$(ls ~/chirag_K/results/per_pod5_fastq/pod5_*.fastq | sort)
: > $LOGF
for t in $THL; do for b in $BINL; do
  ERR=~/chirag_K/results/s6plus/$1.$b.t$t.err
  S=$(date +%s.%N)
  /usr/bin/time -f %e -o /tmp/sweep_t.$$ ~/tools/$b/kraken2 --db ${DB[$DBN]} --threads $t --output /dev/null $READS 2> >(while IFS= read -r l; do echo "$(date +%s.%N) $l"; done > $ERR) >/dev/null
  wait
  echo "threads=$t $DBN $b start=$S wall=$(tail -1 /tmp/sweep_t.$$)" >> $LOGF
done; done
echo DONE >> $LOGF
