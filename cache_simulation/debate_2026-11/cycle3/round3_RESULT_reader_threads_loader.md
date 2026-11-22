# cycle 3 results (luna, 2026-11-23): reader buffer, per-thread cpu, loader threads

- 1 MiB kseq buffer instead of 16 KiB: byte-identical output, no gain, 2 to 4% slower (8 GB 7.03 -> 7.22 s, 50 MB 6.82 -> 6.98 s, 103 GB 10.68 -> 10.89 s, 5 reps, data/rd.csv). the read buffer is not the floor.
- per-thread cpu at T=48 (2 s window): all 48 threads at 65 to 102% (about 80 to 85% mean), no single saturated thread (data/td.txt). consistent with a lock whose holder rotates, or with another shared stage.
- loader thread cap 32 -> 64/96 (K2_LOADT): byte-identical, 103 GB load 3.3 -> 3.15 s, full run 10.72 -> 10.40 s (3%), nothing at 8/16 GB (data/lt.csv). near null.
- seqreader.h shows LoadBlock calls kseq_read per read inside critical(seqread) and copy_from_kseq copies header, comment, seq and quals again, so the serial section does several copies of 12.5 GB. NOT yet measured: a lock wait/hold instrumentation build (e1/src_lock) was written but did not compile (a newline inside the printf string literal at classify.cc line 499-500); fix that one line and run with K2_LOCKSTAT=1 to get wait_total and hold_total.

next: fix the instrumentation, then decide between a faster/parallel reader and the scanner rewrite (IPC 2.31, 1.3 branch misses per base, 267 instructions per base).
