# resident database via the stock classify -D daemon: first attempt hangs (luna, 2026-11-24)

goal: measure how much a resident table saves on repeated jobs (the 103 GB run spends about 3.2 s of 6.7 s loading). test script: code/dm_daemon_test.sh (starts `classify -D` on the 103 GB database with a 10-read first job, then submits full 1.87M-read jobs over the daemon's FIFO and times each; the harness has a timeout and a cleanup trap).

result: the daemon loaded the table and forked its first child, but that child did not finish a 10-read job in 139 s (RSS 108 GB shared copy-on-write, no DONE line), so no timing was obtained. the test was killed and the FIFOs, processes and /dev/shm files were removed (checked: nothing left on luna).

likely cause (not yet confirmed): the build's parallel database loader (S10, an OpenMP `parallel for` with up to 32 threads) runs in the daemon PARENT before it forks; an OpenMP runtime is not safe to use in a forked child after its thread pool was created in the parent, and the child then uses OpenMP again (96 threads) and deadlocks. stock S19's loader may not use OpenMP in the parent, which would explain why -D worked there.

next steps: (a) run the same harness with K2_LOADT=1 (single-thread loader) or with OMP_WAIT_POLICY=passive to see whether the child then completes; (b) if so, a daemon-safe loader (do the parallel load in a short-lived child or via std::thread/pread without OpenMP); (c) only then time job 2 to 4 against a fresh run. nothing about resident-table speed is established yet.

also noted: `pkill -f "classify -D"` from an ssh one-liner kills its own shell (exit 255); use pids.
