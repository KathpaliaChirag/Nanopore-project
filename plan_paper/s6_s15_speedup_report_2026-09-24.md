# kraken2 speedup on luna, S6 to S15 (2026-09-24)

goal from the handoff: make stock kraken2 (S0) faster in a way that holds on every db and every input size, with identical output. this is what was built, measured and found, including the parts that turned out wrong.

## headline

current best is **S15**. output is byte-identical to stock (kraken output and report, sorted by read id) in all 16 cells of the 4 db by 4 read-count matrix, and S15 is faster in every cell.

32 threads, output and report written to disk, one run per cell (`data/s6plus/matrix_s15.log`):

| db | reads | S0 | S15 | speedup |
|---|---|---|---|---|
| 50MB | 10 | 0.08s | 0.06s | 1.3x |
| 50MB | 1,000 | 0.39s | 0.24s | 1.6x |
| 50MB | 104,918 | 1.52s | 0.84s | 1.8x |
| 50MB | 1,872,777 | 16.59s | 9.35s | 1.8x |
| 8GB | 10 | 4.47s | 0.45s | 9.9x |
| 8GB | 1,000 | 5.08s | 0.45s | 11.3x |
| 8GB | 104,918 | 6.03s | 1.12s | 5.4x |
| 8GB | 1,872,777 | 21.12s | 9.43s | 2.2x |
| 16GB | 10 | 8.33s | 0.76s | 11.0x |
| 16GB | 1,000 | 9.11s | 0.69s | 13.2x |
| 16GB | 104,918 | 9.96s | 1.41s | 7.1x |
| 16GB | 1,872,777 | 26.83s | 11.69s | 2.3x |
| 103GB | 10 | 59.78s | 3.87s | 15.4x |
| 103GB | 1,000 | 57.97s | 3.44s | 16.9x |
| 103GB | 104,918 | 59.99s | 4.51s | 13.3x |
| 103GB | 1,872,777 | 95.30s | 21.58s | 4.4x |

## what changed, in order (each stage built on the previous one)

each row is the measured effect at 1,872,777 reads, 32 threads, 3 interleaved reps unless noted. raw logs are in `data/s6plus/`, patch scripts in `scripts/s6plus/`.

| stage | change | effect | verdict |
|---|---|---|---|
| S6 | the 4-way per-thread cache (already built on luna from the simulator work), no atomics, hashed set index | 50MB 15.6s to 13.4s, 8GB 19.7s to 15.9s | **effect was real but not from the cache**, see ablation below |
| S7 | S6 plus batched software prefetch | no gain, back to S0 speed | null |
| S8 | stream all input files through one reader instead of one parallel region per file | 50MB 15.6s to 11.1s, 8GB 19.7s to 14.6s | real. no effect on 103GB |
| S9 | batched software prefetch (batch 16 to 64), no cache | 103GB ~87s to ~76s. null on 8GB and 16GB | real only where lookups are dram-bound |
| S10 | parallel `pread` load of the hash table (32 threads, 64MB chunks) | 16GB with 10 reads 9.14s to 1.89s. 103GB 90.5s to 34.5s | biggest single win for large dbs |
| S11 | ring buffer for the sliding-window minimum, bswap in reverse_complement | user cpu 300s vs 300s, wall unchanged | null, discarded |
| S12 | one modulo per lookup with an exact reciprocal multiply, conditional subtract in the probe loop | 50MB 11.62s to 10.98s. 8GB tied | small, real |
| S13 | `memchr` for the newline scan in kseq (serial parse of 12.5GB: 10.53s to 3.88s) | 8GB 11.94s to 10.41s | real |
| S14 | 2MB-aligned table with `madvise(MADV_HUGEPAGE)` | 16GB 11.9s to 9.15s, 8GB 10.36s to 8.29s, 103GB 35s to 13-20s | real, large |
| S15 | count runs of identical hit taxa, flush to the unordered_map only on change | -1.6% to -2.2% | small, real |

## what i got wrong along the way (kept in the record on purpose)

1. **the cache is not what made S6 fast.** the ablation (stock plus multi-file streaming, no cache, `s8n`) ran 11.06s and 14.48s, identical to S8 with the cache (11.10s and 14.55s). the perf profile agreed: total cpu cycles were the same for S0 and S6 (174K vs 175K samples). S6 finished sooner because it kept more cores busy, not because it did less work. my earlier explanation to you ("the cache avoids lookups") was wrong. the 4-way cache adds nothing and is dropped from S8 onward.
2. **the hit rates i quoted (1 to 3%) came from a different binary** (the lru build with atomic counters), so they could not explain a 13 to 20% wall win, and they did not.
3. **the real cause of the small-db gap was the pipeline**: kraken2 runs one openmp parallel region per input file (16 files here), each ending in a barrier, plus a serial fastq parser inside `critical(seqread)`. that showed up only once i thread-scaled and profiled instead of guessing.

## how the bottleneck moved

stock at 32 threads on the small dbs used only ~22 of 32 cores. fixing one wall exposed the next: per-file barriers (S8), then the serial parser (S13), then page-fault and tlb cost on the table (S14). on 103GB the load alone was ~55s of a ~90s run, which is why S10 and S14 dominate there.

## caveats you should know before citing any of this

- **one machine.** everything is luna (192 cores, 503GB ram). "faster on every machine" is not shown. orion and any non-x86 box are untested.
- **warm page cache.** the db files were already in ram. a cold-cache first run is bounded by disk read speed and would show a smaller gain (i cannot drop caches without root).
- **transparent huge pages have variance.** thp mode on luna is `madvise`. S14 on 103GB alone ran 13.1 to 13.3s over 4 back-to-back runs, but 20.2s when it ran right after a non-huge-page run that left memory fragmented, and 21.58s in the matrix above. the stock 4KB path has no such variance. treat 103GB S14/S15 as 13 to 21s, not a single number. if the kernel cannot supply huge pages it falls back to 4KB pages and the code still works.
- **interleaved benchmarks penalize S14+.** alternating with a non-thp binary is the pessimistic case for thp.
- **the matrix is one run per cell**, not 3 reps. the per-stage tables above are 3 reps with tight spread (cv well under 2%), the matrix is not.
- **output equality means kraken output and report file, sorted by read id, compared byte for byte.** tested for the small read counts on all 4 dbs and for 1.87M reads on all 4 dbs in the matrix. earlier stages were checked on 104,918 reads or on 1 to 3 of the 16 pod5 files (up to ~350K reads), on 50MB, 8GB and 16GB (not 103GB).
- **multi-file streaming applies to unpaired input only.** paired-end paths are untouched and unbenchmarked.

## what is still on the table

- overlap db load with parsing (hide the last ~3s on 103GB).
- software-pipelined prefetch (issue batch n+1 before resolving batch n), untested.
- the scanner is still ~25% of cpu. my two micro-optimizations did nothing, a real rewrite would be needed.
- test on a second cpu, and a cold-cache run.
- more than 32 threads: 103GB went 12.9s to 10.8s at 64 threads with S14.

## reproduce

trees are under `~/tools/kraken2-src-sN` on luna (each built from the previous with `scripts/s6plus/sN_patch.py`), binaries under `~/tools/kraken2-fresh-bin-sN`. `bench.sh` (interleaved timing), `check.sh` (byte compare), `matrix.sh` (full matrix).
