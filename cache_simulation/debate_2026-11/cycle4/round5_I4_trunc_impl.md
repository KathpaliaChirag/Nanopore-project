# truncated and malformed fastq: the parallel reader now behaves like stock (cycle 4, round 5, implementer I4)

status: built and validated on luna (2026-11-23). new tree ~/e1/impl_trunc (copy of impl_pread2, nothing else touched), runnable dir ~/e1/bin_trunc. diff against impl_pread2/src: code/impl_trunc.diff. updated unit test: code/test_pread_trunc.cc (result: code/test_pread_trunc_result.txt). end-to-end driver: code/i4_matrix.sh (logs: code/i4_matrix_cmb.log, code/i4_matrix_sweep.log).

## 1. what changed (three files in src/)

1. classify.cc: right after Plan::Init, a pre-pass runs read_chunk with a NullSink over every chunk on all threads (omp for, dynamic,1). if any chunk returns anything but PR_OK, use_pread is switched off and the whole run uses the stock kseq path (LoadBlock and all), which is stock by construction for every mid-file case. K2_PREAD_PRESCAN=0 turns the pre-pass off (damage then aborts with exit 3 as before). with K2_PREAD_VERBOSE it prints which chunk found damage.
2. preadfq.h process_chunk: `can_tail = (F == fsize && b.eof)`. the first chunk that meets damage (non-'@' byte, parse_record failure, or end-of-parse mismatch) hands all bytes from the damage to eof to `sink.tail(p, len)` and returns PR_OK. every later chunk has S == fsize and emits nothing, so nothing is duplicated. damage followed by a strict-looking record in a later chunk is not a tail and stays PR_BAD (so the pre-pass falls back). NullSink got an empty tail().
3. seqreader.h PSink::tail: copies the tail into a memfd, runs the real kseq_init/kseq_read loop. rc >= 0 adds a record using copy_from_kseq's exact format rule (FASTA-style when no quality). rc == -1 stops. rc == -2 stops if the file is not the last file (stock's AdvanceFile drops the rest of that file) and continues if it is (stock's next LoadBlock resumes the stream). PSink got `last_file` and `tail_failed` (memfd or write failure turns into PR_BAD, which aborts loudly, never silently different).

one change beyond the design (found while reviewing it against the real source): Plan::Init rejected the whole plan if any record inside the first MiB was not strict, including the damaged tail of a file smaller than 1 MiB. that made every small truncated file fall back to kseq, so the tail path could not be tested on small chunk sizes and would not be used for small files. now Init only rejects when the first record is unreadable (nrec == 0); a failing record later in a file that fits in the first MiB just stops the scan, and the pre-pass plus tail replay decide. the design diff compiled and applied clean otherwise; no other defect was found in it. one consequence worth knowing: a mid-file damage in a file that is a single chunk (file smaller than the chunk size) is also a "tail" (F == fsize), so it is replayed through kseq inside the parallel reader instead of falling back. that is still exact (same kseq, same per-file stop rules), and the unit test and the e2e cases cover it (c_short and c_long at chunk 65536 on a 5.8 MB file are multi-chunk, big_*_bigchunk cases in the unit test are single-chunk).

## 2. unit test (test_pread_trunc.cc, build: `g++ -O2 -std=c++17 -I src test_pread.cc -o test_pread -pthread`, run with nice -n 10)

changes as designed: ref_read calls LoadBlock repeatedly and stops after two consecutive false returns (models a surviving thread); new_read runs the NullSink pre-pass first and counts a failing pre-pass as a safe fallback (status 3); the old [3] rejection test now accepts "plan or pre-pass rejects, or identical when the whole file was one replayed tail chunk". new section [7]:

- 7a: byte-by-byte truncation sweep of the last record, behind a 1.4 MB prefix (cut is after the first MiB), 3 record variants (plain, '@' first quality byte, '+' first quality byte), 11 chunk sizes each including boundaries inside the cut record, boundaries that put the cut record in the second to last chunk, 4 KiB, 64 KiB, 1 MiB, 4 MiB. plus the same sweep on a tiny file with chunk sizes 1 to 80 and a zero-length-sequence record. all must be accepted by the pre-pass and identical (want = 0).
- 7b: truncation in file 1 of 2, in the last file, in two consecutive files, two then a clean file, clean then two (5 chunk sizes each, cuts every 5 bytes), plus big (past 1 MiB) multi-file runs with the cut after the sequence line, after '+', mid quality.
- 7c: mid-file damage after the first MiB (short quality, long quality, junk line, extra short record), in a single file, in file 1 of 2, in the last file, and combined with a truncated tail (two damages). with chunks 4096 and 65536 the pre-pass must fall back (asserted); with 1 MiB and 4 MiB any outcome must equal the reference.
- 7d: small files with '@' or '+' as the first quality byte of every record and one damaged record in the middle (short, long, valid control, dropped '+', dropped quality line), with and without a truncated tail.

results (run 3, all sections incl. real data [6] on 3 pod5 files; real data reading was already part of the old test): pass=35214 fail=0, PASS. 26136 damaged runs were accepted by the pre-pass and identical to the kseq reference, 976 fell back in section 7 (all of them the ones asserted to fall back or allowed to), 1148 total fallbacks. extra fuzz runs with a larger section [5] (TEST_SEED and FUZZ_N env vars added to the test): seed 12345 with 8000 fuzz iterations: pass=42609 fail=0; seed 777 with 8000 iterations: pass=42609 fail=0. no "ok but different" anywhere. zero fallbacks in the truncation sweeps (7a big sweep and 7b), so every pure truncation goes through the exact tail path.

## 3. end-to-end vs stock S19 (code/i4_matrix.sh)

setup: db sample_targeted, inputs under /dev/shm/i4_* (base.fq = first 1000 reads of pod5_0, 5.8 MB; pre.fq = 300 reads, 1.49 MB; m1/m2/m3 = 100 reads each), stock ~/chirag_K/tools/kraken2-fresh-bin-s19/kraken2 vs ~/e1/bin_trunc/kraken2. every case runs at -t 1 and -t 8 (stock once per thread count, new once per chunk size 4096 and 65536 per thread count). compared per run: exit code, stderr (with timings stripped), per-read output, classified/unclassified files, report sorted and report in exact line order. every one of the 428 non-sweep comparisons plus 1350 sweep comparisons is byte-identical.

| case group | inputs | option sets | configs per case | result |
|---|---|---|---|---|
| c_eof_midq, c_eof_aplus, c_eof_aplus2 (validate_matrix c_eof_mid_qual, c_eof_after_plus, c_eof_after_plus2) | last record cut inside quality, at '+' without newline, after '+' line | plain, -K (--report-minimizer-data --report-zero-counts), --use-names, --quick, -C -U | 4 chunk/thread configs x 2 thread counts of stock | all PASS, rc 0, 999 reads |
| c_eof_aseq (c_eof_after_seq) | cut after the sequence line (kept FASTA-style) | same 5 | same | all PASS, rc 0, 1000 lines, -C -U shows the '>' record in the classified/unclassified files |
| c_eof_hdr, c_eof_hdr2 (header-only tail, with and without newline) | new | same 5 | same | all PASS |
| c_short, c_long (qual length off by 5 at read 500) | validate_matrix originals | same 5 | same | all PASS (pre-pass falls back at chunk 4096/65536 on a 5.8 MB file) |
| c_atq_short, c_atq_long, c_plq_short, c_atq, c_plq | '@' or '+' as first quality byte of every read, with and without the damage (resync can land inside a quality line) | same 5 | same | all PASS |
| multi_trunc_file1_{midq,aplus,aplus2,aseq,hdr} | file 1 of 2 truncated, file 2 whole (also with -C -U) | plain + CU | same | all PASS |
| multi_trunc_lastfile_*, multi_trunc_two_*, multi_trunc_two_last_* | last file truncated; files 1 and 2 truncated then clean file 3; files 2 and 3 truncated | plain | same | all PASS |
| multi_trunc_mixed | three files truncated three different ways | plain | same | PASS |
| multi_damage_file1_short, multi_damage_lastfile_short, multi_damage_both, multi_damage_then_trunc | mid-file damage in a multi-file run, also combined with a truncated tail | plain | same | all PASS |
| multi_big_trunc_file1, multi_big_trunc_lastfile | cut file is past 1 MiB | plain | same | PASS |
| big_short_big, big_long_big, big_junk_big, big_atq_short_big | damage after the first MiB (read 250 of 300) | plain | same | all PASS |
| big_short_big_tailcut, big_long_big_tailcut, big_atq_short_tailcut | two damages: mid-file plus a cut tail | plain | same | all PASS |
| big_short_aseq, big_short_two_files, big_short_lastfile | damage then truncation; damage in file 1 or last file of 2 | plain | same | all PASS |
| truncation sweep | file of 1.1 MB prefix + a 269 byte last record, cut at all 270 offsets (after '@', mid header, after header newline, mid sequence, after sequence, after '+', mid quality, one byte short, exact end) | plain | 5: chunk 4096 t8, chunk 65536 t1, chunk (prefix+100) t8 (boundary inside the cut record), chunk 4096 t1, chunk (prefix+7) t1 | 1350 identical, 0 different |

repeat of the c, multi, big groups with K2_BULK=1 (the setting used by the benchmark builds): 428 pass, 0 fail. control (K2_PREAD_PRESCAN=0, damage after the first MiB, chunk 4096): exit 3 with the K2_PREAD message, as documented (not stock-equal by design). negative control: the same big group run with ~/e1/bin_pread2 (the old reader): 40 of 40 comparisons FAIL, so the matrix does discriminate.

verbose check: on a truncated tail K2_PREAD reports "on (ok)" (the parallel reader is kept); on mid-file damage it reports "prescan found damage in chunk N" and "off, using kseq path (prescan found damage)".

so: every c_* case (c_short, c_long, c_eof_after_seq, c_eof_after_plus, c_eof_after_plus2, c_eof_mid_qual and the _K variants) is now byte-identical to stock at -t 1 and -t 8, chunks 4096 and 65536.

## 4. pre-pass cost estimate (one measurement pair, tiny db, not real data)

synthetic file: 17 copies of the 1000 read base, 98.4 MB, 17000 reads, in /dev/shm (warm), db sample_targeted, bin_trunc, --threads 8, luna loaded by other users (load average 10 to 20 during the runs). two repeats each: prescan on: wall 0.30 s and 0.31 s, classify time 0.256 s and 0.255 s; prescan off: wall 0.30 s and 0.29 s, classify time 0.247 s and 0.245 s. so the pre-pass costs about 0.008 to 0.01 s per 100 MB at 8 threads on warm cache (about 1 GB/s per thread level, memchr-speed walk), which is about 3 percent of this deliberately tiny wall (db load plus classification of a 50 MB db is almost free) and is a fixed cost per byte, so against the real 7 s wall at 1.87 M reads it extrapolates to well under 1 percent (a 103 GB-db run reads the same fastq). this is an estimate from n = 2 on a noisy machine, not a measurement on real data. the design asked for under 3 percent of wall on the real runs; still to be confirmed on the big data (command below). on a cold file the pre-pass reads the file once from disk, which also warms the cache for the real pass.

## 5. known remaining differences from stock

1. stock thread death and block boundaries. a -2 at the start of a block kills one stock thread, and which thread initialises the outputs is racy. only reachable when damage is followed by more valid records AND the bad record starts a 3 Mbase block AND few threads; the damaged-input path in that case is the kseq path (fallback), i.e. stock's own behaviour, except in the single-chunk tail case (file smaller than K2_PREAD_CHUNK, default 4 MiB, or the last chunk of a file), where the replay keeps the surviving-thread behaviour. the e2e cases at -t 1 and -t 8 showed no difference, but the matrix cannot force that stock race.
2. block boundaries in a replayed tail: the tail records join one block instead of stock's 3 Mbase blocks. only the --report-minimizer-data HLL columns depend on that, and that option already forces the kseq path.
3. K2_PREAD_PRESCAN=0 (off switch) keeps the old loud abort (exit 3) on non-tail damage. default is on.
4. the runtime guard stays as a safety net for the file changing while running or a pread error (exit 3, message names K2_PREAD=0).
5. FASTA input, compressed input, stdin, paired-end and report-minimizer-data never used this reader and are unchanged.
6. fuzz coverage is random, not exhaustive; the only race-dependent stock behaviour (item 1) is the one thing the models (surviving thread reference) deliberately do not claim to match.

## 6. exact command to benchmark on the big data later

build and runnable dir already exist (rebuild only if the source changes):
`cd ~/e1/impl_trunc/src && touch classify.cc seqreader.cc && nice make -j4 classify && cp classify ~/e1/bin_trunc/classify`

pre-pass cost on the real input (run in the usual benchmark slot, same db, same thread counts as the bin_pread2 sweep; run prescan 0 and 1 interleaved, 3 repeats each, report the min wall and K2_PREAD_VERBOSE once):
`for rep in 1 2 3; do for ps in 0 1; do env K2_BULK=1 K2_PREAD_PRESCAN=$ps /usr/bin/time -f "prescan=$ps wall=%e" ~/e1/bin_trunc/kraken2 --db <db> --threads <T> --memory-mapping --output /dev/null --report /tmp/r.$ps.$rep <1.87M read fastq>; done; done`
accept if the prescan=1 wall minus the prescan=0 wall is under 3 percent of wall at T in 32, 64, 96 and the two reports/outputs are identical. also rerun cycle 3's code/validate_matrix.sh with BINS=(~/e1/bin_trunc) and ENVS=(K2_BULK=1): the 18 previous c_* failures should now be PASS.

## 7. summary

1. design applied (pre-pass fallback plus exact kseq tail replay), it compiled with no code fix; one extra fix: Plan::Init no longer rejects a small file for a damaged tail, so tails are exact at every chunk size.
2. unit test: 35214 pass, 0 fail (plus two 8000-iteration fuzz runs, 42609 pass each); truncation sweeps had zero fallbacks and zero differences.
3. end to end vs stock S19: 428 case comparisons plus 1350 sweep comparisons (270 cut points x 5 configs), all byte-identical in rc, stderr, per-read output, -C/-U files, sorted and exact report; also with K2_BULK=1; bin_pread2 fails all 40 of the same big comparisons.
4. pre-pass cost estimate: about 0.01 s per 100 MB at 8 threads, warm (n = 2, tiny db); under 1 percent extrapolated, to be confirmed on the big data.
5. remaining differences: only stock's racy thread-death quirk and block boundaries of a replayed tail; K2_PREAD_PRESCAN=0 keeps the old abort.
6. every c_* case (and the _K variants) is now byte-identical to stock: yes.
