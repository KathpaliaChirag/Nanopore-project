# cycle 3 result: the serial FASTQ read section was the wall floor (luna, 2026-11-23)

## diagnosis

lock instrumentation (e1/src_lock, K2_LOCKSTAT=1) on the best build at T=48, all 1,872,777 reads (12.54 GB): total time the critical(seqread) section was held = 6.40 s (50 MB db) and 6.39 s (8 GB db); total time threads waited to enter = 79 s and 101 s. the classification phase is 6.5 s, so the serial read section ran for essentially the whole phase: 12.54 GB / 6.4 s = 1.96 GB/s. that is the database-independent wall floor seen earlier (6.7 to 7.0 s on every database), and why more threads, a faster scanner, -march=native, a larger read buffer, or numa placement did nothing.

inside the lock, LoadBlock calls kseq_read per read (memchr + memcpy of header, sequence and quality into kseq's strings) and copy_from_kseq then copies header, comment, sequence and quality again into the Sequence object and calls shrink_to_fit on the sequence (a reallocation per read).

## the change (code/serial_section.diff)

1. kseq_read: when the quality string is not needed, count its length with memchr (new ks_skipline, same CR handling and the same seq.l == qual.l check) instead of copying it. needed only for -Q (minimum_quality_score > 0) and for --classified-out / --unclassified-out, so the skip is switched on only when none of those is requested (env K2_KEEPQ=1 forces the old path).
2. copy_from_kseq: use a recorded quality length to keep the FASTQ/FASTA format flag, assign quals only when present, and drop the per-read shrink_to_fit.

## correctness (data/ser_correct.txt)

- per-read output and plain report byte-identical to the previous best build on 50 MB, 8 GB, 16 GB and 103 GB, all 1,872,777 reads.
- --classified-out and --unclassified-out files byte-identical (1,000 reads, 8 GB), so the safety switch works.
- NOT tested: -Q masking runs (the skip is off by construction), FASTA input, CRLF files, paired-end, gzip input. do not ship before those.

## timing (data/ser.csv), T=48, 5 interleaved repetitions, wall seconds

| db | previous best | with serial fix | speedup | user cpu |
|---|---|---|---|---|
| 50 MB | 6.91 6.71 6.85 6.78 6.74 | 5.21 5.25 5.23 5.25 5.25 | 1.30x | 237.5 -> 225.8 s |
| 8 GB | 6.99 7.00 7.07 6.97 6.95 | 5.18 5.18 5.18 5.19 5.20 | 1.35x | 214.8 -> 207.4 s |
| 16 GB | 7.40 7.41 7.28 7.35 7.42 | 5.82 5.78 5.79 5.80 5.83 | 1.28x | 244.5 -> 231.8 s |
| 103 GB | 10.69 10.70 10.47 10.44 10.44 | 9.43 9.27 9.15 9.11 9.09 | 1.15x | 271.0 -> 257.9 s |

cumulative against stock S19 at 32 threads (stack.csv baselines 8.39, 8.60, 10.06, 19.92 s): 1.60x (50 MB), 1.66x (8 GB), 1.73x (16 GB), 2.19x (103 GB), with output byte-identical.

## what is left

the serial section still copies the data twice (kernel to kseq buffer, kseq buffer to the Sequence strings) and parses under the lock. moving the parse out of the lock (read raw blocks under the lock, parse in parallel) or reading the 16 input files with parallel readers would lift the floor further; the cpu-bound limit at 8 GB is about 207 / 48 = 4.3 s against 5.2 s now.
