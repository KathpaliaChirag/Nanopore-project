# cycle 2 round 5 results (luna, 2026-11-23): thread count, numa, prefetch dedup

none of these are cache results. they came out of the round 4 votes and the production profile, and they are recorded here because they change what the final build looks like.

## 1. thread count: 48 beats 32 everywhere (no code change)

guarded S19, all 1,872,777 reads, plain --report, 3 repetitions, wall seconds (raw: data/thr.csv):

| db | T=16 | T=32 | T=48 | T=64 | T=96 |
|---|---|---|---|---|---|
| 50 MB | 14.96 14.99 14.99 | 8.05 7.97 7.88 | 6.71 6.75 6.83 | 6.89 6.86 6.81 | 7.09 7.17 7.12 |
| 8 GB | 13.84 13.96 13.85 | 7.61 7.51 7.57 | 7.21 7.21 7.22 | 7.45 7.41 7.42 | 7.62 7.63 7.61 |
| 16 GB | 15.79 15.85 15.82 | 8.53 8.50 8.59 | 7.61 7.58 7.43 | 7.79 7.72 7.66 | 8.07 7.92 7.94 |
| 103 GB | 20.30 20.20 20.24 | 12.19 12.21 12.17 | 10.36 10.40 10.44 | 10.51 10.51 10.62 | 11.00 10.70 10.98 |

T=48 versus T=32: 50 MB -15%, 8 GB -4.8%, 16 GB -11%, 103 GB -14.7%. more than 48 threads gets slower again, which fits Luna's 48 physical cores per socket (SMT siblings add contention, not throughput). output does not depend on the thread count (the per-read file is written in input order).

## 2. numa placement is not a lever

8 GB: bind node0 7.45 s vs default 7.58 (-1.7%), cpunodebind only 7.53, interleave 7.80 (+2.9%). 16 GB: bind0 8.54 vs 8.60 default, interleave 8.81. 103 GB: default 12.31, interleave 12.76, cpunodebind=0 14.19 (the 111 GB table does not fit one node). the round 3 estimate of 3 to 10% was wrong; the prosecutor and agent C were right that it is under 2%.

## 3. prefetch dedup in fill() (code/prefetch_dedup.diff), found by round 4 agent A

observation: S19's fill() hashes and prefetches EVERY minimizer the scanner returns (about 3,400 per read), but the resolve loop only looks up the ones that differ from the previous minimizer (about 117 per read at 8 GB) and, on capped databases, only those above minimum_acceptable_hash_value. moving both tests into fill() before the hash and the prefetch is byte-identical by construction (the resolve loop never reads hc or idx for those entries).

correctness: per-read output and plain report byte-identical to the guarded build on all four databases, all 1,872,777 reads (data/dd_correct.txt).

timing, T=32, 5 interleaved repetitions (data/dd.csv), median wall seconds, guarded -> guarded + dedup:

| db | guarded | + dedup | gain |
|---|---|---|---|
| 50 MB | 7.93 | 7.69 | -3.0% |
| 8 GB | 7.54 | 7.21 | -4.4% |
| 16 GB | 8.55 | 8.31 | -2.8% |
| 103 GB | 12.13 | 11.93 | -1.6% |

the repetition ranges never overlap. the gain is smaller than the 6 to 10% agent A estimated: the wasted prefetches were mostly cheap (repeats hit the same cache line), so removing them saves hashing and issue slots, not memory stalls.
