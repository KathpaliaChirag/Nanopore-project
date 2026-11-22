# round 1, agent A (historian): what the sniper work on kraken2 actually shows

sources read: command_log.md (all 2464 lines), every csv in measurements/, every cfg in configs/ (incl. hw_assoc readme), RESEARCH_PROMPT_optimal_cache_size.md (grepped), README.md. nothing run, nothing on luna touched. all ratios below were re-derived from csv columns (cycles_M unless stated).

## 0. fixed setup common to every run

- simulator: sniper master HEAD 56505e4 (2026-05-23), built on luna (dell-R760, xeon 8468). frontend is intel SDE trace recording. every run is -n 1 (one simulated core), classify -p 1 (single thread).
- invocation: run-sniper -c address_translation_schemes/baseline -c <hw cfg> -n 1 -- classify -H hash.k2d -t taxo.k2d -o opts.k2d -p 1 -T 0 ... (two separate -c flags, baseline first; the comma form is a hetero-core path and is wrong).
- core model: meteor_lake_pcore interval core (inherited wholesale, not sapphire rapids). only frequency changed per cfg.
- metric rule (logged step 60): headline metric is simulated cycles. csv columns elapsed_s / wallclock_s are sniper's own runtime, not kraken2 runtime.
- binaries: S0 = kraken2-src-baseline/classify (no s2_cache symbols). "original S2" = kraken2-fresh-bin-s2-{baseline,lru-noatomics-Nway,1way}. "sizepin-N" = current-tree 4-way build with S3_MIN_SETS=S3_MAX_SETS=N.
- DBs: sample_targeted 50mb, standard_8gb (7.5G), standard_16gb (15G), pluspf_103gb (104G). default eager load, no -M.
- workload files: tiny_10reads.fastq (10 short reads), 50reads.fastq (50 reads, 91,372 bases, mean 1,827), reads_fast_2000.fastq (2000 reads, 35.05M bases, mean 17,526; the front of the source file is long-read heavy, true file mean is 3,411), long_10/25/50 (nested prefixes of reads_fast_2000, 0.35M/0.90M/1.87M bases), 100/500-read subsets of reads_fast_2000 (4.7M/25.4M bases).

## 1. experiments, in order, with config and numbers

### E0. bring-up (steps 1-37)
config luna.cfg after 3 bugs: (a) comma -c list, (b) 1120KB nuca slice not divisible at 15-way (fixed to 1125KB, 1200 sets), (c) xor_mod hash segfaults when sets is not a power of 2 (fixed with address_hash=mod). tiny_10reads under original-S2 baseline: 25.1M instr, 14.3M cyc, IPC 1.76, 51,558 unique lines, 7/10 classified, output matches native. sniper had to be pointed at the compiled classify binary, not the perl kraken2 wrapper.

### E1. width sweep, 10 reads, 50mb (associativity_sweep_2026-09-08_summary.csv)
binaries: s2-baseline and lru-noatomics-{4,8,16,32,64}way (original S2 design). cycles M: baseline 14.2, 4w 14.3, 8w 14.4, 16w 14.7, 32w 15.1, 64w 15.9. IPC flat 1.76-1.80. unique lines 51.6K to 239.9K. the "baseline" row is NOT true no-cache (it has s2_cache), logged in step 40. result: wider is worse, mildly (64w/4w = 1.112 on cycles).

### E2. fair batch, 50 reads, 5 variants x 4 DBs (final_fair_batch csv, luna.cfg)
S0 vs 1/4/8/16-way original S2. cycles M (S0 / 1w / 4w / 8w / 16w):
- 50mb: 24.4 / 27.0 / 26.8 / 27.8 / 28.7
- 8gb: 51.8 / 28.6 / 28.3 / 28.7 / 28.9
- 16gb: 60.7 / 30.1 / 29.6 / 30.1 / 30.4
- 103gb: 94.3 / 48.8 / 47.8 / 49.1 / 50.0
speedup S0/4way (re-derived): 0.910, 1.830, 2.051, 1.973. S0 instr (M): 35.8, 68.1, 77.3, 102.9 vs 4way instr 39.7, 51.9, 51.9, 70.3. classification output byte-identical across variants. an earlier batch had wall-clock contamination from concurrent jobs and cross-batch drift (steps 53-57); cycles were never affected.

### E3. hardware cache-size comparison, 50 reads, S0 vs 4way (hwsize_comparison csv)
cfgs luna (data from E2), desktop.cfg (ryzen 5 5600x sizes), orion_sizes.cfg (jetson sizes on the x86 core model). 50mb S0/4w cycles: desktop 28.2/30.7 (0.919), orion 26.7/29.6 (0.902), luna 0.910. 8gb: desktop 60.6/31.3 (1.936), orion 55.9/33.9 (1.649), luna 1.830. log conclusion: not monotone in cache size; orion weakest, desktop strongest. the explanation offered (orion larger l1) is marked unverified.

### E4. 2000 reads, 50mb, 5 variants (2000reads_live_summary csv, luna.cfg)
S0 6354.0 cyc, 10053.7M instr, IPC 1.58, 1,615,102 lines. 1way 8336.3 (1.312x), 4way 8159.1 (1.284x), 8way 8508.1 (1.339x), 16way 8805.9 (1.386x). l1d hit 99.04 (S0) down to 97.44 (16w); l2 hit 0.21 to 1.12; nuca hit 0.030 to 0.218. every cache variant loses. each run took 12-15 hours of sniper time.

### E5. hardware llc associativity sweep, S0 only, 50mb (hw_assoc_sweep csv)
overlays configs/hw_assoc/luna_assoc{1,4,8,15,16,30}.cfg, nuca slice fixed at 1125KB (18000 blocks), only assoc and sets change. reads 10/50/100/500. cycles spread: 10 reads 13.6-13.7; 50 reads 24.4 all; 100 reads 869.8-877.3 (0.86%); 500 reads 4523.2-4537.9 (0.32%). unique lines identical across assoc. null.

### E6. hw assoc sweep, big DBs (hw_assoc_sweep_bigdb csv), S0, 50 reads
8gb 51.7-51.8 across all six; 16gb 60.7 across all six. null.

### E7. flat l3 vs nuca (flatl3_comparison csv, luna_flatl3.cfg), S0, 50 reads
50mb nuca 24.4 vs flat 31.9 (1.307x slower); 8gb nuca 51.8 vs flat 60.4 (1.166x). same instr count, IPC 1.47 to 1.12 and 1.32 to 1.13. flat l3: 107520KB, 15-way, 114688 sets, mod hash, shared_cores=1, lru, prefetcher=none, tag 15 / data 20 cycles (same placeholders as nuca). l3_hit_pct column for nuca rows is 0 by script bug.

### E8. software cache size ladder (sizepin-N binaries, current design), 4-way fixed, luna.cfg
N = 2048, 4096, 16384, 65536, 262144, 1048576 sets. correctness: all byte-identical to S0 on tiny_10reads.
- 50mb, 10 reads: 14.2, 14.2, 14.2, 15.1, 14.2, 14.3. true S0 same config: 14.1 cyc, 23.9M instr, IPC 1.69. 65536 vs 16384 = +6.3% cycles. no size beats S0.
- 103gb, 10 reads: 15.1 x3, 16.0, 15.1, 15.1 (+6.0% at 65536). instr 25.4M, 28.0M at the spike.
- 8gb, 50 reads (a different workload): 27.9 x3, 28.6, 27.9, 27.9 (+2.5%). instr 52.1 to 54.4.
- 16gb, 50 reads: 29.2, 29.3, 29.3, 29.6, 29.3, 29.3 (+1.0%). never used in the H1-H4 verdict or fig14.
spike pattern: instr and l1d_loads jump (+660,776 loads at 65536 on 50mb, +621,424 on 103gb, +572,524 on 8gb) with IPC flat or slightly up, then fully revert at 262144 and 1048576.
no true S0 was run for 8gb or 103gb in the size sweep; the only matched S0 is 50mb/10 reads.

### E9. laptop sweep (laptop_sweep csv, laptop.cfg = ryzen 7 5800h, 3.2GHz, l2 512K 8w, nuca 2048KB slices 16w), S0/1/4/8-way original S2
cycles ratio vs own S0, 4way: 10 reads 8gb 0.279, 16gb 0.299; 50 reads 0.516, 0.456; 100 reads 1.031, 0.923; 500 reads 1.092, 1.022. 1way/8way: 100/8gb 1.056 both; 500/8gb 1.119 both; 500/16gb 1.044, 1.050. 4way is best or tied in every row. flip: 8gb flips between 50 and 100 reads, 16gb between 100 and 500. the 10 and 50 read rows use short-read files; 100/500 use the long-read file, so the reads axis is confounded (read count, length and total bases move together).

### E10. long-read scaling (longread_scaling csvs, 8gb, laptop.cfg, S0 vs 4way)
long_10/25/50 reads, bases 0.346M/0.900M/1.869M. S0 cyc 94.1, 200.5, 346.8; 4way 66.2, 166.6, 331.9. ratios 0.703, 0.831, 0.957. joined with 100 reads (1.031, 4.7M bases) and 500 (1.092, 25.4M bases) from E9. flip lies between 1.87M and 4.7M bases. read length is not the sole driver (10 long reads still wins 30%).

## 2. classification of results

positive (cache helps, in cycles):
- E2 on 8gb/16gb/103gb at 50 reads: 1.83x / 2.05x / 1.97x for 4way; E3 same on desktop/orion cfgs; E9 at 10-50 reads on 8/16gb (about 1.9x to 3.6x); E10 at small long-read counts (up to 1.42x).
- caution: 1-way and 16-way original S2 get nearly the same speedup as 4-way (8gb 1.81x vs 1.83x), which is odd if the cache itself were the source (see open question 1).

negative (cache hurts):
- E2 50mb (0.85-0.91x); E4 all variants at 2000 reads (1.28x-1.39x slower); E9 at 100 reads/8gb and 500 reads on both DBs; E10 past about 4.7M bases; E1 wider is worse.
- E8 65536-set spike (+1% to +6% depending on DB), a localized loss.

null:
- E5, E6 (hardware llc associativity, 50mb/8gb/16gb): no effect, under 1% noise.
- E8 size axis outside 65536: flat to within 0.7% of per-DB median. capacity buys nothing.
- E8 vs S0 on 50mb: sizes tie or lose.

mixed or modelling-sensitive:
- E3: hardware size effect real on 8gb (1.65x-1.94x) but not monotone in cache size.
- E7: flat l3 is slower than nuca; a modelling choice that moves results by 17-31%, unexplained.

## 3. corrections and retractions already logged

1. step 20 "comma-joined -c is the fix" retracted in steps 22-24 (it triggers hetero-core config).
2. step 38-39 "baseline" row was an S2 binary, not no-cache (step 40).
3. initial ~4 hour per-DB load extrapolation retracted in step 44 (measured 4x scaling, not 150x).
4. step 46/50: suspected hang of the 2000-read job was a false alarm; slowness was long-read composition (2000-read subset mean length 5.1x the file mean).
5. step 53: 1way/8way wall-clock invalidated by concurrent jobs; step 57: second confound, whole-batch drift (about 14 vs 8 s per Mcycle). charts deleted and rebuilt.
6. step 60: wall-clock (elapsed_s) is simulator speed, not program speed. headline numbers moved to cycles. the "1-way fastest" wall-clock finding retracted.
7. 2026-09-11 16:20: claim that the 2x win was a "small-workload artifact reconciling with the real-hw null" retracted; the 2000-read run used the 50mb DB so it only strengthens the small-DB loss. the large-DB-at-large-reads question was left open (partly addressed later by E9/E10).
8. size sweep iteration 2 "linear init cost" mechanism overturned when 262144 and 1048576 reverted; replaced by "hash artifact" (itself weak, see open question 2).
9. 2026-09-15 21:52: spike magnitudes +4.4% / +10.2% were instruction deltas mislabeled as cycles; correct values +2.5% / +6.0%.
10. iteration 2: "width curve is gradual" retracted by agent E (width is flat then a step at 4w to 8w).
11. 2026-09-19 audit: (a) fig14 mixes workloads (50mb/103gb on 10 reads, 8gb on 50 reads); size_sweep_8gb_peer csv is a byte-identical copy of the 8gb rows, so no independent peer ladder exists; (b) 16gb ladder (+1.0%) was left out of the verdict, so "3-for-3" should read 3 of 4 DBs clearly; (c) flatl3 l3_hit_pct wrong for nuca rows; (d) 103gb csv and its peer copy are duplicates; (e) last two 50mb size rows had blank l1d_hit/nuca_hit (tail script lacked a parsing block, rows recovered by hand).
12. 2026-09-19 design correction: the step-0 claim that the noatomics-4way binary "is already the 262144-set point" is wrong. width-sweep binaries are the ORIGINAL S2 (4,096 sets, 24B entries, lru, static thread_local, low-bit index, no sizing formula). sizepin binaries are the CURRENT design (calloc heap, 16B entries, round-robin eviction, murmur index, sizing formula). H4's "formula lands on 262144" concerns the current design only.

## 4. what the simulator models in this project, and what it does not

knobs actually used (from cfgs):
- core: meteor_lake_pcore interval model, single core. frequency per cfg: luna 2.1GHz (base, not turbo), desktop 3.7, orion 2.2, laptop 3.2. rob, width, branch predictor were never retargeted to any real chip.
- l1i: luna 32K 8-way (sysfs real); desktop/laptop 32K 8w; orion 64K 4w (unverified, ARM TRM typical).
- l1d: luna 48K 12-way; desktop/laptop 32K 8w; orion 64K 4w.
- l2 private: luna 2048K 16w; desktop/laptop 512K 8w; orion 256K 8w.
- llc: modelled as NUCA per-core slices (levels=2). luna 1125KB slice 15-way 1200 sets address_hash=mod; desktop 5461KB slice 16w; laptop 2048KB 16w xor_mod; orion 342KB 16w (associativity is a placeholder). with -n 1 the working capacity the core sees is one slice, not the aggregate 105MB. the flat-l3 cfg (E7) is the only run with the aggregate 107520KB as one bank.
- replacement_policy: lru everywhere (meteor default). real sapphire rapids llc policy is adaptive and not modelled. sniper's mplru exists but was never run.
- prefetchers: never configured in the repo except prefetcher=none in the flat-l3 overlay. the l1/l2/nuca prefetcher settings inherited from the meteor base were never inspected in the log. whether hardware prefetch is active in the nuca runs is unknown from the repo.
- dram: inherited dram_configs/ddr4_2400.cfg, never measured on luna. nuca tag/data latency (15/20) are placeholders from the meteor base.
- tlb/mmu: baseline chain pagetable model; one early sanity check showed 0 va-pa violations; page-walk and dram-read counters checked once (iteration 2) and found negligible at the 65536 spike.
- address hash: mod for non-power-of-2 sets, xor_mod otherwise.

cannot model or not modelled:
- multithreading and contention (every run -n 1, -p 1). production numbers (32-96 threads, shared cache, atomics, numa, tlb) are out of scope. the noatomics fix matters only for threaded builds.
- real arm/orion behaviour (only x86 core with orion-sized caches). dynamoRIO/ARM route paused.
- real prefetch behaviour, real dram timing, real llc replacement.
- transparent hugepages and page-cache state. all simulated instructions include the DB load phase.
- io and the real classify pipeline thread structure (the later stock-to-S15 wins in project memory were pipeline/load/hugepage fixes and are not simulated here).
- runtime scale: about 230 KIPS detailed; 2000 reads took 12.4-15 hours per variant, so 10,000 and full-file (104,832 reads) runs were dropped.

## 5. open questions

1. confounded baseline in E2/E3/E9/E10. S0 (kraken2-src-baseline) is a different source snapshot from the fresh-based S2 binaries (step 52: different line wrapping, fresh tree carries later S-series commits). S0 instruction counts grow with DB size (35.8, 68.1, 77.3, 102.9M at 50 reads) while the cache variants sit near 52M on both 8gb and 16gb, and 1-way (only 4,096 entries) wins as much as 4-way. a tiny cache cannot plausibly remove about 16M instructions of lookup work in 50 reads. my inference (not in the log): much of the "win" at small read counts may be a loader or other code difference between S0 and the fresh tree, amortized away as reads grow, which matches the flip with total bases in E9/E10. needs a control: S0 built from the same tree as the cache builds, differing only by the cache.
2. is the 65536 spike a hash artifact? the log's "same workload file" explanation is contradicted by its own audit (8gb/16gb ladders used 50reads, 50mb/103gb used tiny_10reads). instructions rise about 10% at the spike, more than an index-distribution effect would usually cost. the build-diff check of sizepin-65536 vs its neighbours was flagged and never done.
3. no true S0 for the size ladder on 8gb/103gb, so "capacity does nothing on large DBs" is a flat curve, not a comparison against no-cache.
4. width sweep (original S2) and size sweep (current S2) are different designs; no run compares them under identical workload and DB.
5. 103gb never ran past 50 reads in the width study; 8gb/16gb flip by 100-500 reads but 103gb is unknown. E4 (2000 reads) covered only 50mb.
6. is the hardware llc really irrelevant? at -n 1 the shared level is one 1.1MB slice and l2/nuca hit rates stay under about 2%. a null there says little about a real 105MB llc seen by a threaded run. flat-l3 (E7) was slower, unexplained (set count, latency model, or prefetch).
7. no sniper cycle count was ever compared against a perf measurement on the same binary and DB. sim speedups (up to about 2x) sit against the real-hw null (commit 84436dd, T>1) and the later finding that the cache was not the cause of the real stock-to-S15 speedups.
8. prefetcher state in the meteor base unknown; dram model ddr4_2400 placeholder; nuca latencies placeholders. none of these was swept.
9. reads axis stays below production: largest runs 2000 reads (50mb only) or 500 reads (8/16gb).
10. orion and edge devices: config-only stand-in; real arm trace via dynamoRIO paused.
11. the S2Entry size in the current tree: the log says 16B for sizepin; project memory says 24B with free padding. affects the "65536 x 4 x 16B = 4MB" arithmetic.
12. no run covers eviction policy (round-robin vs lru vs mplru vs adaptive). the thesis 1 core claim (biology-aware eviction) has zero sniper data.
