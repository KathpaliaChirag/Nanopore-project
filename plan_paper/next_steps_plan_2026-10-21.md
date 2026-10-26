# next steps after S19: what to measure, in what order, and why (2026-10-21)

this plan picks the next kraken2 speedup experiments and spells out how to run them, one command at a time. it is for ck to review before anything runs. it starts by checking every claim in `opus_prompt_next_steps_2026-10-21.md` section 3 against the repo and against read-only looks at luna, because three of those claims change what the experiments have to measure. nothing was run on luna or orin except reading files, `perf report` on an already-saved profile, `fincore` and `free`. the laptop ran one smoke test of a new script.

evidence tags: **[repo]** a file in this repo, **[measured]** read today from luna, the laptop or a run log, **[guess]** my estimate, **[external]** outside knowledge, not checked here.

---

## 1. five things that changed while checking (read this first)

each of these changes an experiment further down, so they come before the claim table.

**1. the S10 loader never sees `--threads`.** the natural reading of the sweep is "at 1 thread the parallel loader runs on 1 thread". it does not. `classify.cc:260` builds the hash table, and `classify.cc:273` calls `omp_set_num_threads(opts.num_threads)` only afterwards [measured: grep of luna's S19 tree]. so inside the loader `omp_get_max_threads()` returns the machine default (192 on luna), and the cap turns that into 32 every time. the finished sweep agrees. load is 56.2-58.5 s for stock and 5.7-6.5 s for s10 at every thread count from 1 to 192 [measured]. two consequences:
- the 1-thread 1.53x (1,046.04 s to 685.43 s) splits into 49.9 s from the 32-thread loader, 309.7 s from classification (S8 + S9) and 1.1 s from exit [measured]
- the sweep measured classify scaling only. to sweep the loader itself, set `OMP_NUM_THREADS`. it sets the default the loader reads, and `--threads` still sets classify [external: openmp ICV semantics]

**2. wall minus "processed in" is load plus exit, not load.** after kraken2 prints its last line, the process still has to tear down a 111 GB table. that exit cost 3.9-11.4 s in every stock and s10 103GB run. at 32 threads it is 17% of s10's 26.4 s wall [measured]. the likely cause is the kernel freeing ~27M 4KB pages [guess]. S19's huge pages probably shrink it, because S19 at 10 reads on 103GB is 3.79 s in total, which leaves no room for a 4.5 s exit [repo + inference].

**3. an s20 already exists, and it is a null.** `~/tools/kraken2-src-s20` (2026-10-07) changes one line: the default prefetch batch `K2_B` goes from 16 to 64. its source comment says "measured faster everywhere". its own log, `s20_vs.log`, shows all 4 dbs within ±0.6% over 3 interleaved reps [measured]. it is not in `explanations/`. new trees in this plan are named s21a, s21b..., so nobody reads them as s20 variants.

**4. the cpu profile has moved since the brief.** S19 on 50MB at 32 threads (`perf_s19.data`, 2026-10-07): `NextMinimizer` 38.5%, `ClassifySequence` 25.1%, `GetAt` 12.5%, `PrefetchIndex` 7.0%, memmove 3.1%, `AddHitlistString` 2.1%. the `unordered_map` that S15 targeted is now below 0.8% [measured]. that has three consequences:
- "scanner ~25%" is stale
- the flat hit-count array lever is dead, by the brief's own "under 2%" rule
- the saved `NextMinimizer` annotate is flat, with the top instruction at 3.9%. its prologue and epilogue (push, sub, ret, paid once per base) are about 9% of it [measured: `ann_next.txt`]. that points at inlining across files (LTO), not another S18-style stall

**5. the machines are tighter than the spec's table says.**
- luna has 4 of 8 memory channels populated per socket: one dimm on channel 0 of each of the 4 memory controllers [measured: edac sysfs labels]
- the laptop's single dimm sits in "P0 CHANNEL B" as expected, but only 2.9-3.8 GB of ram was free while checking [measured]
- orin had 8.5 GB free on its emmc in june [repo: `Orion.md`], so the 12.5 GB 1.87M-read input cannot be copied there. orin's installed kraken2 is v2.1.3, not v2.17.1 [repo]

**two build traps** sit under every new tree:
- `install_kraken2.sh` runs `make -C src install` with no `make clean` [measured]. a tree copied with `cp -a` that only changes a Makefile flag relinks the old objects, which gives a fake null
- Makefile line 4 sets `-DLINEAR_PROBING` [measured]. overriding `CXXFLAGS` on the make command line drops it. that silently switches the probe order away from the one the dbs were built with, and the output goes wrong

what this means in practice: every experiment below logs load, classify and exit separately, sweeps the loader with `OMP_NUM_THREADS`, names trees s21*, edits the Makefile with `sed` instead of overriding it, and runs `make clean`.

---

## 2. claim check (spec sections 1 to 3)

this section exists so nothing reaches sir on a claim nobody checked. verdicts: holds / partly / wrong / unverified.

| # | claim | verdict | what the evidence says | tag |
|---|---|---|---|---|
| H1 | S19 is 1.8x to 4.4x faster at 1.87M reads | partly | 1.8-4.4x is the **S15** matrix. S19's own matrix is 1.9x (50MB) to 4.8x (103GB), one run per cell | [repo] report lines 13-28 vs 98-115 |
| H2 | 10-17x at small read counts | partly | true for 8GB/16GB/103GB at 10 and 1,000 reads (S19: 9.8x-15.4x). 50MB at small counts is 1.3x-1.6x, 104,918 reads give 5.3x-12.7x | [repo] |
| H3 | byte-identical in all 16 cells | holds | matrix verdicts, output and report sorted and compared | [repo] |
| H4 | thp variance 13 to 21 s on 103GB | holds, and wider across sessions | 12.3 s (transplant doc, 3 reps), 16.55-16.79 s (`s20_vs.log`, 3 reps), 20.08 s and 21.58 s (matrices) | [repo], [measured] |
| M1 | luna 2x 8468, 192 threads, interleaved node ids, 210 MB L3 | holds | also: SMT siblings are cpu N and N+96, L3 is 105 MB per socket | [measured] `lscpu -e`, command log P.1 |
| M2 | 8x 64 GB ddr5-4800, at most 4 channels per socket, split not verified | now verified | 4 dimms per socket, 1 per channel. the 4800 MT/s speed is still unverified (`sudo dmidecode -t memory`). if it holds, peak is 4 x 38.4 = 153.6 GB/s per socket, 307 GB/s total | [measured] edac, [external] |
| M3 | 361 GB in page cache | holds | 359 GB buff/cache today, all four `hash.k2d` 100% resident | [measured] `free`, `fincore` |
| M4 | 7 TB raid, root 97% full, 35 GB free | holds, with a footnote | the 7T PERC device also holds a 6T ext4 at `/media/dell/Data`, which `student` cannot read. "no room for a 103GB rebuild" holds for anything we can write without the admin | [measured] `lsblk`, `df` |
| M5 | orin: 12x A78AE, 4 MB SLC, 64 GB, ~205 GB/s, 57 GB emmc, 8.5 GB free | holds as documented | bandwidth is a spec number. kraken2 there is v2.1.3 | [repo] `Orion.md`, [external] |
| M6 | laptop: 5800H 8c/16t, 16 MB L3, 1x 16 GB ddr4-3200, 13.9 GB usable | holds | one dimm, "P0 CHANNEL B", 3200 MT/s. only 2.9-3.8 GB free | [measured] CIM |
| M7 | the s10 binary is cumulative with S6-S9 | wrong in detail | S10 = stock + S8 + S9 + S10. S6 and S7 are not in the chain | [repo] `00_INDEX.md`, `04_S09.md` |
| M8 | the parallel loader does nothing at 1 thread | wrong | it runs 32 threads at every `--threads`, see section 1 item 1. load: stock 56.2 s, s10 6.4 s at `--threads 1` | [measured] |
| 1 | cells cannot be copied (16 key bits), lookup transplant works, 65.6% to 94.4%, two limits | holds | pod5_15 gives 66.5% to 94.1%. add a third limit: the sample-independent number is V6, 78.3% (genomes only, no reads from this run) | [repo] transplant doc sections 2, 4, 7 |
| 2a | storage and ram are not single-channel | holds | 8 dimms on 8 controllers across 2 sockets, RAID volume | [measured] |
| 2b | one thread keeps queue depth at 1 | irrelevant to the measured runs | the file sat in page cache, so no device read happened. the warm single-thread cost is page faults: 56.2 s / 27.1M pages ≈ 2.1 µs per 4KB page for fault + zero + copy on one core. queue depth only matters cold, which is untested | [measured] `fincore`, arithmetic |
| 2c | warm load is a ram-to-ram copy that parallelizes until channels or cores run out | holds in shape | luna is nowhere near its channels at 32 loader threads. s10 lands 111 GB in ~6.2 s, about 3 x 111 / 6.2 ≈ 54 GB/s of dram traffic (zero, read, write), ~18% of 307 GB/s | [measured] + [guess] on the 3x traffic factor |
| 2d | orin: S10 gives ~nothing cold, something warm, capped by 12 cores | plausible | the loader picks min(12, 32) = 12 threads on orin by itself (same line order) | [guess] |
| 2e | the laptop saturates at 2 to 3 threads | plausible, maybe earlier | smoke test (256 MB, 1 rep, not a measurement): pure copy 9.0 to 9.2 GB/s from 1 to 2 threads | [measured, smoke only] |
| 3.1 | `-M` vs S19, warm and cold | right lever, untested on S19 | correctness should hold: S12's `InitRecip()` runs on the mmap branch too. `-M` maps `MAP_PRIVATE`, never calls `LoadFile()`, no `MAP_POPULATE` | [repo] `s12_patch.py` lines 46-49, [measured] `mmap_file.cc` |
| 3.2 | `-O3 -march=native`, then PGO | `-O3` is already there | only `-march=native`, LTO and PGO remain | [measured] Makefile:3 |
| 3.3 | parallel fastq parse | see 4a | | |
| 3.4 | flat hit-count array + per-machine prefetch tuning | array dead. luna tuning done and null | `unordered_map` < 0.8% of cycles. `K2_B` 64 vs 16: `s20_vs.log` and `s9_103.log` both null. only orin is left | [measured] |
| 3.5 | overlap db load with first parse, hugetlb pages | weak | lookups need the whole table, so only the first blocks' parse can overlap, worth ≤ ~0.5 s [guess]. hugetlb needs root and a 111 GB reservation on a 66-user machine | [guess] |
| 4a | parse and classify overlap, so 3.88 s is a ceiling only if workers starve. a flat 16-192 thread sweep on 50MB means a serial wall | holds, needs one refinement | verified: `LoadBlock` runs `kseq_read` + `copy_from_kseq` inside `critical(seqread)` (`seqreader.h:107-126`, `classify.cc:522`), and `parse_test.cc` times exactly that, so 3.88 s is the serial floor. but 50MB at 32 threads is cpu-bound: 8-core S18 = 29.31 s ≈ 234 core-s, and 234 / 32 ≈ 7.3 s vs 8.2-8.9 s measured. the parse should bind near 60+ threads. so expect a fall to ~48-64 threads then a plateau near 4-5 s, not "flat from 16". also, `cores.sh` pins `taskset -c 0-(N-1)`, which puts N/2 cores on each socket, so the "small machine" table was a two-socket 8-core | [measured], [repo], [guess] |
| 4b | `-M` loses the S14 huge pages | likely | ext4 on kernel 6.8 has no large folios for regular files, so no 2 MB file mappings. `grid.sh` logs `FilePmdMapped` to check | [guess], [external] |
| 4b | 27M page faults for 103GB with `-M` | wrong | 27M is the anonymous first-touch count. file faults map up to 16 pages around the fault (fault-around, 64 KB default), so a full touch is ~1.7M faults, and a 10-read run touches ~0.6% of the table | [external], [guess] |
| 4b | real load = wall minus "processed in" | wrong | that difference includes exit, 3.9-11.4 s. use the `.err` timestamps (section 6) | [measured] |
| 4c | `-O3` probably already in the Makefile | holds | | [measured] Makefile:3 |
| 4c | big dbs are memory-bound, so flags give ~0 | mostly | the S14 103GB profile still has ~45% of cycles in `NextMinimizer` + `ClassifySequence` + `GetAt`, so expect small, not zero | [measured] `perf_s14_103.data` |
| 5 | P3 already built (S9/S16) | holds | luna tuning is also done (null, s20). only orin is left | [repo], [measured] |
| 5 | P1 double hashing sits behind `-DLINEAR_PROBING` | holds | Makefile line 4 sets the define. `GetAt` calls `second_hash()` | [measured] |
| 5 | failed-lookup probes 6.1 vs 3.3 at load 0.7 | holds | ½(1 + 1/(1-α)²) = 6.06 and 1/(1-α) = 3.33 | [external], arithmetic |
| 5 | linear probes share 64 B lines (16 cells), double hashing jumps lines | holds | expect null or slower on speed. the value is the false-positive cliff (thesis 2) | arithmetic, [guess] |
| 5 | no 103GB rebuild on luna | holds for writable disk | also unverified: whether the library genomes for a rebuild are still on luna | [measured], [guess] |
| 5 | P2 sniper is modelling, not a speedup | holds | | [repo] |

what this means in practice: the spec's direction is right, but four sentences must not reach sir as written:
- "the loader does nothing at 1 thread"
- "wall minus processed in is load"
- "1.8x-4.4x" for S19
- "27M faults with `-M`"

---

## 3. the decision: five experiments, ranked

the ranking rule ck asked for: a lever ranks higher when its mechanism does not depend on luna's size, its output stays byte-identical, it costs under a day, and either outcome decides something.

| rank | experiment | holds on | output check | luna time | what it decides |
|---|---|---|---|---|---|
| 1 | E1: `-M` vs S19, warm, all 16 cells | any linux box, matters most on small-ram boxes | byte compare vs stock | ~20 min | whether the load strategy should depend on input size |
| 2 | E2: S0 vs S19 on orin | the question sir asked | byte compare on orin | 0 (orin ~1 h, campus) | whether the S-chain carries to arm |
| 3 | E3: build variants s21a/b/c (`-march=native`, LTO, PGO) | any machine, rebuilt per machine | byte compare + `modes.sh` | ~2 h | whether inlining and profile-guided layout cut the 38.5% scanner |
| 4 | E4: load scaling, warm and cold, on three machines | the mechanism behind S10 | same binaries, compared anyway | ~1 h | answers sir's channel question; whether to lift the 32-thread cap |
| 5 | E5: S19 thread sweep, 50MB and 8GB (+103GB at 32/64/96) | big boxes only | none needed (one binary) | ~25 min | whether a parallel parser is worth building |

every command below assumes three new scripts have been copied to luna (step 0). each runs one command at a time, and each step gets logged in `plan_paper/command_log.md` and committed per ck's workflow. `grid.sh` prints the full 4 dbs x 4 read counts table for every run and writes "not run" in cells it did not cover, so ck's full-table rule holds automatically.

**step 0, setup (laptop, git bash), not a measurement:**

```bash
$ scp -i ~/.ssh/luna_claude plan_paper/scripts/s6plus/{grid.sh,split_sweep.sh,plot_sweep.py} student@luna.cse.iitd.ac.in:chirag_K/results/s6plus/
```

### E1. `-M` (memory-mapping) vs S19, warm page cache, all 16 cells

**why.** the tempting intuition is "memory-mapping is always faster because it skips the load". half of that is right. `-M` skips the copy, the anonymous allocation and its exit teardown, and it needs 1x the db in ram instead of 2x (page cache + private copy). the other half is wrong. every lookup then lands on a 4 KB page-cache page, with no huge pages, so big tables pay a TLB miss and page walk per random lookup. and every first touch of a 64 KB window costs a page fault [external: fault-around]. so `-M` should win when a run does few lookups, and lose when it does billions of lookups that touch every page anyway.

the fraction of the table a run touches is about 1 - e^(-lookups / windows):
- lookups ≈ bases / 3. that's the minimizer density for k=35, l=31 [guess]. the 1.87M input is 6,036 Mbp [measured], so ~3.2 kbp per read
- windows = table bytes / 64 KB

on 103GB (1.69M windows) that gives:
- 10 reads ≈ 10.7K lookups → 0.6% touched
- 1,000 reads → ~47%
- 104,918 reads → ~100%

**prediction, luna, 32 threads** (S19 column measured in the 2026-09-24 matrix, output written to disk; `-M` column [guess]):

| db | reads | S19 measured (s) | S19 `-M` predicted (s) | predicted `-M` speedup |
|---|---|---|---|---|
| 50MB | 10 | 0.06 | 0.05-0.08 | ~1x |
| 50MB | 1,000 | 0.23 | 0.2-0.3 | ~1x |
| 50MB | 104,918 | 0.84 | 0.8-0.95 | ~1x |
| 50MB | 1,872,777 | 8.88 | 8.8-9.5 | 0.93-1.0x |
| 8GB | 10 | 0.46 | 0.05-0.15 | 3-9x |
| 8GB | 1,000 | 0.45 | 0.2-0.5 | 0.9-2.3x |
| 8GB | 104,918 | 1.08 | 0.7-1.2 | 0.9-1.5x |
| 8GB | 1,872,777 | 9.18 | 9.5-11.5 | 0.8-0.97x |
| 16GB | 10 | 0.77 | 0.05-0.2 | 4-15x |
| 16GB | 1,000 | 0.67 | 0.4-0.9 | 0.75-1.7x |
| 16GB | 104,918 | 1.39 | 0.9-1.4 | 1.0-1.5x |
| 16GB | 1,872,777 | 10.94 | 11-14 | 0.8-1.0x |
| 103GB | 10 | 3.79 | 0.1-0.3 | 13-38x |
| 103GB | 1,000 | 3.95 | 1.0-3.0 | 1.3-4x |
| 103GB | 104,918 | 4.50 | 2-4 | 1.1-2.3x |
| 103GB | 1,872,777 | 20.08 (13-21 thp range) | 18-30 | 0.5-1.1x |

on orin, add the variant to E2's grid. the 1x-ram argument is strongest there: a db over half of orin's 64 GB only fits with `-M` [guess].

**commands (luna), in order:**

1. confirm nothing else is running and the dbs are warm. this protects every number after it.
   ```bash
   $ tmux ls; uptime; fincore ~/AccuracyDrift/databases/*/hash.k2d
   ```
   expect no `thsweep`, load average under ~4, RES = SIZE for all four.
2. correctness gate, about 3 min. S19 with `-M` has never been byte-checked.
   ```bash
   $ RCS=104918 REPS=1 bash ~/chirag_K/results/s6plus/grid.sh m_check "s0=kraken2-fresh-bin-s0 s19M=kraken2-fresh-bin-s19=--memory-mapping"
   $ cat ~/chirag_K/results/s6plus/m_check.md
   ```
   expect `s19M:IDENTICAL` in the four 104,918 rows.
3. timing, all 16 cells, 3 interleaved reps, about 15 min.
   ```bash
   $ bash ~/chirag_K/results/s6plus/grid.sh m_vs "s19=kraken2-fresh-bin-s19 s19M=kraken2-fresh-bin-s19=--memory-mapping"
   $ cat ~/chirag_K/results/s6plus/m_vs.md
   ```
4. find contaminated `-M` cells, where part of a file had been evicted and was re-read from disk.
   ```bash
   $ awk '$4=="s19M" && $10!="majflt=0"' ~/chirag_K/results/s6plus/m_vs.log
   ```

**decision measurement.** the 16 ratios S19 / `-M` from `m_vs.md`, the `minflt` column (pages actually touched, at ≤16 pages per fault), and S19's `exit=` and `thp_gb=` columns. the last two give the first direct S19 exit number, which tests section 1 item 2.

**outcomes.**
- if `-M` wins ≥2x in the 10- and 1,000-read cells of 8GB/16GB/103GB and loses at 1,872,777, the result is "pick the load strategy by input size". a byte-identical auto-switch becomes the next stage (s22, not planned here)
- if `-M` also wins at 1,872,777 on 103GB, it is simply better on luna

**kill criterion.** stop on any MISMATCH in step 2. redo step 3 after rewarming (`cat hash.k2d > /dev/null`) if more than 2 `-M` cells show `majflt` > 0. if `-M` ≤ S19 in all six small-read cells, report it as a measured null and stop.

**confounders.**
- each S19 103GB run allocates 111 GB of anonymous memory while MemFree is ~100 GB [measured], so the kernel reclaims page cache and can evict parts of `hash.k2d` before the next `-M` run. the `majflt` check catches this
- thp coverage of S19 (`thp_gb`, expect ~103 GB when huge pages land)
- numa auto-balancing is on (`/proc/sys/kernel/numa_balancing` = 1 [measured]), so its hinting faults inflate `minflt` on long runs
- one machine, 66 users logged in

### E2. stock vs S19 on orin (the cross-machine replication)

**why.** sir's question was "does it hold on any machine". only a second machine answers that. orin is the honest second machine: arm instead of x86, 12 cores instead of 96, a 4 MB SLC instead of 210 MB, and an emmc instead of a raid. which stages should carry over, by mechanism:
- the cpu stages (S12 division, S13 memchr, S15 run counts, S17 rolling revcomp, S18 store-forwarding) are pure instruction savings. they should carry over anywhere
- S9/S16 prefetch hides dram latency inside one core. the sweep shows it is worth 1.46x at 1 thread on luna (classify 981.7 s to 672.0 s) [measured], so it does not need many cores
- S10 runs 12 loader threads on orin by itself (section 1)
- S14 depends on orin's thp setting, which is unknown
- S8 does nothing on orin's single-file inputs

**prediction, orin, 12 threads** (anchored on orin's stock v2.1.3 numbers for reads_hac at 12 threads: 50MB 4.15 s, 8GB 3.82 s with 2.35 s sys, 16GB 6.32 s with 4.23 s sys [repo: `RESULTS.md` 1.4]; v2.17.1's parser rewrite may shift S0 by ±30% [guess]):

| db | reads | stock v2.17.1 predicted (s) | S19 predicted (s) | speedup predicted |
|---|---|---|---|---|
| 50MB | 10 | 0.05-0.3 | 0.05-0.2 | 1-1.5x |
| 50MB | 1,000 | 0.1-0.5 | 0.1-0.4 | 1-1.3x |
| 50MB | 104,918 | 3.0-4.5 | 2.0-3.5 | 1.1-1.6x |
| 50MB | 1,872,777 | not runnable: 12.5 GB input > 8.5 GB free emmc | | |
| 8GB | 10 | 2.5-3.5 | 0.3-0.9 | 3-10x |
| 8GB | 1,000 | 2.5-3.6 | 0.4-1.0 | 3-8x |
| 8GB | 104,918 | 3.3-4.5 | 1.3-2.5 | 1.5-3x |
| 8GB | 1,872,777 | not runnable (input) | | |
| 16GB | 10 | 4.5-6.0 | 0.6-1.6 | 3-9x |
| 16GB | 1,000 | 4.5-6.2 | 0.7-1.7 | 3-8x |
| 16GB | 104,918 | 5.5-7.5 | 2.0-3.5 | 1.8-3.5x |
| 16GB | 1,872,777 | not runnable (input) | | |
| 103GB | 10 | not runnable: 111 GB table > 64 GB ram and > 57 GB emmc | | |
| 103GB | 1,000 | not runnable | | |
| 103GB | 104,918 | not runnable | | |
| 103GB | 1,872,777 | not runnable | | |

a USB drive holding the 16 pod5 files would open the 1,872,777 column. that's a choice for ck.

**commands, in order.**
- on luna (prep):
  1. pristine stock source, straight from the tag (read-only on the repo):
     ```bash
     $ git -C ~/tools/kraken2-src-fresh archive --prefix=kraken2-v2.17.1/ -o ~/chirag_K/orin_k2_v2.17.1.tar.gz v2.17.1
     ```
  2. S19 source without x86 objects:
     ```bash
     $ tar czf ~/chirag_K/orin_k2_s19.tar.gz --exclude='*.o' --exclude='*.bak' -C ~/tools kraken2-src-s19
     ```
- on the laptop, on campus: copy both tarballs, `grid.sh`, and luna's `reads_10.fastq` / `reads_1000.fastq` to orin with `scp`. luna to orin timed out in september.
- on orin:
  1. state check. it decides which cells can run and whether S14 can work:
     ```bash
     $ df -h ~; free -g; nproc; gcc --version | head -1; ls /usr/bin/time; cat /sys/kernel/mm/transparent_hugepage/enabled; cat /sys/block/mmcblk0/queue/read_ahead_kb; ls -la ~/AccuracyDrift/databases/*/hash.k2d ~/reads/
     ```
     if `/usr/bin/time` is missing, `sudo apt install time` (needs network).
  2. build stock:
     ```bash
     $ mkdir -p ~/tools && tar xzf ~/orin_k2_v2.17.1.tar.gz -C ~/tools && cd ~/tools/kraken2-v2.17.1 && ./install_kraken2.sh ~/tools/kraken2-bin-v217-s0
     ```
  3. build S19:
     ```bash
     $ tar xzf ~/orin_k2_s19.tar.gz -C ~/tools && make -C ~/tools/kraken2-src-s19/src clean && cd ~/tools/kraken2-src-s19 && ./install_kraken2.sh ~/tools/kraken2-bin-s19
     ```
  4. correctness on arm:
     ```bash
     $ OUT=~/k2res DBS="50MB 8GB 16GB" RCS=104918 THREADS=12 REPS=1 R104918=~/reads/reads_hac.fastq bash ~/grid.sh orin_check "s0=kraken2-bin-v217-s0 s19=kraken2-bin-s19 s19M=kraken2-bin-s19=--memory-mapping"
     ```
  5. timing:
     ```bash
     $ OUT=~/k2res DBS="50MB 8GB 16GB" RCS="10 1000 104918" THREADS=12 REPS=3 R10=~/reads/reads_10.fastq R1000=~/reads/reads_1000.fastq R104918=~/reads/reads_hac.fastq bash ~/grid.sh orin_vs "s0=kraken2-bin-v217-s0 s19=kraken2-bin-s19 s19M=kraken2-bin-s19=--memory-mapping"
     ```
  6. orin prefetch tuning, the only `K2_B` question left:
     ```bash
     $ OUT=~/k2res DBS=16GB RCS=104918 THREADS=12 REPS=3 R104918=~/reads/reads_hac.fastq bash ~/grid.sh orin_kb "b16=kraken2-bin-s19 b8=kraken2-bin-s19==K2_B:8 b32=kraken2-bin-s19==K2_B:32 b64=kraken2-bin-s19==K2_B:64"
     ```
  7. cross-machine output check, only if the db files match:
     ```bash
     $ md5sum ~/AccuracyDrift/databases/sample_targeted/hash.k2d
     ```
     run the same on luna. if they match, compare `sort` of the two 50MB S19 outputs. identical output proves the arm build computes the same answer as x86.

**decision measurement.** `orin_vs.md` (S0 vs S19 per cell) and `orin_check.md` (IDENTICAL on arm).

**kill criterion.** a build failure in the `__int128` or `MADV_HUGEPAGE` guards means fix and rebuild, never skip. any MISMATCH means stop. if S19 ≤ S0 in every cell, report that the S-chain does not carry to orin, a real null.

**cost.** ~1 h including transfer. stock 16GB runs dominate (single-thread load).

**confounders.** orin's GPU shares the memory, so check `tegrastats` shows the GPU idle. thp setting. emmc state if anything gets evicted (orin has 64 GB, and the 16GB db plus the S19 copy is 32 GB). thermal throttling, so log `tegrastats` during runs.

### E3. build variants: `-march=native`, then LTO, then PGO (s21a, s21b, s21c)

**why.** the tempting intuition is that `-march=native` is the big compiler lever, because the binary uses no AVX2. but kraken2's hot loops are integer and branchy, and the vector work it does (memchr, memmove) already runs AVX-512 through glibc [measured: `__memmove_avx512_unaligned_erms` in the S19 profile]. the measured shape points elsewhere:
- `NextMinimizer` (38.5%) is called once per base from another source file, and pays its prologue and epilogue every call (~9% of its samples) [measured]
- `GetAt` and `PrefetchIndex` (19.5% together) sit behind a virtual `KeyValueStore*` call, also in another file [repo: `s12_patch.py`]

cross-file inlining (LTO) can remove both call costs and let the compiler keep scanner state in registers. PGO then lays out the branches by real behaviour. `-march=native` goes first only because it is the cheapest to rule in or out.

**step 0: profile before building** (no new run, reads the saved profile). `ClassifySequence` (25%) was never annotated, and `ann_classify.txt` is 0 bytes. one hot instruction above ~5% there would be a new S18-style lead.

```bash
$ cd ~/chirag_K/results/s6plus && perf annotate -i perf_s19.data --stdio --no-demangle $(nm ~/tools/kraken2-fresh-bin-s19/classify | awk '/ClassifySequence/{print $3; exit}') > ann_classify.txt; awk '$1+0 >= 3' ann_classify.txt | sort -rn | head -20
```

if this prints nothing again: [UNCLEAR: perf annotate's symbol matching for this mangled name]. fall back to `perf annotate -i perf_s19.data --stdio > ann_all.txt` and search for the function header.

**prediction, luna, 32 threads, change vs S19** (all [guess]; PGO's range is the typical 5-15% for branchy integer code [external]):

| db | reads | s21a `-march=native` | s21b + LTO | s21c + PGO |
|---|---|---|---|---|
| 50MB | 10 | ~0% | ~0% | ~0% |
| 50MB | 1,000 | ~0% | ~0% | ~0% |
| 50MB | 104,918 | 0 to -3% | -2 to -8% | -4 to -15% |
| 50MB | 1,872,777 | 0 to -3% | -2 to -8% | -4 to -15% |
| 8GB | 10 | ~0% (load) | ~0% | ~0% |
| 8GB | 1,000 | ~0% (load) | ~0% | ~0% |
| 8GB | 104,918 | 0 to -2% | -1 to -6% | -2 to -10% |
| 8GB | 1,872,777 | 0 to -3% | -2 to -8% | -4 to -14% |
| 16GB | 10 | ~0% (load) | ~0% | ~0% |
| 16GB | 1,000 | ~0% (load) | ~0% | ~0% |
| 16GB | 104,918 | 0 to -2% | -1 to -6% | -2 to -10% |
| 16GB | 1,872,777 | 0 to -3% | -2 to -8% | -4 to -14% |
| 103GB | 10 | ~0% (load) | ~0% | ~0% |
| 103GB | 1,000 | ~0% (load) | ~0% | ~0% |
| 103GB | 104,918 | ~0% (load) | ~0% | 0 to -3% |
| 103GB | 1,872,777 | 0 to -2% | 0 to -5% | 0 to -8% |

the same relative ranges apply to orin, rebuilt there with `-mcpu=native` (the arm idiom) [external].

**commands (luna), in order.** every tree is new. none of the existing ones change.

1. new tree:
   ```bash
   $ cp -a ~/tools/kraken2-src-s19 ~/tools/kraken2-src-s21a
   ```
2. add the flags by editing the Makefile, never with a command-line `CXXFLAGS=`, which would drop `-DLINEAR_PROBING`. `-ffp-contract=off` stops gcc from fusing the double maths behind `--confidence` into FMAs, which could flip a borderline call.
   ```bash
   $ sed -i 's/^CXXFLAGS = \$(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -fPIC$/& -march=native -ffp-contract=off/' ~/tools/kraken2-src-s21a/src/Makefile
   ```
3. prove the edit landed and the define survived:
   ```bash
   $ grep -n '^CXXFLAGS' ~/tools/kraken2-src-s21a/src/Makefile
   ```
   expected:
   ```text
   3:CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -fPIC -march=native -ffp-contract=off
   4:CXXFLAGS += -DLINEAR_PROBING
   ```
4. without this, `install_kraken2.sh` relinks the old objects:
   ```bash
   $ make -C ~/tools/kraken2-src-s21a/src clean
   ```
5. build:
   ```bash
   $ cd ~/tools/kraken2-src-s21a && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s21a
   ```
6. proof the new flags reached the binary. expect s21a > 0. M7 found 0 AVX2/AVX-512 in stock [repo]:
   ```bash
   $ objdump -d ~/tools/kraken2-fresh-bin-s21a/classify | grep -cE 'ymm|zmm'; objdump -d ~/tools/kraken2-fresh-bin-s19/classify | grep -cE 'ymm|zmm'
   ```
7. correctness:
   ```bash
   $ RCS=104918 REPS=1 bash ~/chirag_K/results/s6plus/grid.sh s21a_check "s0=kraken2-fresh-bin-s0 s21a=kraken2-fresh-bin-s21a"
   $ bash ~/chirag_K/results/s6plus/modes.sh "kraken2-fresh-bin-s21a" 50MB
   $ bash ~/chirag_K/results/s6plus/modes.sh "kraken2-fresh-bin-s21a" 8GB
   ```
8. s21b = s21a + LTO. repeat steps 1-7 with:
   ```bash
   $ cp -a ~/tools/kraken2-src-s21a ~/tools/kraken2-src-s21b
   $ sed -i 's/-march=native -ffp-contract=off$/& -flto=auto/' ~/tools/kraken2-src-s21b/src/Makefile
   ```
   then the inlining check. a count of 0 means the scanner got inlined everywhere. a nonzero count means LTO left it out of line, and the honest next step is a source-level inline (s22), not more flags.
   ```bash
   $ nm -C ~/tools/kraken2-fresh-bin-s21b/classify | grep -c 'NextMinimizer'
   ```
9. s21c = s21b + PGO.
   1. new tree with the instrumentation flags:
      ```bash
      $ cp -a ~/tools/kraken2-src-s21b ~/tools/kraken2-src-s21c
      $ sed -i 's/-flto=auto$/& -fprofile-generate -fprofile-update=prefer-atomic/' ~/tools/kraken2-src-s21c/src/Makefile
      ```
   2. clean and build the instrumented binary:
      ```bash
      $ make -C ~/tools/kraken2-src-s21c/src clean && cd ~/tools/kraken2-src-s21c && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s21c-train
      ```
   3. training runs:
      ```bash
      $ ~/tools/kraken2-fresh-bin-s21c-train/kraken2 --db ~/AccuracyDrift/databases/standard_8gb --threads 32 --output /dev/null ~/chirag_K/results/basecalling/reads_hac.fastq
      $ ~/tools/kraken2-fresh-bin-s21c-train/kraken2 --db ~/AccuracyDrift/databases/sample_targeted --threads 32 --output /dev/null ~/chirag_K/results/basecalling/reads_hac.fastq
      ```
   4. the profile must exist before the rebuild. expect > 0:
      ```bash
      $ ls ~/tools/kraken2-src-s21c/src/*.gcda | wc -l
      ```
   5. switch to the profile-use flags:
      ```bash
      $ sed -i 's/-fprofile-generate -fprofile-update=prefer-atomic$/-fprofile-use -fprofile-correction -Wno-missing-profile/' ~/tools/kraken2-src-s21c/src/Makefile
      ```
   6. delete only the objects, not `make clean`, so the `.gcda` profile survives:
      ```bash
      $ rm -f ~/tools/kraken2-src-s21c/src/*.o
      ```
   7. final build:
      ```bash
      $ cd ~/tools/kraken2-src-s21c && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s21c
      ```
   8. correctness as in step 7.
10. timing, all three against S19, 16 cells, 3 reps, about 20 min:
    ```bash
    $ bash ~/chirag_K/results/s6plus/grid.sh s21_vs "s19=kraken2-fresh-bin-s19 s21a=kraken2-fresh-bin-s21a s21b=kraken2-fresh-bin-s21b s21c=kraken2-fresh-bin-s21c"
    ```

**decision measurement.** `s21_vs.md`, the 1,872,777-read rows above all. also `perf record` of the winner on 50MB at 32 threads, to see whether `NextMinimizer` disappeared as a separate symbol.

**kill criteria.** drop `-march=native` if s21a gains < 1% in all 1,872,777 cells (CV < 2%), because a portable binary is worth more than 1%. if s21b gains < 2% over s21a on 50MB and 8GB, call LTO a measured null. judge PGO against s21b on its own. any MISMATCH or `modes.sh` FAIL means stop: suspect the Makefile edit first.

**caveat.** the PGO training input (`reads_hac.fastq`) may overlap one of the 16 pod5 files [UNCLEAR: which pod5 it came from]. that's mild for branch statistics, but say it.

**confounders.** none beyond the usual: interleaved reps in one session, warm cache, thp state on 103GB. the cells must come from one `grid.sh` run, never from different days.

### E4. load scaling, warm and cold, on luna, orin and the laptop

**why.** this is the experiment behind sir's "single channel" question. the wrong intuition is "the load is a disk transfer, so more threads only help if the disk has more channels". in the warm runs no disk was involved: the file sat in ram. the cost was one core faulting in 27M pages, 2.1 µs each [measured]. a parallel load spreads that cpu work, and it scales until the memory system or the cores give out. cold is a different machine-specific question, about device throughput vs queue depth. that one cannot be answered from luna alone, so this experiment runs the same measurement on all three machines.

**prediction** [guess unless marked]:
- luna warm, S19 103GB load vs loader threads (`OMP_NUM_THREADS`): 1 → 15-30 s, 32 → 2.5-3.3 s. the 32-thread value is bounded by S19's measured 3.79 s total at 10 reads [repo]. s10 (no thp): 1 → 50-60 s, 32 → 5.7-6.5 s [measured]
- 16GB: S19 1 → 3-5 s, 32 → 0.4-0.6 s
- traffic at 32 threads on 103GB is ~100 GB/s, about a third of 307 GB/s. that leaves room above 32, so lifting the cap might give 2.5-3.3 s → 1.8-2.8 s
- luna cold (raid): device 1.5-4 GB/s at queue depth 1, 3-8 GB/s with 8 parallel streams. stock cold 16GB 6-14 s, S19 cold 16GB 2.5-7 s
- `-M` cold at 10 reads on 16GB: barely better. `read_ahead_kb` = 1024 on sda [measured], so each major fault reads 1 MB around it, and ~10.7K faults pull ~8 GB [guess]. on 103GB it pulls ~10 GB instead of 111 GB, so a clear win
- orin warm: S19 16GB load 1 → 4-6 s, 12 → 0.6-1.5 s
- orin cold: emmc ~0.25-0.33 GB/s [external], so stock and S19 both ~25-35 s on 8GB, with no S10 gain. `-M` at 10 reads reads only what it touches: 2-5x faster [guess]
- laptop (microbenchmark, not kraken2): pure copy flat from 1-2 threads at ~9-12 GB/s. a copy moves 2 bytes of traffic per byte, against one channel's 25.6 GB/s peak. "file → fresh memory" (what S10 does) flattens by 2-4 threads at 3-8 GB/s. unbuffered nvme reads rise to the drive's ~2-3.5 GB/s by 4-8 threads

**commands, in order.**
- luna warm, S19, loader sweep. 10 reads, so the run is all load. stock first as the reference and byte check.
  ```bash
  $ DBS="16GB 103GB" RCS=10 REPS=2 bash ~/chirag_K/results/s6plus/grid.sh load_s19 "s0=kraken2-fresh-bin-s0 L1=kraken2-fresh-bin-s19==OMP_NUM_THREADS:1 L2=kraken2-fresh-bin-s19==OMP_NUM_THREADS:2 L4=kraken2-fresh-bin-s19==OMP_NUM_THREADS:4 L8=kraken2-fresh-bin-s19==OMP_NUM_THREADS:8 L16=kraken2-fresh-bin-s19==OMP_NUM_THREADS:16 L32=kraken2-fresh-bin-s19==OMP_NUM_THREADS:32"
  ```
- luna warm, the same with s10 (4 KB pages). this separates the thp effect on load and exit.
  ```bash
  $ DBS="16GB 103GB" RCS=10 REPS=2 bash ~/chirag_K/results/s6plus/grid.sh load_s10 "s0=kraken2-fresh-bin-s0 L1=kraken2-fresh-bin-s10==OMP_NUM_THREADS:1 L4=kraken2-fresh-bin-s10==OMP_NUM_THREADS:4 L16=kraken2-fresh-bin-s10==OMP_NUM_THREADS:16 L32=kraken2-fresh-bin-s10==OMP_NUM_THREADS:32"
  ```
- read the load column per loader count:
  ```bash
  $ awk '{print $1, $4, $12, $14, $15}' ~/chirag_K/results/s6plus/load_s19.log
  ```
- luna cold: follow the protocol in section 5, once per cell, for stock, S19 and S19 `-M` at 10 reads on 16GB, then one stock/S19 pair on 103GB.
- orin warm: the same grid as the first luna command with `THREADS=12`, `DBS="8GB 16GB"`, variants L1 L2 L4 L8 L12 and the orin bin names. orin cold: section 5's per-file eviction works there too (coreutils 8.30).
- laptop: close the browser first. the script refuses to start below 2.5x the size free.
  ```powershell
  $ powershell -NoProfile -ExecutionPolicy Bypass -File plan_paper\scripts\s6plus\laptop_loadscale.ps1 -SizeMB 1024 -Threads "1,2,4,8,16" -Reps 3
  ```

**decision measurement.** load seconds vs loader threads, as GB/s of table bytes, per machine.

**decision rule.** if S19's load still drops > 25% from 16 to 32 loader threads on 103GB, the cap binds. then build s21d, a copy of s19 with `if (nthr > 32) nthr = 32;` removed in `compact_hash.cc`, and test 48/64/96 loader threads. the gain is only at small read counts, ≤ ~1.5 s [guess]. if the drop is < 10%, the cap is not binding: kill s21d.

**cost.** luna warm ~15 min, cold ~30 min (one run per eviction), orin ~30 min, laptop ~5 min.

**confounders.** thp availability (warm S19 load depends on 2 MB pages being free; log `thp_gb`). other users' disk i/o during cold runs. the PERC controller's own cache serves repeated reads of the same region, so prefer the 16 GB file and never repeat a cold read back to back. on the laptop, background apps and windows' pre-zeroed page lists make fresh-memory faults cheaper than linux's [external].

### E5. S19 thread sweep on 50MB and 8GB (the serial-parse diagnostic), plus 103GB at 32/64/96

**why.** the brief's "parse is 44% of 8.88 s" reads like a wall. it is not one at 32 threads. the parse is serial (section 2, 4a), but it overlaps with 31 other threads classifying, and 50MB at 32 threads is cpu-bound (~234 core-s / 32 ≈ 7.3 s). the parse floor (~3.9 s) only becomes the wall when cpu-time / threads drops below it, near 60+ threads. this sweep finds that knee. it also gives S19's best thread count on luna, a flag-only speedup. and it adds the S19 103GB points the s0/s10 sweep lacks.

**prediction**, `--output /dev/null` like `bench.sh` [guess, anchored on `s20_vs.log` S19 at 32 threads: 50MB 8.19 s, 8GB 7.62 s, 103GB 16.66 s, and 8-core S18 = 29.31 s]:

| threads | 50MB | 8GB | 103GB |
|---|---|---|---|
| 8 | 29-31 s | 27-30 s | not run |
| 16 | 15-16.5 s | 14-16 s | not run |
| 32 | 7.8-8.5 s | 7.3-8.0 s | 13-21 s |
| 48 | 5.5-6.5 s | 5.3-6.3 s | not run |
| 64 | 4.6-5.6 s | 4.5-5.5 s | 11-19 s |
| 96 | 4.2-5.4 s | 4.2-5.4 s | 11-20 s |
| 128, 192 | 4.2-6.0 s | 4.2-6.0 s | not run |

**commands.**
1. 50MB and 8GB, 9 thread counts:
   ```bash
   $ THREADS="8 16 24 32 48 64 96 128 192" DBS="50MB 8GB" RCS=1872777 REPS=3 NOOUT=1 bash ~/chirag_K/results/s6plus/grid.sh s19_thr "s19=kraken2-fresh-bin-s19"
   ```
2. 103GB at 32, 64 and 96:
   ```bash
   $ THREADS="32 64 96" DBS=103GB RCS=1872777 REPS=3 NOOUT=1 bash ~/chirag_K/results/s6plus/grid.sh s19_thr103 "s19=kraken2-fresh-bin-s19"
   ```
3. cpu utilization per point, (user + sys) / (wall x threads):
   ```bash
   $ awk '{split($3,a,"="); split($6,w,"="); split($7,u,"="); split($8,s,"="); if (w[2]>0) printf "%s %s %s util=%.2f\n", $1, a[2], $5, (u[2]+s[2])/(w[2]*a[2])}' ~/chirag_K/results/s6plus/s19_thr.log
   ```
4. optional, to separate numa from the parse: pin to one socket. `--membind=0` is safe for 50MB/8GB only; node 0 has ~47 GB free.
   ```bash
   $ PIN="numactl --cpunodebind=0 --membind=0" THREADS="24 48 96" DBS="50MB 8GB" RCS=1872777 REPS=3 NOOUT=1 bash ~/chirag_K/results/s6plus/grid.sh s19_thr_n0 "s19=kraken2-fresh-bin-s19"
   ```

**decision measurement.** take the plateau P (the best wall at ≥ 64 threads) and the utilization at 96 threads.
- if P < 3.9 s + 1.0 s and utilization at 96 threads < 60%, the serial parse is the wall on big boxes. a parallel parser is then worth building, for luna only. the predicted gain at 96 threads is P → 2.5-3.5 s on 50MB [guess]
- if the wall keeps falling to 96 threads with utilization > 75%, the parse is not the wall yet. drop the lever

**kill criterion.** if most points show CV > 5% over 3 reps, luna is too noisy that day: rerun later rather than read it. there is no correctness check, since it's one binary; `modes.sh` already covers 1 and 7 threads.

**cost.** ~25 min.

**confounders.** past 96 threads two threads share a core. numa auto-balancing. all-core turbo drops as more cores wake [guess]. `NOOUT=1` removes the serial in-order output write, so the plateau is parse plus startup. with output on disk, add ~0.5-1 s [guess, from 8.19 s bench vs 8.88 s matrix, which were different days].

### deliberately not in the top five

- **parallel fastq parser**: built only if E5 says so, and it helps big boxes only.
- **double hashing**: thesis 2. output changes, so it needs an accuracy table. no 103GB rebuild is possible on writable disk, and the gcd(step, capacity) audit is still open [repo].
- **SIMD scanner**: highest ceiling, highest cost (20+ h). do it after E3 says whether inlining alone moved the 38.5%. S11 showed this area can hide a stall.
- **flat hit-count array**: dead (< 0.8%).
- **`K2_B` on luna**: done, null (s20).
- **numa replication or `--interleave`**: luna only.
- **hugetlb**: root plus a 111 GB reservation on a shared box.
- **overlap load with parse**: ≤ ~0.5 s.
- **`-M` + `MADV_RANDOM` for cold first runs** (one line in `mmap_file.cc`): only if E1 and E4 show `-M` is worth keeping. it would stop the 1 MB read-around per fault.
- **the 4-way cache**: ruled out three times [repo].

what this means in practice: E1 and E5 can run today on luna. E3 is an afternoon. E2 and the orin half of E4 need campus and credentials.

---

## 4. the cross-machine story (spec section c)

this section exists because sir's question is about any machine, and only luna has data. the story has to show measured and predicted side by side, and never blur them.

**one table, three machines, same rows.** every cell is marked M (measured), P (predicted, with range), or X (cannot run, with the reason):

| row | luna | orin | laptop |
|---|---|---|---|
| memory | 8 ch ddr5 over 2 sockets, ~307 GB/s peak (M dimms, P speed) | lpddr5 ~205 GB/s (P, spec) | 1 ch ddr4-3200, 25.6 GB/s peak (M dimm, arithmetic) |
| warm load scaling: GB/s of table bytes vs loader threads | E4 (M) | E4 (M) | `laptop_loadscale.ps1` file_fresh (M, microbenchmark) |
| threads where load stops scaling | E4 | E4 | microbenchmark |
| cold device ceiling | `dd iflag=direct` (M) | `dd iflag=direct` on emmc (M) | direct_touched (M) |
| S19 vs stock, 16 cells | M, all 16 (2026-09-24 matrix) | 9 cells M after E2; 7 X (input or db too big) | X: kraken2 cannot run (no linux) |
| `-M` vs S19, 16 cells | E1 | E2 subset | X |
| prefetch alone, 1 thread | 1.46x classify on 103GB (M, sweep) | P after E2 | X |

**one chart.** x = loader threads (1 to 32, log2), y = GB/s of table bytes landed in memory. one line per machine, solid where measured, dashed where predicted. a dotted line per machine at peak bandwidth / 3, because a first-touch load costs 3 bytes of dram traffic per table byte (zero, read, write) [guess on the factor]. the story it tells: the same mechanism predicts where each machine flattens. luna is at ~18-33% of its peak at 32 threads. the laptop's single channel is already near its limit at 1-2 threads (smoke test hint). orin should sit in between.

**the laptop test, written and smoke-tested:** `plan_paper/scripts/s6plus/laptop_loadscale.ps1`. PowerShell 5.1 compiles its C# with the .NET Framework compiler that ships with windows, so nothing gets installed. it times four things vs thread count, each one piece of what S10 does:
- copy into touched memory (bandwidth ceiling)
- copy into fresh memory (adds first-touch faults)
- a cached file read into fresh memory (what S10 does warm)
- unbuffered reads (device vs queue depth)

the smoke test (256 MB, threads 1 and 2, 1 rep, not a measurement) gave copy_touched 9.0 → 9.2 GB/s, copy_fresh 5.6 → 7.8 GB/s, file_fresh 3.2 → 3.8 GB/s and direct 0.54 → 2.09 GB/s [measured, smoke only]. the real run is in E4.

what this means in practice: the laptop can only ever show the mechanism, never a kraken2 speedup, and the table says so in its own cells.

---

## 5. cold-cache protocol for luna (spec section d)

why this needs care: every number so far is warm, and luna is shared by 66 logged-in users. the spec's `echo 3 > drop_caches` throws away 359 GB of everyone's page cache. there is a gentler tool that evicts only our file, needs no root, and is checkable with `fincore`. use it first.

**before any cold run.** check that the sweep is done (`tail -1 sweep103.log` = DONE), there is no other heavy job (`ps -eo pid,user,pcpu,rss,args --sort=-rss | head -5`), and `uptime` load is under ~4.

**per cold measurement (one run per eviction):**

1. state before: expect RES = SIZE.
   ```bash
   $ free -g; fincore ~/AccuracyDrift/databases/standard_16gb/hash.k2d
   ```
2. evict only this file. GNU `dd` 8.32 on luna supports `nocache` [measured]; with `count=0` it asks the kernel to drop the whole file's cached pages (`posix_fadvise DONTNEED`) [external].
   ```bash
   $ dd if=~/AccuracyDrift/databases/standard_16gb/hash.k2d iflag=nocache count=0 status=none
   ```
3. verify: expect RES ≈ 0.
   ```bash
   $ fincore ~/AccuracyDrift/databases/standard_16gb/hash.k2d
   ```
   if RES stays high, another process maps the file (`fuser -v` on it). then either wait, or, only with ck's ok and when luna is quiet, fall back to the global drop. note that `sudo echo 3 > /proc/...` does not work, because the redirect runs without root. ck types the password at the prompt, and it never goes in a file.
   ```bash
   $ sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
   ```
4. disk counter before. field 6 is sectors read.
   ```bash
   $ grep -w sda /proc/diskstats
   ```
5. the cold run, timed with the split:
   ```bash
   $ DBS=16GB RCS=10 REPS=1 bash ~/chirag_K/results/s6plus/grid.sh cold16_s19 "s19=kraken2-fresh-bin-s19"
   ```
6. after: Δsectors x 512 = bytes actually read from disk. that proves the run was cold. `fincore` shows how much the run pulled in (all of it for S19, a fraction for `-M`).
   ```bash
   $ grep -w sda /proc/diskstats; fincore ~/AccuracyDrift/databases/standard_16gb/hash.k2d
   ```
7. repeat 1-6 for stock and for `-M`. then rewarm, so later warm benchmarks are not polluted, and expect 100%:
   ```bash
   $ cat ~/AccuracyDrift/databases/standard_16gb/hash.k2d > /dev/null; fincore ~/AccuracyDrift/databases/standard_16gb/hash.k2d
   ```

**device ceiling, no eviction needed.** `O_DIRECT` bypasses the page cache, so it neither needs a cold file nor disturbs anyone's cache:

```bash
$ dd if=~/AccuracyDrift/databases/standard_16gb/hash.k2d of=/dev/null bs=64M iflag=direct status=progress
$ time (for i in 0 1 2 3 4 5 6 7; do dd if=~/AccuracyDrift/databases/standard_16gb/hash.k2d of=/dev/null bs=64M iflag=direct skip=$((i*30)) count=30 status=none & done; wait)
```

the first line is queue depth 1, sequential. the second is 8 streams over the 16.0 GB file. the input fastq stays warm on purpose, so the cold number isolates the db load.

what this means in practice: about 3-5 min per cold cell on 16GB. no root unless the per-file eviction fails. every cold run carries its own proof (diskstats and fincore) that it really was cold.

---

## 6. the thread sweep, finished, read (spec section e)

this section exists because the sweep finished at 08:50 IST today, and its numbers already correct two claims. the split comes from `split_sweep.sh`:
- load = "done." stamp − start
- classify = "processed in" stamp − "done." stamp (matches kraken2's own number to the millisecond in all 20 runs)
- exit = start + wall − "processed in" stamp

stock (S0) vs s10, 103GB, 1,872,777 reads, `--output /dev/null`, one run per point [measured]:

| threads | S0 wall | S0 load | S0 classify | S0 exit | s10 wall | s10 load | s10 classify | s10 exit | total speedup | classify speedup |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1,046.04 | 56.23 | 981.73 | 8.09 | 685.43 | 6.37 | 672.04 | 7.03 | 1.53x | 1.46x |
| 2 | 516.38 | 57.00 | 454.62 | 4.76 | 368.04 | 5.70 | 350.98 | 11.36 | 1.40x | 1.30x |
| 4 | 304.47 | 57.72 | 236.71 | 10.04 | 156.39 | 6.17 | 141.15 | 9.07 | 1.95x | 1.68x |
| 8 | 172.88 | 58.35 | 107.57 | 6.96 | 81.28 | 6.51 | 66.67 | 8.10 | 2.13x | 1.61x |
| 16 | 115.43 | 57.88 | 52.87 | 4.68 | 41.22 | 5.94 | 30.21 | 5.07 | 2.80x | 1.75x |
| 32 | 91.22 | 58.06 | 29.16 | 4.00 | 26.40 | 6.50 | 15.38 | 4.52 | 3.46x | 1.90x |
| 64 | 82.57 | 58.19 | 20.38 | 4.01 | 22.74 | 6.44 | 11.75 | 4.55 | 3.63x | 1.73x |
| 96 | 84.81 | 58.53 | 22.24 | 4.04 | 22.40 | 5.78 | 12.12 | 4.50 | 3.79x | 1.83x |
| 128 | 84.52 | 58.06 | 22.57 | 3.89 | 23.34 | 6.14 | 12.54 | 4.66 | 3.62x | 1.80x |
| 192 | 85.28 | 58.05 | 23.30 | 3.93 | 24.32 | 6.30 | 13.32 | 4.69 | 3.51x | 1.75x |

(all times in seconds. only the 103GB db and the 1,872,777-read input were swept, so this is not a 4x4 grid. the other 15 db x read-count cells were not run in this sweep.)

**what it says.**
1. **load is flat for both binaries**: 56.2-58.5 s and 5.7-6.5 s at every `--threads`. that is the loader-ignores-`--threads` fact from section 1, now with 20 data points. the "marked line at 32 where the s10 loader cap is" does not belong on this plot. the loader was 32 threads in every s10 run. mark 96 instead, the physical core count.
2. **classify scales near-ideally to 32 threads, gains 1.3-1.4x from 32 to 64, then gets slower.** from the 8-thread point, S0 is at 92% efficiency at 32 threads and 66% at 64; s10 is at 108% and 71%. both are best at 64 threads (S0 20.38 s, s10 11.75 s), 3-9% worse at 96 and 13-14% worse at 192. the flat region starts below 96, so it is not SMT. candidates are all-core frequency dropping as more cores wake, numa auto-balancing, and cross-socket latency under load [guess]. bandwidth is not one: ~2G lookups x ~3 lines ≈ 0.4 TB in 11.75 s ≈ 33 GB/s, about 11% of peak [guess on lines per lookup]. the parse is not one either: its floor is ~3.9 s, far below 11.75 s.
3. **exit is a fixed tax.** 3.9-4.7 s at ≥ 32 threads for both binaries, noisier (4.7-11.4 s) below. at 32 threads it is 17% of s10's wall. E1's split will say how much S19's huge pages remove.
4. **low thread counts scale superlinearly.** s10 classify went 350.98 s → 141.15 s from 2 to 4 threads (2.49x). S0 went 2.16x from 1 to 2. one rep, cause unknown [measured]. candidates: uncore frequency at low load, numa auto-balancing during 10-16 min runs [guess]. so take efficiency from the 8-thread point, not from 1.
5. **session drift is large on 103GB.** s10 at 32 threads took 26.40 s today vs a 34.46 s mean on 2026-09-24 (`05_S10.md`). stock was 91.22 s vs 90.47 s. the same binary is 23% faster today, cause unknown [measured]. 103GB numbers can only be compared inside one interleaved session.

**the plot** (three panels, one y-axis each):
- total wall vs threads (log-log)
- classify only, with dashed ideal-scaling lines from each binary's 8-thread point
- load (solid) and exit (dotted)

blue = stock, orange = s10, matching `plot_s10.py`, with a vertical line at 96.

```bash
$ cd ~/chirag_K/results/s6plus && bash split_sweep.sh sweep103 > sweep103_split.tsv && ~/snn/venv/bin/python3 plot_sweep.py sweep103_split.tsv sweep103_split.png
```

`plot_sweep.py` was written without a local python, so look at the png for label collisions before it goes on a slide.

**how to read a flat region in general.** compute efficiency E(T) = classify(T₀) x T₀ / (classify(T) x T) with T₀ = 8:
- E ≈ 1 means per-thread work stays the same, so add threads
- E falling before the physical core count means a shared resource saturates: memory latency or bandwidth (compare achieved bytes/s with 153.6 GB/s per socket), a serial section (compare the plateau with the 3.9 s parse floor), or frequency
- E falling only past 96 means SMT

with one rep and ±4% noise on 103GB (stock reps 86.58 s vs 92.93 s in `s9_103.log` [measured]), a difference under ~5% is not a result.

what this means in practice: on 103GB, s10's best is 64 threads (22.74 s). E5 adds the S19 points. the remaining 103GB costs are classify (~52%), load (~28%) and exit (~20%) at 64 threads in s10, and E1/E4 attack the last two.

---

## 7. wednesday story, and what not to claim (spec section f)

today is wednesday 2026-10-21. if this is the standing 4 pm meeting, E1 (20 min), E5 (25 min), the sweep plot and the laptop script all fit before it. orin, cold-cache and PGO go into next week's slide as "next".

**the story, in order:**
1. **S19 vs stock, full 4x4, byte-identical, luna only.** 1.9x (50MB) to 4.8x (103GB) at 1,872,777 reads. 9.8x-15.4x at 10 and 1,000 reads on the three big dbs, 1.3x-1.6x on 50MB. one run per cell. S19 on 103GB ranges 12.3-20.1 s across sessions because of huge pages.
2. **sir's channel question, answered with the sweep.** the load was never a disk transfer: the file was in ram. one thread paid ~27M page faults at ~2.1 µs each (56 s). S10 spreads them over 32 threads (6 s). luna has 8 channels over 2 sockets, and that load uses roughly a fifth of their bandwidth. show the three-panel plot. load is flat at every `--threads` (the loader ignores it), classify scales to 64 then stops, and exit is a 4-5 s tax nobody had counted.
3. **the 1-thread result as the portability argument.** at one thread s10 classifies 1.46x faster than stock (981.7 s → 672.0 s). that is prefetch hiding memory latency inside a single core. it needs no extra cores, so it is the piece of the chain most likely to carry to orin and a laptop. this is a prediction, said as one.
4. **if E1 ran: the `-M` table.** where mapping beats copying (few reads, 1x ram) and where it loses (many reads, no huge pages).
5. **if the laptop script ran:** the one-channel laptop curve next to luna's, labelled "microbenchmark, not kraken2".
6. **next:** the orin replication (needs campus), cold-cache runs (per-file eviction, no root), and the LTO/PGO builds, with the decision each one makes.
7. **the transplant, in one line, with its three limits:** not a neural network; 103GB is the reference, not the truth; 94.4% is sample-adaptive, and the sample-independent number is 78.3%.

**do not claim:**
- any orin or laptop kraken2 speedup. nothing ran there.
- that S10 helps because of more disk channels or a deeper queue, for any measured run. they were warm, with no disk reads.
- that the loader "does nothing at 1 thread", or that the sweep shows loader scaling. the loader was 32 threads in every s10 run.
- "wall minus processed in" as the load time.
- s20 (`K2_B` = 64) as a speedup. it is a null.
- a single 103GB S19 number without its range (12.3-20.1 s across sessions), or any 103GB comparison across sessions (s10 alone moved 34.46 s → 26.40 s).
- "1.8x-4.4x" as S19's number. that is S15's.
- the superlinear low-thread scaling as a finding, or any cause for the 64-thread plateau. both are unexplained.
- "`-M` is 12-14x faster". that was stock vs stock, before S10 and S14.
- any guessed percentage from the brief or from this plan (PGO 5-15%, parallel parse 15-30%, the E1-E5 prediction tables).
- that double hashing is faster.
- the transplant's 94.4% as accuracy. it is agreement with 103GB on files from the same run.
- the `cores.sh` table as "an 8-core machine". it pinned 4 cores on each socket.
- "the scanner is 25%". it is 38.5% in the S19 profile.

---

## 8. the single first command (spec section g)

after step 0 copies the scripts over, ck's first command is E1's correctness gate:

```bash
$ RCS=104918 REPS=1 bash ~/chirag_K/results/s6plus/grid.sh m_check "s0=kraken2-fresh-bin-s0 s19M=kraken2-fresh-bin-s19=--memory-mapping"
```

why this one first:
- it gates the top-ranked experiment
- S19 with `-M` has never been byte-checked against stock
- it takes about 3 minutes and gives a yes/no answer
- it can run right now, because the sweep finished at 08:50 IST and luna is free
- it also gives the first load / classify / exit split of S19 on all four dbs, which says straight away whether huge pages removed the 4-5 s exit tax found in section 6

if all four rows say `s19M:IDENTICAL`, the next command is E1 step 3. if any says MISMATCH, stop and read the `.out` diff before timing anything.

---

## appendix: files written for this plan (not committed)

| file | what | tested |
|---|---|---|
| `plan_paper/scripts/s6plus/split_sweep.sh` | load / classify / exit split of a `threads_sweep.sh` run | yes, on a copy of the real sweep103 files: classify matches kraken2's own "processed in" in all 20 runs |
| `plan_paper/scripts/s6plus/grid.sh` | one runner for E1-E5: variants with flags or env, thread lists, full 4x4 summary with "not run" cells, fault counts, thp peak, byte compare on rep 1, `NOOUT`, `PIN` | yes, locally against stub `kraken2` and `time` binaries: IDENTICAL, MISMATCH (env flip), NOOUT and the full-grid summary all behave. not yet run on luna. `exit` values under ~0.05 s are noise |
| `plan_paper/scripts/s6plus/plot_sweep.py` | the three-panel sweep plot | not run: no python on the laptop. run on luna and eyeball it |
| `plan_paper/scripts/s6plus/laptop_loadscale.ps1` | the laptop load-mechanism microbenchmark | smoke-tested at 256 MB, 1 rep (numbers in section 4 are not measurements) |

nothing under `~/tools/` was created or modified on luna. the only luna actions were reads: `grep`, `cat`, `ls`, `lsblk`, `df`, `free`, `fincore`, `numactl -H`, `lscpu`, `perf report` and `scp` of the sweep logs to this laptop.
