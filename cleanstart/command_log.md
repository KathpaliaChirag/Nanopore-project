# cleanstart command log

every command actually run, in order: why, then result. same pattern as cache_simulation/command_log.md.

---

### [0] 2026-09-19 - folder created on this machine

created `cleanstart/` in the repo root (README.md + this file). Luna copy: `~/cleanstart` (created by hand, see step 1).

---

### [1] 2026-09-19 - Luna inventory check + create ~/cleanstart

```bash
ssh -i ~/.ssh/luna_claude student@luna.cse.iitd.ac.in 'mkdir -p ~/cleanstart && ls -la <S0 classify> <luna.cfg> <laptop.cfg>; ls -d ~/chirag_K/AccuracyDrift/databases/*/; find ~ -name "*.pod5" -size +1G'
```

**why:** confirm S0 binary, hardware configs, databases, and any existing large pod5 exist before choosing the fixed baseline. ssh access to Luna works from this machine (key `~/.ssh/luna_claude`), older notes saying it does not are out of date.

**result:**
- S0 classify exists: `~/chirag_K/tools/kraken2-src-baseline/src/classify` (264 KB, built Aug 3)
- `luna.cfg` (Sep 8) and `laptop.cfg` (Sep 15) exist in `~/cache_simulation/snipersim/config/`
- databases: standard_8gb, standard_16gb, pluspf_103gb, sample_targeted, eskape_genomes, plus centrifuge/centrifuger/metabuli ones
- pod5 files over 1 GB already on Luna: `~/chirag_K/data/pod5/fbe/FBE01990_24778b97_03e50f91_{0,3,5,6,7,9,10,11,13,14}.pod5` (at least 10, so no need to fetch one)
- `~/cleanstart` created, empty

---

### [2] 2026-09-19 - fix the inputs: reads file + 3 databases

```bash
ssh ... 'du -sh ~/chirag_K/AccuracyDrift/databases/*/; find ~ -name "*.fastq" -size +50M | count reads (wc -l / 4)'
ssh ... 'ls -lh .../sample_targeted/ .../standard_8gb/ .../standard_16gb/'
```

**why:** CK asked for any pod5, 3 databases (50 MB, 8 GB, 16 GB), and a fastq with ~104K reads. instead of basecalling again, look for an existing fastq near 104K.

**result:**
- reads: `~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_10.fastq` = **104,980 reads**, 723 MB (sup basecall of pod5 `_10`). closest to 104K of the existing fastqs. no dorado run needed.
- 50 MB db = `sample_targeted` (`hash.k2d` is exactly 50 MB, same db the old "50mb" runs used). 8 GB = `standard_8gb` (7.6 GB). 16 GB = `standard_16gb` (`hash.k2d` 15 GB).
- caveat: detailed-mode Sniper cannot run 104K reads. each run will use a fixed slice, size to be decided next.

---

### [3] 2026-09-19 - create 10/50/100-read slices on Luna

```bash
SRC=~/chirag_K/data/basecalled/sup/FBE01990_24778b97_03e50f91_10.fastq; W=~/cleanstart/workloads; mkdir -p $W
for n in 10 50 100; do head -n $((n*4)) $SRC > $W/reads_$n.fastq; done
```

**why:** CK chose 10, 50 and 100 reads per run (3 read counts x 3 databases = 9 workloads per hardware setting). fastq = 4 lines per read, so `head -n 4N` takes the first N reads. slices are nested prefixes of one file, so runs differ only in amount of work, not in which reads are used. kept separate from the old `cache_simulation/workloads` so nothing old is reused by accident.

**result:** all three verified (read count = N, same first read id `@eee06777-c6a0-45dc-8f87-edbc7fa56f2d`):

| file | reads | size | total bases |
|---|---|---|---|
| reads_10.fastq | 10 | 732 KB | 372,413 |
| reads_50.fastq | 50 | 4.3 MB | 2,209,336 |
| reads_100.fastq | 100 | 11 MB | 5,262,723 |

base count grows unevenly (read lengths vary a lot), so "100 reads" is ~14x the work of "10 reads", not 10x.

---

### [4] 2026-09-19 - first baseline run: 1 core, 10 reads, 50 MB db, laptop.cfg unchanged

```bash
cd ~/cache_simulation/snipersim
./run-sniper -c address_translation_schemes/baseline -c laptop -n 1 -d ~/cleanstart/results/base_r10_50mb -- \
  ~/chirag_K/tools/kraken2-src-baseline/src/classify -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
  -p 1 -T 0 -Q 0 -g 2 ~/cleanstart/workloads/reads_10.fastq      # DB = .../databases/sample_targeted
```

**why:** the reference run. no `--fast-forward` (detailed timing mode). S0 binary, unchanged laptop.cfg (Ryzen 7 5800H: 32K/8w L1d, 512K/8w L2, L3 as NUCA slices of 2048 KB/16-way).

**result (took 620 s wall, simulator ran at 202 KIPS):**
- 124.9M instructions, 89.6M cycles, **IPC 1.39**, 202,397 unique data cache lines
- classify itself: 10 reads, 9 classified (90%)
- L1d loads 41,560,001: L1 hit 99.10%, L2 hits 0.126%, L3 (NUCA) hits 0.312%, remaining ~0.46% went past L3 (DRAM)
- simulated time 28.01 ms (`performance_model.elapsed_time` = 28011600000000 fs, matches 89.6M cycles / 3.2 GHz)
- confirmed in `simulation/sim.cfg`: with `-n 1` the L3 is `cache_size = 2048` (one 2 MB slice, NOT the laptop's real 16 MB). multicore `-n 8` gets 8 slices.

**gotchas found:**
- stats live in `<outdir>/simulation/sim.stats`, not `<outdir>/sim.stats`. the queue script had this wrong and was fixed before launch.
- `ssh host 'cd x && nohup cmd > f 2>&1 &'` hangs the ssh call because the whole `&&` list is backgrounded and holds the ssh output open. the run itself was fine. for the queue, launch as a plain `nohup setsid bash script > log 2>&1 < /dev/null &`.
- `performance_model.elapsed_time` is in femtoseconds.

---

### [5] 2026-09-19 - baseline redefined after CK's review; smoke tests found `-n` was silently ignored

CK asked: (a) keep L3 size the same when cores change, (b) model instruction cache + TLB like the Ryzen 7 5800H, (c) name every test by all its knobs, (d) add an L4 to the mix (not done yet, see below), (e) also run 4 cores.

**findings from reading sim.cfg / config on Luna:**
- TLBs were never off: the real ones live under `perf_model/mmu/tlb_level_*` (L1 DTLB 64-entry 4-way x2 page sizes, L1 ITLB 64-entry 4-way, L2 TLB 2048-entry 8-way unified). `perf_model/dtlb|itlb size=0` are unused legacy sections.
- `enable_icache_modeling = "false"` in every earlier run (this whole project's old data). now set to true.
- **`-n N` alone does NOT give N cores.** smoke test `-n 4 -- /bin/true`: effective `total_cores = 1`. some later config layer resets it. fix: add `-c general/total_cores=N` after the config overlays. verified: `total_cores = 4`, per-core stat columns, 4 `nuca-cache` entries (one L3 slice per core).
- sim.stats multicore lines are `name = v0, v1, v2, v3`, so parsers must sum across commas (old `awk '{print $3}'` parse would read only core 0).
- all overrides checked in effective `sim.cfg` (4-core smoke): icache modeling true, L1 TLBs assoc 64, nuca 4096 KB x 4 slices = 16 MB, L2 512/8w, L1d 32/8w.
- icache modeling on changed the /bin/true smoke IPC 0.87 -> 0.42 (cold instruction cache), expected.

**caveats to remember:**
- Sniper cache latency does NOT scale with size: a 16 MB single-slice L3 (1 core) has the same 20+15 cycle latency as a 2 MB slice. "bigger is better" will look artificially true in size sweeps unless we model latency vs size.
- Zen 3 TLB numbers are from AMD's published specs as recalled, not re-verified. Sniper's L2 TLB is unified (Zen 3 has a separate 512-entry L2 ITLB).
- L4: the fork has an `l4_cache` section but the L3 is the NUCA mesh (`perf_model/cache/levels = 2`), so how a 4th level stacks is untested. needs CK's decision on what L4 is, then a smoke test.

**done:** wrote `configs/cleanstart_laptop.cfg` (deployed to snipersim/config/), `scripts/run_one.sh`, `scripts/run_baseline_queue.sh` (27 runs). old first run moved to `~/cleanstart/results/old_no_icache_2MB_L3/` (124.9M instr, 89.6M cycles, IPC 1.39: obsolete definition, kept for reference). queue NOT launched yet, waiting for CK.

---

### [6] 2026-09-19 - L4 dropped

CK: there is no L4, it was only an example. removed `_L4none` from the config name in `run_one.sh` and the README. baseline name is now `L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`. no results existed under the old name.

---

### [7] 2026-09-19 23:04 IST - baseline queue launched (27 runs)

```bash
ssh ... 'nohup setsid bash ~/cleanstart/run_baseline_queue.sh > ~/cleanstart/results/queue.out 2>&1 < /dev/null &'
```

**why:** CK: "just do the baseline runs first". order: cores 1, 4, 8 x reads 10, 50, 100 x db 50mb, 8gb, 16gb, one after another. baseline = `L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`, S0 binary, detailed mode. launched as a plain nohup+setsid with all fds redirected (no `&&` list) so the ssh call returns and the queue survives a disconnect. first run `1c r10 50mb` started 23:04:31, confirmed `lib/sniper` alive.

progress: `~/cleanstart/results/queue_progress.log`. results: `~/cleanstart/results/summary_all.csv`. re-running the queue script skips finished runs.

---

### [8] 2026-09-19 23:16 IST - first baseline row + parser bug fix

**run 1 done:** `1c_r10_50mb` (1 core, 10 reads, 50 MB db, baseline `L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`): 124.9M instr, **86.0M cycles, IPC 1.45**, 202,401 unique data lines, L1d 99.09% / L2 0.12% / L3 0.49% of loads, wall 695 s. (old definition with 2 MB L3 + no icache: 89.6M cycles, IPC 1.39.)

**bug:** `sim_time_max_fs` came out as 2147483647 (int32 max): awk `printf "%d"` overflows on femtosecond values (26,860,600,000,000). the same overflow would hit load counts > 2.1 billion on large/multicore runs. fixed both `stat_sum`/`stat_max` to `%.0f`. deployed via write-to-temp + `mv` (atomic rename) so the queue's running run_one.sh instance was not disturbed. repaired row 1 in place from `sim.stats` (26.86 ms = 86.0M cycles / 3.2 GHz, consistent).

---

### [9] 2026-09-19 23:43 IST - batch 1: 1 core, 10 reads, all 3 databases done

baseline `L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`, S0, detailed mode:

| db | instr (M) | cycles (M) | IPC | unique lines | L1d hit | L2 hit | L3 hit | wall |
|---|---|---|---|---|---|---|---|---|
| 50mb | 124.9 | 86.0 | 1.45 | 202,401 | 99.09% | 0.12% | 0.49% | 695 s |
| 8gb | 132.6 | 80.3 | 1.65 | 189,048 | 99.21% | 0.22% | 0.42% | 758 s |
| 16gb | 154.1 | 99.4 | 1.55 | 202,578 | 99.23% | 0.20% | 0.42% | 884 s |

- row 2 (8gb) had the old int32 overflow in `sim_time_max_fs` (it started before the parser fix); repaired by hand from sim.stats (25.09 ms = 80.3M cycles / 3.2 GHz).
- **odd, unexplained:** 8gb finished in FEWER cycles than 50mb (80.3M vs 86.0M) despite more instructions. a 10-read run is ~125M instructions for only 0.37M bases, so it is dominated by fixed startup work (database load), not classification. do not read a DB-size trend into 10-read numbers.
- results copy committed at `cleanstart/measurements/summary_all.csv`.

---

### [10] 2026-09-20 01:44 IST - batch 2: 1 core, 50 reads, 50mb + 8gb done

baseline `L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`, S0, detailed mode, 1 core, 50 reads (2.2M bases):

| db | instr (M) | cycles (M) | IPC | unique lines | L1d hit | L2 hit | L3 hit | reads classified | wall |
|---|---|---|---|---|---|---|---|---|---|
| 50mb | 677.5 | 446.1 | 1.52 | 842,162 | 99.15% | 0.09% | 0.45% | 84% (42/50) | 3607 s |
| 8gb | 685.0 | 373.3 | 1.84 | 611,804 | 99.31% | 0.15% | 0.43% | 98% (49/50) | 3640 s |

- **repeat pattern:** the 8gb db is FASTER than the 50mb db at both 10 reads (80.3M vs 86.0M cycles) and 50 reads (373M vs 446M, -16%), with almost the same instruction count. not noise.
- 50mb classifies fewer reads (10 reads: 90% vs 100%; 50 reads: 84% vs 98%) and causes more DRAM reads (1.11M vs 0.81M) and more unique cache lines (842K vs 612K).
- **hypothesis, NOT tested:** `sample_targeted` hash table is nearly full, so lookups of k-mers it does not contain probe a long linear-probing chain before hitting an empty slot; unclassified reads pay this on most of their k-mers. to test: compare the hash table load factor (`opts.k2d`/`inspect`) of the 3 dbs, or count probe steps.
- wall time ~1 h per 50-read run, matches the estimate. queue now on `1c r50 16gb` (started 01:44).

---

### [11] 2026-09-20 02:54 IST - 1 core, 50 reads complete (all 3 dbs)

| db | instr (M) | cycles (M) | IPC | unique lines | L1d hit | L2 hit | L3 hit | classified | dram reads | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| 50mb | 677.5 | 446.1 | 1.52 | 842,162 | 99.15% | 0.09% | 0.45% | 84% | 1.11M | 3607 s |
| 8gb | 685.0 | 373.3 | 1.84 | 611,804 | 99.31% | 0.15% | 0.43% | 98% | 0.81M | 3640 s |
| 16gb | 783.1 | 470.8 | 1.66 | 700,624 | 99.31% | 0.15% | 0.42% | 98% | 0.98M | 4221 s |

cycle order at 50 reads: 8gb (373M) < 50mb (446M) < 16gb (471M). 16gb is not the fastest, so the 50mb anomaly is not simply "small db = slow" and not simply "big db = slow" either: 8gb is the odd one out. the nearly-full-hash-table hypothesis for 50mb (see [10]) is still untested. next: 1c r100 x 3 dbs (started 02:54, ~2 h each expected).

---

### [12] 2026-09-20 - 1-core baseline complete (9/27); first 4-core run DEADLOCKED, queue stopped

**1-core baseline, all 9 runs done** (`L3-16MB_L2-512KB_L1-32KB_L1w8_L2w8_L3w16`, S0, detailed, `measurements/summary_all.csv`):

| reads | db | instr (M) | cycles (M) | IPC | wall |
|---|---|---|---|---|---|
| 10 | 50mb / 8gb / 16gb | 124.9 / 132.6 / 154.1 | 86.0 / 80.3 / 99.4 | 1.45 / 1.65 / 1.55 | 12-15 min |
| 50 | 50mb / 8gb / 16gb | 677.5 / 685.0 / 783.1 | 446.1 / 373.3 / 470.8 | 1.52 / 1.84 / 1.66 | 60-70 min |
| 100 | 50mb / 8gb | 1583.6 / 1640.7 | 1017.1 / 880.9 | 1.56 / 1.86 | 2 h 15-21 min |
| 100 | 16gb | (see csv) | (see csv) | (see csv) | 2 h 42 min (9732 s) |

**4-core run `4c_r10_50mb` deadlocked:** started 10:13, still "running" 9 h later at 0.0% CPU. all 4 processes (run-sniper, lib/sniper, record-trace, classify) in sleeping state; log shows "Thread 0..3 started" and 3x "Creating new application with app id = 0" within the first minute, then nothing; `sim.stats` never written. killed manually 19:14 by PID (queue script first). no result was lost (nothing had been produced).

**gotcha:** `ssh host 'pkill -f "pattern"'` kills its own remote shell (the pattern is in that shell's command line) -> ssh exit 255 before the rest runs. use PIDs.

**likely cause (NOT verified):** the `address_translation_schemes/baseline` scheme does not support a multi-threaded app; the fork ships separate `address_translation_schemes/multicore/parametric_baseline_{2,4,8,16}c.cfg` schemes (which set `total_cores` themselves). the 1-core baseline is unaffected. the 17 other multicore runs would all hang the same way if launched unchanged, so the 4/8-core groups are on hold.

---

### [13] 2026-09-20 20:33 IST - multicore smoke test passed; hang watchdog + binary-log fix; queue relaunched

**smoke test:** `-n 4 -p 4`, 2 reads, 50mb db, same setup as the queue (baseline scheme, cleanstart_laptop overlay, `total_cores=4`, nuca 4096 KB x 4 slices): completed in 181 s, no hang. per-core instructions 18.4M / 6.1M / 6.1M / 6.1M (worker threads spin ~6M instr each), 13.8M cycles each core, 1 of 2 reads classified. so multi-threading works in general under the `baseline` scheme; the earlier 9-hour hang of `4c_r10_50mb` was NOT the scheme (`baseline` and the fork's `multicore/parametric_baseline_4c` differ only in DRAM model: ddr4_2400 45 ns / 57.6 GB/s vs readwrite 153 GB/s; both already use `parametric_dram_directory_msi` mesi). cause of that one hang still unknown, could not reproduce with 2 reads.

**fixes to `run_one.sh`:**
1. **hang watchdog:** run-sniper now starts in its own session (`setsid`); every 30 s the runner sums CPU time of all processes in the session (`ps -s <sid> -o cputimes=`); no advance for `HANG_S=900` s -> kill the session group, print `HUNG ...`, write a HUNG row to the CSV, exit 3. the queue then continues instead of blocking.
2. **`grep -a`:** multicore logs contain binary bytes, plain `grep` printed "binary file matches" and the parser would have written blank rows for every multicore run.

**relaunched** the same queue script (1-core runs skip, 9 done). `4c_r10_50mb` started 20:33:48: simulator 95% CPU, classify 40% CPU after 90 s (healthy, unlike the hung run's 0%).

---

### [14] 2026-09-20 22:20 IST - 4 cores: 10 reads done (3 dbs), 50 reads 50mb done

**4 cores, 10 reads** (cycles, 1-core -> 4-core): 50mb 86.0M -> 89.3M (+3.8%), 8gb 80.3M -> 84.0M (+4.6%), 16gb 99.4M -> 105.1M (+5.7%). no speedup: core 0 did ~125M of 148M instructions, cores 1-3 spun (6-8M instr, IPC ~0.08). 10 reads = one kraken2 batch = one working thread.

**4 cores, 50 reads, 50mb** (`4c_r50_50mb`, wall 3754 s): 707.9M instr total, **348.9M cycles vs 446.1M on 1 core = 0.78x (1.28x speedup)**, IPC 2.03 (aggregate over 4 cores), 84% classified (same as 1-core).
per-core instructions: core 0 = 503.0M, core 2 = 188.0M, cores 1 and 3 = 8.4M (idle spinning). so only 2 of 4 threads got real work, split ~73/27. cycles reported = the slowest core (348.9M = 503M / 1.44 IPC).
total instructions +4.5% vs 1-core (677.5M) = spin/sync overhead.
L3 hit share of loads fell to 0.26% (1-core 0.45%), unexplained, not investigated.
