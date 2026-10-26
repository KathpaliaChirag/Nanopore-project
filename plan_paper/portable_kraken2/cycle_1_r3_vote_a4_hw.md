# cycle 1, R3 vote, a4_hw

## 1. vote

- **build list (section 2): DISSENT**, one change.
- **measure-first list (section 3): AGREE.** the orin probe ranks 5th, but it should still ride on the first campus visit, since it can't run on luna anyway.

## 2. the change

**move M10 from rank 7 to rank 9**, so M5 becomes 7 and M21 becomes 8.
- M10's only real cell is H4. it needs kernel ≥ 6.1 [external: a2 src 2]. it is dead on orin's 5.10, where thp is likely already "always" [external: OE4T `mm/Kconfig`].
- H1 can't run any linux kraken2 today [repo: user memory, no wsl since july 2026].
- M5 helps every class whenever the input is gz. M21 is what lets orin build at all, because gcc-11 `-march=native` fails there [external: a3 S7].
- their borda scores tie (16 vs 16), so the class spread should break the tie, not a head-to-head vote.

## 3. factual errors

1. **section 1.2, d is written upside down.** the ratio is 3,220,914 distinct hit minimizers (the `HyperLogLogPlusMinus::insert` count) / 10,179,375 hit positions (the hit-count map's `operator[]` calls) = 0.316 [repo: `gprof_report.txt` lines 10, 123]. as written, the division gives 3.16.
2. **section 1.2, f is from one db.** f ≈ 0.088 belongs to that one wsl2 ESKAPE db. f for our 8GB and 16GB is unmeasured until M22. also d x f = 0.316 x 0.088 = 0.028, which is 1 lookup per 36 positions, not "about 1 per 30" [arith]. so section 1.3's "~10 wasted prefetches per real lookup" on 8GB is a [guess].
3. **the M20 row, H2 cell** drops the measured 16GB figure. it should read 11.4x on 50MB and 4.5x on 16GB [measured: `RESULTS.md` 1.4].
4. every other cell taken from my grid matches `cycle_1_r2_a4_hw.md` section 5.
