# cycle 2, round 1, agent C (experimentalist): measurements that decide the best cache at production scale

read all of debate_2026-11/ first. nothing run here, no luna. every number is quoted from a round file or marked [guess] or [arith]. the one thing this plan must settle: after S19 prefetching, can any cache (per-thread, shared, static) beat a few percent of classify wall time on the 8GB and 103GB dbs at T=32 and 1.87M reads. e1/e5 so far gave: 8GB, T=1, 105k reads, lookups are 7.7% of cpu (15% of user time), GetAt under 1%, 4-way LRU at 262K = 39% hit, Belady 67%.

## 0. step 0 (half a day, gates everything): the missing lookup share

the only unmeasured input to every bound is the lookup share of classify time at T=32, 1.87M reads, on 103GB and 8GB. e1 measured T=1, 105k reads, where kernel db load dominates (65% on 103GB, only about 450 user samples).

- machine check first: `lscpu | grep -i -E "model name|cache|socket"`, `getconf -a | grep CACHE`, `free -g`, `df -h /dev/shm`, `cat /sys/kernel/mm/transparent_hugepage/enabled`, `cat /proc/sys/kernel/perf_event_paranoid`, `uptime`. record all in the log. need the real L2 per core (guess 2 MB, Sapphire Rapids) and L3 per socket (105 MB, from the repo).
- profile: stock S19 binary, T=32, all 1.87M reads, `perf record -F 499 -g --delay <ms after db load> -o /dev/shm/c2_prof.data`, then `perf report --no-children --sort symbol`. report PrefetchIndex + GetAt + the compact-hash probe as share of user samples and of classify wall time. repeat for 8GB. the delay is chosen from the time stamp the kraken2 log prints when loading ends.
- derive Td_eff = (lookup share of user time x classify seconds x T) / (lookups). this is the exposed ns per lookup that a hit can save. it replaces the 90 ns dram number everywhere (round 4 flaw 1).
- gate: if lookup share of user time at 103GB T=32 is under 10%, no cache can win above 3% and the cache question closes as a bounded negative. skip sections 2 and 3 and write that up.

## 1. production-scale trace and offline analyzer

### 1a. what is recorded (tracer v2, extends e1/tracer_patch.diff)

e1 logs `pf[i].idx | hit<<63` per lookup. keep the 8 byte record but use the free bits so the key is nearly exact: bits 0..35 slot index (capacity under 2^36), bits 36..62 a 27-bit fingerprint of the full hash hc (hc >> 37), bit 63 hit. this removes the start-slot collision error that e1 has (two different k-mers sharing a start slot count as a repeat; about 1% of 100M unique keys at 8.6e9 cells [arith]). the 27-bit fingerprint plus idx gives roughly 63 bits of identity.
- timestamp records for the merged order: once per batch (B=16) write one extra 8 byte record `1<<62 | (rdtsc & (2^62-1))` before the batch. invariant tsc is synchronised across cores on this class of xeon (verify with `grep -o constant_tsc /proc/cpuinfo | head -1` and `nonstop_tsc`). one run then gives both per-thread streams (the files) and the merged stream (k-way merge of the files by timestamp). cost is 1/16 more records and one rdtsc per batch, under 1% overhead [guess, e1 tracer was 3%].
- per-thread files `K2_TRACE=/dev/shm/c2_<db>_<A|B>` gives `_<tid>.bin` like e1. check that exactly 32 worker files appear (the reader thread must not trace).
- training records (separate env `K2_TRAIN=path`, run A of each db only): 16 bytes per lookup, `hc` (full 64-bit hash, MurmurHash3 finalizer is a bijection so hc identifies the minimizer exactly) and the exact value returned by GetAt (4 bytes, plus 4 bytes pad). used only to build the hot set in section 2.

### 1b. runs and budget

lookups per read at 8GB: 12,237,762 / 104,918 = 116.6 [arith]. at 1.87M reads: about 218M lookups [arith]. the older M5 figure is 351.8M for some run of the full set. size the budget for the larger number.

| item | lookups | bytes |
|---|---|---|
| one half (A or B, 936k reads), 8B + 1/16 ts | 109M (176M if M5 is right) | 0.93 GB (1.5 GB) |
| both halves, one db | 218M (352M) | 1.86 GB (3.0 GB) |
| train records, run A only, 16 B | 109M (176M) | 1.75 GB (2.8 GB) |
| per db total | | 3.6 GB (5.8 GB) |

runs, in this order, T=32, flags as S19 standard, `--output` to /dev/null for the trace runs (trace overhead measured against a stock run with the same flags):
1. 8GB, half A with K2_TRACE and K2_TRAIN. 2. 8GB, half B with K2_TRACE. 3. the same two runs for 103GB.
halves are disjoint file ranges of the 1.87M reads, split by file (or by read index, first 936,388 reads vs rest). the full-run trace is A then B per thread and merged by timestamp (B starts after A ends, tsc is monotone). this avoids a third run and gives the held-out split for free.
memory: shm must hold one db's 3.6 to 5.8 GB at a time; delete the db's files after its analysis. analyzer RAM about 10 to 14 GB [arith, see 1c]. if `df /dev/shm` shows under 8 GB free, run per-thread files one at a time and skip the merged analysis for the large trace (use SHARDS, see 1c). never write to the 99% full disk. also run one T=1 trace on the first 3M lookups of 8GB to confirm the tracer v2 reproduces e1's table (repeat 81.4%, top-262K 55.8%) before trusting the new numbers.

### 1c. analyzer (new file e1/analyze2.cpp, built on luna with g++ -O2 -std=c++17, streams from /dev/shm)

e1/analyze.cpp keeps `unordered_map` of all uniques and a `set` Belady; at 218M lookups and about 100M uniques that is 15+ GB and slow. changes:
- pass 1: radix-sort the (key, position) pairs to give every key a dense uint32 id (1.75 GB sort buffer). then `ids[]` (0.9 GB), `nxt[]` uint32 next-use positions (0.9 GB), stack distance `sd[]` uint32 (0.9 GB), Fenwick `bit[]` int (0.9 GB). total about 5 GB for the merged trace [arith].
- Belady with a binary heap and lazy deletion on `nxt` (not std::set), bypass never-reused keys like e1.
- SHARDS fallback: keep keys with hash(key) mod 64 == 0, scale distances by 64, to cross-check the exact numbers on the largest stream.
- every policy is reported at entry counts N in {16K, 64K, 256K, 1M} (the section 2 sizes), and 4M as an upper reference, in three scopes:
  - per-thread: each of the 32 files replayed alone, report median, min, max over threads (this is the real design, the thread-local cache sees only its own reads).
  - shared: the merged stream, one structure of N entries.
  - equal total memory: per-thread N vs shared 32 x N, so a per-thread cache is not unfairly compared with a shared one 32 times smaller.
- policies: fully associative LRU (stack distance), 4-way LRU (e1 hash mix), 4-way with the real S19 set index function if reachable, W-TinyLFU style admission (1% window LRU, main segment LRU, 4-bit count-min sketch with 4 rows, sketch size 8N counters, doorkeeper bloom of 8N bits, halve all counters every 10N lookups, admit candidate only if its estimate exceeds the victim's), static top-K, Belady.
- static top-K, three variants, all with K = N:
  - in-sample (train = test), an upper bound for static.
  - held-out: counts from half A, evaluated on half B, and counts from B evaluated on A. report the gap to in-sample.
  - cross-sample if a second basecalled sample exists in ~/chirag_K/data/basecalled (different run/barcode): train on A, test on it. same db for both, otherwise slot ids differ.
  the key for static is the full (idx, fp) identity, the real build uses hc.
- also report: hit share of lookups per hit class (key present in db vs absent) for the static set, windowed dedup at W = 1e6 and 1e7 (needs the merged stream), and the share of lookups after which the same line is touched within 8 lookups (batch-local line sharing).
- output table per db: policy x N x scope, then the gain bound G = h x s_user (section 3). the 4 tables (2 dbs x scope) are the deliverable. run time: per-thread files seconds each, merged Belady about 10 to 30 minutes [guess].

decision rule from the trace alone (before any build): proceed to section 2 only if held-out static hit rate at N = 320K entries (4 MB) is at least 25% on 103GB or 8GB, and s_user x h gives G of at least 4%. per-thread caches are dead if per-thread Belady at 64K is under 20% (round 4 rule, reused). shared-vs-per-thread gap larger than 2x means a shared read-only structure is the right design, which is what section 2 builds.

## 2. minimal real-build experiment: read-only static front table

why this and not a dynamic cache: it has no writes, so one copy serves all 32 threads with no coherence traffic, no per-thread init and no eviction logic. it is the cheapest honest test of "does a small resident table in front of the big one pay". a dynamic policy only matters if the static held-out hit rate is far below LRU/TinyLFU shared hit rate in 1c.

### layout (exact)

one 64-byte line per set, 5 ways, line aligned, 2 MB hugepage backed (`madvise(MADV_HUGEPAGE)` like S14):
- bytes 0..39: five 8-byte keys, the full 64-bit hc (0 means empty, hot-set builder drops hc == 0).
- bytes 40..59: five 4-byte values, the exact value GetAt returns for that hc (0 for hot absent keys, cached too).
- bytes 60..63: pad.
exact because the real table is a pure function of hc: a match returns what GetAt would return. this is what keeps output byte-identical by construction, including 32-bit cell false-positive behaviour.
- set index: `((hc >> 32) * nsets) >> 32` (high bits, independent of the low bits used by the big table's `hc % capacity`). the builder places the entries by descending frequency into the first free way, and drops entries whose set is already full (report the dropped share, expected few percent at load 0.8).
- probe: load the line, compare 5 keys (scalar loop, or AVX2 `cmpeq_epi64` on keys 0..3 plus scalar key 4), return value on match.
- sizes tried (entries are 5 per line, fill 80%):

| name | lines | MB | resident in | entries filled |
|---|---|---|---|---|
| F1 | 16,384 | 1 | L2 (half of an assumed 2 MB) | about 66K |
| F2 | 65,536 | 4 | L3 (spills L2) | about 262K |
| F3 | 262,144 | 16 | L3 | about 1.05M |
| F0 | 0 | 0 | none (loaded but empty) | overhead control |

bigger than 16 MB is pointless: at T=32 the cores' L3 is 105 MB per socket shared with the 100+ GB table's own lines (round 3 B counts 105 MB/socket as budget). 262K entries cover 55.8% in-sample at 8GB, 1M cover 90% (e1) [quoted], so F2 and F3 are the interesting rows; F1 is the L2-resident row (about 24% to 28% in-sample).

### hot-set builder (offline, same analyzer binary, mode `--build-hot`)

input: the K2_TRAIN file from run A of that db, output `hot_<db>_<F>.bin` (header with nsets, then the lines). training on A, testing the build on B-only reads is the held-out build test. also build one in-sample variant (train on the same reads as run) as the ceiling. one file per db and size, a few MB, kept in ~/e1/ not shm.

### hook points in S19 (copy to ~/e1/s19_front, never touch ~/chirag_K/tools/kraken2-src-s19)

- startup: `K2_HOT=path` env, loaded once into an aligned hugepage array, global `const uint8_t* g_front`, `g_nsets`. unset or empty means the stock path (a pure early `if`).
- v0 (cheap, tests identity plumbing only): in the batch loop at the same place e1 put the tracer (right after `taxon = hash->GetAt(...)`, tracer_patch.diff hunk near line 859), compute the set from the already available hc and probe the front table first; on hit use its value and skip `GetAt`. the big-table prefetch is still issued. expected gain about zero (GetAt is under 1%); its job is the byte-identity harness and the overhead baseline.
- v1 (the real test): deepen the existing S16 pipeline from 2 stages to 3. per batch i: (a) scan minimizers of batch i+2, compute hc, `__builtin_prefetch(front_line(hc))`; (b) for batch i+1, probe the front line (now in cache); on hit store the value and mark the slot done; on miss call `hash->PrefetchIndex` for the big table; (c) for batch i, `GetAt` only the not-done slots. keep B=16 (round 4 C also wants a B sweep, run F2 at B = 8, 16, 32 as a side check). hits no longer issue big-table prefetches, which is where DRAM traffic and L3 pollution are saved. this needs `PrefetchIndex` to return hc or the code to call the existing hash function once and store it in the pf[] struct next to idx.
- both versions behind `K2_HOT`; same binary with `K2_HOT` unset must equal stock S19 in time (within noise floor of section 3), which also checks that the extra branch costs nothing.

### byte-identity check

for every (db, F, version, thread count in {1, 32}) cell: `cmp` the per-read `--output` file against stock S19 on all 1.87M reads, and `sort | cmp` the reports (tie order of siblings may differ, documented in round 6; compare after sort). any difference kills the variant until explained. also run F2 on 10, 1,000 and 104,918 reads to catch small-input paths.

### expected gain bounds (bounds, not predictions)

gain on classify ~ s x (h - Tf / Td), where s = lookup share of user time, h = front hit rate on lookups, Tf = exposed cost of the front probe, Td = exposed cost of a big-table lookup (Td_eff from step 0). reference numbers: structbench linear lookup 28.5 ns (T=1) and 82.5 ns (T=32) at 8GB, 35 and 49 ns at 32GB [quoted]. Tf [guess]: 4 ns F1, 10 ns F2 (L3 hit, partly hidden by the prefetch of stage a), 20 ns F3. s: 0.15 of user time at 8GB (e1), 0.28 at 103GB (rough, 450 samples), both to be replaced by step 0.

| size | h in-sample (e1, 8GB, 105k reads) | h held-out [guess x0.8] | Tf/Td at Td = 49 ns | bound at s = 0.15 | bound at s = 0.28 |
|---|---|---|---|---|---|
| F1 66K | about 0.26 | 0.21 | 0.08 | 2.0% | 3.6% |
| F2 262K | 0.56 | 0.45 | 0.20 | 3.8% | 7.0% |
| F3 1.05M | 0.90 | 0.72 | 0.41 | 4.7% | 8.7% |

these use 105k-read coverage; at 1.87M reads more distinct keys appear so in-sample coverage at fixed K drops, the real h comes from 1c. conclusion before running: the achievable win is a few percent at 8GB and at most about 7 to 9% at 103GB, and F2 is the likely best size. gain needs h above Tf/Td, which is 8% to 41% depending on size.

## 3. measurement protocol and kill criteria

### protocol

- one session per comparison (the same binary varied 23% between 2026-09-24 and 2026-10-21, round 4 C), machine quiet-ish: log `uptime` and `cat /proc/loadavg` before and after every rep and drop reps where load average rose by more than 8 over the session baseline [guess], rerun them at the end.
- binaries compared: S19 stock, S19 + K2_HOT unset (check), v1 F0, v1 F1, v1 F2, v1 F3 (and v0 F2). a run list is generated as a shuffled-block design: reps in blocks, order of binaries re-randomised each block so drift does not align with a variant.
- cells: db in {103GB, 8GB}, T in {32, 64} (64 is S0's best, round 4 C; add T=1 on 8GB only), 1.87M reads, `--output /dev/null` for timing and the real output file in a separate identity run, `--report` as in S19 plain form (the hll guard from e5 is on in S19; keep the same flag set for all binaries).
- 7 reps per binary per cell, report the median and the paired ratio per block (variant / stock inside the same block), then the median of ratios with min and max. wall time of the classify phase from the kraken2 log, not process wall time (db load is 65% of a 103GB run).
- noise floor: 7 interleaved A/A reps (stock vs stock copy, a byte-identical second build) per cell. floor = max(1%, 2 x the half-range of the median ratio). e5's sweep and the thp band (13 to 21 s at 103GB, round 4) mean the 103GB floor may reach 3% or more; if it does, increase to 11 reps and warm the page cache by one discard run per cell.
- counters (separate reps from timing, 3 per binary, `perf stat -e` without root on the process only): `cycles,instructions,LLC-loads,LLC-load-misses,dTLB-load-misses,dtlb_load_misses.walk_completed`, plus if `perf list` offers them `mem_load_retired.l2_miss,mem_load_retired.l3_miss,cycle_activity.stalls_l3_miss,mem_inst_retired.all_loads`. the hypothesis to confirm is mechanism, not just time: v1 F2 must cut big-table L3 misses by roughly h x lookups. if time moves but misses do not, it is noise or a layout side effect. compute misses per lookup for each variant.
- keep: the raw log of every rep (time, load, binary, order index) in ~/e1/c2/runs.csv and copy the csv back to cache_simulation/debate_2026-11/cycle2/ after the session.

### kill criteria (numbers fixed now)

1. step 0: lookup share of user time at T=32, 103GB under 10% means no cache build. close as bounded negative.
2. trace stage (section 1): held-out static h at 262K entries under 25% on both dbs, or G = h x s under 4%, means no front-table build. write up the Belady and policy tables as the result.
3. per-thread dynamic caches: per-thread Belady at 64K under 20% at T=32 means drop all per-thread designs (including the existing 4-way) from the paper's positive claims.
4. build stage: v1 at 103GB T=32 shows under 3% median speedup, or the gain is under 2 x the A/A noise floor, means stop. 8GB is allowed to be flat but must not lose more than 1% (a loss of more than 1% on 8GB at F1 is a design bug: investigate the probe cost before dropping).
5. any byte difference in `--output` is an immediate fail of that variant.
6. hit-rate gap: if measured h from perf counters is under half the trace-predicted h, the trace identity (idx+fp) or the hot-set build is wrong; fix before drawing any conclusion.
7. promote to a dynamic-policy study (TinyLFU in front) only if the shared TinyLFU h at the best size beats held-out static h by at least 10 points and v1 F2 already gave at least 3%.

### order of work and cost

step 0 half a day, tracer v2 + 4 trace runs + analyzer 1.5 days, hot-set builder and v0 half a day, v1 and identity checks 1.5 days, measurement 1 day. a single negative at any stage stops the chain, each stage's output is publishable on its own (policy bound tables, then built-and-measured null or win).

## summary (8 lines)

1. step 0 first: perf-profile stock S19 at T=32, 1.87M reads on 103GB and 8GB; if lookups are under 10% of user time, all cache work closes as a bounded negative.
2. trace v2 packs slot (36 bits) + 27-bit fingerprint + hit bit in 8 bytes, rdtsc per batch gives the merged order, so one T=32 run gives per-thread and shared streams.
3. budget: about 218M lookups (352M worst case), 1.9 to 3 GB per db for traces plus 1.75 to 2.8 GB training file, all in /dev/shm, deleted per db, analyzer about 10 to 14 GB RAM.
4. analyzer replays LRU, 4-way, W-TinyLFU, static top-K (in-sample, held-out A to B, cross-sample) and Belady at 16K/64K/256K/1M entries, per-thread, shared and equal-total-memory.
5. real build: read-only 5-way, 64 B line table of exact (hc, value) pairs, 1 MB / 4 MB / 16 MB, hugepages, one shared copy; v1 adds a third pipeline stage so a hit also skips the big-table prefetch; byte-identical by construction and checked by cmp.
6. gain bound is s x (h - Tf/Td): about 2 to 5% at 8GB and 4 to 9% at 103GB, F2 (4 MB) the likely best; the true Td_eff comes from step 0.
7. protocol: shuffled-block interleaved reps (7, or 11 if noisy), paired medians, A/A noise floor, separate perf stat reps for L2/L3/dTLB misses to confirm mechanism.
8. kill: under 3% at 103GB T=32 or under 2x noise floor, any output diff, held-out static h under 25% at 262K entries, or per-thread Belady at 64K under 20%.
