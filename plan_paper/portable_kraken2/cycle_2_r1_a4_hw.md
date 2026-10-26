# cycle 2, round 1, a4_hw (hardware spread)

role unchanged: every idea's effect per machine class. this round adds the class cycle 1 missed (a small cloud vm), fixes the grid cells i now think are wrong, and adds two ideas (M50, M51) that attack the queue-depth-1 problem behind M9.

---

## (a) sources fetched this cycle (all new; grepped the folder for each url)

| # | source | exact claim used | for |
|---|---|---|---|
| N1 | aws ebs gp2/gp3 docs, https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html | gp3 delivers "a consistent baseline IOPS performance of 3,000 IOPS" and "a consistent baseline throughput performance of 125 MiB/s"; provisioned up to 80,000 IOPS and 2,000 MiB/s; gp3 and gp2 "provide single-digit millisecond latency"; gp2 throughput "between 128 MiB/s and 250 MiB/s" | H5, M9, M50, M51, M13 |
| N2 | aws general-purpose instance table, https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html | m7i.large: 8 GiB, 2 vCPUs, **1 core, 2 threads per core**. m7i.xlarge: 16 GiB, 4 vCPUs, **2 cores, 2 threads**. m7g.xlarge (graviton3): 16 GiB, 4 vCPUs, **4 cores, 1 thread**. t3 is "burstable ... using CPU credits". ebs rows (baseline / max): m7i.xlarge 156.25 / 1,250 MB/s, 6,000 / 40,000 iops (16 KiB); m7i.large 81.25 / 1,250 MB/s, 3,600 / 40,000 iops | H5 |
| N3 | aws, ebs and nvme, https://docs.aws.amazon.com/ebs/latest/userguide/nvme-ebs-volumes.html | "Amazon EBS volumes are exposed as NVMe block devices" on nitro instances; device names "/dev/nvme0n1, /dev/nvme1n1" | M51 |
| N4 | raspberry pi processors doc, https://www.raspberrypi.com/documentation/computers/processors.html | bcm2712: "quad-core Arm Cortex-A76 CPU cluster, clocked at up to 2.4 GHz"; 512 kB l2 per core; 2 MB shared l3; 32-bit lpddr4x, "up to 17 GB/s of memory bandwidth" | H3-arm example |
| N5 | raspberry pi 5 product page, https://www.raspberrypi.com/products/raspberry-pi-5/ | "LPDDR4X-4267 SDRAM (1GB, 2GB, 4GB, 8GB, and 16GB)"; "microSD card slot, with support for high-speed SDR104 mode"; "PCIe 2.0 x1 interface ... (requires separate M.2 HAT ...)" | H3-arm example |
| N6 | chips and cheese, "arm's neoverse v2, in aws's graviton 4", https://chipsandcheese.com/p/arms-neoverse-v2-in-awss-graviton-4 | "114.08 ns of latency for accessing directly attached memory"; remote dram "north of 250 ns", "a 142.5 ns penalty"; l2 2 MB at 11 cycles; l3 36 MB, "68 cycles, or 25 ns"; "48 entry fully associative L1 DTLB", "2048 entry 8-way L2 TLB"; "Failed store forwarding costs 10-11 cycles on Neoverse V2, which is better than 19 or 20 cycles on Golden Cove or Zen 4". no l1d miss-buffer count | M2 on arm, M14 |
| N7 | notebookcheck, ryzen 7 5800h, https://www.notebookcheck.net/AMD-Ryzen-7-5800H-Processor-Benchmarks-and-Specs.512759.0.html | "a default TDP (also known as the long-term Power Limit) of 45 W that can be changed to anything between 35 W and 54 W"; 3.2 GHz base to 4.4 GHz boost; l2 4 MB, l3 16 MB; "supports dual-channel DDR4-3200"; one laptop "can be at least 20% faster in CPU-bound workloads than the slowest laptops built around the 5800H" | H1, M20, M54 |
| N8 | libgomp manual, OMP_NUM_THREADS, https://gcc.gnu.org/onlinedocs/libgomp/OMP_005fNUM_005fTHREADS.html, and ICV initialization, https://gcc.gnu.org/onlinedocs/libgomp/Implementation-defined-ICV-Initialization.html | "If undefined one thread per CPU is used". num-procs-var: "The number of CPU cores on the initial device, except that affinity settings might lead to a smaller number". neither page mentions cgroups or cpu quotas | M20 |
| N9 | victoriametrics, "container cpu requests & limits explained with gomaxprocs tuning", https://victoriametrics.com/blog/kubernetes-cpu-go-gomaxprocs/ | the go runtime's cpu count "ends up being the total number of cores on the node, not the actual cores available to the container"; `cpu.max` holds "the quota and the period, both in microseconds", 500m = `50000 100000`; "Once the container hits that 100ms limit, the kernel throttles it. All threads pause until the next period"; eight cpu-bound threads use a 100 ms quota in ~12.5 ms | M20 |

failed: the `posix_fadvise(2)` man page (twice, session limit), so the async-readahead semantics in M50 are [guess]. the amd 5800h page timed out (notebookcheck used instead). no chips and cheese article on the a78 / a78ae was found, so a78ae miss buffers and dram latency stay [UNCLEAR]. the aws footnote on how long the ebs "max" burst lasts was not read: [UNCLEAR].

---

## (b) counters to cycle_1_conclusion.md

### cells i now think are wrong

| row | cell now | corrected cell | why |
|---|---|---|---|
| M9 | H1 "~3x at qd1" | **uncapped ~3.4x, capped ~35x** | capped 8GB at 10 reads ≈ 1,050 lookups [a3 arith]: 1,050 x 0.106 ms = 0.11 s vs a 3.8 s copy [arith on R1 src 6] |
| M9 | H2 "5-30x, iops at unstated qd" | **capped 40-300x, uncapped 4-14x** | copy = 7.6 GB / 0.25-0.40 GB/s = 19-30 s [arith on class range]. map = faults x qd1 latency. qd1 latency [UNCLEAR], bracketed at 0.1-0.5 ms (0.1 from the 11K iops class row, 0.2-0.5 a5's guess): capped 1,050 faults → 0.1-0.5 s; uncapped 10.7K → 1.1-5.4 s [arith]. jetson users mostly carry capped prebuilt dbs [guess] |
| M9 | cold column | **add: network block storage at qd1 can flip it like an hdd** | gp3 has "single-digit millisecond latency" [N1]. uncapped 8GB-class, 10 reads: 10.7K x 1-9 ms = 11-96 s map vs 7.6 GB / 131 MB/s = 58 s copy [arith on N1], so the map can lose. capped: 1.05K x 1-9 ms = 1-9.5 s, map wins 6-55x [arith]. M50 removes the flip |
| M20 | H2 "11.4x on 50MB, 4.5x on 16GB (stock v2.1.3)" | **~11x on classify for all three dbs** with any parallel loader (v2.17.2, S19) | the 4.5x is stock's serial 4.23 s load. classify alone on orin 16GB: (28.42 - 4.23) / (6.32 - 4.23) = 11.6x [arith on measured, `RESULTS.md` 1.4] |
| M20 | H1 "5-8x" | **5.8-8x, ±20% by chassis** | if 1 thread boosts to 4.4 GHz and 8 threads drop to the 3.2 GHz base: 8 x 3.2 / 4.4 = 5.8x [arith on N7]. the same chip differs ≥ 20% between laptops [N7]. smt (16 threads) is [UNCLEAR] |
| M20 | "quota detection [UNCLEAR]" | **known to be needed. read `cpu.max`** | libgomp starts "one thread per CPU", affinity can lower it, a quota is not mentioned [N8]. runtimes see node cores, not the container's [N9]. worked example: a 4-cpu quota on luna's 192 cpus gives 400 ms per 100 ms period. 192 classify threads burn that in ~2 ms, then all pause ~98 ms [arith on N9's rule], every period. see M20 revised below |
| M2 | H2 "1.02-1.10x" | **1.01-1.08x** | S18 fixes a failed store forward. that costs 10-11 cycles on neoverse v2 vs 19-20 on golden cove [N6], so S18 is worth roughly half as much on big arm cores [guess]. a78ae [UNCLEAR] |
| M11 | H1 "3-4 GB free: 10-100x on uncapped 8GB+" | **applies to 103GB only among our dbs** | our 8GB/16GB are capped (lookups ~10x rarer). the only uncapped big db is 103GB, which needs 111 GB of laptop disk. capped dbs: [UNCLEAR] until M12 |
| H1 class note | "1 dimm, 25.6 GB/s" | **half-populated: the chip supports dual-channel ddr4-3200** [N7] | a second dimm doubles peak to 51.2 GB/s [arith]. it may help the warm load up to 2x and the latency-bound lookups little [guess]. a hardware fix worth one line in FINAL |

### ranking counters

- **M10 at 9 should drop below the line.** H5 adds a class where it does nothing: a cloud vm is one numa node with distro kernels of mixed age [guess]. its value is H4 plus kernels ≥ 6.1.
- **M13 at 10 rises for H5.** a cold cloud load is bandwidth-bound at 125 MiB/s [N1]. the 1.37x floor cuts the 8GB cold load from 58 s to ~42 s, and 2x to ~29 s [arith]. still cold-only. it stays at 10, now with a second class behind it.
- **M14 stays below the line**, but note one fact. on 2-socket arm (graviton4) remote dram is "north of 250 ns" vs 114 ns local [N6], a 2.2x ratio [arith]. so the H4-arm case gains more from M14 than luna would [guess]. still H4 only.

---

## (c) ideas (compact)

### M50. batched page-cache fault-in for map runs (raise queue depth)

**byte-identical.** it only changes when file pages arrive, never which cells are read.

**mechanism.**
- wrong intuition: "a few-read `-M` run is cheap because it touches few pages".
- real: one thread does all of a block's lookups. each touch of a non-resident page is a major fault that blocks that thread. so the device sees queue depth 1 (qd: requests in flight at once), and a cpu prefetch cannot start a page read [conclusion 1.5].
- fix: phase 1 already holds the block's lookup slots (RC1's tokens, S16's `fill()`). turn each slot into its 4 KB page, dedupe, and before resolving, start an asynchronous page-cache read for every missing page. two ways: `posix_fadvise` / `madvise` WILLNEED on each page range [guess: semantics not fetched], or 8-32 helper threads that each touch a share of the pages. the device then sees qd 8-32+.
- worked example, uncapped db, 10 reads, ~10.7K pages:
  - gp3: qd1 10.7K x 1-9 ms = 11-96 s. batched, capped by the volume's 3,000 iops [N1]: 3.6 s [arith]
  - nvme: qd1 10.7K x 0.106 ms = 1.1 s. qd16: 10.7K / 151K iops = 0.07 s [arith on R1 src 6]

**gain per class** (cold, few-read, map branch only; warm 1.0x):
- H1: nvme 3-15x on uncapped cells [arith], ~1-3x capped
- H2: emmc with command queueing [UNCLEAR], 1-5x [guess]
- H3: depends on the device
- H4: raid [UNCLEAR]
- H5: 3-27x on uncapped cells [arith: 11-96 s / 3.6 s]

**days**: 1-1.5, inside M9's map branch.

**risk**: WILLNEED may read ahead a larger window than 4 KB [UNCLEAR]. helper threads take cores. on an hdd a deep queue is a seek storm, though the elevator sorts it [guess]. useless if E1 kills the map branch.

**cheapest test**: on luna, time 1,000 random 4 KB `O_DIRECT` reads of `hash.k2d` at qd1 vs 16 parallel `dd` streams. ~2 min, no eviction needed. repeat on orin. kill if qd16 is < 3x faster per request on both.

### M51. device micro-probe at startup (folded into M24 / M9)

**byte-identical** (reads only, through `O_DIRECT`, so the page cache is untouched).

**mechanism.**
- wrong intuition: "sysfs tells M9 the device class".
- real: a gp3 volume shows up as `/dev/nvme1n1` [N3], the same name pattern as a local nvme drive. yet it is ~10-90x slower at qd1 (single-digit ms [N1] vs ~0.106 ms [R1 src 6]) and ~16x slower sequentially (125 MiB/s [N1] vs ~2 GB/s [R1 src 5]) [arith]. the rotational flag is presumably 0 for both [guess]. so the name and the flag cannot pick M9's branch.
- probe, only when residency says the db is cold: 32 random 4 KB reads of `hash.k2d` at qd1, 32 at qd16, one 64 MB sequential read.
- cost: nvme ~0.04 s; gp3 32 x 1-9 ms + 64 MB / 131 MB/s ≈ 0.5-0.8 s [arith]; hdd ~0.3 s of seeks plus ~0.4 s sequential [guess]. warm runs pay 0.

**gain**: indirect. it makes M9 pick right on H5 and on unknown devices, and it keeps M9 from the hdd and cloud flips above. **days**: 0.5-1. **risk**: probe noise on busy shared storage; cost is wasted for tiny dbs (skip below ~1 GB [guess]). **cheapest test**: the same standalone timing as M50's, on luna raid, orin emmc and, if possible, one cloud vm. kill if the three qd1 latencies sit within 3x of each other.

### M20 revised. thread default from cores, smt and the cpu quota

**byte-identical.**
- threads = min(physical cores in the affinity mask [R1 src 10], ceil(quota / period) from `cpu.max` [N9]).
- loader threads follow the same cap unless `--threads` is set explicitly.
- smt siblings join only if M18 or E5 shows they help.

**why**: libgomp does not see quotas [N8], and a quota-exceeding process stalls every thread each period [N9]. the stall can land while a thread holds `critical(seqread)` or sits at a barrier, so the whole team waits [guess].

**gain**: 1.0x where there is no quota. in containers and hpc jobs with a quota, it removes the per-period stall pattern. size [UNCLEAR].

### M53 (measure). small-cloud-vm probe, optional

one m7i.xlarge or m7g.xlarge run, if an account exists [UNCLEAR]:
- S19 and v2.17.2 on 50MB and 8GB
- cold from gp3, then warm
- M51's probe numbers

**cost**: ~1 h, a few dollars [guess]. **decides**: the H5 column below. it is also the only cheap way to get an arm and an smt-x86 core in one session with the same storage.

### M54 (measure). sustained-power protocol for laptop-class runs

a 5800H's long-term power limit is 45 W, configurable 35-54 W [N7], and the same chip differs ≥ 20% between laptops [N7]. so every H1 number needs:
- one discarded warm-up run of ~2 min
- 3 interleaved reps
- `scaling_cur_freq` logged every second

otherwise a 5-10% idea (M4, M8a) can't be read on a laptop. **cost**: +30% run time. it needs a linux boot on the laptop, which has no wsl today [repo: user memory].

---

## (d) rankings (conclusion ids, new ones from me)

### top 10 build

1. **M2 (+M3)**: the binary users install.
2. **M20 (revised: cores, smt, `cpu.max`)**: measured 11x on orin classify; quotas make it necessary on clusters and containers.
3. **M9 (+M24 probe, +M51)**: the only lever for cold and small-ram runs. M51 keeps it from choosing wrong on cloud and hdd.
4. **M4**: every isa, cpu-bound cells.
5. **M50 (new)**: the fix that makes M9's map branch pay at qd > 1. 1-1.5 days.
6. **M5**: gz inputs, every class.
7. **M8a**: ram-bound classes (H1, H2, H5 with 2 MB-class llc slices [guess]).
8. **M11**: uncapped dbs bigger than free ram, after M12.
9. **M21**: lets orin and mixed cloud fleets run one binary.
10. **M13**: cold, bandwidth-bound loads (H2 emmc, H5 gp3).

below the line: M10 (H4 plus new kernels only), M14, M18, M16, M19, M15, M7, M6.

**changes vs the conclusion**: insert M50 at 5; M10 drops below the line; everything else keeps its order.

### top 5 measure-first

1. **M22** lookup census (agree).
2. **M1** re-baseline (agree).
3. **E1 + cold pair**, plus the qd1-vs-qd16 random-read timing on `hash.k2d` (M50/M51's kill test, 2 min).
4. **M12** (agree), with the laptop-class repeat.
5. **orin probe**, plus qd1 random 4 KB latency and `cache/index*/size`.

optional, after these: M53 (cloud), M54 (laptop protocol).

**measure order: agree**, with the riders above.

---

## (e) new hardware class: yes, H5 small cloud vm

kraken2 runs in clouds and containers at this size, and this box differs from H1-H4 on four axes at once [guess on how common, the numbers are external]:

| quantity | H5 example: m7i.xlarge (x86) / m7g.xlarge (arm) |
|---|---|
| vcpus / cores | 4 vcpus = 2 cores x 2 smt (x86), or 4 real cores (arm) [N2] |
| ram | 16 GiB; m7i.large 8 GiB on 1 core x 2 smt [N2] |
| storage, default gp3 | 125 MiB/s, 3,000 iops, single-digit ms latency [N1]. slower sequentially than orin's emmc class (250 MB/s) [arith] |
| instance ebs cap | baseline 156.25 MB/s, 6,000 iops (16 KiB); max 1,250 MB/s [N2], max duration [UNCLEAR] |
| device name | `/dev/nvme*n1`, indistinguishable from local nvme by name [N3] |
| cold load | 8GB 7.6 GB / 131 MB/s = 58 s; 16GB 15 GB = 114 s; 103GB doesn't fit in 16 GiB ram [arith] |
| fit | 8GB fits once, not twice, in 16 GiB minus os [guess]. so copy vs map matters even warm |

H5 column for my top 10 [all guesses or arith on N1/N2]:
- M2 1.02-1.12x
- M20 2-4x for default users [guess: 2 smt-sharing cores, or 4 real cores on arm]
- M9 cold few-read: capped 6-55x, uncapped ≤ 1x without M50 [arith above]
- M4 5-20%
- M50 3-27x on uncapped cold few-read cells [arith]
- M5 1.5-3x when gz-bound [guess, only 2 cores to inflate with]
- M8a 2-8%
- M11 only for 103GB-class
- M21 lets one binary run across instance generations [guess]
- M13 1.37-2x on cold loads [arith]

**raspberry pi 5: no new class. treat it as an H3 example.** it has 4 a76 cores, 2 MB l3, 17 GB/s peak [N4], 1-16 GB ram, microSD (sdr104) or nvme over pcie 2.0 x1 [N5]. that is H3's ram limit with H2's small cache. the 50MB db is ram-bound there, like orin. the 8GB db fits only on the 16 GB model [arith], and microSD makes cold loads slower than emmc [guess].
