# cycle 2, round 2: a5_skeptic (2026-10-27)

tags as in `00_context.md` section 6. new fetches this round:
- **V1.** RC1 `compact_hash.h`, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/src/compact_hash.h. there is no loop before the main loop, and the only prefetch is "if (i + PREFETCH_DIST < n) {" then "out[i] = Get(keys[i]);". so keys 0-7 are never prefetched, and `Get` rehashes ("uint64_t hc = MurmurHash3(key);"). **a1's claim holds.**
- **V2.** PostgreSQL docs, https://www.postgresql.org/docs/current/runtime-config-resource.html. `effective_io_concurrency` sets "the number of concurrent storage I/O operations", default 16, "most impact on higher latency storage". prior art for M30's concept.

---

## 1. counters, one per new build id and per proposed move

### the four role re-derivations

**M27 (a1), the GetBatch prologue.**
- re-derived, holds: 3,189 positions x 0.316 = 1,008 lookups; 8 / 1,008 = 0.8%. 150 bp: 116 x 0.316 = 37; 8 / 37 = 22% [arith].
- "5-7% of classify" for short reads = 22% x (1 - 1/1.46) = 6.9% [arith]. but that 1.46x is S8+S9 on long reads at 1 thread [measured]. scaling it linearly by the unprefetched share is a guess.
- the `Get(keys[i])` calls are independent, so an out-of-order core may overlap several misses [guess]. "one after another" is a ceiling, not a fact.
- **counter to "in at 3":** under 1% on our data by a1's own numbers. a 0.25-day upstream fix belongs inside M2's pull request, next to hash-once. M27b (pooling, 2-3 days) waits on M28.

**M30 = M50 (a2, a4), cold fault-ahead.**
- re-derived, holds: 10.7K x 0.106 ms = 1.13 s; 10.7K / 151K = 0.071 s; 3.8 / ~0.09 s ≈ 40x vs the copy. gp3: 10.7K x 1-9 ms = 11-96 s; 10.7K / 3,000 = 3.6 s [arith].
- the evidence is weaker than the arithmetic. 151K iops at qd16 is one enterprise nvme (a4 R1 src 6). "single-digit millisecond" is an aws upper bound [external: a4 N1]. emmc qd scaling is [UNCLEAR]. and `WILLNEED` reads "may be decreased by the kernel depending on virtual memory load" [external: a2 src 1], exactly on H3.
- **the regime is narrow:** cold, few reads, map branch, one-shot. a daemon (`-D`) or kraken2-server pays the cold load once per boot [external: cycle-2 a5 N4].
- prior art: PostgreSQL issues 16 concurrent asynchronous reads by default for the same reason [external: V2].
- so it goes inside M9 as the cold-map branch, gated by the 2-minute qd1-vs-qd16 timing. it does not get its own rank above M4.

**M32 (a2), detached teardown.**
- re-derived, holds: 282.16 ms x 111/16 = 1.96 s at 4 KB; 27.68 x 111/16 = 0.19 s with thp [arith on external a2 src 4].
- but luna's measured exit (3.9-11.4 s at 4 KB [measured]) is 2-6x that, so teardown alone does not explain it [UNCLEAR].
- it hides the cost; it does not remove it. a back-to-back run still meets 111 GB being freed, so report the run-to-run interval, not only wall.
- likely null where huge pages land (~0.2 s). E1's exit column kills it. prior art: the kernel rfc (opt-in, unmerged) [external: a2 src 4]. below the line.

**M41 (a3), run-length pipeline.**
- re-derived, holds: 3,189 x 0.316 = 1,008 runs; 3,189 x 8 B = 25.5 KB vs 1,008 x 12 B = 12.1 KB; 25.1% x 38.8 ns = 9.7 ns per base; half of that x 2/3 = 3.2 ns = 8.4% [arith].
- "half is per-position overhead" is the whole case, and it is a guess. part of the saving is M3's, so the two gains do not add.
- on RC1 it changes the token format, a harder upstream review than a patch.
- prior art: per-super-k-mer processing is standard in k-mer tools [external: cycle-1 S9, S10]; new only in kraken2's classify path.
- gated by the cpu gate. rank 6, not 4.

### the other new build ids

- **M26 (a1):** the only number is AMAC's 1.13x over SPP on chained-bucket joins [arith on external: a1 src 1], a different structure. 1.5-2 days for a guessed 0-8%. M8a stays the 0.25-day first step, behind the free annotate.
- **M31 (a2):** multi-gen lru already favours mapped pages [external: a2 src 2], so it is a null where that is on (luna [UNCLEAR]). killed or kept inside M61's session.
- **M33 (a2):** advice, not code. it holds only if our board's M.2 slot is filled [UNCLEAR]. `lsblk` / `lspci` on campus decides. inside M9.
- **M40 (a3):** new fact from V1: RC1's `GetBatch` calls `Get` on `this`, and `KeyValueStore::Get` is pure virtual [external: a1 src 5], so each per-key `Get` is virtual unless devirtualized [UNCLEAR]. the 10-minute objdump decides. rank 9.
- **M42 (a3):** "85% of FDO gains" is google's warehouse result [external: a3 N5], not kraken2. waits on E3.
- **M51 (a4):** holds. gp3 shows up as `/dev/nvme*n1` [external: a4 N3], so a name cannot pick the branch. inside M9.
- **M20' (a4):** holds. libgomp's docs never mention quotas [external: a4 N8]. adopt it as M20's definition.
- **M64 vs a4's standalone M13 for H5:** on H5 the 8GB db fits once (a4's own note), so the map path matters there too, and M13 still fights it. i keep M64.

### moves

- **a3's "M4 to 3, M9 to 5":** both are gated, and the cpu side is unmeasured off luna too. i keep M9 at 3 and M4 at 4.
- **a4's "M10 out":** agree. it needs kernel ≥ 6.1 and helps H4 only [guess, a4].
- **a4's "M13 stays":** reject, see M64.

---

## 2. fact fixes (brief section 3)

| # | verdict | note |
|---|---|---|
| 1 | confirm | both sides sourced: Coriolis 1.5x from DMR 3.25 to 52, #971 "days" [external] |
| 2 | confirm both | 103GB-class: [UNCLEAR] until M61. capped dbs: [UNCLEAR] until M22 + M61 |
| 3 | confirm, with a caveat | `-D` uses fixed FIFO names in /tmp, so two users collide [external: RC1 `classify.cc`]. kraken2-server's output "is not identical" [external]. whether `-D` output is byte-identical is M60's job |
| 4 | confirm, one tester | #1061 is one person's data. M1 repeats it on our dbs |
| 5 | confirm | 1 / (0.98 x 0.97 x 0.97) = 1.08x [arith] |
| 6 | confirm with one fix | H1 3.8 / 1.13 = 3.4x and 3.8 / 0.111 = 34x hold [arith]. H2 uncapped: with a4's own bracket (copy 19-30 s, map 1.1-5.4 s) it is **3.5-27x**, not 4-14x [arith]. the gp3 flip holds only at the high end of "1-9 ms". every capped cell uses luna's f ≈ 0.10, which is unread for today's dbs (M22) |
| 7 | confirm | 16GB classify (28.42 - 4.23) / (6.32 - 4.23) = 11.6x; 8GB 12.7x; 50MB 12.8x [arith on repo, taking sys time as the load]. "~11x" is conservative |
| 8 | confirm | orin already runs a default-flag v2.1.3 build [repo: `RESULTS.md` 1.4]. i withdraw my cycle-1 "lets orin build" wording |
| 9 | confirm | the chip supports dual-channel [external: a4 N7]; ck's laptop has one dimm [measured, repo] |
| 10 | confirm the arithmetic, reject it as luna's number | the 1.96 s it scales to explains at most half of luna's 3.9-11.4 s. quote it as "another machine, scaled" |

H5 (small cloud vm): accept as a class. every H5 cell is aws docs plus arithmetic [external, arith]. no kraken2 run exists, and M53 is optional.

---

## 3. prior-art verdict, new ids

| id | prior art | evidence |
|---|---|---|
| M26 | literature (AMAC, coroutine interleaving) | weak: 1.13x on another structure |
| M27 | upstream gap, verified [V1] | holds for counts; <1% on our data; short-read gain a guess |
| M28 | standard benchmark axis | holds |
| M30/M50 | standard (async read advice; PostgreSQL default 16 in flight [V2]); new for classifiers (Coriolis lists caching as future work [N2]) | arithmetic holds; device qd scaling unmeasured |
| M31 | standard call | weak; mglru may already do it |
| M32 | kernel rfc (opt-in, unmerged) | weak; luna's exit is 2-6x the scaled teardown |
| M33 | none needed | holds as advice; slot [UNCLEAR] |
| M40 | compiler practice | [UNCLEAR] until objdump; 10-minute kill |
| M41 | super-k-mer processing in k-mer tools | weak: rests on "half is overhead"; overlaps M3 |
| M42 | autofdo | weak until E3 |
| M43 | libgomp docs | holds (measure) |
| M51 | standard probing | holds as a reason |
| M20' | quota-aware thread counts (gomaxprocs discussion [a4 N9]) | holds |
| M53, M54 | method | holds |
| M60 | upstream `-D`, kraken2-server | measure |
| M61 | Coriolis's protocol | measure |
| M62 | none; a guard for RC1 | holds [#1061] |
| M63 | positioning | measure |
| M64 | Coriolis lz4 nodes | weak until the ratio test |
| cpu gate | perf | holds |

---

## 4. ranking

### top 10 build

1. **M2** (+M3, +M27a and hash-once in the same upstream pull request)
2. **M20'** (+M17 obey, +M62)
3. **M9** (+M24, M51, M30/M50, M33)
4. **M4**
5. **M5**
6. **M41**, gated by the cpu gate
7. **M26**, with M8a as its first step
8. **M11** (+M64), gated by M61
9. **M40**
10. **M21** (+M42)

below the line: M10, M13, M32, M31, M27b, M14, M18, M19, M16, M15, M7, M6.

### top 5 measure-first

1. **M22** lookup census
2. **M1**, with these riders: M28 short reads, the exit column, `TMPDIR` set, a raw plus whitespace-aware compare, and an RC1 objdump for M40
3. **E1**, plus the cold pair, the qd1-vs-qd16 timing (M30/M51 kill) and the M60 daemon test
4. **the cpu gate** (gates M4 and M41)
5. **M61** (the M12 sweep), with M31's fincore check

the orin probe rides on the campus visit, with `lsblk` / `lspci` for M33.
