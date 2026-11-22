# cycle 2, round 2, agent B (defender): the static shared front table will move wall clock at 103GB T=32

read: round1 A, B, C. numbers are quoted from the ledger or marked [arith] or [guess]. nothing run, no luna. i argue the best honest case, then say where it is weak.

## 1. what the design is, in one paragraph

a read-only table of K exact entries (64-bit hash hc, 32-bit value as GetAt returns it), one copy shared by all 32 threads, probed before the 103 GB table. a hit returns the value GetAt would have returned, so output is byte-identical by construction. a miss falls through to the S19 path unchanged. no writes, so no locks, no coherence traffic, no eviction code. a hot set of K=262K to 1M entries is 4 to 16 MB, which sits in the 105 MB per-socket L3 and partly in L2.

## 2. which cycles a front hit actually saves

the T=32 103GB profile (perf samples, S19): PrefetchIndex 9.7%, GetAt 6.7%, NextMinimizer 19.0%, ClassifySequence 17.0%, kernel about 21%. lookup total 16.4% (after the guard about 20% of user time, ledger section 4).

1. GetAt 6.7%. this is the strongest fact for my side. at T=1 GetAt is 0.58% to 0.94% and at T=32 on 103GB it is 6.7%, a ten-fold jump. the prefetch is hiding the latency at T=1 and failing to hide it at T=32. that 6.7% is exposed stall, not work. a front hit removes the demand load and its compare entirely. savings: nearly all of the 6.7% on the hit share.
2. PrefetchIndex 9.7%. the sample lands on the prefetch because a software prefetch to a cold page still needs a TLB translation, and on a 103 GB table at random that is a page walk. the walk's own page-table lines (about 200 MB of PTEs for 4 KB pages, more than the LLC) miss to DRAM too. a hit that skips PrefetchIndex saves the address math, the issue slot, the walk and one DRAM line fill. savings: most of the 9.7% on the hit share. this depends on the front probe coming before the prefetch (design v1 below).
3. the DRAM line. 1.07 lines per present lookup and 1.32 per absent one (ledger item 17), one 64 B line each. a hit saves that line fill and a line fill buffer slot.
4. what is not saved: NextMinimizer 19% and ClassifySequence 17% (the minimizer is computed regardless), and the front probe itself, which costs an L3 hit (about 30 ns raw, mostly hidden if prefetched one stage ahead).

best case, 103GB T=32, 1.87M reads, post-guard wall 12.2 s of which about 9.2 s is classify:
- ceiling: 0.8144 x 0.164 = 13.4% of samples, 15 to 17% post-guard (ledger).
- realistic front hit rate h: in-sample 56% at 262K and 90% at 1M (8GB, 105k reads). held out and at 1.87M reads i guess 45% to 55% at 262K and 70% to 85% at 1M. 1.87M reads should raise the repeat rate, not lower it, because the 100M unique keys of the database get touched many more times than at 105k reads. this is the direction opposite to what round 1 C assumed ("in-sample coverage at fixed K drops"). both are guesses; the trace in step 1 settles it.
- probe cost Tf: about 20% of Td for 1M entries (16 MB), about 10% for 262K (C's table, Tf/Td 0.20 and 0.41 at its guesses; i think 0.41 is pessimistic because stage a prefetches the front line).
- gain on user cpu = s x (h - Tf/Td) = 0.20 x (0.80 - 0.25) = 11% at 1M, 0.20 x (0.50 - 0.15) = 7% at 262K.
- cpu to wall: classify is 9.2 of 12.2 s. assume wall follows cpu inside classify: 11% x 0.75 = 8%, 7% x 0.75 = 5%.

my claimed range at 103GB, T=32: 5% to 9% wall (0.6 to 1.1 s of 12.2 s), center 7%. C's kill line is 3%. the range clears it by 2x at the low end.

## 3. the bandwidth argument, corrected honestly

the task brief says a front hit frees memory bandwidth at 32 threads. checked by arithmetic: 218M lookups x 1.1 lines x 64 B = 15 GB over 9.2 s = 1.7 GB/s. that is nothing against DRAM bandwidth of a two-socket xeon (hundreds of GB/s). the run is not bandwidth bound. i drop the aggregate-bandwidth claim.

what survives is a latency-and-concurrency claim. a core has about 10 to 16 line fill buffers and 2 to 4 page walkers. the 16-wide S19 batch keeps 16 big-table lines plus their walks in flight per thread. when walkers and fill buffers saturate, prefetches stall or drop, which is exactly the GetAt 6.7% at T=32. a hit removes a request from that queue, so the remaining misses see a shorter queue and less contention. it is a super-linear effect on the miss path, which a simple h x share bound does not credit. it is also unmeasured, so i count it as upside only, not in my range.

## 4. design variants i would run, in order

v0, nearly free to build (half a day): no offline file. at startup, process the first 50k to 100k reads in-process, count minimizer hashes, keep the top K in a hash table of exact (hc, value). cost: a counting pass of about 6M lookups (around 5% of a 1.87M-read run if done naively, so use 20k reads, 2.3M lookups, about 1%) plus one table build. this is the version for the paper because the user needs no extra file. probe goes at the same spot as GetAt (C's v0). expected gain about zero by itself, its job is the identity harness. do not read a v0 null as a design null.

v1, the real test: three-stage pipeline. stage a: compute hc for batch i+2, prefetch the front line. stage b: probe front for batch i+1; on hit store value and mark done; on miss issue the big-table PrefetchIndex. stage c: GetAt only the not-done slots. hits skip the 9.7% PrefetchIndex cost and the 6.7% GetAt cost. this is where the money is.

absent-key sentinel: store hot absent keys with value 0. 13% of lookups are absent and an absent lookup costs 1.316 lines against 1.073 for present ones, plus the probe runs to an empty cell. if absent keys repeat like present keys they ride free. ask agent A for the absent repeat rate, it was not measured. cost of being wrong: none, the entry just sits in the table.

hot set source:
- from reads (pilot or offline): what i bet on. measured coverage numbers all come from reads.
- from the database alone: cannot rank by frequency because the db has no read statistics. a proxy is high-copy minimizers (those whose cell holds an LCA near the root, i.e. shared across many taxa); such k-mers are hit by reads from any organism. this needs one pass over the 103 GB table, which is a build-time cost paid once per database. worth one experiment: compare in-sample, held-out-reads and db-only hot sets on the same 1.87M reads. if db-only gets within 10 points of read-derived, the hot set can ship inside the database and drift is irrelevant.

size sweep: 64K (1 MB), 262K, 1M, and 2M entries, with 0 as the overhead control. 1M at 16 B per entry is 16 MB, the interesting row. coverage is 90% at 1M and 81% is the ceiling for repeated keys (the 90% is of a hot set that includes unique-in-window keys). beyond 2M the L3 budget (105 MB shared with the big table's lines) says stop.

SIMD probe: 64 B line holds five 8-byte keys plus values (C's layout), one AVX2 compare for four keys and a scalar fifth, or 8 compressed 4-byte tag keys plus a verify. the hit path is one load and one compare. matters because at hit rates near 80% the probe is on the critical path of most lookups; a scalar loop over five keys costs perhaps 8 to 10 cycles extra per probe, which is a large part of Tf. do SIMD from the start, not as an afterthought.

## 5. what it does at 8GB

8GB: table 8.6e9 cells... the table is 8 GB, so it does not fit L3 either (105 MB) and lookups still go to DRAM. the same savings apply per lookup but the share is smaller and the guard saves less.
- known: lookup 7.7% of cpu at T=1 (15% of user, load excluded). T=32 share unknown. at 103GB the T=1 to T=32 share grew 9.6x because contention made GetAt stall; 8GB has lower page-walk cost (smaller table, fewer PTE misses) so growth is smaller.
- bound: s_user between 0.10 and 0.20, h 0.45 to 0.8, Tf/Td about 0.3 (Td is smaller at 8GB, so the probe is relatively dearer): gain 0.10 x 0.15 = 1.5% to 0.20 x 0.5 = 10% on user cpu. wall: classify is about 6 of 8.6 s post-guard, so 1% to 6%.
- my claim: 2% to 4% wall at 8GB, which is near or inside the 2 x noise floor (round 5: under 15% is noise for single runs, 3 to 4 interleaved reps in E5 resolved 6%). state it plainly: 8GB may be flat, and the paper's claim should be the 103GB result with 8GB reported as "no loss, small gain". the 8GB cell must not lose more than 1% (C kill rule 4).

## 6. rebuttals to the prosecutor

"S19 already overlaps latency, so a hit saves nothing." the data contradicts it: GetAt is 0.6% at T=1 and 6.7% at T=32. overlap works at one thread and breaks under contention, which is the regime that matters. PrefetchIndex at 9.7% is itself cost, a real instruction and TLB stream, that a hit deletes. overlapped latency is not free: it still occupies fill buffers, walkers and issue slots, and the batch depth is only 16.

"a cache hit costs an L3 access, same order as the thing it saves." a DRAM miss on a 103 GB table is 90 ns raw and also pays a page walk, so a mismatch of about 3x on the line and more on the walk. the front probe is one L3 access to a line that stage a prefetched one batch earlier, so it is mostly hidden. break-even is h above Tf/Td, which is 10% to 25% by my numbers against measured hit rates of 45% to 85%. the old negative (round 4: h* near 20% against a small-cache h of 10.65%) was about 4K to 16K entry per-thread caches. at 262K to 1M entries the hit rate is 40% to 90%. the old result does not carry over, and the ledger says so (item 11, 12).

"cache pollution: 32 threads each pushing the big table's lines through L3." the front table is one shared 4 to 16 MB copy, not 32 x 6 to 25 MB (the per-thread design is the one with a 201 MB vs 105 MB problem, ledger section 3 item 9). a hit also removes a big-table line from L3, so the front table reduces pollution by h x lookups. only 18.4% of lookups touch a unique line in the 8GB trace, so most big-table lines are one-shot anyway and are not displaced usefully.

"drift: the hot set goes stale." a static table built from the same run's first reads, or from a pilot of the same sample, does not drift within a run. across samples drift is real, and untested: no held-out run exists (ledger section 3 item 4). but 16 fastq files exist, so the test is cheap. the dominant hot keys are conserved minimizers and high-copy genomic content, which should transfer between samples of similar composition. if held-out static is under 25% at 262K, i concede (C kill rule 2).

"2% bound, you said the cache gain is capped at 6% to 8% at 262K LRU." that bound is for a per-thread dynamic cache at 262K with T=1 hit rates and full probe cost. a shared static table at 1M reaches h 70% to 85% where LRU at 262K reached 40%. the ledger rows show LRU 76% at 1M, so 1M is the point where dynamic and static meet, and static has no eviction cost.

"the guard already gave 1.64x, so a 7% cache win is noise next to it." wrong frame. the guard is on a different axis (report path, 7.9 s). after the guard the lookup is 20% of user time and the cache is the largest remaining single-function target that is not kernel or minimizer. it has to be measured against the guard binary, and that is how i propose it be run.

## 7. where my case is weak (stated, not hidden)

1. no T=32 reuse trace exists. all hit rates are T=1, 8GB, 105k reads. shared static sees every thread's reads, so for a static table T does not matter (the table is built from all of them), which is a point for static, but the 103GB numbers are untested.
2. Td_eff at T=32 is not measured. my 25% Tf/Td is a guess.
3. the PrefetchIndex 9.7% might be mostly instruction cost, not stall, and skipping it saves only the instruction cost on hits. still positive.
4. 8GB T=32 profile is missing. my 8GB range is a bracket.
5. if the front table is not L2/L3 resident at 32 threads (the kernel's 21% and the big-table fills evict it), Tf is a DRAM access and the design dies. 16 MB is the risky size; 1 to 4 MB is safe. this is why the sweep includes 262K.

## 8. kill criterion i accept

i accept C's numbers, plus one of mine:
- step 0 gate: lookup share of user time at T=32, 103GB under 10%, close the cache work.
- trace gate: held-out static h at 262K under 25% on both dbs.
- build gate: median paired speedup under 3% at 103GB T=32, or under 2 x the A/A noise floor, against the S19 guard binary.
- 8GB must not lose more than 1%.
- any byte difference in per-read output kills the variant.
- mine: perf counters must show big-table LLC load misses falling by at least half of h x lookups. a time gain with no miss reduction is not credited to the design.

## summary (6 lines)
1. a front hit deletes the GetAt stall (0.6% at T=1 to 6.7% at T=32 proves exposed latency) and the PrefetchIndex cost (9.7%, includes the page walk), so it is not hidden by S19.
2. best case 103GB T=32: ceiling 13% to 17% of cpu, my estimate 5% to 9% wall (center 7%) at h 50% to 80% and probe cost 15% to 25% of a miss.
3. 8GB: 2% to 4% wall, bracket 1% to 6%, likely inside noise; report it as no loss. the memory-bandwidth argument is dropped (1.7 GB/s measured by arithmetic), only fill-buffer and page-walker contention survives.
4. build order: v0 in-process pilot (nearly free), then v1 three-stage pipeline with SIMD probe, absent sentinel, sweep 64K/262K/1M/2M, plus a database-only hot set experiment.
5. rebuttals: overlap fails at T=32, shared static avoids the 201 MB per-thread pollution, old negatives were 4K to 16K entries, drift is a cheap held-out test.
6. kill: lookup share under 10%, held-out h under 25%, build under 3% or 2x noise vs the guard binary, 8GB loss over 1%, any byte diff, or no miss reduction in perf counters.
