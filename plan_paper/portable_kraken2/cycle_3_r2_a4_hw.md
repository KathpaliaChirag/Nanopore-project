# cycle 3, round 2, a4_hw

no new fetches. "c3 N#" = my `cycle_3_r1_a4_hw.md` sources. i read the brief and the other four cycle-3 R1 files, the hardware-relevant parts in full.

---

## 1. one line per item

| id | verdict | hardware reason |
|---|---|---|
| M75 network / parallel fs rule | **rider in M9 / M33** | it merges my M87, a2's M75 and a5's M92. lustre is poor at random i/o [external: c3 N3], and an hpc centre says to use local scratch [external: a5 T6]. it helps H4-hpc and H1-wsl2 with the db on `/mnt/c`, and moves no rank |
| M76 runtime page size and `hpage_pmd_size` | **rider in M2, M9, M30, M31** | a correctness guard, no speedup. 16 KB pages on apple-silicon linux [external: c3 N4]. on 64 KB arm kernels the pmd huge page is 512M [external: cycle-1 R1 src 13], so S14-style fault-time huge pages need 512 MB of contiguous free memory and will often fail there [guess, a2]. one `getconf PAGESIZE` on orin settles our board |
| M77 input readahead outside the lock (no io_uring) | **rider in M9** | cold or network input only: H2 emmc, H5 gp3, H4-hpc. docker's default seccomp blocks io_uring [external: a2 src 4], so plain WILLNEED is the portable choice. its size is [UNCLEAR] until we know how much input i/o already overlaps classify |
| M82 arm tier at `armv8.2-a` | **revision of M21, no move** | one arm binary covers orin's a78ae and graviton 2 and later [external: a3 P3; cycle-1 a3 S7]. no sve on orin [external: cycle-1 a3 S7], so M7's sve path helps H5-arm (graviton3) only |
| M86 probe backends for wsl2 / macOS | **rider in M24 / M9** (mine) | changes which branch M9 picks on H1-wsl2 and H1-mac, not any rank. the macOS calls stay [UNCLEAR] until M89 |
| M90 channel-aware baseline, a v2.1.3 column | **rider in M1 / E2** | orin runs 2.1.3 [repo], and so do apt users [external: a5 T5]. on H2 the number a jetson user sees is 2.1.3 → S19 or v2.17.2, the whole chain. add a3's conda v2.17.2 linux-aarch64 binary as orin's no-build stock [external: a3 P1]. conda needs network on orin through the campus proxy [UNCLEAR] |
| M91 `ResolveTree` share | **rider in the cpu gate** | isa-neutral. upstream PR #1063's 4.9-53x are microbenchmarks [external: a5]. it matters only if the gate shows a real share on 103GB or short reads |
| M70 sort-by-slot benchmark | **unranked measure** | the right place to test it is the small-cache boxes (H1, H2, H5), where a 50MB panel db misses the llc [repo]. run its orin arm on the campus visit |
| M71 jetson gpu lookups | **below the line** | the gpu is busy exactly when a jetson pipeline runs dorado (M85). shared-memory interference is real in the other direction on older tegra [external: c3 N5]. how the igpu handles random 4-byte reads over a 15 GB buffer (its own address translation) is [UNCLEAR]. every gpu speed is [UNCLEAR] |
| M72 in-ram sweep | **below the line** | only if M70 passes |
| M78 cluster measurement | **unranked measure** | it is the H4-hpc slot's only route to a real number, like M53 for H5 |
| M85 orin co-run | **campus visit** (mine) | it also decides M71: if dorado and kraken2 run together, the gpu is not free for M71 |
| M88 wsl2 cold-after-idle | **unranked measure** (mine) | needs a wsl2 install, and ck's laptop has none [repo: user memory] |
| M89 apple silicon run | **unranked measure** (mine) | needs a mac [UNCLEAR] |

**class changes**: the H1 and H4 splits and H2's "dorado idle" condition stand. none moves a rank. they change M9's and M30's per-variant cells only.

---

## 2. wording fixes

1. **"the binary conda and brew users install": confirm.** our orin runs 2.1.3 [repo: `RESULTS.md` 1.4], and debian sid ships 2.1.3 [external: a5 T5]. so on H2, "the binary everyone installs" is wrong today.
2. **"its own" prefetch, load, parser and huge pages, not "our": confirm.** PR #1033 merged 2026-06-24, before S8 [external: cycle-1 a5 S3].
3. **"~16x on an enterprise nvme": confirm.** the 0.106 ms qd1-16 latency came from a kingston dcp1000 enterprise drive [external: cycle-1 R1 src 6]. consumer nvme is [UNCLEAR].
4. **[UNCLEAR] back on the orin ~11.6x: confirm.** i took stock's 4.23 s of sys time as the load time. that was my guess [repo: `RESULTS.md` 1.4; cycle-2 a4 R1].
5. **drop "only" from "lost only 1.5x": confirm.** coriolis gave no in-ram baseline [external: cycle-2 a5 N2]. so 1.5x describes the slope over DMR 3.25-52, not "mild".

---

## 3. verdict

**list unchanged: agree.** build top 10 and measure top 5 as in `cycle_2_conclusion.md`. every item above is a rider, a below-the-line id, or an unranked measure. no item gives a class a gain big enough to pass the id above it, and every gain is still unmeasured.
