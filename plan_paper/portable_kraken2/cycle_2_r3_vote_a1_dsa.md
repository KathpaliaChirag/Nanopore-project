# cycle 2, R3 vote, a1_dsa

## 1. verdict

- **build list (section 2): AGREE.** M27a inside M2 is fine. it is a 0.25-day rider either way, and M27b waits on M28 as it should. M30 at 5 instead of my 6 is within one rank.
- **measure list (section 3): AGREE.** i had the cpu gate one place higher. the order does not change what runs first, because M22 and M1 come before both.

## 2. moves

none.

## 3. factual errors

one precision fix in section 1.5, "up to ~22% of lookups unprefetched on 150 bp reads". that figure is the uncapped case.
- on a capped db (f ≈ 0.10), a 150 bp read has ~3 real lookups [arith: 116 positions x 0.316 x 0.10]
- all of them fall inside RC1's unprefetched first 8, so none is prefetched [external: RC1 `compact_hash.h`; repo: `cycle_2_r1_a1_dsa.md` M27 table]
- suggested wording: "~22% uncapped, all of them on capped dbs"

the other arithmetic i re-checked holds [arith]:
- 10K syscalls at 1-2 µs is ~0.9-1.8% of 1.13 s
- 111 GB / 131 MB/s ≈ 847 s
- 10.7K x 1-9 ms = 11-96 s
- the H2 range of 3.5-28x
