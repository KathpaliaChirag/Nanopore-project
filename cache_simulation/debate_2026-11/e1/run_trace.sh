#!/bin/bash
# E1: trace slot indices of every GetAt lookup, 8GB db, T=1
export K2_TRACE=/dev/shm/e1_8gb K2_B=16
/usr/bin/time -v ~/e1/bin/kraken2 --db ~/chirag_K/AccuracyDrift/databases/standard_8gb --threads 1 --output /dev/null --report ~/e1/report_8gb_T1.txt ~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_10.fastq > ~/e1/run_8gb_T1.log 2>&1
echo DONE >> ~/e1/run_8gb_T1.log
