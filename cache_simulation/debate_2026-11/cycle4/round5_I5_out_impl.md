# cycle 4 round 5, I5: output path implementation (impl_out)

tree: ~/e1/impl_out/src (copy of impl_pread2, only classify.cc changed), runnable dir ~/e1/bin_out. diff: cycle4/code/impl_out.diff (238 lines, vs impl_pread2/src/classify.cc). test driver: ~/e1/i5_test.sh, logs ~/e1/i5_test.log and i5_test2.log. nothing was timed.

## what changed (all in classify.cc, each behind an env switch, default = new behaviour)

1. c1/c2/u1/u2 are built only when -C or -U is given (classified_output_filename or unclassified_output_filename non-empty). without them the sprintf header edit, Sequence::to_string, the ostringstream copies and the four .str()+.assign copies per chunk are gone. the only consumers of those strings are the writer lines `(*outputs.classified_output1) << out_data.classified_out1_str` etc., which are guarded by output pointers that are non-null only when -C/-U was given, so nothing else reads them. with -C/-U the code is the old code. the four strings are cleared each chunk otherwise, so recycled buffers never carry stale bytes. K2_KEEPSTR=1 restores the old building.
2. the kraken line is now appended straight into out_data.kraken_str (cleared per chunk, capacity kept through the buffers pool). ClassifySequence got an extra `std::string &kstr` argument. integers go through a hand written decimal routine (AppendU64, no locale, no ostringstream); std::to_chars is not usable because the Makefile builds with -std=c++11. a new AddHitlistStringFast keeps every format detail of AddHitlistString: runs as "taxid:count" separated by one space with no trailing space, "A:n " with the trailing space kept even for the last run (the old code does this), "|:|" and "-:-" for mate and frame borders (with a space after when not last), "0:0" when taxa is empty, ":Q" in quick mode, "name (taxid N)" for --use-names, "a|b" lengths for pairs, TrimPairInfo header for pairs. there is no str()+assign copy of the kraken string any more. K2_OLDFMT=1 restores the old ostringstream path (the old functions are untouched).
3. persistent per-thread taxon counters: thread_taxon_counters is no longer cleared per chunk and is merged into total_taxon_counters once per thread after the chunk loop (96 merges instead of about 3000), only with --report. --report-minimizer-data (opts.report_kmer_data, the HLL case) keeps the per-chunk merge. K2_CHUNKMERGE=1 restores the per-chunk merge for everything. zero-count keys from the hit_counts keys are kept because they live in the same per-thread map.

## byte identity (stock = ~/chirag_K/tools/kraken2-fresh-bin-s19/kraken2, --threads 8)

each case compares stock against 4 variants of bin_out (default, K2_OLDFMT=1, K2_KEEPSTR=1, K2_CHUNKMERGE=1) on: per-read --output, --report, stdout, exit code, and every -C/-U file. dbs: sample_targeted (50 MB) and standard_8gb. inputs: reads_10, reads_1000, a 20k read prefix of per_pod5_fastq/pod5_0.fastq, and a small pair (400 reads vs the next 400, from reads_1000).

cases (all in both dbs): plain (10, 1000, 20k reads), --use-names, --quick, --confidence 0.1 --minimum-hit-groups 3, -C and -U together (also with --use-names), -C only, -U only, --memory-mapping, --report-minimizer-data, K2_PREAD=0 (kseq path), --paired, --paired with -C/-U (files cls_1/cls_2/unc_1/unc_2).
extra: stdout output with --threads 1 and 3 on sample_targeted vs stock, report included: identical.

result: 29 of 30 cases identical in all variants. the one difference is standard_8gb --quick, report only (the per-read output is identical): the report has the same line count but a different order for rows with count 1. this is NOT from I5: the unchanged impl_pread2 binary (bin_pread2) gives the same report as every variant here, with K2_PREAD=0 and with --threads 1 too, and stock is stable at T1 and T8. so it is a pre-existing difference between impl_pread2 and stock in quick mode, probably tie ordering from the E8 map or report sort; it should be chased before claiming report identity for --quick.

## benchmark commands (run on Luna in the timing window, not run by me)

```
S=~/e1/bin_out/kraken2
# new default
$S --db DB --threads 96 --report R --output /dev/null READS
# old formatting only
K2_OLDFMT=1 $S ...
# old c1/u1 building only
K2_KEEPSTR=1 $S ...
# old per-chunk counter merge only
K2_CHUNKMERGE=1 $S ...
# all three old (should match impl_pread2 time)
K2_OLDFMT=1 K2_KEEPSTR=1 K2_CHUNKMERGE=1 $S ...
```
a real file output (--output /dev/shm/x, never the root disk) shows the kraken string gain more than /dev/null does. run interleaved, 3+ reps, T=96 and 128.

## known risks

- the persistent counters keep a taxon map per thread for the whole run; memory is bounded by distinct taxa per thread (small) but the merge now happens at the very end, so a crash mid-run loses nothing extra (the report is written at the end anyway).
- if a read has a taxon id whose external_id is above uint64 or negative it cannot occur (external_id is uint64_t).
- only quick mode, report ordering mismatch described above is unresolved and predates this work.
- translated (-X) search is not tested; it goes through the same ClassifySequence output code, so the format code is shared but untested there.
- the hand itoa prints plain decimal like ostream for unsigned values; sizes and ids are unsigned here, so no sign case.
- time gains are not measured; estimates from round1_B: items 1+2 about 8 to 16% of cpu, item 3 0.02 to 0.1 s at T=96.

## summary
1. c1/c2/u1/u2 strings are built only with -C/-U; K2_KEEPSTR=1 restores.
2. kraken line and hit list are appended to the block string with a hand itoa; K2_OLDFMT=1 restores; no str()+assign copy.
3. taxon counters are per-thread persistent and merged once per thread (not with --report-minimizer-data); K2_CHUNKMERGE=1 restores.
4. diff 238 lines in cycle4/code/impl_out.diff; binary in ~/e1/bin_out.
5. 29 of 30 small-input cases byte-identical (output, report, stdout, -C/-U files, paired) across all 4 variants.
6. the one difference (standard_8gb --quick, report tie order) also appears in unchanged impl_pread2, not caused by this change.
