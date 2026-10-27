# cycle 3 conclusion: the list holds (2026-10-27)

this file closes cycle 3. it exists to record that the cycle-2 list survived a full cycle of new reading and counters, and what the cycle added around it. the transcript is `cycle_3_r1_*.md`, `cycle_3_r2_relay_brief.md`, `cycle_3_r2_*.md` and `cycle_3_r3_vote_*.md`.

**stop-rule status: in R1 and again in R2, all five agents said "list unchanged: agree" for both lists. if the R3 vote below confirms it, cycle 3 is the first unchanged cycle. one more unchanged cycle (cycle 4) ends the debate.**

---

## 1. the ranked lists (identical to cycle 2)

build: 1 M2 (+M3, M27a, M40, block list), 2 M20' (+M17, M62), 3 M9 (+M24, M51, M33), 4 M4, 5 M30, 6 M41, 7 M5, 8 M26 (+M8a), 9 M11 (+M64), 10 M21 (+M42). the per-class cells are in `cycle_2_conclusion.md` section 2, with the fixes in section 4 below.

measure-first: 1 M22, 2 M1, 3 E1, 4 cpu gate, 5 M61.

---

## 2. what cycle 3 added: riders and unranked measures only

each agent read at least 3 new sources on ground cycles 1-2 had not covered: hpc and network filesystems, wsl2, apple silicon, 16 KB page kernels, the orin gpu, cache-sized partitioning, gpu hash tables, upstream activity after RC1.

| id | what | rides in |
|---|---|---|
| M75 | network / parallel filesystem rule: on nfs, lustre, gpfs or wsl's `/mnt/*`, copy-load sequentially or advise staging to node-local `/tmp`; never map from lustre at scale (few-read runs [UNCLEAR] until M78). an hpc centre requires local scratch for kraken dbs [external: https://docs.urcf.drexel.edu/software/compiling/Compiling_kraken/]; lustre "slows down considerably" on random i/o [external: https://hpc-docs.uni.lu/filesystems/lustre/] | M9 / M33 |
| M76 | read page size, `hpage_pmd_size` and cache-line size at runtime instead of hard-coding 4 KB / 2 MB / 64 B. asahi linux on apple hardware uses 16 KB pages [external: asahi release notes]; 64 KB arm kernels make the pmd huge page 512 MB [external: kernel arm64 hugetlb doc]; a 128 B line would halve M8a/M26's crossing rates (apple silicon's line size [UNCLEAR]) | M2, M9, M30, M31 |
| M77 | input readahead outside the input lock, not io_uring (docker's default seccomp profile blocks io_uring [external, a2]) | M9 |
| M82 | arm tier at `-march=armv8.2-a` with a current compiler | M21 |
| M86 | probe backends for wsl2 (refuse `-M` for a db under `/mnt/*`, treat vm memory < 2x db as H3, assume cold after idle) and macOS (`sysctl`; its read-advice call [UNCLEAR]) | M24 / M9 |
| M90 | channel-aware baseline: bioconda and homebrew ship 2.17.2, including linux-aarch64 and osx-arm64 [external: bioconda, formulae.brew.sh]; debian sid ships 2.1.3 [external: packages.debian.org], which orin runs. add a v2.1.3 column and the upstream commit hash to M1 and E2 | M1 / E2 |
| M91 | `ResolveTree`'s share in the cpu gate, on 103GB and short reads. upstream's open PR #1063 claims 4.9x at 16 hit taxa and 53x at 256 in microbenchmarks only [external]. the repo's one gprof count puts it at 0.29% of user time, from the old WSL2 run on a capped db [repo, a1, a5] | cpu gate; cherry-pick into M2 if merged |
| M70, M72 | slot-sorted block lookups (radix-partitioned to the llc, after Balkesen et al., ICDE 2013), then an in-ram sweep only if M70 passes | unranked measure / below the line |
| M71 | jetson gpu lookups on the shared table; no gpu source gives throughput, so every gpu speed is [UNCLEAR] | below the line |
| M78, M85, M88, M89 | cluster run; orin with dorado on the gpu; wsl2 cold-after-idle check; one apple silicon run | unranked measures |

**class changes (a4; no rank moves):**
- **H1 splits** into H1-linux, H1-wsl2 and H1-mac. the wsl2 vm gets "50% of total memory on Windows" by default, shuts down after 60 s idle (that setting is windows 11 only, a4), and reclaims cache immediately (`autoMemoryReclaim` = `dropCache`) [external: https://learn.microsoft.com/en-us/windows/wsl/wsl-config]. so on ck's 16 GB laptop a wsl2 run is a ~7-8 GB H3 box that is usually cold [arith, guess]. H1-mac: 16 KB pages under asahi [external]; macOS's own page size and probe calls are [UNCLEAR]
- **H4 splits** into H4-dedicated (luna) and H4-hpc slot: a slurm job gets its cores as a cpuset and a hard memory limit with oom [external: slurm cgroup.conf], page cache is charged to the job on clusters that run cgroup v2 [guess on which clusters do; the charging rule is external: cgroup v2 doc], and the db usually sits on a parallel filesystem. for M9 it behaves like H3 or H5
- **every H2 cell** carries the condition "dorado idle" until M85 runs: the cpu and gpu share one lpddr5 pool, and on an older tegra memory-heavy cpu work slowed gpu kernels up to 4x [external: BWLOCK++, arxiv 1712.08738]. that is the other direction: whether gpu basecalling slows kraken2's cpu lookups is unmeasured [UNCLEAR] (a5)

---

## 3. wording fixes (proposed by a5, confirmed by all five)

1. rank 1 reaches "the binary conda and brew users install", not everyone; apt users are on 2.1.3 [external]
2. upstream shipped "its own" prefetch, parallel load, memchr parser and huge pages (PR #1033, merged 2026-06-24, before S8 was built [external, repo]). batched index prefetch is already established in aligners (an architecture-aware BWA-MEM rewrite, minibwa) [external: arxiv 1907.12931, 2606.15357], so no text should present it as new for bioinformatics
3. "~16x on nvme" → "on an enterprise nvme"; laptop nvme scaling is [UNCLEAR] until the qd1-vs-qd16 timing
4. the orin ~11.6x classify figure keeps its [UNCLEAR]: it takes stock's 4.23 s of sys time as the load time
5. Coriolis's 1.5x: drop "only"; it spans a 16x pressure range with no in-ram baseline

---

## 4. overclaims caught in cycle 3 (a5, R2)

- a1's M71 "0.6 s" for gpu lookups re-derives as ~2.4 s, and orin cannot hold the full input anyway
- a1's M70 traffic share is under 1%, not ~5%
- a2's nfs "≤ 256 MB/s" bound assumes synchronous read-ahead
- a3's "most users run bioconda" claims a usage share the sources cannot show

none of these touch a ranked id.

---

## 5. the R3 vote

| agent | both lists unchanged from cycle 2 | fixes (applied) |
|---|---|---|
| a1_dsa | AGREE | accepts a5's corrections to M71 (~2.4 s) and M70 (0.76%) |
| a2_storage | AGREE | none |
| a3_cpu | AGREE | accepts the bioconda usage-share overclaim |
| a4_hw | AGREE | the 60 s wsl2 idle shutdown is windows 11 only; page cache charged to the hpc job is a guess for cgroup v2 clusters |
| a5_skeptic | AGREE | BWLOCK++ measured cpu slowing the gpu, not the reverse; M91's 0.29% is user time from the old WSL2 run |

**result: 5 of 5 agree, and both lists are identical to cycle 2's. cycle 3 is the first unchanged cycle.** cycle 4 decides: if it also leaves both lists unchanged with all five agreeing, the debate stops and the verification rounds start.
