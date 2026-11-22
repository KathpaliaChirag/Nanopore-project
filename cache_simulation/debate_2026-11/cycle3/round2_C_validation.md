# cycle 3 round 2, agent C: validation plan for the four stacked patches

scope: stock S19 vs (1) hll guard, (2) prefetch dedup, (3) serial-section fix, (4) 48 threads. sources read: kseq.h, seqreader.h, classify.cc, reports.cc, the kraken2 wrapper in ~/e1/src_serial/src and ~/e1/bin_serial. nothing was run. the script is code/validate_matrix.sh (syntax-checked with bash -n, generator checked with perl -c, not executed).

## 0. facts about this build that shape the plan

- no zlib in the classifier. seqreader.h reads a raw fd with read(). gz and bz2 work only because the perl wrapper (`--gzip-compressed`, `--bzip2-compressed`) opens `gzip -dc file |` and passes `/dev/fd/N`. so patches see a pipe, where read() returns short chunks. that makes gz a free buffer-refill test.
- the wrapper has `--paired` (classify -P, two files) but no flag for `-S` (single_file_pairs, interleaved). interleaved is only reachable by calling `classify` directly. the script does that (cases d07 to d10).
- stdin: the wrapper needs a filename, so stdin means `/dev/stdin`. classify with no filenames reads fileno(stdin), a path the wrapper never uses.
- the skip flag k2_skip_qual() is a process global set in ProcessFiles before the readers are built, so it is per run and per file pair. -O (kraken output) does not need quals. `seq1->to_string()` is called for every read even without -C/-U, but the string is only written if a classified/unclassified stream exists, so a FASTQ record with empty quals never reaches a file.
- report map is `std::map<taxid_t, READCOUNTER>` and KrakenReportDFS sorts children with std::sort and a comparator that treats a missing map entry as "after all present entries" (reports.cc lines 219-230).

## 1. what each patch can change, by input or option (section a)

legend: P1 hll guard, P2 prefetch dedup, P3 serial section, P4 48 threads. "same" means identical by construction and the script still checks it.

| input or option | patches touched | can output differ? | script cases |
|---|---|---|---|
| FASTA multi-line | P3 (kseq returns before the skip branch: c != '+') | no, skip branch unreachable. file_format_ and quals handling in copy_from_kseq is the only change | c_fa_ml, c_fa_1l, b06 |
| CRLF | P3 (ks_skipline strips one trailing 13) | only if the strip differs from ks_getuntil2, see section 2. confirmed same except a pathological case | c_crlf, c_crlf_nonl*, bnd_*_1_*, d07 |
| FASTQ empty reads | P3 (qual_len 0 so format becomes FASTA as in stock), P2 (no minimizers) | no | c_empty, d22 |
| '@' (also '+', '>') starting a quality line | P3 | no: the quality loop is line based in both | c_atq, c_atq_all, c_plq, c_gtq, b08 |
| last record without newline | P3 (EOF path in ks_skipline) | no, see section 2 | c_nonl, c_crlf_nonl, c_crlf_nonl2, c_fa_ml_nonl, c_eof_* |
| paired two files | P3 (LoadBatch uses same kseq_read), P2, P1 | no | d01 to d06, d16 |
| interleaved -S | P3 (LoadBatch(2*N)), P2, P1 | no | d07 to d10 (direct classify) |
| gz, bz2 | P3 (pipe, short reads) | no | d13 to d16 |
| -Q | P3 (skip off by construction), P2, P1 | no | b01, b02, b08, d03, d10 |
| -C / -U (and paired '#') | P3 (skip off) | no | b03 to b07, b09, d02, d09, d12 |
| --report-minimizer-data (-K) | P1 (guard off, add_kmer runs) | no, exact report must match | a04, a05, a11, a21, every c_*_K, d06 |
| plain --report | P1 | report line order of tied siblings can change, content cannot. section 3 | a01 and almost all cases, WARN logic in cmp_dirs |
| --use-names | none | no | a02 |
| --report-zero-counts (-z) | P1 | yes, order of zero-count siblings changes (stock puts taxa that had hits first) | a03, a14, a15 |
| mpa style | P1 | clade counts only, no | a06, a07 |
| --confidence | P2 (hit_counts unchanged) | no | a08 |
| --minimum-hit-groups | P2 (minimizer_hit_groups counted in resolve loop, unchanged) | no | a09 |
| --quick | P2 (goto finished_searching leaves fill state in dead locals) | no | a10, a11, a20 |
| translated search | P2 (6 frames, fill_last reset per frame, same as last_minimizer) | no by code reading, untested because no protein db was seen | e_prot_* if PROT_DB set |
| --memory-mapping | none of the patches, but loads change page timing | no | a12, f07 |
| multiple input files | P3 (AdvanceFile resets last_char and stream, qual_len reset at start of kseq_read) | no | d11, d12 |
| stdin / pipe | P3 (short reads) | no | d17 to d22 |
| T=1 vs 48 | P4 | no: per-read output is written in block order. only the report map merge order differs, and std::map is ordered by taxid | a17, a18, f08 |
| capped db (standard_8gb, 16gb) | P2 min-hash skip (idx=0) | no | f01 to f08 |
| N, lowercase, IUPAC, homopolymer | P2 (ambiguous and repeat paths) | no | a19 to a21, f05 |
| -D daemon mode | P3 sets the flag per ProcessFiles call | not tested, needs a fifo session | out of scope, flagged |

## 2. ks_skipline vs ks_getuntil2 (section b)

compared line by line against the original quality loop `while (ks_getuntil2(ks, KS_SEP_LINE, &qual, 0, 1) >= 0 && qual.l < seq.l);`.

what matches:
- loop control. both call once per line and stop when accumulated length >= seq.l. ks_skipline returns -1 only when no byte was consumed and the stream is at EOF, exactly like ks_getuntil2's `!gotany && ks_eof`. an empty quality line returns 0 and the loop continues in both, so a short or blank quality line swallows following lines identically (including a following '@' header line).
- empty read (seq.l = 0): one call, returns 0 in both, kseq_read returns 0, copy_from_kseq sees qual_len 0 and qual.l 0 and picks FASTA in both. stock quirk preserved. at EOF right after the '+' line both return a valid empty read.
- EOF mid-record: tot < seq.l then -1, loop ends, `seq.l != ql_` returns -2, last_char already 0. same as stock (-2). LoadBlock treats -2 as a failed read and then calls AdvanceFile, same as stock, so the rest of that file is dropped identically.
- qual longer than seq in one line: -2 both. qual wrapped over several lines: summed the same.
- last line without newline: i == end, `begin = end+1`, next iteration refills, read returns 0, is_eof set, break with gotany=1, returns tot. same state as ks_getuntil2 (begin > end is tolerated by ks_eof).
- CR strip. stock strips one '\r' from the accumulated string when its length > 1. skip strips one when `tot > 1 && lastc == 13`. lastc is the last byte of the current line, updated per chunk with `if (i > begin)`, so a '\r' at the end of buffer n followed by a lone '\n' at the start of buffer n+1 keeps lastc = 13 (the empty second chunk does not overwrite it). correct. the boundary files bnd_* test offsets -3..3 around byte 16384, with the "\r\n" and the quality line start on the boundary, and the d19/d20 chunked pipes (37 and 1 bytes) test every position.
- return codes -1/-2 and seqreader.h: LoadBlock and LoadBatch only test `>= 0`, so -1 and -2 are the same to callers. unchanged.
- qual_len is reset at the top of every kseq_read, so AdvanceFile (which does not reset it) is safe.

deviation found (theoretical, no real data hits it): the stock strip looks at the last byte of the accumulated string, not the current line. a quality that ends in two '\r' (`...I\r\r\n`) is stripped once, leaving a '\r'. if a following continuation line is empty (`\n`), stock strips a second '\r' while skip does not (lastc is 0 for that call). effect: a different length comparison against seq.l, so one build could return a read and the other -2. needs a wrapped quality with consecutive CRs and an empty continuation line, which is not valid FASTQ. case c_crcr covers the single-line variant (equal) and does not reach the divergent one. cheap exact fix: carry lastc across calls via a field (`ks->lastc`) instead of a local, or test `tot>1` only; not needed to ship.

not a bug but note: when skip is on, quals is cleared (`seq.quals.clear()`), never used because -Q, -C, -U all disable skip. `K2_KEEPQ` is only read in classify.cc, so any other binary that links kseq.h (build_db, k2mask) keeps skip_qual 0 via the static default.

no concrete semantic bug found in ks_skipline.

## 3. hll guard (section a/ P1): a real behaviour change

stock: for every hit group `curr_taxon_counts[taxon].add_kmer(min)` creates a map entry (readCount 0) for each taxon that had a hit. guarded build creates entries only through incrementReadCount (called taxa). consequences in reports.cc:
1. KrakenReportDFS children comparator: absent entry sorts after any present entry, present-with-zero before absent. without -z zero-count clades are not printed, so only the relative order of tied nonzero siblings can move. std::sort is insertion sort for 16 or fewer elements (stable for equal keys) so nodes with at most 16 children are unaffected. nodes with more than 16 children (large genera, the root of a big db) go through introsort, whose order of equal elements depends on the other elements, so tied lines can permute.
2. with `--report-zero-counts` zero-count taxa are printed, and the stock ordering (taxa that had hits first) is gone: those lines reorder at every node. case a03, a14, a15.
3. -K is untouched (guard on), content cannot change: distinct and total minimizer counts, rank and taxid lines are the same set of lines.

so "report identical" must be defined as: sorted report identical (mandatory) and exact order identical (reported as WARN). the cheap exact repair is to keep the map entry without the HLL: in the guarded branch write `else if (!opts.report_filename.empty()) curr_taxon_counts[taxon];` (operator[] only, no add_kmer). that restores the same key set, so stock order is reproduced exactly, and costs one map lookup per hit group on report runs only. recommend measuring it; if within noise, ship it and the WARN class disappears.

## 4. prefetch dedup (section c)

traced every read of pf[i].hc and pf[i].idx. they are read only inside `if (pf[i].min != last_minimizer)` in the resolve loop (hc for the cap test and GetAt, idx for GetAt). fill() skips hash and prefetch when `min == fill_last`, and sets idx=0 for capped keys. conditions that make the two sides agree:
- both are declared inside the frame loop (`last_minimizer` and `fill_last` next to each other), so translated search resets both at each of the 6 frames and each mate. no state leaks between frames or mates.
- ambiguous entries touch neither variable on either side, and the resolve loop ignores hc/idx for them. a pattern m, N, m is a repeat for both (resolve reuses last_taxon, fill skips).
- fill order equals resolve order (batches are filled in sequence and resolved in sequence), and fill_last persists across fill() calls in a frame, so batch boundaries do not break the mirror.
- quick-mode `goto finished_searching` abandons the frame: the next fill may have prefetched, but nothing persists. last_taxon/run state are untouched by the patch.
- capped db: fill sets idx=0 for hc < minimum_acceptable_hash_value; the resolve loop checks the same hc against the same value and never calls GetAt, so idx 0 is never used. fill_last is still updated for skipped keys, as last_minimizer is in resolve (it is set after the skip decision).
- initial sentinel UINT64_MAX is the same on both sides, so even a real minimizer equal to it behaves the same.
- stale hc/idx left in a reused PfSlot is harmless because a slot's repeat flag is implied by `min == previous non-ambiguous min`, which the resolve loop evaluates identically.

result: no case found where hc/idx of a skipped or repeat entry is read. residual risk is only a future edit that reads hc for an ambiguity or stats path. translated search is the one path with no byte test on this machine (no protein db seen), hence PROT_DB in the script; the tiny protein db can be built from a few proteins with kraken2-build --protein.

## 5. test matrix: exact commands (section d)

setup on luna (no kraken2 is run by me):
`bash ~/e1/validate_matrix.sh 2>&1 | tee ~/e1/validate_matrix.log`
optional: `PROT_DB=/path/protdb T=8 bash validate_matrix.sh`. scratch lives in /dev/shm/vm_PID (about 120 MB, deleted inputs at the end, results kept in /dev/shm/vm_PID/res for diffing).

per case the script runs stock S19 (`~/chirag_K/tools/kraken2-fresh-bin-s19/kraken2`) and four builds: bin_hll (P1), bin_dedup (P1+P2), bin_serial (P1+P2+P3), bin_serial with `K2_KEEPQ=1` (control: if only the last two differ from stock then P3 skip is the culprit, if all do then P1/P2). each runs `kraken2 --db DB --threads T --output o.out --report o.rep OPTS INPUTS`. compared: exit code, normalised stderr (timing removed), o.out (cmp), every classified/unclassified file (cmp), file set, report sorted (cmp) and report exact (WARN if only the order differs).

expected output: every line `PASS <case> [db] <build>: IDENTICAL lines=N rc=0`. lines=0 for a case that should classify reads means the input was lost (for example a wrapper auto-detect consuming stdin): investigate. expected rc is non-zero only where stock is also non-zero (the check is equality).

| group | cases | expected |
|---|---|---|
| A options, 21 cases on 1000 real reads, tiny sets and special sequences | a01 to a21 | IDENTICAL; WARN allowed only on exact report order (a01, a03, a14, a15, a16 expected to show it before the P1 fix in section 3) |
| B quality handling | b01 to b09 | IDENTICAL for o.out and classified/unclassified files. these also prove the skip switch |
| C input syntax, 31 input files, each plain and with -K -z, plus 28 boundary files | c_* | IDENTICAL (errors such as short/long: stock exits the same way, the equality of rc and stderr is the pass) |
| D paired, interleaved, multi, gz, bz2, stdin, chunked pipes | d01 to d22 | IDENTICAL |
| E translated | e_prot_* | IDENTICAL if PROT_DB, else SKIP line |
| F capped dbs 8 GB and 16 GB, 8 cases each | f01 to f08 | IDENTICAL (about 3 minutes extra for loads) |

every build also has to be re-checked at scale before shipping, using the earlier 4 db sweep: `cmp` of full per-read output at T=48 against stock at T=32 on 50 MB, 8 GB, 16 GB, 103 GB (already done for the serial build in data/ser_correct.txt; repeat for the final stacked build, plus `sort | cmp` of reports).

## 6. residual risks and what is not covered

- section 3 order change is real. decide: add the one-line map touch, or define the contract as sorted-report equality and document it.
- the extremely rare double-CR deviation in section 2 is not reached by valid FASTQ.
- -D daemon mode, bzip2 via stdin, FASTQ longer than 2 GB per record ((int) cast in ks_skipline return), and databases with a minimum_acceptable_hash_value we did not identify are not covered. section G in the script prints opts.k2d words so the cap in each db is visible.
- P4: the sweep showed 64 and 96 threads slower and 48 best on this host. byte equality across T=1/8/48 is tested (a17, a18, f08). no claim about other hosts.
- one machine, one input source (ONT reads from pod5_*.fastq). real-world files with CRLF, multi-line FASTA or Illumina paired headers are only synthetic here.

## summary: concrete bugs found

1. hll guard changes report content order: stock creates zero-count map entries via add_kmer, guarded build does not, so tied siblings (nodes with more than 16 children) and all zero-count lines under -z can reorder; fix is `curr_taxon_counts[taxon];` in the guarded branch.
2. ks_skipline CR strip uses only the current line's last byte while stock uses the accumulated string: differs only for a wrapped quality ending in `\r\r` followed by an empty continuation line (not valid FASTQ); no fix required.
3. ks_skipline matches ks_getuntil2 on return codes -1/-2, EOF mid-record, no trailing newline, empty reads, split buffers and CRLF at a refill boundary; no other bug found.
4. prefetch dedup: no read of hc/idx for a repeat or skipped minimizer in translated frames, quick mode, ambiguous reset or per-frame reset; no bug found (translated path untestable here without a protein db).
5. gaps: interleaved -S is unreachable through the wrapper, gz is wrapper-pipe only, -D daemon mode and 2 GB records untested.
6. script: code/validate_matrix.sh (about 90 cases, 5 builds each) is written and syntax-checked, not executed.
