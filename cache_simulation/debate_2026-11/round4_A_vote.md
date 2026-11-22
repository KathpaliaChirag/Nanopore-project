# round 4, agent A: attack, defend, final vote

read: all round 1 to 3 files. nothing run, no luna. every luna detail below that i cannot verify is listed in section 4 as a prerequisite. numbers marked [arith] are my own arithmetic, redone here.

## 1. attack on agent B's top 3

### B1 sort-and-partition batched lookup: B's own numbers contradict B's prediction

- B predicts "1.05 to 1.2x on 103GB, null elsewhere, possibly negative" and sets the stage-0 kill at "dedup removes under 10 percent of lookups at B of 1e7".
- the repo already holds the answer to that kill test. 54% of lookups are repeats inside a 3.0M-lookup window at T=1, and 90.7% globally (M5). a perfect dedup over a window of that size removes about half the lookups. the kill criterion cannot fire. a stage 0 that cannot fail is not a gate, it is a delay.
- the mistake is in B's reasoning about sharing. B asks whether two queries share a DRAM line (negligible, correct) and treats dedup as a side effect. dedup is the main effect. a 4-way cache gets only 3.6% hit because 81% of repeats sit at distance 1e4 to 1e6, which a 16K-entry cache cannot reach. a batch of 1e6 to 1e7 lookups reaches all of them, with no eviction at all.
- but the real cost model also kills B's optimism, and i say it against my own side too. the break-even is h* = Tp / Td. with S16 pipelining, the effective Td per lookup is not 107 ns. it is the overlapped cost, plausibly 15 to 25 ns on 103GB [guess, never measured per lookup]. a dedup step that does a random probe into a 3M-key hash set (about 24 MB, LLC-class, roughly 10 to 30 ns) has Tp at or above Td_eff and loses. a radix partition that makes each partition L2-resident has Tp of a few ns and wins. so B1 is positive only if the partition pass is sequential and bandwidth-bound. B never costs the two extra passes in ns, only says "12 to 16 bytes written and read twice". at 16 bytes x 2 passes x 2 (write+read) = 64 bytes per lookup at, say, 10 GB/s per thread, that is about 6 ns per lookup [arith]. against Td_eff of 15 to 25 ns and 54% removed (saving 8 to 13 ns), the net is roughly +2 to +7 ns, so a 10 to 30% gain on lookup time, not 1.05 to 1.2x of total. thin but positive, and entirely dependent on Td_eff, which nobody has measured.
- second flaw: byte-identical output. kraken2 classifies a read from all its minimizer hits. a batch scheme must hold per-read taxon lists for B reads until the last partition finishes. 1e7 lookups is about 40K to 100K reads, a few MB per thread, fine. but it changes the producer/consumer pipeline S10 fixed, and the load/exit tax (4 to 5 s) is untouched.

### B2 structbench: double hashing line counts, checked

- linear probing at alpha 0.70: hit probes 0.5(1 + 1/(1-a)) = 2.17, miss probes 0.5(1 + 1/(1-a)^2) = 6.05 [arith]. with 16 cells per line, lines = 1 + (probes-1)/16 = 1.07 hit, 1.32 miss. this matches B's table, so B's baseline is right.
- double hashing: hit (1/a) ln(1/(1-a)) = 1.72, miss 1/(1-a) = 3.33, each a fresh line. 1.72/1.07 = 1.61 (+61%), 3.33/1.32 = 2.52 (+152%). B's arithmetic is right.
- flaws: (a) the +60 to +150% is lines, not time. with S16 the first probe is prefetched and later probes are demand misses either way, but double hashing probe 2 and 3 are independent addresses that can be prefetched together as soon as the hash is known (both strides are computed from the key). B lists this as a variant but still states "30 to 60 percent slower" as the headline. under full prefetch of 2 to 3 lines the slowdown is bandwidth, not latency, and could be 10 to 30%. the prediction range is too wide to be a prediction. (b) the miss share of lookups on real reads is unmeasured, and the weighted answer swings from +60% to +150%. (c) aligned buckets: the saved second line is the adjacent line, and Intel's adjacent-line (spatial pair) prefetcher fetches the 128-byte pair, so the real saving of "-17% miss lines" is probably smaller, maybe a third of it. B should have flagged this; it is the reason (a) of B's hypothesis is likely to hit the kill line (under 10%). (d) the poisson overflow figure of 8 to 10% at 16 slots, mean 11.2: P(X>=17) is about 7 to 9% [arith, normal approx z about 1.6 plus right skew]. fine.
- what survives: (b) is worth doing because it is a number for thesis 2 either way, and it needs no db rebuild in the microbench form.

### B3 mphf / Elias-Fano: not a two-week item

- B admits it: 4 to 6 days standalone, 2 to 3 weeks integrated, predicted 5 to 25% slower. it is a space result with a speed loss, and the space claim (-23%) is already in the trie brief on paper. a standalone with real keys re-measures an existing number. it cannot be a "positive on real kraken2" in the window. drop.

## 2. attack on agent C's top 3

### C1 sniper microbenchmark gate

- it is a good cheap experiment and answers a real dispute. but it produces a statement about the simulator, not about kraken2, and CK already marked sniper results as not trusted. its best case ("sniper matches within 30%") only reopens a track that has not produced one positive result in three rounds. its worst case (blind to prefetch) is already the prior, since sift format has no prefetch record. expected information is low: both outcomes leave the next move on real hardware. cost 1 to 2 days that i would rather spend on luna.
- arithmetic check: C predicts (b) independent plain loads at 10 to 25 ns and (c) group-prefetch at 7 to 15 ns, ratio 1.3 to 2x. the ratio from those ranges spans 0.67 to 3.6, so the prediction cannot fail. and "emulate 2 MB pages in sim by a huge TLB" is not equal to hugepages: it also removes page-walk cache pressure and walk dram traffic differently. the S14 comparison is apples to oranges.

### C2 CAT sweep

- cheapest real-hardware idea, agreed. the flaws: (a) the headline prediction is only for the 50MB db (+8 to +30% at 14 to 7 MB). C's own arithmetic: 0.195 x (0.5 to 1.5) = 9.8% to 29% [arith ok], but the 0.195 share is the lookup share at 50MB including hashing and fixed compute that does not move with capacity, so the capacity-sensitive part is smaller and the low end (about 8%) is more likely. (b) the 8GB and 103GB cells are predicted flat, which is the null again, so 2 of 3 db sizes give a null and the thesis dbs are those. (c) min_cbm_bits is often 2 on server parts, so "1 way" may be illegal; the 7 MB point may not exist. (d) SPR LLC is non-inclusive, and one socket shared with other lab users breaks the "quiet machine" requirement that C itself lists. (e) needs root; unverified.
- value: a clean characterisation, "kraken2 is LLC-capacity insensitive above the table size". useful for sir's LLC-topology thesis claim whichever way it goes. conditional on root.

### C3 trace once plus fitted mlp model

- the degrees of freedom are wrong. C fits 3 to 4 constants (L_dram, L_walk, MLP_eff, compute) to runtimes of 4 binaries (stock, S9, S14, S16) and validates on one held-out db. 4 constants against 4 runtimes is zero residual freedom; a perfect fit proves nothing. and the binaries differ exactly in MLP_eff and page size by design, so C's own kill criterion ("needs a different MLP_eff per binary, then it explains nothing") fires by construction. 5 days for a model that is probably unfalsifiable as specified. drop. keep only its useful part, the 5-line probe logger, which is my experiment 1.

## 3. defending or retracting my own top 3

### my rank 1, Belady trace replay: defend, and widen

- still the right first step, and now three agents' stage 0s collapse into it: B's dedup ceiling, C's miss-ratio curve, my Belady bound. one logger, one dump. keep.
- correction: my kill criterion used h* from Tp = 30 ns, Td = 90 ns. both were guesses and Td should be the overlapped per-lookup cost under S16, not raw DRAM latency. if Td_eff is 20 ns and Tp is 4 ns, h* is 20%, and 16-way at 10.65% (my rank 2) is below it. so the threshold must be computed from measured numbers: Td_eff = (lookup-phase time, S19, 8GB) / (lookup count), a number available from existing timing plus the logger's count. fix that in the plan.
- new output to add: windowed dedup curve (fraction of lookups removable in a window of 1e5, 1e6, 1e7 lookups, per thread and per batch), because it feeds the only structure that reaches distance 1e4 to 1e6.

### my rank 2, 16-way SIMD set with SRRIP and victim slot: retract as a win-maker

- by my own equation it loses in the S16 regime: h 10.65% < h* about 20%. i predicted 1 to 4% and the arithmetic says 0 or negative. also my layout claim was careless: the S2Entry is 24 bytes (memory note), so a 16-way set of full entries is 384 bytes, not one line. only a split layout (16 two-byte tags in 32 bytes, payload in a parallel array read only on hit) keeps Tp at one line on the 96% miss path. that works, but it is more design than "3 days".
- demote to: run only if experiment 1 shows Belady at 64K entries above measured h* with margin. otherwise log as a closed null.

### my rank 3, static hot set: defend only as a free by-product

- the coverage curve falls out of experiment 1 at no extra cost. keep it as a table in the report. do not schedule the build. my own caution stands (81% of repeats at 1e4 to 1e6 argues for a flat frequency curve).

### things i concede to B and C

- B is right that layout (lines per lookup, overlap) is the lever the real wins came from. C is right that AMAC over S16 is the published and untried continuation, and that a CAT curve is ground truth. i did not give either enough weight in round 3. i also concede that the whole eviction axis is probably a null; its value is the bound.

## 4. prerequisites (not verified by me, all must be confirmed before day 1)

- p1: ssh to luna works, tmux plus iitd-login.py auth and proxy env (memory note). 
- p2: the S19 source tree builds there and its binary reproduces the known S19 timings and byte-identical outputs on one cell. path unknown to me.
- p3: the four dbs (50MB, 8GB, 16GB, 103GB) and the 1.87M-read set exist and the benchmark scripts in plan_paper/scripts still run. the 2 ESKAPE dbs were noted missing earlier.
- p4: free disk for a 1 to 3 GB trace dump (1e8 probes x 8 bytes is about 0.8 GB) and, for E4, ram for a 64 GB array. luna ram unknown to me.
- p5: whether root exists (decides CAT; not in my four).
- p6: thp state recorded per run (13 to 21 s variance at 103GB), runs alternated, 3 reps minimum.

## 5. final vote: ordered plan, at most 4 experiments, ~11 days

total 1.5 + 3 + 4 + 2 = 10.5 days, 3.5 days slack inside two weeks.

### E1. probe logger and trace analysis (1.5 days, no dependency, do first)

- cost: 0.5 day patch, 0.3 day capture, 0.7 day analysis (C++ built on luna, windows box has no compiler).
- luna runs: S19 binary plus a 10-line patch appending (read id, slot index, hit/miss, key) per table probe to a per-thread buffer. db standard_8gb, 1.87M reads, 1 thread (clean per-thread stream) and 32 threads (per-thread streams, then merged). also the 50MB db at 1 thread. measure Td_eff by timing stock S19 with perf stat on the same cell.
- offline outputs: (i) Belady h at 16K, 64K, 262K entries, fully associative and 4/16/64-way; (ii) LRU, SRRIP, TinyLFU h at the same sizes; (iii) frequency coverage of top 16K, 64K, 262K keys; (iv) windowed dedup fraction at 1e5, 1e6, 1e7 lookups; (v) miss-ratio curve (exact stack distance on a 30M window, SHARDS beyond); (vi) hit vs miss mix of lookups (B's unmeasured miss share).
- success criterion: a complete table of (i) to (vi), and a go/no-go computed from measured Td_eff. go for E3 if windowed dedup at 1e6 or 1e7 removes at least 30% of lookups. report the eviction axis closed if Belady at 262K entries is under h* = Tp/Td_eff.
- kill: if the logger changes the byte-identical output or the 32-thread trace disagrees with the 1-thread unique-key count by more than 5%, fix before using. no kill on the science, any answer is publishable as the bound.
- depends on: p1 to p4.

### E2. AMAC and cross-line prefetch on top of S19 (3 days, independent of E1, can start while E1 analysis runs)

- cost: day 1 cross-line prefetch (slot mod 16 in the last 3 cells: prefetch the next line, 0.5 day including verify), days 2 to 3 AMAC state machine replacing the S16 fixed-batch loop (new lookup starts when any in-flight one completes), 0.5 day bench.
- luna runs: binaries S19, S19+xline, S19+AMAC, built from one source lineage and one flag set. dbs 8GB, 16GB, 103GB (50MB as control). reads 1.87M and 1 smaller count. threads 8 and 32. flags exactly as the S19 benchmark scripts, with -M as in S19. measure wall time (excluding load, as before) over 3 alternating reps, output sha equal to S19 on every cell, perf stat cycles and instructions.
- success: at least +5% wall on 103GB or 16GB at 1.87M reads, outside the thp noise band, byte-identical in all 16 cells. also acceptable: a clean "no change" with perf showing the line-crossing demand miss share (real null with a mechanism).
- kill: under +3% at both 103GB and 16GB after 3 alternating reps, drop AMAC and keep only the xline result if it is positive. this is the highest-probability real wall-clock win in the set, small but plausible (C's 5 to 15% guess; my own discount for the adjacent-line prefetcher puts it at 2 to 6%).
- depends on: p2, p6. independent of E1.

### E3. windowed dedup via radix partition (4 days, conditional on E1 go)

- cost: 1 day prototype of per-thread batch (collect minimizers of N reads, radix-partition by top slot bits into L2-sized bins, probe each bin sequentially with S16 prefetch, scatter results back by read id), 1 day verify byte-identical, 1.5 days bench, 0.5 day writeup.
- luna runs: S19 versus S19+dedup, dbs 8GB, 16GB, 103GB, reads 1.87M, threads 8 and 32, batch sizes N = 1000, 10000, 40000 reads (about 1e6 to 4e7 lookups depending on reads), 3 alternating reps, same thp state, output sha equal. record wall time, lookups actually issued (counter), perf cycles.
- success: at least +5% wall on 103GB or 16GB at 1.87M reads, with issued lookups reduced by about the E1 dedup number. my honest prior: 30% chance of success, because the extra passes cost about 6 ns per lookup [arith above] against an unmeasured Td_eff.
- kill: if E1 dedup at 1e6 is under 30% (do not build), or if wall is under +3% on both after 3 reps.
- depends on: E1 (go decision and Td_eff).

### E4. structbench: linear vs aligned bucket vs double hashing at load 0.70 (2 days)

- cost: 1.5 days one-file bench, 0.5 day writeup. no db rebuild, no kraken2 change.
- luna runs: standalone C++ (not kraken2), array of 4-byte cells at 8 GB and a size at most 60 percent of luna ram (p4), random 48-bit keys inserted at load 0.70, lookup mixes 0, 50, 100 percent miss (use E1's measured miss share as the weighted row), 1 and 32 threads, S16-style batch-16 prefetch, double hashing with both probes prefetched. measure lines per lookup (counter, cross-checked against perf mem loads or LLC-load-misses), ns per lookup.
- success: three numbers with intervals for thesis 2: measured lines per lookup versus my arithmetic (1.07/1.32, 1.72/3.33, bucket 1.08/1.10), and the measured ns ratio of double hashing to linear under full prefetch. a result either way: if double hashing is within +15% time it is a usable thesis 2 option, if +40% or worse it is a documented cost.
- kill: nothing to kill, it is a characterisation. downgrade to a half-day run if E1 or E2 overruns.
- depends on: nothing; place it last so it absorbs slack.

### not in my four, and why

- CAT sweep (C2): good, cheap, but a characterisation with predicted nulls for 8GB and up, and it depends on root (p5). if root exists and CK has a spare afternoon, run the 50MB and 8GB rows only, 1 day. not worth a slot over E1 to E4.
- sniper microbenchmark (C1), fitted mlp model (C3): sniper track, no real-wall-clock path. mphf/Elias-Fano (B3): too long. 16-way SIMD cache (my old rank 2): below break-even by my own arithmetic until E1 says otherwise.

## 6. honest framing for the report

- E1 is a bound. it removes the "maybe a smarter policy" escape for the eviction axis whatever it shows.
- E2 and E3 are the only runs that can give a real wall-clock win; both are small-percentage results, and the repo's past real wins (hugepages, prefetch, pipelining) came from the same overlap layer.
- E4 is a characterisation for thesis 2 and is explicitly not a win.
- if E2 and E3 both fail the 3% bar, the paper claim is: lookup caching is a measured null with a Belady bound, double hashing costs a measured number of lines, and the overlap layer is exhausted at S19.

## final vote (6 lines)

1. E1 first, 1.5 days: 5-line probe logger on S19, 8GB, 1.87M reads; Belady, SRRIP, TinyLFU, coverage, windowed dedup, miss-ratio curve, measured Td_eff. a bound, publishable either way.
2. E2, 3 days, parallel to E1 analysis: cross-line prefetch then AMAC over S19 on 8, 16, 103GB; success +5% wall byte-identical; kill under +3%. best odds of a real win.
3. E3, 4 days, only if E1 shows at least 30% windowed dedup: radix-partitioned batch dedup; success +5% wall on 103GB or 16GB; about 30% odds.
4. E4, 2 days, last: structbench linear vs aligned vs double hashing under full prefetch; thesis 2 characterisation, not a win.
5. dropped: sniper gate, fitted mlp model, mphf, 16-way SIMD (below break-even by my own math), static hot set (kept only as a table from E1); CAT only if root is free.
6. retractions: my SIMD rank 2 and the guessed h* of 33 percent; B's stage-0 kill cannot fire (54% repeats already known); C's fit has zero degrees of freedom.
