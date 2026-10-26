# cycle 1, round 2, a4_hw (hardware spread)

role: for every idea, what it does on H1 laptop, H2 orin, H3 8 GB box, H4 big server, and cold vs warm storage. this round: settle conflicts 1-3, counter the other agents' top 3, revise my own ideas after v2.17.2 / RC1, rank, and fill the grid.

R1 sources are cited as "R1 src N" (my `cycle_1_r1_a4_hw.md` list). other agents' sources are cited as "a2 src N", "a5 S3" and so on.

---

## sources fetched this round

1. **PR #1033 page**, https://github.com/DerrickWood/kraken2/pull/1033 . claims used: the benchmark machines are "r8g.2xlarge (Graviton4, clang)" and "r7i.2xlarge (x86, gcc)", on EBS volumes whose "throughput has been cranked up to 1GB/s". the times are "Wall times (classification rate as reported by kraken2)": graviton4 266 s to 202 s, x86 337 s to 204 s, 8 threads, "5 GB/side paired FASTQ". the cold load on graviton4 went "roughly 100 s → 34 s (~3x)" on a "~34 GB hash". the context section says "A 1.3-1.7x improvement in classification throughput". the page does not say whether the classify runs were warm. the nfs / spinning-disk worry is a reviewer's guess, with no measurement. supports: section 1.
2. **aws memory-optimized instance table**, https://docs.aws.amazon.com/ec2/latest/instancetypes/mo.html . claims: r7i.2xlarge = 64 GiB, "Intel Xeon Sapphire Rapids", 8 vCPUs, **4 CPU cores, 2 threads per core**. r8g.2xlarge = 64 GiB, "AWS Graviton4 Processor", 8 vCPUs, **8 CPU cores, 1 thread per core**. supports: section 1.
3. **OE4T linux-tegra-5.10, branch `oe4t-patches-l4t-35.5.0`, `arch/arm64/configs/defconfig`**, https://raw.githubusercontent.com/OE4T/linux-tegra-5.10/oe4t-patches-l4t-35.5.0/arch/arm64/configs/defconfig . claims: "CONFIG_TRANSPARENT_HUGEPAGE=y"; no `TRANSPARENT_HUGEPAGE_MADVISE` line; no `ARM64_64K_PAGES` or `ARM64_16K_PAGES` line; "CONFIG_ARM64_VA_BITS_48=y". the file `tegra_defconfig` in the same folder contains only the word "defconfig" [guess: a link to this file]. supports: conflict 3.
4. **same tree, `mm/Kconfig`**, https://raw.githubusercontent.com/OE4T/linux-tegra-5.10/oe4t-patches-l4t-35.5.0/mm/Kconfig . claims: the choice "Transparent Hugepage Support sysfs defaults" has "default TRANSPARENT_HUGEPAGE_ALWAYS". `READ_ONLY_THP_FOR_FS` exists, labelled "(EXPERIMENTAL)". supports: conflict 3, the M10 counter.
5. **same tree, `arch/arm64/Kconfig`**, https://raw.githubusercontent.com/OE4T/linux-tegra-5.10/oe4t-patches-l4t-35.5.0/arch/arm64/Kconfig . claim: the page-size choice has "default ARM64_4K_PAGES". supports: conflict 3, M10.

caveat on 3-5: OE4T is the yocto community mirror of nvidia's L4T kernel, not the binary kernel shipped in jetpack R35.4.1 on our orin. that the shipped kernel uses the same config is a [guess]. one `cat` on orin settles it.

repo files read this round: `cycle_1_r2_relay_brief.md`; the four R1 files of a1, a2, a3, a5 in full; `dorado-kraken-research/WSL2/kraken2/gprof_report.txt` (the call counts and times); `dorado-kraken-research/docs/reports/kraken2_get_optimizations_v2.md` S3.

---

## 0. the conflicts, settled where i can

### conflict 1: lookups per base

the wrong intuition: "one number, about 1/3, fits every db". it can't. lookups per base = **d x f**, where:
- **d** (density) = how often the minimizer changes from one k-mer position to the next. for kraken2's window (w = 5 l-mers of 31), any forward scheme has d ≥ 0.222, and a random order gives 0.333 [external: a1 src 5, table 1]. so d sits in 0.222-0.333.
- **f** = the share of hash space the db keeps. `--max-db-size` builds set `minimum_acceptable_hash_value`, and classify skips the lookup for any minimizer that hashes below it [external: a1 src 2, upstream `classify.cc`; repo: `s9_patch.py` lines 74-75]. f = 1 for an uncapped db.

so a5's gprof figure (9,871,933 `Get` calls for 354,164,193 `NextMinimizer` calls, 1 per 36 [repo: `WSL2/kraken2/gprof_report.txt` lines 6-7]) **is not a density**. 1/36 = 0.028 is 8x below the 0.222 floor [arith]. it has two possible causes:
1. that wsl2 db was capped, with f ≈ 0.028 / 0.222-0.333 = 0.08-0.13 [arith], or
2. a counting artifact. the same profile gives `Get` 71.30 s of self time over 9.87M calls = 7.2 µs per call [arith], about 70x one ram trip. that is impossible for one probe unless the count is low or each call faulted [guess].

both causes are [UNCLEAR]. neither touches d.

the speed data back f < 1 on our capped dbs:
- at 1 thread, the 7.6 GB 8GB db classifies faster than the 50MB db on both machines: orin 21.19 s vs 47.53 s, luna 16.78 s vs 19.73 s [repo: RESULTS.md 2.3]. a db 150x bigger is faster per read. that only fits fewer lookups.
- S19 at 32 threads: 8GB 9.18 s vs 50MB 8.88 s [repo: talk track 5]. a ram-bound db almost ties a db that sits in l3.
- the repo note "standard_8 has `minimum_acceptable_hash_value == 0`" [repo: `kraken2_get_optimizations_v2.md` line 85] was about a prebuilt index on minerva. it disagrees with this speed evidence, so i treat it as unverified for our 8GB/16GB.

what it moves:
- **M3**: hardly. its waste is per position, so it holds for any d: 1 - d = 67-78% of `fill()` calls are wasted [arith]. the cap-skip half grows as f shrinks.
- **M9 / E1 touched fraction**: L = bases x d x f. on a capped db the map/copy crossover moves up by about 1/f in read count [arith]. so the planner must read f at startup.
- **M8, M11, M16**: all scale with d x f.

the 5-minute fix: dump `k`, `l` and `minimum_acceptable_hash_value` from every db's `opts.k2d` [UNCLEAR: exact field layout, `transplant.cc`'s `read_opts` already parses it, repo]. f = 1 - value / 2^64 [guess on the formula].

### conflict 2: orin cold read speed

two claims can be settled. the speed itself cannot.
- the repo's one "cold" run (`OBSERVATIONS.md` item 84) **was not cold**. the 7.6 GB file would have come in at ~2.5-2.6 GB/s [arith]. but the board's storage is "64GB eMMC 5.1" [R1 src 1], and `Orion.md` shows the 57 GB root on it [repo]. emmc hs400 tops out at a theoretical 400 MB/s [R1 src 3]. so a5's branch "or the device is far faster" needs a non-emmc root device. `lsblk` rules that out in 2 seconds.
- the planning range is 0.25-0.40 GB/s sequential: the emmc 5.1 class figure is 250 MB/s [R1 src 3], a xavier nx emmc measured 294 MB/s [a2 src 18], an i.mx8 emmc 280 MB/s [R1 src 5], and the hs400 ceiling is 400 MB/s. random 4 KB reads: 11,000 iops class figure [R1 src 3]. our board itself: [UNCLEAR] until `dd iflag=direct`.

### conflict 3: orin thp mode

prediction strengthened, not yet measured. the L4T 5.10 kernel tree sets `CONFIG_TRANSPARENT_HUGEPAGE=y` with no madvise override [external: src 3], and the Kconfig default for that choice is "always" [external: src 4]. base pages are 4 KB by default [external: src 5].

so orin most likely runs thp in **always** mode with 4 KB base pages [external config + guess that jetpack ships this config]. that fits R1's anomaly: stock's warm load on orin runs ~3.5 GB/s per thread vs luna's ~2.0 GB/s [R1 arith]. under "always", stock's big table allocation already gets 2 MB pages where 2 MB-aligned ranges allow.

consequences, all [guess] until checked:
- S14 (and upstream's `MADV_HUGEPAGE`) adds ~0 on orin, apart from direct compaction under a fragmented heap
- stock on orin already has most of S14's tlb benefit, so E2's few-read speedups on 8GB/16GB will be smaller than next_steps' 3-10x. my estimate is 2-6x, all from S10
- 4 KB base pages mean the 2 MB alignment in S14 is the right size there. the 512 MB pmd trap (R1 src 13) applies only to 64K-page kernels

check (E2 step 1 already has the first): `cat /sys/kernel/mm/transparent_hugepage/enabled`, `getconf PAGESIZE`, and `grep AnonHugePages /proc/meminfo` while a stock 16GB run loads.

### conflict 4: M3's gain

a1 (-4 to -7%) and a3 (~4.7%) agree once d is a range. 7.0% `PrefetchIndex` share [measured] x 67-78% wasted calls = 4.7-5.5% upper bound on luna 50MB [arith]. that holds only if those cycles are instructions, not waiting [UNCLEAR]. a3's `perf record` test settles it.

---

## 1. what PR #1033's 1.32x (graviton4) vs 1.65x (x86) tells my class model

the wrong reading: "prefetch and huge pages help x86 more than arm". the two machines differ in more than the isa.

1. **the numbers are classify time only.** the PR reports "classification rate as reported by kraken2" [external: src 1]. the cold load (100 s to 34 s) is a separate line. so 1.32x and 1.65x are classify gains, not load gains.
2. **"8 threads" is not the same machine size.** r7i.2xlarge has 4 physical cores with smt (2 threads per core). r8g.2xlarge has 8 physical cores [external: src 2]. smt (simultaneous multithreading) means two threads share one core's out-of-order window and its miss buffers (16 l1 fill buffers on golden cove [R1 src 9]). so the x86 run had half the cores, with two threads squeezed onto each.
3. **per physical core**, the sapphire rapids core did 1.58x the graviton4 core's work in stock and 1.98x after the bundle [arith: (8 x 266) / (4 x 337) and (8 x 202) / (4 x 204)]. stock graviton4 was 1.27x faster in total [arith: 337 / 266], and after the bundle the two tie (~203 s).
4. **reading.** software prefetch gains most where each thread has the least hardware to hide latency on its own, for example two smt threads sharing one core [guess]. graviton4's 8 private cores already hid more of the latency, so it had less left to win. this is an smt-and-core-size effect, not an isa verdict.
5. **huge pages on arm.** the PR says the huge-page effect is "most pronounced on aarch64" [a5 S3], yet the arm gain was the smaller one. if graviton's distro kernel runs thp in "always" mode, as orin's very likely does (conflict 3), stock already had huge pages there, and that half of the bundle was worth ~0 [guess]. this would explain the gap without any isa argument.
6. **the first cold loader data point anyone has.** 34 GB in ~100 s = 0.34 GB/s with stock's single stream. 34 GB in 34 s = 1.0 GB/s with 8 streams, which equals the provisioned ebs ceiling [arith on external src 1]. so one stream left 2/3 of a network block device idle. this backs M9/M17's device-aware stream count, and it is the opposite of the hdd case.

**what changes in my class model:**
- detect **physical cores and smt**, never trust a thread count. sysfs `thread_siblings_list` gives it [R1 src 10]. this feeds M20 and M18.
- **graviton4 ≠ orin.** the a78ae is the smaller core [UNCLEAR: sizes not fetched], so it may need prefetch more than graviton4 did. my H2 prediction for the prefetch stages' classify gain on big dbs: **1.2-1.6x** [guess]. the low end comes from graviton4's 1.32x, the high end from r7i's 1.65x and luna's 1-thread 1.46x [measured]. on orin's 50MB db the gain should still beat luna's, because 50MB misses orin's caches and fits luna's l3 [repo].
- **r7i.2xlarge is the best public proxy for H1**: an 8-thread x86 slice on 4 smt cores, with a ram-bound 35 GB db. its 1.65x classify is my anchor for "S9/S13/S14 on a laptop-sized x86" [external + guess].
- **S14 on H2 → ~1.0x** (conflict 3). **S10 on H2 warm** stays 3-6x on the load [R1 guess], now measured against a stock that probably already has huge pages.

---

## 2. counters to the other agents' top 3

format: what breaks, which class it hurts, what is cheaper, does the evidence hold.

### a1_dsa

**M3 (a1 #1, a3 #1): hash and prefetch only changed minimizers.**
- evidence: holds. the waste is per position (the scanner returns every position [a1 src 1]), so 67-78% of `fill()` calls are wasted for any d [arith]. it doesn't depend on conflict 1.
- hardware: a repeated prefetch to a line already in flight should merge into the fill buffer that already tracks it, not take a new one [guess]. so it frees instructions, not memory parallelism. the gain is largest where the core is cpu-bound: luna 50MB.
- the cap-skip half is a **bandwidth** saving. on a capped db S19 prefetches lines for minimizers it never looks up: d x (1 - f) wasted ram lines per position [arith]. that matters most on a one-channel box (H1), and its size waits on f.
- cheaper: if M2 is a rebase onto RC1, M3 is already done (RC1 skips repeats with `TOK_REPEAT` [a3 S4]): 0 days. build it on its own only if the paper keeps the v2.17.1 lineage.
- class hurt: none.

**M8 (a1 #2): line-aware probe.**
- what can break: part a adds up to 37.5% more line fetches [a1 arith]. they compete for the same 16 l1 fill buffers that S16's up to 32 in-flight lookups already exceed [R1 src 9 + repo]. so on luna it can delay home-line prefetches and be a null or a small loss [guess]. on smt cores two threads share those 16, which is worse.
- bandwidth is fine everywhere: H1 at 8 threads goes from ~4.6 to ~6.3 GB/s of lookup traffic [arith on R1 guess], against 15-23 GB/s achievable.
- intel's adjacent-line prefetcher may already bring the partner line of a 128 B pair [UNCLEAR: not fetched]. that covers at most the crossings where the next line is the partner [guess].
- cheaper: gate part a on "table bytes > llc size" from sysfs [R1 src 10]. then luna's 50MB never pays, and H1/H2, where every db is ram-bound, get it. a1's free `perf annotate` test comes first.
- part b (in-line simd compare): no hardware objection. `GetAt` is 12.5% on luna 50MB [measured].

**M11 (a1 #3, a2 #3, a5 B4): exact out-of-core lookup.**
- what breaks: the worked examples all assume nvme at 2-3 GB/s. typical H3 storage is slower: sata ssd 333 MB/s [R1 src 5], emmc 250 MB/s [R1 src 3]. a1's 11 sweeps x 15 GB = 165 GB then take 500-660 s, not 55-83 s [arith]. that is still 5-26x better than a1's own thrash estimate of 3,300-13,000 s [arith], but no longer "minutes".
- spill writes on flash: emmc 5.1 writes at 125 MB/s sequential [R1 src 3]. a2's ~8 GB of offsets plus answers for the full input is ~64 s of writes [arith], plus flash wear [guess]. orin has 8.5 GB free [repo], so spill and db don't fit together there.
- prior art is strong: KrakenUniq `--preload-size` does exactly this with "identical" results [a5 S13], and Kun-peng uses 4 GB blocks [a5 S14]. only the code for kraken2's own table is new.
- evidence: KrakenUniq's 48 h (mapped) vs 47 min (8 GB chunks) vs 14 min (preload) [a5 S13] supports the order of magnitude.
- cheaper: run M12 first. if `-M` under the cap is within ~3x of warm, kill it.
- class: H3 and low-free-ram H1, plus H2 only for the 103GB db from external storage. 0 on H4.

### a2_storage

**M9 (a2 #1, mine #1): the path-picking loader.** i agree with the frame. four hardware fixes:
- a2's "cold, few reads → `-M` + `MADV_RANDOM`" branch needs the **rotational** flag too, not only in the stream count. on an hdd, copy beats map for 8GB at 10 reads (51 s vs 71 s), and map wins on 103GB below ~100 reads [R1 arith on guessed hdd numbers].
- a2's `O_DIRECT` branch makes every later run cold. on a box where the db fits twice (orin with 8GB), every run would pay ~26-30 s instead of a warm 2-4 s [arith]. a2 gates it on `MemAvailable` < 2x table, which is right. keep that gate strict.
- the touched-fraction model needs **f** (conflict 1). nobody listed it as a startup fact. it comes from `opts.k2d`.
- orin's 5.10 kernel lacks `cachestat`, `MADV_POPULATE_READ` and `MADV_COLLAPSE` [a2 kernel table]. so the planner's orin path is `mincore` plus a parallel touch loop.
- plus a portability point: PR #1033 left the mmap path untouched [external src 1], so M9 is also an upstream contribution.

**M10 (a2 #2): huge pages that land.**
- what breaks: kernel spread. `MADV_COLLAPSE` needs 6.1+ [a2 src 2]. orin's 5.10: dead [a2]. rhel 8 (4.18), rhel 9 (5.14) and jetpack 6 (5.15) are below 6.1 [guess, from memory, not fetched]. so it is dead on most hpc clusters and on every jetson, and alive on ubuntu 22.04 hwe / 24.04 and debian 12 [guess].
- `READ_ONLY_THP_FOR_FS` is "(EXPERIMENTAL)" in the 5.10 tree [external src 4]. on luna's 6.8 it is [UNCLEAR]. if it's off, part B route 2 is dead.
- class hurt: on small-ram boxes (H1, H3), collapse's direct compaction evicts page cache that M9's map branch depends on [guess]. so M10 should never run when M9 picked the map branch for ram reasons.
- on orin with thp "always" (conflict 3), part A buys nothing.
- cheaper: a2's own no-code test (wall vs `thp_gb` over 6 alternating runs) kills or keeps part A in 30 minutes.
- my rank: 12. it is H4 plus new kernels.

**M11 (a2 #3):** see a1 above.

### a3_cpu

**M3 (a3 #1):** see a1 above.

**M4 (a3 #2): branch-free min-of-5 batch scanner.**
- evidence: the 45-57 cycles per base mixes a 32-thread profile share with an 8-core run time [a3's own caveat]. luna had no smt sharing at 32 threads, so the mix is fair. the branch-miss story is a hypothesis with a 15-minute test. good.
- hardware: the mispredict rate is a property of the data (random pop counts) [a3], so it should be similar on every core. the penalty per miss differs by core [UNCLEAR: none fetched for zen 3, a78ae, golden cove]. the branch-free form is a chain of 4 dependent min operations per base [a3]. on a narrow core that chain's latency could eat part of the gain [guess].
- cheaper and decisive for "any machine": a3's `scan_test.cc` on luna, orin and a linux laptop gives scanner ns per base per class. that is the one per-class cpu number we lack.
- switch: only the window size w = k - l + 1 from `opts.k2d` (min-of-5 when w = 5, else the fallback). w is a db fact, not a hardware one.

**M5 (a3 #3): startup-picked parallel gunzip.**
- hardware: on orin, a parallel inflater competes with classify for the same 12 cores. the gain is the serial wall it removes, not the cpu it uses [guess].
- a hardware case a3 half-made: gz shrinks the input 3-4x [a3 guess on ratio]. that puts the 12.5 GB input under orin's 8.5 GB free disk [repo], which opens E2's 1,872,777-read column, and it cuts a cold emmc input read from ~50 s to ~12-17 s [arith on 0.25 GB/s].
- evidence: whether real inputs are gz is [UNCLEAR]. ours are plain [repo].
- my rank: 7, conditional on gz input.

### a5_skeptic

**M1 (a5 B1): re-baseline vs v2.17.2 and RC1.** strong support. three hardware additions:
1. run RC1 at `K2_DB_READ_THREADS` = 8 (its default) and 32, so the S10 vs RC1 load gap separates stream count from code
2. log load / classify / exit separately (`split_sweep.sh`). PR #1033's arm result is hard to read precisely because it gives one number
3. add RC1 as a third binary in E2 on orin. that is what jetson users will install. RC1 moved to c++17 [a3]; orin's gcc version is [UNCLEAR], E2 step 1 prints it

M1 is luna-only, so it says nothing about H1-H3 by itself.

**M2 (a5 B2): residual stages onto RC1, upstream.** right vehicle, smaller off-luna gain:
- the residuals (S8, S12, S15, S17, S18) are instruction savings. on H1/H2 even 50MB is ram-bound [repo: orin llc miss 79-83%, 16 MB laptop l3], so their share of wall shrinks. 1.02-1.12x vs RC1 [guess], below a5's luna 1.14x [a5 arith].
- S8 is 0 on single-file input [repo], and smaller with fewer threads, because fewer threads sit idle at each barrier [guess].
- S12's gain depends on the 64-bit divide's latency, which is [UNCLEAR] on a78ae and zen 3.
- if M2 is done as a rebase onto RC1, M3 and M6 come free.

**M12 (a5 B3): cgroup small-ram emulation.** support, with two hardware fixes:
1. luna's raid and controller cache serve random reads faster than an H3's sata or emmc [a5 agrees]. so log `majflt`, then convert to per-device wall with R1's device table: emmc ~11K iops, enterprise nvme ~9.4K iops at qd1 and ~151K at qd16 [R1 src 3, 6, arith]. one luna run then predicts H3 on three device classes
2. a cgroup emulates ram size only. for the small-llc regime of H1/H2, use eskape_650mb (142 MB, past luna's l3 cliff [repo]) as the "small db that misses the llc" proxy, pinned to one socket. luna can't shrink its l3 without root [guess]

### ranked wrong, in my view

- **M13 (compressed container):** cold only, ≤ 1.37-2x on the load [a2, a5 arith]. it can't be memory-mapped [a5], so it fights M9 on exactly the cold few-read cells where M9's map branch wins 5-30x. its real H2 value is disk footprint (8GB db 7.6 to ~5.5 GB on 8.5 GB free [a2 arith]). rank 13.
- **M16 (miss prefilter):** needs table > llc > filter. on orin an 8 MB bitmap misses the 2 MB cluster l3 + 4 MB system cache [arith], so ~0. only H1 with 50MB qualifies. rank 16.
- **M6 (out-of-lock parser):** H4 only by a3's own arithmetic (knee ~60 threads). free with a rebase. not a separate build.
- **M15 (lower-density sampling):** biggest H3/H2 lever (smaller db, fewer lookups), but not byte-identical and needs a canonical scheme that may not exist [a1]. kept out of the byte-identical top 10.

### ids that are one idea, and one new id

- **M17's stream count lives inside M9** (a2's table already has stream count by device). M17 then shrinks to "the loader obeys `--threads`, the affinity mask and the cgroup cpu quota, plus one stream on rotational / network devices". RC1 has the same load-before-`omp_set_num_threads` order [a3 note 7, a5 S4], so it is an upstream patch.
- **M3 and M6 are in M2** if M2 is a rebase.
- **M14 is mine and a2's**; use a2's version, because `mbind(MPOL_INTERLEAVE)` also takes the range out of numa-balancing scans [a2 src 10, 11].
- **M19 becomes "set `K2_PREFETCH_DIST` from a probe"**, since upstream already reads that variable [a1 src 3].
- **new M22: one startup fact probe.** it reads sysfs (physical cores, smt siblings, sockets, llc size [R1 src 10]; rotational, `read_ahead_kb` [R1 src 11]; thp mode and `hpage_pmd_size` [R1 src 12]), `/proc/meminfo` and the cgroup limits, the db's `opts.k2d` (k, l, f) and table bytes, and file residency (`mincore`). it prints all of it plus the chosen plan to stderr. M9, M17, M20, M18 and the M8a gate all need it. ~1 day [guess]. it doubles as a measurement tool: run it once on orin, the laptop and luna, and my class table fills itself. i count its days inside M9.

---

## 3. my revisions after v2.17.2 / RC1 and the other agents

| my R1 idea | now | why |
|---|---|---|
| idea 1 → M9 | merged with a2's version. adds the rotational rule on the few-read branch, f, and M22 as its probe. 3-4 days | a2's 4-probe frame plus my device model; PR #1033 left mmap untouched [external src 1] |
| idea 2 → M17 | shrunk to the obey-threads / quota / rotational fix; the stream logic moves into M9. 0.5-1 day | upstream has the same order bug [a3, a5]. the PR's own reviewer worried about nfs and spinning disks [external src 1]. the ebs data point shows the opposite need on network flash (section 1 item 6) |
| idea 3 → M18 | unchanged. re-check the high-thread plateau on RC1 inside M1 | RC1's out-of-lock parser may move it [a5 S4] |
| idea 4 → M14 | use a2's mbind version | a2 src 10, 11 |
| idea 5 → M19 | now "set `K2_PREFETCH_DIST`". H2 ceiling lowered from 0-10% to 0-5% [guess] | graviton4 gained least from prefetch (section 1) |
| R1 A3 prediction table | S14 on H2 → ~1.0x. S9/S16 on H2 big dbs → 1.2-1.6x classify. "threads" → physical cores | conflict 3, section 1 |
| R1 H1 | kraken2 can't run on the laptop today. the user memory notes no wsl there since july 2026 [repo: memory]. a2's wsl2 6.6 kernel comes from an older matmul run [a2]. wsl2 also sits on hyper-v, which already broke perf counters in this repo [repo: `dorado-kraken-research/CLAUDE.md`]. so any H1 kraken2 number needs a native linux boot (live usb) | testability |

---

## 4. ranking

### (a) top 10 build list

1. **M2**: residual stages (S8, S12, S15, S17, S18) rebased onto RC1 and sent upstream. the only way a gain reaches every class is inside the binary users install. M3 and M6 come free.
2. **M9 (+ M22 probe)**: the load planner. the biggest per-class wins (cold few reads 5-50x on flash, "runs instead of swaps" on small ram), byte-identical, and it applies to upstream's untouched mmap path.
3. **M20**: default thread count = physical cores (not vCPUs). a few lines. 5-30x for anyone who forgets `--threads`, measured on luna and orin.
4. **M3**: dedupe the hash and prefetch in `fill()`. 0.5 day on the S19 lineage, 0 days if M2 rebases. every class, plus a bandwidth saving on capped dbs.
5. **M4**: branch-free min-of-5 scanner. the one cpu idea that carries to every isa equally. after a3's 15-minute `perf stat`.
6. **M17**: the loader obeys `--threads` / affinity / quota, and uses one stream on rotational or network-file devices. tiny, upstream-able, guards the hdd/nfs case.
7. **M5**: startup-picked parallel gunzip. huge when the input is gz, 0 when it isn't. it also fits orin's disk.
8. **M11**: exact chunked out-of-core lookup. the only route for H3 to run 16GB+ on a full input. build only after M12 says `-M` thrashes.
9. **M8 part a**: next-line prefetch, gated on table > llc. targets H1/H2, where every db is ram-bound. cheap.
10. **M18**: online thread-count controller. H4 and smt boxes, measured 13-14% spread.

below the line: M14 (11, H4 only), M10 (12, new kernels only), M13 (13), M21 (14, portable build tiers: a correctness and portability chore, 0-3% [repo E3 guess]), M19 (15), M16 (16). M15 is outside the byte-identical list.

### (b) top 5 measure-first

1. **M1**: S19 vs v2.17.2 vs RC1, 16 cells, RC1 at `K2_DB_READ_THREADS` 8 and 32, load / classify / exit split, plus an RC1 vs v2.17.1 byte compare. it fixes every "vs stock" number.
2. **orin facts + E2** (~1 h on campus): `lsblk`, `getconf PAGESIZE`, the thp mode, `AnonHugePages` during a stock load, `cache/index*/size`, `dd iflag=direct` for the device ceiling, one evicted cold stock load, then stock / RC1 / S19 on the 9 runnable cells with the split. it settles conflicts 2 and 3, S14 on arm, and the first non-luna S-chain number.
3. **lookups per base** (conflict 1): dump k, l and `minimum_acceptable_hash_value` from every `opts.k2d` (5 min), then one counter build on 50MB and 8GB (15 min). it sets M3's cap half, M8, M9's crossovers and M11's sizing.
4. **E1 + one cold pair**: `-M` vs S19 warm on 16 cells, plus 16GB at 10 reads after eviction, copy vs `-M` vs `-M` + `MADV_RANDOM`. it decides M9's map branches.
5. **M12**: cgroup caps at 8G and 4G after eviction, 8GB and 16GB, 10 / 1,000 / 104,918 reads, logging `majflt`, converted to H3 wall per device class with R1's device table. it decides M11.

---

## 5. the grid

gain = speed ratio vs the named baseline (M2 vs RC1, M20 vs a default 1-thread run, the rest vs S19). "1.0x" means no change. every cell is tagged. the last column says whether the M-id needs a startup switch and which detected fact drives it.

| M-id | H1 laptop | H2 orin | H3 8 GB box | H4 luna | cold disk | switch / fact |
|---|---|---|---|---|---|---|
| **M2** residuals on RC1 | 1.02-1.12x full input [guess] | 1.02-1.10x; S8 1.0x on single-file input [guess, repo] | 1.02-1.12x on dbs that fit [guess] | 50MB/8GB full input 1.05-1.25x [arith on measured stage gains, a5's 1.14x, + S8]; 103GB 1.0-1.1x [guess] | 1.0x [guess] | none |
| **M9** load planner | cold nvme few reads 3-50x [arith on R1 src 5, 6]; warm few reads [UNCLEAR until E1]; full input 1.0x | cold emmc few reads 5-30x [arith: copy 26-30 s vs map 1-5 s]; full input 1.0x | db fits once not twice: runs instead of swapping [guess]; bigger: hands off to M11 | warm few reads 3-38x on big dbs [repo: E1 guess]; full input 1.0x | flash and emmc as H1/H2; hdd: copy kept for ≤ 8GB-class (1.0x), map ~10x on 103GB at ≤ ~100 reads [R1 arith on guessed hdd] | yes: input bytes, residency (`mincore`), MemAvailable + cgroup `memory.max`, storage class (rotational, device name), f and table bytes, kernel features |
| **M20** default threads | up to 5-8x for default users [guess, anchored on orin's 11.4x at 12 cores, repo] | 11.4x on 50MB, 4.5x on 16GB for default users [measured: orin stock v2.1.3 scaling, repo] | 3-6x on 4-8 cores [guess] | 103GB full input 12.7x (stock) to 30x (s10), 1 to 64 threads [measured sweep] | 1.0x on a device-bound load [guess] | yes: physical cores (`thread_siblings_list`), affinity mask, cgroup `cpu.max` |
| **M3** dedupe in `fill()` | 2-5%, plus a bandwidth saving on capped dbs [guess; size UNCLEAR until f] | 2-6% [guess] | 2-5% [guess] | 50MB ≤ 4.7-5.5% [arith on measured 7.0%]; 103GB 0-2% [guess] | 1.0x | none (0 days if M2 rebases) |
| **M4** branch-free scanner | 5-20% [guess] | 5-20% [guess] | 5-20% where cpu-bound [guess] | 50MB 5-25%, 103GB 2-10% [guess]; real only if ≥ 0.2 branch misses per base | 1.0x | db fact w = k - l + 1 from `opts.k2d` |
| **M17** loader obeys threads | 1.0x vs S19; 1-4x vs a 1-stream loader cold [measured smoke] | 1.0x [guess] | hdd box: 1-3x cold load [guess] | 1.0x speed; stops 32 loader threads on a shared box [repo] | hdd 1-3x [guess]; network block storage needs ≥ 8 streams, 1 stream got 1/3 of the ceiling [arith on external src 1] | yes: `--threads`, affinity, `cpu.max`, rotational, device class |
| **M5** parallel gunzip (gz input only) | 3.5-5x when gz-bound [a3 arith on guess] | 2-5x [guess]; the gz input fits orin's 8.5 GB free [repo] | 2-5x [guess] | 4-9x on the full input [a3 arith on external] | input bytes / 3-4: emmc input read ~50 s → 12-17 s [arith on guessed ratio] | yes: per-file magic bytes, installed inflaters, cores, free ram for read-ahead |
| **M11** out-of-core lookup | 3-4 GB free: 10-100x on 8GB+ full input vs `-M` thrash [guess, a1/a2]; enough ram: off, 1.0x | 103GB from external ssd: "cannot run" → minutes [guess]; 8GB/16GB off | nvme 40-236x, sata/emmc 5-26x vs thrash [arith on a1's thrash range and R1 device speeds] | off, 1.0x | it is the cold design; device sequential bandwidth sets it | yes: table bytes vs MemAvailable / `memory.max`, input size, free disk for spill, storage class |
| **M8a** next-line prefetch | 2-8% [a1 guess] | 2-10% [a1 guess] | 2-8% where it fits [guess] | 50MB 1.0x (fits l3); big dbs 0-8% [a1 guess], maybe a small loss from fill-buffer contention [guess] | 1.0x | yes: table bytes > llc size (sysfs cache index) |
| **M18** thread controller | [UNCLEAR] (smt on zen 3), 0-10% [guess] | 1.0x: no smt, near-linear to 12 [repo] | 0-10% [guess] | 0-13% when oversubscribed [measured s0/s10 spread] | 1.0x | runtime hill climb; candidates from physical cores, smt siblings, sockets |

how to read the grid:
- the byte-identical levers with the biggest numbers off luna are **M9** (cold, small ram) and **M20** (default users). neither touches classify cpu.
- the cpu levers (M2, M3, M4, M8a) are single-digit to ~25% everywhere. none is measured off luna.
- **H3's only large lever is M11**, and only after M12 shows `-M` thrashes.
- H2's numbers all hang on two facts nobody has measured: the emmc speed and the thp mode. item 2 of the measure-first list gets both in under 5 minutes of the campus hour.

---

## notes kept for later rounds

- weakest grid cells: everything in the H1 column. no kraken2 can run on the laptop today (section 3). the r7i.2xlarge 1.65x is the only public anchor.
- if the orin thp check says "madvise", revert S14 on H2 to the R1 prediction (works like luna) and raise E2's few-read predictions back toward next_steps' 3-10x.
- open hardware facts i could not fetch: a78ae miss-buffer count and branch penalty, zen 3 miss buffers, graviton4's distro thp default, intel's adjacent-line prefetcher behaviour, dorado's default output format.
