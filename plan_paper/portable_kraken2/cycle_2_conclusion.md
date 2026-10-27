# cycle 2 conclusion: the ranked list after counters to cycle 1 (2026-10-27)

this file closes cycle 2. it exists so cycle 3 starts from one list. it records what changed against `cycle_1_conclusion.md`, the new ranked list, the facts cycle 2 fixed, the open dissent, and the R3 vote. the transcript is `cycle_2_r1_*.md` (counters + new ideas), `cycle_2_r2_relay_brief.md` (merged ids), `cycle_2_r2_*.md` (counters), `cycle_2_r3_vote_*.md` (votes).

tags as in `00_context.md`. **stop-rule status: the list changed (M30 and M41 in, M10 and M13 out), so cycle 2 is not an unchanged cycle.**

---

## 1. what cycle 2 found

### 1.1 the few-read wins are one-shot-run wins

the wrong intuition: "a 10-read run on a big db is load-bound, so a faster loader is a big win for small jobs."

upstream kraken2 already has a daemon mode, `-D`, that keeps the index loaded between requests [external: RC1 `classify.cc`, a5]. ONT's real-time path keeps the db in a persistent kraken2-server [external: https://epi2me.nanoporetech.com/epi2me-docs/tools/kraken2-server/, a5]. for a stream of small batches the load is paid once. so S19's 9.8x-15.4x few-read cells, and every few-read cell below, apply to one-shot cli runs. measure M60 tests how much a daemon amortizes, and what it keeps resident (a2: a copy-path daemon pins the table as anonymous memory, `-M` leaves it reclaimable).

### 1.2 `-M` does run a db bigger than ram; how badly it slows is the open number

FINAL's cycle-1 item 8 said only an exact out-of-core mode can run such a db. wrong. Coriolis (ISMB 2023) ran kraken2 with memory mapping on a 4 GB jetson tx1 under cgroup caps up to a reference/ram ratio of 52, and lost only 1.5x in throughput (611.7 to 403.8 kb/min) [external: https://academic.oup.com/bioinformatics/article/39/Supplement_1/i66/7210430]. that is 1.5x across a 16x range of memory pressure, with no in-ram baseline, so it is not a slowdown against fitting (a5). at the other extreme, a 645 GB table on a 503 GB box with `-M` was "stuck on the first sample for days" [external: kraken2 issue #971]. so M11's gains are [UNCLEAR] until M61 sweeps the table/ram ratio. caveat (a1): Coriolis's ratio counts reference bytes, and its db's cap is unknown; a capped db does few lookups, which may explain the mild 1.5x [guess].

### 1.3 queue depth 1 is the weak point of every cold map, and it has a fix

a cpu prefetch never starts a disk read [external: PREFETCHh]. a few-read run does all its lookups on one thread, so each missing page is a blocking fault at queue depth 1. `posix_fadvise(WILLNEED)` "initiates a nonblocking read of the specified region into the page cache" [external: https://man7.org/linux/man-pages/man2/posix_fadvise.2.html, a2]. so a block's distinct missing pages can all be requested before the resolve pass (M30). PostgreSQL does the same with 16 concurrent reads by default [external: postgresql `effective_io_concurrency`, a5]. worked example [arith on external enterprise-nvme numbers, a4]: 10.7K faults at 0.106 ms = 1.13 s at queue depth 1, vs 10.7K / 151K iops ≈ 0.07 s at depth 16. the cpu cost is ~10K syscalls, ~1-2% of the time they hide [arith on a guessed 1-2 µs per call, a3]. caveat: the kernel may shrink WILLNEED reads "depending on virtual memory load" [external], exactly on small-ram boxes.

### 1.4 a fifth machine class: the small cloud vm (H5)

a4 added it, and all five accept it. example: m7i.xlarge = 4 vcpus on 2 cores x 2 smt, 16 GiB; m7g.xlarge = 4 real arm cores [external: https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html]. default gp3 storage gives 125 MiB/s, 3,000 iops, "single-digit millisecond latency" [external: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html], and shows up as `/dev/nvme*n1` like a local nvme [external: aws ebs nvme doc]. so a cold 8GB load takes ~58 s [arith], and at queue depth 1 a map can lose to the copy on an uncapped db (10.7K x 1-9 ms = 11-96 s vs 58 s) [arith]. a db restored from a snapshot reads slower still until initialized [external: aws "initialize amazon ebs volumes", a2]. a fix there that needs no code: provisioned gp3 goes to 2,000 MiB/s per volume [external], but the instance caps it (m7i.xlarge: 156.25 MB/s baseline, 1,250 MB/s max, for how long [UNCLEAR]) [external: aws gp.html], so on a small vm "provision throughput" buys at most the instance cap (M33's advice line, a5). raspberry pi 5 is treated as an H3 example, not a class.

### 1.5 smaller facts fixed

- **RC1 output**: one outside tester reports classifications and reports byte-identical to 2.17.2 at 1, 4 and 16 threads, plus a `0:0` trailing-space and a `-C` header change [external: kraken2 issue #1061, a5]. M1 must use a raw `cmp` and a whitespace-aware compare.
- **RC1 `GetBatch` has no prefetch prologue**: keys 0-7 of each read are never prefetched, and `Get` rehashes each key [external: RC1 `compact_hash.h`, a1, confirmed by a5]. under 1% on our nanopore reads [arith]; on 150 bp reads ~22% of lookups go unprefetched on an uncapped db, and all ~3 of them on a capped one [arith, a1]. M27a rides in M2's upstream pull request.
- **M2 on 8GB** is ~1.08x without S8 (1 / (0.98 x 0.97 x 0.97)) [arith on luna stage gains]; the 1.25x end needs the 16-file input.
- **M9 cells** (a4, corrected by a1/a2/a3/a5): H1 uncapped ~3.4x, capped ~34x; H2 uncapped 3.5-28x, capped ~36-290x; all at a queue-depth-1 latency of 0.1-0.5 ms [UNCLEAR], and the capped cells use f ≈ 0.10 from an old luna run, unread for today's dbs.
- **M20 cells**: orin classify ~11.6x with a parallel loader (taking stock's 4.23 s sys time as the load, [UNCLEAR]); H1 5.8-8x, ±20% between laptops with the same chip [arith on external].
- **M21** does not "let orin build": orin already runs a default-flag build. it gives a tuned arm tier (a3).
- **ck's laptop is half-populated**: the 5800h supports dual-channel ddr4-3200 [external: notebookcheck, a4]; a second dimm doubles peak bandwidth.
- **exit tax**: a 2026 kernel rfc measured 16 GB teardown at 282 ms (4 KB pages) vs 27.7 ms (thp) [external: lkml, a2]. scaled to 111 GB: ~1.96 s vs ~0.19 s [arith]. luna's measured 3.9-11.4 s is 2-6x above that, so the scaling is a prediction for E1, not a luna number.
- **the WSL2 gprof db is named**: "`~/eskape_db` - pre-built 8 GB standard" [repo: `docs/knowledge_base.md` 18.1]. luna's run (373 ns per `Get` [arith]) is the more trustworthy of the two.
- **positioning** (a5): with load included, kraken2 is already among the fastest on a big box [external: ganon2 preprint]; on small boxes the competition (Metabuli on an 8 GiB laptop, Coriolis on 4-8 GB jetsons) wins on fitting at all. so the S-chain widens a lead on H4; on H1-H3/H5 the gap is memory and storage.

---

## 2. the ranked build list (cycle 2)

how it was built: rank-sum over the five R2 top-10 lists (10 points down to 1), ties broken head-to-head. scores: M2 50, M20' 45, M9 36, M4 34, M30 24, M41 24 (M30 wins head-to-head 4-1), M5 23, M26 13, M27 11, M11 8, M40 4, M21 3 [arith]. a5 counts M30 inside M9; a2 and a5 fold M27a into M2; a1 folds M40 into M2.

merges:
- **M2 now carries four riders**: M3 (on the S19 base), M27a (prologue), M40 (`final` + one dispatch per block, if the objdump shows indirect calls), and a1's **shared per-block lookup list** on RC1's phase 1. M27b, M30, M11 and M25 all consume that list, so it is built once
- **M20' replaces M20**: threads = min(physical cores in the affinity mask, the `cpu.max` quota), loader threads not tied to an implicit 1, and M62's spill guard (RC1 workers spill output to `TMPDIR` and exit 73 without it [external: issue #1061])
- **M9 carries M24, M51 and M33**: the startup fact probe, a device micro-probe (qd1 and qd16 random reads plus one sequential read, only when the db is cold), and the "move the db / provision throughput" advice line
- **M26 absorbs M8a** as its 0.25-day first step
- **M11 absorbs M64** (compressed slices inside the sweep); standalone M13 is gone

gain = speed ratio vs the named baseline. every off-luna cell is a prediction.

| rank | id | idea | byte-identical | H1 laptop | H2 orin | H3 8 GB box | H4 big server | H5 cloud vm | cold disk | days | main risk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | M2 (+M3, M27a, M40, block list) | port S8, S12, S15, S17 (S18 if needed) onto v2.17.2 then RC1, hash once per lookup, prefetch prologue, build the per-block lookup list; send upstream | yes, vs the named upstream | 1.02-1.12x [guess] | 1.01-1.08x [guess] | 1.02-1.12x [guess] | 50MB up to 1.25x with S8 on 16-file input; 8GB ~1.08x [arith on luna stage gains] | 1.02-1.12x [guess] | 1.0x | 3-5 | S8 must be rewritten for `fast_reader`; residual over v2.17.2 unmeasured |
| 2 | M20' (+M17, M62) | default threads = min(physical cores, cpu quota); loader independent of an implicit 1; spill guard | yes | 5.8-8x for default users, ±20% by chassis [arith on external] | ~11.6x classify for default users [arith on measured stock] | 3-6x [guess] | 12.3x-30.6x, 1 vs 96 threads (the M20' default), 103GB [measured, one run per point] | 2-4x [guess] | 1.0x | < 1 | a big default on shared boxes |
| 3 | M9 (+M24, M51, M33) | load planner: copy / map / map + `MADV_RANDOM` / `O_DIRECT` and stream count from input size, residency, free ram + quota, device probe, f, kernel features; plan to stderr | yes | cold nvme few reads: uncapped ~3.4x, capped ~34x [arith on external] | cold emmc few reads: uncapped 3.5-28x, capped ~36-290x [arith, qd1 latency UNCLEAR] | runs instead of swapping when the db fits once [guess] | warm few reads 3-38x [guess, E1 not run] | capped 6-55x; uncapped can lose at qd1 without M30 [arith on external] | its purpose; one-shot runs only | 3-5 | thresholds unmeasured; `-M` on S19 never byte-checked |
| 4 | M4 | `ScanRead`: one scanner call per read, branch-free min-of-5 window, emits runs | yes (stream test) | 5-20% [guess] | 5-20% [guess] | 5-20% [guess] | 50MB 5-25%, 103GB 2-10% [guess] | 5-20% [guess] | 1.0x | 3-4 | 45 cycles per base may not be branch misses (S11) |
| 5 | M30 | cold fault-ahead: one async page-cache read per distinct missing page of a block, before resolving | yes | fault part ~10-16x [arith on enterprise nvme] | emmc 2-5x [guess, qd scaling UNCLEAR] | by device; shrinks under memory pressure [external] | raid [UNCLEAR] | fault part 3-27x [arith on external] | cold only, gated off warm | 1-1.5 | device qd scaling unmeasured |
| 6 | M41 | run-length pipeline: every stage after the scanner works per minimizer run | yes, with a1's three rules (pre-gap compare, no merge across mates, merge counts on taxon) | 2-8% [guess] | 2-8% [guess] | 2-8% [guess] | 50MB and capped dbs 3-10%, 103GB 1-4% [guess] | 2-8% [guess] | 1.0x | 3-5 | rests on "half of `ClassifySequence` is per-position overhead" [guess]; overlaps M3 |
| 7 | M5 | startup-picked parallel gunzip | yes | 3.5-5x when gz-bound [arith on guess] | 2-5x [guess] | 2-5x [guess] | 4-9x on gz input [arith on base64 gzip rate] | 1.5-3x [guess] | fewer bytes read | 0.5-3 | our inputs are plain fastq |
| 8 | M26 (+M8a) | AMAC-style `GetBatch`: a probe that runs off its line prefetches the next one and yields | yes | 0-8% uncapped, ~0 capped [guess] | same [guess] | same where it fits [guess] | 103GB 0-8%, 50MB 0 [guess] | 0-8% uncapped [guess] | warm only | 0.25 + 1.5-2 | AMAC's 1.13x was on chained buckets, not kraken2 |
| 9 | M11 (+M64) | exact out-of-core: one table sweep by slot range, queued lookups, ordered replay, compressed slices | yes, by design | [UNCLEAR] until M61; 103GB-class only among our dbs | 103GB from external storage only | [UNCLEAR] until M61 | off | 103GB-class only: ~847 s sweep at 125 MiB/s [arith] | its design case | 6-10 | KrakenUniq `--preload-size` already does it exactly [external] |
| 10 | M21 (+M42) | portable build tiers, `-ffp-contract=off`, later a shipped sampled profile | yes | 0-3% [guess] | a tuned arm tier [guess] | 0-3% | 0-3% [repo: E3 guess] | one binary across instance generations [guess] | 1.0x | 0.5 (+1) | a chore more than a speedup |

below the line, with the reason:
- **M27b** (pool lookups across reads): consumes the block list; waits on M28's short-read numbers
- **M44** (new, a3: parallel `madvise(DONTNEED)` release before exit): removes the exit tax instead of hiding it; after E1's exit column
- **M32** (detached teardown): hides the cost and may push it into a back-to-back next run, whose huge pages could then fail (a3) [guess: by analogy with luna's 20.2 s vs 13.1-13.3 s, where the 20.2 s run followed a small-page binary, not an overlapping teardown [repo: `explanations/09_S14.md`], a2]. E1 tests it with a back-to-back pair and `thp_gb` logged
- **M31** (input `DONTNEED`): gated by its `fincore` rerun check inside M61; never inside the input lock
- **M10** (`MADV_COLLAPSE`): kernel ≥ 6.1, H4 only; its exit benefit shows only where thp fails
- **M13**: folded into M11 as M64; M33 (nvme on jetsons, provisioned gp3 on H5) beats it standalone
- **M14, M15, M16, M18, M19, M7, M6**: unchanged reasons from cycle 1 (M43 may kill M18)

---

## 3. the measure-first list (cycle 2)

scores over each agent's top 5 (5 down to 1): M22 25, M1 20, E1 12, cpu gate 11, M61 6, M60 1 [arith].

| rank | what | riders | cost | decides |
|---|---|---|---|---|
| 1 | **M22** lookup census: f from each `opts.k2d`, plus counters (positions, changed, looked up, line crossings) | | 15-30 min | lookups per base per db; every per-lookup cell |
| 2 | **M1** re-baseline: S19, S19+M3, v2.17.2, RC1, 16 cells, 3 reps, load / classify / exit split | RC1 at `K2_DB_READ_THREADS` 8 and 32; RC1 `-M`; `thp_gb`; `TMPDIR` set; raw + whitespace-aware compare; RC1 `objdump` (M40); M28 short-read input at 32/64/96 threads with output to disk | ~2 h | every "vs stock" number; rebase or not; M27, M40, M6 evidence |
| 3 | **E1** `-M` vs S19 warm, 16 cells, with the correctness gate | cold pair after eviction (copy vs `-M` vs `-M` + `MADV_RANDOM`); 2-minute qd1-vs-qd16 random 4 KB read timing on `hash.k2d` (M30 / M51 kill); exit column plus one back-to-back pair with `thp_gb` (M32 / M44); M60 daemon test (20 x 1,000-read batches) | ~45 min | M9's map branches, M30, the exit tax, the few-read framing |
| 4 | **cpu gate**: `perf annotate ClassifySequence` + `perf stat -e branch-misses`, 50MB and 8GB | `perf annotate GetAt` on the saved `perf_s14_103.data` (M26) | ~20 min | M4, M41, M26 |
| 5 | **M61** sweep of table/ram ratio (0.5, 1.5, 3, 10) after per-file eviction, capped and uncapped dbs, copy and `-M` variants, `majflt` | M31's `fincore` rerun check; repeat a passing point on a laptop-class box | ~1 h | M11, M9's ram branch, M31 |

next, not ranked: the orin probe on the campus visit (`lsblk`, `lspci` for an nvme in J1, thp mode, page size, `dd iflag=direct`, qd1 latency); M43 (openmp wait/bind/output variants, may kill M18); M53 (one cloud vm run, the only route to real H5 numbers); M54 (laptop power protocol); M63 (load-included comparator run).

---

## 4. open dissent

| topic | who | position |
|---|---|---|
| M27 rank | a1 (3) vs a2, a4, a5 | a1: 0.25 day, fixes a real upstream hole. the others: under 1% on our data, short reads unmeasured, so it rides inside M2. resolved by folding M27a into M2 |
| M4 / M41 vs M9 | a3 vs a2, a4, a5 | a3 puts M4 and M41 above M9: per-position cost is the same on every db and isa, and the capped dbs small boxes carry are ~60% scanner [measured, luna gprof]. a2: on cold, small-ram and cloud boxes a load or a swap dwarfs a 2-25% cpu gain |
| M30 standalone | a5 vs a2, a4 | a5 keeps M30 inside M9 (its regime is cold, few-read, one-shot, and a daemon removes it). a2 and a4 rank it 4th (H5 depends on it) |
| M40 | a1 vs a3, a5 | a1: one keyword, inside M2. a3, a5: own row, because a 10-minute objdump can kill it |
| M13 | a4 (cycle-2 R1) | conceded in R2; folded into M64 |
| M32 vs M44 | a2 vs a3 | a3: M32 moves the cost into the next run; M44 removes it. both wait on E1's exit column |

---

## 5. the R3 vote

| agent | build list | measure list | moves asked | fact fixes (all applied) |
|---|---|---|---|---|
| a1_dsa | AGREE | AGREE | none | 150 bp: ~22% unprefetched uncapped, all on capped |
| a2_storage | AGREE | AGREE | none | M32's reason is an analogy: tag [guess]; E1 adds a back-to-back pair with `thp_gb` |
| a3_cpu | AGREE (keeps its M4/M41-above-M9 view on record) | AGREE | none | M20' H4 cell is at 96 threads, the default: 12.3x-30.6x |
| a4_hw | AGREE | AGREE | none | M9 H2 capped is ~36-290x from its own inputs |
| a5_skeptic | AGREE | AGREE | none | gp3 provisioning is capped by the instance's ebs limit; Coriolis's 1.5x has no in-ram baseline; M20' H4 at 96 threads |

result: **5 of 5 agree on both lists, no moves.** but the list differs from cycle 1's (M30 and M41 entered, M10 and M13 left, M5 and M26 moved), so cycle 2 does not count as an unchanged cycle. the stop rule needs cycles 3 and 4 to leave this list unchanged with all five agreeing.
