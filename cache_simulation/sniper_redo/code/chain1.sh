#!/bin/bash
cd ~/e1/sn
xargs -P 10 -L1 ./sn_job.sh < lists/p1
xargs -P 3 -L1 ./sn_job.sh < lists/p5
xargs -P 6 -L1 ./sn_job.sh < lists/p2
xargs -P 3 -L1 ./sn_job.sh < lists/p6
echo CHAIN1DONE >> ~/e1/sn/chain.progress
