# cycle 2, round 2, agent A (prosecutor): the static front table will not give a measurable win

read: round1 A/B/C, round5_RESULTS, round6_E5, e5/sweep.csv. nothing run, no luna. tags: [L] measured, [T] trace analysis, [A] my arithmetic, [G] guess.
claim to defend: on S19 at T=32, 1.87M reads, 103GB and 8GB, a static shared front table (F2 4 MB or F3 16 MB, 5 exact pairs per line) will not beat the noise floor on wall time. most likely gain is about +2% at 103GB and 0% at 8GB.

## 1. arithmetic (gain ~ s x (h - Tf/Td))

round1_C already gives bounds of 3.8% to 8.7% before any discount. each input is too generous.

1. s is not the saveable part. the 16.4% lookup share at 103GB T=32 [L] is PrefetchIndex 9.7 + GetAt 6.7. a front hit skips the prefetch and the GetAt, but not NextMinimizer (19%), hashing, the value-to-taxon step, or the new pipeline stage. say 85% of s is saveable at best.
2. h is in-sample on one 105k-read file at 8GB T=1 [T]. held-out is unmeasured (ledger section 3 item 4). round1_C guesses x0.8, which has no data behind it. for a different sample (different organisms) the hot set is the wrong set. h is 0.45 for F2 only if the pilot and production reads come from the same sample.
3. the discount nobody applied: the hardware cache already holds the hot lines. a hot slot costs one 64 B line in the big table. 262K hot slots = 16.8 MB of lines, 1M = 64 MB, against 105 MB of LLC per socket. the trace says an LRU of 1M entries gets 76% [T]. so at T=1 on an idle LLC the natural hit rate on this trace is already near 70% to 75%. the perf share s is the cost of the lookups that miss the LLC plus the exposed L3 latency of those that hit. a front table only saves the hits that would have been LLC misses. effective h is h x P(llc miss | hot slot), and P is not 1. it is unmeasured and could be 0.3 to 0.7 [G]. with 65 other users on luna the LLC is partly theirs, which pushes P up, and nobody can control that.
4. Tf is not 4 to 10 ns. the front probe is a dependent load behind its own prefetch, a 5-key compare, and a branch that is about 50/50 (h 0.45) so it mispredicts near half the time at 15 to 20 cycles. [A] 0.5 x 6 ns of mispredict + 3 ns compare + 3 ns for hash and address work = about 8 to 10 ns exposed, and 30 to 35 ns of L3 latency if the stage-a prefetch distance is short. SPR L3 is slow (mesh).
5. Td_eff: s x user time / lookups = 0.164 x 334 s / 218M..352M lookups = 155 to 250 ns of cpu per lookup [A]. this is larger than structbench at T=32 (49 to 82 ns [L]), so the profile includes skid, SMT sharing and neighbour interference. the saveable exposed ns is probably nearer the structbench number. take Td = 60 to 100 ns.
6. put it together at 103GB, T=32, post-guard s = 0.20 [A, ledger section 4], classify only: saveable s = 0.17, h = 0.40 (held-out guess), P = 0.6, Tf/Td = 10/80 = 0.125. gain on classify = 0.17 x (0.40 x 0.6 - 0.125) = 0.17 x 0.115 = 2.0% of classify time. classify is 9.2 of 12.2 s [L, sweep: 10-read run is 3.0 s], so wall gain = 2.0% x 0.75 = 1.5%. range: optimistic (h 0.7, P 1, Tf/Td 0.05) = 0.17 x 0.65 x 0.75 = 8.3%; pessimistic (h 0.2, P 0.4, Tf/Td 0.2) = negative, about -2%.
7. at 8GB, T=32: s is unmeasured. T=1 gave 7.7% of cpu and GetAt 0.66% [L]. with P = 0.5 and s = 0.10, gain = 0.085 x (0.45 x 0.5 - 0.125) = 0.85%. smaller than the 1% noise floor of the 8GB cell.

## 2. the sweep bounds the upside (e5/sweep.csv, guard rows, median of 3)

- 103GB, 1.87M reads: wall 12.21, 12.18, 12.60 s. spread is 3.4% by itself, so the 103GB floor is about 3%, the same as round1_C's kill line. a true +1.5% to +3% cannot be told from drift with 7 reps. round1_C says the same binary varied 23% across sessions [L, round4], so a cross-session claim is hopeless.
- 103GB load and exit is about 3.0 s of 12.2 s (10-read row 3.02 to 3.07 s). a front table cannot touch 25% of wall. the pilot adds to it.
- 8GB wall 7.50 to 7.56 s, user 214 s. the cache-resident 50MB db takes 7.90 s and 234 s user [L]. the 50MB db is confounded (different content) but it is not slower than the DRAM-bound 8GB db, which says the DRAM cost at 8GB is not large enough to show against db content differences. 8GB has no room.
- marginal cost 103GB: (12.21 - 5.70) s / 1.37M reads = 4.75 us per read at 32 threads. the whole classify phase is about 9 s. every lookup in the run lives inside that 9 s. removing 17% of it entirely would give 1.5 s wall (12%). a real cache gets a quarter of that.
- the guard already took the biggest slice (7.9 s). what is left to optimise is mostly db load (3.0 s), NextMinimizer (19% of samples) and the rest of the classify loop, none of which a front table touches.

## 3. pollution, SMT, sharing (b)

- the front table is read-only and shared, so no coherence storm. but lines shared by 32 cores sit in each core's 2 MB L2 and in the LLC, and a 4 to 16 MB table cannot live in L2. only the top few thousand lines (16K entries = 12.5% of lookups = 3.3K lines = 210 KB) stay in L2. the rest are L3 hits at about 30 to 35 ns, which is why Tf is not small.
- every thread also has its own working set (read buffer, minimizer deque, taxa counters, pipeline arrays). adding 4 to 16 MB of shared hot lines to a 2 MB L2 evicts some of those. unmeasured, probably small, but it works against the gain.
- the LLC is shared with other users' jobs. the front table's residency in L3 is not guaranteed and the run to run variance goes up, which hurts the very measurement you need.
- if the scheduler puts two of the 32 threads on one core's SMT siblings, L2 halves per thread. luna has 192 logical cpus and no pinning is recorded in the repo [unverified].
- the pollution benefit is real in the other direction: hits no longer issue big-table prefetches, so fewer lines enter the LLC. concede this. it is why 103GB is the only cell where I give the front table a chance.

## 4. drift and the pilot (c)

- one sample, one fastq, one db were traced. no held-out run exists. a hot set is "the top-K slots of the dominant organisms". a sample with a different mix (a different barcode or a metagenome) has a different top-K, and then h falls toward the natural level and the front table becomes a pure probe tax (round1_B said this too).
- the pilot is not free. a separate pilot pass over 105k reads at 103GB costs about 0.8 s (3.81 s minus 3.0 s load, sweep row 104918) [L]. that is 6.5% of 12.2 s, already larger than my 1.5% expected gain and about equal to the optimistic 8%. if the pilot instead reuses the first chunk of production reads, the cost is the counting: 12M lookups into a counter table plus a sort or top-K selection. single threaded that is about 0.5 to 1 s [G]; sharded across 32 threads, 0.1 to 0.3 s [G]. either way 1% to 8% of wall, same order as the gain.
- the alternative, one prebuilt hot set per database, removes the pilot but makes the result depend on the sample type being known. for a paper that is a weaker claim, and it must be built per db, so every db gets a new file and a staleness story.
- top-K from 105k reads is noisy in the tail: slots with 1 to 3 hits are mostly noise. K = 1M out of 2.27M uniques means the lower half of the set is chosen on counts of 2 to 4. held-out h at K = 1M will lose more than the guess of x0.8 [G].

## 5. restructuring cost (d)

- v1 adds a third pipeline stage: scan batch i+2 and compute hc, prefetch front line; probe front for batch i+1; PrefetchIndex only misses; GetAt for batch i. that holds three batches of state, more registers and array traffic per lookup, and it needs hc stored in pf[] (round1_C says PrefetchIndex must return it).
- the probe-and-branch moves the data-dependent branch into the hot loop. S19's loop is currently branch-light. any mispredicts add to every lookup, including the 55% that miss and pay both costs.
- the hit-skipped lookups leave holes in the batch, so the big-table prefetch batch is no longer 16 dense lookups. the existing 2-batch lookahead of 16 was tuned (S16) for dense batches. with 45% fewer prefetches in flight, DRAM overlap per thread drops, so the lookups that still miss may each be more exposed, not less. a re-tune of B is needed, and every B you try is another reps-times-cells cost.
- the K2_HOT-unset path must match stock within noise. an extra predictable branch is fine, but that is one more thing to prove.

## 6. what matters after the HLL guard (e)

- the guard cuts user cpu 334 to 268 s, so lookup share rises from 16.4% to about 20% (ledger). that helps the front table. concede it.
- but the guard also shortened wall to 12.2 s with 3.0 s of it fixed load. a gain in cpu (user, summed over 32 threads) is not a gain in wall one for one: the load and exit phases are single-threaded or io bound, so the wall gain is 0.75 of the classify gain at best (section 1, item 6).
- the guard shows the pattern. a one-line fix beat every cache idea by a factor of 4 because it was a wasted phase, not a stall. the lookup path has no wasted phase left that I can name, only latency that S19 already hides to GetAt = 6.7%.
- no T=32 profile exists for 8GB or 16GB, so the 8GB claim is held up only by the T=1 profile (GetAt 0.66%). I rate 8GB as dead.
- the absent-key sentinel (13% of lookups, round1_B) adds a front-table case, but nobody has measured whether absent keys repeat. if they do not, the sentinel wastes table slots.

## 7. what the data forces me to concede

1. repeats are real: 81% of lookups, top 262K slots = 55.8%, top 1M = 90% [L/T]. the hot set is small. "no reuse" is dead and I will not use it.
2. 103GB is not 8GB: lookup share rose 9.6x from T=1 to T=32 [L], and the guard raises it again. a front table at 103GB T=32 has a real upside of about 8% in the optimistic corner.
3. compaction is a true mechanism. five hot entries per line beat one hot entry per 64 B line, and a 4 to 16 MB resident table avoids the TLB reach problem: 262K hot lines spread over 52K 2 MB pages of a 103GB table miss the TLB, while the front table has hugepage-compact lines. this is the best argument for the design and I accept it.
4. the design is exact: byte-identical by construction (hc plus exact value), no new false-positive behaviour. that makes the experiment safe and cheap to kill.
5. the idea is novel in the prior art B found, so even a null is publishable as a bounded negative.
6. noise on 8GB is only about 1%, so a real small gain at 8GB would be detectable. I just do not expect one.

## 8. most likely actual gain (with range)

| cell | most likely | range | P(median gain at least 3% and 2x noise) |
|---|---|---|---|
| 103GB, T=32, 1.87M reads | +1.5% to +2.5% wall | -2% to +8% | about 25% |
| 8GB, T=32, 1.87M reads | 0% | -3% to +2% | about 7% |
| 8GB, T=1 | -1% | -3% to +1% | under 5% |
| any cell, different-sample hot set | -1% to -3% | -4% to 0% | under 5% |

with the pilot cost included in wall time, the 103GB most-likely drops to about 0% to +1%. with the pilot paid once per db and amortised (offline hot set), it stays +1.5% to +2.5%.

## 9. cheapest falsification of my pessimism

ordered by cost, each can kill or save the idea before the 1.5-day build.

1. one hour, 2 binary runs, no code: `perf stat -e LLC-loads,LLC-load-misses,dtlb_load_misses.walk_completed,cycles,instructions` on stock S19 at T=32, 1.87M reads, 103GB and 8GB. divide LLC-load-misses by the ~218M lookups (use the tracer count). if LLC misses per lookup are under 0.25 at 8GB, the hardware already serves the hot set and P is small, so my section 1 stands. if they are over 0.5 at 103GB with high walk counts, P is near 1 and compaction is real, and I lose the argument.
2. half a day, a time-only upper bound: in S19 skip PrefetchIndex and GetAt for a random 45% of lookups (output wrong, timing only, no probe cost, no pollution). random skipping removes cold and hot traffic alike, so it over-credits the front table. if wall at 103GB T=32 improves by under 3% over a paired A/B with 7 reps, the front table cannot reach 3% and the idea is dead without any build. if it improves by over 6%, the build is justified and my range is too low.
3. one trace afternoon: held-out static h (train on file A, test on file B and on a different organism mix). if held-out h at 262K is under 25%, kill. this is round1_C's rule and I support it as written.
4. a paired A/A run at 103GB with the exact reps plan. if the A/A half-range is over 3%, a 2% to 3% effect cannot be proved, and the experiment needs 11 or more reps or it cannot confirm my pessimism or its opposite.

if falsifier 2 shows a 6%+ ceiling and falsifier 1 shows P near 1, I withdraw: the front table is a legitimate 3% to 5% win at 103GB and worth building.

## summary

1. expected gain: +1.5% to +2.5% wall at 103GB T=32 (range -2% to +8%), about 0% at 8GB; roughly 25% chance of a measurable 3% at 103GB and 7% at 8GB.
2. biggest hole in the case: the 105 MB LLC already holds most hot lines (1M LRU = 76% hit on the trace), so effective h is h x P(LLC miss), unmeasured and likely 0.3 to 0.7.
3. Tf is 8 to 10 ns exposed and 30+ ns on an L3 hit with a 50/50 branch, so Tf/Td is 0.1 to 0.2, not 0.04.
4. the pilot costs 1% to 8% of wall (0.8 s measured for a separate 105k-read pass), the same size as the gain; 3.0 s of 12.2 s is untouchable load; 103GB noise floor is about 3%.
5. conceded: 81% repeats, compaction and TLB reach are real, the design is byte-exact, and 103GB T=32 with the guard has a real 8% optimistic corner.
6. cheapest kill: perf stat LLC-miss-per-lookup (1 hour), then a random-skip 45% time-only ceiling (half a day); under 3% ceiling at 103GB means do not build.
