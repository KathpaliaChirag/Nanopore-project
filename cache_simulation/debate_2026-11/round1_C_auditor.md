# round 1, agent C (skeptic/auditor): how far can the sniper results be trusted

scope: every csv in cache_simulation/measurements and cleanstart/measurements, both command logs, all hardware cfgs (luna, laptop, desktop, orion_sizes, luna_flatl3, hw_assoc/*, cleanstart_laptop). read-only. nothing run on luna.

verdict up front: the arithmetic in the csvs is clean, but most experiments cannot answer the hardware-cache question. they held the llc at a single 1.1 to 2 mb slice, used workloads with almost no data reuse, and compared binaries that differ in more than the cache. "no positive result" is mostly a statement about the instrument, not about the idea.

---

## 1. recomputation from raw rows

method: for every csv row, instructions_M / cycles_M compared against the ipc column. 17 files, 190 data rows.

- 189 of 190 rows agree within 0.015 ipc. the one flag is laptop_sweep row 3 (10 reads, 8gb, 1way: ipc 1.45 vs 7.3/5.1 = 1.43). that is rounding of a 5.1M cycle count to one decimal, not a real mismatch.
- cleanstart: sim_time_max_fs x 3.2 GHz reproduces cycles_M to within 0.1 percent on all 17 rows. so cycles are really simulated time.
- wallclock_s vs elapsed_s agree within 2 s everywhere. 4-core cleanstart rows differ by up to 20 s (multi-process startup).

headline results, recomputed:

| headline | raw rows | recomputed | flag |
|---|---|---|---|
| "4way about 2x faster than S0 on big dbs" (final_fair_batch) | 8gb S0 51.8M vs 4way 28.3M cycles; 16gb 60.7 vs 29.6; 103gb 94.3 vs 47.8 | 0.546x, 0.488x, 0.507x. arithmetic correct | instruction counts also differ by 25 to 33 percent (68.1 vs 51.9; 77.3 vs 51.9; 102.9 vs 70.3), see 2c |
| cache loses on 50mb | S0 24.4 vs 4way 26.8 | 1.098x slower. correct | none |
| 2000 reads, 50mb | S0 6354.0M cyc, 10053.7M instr; 4way 8159.1M, 11829.2M | cycles +28.4 percent, instructions +17.7 percent, ipc 1.58 to 1.45. correct | cycles grow faster than instructions, so the sw cache lowers ipc (unique lines 1.62M to 2.28M, l1d hit 99.04 to 98.49) |
| hw associativity null (hw_assoc_sweep, bigdb) | 500 reads: 4523.2 to 4537.9M across assoc 1..30 | spread 0.32 percent; 50 reads spread 0.0; bigdb 8gb 51.7 to 51.8M | correct. single run per cell, no replicates, so noise floor unknown |
| laptop_sweep flip | 8gb 10 reads 4way/S0 = 5.1/18.3 = 0.279; 500 reads 4310.7/3946.5 = 1.092 | correct | workload axis confounded (log admits this) |
| longread_scaling | 4way/S0 = 66.2/94.1 = 0.704; 166.6/200.5 = 0.831; 331.9/346.8 = 0.957 | correct | S0 and 4way are different source lineages |
| flatl3 | 50mb nuca 24.4 vs flat 31.9 = +30.7 percent; 8gb 51.8 vs 60.4 = +16.6 percent | correct; instructions identical | flat is a 107 mb cache, slower, with l3 hit 0.02 and 0.11 percent. see 2b |
| size sweep 2048 to 1048576 sets | 8gb: 27.9M cycles at every size except 65536 (28.6M) | correct | identical to 3 digits across a 512x size range means the cache is not hitting meaningfully, see 2c |
| hwsize (desktop/orion/luna) | 50mb S0: 28.2 / 26.7 / 24.4 | correct | L1, L2 and slice all change together, not a one-knob sweep |
| cleanstart 1-core baseline | 9 rows, all sane | correct | 8gb faster than 50mb at same reads (373M vs 446M at 50 reads); the hash-table-fullness explanation is untested |

bookkeeping issues, mostly admitted in the logs but worth restating:
- size_sweep_103gb and size_sweep_103gb_peer are byte-identical, and size_sweep_8gb_peer is a byte-identical copy of the 8gb rows of cache_size_sweep. there is no independent "peer" confirmation.
- size_sweep_50mb last two rows have blank l1d_hit and nuca_hit (hand recovered).
- flatl3_comparison l3_hit_pct is 0 for both NUCA rows (parser bug).
- fig14 panels mix 10-read (50mb, 103gb) with 50-read (8gb) data.
- the 16gb size ladder never entered the H1 to H4 verdict and shows a much weaker 65536 blip (+1.0 percent vs +2.5 to +6.3).
- cleanstart is 17 of 27 planned rows: no 8-core rows, and 4c_r50_16gb is missing (hung).

---

## 2. modelling flaws, and whether each could hide a real hardware-cache effect

### 2a. -n 1 gives one nuca slice, not the full llc (most important)
evidence: cleanstart step 4 and 5: with -n 1 the effective sim.cfg has nuca cache_size = 2048, one slice, not the laptop's 16 mb. luna.cfg splits 105 mb into 1125 kb slices over 96 cores and every old experiment ran -n 1. so the simulated llc was about 1.1 mb for "luna", 5.3 mb "desktop", 0.33 mb "orion", 2 mb "laptop". the hw_assoc sweep varied associativity at a fixed 1125 kb. hwsize_comparison varied slice size, not real llc size.
could it explain the null: yes, strongly. a size-aware or topology-aware llc idea cannot show a benefit when the llc is about 1 percent of the real one.
the flat l3 run (107 mb, one block) is the only run at real capacity. it came out worse (+16 to +31 percent) with 0.02 to 0.11 percent hit rate, which is itself a warning (2b).

### 2b. cache latency does not scale with size, and topology choice moves cycles by 17 to 31 percent
evidence: cleanstart step 5 states the first part. luna_flatl3.cfg uses the same 15+20 cycle placeholder for a 107 mb bank as for a 1.1 mb slice. luna.cfg says nuca latency is an unmeasured meteor_lake placeholder.
effect: bigger is never penalised by latency, so a size sweep is biased toward bigger. even so, no positive result appeared, so this flaw did not hide a win. but flat vs nuca differs by 17 to 31 percent with identical instructions and almost no hits, far larger than the sub-1 percent effects being searched for. the model has artifacts bigger than the signal until latency is validated.
could it explain the null: partly, as added model noise.

### 2c. two different binaries compared: S0 vs variants differ in more than the cache
evidence:
- log step 56: S0 is kraken2-src-baseline, a different source snapshot from the one the variants were built on (the patch script exact-text asserts failed against baseline). 1way was built from a pristine parent of S1.1, noatomics widths from the fresh tree, and S1 to S5 were committed straight into the fresh tree history.
- instruction gap S0 minus 1way grows with database size: 50mb -2.4M (S0 fewer), 8gb +16.4M, 16gb +25.7M, 103gb +34.1M. a pure lookup-path add-on cannot save instructions that scale with db size.
- width independence: 1way (96 kb per thread), 4way (384 kb), 16way (1.5 mb) give 28.6 / 28.3 / 28.9M cycles on 8gb. the size sweep from 128 kb to 64 mb of cache gives 27.9M at every point. if the cache caused the 2x, size and width would matter.
- the later project note (s6 to s15 ablation) says the 4-way cache was not the cause of the speedup.
conclusion: the "2x on big dbs" is a source-lineage artifact (load path, startup, other patches), not evidence for a software or hardware cache. it was reported as the positive headline, then "reversed" by the laptop and 2000-read rows, which made the whole line look contradictory.

### 2d. two different S2 designs mixed
evidence: log "CORRECTION + measured cache sizes". fair-batch, 2000-read, laptop_sweep and hw_assoc 1/4/8/16-way binaries are the original S2: 4096 sets, static thread_local, 24 B entries, lru, raw low-bit set index. sizepin binaries are the current design: calloc, 16 B entries, round-robin eviction, murmur set index, sizing formula. width sweeps and size sweeps are not the same cache. the original has the weak index hash that s4.0 later fixed for an 8.9x hit-rate change, so width and associativity results on old binaries mostly measure conflicts in a broken index.
could it explain the null: yes for the software associativity story.

### 2e. tiny workloads vs production
evidence: 10 to 500 reads: 8k to 372k bases at 10 reads, 4.7 to 5.3M bases at 100. production is 1e5 reads and 1e8 to 1e9 bases. detailed sniper runs about 200 kips (about 1 hour per 50 reads, 12 hours for 500).
effect: reuse of table lines needs many reads. unique_cache_lines (1.4M to 2.3M at 100 reads) is about the count of lookups, so almost nothing is touched twice; llc hit stays at 0.2 to 0.4 percent of loads. the 4way vs S0 sign goes from -30 percent to +9 percent just by scaling 10 to 500 reads. the read-count axis was confounded with read length in laptop_sweep (admitted) and only partly fixed in longread_scaling. the cleanstart axis is uneven (10 to 100 reads is 0.37 to 5.3M bases, 14x).
could it explain the null: yes. in a no-reuse regime no cache has anything to retain. it cuts both ways: production may have more repeated minimizers and was never measured.
extra doubt: cleanstart log says 10-read runs are "dominated by fixed startup work". the numbers say otherwise: marginal cost is about 297 instructions per base ((1583.6M - 677.5M) over (5.26M - 2.21M) bases), so 372k bases is about 110M of the 125M instructions. startup is roughly 15M. drop that explanation.

### 2f. no hardware prefetchers
evidence: cleanstart README says none; luna_flatl3 sets prefetcher = none. s5.0 software prefetch patches exist in the fresh tree but not in the noatomics binaries.
effect: db load and read parsing are sequential and would normally be prefetched. random hash lookups would not be. 
could it explain the null: minor. the random lookups dominate.

### 2g. config-only desktop and orion models
evidence: desktop.cfg and orion_sizes.cfg change cache geometry only, under meteor_lake_pcore timing (5.1 GHz defaults overridden to frequency only, rob, branch predictor, widths all meteor lake). orion associativities are unverified placeholders (the 8-way l2 claim was already retracted). an x86 binary under an x86 core model is not an a78ae.
effect: these show size sensitivity of the x86 model, not of orion or a ryzen 5600x. orion s0 50mb ipc 1.34 beats desktop 1.27 despite smaller l2 and slice, so l1 size (64 vs 32 kb) dominated and the llc did not matter.
could it explain the null: no, it limits claims about edge devices only.

### 2h. dram fixed at 45 ns / 57.6 GB/s (ddr4_2400 default)
evidence: cleanstart README, luna.cfg ("DRAM config is entirely inherited"). real luna is ddr5. big-table runs are dram bound (about 0.8 to 1.1M dram reads per 50 reads), so cycles are set by this number, memory-level parallelism and the page-walk model, none measured. a cache gain is a fraction of a dram-bound runtime.
could it explain the null: yes. when dram latency dominates and is unvalidated, small cache effects are invisible and their sign is not trustworthy.

### 2i. wallclock vs cycles
evidence: log step 57: same job is 1.8x faster in seconds per simulated Mcycle across batches (os page cache). the team then chose cycles, correctly. older narrative text quotes wall-clock "2.05x faster" (steps 41 to 44), which is simulator speed, not target speed. csv cycles are fine (section 1).
could it explain the null: no. do not cite the old wall-clock sentences.

### 2j. hangs and multicore
evidence: cleanstart steps 12, 13, 15. 2 of 14 four-core runs deadlocked at startup (0 cpu), cause unknown; 0 of 9 one-core. 8-core group not done. reported cycles are the slowest core; ipc is aggregate over cores (3.64 at 4c r100 is a sum). only 2 to 3 threads do real work (73/27 split), so core scaling reflects kraken2 batching and sniper sync, not cache. l3 hit share falls from 0.45 to 0.26 percent going 1c to 4c, unexplained.
could it explain the null: for the shared-llc idea, yes. the interesting llc effects need real multi-thread contention, which every old -n 1 run structurally cannot show (the log's own H3 conclusion says single-thread capacity sweeps are the wrong instrument).

### 2k. other
- single run per cell, no replicates. sniper is deterministic at -p 1 only in part (reader thread), so noise is unbounded. spreads of 0.3 to 0.9 percent in hw_assoc cannot be classed as noise or effect.
- icache modeling was false in every old run. cleanstart step 5: switching it on drops /bin/true ipc from 0.87 to 0.42. all old ipc values are inflated, and the software cache code and thread-local table footprint were under-penalised.
- tlb: sniper l1 tlb defaults (4-way) differ from zen 3 (fully assoc). tlb behaviour matters for random access into 8 gb and was not validated.
- no sim-vs-real calibration anywhere: no comparison of sniper ipc or dram reads against perf stat on luna for the same run.
- the 50mb db is nearly full, so absent kmers probe long chains and it behaves unlike the other dbs (log step 10, untested).

---

## 3. ranked reasons the results looked null or negative

1. the llc was not the size under test (2a). with -n 1 the nuca is one slice. only the flat run saw a real capacity. evidence: cleanstart sim.cfg check, luna.cfg header, llc hit under 0.5 percent everywhere.
2. the workload has almost no reuse at the tested scale (2e). unique lines about equals lookups, hw associativity moves cycles by 0.0 to 0.9 percent, the real-hardware null (commit 84436dd, under 2 percent hit rate, 3 dbs x 6 thread counts) agrees. this one is partly a genuine property of kraken2, not just an artifact, and is probably the true cause of the software-cache and associativity nulls.
3. dram and random access dominate and are unmodelled (2h). l1 hits 99 percent are non-table accesses; table accesses go to dram. no cache change beats an unvalidated 45 ns fixed dram.
4. the positive headline was a lineage artifact (2c). once it is removed there is no positive result to find or lose. it also contaminated every "cache helps on big db" sentence.
5. the software cache pollutes the hardware cache it was meant to help (section 1, 2000-read row): ipc falls, unique lines +41 percent, l1d hit -0.6 points. the combined hypothesis was tested with a 384 kb to 1.5 mb thread-local table against a 32 to 48 kb l1d, a worst case for pollution.
6. the original S2 index hash is poor (2d), so width and associativity binaries measure a broken index.
7. model artifacts larger than the signal (2b: flat vs nuca 17 to 31 percent, unvalidated latency, icache off in old runs, no calibration).
8. instrument limits: no replicates, hangs, 17 of 27 cleanstart rows, uneven read axis, mixed fig14 panels.

---

## 4. what must be redone before anything is publishable

must redo:
1. one binary lineage. S0, a cache-off variant of the same tree (constant switch), and cache variants, all from one git sha. report only within-tree differences. removes 2c.
2. full-capacity llc. make the simulated llc the real total for the single running core (one bank or all slices reachable), or run real multicore with the correct setup (baseline scheme plus -c general/total_cores=N, since plain -n does not set it). then redo the llc size and associativity sweeps. caution on cleanstart: the baseline name says L3-16MB, but its own step 4 shows 1-core runs get a 2 mb slice. recheck the 1-core rows before citing them as 16 mb.
3. latency model. measure luna l1/l2/l3/dram latency with a pointer chase, make latency a function of size in the config (or sweep it +-50 percent). validate by running one small workload natively under perf stat and under sniper and comparing ipc and dram reads.
4. icache modeling on and tlb set to the target in every run (cleanstart_laptop.cfg does this; every old csv does not).
5. workload at honest scale: a fixed total-bases ladder with equal read lengths and at least one point near 1e7 to 1e8 bases, using sampling (roi windows or simpoints) since detailed mode cannot run it whole.
6. replicates (3 per cell), or a documented determinism check, so 0.3 to 0.9 percent spreads can be called noise or effect.
7. multicore: fix the startup deadlock (try the parametric_baseline_Nc schemes per the log's hypothesis) and finish 4 and 8 cores; a shared-llc claim needs contention.

can be kept with caveats: the csv arithmetic, flat vs nuca as a warning about model sensitivity, size-sweep invariance as evidence the cache does not hit, the cleanstart S0 baseline once its llc size is restated.

drop from any paper or talk: the 2x speedup claim, the "50 reads artifact" reconciliation text, wall-clock speedups, orion numbers as edge-device evidence, "startup dominates 10-read runs", and the hash-table-fullness explanation until measured.

---

## 10-line summary

1. csv arithmetic is clean: 189 of 190 rows match ipc (one is rounding); cleanstart cycles match sim time within 0.1 percent.
2. the "4way 2x faster than S0 on big dbs" headline is a binary-lineage confound: S0 is another source snapshot, the instruction gap grows with db size, and cycles are the same for 128 kb to 64 mb of cache and 1 to 16 ways.
3. with -n 1 sniper instantiates one nuca slice (1.1 mb luna, 2 mb laptop), so no old run tested a real-size llc. this is the biggest reason a hardware llc idea could not look positive.
4. the workload has almost no reuse at 10 to 500 reads (unique lines about equals lookups, llc hit under 0.5 percent), and the real-hardware null agrees: probably a true property of kraken2 at this scale.
5. dram is a fixed 45 ns ddr4 default and table accesses are dram bound; cache effects of 1 to 5 percent are below the model uncertainty (flat vs nuca differs 17 to 31 percent).
6. two S2 designs were mixed (original 4096-set weak-hash vs current calloc/murmur), so width and size sweeps are not one experiment.
7. icache modeling was off in all old runs and there is no sim-vs-real calibration; orion and desktop runs are cache-size edits under an x86 meteor lake core.
8. cleanstart is the cleaner start but is 17 of 27 done, has 2 multicore deadlocks, and its 1-core runs also have a 2 mb llc despite the 16 mb name.
9. likely reasons for no positive result, in order: llc not the size under test, no reuse at tested scale, dram-dominated unvalidated model, lineage artifact, software-cache pollution.
10. redo before publishing: single-lineage binaries, full-capacity llc, measured latency plus calibration, icache and tlb on, honest-scale sampled workload, replicates, working multicore.
