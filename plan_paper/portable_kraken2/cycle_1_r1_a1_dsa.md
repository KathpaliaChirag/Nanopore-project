# cycle 1, round 1, a1_dsa (data structures and algorithms)

agent a1_dsa. area: hashing, probing, filters, minimizer sampling, query batching and sorting. written 2026-10-26. nothing was run. every number carries a tag from `00_context.md` section 6.

---

## sources read this cycle

all fetched 2026-10-26. this is cycle 1, so none were cited in an earlier cycle file. the trie brief's sources (kraken 2 paper, `compact_hash.h` v2.1.3, sshash, art) are not reused here.

1. kraken2 upstream `master`, `src/mmscanner.cc`, https://raw.githubusercontent.com/DerrickWood/kraken2/master/src/mmscanner.cc. claims used: a candidate is `canonical_lmer ^ toggle_mask_`. the pop rule is `queue_.back().candidate > candidate_lmer`. the front expires when `queue_.front().pos < queue_pos_ - k_ + l_`, so a window holds k - l + 1 = 5 l-mers. once `str_pos_ >= k_`, every call returns `&last_minimizer_` whether or not it changed, so the scanner returns once per k-mer position. supports ideas 1 and 4.
2. kraken2 upstream master `src/classify.cc`, https://raw.githubusercontent.com/DerrickWood/kraken2/master/src/classify.cc. claims used: master now turns each read into a token stream first (`TOK_AMBIG`, `TOK_SKIP`, `TOK_REPEAT`, `TOK_LOOKUP`). it hashes only inside `else if (*minimizer_ptr != last_minimizer)`, it marks `MurmurHash3(*minimizer_ptr) < idx_opts.minimum_acceptable_hash_value` as a skip, and it then calls `hash->GetBatch(lookup_keys.data(), lookup_vals.data(), lookup_keys.size())`. prior art for ideas 1 and 3.
3. kraken2 upstream master `src/compact_hash.h`, https://raw.githubusercontent.com/DerrickWood/kraken2/master/src/compact_hash.h. claims used: `GetBatch` prefetches `&table_[hc % capacity_]` for the key `PREFETCH_DIST` places ahead (default 8, env `K2_PREFETCH_DIST`). keys are not sorted. an empty cell is one with value 0. the step comes from `second_hash`, which returns 1 under `LINEAR_PROBING`. `compacted_key = hc >> (64 - key_bits_)`. cells are templated (32-bit, plus a packed 40-bit cell). supports ideas 1, 2, 3 and 5.
4. kraken2 manual, https://github.com/DerrickWood/kraken2/wiki/Manual. claims used: output column 5 is "a space-delimited list indicating the LCA mapping of each k-mer". "0:" means "the next k-mer was not in the database". "A:" means ambiguous. the defaults are k = 35, l = 31, s = 7. supports the miss-fraction test in ideas 2 and 5.
5. Kille, Groot Koerkamp et al., "a near-tight lower bound on the density of forward sampling schemes", https://pmc.ncbi.nlm.nih.gov/articles/PMC11676336/. claims used: table 1 has a row for (w, k) = (5, 31), labelled kraken2. random minimizer 0.333, best scheme "mod-mini" 0.226, lower bound 0.222. the bound is ⌈(w+k)/w⌉/(w+k). random minimizers are forward schemes. supports idea 4.
6. Groot Koerkamp and Pibiri, "the mod-minimizer" (wabi 2024), abstract page https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.WABI.2024.11. claims used: mod-sampling "finds the position p of the smallest t-mer in a window" and then samples the k-mer at p mod w. "the mod-minimizer uses t≡ k (mod w)". density is "lower bounded by 1/w". supports idea 4.
7. simd-minimizers docs (Groot Koerkamp and Martayan), https://docs.rs/simd-minimizers. claims used: canonical minimizers sample the same k-mers on both strands, and "this requires `l=w+k-1` to be odd for proper tie-breaking". the page does not mention canonical mod-minimizers. the library "depends on AVX2 or NEON". supports idea 4 (its main risk).
8. Graf and Lemire, "binary fuse filters: fast and smaller than xor filters", acm jea 2022, https://arxiv.org/abs/2201.01174. claims used: the filters are "within 13% of the storage lower bound" "without sacrificing query speed", and construction can be "more than twice as fast" as for xor filters. supports idea 5.
9. FastFilter `xor_singleheader` readme, https://github.com/FastFilter/xor_singleheader. claims used: binary fuse8 "bits per entry 9.04" against a bound of 7.99, false-positive probability "1/256". "plan for about 24 bytes of memory per set entry" when building. "we expect that your initial set should have no duplicated entry". apache-2.0 licence. supports idea 5.
10. Metabuli preprint (Kim and Steinegger), https://www.biorxiv.org/content/10.1101/2023.05.31.543018v2.full. claims used: "query metamers from reads are sorted and compared to the reference metamer list". "because both query and reference metamers are sorted, a single iteration through the lists is enough to find all matches". it ran on "a notebook with just 8 GiB RAM and 8 threads". prior art for idea 3.
11. MegIS (isca 2024, extended), https://arxiv.org/html/2406.19113v1. claims used: "MegIS works with lexicographically-sorted data structures to avoid expensive random accesses to the SSD". query k-mers are sorted on the host. their setup made "the DRAM size ... larger than the size of all data accessed", so it never measures a kraken2 db bigger than ram. prior art for idea 3, and it leaves a gap.
12. SKiM (Schneggenburger and Zola, bioinformatics 2025), https://pmc.ncbi.nlm.nih.gov/articles/PMC12502918/. claims used: syncmer sub-sampling lets them "reduce the number of stored k-mers by approximately 85%". peak rss is 14.6 GB against 62.9 GB for default kraken2. kraken2 is still faster on ont reads (about 98-107 Mbp/s against 10-26 Mbp/s). prior art for ideas 3 and 4.
13. abseil swiss tables design note, https://abseil.io/about/design/swisstables. claims used: with sse, "we can winnow 16 candidates down to only those with a matching H2 hash in only a few instructions", and a deleted element does not stop probing "though an empty element would". supports idea 2.
14. "two-way linear probing revisited", https://arxiv.org/html/2309.05308v2. claims used: "the expected and the maximum unsuccessful search times in linear probing are invariant to the replacement strategy", and "in linear probing the unsuccessful search time is related to the cluster sizes". supports the ordered-probing note under "considered".

**fetches that failed or gave nothing usable (no claim used from them):**
- the mod-minimizer full pdf on biorxiv came back as unreadable binary
- the open-closed mod-minimizer at almob and springer redirected to a login
- mitzenmacher's robin hood pdf (arxiv 1401.7616) was binary, and its abstract has no early-termination claim
- programming.guide's robin hood page failed with a dns error
- arxiv 2107.01250, 2501.11582 and 1809.04339 abstracts say nothing about misses stopping early
- wikipedia "hash table" had no linear-probing formulas in the part read

---

## three findings every agent should know first

1. **upstream kraken2 master has moved past v2.17.1** [external 2, 3]. it builds a token stream per read, hashes only changed minimizers, skips capped ones, and then runs `GetBatch` with a prefetch distance of 8 distinct keys. our "stock" is the v2.17.1 tag [repo: `00_context.md` section 1]. [UNCLEAR]: whether this code is in a tagged release yet. a5 should know this before calling any batching idea new.
2. **S9 to S19 hash and prefetch every k-mer position, not every lookup.** S16's `fill()` runs `MurmurHash3` and `PrefetchIndex` for every non-ambiguous position [repo: `plan_paper/scripts/s6plus/s16_patch.py` lines 19-25]. the resolve loop then drops the repeats with `pf[i].min != last_minimizer` [repo: same file, line 46]. stock v2.17.1 hashed only inside that check [repo: `dorado-kraken-research/docs/reports/kraken2_get_optimizations_v2.md` S3 quotes stock's `hash->Get(*minimizer_ptr)` there]. so the S-chain does roughly 1/d times the hashing stock did, where d is the density (distinct minimizers per position, about 1/3 [guess]). idea 1 fixes this.
3. **M5's 90.7% reuse probably counted positions, not lookups.** the M5a recipe prints the minimizer "just before: `if (*minimizer_ptr != last_minimizer)`" [repo: `dorado-kraken-research/Luna/experiments/pending_measurements.md` M5a]. 351.8M emits over 104,918 reads is 3,353 per read, which matches one per position for ~3.4 kb reads [arith]. so about 2/3 of the "reuse" is the trivial next-window repeat that kraken2 already skips. at d ≈ 1/3 that leaves ~117M real lookups for 32.8M unique minimizers, so 72% of real lookups repeat an earlier minimizer, at an unbounded distance [arith on guessed d]. this partly explains the old tension with the 3.6% cache hit rate [repo]. [UNCLEAR]: whether the M5a recipe is the one that actually ran.

---

## idea 1. prefetch only what will be looked up

**1. name.** hash and prefetch only on a change. **byte-identical**, no db change.

**2. mechanism.**

wrong intuition: "the prefetch batch holds 16 lookups, and prefetching a line that is already on its way costs nothing."

what really happens:
- the scanner returns once per k-mer position [external 1]. a minimizer usually wins several windows in a row, so most positions repeat the previous one.
- S16's `fill()` still does a `MurmurHash3`, a virtual `PrefetchIndex` call (a 128-bit multiply plus a prefetch instruction) for every position [repo: `s16_patch.py`]. then the resolve loop throws the repeats away.
- on a capped db (one built with `minimum_acceptable_hash_value > 0`, which keeps only part of the hash space), `fill()` also prefetches lines for minimizers that the resolve loop skips without looking up [repo: `s16_patch.py` lines 48-50]. those are wasted ram trips (memory reads that miss every cache).

the fix: `fill()` keeps a `prev_min` that copies `last_minimizer` exactly. it is updated only on non-ambiguous positions and reset wherever `last_minimizer` is reset. `fill()` hashes only when `pf[n].min != prev_min`, and prefetches only when `hc >= minimum_acceptable_hash_value`. the resolve loop does not change, so every taxon and every counter stays the same. this is what upstream master already does with its token stream [external 2]. here it is restored inside S19's pipeline, which S9 gave up.

worked example:
- a 3,200-base read has 3,200 - 35 + 1 = 3,166 positions [arith]
- at d ≈ 1/3 [guess; the random-order value for (5, 31) is 0.333, external 5], about 1,055 of them change minimizer [arith]
- S19 does 3,166 hashes and 3,166 `PrefetchIndex` calls. the fix does about 1,055. that is 2,111 fewer per read, 67% [arith]
- over the full input (6,036 Mbp [repo]) that is about 4.0 billion fewer calls [arith: 6.036e9 x 2/3]

a side effect: a 16-position batch holds only about 5.3 distinct lookups [arith]. an optional variant 1b counts only real lookups towards `K2_B`. s20 (64 positions, about 21 distinct lookups) was a null on luna [repo], so luna does not need more prefetch distance. 1b is only for the orin tuning in E2.

**3. gain per class.**
- **H4 big server.** 50MB full input: -4 to -7% [guess]. `PrefetchIndex` is 7.0% of cycles [measured: `perf_s19.data`], and 2/3 of its calls go away if d ≈ 1/3, which is -4.7% [arith on guessed d]. 2/3 of the `MurmurHash3` cost inlined in `ClassifySequence` goes too; its share is [UNCLEAR]. big dbs full input: -1 to -4% [guess]. 10 and 1,000 reads: about 0, because they are load-bound [guess].
- **H1 laptop, H2 arm/jetson, H3 8 GB box.** the instructions saved per base are the same, so cpu-bound cells should see a similar share [guess]. on ram-bound cells, fewer prefetch instructions free load slots, effect [UNCLEAR].
- **cap-skip part.** only dbs with `minimum_acceptable_hash_value > 0` benefit. an older repo note says standard_8 has 0 [repo: `kraken2_get_optimizations_v2.md` S3]. for our 8GB and 16GB dbs it is [UNCLEAR]. if a db keeps a fraction f of hash space, (1 - f) of S19's prefetches on it are wasted ram trips [arith].
- **cold vs warm disk.** no difference. it only touches the classify phase [guess].

**4. days.** 0.5.

**5. risk.**
- correctness is low-risk, but `prev_min` must mirror `last_minimizer` through ambiguous spans, translated-search frames and the two-batch pipeline
- it is a null if `PrefetchIndex`'s 7% is mostly waiting rather than instructions [UNCLEAR]
- novelty is low. upstream master already does this [external 2]. the claim is "the S-chain added this cost, remove it"

**6. cheapest test that could kill it.**
- first read `minimum_acceptable_hash_value` from each db's `opts.k2d`, about 5 minutes. it decides whether the cap part matters at all
- then build one s21-style tree and run it against S19 on 50MB and 8GB, 3 interleaved reps, about 20 minutes
- kill it if 50MB gains under 1.5%

**7. sources.** 1, 2, 3.

---

## idea 2. line-aware probe: next-line prefetch plus a simd compare inside the line

**1. name.** line-aware probe. **byte-identical**, no db change. two parts that can be measured apart.

**2. mechanism.**

wrong intuition: "S16 prefetches each lookup, so a lookup never waits on ram."

what really happens:
- S16 prefetches one 64-byte line, the one holding the home cell `table_[idx]` [repo: `s12_patch.py`, `PrefetchIndex`]
- linear probing then walks forward until it reaches an empty cell (value 0) [external 3]
- 16 cells share a line. a probe that starts near the end of a line walks into the next line, which nobody prefetched. on a big db that is a full ram trip, and the "keep probing?" branch has to wait for it

how often this happens: at load 0.70 a lookup touches 1.07 lines on a hit and 1.32 on a miss [repo: trie brief section 1, arith]. so 7% of hits and 32% of misses pay one extra ram trip that nothing hides.

- **part a, next-line prefetch.** in `PrefetchIndex`, if the home cell sits in the last m cells of its line, also prefetch the next line. the check is by address, so it also works on the `-M` mapping. m = 6 should cover most crossings [guess]. it costs 6/16 = 37.5% extra line fetches [arith].
- **part b, simd compare inside the line** (simd: one instruction working on many cells at once). today the probe is a loop that stops after 1 to about 10 cells, and its exit depends on the data. part b instead loads the whole line and compares all 16 key fields with the query's key bits, and all 16 value fields with 0. that gives a match mask M and an empty mask E. shift both by the home offset:
  - if E has a set bit, the answer is the first M bit below the first E bit. if there is none, the lookup is a miss
  - if E has no set bit, return the first M bit, or move on to the next line

  this is exactly linear probing's rule, "first match before the first empty cell". it is the same group-compare trick swiss tables use: "winnow 16 candidates ... in only a few instructions", with an empty slot ending the probe [external 13]. written with gcc vector extensions, it should compile to 1 avx-512 load, 2 avx2 loads, or 4 sse2 or neon loads [guess on code quality].

worked example:
- the home cell is cell 13 of its line, and the lookup is a miss whose run ends 6 cells later
- today: cells 13, 14 and 15 are checked, then cell 0 of the next line. that is a fresh ram trip, about 100 ns on luna [guess], after 4 to 5 compares and a loop exit the branch predictor usually gets wrong
- with part a: the next line was prefetched together with the first one, a whole batch earlier
- with part b: two masked compares and one branch that is mostly predictable

how much this adds up to:
- with a miss fraction mf, the unhidden trips per lookup are 0.07 x (1 - mf) + 0.32 x mf. at mf = 0.5 [guess] that is 0.195 [arith]
- on 103GB at 32 threads, a thread does about 62.5M lookups [arith: 2.0e9 / 32, with 2.0e9 = 6,036 Mbp x 1/3, guess]
- 62.5M x 0.195 x 100 ns ≈ 1.2 s per thread if none of it is hidden [arith on guesses]
- S19's 103GB classify phase is roughly 9-16 s [arith: 13-20 s total minus up to 3.8 s load, repo]

**3. gain per class.**
- **H4 big server.** 50MB: part a about 0, because the table sits in L3 (the last cache level) [guess]. part b -2 to -5%, because `GetAt` is 12.5% of cycles [measured]. 8GB, 16GB and 103GB: 0 to -8% [guess]. intel's adjacent-line prefetcher may already fetch the paired line half the time [UNCLEAR].
- **H1 laptop.** every db is ram-bound there. even the 50MB table (48.8 MB [repo]) is 3x the 16 MB L3 [repo]. so part a applies to all four dbs: -2 to -8% [guess].
- **H2 arm/jetson.** same reasoning, with a 4 MB system cache [repo]: -2 to -10% [guess]. what the a78ae's own prefetchers do here is [UNCLEAR].
- **H3 8 GB box.** like H1 when the db fits in ram. when the db thrashes, this does not matter; idea 3 is the fix [guess].
- **cold vs warm disk.** classify phase only, no change [guess].
- **bandwidth.** +37.5% lines is about 48 GB extra over the full input [arith: 2.0e9 x 0.375 x 64 B]. that is small next to one channel's 25.6 GB/s [repo] over a run of tens of seconds [guess].

**4. days.** part a 0.25. part b 1.5.

**5. risk.**
- part a cannot change the output. it only adds a prefetch
- part b needs a scalar fallback for three edge cases: the table's last, partial line; the `-M` table, which starts 32 bytes into the file, so cell 0 is not line-aligned; and the stop after a full wrap of the table. with that fallback it stays byte-identical
- it is a null if the hardware prefetchers already bring in the next line, or if out-of-order execution hides the trip

**6. cheapest test that could kill it.**
- no new run needed: `perf annotate` `GetAt` in the saved `perf_s14_103.data` [repo: next_steps_plan row 4c]
- if the instructions on the "next cell after a line boundary" path hold under 10% of `GetAt`'s samples, part a is a null on luna. it should still be tried on orin in E2
- then build part a alone as one s21 tree and run it on 103GB and 8GB, 3 interleaved reps

**7. sources.** 3, 13.

---

## idea 3. sorted block lookup: an out-of-core mode for dbs bigger than ram

**1. name.** sorted block lookup (out-of-core: working on data bigger than ram by streaming it from disk in pieces). **byte-identical**, no db change.

**2. mechanism.**

wrong intuition: "if the db is bigger than ram, use `-M` and let linux page it in, so the disk only reads what gets touched." that is right for 10 reads. on a full input the lookups land all over the table. with `-M`, each lookup that hits a page not in ram is a major fault (a random 4 KB disk read). each thread does them one at a time.

the real point: the table, read in slot order, is already a list sorted by `hc % capacity`. so the lookups of many reads can be sorted by slot and merged against the table in one sequential sweep. Metabuli does this with its own sorted db ("a single iteration through the lists is enough" [external 10]). MegIS sorts on the host "to avoid expensive random accesses to the SSD" [external 11].

how it works:
1. for a block of reads, run the scanner and keep every real lookup (changed, not ambiguous, not capped) as a 16-byte record: the hash plus a back-reference to its position [arith: 8 + 4 bytes, padded]. this is upstream master's token stream [external 2], extended across many reads.
2. radix-partition the records by slot range (radix partition: splitting items into buckets by their top bits, in one read pass and one write pass).
3. for each range [a, b), `pread` the cells from a up to the first empty cell at or after b. a linear probe always stops at the first empty cell [external 3], so every probe that starts in [a, b) ends inside that buffer. the table's end wraps to its start the same way. so every lookup returns exactly what `GetAt` returns.
4. scatter the results back to their positions. then run the unchanged per-read logic: counting, `ResolveTree`, quick mode replayed on the full taxa list, and output in input order, as S8 already does.

an optional dedupe: identical minimizers in a block are looked up once. finding 3 above suggests up to ~72% of lookups repeat inside one 104,918-read file [arith on guesses]. real blocks are smaller, so the share is [UNCLEAR].

worked example, H3 (8 GB ram, nvme at about 2-3 GB/s [guess], the 16GB db at 15 GB [repo], full input):
- a 3 GB record buffer holds 187M records [arith: 3e9 / 16]
- about 2.0B lookups [guess] need 11 blocks. 11 sweeps x 15 GB = 165 GB of sequential reading, which is 55-83 s [arith on the guessed disk speed]
- `-M` instead: the page cache holds perhaps a third of the table [guess], so about 1.3B lookups fault to disk. at 16 threads and 100k-400k random reads per second [guess], that is about 3,300-13,000 s [arith on guesses]
- the normal copy path cannot even allocate 15 GB

**3. gain per class.**
- **H3 8 GB box.** it turns thrashing into streaming: 10-100x on 8GB and 16GB full inputs [guess]. small inputs stay on `-M`. a switch picks this mode only when the table is bigger than free ram and lookups x 4 KB is far above the table size [guess rule].
- **H1 laptop.** only 2.9-3.8 GB were free when checked [repo], so the 8GB db and up are in the H3 situation today. same gain [guess]. with 16 GB free, the 8GB db fits and the mode stays off.
- **H2 arm/jetson.** the 8GB and 16GB dbs fit in 64 GB, so the mode is off. 103GB fits neither ram nor the 57 GB emmc [repo]. with an external ssd and a ~40 GB buffer (about 2.5B records, one sweep), it goes from "cannot run" to minutes [guess].
- **H4 big server.** warm and the db fits, so the mode is off. the in-ram dedupe variant is [UNCLEAR] and probably a loss, because sorting and scattering add random writes [guess].
- **cold vs warm disk.** the biggest gain is cold with a db bigger than ram. cold and fits: one sweep can overlap reading with classifying [guess], and that overlap is a2_storage's lever.

**4. days.** 6-10 [guess]. the work is splitting `ClassifySequence` into scan, resolve and decide phases, plus the partition, the range sweep, output order, quick mode and paired reads.

**5. risk.**
- byte-identity needs care in quick mode, paired reads and translated search. modes not covered fall back to the normal path
- it needs memory-budget logic
- it is a null if `-M` with readahead tuning already does well on an ssd. a2 may argue for `MADV_RANDOM`
- prior art: Metabuli and MegIS do the sorted join over their own sorted dbs. using kraken2's hash order as the sort key looks new [UNCLEAR, after one search]

**6. cheapest test that could kill it.**
- on luna, run S19 `-M` on the 16GB db with 104,918 reads inside a cgroup (a linux memory limit for one job) capped at 8 GB, e.g. `systemd-run --user --scope -p MemoryMax=8G`. page cache should count against the cap [UNCLEAR: needs cgroup v2 user delegation on luna]
- log wall time and major faults. about 30 minutes
- if it lands within 2x of the warm S19 run, idea 3 is not needed: kill it

**7. sources.** 2, 3, 10, 11, 12.

---

## idea 4. lower-density canonical sampling

**1. name.** lower-density canonical sampling. **needs a db rebuild** (the db stores one scheme's minimizers) **and an accuracy check.**

**2. mechanism.**

wrong intuition: "kraken2 already samples, one minimizer per window, so it cannot sample less without breaking the window guarantee." it can sample less and keep the guarantee that every 35-base window still contributes at least one sampled l-mer.

the real numbers:
- kraken2's window holds w = 5 l-mers of length 31 [external 1, 4]
- a random-order minimizer has density 2/(w+1) = 0.333 [external 5]
- for exactly kraken2's (5, 31), Kille et al. list the mod-minimizer at 0.226 and the lower bound at 0.222 [external 5, table 1]
- mod-sampling picks the smallest t-mer, with t ≡ 31 (mod 5), so t = 6 or 11. it then samples the l-mer at that position mod w [external 6]

what it buys: fewer lookups per base and fewer distinct minimizers in every db, both down by 1 - 0.226/0.333 = 32% [arith]. this holds if kraken2's real density is near 0.333 [UNCLEAR: its xor-toggle order is not a random order].

worked example:
- a read's 3,166 positions give about 1,055 lookups now and about 715 at 0.226 [arith]
- db sizes, if cells scale with stored minimizers [guess]:
  - 103GB: 111 GB to ~75 GB
  - 16GB: 15 GB to ~10 GB
  - 8GB: 7.6 GB to ~5.2 GB
  - 50MB: 48.8 MB to ~33 MB
  [arith]

the catch is canonical sampling (a read and its reverse complement must sample the same l-mers, or reads from the other strand miss):
- kraken2 gets this by taking the window minimum over canonical l-mer values [external 1]
- mod-sampling's "position mod w" step is not mirror-symmetric
- simd-minimizers implements canonical random minimizers when l = w + k - 1 is odd. it is 35 here, so odd. the docs say nothing about canonical mod-minimizers [external 7]
- whether any canonical scheme gets near 0.226 at (5, 31) is [UNCLEAR]
- SKiM shows the space side of sampling: syncmers, about 85% fewer stored k-mers [external 12]

**3. gain per class.**
- **H4 big server, and every class on ram-bound cells.** classify saves up to 32% x the lookup share [arith]. 50MB on luna: 19.5% x 0.32 ≈ -6% cpu [arith on the measured 19.5%], minus any extra scanner cost [UNCLEAR]. load and exit read 32% fewer bytes [arith]. for 103GB warm on luna that is about 1 s of at most 3.8 s [arith on repo].
- **H1 laptop.** like H3 while free ram is low. otherwise like H4 per lookup [guess].
- **H2 arm/jetson.** more dbs fit and every db loads faster. cold 16GB on emmc at 0.25-0.33 GB/s [external, unverified, from `00_context.md`] goes from 45-60 s to 31-41 s [arith].
- **H3 8 GB box.** the 8GB db at ~5.2 GB fits once in 8 GB of ram under `-M` [arith], so it stops thrashing: a large gain [guess].
- **cold vs warm disk.** cold gains most, because the bytes read drop by 32% [arith].

**4. days.** 1 for the density test. 3-5 for the scanner, the 50MB rebuild and the accuracy check [guess]. 8GB and 16GB need the library genomes on luna [UNCLEAR]. 103GB cannot be rebuilt on luna [repo].

**5. risk.**
- the canonical requirement may remove most of the gain
- fewer hits per read changes calls near the confidence threshold, so it needs the accuracy check from `00_context.md` fact 3
- the new scanner (a sliding minimum over 30 six-mers, then a mod) may cost more cpu than it saves on 50MB [UNCLEAR]
- low-density schemes are well known. the new claim is only applying them to kraken2

**6. cheapest test that could kill it.** laptop only, no luna:
- a ~150-line C# program, compiled by powershell the way `laptop_loadscale.ps1` already compiles C# [repo]
- it reads the 6 ESKAPE genomes and counts sampled l-mers per base for (a) kraken2's current scheme (canonical, xor toggle, spaced-seed mask) and (b) the best canonical candidate
- it also scans the reverse complement to check that each scheme is strand-symmetric
- kill it if (b) is less than 15% below (a) [guess threshold], or if (b) is not strand-symmetric
- the same run measures kraken2's real d, which ideas 1, 2 and 3 also need

**7. sources.** 1, 4, 5, 6, 7, 12.

---

## idea 5. miss prefilter built from hash.k2d

**1. name.** miss prefilter. **byte-identical**, built from the existing `hash.k2d`, so it needs no library genomes and no rebuild.

**2. mechanism.**

wrong intuition: "a bloom or xor filter in front of the table changes the answers, because the table itself returns false positives." that is true if the filter is built over the real minimizers. built over what the table can actually match, a "no" from the filter is always a "no" from the table.

the real point: `GetAt` returns a hit only if some cell between the home slot and the first empty cell holds the query's fingerprint (the key bits kept in the cell) [external 3]. two versions follow from that.

- **b-lite.** a bitmap over every fingerprint value present anywhere in the table. if the query's fingerprint is absent everywhere, the probe cannot match, so skip it. this only works when the fingerprint space is sparse.
  - the 50MB db has 26 key bits [repo] and 8.53M keys [repo: `kraken2opti_report.tex` section 4]
  - the bitmap is 2^26 bits = 8 MB
  - about 1 - e^(-8.53M / 2^26) = 11.9% of values are present, so 88% of misses get skipped [arith]
  - on 103GB it is useless: 16 key bits, so every value is present [arith]
- **b-full.** an occupancy bitmap (1 bit per cell) plus a binary fuse filter (a compact read-only set that answers "maybe present" or "definitely absent") over (run start, fingerprint) pairs. a run is a maximal block of occupied cells. a probe never leaves its run, so "pair absent" proves "miss".
  - binary fuse8 costs 9.04 bits per key, with a false-positive probability of 1/256 [external 9]
  - that is within 13% of the storage bound [external 8]

worked example, laptop with the 50MB db:
- the table is 48.8 MB against 16 MB of L3 [repo], so every lookup is a ram trip
- b-lite's 8 MB sits in L3
- if 60% of lookups miss [guess], 0.6 x 0.88 = 53% of ram trips become L3 hits [arith]
- b-full for 50MB: a 1.53 MB bitmap plus 8.53M x 9.04 bits = 9.6 MB of filter, 11.2 MB in all [arith]. it skips 99.6% of misses but costs a few dependent cache reads [UNCLEAR: the access count is not in the fetched sources]

**3. gain per class.**
- **H1 laptop.** panel dbs, where the table is bigger than the last-level cache and the filter is smaller: 0 to -15% [guess]. it depends on the miss fraction and on how much S16 already hides.
- **H2 arm/jetson.** the 4 MB system cache [repo] holds neither filter, so about 0 [guess].
- **H3 8 GB box.** big-db filters are gigabytes (16GB: ~3.4 GB [arith: a 470 MB bitmap + 2.6B keys x 9.04 bits]). that does not fix thrashing; idea 3 does. 0 to small [guess].
- **H4 big server.** the 50MB table already sits in the 105 MB L3, so this would be a loss. keep it off. the luna case where table > L3 > filter is eskape_650mb at 142 MB, just past the cliff [repo] [guess].
- **cold vs warm disk.** no difference [guess].
- **auto rule.** turn it on only when the table is bigger than the last-level cache and the filter is under half of it, both read from sysfs [guess rule].

**4. days.** b-lite 1.5. b-full 4-6: a builder, plus a 3-stage prefetch pipeline that checks the filter first and touches the table only on "maybe".

**5. risk.**
- byte-identical by construction. the danger is a null, if S16 already hides most of the ram trip
- building the filter takes about 24 bytes per key [external 9]: 205 MB for the 50MB db, about 63 GB for 16GB [arith]. big-db filters must be built on a big box
- niche: it helps one class

**6. cheapest test that could kill it.** free, no new run:
- run awk over column 5 of an existing S19 50MB output on luna
- miss fraction = the sum of "0:" counts / the sum of all non-"A:" counts [external 4]
- kill it if that is under 30%
- on capped dbs, "0:" also counts skipped minimizers, so use 50MB

**7. sources.** 3, 4, 8, 9.

---

## my ranking

1. **idea 1, prefetch only what will be looked up.** the cheapest, byte-identical, helps every machine, and removes a cost the S-chain itself added.
2. **idea 2, line-aware probe.** cheap and byte-identical. it matters most on the machines we have no data for, because there every db is ram-bound.
3. **idea 3, sorted block lookup.** the only idea that lets the 8 GB box (and ck's laptop as it is today) run a full input on the 8GB db and up. it is expensive, and it stays off on luna.
4. **idea 4, lower-density sampling.** the broadest win: lookups, db size, load, exit, fitting in ram. but it needs a rebuild, an accuracy check, and a canonical low-density scheme that may not exist.
5. **idea 5, miss prefilter.** byte-identical and needs no rebuild, but it helps one class: a small-cache box with a panel db.

---

## considered, not proposed this round

- **ordered linear probing** (Amble and Knuth 1974): keep each run ordered by fingerprint, so a miss stops at the first larger fingerprint, with no extra bits per cell. predicted [guess]: miss probes drop from about 6 to about 2. that would cut miss line crossings and move the false-positive cliff (thesis 2) while keeping line locality, which double hashing gives up. not proposed yet, because the classic result behind it could not be fetched this cycle. the one fetched statement, that unsuccessful search times "are invariant to the replacement strategy" [external 14], covers probing until an empty cell, not early stopping. cheapest test: a 100-line simulation at load 0.70. it is a thesis 2 idea, not a portability one. i may bring it in R2 with a source.
- **double hashing**: each probe goes to a new line, so it is slower. its value is thesis 2 accuracy only [repo].
- **bucketized cuckoo or swiss-style tags with a rebuild**: comparing a whole bucket against a key that is only a fingerprint compares more cells per miss, so false positives go up. on 103GB (16 key bits) that moves towards the cliff at b* ≈ 13 [repo: `kraken2opti_report.tex` eq. cliff].
- **mphf, elias-fano, trie**: already priced in the trie brief, and predicted to lose on speed [repo].
- **branchless window minimum**: with w = 5, a minimum over the last 5 candidates replaces the deque's pop loop. it is byte-identical because ties have equal values [external 1]. it belongs to the scanner, so it goes to a3_cpu.

---

## notes for later rounds (my own reasoning file)

- check whether upstream master's token stream is in a tagged release after v2.17.1. if it is, "stock" should arguably be that release, and S19 vs upstream master is a fair new comparison.
- ask a3: is the `MurmurHash3` share inside `ClassifySequence` visible in `perf annotate` (idea 1's second half)?
- ask a2: does `-M` with `MADV_RANDOM` or readahead tuning close idea 3's gap on an ssd?
- ask a4: what next-line hardware prefetchers do zen3 and the a78ae have (idea 2)?
- numbers still open: miss fraction per db, kraken2's real density d, `minimum_acceptable_hash_value` of the 8GB and 16GB dbs, the cross-read repeat share per block.
- R2 candidates: fetch a source for ordered-probing miss cost. cite van herk / gil-werman only if fetched.
