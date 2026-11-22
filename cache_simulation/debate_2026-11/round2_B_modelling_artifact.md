# round 2, agent B: the null is a modelling artifact

position: the sniper setup used so far could not have shown a hardware or software cache win even if one exists, and it also produced fake wins. so the whole set of runs is uninformative in both directions. sources re-read: the three round 1 reports, configs/luna.cfg, laptop.cfg, hw_assoc/README.md, and the csvs hwsize_comparison, flatl3_comparison, laptop_sweep, longread_scaling_4way and _S0, cleanstart summary_all. nothing run.

i argue this as hard as the data allows. section 7 lists what the data forces me to concede.

## 1. -n 1 gives one nuca slice, about 1 percent of the real llc

proof: configs/luna.cfg, block [perf_model/nuca], lines "cache_size = 1125" and "associativity = 15". the file's own comment splits 107520 KB over 96 cores. every old run was -n 1 -p 1 (round 1 A, section 0). cleanstart steps 4 and 5 show the effective sim.cfg for -n 1 carries a single 2048 KB slice for the laptop config.

size: 1125 KB / 107520 KB = 1.05 percent of luna's real llc. desktop slice 5461 KB of 32 MB, orion 342 KB. so every "hardware llc" run modelled a 0.3 to 5 MB last level, not the 32 to 105 MB one the thesis is about.

what it hides: any idea about llc size, topology or llc-aware sizing. the hw_assoc sweep (E5, E6) varied associativity of a 1.1 MB slice that sees 0.2 to 0.4 percent of loads (nuca_hit_pct 0.2 to 0.37 in longread_scaling_S0). a 0.3 percent spread (4523.2 to 4537.9M cycles at 500 reads) is exactly what you get when the level under test serves 3 loads in 1000.

the one run at real capacity is configs/luna_flatl3.cfg (107520 KB, one bank). it came out 1.307x slower on 50mb and 1.166x on 8gb with identical instructions (35.8 and 68.1 M, flatl3 csv). identical instructions and l3 hit 0.02 and 0.11 percent mean the whole delta is model latency and set-count behaviour, not caching. a model artifact worth 17 to 31 percent sits next to the sub-1 percent effects being hunted.

## 2. latency does not scale with size

proof: luna.cfg says nuca data and tag latency are "left at meteor_lake_pcore's own placeholder values"; cleanstart step 5 states latency does not scale with cache size. flatl3 uses the same 15 tag plus 20 data cycles for 107 MB as for 1.1 MB (round 1 A, E7).

size of the flaw: a real 105 MB sapphire rapids llc hit is about 70 to 100 cycles at 2.1 GHz (my estimate from published sapphire rapids latency, not measured on luna; [guess]). the model charges 35. so llc hits are priced at roughly 0.35 to 0.5x. in a size sweep this biases toward bigger. in a "does adding a software cache that avoids llc/dram trips help" test it biases against the cache, because the avoided trip is cheaper than real. direction depends on the experiment, which is the point: the sign cannot be trusted.

## 3. dram is uncalibrated and the window is dram-light

proof: cleanstart README: dram 45 ns, 57.6 GB/s, sniper default (ddr4_2400). real luna is ddr5, 4 of 8 channels populated per socket (round 1 B). 45 ns at 2.1 GHz = 95 cycles; a loaded ddr5 miss on this box is more like 110 to 150 ns = 230 to 315 cycles [guess].

quantify the miss-penalty error: roughly 2.4 to 3.3x too cheap. the memory term in cycles: cleanstart 1-core 50 reads 8gb has about 0.81M dram reads (round 1 B) in 373.3M cycles. 0.81M x 95 = 77M cycles if fully serialized, so at most 21 percent of cycles are dram, less with overlap. so in these windows the program is mostly compute (ipc 1.3 to 1.8, cache hit rates 99 percent at l1d). even a perfect cache that removed 5 percent of dram trips moves cycles under 1 percent. the instrument is dominated by instruction count, which is the thing the binaries differ in (section 5).

real kraken2 at production is memory-bound at 103 GB (perf: lookup share 19.5 percent on 50mb, higher on big dbs, round 1 B; S9/S16 prefetch wins are only on 103gb). the sniper windows never reach that regime.

## 4. windows are tiny and dominated by startup and cold state

proof (windows): 10, 50, 100, 500 reads; 91,372 bases at 50 short reads, 0.35M to 1.87M bases for long_10/25/50, 4.7M and 25.4M at 100 and 500. production is 1e5 reads, 1e8 bases and up. 2000 reads took 12 to 15 hours per variant (E4), so nothing larger exists.

proof (startup): the simulated instructions include the db load phase (round 1 A, section 4). tiny_10reads on 50mb is 23.9M instr for S0; 50 reads is 35.8M. so most instructions in the 10 and 50 read cells are not classification. round 1 C estimates cleanstart startup at only about 15M of 125M for the long sup reads, and i accept that for those files. for the short-read files used in E2, E3, E9 the fixed share is large (my estimate over half; derive properly from a zero-read run, which was never done).

proof (cold llc, the strongest point): real llc = 107520 KB / 64 B = 1.68M lines. unique_cache_lines in the runs: 76K (50mb, 50 reads), 186K (8gb, 50 reads, S0), 713K (long_50 S0), 1.4 to 2.3M at 100 reads (round 1 C). so the 50-read cells touch 5 to 11 percent of the real llc once. a cold cache with compulsory misses cannot reward or punish a replacement or sizing policy. you need touches of at least 10x capacity (about 17M distinct-line touches, thousands of long reads) before steady-state hit rates exist.

what it implies for the sign flip: the 4way/S0 ratio goes 0.28 at 10 reads to 1.09 at 500 (laptop_sweep, E9). a conclusion that flips sign across a 50x window change is a window-dependence measurement, not a cache property.

## 5. binary lineage confound on S0 (a fake win, and it contaminates every ratio)

proof: command log step 56 says S0 = kraken2-src-baseline, a different source snapshot from the fresh-tree S2 binaries; the patch script's text asserts failed on baseline. from the csvs:

- hwsize_comparison, 8gb, 50 reads: S0 68.1M instr and 186,524 unique lines; 4way 51.9M instr and 64,091 unique lines. same reads, same db. a 3x drop in unique lines and a 24 percent drop in instructions cannot come from a 4096-entry per-thread lookup cache; unique lines should not fall at all because every k-mer table line must still be fetched at least once. so the lineages differ in load or parse code.
- laptop_sweep, 8gb, 10 reads: S0 16.3M instr, 18.3M cycles; 1way 7.3M instr, 5.1M cycles. 1way is a 4096-entry cache and wins 3.6x with half the instructions. impossible as a cache effect.
- round 1 C: instruction gap S0 minus 1way is -2.4, +16.4, +25.7, +34.1M for 50mb, 8gb, 16gb, 103gb. it scales with db size, like a load-path difference, not a lookup path difference.
- width and size independence: 1way, 4way, 16way give 28.6, 28.3, 28.9M cycles on 8gb; the size ladder 128 KB to 64 MB gives 27.9M at every point. a real cache effect would move.
- real hardware ablation (s6 to s15): the 4-way cache contributed nothing (11.06 vs 11.10 s).

consequence: the headline "2x win on big dbs" is a lineage artifact, and the "loss at 500 reads" ratio is also contaminated. the only apples-to-apples cell family is the sizepin ladder (same current-tree binary, only set count changed) and it is flat except one hash spike. so the clean runs are null and the dirty runs have a win, which is what an artifact looks like.

## 6. no prefetch, no tlb validation, no contention, no calibration

- prefetch: cleanstart README: none; luna_flatl3 sets prefetcher = none; the l1/l2 prefetch state inherited from meteor was never inspected (round 1 A). the s9 and s16 real-hardware wins are software prefetch and latency hiding on 103gb. a model with no hardware prefetch and no software-prefetch patches in the noatomics binaries cannot rank latency-hiding ideas. effect size on real hw: S9 about 12 percent, S16 10 percent on 103gb.
- tlb: sniper l1 tlb defaults (4-way) vs zen 3 fully associative; huge pages and thp (S14 gave 16gb 11.9 to 9.15 s, 23 percent) are not modelled at all. for random access over 8 to 103 GB, tlb walks are a first-order cost that the model leaves out. also icache modelling was off in every old run: switching it on halves ipc on /bin/true (0.87 to 0.42, cleanstart step 5), so all old ipc values are inflated and extra cache code was under-penalised.
- contention: -p 1 only. the thesis is about 32 to 96 threads sharing one llc, per-thread caches, atomics. 4-core cleanstart runs show only 2 to 3 threads do work and 2 of 14 launches deadlocked; 8-core rows do not exist.
- calibration: no sniper number was ever compared to perf stat on luna for the same binary, db and reads. so the error bar of the model is unknown, not small. the only data point against the real world is the opposite sign: sim "wins" up to 2x, real hardware null (S6 ablation; S3.4).
- replicates: one run per cell; spreads of 0.3 to 0.9 percent (E5) cannot be classed as noise or effect.

## 7. what i concede (the data forces it)

1. the software cache null is partly real and independent of the simulator. real perf hit rates are under 2 percent, 0.40 to 3.58 percent after the murmur fix (S4.0), and wall clock was null on real hardware (S3.4, S6 ablation). a hit rate is a property of the access trace, which sniper replays faithfully. a perfect simulator would not rescue a 3 percent hit rate. agent A is right about this and my thesis does not apply to the software cache.
2. my artifact thesis is strongest for the hardware llc-aware and llc-size ideas and for any claim of a positive win. it is weakest for "software lookup cache has low reuse".
3. the sizepin ladder and the hw_assoc sweep are internally clean (same binary, one knob). within their own limits they are valid nulls. their limits are sections 1 to 4, not arithmetic. round 1 C already showed the csv arithmetic is clean (189 of 190 rows within 0.015 ipc), so i do not claim a computation bug.
4. the cleanstart note that the model is "dominated by startup" is overstated for long reads (round 1 C: about 15M of 125M). my startup point holds for the short-read files only.
5. the cold-llc quantification in section 4 uses unique_cache_lines as a proxy for lines touched; it excludes the load phase and is approximate.
6. -n 1 slice (about 1.1 MB) is coincidentally near the per-thread share of 105 MB across 96 threads (1.1 MB). but the hash table is shared read-only across threads, so effective capacity per thread is much larger than 1/96. i do not rely on this either way.

## 8. what a correct experiment looks like

goal: answer "does an llc-aware or adaptive software cache help kraken2 on luna" with a model whose error is known.

step 0, calibrate first (blocking). on luna, same binary (S19-free stock S0, then one patched build from one source lineage), db 8gb, 1 thread, 1,000 long reads. collect perf stat: instructions, cycles, l1d/l2/llc load misses, dtlb load misses, dram bytes. run sniper on the same input with the same ROI. accept the model only if instructions match within 2 percent, cycles within 15 percent, llc misses within 20 percent, dtlb misses within 25 percent. if it fails, fix inputs in this order: dram latency and bandwidth (measure with a pointer chase and stream on luna, replace ddr4_2400 defaults), nuca latency (measure 1.1 MB vs 105 MB pointer chase, set tag and data accordingly), tlb (match sapphire rapids l1 and stlb sizes, add page size 4 KB vs 2 MB), prefetchers on, icache on.

step 1, one lineage. rebuild S0 and all variants from one commit, differing by one macro (cache on or off, set count, way count). never compare across kraken2-src-baseline and fresh trees again. verify with a zero-read run that load-phase instructions are identical across binaries; any gap there is the confound.

step 2, real llc. do not use -n 1 slices. model the llc as one shared 105 MB 15-way bank with measured latency (about 70 to 100 cycles) plus sniper's shared-cache (shared_cores = N) configuration, or run -n 8 to 16 with total llc preserved and per-slice scaled (cleanstart already does this and holds total at 16 MB). include a hardware prefetcher in l2. use sapphire rapids core parameters (rob 512, width 6) rather than meteor lake defaults, or at least check ipc against perf.

step 3, window. use roi markers around the classification loop only, fast-forward the load phase with cache warming, then simulate a detailed window of at least 20M to 50M lookups (thousands of long reads worth) after a warm-up that touches at least 10x llc capacity (about 17M distinct lines). if wall time is the limit (about 230 KIPS detailed), use sampled simulation: 10 to 20 windows of 50M instructions each, spread through a 100k read run, cache-warmed between windows, report mean and spread. this is the only way to see steady-state hit rates at production scale.

step 4, metrics. report per-region cycles, llc mpki, dram reads, dtlb walks, software-cache hit rate and eviction counts, not just total cycles. report a no-cache and a perfect-cache bound on the same lineage so every effect can be expressed as a fraction of the available headroom (for kraken2 on 50mb the lookup share is 19.5 percent, so the ceiling is 1.24x; on 103gb it is larger and unmeasured).

step 5, replicates and controls. at least 3 runs per cell with perturbed trace start offsets; include a sham control (cache code present, never hits) to separate code-size cost from cache benefit; include one known-positive control, such as software prefetch (S16), where real hardware gave -10 percent on 103gb. if the calibrated model cannot reproduce S16's win and the S6 null, it cannot be trusted for adaptive eviction.

step 6, threads. only after steps 0 to 5 pass, add -n 8 to 16 with the real kraken2 thread pool to see shared llc contention.

## 9. rebuttals

to A (the null is real, no reuse): half right. a hit rate of 0.4 to 3.6 percent is real, and that kills the software cache. but "no reuse" was inferred from windows of 10 to 500 reads that touch 5 to 100 percent of the llc once. reuse across 1e5 reads of a shared table was never observed in any window, so the no-reuse claim is a statement about the window, not about kraken2. and A's own list shows the sim produced a 2x win that A explains as a lineage effect; if lineage can fake a 2x then lineage can hide a 5 percent. A cannot call the sim valid for nulls and invalid for wins.

to C (wrong layer): right that the s6 to s15 wins were pipeline, load and hugepage fixes, and that the llc topology ideas matter at 32 to 96 threads where the sim has no representation. but "wrong layer" is the same claim as mine seen from the other side: the layer that matters (shared llc under contention, dram, tlb, prefetch) is the layer the model leaves out. so C's conclusion should be "cannot decide" rather than "do not model", and the calibrated experiment in section 8 is how to find out cheaply whether the layer is wrong. if step 0 shows sniper cannot hit the perf numbers within the stated bands, then C wins and the next move is real-hardware perf with intel pqos/cat llc partitioning, not more sniper.

## 8-line summary

1. -n 1 gave a 1.1 MB nuca slice (luna.cfg nuca cache_size=1125), about 1 percent of the 105 MB llc; every hardware-llc null is about a different cache.
2. nuca latency is a placeholder (15+20 cycles) for any size, dram is ddr4_2400 default; flatl3 vs nuca differs 17 to 31 percent with identical instructions, larger than any effect hunted.
3. windows of 10 to 500 reads touch 5 to 100 percent of the llc once (76K to 2.3M unique lines vs 1.68M llc lines), so no steady-state reuse was ever measured.
4. S0 is a different source lineage: 8gb 50 reads shows 186K vs 64K unique lines and 68.1 vs 51.9M instr; 1way beats S0 3.6x at 10 reads with half the instructions. the 2x win is an artifact, so wins and nulls are both untrustworthy.
5. no prefetch, no tlb or hugepage model, no contention (-p 1), icache off in old runs, no replicates, no perf calibration anywhere.
6. concession: software lookup cache null is real (hit rate under 4 percent on real hardware, S6 ablation); my thesis applies to llc-aware and adaptive ideas, not to that.
7. correct experiment: calibrate against perf stat on luna first (instr 2 percent, cycles 15 percent, llc misses 20 percent), one source lineage, shared 105 MB llc with measured latency, roi plus sampled windows of 20M to 50M lookups after 17M-line warm-up, sham and S16 positive controls, 3 replicates.
8. rebuttal: A's no-reuse is a window statement; C's wrong-layer is my point restated, and the calibration step decides between us cheaply.
