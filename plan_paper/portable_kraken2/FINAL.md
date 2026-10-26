# portable kraken2: what makes it fast on any machine (FINAL, working copy)

**status: after cycle 1 of the debate. not final.** the debate continues until two cycles in a row leave the ranked list unchanged with all five agents agreeing, then two verification rounds (an audit and a red-team) by new agents. this file is rewritten after each cycle. the per-cycle record is `cycle_N_conclusion.md`.

this file answers sir's question "what else gives a speedup that holds on any machine", for five kinds of machine: a one-memory-channel laptop (H1), an arm jetson (H2, orin), an 8 GB ram box (H3), a big two-socket server (H4, luna), each with a cold or warm disk. it is written for someone who knows nothing about the project. evidence tags: [repo] a file in this repo, [measured] a logged number, [arith] arithmetic shown, [guess] an estimate, [external] a fetched source with its url, [UNCLEAR] unknown.

---

## 1. the 10-line summary for sir

1. upstream kraken2 v2.17.2 (stable, 23 sep 2026) already ships our prefetch, parallel load, memchr parser and huge pages (PR #1033), and v2.18.0-RC1 also parses outside the input lock [external].
2. so S19's 1.9x-4.8x is against v2.17.1, a superseded version. S19 vs v2.17.2 is unmeasured, and that is the first thing to measure [repo, external].
3. what upstream lacks is ours: S8 (one input stream), S12 (no division), S15 (run counts), S17 (rolling reverse complement). porting them upstream is the most portable speedup, because it reaches the binary everyone installs [external, a5's source read].
4. the biggest gain for real users on any machine is a default: both kraken2 wrappers run on 1 thread unless told otherwise [external]. using the physical cores gave 11.4x on orin's 50MB db [measured, stock v2.1.3].
5. lookups per base differ ~10x between dbs: capped dbs (built with `--max-db-size`) skip most minimizers by hash [arith on repo gprof counts]. every "per lookup" prediction must be redone per db once we read each db's cap (5 minutes).
6. S19's prefetch stage hashes and prefetches every position, including skipped ones, so on a capped db it may fetch ~10 ram lines per real lookup that nothing reads [arith on a guessed cap]. upstream does not [external].
7. on cold storage and small ram, how the table gets into memory matters most: copy, memory-map, or map with read-ahead off. the right choice flips by device and input size, so it should be picked at startup [arith on external device numbers, unmeasured here].
8. an 8 GB box can only run a db bigger than its ram with an exact out-of-core mode. krakenuniq already does this with identical output: 48 h memory-mapped vs 47 min chunked on a 392 GB db [external].
9. every orin and laptop number is still a prediction. orin's one "cold" run in the repo was not cold, and its kernel probably already uses huge pages, so S14 may do nothing there [external config, guess].
10. first steps on luna: read each db's cap, re-baseline S19 vs v2.17.2 and RC1 on all 16 cells, then E1 (`-M`) and a small-ram test. on campus: a 10-minute orin probe.

---

## 2. the ranked list (cycle 1)

the wrong intuition to drop first: "make the hot loop faster and it is faster everywhere." on luna the 50MB table sits in a 105 MB cache, so the cpu dominates. on orin (4 MB system cache) and the laptop (16 MB), even 50MB misses the cache [repo: orin llc miss rate 79-83%]. and on a cold disk or a small-ram box, loading dominates and no cpu fix matters. so each idea gets a gain per machine class, and most ideas help only some classes.

gain = speed ratio vs the named baseline. off-luna cells are predictions. full reasoning and sources per cell: `cycle_1_conclusion.md` section 2.

| rank | idea | byte-identical | H1 laptop | H2 orin | H3 8 GB box | H4 big server | cold disk | days | main risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **port S8/S12/S15/S17 onto upstream, send upstream** (on the S19 base instead: skip repeated and capped minimizers before prefetching) | yes, vs the named upstream | 1.02-1.12x [guess] | 1.02-1.10x [guess] | 1.02-1.12x [guess] | 1.05-1.25x on 50MB/8GB [arith on luna stage gains] | 1.0x | 3-5 | S8 must be rewritten for upstream's new reader |
| 2 | **default threads = physical cores** (and the loader stops ignoring an explicit `--threads`) | yes | 5-8x for default users [guess] | 11.4x on 50MB, 4.5x on 16GB [measured, stock] | 3-6x [guess] | 12.7x-30x on 103GB, 1 vs 64 threads [measured, one run] | 1.0x | < 1 | a big default on shared boxes |
| 3 | **load planner**: copy, map, map with read-ahead off, or direct read, picked from input size, cache residency, free ram, storage class and the db's cap | yes | cold nvme few reads ~3x [arith] | cold emmc few reads 5-30x [arith, iops UNCLEAR] | runs instead of swapping [guess] | warm few reads 3-38x [guess, E1 not run] | the point of it | 3-5 | thresholds unmeasured |
| 4 | **branch-free batch scanner** (one call per batch, minimum of 5 candidates without data-dependent branches) | yes | 5-20% [guess] | 5-20% [guess] | 5-20% [guess] | 50MB 5-25% [guess] | 1.0x | 3-4 | may be a null like S11 |
| 5 | **parallel gunzip picked at startup** | yes | 3.5-5x if input is gz [arith on guess] | 2-5x [guess] | 2-5x [guess] | 4-9x on gz input [arith on external] | fewer bytes read | 0.5-3 | our own inputs are plain fastq |
| 6 | **next-line prefetch** when a lookup's cell sits at the end of a 64-byte line, only when the table is bigger than the cache | yes | 2-8% [guess] | 2-10% [guess] | 2-8% [guess] | 0-8% on big dbs [guess] | 1.0x | 0.25 | hardware may already do it |
| 7 | **exact out-of-core lookup** for a db bigger than free ram | yes, by design | 10-100x vs thrashing, uncapped dbs [guess] | 103GB only [guess] | 5-236x vs thrashing, by device [arith on guesses] | off | its design case | 6-10 | complex; spill space |
| 8 | **portable build tiers** (`x86-64-v3`, armv8.2), never ship `-march=native` | yes | 0-3% [guess] | lets orin build at all [external] | 0-3% | 0-3% | 1.0x | 0.5 | a chore, not a speedup |
| 9 | **huge pages that land** (`MADV_COLLAPSE` after load; 2 MB file pages for `-M`) | yes | new kernels only | none (5.10 kernel) | new kernels only | bad 103GB runs ~20 s to 13-16 s [arith + guess] | 1.0x | 1.5-2 | the 103GB variance may have another cause |
| 10 | **compressed db file** made from the existing `hash.k2d`, no rebuild | yes | 1.0x warm | cold emmc 8GB 26 s to 14-19 s [arith on class numbers] | ≈ ratio cold | 1.0x warm | ≥ 1.37x smaller [arith] | 3-4 | cannot be memory-mapped |

worked example for rank 3, so the idea is concrete: the 8GB db is 7.6 GB. on orin's emmc at a class rate of 0.25 GB/s, copying it takes 7.6 / 0.25 = 30 s [arith on external class number]. a 10-read run needs only ~1K-10K table lookups, depending on the db's cap [arith]. memory-mapping with read-ahead off reads only those pages, a few MB to ~44 MB. so the map wins big there. but on the same run with 1.87M reads, the run touches every page anyway, and the copy (with huge pages) wins. same db, same machine, opposite answers: hence a startup switch.

---

## 3. what to measure first

| order | measurement | where | cost | decides |
|---|---|---|---|---|
| 1 | read each db's cap (`minimum_acceptable_hash_value` in `opts.k2d`), count lookups once | luna | 15-30 min | lookups per base per db; every per-lookup prediction |
| 2 | S19, S19 + skip-before-prefetch, v2.17.2 and RC1 on all 16 cells, load / classify / exit split | luna | 1.5-2 h | every "vs stock" number; rebase or not |
| 3 | E1: `-M` vs S19 warm, plus one cold pair after evicting the db file | luna | 30 min | the load planner's map branch |
| 4 | small-ram emulation: evict the file, run under a cgroup memory cap | luna, then a laptop-class box | 1 h | whether out-of-core is needed |
| 5 | orin probe: storage speed (`dd iflag=direct`), thp mode, page size | orin, campus | 10 min | every H2 cell |

---

## 4. what not to do, and why

- **do not quote S19's 1.9x-4.8x as "faster than kraken2".** it is vs v2.17.1; v2.17.2 already has half the chain [external].
- **do not build a parallel fastq parser.** upstream RC1 already parses outside the lock, and by the repo's own arithmetic it only binds near 60+ threads [external, arith].
- **do not tune the prefetch batch on luna again.** s20 (16 to 64) measured nothing [measured]; upstream exposes `K2_PREFETCH_DIST` already.
- **do not revive the software k-mer cache, or minimizer-locality hashing (kache-hash style).** kraken2 already stores only minimizers and skips repeats, so that locality is built in; the cache hit rate was 3.6% [repo, external].
- **do not build a trie or a succinct table for speed.** one random access is the floor; tries and mphf/elias-fano need 2-3 [repo: trie brief]. they are thesis 2 space results at best.
- **do not ship `-march=native` binaries**, and never override `CXXFLAGS` on the make command line (it drops `-DLINEAR_PROBING` and silently changes output) [repo].
- **do not lift the 32-thread loader cap blindly.** on a hard disk parallel streams seek; on network storage one stream left 2/3 of the device idle [external, guess]. the stream count belongs to the load planner.
- **do not quote any predicted multiplier (3-50x cold, 30x emmc, 900 s thrash) as measured.** they rest on class numbers at unknown queue depth and, until the cap is read, on the wrong lookup count [arith].
- **do not spend effort on numa or `MADV_COLLAPSE` first.** they help one class (big servers on new kernels).

---

## 5. what changed in each cycle

- **cycle 1**: upstream prior art found; lookups = d x f; S19's wasted prefetches on capped dbs; the PR #1033 x86-vs-arm pair isolates nothing; the orin "cold" run was not cold. ranked list built, vote not unanimous (4 of 5 asked for a change, all applied).
