# the best build so far (luna, 2026-11-23): everything stacked, byte-identical to stock S19

tree: ~/e1/src_best (diff against the prefetch-dedup tree: code/best_build_vs_dedup.diff, new file code/mmbulk_best.h). contents, all on top of S19:

1. HLL guard: no HyperLogLog work unless --report-minimizer-data. the empty per-taxon report entries stock creates are inserted once per taxon per read from hit_counts (not once per hit group), so the plain report AND --report-zero-counts output are byte-identical to stock (this fixes the tie-order caveat of the first guard; the bug was found by the round 2 validator agent).
2. prefetch dedup: fill() skips hash + prefetch for repeated minimizers and for keys below minimum_acceptable_hash_value on capped databases.
3. serial section: kseq_read counts the quality line instead of copying it when no -Q and no -C/-U is requested; no per-read shrink_to_fit (K2_KEEPQ=1 restores the old behaviour).
4. scalar bulk scanner (K2_BULK=1; default is OFF in this build, so benchmark with the env set): mmbulk.h ScanBulk, a resumable sentinel-gated 5-slot window min with state in registers, exact fallback to NextMinimizer for protein/translated, revcom_version 0, k-l != 4. exactness harness (code/mmcmp.cc): 1,893,992,308 items, 2.79M sequence comparisons, chunk sizes 1/7/64/4096, six parameter sets: 0 mismatches.
5. 48 threads instead of 32 (thread sweep, see below for the caveat).

## correctness (data/best_correct.txt): all four databases, all 1,872,777 reads, T=48 with K2_BULK=1 vs STOCK S19 at T=32

50 MB, 8 GB, 16 GB, 103 GB: per-read output identical (cmp) and the plain report BYTE-identical to stock.
also (round 5): final2 (items 1 to 3 and 5) byte-identical to stock even with --report-zero-counts on 8 GB.

## timing (data/best.csv), wall seconds, 5 interleaved repetitions

| db | stock S19, T=32 | previous best (final2), T=48 | best, T=48, K2_BULK=1 | speedup vs stock |
|---|---|---|---|---|
| 50 MB | 8.37 8.38 8.39 8.39 8.42 | 5.26 5.26 5.29 5.26 5.27 | 4.96 4.90 4.92 4.89 4.97 | 1.71x |
| 8 GB | 8.58 8.61 8.60 8.60 8.71 | 5.23 5.23 5.23 5.22 5.28 | 5.31 5.21 5.30 5.23 5.22 | 1.64x |
| 16 GB | 10.18 10.16 10.17 10.07 10.07 | 5.94 5.88 5.86 5.87 5.87 | 5.59 5.42 5.46 5.50 5.52 | 1.85x |
| 103 GB | 20.29 20.43 20.34 19.98 20.19 | 9.51 9.63 9.39 9.30 9.42 | 8.88 8.85 8.72 8.69 8.81 | 2.30x |

## where the 8 GB case stands, and why

the bulk scanner gives about 8 to 9% on 50 MB and 103 GB but nothing on 8 GB at T=48: the wall there sits at a floor of about 5.2 s that is the remaining serial read section (the lock). the thread sweep on the best build confirms it:

| db | T=32 | T=40 | T=48 | T=56 | T=64 | T=80 |
|---|---|---|---|---|---|---|
| 8 GB | 5.03 5.04 5.03 | 5.23 5.16 5.14 | 5.23 5.30 5.25 | 5.34 5.32 5.29 | 5.38 5.37 5.45 | 5.46 5.45 5.58 |
| 103 GB | 9.77 9.63 9.39 | 8.83 8.70 8.68 | 8.81 8.80 8.59 | 8.88 8.77 8.66 | 8.87 8.72 8.77 | 9.04 8.86 9.17 |

with a serial read section, more threads only add contention on 8 GB (best T=32). on 103 GB the memory-bound phase benefits from 40 to 64 threads. the lock-free parallel reader (round 5, implementer I3) is the fix for this.

## things tried this cycle that did not help

reader fast path (one copy cut, round 5 I1): null, 7% slower at 8 GB. -M, loader thread cap, 1 MiB kseq buffer, numa binding, -march=native: nulls (see round2/round3 result files).
