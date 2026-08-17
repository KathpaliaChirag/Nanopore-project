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

*(More sections landing as the rest of wave 1 reports back: recsys embedding-table caching, feature-hashing collision math for the bitmask cell, advanced hashing schemes, hardware-aware/CXL caching, and a sweep for anything 2025-2026 that might threaten either thesis.)*
