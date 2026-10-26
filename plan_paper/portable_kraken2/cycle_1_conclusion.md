# cycle 1 conclusion: one ranked list, with open dissent (2026-10-26)

this file closes cycle 1 of the portable-kraken2 debate. it exists so the next cycle starts from one list instead of five. it records what the five agents found, the ranked list the relay built from their R2 rankings, the R3 vote, the changes the vote forced, and the dissent that is still open. the transcript is `cycle_1_r1_*.md` (proposals), `cycle_1_r2_relay_brief.md` (merged ids), `cycle_1_r2_*.md` (counters), `cycle_1_r3_vote_*.md` (votes).

evidence tags as in `00_context.md`: [repo], [measured], [arith], [guess], [external], [UNCLEAR].

---

## 1. five findings that changed the debate

### 1.1 upstream kraken2 already shipped half the S-chain

the wrong intuition: "stock is v2.17.1, so S19's 1.9x-4.8x is how much faster we made kraken2."

what is true:
- the stable release **v2.17.2** (23 sep 2026) contains PR #1033 [external: https://github.com/DerrickWood/kraken2/releases/tag/2.17.2]
- PR #1033 gives the table 2 MB alignment + `MADV_HUGEPAGE`, a parallel `pread` load with `K2_DB_READ_THREADS` (default 8), upstream kseq with `memchr` and a 64 KB buffer, and batched lookups with prefetch distance `K2_PREFETCH_DIST` (default 8). it claims byte-identical output [external: https://github.com/DerrickWood/kraken2/pull/1033]
- **v2.18.0-RC1** (20 oct 2026) adds a parser that runs outside the input lock, plus output-changing fixes (a minimizer undercount, a stricter fastq parser) [external: https://github.com/DerrickWood/kraken2/releases/tag/v2.18.0-RC1]

a1, a3 and a5 found this on their own, and the relay re-fetched it. so S9, S10, S13, S14 and S19 have public prior work. what upstream lacks, by a5's read of the RC1 source: S8 (one input stream), S12 (no division), S15 (run-length counts), S17 (rolling reverse complement). S18 is [UNCLEAR] [external: a5 cycle-1 S4].

what this means: "byte-identical vs stock" must name the version. the honest headline is S19 vs v2.17.2, and nobody has measured it.

### 1.2 lookups per position = d x f, not one number

the wrong intuition: "the minimizer changes about once every 3 positions, so every db does about 1 lookup per 3 bases."

two numbers have to be kept apart:
- **d** (density): how often the minimizer changes from one k-mer position to the next
- **f** (kept fraction): the share of hash space a capped db keeps. a `--max-db-size` build sets `minimum_acceptable_hash_value`, and classify skips any minimizer hashing below it [external: kraken2 `build_db.cc` and `classify.cc`, via a1]. f = 1 for an uncapped db

what the repo's counts give:
- **d ≈ 0.316**: in the WSL2 gprof run, 3,220,914 distinct hit minimizers (`HyperLogLogPlusMinus::insert` calls) / 10,179,375 hit positions (`hit_counts[taxon]++` calls) = 0.316 [arith on repo: `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`]. it matches the random-order value 0.333 for kraken2's window [external: Kille et al., via a1]. a 5-wide window also forces d ≥ 0.222 [external, via a4]
- **lookups per position in two old runs**: WSL2 run, 9,871,933 `Get` / 354,164,193 scanner calls = 1 per 36 [arith on repo]. luna's own stock v2.1.3 gprof run on `~/data/kraken2_db` (the standard 8 GB db): 11.6M `Get` / 351M scanner calls = 1 per 30 [repo: `dorado-kraken-research/Luna/bash_history.md` step 40, `dorado-kraken-research/CLAUDE.md`]
- so those dbs kept f ≈ 0.08-0.10 [arith: (1/36 or 1/30) / 0.316]. a gprof undercount of `Get` could also explain part of it [guess, a5]

what is **not** known: f for the dbs we use today. luna's `AccuracyDrift/databases/standard_8gb` and `standard_16gb` are capped standard builds by name [repo], but their f is [UNCLEAR], and an unsourced repo note says standard_8 has a cap of 0 [repo: `kraken2_get_optimizations_v2.md` S3]. the 50MB db is our own build, so its cap is [UNCLEAR] too. M22 below reads them in 5 minutes.

the speed data fit a small f on the 8GB db: at 1 thread it classifies faster per read than the 50MB db on both luna (16.78 s vs 19.73 s) and orin (21.19 s vs 47.53 s) [repo: `RESULTS.md` 2.3]. and 103GB looks uncapped: stock at 1 thread costs 162.6 ns per base there; take away the ~56 ns per base of non-lookup work seen on the L3-resident 50MB db, and ~107 ns per base is lookup waiting. at 1 lookup per 36 bases that would be ~3.9 µs per lookup, impossible with a warm table. at ~1/3 it is ~320 ns, one dram miss plus a page walk [arith on measured, two sessions, a2].

### 1.3 S19 may send billions of prefetches nobody reads on capped dbs

S16's `fill()` hashes and prefetches every k-mer position before the resolve loop checks repeats and the cap [repo: `plan_paper/scripts/s6plus/s16_patch.py` lines 23-26 vs 46-50]. stock v2.17.1 hashed only on a change [external: a5 cycle-1 S5]. so on every db, 1 - d ≈ 67-78% of `fill()` hashes and prefetches are thrown away [arith]. on a capped db the capped-out minimizers add d x (1 - f) wasted ram-line prefetches per position. if f ≈ 0.09, that is about 10 per real lookup and 1.8-2.4 billion lines, 115-154 GB of traffic per full 8GB input (a3) [arith on a guessed f]. luna has the bandwidth to absorb it; a one-channel laptop may not [guess]. upstream never issues them (`TOK_SKIP`, `TOK_REPEAT`) [external: a1 cycle-1 src 2].

### 1.4 the only cross-isa number does not isolate anything

PR #1033 measured its bundle at 1.32x on graviton4 and 1.65x on x86 at 8 threads [external: PR #1033]. a4 checked the instances: r7i.2xlarge is 4 cores x 2 smt threads, r8g.2xlarge is 8 real cores [external: https://docs.aws.amazon.com/ec2/latest/instancetypes/mo.html]. the pair also mixes clang and gcc, and the whole bundle. so it supports no claim about prefetch alone, or about arm vs x86 (a5). it is still the only off-luna measurement of these mechanisms, and its cold load (~100 s to 34 s on network block storage) is the only cold loader number anyone has.

### 1.5 orin facts in the repo are shaky

- the one "cold" orin run read 7.6 GB at ~2.5 GB/s, above emmc hs400's 400 MB/s ceiling, so it was not cold [repo + external, a4, a5]. orin cold speed is unmeasured. planning range 0.25-0.40 GB/s [external class numbers]
- orin's kernel config (the L4T 5.10 tree) defaults thp to "always" with 4 KB pages [external: OE4T linux-tegra-5.10 `mm/Kconfig`, a4]. if the shipped kernel matches [guess], S14 buys ~0 there
- a few-read cold `-M` run is queue depth 1: one thread does all the lookups of one input block (~10K on an uncapped db, ~1K on a capped one [arith]), and a prefetch cannot fault a page in [external: PREFETCHh "does not affect program behavior", a5 + guess]. so the map cost is fault latency at queue depth 1, unmeasured on every machine

what this means: every orin and laptop gain below is a prediction until E2 and the orin probe run.

---

## 2. the ranked build list (cycle 1, after the vote)

how it was built: each agent's R2 top 10 scored 10 points down to 1 (rank-sum, a "borda count"), ties broken by head-to-head majority. scores: M2 48, M9 37, M20 35, M4 33, M3 27 (two more agents count it inside M2), M17 23, M11 19, M8a 19, M10 16, M5 16, M21 4, M13 3 [arith]. then the R3 vote moved four ids (section 5).

merges:
- **M3 rides with M2.** on an upstream base it costs 0 days. on the S19 base it is a half-day build
- **M17 splits.** "obey `--threads`" ships inside M20: both wrappers default to 1 thread, so obeying alone would load 103GB on one thread for every default user (a3: up to ~15x slower load) [external: `scripts/kraken2`, `scripts/k2`; arith on measured]. the device-aware stream count moves inside M9
- **M24 (a4's startup probe) is part of M9**

gain = speed ratio vs the named baseline. every off-luna cell is a prediction.

| rank | id | idea | byte-identical | H1 laptop | H2 orin | H3 8 GB box | H4 big server | cold disk | days | main risk | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | M2 (+M3) | port S8, S12, S15, S17 (S18 if needed) onto upstream v2.17.2 then RC1; hash once per lookup in `GetBatch`; send upstream. on the S19 base, M3 instead (skip repeats and capped minimizers in `fill()`) | yes, vs the named upstream | 1.02-1.12x [guess] | 1.02-1.10x [guess] | 1.02-1.12x [guess] | 1.05-1.25x on 50MB/8GB full input [arith on luna stage gains] | 1.0x | 3-5 (M3 alone 0.5) | S8 must be rewritten for `fast_reader`; residual over v2.17.2 unmeasured | stage gains [measured, luna]; absence upstream [external] |
| 2 | M20 (+M17 obey) | default threads = physical cores in the affinity mask and cgroup quota; loader threads independent of an implicit 1; an explicit `--threads` bounds both | yes | 5-8x for default users [guess] | 11.4x on 50MB, 4.5x on 16GB for default users [measured: orin stock v2.1.3 scaling, `RESULTS.md` 1.4] | 3-6x [guess] | 12.7x (stock) to 30x (s10), 1 vs 64 threads on 103GB [measured, one run per point, includes an unexplained superlinear low-thread effect] | 1.0x | < 1 | rude default on shared boxes; quota detection [UNCLEAR] | wrapper defaults [external]; `modes.sh` 1 and 7 threads [repo] |
| 3 | M9 | load planner: map / copy / `O_DIRECT` / `MADV_RANDOM` and stream count, picked at startup from input size, residency, free ram + cgroup limit, storage class, f, kernel features; plan printed to stderr | yes | cold nvme few reads ~3x at queue depth 1 [arith on a4 external 0.106 ms]; full input 1.0x | cold emmc few reads 5-30x [arith on class iops at unstated queue depth, UNCLEAR]; full input 1.0x | runs instead of swapping when the db fits once [guess] | warm few reads 3-38x on big dbs [guess, E1 not run] | hdd: keep copy for ≤ 8GB-class; map wins on 103GB at few reads [guess] | 3-4 + 1 probe | thresholds unmeasured; `-M` on S19 never byte-checked | E1/E4 not run; KrakenUniq leaves the choice to the user [external] |
| 4 | M4 | scanner with one call per batch (or per read on RC1) and a branch-free min-of-5 window; scalar, every isa | yes (stream-equivalence test) | 5-20% [guess] | 5-20% [guess] | 5-20% where cpu-bound [guess] | 50MB 5-25%, 103GB 2-10% [guess] | 1.0x | 3-4 | 45 cycles per base may not be branch misses (S11 precedent) | mechanism [external: SimdMinimizers]; misses unmeasured |
| 5 | M5 | startup-picked parallel or faster gunzip (rapidgzip / igzip / pigz), per-file detection | yes | 3.5-5x when gz-bound [arith on guess] | 2-5x; gz input fits orin's disk [guess] | 2-5x [guess] | 4-9x on gz full input [arith on a gzip rate measured on base64 data; fastq rate UNCLEAR] | fewer input bytes read | 0.5 + 2-3 | our inputs are plain fastq, so 0 for every repo number | minknow example names `.fastq.gz` [external] |
| 6 | M8a | next-line prefetch when the home cell sits near the end of its 64 B line, only when the table is bigger than the llc | yes | 2-8% [guess] | 2-10% [guess] | 2-8% [guess] | 50MB off; big dbs 0-8%, maybe a small loss [guess] | 1.0x | 0.25 | fill-buffer contention; hardware prefetcher may already cover it | crossing rates 7% hit / 32% miss [arith]; none measured |
| 7 | M11 | exact out-of-core lookup for a db bigger than free ram: one table sweep by slot range, lookups queued per slice, answers replayed in order | yes, by design | 3-4 GB free: 10-100x on uncapped 8GB+ full input vs `-M` thrash [guess] | only 103GB from external storage [guess] | uncapped dbs: nvme 40-236x, sata/emmc 5-26x vs thrash [arith on guessed thrash, f = 1]; capped dbs ~10x less thrash to beat [arith] | off | it is the cold design | 6-10 | probe runs past slice edges; spill space; record design disputed | KrakenUniq `--preload-size`: identical output, 48 h mapped vs 47 min chunked [external] |
| 8 | M21 | portable build tiers (`x86-64-v3`, armv8.2) with E3's lto/pgo, `-ffp-contract=off`, never ship `-march=native` | yes, if fp contraction is off | 0-3% [guess] | lets orin build: gcc-11 `-march=native` fails there [external] | 0-3% | 0-3% [repo: E3 guess] | 1.0x | 0.5 | a packaging chore more than a speedup | E3 not run |
| 9 | M10 | huge pages that land: `MADV_COLLAPSE` after the copy (part A), 2 MB file mappings for `-M` (part B) | yes | kernel ≥ 6.1 only [external] | none: 5.10 kernel, thp likely already "always" | as H1 | bad 103GB sessions ~20 s to 13-16 s [arith + guess] | collapse faults non-resident pages first | 1.5-2 | variance cause unproven; reclaim hurts other users | kernel docs [external]; luna variance [measured] |
| 10 | M13 | compressed db container made from the existing `hash.k2d` (zero-cell bitmap or zstd frames), no rebuild | yes | 1.0x warm; cold nvme ≈ ratio on the load | cold emmc 26 s to 14-19 s on 8GB [arith on class numbers] | ≈ ratio on a cold load | 1.0x warm | 1.37x floor by arithmetic at load 0.70 | 3-4 | cannot be memory-mapped (workaround: decompress once to `/dev/shm`, then map, a2) | floor [arith]; device speeds unmeasured |

below the line, with the reason:
- **M15** lower-density sampling: not byte-identical, needs a rebuild and a canonical scheme that may not exist at (5, 31) [external: Kille et al.]; on capped dbs it trades for accuracy per byte, not speed. a thesis 2 item
- **M18** online thread controller: only a4 ranks it. at M20's default the measured gap is ~3%, inside noise [measured]
- **M14** numa policy: big server only; interleave is one `numactl` flag
- **M16** miss prefilter: the hash cap already prefilters capped dbs for free; panel dbs on small-llc boxes only
- **M19** prefetch-depth probe: s20 null on luna [measured]; E2 step 6 decides orin for free
- **M7** simd scanner: gain is largest on the box that needs it least; after M4
- **M6** out-of-lock parser: upstream RC1 has it; it comes with M2

---

## 3. the measure-first list (cycle 1, after the vote)

scored the same way over each agent's top 5 (M1 24, M22 17, E1 13, M12 9, orin probe 8 [arith]). the vote then put M22 first, because it takes 5-30 minutes and both M1's capped-vs-uncapped split and the E1 and M12 predictions need its f values (a1).

| rank | what | cost | what it decides |
|---|---|---|---|
| 1 | **M22** lookup census: read `minimum_acceptable_hash_value` from each `opts.k2d` (f = 1 - value / 2^64, `kraken2-inspect` prints it as "Min clear hash value" [external: `dump_table.cc`, via a3]), then one throwaway counter build (positions, changed, looked up) on 50MB and 8GB | 15-30 min | d and f per db; resizes M3, M8, M9, M11, M12, E1 |
| 2 | **M1** re-baseline: S19, S19+M3, v2.17.2 and RC1 on all 16 cells, 3 reps, load / classify / exit split, RC1 at `K2_DB_READ_THREADS` 8 and 32, RC1 `-M`, `thp_gb`; byte compares RC1 vs v2.17.1 on a capped and an uncapped db | ~1.5-2 h on luna | every "vs stock" number, whether to rebase (M2) or stay on S19 (M3), how much of S10's lead is one env var |
| 3 | **E1** `-M` vs S19 warm, 16 cells, with the correctness gate, plus one cold pair (16GB, 10 reads, after per-file eviction: copy vs `-M` vs `-M` + `MADV_RANDOM`) | ~30 min | M9's map branches |
| 4 | **M12** small-ram emulation: evict the db file, then run inside `systemd-run --user --scope -p MemoryMax=8G` (and 4G), capped and uncapped dbs, log `majflt`. a pass on luna must be repeated on a laptop-class box before M11 is dropped, because luna's raid serves faults faster (a2) | ~1 h | whether M11 is needed; M9's ram branch |
| 5 | **orin state probe**: `lsblk`, `getconf PAGESIZE`, thp mode, `AnonHugePages` during a stock load, `dd iflag=direct` sequential, a queue-depth-1 random 4 KB read loop. rides on the first campus visit, since it cannot run on luna (a4) | ~10 min | conflicts 2 and 3; M9 and M13 on H2; whether S14 does anything on arm |

free gates to run alongside: awk miss fraction over output column 5 (M8, M16), `perf annotate GetAt` on the saved `perf_s14_103.data` (M8), `perf stat -e branch-misses` on S19 50MB (M4), `zstd -1` ratio on two dbs (M13), wall vs `thp_gb` over 6 runs or `thp_fault_fallback` (M10), a `.fastq.gz` timing (M5).

new measure ids (renumbered here, because agents reused M22):
- **M22** lookup census (a1's K1, a3's and a5's M22)
- **M23** `scan_test.cc`: a scanner-only timer that dumps the (value, ambiguous) stream. it gives scanner ns per base on each class and is M4's equivalence test (a3)
- **M24** startup fact probe: sysfs cores / smt / sockets / llc, rotational, thp mode, meminfo and cgroup limits, `opts.k2d`, residency; prints the plan (a4; counted inside M9)
- **M25** block-sorted dedupe of lookups across reads: 70% of real lookups repeat within one 104,918-read file [arith on repo M5 + d]. measure the repeat share vs block size first (a1)

---

## 4. open dissent

| topic | who | position |
|---|---|---|
| M3 rank | a1, a3 vs a2, a5 | a1 and a3 put M3 first: half a day, and M1 is unfair without it. a2 and a5 count it inside M2. resolved for now by building S19+M3 as a column of M1 |
| M9 size | a2, a4 vs a3, a5 | a2 and a4 quote large cold gains. a5: emmc 11K iops is a class row at unstated queue depth, and few-read faults run at queue depth 1, so no multiplier is a planning number. the direction holds. the vote moved M9 below M20 |
| M10 | a2 (R2 rank 4) vs a4 (rank 12) | a4: dead on orin, rhel 8/9 and jetpack kernels, so it is a big-server item. the vote moved it to 9 |
| M11 design | a1, a3 vs a2 | a1: 16-byte records, no second scan. a2: 4-byte in-slice offsets, one sweep, re-scan the reads when tokens do not fit. a3 prefers a1's (the scanner is ~60% of cycles on a capped db [measured: luna gprof]) |
| M11 need | a3 vs a5 | a3: capped dbs do ~10x fewer lookups, so `-M` may cope and M11 is mainly for uncapped big dbs. a5 ranked it 5th. the vote moved it to 7 |
| M8a trigger | a1 vs a3, a4 | a1: last 6 cells (+37.5% lines). a3: start at the last 2 (+12.5%). a4: gate on table > llc |
| M5 | a5 vs a2, a3, a4 | a5: our input is plain fastq, and the gzip rate is from base64 data. the others: minknow users get `.fastq.gz` [external: ONT output spec example]. the vote moved it to 5 |
| M18 | a4 vs everyone | a4 keeps it in the top 10 for smt boxes; the rest say M20 covers the measured case |

---

## 5. the R3 vote

| agent | build list | measure list | change asked | applied? |
|---|---|---|---|---|
| a1_dsa | AGREE | DISSENT | M22 before M1 | yes |
| a2_storage | AGREE | AGREE | fix M9's H1 cell (qd1, ~3x) | yes (a fact fix, not a reorder) |
| a3_cpu | DISSENT | AGREE | M5 to 5, M11 to 8 | M5 to 5 yes; M11 to 7 (a4's move put M21 at 8) |
| a4_hw | DISSENT | AGREE | M10 to 9, so M5 and M21 rise | yes |
| a5_skeptic | DISSENT | AGREE | M20 to 2, M9 to 3 | yes |

result: **not unanimous.** 1 of 5 agreed with both lists as drafted. every change asked for was applied in full or within one rank, so cycle 2 starts from this list.

facts fixed after the vote (all accepted):
- section 1.2 had d upside down, and stated f = 0.088 as if it were our 8GB db. it is the WSL2 db's; luna's run gives 1 per 30; ours stay [UNCLEAR] until M22 (a1, a3, a4, a5)
- the "cross-check" in the draft rearranged the same ratio, so it proved nothing. removed (a5)
- the 3.9 µs figure needs the 56 ns subtraction stated (a1)
- section 1.4 claimed the PR pair shows where prefetch helps. it shows nothing that specific (a5)
- M9's H1 cell was 3-50x; at queue depth 1 it is ~3x (a2, a5)
- M11's H3 cell assumed f = 1; now scoped to uncapped dbs (a5)
- M20's H2 cell lacked the measured 4.5x on 16GB (a4). its H4 30x is one run with an unexplained superlinear effect (a5)
- M5's H4 rate comes from base64 data (a5)

stop-rule status: cycle 1 is the first list, so it cannot count as an unchanged cycle. the debate continues.
