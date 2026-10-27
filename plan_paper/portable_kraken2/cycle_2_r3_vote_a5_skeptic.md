# cycle 2 R3 vote: a5_skeptic

**build list (section 2): AGREE.** M30 standalone at 5 is fine, because its 2-minute qd1-vs-qd16 gate runs first. M40 rides inside M2, as listed.

**measure list (section 3): AGREE.**

**fact fixes (no reorder):**
1. **1.4, "provisioned gp3 goes to 2,000 MiB/s".** that is the volume's limit. the instance caps it: m7i.xlarge has 156.25 MB/s baseline and 1,250 MB/s max EBS bandwidth [external: aws gp.html, a4 N2], and how long the max lasts is [UNCLEAR]. so on a small vm, "provision throughput" buys at most the instance cap. it is not the cheapest fix as stated.
2. **1.2, "lost only 1.5x".** that is 611.7 vs 403.8 kb/min between ratios 3.25 and 52. Coriolis gives no in-ram point [external: Coriolis table], so it is not a slowdown against fitting. say "1.5x across a 16x pressure range, no in-ram baseline".
3. **M20' H4 cell, "1 vs 64 threads".** M20' picks physical cores, which is 96 on luna. at 96, stock gives 1,046.04 / 84.81 = 12.3x and s10 gives 685.43 / 22.40 = 30.6x [arith on measured, one run each]. the range barely moves, but the thread count should match the rule.
