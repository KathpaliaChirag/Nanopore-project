# round 3, agent B: storage structure and data layout, what could give a positive result

axis: change how the 8 to 104 GB table is laid out or visited, not what a cache retains. read first: round2_C, round2_B, and plan_paper/research_brief_db_structure_trie_dictionary_2026-10-21.md (the trie brief). nothing run, no luna. web searches done this session; a link marked [verified] was seen in a search result with matching title and authors, [unverified] means from my memory or only a thin hit, not opened.

## 0. what the data already fixes

- the cost is one dependent dram access plus a tlb walk per lookup, into a table far above any cache. real wins so far: parallel load (S10), hugepages (S14), prefetch and pipelining (S9, S16). every retention idea was null (S6 ablation, S3.4).
- the trie brief already priced the main structures: flat table 1.07 hit lines and 1.32 miss lines per lookup at load 0.70; trie 3 to 24 dependent reads; exact dictionary 2x memory; mphf plus fingerprint 2 to 3 reads, minus 23% size; Elias-Fano 2 to 3 reads, minus 31%. i do not redo that. i add what it left out: sort-and-partition batching, line-aligned buckets, what double hashing costs in lines, prefilters, and prior art.
- a flat table is the floor for random exact lookup: one dram access. a layout can only win by (a) keeping the count at about 1 while shrinking bytes, (b) making accesses share pages or lines, or (c) overlapping them. (b) and (c) are the live options.

## 1. a fact that kills one popular idea: minimizer locality does not apply to the key kraken2 stores

the tempting idea: consecutive k-mers of a read share a minimizer, so bucket the table by minimizer and consecutive lookups hit the same bucket. check against kraken2: the table is keyed by the minimizer itself (a hash of the 24 non-ignored letters out of 31), one lookup per distinct minimizer. the Kraken 2 paper says only distinct minimizers of a read trigger table accesses (Wood, Lu, Langmead, "Improved metagenomic analysis with Kraken 2", Genome Biology 20:257, 2019, https://pmc.ncbi.nlm.nih.gov/articles/6883579 [verified]). so the sharing is already harvested by the existing "same as last minimizer, skip" logic. the next minimizer in a read is a different 24-letter string, and after hashing its slot is unrelated. there is no within-read locality left to bucket.

where minimizer bucketing does pay: tools whose stored key is the k-mer and whose bucket id is the minimizer (SSHash: Pibiri, "On weighted k-mer dictionaries" and "Sparse and skew hashing of k-mers", Bioinformatics 2022, https://github.com/jermp/sshash [unverified paper titles, repo known]; Metabuli stores 60-bit metamers in a sorted array with a prefix index and matches sorted queries [unverified detail]). kraken2 would need to store k-mers instead of minimizers: that is a different tool and a much larger db. rule it out, cite it as the reason.

the locality that does exist is across reads: the same minimizer appears in many reads (high-copy organisms, plasmids, rRNA). round 2 A and S4.0 measured 0.4 to 3.6 percent hit rate on real runs, so repeat rate within a thread's recent window is tiny. over a whole batch of millions of reads it is higher, which is the entry point for experiment 1.

## 2. the options table

columns: mechanism, effect on dram lines per lookup and tlb reach, memory cost, sniper-modellable (it executes real traced binaries, so any C++ layout with a real access pattern is modellable; the limit is calibration, not the idea), luna try time.

1. flat open addressing, linear probing, 32-bit cell (current). 1.07 / 1.32 lines. baseline.
2. double hashing (already compiled behind -DLINEAR_PROBING). this is a cost, not a gain, in lines. each probe jumps to an unrelated line. expected probes at load 0.7: hit about (1/alpha) ln(1/(1-alpha)) = 1.72, miss about 1/(1-alpha) = 3.33 (textbook, [arith]). each is a fresh dram line, so 1.72 and 3.33 lines vs 1.07 and 1.32. it removes the long-cluster false-positive cliff of linear probing (thesis 2) but raises lines per lookup by 60 percent (hit) and 150 percent (miss). worth stating to sir before B1.1 is benchmarked: predict it slower on large dbs unless the prefetch covers all probes. sniper: yes. luna: 0 days of code, 1 rebuild.
3. line-aligned bucketed linear probing (probe restarts at line start, wraps inside the 16-cell line, overflow goes to next line). at load 0.70 a 16-slot bucket has mean 11.2 keys; overflow past 16 is about 8 to 10 percent [arith, Poisson tail]. hits about 1.08 lines (no gain), misses about 1.10 vs 1.32 (-17 percent). effect on dram lines is at most 10 percent weighted by miss share, which is unmeasured. memory same. luna: needs a db rebuild (cells cannot be re-placed from the fingerprint, trie brief section 1), 3 to 5 days. modellable.
4. cuckoo / bucketed cuckoo (two candidate lines). hit 1 to 2 lines, miss always 2 lines. loses to linear probing on random reads unless a tag filter picks the line. skip. Swiss table style (control bytes then slots, Google Abseil, https://abseil.io/about/design/swisstables [unverified]) gives one line for the control group but a second for the slot at 1-byte keys; a 4-byte cell with no tag byte gains nothing. Robin Hood hashing bounds probe variance, which helps the miss tail; same line count as aligned buckets. skip as separate items.
5. blocked bloom / xor / binary fuse prefilter to skip absent k-mers. binary fuse filters: Graf and Lemire, "Binary Fuse Filters: Fast and Smaller Than Xor Filters", ACM JEA 2022, arXiv 2201.01174, https://arxiv.org/abs/2201.01174 [verified]; within 13 percent of the storage bound. a prefilter only helps if it lives in cache. 19.4e9 keys at 9 bits is about 22 GB on the 103GB db, 1.4e9 keys at 9 bits is about 1.6 GB on the 8GB db: neither fits a 105 MB L3. so a lookup still pays a dram line to the filter (binary fuse pays 3 reads) before the table. fits L3 only on the 50MB db (about 11 MB), where the table already largely fits too. verdict: dead on big dbs, no gain on small. ganon / ganon2 use hierarchical interleaved bloom filters (Piro et al., Bioinformatics 2020 https://pmc.ncbi.nlm.nih.gov/articles/PMC7355301; ganon2 bioRxiv 10.1101/2023.12.07.570547 [verified via search]) but there the filter is the whole index, not a front gate.
6. minimal perfect hash plus fingerprint. PTHash: Pibiri and Trani, "PTHash: Revisiting FCH Minimal Perfect Hashing", SIGIR 2021, https://arxiv.org/abs/2104.10402 [verified]; 2 to 4x faster lookup than competitors at similar space. RecSplit: Esposito, Graf, Vigna, ALENEX 2020, https://arxiv.org/abs/1910.06416 [verified]; first to go below 2 bits per key in practice. SicHash and BBHash (Limasset et al., "Fast and scalable minimal perfect hashing for massive key sets", SEA 2017 [unverified]) are in the same family. lines: 2 to 3 (pilot or bucket table, then the cell). memory: load factor 1.0 plus 2 to 3 bits per key, so about -23 percent vs now (trie brief). for 19.4e9 keys, building an mphf needs the key list, so a rebuild from library genomes. modellable. luna: 1 to 2 weeks. a space win, a probable speed loss.
7. Elias-Fano sorted keys, quotient filter, counting quotient filter. Elias-Fano costs 2 + log2(u/n) bits per key (trie brief: 31.8 bits per key incl. value at 103GB, exact). a quotient filter keeps remainder bits in a sorted run per quotient, so a lookup reads one line plus a short scan, with good locality and exactness-of-fingerprint; counting quotient filter (Pandey et al., SIGMOD 2017 [unverified]) is used by Squeakr for k-mers. quotient filters hold counts not taxa, so a 6-bit value per slot would have to be added. lines 1 to 2, high compute. a candidate for the space axis only.
8. tries, HAT-trie, ART. random 48-bit keys give no shared prefixes to compress; the top 17 levels of a 4-letter trie are dense (4^17 is about 1.7e10, near n). HAT-trie (Askitis and Sinha, 2007 [unverified]) is built for skewed string keys, not random integers. trie brief predicts slower; agree. the only workable shape is a direct-index directory plus a short sorted bucket (Kraken 1, and the "D" row of the trie brief).
9. sort-and-merge / radix-partitioned batching of queries. the one structural idea that changes how many accesses share a page or line without changing the table. see experiment 1. modellable: yes, as a real binary.
10. learned indexes (RMI, Kraska et al., SIGMOD 2018 [unverified]). for sorted data they replace binary search with a model. keys are hashed so uniform; the model is the identity, which is just interpolation search. gain is on option 7 style sorted layouts only. no new idea beyond "D with interpolation search" in the trie brief.
11. latency-hiding lookup structures: group prefetching and software-pipelined prefetching (Chen, Ailamaki, Gibbons, Mowry, "Improving Hash Join Performance through Prefetching", ICDE 2004 [unverified link]), AMAC (Kocberber, Falsafi, Grot, "Asynchronous Memory Access Chaining", PVLDB 9(4), 2015, https://core.ac.uk/download/43718028.pdf [verified via search], up to 2.3x on irregular chains). S9 is group prefetching and S16 is software pipelining. the missing step is AMAC for the 32 percent of misses whose probe run crosses a line: today the second line is a demand miss. adjacent to storage, listed because it pairs with option 3.
12. what the other tools do. Centrifuge and Centrifuger are FM-index tools: Centrifuger, Song and Langmead, Genome Biology 25:106, 2024, https://link.springer.com/doi/10.1186/s13059-024-03244-4 [verified]; memory is their bottleneck, they halve FM-index size. FM-index lookups are many dependent rank queries per read, so on raw latency per read they are slower, they win on space. MetaCache and MetaCache-GPU (Kobus et al., arXiv 2106.08150, https://arxiv.org/abs/2106.08150 [verified]) use a multi-bucket hash table keyed by minhash sketches; bucket values are location lists, a different shape. Sylph is a containment-ANI sketch method with tiny indexes [unverified]. none of the sources i found sort queries against a hashed table for speed. kache-hash: web search returned nothing under that name ("no sources found"); i could not confirm it exists in this form. treat it as unverified until ck gives a link; it should not be cited from my side.

## 3. what tlb reach and dram lines mean for each

- tlb: 104 GB table with 4 KB pages is 27M pages against a 2048-entry l2 tlb; with 2 MB pages 52K pages, still above reach, so with S14 a random lookup still often misses the l2 tlb but the walk is short (the page-table entries stay in cache). 1 GB pages (hugetlbfs) would make it 104 pages, inside reach. no layout change gets this, it is the OS-level cousin of the structure ideas, and it composes with all of them. note -M (mmap) uses page-cache pages, which E1 (never run) has to reconcile.
- shrinking cells (thesis 2) shrinks the page count proportionally: 16-bit cells halve it at the same load. that is the one structural move with a direct tlb and dram-footprint gain, already measured as accuracy trade-off.
- dram lines: only options 3 (misses), 9 (shared lines when queries cluster), 11 (overlap) move the line count or its overlap. everything else holds or raises it.

## 4. TOP 3 experiments, ranked

### rank 1: sort-and-partition batched lookup, preceded by a trace analysis

hypothesis: if a worker collects the minimizers of a large batch of reads first, partitions them by table-region (radix on slot index bits) and then probes region by region, each region's page-table entries and a share of its lines stay hot, and duplicate minimizers across reads are fetched once. the gain is real only when batch size B is large relative to the number of table pages P (needs B on the order of P or above for pages to be shared; with 2 MB pages and 103 GB P is 52K, so B of a few million lookups is enough; with 4 KB pages it is not).

predicted effect: 103GB: 1.05 to 1.2x on the lookup phase, null on 8GB and 16GB (table already near tlb reach with S14, lookups overlapped by S16). reasoning: S14 already removed most walks; S16 overlapped most dram waits; what remains is dram latency per distinct line, which partitioning cannot reduce unless two queries share a line. at load 0.7 the odds two random queries share a 64-byte line out of 1.6e9 lines is negligible unless B is about the table's line count. so the gain is mostly dedup (repeats) plus page locality, both small. honest expectation: small and possibly negative from the extra pass (write and read 12 to 16 bytes per lookup twice). this is why the trace analysis comes first.

stage 0 (about 1 to 2 days, no new table code): in the S19 binary log (read id, slot index, hit/miss) for one 103GB or 8GB run on a subset. offline compute (i) the fraction of lookups that repeat a minimizer within windows of 1e4, 1e6 and 1e8 lookups, (ii) distinct 2 MB regions and distinct lines per lookup within each window. this gives the dedup and page-sharing ceiling directly, with no implementation. the data does not exist yet; the sniper instrumentation already writes access traces, reuse the same hook.

what to measure: repeat rate vs window; lines per lookup after dedup; then, if promising, wall time of a prototype (partition by top 10 slot bits into per-thread bins, 2 passes) at 103GB, 16GB, 8GB, 50MB, all 4 read counts, full grid, 3 reps, S19 as control; byte-identical output must hold (order of results restored by read id).

runtime: 2 days stage 0, +4 to 5 days prototype if it passes.

kill criterion: stop after stage 0 if dedup removes under 10 percent of lookups at B of 1e7 and distinct lines per lookup stays above 0.9. stop after prototype if 103GB wall time is not at least 5 percent better than S19 outside the 13 to 21 s thp noise band (3 reps, same binary lineage, same thp state).

### rank 2: structbench of line-aligned buckets vs linear vs double hashing at load 0.70, then pair with AMAC for line-crossing probes

hypothesis: (a) line-aligned bucketed probing cuts miss-path dram lines by about 17 percent and hit-path by about 1 percent vs linear probing at the same load, (b) double hashing raises lines per lookup by about 60 percent (hit) and about 150 percent (miss), so on large dbs it runs slower even though it improves accuracy, (c) prefetching the second line of a crossing probe recovers part of linear probing's remaining 32 percent miss crossing.

predicted effect: (a) at most 5 to 8 percent on lookup time on 103GB if the miss share is around half; (b) 30 to 60 percent slower lookup on 103GB with the current S16 prefetch (it covers only the first probe) and near zero on 50MB; (c) 1 to 3 percent, near noise. (b) is a prediction i am most confident in, because it is arithmetic on lines, and it informs the thesis 2 trade-off with a number instead of a flag flip.

what to measure: one-file microbenchmark, 8 and 64 GB array of 4-byte cells (not a real db, random 48-bit keys inserted at load 0.70), hit mix 0, 50, 100 percent miss, 1 and 32 threads, with S16-style pipelined prefetch (batch 16). report lines per lookup (count via a counter and cross-check with perf mem loads), ns per lookup, and for double hashing the effect with a prefetch of probe 1 and probe 2. then run the same binary under sniper to check lines/dram reads agree with the counter and to test whether traced prefetch overlaps (round 2 C open question).

runtime: 2 to 3 days for the bench and sniper pass; a real db rebuild with aligned buckets only if (a) shows at least 5 percent.

kill criterion: drop (a) if the measured miss-line reduction is under 10 percent or the ns-per-lookup gain is under 3 percent at 64 GB; keep (b) as the standalone result whatever it shows, since it is a negative or positive number for thesis 2 either way.

### rank 3: mphf plus fingerprint (PTHash) or Elias-Fano as the space point of the thesis 2 curve

hypothesis: an exact or fingerprint structure with 2 to 3 reads per lookup is 23 to 31 percent smaller than the flat table (trie brief section 4) and, for the exact variants (Elias-Fano, full-key mphf), has zero false positives. it does not win speed. the positive result sought is space and accuracy at the far end of the cell-width curve, and loading faster (about 3 s of a 20 s run on 103GB per the brief).

predicted effect: 8GB and 16GB: 20 to 30 percent smaller db, lookup 1.3 to 2x slower on the lookup phase, wall time 5 to 25 percent slower; 103GB: size gain saves about 3 s of load and exit, lookup loss likely costs more than that. a pass criterion: accuracy at equal bytes is better than 16-bit linear probing cells.

what to measure: a standalone one-file test with real minimizer keys from one small library (build time, bits per key, lines per lookup via perf, ns per lookup with pipelined prefetch), PTHash (C++ header, https://github.com/jermp/pthash [unverified repo, paper verified]) as the mphf and a 16-bit fingerprint; compare with the flat 32-bit table at the same key count on the 50MB db keys. only if the numbers pass, extend to the 8GB db.

runtime: 4 to 6 days for the standalone, 2 to 3 weeks for a full integration; not a fit for the near deadline, report it as the plan.

kill criterion: stop if bits per key is not at least 20 percent below 45.7 (the current figure at load 0.70), or if lookup is more than 2.5x slower on 50MB keys with pipelined prefetch, or if the key-list build for 8GB needs over 64 GB of ram.

## 5. what i would tell sir, and the fair caveats

- there is no structural change that is known to be faster. a flat table is at the floor of one access, the competing tools win on space, and the practical speed record in this repo is overlap and pages, not structure.
- the best honest structural claim for a paper is a measurement: double hashing is predicted to cost lines, the aligned bucket saves a bounded amount, and sort-and-partition is bounded by the repeat rate, each priced before building. a bounded negative with the mechanism is a result.
- big-db lookup share of cpu is still unmeasured (stage 0c of the trie brief). every ceiling above rests on 19.5 percent at 50MB; if big-db share is 60 percent the ceilings triple.
- all sizes and probe formulas here are textbook arithmetic at load 0.70 under the random-key assumption, not measured on luna.
- sniper can run all three experiments as real binaries, but no sim cycle count was ever calibrated against perf and prefetch overlap is unchecked, so sim results for these layouts are hypotheses until the S14 and S16 direction is reproduced.
- unverified or not found: kache-hash (no web hit), SSHash paper titles, Metabuli sorted-query detail, Sylph, HAT-trie, quotient filter, learned index, BBHash, Swiss table pages (from memory, not opened).

## summary (8 lines)

1. a flat table is already at one dram access, so no layout is likely to be faster, wins are space, or overlap, or fewer pages.
2. minimizer bucketing does not apply, kraken2 stores the minimizer itself and already skips repeats within a read.
3. double hashing is predicted to cost about 60 percent (hit) and 150 percent (miss) more dram lines than linear probing, slower on big dbs.
4. prefilters (bloom, xor, binary fuse) cannot fit in L3 for 8 to 104 GB dbs, dead except on 50MB.
5. tries, HAT-trie, learned indexes and quotient filters add reads; mphf and Elias-Fano give 23 to 31 percent space at 2 to 3 reads, a thesis 2 result, not speed.
6. top 1: trace analysis then sort-and-partition batched lookup, predicted 1.05 to 1.2x on 103GB only, killed if dedup is under 10 percent.
7. top 2: structbench of aligned buckets vs linear vs double hashing, predicted bucket -17 percent miss lines, double hashing +60 to +150 percent, 2 to 3 days.
8. top 3: PTHash or Elias-Fano space point, 4 to 6 days standalone, killed if under 20 percent smaller or over 2.5x slower; kache-hash not found on the web.
