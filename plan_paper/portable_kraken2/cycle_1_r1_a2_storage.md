# cycle 1, round R1, a2_storage: storage and memory ideas for a portable kraken2 (2026-10-26)

agent: a2_storage (db file format and layout, compression, mmap vs copy, cold vs warm page cache, readahead, O_DIRECT / io_uring, huge pages, numa placement, small-ram footprint, exit teardown). research and writing only. nothing was run.

---

## sources read this cycle

all fetched today. "via proxy" means the pdf came back as binary and was read through `r.jina.ai`. each line: url, the exact claim used, which idea it supports.

1. linux kernel docs, transparent hugepage admin guide, https://www.kernel.org/doc/html/latest/admin-guide/mm/transhuge.html
   - "madvise(..., MADV_COLLAPSE) ignores these settings and collapses ranges to PMD-sized huge pages unconditionally." (idea 2)
   - defrag `madvise` is the default and "will enter direct reclaim like `always` but only for regions that are have used madvise(MADV_HUGEPAGE)". so S14's fault-time huge page can still fail and fall back. (idea 2)
   - "Currently THP only works for anonymous memory mappings and tmpfs/shmem." tmpfs mount default is `never`. per-process `FilePmdMapped` is in `/proc/PID/smaps`. (idea 2)
2. madvise(2) man page, https://man7.org/linux/man-pages/man2/madvise.2.html
   - `MADV_POPULATE_READ` (since 5.14): "Populate (prefault) page tables readable, faulting in all pages in the range just as if manually reading from each page." for a file mapping it may "read the underlying file". (idea 1)
   - `MADV_COLLAPSE` (since 6.1): "supports private anonymous pages, shmem pages, and file-backed pages"; independent of the sysfs THP settings; allocation "may enter direct reclaim and/or compaction"; file and shmem need `CONFIG_READ_ONLY_THP_FOR_FS`; failure errors `ENOMEM`, `EBUSY`. (idea 2)
   - `MADV_RANDOM`: read ahead less useful. `MADV_SEQUENTIAL`: pages "can be aggressively read ahead". (idea 1)
   - `MADV_HUGEPAGE` on file-backed, non-tmpfs memory: the file must not be open for write and the mapping must be executable. so the old `kraken2_opt_v1.patch` `MADV_HUGEPAGE` on the `-M` mapping could not have worked on a read-only data mapping. (idea 2)
3. lkml, "mm: use mapping_max_folio_order() for force_thp_readahead order" (v6, may 2026), https://lkml.rescloud.iu.edu/2605.3/08427.html
   - the existing `VM_HUGEPAGE` path in `do_sync_mmap_readahead()` "is gated on HPAGE_PMD_ORDER <= MAX_PAGECACHE_ORDER and always requests HPAGE_PMD_ORDER / HPAGE_PMD_NR". so on a filesystem with large folios, `MADV_HUGEPAGE` on a file mapping makes cold faults read 2 MB folios. (idea 2)
4. lkml, ext4 large folio series v2, https://lkml.iu.edu/hypermail/linux/kernel/2505.2/00482.html
   - large folios for ext4 regular files "with the exception of fsverity, fscrypt, and data=journal mode", rebased to 6.15-rc6. (idea 2)
   - **fetch failed**: phoronix "EXT4 for linux 6.16" (`https://phoronix.com/news/Linux-6.16-EXT4-Performance`) returned 403. the "merged in 6.16" claim is a search snippet only, so i treat the merge version as [UNCLEAR]. luna's 6.8 is older either way.
5. Crotty, Leis, Pavlo, "are you sure you want to use mmap in your dbms?", cidr 2022, https://www.cidrdb.org/cidr2022/papers/p13-crotty.pdf (via proxy)
   - random reads over a 2 TB range: fio "achieved close to 900K reads per second"; mmap fell to near zero once the page cache filled, "and finally recovered to approximately half of fio". (idea 4)
   - "the OS uses only a single process (kswapd) for page eviction, which was CPU-bound in our experiments". (idea 4)
   - "MADV_NORMAL causes the OS to read 128 KB from secondary storage"; `MADV_RANDOM` "reads only the necessary page". (idea 1)
   - when mmap is fine: "Your working set (or the entire database) fits in memory and the workload is read-only." (idea 1)
6. Haas and Leis, "what modern nvme storage can do, and how to exploit it", vldb 2023, https://www.vldb.org/pvldb/vol16/p2090-haas.pdf (via proxy)
   - synchronous one-at-a-time I/O "would result in a meager 10k IOPS (or 40 MB/s)"; "around 1000 concurrent I/O requests, i.e., more than 100 per device, are necessary"; each ssd is specified at "1.5 M random 4 KB reads per second". (ideas 1, 4)
7. MegIS, isca 2024, https://arxiv.org/html/2406.19113
   - "MegIS works with lexicographically-sorted data structures to avoid expensive random accesses to the SSD". (idea 4)
   - footnote 4: mmap vs "loads the entire database from the SSD to DRAM as the first step": "the second approach performs slightly better", because the run touches most of the db. (idea 1)
   - "For Kraken2, this results in a 293 GB database". (idea 4)
8. linux kernel docs, numa memory policy, https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html
   - for a private file mapping, the vma policy applies "only when an anonymous page is allocated on an attempt to write"; shared page cache pages "follow task policy, if any, else System Default Policy"; a policy "applies only to pages allocated after the policy is installed". (idea 5)
9. linux kernel docs, sysctl `numa_balancing`, https://docs.kernel.org/admin-guide/sysctl/kernel.html
   - "the kernel samples what task thread is accessing memory by periodically unmapping pages"; "If the target workload is already bound to NUMA nodes then this feature should be disabled." (idea 5)
10. lkml rfc, "sched/numa: allow interleave memory allocation for numa balance", https://lkml.iu.edu/2502.3/03383.html
    - "Under MPOL_INTERLEAVE mode, NUMA load balance page migration does not occur"; `mpol_misplaced()` returns `NUMA_NO_NODE`. (idea 5)
11. lkml, "mm: mempolicy: fix automatic numa balancing for shmem" (2026), https://lkml.iu.edu/2606.3/09439.html
    - commit fc3147245d19 "added a vma_policy_mof() gate to task_numa_work()": "VMAs whose policy lacks MPOL_F_MOF are skipped from NUMA balancing scans", i.e. "don't scan stuff the user explicitly pinned". (idea 5)
12. Mitosis, asplos 2020, https://export.arxiv.org/abs/1910.05398
    - replicating page tables across sockets "improves performance for large-scale multi-socket workloads by up to 1.34x". (idea 5)
13. zstd readme, https://github.com/facebook/zstd
    - on an i7-9700K, Silesia corpus: zstd 1.5.7 `-1` ratio 2.896, compress 510 MB/s, decompress 1550 MB/s; lz4 decompress 3850 MB/s. (idea 3)
14. cachestat(2) man page, https://man7.org/linux/man-pages/man2/cachestat.2.html
    - since linux 6.5; returns `nr_cache` and `nr_evicted` for a byte range of a file, given an fd. (idea 1)
15. LWN, fault-around patchset, https://lwn.net/Articles/588802/
    - "FAULT_AROUND_PAGES is 16 for now"; sequential read of a 16 GiB file with 120 threads: minor faults about 503M to 35M, run time 125 s to 32 s; worst case (one page touched every 2 MB) gives no reduction and extra overhead. (ideas 1, 2)
16. microsoft learn, wsl file systems, https://learn.microsoft.com/en-us/windows/wsl/filesystems
    - "For the fastest performance speed, store your files in the WSL file system if you are working in a Linux command line". (idea 1, H1 note)
17. Metabuli readme, https://github.com/steineggerlab/Metabuli
    - "Metabuli operates within user-specified RAM limits, allowing it to search any database that fits in storage." "A PC with 8 GiB of RAM is sufficient for most analyses." (idea 4, prior art)
18. nvidia developer forum, jetson xavier nx emmc bandwidth, https://forums.developer.nvidia.com/t/about-jetson-nx-emmc-i-o-bandwith/157714
    - "294 MB/sn Read, 82 MB/sn Write speed from eMMC of NX"; nvidia: "expected perf numbers". this is a different module from orin, so i use it only as an anchor. (ideas 1, 3)

searches that returned nothing usable: an orin agx emmc read benchmark (none found), Metabuli's out-of-core mechanism (not in the readme).

---

## repo facts this file leans on (checked today)

- **orin runs kernel 5.10.120-tegra** [repo: `dorado-kraken-research/AccuracyDrift/machines/Orion.md:18`]. luna runs 6.8.0-78 [repo: `dorado-kraken-research/Luna/luna_stats.md:188`]. the laptop's wsl2 kernel is 6.6.87.2 [repo: `dorado-kraken-research/matmul_reports/matrix_multiplication/README.md:16`]. this matters for every kernel feature below:

| feature | needs kernel | luna 6.8 | orin 5.10 | wsl2 6.6 |
|---|---|---|---|---|
| `mincore` (page residency of a mapping) | very old | yes | yes | yes |
| `MADV_RANDOM`, `MADV_WILLNEED`, `O_DIRECT` | very old | yes | yes | yes |
| `MADV_POPULATE_READ` | 5.14 [external: src 2] | yes | **no** | yes |
| `MADV_COLLAPSE` | 6.1 [external: src 2] | yes | **no** | yes |
| `cachestat` | 6.5 [external: src 14] | yes | **no** | yes |
| ext4 large folios | 6.15/6.16 [external: src 4, UNCLEAR] | no | no | no |

- **`-M` was measured once, on stock, in august** [repo: `dorado-kraken-research/Luna/experiments/patch/commands_log.md` lines 743-752, 702-711, 667-676]. 104,918 reads (`reads_hac.fastq`), `numactl --cpunodebind=0 --membind=0`, `--output /dev/null`, mean of 3:

| db | threads | stock, copy | stock, `-M` |
|---|---|---|---|
| 8GB | 32 | 4.45 s | 0.96 s |
| 16GB | 32 | 8.23 s | 1.26 s |
| 103GB | 1 | 110.8 s | 49.5 s |
| 103GB | 32 | 53.47 s | 4.17 s |
| 103GB | 96 | 53.24 s | 3.72 s |

  set this next to S19 copy at 104,918 reads in the 2026-09-24 matrix [repo: talk track section 5]: 8GB 1.08 s, 16GB 1.39 s, 103GB 4.50 s. so stock with `-M` was already about level with S19's copy at 104,918 reads. this is **not a result**: different sessions, different pinning, and the matrix wrote output to disk. it only says the crossover sits somewhere above 104,918 reads on luna, which E1 will measure.
- **an empty cell is the all-zero word.** the stock probe loop says `if (! table_[idx].value(value_bits_))  // value of 0 means data is 0` [repo: `dorado-kraken-research/Luna/experiments/kraken2_opt_v1.patch:99`, unchanged stock context]. at load factor 0.70 [repo: M1], 30% of `hash.k2d` is zero words.
- **the old patch put `MADV_HUGEPAGE + MADV_WILLNEED + MADV_RANDOM` on the `-M` mapping** [repo: same patch, lines 113-115]. per source 2, `MADV_HUGEPAGE` cannot act on a non-executable regular-file mapping, and per the patch's own review, `WILLNEED` and `RANDOM` fight [repo: `dorado-kraken-research/docs/presentation_plan.md:282`]. so nobody has measured a huge-page `-M` yet.

---

## the five ideas at a glance (my rank order)

| rank | idea | byte-identical? | main classes | builds on |
|---|---|---|---|---|
| 1 | one loader that picks its path (map / copy / direct read) from four startup probes | yes | all, cold and warm | E1, E4 |
| 2 | huge pages that actually land: `MADV_COLLAPSE` for the copy, huge file mappings for `-M` | yes | H1, H3, H4 (kernel ≥ 6.1); none on orin 5.10 | S14, E1 |
| 3 | partitioned out-of-core lookup for dbs bigger than ram | yes, if replayed exactly | H3, H1 (low free ram), H2 with 103GB | new |
| 4 | a compressed db container for slow and cold storage, made from the existing `hash.k2d` | yes | H2 cold emmc, hdd, network fs | S10 chunks |
| 5 | numa placement of the table on multi-node servers: interleave, then per-socket copies | yes | H4 only | none |

---

## idea 1. one loader that picks its path: map, copy or direct read

**byte-identical.** every path puts the same bytes at the same table offsets. builds on E1 (`-M` vs S19) and E4 (load scaling warm and cold); it is the "s22 auto-switch" the plan named but did not design [repo: `next_steps_plan_2026-10-21.md` E1 outcomes].

### mechanism

**the wrong intuition.** "there is one best way to load the table. find it on luna and ship it." on luna, warm, the best way for the full input is S19's parallel copy into huge pages. but that same choice is the worst one on a box where the db is not in the page cache (the kernel's copy of recently read files in spare ram), or where ram cannot hold the table twice.

**the real mechanism.** four facts are cheap to learn at startup, and together they pick the loader:
1. **input size**: total bytes of the input files, from `stat`. this predicts how much of the table the run will touch: touched ≈ 1 - e^(-lookups / windows), with lookups ≈ bases / 3 [repo: plan E1, density is a guess]
2. **residency**: how much of `hash.k2d` is already in the page cache. `cachestat` gives it in one call on kernel ≥ 6.5 [external: src 14]. `mincore` (a call that reports which pages of a mapping are resident) works on every kernel, orin included: map the file without touching it and ask
3. **free ram**: `MemAvailable` in `/proc/meminfo`. a private copy needs the table once more on top of the page cache
4. **device class**: `/sys/block/<dev>/queue/rotational`, plus the device name (nvme, mmcblk, sd)

the branches:

| case | path | why |
|---|---|---|
| warm, few reads | `-M` lazy mapping, default readahead | no copy, no zeroing, only touched pages fault, ~16 pages per fault [external: src 15] |
| warm, many reads, ram ≥ 2x table | S19 copy (parallel `pread` into 2 MB pages) | the run touches the whole table, so 2 MB pages win on TLB misses |
| cold, few reads | `-M` + `MADV_RANDOM` | read only the 4 KB pages the lookups hit, not 128 KB to 1 MB around each one [external: src 5] |
| cold, many reads | `O_DIRECT` (read straight from the device into the program's buffer, skipping the page cache) into the 2 MB-aligned table, stream count by device class | one device-to-table transfer instead of device-to-cache-to-table, and the cache is not filled with a second copy |
| table > `MemAvailable` | `-M` (or idea 3) | a copy would swap; see idea 3 for when even `-M` collapses |

the stream count is the only device-tuned number. a 64 MB `pread` per thread is a big sequential request, so io_uring (linux's batched asynchronous I/O interface) buys nothing here: 111 GB / 64 MB = 1,776 requests in a whole load [arith]. io_uring matters when you need ~1,000 small requests in flight [external: src 6]. what matters is how many streams the device likes:
- nvme: 8 to 32 streams [guess]
- sata ssd, emmc: 2 to 4 [guess]
- hdd: 1 or 2. S10's 32 streams on a spinning disk turn one sequential read into 32 interleaved ones, so the head seeks between them [guess; never measured, no hdd in this project]

**worked example: one db, three machines, 10 reads, 8GB db (7.6 GB file [repo: `dorado-kraken-research/CLAUDE.md`]).**
- luna, warm: S19 measured 0.46 s total [repo: matrix]. a lazy map touches ~10.7K lookups' worth of pages and skips the 7.6 GB copy. E1 predicts 0.05-0.15 s [guess, plan]
- orin, cold emmc: a copy has to read 7.6 GB. at ~0.29 GB/s (xavier nx emmc, the nearest anchor [external: src 18]) that is 7.6 / 0.294 = 26 s [arith]. a map with `MADV_RANDOM` reads ~10.7K x 4 KB = 44 MB [arith], so the cost becomes emmc random-read latency, [UNCLEAR: orin emmc random 4 KB iops]. with default readahead (128 KB per fault [external: src 5]) it would pull up to 10.7K x 128 KB = 1.4 GB, about 4.7 s at 0.294 GB/s [arith]
- laptop (linux), warm, 2.9-3.8 GB free [repo: plan M6]: the copy needs 7.6 GB of new private memory. it does not fit, so it swaps or dies [guess]. the map needs no new private memory at all

so the same three runs want three different loaders. none of them is the one luna's full-input run wants.

**the exit tax** (freeing the table when the program ends, 3.9-11.4 s on 103GB for stock and s10 [repo: context 2.6]) also depends on the branch. the map branch has no private copy to free; it only drops 27M page-table entries [arith: 111 GB / 4 KB], cost [UNCLEAR]. the copy branch with 2 MB pages frees ~53K pages instead of ~27M [arith: 111 GB / 2 MB = 52.9K]. E1's first run gives S19's real exit number.

### gain per class

| class | warm | cold |
|---|---|---|
| H1 laptop | 8GB db, few reads: runs instead of swapping when free ram < table [guess]. 50MB: ~1x [guess]. under wsl2, keep the db in the wsl ext4 disk, not `/mnt/c` [external: src 16] | 8GB, 10 reads: copy is bounded by the nvme, ~2.1 GB/s seen in the smoke test [measured, smoke only], so ≥ 3.6 s [arith]; map with `MADV_RANDOM` pulls ~44 MB [arith], so [guess] 4-30x |
| H2 orin | E2 already runs `-M` as a variant; the branch just picks it by input size [repo] | emmc: 8GB copy ≈ 26 s [arith on src 18 anchor]; map at 10 reads [guess] 5-25x. orin's 5.10 kernel has no `cachestat` or `MADV_POPULATE_READ`, so probes use `mincore` [repo + external] |
| H3 8 GB box | the 8GB db only runs with the map branch; 16GB and 103GB need idea 3 [guess] | same as H1 |
| H4 luna | few reads on 8GB/16GB/103GB: E1 predicts 3-38x [guess, plan]; stock `-M` already measured 4.17 s at 104,918 reads on 103GB [repo, cross-session caveat above]. full input: stays S19 copy, so never slower than S19 except the probe cost (~ms [guess]) | raid ssd 1.5-8 GB/s [guess, plan], so a 103GB copy is ≥ 111 / 8 = 14 s [arith]. map at 10 reads with `MADV_RANDOM` pulls ~44 MB instead of the ~10.7 GB that 1 MB read-around (`read_ahead_kb` = 1024 [measured]) would pull [arith] |

### days

2 to 3 days for one person, after E1 and E4 give the thresholds. the probes are ~100 lines, the `O_DIRECT` branch ~80 [guess].

### risk

- thresholds are machine-dependent; that is the point, but a wrong default makes one class slower than S19. guard: never pick map for an input bigger than the measured crossover
- `O_DIRECT` needs the file offset, length and buffer aligned to the device block size. the table buffer is 2 MB-aligned (S14). the header in front of the cells is not a multiple of 4 KB [UNCLEAR: header size, believed ~32 bytes]. fix: read from file offset 0 into the aligned buffer and point `table_` at buffer + header size. the cells move 32 bytes inside each cache line, which is speed-neutral [guess]
- `O_DIRECT` makes every run cold. right on H3 (it cannot cache the db anyway), wrong on H4 (the cache is free). so the branch is gated on `MemAvailable` < 2x table
- `-M` on S19 has never been byte-checked [repo]; E1 step 2 does it
- null risk: if E1 shows `-M` ≤ S19 in every small-read cell, the map branches die and only the cold `O_DIRECT` branch is left

### cheapest test that could kill it

E1 as planned (20 min), plus one cold pair from the plan's section 5 protocol: S19 vs S19 `-M` on 16GB, 10 reads, after `dd ... iflag=nocache count=0` eviction. if `-M` ≤ S19 warm in all six small-read big-db cells (E1's own kill rule) **and** cold, the map branches die. for the `O_DIRECT` branch: `dd bs=64M iflag=direct` vs `dd bs=64M` on a cold copy of the same file; if they differ by < 10%, drop it.

### sources

src 5 (128 KB read-around, `MADV_RANDOM`, mmap is fine when the db fits and is read-only), src 6 (io_uring needed only at ~1,000 small requests), src 7 (load-first beat mmap when most of the db is touched), src 14 (`cachestat`), src 15 (fault-around 16 pages), src 16 (wsl2 storage), src 18 (emmc anchor). repo: E1, E4, august `-M` table.

---

## idea 2. huge pages that actually land: `MADV_COLLAPSE` for the copy, huge file mappings for `-M`

**byte-identical.** only the page size behind the same bytes changes, the same argument as S14 [repo: `explanations/09_S14.md`].

### mechanism

**the wrong intuition.** "S14 already gives the table huge pages, and `-M` can never have them." both halves are wrong.
- S14 only *asks*. a huge page (one 2 MB page instead of 512 small 4 KB ones) needs 2 MB of physically contiguous free memory at the moment of the fault. under the default `defrag` setting the kernel tries direct reclaim for madvised regions [external: src 1], and when that fails it silently uses 4 KB pages. on luna that is the measured 12.3-21.6 s spread on 103GB [repo: plan H4]
- `-M` maps page-cache pages, and the page cache can hold 2 MB folios (a folio is the kernel's unit for a group of contiguous pages). then the mapping can use one PMD entry (the page-table level that maps 2 MB at once) instead of 512 PTEs (the 4 KB entries)

**the real mechanism, part A (the copy).** after the S10 load, each loader thread calls `madvise(MADV_COLLAPSE)` on its own 64 MB chunks. `MADV_COLLAPSE` (kernel 6.1+) is synchronous, ignores the sysfs THP settings, and may do direct reclaim and compaction to find the 2 MB blocks [external: src 1, src 2]. so the pages that missed at fault time get a second, stronger try, before classification starts. regions that are already huge cost a check. regions that are not cost a 2 MB copy each.

**part B (`-M`).** three routes, cheapest first:
1. on a filesystem with large folios (xfs; ext4 from 6.15/6.16 [external: src 4, UNCLEAR merge version]), `madvise(MADV_HUGEPAGE)` on the mapping makes the mmap readahead path request PMD-order folios [external: src 3]. cold faults then read 2 MB at a time
2. on any filesystem, `MADV_COLLAPSE` on the file mapping collapses the page cache into 2 MB folios, if the kernel has `CONFIG_READ_ONLY_THP_FOR_FS` [external: src 2]. the page cache keeps them, so every later `-M` run on that boot maps them huge
3. plain `MADV_HUGEPAGE` does **not** work on a read-only data mapping of a regular file: it needs an executable mapping [external: src 2]. this is why the old patch's `MADV_HUGEPAGE` on `-M` was a no-op

**worked example (103GB).**
- page-table size at 4 KB: 27.1M entries x 8 bytes = 217 MB. at 2 MB: 52.9K x 8 bytes = 423 KB [arith]. the second fits in L2, the first does not fit even in luna's 105 MB L3, so every random lookup at 4 KB can also miss on its page walk
- part A on a bad session: S19 measured up to 20.1-21.6 s [repo]. good sessions with full coverage measured 12.3-13.3 s [repo]. if the gap is coverage, and collapsing the missed fraction costs 1-3 s [guess], a bad session lands near 13-16 s: about 1.3-1.5x [arith on the measured range + guess on cost]. a good session gains ~0
- part B on the full input: E1 predicts `-M` at 4 KB loses, 18-30 s vs S19's 13-20 s [guess, plan]. with PMD file mappings, `-M` should match S19's classify time minus its load and exit, [guess] 10-17 s. then the map path wins at every input size, 1x ram, and idea 1 collapses to "always map"

### gain per class

| class | warm | cold |
|---|---|---|
| H1 laptop | wsl2 6.6 and current distro kernels have `MADV_COLLAPSE` [repo + external]; whether `CONFIG_READ_ONLY_THP_FOR_FS` is on is [UNCLEAR]. S14 alone gave -20% on 8GB on luna [repo]; the laptop's tlb sizes are [UNCLEAR] | part B route 1 or 2 makes the cold map read 2 MB at a time instead of 4 KB to 128 KB [external: src 3, src 5] |
| H2 orin | **none**: kernel 5.10 has no `MADV_COLLAPSE` [repo + external]. falls back to S19 behaviour by design | none |
| H3 8 GB box | part B is the best combination for small ram: 1x ram (no private copy) plus 2 MB tlb reach [guess] | as H1 |
| H4 luna | part A: bad sessions 20 s to ~13-16 s on 103GB [arith + guess]; part B: full-input `-M` [guess] 10-17 s instead of 18-30 s | collapse of non-resident pages faults them in first [external: src 2], so on a cold file it behaves like a load |

exit: 52.9K huge pages to free instead of 27.1M small ones [arith], and part B has no private pages at all. E1 measures S19's exit for the first time.

### days

part A 0.5 day (one loop after the S10 load, plus an `AnonHugePages` read from `/proc/self/smaps_rollup` for the log). part B 1 to 1.5 days (collapse on the mapping, `FilePmdMapped` check, fallbacks). total 1.5 to 2.

### risk

- `CONFIG_READ_ONLY_THP_FOR_FS` may be off in ubuntu's 6.8 kernel [UNCLEAR: `grep READ_ONLY_THP /boot/config-$(uname -r)`]. then part B route 2 is dead on luna
- on a shared box, direct reclaim evicts other users' page cache to build 2 MB blocks [external: src 2]. polite default: collapse only when the input is big (idea 1's switch), never for a 10-read run
- collapse cost could exceed the tlb gain on a short run. gate it the same way
- collapsed file folios may be split again under memory pressure [guess]
- null risk: if the 103GB variance is not thp coverage (frequency, numa, other users), part A does nothing

### cheapest test that could kill it

- part A, no code: `grid.sh` already logs `thp_gb` [repo: plan E1]. run S19 103GB 6 times, alternating with s10 runs to fragment memory. if wall does not track `thp_gb`, the variance is not coverage, kill part A
- part B, a 20-line c program on luna: open the 16GB `hash.k2d` read-only, `mmap(PROT_READ, MAP_PRIVATE)`, `madvise(MADV_COLLAPSE)` on the first 1 GB, print the return and `errno`, then read `FilePmdMapped` from `/proc/self/smaps`. `EINVAL` or 0 kB means part B is dead on this kernel. ~15 min

### sources

src 1 (collapse ignores sysfs, defrag default, tmpfs default never, `FilePmdMapped`), src 2 (collapse supports file-backed, needs the config, may reclaim; `MADV_HUGEPAGE` needs an executable file mapping), src 3 (PMD-order readahead for `VM_HUGEPAGE`), src 4 (ext4 large folios), src 15 (fault-around).

---

## idea 3. partitioned out-of-core lookup for dbs bigger than ram

**byte-identical, if the replay is exact.** every lookup still probes the same table cells in the same way; only the order in which the lookups are *resolved* changes, and the per-read decision then runs in the original order. needs a careful equality check, not just a byte compare, during development.

### mechanism

**the wrong intuition.** "if the table does not fit in ram, `-M` lets the kernel page it in, so it just runs a bit slower." it runs thousands of times slower. lookups are random, so with a table k times bigger than the page cache can hold, about (1 - 1/k) of lookups miss the cache and each one becomes a disk read. a disk read is ~100 µs one at a time [external: src 6, "10k IOPS" for synchronous I/O], against ~100 ns for ram. and once the cache is full, eviction itself becomes the wall: in the cidr study mmap fell to near zero, then recovered to about half of fio's random-read rate, with a single cpu-bound `kswapd` doing all eviction [external: src 5].

**the real mechanism.** turn random reads into one sequential read, the way MegIS does in storage [external: src 7] and Metabuli does with a ram cap [external: src 17]:
1. **pass 1, scan.** run the scanner over the reads (or a block of them). for each lookup, compute the slot (S12 already computes it once) and append the slot's offset inside its slice to that slice's temp file. 4 bytes per lookup if a slice is ≤ 2^32 cells (16 GB)
2. **pass 2, resolve.** for slice s = 1..P: read slice s sequentially into ram (2 MB pages), plus a short tail past its end so linear probing can run off the edge (stop at the first empty cell; wrap the last slice to the first). resolve that slice's lookups with the S9/S16 prefetch batches. write one answer per lookup, in arrival order
3. **pass 3, replay.** run the normal `ClassifySequence` again, but its `GetAt` reads the next answer from the answer stream of the slice the slot belongs to. arrival order inside each slice equals pass-1 order, so no sequence numbers are needed

the replay re-runs the scanner (38.5% of cpu on 50MB [measured]), which is the price of keeping the decision code untouched.

**worked example: 8 GB box, 16GB db (16.0 GB), 104,918 reads (355 Mbp [repo: commands_log]).**
- lookups ≈ 355M / 3 = 118M [arith on the density guess]
- with `-M` and ~6 GB of usable page cache [guess], a lookup hits the cache 6 / 16 = 37.5% of the time [arith, uniform access]. the other 62.5%, ~74M lookups, are disk reads. 8 threads of synchronous 4 KB reads at ~10k IOPS each [external: src 6] give ~80K IOPS, so ~925 s [arith]. readahead makes it worse, not better: each miss drags in 128 KB that evicts something else [external: src 5]
- partitioned, P = 4 slices of 4 GB: read 16 GB once at ~2 GB/s (laptop nvme direct read, smoke only [measured]) = 8 s; temp traffic 118M x 4 B = 0.47 GB written and read, answers 118M x 4 B = 0.47 GB [arith]; plus normal classify cpu with the scanner twice. total [guess] 15-25 s, so ~40-60x over the thrash [guess on both ends]

when it is the wrong choice: few reads. 10 reads touch ~10.7K pages, which `-M` reads in well under a second, while a partitioned pass reads all 16 GB. so idea 1's switch picks: few reads → `-M`; many reads and table > `MemAvailable` → partitioned.

### gain per class

| class | gain |
|---|---|
| H1 laptop | with 2.9-3.8 GB free [repo], even the 8GB db is bigger than ram, P = 2-3: [guess] 10x+ on the full input vs `-M` thrash |
| H2 orin | 103GB (111 GB) on 64 GB ram from an external ssd: P = 3 slices of ~37 GB [arith]. turns 4 "not runnable" cells into runnable ones; emmc cannot hold the file at all [repo] |
| H3 8 GB box | 16GB: [guess] 900 s → 15-25 s at 104,918 reads; 103GB: P = 28 slices of 4 GB, one sequential 111 GB read, ~55 s at 2 GB/s [arith] plus classify |
| H4 luna | 0: everything fits |
| cold vs warm | it is a cold, sequential-read design by nature; warm does not apply (the db does not fit) |

### days

8 to 12 days: pass-1 hook in the S16 loop, slice loader with probe tail, answer streams, replay `GetAt`, temp-file handling, 12-mode check. the scale-up to 103GB needs a machine where it does not fit, which luna is not.

### risk

- correctness: probe runs crossing slice edges and the table wrap-around; the replay must consume answers in exactly pass-1 order. mitigation: a debug mode that runs both paths on 50MB and compares every lookup
- temp disk: 4 B per lookup per stream. the full 1,872,777-read input is ~2.0G lookups [arith: 6,036 Mbp / 3], so ~8 GB of slot offsets plus answers [arith]. on a small box, process the input in blocks, at the price of reading the table once per block
- the scanner runs twice: on a cpu-bound box that is up to +38.5% cpu [measured share, applied as a guess]
- prior art: MegIS (in-storage, needs special hardware) and Metabuli (ram-capped, different index) [external: src 7, src 17]. the host-only, byte-identical version for kraken2's own table is the new part [UNCLEAR: not searched exhaustively]
- null risk: if the kernel's page cache copes better than the arithmetic says (high cache hit from read skew), the thrash baseline is much less than 925 s

### cheapest test that could kill it

emulate H3 without new code. on the laptop: wsl2 with `memory=8GB` in `.wslconfig`, run S19 `-M` on the 16GB db with 104,918 reads. or on luna: evict the file first (`dd iflag=nocache count=0`), then `systemd-run --user --scope -p MemoryMax=6G` around the run [UNCLEAR: whether luna delegates the memory controller to user scopes; page cache is charged to the cgroup that faults it in, so the eviction is required]. if the constrained run finishes within ~3x of the unconstrained wall, the page cache copes and the idea is dead.

### sources

src 5 (mmap collapse past ram, single `kswapd`), src 6 (synchronous random I/O ~10k IOPS), src 7 (sorted, sequential access to avoid random ssd reads; 293 GB kraken2 db), src 17 (ram-capped classifier prior art).

---

## idea 4. a compressed db container for slow and cold storage, made from the existing `hash.k2d`

**byte-identical.** decompression gives back the exact bytes. and it needs **no db rebuild**: the container is a lossless transform of the existing file (`k2pack hash.k2d → hash.k2z`), unlike every new table format.

### mechanism

**the wrong intuition.** "the table is random fingerprints, so it cannot be compressed. and compression saves disk, not time." both are wrong for this file.
- 30% of the cells are the zero word (load 0.70, empty = 0 [repo]). the taxon bits are skewed toward common taxa [UNCLEAR: distribution never measured]. only the fingerprint bits are truly random
- when the device reads at 0.29 GB/s [external: src 18 anchor], bytes are time. a cold load is device bandwidth x bytes

**the real mechanism.** cut the table into 64 MB frames, the same chunks S10 already uses, and compress each frame on its own. the loader's threads each read a compressed frame and decompress it straight into the 2 MB-page table. two codecs:
- **zero-cell bitmap**: 1 bit per cell saying "empty or not", then only the nonzero cells. cost per cell = 1 + 32 x 0.70 = 23.4 bits instead of 32, so 1.37x smaller [arith]. decoding is a bit-scan and copy, near memcpy speed [guess]
- **zstd per frame** (a general compressor): might also exploit the taxon skew. on generic data zstd `-1` decompresses at 1,550 MB/s per core [external: src 13]; the ratio on this data is [UNCLEAR]

the ceiling, if the taxon bits had entropy H: 1 + 0.70 x (key bits + H). on 103GB (16 key + 16 value bits), H = 8 [guess] gives 17.8 bits, so 1.8x [arith]. on 50MB (26 key + 6 value bits) the ceiling is ≤ 32 / 23.4 = 1.37x [arith], because there is almost nothing to squeeze out of 6 value bits.

**worked example: orin, cold, 8GB db.**
- today: 7.6 GB / 0.294 GB/s = 26 s [arith on src 18 anchor]
- bitmap container: 7.6 / 1.37 = 5.5 GB, so 19 s [arith]. at a 1.8x zstd ratio [guess]: 4.2 GB, 14 s [arith]
- decode cost: 12 a78 cores at even half the i7's 1,550 MB/s is ~9 GB/s [guess], 30x more than the emmc delivers, so it hides fully
- disk: orin had 8.5 GB free [repo]. 5.5 GB fits with room; 7.6 GB barely does

### gain per class

| class | warm | cold |
|---|---|---|
| H1 laptop | ~0, maybe slightly negative: decode instead of memcpy [guess] | nvme ~2 GB/s [measured, smoke]: decode at 8 cores x 1.55 GB/s ≈ 12 GB/s [arith on src 13] is not the limit, so gain ≈ ratio, [guess] 1.3-1.8x on the load |
| H2 orin | ~0 | emmc: 26 s → 14-19 s on 8GB [arith + guess]; also disk footprint |
| H3 8 GB box | ~0 | ≈ ratio on the load; ram use unchanged (the table is decompressed in ram) |
| H4 luna | ~0 (load is ~6 s from page cache; decode across 32 cores [guess] keeps up) | raid ssd: ≈ ratio on cold runs only, which are rare on luna |
| hdd, network fs | | ≈ ratio, the clearest win: these are bandwidth-bound [guess] |

### days

3 to 4 days: `k2pack` tool, frame index, parallel decode inside the S10 loop, fallback to the plain file, tests.

### risk

- **conflicts with the map path.** `-M` needs the plain bytes on disk. a box that keeps only `hash.k2z` loses idea 1's map branches; keeping both costs 1.7x the disk [arith: 1 + 1/1.37]
- ratio may be only the 1.37x floor; on the 50MB db it cannot be more
- a second file format to maintain (version field, checksum per frame)
- null risk: if the orin cold load turns out cpu-bound, not emmc-bound, there is nothing to win

### cheapest test that could kill it

on luna, 5 minutes, no code: `zstd -1 -T0 -k` on the 8GB `hash.k2d` and on the 50MB one, note the ratio and `zstd -d` speed. the bitmap floor needs no test, it is 1.37x by arithmetic. the real kill comes from E4's orin cold run: if the cold 8GB load is less than ~1.5x the warm load, emmc bandwidth is not the limit and compression has nothing to win.

### sources

src 13 (zstd and lz4 decode speeds), src 18 (emmc anchor). repo: empty cell = 0, load 0.70, cell bit splits.

---

## idea 5. numa placement of the table on multi-node servers: interleave, then per-socket copies

**byte-identical.** placement only, the bytes do not change.

### mechanism

**the wrong intuition.** "lookups are random, so half of them are remote whatever we do. numa placement cannot matter." the average remote share is indeed ~50% for any placement spread over two nodes (a numa node is one socket's cores plus the memory attached to it). but three things still move:
1. **where the table lands is uncontrolled today.** the S10 copy lands wherever the 32 loader threads happened to run (first touch). with `-M`, the page-cache pages sit wherever the *first reader* of the file ran, because page-cache pages "follow task policy, if any, else System Default Policy" [external: src 8]. if that was one `cat` warm-up on socket 0, the whole 111 GB sits behind socket 0's 4 populated channels [repo: plan M2], and socket 1's threads are 100% remote
2. **numa balancing churns.** luna has `numa_balancing=1` [repo], which works by "periodically unmapping pages" and taking hinting faults [external: src 9]. a table read randomly by both sockets has no good home, so this is pure cost [guess]. an explicit policy set with `mbind` turns it off for that range: vmas whose policy lacks `MPOL_F_MOF` "are skipped from NUMA balancing scans" [external: src 11], and interleaved pages are never migrated [external: src 10]
3. **replication makes every lookup local.** one copy per socket, each thread reads its own socket's copy. luna has 503 GB, so 2 x 111 GB fits [arith]

so the code change is: `mbind(MPOL_INTERLEAVE)` on the table before the S10 load (cheap, half the table on each node, scans off), and optionally a per-socket copy.

**worked example (latency-bound lookups, luna).** lookups use 5-11% of dram bandwidth [repo: M4], so they wait on latency, not bandwidth. say a local miss costs L and a remote miss R = 1.6 L [guess; luna's real ratio is UNCLEAR]. spread table: average 0.5 L + 0.5 R = 1.3 L. replicated: 1.0 L. that is up to 1.3x on the lookup-wait part of classify only [arith]. page-table replication (Mitosis, up to 1.34x [external: src 12]) matters at 4 KB pages, where the 103GB page table is 217 MB [arith]; with S14's 2 MB pages it is 423 KB [arith], so S19 mostly does not need it.

### gain per class

| class | gain |
|---|---|
| H1 laptop | 0: one node [guess, single-socket ryzen] |
| H2 orin | 0: one node [repo: `dorado-kraken-research/CLAUDE.md`, "single NUMA node"] |
| H3 8 GB box | 0 for typical one-socket boxes |
| H4 luna and any multi-node box (2-socket xeon, epyc in multi-node modes) | 103GB and 16GB classify at ≥ 64 threads: [guess] 0-15%. it is one of the listed candidates for the unexplained 64-thread plateau [repo: plan section 6]. 50MB: ~0 (it sits in both sockets' L3) |
| cold vs warm | no effect on the disk side; replication doubles the load bytes |

### days

interleave via `mbind`: 0.5 day. replication: 2 to 3 days (per-node allocation and load, per-thread table pointer through the `KeyValueStore` interface).

### risk

- `numactl --interleave=all` already gives interleave with no code; the code version is only worth it as a default, or for replication
- replication doubles ram and load bytes, and on a 66-user box it competes with everyone's page cache
- noise: 103GB runs vary ±4% within a session and 23% across sessions [repo], so it needs interleaved reps
- luna-only evidence; the only H4 we have

### cheapest test that could kill it

no code, ~30 min on luna: S19 on 16GB and 103GB at 64 and 96 threads, three placements interleaved (default, `numactl --interleave=all`, and for 16GB only `--cpunodebind=0 --membind=0` as the "all local" upper bound), 3 reps. read `numa_hint_faults` from `/proc/vmstat` before and after. if interleave vs default differs by < 3% and hint faults are negligible, kill interleave. if the node-0-only run's per-thread rate is no better than the two-socket run's, replication has no headroom either: kill it.

### sources

src 8 (page cache follows task policy, first-touch only), src 9 (numa balancing unmaps pages), src 10 (no migration under interleave), src 11 (explicit-policy vmas skipped from scans), src 12 (page-table replication). repo: M2 channels, M4 bandwidth share, numa_balancing=1.

---

## considered and not proposed

- **io_uring for the load**: 1,776 requests of 64 MB for the whole 103GB table [arith]. io_uring pays off at ~1,000 small requests in flight [external: src 6]. nothing to gain
- **`MAP_POPULATE` with `-M`**: it populates inside the one `mmap` call, on one thread, so it re-serialises the load that S10 parallelised [guess]. idea 1 uses per-thread `MADV_POPULATE_READ` (5.14+) or a parallel touch loop (older kernels) instead
- **hugetlbfs** (reserved huge pages): needs root and a 111 GB reservation on a shared box [repo: plan]
- **SPDK / user-space nvme**: takes the device away from the kernel, root only
- **succinct in-memory tables** (mphf, elias-fano): a1_dsa's area, and they need a rebuild [repo: trie brief]
- **overlap load with the first parse**: ≤ ~0.5 s [guess, plan]

## my ranking, and why

1. **idea 1, the path-picking loader**: every class gains somewhere, it is byte-identical, 2-3 days, and E1 plus one cold pair can kill it within an hour
2. **idea 2, huge pages that land**: 1.5-2 days, byte-identical, fixes luna's 103GB variance and is the only route to a `-M` that also wins on big inputs. dead on orin's 5.10 kernel, which caps it below idea 1
3. **idea 3, out-of-core partitions**: the only idea that makes the 16GB and 103GB dbs usable on 8 GB boxes and the 103GB db on orin. but 8-12 days and the hardest correctness story
4. **idea 4, compressed container**: no rebuild, byte-identical, real on emmc, hdd and network storage, but cold runs only, 1.37-1.8x on the load at best, and it fights the map path
5. **idea 5, numa placement**: H4 only, gain unknown, and the interleave half is already one `numactl` flag

the order flips in one case: if E1 shows `-M` beats S19 even at 1,872,777 reads on luna, idea 2's part B is unnecessary and idea 1 becomes "always map, plus `O_DIRECT` for cold big inputs".
