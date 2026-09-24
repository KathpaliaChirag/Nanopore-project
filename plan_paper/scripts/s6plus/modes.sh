#!/bin/bash
# usage: modes.sh "BINS" DBNAME   -> compares each bin vs S0 across kraken2 modes; prints PASS/FAIL per mode
declare -A DB=([50MB]=~/AccuracyDrift/databases/sample_targeted [8GB]=~/AccuracyDrift/databases/standard_8gb)
D=${DB[$2]}; O=~/chirag_K/results/s6plus/modes; mkdir -p $O
P=~/chirag_K/results/per_pod5_fastq
HAC=~/chirag_K/results/basecalling/reads_hac.fastq
awk "NR%4==1{print \">\" substr(\$0,2)} NR%4==2{print}" ~/chirag_K/results/readcount_bench/reads_1000.fastq > $O/reads_1000.fasta
# mode name | extra args | input files
modes=(
"default||$HAC"
"confidence0.2|--confidence 0.2|$HAC"
"minhits3|--minimum-hit-groups 3|$HAC"
"quick|--quick|$HAC"
"basequal10|--minimum-base-quality 10|$HAC"
"usenames|--use-names|$HAC"
"zerocounts|--report-zero-counts|$HAC"
"fasta||$O/reads_1000.fasta"
"paired|--paired|$P/pod5_0.fastq $P/pod5_0.fastq"
"multifile3||$P/pod5_0.fastq $P/pod5_1.fastq $P/pod5_2.fastq"
"threads1||~/chirag_K/results/readcount_bench/reads_1000.fastq"
"threads7||$HAC"
)
run() { # bin extra input threads outprefix
  ~/tools/$1/kraken2 --db $D --threads $4 $2 --output $5.out --report $5.rep --classified-out $5.cls#.fq --unclassified-out $5.unc#.fq $3 >/dev/null 2>&1
}
for m in "${modes[@]}"; do
  IFS="|" read name extra input <<< "$m"; th=32
  [ "$name" = threads1 ] && th=1; [ "$name" = threads7 ] && th=7
  input=$(eval echo $input)
  run kraken2-fresh-bin-s0 "$extra" "$input" $th $O/ref
  for b in $1; do
    run $b "$extra" "$input" $th $O/t
    ok=1
    for ext in out rep; do cmp -s <(sort $O/ref.$ext) <(sort $O/t.$ext) || ok=0; done
    for f in $O/ref.cls* $O/ref.unc*; do [ -e "$f" ] || continue; g=${f/ref/t}; cmp -s <(sort $f) <(sort $g) || ok=0; done
    [ -s $O/ref.out ] || ok=0
    echo "$([ $ok = 1 ] && echo PASS || echo FAIL) $2 $name $b"
  done
  rm -f $O/ref.* $O/t.*
done
