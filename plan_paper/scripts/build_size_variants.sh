#!/bin/bash
# Builds the 3 extra S2 cache-size variants used in the size sweep
# (plan_paper/scripts/compare_sizes_full.py). Run from
# ~/tools/kraken2-src-fresh/src on Luna, AFTER s2_patch.py has already been
# applied (i.e. classify.cc already has S2_NUM_SETS = 4096 in it).

set -e
cd ~/tools/kraken2-src-fresh/src

# Preserve the current (4096-set) classify.cc explicitly - each size variant
# is generated FROM this same known-good baseline, not by editing on top of
# the previous iteration's edit, so there's no risk of the size constant
# drifting or a previous sed leaving the file in an unexpected state.
cp classify.cc classify.cc.s2-4096.bak

for size in 65536 1048576 4194304; do
  echo "=== building S2_NUM_SETS=$size ==="
  sed "s/static const size_t S2_NUM_SETS = 4096;/static const size_t S2_NUM_SETS = $size;/" \
    classify.cc.s2-4096.bak > classify.cc
  cd ..
  ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s2-$size
  cd src
done

# Restore the working tree to the committed 4096-set version - the sweep
# only needed temporary rebuilds; the actual committed S2 code stays at
# 4096 unless a later step deliberately changes it. Verify this worked
# with: diff classify.cc classify.cc.s2-4096.bak (should print nothing).
cp classify.cc.s2-4096.bak classify.cc
