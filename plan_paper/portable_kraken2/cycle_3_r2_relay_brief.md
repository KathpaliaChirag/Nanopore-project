# cycle 3, round 2: relay brief (2026-10-27)

this file exists so R2 counters one merged set. in cycle 3 R1 all five agents said **"list unchanged: agree"** for both the build top 10 and the measure top 5. everything new is a rider inside an existing id, an unranked measure, or a wording fix. R2's job is to check that none of it should move a rank.

---

## 1. new items, merged

| id | what | from | where it goes |
|---|---|---|---|
| M75 | network / parallel filesystem rule: if `statfs` says nfs, lustre, gpfs or wsl's 9p/DrvFs, copy-load sequentially or print "stage the db to node-local `/tmp`"; never map from lustre at scale; lustre stripe count and nfs readahead notes | a2 M75, a4 M87, a5 M92 | rider in M9 / M33 |
| M76 | no hard-coded 4 KB / 2 MB: read the page size and `hpage_pmd_size` at runtime (16 KB pages on asahi and some arm distros; 64 KB arm kernels make the pmd huge page 512 MB) | a2 M76, a3 M81 | rider in M2, M9, M30, M31 |
| M77 | input readahead outside the input lock instead of io_uring (docker's default seccomp blocks io_uring) | a2 | rider in M9 |
| M82 | arm tier at `-march=armv8.2-a` with a current compiler | a3 | revision of M21 |
| M86 | platform backends for the startup probe: wsl2 (warn on `/mnt/*`, vm memory < 2x db means H3, assume cold after idle) and macOS (`sysctl`, its own read-advice call [UNCLEAR]) | a4 | rider in M24 / M9 |
| M90 | channel-aware baseline: v2.17.2 is what bioconda and homebrew ship (linux-aarch64, osx-arm64 too); debian sid still ships 2.1.3, which orin runs. add a v2.1.3 column to M1 and E2; record the upstream commit hash | a5 M90, a3 M80 | rider in M1 / E2 |
| M91 | report `ResolveTree`'s share in the cpu gate, on 103GB and short reads; adopt open upstream PR #1063 (4.9x at 16 taxa, 53x at 256 taxa, microbenchmarks only) if it matters | a5 | rider in the cpu gate; cherry-pick into M2 if merged |
| M70 | 1-day benchmark: a block's lookups sorted by slot vs random order (radix-partitioned, llc-sized, after Balkesen et al. ICDE 2013) | a1 | unranked measure |
| M71 | jetson gpu lookups on the shared table, no copy | a1 | below the line; every gpu speed [UNCLEAR] |
| M72 | in-ram sweep built on M11's code, only if M70 passes | a1 | below the line |
| M78 | optional cluster measurement | a2 | unranked measure |
| M85 | orin co-run: classify alone vs with dorado on the gpu, `tegrastats` logged | a4 | campus visit |
| M88 | wsl2 cold-after-idle check (`vmIdleTimeout` 60 s, `autoMemoryReclaim` = `dropCache`) | a4 | unranked measure |
| M89 | one apple silicon run (page size, core types, cold and warm) | a4 | unranked measure |

**class changes (a4), no rank moves:** H1 splits into H1-linux, H1-wsl2 (the vm gets 50% of windows ram by default and drops its cache when idle [external: microsoft wsl-config]) and H1-mac (16 KB pages on that hardware under asahi [external], macOS page size [UNCLEAR]). H4 splits into H4-dedicated and H4-hpc slot (cpuset cores, hard memory limit with oom, page cache charged to the job, db on a parallel filesystem [external: slurm cgroup.conf, uni.lu lustre docs]). every H2 cell gets the condition "dorado idle" until M85 runs.

---

## 2. wording fixes proposed (a5)

1. FINAL rank 1: "the binary everyone installs" → "the binary conda and brew users install"; apt users are on 2.1.3 [external: bioconda, homebrew, debian sid pages].
2. FINAL item 1: upstream ships "its own" prefetch, load, parser and huge pages, not "our"; PR #1033 merged 2026-06-24, before S8 [external]. aligners already prefetch (BWA-MEM rewrite, minibwa) [external], so batched prefetch is not new for bioinformatics.
3. "~16x on nvme" → "on an enterprise nvme".
4. FINAL item 4: put back [UNCLEAR] on the orin ~11.6x (it uses sys time as the load time).
5. cycle 2 conclusion 1.2: drop "only" from "lost only 1.5x".

---

## 3. R2 task (each agent, at most ~800 words, file `cycle_3_r2_<slug>.md`)

1. one line per item in section 1: keep as a rider / below the line, or argue it moves a rank (and which).
2. confirm or reject each wording fix in section 2.
3. say plainly: **"list unchanged: agree"**, or give the exact moves.
