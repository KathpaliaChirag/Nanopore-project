#!/bin/bash
cd ~/e1/sn
./hw_launch2.sh hw_variants_pf.txt 1 8gb 12 10 25 50 &
./hw_launch2.sh hw_variants_pf.txt 1 16gb 8 10 25 50 &
wait
./hw_launch2.sh hw_variants_pf.txt 4 8gb 4 10 25 50
echo CHAINDONE >> ~/e1/sn/hw.progress
