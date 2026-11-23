# the output path: 15 to 19% faster on the small databases, byte-identical (luna, 2026-11-23)

build: bin_out2 = lock-free reader + bulk scanner + guard + dedup + quality skip + implementer I5's output-path changes (code/impl_out.diff) + the quick-mode key fix (code/quickmode_keys_fix.diff). all 1,872,777 reads, T=96, K2_BULK=1, report on. data/out.csv, data/out_correct.txt.

changes (each with an env switch to turn it off in the same binary):
1. the c1/c2/u1/u2 strings (to_string + ostringstream copies of every read, plus 4 str()+assign copies per chunk) are only built when -C/-U is requested. K2_KEEPSTR=1 restores the old behaviour.
2. the kraken output line and the hit list are appended into the output buffer with a hand-written decimal routine instead of ostringstream. K2_OLDFMT=1 restores the old path.
3. per-thread taxon counters merged once per thread instead of once per chunk (only with --report, never with --report-minimizer-data). K2_CHUNKMERGE=1 restores the old merge.

## byte-identity against stock S19 (T=32) at T=96, all reads

50 MB, 8 GB, 16 GB, 103 GB: per-read output identical, plain report BYTE-identical.
(small inputs, implementer I5, 29 of 30: all identical; the one difference, --quick on standard_8gb, was my lazy-key shortcut, now fixed: see round6_RESULT_quickmode_keys.md.)

## timing, wall seconds, 5 interleaved repetitions, output to /dev/null

| db | before (bin_pread2) | all three changes | K2_OLDFMT=1 | K2_KEEPSTR=1 | K2_CHUNKMERGE=1 |
|---|---|---|---|---|---|
| 50 MB | 2.09 2.11 2.14 2.14 2.19 | 1.76 1.79 1.77 1.81 1.81 | 1.91 1.90 1.90 1.94 1.92 | 1.98 1.99 2.03 2.04 2.15 | 1.79 1.79 1.82 1.80 1.85 |
| 8 GB | 2.15 2.17 2.18 2.16 2.21 | 1.76 1.75 1.83 1.75 1.77 | 1.94 1.93 1.95 1.94 1.98 | 2.07 2.06 2.06 2.04 2.08 | 1.73 1.76 1.72 1.72 1.72 |
| 103 GB | 7.35 7.30 7.42 7.54 7.50 | 7.09 7.00 6.95 6.84 7.10 | 6.92 7.09 7.03 6.87 7.07 | 7.27 7.42 7.30 7.31 7.37 | 6.93 6.99 6.91 6.88 6.86 |

medians: 50 MB 2.14 -> 1.79 (-16%), 8 GB 2.17 -> 1.76 (-19%), 103 GB 7.42 -> 7.00 (-6%). skipping the discarded c1/u1 strings is the largest part (turning it back on costs 0.2 to 0.3 s), the new formatting is worth about 0.15 to 0.2 s, the per-thread counter merge is neutral.

real output file (8 GB, output written to /dev/shm, 3 reps): 2.31 2.30 2.36 -> 1.96 1.97 1.96 (-15%), so the gain is not an artefact of writing to /dev/null.

## against stock S19 at its default 32 threads (stock medians 8.39 / 8.60 / 10.16 / 20.29 s)

50 MB: 8.39 -> 1.79 s = 4.7x. 8 GB: 8.60 -> 1.76 s = 4.9x. 103 GB: 20.29 -> about 7.0 s = 2.9x. byte-identical output and report.
