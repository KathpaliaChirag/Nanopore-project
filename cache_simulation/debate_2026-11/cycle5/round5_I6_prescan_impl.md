# cheaper pre-pass: mmap read plus overlap with the database load (cycle 5, round 5, implementer I6)

status: built and validated for correctness on luna (2026-11-23). nothing timed (as asked). new tree ~/e1/impl_pre (copy of impl_all, nothing else touched), runnable dir ~/e1/bin_pre. diff against impl_all/src: code/impl_pre.diff. unit test: code/test_pread_pre.cc (log in ~/e1/impl_pre/test_pread_result_i6.txt). end-to-end logs: ~/e1/i6_logs/*.log, driver ~/e1/i6_matrix.sh (the i4 matrix with i6_ temp names) and ~/e1/i6_run.sh.

the decision the pre-pass makes did not change: every chunk is parsed with the same process_chunk logic, tail damage is accepted, any other damage switches the whole run to the stock kseq path. only how the bytes arrive and when the work runs changed.

## 1. what was built (two files: src/preadfq.h and src/classify.cc)

### idea A, K2_PRESCAN_MMAP (default on)

- new read_chunk_mm in preadfq.h. it computes the same base, want and eof flag as read_chunk, maps that byte range with mmap(PROT_READ, MAP_PRIVATE) (offset rounded down to 4096), calls madvise(MADV_SEQUENTIAL), runs process_chunk on the mapping, then munmaps. no copy, no buffer. the tail-retry loop (tail times 4 on PR_MORE) is the same. if mmap fails for a chunk it falls back to read_chunk (pread) for that chunk.
- per chunk map and unmap (not one big map per file) so the teardown of page tables is spread over the worker threads and the process never holds a 12.5 GB mapping.
- K2_PRESCAN_POPULATE (default on) adds MAP_POPULATE, so the kernel maps the chunk's pages in one call instead of one fault per 16 pages. this is the one detail I would A/B first, it is a guess that it helps; K2_PRESCAN_POPULATE=0 turns it off.
- skipping work the real pass redoes: parse_record is now a template with a CHECK flag. with CHECK=true (selected automatically when the sink is NullSink) it skips the name/comment split of the header line (a byte loop over every header) and the Rec pointer stores. that work never returns PR_BAD or PR_MORE, so every accept, reject and more decision is the same. what remains per record is four memchr line scans, the '@' and '+' checks and the seq length == qual length check, which is exactly the structural validation. the quality line cannot be skipped: the only way to know line 4 has length equal to line 2 without scanning it is to find its newline.
- NullSink does no allocation or string copy (it never did); the only per-thread allocation left is the pread fallback buffer, unused on the mmap path.

### idea B, K2_PRESCAN_OVERLAP (default on)

- main() calls StartPrescanOverlap(opts) right after ParseCommandLine and before load_index(). it only starts when the run is exactly the case where ProcessFiles would run the pre-pass: K2_PREAD, K2_PREAD_PRESCAN not 0, not --report-minimizer-data, not paired-end, at least one input file, and not daemon mode. the file list is opts.filenames (in the unpaired case classify() passes exactly that list to the single ProcessFiles call, first file plus g_extra_files).
- it launches one launcher std::thread which runs Plan::Init (the same first-MiB check), and if that accepts, spawns K2_PRESCAN_THREADS (default 16) workers, itself included, each looping over an atomic chunk ticket and calling the shared k2pread::prescan_worker. the bound of 16 is so the load (which runs on the main thread and may use other cores) is not starved on a 96-core run.
- ProcessFiles first joins the launcher (a no-op when none ran), then if the stored file list and chunk size equal what it would have used, it takes over the Plan and the verdict (init_ok, bad). if they differ or the job was not wanted it discards the job and runs the inline pre-pass as before. the job is owned by a unique_ptr so the Plan's fds are closed at the end of ProcessFiles.
- the inline pre-pass (K2_PRESCAN_OVERLAP=0) now calls the same prescan_worker from an OpenMP parallel region, so inline and overlapped use identical per-chunk logic. K2_PRESCAN_MMAP applies to both.
- if load_index() errors out (errx), the process exits while the workers run. the job and threads are heap objects never destroyed, so there is no std::terminate from a joinable thread.
- the pre-pass time is no longer inside the "processed in ...s" figure (ReportStats times from after the load), but it is inside the wall clock; time the whole command.
- K2_PREAD_PRESCAN=0 still skips the pre-pass entirely (neither inline nor overlapped).

what overlap can and cannot hide: at 103 GB the load takes about 3.2 s, so a 0.1 to 0.3 s pre-pass disappears inside it if the load is not bandwidth-saturated. at 50 MB and 8 GB the load is far shorter than the pre-pass, so there only idea A (cheaper pre-pass) helps, and part of the pre-pass is still exposed.

## 2. tests (all done on luna, nice, tiny inputs, db sample_targeted, threads 1 and 8, inputs under /dev/shm/i6_*)

end-to-end, vs stock S19 (per-read output, sorted and exact-order report, exit code, stderr stats, classified/unclassified outputs where used): the i4 matrix groups c (13 damage shapes x 5 option sets: plain, --report-minimizer-data with zero counts, --use-names, --quick, classified/unclassified outputs; truncated tails at six cut points, mid-file short and long quality, '@' and '+' in quality lines, resync cases), multi (truncation in file 1, last file, consecutive files, mixed, damage in file 1 of 2, damage in two files, damage then truncation), big (damage after the first MiB, two damages, short/long/junk, '@' quality), control. each case at chunk sizes 4096 and 65536. CRLF, FASTA fallback and the rest of validate_matrix4 were not rerun (they do not touch the pre-pass beyond what these cases cover, see risks).

| config (env) | result |
|---|---|
| default (mmap on, populate on, overlap on, 16 threads) | 428 pass, 0 fail |
| K2_PRESCAN_MMAP=0 | 428 pass, 0 fail |
| K2_PRESCAN_OVERLAP=0 | 428 pass, 0 fail |
| K2_PRESCAN_MMAP=0 K2_PRESCAN_OVERLAP=0 (the old pre-pass, new code) | 428 pass, 0 fail |
| K2_PRESCAN_POPULATE=0 K2_PRESCAN_THREADS=3 | 428 pass, 0 fail |
| truncation sweep (every cut point of the last record, 270 cuts x 5 chunk/thread configs), default config | 1350 pass, 0 fail |

in the control cases the overlap is visibly active: with K2_PREAD_VERBOSE the damage message prints while "Loading database information..." is still on the line (default and nopop configs), and appears after it with K2_PRESCAN_OVERLAP=0. K2_PREAD_PRESCAN=0 on mid-file damage still gives exit 3 with the same message as before.

unit test (impl_trunc's test_pread.cc, which has the truncation sections, carried into impl_pre and extended): new_read now computes, for every chunk of every case, the verdict of four readers (pread + NullSink with the CHECK parse, pread + a non-NullSink counting sink with the full parse, mmap with MAP_POPULATE, mmap without) and fails on any difference, plus the overall verdict of prescan_worker with 1 and 4 threads, pread and mmap. result: 35,214 cases passed, 0 failed, and 46,067,058 variant comparisons with no disagreement (pre-pass fallbacks 1,148, damaged cases rejected up front 124). the run takes about 10 minutes because of the extra readers.

## 3. benchmark commands for you (nothing timed here)

all on luna, bin_pre, T=96, the 12.5 GB input, each db (50 MB, 8 GB, 103 GB), 5 interleaved repetitions, wall clock of the whole command. use whatever your existing driver (all.sh / all_prescan.csv style) uses; the five configurations are only env prefixes:

```
B=~/e1/bin_pre/kraken2
# baseline: old exact behaviour, no pre-pass at all (the floor)
K2_PREAD_PRESCAN=0                                        $B --db $DB --threads 96 --output o.out --report o.rep $IN
# old pre-pass (what bin_all does): pread, inline
K2_PRESCAN_MMAP=0 K2_PRESCAN_OVERLAP=0                    $B ... 
# A only: mmap inline
K2_PRESCAN_MMAP=1 K2_PRESCAN_OVERLAP=0                    $B ...
# B only: overlap with pread
K2_PRESCAN_MMAP=0 K2_PRESCAN_OVERLAP=1                    $B ...
# A + B (the new default)
                                                          $B ...
```

extra A/B knobs worth one extra column each: K2_PRESCAN_POPULATE=0 (is MAP_POPULATE a help or a hurt), K2_PRESCAN_THREADS=8 and 32 (overlap pool size; 16 is a guess). pairs to read off: (old pre-pass minus floor) is the 0.33 s cost; each other row minus floor is what is left. also check that K2_PREAD_PRESCAN=0 on bin_pre is not slower than on bin_all (the load path is untouched, but main() now starts nothing in that case).

the outputs should stay byte-identical to the earlier runs (compare o.out with all_correct.txt's reference as before).

## 4. risks and things I could not check

1. no timing. whether mmap beats pread here is a guess: the pread path copies into an L2-sized buffer, which is cheap in DRAM traffic, so the gain may be only the saved copy cycles, not half the cost. overlap is the larger lever on the 103 GB db and does nothing for the 50 MB db.
2. overlap competes with the load for memory bandwidth and, if the input is not in page cache, for the disk. with a cold 12.5 GB input the pre-pass reads it first (as before) and the real pass then hits cache; no worse than before, but the load could slow slightly. K2_PRESCAN_THREADS bounds it.
3. mmap hazards: a file truncated while mapped gives SIGBUS in the pre-pass (pread would just fail the read and report damage). a file that grows is fine (we only map up to the size read at Plan::Init). filesystems that do not support mmap fall back per chunk to pread. input on a network filesystem is the case to watch.
4. MADV_SEQUENTIAL and MAP_POPULATE on a file mapping read by 96 threads at interleaved offsets: expected harmless, but readahead tuning is the kind of thing that can surprise; that is why both are switchable.
5. the overlapped pre-pass runs before the database is loaded, so a bad database path or a bad option combination errors out while workers are running. harmless (the process exits), but the K2_PREAD_VERBOSE damage message can then appear before the error text.
6. CRLF, FASTA, paired-end, gz and stdin inputs were not rerun end to end. they are outside the pre-pass (paired-end, gz, stdin never start it: a non-regular file or paired mode fails the eligibility check; FASTA and CRLF only matter to Plan::Init and process_chunk, which are unchanged except for the CHECK flag, covered by the unit test and the 5-config comparison above). I would still rerun validate_matrix4 once on bin_pre before replacing bin_all.
7. the CHECK flag is correct only because the skipped header work cannot produce a non-OK code; the unit test now guards that by comparing the CHECK parse against the full parse on every chunk of about 22,000 cases.

## summary

1. K2_PRESCAN_MMAP (default on): per chunk mmap + MADV_SEQUENTIAL + MAP_POPULATE, no copy, header-split skipped (CHECK parse); pread fallback on mmap failure.
2. K2_PRESCAN_OVERLAP (default on): the pre-pass starts in main() before the database load, 16 threads (K2_PRESCAN_THREADS), joined in ProcessFiles; verdict handed over with the Plan.
3. the decision rule is unchanged: clean or tail-damaged file takes the parallel reader, any other damage takes the stock kseq path; K2_PREAD_PRESCAN=0 still skips it.
4. e2e vs stock S19: 428 cases x 5 env configs plus a 1350-case truncation sweep, all identical (output, report, rc, stderr stats).
5. unit test: 35,214 cases pass, 0 fail, 46,067,058 pre-pass variant comparisons all agree.
6. not timed: benchmark commands are in section 3; the two guesses to settle are whether mmap helps and whether 16 overlap threads is right.
