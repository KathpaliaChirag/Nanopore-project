# cycle 3 round 2, agent A: lifting the serial reader floor (read-only design)

source read on luna: kraken2-src-s19/src seqreader.h, seqreader.cc, kseq.h, classify.cc ProcessFiles, plus the serial_section.diff. tags: [R] read in code, [M] measured, [E] my estimate. nothing was run.

## 0. what the code does today [R]

- one omp parallel region. every thread loops: critical(seqread) { LoadBlock(3 MiB of bases); block_id = next_input_block_id++ }, classify outside the lock, push the OutputData into a priority_queue keyed by block_id, flush while top id == next_output_block_id. the output order depends only on block_id, never on where blocks are cut. so any scheme that hands out ids in file order and keeps every record in its block gives identical output.
- BatchSequenceReader copies share one kseq_t (primary_ false). AdvanceFile swaps the fd inside the shared kstream when kseq hits EOF, so all 16 files are one logical stream read by one holder at a time.
- per read under the lock after the serial fix: kernel to 16 KB kseq buffer (read syscalls), memchr + memcpy of header/comment/seq into kseq kstrings, then assign() of header, comment, seq into the thread's Sequence. quality is only counted (ks_skipline).
- input is 12.54 GB of file bytes, 6.04e9 bases, 1.87M reads, so about 3.2 kb of bases and 6.7 kB of file per read. the database size (50 MB to 103 GB) does not change this work.

rough split of the 5.0 s hold after the fix [E, not measured; re-run K2_LOCKSTAT on src_serial first, it is one command and tells us the true remaining hold]: kernel to user copy of 12.5 GB about 2.0 s, memchr scans of 12.5 GB about 0.8 s, kstring copy of 6 GB about 0.9 s, assign into Sequence of 6 GB about 0.9 s, malloc and header work about 0.3 s. total about 4.9 s, consistent with the 5.18 s wall.

wall model: wall = db load + max(serial hold, cpu bound). at 8 GB load is about 0.5 s and the cpu bound is 207/48 = 4.3 s; at 103 GB load is about 3.2 s and cpu is 258 cpu-s, bound 5.4 s. caveat: the 207 cpu-s may include omp spin time of waiting threads, so the true bound could be a little lower. the slope test supports it being real: one extra scan pass (102 cpu-s) cost 2.1 s once the threads were saturated.

## 1. option 1: raw block under the lock, parse outside

algorithm, in the lock (replace the LoadBlock body, keep a shared carry buffer and the file list):
1. buf = this thread's own raw buffer, capacity B + carry. B = 4 MiB of file bytes (output is unchanged by the block size).
2. memcpy the carry (the partial record left from the previous block, tens of kB) to buf, then read() into the rest until full or EOF (loop for short reads and pipes).
3. find the cut: count newlines n in buf with an AVX2 popcount pass (cmpeq 10, movemask, popcnt; about 10 GB/s hot, 12.5 GB total is about 1.2 s). a block that starts at a record start holds floor(n/4) complete records. the cut is after newline number 4*floor(n/4). find it by scanning backward from the end for (n mod 4) newlines, a few lines only, bounded by the last partial record.
4. carry = the bytes after the cut, saved in the shared carry buffer. block_id = next_input_block_id++. hand (buf, len) to the thread.

outside the lock, per thread: a strict parser over [buf, buf+len) that reproduces kseq exactly for 4-line records (section 5), filling the thread's seqs_. this is where the header/seq copies now happen, in parallel.

file boundaries: when read returns 0, close the fd and open the next file (AdvanceFile logic). a leftover partial record at the end of a file goes to a final small block parsed with the real kseq path.

serial time: read() 2.0 s + count 1.2 s + bookkeeping 0.1 s = about 3.3 s per 12.5 GB, down from about 5.0 s. that is below the 4.3 s cpu bound at T=48, but the lock runs at about 70% utilisation, which costs some queueing at ramp-up.
expected wall: 8 GB db about 4.7 to 5.0 s (now 5.18 s), 103 GB db about 8.6 to 8.9 s (now 9.1 to 9.4 s). gain is only 0.3 to 0.5 s at T=48. at T=96 the cpu bound is about 2.2 s, so the 3.3 s hold becomes the floor again: option 1 does not scale to the full 96-core box.
code sites: seqreader.h LoadBlock (lines ~104-120) plus a new ParseBlock; classify.cc ProcessFiles lines ~505-520 (the critical block must return a raw span, the per-thread parse call goes after the lock); copy_from_kseq stays for the paired-end LoadBatch path.

## 1b. variant of option 1: no lock at all (offset partition), the recommended core

the lock exists only to find where the next record starts. for a regular file each thread can do that locally, so the read() leaves the lock too.
1. at start fstat all 16 files (regular files only) and build prefix sums nblocks[f] = ceil(size_f / B). global ticket t = atomic fetch_add; block_id = t; (file f, chunk k) comes from a binary search on the prefix sums. this is the same monotone id space the output queue already uses, so next_output_block_id and the priority_queue stay unchanged.
2. thread for chunk (f,k): start s_k = find_start(f, k*B), end s_{k+1} = find_start(f, (k+1)*B), with s_0 = 0 and s_k = size when k*B >= size. pread [k*B, (k+1)*B + slack) and extend the pread while find_start has not succeeded and not EOF (a nanopore read can be 2 MB of file).
3. find_start(p): the first line start L >= p (L == p only if p == 0 or byte p-1 is '\n') with buf[L] == '@' and the line at L+2 starting with '+' (and len(line L+1) == len(line L+3) after CR strip as a second check). for valid FASTQ this is unique: a quality line that starts with '@' is followed by a header line and then a sequence line, which never starts with '+', so the L+2 test rejects it.
4. both neighbours call the same deterministic find_start on the same bytes, so chunk k's end equals chunk k+1's start by construction. an empty chunk (no record start inside) must still push an empty OutputData with its block_id, otherwise next_output_block_id stalls. today `if (! ok_read) break` skips that; the new loop needs: ticket >= total means break, empty block means push empty output and continue.
5. runtime guard: the strict parser must consume exactly [s_k, s_{k+1}) with every record valid (starts '@', 3rd line starts '+', seq length == qual length), else abort with a clear message and nonzero exit (never silently differ).
serial time: about 0 (one atomic per block). the cost moves to the parallel threads: pread of 12.5 GB (about 2 cpu-s total), scans, parse copies (about 2 cpu-s). none of it is new cpu, it was serial wall before.
expected wall: 8 GB db about 4.5 to 4.8 s, 103 GB db about 8.5 to 8.8 s at T=48, and it keeps scaling at T=96 (estimate 2.9 to 3.2 s at the 8 GB db), where options 1 and 4 and the current floor cannot.
risks specific to 1b: needs regular files (stdin or pipes fall back to option 1 or the old path); the unique-start rule assumes sequence lines never begin with '+' or '@' (true for DNA, and the guard catches violations); many threads pread the same files (shared page cache lock, expect fine, 16 files help).

## 2. option 2: pread into a ring of big aligned buffers, no O_DIRECT

the 16 KB read loop is not the cost [M]: a 1 MiB kseq buffer was 2 to 4% slower (rd.csv). the kernel copy of 12.5 GB is bandwidth, not syscall count (about 370 syscalls per 6 MiB block at about 1 microsecond each is 0.4 ms of 3 ms). big aligned reads only help if the copy happens off the lock. by itself this is a null to slightly negative and it is just a component of 1 and 1b. rank last standalone. expected wall about 5.1 to 5.3 s at 8 GB (no gain).

## 3. option 3: parallel per-file readers, key (file index, block index)

design: 16 per-file reader states (own kseq, own omp lock). a thread does omp_test_lock round robin over files with data left, so it never waits on a busy file; the per-file hold is about 5.0/16 = 0.3 s, trivially hidden. block key = (f, i). the comparator becomes lexicographic and next_output becomes a cursor (f, i). to move the cursor from f to f+1 the output side needs n_blocks[f], known only when file f hits EOF: the EOF thread publishes it under output_lock (array of atomics, UINT64_MAX until known). a finished block of a later file just waits in the queue (total output is under 0.5 GB). code sites: ProcessFiles lines ~484-520 (reader set, loop, the block_id type in OutputData), the comparator at line ~478, the flush loop after critical(output_queue). BatchSequenceReader needs a per-file constructor and no AdvanceFile.
serial time: about 0.3 s per file, in parallel. expected wall: close to 1b, 8 GB db 4.5 to 4.8 s, 103 GB db 8.5 to 8.8 s; concurrency capped at 16 readers, which is fine at T=48 and probably fine at T=96.
weak points: only helps multi-file input (one big FASTQ, stdin and the paired-end paths are unchanged), lets late files finish before early ones (more queued output, bounded by memory, not a correctness issue), and the cursor logic is new concurrency code where a bug means a hang. its real strength: the parse is today's kseq, so FASTA, CRLF and multi-line behave identically for free, zero parser risk.

## 4. option 4: cut the remaining copies in the serial section

the cheapest. kseq copies header/comment/seq into its own kstrings, then copy_from_kseq assign()s them again. std::string cannot adopt a malloc buffer, and handing kseq a std::string buffer via realloc is undefined behaviour, so a true swap is out. instead: a ReadRecordDirect(Sequence&) in seqreader.h that uses the same kstream and fast-paths the common case: when the whole header line and the whole sequence line sit inside ks->buf (memchr finds '\n'), assign() straight from ks->buf into the Sequence (one copy), and only if a line spans the 16 KB buffer fall back to the real kseq_read for that record. rules to copy: name ends at the first isspace byte (space, tab, \r, \v, \f); comment is the rest of the line after that one byte; trailing '\r' is stripped from the comment only if its length > 1 and from the sequence only if its length > 1. keep the skip-quality switch.
saves one 6 GB memcpy and the kstring realloc churn: about 0.8 to 1.0 s of hold, so hold about 4.0 s. expected wall: 8 GB db 4.7 to 4.9 s, 103 GB db 8.8 to 9.0 s. effort a few hours, low risk because the fallback is the real kseq.
sites: seqreader.h LoadBlock (call the new function instead of kseq_read + copy_from_kseq); copy_from_kseq stays.

## 5. faithful kseq semantics for the strict parser (options 1, 1b)

per record, lines l1..l4 (a line ends at '\n' or EOF):
- l1 must begin '@' (else not strict). name = bytes after '@' up to the first isspace byte. if that byte is '\n' (or EOF) the comment is empty and the line ends. otherwise comment = bytes from the next byte to the end of line, with one trailing '\r' removed only if the comment length > 1 (so "@id \r\n" keeps comment "\r"; "@id\r\n" gives name "id" and an empty comment because the '\r' itself was the delimiter).
- l2 = the sequence, one line, trailing '\r' removed when its length > 1. an empty l2 is allowed (kseq skips blank lines, so l2 empty then a '+' line is the same record with length 0). if l2 starts with '+', '>' or '@' it is not strict.
- l3 must start with '+' (the rest is ignored). l4 = quality, trailing '\r' removed when length > 1, length must equal the sequence length or kseq returns -2.
- format flag: FASTQ iff quality length > 0, so an empty-sequence record is flagged FASTA exactly as copy_from_kseq does today (the qual.l > 0 test). replicate it or the c1/u1 text differs.
- any non-strict shape (blank lines between records, multi-line sequence, '>' record, junk before the first '@') means that file uses the old kseq path from the start. a sniff of the first 64 records at open decides; the runtime guard in 1b catches later violations with an abort.

## 6. risks and edge cases

- FASTA and multi-line records: kseq joins sequence lines until '>', '+' or '@'; counting 4 newlines is wrong for them. the sniff fails, old path. the guard aborts rather than mis-parse.
- CRLF: newline counting is unaffected (the '\r' is just a byte); the parser's '\r' rules above must match, including the length quirks. most likely source of off-by-one, test it first.
- paired-end: uses LoadBatch with record counts and a second reader; leave it on the old path (guard on opts.paired_end_processing). do not touch r2.
- gz input: this build reads raw fds and has no gz support, so a gz file already fails the same way. the sniff sees a non-'@' first byte and takes the old path.
- last record without a trailing newline: accept an unterminated final l4 as a line end (kseq does). in 1b the last chunk ends at file size; in 1 only the final partial line counts as a newline, and only at EOF.
- records spanning chunk boundaries: carry (1) and find_start extension (1b); test with B = 4 KiB and 64 KiB on 100 kB reads.
- very long reads: the carry or pread slack must grow, never assume a maximum length.
- -Q, --classified-out and --unclassified-out need quality: keep the K2_KEEPQ safety switch, the parser copies quality when set.
- file_format_ is shared mutable state written per record today; make it per-thread in the strict path.
- an fd that fails to open acts as empty today (AdvanceFile continue); keep that.
- stats and report depend only on read content, not on block cut points.

## 7. unit-test plan

1. host-side harness (no kraken needed): link the old kseq path and the new parser into one binary; for each of the 16 input files stream all records with both and compare record by record: header, comment, seq, qual (when kept), format flag. count and FNV-hash both streams; any mismatch prints the record index and byte offset.
2. boundary sweep: run the new splitter with B in {4 KiB, 64 KiB, 1 MiB, 3 MiB}, and B = 1..4096 on small synthetic files (every offset class); the concatenation of block outputs must equal the old stream exactly, no lost or duplicated record.
3. synthetic edge files: CRLF (including "@id \r" and 1-base reads), no trailing newline, empty-sequence record, quality line starting with '@' and with '+', blank lines, junk before the first '@', multi-line FASTA, '>' FASTA, a 2 MB read, a file of exactly B bytes, an empty file, a one-record file. each compares old vs new or checks the documented fallback or abort.
4. end to end: kraken2 per-read output and --report md5 against the previous best build at T=1, 48 and 96, 50 MB and 8 GB dbs, with and without -C/-U (1,000-read cut) and -Q, all 16 files, plus a single-file run and a stdin run (these must take the old path and match).
5. repeat the 5-run interleaved timing and K2_LOCKSTAT on the new build so the hold is measured, not estimated.

## summary (6 lines)
1. the floor is the lock holder copying 12.5 GB about five times; after the serial fix the wall (5.18 s) is still about 0.5 to 0.9 s above the cpu bound (about 4.3 s).
2. option 4 (direct copy from the kseq buffer, real kseq fallback): a few hours, low risk, wall about 4.7 to 4.9 s at 8 GB and 8.8 to 9.0 s at 103 GB.
3. option 1 (raw read plus newline count under the lock, parse outside): hold about 3.3 s, wall about 4.7 to 5.0 s, but it stops scaling past about 64 threads.
4. option 1b (offset partition, pread and parse outside any lock, global ticket as block_id): serial about 0, wall about 4.5 to 4.8 s (8 GB) and 8.5 to 8.8 s (103 GB), the only one that also scales to T=96; needs regular files and a strict-FASTQ guard.
5. option 3 (per-file readers, (file, block) key) matches 1b with no parser risk but only for multi-file input and needs new output-cursor concurrency; option 2 alone is a null.
6. all T=48 gains are small (5 to 13%), so re-measure the hold on src_serial first; the large payoff of 1b is at T=96.

ranked recommendation: (a) option 4 now, (b) option 1b with the old kseq path as fallback for non-regular, non-strict or paired-end input, (c) option 3 only if the 1b boundary rule is judged too risky, (d) option 1 as the pipe/stdin fallback, (e) option 2 never on its own.
