# sniper redo (started 2026-11-24): same-source cache-off baseline, cache modelling, single and multicore

why: the first Sniper study compared a no-cache build (S0) from a different source tree against cache builds (16 to 34 M extra instructions in S0), used a half-size LLC slice (config error), and only ever ran single-core. this redo builds EVERY variant from one source tree (the sizepin-65536 tree) with compile-time switches, checks each against the baseline classifier for identical output, uses the corrected luna2.cfg (LLC slice 2250 KB), and adds multicore.

variants (all from one tree, code/sn_patch.py + code/build.sh): off (cache never hits or allocates), w1/w4/w8/w16 (1/4/8/16 ways at 4,096 sets), s2048/s16384/s65536 (4 ways at 2,048/16,384/65,536 sets; entry 16 B so 128 KB / 1 MB / 4 MB).
workloads: short set = nested prefixes of workloads/50reads.fastq (10/25/50 reads = 7.9 K / 37 K / 91 K bases); long set = the existing long_10/25/50.fastq (0.35 M / 0.9 M / 1.87 M bases).
single core: run-sniper -n 1; multicore: -n 4 with general/total_cores=4, classify -p 4 and K2_BLOCK=10000 so small inputs split into several blocks (otherwise they fit in one 3 M-base block and only one core works).
runner: code/sn_job.sh (one run, appends one row to results.csv), chains in code/chain1.sh and chain2.sh. results: results.csv (copied here as results.csv when the run finishes).
