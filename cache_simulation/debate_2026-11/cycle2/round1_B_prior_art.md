# cycle 2, round 1, agent B: prior art for caching the hot subset of a huge read-mostly hash table

scope: our workload is kraken2 minimizer lookups into an 8-104 GB open-addressing table, 4-byte cells. measured: 81% of lookups hit a slot seen before, top 262,144 slots = 56% of lookups, 1M slots = 90%, repeat distance mostly 1e5-2e6 distinct slots, ~13% of lookups are absent keys, lookup ~16% of cpu at T=32 on 103GB after prefetching.

verification key: [opened] = I fetched or saw the abstract/snippet in search this session. [unverified] = recalled from memory, not opened. web search was standard mode only; most hits were abstracts, not full text.

the one number that frames everything: 1M slots x 4 bytes = 4 MB. 262k slots = 1 MB. a hot set that small fits in L2/L3 of any modern core. so the question is not "can the hot set fit" (it can, trivially) but "how cheaply can we detect membership and serve a hit before we pay a DRAM miss". a hit on a cache that needs its own random DRAM access gains nothing, so the cache must live in L1/L2/L3.

## 1. frequency-based admission: TinyLFU, Count-Min, doorkeeper

- TinyLFU: a highly efficient cache admission policy. Einziger, Friedman, Manes. ACM Trans. Storage 2017, arXiv:1512.00727. https://arxiv.org/abs/1512.00727 [opened, abstract only]. earlier PDP 2014 version by Einziger and Friedman [snippet only].
- mechanism: approximate frequency histogram (Count-Min sketch, aged by periodic halving) decides whether a new item deserves to displace the victim. a small bloom "doorkeeper" absorbs one-hit wonders so the sketch only counts items seen twice. W-TinyLFU adds a small LRU window (Caffeine). sketch cost ~2 bytes per cache entry per Caffeine docs [opened, secondary].
- fit to our skew: strong in principle. skew is heavy (1M slots = 90%) and 19% of lookups are first-touch, which is exactly the one-hit-wonder traffic a doorkeeper filters. but our "cache" would be tiny (1-4 MB) and the per-lookup cost of a sketch update (4 hash probes) is comparable to the lookup work we save at L2 speeds. the policy is built for caches where a miss costs a disk or network trip.
- expected gain: small incremental hit rate over plain LRU at 1M entries; the hot set is stable across a run (static-ish), so admission matters less than in drifting workloads.
- cost: ~1 extra cache line touch per lookup for the sketch. risk: the sketch costs more than it saves. verdict: use as a one-time offline/online hot-set selector, not per-lookup.

## 2. static hot-set / pinned table (no eviction)

- no single paper; this is the classic "static caching" result: for stationary skewed traffic, pinning the top-K by frequency is optimal among non-clairvoyant policies (the independent reference model result, Coffman and Denning style) [unverified, textbook].
- mechanism: pass 1 (or a prior run, or a sampled prefix of reads) counts slot frequency; build a small dense table of the top-K keys with their 4-byte values; probe it first with a cheap hash. no eviction, no admission logic, read-only so thread-shared with no locks.
- fit: best match to our data. 262k keys = 56%, 1M = 90%. a 2-4 MB read-only open-addressing table sized at load 0.5 is 8 MB, fits L2/L3. our simulator saw 81% repeats; a static top-1M should capture most of that.
- risk: hot set depends on the sample/biology (which organisms in reads). must be built per run from a prefix of reads, or per database+sample class. a wrong set degrades to a pure extra-probe tax (~1 L3 hit per lookup). also the big table is shared across processes; kraken2 is one process, so per-run build is fine.
- expected gain: if 90% of lookups become L2/L3 hits (~10-40 cycles vs ~300 cycle DRAM miss), lookup time drops by up to ~5x on those; but with prefetch already hiding latency, real gain is bounded by the 16% of cpu: best case save ~10-13% of total cpu (about 1.1-1.15x end to end). this bound applies to every design below.

## 3. tiered hash table (small hot table in front of big cold table)

- F2: Designing a Key-Value Store for Large Skewed Workloads. Kanellis, Alagappan, Chandramouli, Kossmann, Kraska? [author list unverified] arXiv:2305.01516 / "From FASTER to F2". https://arxiv.org/abs/2305.01516 [opened via search snippets]. mechanism: hot index + hot log + cold index + cold log + a read cache; read-hot and write-hot sets treated separately. fits the idea; but F2 solves SSD-tier problems and compaction, which we do not have (our table is immutable at query time).
- FASTER (Chandramouli et al., SIGMOD 2018) [snippet only]: 8 bytes per key index overhead, hybrid log keeps hot records in memory in place. irrelevant mechanism, but confirms the "hot set in front" framing.
- fit: the idea matches option 2 (static hot table) in a read-only form. none of this code is reusable; the concept is.

## 4. KV-store skew exploitation: MICA, MemC3, cuckoo

- MICA: Lim, Han, Kaminsky, Andersen. NSDI 2014. https://www.pdl.cmu.edu/PDL-FTP/Storage/mica-nsdi2014.pdf [opened, snippet]. mechanism: partitioned (EREW) per-core tables, bucketed index with lossy eviction in cache mode, 8 entries per bucket (one cache line), batched requests with software prefetch of buckets. headline: 65.6 Mops, 4x others on skewed read-heavy loads. lesson for us: bucket = one cache line; batch + prefetch is what already got us here. skew help in MICA came from partitioning CPU load, not from a hot cache.
- MemC3: Fan, Andersen, Kaminsky. NSDI 2013. https://www.pdl.cmu.edu/ftp/Storage/memc3-nsdi2013.pdf [opened, snippet]. mechanism: optimistic concurrent cuckoo hashing (~95% load, 4-way buckets, 1-byte tags to skip key compares), CLOCK eviction (1 bit/entry). lesson for us: tags in the bucket let a probe reject most non-matching entries without touching the full key; our cells are 4 bytes already so there is no wider key to avoid. CLOCK is a cheap eviction if we ever want one.
- cuckoo hashing for our big table: bounded 2 probes per lookup worst case (vs linear probing's variable chain), but our table is built once (kraken2 build) and "double hashing was 1.8-2.5x slower" in E3 (local result). cuckoo would need a rebuild path and a second random DRAM access per absent key. verdict: not worth it for the hot-set goal.

## 5. front filters for absent keys (~13% of lookups)

- cuckoo filter: Fan, Andersen, Kaminsky, Mitzenmacher. CoNEXT 2014 [unverified, recalled]. bloom filter: Bloom 1970. blocked bloom / one-cache-line bloom: Putze, Sanders, Singler, "Cache-, hash- and space-efficient Bloom filters", WEA 2007 [unverified]. xor/ribbon filters (Graf and Lemire 2020; Dillinger and Walzer 2021) are more compact static options [unverified].
- mechanism: a small structure answers "definitely absent" for a key; absent lookups skip the DRAM probe. the 13% absent share is the cap on savings, and absent keys in linear probing are the costliest lookups (probe until an empty cell), so they may be worth more than 13% of time, perhaps ~20% [estimate].
- cost problem: a filter over 104 GB / 4 B = up to 26e9 cells is itself gigabytes; at 8-10 bits/key a bloom over ~20e9 keys is ~20 GB, which defeats the cache purpose (random DRAM access again). only works if the filter is cache-resident, i.e. covers just the hot set, which does not answer "absent". so a front filter helps absent keys only in the one case: a filter of hot ABSENT keys (negative cache). check whether repeated absent keys are common in the trace; if absent keys repeat like present ones, the static hot table can store "absent" as a sentinel value and the 13% rides along for free.
- kraken2 itself already has a form of this: the 16-bit-compact-hash "key" bits reject most false matches inside a bucket; no front filter in stock kraken2 [unverified recall of the source].
- verdict: fold absent-key repeats into the hot table; do not build a gigabyte filter.

## 6. metagenomic classifiers

- Kraken 2: Wood, Lu, Langmead. Genome Biology 2019. https://genomebiology.biomedcentral.com/articles/10.1186/s13059-019-1891-0 [opened, abstract]. minimizers: only distinct minimizers of a read hit the table (query-side dedupe, which is why our 81% repeat figure is across reads, not within). compact hash table, one third of standard. no hot-set cache reported in the paper.
- KrakenUniq: Breitwieser, Baker, Salzberg. Genome Biology 2018. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6238331/ [opened, snippet]. adds HyperLogLog unique k-mer counting; its cost is extra per-lookup work. relevant only as a precedent that kraken variants add per-lookup structures.
- Centrifuger: lossless run-block compressed BWT/FM-index, Song, Langmead 2024 Genome Biology (s13059-024-03244-4) [opened, snippet]. different substrate, no hot-set trick; per-read FM-index walks have their own locality.
- Metabuli: Kim et al., Nature Methods 2024 (amino-acid + spaced k-mer "metamer" index, sorted-array binary search) [unverified recall; search returned only benchmarks]. sorted arrays + "last-used" locality exist but I did not confirm any cache.
- MetaCache / MetaCache-GPU: Muller et al. 2017; Kobus et al. 2021 arXiv:2106.08150 [opened, snippet]. GPU multi-value hash table, bucket-list; speedup comes from GPU memory bandwidth not caching of hot keys.
- CLARK (Ounit et al. 2015), ganon / HIBF (Piro et al.) [unverified]: CLARK sorts/lays out keys in a discriminative-k-mer table; ganon uses interleaved bloom filters with per-bin bitvectors, which are the "front filter" idea taken to full-index scale. no hot-set caches documented.
- Sylph: Shaw and Yu 2024 [unverified]. avoids the problem: subsamples k-mers (FracMinHash c=200) so the index is tiny. a different accuracy/speed trade, not a cache.
- kache-hash: Khan, Patro, Pandey, bioRxiv preprint [opened, search abstract]. https://bio.sciencecast.org/casts/r5yehc1k467z . mechanism: Iceberg hashing with minimizer-based bucket placement so consecutive k-mers share buckets; reports 7.39x fewer cache misses and up to 6.1x query throughput. fits the "consecutive k-mers of a read are adjacent" case, but kraken2 already hashes one minimizer per window, so consecutive minimizers differ anyway. the transferable idea is hashing by something locality-preserving (e.g. a coarse minimizer prefix selects the 4 KB page, fine hash selects the cell). that is a big-table rebuild, changes false-positive behavior, and needs a new database format.
- finding: no classifier I could locate caches hot slots in front of the main table. this supports a (preprint-level) novelty claim, with the caveat that my search was standard mode and shallow, not an exhaustive review.

## 7. cpu-side tricks (some already in our build)

- huge pages: 2 MB/1 GB pages cut TLB misses on random DRAM access; already measured as a win in our S6-S15 work (local result). -M mmap flag mattered more. 104 GB table with 4 KB pages is ~25M pages; TLB reach is tiny. 1 GB pages (if the kernel/machine allows) would nearly eliminate TLB misses [unverified on Luna].
- software prefetch + batching: Chen, Ailamaki, Gibbons, Mowry, "Improving hash join performance through prefetching", ICDE 2004 / TODS 2007 [unverified]; group prefetching and AMAC (Kocberber et al., "Asynchronous memory access chaining", VLDB 2015) [unverified]. mechanism: interleave many in-flight lookups so DRAM latency overlaps. we already prefetch; the remaining 16% is probably residual latency plus probe chains, so a deeper batch or coroutine style could shave a few more percent.
- SIMD probes: compare a whole bucket of cells in one AVX2/AVX-512 instruction (as in SwissTable/F14 style tables, Folly F14 and Abseil raw_hash_set, 1-byte control-tag groups) [unverified]. relevant to the small hot table: with 4-byte cells, 8 cells per AVX2 compare, 16 per AVX-512, per 64 B line. our earlier hypothesis (sequential AoS scan vs parallel comparator, week7 item 5) matches this.
- for the big table with linear probing: a 64 B line holds 16 cells; the average probe stays in one line, so SIMD helps little on the cold table; it helps most on the hot table.

## 8. cost model sanity check (so ranks reflect the 16% cap)

- total lookup cpu = 16%. if the hot tier serves 90% at L2 speed (say 20 cycles vs ~100 effective after prefetch overlap), residual lookup time drops by at most ~70-80%, so end-to-end gain is ~11-13% at best. at smaller thread counts or without prefetch the lookup share is larger and gains grow. this is consistent with the earlier measured "1.64x at 103GB/T=32 with --report" being driven mostly by other stages; the cache is a polish, not a 2x.
- tagging every design with "must beat a ~100-cycle effective miss with a probe that costs <= ~20 cycles and zero locks" is the cleanest filter.

## ranked candidate designs for a real kraken2 build

1. static top-K pinned table, built from the first N reads (or a pilot pass), read-only, shared by all threads, sized 1-4 MB of cells (K around 262k-1M) at load ~0.5, plus an "absent" sentinel to capture repeated absent keys. probe before the big table; fall through on miss. cost: one extra L2/L3 probe on the 10-44% that miss; no locks; no eviction code. gain up to ~10-13% cpu. risk: stale hot set if reads shift; mitigated by rebuilding per run. this is the lowest-risk first experiment and our simulator already agrees with its premise.
2. per-thread small direct-mapped/2-way cache (the existing 4-way direction) with a bit of frequency gating: insert only after second sighting using a 1-bit doorkeeper (TinyLFU-lite). cost: one extra bit array lookup. benefit over (1) only if hot set drifts. risk: our own earlier result says plain 4-way cache was not the cause of the wins; this variant adds thrash protection for the 19% first-touch traffic.
3. SIMD-probed 8- or 16-way bucketed hot table (design 1's layout, but AVX2 compare over a 64 B bucket instead of scalar open addressing). cost: one gather-free compare; tags unnecessary since cells are 4 B. benefit: fewer cycles per hit and bounded probe length. low risk; do as the layout of 1, not a separate project.
4. deeper prefetch batching (AMAC-style, interleave 8-16 lookups instead of per-read prefetch) on the cold table. no hot-set assumptions, works for the 13% absent keys too. gain unknown, maybe a few percent of the 16%; try only if 1 shows the cold-path stall remains.
5. 1 GB huge pages (or at least verify 2 MB THP is on for the mmapped table) and a locality-preserving placement (kache-hash-style coarse-minimizer page selection). highest potential on cold-path TLB cost but largest change: new DB format, rebuilt hash, changes false-positive law. defer to the paper's future-work section unless 1-4 all fail.

not recommended: gigabyte-scale bloom/cuckoo front filter for absent keys (filter itself becomes a DRAM miss), cuckoo table replacement (build-path rewrite, extra probe for absent keys), per-lookup Count-Min updates (cost rivals the saving).

## gaps and caveats

- most citations are search snippets, not full papers. unverified: Metabuli algorithm details, CLARK, ganon, Sylph, cuckoo filter, blocked bloom, AMAC, F14, 1 GB page availability on Luna.
- F2 author list not confirmed.
- I did not check whether absent keys repeat in our trace; that decides whether design 1's absent sentinel pays. ask agent A (data) for the repeat rate among absent slots.
- 11-13% ceiling is my arithmetic from "16% of cpu"; confirm with a perf annotate on the lookup function after prefetch.

## summary (8 lines)
1. no classifier or KV store I found caches a hot slot set in front of a huge read-only table; the idea looks novel but my search was shallow.
2. our 1-4 MB hot set fits L2/L3, so a static pinned table is the natural design (optimal for stationary skew).
3. TinyLFU and Count-Min are for drifting disk/network caches; use only as a one-bit doorkeeper or offline selector.
4. MICA/MemC3 lessons (cache-line buckets, batching, tags, CLOCK) are already largely in our build or cheap to borrow.
5. a gigabyte front filter for the 13% absent keys defeats itself; store absent as a sentinel in the hot table instead.
6. lookup is 16% of cpu, so even a perfect cache caps end-to-end gain near 1.1-1.15x at T=32/103GB.
7. ranked: static top-K table, doorkeeper-gated per-thread cache, SIMD-bucketed hot layout, deeper AMAC prefetch, 1GB pages/locality placement.
8. next data needed: repeat rate of absent keys and a perf annotate of the post-prefetch lookup stall.
