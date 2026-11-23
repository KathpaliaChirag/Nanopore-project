# cycle 4 round 1, agent A: the remaining fixed costs (luna, 2026-11-23, read-only research)

sources read: cycle3 round6/7/8 results, data/lt.csv, mm.csv, pr.csv, hi.csv, round2 and round3 results; on luna (read-only) ~/e1/src_best/src/classify.cc, compact_hash.cc, mmap_file.cc, taxonomy.cc, /sys/kernel/mm/transparent_hugepage/*, /proc/vmstat, /proc/meminfo, /proc/buddyinfo, /boot/config-6.8.0-78-generic. nothing was run.

## 0. three findings that change the question

1. the "2.0 s floor" on small databases is not a fixed cost. user cpu is about 150 s no matter the thread count (pr.csv: 150.4 at T=32, 151.6 at T=48; hi.csv: 155 at T=96). 155 cpu-s on 96 physical cores is 1.6 s. the run is compute-bound on the 96 physical cores; T=128..192 only add SMT siblings (user cpu rises to 188 then 216 s, wall stays 2.0 to 2.1 s). the true fixed part is small: the -M 10-read run is 0.11 s total at 8 GB (mm.csv), so startup + taxonomy + mmap + exit is at most about 0.1 s.
2. scaling efficiency at 50 MB is 150 / (wall x T): T=32 94%, T=48 90%, T=64 86%, T=96 75%. the 25% lost at T=96 is about 0.5 s. candidates are tail imbalance, all-core clock drop, other users' jobs on the shared machine, kernel pread copy time, and the 0.1 s fixed part. only the first and the last are in our control and together they are about 0.1 to 0.2 s.
3. _exit does not remove the teardown of a 104 GB table. free() of the posix_memalign block is a munmap; skipping it only moves the same page freeing into the kernel's exit_mmap, which runs before the parent's wait() returns. the saving from _exit alone is the user-space destructors (a few ms). only parallelising or deferring the teardown can win.

## 1. the 103 GB load: why about 32 GB/s

arithmetic: 104 GB / 3.2 s = 32.5 GB/s. the same rate holds at 8 GB (0.27 s) and 16 GB (0.5 s), so it is a per-byte cost, not a one-off reclaim stall. the code (compact_hash.cc): posix_memalign 2 MB aligned + madvise(MADV_HUGEPAGE), then 32 threads (cap) each pread 64 MB chunks straight into the unpopulated buffer, so every 2 MB of destination is a THP fault inside the copy.

the key datum is sys cpu (lt.csv, 103 GB 10-read): 91 cpu-s at T=32, 134 at 48, 173 at 64, 270 at 96, 350 at 128, 610 at 192, while wall stays 3.2, 3.2, 3.1, 3.3, 3.2, 3.7 s. so the throughput is capped by one shared resource and extra threads only stall in it. a plain page-cache-to-user copy costs about 0.1 cpu-s per GB and zeroing about 0.1, but the observed cost is 0.9 cpu-s per GB at T=32 (91 / 104) and 3.4 at T=128, so the kernel is stalled, either on memory traffic or on a lock.

traffic arithmetic: read page cache 104 GB, zero 104 GB (clear_huge_page), write the copy 104 GB, about 312 GB in 3.2 s = 98 GB/s. two Xeon Platinum 8468 sockets (8 channels DDR5 each) peak near 600 GB/s, so a pure bandwidth cap is possible only if source pages sit on the other socket (UPI) or other tenants share the bus; it is not obviously the limit.

evidence for the allocator/reclaim path on this machine (read from /proc/vmstat, since boot): allocstall_movable 774,213, compact_stall 1,460,169 with compact_fail 1,365,311 (93.5% of compaction stalls fail), pgmigrate_success 2.2e9, thp_fault_alloc 34.8M, thp_fault_fallback only 31k. meminfo: Cached 318 GB, MemFree swung 87 to 160 GB within one minute (other users), node 1 free only 31 GB at one sample. a 104 GB hugepage allocation therefore competes with page cache and other tenants and takes direct compaction on a fraction of faults. defrag=madvise (our MADV_HUGEPAGE opts into direct reclaim and compaction). also CONFIG_INIT_ON_ALLOC_DEFAULT_ON=y, no READ_ONLY_THP_FOR_FS, shmem_enabled=never, HugePages_Total=0, khugepaged defrag=1 (not tunable without root).

page-cache read side: every parallel pread of the same file hits folio_mark_accessed on 25M 4 KB folios; the activate batches take the lruvec lock for the whole node. this is a known multi-reader contention point; I did not verify it here (hypothesis).

### ideas, ranked by what they could save at 103 GB (load about 3.2 s of 7.0 s)

| # | idea | expected saving | output risk | effort | time-only test first |
|---|---|---|---|---|---|
| L1 | diagnose first: perf record -a -g during the 10-read 103 GB run, plus /proc/vmstat deltas (compact_stall, allocstall, thp_fault_fallback) before and after | 0 by itself, picks the fix | none | 1 h | perf symbols: queued_spin_lock_slowpath callers, clear_huge_page, copy_user, compact_zone shares |
| L2 | overlap scanning with the load (stage 1: read + scan + hash all reads into a minimizer store while the 32 loader threads run; stage 2: lookups after the load) | slope test: one scan pass = 48% of 214 cpu-s at 8 GB; with bulk scanner and reader about 60% of the 155 user cpu-s is scan+parse = 90 cpu-s / 160 idle logical cpus = 0.6 s if memory bandwidth is not the shared cap; realistic 0.4 to 0.8 s of 7.0 s (6 to 11%) at 103 GB, at most 0.3 s at 8 GB | none if lookups run after load and per-read output order is kept; storage about 2e9 minimizers x 8 B = 16 GB at density 1/3 (w=5), less after dedup | 25 to 40 h | run the scanner alone (bin_slope style) concurrently with a load10 run; does load wall grow beyond 3.2 s? |
| L3 | persistent database via the existing -D daemon (classify.cc ClassifyDaemon: loads the index once, forks one child per job, children share the table copy-on-write and only read it) | whole 3.2 s load plus about 0.4 s teardown per job after the first; zero for a one-shot run | none (same classify() path in the child), but the child uses fifos for stdin/stdout so a driver script is needed | 4 to 8 h | start -D on 8 GB, time two sequential jobs: job 2 should be classify only; check fork cost of a 104 GB table (about 52k pmd entries, expect tens of ms) |
| L4 | parallel pre-population with MADV_POPULATE_WRITE (kernel 6.8 supports it) then pread | predicted null to slightly negative: the fault inside copy_to_user already runs in 32 threads, and clear_huge_page leaves the 2 MB hot in L2 (SPR L2 is 2 MB per core) for the copy; a separate populate pass loses that and adds DRAM traffic | none | 1 h | time populate-only and copy-only separately in a C microbench; if populate alone is already 2.5 s then zeroing+allocation dominates; if under 1 s it will not help |
| L5 | sweep loader threads below 32 and pin them one per physical core (OMP_PLACES=cores) | 0 to 0.2 s; lt.csv shows no gain from more threads, so fewer may lose nothing and cut the sys-time waste on a shared machine | none | 0.5 h | K2_LOADT=8,16,24,32 on 103 GB load10, 3 reps |
| L6 | MPOL_INTERLEAVE or per-node mbind of halves of the table | null or worse; the earlier numa test already showed interleave worse; lookups are random so placement cannot match thread nodes | none | 1 h | skip |
| L7 | O_DIRECT / splice / bigger preads / io_uring | none: O_DIRECT bypasses the page cache and reads the disk (104 GB at SSD speed is 10+ s); splice and buffered io_uring still copy page by page; 64 MB preads already amortise syscalls | none | n/a | rejected |
| L8 | file THP so a mapping needs no copy (MADV_COLLAPSE on the mmap'd file) | would turn 3.2 s into about 0.75 s | none | n/a | rejected: CONFIG_READ_ONLY_THP_FOR_FS is not set here and file MADV_COLLAPSE needs it (patch notes: https://spinics.net/lists/linux-api/msg52936.html; the removal series is 2026 work, not in 6.8); shmem_enabled=never and an empty hugetlb pool rule out tmpfs and memfd-hugetlb without root |
| L9 | vmtouch / page-cache pinning | none for load speed (file is already cached); only protects against eviction by other tenants | none | 0.5 h | not a speed idea; useful to keep runs comparable |
| L10 | table-chunk-ordered lookups so queries start before the load ends | rejected: the table uses double hashing (second_hash jumps anywhere), so a probe is not local to a 64 MB chunk | n/a | n/a | rejected |

note on the shared state: MemFree moved 87 to 160 GB in one minute while I read; 65 users share this box. any load-time test must record MemFree, thp_fault_fallback and compact_stall before and after, or a 3.2 s result cannot be told from a reclaim lottery.

## 2. process exit

what is known: the e5 split at T=32 (hll build, 103 GB): wall 12.39 s, kraken2's own "processed in" 8.78 s, 10-read wall 3.04 s, so non-classify is 3.61 s and the part beyond a 10-read run is 0.57 s. that 0.57 s is the best measurement of "exit after a real run". the 10-read wall (3.04 to 3.2 s) already contains one full free() of 104 GB, so the load alone is less than 3.2 s; the split is not measured.

code facts (main(): load_index, classify(), delete CompactHashTable, return): the report is written inside classify() (ReportKrakenStyle with a local ofstream that closes on return) before the delete, and ProcessFiles flushes every output stream. so a flush then _exit(0) after classify() is byte-identical for stdout, -o and the report. but see finding 3: it saves only user-space destructors.

| # | idea | expected saving | risk | effort | test first |
|---|---|---|---|---|---|
| X1 | stderr timestamps (env K2_TIMING): after load_index, after classify, after report, after delete, compared with external wall | 0, but turns the unmeasured 0.57 s into numbers | none (stderr, off by default) | 0.5 h | do it first |
| X2 | parallel teardown: before the free, 32 to 64 threads each madvise(MADV_DONTNEED) a 1 GB slice (mmap_lock read side, so it scales; munmap holds it for write), then free | teardown of 52k hugepages is struct-page work, about 5 to 10 us per 2 MB single-threaded, so 0.25 to 0.5 s; a 5 to 10x cut saves 0.2 to 0.4 s at 103 GB (3 to 6%), about 0.02 s at 8 GB | none after the report is written | 2 h | time free() alone in the X1 build, then with the parallel DONTNEED loop |
| X3 | _exit after flush | about 0.01 s (destructors only); free cost just moves to exit_mmap | none if cout, cerr, the report and -o files are flushed first (they are) | 0.5 h | include in the X1 build |
| X4 | fork and let the child outlive the parent so its exit does the teardown | hides 0.2 to 0.57 s from measured wall but the cpu work still happens in the background | none for bytes; changes what "wall" means, so disclose it; not for headline numbers | 3 h | not recommended |

## 3. the small-database floor (50 MB, 8 GB: about 2.05 s)

budget at T=96, 50 MB: wall 2.09 s; compute 155 user cpu-s / 96 cores = 1.61 s; pread copy of the 12.5 GB input is a few cpu-s (0.03 to 0.1 s); fixed part at most 0.1 s; the rest (0.2 to 0.3 s) is tail, clock and neighbours.

| candidate | cost | evidence |
|---|---|---|
| process start, taxonomy (taxo.k2d), mmap/open | under 0.1 s | -M 10-read run is 0.11 s at 8 GB (mm.csv) |
| OpenMP thread creation | about 128 x 50 us = 6 ms | negligible |
| ordered output writer | not on the critical path: 1.87M lines to /dev/null under a lock, workers hand blocks over | 8 GB wall equals 50 MB wall (2.07 vs 2.04 s); the 0.3 s 8 GB load barely shows, because 8 GB lookups cost more and 50 MB lookups cost less, so the two differences roughly cancel |
| final report | 383 KB, under 5 ms | |
| tail imbalance | 4 MiB chunks, 2998 chunks, 23 per thread at T=128: one chunk is 2.04 s / 23 = 0.09 s, expected loss half of that (0.04 s), up to 0.09 s | round 7 already tested 1 MiB chunks for byte identity (11,968 chunks) |
| SMT and clock | T=128..192 adds user cpu 188 to 216 s for no wall gain | the 96 physical cores are saturated |

| # | idea | expected saving | risk | effort | test |
|---|---|---|---|---|---|
| F1 | chunk size 1 or 2 MiB instead of 4 MiB | 0.03 to 0.07 s (1.5 to 3%) | none (byte-identity already shown at 1 MiB, 64 KiB, 4 KiB) | 0.5 h | chunk-size env at 1 and 2 MiB, T=96/128, 50 MB, 5 interleaved reps |
| F2 | OMP_PLACES=cores OMP_PROC_BIND=spread at T=96 (one thread per physical core, no sibling doubling while other cores idle) | 0 to 0.2 s; unpinned T=96 is at 75% efficiency vs 94% at T=32, part may be sibling collisions | none | 0.5 h | pinned vs unpinned T=96, 5 reps, also T=88 to leave room for neighbours |
| F3 | measure the fixed part: 10 reads on 50 MB, plus 25% and 50% of the reads (head -n 4N), fit wall = a + b x reads | 0, says whether anything is left to chase | none | 1 h | do before any small-DB work |
| F4 | lower cpu per base: 155 cpu-s / 6.04e9 bases = 26 ns per base, still far above the 1.6 ns per base SIMD minimizer literature figure | each 10% off user cpu is about 0.16 s at T=96 | exactness harness exists (mmcmp.cc) | 20+ h | outside "fixed costs"; named so it is not forgotten |

## 4. summary

1. the small-database 2 s is compute on 96 saturated physical cores (155 cpu-s / 96 = 1.6 s), not a fixed floor; real fixed costs total under 0.1 s.
2. the 103 GB load runs at 32 GB/s with sys cpu growing 4x while wall stays flat: a shared bottleneck (memory traffic, reclaim/compaction on a box with a 93% compaction-fail rate, or the lruvec lock), not missing parallelism; diagnose with perf before building anything.
3. _exit alone saves nothing for the 104 GB table; parallel MADV_DONTNEED teardown might save 0.2 to 0.4 s.
4. file-THP mapping (the route to a 0.75 s load with huge pages) is blocked: CONFIG_READ_ONLY_THP_FOR_FS is off and there is no root.
5. the only large structural wins left at 103 GB are overlapping scan with load (0.4 to 0.8 s, 25 to 40 h) and a resident daemon (3.6 s per job after the first, 4 to 8 h, half-built in stock -D).
6. the cheap items (F1, F2, L5, X1, X2) are each under 3 h and byte-identical by construction; together about 0.3 to 0.6 s at 103 GB and 0.05 to 0.25 s at small databases.

## ranked top 4 (value per hour, risk to bytes)

1. L1 + X1 diagnostics (1.5 h): perf of the load10 run and timestamps; every later load or exit decision depends on it.
2. L3 resident daemon via -D (4 to 8 h): removes load and teardown (about 3.6 s of 7.0 s at 103 GB) for every job after the first, byte-identical by construction; honest only for multi-sample use, not a single-shot claim.
3. X2 parallel teardown + F1/F2 chunk size and core pinning (about 3 h total): 0.2 to 0.4 s at 103 GB, 0.05 to 0.25 s at small databases, zero output risk.
4. L2 overlap scan with load (25 to 40 h): 0.4 to 0.8 s at 103 GB only; do it after L1 shows whether the load is bandwidth-bound (if it is, overlap fights it and the gain shrinks).

Sources: https://www.kernel.org/doc/html/v6.8/admin-guide/mm/transhuge.html , https://spinics.net/lists/linux-api/msg52936.html , https://lwn.net/Articles/1067225/
