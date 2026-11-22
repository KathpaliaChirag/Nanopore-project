# round 4, agent B: attacks, retractions, final vote

read: all round 1 to 3 files, the trie brief lines on cell width, dorado-kraken-research/CLAUDE.md M1. nothing run, no luna. [arith] means my own arithmetic, [guess] means unmeasured.

## 1. attacks on agent A (eviction)

A's frame is net per lookup = h x Td - Tp, break-even h* = Tp/Td. the frame is right. the numbers put into it are not.

attack A1: Td is wrong after S16. A uses Td = 90 ns, the unhidden dram miss. but the real binary already overlaps misses (S9 1.14x, S16 1.10x, round 3 C section 5). what a cache hit saves is the amortised cost of a pipelined lookup, not 90 ns. if a pipelined lookup costs 10 to 20 ns of throughput on 8 GB [guess, C predicts 6 to 13 ns per probe on a microbenchmark], then h* = Tp/Td_eff is 4/15 = 27% for an L2-class Tp of 4 ns, not 33% from Tp=30. the 33% kill line is arbitrary in both numerator and denominator. it has no business as a kill criterion. the real break-even must be measured, as ns per lookup with and without the cache on the S19 binary, then divided into Tp.

attack A2: A uses two different Tp values for one cache. "16K entries" has Tp near L2 (4 ns). "262K entries" is where Belady reaches 45 to 60% h, but 262K x 24 B = 6.3 MB [arith], which is not in the 2 MB private L2, so Tp is an L3 hit near 30 ns. a policy cannot have the small cache's Tp and the large cache's h together. the Belady bound has to be tabulated as h(N) against Tp(N), and the break-even compared per row.

attack A3: A's arithmetic on size. "16K entries is about 1 MB at 64 B per 4-way set line" does not hold. 16K entries / 4 ways = 4096 sets. an S2Entry is 24 B (memory note), so a 4-way set is 96 B, which is 1.5 lines, not one. total is 16K x 24 = 384 KB [arith]. A's rank 2 packs 16 tags of 16 bits into 32 B plus payload in a second half, which is two lines again. so "Tp stays at one L1/L2 access" is not what that layout gives. the simd idea is still fine as a software cost cut, but its Tp is two lines, and the ablation already says the 4-way cache gave 11.06 vs 11.10 s, zero.

attack A4: rank 3 (static hot set) is killed by A's own equation. A predicts top 64K keys cover 8 to 15% of lookups. with Td_eff near 15 ns, a 10% hit saves 1.5 ns per lookup and costs an L2 probe of 4 ns. the net is negative at any Td_eff under 40 ns. A's kill criterion (under 10%) is too lenient by a factor of about 2.5. the "biology dependent" selling point does not rescue it.

attack A5: rank 2's predicted effect of 1 to 4% is below the 0.6% noise band only by a thin margin, and S6 to S15 ablation showed zero at the same scale. spending 3 days on it for a predicted 1% is the worst expected return on the list.

what survives from A: rank 1 (Belady and all-policy replay on one trace) is the right experiment and the only one that turns a null into a bound. i adopt it, with the Tp(N) correction in A2 and the measured Td_eff from A1.

## 2. attacks on agent C (methodology)

attack C1: the sniper gate (experiment 1) answers a question whose answer does not move the plan. if sniper is blind to prefetch, the plan goes native. if sniper sees prefetch, C's own section 1 says it is 25% error validated, dram 2.4x too cheap, nuca 3x too cheap, and one run per cell has no noise estimate. either way the next step is a real-luna run. a positive finding needs wall time on luna, so the gate spends 1 to 2 days to be told to do what we would do anyway. it is also only a statement about the simulator, which cannot be a result for the thesis.

attack C2: the microbenchmark predictions are not independent checks. "(b) 10 to 25 ns" comes from 10 to 12 line fill buffers: 107 ns / 10 = 10.7 ns [arith], so (b) is just the LFB bound. the prediction that c beats b by 1.3 to 2x then rests on the prefetch retiring early, which is the thing under test. a result either way will match one of the three branches C wrote, so the experiment cannot embarrass the prediction. that is a sign the branches are too wide.

attack C3: experiment 2 (CAT). the arithmetic 0.195 x (0.5 to 1.5) = 10 to 29% [arith] is right, but the 19.5% share is measured on the 50 MB db only and C says so. also min_cbm_bits is often 2, so the "1 way, 7 MB" point may not be legal; the real smallest mask is unknown until `info/L3/min_cbm_bits` is read. and CAT on a shared lab machine may be unavailable (no root, hypervisor). the result, even when it works, is a characterisation of a toy db (the 50 MB one fits in LLC by design). it supports "llc-aware sizing matters only when table is within 2x of llc", which sir already half expects. cheap if root exists, but not a speed win.

attack C4: experiment 3 (fit a model) has about zero degrees of freedom. four constants, four binaries (stock, S9, S14, S16), and the binaries differ exactly in MLP_eff and page walks, which are the fitted constants. C's own kill ("needs a different MLP_eff for every binary") is triggered by construction, since S9 and S16 are different MLP designs. the held-out db is one point. 5 days for a model that will most likely end as "negative methodology result".

what survives from C: section 3 (log the slot index per probe, 5 line patch, run SHARDS or exact stack distance offline, no pin) is the best idea in the file. also section 5 AMAC: it is the only lever where real luna data has already paid (S9, S16), and nobody has taken the next step. i adopt both.

## 3. defence and retraction of my own top 3

### 3.1 double hashing line count: re-derived, claim holds, but the framing needed a fix

facts from the repo: Kraken2 cell is one uint32 (value low bits, fingerprint high bits), 16 cells per 64 B line [trie brief line 27, M1: load 0.70, 32-bit cells, PF_STRIDE=16]. probe sequence stock is linear. i did not find in the repo docs the exact second_hash step formula, only the memory note that second_hash() exists behind -DLINEAR_PROBING and that gcd(step, capacity) was never audited.

linear probing at alpha = 0.7, uniform hash (Knuth):
- hit probes = 0.5 x (1 + 1/(1-a)) = 0.5 x (1 + 3.33) = 2.17
- miss probes = 0.5 x (1 + 1/(1-a)^2) = 0.5 x (1 + 11.1) = 6.06
cells are adjacent, so extra cells past the first are 1.17 (hit) and 5.06 (miss). chance a run of e extra cells crosses a 16-cell line from a uniform start is about e/16: 0.073 and 0.32. lines = 1.07 and 1.32. this matches the trie brief, so the brief and my formula agree.

double hashing (uniform hashing model): hit = (1/a) ln(1/(1-a)) = 1.43 x 1.204 = 1.72, miss = 1/(1-a) = 3.33. every probe jumps to an unrelated line (step is not a multiple of 16 in the typical case), so lines = probes: 1.72 and 3.33.

ratio: hit 1.72/1.07 = 1.61, miss 3.33/1.32 = 2.52. so +61% and +152% in lines, as i said in round 3. in compares double hashing is cheaper (1.72 vs 2.17, and 3.33 vs 6.06), which is the false-positive benefit, but dram lines, not compares, price a 103 GB lookup.

corrections to what i said in round 3:
1. the time effect is not simply the lines ratio. S16 prefetches probe 1 only, so extra lines are demand misses. if the lookup is MLP-bound, lookup time scales near lines, which gives +60% hit and +150% miss on the lookup phase. if it is latency-bound for the first probe only, the extra lines add serial 100 ns each. both say slower. my 30 to 60% figure on the lookup phase is a fair [guess] but unmeasured.
2. the miss share of lookups is unmeasured. in a real sample many minimizers are absent from the db. if miss share is 50%, average lines go 1.195 to 2.53, +112%. if 20%, 1.12 to 1.70, +52%.
3. a real double-hash db cannot be built by rehashing: only a fingerprint is stored (brief section 1), the step is derived from the full key hash. so any real-db test needs kraken2-build from library on a small db first. the microbenchmark is the only 2-day path.
4. the gcd(step, capacity) risk is real: if capacity is not prime or step is not forced coprime, some keys cycle in a subset of slots, which would show as a longer-than-textbook probe count in the microbench. the bench should measure probe-count histograms and check this.

verdict: defend the claim, add the miss-share caveat, and present it as a priced trade-off for thesis 2 (the false-positive cliff vs +60 to +150% lines), not a prediction of a win.

### 3.2 my rank 1 (sort-and-partition batching): keep only the dedup half, retract the page half

retract: page sharing. with 2 MB pages and 103 GB there are 52K pages, and at 12 to 16 B per entry a batch of 1e7 gives about 190 lookups per page. that is not nothing, but S14 already reduced walks and S16 hides the dram wait, so the saved part is small. my predicted 1.05 to 1.2x was a guess with no base.

new reason to keep dedup, from A's own data: 54% of lookups are repeats at T=1 in a 3.0M window and 81% of repeats sit at distance 1e4 to 1e6. a batch of 1e6 to 1e7 lookups covers that whole distance range, with no capacity limit, because dedup by sort or hash-partition does not evict. a cache of 16K to 262K entries cannot reach those distances, a batch can. rough ceiling: 0.54 x 0.81 = 44% of lookups removable at 1e6 [arith, from two measured fractions]. but the cost is two passes over 12 to 16 B per lookup. a radix pass is about 3 to 6 ns per element [guess]; two passes 6 to 12 ns, against a pipelined lookup of 10 to 20 ns [guess]. removing 44% saves 4 to 9 ns per lookup on average, and the passes cost 6 to 12. so net is about zero or negative at low thread count unless dedup rate at the batch size is much higher than 44% or Td_eff is higher on 103 GB. honest prediction: 0 to 10% on 103 GB, likely nothing on 8 GB. this is exactly why stage 0 (measure first) decides. keep it as a conditional experiment, not a lead.

### 3.3 my rank 2 (structbench): keep, but broaden to include real binary hook

keep the three layouts (linear, line-aligned bucket, double hashing) at load 0.70 with 4 B cells. add a 16-bit-cell variant, since thesis 2 is about cell width and 16-bit cells halve the page count. keep the claim that the double-hash number is the main deliverable. retract the line-aligned bucket hope of 5 to 8%: the saved miss lines are 1.32 to about 1.10, and a db rebuild is required, so it can only be reported as a bench number.

### 3.4 my rank 3 (mphf, PTHash or Elias-Fano): retract for these 2 weeks

4 to 6 days standalone for a space point that is predicted slower, needs a key list from library genomes, and cannot move wall time. not worth a slot. mention as future work only.

### 3.5 one thing neither A nor C weighted enough

all three of us (A, B, C) predicted effects against a ceiling set by a 19.5% lookup share measured on the 50 MB db. the big-db share is unmeasured. a `perf record` of S19 on 8 GB takes under 2 hours and moves every ceiling by up to 3x. it is step 0 of the vote below.

## 4. FINAL VOTE: ordered plan, at most 4 experiments, about 2 weeks

shared prerequisites (verify first, none assumed): (P1) ssh and a working S19 binary with source on Luna; (P2) standard 8 GB, 16 GB, 50 MB db present, 103 GB db present if the full grid is wanted; (P3) read sets for 4 read counts as used in S6 to S15; (P4) a compiler on Luna (the Windows box has none); (P5) perf stat and perf record permitted; (P6) a quiet window or alternating-run harness, since thp variance at 103 GB is 13 to 21 s; (P7) a byte-identical output checker (hash of kraken2 output). do not start any experiment until P1 to P5 are confirmed.

### E1. probe trace plus offline replay (Belady, dedup windows, coverage, MRC), with perf profile as step 0. cost 3 days. no dependency.

- step 0 (2 hours): `perf record` S19 on 8 GB, 1.87M reads, T=1 and T=32, report share of cycles in the lookup loop. this fixes every later ceiling.
- patch: append the table slot index plus the hit/miss flag per probe to a per-thread buffer (about 5 lines, 12 bytes per lookup, under 1 GB for 8e7 lookups). run on 8 GB db, 1.87M reads, T=1 plus one T=32 run with per-thread files.
- offline program on Luna (C++): exact and SHARDS stack distance, repeat rate per window (1e4, 1e5, 1e6, 1e7), distinct lines per lookup after dedup, key frequency coverage curve (top 16K, 64K, 262K), Belady and LRU/SRRIP/static top-K h at 16K, 64K, 262K entries, with Tp(N) set by cache size (L2 4 ns for 384 KB, L3 30 ns for 6 MB). measure Td_eff as ns per lookup of the S19 lookup phase from the step 0 profile.
- success (positive characterisation): a table of Belady h(N) against measured break-even h*(N), with the claim "no policy can win" or "this much room exists", plus dedup ceiling per window. publishable as a bound in either direction.
- kill: if the traced miss ratio from the trace differs from perf llc miss ratio by more than 10 points, the trace is not the real stream; stop and fix the logger. branch: if Belady at 64K or less is below h*, eviction axis is closed and goes in the paper as a proved null. if dedup at 1e6 to 1e7 removes at least 25% of lookups, E4 runs.

### E2. structbench of linear vs line-aligned bucket vs double hashing, at load 0.70. cost 2 to 3 days. no dependency (runs while E1 offline analysis proceeds, but not while timing).

- what runs: one C file, 8 GB and 64 GB arrays of uint32 cells (check free RAM on Luna first), random 48-bit keys inserted at load 0.70, hit mix 0, 50, 100% miss, S16-style pipelined prefetch with batch 16, probe-1-only and all-probes prefetch variants, T=1 and T=32 pinned to one socket, huge pages on. 16-bit cell variant of the same. use 3 alternating repetitions.
- measure: lines per lookup (software counter, cross-checked by perf mem loads or dram reads), ns per lookup, probe-count histogram (to expose any gcd(step, capacity) cycle), for double hashing run with a prime and a power-of-two capacity.
- success: measured lines match arithmetic within 5% (1.07/1.32 linear, 1.72/3.33 double), and ns per lookup ratio for double hashing is a number thesis 2 can quote. a clean cost number is the positive result here. any layout winning at least 5% on miss-heavy mix at 64 GB is a bonus.
- kill: drop the aligned-bucket arm if the miss-line saving is under 10% or time gain under 3%. keep the double-hashing number whatever it shows.
- caveat in the writeup: miss share of real lookups comes from E1's flag, so report the weighted figure at the real hit/miss mix.

### E3. AMAC (per-lookup state machine) in place of S16 lockstep batching. cost 4 days. dependency: E1 step 0 shows lookup share of at least 25% on 8 GB or 103 GB; otherwise the ceiling is too low and E3 is skipped for the next item.

- what runs: S19 binary plus a variant with the lookup loop rewritten as AMAC (one state machine per lookup, start a new lookup when any in-flight one completes, in-flight 10 to 16), same source lineage, same flags, same make. stock S19 vs AMAC build, alternating runs, 3 reps minimum, 8 GB and 16 GB first (S14 variance is small there), 103 GB only if the first two show gain.
- measure: wall time excluding load, perf cycles and instructions, dtlb walks, output hash byte-identical to S19 in every cell.
- success: at least 5% wall time on 8 GB or 16 GB at 1.87M reads over S19, outside the noise band (0.6%), byte-identical output. this is the only experiment in the vote with a plausible real wall-clock win, because probe chains here have variable length and lockstep leaves bubbles (C's argument, and my own 1.07 to 1.32 line spread).
- kill: under 3% across 3 reps at both 8 GB and 16 GB; or a different output hash.
- honesty: C's 5 to 15% is a guess. S9 group-size sweeps saturated at 0.6% (K2_B 16 to 64), so the S16 loop may already capture most of it. a null here is a bounded "S16 is near the latency-hiding limit" statement.

### E4 (conditional). batched dedup prototype OR CAT sweep. cost 4 days (dedup) or 2 days (CAT). dependency: E1.

- if E1 shows dedup removes at least 25% of lookups at a batch of 1e6 to 1e7 and Td_eff at 103 GB is at least 20 ns: run the dedup prototype. per-thread batch, radix by top slot bits, probe once per distinct key, scatter results back by read order, byte-identical output. compare against S19 on 8 GB and 103 GB, all four read counts, full grid, 3 alternating reps. success: at least 5% wall time on 103 GB outside the 13 to 21 s thp band (use paired alternating runs, report spread). kill: under 5%, or output differs.
- else, if root and `cat_l3` in /proc/cpuinfo and `resctrl` mount work (verify min_cbm_bits and way count before choosing masks): run C's CAT sweep on 50 MB and 8 GB db only, ways 15, 12, 8, 4, 2, 1 (or smallest legal mask), S19, 1.87M reads, 8 and 32 threads pinned to one socket via numactl, 3 reps. success: a measured time-vs-llc-capacity curve (clean characterisation), with the predicted +10 to +29% at 14 MB on 50 MB db either confirmed or refuted. kill: no root, no cat_l3, or run to run spread above 5%.
- if neither condition holds, spend the 4 days on a longer E2 plus the writeup of E1 and E2.

### what is deliberately left out
sniper gate and sniper layout runs (cannot give a wall-clock result, calibration unknown); hardware replacement policies in sniper (known null, nuca sees 0.2 to 0.5% of loads); SHiP, Hawkeye, Mockingjay, dead-block (one lookup site, no signature); the 16-way simd cache (predicted 1%, below the noise of the ablation); static hot set (negative by A's own equation); mphf and Elias-Fano (space only, 5+ days); the three-parameter model (no degrees of freedom).

### order and total
E1 (3 d), then E2 (3 d, can overlap E1 offline analysis), then E3 (4 d), then E4 (2 to 4 d). total 12 to 14 days. if time is short, E1 and E2 are the guaranteed publishable pieces (a Belady bound and a priced double-hashing cost); E3 is the only real speedup candidate; E4 is the lottery ticket.

## summary of my vote (6 lines)
1. E1 first: probe trace plus offline Belady, dedup windows and coverage, after a 2 hour perf profile of the big-db lookup share. 3 days, a bound that turns the null into a proof.
2. E2: structbench of linear vs aligned bucket vs double hashing at load 0.70, expecting lines 1.07/1.32 vs 1.72/3.33 (+61% hit, +152% miss). 3 days, a priced thesis 2 trade-off.
3. E3: AMAC replacing S16 lockstep batching, success at least 5% on 8 or 16 GB with byte-identical output, kill under 3%. 4 days, the only plausible real speedup.
4. E4 conditional: batched dedup prototype if E1 shows at least 25% removable lookups, else CAT sweep if root exists, else extend E2.
5. retracted: my page-sharing claim, aligned-bucket 5 to 8% hope, mphf slot; rejected: sniper gate, simd 16-way cache, static hot set, fitted mlp model.
6. A's h* = Tp/Td with Tp=30, Td=90 is unusable (Td_eff after S16 is 10 to 20 ns, and Tp depends on cache size); every ceiling rests on an unmeasured big-db lookup share.
