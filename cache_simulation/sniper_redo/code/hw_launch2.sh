#!/bin/bash
# hw_launch2.sh <variants-file> <cores> <db> <parallel> <reads...>
vf=$1; cores=$2; db=$3; par=$4; shift 4
cd ~/e1/sn; L=lists/hw2_${cores}c_${db}; : > $L
for r in "$@"; do while IFS='|' read -r vn ovr; do printf '%s\t%s\t%s\t%s\t%s\n' "$vn" $cores $r $db "$ovr" >> $L; done < $vf; done
tr '\n' '\0' < $L | xargs -0 -P $par -I{} bash -c 'IFS=$'"'"'\t'"'"' read -r a b c d e <<< "{}"; ./hw_job.sh "$a" "$b" "$c" "$d" "$e"'
echo "HW2DONE $cores $db" >> ~/e1/sn/hw.progress
