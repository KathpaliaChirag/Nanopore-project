# round 5 results: E1 (trace + bound) and E3 (structbench), run on luna 2026-11-23

all numbers below were measured on luna (dell-R760, 192 threads, shared, ~65 users logged in). single runs or best-of-3, so differences under ~15% are noise. nothing here is a wall-clock speedup of kraken2.

## E1: probe-slot trace of S19 on the 8GB db (105k reads, T=1)

method: copied the S19 tree to ~/e1, added a tracer at the GetAt call site (e1/tracer_patch.diff) that logs slot index + hit bit per lookup to /dev/shm. classification output unchanged (101,922 / 104,980 classified, 97.09%, same as stock). tracer overhead ~3% (15.4 s vs 14.9 s). 12,237,762 lookups, 2,270,742 unique slots. analysis code: e1/analyze.cpp, raw output: e1/analysis_8gb_T1.txt.

| fact | value |
|---|---|
| lookups that hit a stored k-mer | 86.75% |
| global repeat rate (lookup slot seen before) | 81.4% |
| top 16K / 64K / 262K / 1M slots cover | 12.5% / 24.2% / 55.8% / 90.0% of lookups |
| repeats at reuse distance 2^17 to 2^21 | about 77% |
| lines (64 B) per lookup if all distinct | 0.184 |

hit rate of a cache of N entries on this trace (fully associative unless noted):

| N | LRU | 4-way LRU | Belady (optimal) |
|---|---|---|---|
| 16K | 10.4% | 10.4% | 28.0% |
| 64K | 18.9% | 18.5% | 44.1% |
| 262K | 40.1% | 38.9% | 66.6% |
| 1M | 76.5% | 71.0% | 81.4% |

windowed dedup (share of lookups removable inside a window of W lookups): 8.2% at 10K, 15.4% at 100K, 43.7% at 1M, 75.8% at 10M.

so the earlier "no reuse" story is wrong for this workload: reuse is large and skewed. the reuse is just far away (tens of thousands to millions of distinct slots between uses), so only caches of 262K entries or more capture it. caveat: 105k reads is a sample of one fastq file, so repeat rates are lower bounds for a 1.87M-read run, and a T=32 per-thread cache sees 1/32 of this trace.

lookup share of cpu, stock S19, perf record, T=1, 105k reads (classify process):

| db | PrefetchIndex | GetAt | lookup total | NextMinimizer | notes |
|---|---|---|---|---|---|
| 8GB | 7.08% | 0.66% | 7.7% (about 15% of user-space time) | 23.8% | kernel db load ~20% |
| 16GB | 5.98% | 0.94% | 6.9% | 17.6% | kernel db load ~45% |
| 103GB | 1.13% | 0.58% | 1.7% (about 28% of user-space time) | 2.4% | kernel load ~65%, only ~450 user samples, rough |

GetAt is under 1% everywhere: S19's prefetching already hides almost all dram latency. the table lookup is not what limits S19 on 8GB.

bound on any cache or eviction policy at 8GB: gain is at most (hit rate) x (lookup share). 4-way LRU at 262K: 0.39 x 0.077 = about 3%. belady at 262K: 0.67 x 0.077 = about 5%. both are before paying the cache's own probe cost. so no eviction policy can give a noteworthy speedup on 8GB or 16GB after S19.

## E3: structbench, linear vs double hashing vs line-aligned (4-byte cells, load 0.70, S16-style batched prefetch)

tables: 2^31-1 and 2^33-1 cells (8 and 32 GB), hit mix 87% like the real trace. code: e1/structbench.cpp, raw: e1/structbench_8gb.txt, structbench_32gb.txt (also 0% and 100% miss mixes).

cache lines touched per lookup (exact, counted):

| scheme | hit | miss |
|---|---|---|
| linear (kraken2 -DLINEAR_PROBING) | 1.073 | 1.316 |
| double hashing (kraken2 second_hash = (h>>8)\|1) | 1.720 | 3.333 |
| line-aligned linear | 1.016 | 1.154 |

time per lookup, ns per thread, 13% misses, best of 3:

| table | T | linear | aligned | double | double + prefetch both probes |
|---|---|---|---|---|---|
| 8GB | 1 | 28.5 | 36.1 | 65.5 | 56.4 |
| 8GB | 32 | 82.5 | 72.4 | 151.0 | 130.6 |
| 32GB | 1 | 35.1 | 38.1 | 79.1 | 66.0 |
| 32GB | 32 | 49.2 | 63.6 | 125.0 | 112.1 |

findings:
1. double hashing is 1.8x to 2.5x slower than linear per lookup at T=32 and about 2.2x at T=1, even though it needs fewer probes (hit 2.17 to 1.72, miss 6.06 to 3.33). every probe lands on a new cache line, so lines per lookup go up 60% (hit) and 153% (miss), and time follows lines. prefetching both probe addresses recovers only about 10% to 15%. this settles the thesis-2 question: keep linear probing for speed.
2. line-aligned buckets cut lines per lookup by 5% (hit) and 12% (miss), but the timing shows no reliable win (faster at 8GB T=32, slower at 32GB T=32, noise level). not worth a table-format change.
3. double hashing needs a safety fix: failed_inserts was 1 at 2^26 and 2^31 (0 at 2^33). capacities of the form 2^k-1 are divisible by 3, so a step that is a multiple of 3 walks only a third of the table and the insert gave up. real kraken2 capacities are arbitrary, so the gcd(step, capacity) risk is real, not theoretical (rare: 1 key in 1.5 billion here, but a probe chain that cannot find a free cell is a silent false negative).

bug caught on the way: the first structbench run reused the high hash bits for both the start slot and the fingerprint, which made 43% of absent keys falsely match. fixed (fingerprint now uses low bits) and every number above is from the fixed version.

## verdict for this iteration

noteworthy positive speedup: none. what we do have, all measured on luna:
- a quantified upper bound (about 3% to 5% on 8GB) for any software cache or eviction policy after S19, with the reuse profile that explains why earlier cache nulls happened (reuse is real but too far apart, and lookups are only about 7% of cpu once prefetched).
- a priced answer for double hashing (1.8x to 2.5x slower lookups, keep linear) and a real silent-failure risk to fix before anyone ships it.
- a correction to our own framing: "no reuse" is false (81% repeats, 262K hot slots cover 56%).

E2 (amac) was gated on a lookup share of at least 25% (the debate's own rule). the 8GB and 16GB shares are 15% and 14% of user time, so it did not run. 103GB looks higher (about 28% of user time) but that run is dominated by database loading at T=1 and has few samples, so the next honest step is a T=32, 1.87M-read profile on 103GB before spending 3 to 4 days on amac.
