# cycle 1, round 1, a4_hw (hardware spread)

role: for every idea, its effect on H1 laptop, H2 orin, H3 8 GB box, H4 big server, and cold vs warm storage. i own the machine model.

---

## sources read this cycle

fetched and used (all new, no earlier cycle files exist):

1. **nvidia jetson orin product page**, https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/ . claims used, agx orin 64GB column: "12-core Arm Cortex-A78AE v8.2 64-bit CPU", "3MB L2 + 6MB L3", max "2.2 GHz", "64GB 256-bit LPDDR5", "204.8GB/s", "64GB eMMC 5.1". supports: part A H2 row, section 0 corrections, idea 1.
2. **nvidia forum, agx orin 32GB measured bandwidth**, https://forums.developer.nvidia.com/t/jetson-agx-orin-32gb-measured-memory-bandwidth-much-lower-than-theoretical-spec/331766 . claims: a user's cpu stream copy gave ~54.5 GB/s with `OMP_NUM_THREADS=8`, `nvpmodel -m 0`, `jetson_clocks`. nvidia staff got "72GB/s" copy on one run and "Avg: 55 GB/s" on a 32GB kit. staff: "The memory controller has an arbiter that allows other cores like CPUs, USB/PCIe root complex access to the memory also." supports: H2 achievable bandwidth, idea 2.
3. **wikipedia, multimediacard (emmc versions table)**, https://en.wikipedia.org/wiki/MultiMediaCard . claims: emmc 5.1 row = 250 MB/s sequential read, 125 MB/s sequential write, 11,000 random read iops, 13,000 random write iops. emmc 5.0 "introduced the HS400 interface mode, enabling theoretical data transfer speeds of up to 400 MB/s". the fetch tool flattened the table; it inferred the column placement from value order, consistent across rows. supports: storage axis, idea 1, section 0 item 3.
4. **jedec emmc v5.1 press release** (mirror, because jedec.org returned 403), https://us.design-reuse.com/news/36653/jedec-e-mmc-standard-update-v5-1.html . claim: "Command Queueing will enable the device to analyze commands before executing them", with "a positive effect on random read performance and read latency". no numbers. supports: idea 1 (queue depth on emmc).
5. **tmpdir community storage tests**, https://community.tmpdir.org/t/sd-emmc-ssd-nvme-usb-bandwidth-tests-on-amd-ryzen-i-mx8-and-jetson-orin-nano/1149 . claims (`hdparm -tT`, sequential): i.mx8 emmc 280.14 MB/s; ryzen sata ssd 332.61 MB/s; samsung 970 evo nvme 1,847-2,035 MB/s; orin nano nvme 1,553.92 MB/s; orin nano sd card 70.04 MB/s; the author says results varied from run to run. supports: storage axis, ideas 1 and 2.
6. **the ssd review, kingston dcp1000 enterprise nvme**, https://thessdreview.com/featured/kingston-dcp1000-enterprise-nvme-ssd-review-1-6tb-7gbs-1-mil-iops-single-hhhl-ssd/3 . claims: 4 KB random read latency "0.106ms at QD 1-16", 0.111 ms at qd32, 0.235 ms at qd256; "1.1 million IOPS at QD256". supports: idea 1 nvme crossover, idea 2.
7. **esmaili-dokht et al., "a mess of memory system benchmarking, simulation and application profiling", micro 2024**, https://arxiv.org/html/2405.10170v4 . claims (table I): unloaded memory latency sapphire rapids 109 ns, zen 2 113 ns, graviton 3 122 ns (the prose says 129 ns, so the paper conflicts with itself), skylake 89 ns, cascade lake 85 ns. saturated bandwidth: sapphire rapids 60-86% of theoretical, zen 2 57-71%, most platforms "between approximately 70% and 90%". saturation is where "the memory access latency doubles the unloaded latency". max loaded latency on sapphire rapids 238-406 ns. supports: part A latency and achievable-bandwidth rows, ideas 2 and 3.
8. **chips and cheese, "sapphire rapids: golden cove hits servers"**, https://chipsandcheese.com/p/a-peek-at-sapphire-rapids . claims: "SPR's DRAM latency was measured at just above 107 ns, with a 1 GB array and 2 MB pages"; l3 latency "around 33 ns"; "In DRAM-sized regions, we get just over 200 GB/s bandwidth"; quotes little's law, "steady state throughput is equal to queue size divided by latency". supports: part A H4 row, idea 5.
9. **hwcooling, golden cove microarchitecture analysis**, https://www.hwcooling.net/en/intel-alder-lake-golden-cove-cpu-core-unveiled-microarch-analysis/2/ . claims: "L1 cache fill buffers were increased from 12 to 16"; l2 outstanding misses raised from 32 to 48; l1 data tlb 64 to 96 entries; page walkers 2 to 4. this is the client golden cove core. that luna's sapphire rapids core has the same buffers is [guess]. supports: idea 5, the s20 reading.
10. **linux kernel abi, sysfs-devices-system-cpu**, https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-devices-system-cpu . claims: `cpu*/cache/index*/` holds `size` ("the total cache size in kB"), `level`, `type`, `shared_cpu_list` ("the list of logical cpus sharing the cache"); `topology/thread_siblings_list` lists "cpuX's hardware threads within the same core"; `physical_package_id` is the socket. supports: the detection table, ideas 2 to 4.
11. **linux kernel abi, sysfs-block**, https://www.kernel.org/doc/Documentation/ABI/stable/sysfs-block . claims: `queue/rotational` says whether the device "is of rotational type or non-rotational type"; `queue/nr_requests` "controls how many requests may be allocated in the block layer"; `queue/read_ahead_kb` is the "Maximum number of kilobytes to read-ahead"; `inflight` relates to nr_requests and the scsi queue_depth. supports: the detection table, ideas 1 and 2.
12. **linux kernel docs, transparent hugepage (6.8)**, https://docs.kernel.org/6.8/_sources/admin-guide/mm/transhuge.rst.txt . claims: `enabled` takes always, madvise or never; `hpage_pmd_size` lets userspace learn the size of a pmd-sized huge page; "Currently THP only works for anonymous memory mappings and tmpfs/shmem"; failed huge allocations fall back to small pages (`thp_fault_fallback`). supports: part A S14 row, the detection table.
13. **linux kernel docs, arm64 hugetlbpage**, https://docs.kernel.org/arch/arm64/hugetlbpage.html . claims: with 4K base pages the pmd huge page is 2M; with 64K base pages it is 512M. the fetch tool inferred the column alignment of a flattened table. supports: part A S14 row on arm.
14. **linux kernel docs, sysctl kernel, numa_balancing**, https://docs.kernel.org/admin-guide/sysctl/kernel.html . claims: numa balancing "samples what task thread is accessing memory by periodically unmapping pages"; "The unmapping of pages and trapping faults incur additional overhead"; the doc advises disabling it if the workload is already bound to numa nodes. supports: idea 4.

fetch failures (claims from these are NOT used as [external]):
- nvidia agx orin technical brief pdf, and the hot chips 2022 orin slides pdf: both came back as binary, unreadable. a search snippet said "2 MB l3 per cluster, 4 MB system cache". i did not read the source, so the 4 MB system cache stays [repo] and "2 MB per cluster" is [arith] (6 MB / 3 clusters).
- arm cortex-a78ae technical reference manual (javascript-only page), wikichip a78 and zen 3 pages (connection refused), anandtech zen 3 deep dive (site gone, archive blocked). so the outstanding-miss count of the a78ae and of zen 3 is [UNCLEAR].
- vldb 2016 amac paper pdf (binary), jedec.org (403), two emmc vendor datasheets (binary), nvidia forum thread 258456 (it has no numbers).

repo files read: `00_context.md`; `talk_track_sir_2026-10-21.md`; `next_steps_plan_2026-10-21.md` (all of it); `research_brief_next_speedups_2026-10-21.md`; `dorado-kraken-research/AccuracyDrift/machines/Orion.md`; `dorado-kraken-research/AccuracyDrift/RESULTS.md` (sections 1.4, 2); `dorado-kraken-research/AccuracyDrift/OBSERVATIONS.md` (orion sections); `dorado-kraken-research/Luna/luna_stats.md`; `dorado-kraken-research/docs/Luna_vs_Minerva.md` (orion part); `plan_paper/scripts/s6plus/laptop_loadscale.ps1`.

---

## 0. four repo numbers that are wrong or shaky (read before using them)

1. **orin bandwidth and clock.** `OBSERVATIONS.md` says "LPDDR5-6400 × 128-bit bus, ~102 GB/s theoretical peak, ~68 GB/s practical" and "Cortex-A78 at ~1.7 GHz" [repo]. those numbers fit the orin nx / orin nano modules, not agx orin 64GB. nvidia lists agx orin 64GB as 256-bit lpddr5, 204.8 GB/s, cpu max 2.2 GHz [external: source 1]. so the 205 GB/s peak in `00_context.md` is right. but the cpu can't reach it: cpu stream copy on an agx orin 32GB gave 55-72 GB/s [external: source 2], 27-35% of peak [arith].
2. **orin cache.** `Orion.md` calls the 4 MB system cache "SLC (L3)" [repo]. nvidia lists "3MB L2 + 6MB L3" for the cpu [external: source 1]. so each 4-core cluster has its own 2 MB l3 [arith: 6 / 3], and the 4 MB system cache sits behind that [repo]. the conclusion "every db is post-cliff on orin" still holds: 50 MB is far above 2 + 4 MB.
3. **orin emmc speed.** `OBSERVATIONS.md` item 84 says the first 8GB run read the db at "~2.5 GB/s effective" and calls the device "NVMe-spec internal eMMC" [repo]. emmc hs400 tops out at a theoretical 400 MB/s [external: source 3]. so that run was not cold. a 3 s penalty at 0.25-0.4 GB/s means at most 0.75-1.2 GB came from the device [arith], so 84-90% of the 7.6 GB file was still cached [arith]. orin cold has never been measured. i use 0.25 GB/s as a class number [external: source 3], unverified on our board.
4. **cost per read is not a function of table size alone.** at 1 thread the 50MB db is slower than 8GB on both machines: orin 47.53 s vs 21.19 s, luna 19.73 s vs 16.78 s [repo: RESULTS.md 2.3]. so the capped 8GB/16GB builds do less work per read. my guess: a db built with `--max-db-size` skips lookups for minimizers above a hash threshold [guess, from memory of the kraken2 source: check `minimum_acceptable_hash_value` in `classify.cc`]. flag for a1 and a5: a machine model must count lookups per db, not assume one lookup per minimizer everywhere.

---

## part A: the class model

### A1. the numbers that decide kraken2 speed

terms first:
- **channel**: one independent 64-bit path from the memory controller to the dimms. more channels give more bandwidth in parallel.
- **peak bandwidth**: transfers per second x bytes per transfer x channels. ddr4-3200 on one channel = 3200e6 x 8 B = 25.6 GB/s.
- **achievable bandwidth**: what a real program measures. always below peak.
- **dram latency (unloaded)**: time from a load missing the last cache to its data arriving, on an idle machine. under load it grows.
- **llc** (last-level cache): the biggest on-chip cache.
- **mlp** (memory-level parallelism): how many cache misses one core can keep in flight at once. it is capped by **line fill buffers** (lfb, the slots that track l1 misses) and the l2 miss queue.
- **iops**: input/output operations per second, here random 4 KB reads.
- **queue depth (qd)**: how many requests the storage device has in flight at once.

| quantity | H1 laptop (ck's 5800H) | H2 orin agx 64GB | H3 8 GB box (generic) | H4 luna |
|---|---|---|---|---|
| cores / smt | 8c / 16t [repo] | 12c, 3 clusters of 4, no smt [repo] | 4-8c [guess] | 2 x 48c, smt 2 = 192t [repo] |
| clock max | [UNCLEAR] | 2.2 GHz [external 1]; the repo's ~1.7 GHz is wrong for this module | [UNCLEAR] | 3.8 GHz [repo luna_stats] |
| memory channels | 1, one ddr4-3200 dimm [repo measured] | 256-bit lpddr5 [external 1]; channel count [UNCLEAR] | 1-2 [guess] | 4 of 8 per socket populated [repo measured] |
| peak bandwidth | 25.6 GB/s [arith] | 204.8 GB/s [external 1] | 12.8-51.2 GB/s [guess] | 153.6 GB/s per socket, 307 total, if ddr5-4800 [repo, speed unverified] |
| achievable bandwidth | 15-23 GB/s if it behaves like the mess platforms (57-90%) [arith on external 7, applied by guess]; smoke copy 9.2 GB/s, which is ~18 GB/s of traffic (a copy reads and writes) [measured smoke + arith] | cpu stream copy 55-72 GB/s, measured on an agx orin 32GB [external 2] | [UNCLEAR] | 92-132 GB/s per socket [arith: 60-86% x 153.6, external 7]; chips and cheese got "just over 200 GB/s" on their spr test box [external 8] |
| dram latency, unloaded | [UNCLEAR]; mess has a zen 2 server at 113 ns [external 7], but a monolithic laptop chip differs | [UNCLEAR]; the repo's 100-130 ns has no source [repo] | [UNCLEAR] | 107-109 ns on spr systems [external 7, 8]; luna itself unmeasured |
| latency near saturation | [UNCLEAR] | [UNCLEAR] | [UNCLEAR] | 238-406 ns on spr [external 7] |
| mlp per core | [UNCLEAR] (zen 3 counts not fetched) | [UNCLEAR] (a78ae manual unreadable) | [UNCLEAR] | 16 lfb, 48 l2 misses on golden cove [external 9; same in spr is a guess] |
| caches | l3 16 MB shared [repo]; l2 [UNCLEAR] | l2 3 MB total (256 KB per core [arith]), l3 6 MB total, 2 MB per cluster [external 1 + arith], 4 MB system cache [repo] | 4-16 MB l3 [guess] | l2 2 MB per core, l3 105 MB per socket [repo]; l3 latency ~33 ns [external 8] |
| ram total / free | 16 GB, 13.9 usable, 2.9-3.8 GB free when checked [repo] | 64 GB shared with the gpu [repo] | 8 GB, ~5-6 GB usable [guess] | 503 GB; ~100 GB memfree, 359 GB page cache [repo] |
| numa nodes | 1 [guess] | 1 [repo] | 1 [guess] | 2, numa_balancing = 1 [repo] |
| storage | nvme, model [UNCLEAR]; smoke unbuffered reads 0.54 GB/s at 1 thread, 2.09 GB/s at 2 [measured smoke] | 64 GB emmc 5.1 [external 1], 8.5 GB free [repo] | sata ssd, emmc or nvme [guess] | perc raid ssd, read_ahead_kb 1024 [repo] |
| cold read, sequential | consumer nvme 1.5-2.0 GB/s by hdparm [external 5] | emmc 5.1 class 250 MB/s, hs400 ceiling 400 MB/s [external 3]; one measured emmc (i.mx8) 280 MB/s [external 5]; our board [UNCLEAR] | sata ssd 333 MB/s, one drive [external 5]; hdd [UNCLEAR] | raid [UNCLEAR]; next_steps guesses 1.5-8 GB/s [repo guess] |
| cold read, random 4 KB | enterprise nvme 0.106 ms at qd1-16, so ~9.4K iops at qd1 [external 6 + arith]; consumer drive [UNCLEAR] | emmc 5.1 class 11,000 iops [external 3] | hdd [UNCLEAR], [guess] 100-200 iops | [UNCLEAR] |
| warm 1-thread load rate (fault + copy, stock) | not linux; windows smoke `file_fresh` 3.2 GB/s [measured smoke] | ~3.5 GB/s: 15 GB in ~4.23 s sys, stock v2.1.3, 16GB [arith on repo RESULTS 1.4] | [UNCLEAR] | ~2.0 GB/s: 111 GB in 56.2 s [arith on measured]; 16GB ~1.8 GB/s (15 GB in 8.40 s, exit included) [arith] |
| cost per lookup, 1 thread | X | ~424 ns: 50MB, ~112M lookups [guess] in 47.53 s [arith] | X | s10 ~334 ns, stock ~488 ns: 103GB, ~2.0G lookups [guess] [arith] |

one surprise in this table: orin's stock loader fills memory ~1.8x faster per thread than luna's (3.5 vs 2.0 GB/s) [arith], even though luna has the faster core. two candidates:
- orin's kernel may run thp (transparent huge pages) in "always" mode, so stock's big allocation already gets 2 MB pages and pays 512x fewer faults [guess]
- luna's fault path may be slower: two sockets, numa_balancing on, kernel 6.8 vs 5.10 [guess]

the check is already in E2 step 1 (`cat /sys/kernel/mm/transparent_hugepage/enabled` on orin), plus `grep AnonHugePages /proc/meminfo` during one stock run. it matters: if orin runs "always", S14 buys nothing there, and stock already has part of S19's load win. then next_steps' "3x to 10x on few reads" orin prediction is too high.

### A2. what a program can detect at startup, without root

| fact | where | gives | gaps |
|---|---|---|---|
| usable cpus | the affinity mask, what `nproc` prints [guess: standard interface, not fetched] | honours `taskset` and cpusets | not a cgroup cpu quota [guess] |
| smt siblings | `/sys/devices/system/cpu/cpuN/topology/thread_siblings_list` [external 10] | physical core count | |
| sockets | `topology/physical_package_id` [external 10] | socket count | |
| cache sizes | `/sys/devices/system/cpu/cpu0/cache/indexN/{level,size,type,shared_cpu_list}` [external 10] | llc size, which cpus share it | whether orin lists its 4 MB system cache [UNCLEAR] |
| numa | `/sys/devices/system/node/` [guess]; `numa_balancing` sysctl [external 14] | node count, balancing on or off | |
| thp mode, huge page size | `/sys/kernel/mm/transparent_hugepage/enabled` and `hpage_pmd_size` [external 12] | whether S14's madvise will work, and at what size | |
| free ram | `/proc/meminfo` MemAvailable [guess: not fetched]; cgroup `memory.max` [guess] | does the db fit once, or twice | MemAvailable shows the host, not a job's cgroup limit [guess] |
| db already cached | the residency call `fincore` uses [repo: next_steps uses `fincore`] | warm vs cold, per file | |
| storage type | `/sys/block/<dev>/queue/rotational`, `nr_requests`, `read_ahead_kb` [external 11]; device names mmcblk / nvme / sd [guess] | hdd vs flash, queue limits | network filesystems have no block device [guess] |
| **not detectable** | memory channels (root `dmidecode`; luna's edac sysfs labels were readable [repo]), dram latency, mlp, achievable bandwidth, device iops | | measure with a micro-probe, or assume a class default |

what this means: cores, caches, numa, thp and storage type cost microseconds to read. bandwidth, latency and iops can't be read at all. an adaptive kraken2 either measures them (tens of ms) or falls back to a class default.

### A3. which S8-S19 stages should carry to each class (predictions)

every cell is [guess] unless tagged. the H4 column is measured on luna.

| stage | H1 laptop | H2 orin | H3 8 GB box | H4 luna (measured) | cold disk |
|---|---|---|---|---|---|
| S8 one stream | carries for multi-file input; smaller than luna, because 8 threads idle at each barrier, not 32 | 0 on our single-file orin inputs [repo next_steps E2] | as H1 | 1.05-1.41x | not related |
| S9/S16 prefetch | carries on every db, 50MB included, since 16 MB l3 < 50 MB | carries on every db: even 50MB misses the llc 79-83% on orin [repo RESULTS 1.4], vs 10% on luna. so the 50MB gain should beat luna's | carries on dbs that fit | 1.46x classify at 1 thread on 103GB; ~0 on 50MB (fits l3) | not related |
| S10 parallel load | warm: flat after ~2 threads (one channel); 1.2-2x on load [guess from smoke 3.2 to 3.8 GB/s] | warm: up to 12 threads against 55-72 GB/s, maybe 3-6x on load; but stock is already 3.5 GB/s per thread [arith] | the private copy needs ram the box doesn't have for 8GB+; S10 is beside the point | ~9x on load (58 s to 6.4 s) [measured] | device-bound; on an hdd, 32 streams may seek back and forth and lose |
| S12 no division | carries (cpu) | carries if aarch64 gcc has `__int128` [UNCLEAR]; otherwise S17's guard falls back to `%` | carries | -5.5% 50MB | not related |
| S13 memchr | carries; at 8 threads the parse is rarely the wall, so only the cpu saving shows | carries if aarch64 glibc `memchr` is vectorised [UNCLEAR] | carries | -12.8% 8GB | not related |
| S14 huge pages | depends on the thp mode: madvise works like luna; always means stock already has them; never gives 0 | thp mode [UNCLEAR]; the 3.5 GB/s stock load hints "always" [guess]. on a 64K-page arm kernel the pmd huge page is 512M [external 13], so a 2 MB alignment never gets pmd pages | small, fragmented ram gives fewer 2 MB pages | -20% to -23%; 103GB 35 s to 13-20 s | not related |
| S15, S17 | carry (cpu) | carry | carry | -1.6% to -3.7% | not related |
| S18 store forwarding | carries on x86 | depends on the core's forwarding rules [UNCLEAR on a78ae]: could be 0 or bigger | as H1 | -2% to -3% | not related |
| S19 guards | needed | needed; this is the build they exist for | needed | 0 by design | |

where each class probably spends its time after S19 [guess]:
- **H1**: the load is one-channel-bound. lookups are latency-bound on every db (16 MB l3). but 8 threads x ~3M lookups/s x ~3 lines x 64 B ≈ 4.6 GB/s of traffic [arith on luna's per-thread rate], well under 15-23 GB/s. so one channel hurts the load, not the lookups. ram is the hard wall: with 2.9-3.8 GB free, even 8GB doesn't fit.
- **H2**: lookups are latency-bound everywhere. 12 threads x ~2.4M lookups/s x 3 x 64 B ≈ 5.4 GB/s [arith], ~10% of achievable. the emmc is the killer on the first, cold run. the gpu shares the same lpddr5, so a concurrent dorado run would take bandwidth [guess; the controller arbitrates between clients per external 2].
- **H3**: ram-bound. only 50MB-class dbs run at memory speed. everything bigger runs at storage speed.
- **H4**: numa, smt, the 4-5 s exit, the serial parse, and kernel fault scalability. s10's 32 loader threads land 111 GB in ~6.2 s = ~18 GB/s, 0.56 GB/s per thread, about 3.5x below the 1-thread rate [arith]. so something other than bandwidth binds luna's load.

---

## part B: five ideas to make kraken2 adapt to the machine

### idea 1: cold-start load planner with a device model

**byte-identical**: yes, once E1's `-M` correctness gate passes. the planner only picks how the table gets into memory; every lookup reads the same cell. it builds on E1 and on next_steps' parked note "`-M` + `MADV_RANDOM`, only if E1 and E4 show `-M` is worth keeping" [repo]. the new part is the device model and the rule that flips by device.

**mechanism.**

the wrong intuition: "few reads, so memory-map; many reads, so copy". E1 tests that rule on warm luna. on a cold disk the right rule depends on the storage device, and it flips between devices.

terms:
- **memory-mapping (`-M`)**: the program reads the db file's pages straight from the page cache; nothing is copied up front.
- **major fault**: a page fault that must read the disk, because the page isn't cached.
- **readahead**: on a major fault, linux also reads the following pages, betting you'll want them. `read_ahead_kb` caps it [external 11].
- **`MADV_RANDOM`**: a hint that turns readahead off for a mapping, so a fault reads only its own page [repo: next_steps "it would stop the 1 MB read-around per fault"].

the real mechanism. there are two ways to get the table:
- **copy** costs `table_bytes / sequential_bandwidth`
- **map with `MADV_RANDOM`** costs `distinct_pages_touched / random_iops`
- `distinct_pages = P x (1 - e^(-L/P))`, with P = 4 KB pages in the table and L = lookups ≈ bases / 3 [repo: next_steps E1 formula; the density is a guess]
- the device sets both rates. flash has decent random iops. a hard disk has almost none.

worked example. 8GB db: 7.6 GB, P = 1.86M pages. 10 reads ≈ 10.7K lookups [repo], so ≈ 10.7K distinct pages.

| device | copy | map + random, 10 reads | winner | crossover |
|---|---|---|---|---|
| emmc 5.1: 250 MB/s, 11K iops [external 3] | 7.6 / 0.25 = 30.4 s | 10.7K / 11K = 0.97 s at qd1 | map, ~31x | ~345 reads [arith: D = 30.4 x 11K = 334K pages; L = -P ln(1 - D/P) = 368K lookups; / 1,070 lookups per read] |
| nvme: 2.0 GB/s, 0.106 ms per 4 KB up to qd16 [external 5, 6] | 3.8 s | qd1: 10.7K / 9.4K = 1.1 s; qd16: 10.7K / 151K = 0.07 s | map, 3.4-54x | ~640 reads at qd16 [arith, same method] |
| hdd: 150 MB/s, 150 iops [guess] | 51 s | 10.7K / 150 = 71 s | **copy**, 1.4x | never, on 8GB |
| hdd, 103GB (111 GB) | 740 s | 71 s | map, 10x | ~100 reads [arith: 740 x 150 = 111K pages ≈ 111K lookups] |

so the same "10 reads, so map" rule wins 31x on emmc and loses 1.4x on a hard disk. the planner needs `rotational` and a device class, and sysfs gives both [external 11]. queue depth matters too: with 12 threads faulting, the device sees up to 12 requests at once. emmc 5.1 command queueing helps random reads [external 4, no number]. the enterprise nvme's latency stays flat up to qd16 [external 6]. so on flash, random iops should grow with the number of faulting threads [guess on how much].

the planner, run once at startup (every threshold is a [guess], to be set from E1 and E4):
1. **residency**: how much of `hash.k2d` is cached already. mostly warm: use E1's warm rule.
2. **fit**: db size vs min(MemAvailable, cgroup limit). 2x fits: copy allowed. only 1x fits: map only. not even 1x: print the expected major-fault count and stop with advice (use a smaller db), because every strategy then runs at storage speed.
3. **cold**: estimate copy time and map time from the device class and the input size. pick the smaller. set `MADV_RANDOM` on the map branch only.
4. print the plan and the numbers behind it to stderr, so a wrong guess is visible.

variant 1b, for when the device is unknown (network filesystems): map the file, and start one background thread that streams it sequentially into the page cache while the workers classify through the mapping. small inputs finish on their own faults. big inputs find their pages already streamed. the cost: big inputs then classify on 4 KB file pages with no huge pages, which E1 predicts is slower warm [repo]. so 1b is the fallback, not the default.

the H3 case in numbers. 8GB db on an 8 GB box with ~5 GB usable: about 5 / 7.6 = 66% of the table can stay cached [arith on guess]. so ~34% of ~2G lookups miss, ≈ 680M random reads. at 151K iops that is ~4,500 s, against tens of seconds when the db fits [arith on guesses]. no load strategy fixes this, so the planner should say it up front. the real fix for H3 is a smaller-cell db (thesis 2), which is not byte-identical.

**gain per class**
- H1 laptop: cold, few reads, a db that fits: 3-50x on those cells [arith on external nvme numbers; ck's own drive UNCLEAR]. warm: that's E1's result, not this idea. ram-tight: no speedup, it avoids swapping [guess].
- H2 orin: cold 8GB at 10 reads, ~30 s to ~1 s, ~30x; cold 16GB, ~60 s to ~1 s [arith on emmc class numbers, unverified on our board]. at 1,000 reads and up it keeps the copy, so 0 loss.
- H3: no speedup. it turns a multi-hour thrash into an immediate message [arith on guesses].
- H4 luna: cold raid random iops [UNCLEAR]. without `MADV_RANDOM`, `read_ahead_kb` 1024 makes 10.7K faults pull ~10.7 GB, more than the whole 8GB file [repo next_steps], so the hint is what makes the map win cold. warm: E1.
- warm vs cold: warm and fits gives no change vs E1's rule. all gains are cold or ram-tight.

**days**: 3 for the planner, the hint, the residency and fit checks and the stderr plan, plus 1 to test cold on orin and luna.

**risk**
- `-M` on S19 is still not byte-checked (E1 step 2) [repo]
- `MADV_RANDOM` is wrong for big inputs on a cold disk, where readahead helps. the plan must never set it when the copy would win
- the emmc numbers are a class, not our board, and the repo's one "cold" orin run was not cold (section 0 item 3)
- on luna, other users' runs can evict the file mid-run [repo E1 confounders]
- overlap: a2 will likely propose the warm map/copy switch. this is the cold, per-device extension of it

**cheapest test that could kill it**: on orin, 8GB, 10 reads. evict the file (`dd iflag=nocache count=0` [repo protocol]), run S19 copy; evict, run S19 `-M`; evict, run a one-line `MADV_RANDOM` build. about 10 minutes. kill it if cold `-M` with the hint is not ≥ 3x faster than the cold copy.

**sources**: 3, 4, 5, 6, 11; repo next_steps E1 and section 5.

### idea 2: loader thread plan from cpus, quota and storage type

**byte-identical**: yes. thread counts change speed, never cells.

**mechanism.**

the wrong intuition: "more loader threads never hurt, so S10's `min(machine default, 32)` is safe anywhere". three cases break it.

1. **the loader ignores `--threads`** [repo]. on luna (66 users) a job that asks for 4 threads still loads with 32. on an hpc node inside a 4-cpu cgroup quota, the loader may start 32 threads on 4 cpus' worth of time [guess; whether the openmp default sees the quota is UNCLEAR].
2. **a hard disk hates parallel streams.** S10 has 32 threads `pread` 32 different 64 MB regions at once. warm, that is pure cpu work, and it splits well. cold on an hdd, the head jumps between 32 places. worked example [guess on hdd numbers]: if the disk switches stream every 512 KB request and each seek costs ~10 ms, it moves ~512 KB per ~10 ms ≈ 51 MB/s instead of ~150 MB/s sequential, about 3x slower than one stream [arith on guesses].
3. **flash wants the opposite.** on ck's nvme, unbuffered reads went from 0.54 to 2.09 GB/s going from 1 to 2 threads, 3.9x [measured smoke]. one stream leaves the drive idle between requests.

warm, the useful thread count is set by memory bandwidth, not by cores. a first-touch load moves ~3 bytes of dram traffic per table byte (zero, read, write) [repo guess factor]. so the knee is about `achievable_bandwidth / 3 / per_thread_rate`:
- laptop: 15-23 / 3 / 3.2 ≈ 1.6-2.4 threads [arith on guesses]
- orin: 55-72 / 3 / 3.5 ≈ 5-7 threads [arith]
- luna: (2 x 92-132) / 3 / 2.0 ≈ 31-44 threads [arith]. but luna's per-thread rate already falls ~3.5x by 32 threads (section A3), so there the kernel fault path sets the knee, not bandwidth. E4 measures it

the plan:
- warm: loader threads = min(what the user allowed through `--threads` or the affinity mask, the warm knee)
- cold and `rotational = 1`: one sequential stream, or one reader filling the page cache while the others copy
- cold flash: min(threads, 8-32) streams [guess on the cap]
- fix the order bug: call `omp_set_num_threads` before the table load, or pass the count in

**gain per class**
- H1: warm ~0, it is already flat past 2 threads [guess]. cold nvme: keep ≥ 2 streams, 1-4x vs a one-stream loader [measured smoke]. frees cores sooner on a shared laptop.
- H2: warm ~0 vs S19's default of 12 [guess]. cold emmc ~0 [guess].
- H3 with an hdd: avoids a ~3x cold-load regression [guess]. with sata or emmc ~0.
- H4: obeys `--threads` on a shared box, which is politeness, not speed. if E4 shows the 32 cap binds, lifting it gives ≤ ~1.5 s at small read counts [repo guess]. the hpc quota case is [UNCLEAR].
- warm vs cold: the hdd and nvme effects are cold only.

**days**: 1.5.

**risk**: no correctness risk. on our three machines it is probably a null unless E4 shows the cap binds. its value is on machines we don't have (hdd, hpc quotas), and no rotational disk is available to test it [UNCLEAR].

**cheapest test**: E4's luna loader sweep (`OMP_NUM_THREADS` 1-32), already planned [repo], gives the warm knee. for the hdd claim: the laptop script's `direct_touched` mode on any usb hard disk, 1 vs 8 threads, 5 minutes, if one is around. kill the hdd branch if 8 streams come within 20% of 1.

**sources**: 5, 10, 11; repo next_steps E4, `laptop_loadscale.ps1`.

### idea 3: online thread-count controller (thread parking)

**byte-identical**: yes. kraken2 writes output in input order through its in-order writer [repo: next_steps E5 "serial in-order output write"], and `modes.sh` already passes at 1 and 7 threads [repo: talk track section 5].

**mechanism.**

the wrong intuition: "use every hardware thread; `--threads $(nproc)` is the fast setting". on luna it isn't. classify on 103GB was 13-14% slower at 192 threads than at 64, for both stock (23.30 vs 20.38 s) and s10 (13.32 vs 11.75 s) [measured]. 96 is also worse than 64. nobody knows why yet [repo]. on other machines the best count is unknown too: a laptop with smt might gain or lose from the second thread per core [UNCLEAR].

a model can't predict this, so measure it during the run:
- **thread parking**: start T threads as now. keep a shared counter `active`. a worker whose id is ≥ `active` sleeps instead of taking the next block. changing `active` is free, and no openmp region restarts.
- **hill climb**: every window (for example 2% of input bytes), compute bases per second. try `active` = physical cores, then all hardware threads, then one socket's cores. keep the best. check once more later in the run.
- inputs under a few seconds of classify skip the controller, because there isn't enough signal [guess].

worked example, luna 103GB s10 [measured sweep]: windows at 64, 96 and 192 threads run in the ratio 11.75 : 12.12 : 13.32. the controller keeps 64. if the user passed 192, the run goes from 13.32 s to ~11.75 s plus the cost of the probe windows. with 3 windows of 2% each at a worse setting, that cost is at most 3 x 2% x 13% ≈ 0.8% [arith]. net ≈ 11%.

**gain per class**
- H4: 0-13% classify on 103GB when the user oversubscribes [measured: s0 and s10 spread]. S19's own spread is E5's job.
- H1: [UNCLEAR]; it hinges on whether smt helps latency-bound lookups on zen 3.
- H2: ~0. 12 cores, no smt, and stock scaled 11.4x at 12 threads on 50MB [repo], so there is nothing to choose.
- H3: [UNCLEAR], like H1.
- warm vs cold: warm only. cold runs are storage-bound.

**days**: 2.

**risk**: noisy windows pick the wrong count (reads differ in length, so use bases/s, not reads/s). near the serial-parse wall every count looks the same, and then fewer threads is fine. if the 64-vs-192 gap is gone in S19 (E5), the H4 case dies.

**cheapest test**: E5, already planned, 25 minutes. if S19's best and worst over {48, 64, 96, 192} differ by < 3% on every db, kill it for H4. then one smt laptop-class linux box decides H1.

**sources**: 7 (latency rises with load, one way extra threads can hurt); repo next_steps section 6.

### idea 4: numa placement policy for multi-socket servers

**byte-identical**: yes.

**mechanism.**

terms: **numa** (non-uniform memory access): each socket has its own memory, and reaching the other socket's memory is slower. **local / remote**: memory on your own socket vs the other one.

the wrong intuition: "S10's loader threads first-touch chunks from both sockets, so the table is spread evenly, so there's nothing left to do". spread evenly means about half of all lookups go to the remote socket [guess]. and luna runs numa_balancing = 1 [repo], which "samples ... by periodically unmapping pages", and the kernel says the "unmapping of pages and trapping faults incur additional overhead" [external 14]. on a 111 GB table that is a stream of extra faults during classify [guess on how many].

the policy, from the node count, per-node free memory and the thread count:
1. threads ≤ one socket's cores, and the table fits that node's free memory: bind threads and table to that node. all lookups local. the kernel doc advises turning balancing off for bound workloads [external 14].
2. ram ≥ 2 x table plus a margin, and many threads: one table copy per node, each thread reads its own node's copy. all local, at twice the load work.
3. otherwise: interleave, which is today's behaviour, made explicit.

worked example, luna: node 0 has ~47 GB free [repo], so 8GB and 16GB fit case 1 at ≤ 48 threads. stock 8GB once ran 21.8% faster at 32 threads pinned to node 0 than at 96 threads unpinned [repo: `dorado-kraken-research/CLAUDE.md`], but that mixes the thread count with the pinning. 103GB: 2 x 111 = 222 GB of 503 GB fits case 2 [arith], at the price of a second ~3 s load [guess from S19's 3.79 s total at 10 reads].

**gain per class**
- H4: 0-20% classify on dbs that fit one node. 0-25% on 103GB at ≥ 64 threads with replication, minus ~3 s of extra load, so long runs only [guess].
- H1, H2, H3: 0, one node [repo for orin; guess for the others].
- cold: replication reads the file once and copies it twice, so the cold cost doesn't change [guess].

**days**: 2 for cases 1 and 3, plus 1-2 for replication.

**risk**: replication takes 111 GB more ram on a 66-user box. binding needs libnuma or raw syscalls, a portability cost. E5's one-socket point may show no gain. this is next_steps' "numa replication or `--interleave`: luna only" item [repo]. i bring it back only because 2-socket nodes are the normal hpc kraken2 machine, so H4 is a class, not just luna.

**cheapest test**: E5 step 4, already planned: `numactl --cpunodebind=0 --membind=0` at 24 and 48 threads vs unpinned 48, on 8GB. kill case 1 if pinned 48 is not ≥ 5% faster than unpinned 48.

**sources**: 14; repo next_steps E5, `dorado-kraken-research/CLAUDE.md`.

### idea 5: memory-parallelism probe to set the prefetch depth

**byte-identical**: yes. S9 and S16 already show that prefetch timing doesn't change answers [repo].

**mechanism.**

the wrong intuition: "s20 tried batch 64 and got nothing, so prefetch depth doesn't matter on any machine".

the real mechanism is little's law: one core's random-lookup rate ≤ misses in flight / latency [external 8]. golden cove tracks 16 l1 misses and 48 l2 misses at once [external 9]. S16 already keeps up to 2 x 16 = 32 lookups prefetched [repo]. so on luna, more depth can't add parallelism. and luna's 1-thread s10 classify does ~2.0G lookups in 672 s = 3.0M lookups/s, 334 ns each [arith], far below the 16 / 107 ns ≈ 150M lines/s the buffers allow [arith]. so mlp isn't the binding limit there either. the s20 null fits both readings.

on the a78ae the miss-buffer count is [UNCLEAR], its dram latency is [UNCLEAR], and even the 50MB db misses the llc 79-83% of the time [repo]. so nothing supports luna's depth on orin. if the a78ae tracks fewer misses than S16 issues, the extra prefetches queue behind each other. if it tracks more, 16 is too shallow [guess].

the probe: after the load, pick a few thousand random slots of the real table. time batches with k = 1, 2, 4 ... 64 independent prefetch-then-read lookups in flight. take the smallest k after which ns per lookup improves < 5%. set `K2_B` = k, keep two batches in flight. it costs ~20-50 ms [guess], with no root and no sysfs.

worked example [guess, illustrative only]: if orin measures 400 ns at k = 1, 120 ns at k = 8 and 115 ns at k = 16, the knee is 8, and `K2_B` = 8 frees half the prefetch slots at no cost. if it measures 60 ns at k = 32, then 16 was too shallow and `K2_B` = 32 helps.

**gain per class**
- H4: ~0 [measured: s20 null].
- H2: 0-10% classify on all three runnable dbs [guess].
- H1: 0-5% [guess].
- H3: as H1, on dbs that fit.
- cold: 0.

**days**: 1.5.

**risk**: a 20 ms probe is noisy on a busy box; a wrong k is at worst today's default. the most likely outcome is a null everywhere, like s20.

**cheapest test**: E2 step 6, already planned: orin `K2_B` 8/16/32/64 on 16GB, 104,918 reads, 3 reps [repo]. kill it if all four are within 2%.

**sources**: 8, 9; repo next_steps E2 step 6, s20.

### my ranking of my own five

1. **idea 1, cold-start load planner**: the biggest numbers (~30x on cold emmc few-read cells [arith on external class numbers]), on the machine sir asked about, and the rule provably flips by device. it depends on E1's gate.
2. **idea 3, online thread controller**: there is a measured 13-14% spread to win on luna, it costs 2 days, and it needs no machine model.
3. **idea 2, loader thread plan**: mostly guards against regressions we can't test (hdd, quotas), plus the `--threads` order fix, which should land anyway.
4. **idea 4, numa policy**: real for the 2-socket class, zero everywhere else, and it costs ram.
5. **idea 5, mlp probe**: cheap, but the only data (s20) is a null, and E2 step 6 decides it for free.

---

## notes kept for later rounds

- least sure number in my class model: orin's cold emmc read rate. 0.25 GB/s is an emmc 5.1 class figure [external 3], never measured on our board, and the repo's one "cold" run was partly cached. idea 1's orin gains hang on it.
- next lookups if a later round needs them: a78ae outstanding-miss count (the arm manual as text), zen 3 miss buffers, orin's thp mode and base page size, luna's remote-node latency, ck's nvme model and its random 4 KB iops (the laptop script could time random direct reads with a small change).
- cross-agent flags: section 0 item 4 (capped dbs may skip lookups) for a1 and a5; the orin-vs-luna stock load rate (section A1) for a2; S18 on arm for a3.
