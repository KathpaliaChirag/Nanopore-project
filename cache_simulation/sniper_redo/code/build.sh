#!/bin/bash
cd ~/e1/sn; mkdir -p bin
build() { # name macros
  rm -rf b_$1 && cp -r src0 b_$1 && cd b_$1/src && make clean >/dev/null 2>&1
  nice make -j4 classify KRAKEN2_SKIP_FOPENMP="-fopenmp $2" > ../build.log 2>&1 && cp classify ~/e1/sn/bin/classify_$1 && echo "built $1 ($2)" || echo "FAILED $1"
  cd ~/e1/sn; }
build off   "-DS2_OFF"
build w1    "-DS2_WAYS_N=1 -DS2_SETS_N=4096"
build w4    "-DS2_WAYS_N=4 -DS2_SETS_N=4096"
build w8    "-DS2_WAYS_N=8 -DS2_SETS_N=4096"
build w16   "-DS2_WAYS_N=16 -DS2_SETS_N=4096"
build s2048  "-DS2_WAYS_N=4 -DS2_SETS_N=2048"
build s16384 "-DS2_WAYS_N=4 -DS2_SETS_N=16384"
build s65536 "-DS2_WAYS_N=4 -DS2_SETS_N=65536"
ls -la bin | tail -9
