# prefetch batch size at 96 threads (luna, 2026-11-23)

the batch size K2_B (lookups issued ahead before resolving; default 16, compile-time cap PF_MAX = 64) was tuned at 32 threads, where a sweep to 64 was a null (s20). at 96 threads with the lock-free reader the optimum has moved. bin_all (default pre-pass on, so absolute times include about 0.3 s), all reads, T=96, K2_BULK=1, 3 repetitions (data/kb.csv):

| db | K2_B=4 | 8 | 16 (default) | 32 | 64 |
|---|---|---|---|---|---|
| 8 GB | 2.08 2.08 2.09 | 2.12 2.14 2.10 | 2.06 2.05 2.09 | 2.01 2.03 2.01 | 2.01 1.98 2.00 |
| 16 GB | 2.63 2.63 2.62 | 2.58 2.56 2.60 | 2.51 2.52 2.52 | 2.43 2.47 2.46 | 2.43 2.43 2.42 |
| 103 GB | 7.97 7.79 7.87 | 7.38 7.35 7.44 | 7.08 7.05 7.33 | 6.91 6.98 7.15 | 6.79 6.88 6.97 |

medians 16 -> 64: 8 GB 2.06 -> 2.00 (-3%), 16 GB 2.52 -> 2.43 (-4%), 103 GB 7.08 -> 6.88 (-3%). the curve is still falling at the compile-time limit of 64, so a PF_MAX = 256 build (bin_pf) is queued to test 128 and 256 at T=96 and T=128.

why it makes sense: with 96 threads each keeping a batch in flight the memory system has far more outstanding misses, and a deeper lookahead hides more of the exposed GetAt stall (29.5% of the profile at 103 GB). the earlier 32-thread null does not transfer.
