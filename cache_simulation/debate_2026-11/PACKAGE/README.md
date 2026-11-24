# reproducing the final build (state at the end of cycle 6, 2026-11-24)

one diff, five files: `final_vs_s19.diff` (1,155 lines) turns the S19 source tree into the final build described in ../FINAL_best_build.md. files touched: src/classify.cc, src/kseq.h, src/seqreader.h; new files src/mmbulk.h (bulk scanner) and src/preadfq.h (lock-free reader, exactness pre-pass, tail replay).

## the baseline it applies to

S19 on luna: `~/chirag_K/tools/kraken2-src-s19` (a working tree with uncommitted S6 to S19 changes; it has no git commit of its own, so identify it by checksum). first 16 hex characters of sha256 of the baseline files, and of the final files:

```
cb9a74af5b6f4a0a  classify.cc
7a5a5c5aef6719df  kseq.h
4d826566f35f8014  seqreader.h
02f1a740856190e9  compact_hash.cc
3c47d7e375592248  compact_hash.h
9b0a3d718de565b3  mmscanner.cc
---final
edaec02df3a1fdc5  classify.cc
ea51f5e7e22b72de  kseq.h
30fa1021c26fdc84  seqreader.h
d31e8ef4d685a614  mmbulk.h
33f3299b85cb1cd4  preadfq.h
```

## rebuild recipe (verified on luna, 2026-11-24)

```
cp -r ~/chirag_K/tools/kraken2-src-s19 build_final && cd build_final
patch -p1 < final_vs_s19.diff          # patches classify.cc kseq.h seqreader.h, creates mmbulk.h preadfq.h
cd src && make -j8 classify            # the Makefile keeps -DLINEAR_PROBING; make does not track headers: touch classify.cc seqreader.cc after editing a header
```

then copy the S19 install directory (`~/chirag_K/tools/kraken2-fresh-bin-s19`), replace its `classify` with the new one and point the `kraken2` wrapper's $KRAKEN2_DIR at it.

verification run of exactly this recipe: the patch applied cleanly, the build produced a 321,464-byte classify, and with `K2_BULK=1 K2_B=64` its per-read output and plain report were byte-identical to stock S19 on sample_targeted and standard_8gb, for reads_1000.fastq and a 20,000-read prefix (4 of 4 comparisons).

## run switches (all are env variables; defaults are conservative)

`K2_BULK=1` bulk scanner (default off); `K2_B=64` prefetch batch (default 16); `K2_PREAD=0` stock reader; `K2_PREAD_PRESCAN=0` skip the exactness pre-pass (malformed input then aborts with exit 3 instead of matching stock); `K2_PRESCAN_MMAP=0` plain pread pre-pass (recommended; the mmap pre-pass is slower); `K2_PRESCAN_OVERLAP=0` run the pre-pass after the database load; `K2_KEEPQ=1`, `K2_KEEPSTR=1`, `K2_OLDFMT=1`, `K2_CHUNKMERGE=1` restore the old quality handling, string building, formatting and counter merge for A/B. use 96 to 128 threads on a machine like luna.

## not covered by this package

translated (protein) search and `-D` daemon mode are untested; the validation scripts are in ../cycle3/code (validate_matrix.sh) and the results in ../cycle4/data and ../cycle5/data.
