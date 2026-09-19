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
