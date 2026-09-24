#!/bin/bash
# usage: matrix.sh LOGNAME "BINS"   (first bin is the reference, compared against by the rest)
LOGF=~/chirag_K/results/s6plus/$1.log; BINS=$2
O=~/chirag_K/results/s6plus/mx; mkdir -p $O; : > $LOGF
declare -A DB=([50MB]=~/AccuracyDrift/databases/sample_targeted [8GB]=~/AccuracyDrift/databases/standard_8gb [16GB]=~/AccuracyDrift/databases/standard_16gb [103GB]=~/AccuracyDrift/databases/pluspf_103gb)
declare -A RF=([10]=~/chirag_K/results/readcount_bench/reads_10.fastq [1000]=~/chirag_K/results/readcount_bench/reads_1000.fastq [104918]=~/chirag_K/results/basecalling/reads_hac.fastq [1872777]="$(ls ~/chirag_K/results/per_pod5_fastq/pod5_*.fastq | sort | tr "\n" " ")")
for d in 50MB 8GB 16GB 103GB; do for rc in 10 1000 104918 1872777; do
  ref=""
  for b in $BINS; do
    /usr/bin/time -f %e -o $O/t.$$ ~/tools/$b/kraken2 --db ${DB[$d]} --threads 32 --output $O/$b.out --report $O/$b.rep ${RF[$rc]} >/dev/null 2>&1
    t=$(tail -1 $O/t.$$)
    if [ -z "$ref" ]; then ref=$b; verdict="ref"; else
      if cmp -s <(sort $O/$ref.out) <(sort $O/$b.out) && cmp -s <(sort $O/$ref.rep) <(sort $O/$b.rep); then verdict="IDENTICAL"; else verdict="MISMATCH"; fi
    fi
    echo "$d reads=$rc $b time=$t $verdict" >> $LOGF
  done
done; done
echo DONE >> $LOGF
