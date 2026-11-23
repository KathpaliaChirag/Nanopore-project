# why the 103 GB run stops at about 6.7 s: three theories tested and closed (luna, 2026-11-23)

after the final configuration (FINAL_best_build.md) the 103 GB run takes about 6.7 s, of which about 3.2 s is loading the 104 GB table and the profile at T=96 shows GetAt at 29.5% and kernel time at about 23%. round 1 agent A (round1_A_lookup_stall.md) proposed three explanations to test; all three came back negative.

## 1. huge pages are NOT falling back to 4 KB pages (data/thp.txt)

smaps_rollup during runs of bin_pre (T=96): 103 GB db: peak AnonHugePages 105,858 MB of 106,702 to 107,140 MB anonymous memory = 98.8 to 99.2% on 2 MB pages (3 runs); 16 GB db: 15,258 MB of about 16,140 MB = 94.5% (the remainder is thread buffers). /proc/vmstat: thp_fault_alloc 45,844,910 vs thp_fault_fallback 31,458 (99.93% success), even though compact_stall 1.54M / compact_fail 1.44M look bad in isolation (they are background compaction attempts, not user-visible fallbacks). with 2 MB pages the page-walk cost is about 0.3% of the run. so the page-walk / 4 KB-page theory is refuted.

## 2. NUMA balancing is NOT the source of the kernel time (data/nb.txt)

kernel.numa_balancing is 1 on Luna and the lifetime hint-fault counter is 1.15e10, but the vmstat delta around a whole run is tiny: numa_hint_faults +5,486 and +2,778 on two 103 GB runs (T=96, 6.8 s), +98,177 and +91,098 on two 8 GB runs; numa_pages_migrated +95,000 and +50,000 (about 0.4 GB and 0.2 GB) on the 103 GB runs. so balancing does not touch our table in any significant way.

where the kernel time actually is: sys cpu time is 135 cpu-s on the 103 GB run (user 255) vs 28 cpu-s on 8 GB (user 104). the extra 107 cpu-s of sys time is the table load (about 32 loader threads x 3.3 s), plus about 28 cpu-s of sys time common to both (the 12.5 GB of input pread and process teardown).

## 3. the table load is at a memory-bandwidth floor, not a software limit (data/lb.txt, code/loadbench.cpp)

standalone benchmark that loads the real 104 GB hash.k2d into 2 MB-aligned, MADV_HUGEPAGE anonymous memory, 2 repetitions (identical within 0.1 s):

| method | threads | chunk | seconds | GB/s |
|---|---|---|---|---|
| pread (what kraken2 does now) | 32 | 64 MB | 2.96 / 2.97 | 37.5 |
| pread | 96 | 64 MB | 2.78 / 2.78 | 40.0 |
| pread | 32 | 16 MB | 2.92 / 2.94 | 38.0 |
| pread | 32 | 256 MB | 3.01 / 3.06 | 36.9 |
| mmap + memcpy | 32 | 64 MB | 3.15 / 3.11 | 35.2 |
| mmap + memcpy | 96 | 64 MB | 2.95 / 2.92 | 37.7 |
| mmap + MADV_POPULATE_READ + memcpy | 32 | 64 MB | 3.03 / 2.99 | 36.6 |
| MADV_POPULATE_WRITE the destination first, then pread | 32 | 64 MB | 1.39 + 3.45 = 4.84 | 22.9 |
| MADV_POPULATE_WRITE first, then pread | 96 | 64 MB | 0.81 + 3.22 = 4.03 | 27.5 |
| MADV_POPULATE_WRITE first, then mmap memcpy | 96 | 64 MB | 0.82 + 2.61 = 3.43 | 32.4 |

every copy method lands at 35 to 40 GB/s whatever the chunk size, thread count or API, and splitting the page-zeroing from the copy makes it worse. at 38 GB/s the copy moves about 100 GB/s of memory traffic (read the page cache once, zero the huge page once, write the copy once), close to the practical limit of this two-socket box. conclusion: the 3 s load cannot be tuned away; only skipping the copy removes it (a resident database via the stock -D daemon; -M maps the file but its 4 KB pages cost 4.9 s of TLB misses, see cycle3 round2_RESULT).

## what is left at 103 GB (agent A's ranked list, untested)

(a) pipelining lookups across reads (a read with fewer lookups than K2_B gets no lookahead; the average is about 116 lookups per read): expected 2 to 7% at 103 GB, 6 to 10 h of work, no output risk. (b) prefetch hint t1/t2 vs t0: 0 to 3%, 0.5 h. (c) a second-line prefetch for cells near a 64-byte line end: about 1.3%. none of these is worth more than a few percent.

## 4. the prefetch hint is a null (data/hint.csv)

bin_hint (compact_hash.cc PrefetchIndex with a runtime-selectable locality hint, K2_HINT): 3 = prefetcht0 (all cache levels, the default), 2 = prefetcht1, 1 = prefetcht2, 0 = prefetchnta. T=96, K2_B=64, pre-pass off, K2_BULK=1, all reads, 5 interleaved repetitions, wall seconds:

| db | t0 (3) | t1 (2) | t2 (1) | nta (0) |
|---|---|---|---|---|
| 103 GB | 6.77 6.76 6.41 6.44 6.51 | 6.85 6.66 6.57 6.68 6.55 | 6.86 6.56 6.66 6.67 6.80 | 6.69 6.49 6.37 6.62 6.53 |
| 16 GB | 2.14 2.09 2.07 2.09 2.08 | 2.14 2.12 2.11 2.12 2.09 | 2.17 2.18 2.14 2.14 2.08 | 2.11 2.09 2.12 2.09 2.09 |
| 8 GB | 1.70 1.64 1.65 1.64 1.65 | 1.66 1.65 1.64 1.66 1.66 | 1.67 1.67 1.65 1.64 1.66 | 1.66 1.67 1.67 1.67 1.67 |

medians: 103 GB 6.51 / 6.66 / 6.67 / 6.53; 16 GB 2.09 / 2.12 / 2.14 / 2.09; 8 GB 1.65 / 1.66 / 1.66 / 1.67. all within noise (about 2%), no hint beats the default. the lookup stall is not about which cache level the line lands in.

## 5. cross-read head prefetch is a null (implementer I7, code/impl_head.diff, data/head.csv)

idea (agent A's ranked idea 2): the lookahead never spans reads, so the first batch of every read is resolved with no overlap; while the last batch of read i is resolved, prefetch the first distinct minimizers of read i+1 (a PeekNext() plus a once-per-read HeadPrefetch with its own scanner state; prefetch instructions only, so output cannot change). K2_HEAD = max prefetches (0 = off), K2_HEADW = scan window in items.

byte-identity: K2_HEAD=32 at T=96 vs stock S19 on 8 GB and 103 GB, all reads: output identical, report byte-identical (data/head_correct.txt). small-input matrix by I7: 80/80 single and 32/32 paired comparisons per sweep.

timing, T=96, K2_B=64, K2_BULK=1, pre-pass off, 5 interleaved repetitions, wall seconds:

| db | K2_HEAD=0 | 16 | 32 | 64 |
|---|---|---|---|---|
| 103 GB | 6.82 6.62 6.64 6.42 6.39 | 6.69 6.57 6.62 6.44 6.43 | 6.67 6.50 6.49 6.40 6.42 | 6.54 6.68 6.46 6.43 6.42 |
| 16 GB | 2.18 2.09 2.11 2.08 2.08 | 2.15 2.10 2.10 2.14 2.10 | 2.14 2.11 2.10 2.10 2.11 | 2.12 2.10 2.12 2.11 2.11 |
| 8 GB | 1.71 1.68 1.68 1.66 1.68 | 1.70 1.69 1.70 1.67 1.70 | 1.68 1.68 1.68 1.69 1.67 | 1.69 1.71 1.69 1.69 1.68 |

medians: 103 GB 6.62 / 6.57 / 6.49 / 6.46 (best -2.4%, inside a 0.4 s run-to-run spread); 16 GB 2.09 / 2.10 / 2.10 / 2.11; 8 GB 1.68 / 1.69 / 1.68 / 1.69. window sweep at K2_HEAD=32 on 103 GB (3 reps): K2_HEADW 32 / 64 / 128 / 256: 6.38 6.25 6.46 / 6.42 6.47 6.50 / 6.48 6.32 6.38 / 6.33 6.36 6.36: no trend.

why it does not matter: only about 1 scanned item in 10 survives the hash filter and the repeat skip, so a 64-item window yields 6 to 7 real lookups; only about 1 of roughly 15 batches per read is helped.

## summary of cycle 6

every lookup-side idea for the 103 GB stall is now closed at 3% or less: huge pages fine, NUMA balancing not involved, load at the memory-bandwidth floor, prefetch hint irrelevant, cross-read head prefetch within noise. the only larger lever left is removing the load for repeated jobs (a resident database).
