# resident database via the stock classify -D daemon: not usable as shipped (luna, 2026-11-24)

goal: measure how much a resident table saves on repeated jobs (the 103 GB run spends about 3.2 s of 6.7 s loading). test harness: code/dm_daemon_test.sh and dm_daemon_test2.sh (start `classify -D` on the 103 GB database with a 10-read first job, then submit full 1.87M-read jobs over the daemon's FIFO and time each; timeout and cleanup trap).

## correction of my first note

the first attempt looked like a hang (a 10-read first job unfinished after 139 s) and I guessed an OpenMP-after-fork deadlock caused by the parallel database loader. that guess is NOT supported: the follow-up shows the same per-job cost in the stock S19 binary, so it is not a deadlock and not caused by the parallel loader.

## measurements (data/dm_A_omp1.log, data/dm_B_stock.log; T=96 requested)

| run | job 1 (10 reads, includes the table load) | job 2 (all 1.87M reads, table already resident) |
|---|---|---|
| best build (bin_pre), OMP_NUM_THREADS=1 in the daemon | 62.9 s | 152.5 s |
| stock S19 classify -D (control) | 144.7 s | 142.0 s |

jobs 3 and 4 did not log before the 420 s timebox. a fresh run of the same job is about 7 s (best build) or 11 to 20 s (stock). so in daemon mode every job costs about 140 to 150 s, for the best build AND for stock, and a resident table gives no speedup here. the cause of the per-job cost is not explained: candidates are the copy-on-write fork of a 104 GB mapping (page-table copy and page-fault behaviour when the table is on 4 KB pages: the single-thread load path allocates without MADV_HUGEPAGE), the output going through FIFOs, or process teardown. job 1 in the stock run (144.7 s) is simply the single-thread load of the 104 GB file at about 0.7 GB/s.

## what is established and what is not

established: stock -D mode as shipped does not make repeated 103 GB jobs faster (about 140 s per job here). not established: why, and whether a daemon built differently (huge-page table in the parent, output to a file instead of FIFOs, no fork) would work. no claim about resident-table speed should be made from this.

cleanup verified: no classify processes and no /tmp/classify_* FIFOs left on luna after both runs.

note: `pkill -f "classify -D"` from an ssh one-liner kills its own shell (exit 255); use pids. also: a script created with sed redirection needs chmod +x (the first diagnostic run silently did nothing for that reason).
