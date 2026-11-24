#!/bin/bash
cd ~/e1/sn
xargs -P 9 -L1 ./sn_job.sh < lists/p3
xargs -P 5 -L1 ./sn_job.sh < lists/p4
echo CHAIN2DONE >> ~/e1/sn/chain.progress
