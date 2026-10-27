# cycle 2, R3 vote, a4_hw

## 1. vote

- **build list (section 2): AGREE.** it differs from my R2 list by one rank in two places: M30 sits at 5 instead of 4, and M5 at 7 instead of 6. both came out of the rank-sum. neither changes what gets built first.
- **measure list (section 3): AGREE.** the riders on E1 (the qd1-vs-qd16 timing, the exit column, M60) cover my kill tests.

## 2. moves

none.

## 3. factual errors (non-blocking)

1. **the M9 row's H2 capped cell says 38-300x.** from the cell's own inputs:
   - copy: 19-30 s [arith on the 0.25-0.40 GB/s class range]
   - map: 1,050 faults x 0.1-0.5 ms = 0.105-0.525 s [arith]
   - ratio: 19 / 0.525 = 36x, 30 / 0.105 = 286x

   so the cell should read **~36-290x** [arith]. the uncapped 3.5-28x is right (19 / 5.35 = 3.6x, 30 / 1.07 = 28x).
2. **I checked every other H1-H5 cell taken from my files, and they match:** M9 (H1 ~3.4x / ~34x, H5 6-55x), M20' (H2 ~11.6x, H5 2-4x), M30 (H5 3-27x), M11 (H5 ~847 s), M2 (H2 1.01-1.08x), M5 (H5 1.5-3x), M26, M21 [repo: `cycle_2_r2_a4_hw.md` section 4].
