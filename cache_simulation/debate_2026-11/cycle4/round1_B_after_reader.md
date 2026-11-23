# cycle 4 round 1, agent B: what limits the wall at 96+ threads (read-only audit)

sources read: ~/e1/impl_pread2/src/classify.cc (ProcessFiles lines 470-740, ClassifySequence, AddHitlistString, InitializeOutputs), seqreader.h (LoadPreadTry), readcounts.h, hyperloglogplus.cc (merge), reports.cc, plus cycle3 data/hi.csv and pr.csv. tags: [R] read in code, [M] computed from measured csv numbers, [E] my estimate, [U] unverified. nothing was run.

## 1. the first finding: the wall is mostly compute on 96 physical cores, plus a non-cpu term that grows with threads

the box is 2 sockets x 48 cores x 2 hw threads, so T=96 is one thread per physical core and T>96 is smt. from data/hi.csv and pr.csv (user cpu seconds, means of 3 reps), idle = wall - user/T is the average per-thread time not spent in user mode [M]:

| db | T | wall | user cpu | user/T | idle per thread |
|---|---|---|---|---|---|
| 50 MB | 48 | 3.53 | 151.6 | 3.16 | 0.37 |
| 50 MB | 96 | 2.10 | 157.0 | 1.64 | 0.46 |
| 50 MB | 128 | 2.04 | 189.2 | 1.48 | 0.56 |
| 50 MB | 160 | 2.04 | 217.5 | 1.36 | 0.68 |
| 50 MB | 192 | 2.09 | 239.7 | 1.25 | 0.84 |
| 8 GB | 96 | 2.12 | 134.9 | 1.41 | 0.71 |
| 8 GB | 128 | 2.08 | 163.8 | 1.28 | 0.80 |
| 8 GB | 160 | 2.10 | 187.0 | 1.17 | 0.93 |
| 8 GB | 192 | 2.18 | 210.5 | 1.10 | 1.08 |

two things follow.
1. work is conserved up to 96 threads (user 151.6 at T48, 157.0 at T96 on 50 MB), so the code scales cleanly while there is a free physical core. past 96, user cpu grows 50% (two hyperthreads share a core, and the scanner runs at IPC 2.3 so the second thread adds little) and the wall stops falling. T=128 to 192 buys nothing because the extra threads only make every thread slower. that is the compute floor: 157 cpu-s / 96 cores = 1.64 s on 50 MB, 135 / 96 = 1.41 s on 8 GB.
2. the non-cpu term is not constant. at 50 MB it is 0.37 s at T48, 0.46 at T96, 0.84 at T192, about +4 ms per added thread with an intercept near 0.08 s [M]. a fixed startup or exit cost would be flat; this one scales with the thread count. that is the signature of lock convoys, per-thread startup and teardown, or the tail, and it is the only part Amdahl lets us attack besides cutting the cpu work. on 8 GB add about 0.3 s of load and exit (the 10 read load-only run on 8 GB was 0.31 s in cycle3 round 2).

so the bound: wall(T=96) = 2.10 = 1.64 compute + 0.46 nonscaling on 50 MB. parallel fraction p = 1.64/2.10 = 78%. removing ALL non-cpu time would give 1.64 s (1.28x); cutting cpu work by x% gives x% of 1.64 s. both directions are small multiples of 0.1 s now.

## 2. every remaining serial or lock-protected section, with hold-time estimates

chunk facts: 12.5 GB of fastq in 2,998 chunks of 4 MiB (round 7), about 625 reads per chunk (1.87 M reads / 2,998), about 52 ms of compute per chunk (157 cpu-s / 2998). each thread does about 31 chunks. a per-chunk event costing h under one global lock occupies that lock 2998 x h in total.

| section | what runs inside | hold per chunk | total hold | verdict |
|---|---|---|---|---|
| atomic ticket (pread_plan.next) | one fetch_add [R] | 20-100 ns | under 1 ms | none |
| critical(output_stats) | 3 adds plus isatty(fileno(stderr)), one ioctl [R] | 1-2 us | about 5 ms | none |
| critical(output_queue), 3 entries per chunk | push (moves 5 strings), top/pop, buffers vector push/pop [R] | 0.1-1 us each (line bounces across sockets) | about 10 ms | none |
| omp_set_lock(output_lock) taken INSIDE critical(output_queue) [R] | a thread that finds the next block ready takes the writer lock while still holding the queue critical | blocks until the current writer finishes its write | /dev/null about 0; real file see section 4 | latent stall for every other thread |
| the write, `kraken_output << kraken_str` [R] | one 0.3-2 MB write(2) per chunk (libstdc++ filebuf passes big strings straight through) | /dev/null: microseconds | about 5 ms | none for the benchmark |
| critical(update_taxon_counters) [R] | per distinct taxon in the chunk: std::map find or insert in the global map, default-construct a ReadCounts (it carries a HyperLogLogPlusMinus with a vector and a sparse list), move-add | taxa_per_chunk x 0.2-0.4 us | 0.6 to 1.2 s per 1000 taxa per chunk | the one real candidate, see below |
| first-wave convoy | all threads start together, so first chunks end within a few ms and queue on the criticals | about T x h_merge | 20-60 ms once (twice at T=192) | 1-3% of wall |
| tail | last chunk per thread ends unevenly | 0.5 x one chunk | about 25-50 ms | 1-2% |
| ReportKrakenStyle at exit | GetCladeCounters plus DFS over the taxonomy, one ofstream [R] | n/a | a few ms (report is 384 KB) | none |
| process exit | table is not deleted (commented out) [R], thread-local teardown | n/a | 0.05-0.3 s depending on resident size [U] | part of the 0.46 s |

HLL is not an issue here: with --report and no -K the HLL is never inserted into (n_observed stays 0), so merge() returns on its first line [R, hyperloglogplus.cc:577]. what remains per taxon is the std::map operation and the ReadCounts construct and move.

the taxa-per-chunk number is the missing fact [U]. with E8 every distinct hit taxon of every read is inserted into the thread's std::map, and a chunk of 625 long reads can touch hundreds to a few thousand distinct taxa on the standard 8 GB database. at 500 taxa per chunk h = 0.15 ms and the lock is busy 0.45 s of the 2.1 s wall (utilisation 0.2 at T96, 0.4 at T192). at 3000 taxa h = 0.9 ms and utilisation passes 1 at T=192, which would produce exactly an idle term that grows linearly with T. both cases fit the +4 ms/thread slope, so section 5 has the oracle.

per-read serial work: none. the ordered writer does not serialise compute: a thread that finds block n+1 not ready goes back to classifying. the only way output blocks compute is the nested lock (section 4).

## 3. what the per-read parallel work still contains [R], cost estimates [E]

total W is 157 cpu-s on 50 MB, about 84 us per read. visible waste inside it:
- c1/c2/u1/u2 building, done for EVERY read even with no -C/-U (the round 1 audit item, still present in impl_pread2 lines 589-605): sprintf and `header +=` for classified reads, then Sequence::to_string() allocates a fresh 3.3 kB string (header plus seq; quals are already dropped by quality skip), `<<` copies it into c1_oss or u1_oss (doubling growth), then at chunk end `.str()` copies the whole 2 MB stream and `.assign` copies it again into out_data. about 6 passes over 3.3 kB x 1.87 M reads is 37 GB of memcpy, 6 to 9 cpu-s, plus 4 large allocations per chunk (out_data was moved-from by the push, so every assign reallocates), all thrown away at write time because those outputs are nullptr. big mallocs in non-main glibc arenas grow and trim the heap with mprotect/madvise, which takes the process mmap lock, so this cost may also grow with thread count [U].
- kraken line formatting with ostringstream: `<<` on integers goes through locale num_put (about 50-80 ns each), 3 inserts per run in AddHitlistString plus about 8 for the line header. cost = runs per read x about 0.2 us. at 30 runs per read that is 6 us (7% of 84 us), at 100 runs 20 us (24%). runs per read is not measured.
- hit_counts unordered_map: one node malloc/free per distinct taxon per read, plus `hit_counts[max_taxon]` and ResolveTree's n^2 loop with O(depth) IsAAncestorOfB. S15 run merging already cut the map calls, so 1-3%.
- E8 inserts every hit taxon into a per-thread std::map (rb-tree, a node per taxon, freed by `thread_taxon_counters.clear()` every chunk): 1-4 us per read, 1-5%.
- `auto empty_sequence = Sequence();` per read: cheap, under 1%.
- LoadPreadTry copies header, comment and seq into the per-thread Sequence with assign: one more 3.3 kB memcpy per read. a view-based Sequence would drop it but is invasive (about 2%).

## 4. output: how big, and what a real file costs

input is 12.5 GB (that is the number to Amdahl against, not the output). the per-read kraken file is one line per read: C or U, tab, header (about 36 chars, only the name, not the comment), tab, taxid, tab, length, tab, then the run list "taxid:count " per run. 1.87 M lines at 0.3 to 1.7 kB (30 to 200 runs of about 8 chars) is 0.6 to 3.2 GB, central estimate about 1.5 GB [E]. the round 1 audit said under 0.5 GB, which looks low for 3.2 kb reads with about 1000 minimizers each. oracle: `--output /dev/shm/x.out` on 20 reads, `wc -c`, scale by 1.87 M / 20 (tmpfs has 248 GB free; the root disk has only 11 GB free, so never write the real run to ~).

/dev/null versus a real file as a floor:
- /dev/null: write(2) returns at once, so the benchmark pays only formatting, not the kernel copy of about 1.5 GB or filesystem work.
- real file in page cache: 1.5 GB through one ordered writer at 1.5 to 3 GB/s is 0.5 to 1 s of write time. production is about 0.9 GB/s (1.5 GB in 1.7 s), so the writer is 30 to 60% busy: not a hard floor, but 0.5 to 1 s of serial work, and the final drain happens after the last chunk is classified.
- the nested lock makes it worse than utilisation suggests: thread B holds critical(output_queue) while it waits in omp_set_lock for writer A to finish a 0.3 to 1 ms write, and every other thread that finishes a chunk blocks at its push behind B. with about 1800 chunk completions per second the queue critical is blocked a large fraction of the time. estimate +0.05 to 0.3 s wall at T=96, more at T=192 [E]. a 1.5 GB file stays in dirty page cache (dirty_ratio of 252 GB is far above it), so no throttle.
- stdout (the default with no --output) goes through std::cout with sync_with_stdio on, one fwrite per block; a pipe to gzip or a terminal makes the consumer the floor (gzip 0.3 to 1 GB/s, so 2 to 5 s for 1.5 GB).

what else a real run changes:
- -C/-U: quality skipping is off (k2_skip_qual needs no -Q, -C or -U), quals are parsed and copied, and c1/u1 are real outputs. classified plus unclassified together rewrite the whole input, so about 12.5 GB through one ordered writer at 2 GB/s is 6 s, about 3x the compute floor. the run becomes write-bound and scanner work is invisible. this case needs the parallel writer (item 4b).
- no --report: no E8 inserts, no merge, no HLL, so item 3 is zero for such a user. the oracle "run without --report" doubles as the answer to how much the report bookkeeping costs.
- paired-end, FASTA, gz and stdin never take the pread path (round 7), so a real run on gz input is back at the old serial-reader floor (5+ s) whatever is done here. that is the biggest real-user gap and is outside this round.

## 5. oracles, time-only unless stated (T=96 and T=128, 50 MB and 8 GB, 3 interleaved reps)

- O0, no code: K2_PREAD_CHUNK sweep 512 KiB, 1, 4 (default), 16 MiB. if wall moves less than 1% across the sweep, chunk overhead and tail are both dead and the idle term is exit or the start convoy. the env var already exists.
- O1, no code: the same run without --report. the difference is the whole cost of E8 + merge + HLL objects (upper bound of item 3).
- O2, no code: `--output -` (kraken_output is nullptr, no write call) versus `--output /dev/null`: the write(2) path plus writer-side string handling.
- O3, a few lines of capture: ReportStats already prints the classify wall (tv1 to tv2) on stderr; compare it to total wall to separate load and exit from the parallel region.
- O4, 10 lines: omp_get_wtime around critical(update_taxon_counters) and around the omp_set_lock wait, summed per thread and printed at exit, plus mean distinct taxa per chunk. resolves the section 2 unknown.
- O5, env flag, outputs not identical: skip the c1/u1 block (the whole `if (call) ... else ...`); separately skip AddHitlistString (write "0:0"). each bounds its item.
- O6, no code: `perf stat -e task-clock,page-faults,context-switches` and sys seconds at T=96 versus T=192. a sys or fault count that grows with T confirms the malloc/mmap-lock path in item 1.

## 6. proposed byte-identical fixes

1. skip building c1/c2/u1/u2 when no -C/-U (gate on opts.classified_output_filename and opts.unclassified_output_filename being empty, not on the lazily initialised output pointers). removes sprintf, to_string, 3 to 6 copies and 4 large allocs per chunk. expected 4 to 6% of cpu = 0.07 to 0.1 s at T=96, a bit more at 128 if the mmap lock is involved. risk none: those strings are discarded and the kraken line is written before the header is mutated. oracle O5 first half.
2. format the kraken line with snprintf or a hand itoa into a per-thread std::string, directly into out_data.kraken_str, no ostringstream, no str()+assign. keep the exact format (C or U, tab, header, tab, taxid or name, tab, length or a|b for pairs, tab, runs separated by single spaces, no trailing space, newline; keep the A: and |:| and -:- cases). expected 4 to 10% of cpu = 0.07 to 0.16 s at T=96, depending on runs per read. oracle O5 second half gives the bound before writing it. risk: format drift, cmp catches it.
3. take the report bookkeeping off the shared lock and off the per-chunk path: one persistent per-thread counter (flat array keyed by internal taxid, or the existing std::map but NOT cleared per chunk), accumulated across all chunks and merged into total_taxon_counters once per thread at the end: 96 merges instead of 2,998. expected 0.02 to 0.1 s at T=96 and most of the idle growth at 128-192 if the section 2 lock is the cause; zero without --report. risk: counts are plain sums so identical; the -K path uses kseq and keeps the old code. oracles O1 (upper bound) and O4.
4a. fix the nested lock: take output_lock with omp_test_lock or hand off by a flag outside critical(output_queue), so a thread that cannot become the writer leaves its block in the queue (the active writer already loops until the queue top is not next); recycle the out_data string buffers through the existing `buffers` pool. about 1% in the benchmark (/dev/null writes are instant), 0.05 to 0.3 s on a real file.
4b. parallel ordered output for real files and -C/-U: once a thread knows its block's byte size, a chain of 8-byte atomics hands it its file offset (a prefix sum passed down in block order, nanoseconds per block), then each thread does its own pwrite at that offset, no writer thread. byte-identical to the serial file, removes the writer floor, and is what lets a 12.5 GB -C run scale. gain for the /dev/null benchmark is about zero, so this is a real-user item.

not worth it now: larger chunks (chunk overhead is about 1% and the tail grows), flat hit_counts alone (1-2%), Euler-tour ancestor test (under 1%), view-based Sequence (invasive for 2%), db replication per NUMA node (only if O6 shows remote LLC stalls on the 50 MB case; separate experiment).

## amdahl check

at T=96 on 50 MB: wall 2.10 = 1.64 compute + 0.46 nonscaling. items 1+2 cut compute by 8 to 16%, 0.13 to 0.26 s. item 3 cuts 0.05 to 0.2 s of the nonscaling part. together a plausible 1.7 to 1.9 s (10 to 19% faster), about 4.4 to 4.9x stock on 50 MB if every estimate lands. cutting the rest of the 0.46 s needs the exit, startup and tail pieces (O0, O3), which are not yet diagnosed. past about 128 threads nothing here helps because the smt cost dominates, so keep the recommended thread count at 96 to 128.

## 6 line summary
1. the wall at 96+ threads is mostly compute on 96 physical cores: user cpu is conserved to T=96 (151.6 to 157 s), so 157/96 = 1.64 s of the 2.10 s is work, and past 96 smt inflates user cpu 50% for no wall gain.
2. a non-cpu term of 0.46 s per thread at T=96 grows about 4 ms per added thread (0.84 s at T=192); it is lock convoy, per-thread startup or teardown, tail or exit, and it is undiagnosed.
3. no section is a hard serial floor for the /dev/null benchmark: writer, queue and stats criticals total under 30 ms; the only lock with real hold time is critical(update_taxon_counters), 0.3 to 1.8 s total depending on distinct taxa per chunk (unmeasured).
4. real runs differ: a real file costs 0.5 to 1 s of ordered writing and exposes the nested omp_set_lock stall; -C/-U makes the run write-bound at about 6 s for 12.5 GB; no --report removes the lock; gz, paired and stdin input never reach the fast path.
5. the per-read waste still in the loop: c1/c2/u1/u2 built unconditionally (about 37 GB memcpy, 4 large allocs per chunk) and ostringstream formatting (5 to 25% of per-read time depending on runs per read).
6. free oracles first: K2_PREAD_CHUNK sweep, run without --report, `--output -`, ReportStats time versus wall, sys and page faults at T=96 versus 192, one 10-line timer on the taxon-counter lock.

## ranked top 4
1. skip c1/c2/u1/u2 when no -C/-U: 4 to 6% cpu, 0.07 to 0.1 s at T=96, byte-identical, about 1 hour.
2. snprintf/itoa kraken line built straight into the block buffer (no ostringstream, no str()+assign): 4 to 10% cpu, 0.07 to 0.16 s, bounded first by oracle O5.
3. per-thread persistent taxon counters merged once per thread, not per chunk: 0.02 to 0.1 s at T=96, larger at 128-192, only with --report.
4. output writer: non-nested lock plus buffer pool (about 1% in the benchmark, 0.05 to 0.3 s on a real file), and offset-prefix parallel pwrite for real files and -C/-U (removes a 6 s write floor on 12.5 GB).
