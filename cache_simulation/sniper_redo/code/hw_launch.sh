#!/bin/bash
# hw_launch.sh <cores> <db> <parallel> <reads...>   builds the job list from hw_variants.txt and runs it
cores=$1; db=$2; par=$3; shift 3
cd ~/e1/sn; L=lists/hw_${cores}c_${db}; : > $L
for r in "$@"; do while IFS='|' read -r vn ovr; do printf '%s\t%s\t%s\t%s\t%s\n' "$vn" $cores $r $db "$ovr" >> $L; done < hw_variants.txt; done
tr '\n' '\0' < $L | xargs -0 -P $par -I{} bash -c 'IFS=$'"'"'\t'"'"' read -r a b c d e <<< "{}"; ./hw_job.sh "$a" "$b" "$c" "$d" "$e"'
echo "HWDONE $cores $db" >> ~/e1/sn/hw.progress
