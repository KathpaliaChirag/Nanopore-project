#!/bin/bash
cd ~/e1/sn
# stop the launchers for 64, 32 and 12 cores (each was started with setsid, so its pid is its group id)
for c in 64 32 12; do
  for p in $(ps -u student -o pid,cmd | grep "hw_launch2.sh hw_variants_scale.txt $c 8gb" | grep -v grep | awk '{print $1}'); do kill -TERM -- -$p 2>/dev/null; done
done
# stop the Sniper job groups for those core counts (timeout starts its own group)
for c in 64 32 12; do
  for p in $(ps -u student -o pid,cmd | grep "timeout 43200 ./run-sniper" | grep "total_cores=$c " | grep -v grep | awk '{print $1}'); do kill -TERM -- -$p 2>/dev/null; done
done
sleep 5
for c in 64 32 12; do
  for p in $(ps -u student -o pid,cmd | grep "timeout 43200 ./run-sniper" | grep "total_cores=$c " | grep -v grep | awk '{print $1}'); do kill -KILL -- -$p 2>/dev/null; done
done
# clear any partial output and rows of the stopped core counts
rm -rf /dev/shm/hw_out/hw_64c_* /dev/shm/hw_out/hw_32c_* /dev/shm/hw_out/hw_12c_*
export K2B=1
for c in 16 8; do nohup setsid ./hw_launch2.sh hw_variants_scale.txt $c 16gb 4 50 > scale16_$c.out 2>&1 < /dev/null & done
sleep 15
echo "running by core count:"; ps -u student -o cmd | grep "hw_job.sh" | grep -v "grep\|xargs\|bash -c" | awk '{print $4" cores, "$6" db"}' | sort | uniq -c
free -g | sed -n 2p
