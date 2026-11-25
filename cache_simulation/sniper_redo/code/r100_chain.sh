#!/bin/bash
# waits for the eight 10/25-read runs, then runs the 100-read file: base + pf_both at 1, 4, 8, 16 cores, 8 GB
cd ~/e1/sn
until [ "$(ls hwdone | grep -cE '^hw_(8|16)c_(base|pf_both)_r(10|25)_8gb$')" -ge 8 ]; do sleep 60; done
echo "start r100 $(date)" >> r100_chain.log
./hw_launch2.sh hw_variants_pb.txt 1 8gb 2 100 > r100_1.out 2>&1 &
./hw_launch2.sh hw_variants_pb.txt 4 8gb 2 100 > r100_4.out 2>&1 &
K2B=1 ./hw_launch2.sh hw_variants_pb.txt 8 8gb 2 100 > r100_8.out 2>&1 &
K2B=1 ./hw_launch2.sh hw_variants_pb.txt 16 8gb 2 100 > r100_16.out 2>&1 &
wait
echo "R100DONE $(date)" >> r100_chain.log
