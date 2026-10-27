# portable kraken2: what makes it fast on any machine (FINAL, working copy)

**status: after cycle 2 of the debate. not final.** the debate stops when two cycles in a row leave the ranked list unchanged with all five agents agreeing; then two verification rounds (an audit and a red-team) by new agents. cycle 2 ended 5 of 5 agreeing, but its list differs from cycle 1's, so it does not count yet. per-cycle record: `cycle_N_conclusion.md`.

this file answers sir's question "what else gives a speedup that holds on any machine" for five kinds of machine: a one-memory-channel laptop (H1), an arm jetson (H2, orin), an 8 GB ram box (H3), a big two-socket server (H4, luna) and a small cloud vm (H5), each with a cold or warm disk. it is written for someone who knows nothing about the project. evidence tags: [repo] a file in this repo, [measured] a logged number, [arith] arithmetic shown, [guess] an estimate, [external] a fetched source, [UNCLEAR] unknown.

---

## 1. the 10-line summary for sir

1. upstream kraken2 v2.17.2 (stable, 23 sep 2026) already ships our prefetch, parallel load, memchr parser and huge pages (PR #1033); v2.18.0-RC1 also parses outside the input lock [external].
2. so S19's 1.9x-4.8x is against v2.17.1, a superseded version. S19 vs v2.17.2 is unmeasured, and it is the first thing to measure after a 15-minute lookup count [repo, external].
3. what upstream lacks is ours: S8, S12, S15, S17. porting them upstream is the most portable speedup, because it reaches the binary everyone installs: ~1.08x on 8GB, more on 50MB with many input files [arith on luna stage gains].
4. the biggest gain for users who keep the defaults is the default itself: both wrappers run 1 thread. on orin, classify with all 12 cores is ~11.6x faster than with one [arith on measured stock runs].
5. lookups per base differ ~10x between dbs: capped dbs (built with `--max-db-size`) skip most minimizers by hash [arith on repo gprof counts]. each db's cap must be read before any per-lookup prediction is trusted.
6. on cold storage and small ram, how the table gets into memory matters most, and the right way flips with the device, the input size and the db's cap. so kraken2 should pick it at startup [arith on external device numbers, unmeasured here].
7. a cold memory-mapped run reads its pages one at a time; asking the kernel for all of a block's pages at once (`posix_fadvise`) could cut that ~16x on nvme and 3-27x on cloud disks [arith on external numbers].
8. these few-read and cold wins are per one-shot run: upstream's `-D` daemon and ONT's kraken2-server already load the db once and keep it [external].
9. `-M` does run a db bigger than ram (Coriolis ran kraken2 that way on a 4 GB jetson); how badly it slows is unmeasured, so an exact out-of-core mode waits on a memory-pressure sweep [external].
10. every orin, laptop and cloud number is a prediction. first steps on luna: lookup census, re-baseline vs upstream, E1 (`-M`) with a cold pair, a cpu gate, a memory-pressure sweep. on campus: a 10-minute orin probe.

---

## 2. the ranked list (cycle 2)

the wrong intuition to drop first: "make the hot loop faster and it is faster everywhere." on luna the 50MB table sits in a 105 MB cache, so the cpu dominates. on orin (4 MB system cache) and the laptop (16 MB), even 50MB misses the cache [repo: orin llc miss rate 79-83%]. on a cold disk, a small-ram box or a cloud volume, loading dominates and no cpu fix matters. so each idea gets a gain per machine class, and most ideas help only some.

gain = speed ratio vs the named baseline. off-luna cells are predictions. full reasoning, sources and riders per row: `cycle_2_conclusion.md` section 2.

| rank | idea | byte-identical | H1 laptop | H2 orin | H3 8 GB box | H4 big server | H5 cloud vm | days | main risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **port S8/S12/S15/S17 onto upstream**, hash once per lookup, add a prefetch prologue, build one per-block lookup list; send upstream | yes, vs the named upstream | 1.02-1.12x [guess] | 1.01-1.08x [guess] | 1.02-1.12x [guess] | 8GB ~1.08x; 50MB more with 16 input files [arith] | 1.02-1.12x [guess] | 3-5 | S8 must be rewritten for upstream's new reader |
| 2 | **default threads = physical cores, capped by the cpu quota**; loader not tied to 1 thread; guard against output spill failures | yes | 5.8-8x for default users [arith on external] | ~11.6x classify [arith on measured] | 3-6x [guess] | 12.3x-30.6x, 1 vs 96 threads, 103GB [measured, one run] | 2-4x [guess] | < 1 | a big default on shared boxes |
| 3 | **load planner**: copy, map, map without read-ahead, or direct read, picked from input size, cache residency, free ram, a quick device probe and the db's cap | yes | cold nvme few reads: ~3.4x uncapped, ~34x capped [arith] | cold emmc few reads: 3.5-28x uncapped, ~36-290x capped [arith, latency UNCLEAR] | runs instead of swapping [guess] | warm few reads 3-38x [guess, E1 not run] | capped 6-55x; uncapped can lose without rank 5 [arith] | 3-5 | thresholds unmeasured; one-shot runs only |
| 4 | **branch-free batch scanner** (one call per read, minimum of 5 candidates with no data-dependent branches) | yes | 5-20% [guess] | 5-20% [guess] | 5-20% [guess] | 50MB 5-25% [guess] | 5-20% [guess] | 3-4 | may be a null like S11 |
| 5 | **cold fault-ahead**: request all of a block's missing table pages from the disk at once before resolving | yes | fault time ~10-16x [arith on external nvme] | 2-5x [guess] | by device [guess] | [UNCLEAR] | fault time 3-27x [arith on external] | 1-1.5 | device queue scaling unmeasured |
| 6 | **run-length pipeline**: every stage after the scanner works per minimizer run, not per position | yes, with three boundary rules | 2-8% [guess] | 2-8% [guess] | 2-8% [guess] | 3-10% on cpu-bound cells [guess] | 2-8% [guess] | 3-5 | rests on a guessed overhead share |
| 7 | **parallel gunzip picked at startup** | yes | 3.5-5x if input is gz [arith on guess] | 2-5x [guess] | 2-5x [guess] | 4-9x on gz input [arith] | 1.5-3x [guess] | 0.5-3 | our own inputs are plain fastq |
| 8 | **interleaved probing**: a lookup that runs off its 64-byte line prefetches the next line and lets another lookup run | yes | 0-8% uncapped dbs [guess] | 0-8% [guess] | 0-8% [guess] | 103GB 0-8% [guess] | 0-8% [guess] | 0.25-2 | the literature gain was on a different table |
| 9 | **exact out-of-core lookup** (one sequential table sweep, compressed slices) for a db bigger than free ram | yes, by design | [UNCLEAR] until the sweep | 103GB on external disk only | [UNCLEAR] until the sweep | off | 103GB-class: ~847 s sweep at 125 MiB/s [arith] | 6-10 | krakenuniq already does it exactly |
| 10 | **portable build tiers** (`x86-64-v3`, a tuned arm tier), later a shipped sampled profile | yes | 0-3% [guess] | a tuned arm tier | 0-3% | 0-3% | one binary across instance types | 0.5-1.5 | a chore, not a speedup |

worked example for rank 3: the 8GB db is 7.6 GB. on orin's emmc at 0.25-0.40 GB/s, copying it takes 19-30 s [arith on external class numbers]. a 10-read run on a capped db needs only ~1,050 table lookups [arith on a guessed cap]. memory-mapping reads only those pages: at 0.1-0.5 ms per page that is 0.1-0.5 s, so the map wins ~36-290x. with 1.87M reads the run touches every page anyway, and the copy (with huge pages) wins. same db, same machine, opposite answers: hence a startup switch. and on a default cloud disk at 1-9 ms per page, an uncapped db's map can lose to the copy unless rank 5 lifts the queue depth [arith on external].

---

## 3. what to measure first

| order | measurement | where | cost | decides |
|---|---|---|---|---|
| 1 | read each db's cap (`opts.k2d`), count positions, lookups and line crossings once | luna | 15-30 min | every per-lookup prediction |
| 2 | S19, S19 + skip-before-prefetch, v2.17.2 and RC1 on all 16 cells, load / classify / exit split, plus a 150 bp short-read input | luna | ~2 h | every "vs stock" number; rebase or not |
| 3 | E1: `-M` vs S19 warm, a cold pair after evicting the db file, a 2-minute qd1-vs-qd16 read timing, the exit tax, a daemon test | luna | ~45 min | ranks 3 and 5; the exit tax; the one-shot framing |
| 4 | cpu gate: annotate the per-read loop, count branch misses, on 50MB and 8GB | luna | 20 min | ranks 4, 6, 8 |
| 5 | memory-pressure sweep: evict the file, run under cgroup caps at table/ram 0.5 to 10, capped and uncapped dbs | luna, then a laptop-class box | 1 h | rank 9 |

then: a 10-minute orin probe on campus (storage speed, nvme slot, huge-page mode), openmp wait and binding variants, and optionally one small cloud vm run (the only way to get real H5 numbers).

---

## 4. what not to do, and why

- **do not quote S19's 1.9x-4.8x as "faster than kraken2".** it is vs v2.17.1; v2.17.2 already has half the chain [external].
- **do not quote few-read speedups without "per one-shot run".** a daemon (`-D`) or kraken2-server pays the load once [external].
- **do not build a parallel fastq parser.** upstream RC1 already parses outside the lock [external].
- **do not tune the prefetch batch on luna again.** s20 measured nothing [measured]; the amac paper also finds little gain past ~8 in flight [external].
- **do not revive the software k-mer cache, or minimizer-locality hashing.** kraken2 already stores only minimizers and skips repeats; the cache hit rate was 3.6% [repo, external].
- **do not change the hash function.** the slot is `hash % capacity`, so a new hash moves every key, needs a rebuild and loses byte identity [external: kraken2 source]. compute it once per lookup instead.
- **do not build a trie or a succinct table for speed.** one random access is the floor; they need 2-3 [repo: trie brief].
- **do not ship `-march=native` binaries**, and never override `CXXFLAGS` on the make command line (it drops `-DLINEAR_PROBING`) [repo].
- **do not hide the exit tax with a detached process.** it moves the cost into the next run [guess]; measure it first, then free in parallel if it is real.
- **do not build a standalone compressed db file.** it cannot be memory-mapped, and on jetsons and cloud vms faster storage beats it (nvme slot, provisioned volume) [arith on external]; compression belongs inside the out-of-core sweep.
- **do not quote any predicted multiplier as measured.** they rest on device class numbers at unknown queue depth and, until the caps are read, on guessed lookup counts.

---

## 5. what changed in each cycle

- **cycle 1**: upstream prior art found; lookups = d x f; S19's wasted prefetches on capped dbs; the PR #1033 x86-vs-arm pair isolates nothing; the orin "cold" run was not cold. vote: 1 of 5 agreed as drafted, all changes applied.
- **cycle 2**: few-read wins are one-shot wins (daemon mode); `-M` runs dbs bigger than ram (Coriolis); queue depth 1 is the cold map's weak point, with a `posix_fadvise` fix (rank 5); a fifth class, the small cloud vm; a run-length pipeline (rank 6); M10 and the standalone compressed file left the list. vote: 5 of 5 agree, no moves; the list changed, so the stop rule is not met yet.
