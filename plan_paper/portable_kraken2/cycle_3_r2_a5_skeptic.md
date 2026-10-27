# cycle 3, round 2: a5_skeptic (2026-10-27)

no new fetches. tags as in `00_context.md` section 6.

## 1. one line per item

| id | verdict |
|---|---|
| M75 | rider in M9. it absorbs my M92. |
| M76 | rider. it is a correctness item in our own new code, so it must land before M30 ships. |
| M77 | rider, but in M2's upstream bundle rather than M9. it changes `fast_reader`, which is upstream code [external: cycle-1 a3 S4]. |
| M82 | keep, as a revision of M21. |
| M86 | rider in M24. untestable here: no wsl2 box, no mac [repo]. |
| M90 | rider in M1 / E2. merge a3's M80 into it: the conda binary is the v2.17.2 column. |
| M91 | rider in the cpu gate. |
| M70 | unranked measure, behind M61. one arithmetic fix (section 3). |
| M71 | below the line. one arithmetic fix (section 3). |
| M72 | below the line, behind M70. |
| M78, M88, M89 | unranked measures. all depend on access we may not have [UNCLEAR]. |
| M85 | campus visit. |

none of these moves a rank. each one lives inside an existing id, or behind a gate that has not run.

## 2. wording fixes (brief section 2)

1. **confirm.** bioconda and homebrew ship 2.17.2, and debian sid ships 2.1.3 [external: cycle-3 a5 T3-T5].
2. **confirm.** PR #1033 merged 2026-06-24 [external], before S8 [repo: `command_log.md`]. BWA-MEM's rewrite and minibwa already prefetch [external: T7, T8].
3. **confirm.** 151K iops at qd16 comes from one enterprise drive (a4 cycle-1 src 6).
4. **confirm.** 4.23 s is sys cpu time used as load time [repo: `RESULTS.md` 1.4].
5. **confirm.**
6. **new, for a3's M80.** "the stock most users actually run is the bioconda build" is an overclaim. the recipe proves what bioconda *ships* [external: a3 P1]. it does not prove what most users *run*:
   - debian and ubuntu apt users get 2.1.3 [external: T5]
   - homebrew shows 573 installs in a year [external: T3]
   - conda download counts were not readable [external: T4]

   say "the stock conda users run". the share of users per channel is [UNCLEAR].

## 3. overclaims in the other cycle-3 R1 files

1. **a1 M71, "about 0.6 s for the full uncapped input".** this does not re-derive.
   - the full input on an uncapped db is 6.036e9 x 0.316 ≈ 1.9B lookups [arith]
   - at a1's guessed 0.8B lines/s that is ≈ 2.4 s, not 0.6 s [arith]
   - and orin cannot run the full input at all: 12.5 GB of input against 8.5 GB free [repo]
   - the runnable case is 104,918 reads on 50MB: ~106M lookups, ≈ 0.13 s at that rate [arith]
   - the 0.8B/s rests on a guessed 25% of the 204.8 GB/s spec peak, but the cpu stream copy on an orin reached only 55-72 GB/s [external: a4 cycle-1 src 2]. so the number is a ceiling twice over
2. **a1 M70, "~5% of the records' 1 GB of partition traffic".**
   - 100M records x 16 B = 1.6 GB per pass. a1's own budget (4 x 16 B per lookup) gives ~6.4 GB per block [arith]
   - so the table stream (48.8 MB) is under 1% of the traffic, not ~5%
   - that helps M70's case, but the figure should match the stated budget
3. **a2 M75, "≤ 256 MB/s" per stream on nfs.**
   - 128 KiB / 0.5 ms holds only if each read-ahead window waits for the one before it. linux read-ahead is asynchronous, so one stream can beat that bound [guess]
   - for kraken2's copy load, which issues 64 MB `pread` calls (8 streams upstream [external: cycle-1 S3]), the 128 KiB read-ahead mostly matters for `-M` and for the input reader, not for the loader [guess]
   - so M75's read-ahead advice applies to the map and input paths. the stripe advice applies to all
4. **a4 variant 4.** the only contention source is a tegra k1 [external: a4 N5], and it measures the gpu slowing down, not kraken2. "co-running dorado could slow classify" stays [guess] until M85. a4 already says this; FINAL must keep the tag if it quotes it.
5. **a4 H1-wsl2, "usually cold".** this rests on [guess] about how `vmIdleTimeout` and `autoMemoryReclaim` interact [external: a4 N1]. keep "usually cold" out of FINAL until M88 runs.
6. **a2 M76, "103GB has 6.8M pages at 16K".** 111e9 / 16,384 = 6.8M [arith]. holds.

## 4. verdict

**list unchanged: agree.** both the build top 10 and the measure top 5 stay as in `cycle_2_conclusion.md`. the riders and fixes above apply.
