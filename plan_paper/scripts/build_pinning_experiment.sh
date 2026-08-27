#!/bin/bash
# Builds all 6 binaries for the capacity x eviction-policy experiment:
# 2 eviction policies (round-robin via s2_standalone_patch.py, pinned via
# s2_pinned_patch.py) x 3 sizes (4096, 65536, 262144). Skips 1,048,576+
# deliberately - we already confirmed that's dominated by the thread_local
# memory-init cliff regardless of eviction policy, which would confound
# this specific comparison rather than inform it.
#
# Both patch scripts now print their own configured size in every run's
# output (size=%zu ways=%zu), so every binary this script builds is
# self-labeling - no risk of mixing up which binary was which size, the
# way we could have before.
#
# Run from ~/tools/kraken2-src-fresh/src, with s2_standalone_patch.py and
# s2_pinned_patch.py already downloaded to /tmp (curl from GitHub raw URLs).

set -e
cd ~/tools/kraken2-src-fresh/src

# Preserve the real committed tree - every build below is a temporary
# swap-patch-build-restore, same discipline as every size variant this
# session.
cp classify.cc classify.cc.s1s2-combined.bak

build_variant() {
  local patch_script=$1
  local size=$2
  local outdir=$3
  cp classify.cc.pre-s1.1.bak classify.cc
  python3 "$patch_script"
  if [ "$size" != "4096" ]; then
    sed -i "s/static const size_t S2_NUM_SETS = 4096;/static const size_t S2_NUM_SETS = $size;/" classify.cc
  fi
  cd ..
  ./install_kraken2.sh ~/tools/kraken2-fresh-bin-"$outdir"
  cd src
}

echo "=== round-robin, 4096 (already exists as kraken2-fresh-bin-s2-standalone, rebuilding for the size-label fix) ==="
build_variant /tmp/s2_standalone_patch.py 4096 s2-standalone
echo "=== round-robin, 65536 ==="
build_variant /tmp/s2_standalone_patch.py 65536 s2-standalone-65536
echo "=== round-robin, 262144 ==="
build_variant /tmp/s2_standalone_patch.py 262144 s2-standalone-262144
echo "=== pinned, 4096 (rebuilding for the size-label fix) ==="
build_variant /tmp/s2_pinned_patch.py 4096 s2-pinned
echo "=== pinned, 65536 (rebuilding for the size-label fix) ==="
build_variant /tmp/s2_pinned_patch.py 65536 s2-pinned-65536
echo "=== pinned, 262144 ==="
build_variant /tmp/s2_pinned_patch.py 262144 s2-pinned-262144

# Restore the real committed tree.
cp classify.cc.s1s2-combined.bak classify.cc
diff classify.cc classify.cc.s1s2-combined.bak && echo "RESTORED CORRECTLY - all 6 variants built"
