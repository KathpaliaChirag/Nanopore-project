#!/bin/bash
# resident-database test with the stock classify -D daemon mode (bin_pre build), 103GB db, T=96
R=$(ls ~/chirag_K/results/per_pod5_fastq/pod5_*.fastq | sort | tr "\n" " ")
R10=~/chirag_K/results/readcount_bench/reads_10.fastq
DB=~/chirag_K/AccuracyDrift/databases/pluspf_103gb
C=${DM_C:-$HOME/e1/bin_pre/classify}
STOCK=~/chirag_K/tools/kraken2-fresh-bin-s19/kraken2
export K2_BULK=1 K2_B=64 K2_PRESCAN_MMAP=0; [ -n "$DM_OMP" ] && export OMP_NUM_THREADS=$DM_OMP
LOG=~/e1/dm_${DM_TAG:-x}.log; : > $LOG
cleanup() { [ -f /tmp/classify.pid ] && kill $(cat /tmp/classify.pid) 2>/dev/null; sleep 1; pkill -u $USER -f "classify -D" 2>/dev/null; rm -f /tmp/classify_stdin /tmp/classify_stdout /tmp/classify_*_stdin /tmp/classify_*_stdout /tmp/classify.pid /dev/shm/dm_*; }
trap cleanup EXIT
if [ -e /tmp/classify_stdin ]; then echo "stale daemon fifo exists, aborting" >> $LOG; exit 1; fi
BASE="-H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d -p 96"
now() { date +%s.%N; }
t0=$(now)
timeout 400 $C -D $BASE -R /dev/shm/dm_rep0 -O /dev/shm/dm_out0 $R10 &
for i in $(seq 1 100); do [ -p /tmp/classify_stdout ] && break; sleep 0.1; done
cat /tmp/classify_stdout > ~/e1/dm_daemon.out &
waitdone() { # wait until daemon.out has $1 DONE lines; echo elapsed seconds since $2
  for i in $(seq 1 6000); do n=$(grep -c "^DONE" ~/e1/dm_daemon.out 2>/dev/null); [ "${n:-0}" -ge "$1" ] && break; sleep 0.02; done
  echo "$(now) $2" | awk "{printf \"%.2f\", \$1-\$2}"; }
attach() { # start a reader for the newest child fifo output
  for i in $(seq 1 200); do pid=$(grep "^PID:" ~/e1/dm_daemon.out | tail -1 | awk "{print \$2}"); [ -p /tmp/classify_${pid}_stdout ] && break; sleep 0.05; done
  cat /tmp/classify_${pid}_stdout > ~/e1/dm_job_$1.out 2>&1 & }
attach 1
e1=$(waitdone 1 $t0)
echo "job1 (initial, 10 reads, includes the 104GB index load): $e1 s" >> $LOG
for j in 2 3 4; do
  t=$(now)
  echo "$BASE -R /dev/shm/dm_rep$j -O /dev/shm/dm_out$j $R" > /tmp/classify_stdin
  sleep 0.05; attach $j
  e=$(waitdone $j $t)
  echo "job$j (full 1.87M reads on the resident table): $e s" >> $LOG
done
$STOCK --db $DB --threads 32 --output /dev/shm/dm_ref.out --report /dev/shm/dm_ref.rep $R >/dev/null 2>&1
cmp -s /dev/shm/dm_ref.out /dev/shm/dm_out4 && echo "daemon job output vs stock: OUT_OK" >> $LOG || echo "daemon job output vs stock: OUT_DIFF" >> $LOG
cmp -s /dev/shm/dm_ref.rep /dev/shm/dm_rep4 && echo "daemon job report vs stock: REP_BYTE_IDENTICAL" >> $LOG || echo "daemon job report vs stock: REP_DIFF" >> $LOG
echo "STOP" > /tmp/classify_stdin; sleep 2
echo DMDONE >> $LOG
