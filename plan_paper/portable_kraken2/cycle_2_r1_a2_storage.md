# cycle 2, round R1, a2_storage (2026-10-26)

agent: a2_storage. i read `cycle_1_conclusion.md`, `FINAL.md`, and every cycle-1 R2 and R3 file. nothing was run. new ids are M30-M33.

---

## (a) sources read this cycle (all new: none of these urls appear in any `cycle_1_*` file)

1. posix_fadvise(2), https://man7.org/linux/man-pages/man2/posix_fadvise.2.html
   - `POSIX_FADV_WILLNEED` "initiates a nonblocking read of the specified region into the page cache"; "The amount of data read may be decreased by the kernel depending on virtual memory load". (M30)
   - `POSIX_FADV_DONTNEED` "attempts to free cached pages associated with the specified region"; partial pages are ignored; dirty pages are not freed. (M31)
   - `POSIX_FADV_NOREUSE` was a no-op "from Linux 2.6.18 until Linux 6.2". since 6.3 it lets page replacement ignore accesses to mapped page cache marked with it, for "streaming large files". `POSIX_FADV_SEQUENTIAL` "doubles" the readahead window. (M31)
2. linux kernel docs, multi-gen LRU design, https://docs.kernel.org/mm/multigen_lru.html
   - for pages accessed through page tables vs through file descriptors: "The protection of the former channel is by design stronger". "The first tier contains single-use unmapped clean pages, which are the best bet" for eviction. with `lru_gen_min_ttl`, "The OOM killer is triggered if this working set cannot be kept in memory". (M31)
3. nvidia jetson agx orin developer kit, hardware layout, https://docs.nvidia.com/jetson/agx-orin-devkit/user-guide/latest/hardware_layout.html
   - default storage is "eMMC flash memory on the Jetson AGX Orin module". optional: "NVMe SSD card (on M.2 M-Key slot J1)", "microSD card (in microSD card slot J10)" (UHS-1), "USB thumb-drive (on any USB port)"; ports include "2x USB 3.2 Gen 2". (M33)
4. lkml rfc, "mm: defer address-space teardown of large exiting processes to a kthread" (july 2026), https://lkml.iu.edu/2607.2/06062.html
   - "Address-space teardown on process exit runs synchronously in the dying task's context".
   - kill to reaped: 4 GB 73.71 ms, **16 GB 282.16 ms** at 4 KB pages, **16 GB with THP 27.68 ms**. opt-in, default off, not merged. (M32, M10, E1)
5. linux kernel docs, zram, https://docs.kernel.org/admin-guide/blockdev/zram.html
   - pages "are compressed and stored in memory itself"; for same-element pages "No memory is allocated". (considered list)

---

## (b) counters to `cycle_1_conclusion.md`

### moves i want

1. **M13 out of the top 10, M30 in at rank 4.**
   - M13's main use case was a cold emmc load on orin. the agx orin dev kit has an M.2 M-key slot for an NVMe SSD, plus usb 3.2 gen 2 ports [external: src 3].
   - an orin nano NVMe read 1.55 GB/s against 0.25 GB/s for the emmc 5.1 class [external, via a4 cycle-1 src 5 and 3]. that is ~6x on a cold copy [arith] with no code (M33). M13 gives 1.37-2x [arith] and fights the map path.
   - M30 (below) closes the weakest point the vote found in M9: few-read cold faults run at queue depth 1.
2. **M10 stays at 9, with one more benefit on its row.**
   - THP cuts teardown ~10x: 16 GB 282 ms at 4 KB vs 27.68 ms with THP [external: src 4]; scaled to 111 GB, ~1.96 s vs ~0.19 s [arith, other machine]. so where huge pages fail to land, the exit tax returns along with the TLB misses, and part A fixes both. kernel 6.1+ still limits it, so no move.

### still wrong or missing in the conclusion

- **M9 row, H2 cell, "cold emmc few reads 5-30x"**: wrong in both directions.
  - uncapped db at queue depth 1 [UNCLEAR latency]: a5's 0.2-0.5 ms guess gives 2.1-5.4 s of faults vs a 26-30 s copy, so 5-14x [arith on guess]
  - capped 8GB (~1,050 lookups at 10 reads [arith, a3]): 0.2-0.5 s, so 50-150x [arith on guess]
  - the cell should say "depends on f and on qd-1 latency; 5x to 100x+ [arith on guesses]"
- **exit tax is missing from FINAL and the conclusion.** 00_context fact 6 says S19 "probably shrinks it, unmeasured". src 4 gives a number to predict with:
  - S19 with full THP: ~0.2 s on 103GB [arith, scaled from a 16 GB run on another machine]
  - luna's measured 3.9-11.4 s at 4 KB [measured] is 2-6x above the scaled 1.96 s [arith]. two sockets and 192 cpus are the likely reasons [guess]
  - E1's exit column tests this prediction
- **orin probe (measure rank 5)** checks `lsblk` but not whether J1 holds an NVMe. add `lsblk -d -o NAME,ROTA,TRAN,SIZE` and `lspci`. if an NVMe exists, every H2 cold cell changes class (M33).
- **section 1.5, "a prefetch cannot fault a page in"** is right, and it has a fix that works on every kernel. `posix_fadvise(WILLNEED)` "initiates a nonblocking read" [external: src 1]. that is M30.

---

## (c) ideas

### M30. cold fault-ahead: an i/o prefetch for the mapped table

1. **byte-identical.** it only warms the page cache earlier; lookups are unchanged. builds on M9 and E1.
2. **mechanism.**
   - *wrong intuition*: "S16 already prefetches every lookup, so a cold mapped run overlaps its disk reads too." no. a cpu prefetch "does not affect program behavior" [external, via a5], so it never starts a disk read. ten reads sit in one input block, on one thread. every non-resident page then becomes a blocking major fault, one at a time: queue depth 1 [repo: conclusion 1.5].
   - *real mechanism*: before the resolve pass on a cold mapped table, take the block's real lookups (changed, not ambiguous, at or above the cap) and collect their distinct 4 KB pages. call `posix_fadvise(fd, page_offset, 4096, POSIX_FADV_WILLNEED)` on each. every call returns at once and queues a read [external: src 1]. the device then sees hundreds of requests in flight instead of one, so it can reorder them. by the time the resolve pass faults, most pages are in the cache or already on their way. this works on every linux kernel, orin's 5.10 included.
   - *worked example*: nvme, uncapped db, 10 reads, ~10.7K lookups [arith]:
     - today, queue depth 1: 10.7K x 0.106 ms = 1.13 s [arith on external, a4 src 6]
     - with fault-ahead at queue depth 16 (~151K iops [arith, a4]): ~0.07 s, plus ~10-20 ms of syscalls [guess: ~1-2 µs each]
     - so ~16x on the fault part [arith]. against the 3.8 s copy, the map branch goes from ~3.4x to ~40x [arith]
     - on a hard disk, handing the elevator 10.7K requests at once lets it sort them into a sweep instead of random seeks [guess]
3. **gain per class.**

| class | cold | warm |
|---|---|---|
| H1 laptop nvme | map part ~10-16x faster on few-read runs [arith on enterprise-nvme numbers; consumer drive UNCLEAR] | 0, gated off |
| H2 orin emmc | emmc 5.1 has command queueing [external, via a4 src 4]; qd1-vs-qd16 ratio [UNCLEAR], [guess] 2-5x | 0 |
| H3 8 GB box | as H1/H2 by device. the 8GB db's map branch is the one H3 runs | 0 |
| H4 luna | raid with `read_ahead_kb` 1024; few-read cold cells [UNCLEAR], likely large [guess] | 0 |

4. **days**: 1-1.5. it is a pre-pass over the block's lookups inside the resolve phase (RC1 phase 2 or S16), plus the cold gate (residency below ~50%, from `mincore`).
5. **risk**: WILLNEED may be trimmed under memory pressure [external: src 1], so on H3 the gain shrinks exactly when ram is tight. wasted syscalls on a warm table, hence the gate. a null if the device gives no queue-depth scaling (some emmc) [UNCLEAR].
6. **cheapest kill test**: no kraken2 code. on each device, run a random 4 KB direct read at queue depth 1 and at 16 (`fio`, or 16 parallel `dd iflag=direct skip=$RANDOM` loops). if the qd16 iops are under 2x the qd1 iops, kill M30 for that device class.
7. **sources**: src 1; a4 cycle-1 src 4 and 6 (via a4); a5's PREFETCHh source (via a5).

### M31. input page-cache hygiene: drop the fastq pages after parsing

1. **byte-identical.** only page-cache state changes.
2. **mechanism.**
   - *wrong intuition*: "the 12.5 GB input is read once, so it costs no ram." where db + input exceed ram, the input competes with the mapped db for the page cache, and the next run may find its db evicted.
   - *what limits it already*: under MGLRU, mapped pages get "stronger" protection, and single-use unmapped clean pages are "the best bet" for eviction [external: src 2]. classic LRU is [UNCLEAR]. orin's 5.10 likely predates MGLRU [guess], so it is the classic case.
   - *the fix*: after the reader consumes a range of an input file, `posix_fadvise(DONTNEED)` its page-aligned part, and set `SEQUENTIAL` at open (double readahead) [external: src 1]. only when table + input > `MemAvailable`, never on pipes.
   - *worked example*: 8 GB box, 8GB db (7.6 GB) mapped, full input (12.5 GB) [repo]: 20.1 GB of demand on ~5-6 GB of cache [arith; usable guessed]. without the fix the rerun refaults db pages the input pushed out. with it, the input holds only a few blocks. on orin, dorado on the gpu shares the same 64 GB [repo], so a basecall-then-classify pipeline adds pressure [guess].
3. **gain per class**: H3 and low-free-ram H1: reruns stay warm, size [UNCLEAR], up to a whole cold load (~30 s on emmc). H2: only with dorado running [guess]. H4: 0. first cold run: 0.
4. **days**: 0.5.
5. **risk**: our benchmark protocol keeps the input warm on purpose [repo: next_steps section 5]. DONTNEED would make every repeat input-cold, so the gate must be strict and an env switch must turn it off. a null on MGLRU kernels.
6. **cheapest kill test**: no code, inside M12. under an 8G cap, run S19 `-M` on the 8GB db with the full input, then `fincore hash.k2d`, then rerun at once and log `majflt`. if the db stays mostly resident and the rerun's `majflt` is small, kill M31.
7. **sources**: src 1, src 2.

### M32. detached teardown: hide the exit tax from the wall clock

1. **byte-identical.** the output is complete before the parent returns.
2. **mechanism.**
   - *wrong intuition*: "exit is free." teardown "runs synchronously in the dying task's context" [external: src 4], and the wrapper waits for it: 3.9-11.4 s on luna's 103GB at 4 KB pages [measured], against S19's 3.79 s total at 10 reads [measured].
   - *real mechanism*: classify forks a worker before loading. the worker loads, classifies, flushes and closes all output, then writes its exit status into a pipe. the parent exits with that status at once, and the wrapper returns. the worker's teardown runs afterwards, reparented. this is src 4's kernel idea, in user space.
   - *worked example*: scaled from src 4, 111 GB costs ~1.96 s at 4 KB and ~0.19 s with THP [arith]. s10's measured 4.5 s [measured] leaves the wall clock.
3. **gain per class**: H4 103GB when THP fails or under `-M`: 1-11 s off small-read runs [measured range]; with THP ~0.2 s [arith]. H1-H3 tables ≤ 16 GB: ≤ 0.3 s at 4 KB [external: src 4], ~0. cold or warm: the same.
4. **days**: 0.5-1.
5. **risk**: it hides the cost, it does not remove it. a back-to-back run may not find the ram free yet, so gate on table ≥ ~16 GB and ram ≥ 2.5x table [guess]. exit-code plumbing. likely a null if E1 shows S19's exit ≤ 0.3 s.
6. **cheapest kill test**: E1's exit column for S19 and S19 `-M` on 103GB (already planned). kill if both are ≤ 0.3 s.
7. **sources**: src 4.

### M33. jetson-class storage placement: put the db on the fastest attached device

1. **byte-identical.** it is a deployment fact plus one line of planner advice.
2. **mechanism.**
   - *wrong intuition*: "H2 means emmc, so cold loads on a jetson are 0.25-0.4 GB/s, and only compression helps." the agx orin dev kit also takes an NVMe SSD in M.2 slot J1, a UHS-1 microSD card, and usb drives on 3.2 gen 2 ports [external: src 3].
   - the H2 storage class is really four rows:
     - emmc: 0.25-0.4 GB/s [external, conclusion 1.5]
     - microSD: an orin nano's SD card read 70 MB/s [external, via a4 cycle-1 src 5], the slowest
     - usb ssd: [UNCLEAR]
     - nvme: 1.55 GB/s on an orin nano [external, via a4 cycle-1 src 5]
   - M9's probe already reads the device class. on a slow device with a faster block device attached, it prints "db on mmcblk0, nvme0n1 present: move the db"
   - *worked example*: cold 8GB copy, emmc 7.6 / 0.25 = 30 s vs nvme 7.6 / 1.55 = 4.9 s, so ~6x [arith on class numbers]. an NVMe also fits the 12.5 GB full input (E2's missing column) and the 111 GB 103GB db (with M11, since 64 GB of ram is not enough) [repo + arith].
3. **gain per class**: H2 cold ~6x on the load [arith on class numbers]; H1/H3 only if they boot from sd or emmc; H4 0.
4. **days**: 0.25 for the planner line; the rest is buying an SSD.
5. **risk**: our board may not be a dev kit, or J1 may be empty [UNCLEAR]. the orin nano numbers are a different module.
6. **cheapest kill test**: on orin, `lsblk -d -o NAME,ROTA,TRAN,SIZE` and `lspci`. no NVMe and no usable slot: then only usb remains, and it needs one `dd iflag=direct` on a usb ssd.
7. **sources**: src 3; a4 cycle-1 src 5 (via a4).

### considered, not proposed

- **zram swap on H3 for the copy path**: an overflowing copy would swap at decompression cost, not disk cost [external: src 5]. but the same-element shortcut never fires: P(all 1,024 cells of a page empty) = 0.3^1024 ≈ 0 [arith]. the ratio is [UNCLEAR], and it needs root.
- **`POSIX_FADV_NOREUSE`**: it acts on mapped page cache [external: src 1]. kraken2 reads input with `read()`, so DONTNEED applies.
- **output write path**: output bytes per full run are [UNCLEAR]. one `wc -c` tells. emmc writes ~82-125 MB/s [external, cycle 1]. a free gate for now.

---

## (d) my rankings (conclusion ids, plus M30-M33)

### top 10 build

| rank | id | reason |
|---|---|---|
| 1 | M2 | reaches every class through the binary people install; M3 and M6 come free |
| 2 | M20 | under a day; the only build with measured gains on two machines |
| 3 | M9 | byte-identical; cold and small-ram runs on every class. now fed with d x f, and with M33's advice line |
| 4 | **M30** | makes M9's cold map branch real: queue depth 1 → many, on every kernel. 1-1.5 days, gated by a 10-min `fio` test |
| 5 | M4 | the scanner dominates capped dbs on every isa |
| 6 | M5 | the biggest lever for gz users; half a day for step a |
| 7 | M11 | the only route for uncapped dbs bigger than ram; gated by M12 |
| 8 | M8a | cheap; ram-bound classes |
| 9 | M10 | new kernels: huge pages that land also cut the exit ~10x [external: src 4] |
| 10 | M21 | portable builds; orin cannot build with `-march=native` |

just outside: M31 (gated by its fincore test inside M12), M32 (gated by E1's exit column), M13 (placement M33 beats it on jetsons, and it fights the map path), M14, M18. M33 is a 0.25-day line inside M9, so it does not take a rank.

### top 5 measure-first

| rank | what | reason |
|---|---|---|
| 1 | M22 lookup census | f and d resize M9, M11, M12, M30 |
| 2 | M1, with the exit column | also tests the THP-teardown prediction: S19 ~0.2 s on 103GB if huge pages land [arith on src 4] |
| 3 | E1 plus the cold pair, and a qd1-vs-qd16 random-read test on luna's raid | decides M9's map branch and M30 on H4 |
| 4 | M12, plus M31's fincore-and-rerun check | gates M11 and M31 in one session |
| 5 | orin probe, plus `lsblk` / `lspci` for an NVMe in J1 and the qd1-vs-qd16 read test on each device found | settles H2's storage class (M33), M30 on emmc, conflicts 2 and 3 |
