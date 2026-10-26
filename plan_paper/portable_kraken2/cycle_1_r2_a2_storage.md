# cycle 1, round R2, a2_storage: counters, revisions, ranking (2026-10-26)

agent: a2_storage (db format, compression, mmap vs copy, cold vs warm, readahead, O_DIRECT, huge pages, numa placement, small ram, exit teardown). i read the relay brief and all four other R1 files in full. nothing was run.

---

## sources fetched this round (to check claims)

1. kraken2 v2.18.0-RC1 `src/mmap_file.cc`, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/src/mmap_file.cc
   - the `-M` map is `mmap(0, filesize_, prot_flags, map_flags, fd_, 0)` with `PROT_READ` and `MAP_PRIVATE` for read-only opens. "I don't use MAP_POPULATE to do this because of portability issues". **no `madvise` call anywhere in the file.**
   - its old `LoadFile` page-toucher caps itself: "Don't use more than 4 threads, don't want to hammer disk".
2. kraken2 v2.18.0-RC1 `src/compact_hash.h`, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/src/compact_hash.h
   - copy branch: `posix_memalign(..., 1 << 21, table_bytes)`, `madvise(table_, table_bytes, MADV_HUGEPAGE)` under `#ifdef`, then `pread_parallel(fd, table_, table_bytes, table_off, db_read_threads(), filename)` with default `int n = e ? atoi(e) : 8;` from `K2_DB_READ_THREADS`. no `O_DIRECT`.
   - the header is four `size_t` fields (`capacity_`, `size_`, `key_bits_`, `value_bits_`), so **32 bytes**, then the cells.
   - destructor: `if (! file_backed_) free(table_);`. so the copy path frees the table itself; the map path frees nothing.
3. KrakenUniq on low-memory computers (Pockrandt, Zimin, Salzberg, JOSS 2022), https://pmc.ncbi.nlm.nih.gov/articles/PMC10438097/ (checking a5's S13)
   - `--preload-size` "loads the chunk of the minimizer table and the corresponding chunk of the k-mer table" and "iterates over all of the reads provided as input". this repeats per chunk. "Classification results will be identical to running in the default mode."
   - 392 GB db, 9.4M reads: memory mapping 48 h; full `--preload` 14 min; 8G chunks (49) 47 min; 16G (25) 32 min; 32G (13) 25 min; 64G (7) 19 min. chunking "adds overhead because of the need to iterate over the reads multiple times". no hardware stated, and the thread count conflicts (caption 8, command 24).
4. web search, "jetson orin L4T transparent_hugepage default": **nothing jetson-specific found.** so orin's thp mode stays [UNCLEAR] (conflict 3).

R1 sources reused below keep their R1 numbers (`cycle_1_r1_a2_storage.md`, "src N").

---

## 0. three findings that move my area (read first)

**0.1 conflict 1 is mostly settled by numbers already in the repo: uncapped dbs do about 1 lookup per 3 bases; capped dbs skip most lookups.**
- the wrong intuition: "a5's gprof count, 1 lookup per 36 bases, is the only real measurement, so trust it over the 1/3 guess."
- the check: stock at 1 thread on 103GB classifies 6,036 Mbp in 981.73 s [measured: sweep], so **162.6 ns per base** [arith]. stock never prefetches, so each lookup waits a full dram trip plus a 4 KB page walk. spr dram latency is 107-109 ns unloaded [external, via a4 src 7, 8].
- the non-lookup work per base, from a db that sits in L3: stock 50MB at 1 thread, 20.01 s for ~355 Mbp [repo: `dorado-kraken-research/Luna/experiments/patch/commands_log.md` line 643, `reads_hac`], so **~56 ns per base** including its cheap L3 lookups [arith].
- so ~107 ns per base on 103GB is lookup waiting [arith: 162.6 - 56]. the two numbers come from different sessions (august, pinned to node 0, vs the october sweep), so this is an order-of-magnitude check only.
  - at 1/36 lookups per base, each lookup would cost 107 x 36 ≈ 3.9 µs. that is 35x a dram miss. it cannot be.
  - at 1/3, each costs ~320 ns: one dram miss plus a page walk that also misses. that fits [arith + guess on the walk].
- so on the uncapped 103GB db, ~1/3 holds to within a small factor [arith on measured]. the gprof run was a different, old build on `eskape_650mb` [repo], so it does not transfer.
- **the capped dbs are the real exception.** stock 8GB at 1 thread is 16.48 s on the same input [repo: commands_log line 671]. about 3.7 s of that is load [repo: same file, line 676], so ~12.8 s of classify, ~36 ns per base [arith]. that is *below* 50MB's 56 ns. so the 8GB db does far fewer lookups (and less hit counting) than 50MB. this is a4's suspicion (`minimum_acceptable_hash_value`) in numbers.
- what changes: every touched-fraction and spill estimate needs **L = bases x d x f**. d ≈ 1/3 [arith-supported guess]. f = the kept fraction of hash space = 1 - `minimum_acceptable_hash_value` / 2^64, read from `opts.k2d` at startup, exactly. classify skips a minimizer whose hash is below that value [external, via a1 src 2]. for our 8GB and 16GB dbs, f is [UNCLEAR] but small by the arithmetic above.

**0.2 S10's edge over RC1 is a default, not code.** RC1 loads with `pread_parallel` and `K2_DB_READ_THREADS`, default 8 [external: src 2 above]. S10 uses `min(omp_get_max_threads(), 32)` [repo]. set `K2_DB_READ_THREADS=32` and RC1's loader is S10 + S14 [external + repo]. so a5's "RC1's load is up to ~4x S19's" [repo: a5 B1] is a question about one env var:
- the gap is at most the drop from 8 to 32 streams on S19's own E4 loader curve
- luna's per-thread load rate already falls ~3.5x by 32 threads [arith, a4 section A3], so the gap is likely well under 4x [guess]
- the storage contribution left for us vs upstream is the planner (M9), the huge-page fallback (M10), the thread-order fix, and anything cold. not S10 itself.

**0.3 M11 has exact prior art.** KrakenUniq's `--preload-size` already classifies against one chunk at a time with "identical" results [external: src 3 above]. a5 found it; i checked it. so M11's novelty is low. what is still new: scanning the reads **once** instead of once per chunk. KrakenUniq's 49 chunks cost 47 min against 14 min for a full preload [external], ~33 min for 48 extra passes over 9.4M reads [arith]. that overhead is exactly what a scan-once design removes.

---

## 1. counters to the other four agents' top 3

### a1_dsa

**M3 (a1 i1): prefetch only changed minimizers.**
- what breaks: nothing, if `prev_min` mirrors `last_minimizer` [repo: a1]. agreed.
- class it hurts: none.
- cheaper: free if the base moves to RC1, which already pushes a key only on a change (`TOK_REPEAT`) [external, via a1 src 2 and a5 S4]. so M3 is a cost only while S19 stays the base.
- evidence: the **cap-skip half is probably the bigger half on 8GB and 16GB**. section 0.1 says those dbs skip most lookups, and S19's `fill()` still prefetches a line for every skipped one [repo: a1, `s16_patch.py` lines 48-50]. on a capped db with kept fraction f, (1 - f) of S19's prefetches fetch lines nobody reads [arith]. on a one-channel laptop that is wasted bandwidth. storage side: under `-M`, a prefetch to a page that is not resident does not fault in the page [guess: software prefetches are hints], so it adds no disk reads.

**M8 (a1 i2): line-aware probe.**
- what breaks: part a, nothing. part b needs the scalar edge paths a1 lists.
- correction for the `-M` case: the cells start **32 bytes** into the file [external: src 2 above, four `size_t`], so a mapped table's lines start 8 cells off. the average crossing rate does not change [arith], but part b's aligned vector load must handle it. the copy path is aligned (`posix_memalign` 2 MB).
- class it hurts: none. the +37.5% line fetches are about 48 GB over the full input [arith: a1], small even on one channel.
- cheaper: part a alone (0.25 day) after the `perf annotate` kill test. part b only if part a shows the crossing matters.
- evidence: the 7% / 32% crossing rates assume a run starts at a uniform offset in its line [repo: trie brief]. holds for hashed slots.

**M11 (a1 i3): sorted block lookup.**
- what breaks: two costs, not correctness.
  - 16-byte records are 4x what is needed. a slot offset inside a slice of ≤ 2^32 cells fits in 4 bytes, and arrival order can replace the back-reference (my R1 design) [arith]
  - a fixed 3 GB record buffer forces one full table sweep per read block: a1's own H3 example is 11 sweeps x 15 GB = 165 GB [arith: a1]. one sweep with spilled 4-byte queues moves ~47 GB (section 2.2) [arith]
  - a1's optional dedupe needs a sort, which destroys arrival order, so it needs the 16-byte back-references back. drop it, or keep it in-ram only
- class it hurts: H3 and H1 full inputs pay the extra sweeps.
- evidence: the merge-join idea is sound and has prior art (Metabuli, MegIS [external via a1], KrakenUniq [external: src 3]). "using kraken2's hash order as the sort key looks new": the slot order is the natural order of the existing table, so no sort is needed at all, only a radix partition by slice. a1 says this too.

### a3_cpu

**M3 (a3 i1):** same as above. one more point: a3's 4.7% assumes every position costs a full `PrefetchIndex` [repo: a3]. on capped dbs the saved work is partly ram trips, not only instructions, so the 8GB/16GB gain could be larger than a3's 0-2% for big dbs [guess].

**M4 (a3 i2): branch-free min-of-5 scanner.**
- storage lens: no storage effect.
- evidence point a3 can use: section 0.1 says capped dbs do few lookups, so the scanner is a **larger** share of the 8GB and 16GB runs than of 50MB. a3's 8GB/16GB range (3-15%) may be low [guess].
- what breaks if M2 happens: RC1's `mmscanner.cc` differs (vector window, non-rolling revcomp) [external, via a5 S4]. M4 must be specified against the base we pick.

**M5 (a3 i3): fast or parallel gz decompression.**
- this is a storage lever on the input side, and it is bigger than a3 says on slow storage. on orin, the plain 12.5 GB input alone takes 31-50 s at 0.25-0.4 GB/s [arith; conflict 2 bounds]. that is more than the 8GB db's 19-30 s cold load [arith]. **for big inputs on slow storage, input bytes dominate db bytes.** so M5 should rank above M13 (my compressed db).
- what breaks: nothing; gzip is lossless.
- evidence: the 158-170 MB/s gzip rate comes from rapidgzip's 55x and 33x ratios on base64 and silesia data [external, via a3 S8], not on fastq [UNCLEAR for fastq]. a3's 10-minute kill test settles it.
- cheaper: step a (the wrapper picks rapidgzip / igzip / pigz, per-file detection) is 0.5 day. do it first.

### a4_hw

**M9 (a4 i1): cold-start load planner.** merged with my R1 idea 1, see section 2.1. counters to a4's version:
- its lookups-per-read (1,070) assumes f = 1. on capped dbs the map-vs-copy crossover moves up by 1/f. worked example: a4's emmc crossover for 8GB is ~345 reads [arith: a4]. at f = 0.1 [guess] it becomes ~3,440 reads [arith: 368K lookups / 107 per read].
- its copy branch on an hdd at 150 MB/s assumes one stream. S10's 32 streams on an hdd may lose ~3x to seeks [guess: a4 i2]. so the path and the stream count must be chosen together. that is why M17 belongs inside M9.
- "not even 1x fits, stop with advice" should route to M11 once M11 exists.
- agree with a4's two additions to my version: the cgroup `memory.max` in the fit check (`MemAvailable` shows the host, not the job [guess: a4]), and printing the plan to stderr.

**M18 (a4 i3): online thread controller.**
- what breaks: its windows measure the disk, not the cpu, while a cold or partly cached run is still faulting pages in. on a cold `-M` run, more threads means more faults in flight, so it would climb for the wrong reason. start the windows only after the load ends (copy path) or after residency passes ~95% (map path) [guess threshold].
- class it hurts: H2 cold, any cold `-M` run.
- evidence: the 13-14% spread is measured on s0/s10 with 4 KB pages [measured]. S19 with 2 MB pages may not show it. E5 decides first.
- cheaper: a static default from E5 (M20 plus "physical cores; one socket if the db fits one node") may capture most of it.

**M17 (a4 i2): loader thread plan.** fold it into M9 (same probes, same decision). keep the one-line fix, `omp_set_num_threads` before the load, as a separate upstream patch: RC1 has the same order [external, via a5 S4]. evidence that the worry is real: the PR author worried about "NFS or large spinning disks" [external, via a5 S3], and upstream's own old `LoadFile` caps itself at 4 threads to not "hammer disk" [external: src 1 above]. but no hdd number exists anywhere [UNCLEAR].

### a5_skeptic

**M1 (a5 B1): re-baseline vs RC1.** agree it is first. add four storage riders, all free in the same session:
- RC1 at `K2_DB_READ_THREADS` = 8 and = 32. this splits "S10's edge" from everything else (section 0.2)
- RC1 with `-M`. its map path is v2.17.1's, untouched [external: src 1 above], so this is also the RC1 version of E1
- the exit column for every run. RC1 frees the copy with `free(table_)` [external: src 2 above] and fixed a double free at exit [external, via a5 S1]
- `thp_gb` per run, which is also M10 part A's kill test
- counter to a5's worked example: "up to ~4x" is one env var, see section 0.2.

**M2 (a5 B2): residual stages onto RC1, upstream.** agree. storage pieces that fit the same upstream pull request, each small and byte-identical: the thread-order fix, the `MADV_COLLAPSE` fallback (M10 part A), a device-aware `K2_DB_READ_THREADS` default (M9/M17), and `MADV_RANDOM` on the `-M` map for cold few-read runs. also: **build M11 on RC1**, because RC1 already has the scan / resolve / replay shape [external, via a5 S4], so the replay phase is existing code.

**M12 (a5 B3): small-ram emulation.** agree it is the gate for M11. sharpen it, section 2.3.

**a5's B5 (M13), and two attributions to me.**
- B5's kill rule "kill if zstd is under 1.3x" is wrong. a trivial zero-cell bitmap codec gives 1.37x by arithmetic on any table at load 0.70, whatever zstd does (section 2.4). the real kill is whether cold storage is the bottleneck anywhere we care.
- A6 lists a2 under "lift the 32-thread cap". i did not propose that. my R1 idea 1 picks streams by device: 1-2 on an hdd, 2-4 on emmc, 8-32 on nvme [repo: `cycle_1_r1_a2_storage.md`].
- A4 ("`-M` is the small-ram answer") is right, and my R1 idea 3 says the same: `-M` collapses once the table is bigger than the free page cache. KrakenUniq's 48 h for memory mapping on a 392 GB db [external: src 3 above] is the strongest number for it.

### M-ids i think are ranked wrong by their owners

- **M13 (mine, and a5 B5) is ranked too high by me in R1** for slow storage. M5 (input gz) beats it there (a3 counter above).
- **M6 (out-of-lock parser)**: drop from every build list. upstream has it, and it comes with M2.
- **M16 (miss prefilter)**: a1 ranked it 5th, fine. storage note: b-full for big dbs is gigabytes (16GB: ~3.4 GB [arith: a1]) that must also be loaded, so it adds cold-load bytes on exactly the class (H3) that cannot afford them.
- **M15 (lower-density sampling)**: its best argument is a storage one. ~32% smaller dbs [arith: a1] can turn "does not fit" into "fits" on H3 (8GB to ~5.2 GB). it needs a rebuild and an accuracy check, so it stays thesis-side, but it is the only idea that changes fit without M11's complexity.

---

## 2. merges and designs in my area

### 2.1 M9 = a2 idea 1 + a4 idea 1 + a4 idea 2 (M17 folded in)

one planner, run once at startup, with two outputs: **how** the table gets into memory, and **how many streams** read it.

**probes** (each costs microseconds to ms, no root):

| probe | how | kernel | from |
|---|---|---|---|
| input bases | `stat` sizes; fastq is ~2 bytes per base [arith: a5] | any | a2 |
| kept fraction f | `opts.k2d`'s `minimum_acceptable_hash_value` | any | new (section 0.1) |
| residency r | `cachestat` (6.5+) else `mincore` on an unread map | `mincore` any | a2, a4 |
| fit | `MemAvailable` and cgroup `memory.max` | any | a2 + a4 |
| device | `/sys/block/<dev>/queue/rotational`, device name (nvme, mmcblk, sd); no block device means network fs | any | a2, a4 |
| features | `MADV_POPULATE_READ` 5.14+, `MADV_COLLAPSE` 6.1+; probe by calling them and checking `EINVAL` | | a2 |

**the cost model** (a4's, with f added):
- lookups L = bases x d x f, d ≈ 1/3 [arith-supported guess, section 0.1]
- touched pages = P x (1 - e^(-L/P)), P = table bytes / 4 KB [repo: plan E1]
- cold copy = (1 - r) x table bytes / sequential rate(device, streams)
- cold map + `MADV_RANDOM` = (1 - r) x touched pages / random iops(device, threads)
- warm: E1's measured crossover per db [repo: E1, not run]

**the decision:**

| case | path | streams |
|---|---|---|
| warm, reads below the E1 crossover | `-M`, lazy, default readahead | n/a |
| warm, above it, fits 2x | copy (RC1 / S19 loader), then `MADV_COLLAPSE` (M10 A) | warm knee (E4) |
| cold, map cheaper by the model | `-M` + `MADV_RANDOM` | n/a, threads set the queue depth |
| cold, copy cheaper, fits 2x | buffered copy, leaves the cache warm for the next run | hdd 1, emmc 2-4, nvme 8-32, network fs 8 [guess] |
| cold, copy cheaper, fits 1x only | `O_DIRECT` copy into the 2 MB-aligned buffer, no second copy in the cache | same |
| unknown device or network fs, many reads | a4's 1b: map, plus one thread streaming the file into the cache | 1 background |
| does not fit 1x | M11 if built, else print the expected major-fault count and stop | |

`O_DIRECT` detail, now checked: the header is 32 bytes [external: src 2 above]. read from file offset 0 into the aligned buffer, and set `table_` = buffer + 32. the cells then sit 32 bytes into each line, like the `-M` layout (a1's part b scalar fallback covers that).

**the thread-order fix** goes in too: call `omp_set_num_threads` before the load, so `--threads` bounds the loader on shared boxes [repo: context fact 5; RC1 same, external via a5].

**gain per class**: unchanged from my R1 and a4's R1 tables, with one correction. on capped dbs the map branch wins up to ~1/f times more reads [arith]. orin with thp `always` (conflict 3) would shift the *warm* crossover toward copy, because then the copy gets 2 MB pages and the map stays at 4 KB [guess].

**days**: 3-4 for both merged, after E1 and E4.

### 2.2 M11: which of the three designs is right

| | a1 i3 | a2 R1 idea 3 | a5 B4 |
|---|---|---|---|
| record | 16 B (hash + back-ref) | 4 B in-slice offset, order is the reference | 12 B (hash or slot + taxon) |
| table sweeps | one per read block (3 GB buffer) | one | one per read batch |
| replay | scatter results back, then unchanged per-read logic | re-run scanner + classify, `GetAt` pops the next answer from its slice's queue | RC1's phase 3 |
| scanner runs | 1 | 2 | 1 |
| probe tail | read past b to the first empty cell | same | "must cover the longest run" [UNCLEAR] |

**what is right in each:**
- a1 is right that the tail is local: read cells past b until the first empty one. a linear probe always stops there [external, via a1 src 3]. a5's "longest run in the table" is not needed; each slice finds its own tail at load time.
- a5 is right that RC1's three phases give the replay for free [external, via a5 S4].
- mine is right that order can replace the back-reference: lookups enter each slice's queue in arrival order, and the replay asks for them in the same order, so a 4-byte offset is enough [arith].

**the merged design:**
1. one sweep of the table, always: P slices of at most `memory budget / 2`
2. per read block, RC1 phase 1 makes tokens. each real lookup (changed, not ambiguous, not below the cap) appends its 4-byte in-slice offset to its slice's queue
3. queues stay in ram if they fit the budget, else they spill to disk as sequential appends
4. per slice: read it once (2 MB pages), plus its tail. resolve its queue in order with the prefetch batches. append answers in order (2 or 4 bytes, by value bits)
5. replay: if the block's tokens are still in ram (small inputs), run RC1's phase 3 on them. if not (big inputs), re-scan the reads, and each lookup pops the next answer from its slice's answer queue
6. `--quick` falls back to the normal path, because an early exit leaves answers unpopped in each queue

**worked example: H3 (8 GB ram), 16GB db (15 GB [repo]), nvme ~2 GB/s [measured, laptop smoke], full input, worst case f = 1:**
- lookups ≈ 2.0G [arith: 6,036 Mbp / 3]
- a1: 11 sweeps x 15 GB = 165 GB read, ~83 s of table i/o [arith: a1]
- merged: table 15 GB once, queues 2.0G x 4 B = 8 GB written and read, answers ~8 GB written and read: 15 + 16 + 16 = 47 GB, ~24 s [arith]. plus the second scanner pass, ~90 core-s at luna's 14.9 ns per base [arith: a3 section 1], 11-23 s on 4-8 cores [arith; small-box cores differ]
- so ~35-47 s of overhead against ~83 s [arith]. at 104,918 reads everything fits in one block, so a1's and the merged design are the same thing: one sweep, no re-scan
- if f is small, as section 0.1 suggests for this db, every queue term shrinks by f [arith]

**days**: 6-8 on RC1, since the phases exist. prior art: KrakenUniq (identical output, re-scans per chunk) [external: src 3 above], Kun-peng (4 GB blocks, identity not claimed vs kraken2) [external, via a5 S14], Metabuli, MegIS [external]. the new part is scanning once, on kraken2's own table.

### 2.3 M12 as the gate for M11, sharpened

a5's B3 design is right. four additions:
1. **evict first, always.** a page is charged to the cgroup that first brought it in [external, via a5 S16]. luna's db files are already in the global cache, so a capped run on a warm file is not a small-ram run.
2. **run the map variants that M9 would pick**: S19 `-M`, S19 `-M` + a one-line `MADV_RANDOM`, RC1 `-M`, and the copy path (whose OOM or swap is itself the H3 answer for copying).
3. **read it asymmetrically.** luna's raid plus controller cache make a major fault cheaper than on a laptop ssd [guess: a5]. so "thrashes on luna" proves M11 is needed, but "survives on luna" does not prove an 8 GB laptop survives. a pass on luna must be repeated on the laptop (wsl2 with a memory cap [UNCLEAR: exact `.wslconfig` key not fetched]) before M11 is killed.
4. **use f.** read the 16GB db's `minimum_acceptable_hash_value` first. if f is small (section 0.1), the full input touches few distinct pages, so it may survive an 8G cap even though the file is 15 GB. an uncapped db of the same size would not. we have no uncapped db between 50MB and 103GB, so the gate cannot test the uncapped case directly. a tighter cap on a smaller db (8GB db under 4G) is the closest stand-in [guess].

kill rule (a5's, kept): if `-M` under an 8G cap stays within ~2x of uncapped warm **on the laptop as well as on luna**, kill M11.

### 2.4 M13: compressibility, and the kill rule

two bounds, both [arith]:
- **floor** (zero-cell bitmap, no entropy coding): cell bits / (1 + α x cell bits). at α = 0.70: 32-bit cells 1.37x, and RC1's 40-bit cells [external, via a5 S1] 1.38x. the floor depends on the load factor, not the data, so **any** table at 0.70 compresses at least ~1.37x
- **a5's entropy bound**: H(0.30) + 0.70 x (key bits + value entropy) per cell. 103GB 1.7-2.0x, 50MB 1.5-1.6x [arith: a5, on a guessed value entropy]
- a5's occupancy term H(0.30) = 0.88 bits treats cells as independent. linear probing clusters filled cells into runs, so the real occupancy entropy is lower [guess on how much]. the bound is not a ceiling.

so the zstd test cannot kill M13. it only picks the codec: zstd frames if zstd beats ~1.6x, else the bitmap. the kill is elsewhere:
1. is cold storage the bottleneck? orin `dd iflag=direct` (conflict 2). above ~1.5 GB/s, kill for H2 [repo: a5 rule]
2. M5 first: input bytes dominate on slow storage for big inputs (a3 counter)

the conflict with `-M` (a compressed file cannot be mapped [repo: a5, mine]) has a workaround for boxes that run many jobs per boot: decompress once into `/dev/shm` (world-writable tmpfs, no root), then map that copy. ram cost is 1x, like the page cache. caveats: tmpfs pages are swap-backed, not droppable, so on H3 they push other memory to swap [guess]; and tmpfs defaults to `huge=never` [external: R1 src 1], so 4 KB pages.

days: test 0.1, build 3-4. it stays near the bottom of my list.

---

## 3. the number conflicts

1. **lookups per base**: settled to an order of magnitude, section 0.1. uncapped: ~1/3 [arith on measured 1-thread times]. capped: d x f, f from `opts.k2d`, small for our 8GB [arith, rough]. one counter in a throwaway tree gives the exact d (a5 A7, 15 min). reading `opts.k2d` gives f (a1, 5 min).
2. **orin cold read**: the 2.6 GB/s "cold" run [repo: a5 A5] is above emmc hs400's 400 MB/s ceiling [external, via a4 src 3], so it was cached. agree with a4 and a5. planning range: 0.25-0.29 GB/s class [external: a4 src 3, my R1 src 18], hard ceiling 0.4 GB/s. it stays [UNCLEAR] on our board until `dd iflag=direct` (2 min).
3. **orin thp mode**: [UNCLEAR]. no jetson source found (src 4 above). for my ideas: if `always`, S14 buys nothing on orin, the copy path already has 2 MB pages, and M9's warm crossover moves toward copy (2.1). M10 is unaffected either way: orin's 5.10 kernel has no `MADV_COLLAPSE` [repo + external]. settle with E2 step 1 plus `AnonHugePages` during one stock run.
4. **M3's gain**: not my area. section 0.1 adds that on capped dbs part of M3's saving is ram trips, not instructions.

---

## 4. my own revisions after v2.17.2 / RC1

- **M9**: build it on RC1 (or on M2's s22). the stream rule becomes "set `K2_DB_READ_THREADS` from the device class", a small upstream patch. RC1's map path has no hints at all [external: src 1 above], so `MADV_RANDOM` for cold few-read runs is a clean addition there too. upstream's cold Graviton4 win (~100 s to 34 s, 8 streams, cloud block storage [external, via a5 S3]) supports "network block storage wants many streams".
- **M10 part A** applies to RC1 unchanged: RC1 also depends on `MADV_HUGEPAGE` at fault time [external: src 2 above], so it has the same fallback risk as S14. upstreamable. **part B**: no change, the map path is untouched upstream. upstream says huge pages matter most on aarch64 [external, via a5 S3], but orin's 5.10 kernel cannot use `MADV_COLLAPSE`, so part B helps newer-kernel arm boxes (graviton), not our jetson.
- **M11**: merged design (2.2), built on RC1's phases. novelty down (KrakenUniq). gate M12.
- **M13**: kill rule changed (2.4). ranked below M5.
- **M14**: a4's three-case policy is a superset of mine. my two additions stand: an explicit `mbind` policy takes the table out of numa-balancing scans [external: R1 src 11], and under `-M` the placement is set by whoever first read the file into the cache [external: R1 src 8]. so a cheap no-code trick: warm the cache with `numactl --interleave=all cat hash.k2d > /dev/null` before `-M` runs on a 2-socket box. still H4 only, so it falls out of my top 10.
- **exit tax**: RC1's copy path frees with `free(table_)`, the map path frees nothing [external: src 2 above]. so E1's exit column for S19 and RC1 `-M` measures both teardown kinds in one session.

---

## 5. my ranking

### 5a. top 10 build list

| rank | id | one-line reason |
|---|---|---|
| 1 | M2 | the binary everyone installs. the residual stages are pure instruction savings, and M3 and M6 come free with the RC1 base |
| 2 | M9 (with M17 folded in, plus the thread-order fix) | byte-identical. on cold or small-ram runs it gives [guess] 3-30x (R1 tables); warm, it never does worse than the copy path. touches every class |
| 3 | M20 | default threads = physical cores. trivial, every class, large for real users who forget `--threads` [guess: a3] |
| 4 | M10 (part A first, B only if its 15-min test passes) | removes the 12.3-21.6 s 103GB spread [repo] on any kernel ≥ 6.1, and part B is the only route to a map that also wins at full input |
| 5 | M4 | every isa; the scanner is the biggest cpu share, larger still on capped dbs (0.1) |
| 6 | M5 | the biggest cold-storage lever when inputs are big or gzipped; step a is 0.5 day |
| 7 | M11 (merged design, gated by M12) | the only way the 16GB-class and 103GB dbs run at device speed on 8 GB boxes and on orin |
| 8 | M8 part a | 0.25 day; helps the classes where every db misses the last-level cache (H1, H2) |
| 9 | M21 | portable binaries instead of `-march=native` |
| 10 | M13 (gated by orin `dd` and M5) | cold slow storage only, ≥ 1.37x on the load by arithmetic, fights the map path |

just outside: M14 (H4 only), M18 (E5 decides), M19 (E2 step 6 decides), M16 (one niche class), M15 (rebuild plus accuracy), M7 (after M4). M3 is rank 2 instead of nothing if the team stays on S19 and rejects M2.

### 5b. top 5 measure-first

| rank | measurement | one-line reason |
|---|---|---|
| 1 | M1, with the four storage riders (RC1 at 8 and 32 read streams, RC1 `-M`, exit column, `thp_gb`) | resets every ratio, isolates S10's edge as an env var, and gives M10 A's kill test for free |
| 2 | E1 plus one cold pair (S19 `-M` vs copy, 16GB, 10 reads, after eviction, with and without `MADV_RANDOM`) | decides whether M9's map branches live |
| 3 | orin state probe: `dd iflag=direct` on the emmc, thp mode, `AnonHugePages` during a stock run, kernel config | settles conflicts 2 and 3; decides M9's and M13's H2 cells |
| 4 | M12, sharpened (2.3) | the gate for M11 |
| 5 | lookup counter plus `opts.k2d` `minimum_acceptable_hash_value` for every db | settles conflict 1 exactly; feeds M3, M8, M9, M11. 20 min, can ride along with rank 1 |

**my single strongest counter**: a5's 1 lookup per 36 bases cannot hold for the uncapped 103GB db. stock at 1 thread spends 162.6 ns per base there against ~56 ns on the L3-resident 50MB db [arith on measured]. at 1/36, each lookup would cost ~3.9 µs, 35x a dram miss. at ~1/3 it costs ~320 ns, one miss plus a page walk. the capped 8GB db is the real exception: it does fewer lookups than 50MB, which the kept fraction f in `opts.k2d` explains. every touched-fraction estimate (M3, M8, M9, M11) should use L = bases x 1/3 x f.
