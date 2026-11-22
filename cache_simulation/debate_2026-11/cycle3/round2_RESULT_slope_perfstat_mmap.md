# cycle 3 evidence (luna, 2026-11-23): scanner slope test, perf stat, -M comparison

all on the best build so far (S19 + HLL guard + prefetch dedup), all 1,872,777 reads, T=48, plain --report. raw: data/slope.csv, data/pstat.txt, data/mm.csv.

## 1. scanner slope test: the scanner is about half the cpu, but not the wall

variant bin_slope (e1/src_slope): K2_EXTRA=N runs N extra, discarded NextMinimizer passes over every sequence before the real one.

| db | extra passes | wall s (3 reps) | user cpu s |
|---|---|---|---|
| 8 GB | 0 | 6.99 7.02 7.08 | 214 |
| 8 GB | 1 | 7.52 7.53 7.49 | 316 |
| 8 GB | 2 | 9.63 9.65 9.60 | 420 |
| 103 GB | 0 | 10.76 10.74 10.66 | n/a |
| 103 GB | 1 | 11.90 11.87 11.79 | n/a |
| 103 GB | 2 | 14.25 14.07 14.09 | n/a |

- one extra pass adds about 102 cpu-s and the second about 104 cpu-s at 8 GB, so a single scan pass is about 48% of the 214 cpu-s total. perf samples said 38%.
- the wall does not follow: the first pass adds only 0.5 s, the second 2.1 s. at T=48 the threads have slack (parallel efficiency 0.64 at 8 GB, so about 36% of thread time is idle), and the first pass fits into that slack. the wall is set by something other than cpu at about 7 s. a faster scanner will not shorten the wall until that floor moves.

## 2. perf stat of the best build, 8 GB and 103 GB, full reads and 10 reads (the 10-read run is the load-only baseline)

| run | cycles | instructions | IPC | branches | branch-misses | miss rate |
|---|---|---|---|---|---|---|
| 8 GB full | 6.99e11 | 1.615e12 | 2.31 | 2.83e11 | 7.87e9 | 2.78% |
| 103 GB full | 1.173e12 | 1.870e12 | 1.59 | 3.36e11 | 8.79e9 | 2.61% |
| 8 GB, 10 reads | 2.12e10 | 1.62e8 | 0.08 | 3.4e7 | 1.4e6 | 0.40% |
| 103 GB, 10 reads | 3.05e11 | 2.03e9 | 0.07 | 4.0e8 | 5.2e7 | 0.13% |

per base (6.04e9 bases, the load-only rows are negligible next to the full runs): 8 GB: 267 instructions, 116 cycles (across all threads), 1.30 branch misses. at roughly 15 to 20 cycles each, mispredicts take 17% to 22% of all cycles at 8 GB. IPC 2.31 means the code is instruction-bound, not memory-bound: 267 instructions per base is far more than a sliding-window minimum needs (the SimdMinimizers literature quotes about 1.6 ns per base in total). so the scanner rewrite has both an instruction-count and a branch-miss target. at 103 GB IPC falls to 1.59 because of the memory stalls the 8 GB run does not have.

## 3. -M (memory-mapping) vs copy-load: a net loss at 103 GB, equal elsewhere (byte-identical output in all three)

| db | load-only (10 reads), copy | load-only, mmap | full run, copy | full run, mmap |
|---|---|---|---|---|
| 8 GB | 0.31 s | 0.11 s | 7.28 s | 7.32 s |
| 16 GB | 0.55 s | 0.17 s | 7.56 s | 7.60 s |
| 103 GB | 3.51 s | 0.75 s | 10.46 s | 12.63 s |

mapping removes 2.8 s of load at 103 GB but file-backed pages are 4 KB, so the classification phase pays about 4.9 s in extra TLB misses. net +2.2 s. a file-mapped database cannot get huge pages here, so -M stays a null for S19.

## what this implies

wall = max(cpu / threads, serial front-end floor). cpu / 48 at 8 GB is about 214 / 48 = 4.5 s while the wall is 7.0 s, so about 2.5 s is floor. the next experiments are the reader (1 MiB kseq buffer, queued) and a per-thread cpu snapshot (queued) to see whether one thread is saturated. only after the floor moves will the scanner rewrite (fewer instructions and fewer mispredicts) turn into wall time.
