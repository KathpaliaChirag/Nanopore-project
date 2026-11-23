# scaling to 192 threads and the bulk scanner at high thread counts (luna, 2026-11-23)

build: bin_pread = best build (guard with lazy keys, prefetch dedup, quality skip, bulk scanner K2_BULK=1) + the lock-free parallel reader (K2_PREAD=1). all 1,872,777 reads, plain --report, output /dev/null, 3 interleaved repetitions (data/hi.csv). byte-identity of this build against stock S19 is in round7 (data/pr_correct.txt).

## wall seconds by thread count (bulk scanner on)

| db | T=96 | T=128 | T=160 | T=192 |
|---|---|---|---|---|
| 50 MB | 2.09 2.10 2.12 | 2.01 2.04 2.06 | 2.03 2.04 2.04 | 2.10 2.12 2.06 |
| 8 GB | 2.11 2.12 2.13 | 2.08 2.06 2.10 | 2.08 2.08 2.13 | 2.17 2.20 2.18 |
| 16 GB | 2.69 2.67 2.68 | 2.60 2.61 2.57 | 2.60 2.58 2.58 | 2.63 2.65 2.62 |
| 103 GB | 7.10 7.03 7.23 | 6.90 7.30 7.27 | 7.04 7.27 7.09 | 7.09 7.24 7.30 |

the curve is flat from 96 to 192 threads, so 96 to 128 is the useful range on this 2 x 48 core (192 logical) machine. past that the run is bound by something that does not scale with threads (database load, exit, the ordered output writer, the memory system), and oversubscribing a shared server buys nothing.

## what the bulk scanner is worth now (T=96, same binary, K2_BULK=0 vs 1)

| db | bulk off | bulk on | gain |
|---|---|---|---|
| 50 MB | 2.90 2.89 2.89 | 2.09 2.10 2.12 | 27% |
| 8 GB | 2.86 2.85 2.84 | 2.11 2.12 2.13 | 26% |
| 16 GB | 3.43 3.39 3.39 | 2.69 2.67 2.68 | 21% |
| 103 GB | 7.23 7.55 7.48 | 7.10 7.03 7.23 | 5% |

once the serial read floor is gone the scanner is the limiter again, and the bulk scanner is worth 21 to 27% on the cpu-bound databases. on 103 GB the 3.2 s database load and the memory-bound lookups dominate, so it is worth 5%.

## headline against stock S19 at its default 32 threads (stock medians 8.39 / 8.60 / 10.16 / 20.29 s)

| db | best build | threads | speedup vs stock | output and report vs stock |
|---|---|---|---|---|
| 50 MB | about 2.04 s | 128 | 4.1x | byte-identical |
| 8 GB | about 2.07 s | 128 | 4.2x | byte-identical |
| 16 GB | about 2.58 s | 128 | 3.9x | byte-identical |
| 103 GB | about 7.0 s | 96 to 128 | 2.9x | byte-identical |

(the byte-identity at T=96/128 itself has only been checked at T=48 so far; output does not depend on the thread count by construction, but a T=96 cmp should be added to the validation matrix before quoting it.)

## what is left

- 103 GB: about 3.2 s of the 7.0 s is loading the table (kernel page-cache copy plus huge-page zeroing at about 32 GB/s); a loader thread cap of 64 gave 3% earlier. overlapping the load with scanning, or a persistent resident database, are the only ideas left on that path.
- small databases: about 2.0 s is now a floor that does not move with threads; candidates are the ordered output writer, process exit, and the 12.5 GB parse in the preads. a perf profile at T=96 would say.
- validation matrix on bin_pread (queued) must pass before any of this is called shippable; paired-end, FASTA, gz and stdin use the old path by design.

## addendum: byte-identity at 96 and 128 threads, and the 96-thread profile (data/t96_correct.txt, data/t96_prof.txt)

bin_pread2 (K2_BULK=1) vs STOCK S19 at T=32: per-read output identical and plain report byte-identical at T=96 AND T=128 on all four databases (50 MB, 8 GB, 16 GB, 103 GB, all 1,872,777 reads). this closes the "T=96 not checked" caveat.

perf record, T=96, share of classify-process samples:
| symbol | 8 GB | 103 GB |
|---|---|---|
| ClassifySequence (hash, resolve loop, run merge, hit list; all inlined) | 39.85% | 13.02% |
| ScanBulk (the new scanner; was about 38% of cpu as NextMinimizer) | 13.25% | 5.30% |
| kernel (top two unresolved symbols) | about 10% | about 23% |
| memmove | 4.33% | 2.85% |
| GetAt | 3.38% | 29.49% |
| AddHitlistString + xsputn + __ostream_insert + num_put + sentry | about 10% | about 3% |
| PrefetchIndex | 1.61% | 5.46% |

the scanner is no longer the limiter. on the small databases the remaining cost is the classification loop body and string formatting; on 103 GB it is table lookups (memory stalls) plus kernel time. next candidates: build the output line without ostringstream, stop building the c1/c2/u1/u2 strings when -C/-U is off (the 4% memmove), and a perf annotate of ClassifySequence.
