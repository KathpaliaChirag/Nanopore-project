# cycle 3 round 1 agent A (ledger): time budget of the production run

build = S19 + hll guard + prefetch dedup, T=48, 1,872,777 reads, 6,036.15 Mbp, plain --report. every number below is a median re-derived from cycle2/data/*.csv and e5/*.csv. lt.csv does not exist, so load comes from the 10-read rows of e5/sweep.csv (T=32, hll build). load does not depend on T (loader is capped at 32 threads).

## 1. wall-clock budget per db (seconds)

| db | stock T32 | best T48 wall | load + tiny exit (10 reads) | rest of wall (classify + exit) | user cpu | user/(wall*48) |
|---|---|---|---|---|---|---|
| 50 MB | 8.39 | 6.87 | 0.05 | 6.82 | 237.97 | 0.722 |
| 8 GB | 8.60 | 7.04 | 0.26 | 6.78 | 214.61 | 0.635 |
| 16 GB | 10.06 | 7.41 | 0.43 | 6.98 | 244.82 | 0.688 |
| 103 GB | 19.92 | 10.74 | 3.04 | 7.70 | 271.20 | 0.526 |

sources: wall and user = stack.csv dedup_T48 and stock_T32 (3 reps, median). load = median of 3 hll 10-read rows in e5/sweep.csv. at 103 GB hll is 10.58 and dedup 10.74 in stack.csv, dedup 10.65 in the tfine rows: dedup is not a win at 103 GB T=48 (within 1.5%).

split of the 103 GB run (the only db with a big non-classify part). e5/ab_103.txt, T=32 hll, 4 reps: wall median 12.39 s, kraken2's own "processed in" median 8.78 s. so non-classify = 3.61 s = 3.04 load (10-read wall) + 0.57 exit and teardown after 1.87M reads. assuming both carry to T=48: 103 GB = load 3.04 (28%) + classify about 7.13 (66%) + exit 0.57 (5%). for 50 MB, 8 GB, 16 GB no "processed in" exists, so the post-load 6.8 to 7.0 s is classify plus an unmeasured exit, probably under 0.1 s.

phase-only efficiency (user over classify wall x 48, with load and the 0.57 exit removed at 103 GB): 50 MB 0.727, 8 GB 0.658 (6.79 s), 16 GB 0.731, 103 GB 0.793 (7.13 s). user excludes sys, so these are floors on busy time. in every db about 20 to 35% of the 48 thread-seconds is not user cpu.

stock to best: 103 GB -46% (19.92 to 10.74), 16 GB -26%, 8 GB -18%, 50 MB -18%. the thread count step 32 to 48 alone is -14.7% at 103 GB (thr.csv).

## 2. cpu-seconds budget by function (T=32 hll profile, p32_summary.txt)

caveats: the profile is T=32 and pre-dedup, there is no 50 MB profile, and the summary lists only the top 9 symbols per db. listed shares sum to 77.6% (8 GB), 73.0% (16 GB), 81.5% (103 GB). the missing 18 to 27% is not in the file (likely libc, libgomp, unresolved hex, filtered out). i converted shares to cpu-s with total = hll user / (1 - kernel share), kernel share = sum of the [k] lines: 4.1%, 5.5%, 26.0%. check: at 103 GB this gives sys = 362.5 - 268.4 = 94 s against a measured sys of 101 to 106 s in ab_103.txt, so the scale is good to about 10%.

| function | 8 GB cpu-s (share) | 16 GB | 103 GB | ns per base (8 GB) |
|---|---|---|---|---|
| NextMinimizer (scanner) | 86.4 (38.6%) | 86.2 (33.9%) | 82.8 (22.9%) | 14.3 |
| ClassifySequence (hash, resolve, fill, tree) | 48.2 (21.6%) | 50.4 (19.9%) | 50.6 (14.0%) | 8.0 |
| PrefetchIndex | 26.4 (11.8%) | 28.2 (11.1%) | 38.5 (10.6%) | 4.4 |
| GetAt (demand lookup) | 3.4 (1.5%) | 6.5 (2.6%) | 29.1 (8.0%) | 0.6 |
| kernel (all [k]) | 9.1 (4.1%) | 14.1 (5.5%) | 94.1 (26.0%) | 1.5 |
| not in the summary | about 50 | about 69 | about 67 | |

readings. (a) the scanner is about 14 ns per base on all three dbs (86, 86, 83 cpu-s), independent of table size, so it is pure compute: 40 to 50 cycles per base. (b) ClassifySequence is a flat 48 to 51 cpu-s. (c) the table-sensitive rows (PrefetchIndex, GetAt, kernel) grow from 39 cpu-s at 8 GB to 162 cpu-s at 103 GB. kernel at 103 GB is almost all load: 3.04 s x 32 loader threads is 97 cpu-s against 94 estimated. so the extra 103 GB cost is load, not steady-state lookup.
dedup check: at T=48 dedup cut user from 224.78 to 214.61 at 8 GB (-10.2 cpu-s). PrefetchIndex was 26 cpu-s, so about 20 cpu-s of it is the real first-touch stalls of the roughly 117 unique lookups per read (inference, not measured).

## 3. theoretical floors and gaps

pure-throughput floor at T=48 if user cpu stayed fixed and all 48 threads were 100% busy: user/48 = 4.96 (50 MB), 4.47 (8 GB), 5.10 (16 GB), 5.65 s (103 GB). the real classify phase is 6.8 to 7.7 s. the gap (1.8 to 2.3 s, 26 to 34% at the smaller dbs) is unexplained idle or kernel time.

scanner. a perfect 1.5 ns/base scanner = 9.1 cpu-s over 6.04 Gbp. saving at 8 GB = 86.4 - 9.1 = 77 cpu-s, 34% of cpu, which at 48 busy cores is 1.6 s. so cpu-wise the scanner is the biggest single lever, 1.6x ClassifySequence. but see section 4: at T=48 the wall does not follow cpu any more. a realistic 3 ns/base (branch-free minimizer) would save 65 cpu-s.

load. 103 GB: 3.04 s for about 111 GB = 36 GB/s with 32 threads, sys-bound (97 cpu-s). cap 32 to 64 saves about 0.1 s (3%) per the earlier test. a hard floor needs Luna's memory bandwidth, which is not measured, so no number. -M (running) is the only lever that can remove most of it, by moving the cost into page faults during classify.

exit. 0.57 s at 103 GB (5%), unmeasured elsewhere. round 4 B already corrected itself: an early _exit does not skip the kernel page free, only THP shrinks it.

reader. input is plain fastq, no gzip, memchr line scan (round3_B). size is not in any csv. estimate 2 bytes per base for seq plus qual = 12.07 GB, plus headers (1.87M x about 125 B = 0.23 GB) = about 12.3 GB (estimate). a single thread needs read() copy at 3 to 6 GB/s (2 to 4 s) plus parse and string copy (about 1 s). required rate to keep the 6.8 s classify wall: 12.3 / 6.8 = 1.8 GB/s, so a lone reader would be 30 to 60% utilised on paper: not a bottleneck by this estimate, but it becomes one once the workers are fast enough that wall falls below about 3 to 5 s. the 1.1 ns/base serial budget the data implies (section 4) is just inside that range, so it cannot be excluded.

## 4. Amdahl: what caps scaling past 48 threads

the strongest finding in this file. user cores busy (user / wall) by thread count, 50 MB, thr.csv medians:
T16 230.39/14.99 = 15.4 (96% of 16); T32 235.13/7.97 = 29.5 (92%); T48 245.07/6.75 = 36.3 (76%); T64 247.64/6.86 = 36.1 (56%); T96 250.08/7.12 = 35.1 (37%).
it plateaus at about 36 busy cores and wall stops falling at T=48.

the classify-phase wall floor (best-T wall minus load and exit) is nearly the same on all four dbs although user cpu differs 234 to 281 s and the table is 2000x larger:
50 MB 6.71 (T48, 0.05 load); 8 GB 7.21 - 0.26 = 6.95; 16 GB 7.43 to 7.61 - 0.43 = 7.0 to 7.2; 103 GB 10.40 - 3.61 = 6.79.
a db-independent floor of about 6.7 to 7.2 s says the limit is a stage that does not depend on the table: reader, ordered writer or a shared lock. in the form wall = max(cpu/T, F): at T=32, cpu/T = 7.35 for 50 MB against 7.97 measured (+8%, floor not yet binding but close); at T>=48, F of about 6.7 s binds.

second evidence: dedup's cpu gain stopped converting at T=48. T=32 (dd.csv): 50 MB -3.0%, 8 GB -4.4%, 16 GB -2.8%, 103 GB -1.6%. T=48 (stack.csv, hll to dedup): 50 MB +1.5% (6.77 to 6.87), 8 GB -3.7%, 16 GB -3.3%, 103 GB +1.5%. user cpu fell about 3% at all four. a cpu cut that does not move wall is the signature of a wall set by something that is not cpu.

serial stages ranked by suspicion (if the floor were serial it would be 6.8 s over 1.87M reads = 3.6 us per read = 1.13 ns per base = 1.8 GB/s of fastq):
1. input reader plus parse (one thread). plausible at 1.8 GB/s if parse copies each base into a std::string; unlikely for memchr alone.
2. ordered output writer (per-read file must keep input order; about 0.3 to 0.5 GB). cheap per byte, but ordering makes workers wait on one batch.
3. loader: not a cap after load (parallel, 3.04 s at 103 GB, constant in T).
4. exit: 0.57 s at 103 GB only, serial, 5%.
the non-serial alternative is hardware: 48 busy user cores out of 96 physical, and user per thread rises 6% from T32 to T96 (235 to 250 s), consistent with turbo droop or shared uncore. the thr data cannot separate a serial stage from a hardware limit. the pending perf stat (IPC) and a per-thread cpu view (pidstat -t) can.
upper bound if the floor vanished (cpu/48): 50 MB 6.87 to 4.96 (-28%), 8 GB 7.04 to 4.73 with load (-33%), 16 GB 7.41 to 5.53 (-25%), 103 GB 10.74 to 9.28 with load and exit (-14%). realistic: half of that.

## 5. ranked remaining levers (8)

| # | lever | expected wall gain | evidence that confirms it |
|---|---|---|---|
| 1 | break the serial front end (second reader thread, bigger input batch, lock-free ordered writer) | 0% if the floor is hardware; if serial, 10 to 15% at the three small dbs, 5 to 7% at 103 GB (caps 28, 33, 25, 14%) | pidstat -t or perf per thread: one thread near 100% while workers sit at 70 to 75%; fastq on /dev/shm and output to /dev/null leaves wall unchanged; a stub run (workers return immediately) still takes about 6 s |
| 2 | 103 GB load: -M mmap, 64 loader threads, or keeping the db resident across runs | 3% (cap 64), 0 to 25% (-M, depends on fault cost), 28% (resident server, changes usage model) | the pending -M run: load falls below 3.04 s and classify grows by less than the saving; vmstat sys during load |
| 3 | scanner rewrite (branch-free window minimum, or vectorised minimizers) | cpu 15 to 34% on any db (86 cpu-s now); wall 0% if lever 1 binds, up to 20% if not | the pending scanner slope test and perf stat branch-misses with IPC; microbench of NextMinimizer alone at 14 ns/base against a branch-free version |
| 4 | LTO + PGO build (scanner branch layout, inlining the fill/resolve loop) | 0 to 8% cpu, wall gated by lever 1 | one rebuild, 5 interleaved reps on 8 GB; -march=native was a null so only branch layout is expected to help |
| 5 | huge pages for the 103 GB table (PrefetchIndex 38 and GetAt 29 cpu-s at 103 GB) | 3 to 8% at 103 GB, 0% at the others | perf stat dTLB-load-misses and page-walk cycles; AnonHugePages in /proc/meminfo during classify; THP on vs off, 3 reps |
| 6 | cross-read batched dedup (54% of lookups are repeats at T=1, 81% of those at distance 1e4 to 1e6, round4 B) | 0 to 5% cpu at 103 GB, about 0% elsewhere; costs 120 to 160 MB per thread | trace of unique vs total lookups per 1e6 window at T=48; an oracle skip ceiling as in cycle 2 |
| 7 | exit teardown at 103 GB (0.57 s) | up to 5% at 103 GB only | strace -T on exit_group; THP state, since only THP shrinks the page free |
| 8 | placement: T=40 to 44, one thread per physical core, SMT off | 0 to 2% | tfine: 8 GB T40 6.92, T44 6.97, T48 7.04, T52 7.03, T56 7.13; 103 GB flat at 10.58 to 10.84 |

ranking logic: levers 1 and 2 are the only ones that can change the wall at T=48 by more than 5% on every cell, but lever 1 is a hypothesis. levers 3 and 4 are large in cpu and conditional in wall. lever 6 was already half realised by dedup.

## 6. summary

1. best build budget at T=48: 50 MB 6.87 s, 8 GB 7.04, 16 GB 7.41, 103 GB 10.74 (load 3.04, classify about 7.1, exit about 0.57); stock T32 was 8.39, 8.60, 10.06, 19.92.
2. cpu: the scanner is a flat 14 ns/base (83 to 86 cpu-s on every db), ClassifySequence 48 to 51; table work plus kernel grows 39 to 162 cpu-s from 8 GB to 103 GB, and the 103 GB kernel share is the load.
3. parallel efficiency user/(wall*48) is 0.72, 0.64, 0.69, 0.53 (classify phase alone 0.66 to 0.79); busy user cores plateau at about 36 for T>=48.
4. the classify wall floor is 6.7 to 7.2 s on all four dbs although user cpu varies 20% and table size 2000x, and dedup's 3% cpu cut gave 0% wall at 50 MB and 103 GB: a serial or hardware limit now binds, not cpu.
5. fastq is about 12.3 GB (estimate); a lone reader needs 1.8 GB/s at the current wall, plausible but it would cap wall near 3 to 5 s, so it explains 6.8 s only if parse is slower than estimated.
6. next best action: pidstat -t per-thread cpu on one 8 GB T=48 run; one saturated thread puts lever 1 first, otherwise the floor is hardware and scanner/PGO levers resume.
