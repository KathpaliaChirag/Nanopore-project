# cycle 3, round 2: a3_cpu

no new fetches. read: the relay brief and all five `cycle_3_r1_*.md` files.

## 1. one line per new item

| id | verdict | cpu-lens note |
|---|---|---|
| M75 network / parallel fs rule | keep as a rider in M9 / M33 | no cpu cost. it is advice plus a stream count |
| M76 runtime page size and `hpage_pmd_size` | keep as a rider (same as my M81) | i take a2's reading of the arm64 doc: 16K base pages give a 32M pmd huge page, 64K give 512M [external: a2 c3] |
| M77 input read-ahead outside the lock, no io_uring | keep as a rider in M9 | one `WILLNEED` per 3 MB block is ~3,974 calls per full input [arith], negligible. docker's default seccomp "blocks" io_uring [external: a2 c3 src 4], so i withdraw my cycle-2 "io_uring could batch M30's calls" option. M30 stays plain `fadvise` calls or helper threads |
| M82 arm tier `armv8.2-a` + a current compiler | keep inside M21 | the 15% compiler gain is graviton2, another workload [external: my c3 P3], so [guess] for kraken2 |
| M86 probe backends (wsl2, macOS) | keep as a rider in M24 / M9 | on macOS, M30, M31 and M77 all lean on `posix_fadvise`. if it is missing there [UNCLEAR], all three fall back to "copy, no advice" |
| M90 channel-aware baseline (v2.1.3 column) | keep as a rider in M1 / E2 | it merges with my M80. bioconda and brew ship 2.17.2 binaries for arm and macOS [external: P1, a5 T3-T4], so E2 and M89 need no stock build. 2.1.3 predates the parser rewrite, so report a diff count, not only a ratio [a5] |
| M91 `ResolveTree` share in the cpu gate, #1063 if it matters | keep as a rider | a5's arithmetic holds: 0.69 µs x 1,872,777 = 1.29 s; 199 µs x 1,872,777 = 373 s [arith]. no `ResolveTree` symbol appears in S19's top list [measured], so it may be inlined into `ClassifySequence` [UNCLEAR]. the cpu gate's annotate shows its inlined lines either way. #1063 claims no byte identity [external: a5 T2], so `cmp` decides |
| M70 sort-probe-unsort microbenchmark | keep unranked | luna 50MB should lose: probes there are already L3 hits [measured: 50MB fits 105 MB L3], so the two radix passes (~64 B per lookup [a1]) are pure cost. orin 50MB is the real test, as a1 says |
| M71 orin igpu lookups | keep below the line | the cpu still scans and builds the list, so the gpu can remove only the lookup share: 19.5% on luna 50MB [measured], [UNCLEAR] on orin. ceiling 1 / (1 - share). ~0 on capped dbs, and 0 while dorado runs |
| M72 in-ram sweep | keep below the line | waits on M70 |
| M78 cluster run | keep unranked | |
| M85 orin co-run with dorado | keep on the campus visit | if co-running slows classify, M20' on orin should leave cores to dorado's host threads. that is a rider, not a rank |
| M88 wsl2 cold-after-idle | keep unranked | |
| M89 apple silicon run | keep unranked | the bioconda osx-arm64 binary [external: P1] means no build is needed for stock |

none of these moves a rank. each is a rider inside a top-10 id, a measure behind the top 5, or below the line.

## 2. wording fixes

1. **"the binary conda and brew users install": confirm.** bioconda and brew are on 2.17.2, debian sid on 2.1.3 [external: a5 T3-T5; my c3 P1].
2. **"its own" prefetch, load, parser and huge pages: confirm.** PR #1033 merged on 2026-06-24, before S8 [external: cycle-1 S3; repo]. aligners already prefetch [external: a5 T7, T8]. no talk should present batched prefetch as new for bioinformatics.
3. **"on an enterprise nvme": confirm.** the 0.106 ms and 151K iops come from one Kingston DCP1000 review [external: a4 cycle-1 src 6]. laptop nvme stays [UNCLEAR] until the qd1-vs-qd16 timing.
4. **[UNCLEAR] back on orin's ~11.6x: confirm.** it treats stock's 4.23 s of sys cpu time as load time [repo: `RESULTS.md` 1.4]. i flagged the same in cycle 2.
5. **drop "only" from "lost only 1.5x": confirm.** Coriolis has no in-ram point [external: a5 c2 N2].

## 3. verdict

**list unchanged: agree.** build top 10 and measure top 5 as in `cycle_2_conclusion.md`, with the riders above.
