# cycle 3, round 1, a4_hw (hardware spread)

this round looks at four machine variants the list has not covered: windows users on wsl2, apple silicon laptops, an hpc job slot, and orin running dorado and kraken2 at the same time. **result: list unchanged: agree.** everything new below is either a rider inside an existing id or an unranked measure.

---

## (a) sources fetched this cycle (all new; each url grepped in the folder first)

| # | source | exact claim used | for |
|---|---|---|---|
| N1 | microsoft learn, advanced settings configuration in wsl, https://learn.microsoft.com/en-us/windows/wsl/wsl-config | `memory`: default "50% of total memory on Windows". `processors`: "The same number of logical processors on Windows". `swap`: "25% of memory size on Windows". `vmIdleTimeout`: 60000 ms, "idle, before it is shut down". `instanceIdleTimeout`: 15000 ms. `autoMemoryReclaim` default `dropCache`: "cached memory will be reclaimed immediately". windows drives are mounted through "DrvFs" under `/mnt` | H1-wsl2 |
| N2 | slurm `cgroup.conf` manual, https://slurm.schedmd.com/cgroup.conf.html | `ConstrainCores`: "constrain allowed cores to the subset of allocated resources", using "the cpuset subsystem". `ConstrainRAMSpace`: soft limit "to the allocated memory", hard limit "the allocated memory * AllowedRAMSpace". over the hard limit "it might trigger Out Of Memory (OOM) events". no statement on page cache or cpu quotas | H4-hpc |
| N3 | university of luxembourg hpc docs, lustre, https://hpc-docs.uni.lu/filesystems/lustre/ | "best used to write large files in a continuous manner". random i/o "still slows down considerably as the number of I/O operations increases". "Prefer the locally mounted file system in `/tmp` for small file and random I/O". ~12 GB/s "for large sequential read and writes" for the whole filesystem (8 osts) | H4-hpc, M9 |
| N4 | asahi linux alpha release notes, https://asahilinux.org/2022/03/asahi-linux-alpha-release/ | "The Asahi Linux kernel is compiled to use 16K pages", needed for the m1's iommus; "up to 20% or so under some workloads"; "some Linux software has problems running with 16K pages", including "Anything using jemalloc" | H1-mac |
| N5 | Ali and Yun, BWLOCK++, https://arxiv.org/abs/1712.08738 | "sharing of main memory between CPU applications and GPU kernels can severely affect the execution of GPU kernels"; on tegra k1, "as much as 4X slowdown in the presence of co-running memory intensive CPU applications" | H2 co-run |

failed: apple's "addressing architectural differences in your macos code" page returned only its title (javascript-rendered). so **macOS's own page size is [UNCLEAR]**. N4 is asahi linux running on the same hardware. no peer-reviewed orin or xavier cpu/gpu contention measurement was found. N5 is the older tegra k1, and it measures the other direction (cpu traffic slowing the gpu).

---

## (b) counters to cycle_2_conclusion.md

**list unchanged: agree.** no rank moves. the build order and the measure order stand. the cells below are not wrong for the classes they name. they are missing four common variants.

### variant 1: a windows laptop running kraken2 in wsl2 behaves like H3, and runs cold

- **wrong intuition**: "a 16 GB windows laptop running wsl2 is H1".
- **real**: the wsl2 vm gets "50% of total memory on Windows" by default [external: N1]. on ck's 16 GB laptop (13.9 GB usable [repo]) that is ~7-8 GB [arith]. so the 7.6 GB 8GB db cannot be copied, only mapped. that is H3's fit case, not H1's.
- **the cache does not stay warm**:
  - the vm shuts down after 60 s idle (`vmIdleTimeout`) and the distro after 15 s (`instanceIdleTimeout`) [external: N1]
  - `autoMemoryReclaim` defaults to `dropCache`, "cached memory will be reclaimed immediately" [external: N1]
  - [guess on how these interact]: any run that starts a minute or more after the last one finds the db cold. on wsl2, M9's cold branch and M30 are the normal case, not an edge case.
- dbs under `/mnt/c` sit behind DrvFs [external: N1]. a2's cycle-1 source already said to keep files in the linux filesystem "for the fastest performance" [external: a2 cycle-1 src 16].
- **cell fixes, M9 row**: add an H1-wsl2 note: "map only at ≤ 8 GB vm memory; usually cold; db must live on the vm's ext4, not `/mnt/c`" [arith on N1, guess on cold].
- **M20' row**: the vm sees all logical processors by default [external: N1]. so M20' counts smt siblings inside the vm. sysfs inside wsl2 may not show the host's real topology [UNCLEAR]. that cell is [UNCLEAR].

### variant 2: apple silicon laptops need their own probe path

- 16K base pages on that hardware: Asahi Linux uses them, with "up to 20%" gains in some workloads [external: N4]. macOS itself is [UNCLEAR] (fetch failed).
- with 16 KB pages a tlb entry covers 4x the memory of a 4 KB entry [arith]. so part of S14's gain is native there, and S19's `MADV_HUGEPAGE` guard just compiles it out [repo: S19].
- what changes for the list:
  - M24 / M51's sysfs probes do not exist on macOS [guess]
  - M30's `posix_fadvise` may not exist there [UNCLEAR: not fetched]
  - M20' has to count performance and efficiency cores separately [UNCLEAR: not fetched]
- **cell fix**: an H1-mac row for M9, M30 and M20' reads [UNCLEAR] until one run on a mac. RC1 has been run on macos/arm64 by one outside tester [external: a5 c2 N5]. Metabuli ran on an 8 GiB m1 laptop [external: cycle-1 a5 S8].

### variant 3: an hpc job slot is H3 inside H4

- **wrong intuition**: "an hpc node is luna: lots of cores and ram".
- **real**: a slurm job gets a cpuset ("the subset of allocated resources" [external: N2]). so the affinity mask already shows the job's cores, and M20' works there with no quota logic. ram has a hard limit, and going over it "might trigger Out Of Memory (OOM) events" [external: N2].
- cgroup v2 charges page cache to the group that read it [external: cycle-1 a5 S16]. so under `-M`, a job's db pages count against its `--mem` too [arith on two sources; that slurm runs cgroup v2 on a given cluster is a guess].
- the db usually sits on a parallel filesystem. that is fine for big sequential reads (~12 GB/s for the whole filesystem [external: N3]) and poor for random i/o [external: N3], whose advice is node-local `/tmp`.
- **consequence for M9**: on a parallel filesystem, prefer the sequential copy (or stage to node-local storage) over `-M` for anything but tiny inputs. a qd1 random fault on lustre is [UNCLEAR], but N3 says it degrades with operation count.
- M51's probe measures this case directly, so no new id. it is one more advice line in M33: "db on a parallel fs: stage it to `/tmp` or copy-load it".
- **cell fix, M9 H4**: add "hpc slot: copy-load or stage, never map from lustre at scale" [external: N3; guess on the size].

### variant 4: orin with dorado running on the gpu at the same time

- **wrong intuition**: "kraken2 uses ~5 GB/s of orin's 55-72 GB/s cpu bandwidth, so the gpu doesn't matter".
- **real**: the cpu and gpu share one lpddr5 pool through one arbiter [external: cycle-1 forum source]. on tegra k1, memory-heavy cpu work slowed gpu kernels "as much as 4X" [external: N5]. the reverse direction (gpu basecalling slowing cpu lookups) is unmeasured on any jetson [UNCLEAR].
- kraken2's lookups are latency-bound [repo], and loaded latency rises as the memory system fills (mess: saturation = latency doubles [external: cycle-1 R1 src 7]). so co-running dorado could slow classify even at a small bandwidth share [guess].
- **cell fix, every H2 cell**: add "dorado idle". the E2 plan already says to check `tegrastats` for an idle gpu [repo: next_steps E2 confounders].

---

## (c) ideas (compact)

### M85 (measure). orin co-run test

- run S19 (or RC1) on 16GB at 104,918 reads, 12 threads:
  - alone
  - with dorado basecalling on the gpu
  - log `tegrastats` EMC util both times
- **cost**: ~20 min of the campus hour. **byte-identical**: same binary.
- **decides**: whether a basecall-then-classify pipeline on a jetson should run the two steps one after the other, and whether M20' should leave cores to dorado.
- **gain**: none by itself. if co-running costs ≥ 1.5x on classify [guess threshold], "run them in series" is free advice for every H2 pipeline.

### M86 (rider inside M24 / M9). platform backends for the startup probe

- linux: sysfs, as planned.
- wsl2: detect it [guess: a "microsoft" string in `/proc/version`]. then:
  - warn when the db is under `/mnt/*` (DrvFs [external: N1])
  - treat vm memory < 2x db as H3
  - assume cold after idle (N1 timeouts)
- macOS: `sysctl` instead of sysfs, and the platform's read-advice call instead of `posix_fadvise` [UNCLEAR on both names, not fetched]. fall back to "copy, no probe" if unsure.
- **byte-identical**. **days**: +1 on top of M9. **risk**: untestable without a wsl2 install and a mac. both are [UNCLEAR] access.

### M87 (rider inside M33). parallel-filesystem rule

- if `statfs` says the db sits on a network or parallel filesystem [guess: the call reports a filesystem type], then:
  - many reads: copy-load sequentially
  - long runs, or many jobs with node-local room: print "stage to `/tmp`"
  - never map from lustre for more than tiny inputs
- **source**: N3.
- **gain**: avoids a random-i/o storm on shared storage. that is kinder to other users too. size [UNCLEAR].
- **days**: 0.25.

### M88 (measure). wsl2 cold-after-idle check

- on any windows box with wsl2:
  - run S19 on 8GB twice, 10 s apart
  - run it again 90 s later
  - `fincore` before each run
- **decides**: whether wsl2's idle and reclaim settings [external: N1] really empty the db cache. if yes, every wsl2 user is in M9's cold branch.
- **cost**: 10 min. ck's laptop has no wsl today [repo: user memory].

### M89 (measure). one apple silicon run

- RC1 (it builds on macos/arm64 [external: a5 c2 N5]) on 50MB and 8GB:
  - read the page size with `getconf PAGESIZE`
  - count cores by type
  - time one cold and one warm run
- **decides**: the H1-mac cells for M9, M30, M20'. **cost**: 30 min, if anyone has a mac [UNCLEAR].

---

## (d) rankings (cycle-2 ids; riders shown)

### top 10 build: unchanged

1. **M2** (+M3, M27a, M40, block list)
2. **M20'** (+M17, M62)
3. **M9** (+M24, M51, M33, and now M86 platform backends, M87 parallel-fs line)
4. **M4**
5. **M30**
6. **M41**
7. **M5**
8. **M26** (+M8a)
9. **M11** (+M64)
10. **M21** (+M42)

### top 5 measure: unchanged

1. **M22**
2. **M1**
3. **E1** (+cold pair, qd1-vs-qd16, exit column, M60)
4. **cpu gate**
5. **M61**

next, not ranked:
- campus visit: the orin probe plus **M85** (co-run), on the same visit
- **M88** and **M89**, if a wsl2 box or a mac is around
- M43, M53, M54, M63 as before

---

## (e) classes: split two, add none

| class | split into | why, with numbers |
|---|---|---|
| H1 laptop | **H1-linux** (as now), **H1-wsl2**, **H1-mac** | wsl2: the vm gets 50% of windows ram by default and drops its cache when idle [external: N1], so a 16 GB laptop runs as a ~7-8 GB H3 box that is usually cold [arith, guess]. mac: 16K pages on that hardware [external: N4], no sysfs, no thp, probe calls [UNCLEAR]. the cpu cells (M2, M4, M41, M26) stay the same, so the split only changes M9, M30 and M20' |
| H4 big server | **H4-dedicated** (luna-style), **H4-hpc slot** | slurm: cores via cpuset, ram via a hard cgroup limit with oom [external: N2], page cache charged to the job [external: cycle-1 a5 S16], db on a parallel fs that is fast sequentially (~12 GB/s shared) and poor at random i/o [external: N3]. for M9 it behaves like H3 or H5, not luna |
| H2 orin | no split; add a "co-running dorado" condition to every H2 cell until M85 runs | shared lpddr5, and interference shown on an older tegra [external: N5] |
| pi 5, small cloud | unchanged (H3 example, H5) | covered in cycle 2 |

the splits change no rank. they change which branch M9 picks and which probe M24 runs. so they belong in M9's cells and in FINAL's class list, not in the ranking.
