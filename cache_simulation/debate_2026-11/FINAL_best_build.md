# the best build, in one place (state at the end of cycle 5, 2026-11-23)

this file summarises the whole non-cache speedup track that grew out of the cache investigation. the cache investigation itself (hardware associativity, software cache, eviction, hot-set front cache, double hashing) ended in bounded negatives; see round5_RESULTS.md and cycle2/round2_RESULT_oracle_ceiling.md and the study notes artifact. everything below is on top of S19 (the fastest version before this work) and every claim is byte-identical to stock S19 unless a caveat says otherwise.

## what the build contains (source on luna: ~/e1/impl_pre/src; diffs and notes in this repo)

| piece | what it does | where it is documented |
|---|---|---|
| HLL guard with report keys | skips the HyperLogLog work unless --report-minimizer-data; the empty per-taxon report keys are still created (in quick mode per hit, otherwise once per read from hit_counts) so the report is byte-identical | cycle3 round6, cycle4 round6_RESULT_quickmode_keys.md |
| prefetch dedup | fill() skips hash + prefetch for repeated minimizers and for keys below minimum_acceptable_hash_value | cycle2 round5_RESULTS_threads_numa_dedup.md |
| quality skip | kseq_read counts the quality line instead of copying it when no -Q, -C or -U; no per-read shrink_to_fit | cycle3 round4_RESULT_serial_reader.md |
| bulk scanner (K2_BULK=1) | scalar ScanBulk replaces NextMinimizer: 1.89 billion stream items compared with the old scanner, 0 mismatches | cycle3 round5_I2_scanner_impl.md |
| lock-free parallel reader | atomic ticket = block id, each thread preads its own 4 MiB chunk and parses outside any lock | cycle3 round7_RESULT_parallel_reader.md |
| exact damage handling | a pre-pass (overlapped with the database load) falls back to the stock kseq path on mid-file damage; a truncated tail is replayed through the real kseq_read | cycle4 round5_I4_trunc_impl.md, cycle5 round7_RESULT_prepass.md |
| output path | c1/c2/u1/u2 strings only built with -C/-U; kraken line formatted without ostringstream | cycle4 round7_RESULT_output_path.md |
| batch size | K2_B=64 instead of 16 at 96+ threads | cycle5 round6_RESULT_prefetch_batch_96.md |
| threads | 96 to 128 instead of 32 (flat beyond 128 on this 192-thread machine) | cycle3 round8_RESULT_scaling_to_192.md |

## how to run it (defaults are conservative; the speed settings are env switches)

K2_BULK=1 K2_B=64 kraken2 --threads 96 ...   (K2_PREAD=0 forces the stock reader, K2_PREAD_PRESCAN=0 skips the exactness pre-pass, K2_PRESCAN_MMAP=0 is the recommended pre-pass mode (mmap is slower), K2_KEEPQ=1 / K2_KEEPSTR=1 / K2_OLDFMT=1 / K2_CHUNKMERGE=1 restore old behaviours for A/B).

## numbers, all 1,872,777 reads (12.5 GB), plain --report, output /dev/null, medians

| db | stock S19 at 32 threads | best build | speedup | notes |
|---|---|---|---|---|
| 50 MB | 8.39 s | about 1.7 s (T=96, pre-pass off); about 1.9 s with the exactness pre-pass | 4.4x to 4.9x | |
| 8 GB | 8.60 s | 1.59 s (T=128, K2_B=128, pre-pass off); about 1.8 s with the pre-pass | 4.8x to 5.4x | |
| 16 GB | 10.16 s | 2.00 s (T=128, K2_B=128, pre-pass off); about 2.2 s with the pre-pass | 4.6x to 5.1x | |
| 103 GB | 20.29 s | about 6.4 to 6.5 s (T=96/128, K2_B=64, pre-pass off); about 6.6 s with the pre-pass | 3.1x | 3.2 s of the time is loading the table |

(each component's own measurement is in its result file; the combined line above stitches the K2_B sweep, which was run with the pre-pass off, onto the other results, so the exact final combination should be re-measured in one run before quoting it.)

## validation status

- byte-identity vs stock S19 on all four databases at T=96/128, all reads: yes (data in cycle3/data and cycle4/data).
- validation matrix (about 150 generated cases x builds: FASTA, CRLF, empty reads, '@' in quality, 16 KiB boundaries, paired-end, -Q, -C/-U, --report-minimizer-data, --use-names, --report-zero-counts, --confidence, --minimum-hit-groups, --quick, gz/bz2/stdin, every malformed and truncated input): 308 PASS, 0 FAIL on the merged build (cycle4/data/validate_matrix4.log). two bugs in my own earlier shortcuts were found by this process and fixed (report-minimizer-data block dependence; the lazy report-key shortcut in --quick mode).
- NOT done: the final combination with the cheaper pre-pass and K2_B=64 has not been run through the full matrix; translated (protein) search is untested for lack of a database; paired-end, gz and stdin inputs use the stock reader path by design (so they are exact but not faster); -D daemon mode untested.

## honest caveats

- one machine (Luna: 2 x 48 cores, 192 logical CPUs, warm page cache), 16 input files of 12.5 GB total. the per-read kraken output was written to /dev/null except one 8 GB run to /dev/shm.
- 96 to 128 threads takes up to two thirds of a shared server; the thread count is a policy decision for sir.
- the exactness pre-pass costs about 0.2 s (about 10% of a 1.8 s run) and is skippable (K2_PREAD_PRESCAN=0, then malformed input aborts loudly instead of matching stock).
- the 103 GB floor is the database load (about 3.2 s); only a resident database (the stock -D daemon) would remove it for repeated jobs.
