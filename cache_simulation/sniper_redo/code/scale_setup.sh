#!/bin/bash
cd ~/e1/sn
# 1) identity check: one read per block, 8 and 64 threads, must equal the stock classifier output
DB=~/chirag_K/AccuracyDrift/databases/standard_8gb; IN=~/e1/sn/wl/r50.fastq; mkdir -p /dev/shm/idchk
BASE=~/chirag_K/tools/kraken2-src-baseline/src/classify
$BASE -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d -p 1 -T 0 -O /dev/shm/idchk/base.out -Q 0 -R /dev/shm/idchk/base.rep -g 2 $IN > /dev/null 2>&1
for p in 8 64; do
  K2_BLOCK=1 ./bin/classify_off -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d -p $p -T 0 -O /dev/shm/idchk/p$p.out -Q 0 -R /dev/shm/idchk/p$p.rep -g 2 $IN > /dev/shm/idchk/p$p.log 2>&1
  cmp -s /dev/shm/idchk/base.out /dev/shm/idchk/p$p.out && echo "p$p K2_BLOCK=1 output: IDENTICAL" || echo "p$p K2_BLOCK=1 output: DIFFERENT"
done
rm -rf /dev/shm/idchk
# 2) make the runner take the block size from K2B and allow 12 h
sed -i 's|BLK="K2_BLOCK=10000"|BLK="K2_BLOCK=${K2B:-10000}"|; s|timeout 14400|timeout 43200|' hw_job.sh
grep -n 'K2B\|timeout 43200' hw_job.sh | cut -c1-120
# 3) variants + launch (largest core counts first)
cat > hw_variants_scale.txt <<'EOV'
base|
pf_both|-c perf_model/l1_dcache/prefetcher=simple -c perf_model/l1_dcache/prefetcher/simple/flows=8 -c perf_model/l1_dcache/prefetcher/simple/flows_per_core=false -c perf_model/l1_dcache/prefetcher/simple/num_prefetches=4 -c perf_model/l1_dcache/prefetcher/simple/stop_at_page_boundary=true -c perf_model/l2_cache/prefetcher=simple -c perf_model/l2_cache/prefetcher/simple/flows=64 -c perf_model/l2_cache/prefetcher/simple/flows_per_core=true -c perf_model/l2_cache/prefetcher/simple/num_prefetches=8 -c perf_model/l2_cache/prefetcher/simple/stop_at_page_boundary=true
pf_l1_simple|-c perf_model/l1_dcache/prefetcher=simple -c perf_model/l1_dcache/prefetcher/simple/flows=8 -c perf_model/l1_dcache/prefetcher/simple/flows_per_core=false -c perf_model/l1_dcache/prefetcher/simple/num_prefetches=4 -c perf_model/l1_dcache/prefetcher/simple/stop_at_page_boundary=true
llc_assoc4|-c perf_model/nuca/associativity=4
EOV
export K2B=1
for c in 64 32 16 12 8; do nohup setsid ./hw_launch2.sh hw_variants_scale.txt $c 8gb 4 50 > scale_$c.out 2>&1 < /dev/null & done
sleep 20; echo "jobs running: $(ps -u student -o cmd | grep 'hw_job.sh' | grep -v 'grep\|xargs\|bash -c' | wc -l)"; free -g | sed -n 2p
