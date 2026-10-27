# cycle 2, r3 vote: a3_cpu

## 1. vote

- **build list (section 2): AGREE.**
  - my M4/M41-above-M9 view stays on record in section 4, but i do not block on it. all three are gated by cheap tests, so the order only changes which test runs first.
  - folding M27a and M40 into M2 is fine, as long as M40's 10-minute `objdump` check runs (it is listed under M1's riders).
- **measure list (section 3): AGREE.**

## 2. moves

none.

## 3. factual error

**M20' row, H4 cell: "12.7x-30x, 1 vs 64 threads, 103GB".**
- M20' sets the default to physical cores, which is 96 on luna, not 64.
- at 96 threads the same sweep gives:
  - stock: 1,046.04 / 84.81 = **12.3x**
  - s10: 685.43 / 22.40 = **30.6x**

  [arith on measured: `next_steps_plan_2026-10-21.md` section 6]
- the cell should read "12.3x-30.6x, 1 vs 96 threads (the M20' default) [measured, one run per point]".
- the range barely moves, but the cell should describe the default it ranks.
