# cycle 6 round 5, implementer I7: cross-read head prefetch

code: ~/e1/impl_head on luna (copy of ~/e1/impl_pre), diff in code/impl_head.diff (126 lines, classify.cc and seqreader.h only). runnable dir ~/e1/bin_head. nothing large was run and nothing was timed.

## design as built

1. seqreader.h: new `const Sequence* PeekNext() const` returns `&seqs_[curr_]` if the block still has a sequence, else NULL. it consumes nothing. both the lock-free pread path and LoadBlock fill the same `seqs_` vector, so one accessor covers both.
2. classify.cc thread loop: right before each ClassifySequence call, `k2_head_next = reader1.PeekNext();` (a file-scope `static thread_local const Sequence*`, so no signature change). for paired runs the peek happens after seq2 was taken, so it points at the next pair's mate 1 in both single-file and two-file modes. at the end of a block it is NULL and the head prefetch is skipped.
3. ClassifySequence: a `head_go` lambda runs once per read, on the last mate (mate 0 for single, mate 1 for paired), never with translated search. it fires at the moment `exhausted` becomes true (right after the final fill, before the resolve loop), so the head prefetches are in flight while the last one or two batches resolve. it also fires if the very first fill is already short but non-empty.
4. HeadPrefetch(): scans the first K2_HEADW items (default 64, max 256) of the next read, skips ambiguous items, repeats of the previous minimizer (same fill_last logic) and hashes below minimum_acceptable_hash_value, hashes with MurmurHash3 and calls `hash->PrefetchIndex(hc)`, at most K2_HEAD times (default 32, max 64, 0 disables). bulk path (K2_BULK=1): own BulkState on the stack plus a thread_local 256-entry result buffer, ScanBulk on the next read's data. non-bulk path: a separate lazily built thread_local MinimizerScanner, so the real scanner is untouched. it writes no per-read state, no pf arrays, no counters or stats and ignores the returned index. the only effect is prefetch instructions, so output cannot change.
5. a finding that changed one default: my first version scanned 3*K2_HEAD items. instrumented counts on the 20k-read file (1 thread) showed 19942 calls issued only 64648 prefetches (3.2 per call out of 96 items), because standard_8gb lets only about 1 item in 10 through the hash filter and the repeat skip. so the window, not K2_HEAD, limits the count; I added K2_HEADW (default 64, the size of one K2_B=64 batch). perf stat sw_prefetch_access.t0 confirmed the extra prefetches exist (3.12M with K2_HEAD=0 vs 3.19M with 32, for bulk 0 and 1). for the 103 GB db the pass ratio may differ, so K2_HEADW is a benchmark knob too.

## byte-identity results (all against stock S19 kraken2, whole files compared with cmp)

harness: ~/e1/i7test.sh and ~/e1/i7pair.sh on luna, inputs in /dev/shm/i7_in (now cleaned up for outputs), T=8. compared: per-read output, report, -C file, -U file (and _1/_2 for pairs).

| case | db | variants | result |
|---|---|---|---|
| reads_10, reads_1000 | sample_targeted | K2_HEAD 0/8/32/64 x K2_BULK 0/1 | identical |
| 20k-read prefix of pod5_2 | sample_targeted, standard_8gb | same 8 variants | identical |
| reads_1000 | standard_8gb | same | identical |
| --use-names, --quick, --minimum-base-quality 10, --confidence 0.1 on the 20k file | standard_8gb | same | identical (quality masking mutates the read after our peek, which only changes which lines get prefetched) |
| paired, two files, 1000 pairs (different mates) | standard_8gb | HEAD 0/8/32/64 x BULK 0/1 x PREAD 0/1 | identical |
| paired, 1000 pairs where mate 2 is the same read as mate 1 | standard_8gb | same 16 | identical |
| K2_PREAD=0 on 20k and reads_1000 | standard_8gb, sample_targeted | HEAD 0/32 | identical |
| extra sweeps | | K2_HEADW=256 (singles), K2_HEADW=1 (pairs), K2_B=64 (singles), K2_B=1 (pairs) | identical |

counts: single-end 80 of 80 comparisons pass in each of 3 sweeps (HEADW 64, HEADW 256, K2_B=64). the script prints 16 "DIFF" lines per sweep for the two paired cases inside i7test.sh; that is a harness bug (stock failed there because the -C/-U paths lacked the `#` placeholder), not a kraken difference. the paired cases were redone correctly in i7pair.sh: 32 of 32 pass in each of 3 sweeps (HEADW 64, HEADW 1, K2_B=1). translated search was not tested; the code path is skipped by construction (`opts.use_translated_search` makes head_done true).

## benchmark commands for you

run on idle luna with the flags of the final-build numbers, 5 interleaved reps per setting, plus one cmp against K2_HEAD=0 per setting. K2_B=64 assumed. fill in the db path and read file.

```
cd ~/e1; B=bin_head/kraken2; R=<the 1.87M-read input>
for rep in 1 2 3 4 5; do for H in 0 16 32 64; do
  K2_B=64 K2_HEAD=$H /usr/bin/time -f "103gb T96 H$H %e" $B --db <103GB db> --threads 96 --output /dev/shm/i7_o103_$H.out $R
done; done
for rep in 1 2 3 4 5; do for H in 0 16 32 64; do
  K2_B=64 K2_HEAD=$H /usr/bin/time -f "8gb T96 H$H %e" $B --db ~/chirag_K/AccuracyDrift/databases/standard_8gb --threads 96 --output /dev/shm/i7_o8_$H.out $R
done; done
for H in 16 32 64; do cmp /dev/shm/i7_o103_0.out /dev/shm/i7_o103_$H.out; cmp /dev/shm/i7_o8_0.out /dev/shm/i7_o8_$H.out; done
# window sweep, only if the above shows a gain: K2_HEAD=32 with K2_HEADW=32 / 64 / 128 / 256
```

H0 is the same binary with the feature off, which keeps code layout constant. also run ~/e1/bin_pre once to check H0 equals it.

## risks

1. extra scan cost per read: up to K2_HEADW items (64 default) are scanned twice per read. if a read yields about 1000 items (116 lookups at roughly a 10 percent pass rate suggests that) that is about 6 percent more scan work, plus the hashing and a few prefetches. against it, the saved stall is about one exposed miss (about 130 to 300 ns). expected gain is small, possibly negative at 8 GB; it can only win where a miss is expensive (103 GB). test K2_HEADW 32 and 16 as well.
2. the premise: a 64-item batch holds only about 6 to 7 real lookups on a subsampled db, so a read has far more batches than the 2 per read assumed in round 1, and only the first batch is helped (about 1 of 15).
3. thread-local state: one thread_local MinimizerScanner (only when K2_BULK=0, never freed, one per thread) and a 256-entry bulk buffer pair (about 2.3 KB) per thread. no shared state, no atomics. the peeked Sequence belongs to this thread's own reader block, so there is no race.
4. quality masking and --quick: masking is applied after the peek, so lines prefetched for a masked read can be slightly off (harmless); in quick mode the loop can exit before head_go fires, which just loses the prefetch.
5. up to 32 more lines in flight on 16 fill buffers exactly when the last batch resolves; K2_HEAD 16 may beat 32 for that reason.
6. stale-prefetch risk: head lines are used about one read-scan later; with very long reads the lines could be evicted before use.

## summary
1. built PeekNext() in seqreader.h plus a once-per-read HeadPrefetch in classify.cc (prefetch instructions only; K2_HEAD default 32, K2_HEAD=0 disables; new K2_HEADW scan window default 64).
2. finding: standard_8gb lets about 1 item in 10 become a lookup (3.2 prefetches per 96 scanned items), hence K2_HEADW; perf confirms the extra prefetches fire in bulk and non-bulk modes.
3. diff vs impl_pre is 126 lines, at code/impl_head.diff in the repo and ~/e1/impl_head/changes.diff on luna; build is ~/e1/bin_head.
4. byte-identity: single-end 80 of 80 per sweep, paired 32 of 32 per sweep, across HEAD 0/8/32/64, BULK 0/1, PREAD 0/1, HEADW 1/64/256, K2_B 1/64, --quick, --use-names, quality masking, --confidence, -C/-U.
5. benchmark commands are in the section above (K2_HEAD 0/16/32/64, T=96, 103 GB and 8 GB, 5 interleaved reps, plus cmp).
6. all small-input comparisons were byte-identical (the 16 DIFF lines per sweep in i7test.sh logs are a harness bug in two paired cases, redone correctly in i7pair.sh); expected gain is small and the extra scan cost is the main risk.
