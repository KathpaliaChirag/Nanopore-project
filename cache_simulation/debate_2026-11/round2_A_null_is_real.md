# round 2, agent A: the null is real (workload, not simulator)

assigned position: kraken2's table lookups give no cache organisation anything to win, so the null belongs to the workload. sources re-read: the three round-1 reports, measurements/*.csv, plan_paper/command_log.md, plan_paper/s6_s15_speedup_report_2026-09-24.md, plan_paper/track_a_pivot_debate_2026-08-30.md, cache_simulation/command_log.md. nothing run, nothing changed except this file.

## 0. first, what the data forces me to concede

my assigned wording was "near-zero reuse". that wording is FALSE and my own repo falsifies it. do not repeat it in the paper.

- M5 (dorado-kraken-research/README.md line 65): 32.8M unique minimizers in 351.8M lookups, so 90.7% of lookups have a repeat somewhere earlier in the run.
- S4.0 reuse-distance histogram (plan_paper/command_log.md, 2026-08-30, standard_8gb, T=1, 3,006,550 lookups): 54% of lookups are repeats. 81% of the repeats sit at distance 1e4 to 1e6 lookups (lt1e5 = 341,228 and lt1e6 = 978,748 out of about 1.62M repeats [arith: 0.54 x 3.0M]). so about 19% of repeats (roughly 10% of all lookups) are closer than 1e4.
- hit rate does climb with capacity: LRU 4-way to 64-way, 3.58% to 27.75% hit rate at 16K to 262K entries (command_log 2026-09-02 table). that is reuse being caught, not absent.

so the corrected claim I defend is narrower and, I think, stronger: **reuse exists but is long-distance and sparse in the wrong place. every cache that fits in the budget a cache must live in (L1d or L2 sized, or a per-thread software array) sees a hit rate too low to pay for its own probe, and the capacity that would catch the bulk of the reuse (1e5 to 1e6 distinct lines, 6 to 64 MB per thread) is already what the real LLC provides.** the null is a property of kraken2's access stream meeting realistic cache costs. it is not a property of sniper.

## 1. the argument in five steps, with numbers

### step 1: a cache wins only if hit_rate x (cost of a table miss) exceeds the cache's own probe cost

worked example. a software cache probe costs Tp. a table lookup that misses to DRAM costs Td (about 90 ns on a big db, a guess, not measured here). every lookup pays Tp. a hit saves Td. net per lookup = h x Td - Tp. break-even h = Tp / Td.
- if the cache array is L1-resident, Tp is a few ns and break-even h is a few percent. but an L1-resident array (under 32 KB, about 500 entries) has a tiny reach, and 81% of repeats are at distance 1e4 or more. hit rate stays near 0.
- if the array is big enough to reach those distances (4 MB at 64-way, 262K entries), it is itself larger than L2 on most chips, so each probe is a random L2/LLC access. Tp rises to tens of ns. at Tp = 30 ns and Td = 90 ns [guess] break-even is h = 33%. the best measured was 27.75%.
- measured, same session, standard_8gb T=1: 4-way 3.58% hit, -0.40% time; 8-way 6.22%, +0.19%; 16-way 10.65%, +0.90%; 32-way 17.68%, +2.02%; 64-way 27.75%, +3.86%. hit rate went up 7.8x and time got worse monotonically. the arithmetic above fits that shape: every extra hit is bought with a more expensive probe on all lookups. this is the mechanism, not coincidence.

### step 2: the real-hardware nulls need no simulator

- S6 ablation (s6_s15 report line 49): stock plus multi-file streaming with NO cache = 11.06 s and 14.48 s; same with the cache = 11.10 s and 14.55 s. perf cycles 174K vs 175K samples. the 13 to 20% "cache win" was a pipeline effect.
- S3.4 (full db x thread grid, 3 dbs x 6 thread counts x 3 runs, cv mostly under 1%): S0 = S2-baseline = S2-final within noise.
- S4.0 hash fix: 8.9x hit rate (0.4035% to 3.5758%), no wall-clock change. S4.0 also reversed the pinning eviction result (+25.2% to -3.9%), so there is no surviving eviction win either.
- S7, S11, S20 (prefetch batch, ring buffer, K2_B 16 to 64): null, within +/-0.6%.
- eviction policy: LRU vs round-robin at equal capacity is -0.40% wall, a real but sub-percent effect. that is the size of the whole eviction lever.

these are four independent real-hardware experiments on three dbs. none touches sniper.

### step 3: where the real time went says it is latency, not reuse

the wins that did land are S8 (pipeline), S10 (parallel pread load), S14 (2 MB hugepage table, 103GB 35 s to 13-20 s), S9/S16 (prefetch, -10% at 103GB, null on 8/16GB). every one removes waiting or setup. none removes distinct lines from being fetched. S16 hides the latency of the same DRAM misses by overlapping them. if lookups had capturable reuse, a cache would have beaten prefetch at 8GB. it did not.

### step 4: the simulator, read honestly, is consistent with this and with a cold window

- hw_assoc_sweep_bigdb (8gb, 50 reads): cycles 51.7 to 51.8 M across associativity 1, 4, 8, 15, 16, 30. spread about 0.2%. 16gb: 60.7 M in every row (0.0%). unique_cache_lines identical per db (186,524 and 200,411). l1d loads 13.97M, l1d hit 98.86%.
- nuca hit is 0.0064% to 0.0081% of loads on 8gb, against an L1 miss rate of 1.14%. so the LLC slice catches under 1% of what leaves L2. everything that gets past L2 goes to DRAM.
- cleanstart (9 of 9 one-core cells): L1d hit 99.09 to 99.37%, L2 hit 0.08 to 0.22%, L3 hit 0.38 to 0.49% of loads. under 1% of loads ever leave L1.
- software cache size sweep (8gb, 2048 to 1,048,576 sets): cycles 27.9 M at five of six sizes. 103gb: 15.1 M at five of six. 16gb 29.2 to 29.6 M. the one deviation (65536) is a hash artifact, +2.5% to +6.0%. capacity buys nothing across a 512x range.

what this shows precisely: the table lines that miss are first touches inside the window (cold), and reuse that exists is farther than the modelled LLC slice reaches. both readings agree with section 0. it does NOT show zero reuse, and I do not claim it does.

### step 5: why more and better engineering did not rescue it

- admission control (not eviction) is the one idea the Track A debate left standing: 63.4% of distinct minimizers appear once and take 29.9% of lookups (KRAKEN2_CHANGES.md:181, cited in track_a_pivot_debate line 52). that bounds the ceiling. if 30% of lookups are one-shot, then at best the cache can serve the other 70%, and 81% of those repeats are beyond 1e4. the product of those fractions with a probe cost near break-even leaves headroom of a few percent at most [arith, not measured].
- lookup share of cpu on 50MB is 19.5% (perf_s19: GetAt 12.5% + PrefetchIndex 7.0%). a free table gives at most 1.24x. a cache that catches 10% of lookups (the near-reuse slice) saves about 2% of cpu before paying its own probe. that is below the +/-0.6% to 4% noise floors in this project.

## 2. what would FALSIFY my position (be exact)

my corrected claim is: "no cache that is affordable in probe cost improves wall-clock or simulated cycles for stock kraken2 on any db at a production read count." it is false if any of these is measured:

F1. **hardware capacity sensitivity on real silicon.** use Intel CAT (pqos / resctrl) on luna to restrict classify to 2, 4, 8, 16 LLC ways at 32 threads on 8GB at 1.87M reads. if wall-clock changes by more than the noise floor (about 1%, cv under 1%) as ways drop, the LLC is capturing reuse and capacity/organisation matters. a flat line confirms my position. this is the single cleanest falsifier and has never been run.
F2. **capacity misses vs compulsory misses at production scale.** perf stat on S19, 8GB and 103GB, 1.87M reads, T=1 and T=32: count DRAM line fetches for the table divided by distinct table lines touched (needs the reuse-distance binary at production scale, not 3M lookups). if the ratio is well above 1 (say more than 1.5), lines are fetched, evicted, refetched: capacity misses exist and policy has headroom. if the ratio is near 1, every miss is compulsory and nothing helps. the sim row I would use today (DRAM about equals unique lines) is inference from percent-of-loads columns whose denominator I could not fully confirm, so treat it as a lead, not proof.
F3. **an L1/L2-sized software cache with hit rate above its break-even.** a 512-entry to 8K-entry array (fits L1/L2) with admission gating (1-in-n) at real thread counts showing hit rate above about 15% AND a wall win outside noise on 8GB at 1.87M reads. none exists; best L1/L2-sized result is the 4-way at 3.58% and null.
F4. **reuse-distance histogram at 1.87M reads on 103GB at 32 threads showing mass below 1e4.** S4.0 is T=1, 8gb, 3M lookups. if at production scale more than about 30% of lookups have distance under 1e4, an L2-sized cache has real material. open: week6plan itself flagged "not run by anyone" whether the shape generalises to 103GB and threads.
F5. **a simulator run that is not cold.** sniper at 1.87M reads is infeasible (about 230 KIPS, 2000 reads already took 12 to 15 h). a cheaper test: a trace-driven cache model (no timing) fed the real lookup address stream at production length. if its hit curve has a knee below the LLC share, the hardware question is alive.

if F1 and F2 both come back flat/near 1, the null is real and should be written up as a characterisation result.

## 3. rebuttal to B: "the null is a modelling artifact"

B (and C's modelling findings) have real points, and I concede them:
- hierarchy at -n 1 is one 1.1 to 2 MB NUCA slice, not 105 MB. flat vs nuca moves cycles 17 to 31% with almost no hits, far larger than the effects being hunted. latency does not scale with cache size. prefetchers were never inspected. DRAM is ddr4_2400 placeholder. S0 and the S2 binaries come from different source snapshots.
- windows are 10 to 500 reads (0.35M to 25M bases), startup-heavy and cold. the sim hw-assoc null alone proves little. concede.

but these do not rescue a positive result, for four reasons.
1. **direction of the bias.** sim latency not scaling with size favours bigger caches (cleanstart's own caveat). so the sim error pushes toward finding a win. no win appeared. a biased-toward-yes instrument saying no is stronger evidence for no.
2. **the sim's one big "positive" was the artifact, not the null.** 1.8x to 2.05x on 8/16/103gb came from S0 vs S2 source lineage: 1-way (4,096 entries) wins as much as 4-way (1.81x vs 1.83x on 8gb) and S0 executes 16M to 50M extra instructions that a tiny cache cannot remove. the sim made a false positive, not a false null.
3. **a second instrument agrees.** S6 ablation, S3.4, S4.0 and the T=1 associativity sweep (wall-clock +3.86% at 64-way) are native runs on luna with 105 MB LLC, real prefetchers, real DRAM, hugepages. B's artifact list cannot touch them. the sim null and the native null have independent error sources and the same sign.
4. **B's modelling gaps cut my way when fixed.** a bigger LLC slice only helps if reuse is within its reach. the measured distances (81% of repeats at 1e4 to 1e6 lookups, 640 KB to 64 MB of lines if each lookup touches a distinct 64 B line) mostly fit in luna's real LLC already. if so, the real LLC already catches most of the catchable reuse, which is why associativity and software caches add nothing on top. this is testable (F1).

where B is right and I should not push back: the sim cannot say anything about a real 105 MB LLC at production scale, so "sim hw-assoc null" must not be cited as evidence about luna. the paper can cite only native results for that claim.

## 4. rebuttal to C: "the question is at the wrong layer"

C's strongest point (auditor section 2e, concluding 2 and 9): the sim holds LLC to one slice, workloads have almost no reuse at tested scale, so the hardware-cache question was unanswerable, and the real wins live in pipeline, prefetch and TLB.

what I accept: the real stock-to-S15 gain (1.8x to 4.4x at 1.87M reads) came from pipeline, load, hugepage and prefetch fixes. S14 alone took 103GB from 35 s to 13-20 s. the cache layer was never where the time was.

why that supports me and does not replace me:
1. "wrong layer" is a consequence of "no reuse to capture", not a rival to it. the layer is wrong because the cache layer has no demand signal. my claim explains why the right layer is latency hiding.
2. "wrong layer" overreaches if it implies the right layer would yield a cache paper. the right layers (S9, S16) gave null on 8GB and 16GB and -10% on 103GB only, a dram-bound regime. no layer in the cache hierarchy shows reuse headroom either.
3. C's own item 9 ranks "llc not the size under test" first for the null. that is partly refuted by cleanstart: L1d hit 99%+ and L2/L3 hit under 0.5% of loads at every cell. growing the LLC from slice to 16 MB (cleanstart held total L3 at 16 MB) is a knob nobody turned, but the hit columns say demand at that level is tiny. F1 settles it natively.
4. where C is right and I yield: the question "what is the best cache for kraken2" is itself a characterisation question. the publishable result may be "kraken2 is latency-bound and cache-insensitive, here is the evidence on three instruments", with S14/S16 as the actionable part.

## 5. residual honesty items

- my 90 ns Td and 30 ns Tp are guesses; real luna latencies were never measured in this repo (trie brief stage 0 would measure them).
- the break-even model predicts the sign of the 4 to 64-way sweep but I did not fit it; it is an explanation, not a proof.
- the DRAM-lines vs unique-lines argument rests on hit_pct columns being percent of loads. if that denominator is wrong the inference collapses; F2 replaces it.
- S4.0 reuse-distance data is T=1, 8gb, 3M lookups, a hash-bug era binary (S2SetIndex before murmur mixing). the histogram is a property of the minimizer stream, not the cache index, so it should survive. not re-measured after the fix.
- M5's 90.7% and S4.0's 54% differ because of window length (351.8M vs 3.0M lookups). reuse fraction grows with window, which is exactly why short sim windows look cold.

## summary (8 lines)

1. the assigned claim "near-zero reuse" is false: M5 = 90.7% global reuse, S4.0 = 54% of lookups repeat at T=1 on 8gb.
2. what holds: 81% of repeats are 1e4 to 1e6 lookups apart, beyond any L1/L2-sized cache and already within a real 105 MB LLC.
3. hit rate rose 3.58% to 27.75% (4 to 64-way) while wall-clock got monotonically worse (-0.40% to +3.86%): probe cost beats hit benefit below break-even.
4. four native luna nulls (S6 ablation 11.06 vs 11.10 s, S3.4, S4.0 hash fix, S7/S11/S20) need no simulator.
5. sim hw-assoc null (cycles within 0.0 to 0.9%) is real but cold-window and one-slice; it cannot speak for luna, concede to B.
6. vs B: sim biases favour bigger caches yet show no win; its only positive was a source-lineage artifact; native runs agree.
7. vs C: "wrong layer" follows from no capturable reuse; the winning layers (S14, S16) are latency hiding.
8. falsifiers: CAT way-restriction on luna (F1), DRAM-lines/unique-lines at 1.87M reads (F2), L1/L2-sized gated cache above 15% hit with a wall win (F3), production-scale reuse-distance mass under 1e4 (F4).
