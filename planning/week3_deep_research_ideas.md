# Week 3 — Deep Research Pass: Ideas From Outside Bioinformatics

Started 2026-08-17, same day as the Kun-peng close read. Sir's ask ("ask LLMs for additional ideas") plus your own push to stop treating Kraken2 as a bioinformatics-only problem and start treating it as a general lookup/caching system with biology as one specific workload — this doc is that search. Findings get added and committed one topic at a time as agents report back, not batched at the end, so you can watch this fill in.

Each section: what was searched for, what came back, and — the part that matters — whether it's a real lead or a dead end. Dead ends get kept, not deleted, so nobody re-runs the same search in three weeks.

---

## LLM KV-cache eviction as the model for Thesis 1's eviction policy

**The reframe that motivated this search:** an LLM's KV-cache and Kraken2's k-mer lookup cache have the same shape — both are "keep the hot entries near compute, evict the cold ones, and the access pattern is skewed and bursty, never uniform." Nobody in either literature seems to have said that sentence out loud before this search. That gap is the finding.

Five mechanisms, each with a concrete translation to k-mer caching:

1. **H2O (Heavy-Hitter Oracle)** — Zhang et al., NeurIPS 2023 ([arXiv:2306.14048](https://arxiv.org/abs/2306.14048)). Scores each cached token by *cumulative* attention received so far, evicts low scorers, always protects a fixed recent window. **Translation:** score each cached k-mer by cumulative lookup count *within the current read*, protect a fixed window of the last N minimizers scanned. This is close to a drop-in replacement for the current 4-way baseline's eviction rule.

2. **StreamingLLM (attention sinks)** — Xiao et al., ICLR 2024 ([arXiv:2309.17453](https://arxiv.org/abs/2309.17453)). Discovers that the first few tokens of any sequence absorb outsized attention regardless of content, and must be pinned permanently rather than left to recency-based eviction. **Translation:** the genomic version of an "attention sink" is a small set of near-universal conserved k-mers (rRNA genes, low-complexity regions) that get hit constantly across species. Pin them unconditionally instead of letting per-read recency evict them.

3. **Scissorhands** — Liu et al., NeurIPS 2023 ([arXiv:2305.17118](https://arxiv.org/abs/2305.17118)). "Persistence of Importance Hypothesis": a token that mattered once is likely to matter again, so track importance as a decaying historical statistic, not a single current-step signal.

   > [!IMPORTANT]
   > This is the best single anchor found for Thesis 1's own stated goal — "biology-dependent, access-pattern-driven adaptive eviction" is almost a restatement of Scissorhands' hypothesis, just for k-mers instead of tokens: a k-mer hot earlier in a read (or in prior reads from a dominant species) is likely to recur, so track a decayed hit-history score per k-mer instead of pure LRU.

4. **SnapKV** — Li et al., NeurIPS 2024 ([arXiv:2404.14469](https://arxiv.org/abs/2404.14469)). Pools attention over a small trailing observation window to predict which *earlier* positions matter for the rest of generation. **Translation:** use a sliding window over the last M k-mers scanned in a read to predict which taxon the rest of the read belongs to (real reads have strong local compositional bias), then pre-warm cache entries for that predicted taxon instead of scoring every k-mer in isolation.

5. **PyramidKV** — Cai et al., 2024 ([arXiv:2406.02069](https://arxiv.org/abs/2406.02069)). Allocates *unequal* cache budget across transformer layers based on where attention empirically concentrates, instead of a uniform per-layer size. **Translation:** maps directly to LLC-topology-aware sizing — give each thread/core an unequal cache slice based on measured per-core LLC pressure and per-thread taxon diversity, instead of one fixed size for every thread.

**Has anyone already made this KV-cache ↔ genomics connection in print?** Searched explicitly — no. The closest adjacent hits (HashEvict, arXiv:2412.16187, LSH-based KV eviction; kache-hash, bioRxiv 2026) don't cross the streams. This looks like a genuinely open framing, worth stating as an explicit novelty claim in the write-up, not just a source of borrowed mechanisms.

**The honest caveat:** all five papers get their "importance" signal for free, as a side effect of the attention matrix the forward pass already computes. A CPU hash-table cache has no equivalent free signal — you'd have to explicitly instrument lookup counts/recency yourself. These are inspirations for *what the scoring policy should reward*, not code that ports over.

---

## Modern approximate-membership filters (Xor, Ribbon, Binary Fuse, Vacuum, Morton)

> [!WARNING]
> **Taxor** (Genome Research 2024) already uses hierarchical interleaved XOR filters for long-read taxonomic classification, cutting index size >50% vs. competing tools. So does a 2025 tool called **TAXICF**, with interleaved cuckoo filters instead. Both sit close enough to the bitmask-cell idea that they need the same explicit differentiation paragraph Kun-peng and kache-hash already get — flagged here, not yet written. Do this close read before Thesis 2's framing is final, the same way today's Kun-peng read corrected "smaller database."

The rest of this family, ranked by relevance:

1. **Xor filter** — Graf & Lemire, *J. Experimental Algorithmics* 25(1), 2020 ([arXiv:1912.08258](https://arxiv.org/abs/1912.08258)). Three hash positions per key, fingerprint reconstructed by XORing the three slots; ~1.23n slots, 2 memory accesses per lookup, faster and smaller than Bloom or cuckoo at equal false-positive rate. This is the structure behind Taxor above — a fixed-width fingerprint array is naturally close to a per-organism bitmask, so the 6-bit cell could be built as parallel xor filters instead of linear-probed cells, removing probe-sequence variance entirely. Build-once, no insert/delete — fine for Kraken2's static database.

2. **Binary Fuse filter** — Graf & Lemire, *ACM JEA*, 2022 ([arXiv:2201.01174](https://arxiv.org/abs/2201.01174)). A strict upgrade over xor filters: >2x faster construction, space within 8-13% of the theoretical lower bound vs. xor's 23%. Nobody's applied this to genomics yet — flagged in passing in one 2024/2025 storage-systems paper as a candidate to swap into Taxor's design, but no published implementation found. Genuinely open.

3. **Ribbon filter** — Dillinger & Walzer, SEA 2021 ([arXiv:2103.02515](https://arxiv.org/abs/2103.02515)), retrieval-mode extension in SEA 2022 ([arXiv:2109.01892](https://arxiv.org/abs/2109.01892)). Near-optimal space (down to <10% overhead, tunable), deployed in production in Facebook's RocksDB. The retrieval-mode variant stores a small *value* per key, not just a membership bit — that maps onto Kraken2's actual cell semantics (key → compressed taxid) more directly than a plain xor filter does. No genomics application found — a real citable gap, arguably the best mechanistic match of the five.

4. **Vacuum filter** — Wang et al., VLDB 13(2), 2020 ([PDF](https://www.vldb.org/pvldb/vol13/p197-wang.pdf)). Supports inserts/deletes, unlike the three above — less relevant to Kraken2's build-once table, worth one sentence only if incremental DB updates ever becomes a goal.

5. **Morton filter** — Breslow & Jayasena, VLDB 2018. Compressed sparse cuckoo filter with per-bucket occupancy metadata to skip empty probes and cut cache misses. Older than the rest, included because it's the cache-friendliness benchmark cuckoo-adjacent work still cites — a technique to borrow (metadata-pruned probing), not a structure to adopt.

**Dead end worth recording:** the hunch that Bifrost or kmtricks already use xor filters doesn't hold — both use blocked Bloom filters. The real precedent is Taxor and TAXICF, both flagged above.

## Learned indexes / learned Bloom filters

1. **Sandwiched Learned Bloom Filter** — Mitzenmacher, NeurIPS 2018 ([arXiv:1901.00902](https://arxiv.org/pdf/1901.00902)). A small classifier sits between two classical Bloom filter stages — cheap pre-filter, learned scorer, small backup filter for the classifier's false negatives. Template for deriving the bitmask cell's false-positive math: treat "spurious bit OR'd in by a collision" as the backup filter's residual error and reuse their FP decomposition. Caveat: needs a learnable signal to score k-mers on, and a 6-organism ESKAPE panel may not have enough structure for a cheap classifier to beat plain hashing — worth a feasibility check first.

2. **PLBF (Partitioned Learned Bloom Filter)** — Vaidya, Knorr, Kraska, Mitzenmacher, ICLR 2021 ([paper](https://openreview.net/pdf?id=6BRLOfrMhW), [code](https://github.com/kapilvaidya24/PLBF)). Buckets keys into score groups, each with its own locally-tuned filter instead of one global filter. The bitmask cell already has a natural grouping — one per organism — so PLBF's per-group budget allocation could formalize how many spare bits to give each organism to bound the spurious-bit rate.

3. **Ada-BF** — Dai & Shrivastava, NeurIPS 2020. Varies hash-function count per score group instead of a separate backup filter. Feeds Thesis 1 too — fewer probes means a cheaper cache-miss path. Caveat: tuned for skewed, known score distributions (malicious URLs); k-mer minimizer distributions may not have that shape without rework.

4. **Sapling** — Kirsche, Das, Schatz, *Bioinformatics* 37(6), 2021. Already-occupied territory worth knowing about: replaces binary search over a genomic suffix array with a learned piecewise-linear model. Not a hash table or Bloom filter, and not taxonomic classification — but proof the Kraska line of work already reaches genomic indexing at scale. Cite as an existence proof, don't try to lift the technique directly.

5. **Learned Count-Min Sketch** — Hsu et al., ICLR 2019 ([paper](https://openreview.net/pdf?id=r1lohoCqY7)); recent variant, NeurIPS 2025 workshop ([arXiv:2512.12252](https://arxiv.org/abs/2512.12252)). A model predicts heavy hitters and tracks them exactly, offloading only the tail to a small CMS. Feeds **Thesis 1** directly — W-TinyLFU (already in scope) is built on a CMS for frequency estimation, so a learned CMS is a drop-in upgrade path: predict "hot" k-mers (conserved regions) instead of learning their frequency purely online.

**Dead end worth flagging:** any learned-filter pitch for Thesis 2 needs to beat Taxor's non-learned hierarchical interleaved XOR filters, not just a plain Bloom filter, to be a credible improvement — that's the real baseline now, not the textbook one.

---

## Recsys embedding-table caching (DLRM-adjacent systems)

Searched explicitly for prior work applying this style of caching to genomics/bioinformatics indexing — found none. Genomics k-mer caching work cites minimizers and locality-sensitive hashing, not hot/cold embedding-row placement. Same shape of gap as double hashing: nobody's crossed these two literatures.

1. **FAE (Framework for Accelerating Embeddings)** — Adnan et al., VLDB 2022 ([arXiv:2103.00686](https://arxiv.org/abs/2103.00686)). Profiles access counts on a data sample, picks a hot/cold threshold from that profile (on Criteo's dataset, the top 6.8% of rows take ~76% of accesses), places hot rows in fast memory. **Translation:** profile the k-mer access histogram per organism/dataset offline, size the cache to the hot fraction, pick the threshold from that profile instead of relying purely on runtime decay. The GPU/CPU split doesn't transfer; the sampling-based threshold selection does, cheaply.

2. **Bandana** — Eisenman, Naumov et al. (Facebook), MLSys 2019 ([arXiv:1811.05922](https://arxiv.org/abs/1811.05922)). Two ideas: co-locate rows likely to be read together in the same physical block, and pick DRAM cache size by simulating candidate sizes against traced access logs rather than guessing. **Translation:** the co-location idea maps to grouping k-mers from the same genomic region into the same cache line/cell block. The trace-driven sizing method is a concrete, liftable technique for the LLC-topology-aware sizing piece — replay real read traces through a cache simulator to pick per-core cache size instead of guessing a fraction of LLC.

3. **Frequency-aware software cache (CachedEmbedding, ColossalAI)** — arXiv:2208.05321, 2022.

   > [!IMPORTANT]
   > Closest existing analogue to Thesis 1's whole eviction-policy pitch found so far: precomputes offline access-frequency priors and layers them on top of a runtime LFU-like eviction, so cold rows *known* to be rare get evicted preferentially even before they'd naturally age out. Translation is almost 1:1 — combine offline k-mer frequency priors (from reference genome composition) with runtime W-TinyLFU counters, instead of recency alone. Single-node, single-table — architecturally the closest of the five to Kraken2's setup.

4. **Hierarchical Parameter Server (HPS)** — NVIDIA Merlin HugeCTR ([arXiv:2210.08804](https://arxiv.org/abs/2210.08804)). Explicit 3-tier cache (GPU HBM → CPU DRAM → SSD) with frequency-driven promotion/demotion. Template for generalizing LLC-topology-aware sizing to more than two tiers (L2-private / LLC-shared / DRAM) even without a GPU tier.

5. **ERCache** — Meta Ads, [arXiv:2410.06497](https://arxiv.org/abs/2410.06497), Oct 2024. Per-workload-class eviction/TTL tuning plus a failover cache serving stale-but-valid entries under load. Weakest fit — no k-mer analogue to "stale but usable" (a k-mer either is or isn't in the table) — but a reminder that per-organism policy tuning (not one global policy) is a legitimate design axis.

**Caveat across all five:** every one of these targets multi-GB/TB tables at datacenter scale with GPU or multi-node hardware, amortizing cache-management overhead over huge batches. Kraken2 makes cache decisions per-lookup on one CPU node — the *policies* (frequency priors, tiered sizing, trace-driven simulation) transfer far better than any actual code would.

## Feature-hashing / sketch collision theory — a derivation strategy for the bitmask cell

This is the one that actually answers "how do we derive the formula," not just "who else has a similar idea." Three source techniques, then the fitted answer.

1. **Feature hashing** — Weinberger, Dasgupta, Langford, Smola, Attenberg, ICML 2009 ([arXiv:0902.2206](https://arxiv.org/abs/0902.2206)). Multiplies a *signed* hash (±1) onto each feature before accumulating, so collisions cancel in expectation (E[ζ(t)ζ(t′)]=0 for t≠t′) instead of biasing the result — then bounds the tail with Talagrand's concentration inequality.
2. **Count-Sketch** — Charikar, Chen, Farach-Colton, ICALP 2002. Same signed-cancellation idea, generalized: variance bounded via Chebyshev on the L2 norm of the rest of the vector, boosted to a high-probability bound with median-of-means.
3. **Count-Min Sketch** — Cormode & Muthukrishnan, 2005. Deliberately *unsigned* — counters only ever increase, so error is strictly one-sided, and Markov's inequality applies directly without needing cancellation.

> [!IMPORTANT]
> **The bitmask cell is structurally an OR-accumulator, not a sum — so it's the odd one out relative to all three.** Signed-hash cancellation (techniques 1 and 2) can't help here: OR has no additive inverse to cancel against. Bit-flip events are strictly one-directional (bits only ever turn on), which makes **Count-Min's one-sided Markov/union-bound machinery the right template**, not feature hashing's signed trick — re-targeted at OR instead of sum, and split per-organism instead of per-query. Concretely: for a cell with load factor λ = N/m, and organism *i* truly absent from that cell, "spurious bit set" is the probability that ≥1 of organism *i*'s k-mers (weighted by its genome-representation share p_i) also lands in this cell — a balls-into-bins occupancy calculation per organism per cell, summed via linearity of expectation into E[# spurious bits | true bits] per cell, then averaged over the table for expected FPR per organism as a function of (N, m, p_i).

**Already solved elsewhere under a different name? Checked explicitly — no.** Bifrost's Blocked Bloom Filter stores existence only; organism/color membership lives in a *separate* compressed matrix, never OR'd into the same cell. Mantis/Squeakr make the base structure exact (zero false positives) specifically to dodge this problem, keeping color classes in a side table. Sequence Bloom Tree/SSBT/HowDeSBT give each organism its own filter, unioned only at query time. Nobody stores N organism-presence bits packed into one collision-prone cell and derives the OR-collision math for it — confirmed genuinely open.

**Concrete next step, not just theory:** the naive m-choose-k birthday-paradox collision count is wrong for an open-addressed table, because probing redistributes k-mers away from full cells — collisions become occupancy-dependent, not independent. First task is re-deriving "effective number of distinct k-mers landing in the final cell" under Kraken2/Patch 4's actual probing scheme (linear now, double hashing planned), *then* plugging per-organism skew p_i into that corrected occupancy model — and validating the closed form against an instrumented run of the real hash table rather than trusting it blind.

---

## Advanced hashing / collision-resolution schemes beyond linear, double, and cuckoo

1. **Robin Hood hashing** and **Hopscotch hashing** — both **dead ends for this project**, and worth recording as such so nobody re-chases them. Both solve variance/neighborhood problems that only matter under *online insert/delete* — for a table built once and never mutated, you get the same end-state probe-length profile just by placing keys optimally during the bulk build, no runtime swap/displacement logic needed. Robin Hood: Celis 1986, recent variance proof [arXiv:1605.04031](https://arxiv.org/pdf/1605.04031). Hopscotch: Herlihy, Shavit, Tzafrir, DISC 2008, recent lock-free/RDMA variants exist but target concurrent tables Kraken2 doesn't need.

2. **Bucketized multi-way cuckoo hashing** — d candidate buckets per key, cuckoo displacement across buckets, O(1) worst-case lookup at very high load factor.

   > [!NOTE]
   > Already applied to k-mers: **hackgap** (Zentgraf & Rahmann, WABI 2022) uses subdivided multi-way bucketed cuckoo hash tables specifically for gapped-k-mer counting. This slightly undercuts double hashing's novelty claim less than it might seem — cuckoo and double hashing are a genuinely different collision-resolution family (bucketed relocation vs. probe-sequence formula) — but cite hackgap as related work, not as competing with the double-hashing claim.

3. **Power-of-d-choices + simple tabulation hashing** — Azar et al. 1994; Aamand et al., ICALP 2018 ([arXiv:1407.6846](https://arxiv.org/pdf/1407.6846)). Each key gets d independent candidate cells, placed in whichever is least loaded at build time; simple tabulation hashing gives O(1) evaluation via small cache-resident lookup tables. For a build-once table, this is a strong fit — no online rebalancing needed, lookups check only d fixed precomputed cells, directly comparable in probe cost to double hashing's 2-probe scheme but with better worst-case load-balance guarantees. No genomics-specific application found — **flagging this as a real candidate to prototype alongside double hashing**, not just cite.

4. **Minimal perfect hashing (MPHF) family** — BBHash, PTHash/PtrHash (SEA 2025), SSHash, LPHash. Eliminates collision resolution entirely via a build-time bijection from the known key set to slots, rather than optimizing probing.

   > [!IMPORTANT]
   > This is already the dominant established solution for static k-mer sets in genomics (SSHash/LPHash routinely cited, 0.5-0.9 bits/k-mer). Cite it explicitly as the reason double hashing is scoped as *a probing-scheme improvement*, not a switch to MPHF — MPHF needs the full key set fixed at build time with no slack for new taxa later, and needs separate handling for negative queries. Anticipate this as the first question sir or a reviewer asks: "why not just use a perfect hash?"

5. **k-Perfect Hashing (k-PHF)** — Groot Koerkamp, Hermann, Sanders, Walzer, ESA 2026 ([arXiv:2607.07257](https://arxiv.org/pdf/2607.07257)), very recent. Maps keys into fixed-capacity cache-line bins via a tiny cache-resident perfect hash function — branchless, single-cache-miss lookup, supports negative queries. Structurally the closest match found anywhere in this search to Kraken2's actual cell design (fixed-capacity cache-line bins). No genomics application exists yet; unimplemented outside the authors' own benchmark. **Flag to sir as a second theory-adjacent stretch goal**, alongside the already-known Elastic/Funnel hashing — not a near-term build target, but worth knowing it exists before finalizing the "future work" list.

## Sweep: anything 2025-2026 that could threaten either thesis

> [!WARNING]
> **Chimera / IMCF, with a companion classifier "TAXICF"** (bioRxiv Mar 2025, ICIC 2026) — an Interleaved Merged/Cuckoo Filter that groups taxon bins by capacity to cut space waste under skewed bin sizes, explicitly targeting database size and memory. This is the **closest thing found anywhere in this whole research pass to a direct scoop of Thesis 2**. It's cuckoo-based, not double-hashing-based — a genuinely different collision-resolution family — so the novelty claim likely survives, but this needs the same close-read-and-differentiate treatment Kun-peng got today, before Wednesday if possible. [github.com/LoadStar822/Chimera](https://github.com/LoadStar822/Chimera), [TAXICF paper](https://link.springer.com/chapter/10.1007/978-981-92-3498-1_30).

Five other tools found, lower risk:

- **Taxor (HIXF)** — Genome Research 2024, hierarchical interleaved XOR filters, >50% memory/index-size reduction. Already flagged above (in the AMQ-filters section) as needing its own differentiation paragraph — repeated here because it showed up independently in this sweep too, which is a signal it's a real must-address, not a minor citation.
- **Slacken** — NAR Genomics and Bioinformatics, July 2025. Spark-based distributed Kraken2 reimplementation that *deliberately avoids* the compact hash table, storing full records instead — opposite direction from this project's compression thesis. Low scoop risk, useful as a counter-example: trades hash compactness for precision at cluster scale.
- **genCRC32** — Bioinformatics Advances, Jan 2026. Collision-free CRC32-based hashing for short k-mers via bit-packing and tuned CRC32 polynomials. Not a classifier, a hash-function primitive — worth citing as recent hash-design prior art for Thesis 2's hash function choice, low scoop risk (it's a hash function, not a cell layout or probing scheme).
- **DuoHash** — ICCABS 2025, fast spaced-seed hashing for k-mer counting, up to 11x speedup. Adjacent, not classification-focused, low overlap.
- **MetageNN** — neural-network long-read classifier, <1/4 the memory of Kraken2, >7x faster than MetaMaps/GeNet. Different mechanism entirely (NN vs. hash table) — low scoop risk for either thesis, but a relevant memory-efficiency comparator on Nanopore data specifically if the comparator table ever wants a non-hash-based entry.

**Novelty claims re-checked (actively trying to falsify, not just confirm):**
- Double hashing (not cuckoo) in a genomic hash table, 2025-2026: **not found anywhere** — the only near-hits are Chimera/TAXICF's cuckoo-family work, which is a different collision-resolution approach. **Claim survives.**
- Per-organism bitmask/presence-vector cell for small fixed panels: **not found anywhere**, including in a dedicated re-check against a 2016 bitpacking-for-offset-arrays paper that turned out to solve a different problem (compressing position lists, not organism-membership bits). **Claim survives.**

## Hardware-aware / CXL / NUMA caching (non-genomics systems research, 2023-2025)

1. **HybridTier** — Song et al., ASPLOS 2025 ([paper](https://www.sihangliu.com/docs/hybridtier_asplos25.pdf)). Classifies memory pages hot/cold using both long-term frequency and short-term "access momentum" (rate of change), so pages that just turned hot/cold get caught fast, not just steady-state-hot ones — 2-7.8x less overhead memory, 1.7-3.5x fewer cache misses than prior CXL tiering systems. Closest analog found to "evict cold k-mers to a slower tier instead of discarding" — the momentum-based classifier is directly adaptable to skew-aware eviction, tracking short-term momentum per k-mer bucket so recently-hot organisms aren't evicted just for being new. **Caveat:** needs real CXL hardware exposing a slow tier via OS page migration — Luna (4th-gen Xeon) supports CXL 1.1 at the platform level, but there's no evidence the lab machine has a populated CXL memory expander. May only be simulable.

2. **Lightweight frequency-based CXL tiering** — companion/earlier line of work ([arXiv:2312.04789](https://arxiv.org/abs/2312.04789)), a simpler frequency-counter-only policy, useful as a cheap fallback baseline if HybridTier's momentum-tracking proves too expensive for the k-mer cache's hot path.

3. **Simple cache partitioning via Intel CAT** — Boucher et al., CMU tech report. Static LLC-way partitioning between a latency-critical key-value store and co-tenants; shows cache contention alone inflates a KV-store's P99.9 tail latency 5x, and CAT partitioning nearly eliminates it. Real number to cite for how much LLC interference costs a lookup-heavy service, on a hash-lookup workload specifically — validates the same conclusion Farshin (already cited) reached. **Caveat:** Intel-only — works on Luna (Xeon Platinum 8468), but Orion (ARM64 Jetson) has no equivalent mechanism, so this is a Luna-only technique.

4. **PIM-Tree** — Kang, Zhao, Blelloch, Dhulipala, Gu, McGuffey, Gibbons, PVLDB 2023 ([arXiv:2211.10516](https://arxiv.org/abs/2211.10516)).

   > [!IMPORTANT]
   > Strongest match found anywhere in this search for the "biology-dependent skew-aware eviction" half of Thesis 1. A skew-resistant index that dynamically routes hot ranges differently from cold ranges rather than statically partitioning — built for processing-in-memory hardware, but the routing *logic* transfers even without real PIM hardware (neither Luna nor Orion has any). Real metagenomic read streams are Zipf-skewed toward a handful of dominant taxa — exactly the regime this paper targets. Template for a skew-aware admission/eviction policy: route/cache hot taxa's k-mers differently than the long tail.

5. **Phoenix** — NUMA-aware thread and page-table placement, kernel module, [arXiv:2502.10923](https://arxiv.org/abs/2502.10923), Feb 2025. Coordinates thread placement and page-table placement live based on observed access behavior — 2.09x fewer CPU cycles, 1.58x fewer page-walk cycles vs. prior NUMA placement. Suggests detecting topology via `/sys` or `hwloc` at startup (exactly what "read actual LLC size at startup" needs) then re-evaluating live, not just once. **Caveat:** Orion is single-NUMA-node, so this is Luna-only, and only matters above the ~32-thread NUMA-crossover point already flagged elsewhere as unmeasured.

**Cross-cutting note:** none of these five — or any paper found in any of the eight wave-1 searches — has been applied to genomics/k-mer/metagenomics workloads. That confirms the whole "hardware-aware caching for a k-mer classifier" framing remains a citable, real gap for Thesis 1.

---

## Wave 1 complete — what needs to happen before Wednesday

Eight research streams, all landed. Three close-reads are now queued, same treatment as today's Kun-peng session:

1. **Chimera/TAXICF (IMCF)** — closest real scoop risk to Thesis 2 found in this entire pass. Cuckoo-based, not double-hashing, but targets the same "smaller database" territory. Highest priority close-read.
2. **Taxor (HIXF)** — flagged twice independently (once from the filters search, once from the sweep). XOR-filter-based taxonomic classification, >50% index-size reduction.
3. **kache-hash** — flagged weeks ago for Thesis 1, never actually deep-read. Do it now while in close-read mode, same as Kun-peng and the two above.

Two genuinely new implementation candidates surfaced, beyond the four already planned:

- **Power-of-d-choices + tabulation hashing** — a real, implementable alternative/complement to double hashing for a build-once table, no genomics prior art.
- The **LLM KV-cache eviction analogy** (Scissorhands/H2O/SnapKV/PyramidKV) and **PIM-Tree's skew-resistant routing** are two independent, unconnected literatures that both land on the same answer for Thesis 1's eviction policy — track decayed historical importance per k-mer, route hot vs. long-tail differently. That convergence from two unrelated fields is itself worth a sentence in the write-up.

One anticipated objection now has an answer ready: MPHF (SSHash/PTHash) is genomics' existing dominant static-hash-table paradigm — "why not just use a perfect hash instead of double hashing" is the first question a reviewer will ask, and the answer (MPHF can't handle new taxa post-build, needs separate negative-query handling) is now on record.

---

# Wave 2 — close reads and the ML-systems reframe

## Mixture-of-Experts routing and expert caching (the "general ML model" angle)

The reframe you asked for — "think of Kraken2 as a general ML model with these properties" — pointed straight at MoE serving systems: an MoE router picks which expert handles each input token, which sounds like Kraken2 picking which taxon a k-mer belongs to. The honest result is a **split verdict**, and the split matters more than either half alone.

**What transfers cleanly — expert caching and placement:**

1. **MoE-Infinity** — Xue et al., 2024 ([arXiv:2401.14361](https://arxiv.org/abs/2401.14361)). Traces per-request expert activation *sparsity* at runtime and uses those traces — not just recency — to drive which experts stay GPU-resident. **Translation:** use observed per-sample/per-organism k-mer hit patterns to predict which hash-table regions go hot next, not just which were hot last — feeds skew-aware eviction.
2. **Fiddler** — Kamahori et al., ICLR 2025 ([arXiv:2402.07033](https://arxiv.org/abs/2402.07033)). Keeps as many hot experts GPU-resident as a fixed memory budget allows, pushes cold-expert compute to CPU instead of transferring cold weights. **Translation:** frame LLC-topology-aware cache sizing as exactly this — a hardware-budget allocation problem, cold lookups falling back to DRAM the way Fiddler falls back to CPU.
3. **SiDA-MoE** — Du et al., MLSys 2024 ([arXiv:2310.18859](https://arxiv.org/abs/2310.18859)). Predicts activation sparsity *ahead of* the forward pass, partitions experts across memory tiers accordingly — up to 80% memory savings, <1% accuracy loss. Adds a prediction step on top of Fiddler's static placement — a possible refinement: predict hot k-mer regions from a fast pre-pass instead of purely reactive counters.
4. **Chameleon** (MICRO 2025) — general MoE-serving skew measurements: ~15-20% of experts handle ~80% of tokens, Zipf-distributed activation, skew-aware policies (SLRU/LFRU) beat plain LRU by 8-15 points hit-rate on skewed traffic. Directly citable precedent for "don't use plain LRU here" independent of the genomics framing.

**What doesn't transfer — and why it's worth knowing that, not just the parts that work:**

> [!IMPORTANT]
> Kraken2's k-mer-to-taxon mapping is a **deterministic, exact hash lookup** — same k-mer always resolves to the same node, no ambiguity. MoE routing is a **learned, soft/probabilistic** decision that tolerates approximate answers with graceful degradation. That kills the more exotic half of the analogy: Pre-gated MoE and ProMoE's speculative prefetch rely on a soft signal available *before* the lookup finishes — Kraken2 has no such signal, only the k-mer itself. Sticky/cache-aware routing tricks (biasing a trainable router toward already-cached experts) have no equivalent either — Kraken2's hash function can't be nudged. The part of the analogy that's load-bearing is narrower than it first looks: *placement and caching policy for an empirically skewed access distribution* transfers; *speculation and routing-bias* do not.

**Routing-decision memoization — weaker than hoped.** No MoE paper caches the router's decision for literally-repeated inputs the way a k-mer cache memoizes exact repeated lookups, because LLM inputs are almost never bit-identical between requests. Not a useful angle here.

**Bioinformatics connection:** searched explicitly, found none — every MoE-in-genomics hit found uses MoE as a *model architecture* for prediction tasks (GC-MoE, AMR-MoEGA), never as a systems analogy for lookup infrastructure. Genuinely open, on top of the KV-cache-eviction gap already found in wave 1.

**Caveat common to the whole angle:** these systems assume GPU-memory-constrained, PCIe-transfer-cost serving. The specific latency-hiding mechanics (async prefetch overlapped with GPU compute) don't map onto a CPU L2/L3 cache, where the cost being hidden is a DRAM cache-line fill — orders of magnitude cheaper than a PCIe expert transfer. Take the skew/placement *policies*, leave the *mechanics* behind.

## Power-of-d-choices + tabulation hashing — feasibility verdict

Wave 1 flagged this as "genuinely underexplored, worth prototyping." A real feasibility dive changes the recommendation.

**The mechanism, concretely.** Each key gets d candidate cells (d=2 is the natural comparison point to double hashing). Because Kraken2's table is build-once, you skip cuckoo's online eviction machinery entirely — place each key in whichever candidate cell is emptier at build time, an offline assignment problem, with a bipartite-matching pass for anything that can't be greedily resolved. Lookup checks exactly the two fixed, precomputed addresses — no probe-chasing, fully prefetchable. Simple tabulation hashing (Aamand/Knudsen/Thorup, ICALP 2018; Dahlgaard et al., SODA 2016 — both read in full) generates those two values cheaply: a few KB of lookup tables total, "as fast as two multiplications" by the original authors' own benchmark, comfortably L1-resident.

**Head-to-head vs. double hashing — no direct comparison exists in the literature**, and would have to be derived, not cited. What *is* established (Mitzenmacher, "Balanced Allocations and Double Hashing," 2012/2014): double hashing used purely to *generate* the d candidate slots is asymptotically indistinguishable from independent random hash functions in the balanced-allocation setting.

> [!IMPORTANT]
> **That's the actual finding.** Reuse the double-hash primitive (f, g) Thesis 2 already needs for its probe sequence — but consume it differently: generate 2-4 parallel bucket *candidates* instead of a serial probe chain. Near-free repurposing of a hash pair you're building anyway.

**Why plain power-of-d-choices as a standalone replacement is a bad idea at this project's scale:** single-slot d=2 cuckoo caps load factor near 50% (Pătrașcu-Thorup, JACM 2012) — roughly doubling memory versus Kraken2's current linear probing at comparable load, a real cost for a memory-bound genomics DB. At this project's table sizes (not distributed-systems scale), lg lg n is tiny (~4-5 for n≈10⁸) — the asymptotic max-load gain over plain hashing is marginal here, diminishing returns. And critically, power-of-d-choices attacks max bucket occupancy/chain length, not false-positive rate — which is the actual axis Thesis 2's exponential-FP-law problem lives on. Partial fit to the real pain point.

**Verdict: don't build plain power-of-d-choices as a double-hashing replacement.** Do prototype the combined version: double hashing generates 2-4 bucket candidates, bucketed 4-way (libcuckoo — real, deployed precedent, >95% load factor — uses exactly this shape), greedy-packed at build time. This is cheap (reuses existing f/g), gives bounded-d prefetchable lookups (directly feeding the §5 "latency-hiding lookup cache" future-work item), and — worth noting — libcuckoo's 4-way bucket structure happens to mirror Thesis 1's own 4-way set-associative cache baseline, a coincidence worth exploiting rather than ignoring. Frame it as a build-time placement optimization layered on top of double hashing, not a rival collision-resolution scheme.

---

# Synthesis — the whole pass, ready for Wednesday

Two waves, 13 agents, covering everything from classic AMQ-filter theory to LLM KV-cache eviction to MoE serving systems. Here's what actually changes going into the meeting.

## Three close-reads, three different outcomes — the honest scorecard

| Tool | Threatens | Verdict |
|---|---|---|
| **Kun-peng** (earlier today) | "Smaller database" | Survives — same DB size, only RAM footprint shrinks, different memory tier entirely |
| **kache-hash** | Thesis 1's adaptive cache | Survives, but the closest real overlap found — same CPU-cache tier, needs mechanism-level defense (static hash-function locality vs. runtime-adaptive eviction), not a tier-based dismissal |
| **Chimera/TAXICF** | "Smaller database" | **Doesn't fully survive** — genuinely shrinks the on-disk database via cuckoo filters, needs an explicit caveat in the write-up. Underlying mechanisms (cell-width, double hashing, bitmask) still untouched |
| **Taxor** | Bitmask cell specifically | Survives cleanly — never shares storage between organisms, so its collisions are a structurally different, non-OR failure mode |

**The one thing to say differently on Wednesday because of this:** "smaller database" can no longer be pitched as an unqualified outcome claim — Chimera already gets there, via cuckoo filters, for large taxonomies. The pitch needs to be specifically about the *mechanism* (cell-width + double hashing + bitmask cell for a small fixed panel), not the headline number, with Chimera cited as "outcome-adjacent, mechanism-different."

## Two independent literatures converged on the same answer for Thesis 1

LLM KV-cache eviction (Scissorhands' "persistence of importance," H2O's heavy-hitter scoring) and general systems research on skew-resistant indexing (PIM-Tree's hot/cold routing) — two fields that don't cite each other — both land on: **track decayed historical importance per item, route/protect hot items differently from the long tail, don't rely on recency alone.** MoE expert-caching research (Fiddler, MoE-Infinity, SiDA-MoE) adds a third, independent confirmation from yet another field. Recsys embedding caching (CachedEmbedding) adds a fourth: combine offline frequency priors with runtime counters. Four unrelated literatures, one converging answer — that convergence is itself worth a sentence in Thesis 1's write-up, not just the individual citations.

## What's implementable now, ranked

1. **Double hashing** — already planned, still the cleanest first target (unchanged from before this research pass).
2. **Combined double-hashing + power-of-d-choices bucket placement** — new this pass, cheap (reuses the same hash pair), real precedent (libcuckoo), feeds the §5 latency-hiding-cache future-work item directly.
3. **Scissorhands-style decayed-importance eviction** for Thesis 1, informed by the four-literature convergence above — the strongest-grounded version of "biology-dependent adaptive eviction" now available, better-cited than W-TinyLFU/ARC alone.
4. **Trace-driven LLC sizing** (Bandana's method: simulate candidate cache sizes against real read traces, pick the cheapest one hitting a target) — concrete methodology for the LLC-topology-aware sizing piece, not just "read `/sys` at startup."
5. **Bitmask-cell false-positive formula** — derivation strategy now exists (Count-Min-style one-sided Markov bound, re-targeted at OR instead of sum, occupancy-corrected for the real probing scheme) — this is now a "sit down and derive it" task, not an open research question.

## Three citations that pre-empt reviewer questions before they're asked

- **MPHF (SSHash/PTHash)** answers "why not just use a perfect hash instead of double hashing?"
- **hackgap's bucketized cuckoo** answers "hasn't cuckoo hashing already been tried on k-mers?" (yes, but double hashing is a different family, still untried)
- **kache-hash's static locality vs. Thesis 1's runtime adaptivity** answers "why not just use kache-hash's bucket layout?"

## What to bring to sir Wednesday

1. Kun-peng and Chimera/TAXICF are strong candidates for the comparator table (both live, both real, both DB-compatible-ish or at least directly benchmarked against Kraken2) — decide scope with sir, same open question already flagged for Kun-peng.
2. The "smaller database" pitch needs the reframe above — mechanism over headline number.
3. Four independent literatures (KV-cache eviction, PIM-Tree, MoE serving, recsys embedding caching) converging on the same eviction-policy answer is a genuinely strong grounding story for Thesis 1 that didn't exist before today.
4. Two new implementation candidates worth floating: combined double-hash/power-of-d-choices bucket placement, and Scissorhands-style decayed importance as the concrete eviction mechanism.
