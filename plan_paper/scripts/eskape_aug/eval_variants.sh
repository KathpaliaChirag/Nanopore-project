#!/bin/bash
# eval_variants.sh - run each student variant on held-out pod5 files, compare to the 103GB teacher.
# a variant dir = copy of sample_targeted with hash.k2d swapped (taxo.k2d/opts.k2d unchanged:
# taxonomy ids are the student's own, so no remap is needed).
#
# usage: eval_variants.sh "v1 v2 v3" "0 15"
cd ~/chirag_K/results/eskape_aug || exit 1
A=~/AccuracyDrift/databases
K=~/tools/kraken2-fresh-bin-s19/kraken2
for v in $1; do
  d=db_$v; mkdir -p $d
  cp -f $A/sample_targeted/taxo.k2d $A/sample_targeted/opts.k2d $d/
  ln -sf $PWD/hash_$v.k2d $d/hash.k2d
  for p in $2; do
    F=~/chirag_K/results/per_pod5_fastq/pod5_$p.fastq
    $K --db $d --threads 16 --output t_p${p}_$v.out --report t_p${p}_$v.rep $F > /dev/null 2>&1
  done
done
for p in $2; do
  echo "################ held-out pod5_$p ################"
  for v in 50mb $1; do
    echo "=== student: $v  vs teacher 103GB ==="
    python3 gap_analysis.py t_p${p}_$v.out t_p${p}_$v.rep t_p${p}_103gb.out t_p${p}_103gb.rep | \
      sed -n '1,16p;/MISSED/,/^$/p;/WRONG/,+1p' | grep -v "^$"
  done
done
