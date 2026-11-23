# validation matrix on the stacked builds (luna, 2026-11-23): what passed, what the parallel reader broke

script: code/validate_matrix.sh (written by the round 2 validator agent, about 130 generated cases: FASTA single and multi-line, CRLF, empty reads, '@' in quality lines, reads at 16 KiB buffer boundaries, paired-end and interleaved, -Q, -C/-U, --report-minimizer-data, --use-names, --report-zero-counts, --confidence, --minimum-hit-groups, --quick, gz and bz2 via the wrapper, stdin, chunked pipes, translated search skipped for lack of a protein db) against STOCK S19. per case it compares exit code, normalised stderr, per-read output, classified/unclassified files and the report. log: data/validate_matrix2.log.

## result of run 2 (builds: parallel reader on, parallel reader off, parallel reader with K2_KEEPQ=1, scalar-bulk-scanner-only): 586 PASS, 78 FAIL, 0 WARN

every failure is in the two builds with the parallel reader ON (39 each). the build with the reader OFF (kseq path, but with the HLL guard + lazy keys, prefetch dedup, quality skip and bulk scanner) and the scanner-only build pass EVERY case. so those four changes are validated across the whole option matrix, including -Q, -C/-U, paired-end, FASTA, CRLF, gz and stdin; the quality skip was also checked with K2_KEEPQ as a control.

the parallel reader failures:

1. report-minimizer-data cases with quick mode (a11_quick_hg_K) and with --report-zero-counts on 8 GB and 16 GB (f02_K_z): the distinct-minimizer columns of the report differ even sorted while the per-read output is identical. cause (reproduced by hand): stock block boundaries are every 3 M bases, and the HyperLogLog columns depend on where block boundaries fall: reports from the parallel reader at chunk sizes 64 KiB, 256 KiB, 1 MiB and 4 MiB were identical to each other, differed from a single-chunk run (16 MiB), and only the single-block run (like stock's 1 or 2 blocks) matched stock. stock itself is deterministic (3 runs identical). a lock-free reader cannot reproduce stock's content-dependent block boundaries cheaply. FIX applied (impl_pread2, bin_pread2): the parallel reader is not used when --report-minimizer-data is requested. the plain report and the per-read output are partition independent (all 4 databases at 4 MiB, 64 KiB, 1 MiB and 4 KiB chunks matched stock byte for byte).
2. malformed or truncated FASTQ (c_eof_after_seq, c_eof_after_plus, c_eof_after_plus2, c_eof_mid_qual, c_long, c_short and their _K variants): stock silently stops reading at the first malformed record and exits 0 with the output so far; the strict parallel reader aborts with an error that names K2_PREAD=0 (nothing is silently different, but the exit code and files differ). this is a deliberate design choice (a damaged file is loudly rejected instead of silently truncated) but it IS a behaviour difference, most relevant for a file cut off mid-record (an interrupted basecaller). open item: handle a truncated final record like stock (drop it, exit 0).

## what this means for shipping

- safe to ship by the matrix: HLL guard with lazy keys, prefetch dedup, quality skip, bulk scanner (K2_BULK).
- the parallel reader needs run 3 (bin_pread2, running) to confirm group 1 is gone, and a decision on group 2 (abort vs tolerate).
