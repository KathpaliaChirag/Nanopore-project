# cycle 2: -march=native (the never-built S21a) is a null (luna, 2026-11-23)

build: guarded S19 source (e1/src_hll) with `-march=native -ffp-contract=off` added to CXXFLAGS in src/Makefile (the Makefile edited in place, so -DLINEAR_PROBING stays). the binary now contains 61 vector instructions (ymm/zmm) against 0 in the stock build, so the flag did reach the code.

correctness: 8 GB, all 1,872,777 reads, per-read output byte-identical to the guarded build, and the plain report byte-identical.

timing: T=32, all reads, plain --report, 5 interleaved repetitions, wall seconds (raw: data/nat.csv):

| db | guarded S19 | + -march=native |
|---|---|---|
| 50 MB | 7.97 7.94 7.89 7.93 7.90 | 7.92 7.92 7.89 7.91 7.89 |
| 8 GB | 7.53 7.60 7.60 7.58 7.55 | 7.67 7.58 7.61 7.53 7.59 |
| 16 GB | 8.58 8.51 8.60 8.63 8.55 | 8.65 8.68 8.64 8.61 8.61 |
| 103 GB | 12.26 12.37 12.25 12.15 12.21 | 12.49 12.37 12.32 12.29 12.28 |

medians: 50 MB 7.93 vs 7.91, 8 GB 7.58 vs 7.59, 16 GB 8.58 vs 8.64, 103 GB 12.25 vs 12.32. all inside noise, 103 GB and 16 GB marginally worse (+0.6%, +0.7%).

verdict: null. the compiler vectorised a little but the scanner's cost is a data-dependent loop with branches, not arithmetic the vector units can speed up, which also matches the scanner agent's branch-misprediction hypothesis (round3_A_scanner.md). LTO and PGO remain untested (round3_B ranks them third).
