# round 5, I1: option 4 reader fast path (cut one copy inside critical(seqread))

## what changed

source tree: ~/e1/impl_reader/src (copied from ~/e1/src_final, nothing else on luna touched). diff: ~/e1/impl_reader/changes.diff, in the repo as cache_simulation/debate_2026-11/cycle3/code/impl_reader.diff.

1. kseq.h: kstream_t gets a `size_t cap` field (the buffer capacity, set to 16384 in ks_init). nothing else in kseq.h changed, kseq_read is untouched.
2. seqreader.h, LoadBlock: before each kseq_read it now tries FastRecord(). on success the record goes straight from kseq's stream buffer into the Sequence strings (header, comment, seq, quals assign()ed once). on any doubt it returns false having consumed nothing, and the original kseq_read + copy_from_kseq runs on the untouched stream.
3. FastRecord only accepts a strict 4-line FASTQ record: kseq state is between records (last_char == 0), first byte is '@', the sequence line is non-empty and does not start with '>', '+', '@' or newline, line 3 starts with '+', and the quality line length (after the same stripping) equals the sequence length. everything else (FASTA, multi-line, blank lines, empty read, junk before the first '@', short or long quality, unterminated last line) takes the real kseq path.
4. kseq rules copied exactly: name ends at the first isspace byte; comment is the rest of the header line after that one byte; trailing '\r' stripped from the comment, the sequence and the quality only when that field's length is > 1; qual is dropped when kseq_->skip_qual is set (k2_skip_qual), else copied; format is FASTQ (the accepted records always have seq length > 0, so the qual.l > 0 test in copy_from_kseq is always true for them).
5. FastFill: when the record is not fully in the buffer, it compacts the unread bytes to the buffer start (memmove), reads more with read() into the rest of the buffer, and retries. it sets is_eof when read() returns 0, same as kseq. the buffer grows by realloc (doubling) only when a partial record fills it. initial target is 64 KiB (the first fill grows the 16 KiB buffer to 64 KiB), so a typical 2.8 kb read (about 5.7 kb record) almost always hits, instead of the roughly one third that straddle a bare 16 KiB buffer. kseq's own refills still ask for 16384 bytes, which is safe since capacity only grows. I kept the stream buffer small on purpose (64 KiB, not 1 MiB) given the earlier 1 MiB result; no evidence either way, K2_FASTBUF (bytes) lets you A/B it.
6. env switches, read once in the constructor: K2_FASTREAD=0 disables the fast path (default on); K2_FASTBUF=<bytes> sets the fill target (default 65536). paired-end (LoadBatch, NextSequence) is not touched.
7. optional counters behind -DK2_FAST_STATS (off in the classify build).

## unit test

~/e1/impl_reader/test_reader.cc (build: `g++ -O2 -std=c++17 -I src test_reader.cc -o test_reader -pthread`, run `./test_reader`, about 1 s). it runs old (K2_FASTREAD=0) and new on the same file and compares header, comment, seq, quals and format of every record, for block sizes 1, 100 and 3 MiB, skip_qual on and off, and (for a subset) reading through a pipe fed in 997-byte chunks so records split at every offset.

result: cases passed=516 failed=0, PASS. each case is run in 6 to 12 old-vs-new configurations. cases: first 200 lines of pod5_0.fastq (tiny.fastq), empty file, one record, empty read (twice), '@' and '+' at the start of the quality line, CRLF (including 1-base reads and "@id \r"), tab-separated comments, empty name, multiple spaces, no trailing newline (LF and CRLF), truncated after '+', quality too short and too long, multi-line sequence and quality, blank line between records, junk before first record, FASTA (multi-line and single line), mixed FASTA and FASTQ, '+' with a name, header only, a record of 20 kb, 70 kb and 2 MB, 81 buffer-boundary offsets, and 400 random fuzz files with random damage. a stats build (-DK2_FAST_STATS) shows both paths are really exercised: 94,612 fast hits and 12,360 fallbacks across the run.

limit: the test only covers the reader; it does not run kraken2, so end-to-end byte-identity of the c1/u1 output and report is not yet checked.

## build

classify compiled with `cd ~/e1/impl_reader/src && nice make -j4 classify` (clean, -std=c++11, only the old write() warning). runnable dir: ~/e1/bin_reader (copy of kraken2-fresh-bin-s19 with the new classify; its kraken2 script points at /home/student/e1/bin_reader). not run on any real data.

## how to benchmark

same invocation as your other runs, only the bin dir changes: `/home/student/e1/bin_reader/kraken2 ...`.
- A/B inside one binary: `K2_FASTREAD=0 /home/student/e1/bin_reader/kraken2 ...` (old path) against the default (fast path). interleave them as in the 5-run protocol.
- buffer A/B: `K2_FASTBUF=16384` (no growth) and `K2_FASTBUF=262144`.
- lock hold: run with K2_LOCKSTAT as before.
- correctness: md5 of the per-read output and the --report against the previous best build at T=1, 48 and 96, with and without -C/-U and -Q, a single-file run and a stdin run.

expected gain (from round 2 design): hold about 0.8 to 1.0 s lower, wall 4.7 to 4.9 s at 8 GB and 8.8 to 9.0 s at 103 GB. this is an estimate, not measured.

## known risks

- fast path hit rate on real data was not measured; the unit test hit rate is dominated by synthetic edge cases. check it with a -DK2_FAST_STATS build if the gain looks small.
- the 64 KiB fill adds a memmove of the partial record tail (at most one record, a few kb) per fill. small, but it is new work inside the lock.
- the fast path may read further ahead than kseq would (up to 64 KiB per fill instead of 16 KiB). on a pipe this means it can block waiting for more bytes only when a record is incomplete, same as kseq would.
- the earlier 1 MiB buffer test was 2 to 4% slower; if the larger fill hurts the same way, set K2_FASTBUF=16384.
- the shared kstream is now mutated from seqreader.h; any future change to kseq's buffer handling must keep begin/end/is_eof/cap in step.
- uses getenv at reader construction only; the copy constructor copies the flags.

## summary (6 lines)
1. added FastRecord/FastFill to seqreader.h LoadBlock: strict 4-line FASTQ parsed from kseq's buffer straight into Sequence strings, one copy instead of two; real kseq_read fallback for everything else.
2. kseq.h only gained a `cap` field; kseq_read semantics untouched.
3. env gates: K2_FASTREAD=0 turns it off, K2_FASTBUF sets the fill size (default 64 KiB).
4. unit test old vs new: 516 cases, 0 failures (edge cases, CRLF, long reads, pipe, 400 fuzz files, both skip_qual modes).
5. binary at ~/e1/bin_reader (classify built clean, not run on data); diff at cache_simulation/debate_2026-11/cycle3/code/impl_reader.diff.
6. unit test passed: yes; end-to-end byte-identity and the speedup are still unmeasured.
