# cycle 2, round 1: a5_skeptic (2026-10-26)

role: the skeptic. this round: new prior art, counters to `cycle_1_conclusion.md` and `FINAL.md`, up to 5 ideas, and my rankings by the conclusion's ids. tags follow `00_context.md` section 6.

---

## (a) sources read this cycle

all new: i grepped the folder and none of these urls appear in any `cycle_1_*` file.

| # | source | exact claim used |
|---|---|---|
| N1 | ganon2 preprint, https://www.biorxiv.org/content/10.1101/2023.12.07.570547v1.full | "metacache and kraken2 were the fastest tools, however with a higher memory usage"; "ganon2 is the tool with the smallest memory footprint classifying reads against the full RefSeq" (~160 GB); table 4's time covers "load database in memory, classification ..."; 64 threads, "AMD EPYC 7702P ... 1TB RAM" |
| N2 | Coriolis, Mikalsen and Zola, ISMB 2023, https://academic.oup.com/bioinformatics/article/39/Supplement_1/i66/7210430 | Jetson TX1, "four-core ARMv8 processor and 4 GB of RAM", sata ssd at ~250 MB/s. memory capped with "Linux control groups (cgroups)". "The DMR expresses how many times larger the reference data is than the available memory." kraken2 2.1.2 with "the memory-mapping options", 4 threads. kraken2 throughput (HighC): 611.7 / 502.0 / 403.8 kb/min at DMR 3.25 / 6.5 / 52; Coriolis 1,323.8 / 1,311.2 / 1,251.2; Centrifuge "unable to run with DMR ≥ 6.5". kraken2's "slowdown is caused by higher I/O". Coriolis's lz4 node compression "reduces node sizes by 26%, allowing us to load more data per I/O step" |
| N3 | Coriolis project page, https://cse.buffalo.edu/~jzola/smarten/ | demo on "an NVIDIA Jetson Orin Nano with 8GB of RAM"; "Coriolis uses 1GB of RAM to cache the reference database" of a >150 GB RefSeq set; "speeds close to 50 reads/s" |
| N4 | EPI2ME kraken2-server docs, https://epi2me.nanoporetech.com/epi2me-docs/tools/kraken2-server/ | the database is loaded once into a persistent process, because loading is slow next to classification; output "is not identical" to kraken2; "public beta"; benchmarks on an M1 Max macbook and a Xeon Gold 6230 |
| N5 | kraken2 issue #1061, "2.18.0-RC1 feedback", https://github.com/DerrickWood/kraken2/issues/1061 | "Classifications and reports are byte-identical to 2.17.2, at 1, 4 and 16 threads"; a column-5 note, "Lines whose hit list is `0:0` don't get the space"; the `-C` header change "breaks anything that reads the taxid from `-C` output"; "Threads now spill rather than wait for the output lock, so if the downstream consumer stalls, spill files pile up"; a missing `TMPDIR` gives exit 73; tested "on macOS/arm64"; huge pages and parallel load shipped in 2.17.2 |
| N6 | kraken2 issue #971, https://github.com/DerrickWood/kraken2/issues/971 | "Mem: 503Gi", a 645G `hash.k2d`; without `-M`: "unable to allocate hash table memory"; with `--memory-mapping` on v2.1.6 it was "stuck on the first sample for days". still open |
| N7 | kraken2 issues for "memory-mapping", https://github.com/DerrickWood/kraken2/issues?q=is%3Aissue+memory-mapping | 51 issues. titles include #962 "Memory mapping fails under Kraken 2.1.5" and #1045 "`--memory-mapping` is silently dropped by `k2 classify`" (titles only) |
| N8 | MetaCache-GPU abstract, https://arxiv.org/abs/2106.08150 | builds "large reference databases in a matter of seconds", while kraken2 needs "over an hour for index construction". the abstract has no gpu memory or query-speed numbers, so gpu claims stay [UNCLEAR] |

re-read for a new claim (url already cited in cycle 1): RC1 `src/classify.cc` has a daemon mode, "-D Start a daemon, this options is intended to be used with wrappers". it keeps the index loaded across requests (FIFOs in /tmp, a `std::map` of loaded indexes).

failed: the EPI2ME wf-metagenomics community page (404, no claim used). ganon2's numeric tables were not in the fetched text.

repo checked: `dorado-kraken-research/Luna/bash_history.md` step 40 confirms the luna gprof run. it used `--db ~/data/kraken2_db`, 1 thread, and got 351M scanner calls and 11.6M `Get` calls.

---

## (b) counters to `cycle_1_conclusion.md` and `FINAL.md`

1. **FINAL item 8 is wrong: "an 8 GB box can only run a db bigger than its ram with an exact out-of-core mode."**
   - `-M` runs it. Coriolis measured kraken2 with memory mapping on a 4 GB jetson under cgroup caps up to DMR 52 [external: N2]. it was slower, but it ran.
   - the upstream `k2` split-db path runs too (not exact) [external: cycle-1 S6].
   - say instead: "the only byte-identical way to run it at device speed, *if* `-M` thrashes."

2. **M11's multipliers (5-236x, 10-100x) are not supported yet. the outside evidence is split.**
   - #971: a 645 GB table on a 503 GB box, `-M` "stuck ... for days" [external: N6]. that supports a need on uncapped, huge dbs.
   - Coriolis: kraken2 `-M` lost only 611.7 → 403.8 kb/min, 1.5x, from DMR 3.25 to DMR 52 [external: N2; arith]. no in-ram baseline was given. and DMR counts *reference* bytes, not kraken2 table bytes, so the table/ram ratio is [UNCLEAR].
   - so the thrash baseline itself is the unknown. M11's H1 and H3 cells should read [UNCLEAR] until M12 runs, not a range built on a guessed thrash.

3. **the few-read wins assume one load per run. upstream and ONT already avoid that.**
   - upstream kraken2 has `-D`, a daemon that keeps the index loaded between requests [external: RC1 `classify.cc`].
   - ONT's real-time path keeps the db in a persistent kraken2-server, loaded once [external: N4].
   - so S19's 9.8x-15.4x few-read cells (load-dominated [repo]) and M9's warm few-read branch (3-38x [guess]) apply to one-shot cli runs only. for a stream of small batches, the load is paid once.
   - M9's H4 warm cell should add "0 for daemon or server users".
   - the talk-track headline should say "per one-shot run".

4. **conclusion 1.1, "output-changing fixes" in RC1, is narrower than written.**
   - the one outside test says classifications and reports are byte-identical to 2.17.2 at 1, 4 and 16 threads [external: N5].
   - what does change: a trailing space on `0:0` lines in column 5 (whether that is an RC1 change is [UNCLEAR]), and the `-C`/`-U` headers [external: N5].
   - so M1 should expect identity. it should run a raw `cmp` and also a compare that ignores trailing whitespace, so a formatting diff is not read as a classification diff.

5. **M20 is missing a risk on an RC1 base.**
   - with more than one thread, RC1 workers "spill rather than wait for the output lock". spill files pile up if the consumer stalls, and a missing `TMPDIR` exits 73 [external: N5].
   - so a many-thread default changes failure behaviour on containers and small disks. it should ship with a spill guard (M62 below).
   - FINAL item 4, "the biggest gain for real users", is also unproven. the share of users who keep the 1-thread default is [UNCLEAR], and ONT's pipeline sets its own server threads [external: N4 benchmarks use 8 server threads]. say "for users who keep the default".

6. **the M2 H4 cell "1.05-1.25x on 50MB/8GB" needs splitting.**
   - on 8GB without S8: S12 gave 0 [measured], and S13 is already upstream. that leaves S15 (~2%), S17 (3%) and S18 (3%): 1 / (0.98 x 0.97 x 0.97) ≈ 1.08x [arith on luna stage gains].
   - the 1.25x end needs S8, which applies only to the 16-file input [repo].

7. **FINAL's rank-3 worked example ends "so the map wins big there".**
   - at queue depth 1 with unmeasured emmc latency, "wins" holds and "big" is unquantified [conclusion 1.5's own point].

8. **positioning, not in either file: on H1-H3 the competition beats kraken2 on memory, not speed.**
   - with load included, on a 64-thread 1 TB box, kraken2 is among the fastest and ganon2 uses the least memory [external: N1].
   - Centrifuger also found kraken2 fastest (load excluded) [external: cycle-1 S7]. Metabuli's own text says Kraken2X was fastest [external: cycle-1 S8].
   - but Metabuli ran on an 8 GiB m1 laptop [external: cycle-1 S8], and Coriolis on 4-8 GB jetsons with a 1 GB cache [external: N2, N3].
   - so on H4 kraken2 already leads, and the S-chain widens a lead. on H1-H3 the gap is fitting at all. that is where M9, M11 and capped dbs matter. FINAL's "what makes it fast on any machine" should say so.

9. **the conclusion's f evidence: the luna run is the trustworthy one. say why.**
   - luna's `Get` costs 23.23% x 18.617 s / 11.6M ≈ 373 ns per call [arith on repo], plausible for a dram miss plus a 4 KB page walk.
   - the WSL2 run's ~7.2 µs per call [arith, a4] is not plausible. so 1.2 should lead with luna's 1 per 30, and give f ≈ 0.10 on `~/data/kraken2_db` [arith with d = 0.316].
   - whether that file is today's `standard_8gb` stays [UNCLEAR].

10. **comparator gpu tools: no number exists here.** the MetaCache-GPU abstract gives build speed only [external: N8]. nothing in the repo should claim a gpu classifier speed or memory figure.

---

## (c) ideas (compact format)

### M60. daemon amortization test (measure first)
1. **name:** measure upstream's `-D` against one-shot runs. byte-identical is the hypothesis, checked by `cmp`.
2. **mechanism:**
   - wrong intuition: "few-read runs are load-bound, so the loader must get faster."
   - real: a persistent process loads once and serves many requests [external: RC1 `-D`, N4].
   - worked example: S19 at 103GB with 1,000 reads is 3.95 s, nearly all load [repo]. 100 such batches cost ~395 s as cli runs, but ~4 s + 100 x (classify time) through a daemon [arith on measured; classify per batch UNCLEAR].
3. **gain per class:**
   - H4: large for streams of small batches [arith]; 0 for one big run.
   - H2/H1 cold: the cold load is paid once per boot instead of per batch [guess].
   - H3: unchanged; the db still has to fit.
4. **days:** 0.25.
5. **risk:** `-D` uses fixed FIFO names in /tmp [external], so two users on luna may collide. the output may differ [UNCLEAR].
6. **cheapest kill test:** 20 × 1,000-read batches via `-D` vs 20 cli runs on 8GB. kill M9's warm branch for repeated-batch users if `-D` matches the cli output and amortizes the load.
7. **sources:** RC1 `classify.cc`, N4.

### M61. M12 revised as a DMR sweep, with the baseline Coriolis lacks
1. **name:** measure. same binaries, byte compare.
2. **mechanism:**
   - wrong intuition: "one cap at 8 GB answers 'does `-M` thrash'."
   - real: Coriolis's curve shows kraken2 degrading 1.5x over a 16x range of memory pressure [external: N2], while #971 shows "days" [external: N6]. the answer depends on the table/ram ratio and on the lookup density (d x f).
   - so: caps at table/ram ≈ 0.5, 1.5, 3 and 10, on one capped and one uncapped db, after per-file eviction. run copy, `-M`, RC1 `-M` and `-M` + `MADV_RANDOM`. log `majflt` and wall.
3. **gain per class:** none itself. it decides M11 (H3, low-ram H1) and M9's ram branch.
4. **days:** 0.5.
5. **risk:** luna's raid serves faults fast. a pass on luna does not clear a laptop (a2, cycle 1).
6. **cheapest kill test:** the two highest-ratio points on the uncapped db. if wall stays within 3x of the 0.5 point, kill M11.
7. **sources:** N2, N6, cycle-1 S16.

### M62. spill guard for the RC1 out-of-lock path
1. **name:** byte-identical (output order is unchanged).
2. **mechanism:** when `TMPDIR` is missing or nearly full, wait for the output lock instead of spilling. RC1 exits 73 today [external: N5].
3. **gain per class:** 0 speed. it removes a failure mode M20 would expose on containers and small disks (H1, H3) [guess].
4. **days:** 0.5. it is an upstream patch.
5. **risk:** none for output.
6. **cheapest test:** RC1 `-p 16` with `TMPDIR=/nonexistent` on a cpu-bound run, as N5 did.
7. **sources:** N5.

### M63. one load-included comparator run (positioning, measure)
1. **name:** RC1 / S19 vs Centrifuger and Metabuli on the same reads, plus Centrifuge (sir's named baseline [repo: root `CLAUDE.md`]). report wall with load and peak rss, uncapped and under one cgroup cap.
2. **mechanism:**
   - wrong intuition: "the paper's claim is speed."
   - real: on a big box kraken2 already leads [external: N1, cycle-1 S7, S8]. on small boxes its weakness is memory [external: N1, N2, N3]. the comparison has to show both.
3. **gain:** none. it decides which classes the paper can claim.
4. **days:** 2-4, mostly index builds [guess].
5. **risk:** different dbs make the comparison unfair. use the same reference set.
6. **cheapest test:** Centrifuge alone on the 50MB-class reference.
7. **sources:** N1, N2, cycle-1 S7, S8.

### M64. M13 moves inside M11: compressed slices for the out-of-core sweep
1. **name:** byte-identical (lossless).
2. **mechanism:** Coriolis compresses index nodes with lz4 so each i/o step loads more [external: N2, 26% smaller]. a standalone compressed container fights `-M` (conclusion, M13). inside M11's sweep there is no map to fight, and every byte saved is device time. the floor is the 1.37x zero-cell bitmap [arith, a2].
3. **gain:** only where M11 runs: H3, low-ram H1, orin with 103GB external. the sweep is ≈ 1/ratio of its table i/o [arith].
4. **days:** +1-2 on top of M11.
5. **risk:** decode cpu on small arm cores [UNCLEAR].
6. **cheapest test:** `zstd -1` / `lz4` ratio on two dbs (already a free gate).
7. **sources:** N2.

---

## (d) rankings

### build, top 10 (conclusion ids)

| rank | id | one line |
|---|---|---|
| 1 | M2 (+M3) | still the only way a gain reaches every installed binary. its 8GB cell is ~1.08x without S8 (counter 6) |
| 2 | M20 (+M17 obey, +M62 guard) | tiny, every class, for default users. ship it with the spill guard on an RC1 base |
| 3 | M9 | cold and ram-tight branches stand. the warm few-read branch waits on M60 |
| 4 | M4 | the scanner is the top cpu share; the 15-minute branch-miss gate first |
| 5 | M5 | MinKNOW users get `.fastq.gz`. 0 for our inputs |
| 6 | M8a | 0.25 day, ram-bound boxes only, after the free annotate |
| 7 | M11 (+M64) | H3's only byte-identical route at device speed. gated by M61. cells [UNCLEAR] until then |
| 8 | M21 | packaging. lets orin build |
| 9 | M10 | big server on new kernels only |
| 10 | M62 | listed on its own so it is not lost if M20 slips |

M13 as a standalone format drops out; it lives on as M64 inside M11.

### measure first, top 5

| rank | what | why |
|---|---|---|
| 1 | M22 lookup census | f per db. luna's run already gives ~0.10 on one capped db (counter 9) |
| 2 | M1 | with `TMPDIR` set, and a raw plus whitespace-aware compare (counter 4) |
| 3 | E1 | M9's map branches |
| 4 | M60 daemon test | 20 minutes. decides whether the few-read regime matters for repeated batches (counter 3) |
| 5 | M61 (= M12 as a DMR sweep) | the thrash curve, not one point (counter 2) |

the orin probe is not ranked here because it cannot run on luna. it rides on the first campus visit whatever its rank.

**do i want the cycle-1 list changed?**
- build list: no reorder. M62 joins M20, M13 folds into M11 as M64, and the cell fixes in counters 2, 3, 5 and 6 apply.
- measure list: yes. M60 enters at 4, and M12 becomes the M61 sweep at 5.
