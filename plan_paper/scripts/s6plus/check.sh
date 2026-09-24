#!/bin/bash
# usage: check.sh "BINS" "DBS" READSFILE   -> compares full kraken output + report vs S0, byte for byte (sorted by read id for safety)
declare -A DB=([50MB]=~/AccuracyDrift/databases/sample_targeted [8GB]=~/AccuracyDrift/databases/standard_8gb [16GB]=~/AccuracyDrift/databases/standard_16gb [103GB]=~/AccuracyDrift/databases/pluspf_103gb)
O=~/chirag_K/results/s6plus/chk; mkdir -p $O
RF=${3:-$HOME/chirag_K/results/basecalling/reads_hac.fastq}
for d in $2; do
  ~/tools/kraken2-fresh-bin-s0/kraken2 --db ${DB[$d]} --threads 32 --output $O/ref_$d.out --report $O/ref_$d.rep $RF >/dev/null 2>&1
  for b in $1; do
    bin=${b%%@*}; kb=""; [ "$b" != "$bin" ] && kb=${b##*@}
    K2_B=$kb ~/tools/$bin/kraken2 --db ${DB[$d]} --threads 32 --output $O/t.out --report $O/t.rep $RF >/dev/null 2>&1
    if cmp -s <(sort $O/ref_$d.out) <(sort $O/t.out) && cmp -s <(sort $O/ref_$d.rep) <(sort $O/t.rep); then echo "CHECK OK   $d $b"; else echo "CHECK FAIL $d $b"; fi
  done
done
