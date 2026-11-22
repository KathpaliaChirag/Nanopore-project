# E5: skip the HyperLogLog work unless --report-minimizer-data is set (found by the production-scale profile, 2026-11-23)

this is the first noteworthy positive result of the debate. it is not a cache or eviction result. it came from re-profiling at production scale after round 5's bound showed the lookup layer was capped.

## what the profile showed

S19, 103GB db, T=32, 1,872,777 reads (all 16 per-pod5 fastq files), perf record: NextMinimizer 19.0%, ClassifySequence 17.0%, PrefetchIndex 9.7% + GetAt 6.7% (lookup 16.3%), HyperLogLogPlusMinus::insert 3.3% + merge 1.2%.
the hyperloglog symbols are not part of classification. classify.cc line 866 calls add_kmer (a hyperloglog insert) whenever a report file is requested, but the distinct-minimizer numbers are only printed with --report-minimizer-data.

## the change (e5/hll_guard.diff, one line)

`if (!opts.report_filename.empty())`  ->  `if (!opts.report_filename.empty() && opts.report_kmer_data)`

## results (luna, T=32, all 1.87M reads, plain --report, kraken output to /dev/null)

| db | stock S19 wall (s) | patched wall (s) | speedup | user cpu stock -> patched |
|---|---|---|---|---|
| 103GB (4 interleaved reps) | 20.33 / 20.36 / 20.45 / 19.96 | 12.48 / 12.36 / 12.42 / 12.24 | 1.64x | 334 -> 268 s |
| 16GB (2 reps) | 10.26 / 10.09 | 8.51 / 8.57 | 1.19x | 265 -> 240 s |
| 8GB (2 reps) | 8.58 / 8.56 | 7.62 / 7.56 | 1.13x | 233 -> 215 s |
| 50MB (2 reps) | 8.38 / 8.44 | 7.90 / 7.94 | 1.06x | 250 -> 234 s |

the 103GB gap (8 s) is larger than the classification-phase gap (10.7 s -> 8.8 s), so the hyperloglog structures also cost a lot to tear down at exit. this matches the "4-5 s exit tax" in the next-steps notes, now with a cause.

control (103GB): stock WITHOUT --report = 12.41 / 12.29 s, patched WITH --report = 12.4 s, stock WITH --report = 19.87 / 19.85 s. the whole gap is the hyperloglog path that --report switches on. without --report the two binaries are equal (12.3 vs 12.3 s), so there is no gain to claim for runs that do not write a report.

## correctness

- classification output (the per-read file): byte-identical to stock S19 over all 1,872,777 reads on the 103GB db (cmp, no sort). 1,850,859 classified (98.83%) in both. also identical on 105k reads / 8GB.
- --report-minimizer-data report: byte-identical to stock (that path still runs the hyperloglog).
- plain --report: the sorted report is identical to stock (same lines, same counts), but the line order differs. the report prints sibling taxa sorted by read count and breaks ties by distinct-minimizer count, so without that count the order of siblings with equal read counts changes (for example the 5-read Pseudomonas siblings swap places). anything that parses the report by hierarchy and taxid is unaffected. anything that diffs report text byte for byte against stock will see order changes. if exact order matters, a deterministic tie-break (for example taxid) or keeping the hyperloglog only for tied siblings would be needed.

## caveats

- one machine (luna), warm page cache, single binary lineage (S19 tree with uncommitted S6-S19 changes, so this diff is against that working tree, not a git commit).
- whether stock kraken2 upstream has the same unconditional add_kmer under --report was not checked here. the claim is only about the S19 tree.
- benchmarked with the repo's usual grid conditions (--report on, output to /dev/null, 32 threads). a user who never passes --report sees no change.
- the report order change is a real behaviour change and should be agreed with sir before this becomes "S22".

## what this changes about the debate

round 5 showed the lookup layer (cache, eviction, layout) is capped at about 3 to 5% on 8GB. this result came from the part of the profile nobody was optimising: bookkeeping that runs under --report. at 103GB it is worth more than every cache and eviction idea combined.
