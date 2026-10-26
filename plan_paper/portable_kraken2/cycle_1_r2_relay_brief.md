# cycle 1, round 2: relay brief (2026-10-26)

this file exists so all five agents counter the same list. it does three things: it confirms the upstream finding, it merges the 25 R1 ideas into one id list, and it lists the number conflicts R2 must settle.

---

## 1. the upstream finding, checked by the relay

three agents (a1, a3, a5) found it on their own. the relay re-fetched it:
- **v2.17.2** (released 23 sep 2026) lists "Multiple performance improvements to classify" by PR #1033 [external: https://github.com/DerrickWood/kraken2/releases]
- **PR #1033** adds four things: a 2 MB-aligned table with `MADV_HUGEPAGE`; parallel `pread` load with `K2_DB_READ_THREADS` (default 8, mmap path untouched); upstream kseq with `memchr` and a 64 KB buffer; batched lookups with prefetch distance `K2_PREFETCH_DIST` (default 8). benchmark: 8 threads, 5 GB per side paired fastq, Graviton4 266 s to 202 s (1.32x), x86 r7i 337 s to 204 s (1.65x), cold load on Graviton4 ~100 s to 34 s. it claims byte-identical output vs stock [external: https://github.com/DerrickWood/kraken2/pull/1033]
- **v2.18.0-RC1** (20 oct 2026) adds the out-of-lock parser, says the prefetch gain is "especially on aarch64/Graviton", and lists output-changing fixes: minimizer undercount, merge k-mer counts, a stricter fastq parser [external: https://github.com/DerrickWood/kraken2/releases/tag/v2.18.0-RC1]

consequence for everyone: "stock" now needs a version number. S9, S10, S13, S14 and S19 have public prior work. what upstream lacks, per a5's source read: S8, S12, S15, S17 (S18 unclear).

---

## 2. merged idea ids (use these in R2)

| id | idea | from | type |
|---|---|---|---|
| M1 | re-baseline S19 vs v2.17.2 and v2.18.0-RC1, all 16 cells, plus RC1 vs v2.17.1 byte compare | a5 B1, a3 s0, a1 f1 | measure |
| M2 | port the residual stages (S8, S12, S15, S17, S18 if needed) onto RC1, send upstream | a5 B2 | build |
| M3 | hash and prefetch only changed (and uncapped) minimizers in `fill()` | a1 i1, a3 i1 | build (upstream RC1 already does it) |
| M4 | batch scanner with a branch-free min-of-5 window, scalar, every isa | a3 i2 | build |
| M5 | faster / parallel gz decompression picked at startup | a3 i3 | build |
| M6 | out-of-lock parser (port `fast_reader`) | a3 i4 | build (upstream has it) |
| M7 | simd scanner with runtime dispatch (avx2 / avx-512 / neon) | a3 i5 | build |
| M8 | line-aware probe: next-line prefetch + simd compare inside the 64 B line | a1 i2 | build |
| M9 | load planner: map / copy / `O_DIRECT` / `MADV_RANDOM`, picked from input size, residency, free ram, device class | a2 i1, a4 i1 | build |
| M10 | huge pages that land: `MADV_COLLAPSE` after the copy, 2 MB file mappings for `-M` | a2 i2 | build |
| M11 | exact out-of-core lookup for a db bigger than ram (slot-partitioned / sorted sweep, then replay) | a1 i3, a2 i3, a5 B4 | build |
| M12 | small-ram emulation: cgroup `MemoryMax` after evicting the db file | a5 B3 | measure |
| M13 | compressed container made from the existing `hash.k2d` (zero-cell bitmap or zstd frames), compressibility check first | a2 i4, a5 B5 | measure, then build |
| M14 | numa policy: bind to one node / interleave / per-socket copies | a2 i5, a4 i4 | build |
| M15 | lower-density canonical sampling (mod-minimizer class), rebuild + accuracy check | a1 i4 | build, not byte-identical |
| M16 | miss prefilter built from `hash.k2d` | a1 i5 | build |
| M17 | loader thread plan: obey `--threads`, device-aware stream count | a4 i2 | build |
| M18 | online thread-count controller (thread parking + hill climb) | a4 i3 | build |
| M19 | memory-parallelism probe to set prefetch depth | a4 i5 | build |
| M20 | default thread count = physical cores instead of 1 (the wrapper reads `KRAKEN2_NUM_THREADS` or 1) | a3 note 6 | build (tiny) |
| M21 | portable build tiers: `-march=x86-64-v3` / armv8.2 tier + E3's lto / pgo, instead of `-march=native` | a3 note 2, E3 | build |

if you think two ids are really one idea, or an idea is missing, say so and give it a new id (M22 up).

---

## 3. number conflicts R2 should settle (or mark [UNCLEAR])

1. **lookups per base.** a3 and a1 use density ~1/3 [guess]. a5 cites an old gprof run: 9.87M `Get` calls for 354M scanner calls, ~1 per 36 bases [repo: `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`]. a4 suspects capped dbs skip lookups via `minimum_acceptable_hash_value`. a1 notes M5's 351.8M emits over 104,918 reads match one per position. this one number moves M3, M8, M9, M11 and every touched-fraction estimate.
2. **orin cold read speed.** a4 and a2 use emmc 5.1 class numbers (~0.25-0.29 GB/s) [external]. a5 and a4 both show the repo's one "cold" orin run was not cold. unmeasured on our board.
3. **orin thp mode.** a4: stock's 3.5 GB/s per-thread load on orin hints thp `always`. if so, S14 buys nothing there.
4. **M3's gain.** a1 says -4 to -7% on 50MB, a3 says ~4.7%. both rest on the 1/3 density and on `PrefetchIndex` being instructions, not waiting.

---

## 4. what R2 asks of every agent

write `cycle_1_r2_<your slug>.md` with:
1. **counters.** for each other agent's top 3 (more if you have time), and for every M-id you think is ranked wrong: what breaks, which class it hurts, what is cheaper, and whether its evidence holds. you may fetch sources to check a claim. tag everything.
2. **your own revisions.** what changes in your own R1 ideas now that v2.17.2 / RC1 exist, and in light of what the others wrote.
3. **your ranking.** (a) a ranked top 10 **build** list by M-id, one line of reason each. (b) a ranked top 5 **measure-first** list (M1, M12, E1-E5 parts, kill tests), one line each.
4. role extras:
   - a4_hw: fill one grid, rows = your top 10 M-ids, columns = H1 / H2 / H3 / H4 / cold, each cell a gain range with a tag.
   - a5_skeptic: a one-line prior-art and evidence verdict for every M-id (new / upstream has it / other tool has it; evidence holds / weak / fails).
