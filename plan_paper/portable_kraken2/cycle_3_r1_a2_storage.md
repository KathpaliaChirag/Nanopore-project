# cycle 3, round R1, a2_storage (2026-10-27)

i read `cycle_2_conclusion.md` (vote 5/5), `FINAL.md`, and the other four `cycle_2_r2_*` and `cycle_2_r3_vote_*` files. nothing was run. new ids: M75-M78.

---

## (a) sources (new: none of these urls appear in any `cycle_1_*` or `cycle_2_*` file)

1. lustre wiki, "lustre striping best practices", https://wiki.lustre.org/Lustre_Striping_Best_Practices
   - stripe_count is "How many OSTs to spread the file across", **default 1**
   - for "Large files (> 1 GiB), single client": stripe count **4 to 8**, because it "Aggregates bandwidth across multiple OSTs"
   - many clients on one large file: "8+" or "-1", so "no single OST becomes a bottleneck". syntax: `lfs setstripe -c <count> -S <size> <file_or_directory>`. (M75)
2. microsoft learn, "linux nfs read-ahead best practices", https://learn.microsoft.com/en-us/azure/azure-netapp-files/performance-linux-nfs-read-ahead
   - the old default was "15 times the mounted filesystems `rsize`". "RHEL 8.3 and Ubuntu 18.04 ... set read-ahead to a default of 128 KiB regardless of the `rsize`". upgrading "experienced decreases in sequential read performance"
   - a SAS GRID test "found the 15,360 KiB read value optimal". the knob is `/sys/class/bdi/<dev>/read_ahead_kb`, which needs root. (M75, M77)
3. android developers, "support 16 KB page sizes", https://developer.android.com/guide/practices/page-sizes
   - 16 KB devices "use slightly more memory on average" but gain, for example, "3.16% lower" app launch under memory pressure
   - "Remove any hard-coded dependencies that reference the `PAGE_SIZE` constant or ... assume that a device's page size is 4 KB (`4096`)"; use "`getpagesize()` or `sysconf(_SC_PAGESIZE)`". (M76)
4. docker docs, "seccomp security profiles", https://docs.docker.com/engine/security/seccomp/
   - the default profile "is an allowlist", and `io_uring_setup`, `io_uring_enter` and `io_uring_register` are "Blocked due to security vulnerabilities that can be exploited to break out of containers". (M77, a firm "do not")

reused for a new claim (url cited in cycle 1 by a4): arm64 hugetlbpage, https://docs.kernel.org/arch/arm64/hugetlbpage.html. with a **16K** base page the PMD huge page is **32M** and CONT PTE is 2M; with 64K the PMD is 512M. (M76)

fetched but not used: io_uring(7) at man7.org. it says nothing about buffered reads or kernel versions that i needed.

---

## (b) counters to `cycle_2_conclusion.md`

**list unchanged: agree.** build and measure lists stay as they are. my new ideas fold into existing ids as riders, the way M33 and M51 did. so they do not move a rank:
- M75 (network and parallel filesystems) and M77 (input read-ahead) go inside M9
- M76 (page-size rule) is a coding rule for M9, M30 and M31, plus one line in M2's upstream bundle
- M78 is an optional measure, next to M53

two things the conclusion does not say yet:
- **the storage axis lacks the hpc case.** `00_context.md` lists "network fs" on the storage axis, but no cell covers it. hpc kraken2 users often keep a 70-111 GB db on a shared parallel filesystem [guess on how common]. there, lustre's default stripe count of 1 [external: src 1] caps a single file at one storage server's bandwidth. M75 covers it.
- **page size is assumed to be 4 KB everywhere.** M30's page index `(32 + 4·idx) / 4096` [repo: a1 cycle-2 R2], M31's alignment and M51's probe all hard-code 4096. 16 KB (apple silicon laptops under linux, android-class arm) and 64 KB kernels exist [external: src 3, arm64 doc]. that is a correctness risk in our own new code, not in S19.

---

## (c) ideas (compact)

### M75. network and parallel filesystem branch (inside M9)

1. **byte-identical.** it is advice plus stream counts and read hints.
2. **mechanism.**
   - *wrong intuition*: "a network filesystem is just a slow disk, so the same planner rules apply."
   - two things differ. bandwidth for one file is set by how the file is laid out. on lustre, a file with stripe count 1 lives on one storage target, and 4-8 stripes "aggregate bandwidth" for a large single-client file [external: src 1]. and each read pays a network round trip, so a small read-ahead leaves the link idle. ubuntu ≥ 18.04 and rhel ≥ 8.3 default nfs read-ahead to 128 KiB [external: src 2].
   - the branch:
     - detect the filesystem type from `/proc/self/mountinfo`
     - on lustre, print "db striped over N targets; `lfs setstripe -c 4-8` and recopy" when N = 1
     - on nfs, set `POSIX_FADV_SEQUENTIAL` on the db fd. it doubles read-ahead and needs no root [external: cycle-2 posix_fadvise]. print the root-only `read_ahead_kb` advice [external: src 2]
     - raise loader streams to at least the stripe count
     - for job arrays, advise staging the db once per node to local nvme or `/dev/shm`, or using M60's daemon, because the page cache is per node
   - *worked example*: one stream, 128 KiB read-ahead, 0.5 ms round trip [guess] gives ≤ 128 KiB / 0.5 ms = 256 MB/s [arith]. that is 111 GB in ~430 s [arith]. 8 streams, or a stripe count of 8, divide that if the servers keep up [guess]. upstream's own cold load, with 8 streams on network block storage, reached the provisioned 1 GB/s [external, via a4: PR #1033].
3. **gain per class**: H4-on-shared-storage and H5: cold loads [guess] 2-8x (stripe and stream count); warm 1.0x. H1, H2, H3: 0 unless the db sits on nfs.
4. **days**: 0.5 (fs detection plus advice lines; the stream count already lives in M9).
5. **risk**: stripe layouts are site policy and need a recopy. advice only, never automatic. querying the stripe count programmatically needs lustre's ioctl or `lfs` [UNCLEAR], so the first version only prints the fs type and the command.
6. **cheapest kill test**: one cluster run (M78): cold `dd` of a 15 GB db copy at stripe 1 vs stripe 8. kill if they are within 1.5x.
7. **sources**: src 1, src 2.

### M76. page-size-agnostic code, and huge-page alignment from sysfs

1. **byte-identical.**
2. **mechanism.**
   - *wrong intuition*: "linux pages are 4 KB, and huge pages are 2 MB."
   - on arm64 the base page can be 4K, 16K or 64K. with 16K the PMD huge page is 32M; with 64K it is 512M [external: arm64 doc]. android tells native code to drop every hard-coded 4096 and ask `sysconf(_SC_PAGESIZE)` [external: src 3].
   - the rule, for our code:
     - every page computation (M30's page index, M31's `DONTNEED` alignment, the `mincore` vector, M51's direct reads) uses `sysconf(_SC_PAGESIZE)`
     - `O_DIRECT` alignment uses the device's logical block size, not the page size [guess: standard rule, not fetched]
     - S14 / RC1's 2 MB `posix_memalign` should align to `/sys/kernel/mm/transparent_hugepage/hpage_pmd_size` when it is larger
   - *worked example*: on a 16K kernel, `mincore` returns one byte per 16 KB page. M30's 4096-based index is 4x too large, so its residency check reads the wrong byte: byte 4i instead of byte i [arith: 16384 / 4096 = 4]. it then skips reads that are needed, or issues ones that are not. the upside of 16K for the table: 103GB has 6.8M pages instead of 27.1M, so 4x fewer faults and 4x smaller page tables (217 MB → 54 MB) [arith].
3. **gain per class**: none by design. it prevents wrong code on 16K / 64K kernels (apple-silicon linux laptops in H1, some arm servers in H4 [guess on which distros]). on 64K kernels, S14's 512M PMD needs 512 MB of contiguous free memory, so fault-time huge pages will often fail there [guess]. CONT PTE at 2M [external] may be the useful size instead.
4. **days**: 0.25.
5. **risk**: none.
6. **cheapest kill test**: `getconf PAGESIZE` plus `cat .../hpage_pmd_size` on every box we touch (orin probe, any arm vm). if every box says 4096 and 2097152, the rule still costs nothing, so keep it.
7. **sources**: src 3, arm64 doc.

### M77. input read-ahead outside the lock (and: do not use io_uring)

1. **byte-identical.**
2. **mechanism.**
   - *wrong intuition*: "io_uring is the modern way to read the input fast."
   - it is blocked by docker's default seccomp profile [external: src 4], so it fails in containers, which is H5's normal setting. and the input is one sequential stream, so batching submissions buys little.
   - the real stall: RC1's `fast_reader` does the raw `read()` inside the input lock [external, via a3 cycle-1 S4]. on a cold or network input, the lock holder waits on the device while every worker waits on the lock. kernel read-ahead hides this only if its window covers latency x bandwidth. at 128 KiB on nfs it may not [external: src 2].
   - fix: outside the lock, after each block, issue `posix_fadvise(fd, next_offset, N MB, POSIX_FADV_WILLNEED)` for the next few blocks. it is non-blocking [external: cycle-2 posix_fadvise], works on any kernel and in any container, and costs one syscall per block.
   - *worked example*: on orin emmc, the 12.5 GB input reads in 31-50 s [arith: conclusion]. today that overlaps with classify only as far as read-ahead runs ahead. with M77, the device stays busy for the whole run, so the input costs max(31-50 s of i/o, classify) instead of part of their sum [guess on today's overlap]. on nfs at 256 MB/s per stream [arith, M75], 12.5 GB is ~49 s, and a deep WILLNEED queue moves it toward the link rate [guess].
3. **gain per class**: cold or network input only. H2 emmc and H5 gp3: up to the input's device time [UNCLEAR how much overlaps today]. H4 shared storage: likewise. warm: ~0. luna's warm input [repo]: 0.
4. **days**: 0.5, on `fast_reader` (it can go upstream).
5. **risk**: WILLNEED may be trimmed under memory pressure [external: cycle-2]. on small boxes it pairs with M31's `DONTNEED` behind the read point. a null if read-ahead already keeps up (local nvme).
6. **cheapest kill test**: on the slow device, compare `cat input > /dev/null` speed with the input rate kraken2 achieves on a cpu-light run (50MB db, `--output /dev/null`). if kraken2 already reads at ≥ 90% of `cat`'s rate, kill it.
7. **sources**: src 2, src 4; cycle-2 posix_fadvise.

### M78 (measure, optional). one run on a shared parallel filesystem

if a cluster account exists (IIT delhi hpc [UNCLEAR access]):
- `lfs getstripe` (or the gpfs / nfs equivalent) on a db copy
- cold copy-load and `-M` timing at stripe 1 vs 8
- `cat` of the input
- read_ahead_kb of the mount

~1 h. it decides M75 and M77 for the hpc case. like M53, it is the only route to real numbers for its class.

---

## (d) rankings (unchanged from `cycle_2_conclusion.md`)

### top 10 build
1. M2 (+M3, M27a, M40, block list; + M76's alignment line)
2. M20' (+M17, M62)
3. M9 (+M24, M51, M33, **M75, M77**; M76 rule)
4. M4
5. M30 (M76 rule)
6. M41
7. M5
8. M26 (+M8a)
9. M11 (+M64)
10. M21 (+M42)

### top 5 measure-first
1. M22
2. M1
3. E1 (+cold pair, qd1-vs-qd16, exit column, back-to-back pair with `thp_gb`, M60)
4. cpu gate
5. M61

optional, unranked: the orin probe (+`getconf PAGESIZE`, `hpage_pmd_size`), M53, M78.
