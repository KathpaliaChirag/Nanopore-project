# round 3, agent A: eviction, replacement, organisation ideas that could plausibly win

axis: what replacement, admission or organisation change could produce a positive result. read first: all six round 1 and round 2 files. nothing run, no luna, only this file written. sources marked [opened] were returned by search with their abstract or content read; [unverified] means only secondary descriptions or a bare search hit, or my memory.

## 0. the frame that decides everything

the round 2 files agree on one equation and i use it throughout. a software lookup cache pays its probe cost Tp on every lookup and saves a table miss cost Td on a hit. net per lookup = h x Td - Tp, so break-even hit rate is h* = Tp / Td.

two consequences nobody has fully used yet:

1. there are two ways to win. raise h (replacement, admission, capacity) or lower Tp (cheaper probe, one cache line per set, simd tag compare). the null so far came from only pulling the first lever and, at 64-way, making Tp worse while h rose (3.58% to 27.75% hit, -0.40% to +3.86% time, round 2 A).
2. replacement policy can only change h among hits that exist. the data says 54% of lookups are repeats at T=1 (3.0M window), 90.7% globally (M5), and 81% of those repeats sit at distance 1e4 to 1e6. so the ceiling on h for a cache of N entries is the fraction of repeats within reach of N. a 16K-entry cache (about 1 MB at 64 B per 4-way set line, my arithmetic) reaches only the distance under 1e4, roughly 10% of all lookups (round 2 A arithmetic: 19% of 54%). no eviction policy can beat Belady, so Belady at N entries is a hard upper bound on h. that bound has never been computed on the real trace. computing it is cheap and is my experiment 1.

worked example of why policy cannot rescue a distance problem. cache holds N=16K entries. a key repeats at distance 100K lookups. between its two uses, 100K other lookups happen, about 54% of them repeats of other keys and 46% first-touches. under LRU the key is evicted after about N new distinct keys, i.e. about 16K to 30K lookups. LRU misses it. a smarter policy (SRRIP, Hawkeye) could keep it only by evicting something else that is used sooner, and there are at most 16K slots for the roughly 50K distinct keys that arrive in 100K lookups. the best any policy does is keep the 16K with the nearest next use. that is exactly Belady and it is the number to measure.

## 1. idea catalogue

format per idea: mechanism, why it might or might not help given the profile, cost, sniper, luna.

### 1.1 RRIP / SRRIP / DRRIP (hardware policy, usable in software)
- source: Jaleel, Theobald, Steely, Emer, "High Performance Cache Replacement Using Re-Reference Interval Prediction (RRIP)", ISCA 2010, ACM SIGARCH CAN 38(3) 60-71 [opened as abstract/summary via search, full text unverified]. url: https://www.scilit.net/publications/ab158107b3e6646f0d1043bbb5c9046e . 2 bits per line; SRRIP inserts at "long" re-reference interval so one-touch lines leave fast (scan resistant); DRRIP set-duels SRRIP vs bimodal BRRIP (thrash resistant).
- relevance: 46% of lookups are first-touch keys that never return soon. under LRU each pollutes a way for N insertions. SRRIP inserts them at distant-ish RRPV and evicts them before re-referenced lines. this is the correct mechanism class for a stream that is half one-shot. the 4-way LRU in the current cache gives exactly the pollution case.
- limit: it re-orders within a set. with 4 ways the choice space is tiny (4 candidates), so SRRIP and LRU differ little at 4-way. gains show at 16-way and up, which is where Tp is already worse.
- cost in software: 2 bits per entry. the S2Entry has free padding (24 bytes with free padding, memory note), so storing a 2-bit rrpv is free. aging loop on a miss costs a few extra compares in the set.
- sniper: ships srrip (a 2019 sniper mailing-list thread shows `replacement_policy = srrip` with an `srrip` subsection `bits=2`) [opened: https://groups.google.com/g/snipersim/c/FqdohnPQyS8]. but that applies to the simulated hardware caches (L1, L2, nuca). the software cache is program data, so sniper models it only by running the modified binary. hardware srrip on the LLC acts on the 0.2 to 0.5% of loads that reach it (round 2 B), so predicted null.
- luna: yes, in the existing 4-way to 64-way software cache, about half a day. it needs no new data structure.

### 1.2 SHiP and signature-based predictors
- source: Wu et al., "SHiP: Signature-based Hit Predictor for High Performance Caching", MICRO 2011 [unverified, only secondary descriptions seen; the MIT-hosted pdf url from search was https://people.csail.mit.edu/emer/media/papers/2011.12.micro.ship.pdf, not opened]. predicts reuse per signature (PC or memory region) and picks the RRIP insertion value from it.
- relevance: kraken2 has one lookup site, so a PC signature carries no information. a different signature could be useful: the table bucket region, or a hash of the minimizer's low bits, or a per-read property (read is repeat-rich, e.g. low complexity or a high-abundance organism). the S4.0 earlier finding that adaptive-by-biology ideas rested on a bug hash (memory note) means this needs fresh measurement, not trust.
- cost: a signature history counter table, small. real design effort, 2 to 3 days. gain bounded by 1.1 and by Belady.
- sniper/luna: software only; luna possible, not quick.

### 1.3 Hawkeye and Mockingjay (Belady-approximating)
- Hawkeye: Jain and Lin, "Back to the Future: Leveraging Belady's Algorithm for Improved Cache Replacement", ISCA 2016 [opened via search: https://www.cs.cmu.edu/~18742/papers/Jain2016.pdf]. OPTgen replays past accesses with OPT to label each line cache-friendly or cache-averse; a PC-indexed predictor learns the label.
- Mockingjay: Shah, Jain, Lin, "Effective Mimicry of Belady's MIN Policy", HPCA 2022, doi 10.1109/HPCA53966.2022.00048 [opened via search: https://www.cs.utexas.edu/~lin/papers/hpca22.pdf]. predicts reuse distance (multiclass) and evicts the line with the furthest predicted next use. reported single-core gain over LRU 5.7% vs 6.0% for MIN and 4.5% for Hawkeye, 92% of evictions mimic MIN. code: https://github.com/ishanashah/Mockingjay [url from search, repo not opened].
- relevance: the useful part is the idea, not the hardware. both depend on a PC signature that separates friendly from averse loads. with one lookup site and a table of mostly unique keys, the predictor has little to separate. a software version would need a key-derived signature, which is a hash of the very thing being cached, and that is what the cache itself already tests.
- value for us: Mockingjay's own paper contains a method to compute Belady on a trace. use it as the upper-bound tool (experiment 1), not as a design to ship.
- cost: high for the predictor; the offline Belady replay is a few hours of code.
- sniper: not shipped; custom policy needs C++ in sniper's cache_set code and only affects hardware levels. not worth it.

### 1.4 reuse-distance-aware bypass and admission filters
- mechanism: do not insert a key until it has shown it can repeat. variants: doorkeeper bloom filter (insert only on second touch), TinyLFU frequency sketch, sampled reuse-distance bypass.
- TinyLFU: Einziger, Friedman, Manes, "TinyLFU: A Highly Efficient Cache Admission Policy", ACM Transactions on Storage 13(4), Nov 2017 (arXiv 1512.00727, earlier PDP 2014) [opened abstract: https://arxiv.org/abs/1512.00727]. an approximate LFU counter built on bloom-filter theory decides if a new object may displace the eviction victim; W-TinyLFU adds a small window LRU in front and equals or beats other state-of-the-art policies on the paper's traces, integrated in Caffeine.
- relevance: this is the best match to the profile, because 46% of lookups are one-shot. a plain "second touch" filter has a problem here: 81% of repeats are 1e4 to 1e6 lookups apart, so the filter itself must remember keys that long. a bloom filter sized for 1e6 recent keys is about 1.2 MB at 10 bits per key (standard bloom rule of thumb, my arithmetic), which is bigger than the cache it protects and is itself a random access of cost Tp. so naive doorkeeper doubles probe cost. TinyLFU's 4-bit counters at 1e6 keys are about 0.5 MB. still L2-class, still a probe.
- the real win would be a filter that is tiny and acts before the cache probe, so first-touch keys cost nothing extra. no such free signal exists in the key itself. exception: the minimizer hash already computed by kraken2. its extra bits can index a small counting filter; the filter lookup is one more random access.
- expected effect: raises h at fixed capacity by dropping pollution. upper bound set by 1.5 below (frequency skew). cannot lower Tp, so by the equation it only wins if h rises faster than Tp.
- sniper: program-level, run the binary. luna: yes, 1 to 2 days.

### 1.5 static hot-set (offline frequency admission, "pinned" top-K)
- mechanism: profile once, take the K most frequent minimizers (or K table buckets), place them in a small dense array that stays L1/L2 resident, never evict. LFU-oracle with zero runtime eviction logic. related to the "frequency" half of TinyLFU/LFU.
- relevance: succeeds only if frequency is skewed. the data so far gives reuse distance, not frequency. 90.7% of 351.8M lookups are repeats while only 32.8M are unique, so the average unique key is looked up 10.7 times. that is an average; if the distribution is heavy-tailed (a few thousand minimizers carry tens of percent of lookups, e.g. low-complexity or highly conserved sequence), a small static set gets a high h at tiny Tp. if flat, it is dead. one number answers it: lookups covered by the top 16K, 64K, 262K unique keys. this was never extracted from the histogram work, which kept distance and not frequency.
- caution: 81% of repeats at distance 1e4 to 1e6 weakly argues against a few extremely hot keys (very hot keys would produce short distances). it argues for a flat-ish frequency over many keys. so predict the coverage curve is gentle (the top 16K covering maybe a few percent to 15% of lookups, guess).
- sniper/luna: coverage is a trace computation (hours); a static array is trivial on luna.

### 1.6 ARC, LIRS, 2Q (database/buffer-pool policies)
- ARC: Megiddo and Modha, "ARC: A Self-Tuning, Low Overhead Replacement Cache", USENIX FAST 2003 [opened: https://static.usenix.org/event/fast03/tech/full_papers/megiddo/megiddo.pdf]. two lists (recency, frequency) plus ghost lists, self-tunes the split, scan resistant. LIRS: Jiang and Zhang, SIGMETRICS 2002 [unverified, only a secondhand description seen]. ranks by inter-reference recency, keeps about 1% of the cache for new (HIR) blocks.
- relevance: both need per-entry list pointers or ghost metadata that costs bytes and pointer chasing, which is the opposite of a 4 to 16 entry flat set. ARC's ghost lists are a way to get reuse distance beyond the cache (they remember evicted keys), which is exactly the long-distance repeat case, but the metadata for 1e6 ghost keys is again an L2/LLC-sized structure.
- verdict: good as a simulator reference (trace replay, section 3), not as a shippable design.

### 1.7 way partitioning (Intel CAT)
- mechanism: Cache Allocation Technology gives software a bitmask of LLC ways per class of service, set via msr-tools or `pqos` from intel-cmt-cat [opened: https://www.intel.com/content/www/us/en/developer/articles/technical/introduction-to-cache-allocation-technology.html and https://documentation.ubuntu.com/real-time/latest/tutorial/intel-tcc/intel-cat ]. reported: a CMU/Intel networking study found CAT cut tail latency by up to 5.3x, benefit largest for small working sets (as summarised by search, original not opened) [unverified].
- relevance: a CAT experiment would reserve ways for the table's hot region or for the software cache array, protecting them from streaming read data (the reads and the minimizer buffers are one-shot streams). real luna has 105 MB LLC per socket (memory notes), the 8 GB and 103 GB tables are far above it, so what CAT could protect is small hot structures (taxonomy, the cache array, ring buffers). those are already L2-resident (99% L1d hit in sim). expect null for the table itself because the table is random with 80% LLC miss (round 2 C), and reserving ways for it just shrinks space for others.
- risk: needs root, the luna kernel and whether resctrl is exposed are unknown to me; a VM would hide it [unverified: whether luna allows it].
- sniper: cannot model CAT directly; one could shrink nuca size per core as a proxy. not valuable.
- luna: possibly quick if root is available; 1 day. predicted null; its value is a clean negative claim, low priority.

### 1.8 victim cache / skewed-associative / cuckoo-style placement
- mechanism: a small fully associative buffer holds the most recent evictees (Jouppi style victim cache; i am citing the concept from memory, not a source opened). skewed-associative uses a different hash per way so conflicts spread. cuckoo-style insertion moves an entry to its alternate location.
- relevance: the 4-way to 64-way jump shows hit rate is capacity and conflict limited: 3.58% at 16K entries 4-way versus 27.75% 64-way at 262K entries, but note these numbers mix capacity and associativity (round 1 B, memory note says 16K to 262K entries). to separate them, run 64-way at 16K entries total. if conflict misses are the issue, 16K-entry fully associative should sit well above 3.58%. a victim buffer of 8 to 16 entries recovers conflict misses cheaply and does not add a random access (it sits in the same line as the set or in one L1-resident line).
- cost: tiny. effect bounded by the conflict-miss fraction, only measurable by trace replay.
- sniper: program-level. luna: yes.

### 1.9 dead-block prediction
- Khan, Tian, Jimenez, "Sampling Dead Block Prediction for Last-Level Caches", MICRO 2010 [unverified: search returned nothing for this paper, citation from memory]. predicts when a block will never be reused so it is evicted or bypassed early.
- relevance: same as admission, with a PC signature. with one lookup site it reduces to "which keys are dead", and the only evidence available is the key, so it collapses into 1.4.
- skip.

### 1.10 genomics prior art
- kache-hash: Khan, Patro, Pandey, "kache-hash: A dynamic, concurrent, and cache-efficient hash table for streaming k-mer operations", preprint, not peer reviewed (as stated by search) [opened summary: https://bio.sciencecast.org/casts/r5yehc1k467z ; code github jamshed/kache-hash, not opened]. it builds on Iceberg hashing but uses minimizer-based hashing so consecutive k-mers land in the same buckets; reports 1.58 to 2.62x insert and up to 6.1x query throughput over IcebergHT and 7.39x fewer cache misses on the human genome. the relevance for us: it wins by changing placement (locality between neighbouring k-mers), not by adding an eviction cache. that supports agent C's "wrong layer" reading. kraken2 already looks up minimizers (one per window), so consecutive minimizers are far apart in the table by design of a hash; kache-hash's trick would apply only if the table used a minimizer-of-minimizer bucket map. this is a layout change to the 103 GB table, big work, but it is the one genomics result that reports a large cache-miss reduction.
- Kraken 2 itself: Wood, Lu, Langmead, "Improved metagenomic analysis with Kraken 2", Genome Biology 2019, doi 10.1186/s13059-019-1891-0 [opened: https://link.springer.com/10.1186/s13059-019-1891-0]. the speedup over kraken 1 comes from querying only distinct minimizers per read. i found no kraken2-variant paper with a lookup cache or eviction policy in this search (one search, not exhaustive). MetaCache, MegIS, MetaCache-GPU, GPMeta are already on the must-cite list in memory and i did not re-open them. my honest finding: no comparator does eviction (matches the earlier 5-agent debate).

## 2. which ideas can sniper model

sniper ships these replacement policies as far as i recall: lru, lru_qbs, nru, mru, nmru, plru, srrip, random, round_robin [from memory; local sniper source is not in the repo, so unverified. confirm with `ls sniper/common/core/memory_subsystem/cache/cache_set_*.cc` on the machine that has it]. only srrip is confirmed by the mailing-list thread above.

key limit: all of them act on simulated hardware caches (L1d, L2, nuca/L3). round 2 B showed the nuca slice sees 0.2 to 0.4% of loads in every measured cell and the flat 105 MB L3 run mostly measured latency-model artifacts. a hardware srrip or plru sweep therefore returns a null for the same reason the hw_assoc sweep did. sniper can model a software cache only by executing the modified binary, which was already done (the 4-way to 64-way runs). adding sniper time to eviction policy ideas buys nothing the trace replay in section 3 does not give faster and with exact numbers.

## 3. top 3 experiments, ranked

### rank 1: offline trace replay, Belady bound plus every policy at once (no luna runtime, no sniper)
- hypothesis: even Belady at 16K, 64K and 262K entries (fully associative and 4/16/64-way) gives an h below the break-even h* = Tp/Td, so no eviction or admission policy can produce a wall-clock win for the software cache. if instead Belady gives h well above h*, there is room and policies close part of the gap.
- how: dump the lookup key sequence per thread from the existing instrumented binary (the S4.0 reuse histogram already instrumented this) for standard_8gb at T=1 and a 3M to 30M lookup window, plus one T=32 run per-thread streams and merged. write one trace replayer (about 200 lines C++ or awk is not enough; use C++ built on luna, the user's windows box has no compilers per memory) running: LRU, SRRIP, BRRIP, 2-touch doorkeeper, TinyLFU, ARC, static top-K (LFU oracle), Belady. also output the frequency coverage curve (section 1.5) and the per-thread vs shared-cache comparison.
- predicted effect size: LRU fully associative at 16K entries lands near 10% (the near-distance repeats), at 262K about 30 to 40% (the 27.75% measured at 64-way plus remaining conflicts). Belady at 16K maybe 15 to 25%, at 262K maybe 45 to 60% (reasoning: 54% of lookups repeat in the window, so Belady at big N cannot exceed 54% at T=1; my guess for how much of the 54% it reaches). SRRIP/TinyLFU recover maybe a third of the LRU-to-Belady gap. all numbers are guesses and the experiment exists to replace them.
- cost model: put the measured Tp (from the 64-way run, probe cost per lookup) and Td (8 GB table miss) into h*. one clean table gives each policy's predicted net.
- measure: h per policy per size, Belady h, coverage curve, h* from existing timing (time delta / hit rate arithmetic from the 5-row table).
- runtime: 1.5 to 2 days (half day trace dump, one day replayer, half day analysis).
- kill criterion: if Belady at 262K entries is under h* (about 33% by round 2 A's illustrative Tp=30 ns, Td=90 ns, both guesses), the eviction axis is dead, write that as a negative result with the bound as the proof, and stop. if Belady at 16K to 64K is under 15%, drop all small-cache policy work.

### rank 2: cut Tp, not raise h: one-cache-line sets with simd tag compare, SRRIP and admission inside the line
- hypothesis: the null arises because every extra way costs an extra dependent compare and extra cache lines. if a 16-way set fits in one 64 B line (16 tags of 16 bits = 32 B, payloads in the second half or a parallel array) and tags are compared in one simd instruction, Tp stays at one L1/L2 access regardless of ways. then moving 4-way to 16-way raises h from 3.58% to 10.65% (measured) with flat Tp, and the net turns positive iff 10.65% x Td exceeds the unavoidable cache access cost.
- predicted effect: with Td=90 ns, h=10.65% saves 9.6 ns per lookup, minus an L2 access at maybe 4 ns for 1 MB array = about 5 ns per lookup on lookups that are 19.5% of cpu (round 2 C). 50 MB: lookups time share 19.5% so up to 19.5% x (5 / 90 normalised ...) is tiny, about 1% wall on 50 MB; on 8 GB with Td larger it could reach 2 to 4% (guess). that is a small positive, consistent with the 1 to 4% steps S12 to S18 already delivered and not with a headline result. this was already logged as week7plan item 5 with s2_lru_4way_simd_patch.py written and unbuilt (memory note), so it is the cheapest to resume.
- extras inside the same patch: SRRIP 2-bit state packed in padding (1.1), 8-entry victim slot (1.8). run each as a one-flag ablation.
- measure: wall time via the same multi-file, hugepage stack that the ablation used (S6 style with and without the cache, as round 2 A required), hit rate, perf stat cycles and instructions, 5 repeats on 8 GB and 16 GB, byte-identical output check.
- runtime: 3 days (build and debug 1.5, measurements 1, writeup 0.5).
- kill criterion: if 16-way simd shows under +1% on 8 GB with 5 repeats (noise band under 0.6% from S7/S11/S20) or if rank 1 shows Belady at 16K entries under 15%, stop.

### rank 3: static hot-set plus doorkeeper-free admission (frequency, not recency)
- hypothesis: if the coverage curve from rank 1 shows the top 64K unique keys carry at least 25% of lookups, a read-only precomputed array of those keys with answers (built from a profiling pass on a sample of reads, 64K x 16 B = 1 MB, L2 resident) gives h of 25% at one L2 access and zero eviction logic, which beats any dynamic 64-way cache at the same size. if the curve is flat (top 64K under 10%) the idea is dead.
- predicted effect: the curve is likely gentle (section 1.5 caution), so i predict top 64K covers 8 to 15% of lookups. that gives h around 10% with Tp of one L2 hit and almost no insertion cost, comparable to rank 2's 16-way result without the set-search machinery. wall gain 0 to 2% on 8 GB. caveat: a static set tuned on one sample depends on the sample's biology; across samples the benefit changes, which is exactly the "biology-dependent" angle sir asked for and the one place an adaptive policy could be justified.
- measure: coverage curve (free from rank 1), then on luna the wall time of a build-time-generated array on held-out reads from a different sample, same DB, plus the cost of building it.
- runtime: 1 day for the curve and decision, 2 more days only if the curve passes (so 1 to 3).
- kill criterion: top 64K under 10% coverage, or held-out sample coverage under 60% of the training sample's coverage.

CAT (1.7) and ARC/LIRS/Hawkeye (1.3, 1.6) are not in the top 3 on purpose: CAT predicts null for the random-miss table, and the others are covered by rank 1 as trace-replay comparisons without building them.

## 4. what would be a publishable positive or negative from this axis

- positive only through rank 2 or 3, and only at the 1 to 4% scale, not a headline. the memory note that real wins came from prefetch, hugepages and pipeline stays the correct ranking. the realistic framing is a bound: "Belady upper bound on kraken2 minimizer lookup caching, with measured break-even", which rank 1 alone delivers and which no kraken2 variant paper reports in my one search.
- a negative result with the Belady bound is stronger than the current null, because it removes the "maybe a smarter policy" escape hatch that round 2 A, B and C all left open.
- trap list: do not cite the old 22x cliff or the +25.2% pinning gain (both superseded, memory notes); do not claim "8-way L2" for orion (retracted); the 19.5% lookup share is 50 MB only, big-table share unprofiled; all Tp and Td values here are illustrative guesses until measured.

## summary (8 lines)
1. break-even rule h* = Tp/Td means a cache can win by raising h or by lowering Tp; only the first has been tried.
2. replacement policy cannot beat Belady, and Belady on the real minimizer trace was never computed; that bound is the highest-value experiment.
3. SRRIP/BRRIP fit the 46% one-shot first-touch stream, but at 4 ways there is little to choose from, and at 16 to 64 ways the probe cost has already killed the win.
4. admission (doorkeeper, TinyLFU) is the best conceptual match, but its filter needs a 0.5 to 1.2 MB structure to remember 1e4 to 1e6 distance repeats, so it adds its own probe.
5. SHiP, Hawkeye, Mockingjay, dead-block need a PC signature; kraken2 has one lookup site, so they reduce to the cache's own key test; use Mockingjay's trace method only for the upper bound.
6. sniper ships srrip (confirmed by a mailing list thread) plus likely lru, nru, plru, mru, random; all act on hardware levels that see 0.2 to 0.5% of loads, so hardware policy sweeps in sniper repeat the known null.
7. top 3: (1) offline Belady plus all-policy trace replay, 1.5 to 2 days; (2) one-line 16-way simd set with SRRIP and victim slot, 3 days; (3) static top-K hot set, 1 to 3 days; CAT predicted null.
8. kache-hash (minimizer-locality placement, 7.39x fewer misses) supports the "layout, not eviction" reading; no kraken2 variant with an eviction policy found in one search, so a Belady-bound negative result is novel and safe to publish.
