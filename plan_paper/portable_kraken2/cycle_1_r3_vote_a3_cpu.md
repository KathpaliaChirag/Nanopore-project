# cycle 1, r3 vote: a3_cpu

## 1. vote

- **build list (section 2): DISSENT**, two moves.
- **measure-first list (section 3): AGREE.** M4's `perf stat` sits in the free gates, which is enough.

## 2. changes

1. **move M5 from rank 8 to rank 5.** step a is a half-day wrapper change. both upstream wrappers decompress gz on one thread (perl `gzip -dc` pipes, `k2` python `gzip.open` into one fifo) [external: `scripts/kraken2`, `scripts/k2` at v2.18.0-RC1]. a 10-minute test decides it.
2. **move M11 from rank 5 to rank 8.** it costs 6-10 days and is gated by M12. its H3 column uses uncapped lookup counts. on the capped 8GB and 16GB dbs, lookups are about 10x rarer (section 1.2), so the `-M` thrash it beats shrinks by about 10x [arith: a3 r2 section 0].

## 3. factual errors

1. **section 1.2 sources the capped-db link to the WSL2 gprof file.** that file never names its db [repo: `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`], so "on that capped db" is [UNCLEAR] there. the link comes from luna's own gprof run on `~/data/kraken2_db`, which is the standard 8 GB db: 351M scanner calls and 11.6M `Get` [repo: `dorado-kraken-research/Luna/bash_history.md` step 40; `dorado-kraken-research/CLAUDE.md` key paths]. cite that run too.
2. **section 1.2 states that 50MB is uncapped.** it is our own build, and no cap value was read. mark it [UNCLEAR] until M22.
3. **section 1.5's "~10K lookups" for a few-read run holds only on uncapped dbs.** on the capped 8GB db it is about 10 x 3,189 x 0.033 ≈ 1,050 [arith on measured gprof].
