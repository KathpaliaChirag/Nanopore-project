# truncated and malformed fastq: making the parallel reader behave exactly like stock (cycle 4, round 1, agent C)

status: design plus an unapplied, unbuilt diff (code/truncation.diff, made with `diff -u` against copies of ~/e1/impl_pread2/src read over ssh; `patch --dry-run` applies it clean; apply from ~/e1 with `patch -p1`). nothing was run on Luna.

## 1. what stock really does (from seqreader.h, kseq.h, classify.cc in ~/e1/src_best/src)

the round 9 claim "stock silently stops reading at the first malformed record" is only true for a damaged tail. the source says:

- LoadBlock (seqreader.h line 130): `kseq_read >= 0` adds a record. any value below 0 (-1 eof, -2 error) goes to `else if (AdvanceFile()) continue; else break;`. the bad record itself is never copied (copy_from_kseq runs only on rc >= 0).
- AdvanceFile (line 182): if another file is queued, swap the fd and reset the kstream (begin=end=0, is_eof=0, last_char=0) and keep filling the SAME block. so a -2 anywhere in file 1 of 2 drops the REST of file 1 and continues with file 2. a truncated file 1 is therefore harmless: its cut record is dropped, file 2 is read whole.
- last file: break, and LoadBlock returns size_ > 0, so the partial block IS classified. the next LoadBlock call (any thread) calls kseq_read again on the same stream. after a -2 the stream sits after the lines kseq consumed and last_char is 0, so it resyncs at the next '@' or '>' byte anywhere (even inside a quality line). stock does not stop at a mid-file bad record, it drops it and carries on.
- the thread loop (classify.cc 541 to 560): a LoadBlock call that returns size_ == 0 makes that thread leave its loop for good. so a -2 on the first read of a block kills one thread. with -t 1 that loses the rest of the file. this is timing and thread-count dependent stock behaviour and cannot be reproduced by any reader that is not the kseq path.
- stats and counters: thread_stats and thread_taxon_counters are merged after each block (lines 614 to 646), only for reads that were classified. nothing is counted for a dropped record.

what each c_* case produces in stock (derived from the kseq_read code, to be confirmed by the matrix itself since the stock side already runs there):

| case | kseq_read result | stock output |
|---|---|---|
| eof_mid_qual (cut inside the last quality line) | qual shorter than seq, -2 | last record dropped, rc 0, 999 reads |
| eof_after_plus (ends at the '+', no newline) | -2 at "no quality string" | last record dropped |
| eof_after_plus2 ('+' then newline, eof) | skip-line loop gets -1, qual_len 0 != seq.l, -2 | last record dropped |
| eof_after_seq (ends after the sequence line) | c == -1 in the seq loop, `c != '+'` returns seq.l | last record KEPT as a FASTA-style read with its sequence (format flips to FASTA, so -C/-U print it with '>') |
| header only ("@h\n" or "@h") | returns 0 | kept as an empty read |
| short or long (one record, qual length off by 5, mid-file) | reads one extra line (the next '@' header) into qual, then -2 | that record and the next header line are consumed, the next record's sequence and '+' line are skipped by the resync, so 2 records are lost (more if a quality line contains '@') |

## 2. how the current reader differs and why a "first bad ticket" design does not work

today every strict failure ends in `_exit(3)`. the proposed rule "record min bad ticket t, discard all later blocks" is wrong for stock: stock does not discard anything after a mid-file bad record, it resyncs and keeps classifying. even a perfect min(t) discard would drop reads stock counts. exactness for mid-file damage means reproducing kseq's resync, which is a sequential state machine whose next record boundary can land inside a quality line, so chunk starts after the damage cannot be trusted. deferring stats and counters to the in-order release is possible (thread_stats and thread_taxon_counters could ride in OutputData and be merged by the thread that takes next_output_block_id, at the cost of a per-block map in the queue) but it does not buy exactness, so it is not needed.

## 3. the two ways to make mid-file damage exact, and the cost of each

a) restart with the kseq path after damage is seen. impossible in general: by the time ticket t is bad, blocks before it were written to the output file (or stdout), and the order of writes is the point of the writer. delaying output until the first N blocks are validated does not help, because damage can sit after the first MiB (the existing guard test [4] proves that case occurs). only a full validation before any output exists is sound.

b) pre-pass. before InitializeOutputs, every chunk is parsed with a NullSink on all threads (no Sequence allocation). a read-only strict parse costs one memchr-speed walk of the file. the input in the benchmarks is 1.87 M reads against a 7 s wall, so a warm-cache pre-pass at 64+ threads should cost low single digit percent; on a cold file it also warms the page cache for the real pass. this must be measured, not assumed. K2_PREAD_PRESCAN=0 turns it off (damage then aborts exactly as now).

## 4. recommended design: pre-pass for the whole file, exact tail replay for truncated tails, stock kseq for everything else

1. keep Plan::Init (first MiB must be strict; fails over to the kseq path as now).
2. new pre-pass (classify.cc, right after Plan::Init): `#pragma omp parallel for schedule(dynamic,1)` over all tickets, read_chunk with NullSink. any PR_BAD sets an atomic flag and `use_pread = false`, so the WHOLE run uses the stock kseq path (LoadBlock and all), which is stock by construction for every mid-file case (c_short, c_long, '@' in quality, damage after 1 MiB, thread-death quirk included). cost only for damaged files: stock speed.
3. exact tail (preadfq.h process_chunk): `can_tail = (F == fsize && b.eof)`, i.e. find_start found no strict record start after this chunk and the buffer reaches eof. the first chunk that meets damage (non-'@' byte, parse_record failure, or end-of-parse mismatch) calls `sink.tail(p, len)` with all bytes from the damage to eof and returns PR_OK. every later chunk has S == fsize and emits nothing, so there is no duplicate, and the straddle case (cut record starts in the second last chunk) works because that chunk computes F itself. damage followed by any later strict-looking record is not a tail and returns PR_BAD (pre-pass fallback), since kseq's resync might not land on that record.
4. tail replay (seqreader.h PSink::tail): copy the tail bytes into a memfd, `kseq_init` (which copies k2_skip_qual, as stock does), loop `kseq_read`. rc >= 0 adds a record with copy_from_kseq's exact format rule. rc == -1 stops. rc == -2 stops if the file is not the last file (stock's AdvanceFile drops the rest of that file) and continues if it is (stock's next LoadBlock resumes the stream). this reuses the real kseq, so there is no hand-written port to get wrong. cost only for damaged tails (a memfd and a few KB of parsing).
5. NullSink gets an empty tail(); PSink gets `last_file` (f + 1 == plan.fds.size()) and `tail_failed` (memfd_create or write failed, reported as PR_BAD so it aborts loudly rather than differ).
6. the runtime guard stays as a safety net (file modified while running, pread error): it still prints the K2_PREAD message and `_exit(3)`.

what this gives, per case:

| input | result |
|---|---|
| truncated last record, last file (eof_mid_qual, eof_after_plus, eof_after_plus2) | record dropped, rc 0, byte-identical output, report and stderr stats, parallel speed kept |
| eof_after_seq, header-only tail | kept as FASTA-style or empty read exactly like stock |
| file 1 of 2 truncated (any of the above) | tail handled with last_file = false: record dropped, file 2 read whole |
| file 1 of 2 with damage then more records in the same file | pre-pass BAD (a strict record follows), whole run on kseq path, exact |
| mid-file damage (c_short, c_long), including after the first MiB | pre-pass BAD, kseq path, exact |

## 5. what is still not reproduced, stated honestly

- stock thread-death (a -2 at a block start with few threads) and the timing dependence of which thread initialises outputs: only reachable through the kseq path, which the fallback uses, so the damaged-input behaviour on that path is stock's own. in the tail path it only matters if a resync record follows a bad record in the last file AND the bad record starts a 3 Mbase block with -t 1 (stock then loses the remainder, the replay keeps it). pure truncation (nothing after the cut) is exact for every -t.
- block boundaries: the tail record joins the last chunk's block, stock puts it in a 3 Mbase block. only the --report-minimizer-data HLL columns depend on this and that option already forces the kseq path.
- file_format_ for output initialisation follows the last record of the block that wins the race to InitializeOutputs, in stock and here alike.

## 6. validation (extend validate_matrix.sh, all against stock S19, compare rc, normalised stderr, per-read output, -C/-U, report; also run each at -t 1, 8, 48 and K2_PREAD_CHUNK in 4096, 65536, 4 MiB so cuts straddle chunk boundaries)

existing: c_eof_after_seq, c_eof_after_plus, c_eof_after_plus2, c_eof_mid_qual, c_long, c_short and their _K variants must now all PASS (rc 0, identical files).
new cases, built from base.fq (1000 reads) and a 20 MiB file made by concatenating copies (so damage can sit after the first MiB):
1. truncation sweep: cut the last record at every byte offset from its first byte to its last (about 300 files per chunk size). covers cuts after '@', mid header, after header newline, mid sequence, after sequence, after '+', mid quality, one byte short, exact end without newline (valid).
2. the same sweep with the cut record straddling a chunk boundary (choose K2_PREAD_CHUNK = file size minus half the record).
3. file 1 of 2 truncated mid-quality, after sequence (FASTA-style kept), after '+'; file 2 whole. then file 2 truncated too.
4. file 1 of 2 damaged mid-file (short qual at record 500) followed by valid records, file 2 whole: stock drops the rest of file 1 only if the damage is in the tail path, otherwise resync; both must match stock.
5. big file, short and long qual at copy 40 (after 1 MiB), at -t 1, 8 and 48 (pre-pass fallback; compare to stock).
6. damage whose resync record starts inside a quality line containing '@' (atq style), and one with '+' in a quality line.
7. truncated tail plus -C -U (FASTA-style tail record prints with '>' in classified/unclassified files) and plus --report, --use-names, --quick.
8. a file with two damaged regions, only the last in the tail (pre-pass must fall back).
9. tail-only damage in 3 files: two consecutive truncated files then a clean one.
10. control: K2_PREAD_PRESCAN=0 on a mid-file damage must still abort with exit 3 (documented, not stock-equal).
unit test (test_pread.cc): change ref_read to call LoadBlock(3 Mbase) repeatedly and stop only after two consecutive false returns (models a surviving thread, so resync after a -2 is exercised); in new_read run the NullSink pre-pass first and count a failing pre-pass as "fallback" (safe); the fuzz section must then show zero "ok but different" and the truncation sweep must show zero fallbacks (all exact through the tail).
add a perf check: time the pre-pass alone (K2_PREAD_VERBOSE print) on the 50 MB and 8 GB runs at 32, 64 and 96 threads; accept if under 3 percent of wall, otherwise default K2_PREAD_PRESCAN to run only when the file's last chunks are not clean.

## 7. summary

1. stock drops a malformed record and resyncs (last file) or drops the rest of the file (earlier files); it stops only at a damaged tail.
2. truncated tails (last or any file) can be reproduced exactly by replaying the tail through the real kseq_read on a memfd, keeping parallel speed.
3. mid-file damage cannot be reproduced by a lock-free reader (resync lands inside quality lines); "first bad ticket plus discard" is wrong because stock keeps reading.
4. restart-after-damage is unsound once output is written; a pre-pass before InitializeOutputs is the sound form.
5. recommendation: pre-pass over all chunks (damage outside the tail means the whole run uses the stock kseq path) plus exact tail replay; diff in code/truncation.diff, unbuilt and unrun.
6. needs: build, c_* matrix at three thread counts, truncation sweep, pre-pass timing under 3 percent of wall.

recommended design: pre-pass fallback to the stock kseq path for any non-tail damage, and kseq memfd replay with per-file stop rules for damaged tails.
