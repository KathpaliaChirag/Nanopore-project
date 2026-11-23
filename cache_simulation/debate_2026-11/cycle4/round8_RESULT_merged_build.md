# the merged build (bin_all): every case in the matrix identical to stock, and the price of exactness (luna, 2026-11-23)

bin_all = lock-free reader + exact truncation/damage handling (implementer I4, with its pre-pass) + bulk scanner + guard (quick-mode key fix) + prefetch dedup + quality skip + output path (implementer I5). tree ~/e1/impl_all, diff vs the output-path tree: code/merged_trunc_on_out2.diff. data/all_correct.txt, data/all_prescan.csv, data/validate_matrix4.log.

## correctness

- all 1,872,777 reads at T=96 vs stock S19 at T=32 on 50 MB, 8 GB, 16 GB, 103 GB: per-read output identical and plain report BYTE-identical.
- validation matrix run 4 (about 150 generated cases x 2 builds: bin_all with K2_BULK=1 and the same binary with K2_OLDFMT=1 K2_KEEPSTR=1): 308 PASS, 0 FAIL, 0 WARN. this includes every malformed/truncated-input case (c_eof_after_seq, c_eof_after_plus, c_eof_after_plus2, c_eof_mid_qual, c_long, c_short and their _K variants) that the previous parallel reader failed, FASTA, CRLF, paired-end, -Q, -C/-U, --report-minimizer-data, --quick and gz/stdin inputs.
- implementer I4's own checks: 35,214 unit cases plus two 8,000-iteration fuzz runs with no differences; 428 end-to-end case comparisons and 1,350 truncation-sweep comparisons identical to stock.

## the cost of the pre-pass (data/all_prescan.csv, T=96, 5 interleaved repetitions, wall seconds)

| db | K2_PREAD_PRESCAN=0 (old behaviour: loud abort on mid-file damage) | prescan on (exact, the default) | cost |
|---|---|---|---|
| 50 MB | 1.79 1.79 1.82 1.79 1.80 | 2.10 2.14 2.13 2.15 2.12 | +0.32 s (+18%) |
| 8 GB | 1.77 1.73 1.74 1.71 1.75 | 2.08 2.08 2.06 2.08 2.08 | +0.34 s (+19%) |
| 103 GB | 6.97 6.87 6.96 7.03 6.81 | 7.24 7.10 7.13 7.26 7.22 | +0.26 s (+3.7%) |

implementer I4 had estimated under 1% from a 100 MB test; at 12.5 GB the pre-pass costs about 0.33 s because it reads the whole input once more (about 38 GB/s, a copying read near the memory-bandwidth limit), which is a fixed 0.3 s that matters only when the whole run is under 2 s.

speed against stock S19 at 32 threads (8.39 / 8.60 / 20.29 s): prescan on 4.0x (50 MB), 4.1x (8 GB), 2.8x (103 GB); prescan off 4.7x, 4.9x, 2.9x.

## decision for sir (not made here)

exactness on malformed input costs 0.3 s per 12.5 GB of input. options: (a) keep the pre-pass on by default (exact; the safe default), (b) default it off and keep the loud abort (rc 3 with a message naming K2_PREAD_PRESCAN=0/K2_PREAD=0), (c) make the pre-pass cheaper: use mmap'd chunks instead of pread (no copy, likely half the cost), or run it concurrently with the database load (hidden at 103 GB where the load takes 3.2 s). (c) is the next engineering step.
