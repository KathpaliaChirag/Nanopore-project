# the lock-free parallel FASTQ reader removes the wall floor (luna, 2026-11-23)

built by implementer I3 (code/impl_pread.diff, new logic in src/preadfq.h, unit test code/test_pread.cc, 8,101 cases 0 failures: code/test_pread_result.txt), on top of the best build (round6). K2_PREAD=1 is the default in bin_pread, K2_PREAD=0 forces the old path.

how it works: an atomic ticket is the block id and maps to a (file, 4 MiB chunk). every thread preads its own chunk and parses the records that START inside it with the exact kseq rules, outside any lock. empty chunks still emit an empty output block so the ordered writer never stalls. before running, every input file must be a regular file and its first MiB must be strict 4-line FASTQ; otherwise (FASTA, multi-line, stdin, pipes, paired-end, gz via the wrapper's pipe) the old path is used unchanged. a per-chunk guard aborts with "rerun with K2_PREAD=0" rather than produce different output.

## end-to-end correctness (data/pr_correct.txt): everything byte-identical to STOCK S19 (T=32, no patches)

per-read output (cmp) identical and plain report byte-identical in all of: 10 reads (one chunk, many idle threads) on 8 GB; 1,000 reads on 8 GB; 10 reads with 64 KiB chunks (14 chunks); 1,000 reads with 4 KiB chunks (14,184 chunks); all 1,872,777 reads on 50 MB with 64 KiB chunks (191,409 chunks), 1 MiB chunks (11,968) and the default 4 MiB (2,998), and the default on 8 GB, 16 GB and 103 GB. the verbose log confirmed the pread path actually ran every time.

## timing (data/pr.csv), all 1,872,777 reads, wall seconds, 5 interleaved repetitions, K2_BULK=1

| db | threads | old reader (K2_PREAD=0) | parallel reader |
|---|---|---|---|
| 50 MB | 32 | 5.28 5.36 5.32 5.31 5.28 | 5.07 5.05 5.06 5.05 5.05 |
| 50 MB | 48 | 4.93 4.94 4.94 4.91 4.92 | 3.53 3.51 3.52 3.52 3.53 |
| 50 MB | 64 | 5.09 5.15 5.16 5.09 5.14 | 2.76 2.76 2.77 2.76 2.76 |
| 50 MB | 96 | 5.28 5.29 5.31 5.33 5.30 | 2.11 2.10 2.08 2.10 2.07 |
| 8 GB | 32 | 5.01 4.99 5.01 5.02 4.99 | 4.56 4.54 4.56 4.58 4.56 |
| 8 GB | 48 | 5.29 5.26 5.18 5.22 5.27 | 3.27 3.26 3.28 3.26 3.27 |
| 8 GB | 64 | 5.39 5.42 5.38 5.35 5.37 | 2.65 2.65 2.66 2.66 2.68 |
| 8 GB | 96 | 5.61 5.61 5.54 5.59 5.56 | 2.15 2.16 2.14 2.25 2.15 |
| 103 GB | 32 | 9.60 9.60 9.57 9.52 9.65 | 9.49 9.48 9.54 9.46 9.48 |
| 103 GB | 48 | 8.61 8.85 8.86 8.83 8.72 | 7.72 7.88 8.10 7.86 7.83 |
| 103 GB | 64 | 8.94 9.01 8.91 8.92 8.82 | 7.25 7.31 7.45 7.29 7.44 |
| 103 GB | 96 | 9.10 9.26 9.14 9.25 9.11 | 7.15 7.34 7.34 7.35 7.13 |

with the old reader the wall got WORSE past 32 to 48 threads (more threads, more lock contention); with the parallel reader it keeps falling to 96 threads. against stock S19 at its default 32 threads (50 MB 8.39 s, 8 GB 8.60 s, 103 GB 20.29 s): 4.0x (50 MB, 96 threads), 4.0x (8 GB, 96 threads), 2.8x (103 GB, 96 threads), all with output and report byte-identical to stock.

at 103 GB the floor is now the database load (about 3.2 s) plus the memory-bound lookups, which is why it flattens at 7.3 s from 64 threads.

## caveats (do not skip)

- one machine (Luna), warm page cache, FASTQ input in regular files only (the fast path is off for stdin, pipes, paired-end, gz (the perl wrapper pipes gzip -dc), FASTA, and anything not strict 4-line FASTQ).
- Luna is shared (65 users). 96 threads is a policy choice, not free: it takes half of the 192 logical CPUs. the sweep up to 192 threads is running (data/hi.csv when it lands).
- a file that is strict in its first MiB but damaged later makes the run abort with an error message instead of continuing (kseq would have tolerated e.g. a late blank line). the error names K2_PREAD=0.
- quality skipping (round 4) is on in all these runs; -Q and -C/-U requests disable it and need re-validation with the parallel reader (the validation matrix, code/validate_matrix.sh, has not been run on bin_pread yet).
