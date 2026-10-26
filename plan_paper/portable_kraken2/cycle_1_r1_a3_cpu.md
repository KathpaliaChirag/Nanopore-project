# cycle 1, round 1: a3_cpu (scanner, simd, threads, input lock, arm vs x86, compiler)

agent a3_cpu. role: the cpu side. research and writing only: nothing was built, run or committed.

---

## sources read this cycle

all fetched on 2026-10-26. none were cited in an earlier cycle file (this is cycle 1).

| # | source | exact claim used (quote or close paraphrase) | supports |
|---|---|---|---|
| S1 | groot koerkamp and martayan, "SimdMinimizers: computing random minimizers, fast", SEA 2025. https://drops.dagstuhl.de/storage/00lipics/lipics-vol338-sea2025/html/LIPIcs.SEA.2025.20/LIPIcs.SEA.2025.20.html | the input is split into L chunks, "L = 8 on AVX2 and NEON", and chunks overlap so each window falls inside one chunk. a "completely deterministic two-stacks sliding window minimum algorithm" whose only branch "triggers exactly every w iterations". "3.4× (for large w=19) to 6.8× (for small w=5)" faster than scalar rescan. the hash is 32-bit and only its upper 16 bits are compared. a 16-lane avx-512 build was about 20% slower than avx2. de-interleaving the output and dedup are the main bottleneck. non-ACGT characters "have to be handled during this preprocessing" | ideas 2, 5 |
| S2 | the same paper's bioRxiv abstract, seen as a WebSearch result (not fetched as a page). https://www.biorxiv.org/content/10.1101/2025.01.27.634998.full.pdf | finds all (canonical) minimizers of a 3.2 Gbp human genome in 5.2 (resp. 6.7) seconds. whether that was one thread is [UNCLEAR]: my fetch of S1 did not confirm it | idea 2 (sizing only) |
| S3 | langmead, wilks, antonescu, charles, "scaling read aligners to hundreds of threads on general-purpose processors", bioinformatics 2018. https://pmc.ncbi.nlm.nih.gov/articles/PMC6361242/ | O-parsing "both reads and parses a sequencing read in the critical section". deferred (D), batch (B) and block-deferred (L) parsing move the parse out of it. B beat D in "basically every scenario tested". L-parsing with striped output was best in 11 of 18 cases. machines up to 272 threads (KNL). the TinyThread++ spinlock "scaled poorly", and on numa "choice of lock type has a major impact on thread scaling". output "becomes the bottleneck on very large numbers of threads" | idea 4, notes |
| S4 | upstream kraken2 on github (DerrickWood/kraken2), master as of 2026-10-26: `CHANGELOG.md`, the releases api, `src/classify.cc`, `src/compact_hash.h`, `src/fast_reader.h`, the commit list for `src/fast_reader.h`, `src/mmscanner.cc`, `scripts/kraken2`. https://github.com/DerrickWood/kraken2 | v2.18.0-RC1, published 2026-10-20, lists "Batched minimizer lookups with software prefetching", "Parallel hash table loading", "Huge page support", a parser that "Keeps parsing out of the input critical section", a "Stricter FASTQ parser", and "Keep the minimizer window in a vector rather than a deque". `classify.cc` phase 1 pushes a key only when `*minimizer_ptr != last_minimizer` and marks repeats `TOK_REPEAT`. `compact_hash.h`: prefetch distance 8 from `K2_PREFETCH_DIST`, slot `hc % capacity_`, the prefetched key is hashed and `Get()` hashes it again, load threads from `K2_DB_READ_THREADS` default 8 with no cap, `posix_memalign` to 2 MB plus `MADV_HUGEPAGE`. `fast_reader.h`: the critical section only reads raw bytes and cuts at a record boundary, and it credits langmead et al. 10 commits from 2026-09-04 to 2026-10-16, incl. "Hand out views over the block buffer instead of copying each record". `mmscanner.cc`: returns after each completed l-mer once k chars are read, pops with `queue_.back().candidate > candidate_lmer`. `scripts/kraken2`: decompresses with `open my $fh, "$compression_program -dc $qm_file |"` and passes `/dev/fd/N`; auto-detects only the first file; `$threads = $ENV{"KRAKEN2_NUM_THREADS"} || 1`. changelog also: "Fixed issue causing classification to hang when processing compressed inputs" | section 0, ideas 1, 3, 4, notes |
| S5 | gcc manual, common function attributes, `target_clones`. https://gcc.gnu.org/onlinedocs/gcc/Common-Attributes.html | a function is "cloned into multiple versions compiled with different target options than specified on the command line". for aarch64 it "works similarly" to `target_version`. "GCC must be configured to use GLIBC 2.23 or newer in order to use the target_clones attribute" | idea 5 |
| S6 | x86 instruction reference. https://www.felixcloutier.com/x86/pminud:pminuq and https://www.felixcloutier.com/x86/pcmpgtq | `VPMINUQ` (unsigned 64-bit min) exists only in EVEX forms (AVX512F / AVX512VL), no VEX/avx2 form. `VPCMPGTQ` ymm: "Compare packed signed qwords ... for greater than", flag AVX2 | idea 5 |
| S7 | nvidia developer forum, "jetson orin processor features (unknown architectural extension 'flagm')". https://forums.developer.nvidia.com/t/jetson-orin-processor-features-unknown-architectural-extension-flagm/266838 | gcc-11 `-march=native` on orin resolves to `armv8.2-a+crypto+fp16+rcpc+dotprod+flagm`, then "Error: unknown architectural extension 'flagm'". gcc-9 resolves to plain `armv8-a`. jetpack r35.3.1 / r35.4.1. no workaround given | idea 5, E3 notes |
| S8 | knespel and brunst, "rapidgzip: parallel decompression and seeking in gzip files using cache prefetching", HPDC 2023. https://arxiv.org/abs/2308.08955 | "Using 128 cores, our implementation reaches 8.7 GB/s decompression bandwidth for gzip-compressed base64-encoded data", a speedup of 55 over single-threaded GNU gzip; "5.6 GB/s for the Silesia corpus, a speedup of 33 over GNU gzip" | idea 3 |
| S9 | panchenko et al., "BOLT: a practical binary optimizer for data centers and beyond". https://arxiv.org/abs/1807.06735 | data-center apps are "very large and complex". "up to 8.0%" on top of profile-guided function reordering and LTO; gcc/clang binaries up to 20.4% on top of FDO and LTO | E3 notes |
| S10 | clang user's manual, profile guided optimization. https://clang.llvm.org/docs/UsersManual.html | "As you make changes to your code, clang may no longer be able to use the profile data". sampling profiles "can only be used for optimization". IR-based instrumentation (`-fprofile-generate`) is recommended. merge raw profiles with `llvm-profdata merge` | E3 notes |

**fetches that failed, so their claims are not used:**
- `src/seqreader.cc` and `src/seqreader.h` on upstream master: 404. the commit list explains it: "Replace seqreader with fast_reader" (2026-10-16).
- openbenchmarking.org `lscpu` page for a jetson orin: 403. so i cannot quote orin's cpu flag list. the claim "no sve on orin" below rests only on S7's `-march=native` string, which has no `+sve`.
- the arm cortex-a78ae technical reference manual pdf: fetched, but only as a binary stream i could not read. developer.arm.com pages for the a78ae and for `vcgtq_u64`: redirect or empty. so neon register width and the a78ae branch-miss penalty stay [UNCLEAR] this cycle.
- the oxford nanopore minknow output spec and a ridom user guide: fetched, but neither says whether fastq output is gzipped by default. so "nanopore fastq is usually .gz" stays a [guess].

---

## 0. a finding that changes the baseline: upstream kraken2 v2.18.0-RC1

**wrong intuition:** "stock kraken2 is v2.17.1, so S19 vs v2.17.1 is the comparison anyone will ask for."

**what actually happened:** upstream released v2.18.0-RC1 on 2026-10-20 [external S4], six days ago and after S19 was finished on v2.17.1. it already contains its own version of several S-stages. i checked upstream master; the RC1 tag came out after the 2026-10-16 parser commit, so it very likely includes it [guess: i did not fetch the tag's own tree].

| our stage | upstream master / v2.18.0-RC1 | tag |
|---|---|---|
| S9, S16 batched prefetch | yes: three phases, distinct keys collected, `GetBatch` prefetches 8 keys ahead (`K2_PREFETCH_DIST`) | [external S4] |
| S10 parallel load | yes: `pread` on disjoint chunks, `K2_DB_READ_THREADS` default 8, no cap. it still loads before `omp_set_num_threads` | [external S4] |
| S14 huge pages | yes: 2 MB `posix_memalign` + `MADV_HUGEPAGE` under `#ifdef` | [external S4] |
| S11 / S18 window | a `vector` instead of the `deque`. whether it has S18's store-forwarding stall is [UNCLEAR] | [external S4] |
| the parse floor (E5) | yes: parsing outside the input lock, records handed out as views (no copy) | [external S4] |
| S12 no division | no: `hc % capacity_`, and the prefetched key is hashed twice | [external S4] |
| repeated minimizers | skipped before the batch (`TOK_REPEAT`), which S9/S16 do not do (idea 1) | [external S4], [repo] |
| S8, S15, S17 | [UNCLEAR], not checked | |

**what this means.** any "S19 is X times faster than stock" claim will now be read against v2.18.0-RC1, and nobody has run that. the cheapest fix is an experiment, not an idea, so i only flag it for the relay and a5_skeptic: build v2.18.0-RC1 into a new tree on luna, byte-compare it with v2.17.1 (its parser is "stricter" [external S4], so this is not guaranteed), and run the 16 cells against S19. it also changes my ideas 1 and 4 below: both now have upstream prior art.

---

## 1. the numbers i build on

every gain estimate below starts from these. the arithmetic is shown so a5 can re-derive it.

- input: 6,036 Mbp in 1,872,777 reads [measured, next_steps_plan E1], so 3,223 bases per read [arith: 6,036e6 / 1,872,777].
- k-mers per read: 3,223 - 35 + 1 = 3,189 [arith].
- the scanner returns once per k-mer, i.e. once per base after the first k [external S4: `mmscanner.cc` breaks after each completed l-mer once `str_pos_ >= k_`].
- 50MB S19 needs about 234 core-seconds [repo: next_steps_plan 4a, 8-core S18 = 29.31 s x 8]. so 38.8 ns of cpu per base [arith: 234 / 6.036e9].
- the scanner is 38.5% of cpu [measured], so 14.9 ns per base [arith: 0.385 x 38.8]. at 3.0-3.8 GHz that is 45-57 cycles per base [arith; the all-core clock is a guess]. caveat: the 38.5% comes from a 32-thread profile and the 234 core-s from an 8-core run.
- `PrefetchIndex` is 7.0% [measured], so 2.7 ns per k-mer call [arith: 0.070 x 38.8].
- six functions hold 88.3% of cycles [arith: 38.5 + 25.1 + 12.5 + 7.0 + 3.1 + 2.1, measured shares]. the hot code is small.
- minimizer density (how often the minimizer changes between neighbouring k-mers): window w = k - l + 1 = 5 l-mers [arith], and a random order changes the minimizer with probability about 2 / (w + 1) = 1/3 per step [guess: the standard density formula; the repo already guesses "lookups ≈ bases / 3"]. kraken2's spaced-seed mask may push density lower [guess].

---

## 2. the ideas, in my rank order

### idea 1. skip the hash and prefetch for repeated minimizers in the S16 fill loop

**1. name and output check.** dedupe before prefetch. **byte-identical**: the same lookups happen in the same order; only work whose result is thrown away is removed. check with `check.sh` + `modes.sh`.

**2. mechanism.**
- *wrong intuition:* "S9 prefetches each lookup once, so the pipeline has no waste."
- *what really happens:* the scanner hands back one minimizer per k-mer, and neighbouring k-mers usually share one. S16's `fill()` hashes and prefetches every non-ambiguous k-mer: `pf[n].hc = MurmurHash3(pf[n].min); pf[n].idx = hash->PrefetchIndex(pf[n].hc);` [repo: `scripts/s6plus/s16_patch.py` lines 23-26]. but the resolve step only uses `hc` and `idx` when `pf[i].min != last_minimizer` [repo: same file, line 46]. so every repeated k-mer pays a hash, a virtual call, a FastMod multiply and a prefetch of a cache line that is already on its way. stock kraken2 never did this: it only hashed inside that `if` [repo: `s9_patch.py` lines 72-80 keep stock's logic in pass 2]. S9 introduced the waste when it moved hashing into pass 1. upstream avoids it: phase 1 pushes a key only for a changed minimizer and marks repeats `TOK_REPEAT` [external S4].
- *the fix:* in `fill()`, keep `fill_last`, the minimizer of the previous non-ambiguous k-mer, reset to `UINT64_MAX` exactly where resolve's `last_minimizer` is reset (once per frame [repo: `s9_patch.py` line 47]). if `pf[n].min == fill_last`, mark the slot `dup` and skip the hash and the prefetch. resolve does not change. a `dup` slot always takes the `taxon = last_taxon` branch, because at resolve time `last_minimizer` holds the same value `fill_last` held at fill time: both are "the minimizer of the previous non-ambiguous k-mer in this frame".
- *worked example:* a read has 3,189 k-mers [arith]. at density 1/3, about 1,063 need a lookup and about 2,126 are hashed and prefetched for nothing [arith]. over the whole input that is about 4.0 billion wasted calls [arith: 6.036e9 x 2/3]. `PrefetchIndex` costs 2.7 ns per call [arith, section 1]. dropping 2/3 of them saves about 1.8 ns of the 38.8 ns per base, **about 4.7% of cpu on 50MB** [arith on the 1/3 guess]. the `MurmurHash3` that is inlined into `ClassifySequence` comes on top [UNCLEAR how much].
- *what it does not change:* the look-ahead. S16 keeps two batches of 16 k-mers in flight, about 10.7 distinct lookups [arith: 32 / 3]. that stays the same if `K2_B` keeps counting k-mers. an optional env switch could count distinct lookups instead (16 distinct is about 48 k-mers [arith]). that is still byte-identical. s20 (64 k-mers) was a null on luna [measured], but orin's memory latency is different [UNCLEAR], so it is worth one point in E2's `K2_B` step.

**3. gain per class.** instruction savings only: a repeated prefetch targets a line already in flight, so no dram traffic is saved [guess].

| class | gain | tag |
|---|---|---|
| H1 laptop | 2-5% on cpu-bound cells | [guess] |
| H2 orin | 2-6%: weaker cores make instruction savings a bigger share of wall | [guess] |
| H3 8 GB box | 2-5% | [guess] |
| H4 luna | 50MB about 3-5%; 103GB 0-2% (memory-bound) | [arith on guess], [guess] |
| warm vs cold | warm only. a cold run that waits on the device gains 0 | [guess] |

**4. days.** 0.5-1.

**5. risk.** correctness: `fill_last` must reset exactly where `last_minimizer` resets (per frame in translated search, per mate in paired mode). `modes.sh` covers paired, quick and fasta [repo]. null risk: if the core is stall-bound, the extra hash work may run for free in the shadow of the stalls. then `PrefetchIndex` samples drop but the wall does not move.

**6. cheapest kill test.** about 30 min on luna. build a new tree with the change, `perf record` 50MB at 32 threads. `PrefetchIndex` should fall from 7.0% to about 2-3%. then 3 interleaved reps on 50MB and 8GB against S19. kill if the wall gains less than 1% on both (CV under 2%). in the same build, two counters (fill calls, non-dup calls) for one run give the real density instead of my 1/3.

**7. sources.** S4 (upstream `TOK_REPEAT`, per-l-mer return); repo `s9_patch.py`, `s16_patch.py`, `s12_patch.py`.

---

### idea 2. a batch scanner with a branch-free window (scalar, every isa)

**1. name and output check.** `NextBatch` + min-of-5 window. **byte-identical** if the per-k-mer stream of (minimizer value, ambiguous flag) is identical to stock's. check with a new stream-equivalence test, then `check.sh` + `modes.sh`.

**builds on E3.** E3's LTO step tests whether the compiler alone inlines `NextMinimizer` and removes the per-call cost (prologue and epilogue are about 9% of the scanner [measured]). this idea is the source-level version. it removes the call cost on any compiler, including where LTO is unavailable or fails, and it changes the algorithm, which no flag can do.

**2. mechanism.**
- *wrong intuition:* "S18 removed the scanner's stall, so what is left is real work, and only SIMD (one instruction on many values) can speed it up."
- *what is left is a lot of time per base.* the scanner costs about 14.9 ns, 45-57 cycles, per base (section 1). the work per base is maybe 20-25 simple instructions [guess]: look up the 2-bit code, shift it into the l-mer, update the rolling reverse complement (S17), take the smaller of the two, apply the spaced-seed mask and the toggle xor, update the window. a modern core retires about 4 instructions per cycle on code like this [guess], which is 6-10 cycles, not 45.
- *where the rest likely goes* [guess, the kill test checks it]: the window is a monotone queue (a deque in stock, a ring in S18, a vector upstream). each new candidate pops every larger one from the back: `queue_.back().candidate > candidate_lmer` [external S4]. on random DNA the number of pops (0, 1, 2...) is random, so the branch predictor (the cpu's guess of which way a branch will go, made before it knows) is often wrong. each wrong guess throws away roughly 15-20 cycles of work [guess]. the check for an expired front is data-dependent too. and there is a function call per base.
- *the fix, part 1: no data-dependent branches.* kraken2's window is tiny: w = 35 - 31 + 1 = 5 l-mers. so keep the last 5 candidates in a fixed 8-slot ring and take the minimum of the 5 directly every step: 4 compare-and-select operations (a cmov, a "conditional move" that picks one of two values without branching). no branch depends on the data. the simd-minimizers paper makes the same move for any w with a "completely deterministic two-stacks sliding window minimum" whose only branch "triggers exactly every w iterations" [external S1]. for w = 5 the plain min of 5 is simpler [guess]. a two-stacks fallback covers databases built with a larger k - l.
- *the fix, part 2: one call per batch.* `int n = scanner.NextBatch(min_out, amb_out, la_batch)` fills the 16 slots that S16's `fill()` asks for in one call. scanner state stays in registers for 16 bases, and the call cost is paid once per 16 k-mers instead of once per k-mer [arith: 1/16].
- *why the value is the same:* the monotone queue's front is the minimum of the window's candidates. the strict `>` pop keeps equal values [external S4], and kraken2 uses only the value, never the position. after an ambiguous base the queue is cleared. the next clean k-mer starts exactly k bases later, when exactly k - l + 1 = 5 new candidates exist [arith], so "min of the last 5" is defined exactly when the old code first returns a non-ambiguous minimizer. k-mers inside an ambiguous span return a stale value with the ambiguous flag set [external S4], and classify ignores that value. the new code keeps the same state machine anyway, so the test can demand an exact match on both fields.
- *worked example* (toy values, window of 5 positions p0-p4 = 40, 17, 93, 21, 58):
  - old: the monotone queue holds [17, 21, 58]. p5 = 25 arrives. pop 58 (58 > 25, branch taken), test 21 (21 > 25, not taken, loop exits), push 25: [17, 21, 25]. the front p1 is still inside p1-p5, so the minimizer is 17. at p6 = 30: no pop, push, then the front p1 expires (branch taken), pop it: minimizer 21. the branch pattern changes every step.
  - new: the ring holds [17, 93, 21, 58, 25] at p5, min of 5 = 17. at p6 it holds [93, 21, 58, 25, 30], min = 21. same values, the same 4 cmovs every step, nothing to mispredict.

**3. gain per class.** if NextMinimizer has about 1 branch miss per base and the call cost is about 9% of it, the scanner could fall from about 15 ns to about 4-7 ns per base [guess]. that would be 20-28% of total cpu on 50MB [arith on the guess: (15 - 4..7) / 38.8]. i plan with a wider, lower range:

| class | gain | tag |
|---|---|---|
| H1 laptop | 5-20% on cpu-bound cells. caveat: on the laptop even the 50MB db is bigger than the 16 MB L3 [arith: 50 > 16], so lookups lean on the one dram channel more than on luna, and the scanner's share there is unknown | [guess], [UNCLEAR] |
| H2 orin | 5-20%. there is no isa-specific code, so this is the cpu idea most likely to carry to arm. the a78ae miss penalty is [UNCLEAR] | [guess] |
| H3 8 GB box | as H1 | [guess] |
| H4 luna | 50MB 5-25%, 8GB/16GB 3-15%, 103GB 2-10%. the S14 103GB profile still has about 45% of cycles in NextMinimizer + ClassifySequence + GetAt | [guess], [measured] |
| warm vs cold | warm. cold device-bound runs gain 0 | [guess] |

**4. days.** 3-4: 1 day for a stand-alone `scan_test.cc` (like `parse_test.cc` [repo]) that times the scanner alone and dumps the stream, 1-2 for `NextBatch`, 1 for checks.

**5. risk.** correctness of the ambiguity state machine. protein and translated mode keep the stock path (`!dna_`, `revcom_version 0`), as S17 does [repo: `s17_patch.py`]. null risk: the 45 cycles may not be branch misses (front-end or dependency stalls instead). then only the call-cost half is left, and E3's LTO may already capture it. S11 showed scanner changes can null out [repo].

**6. cheapest kill test.** 15 min, no build: `perf stat -e cycles,instructions,branches,branch-misses` on S19 50MB at 8 threads, plus `perf record -e branch-misses` to see how many land in NextMinimizer. divide by 6.036e9 bases. kill the branch-free half if NextMinimizer has under 0.2 misses per base (at most about 3-4 cycles per base at stake [arith: 0.2 x 15-20]). the batch-call half is judged by E3: if s21b's `nm` shows NextMinimizer inlined and the scanner share falls by about its 9% prologue/epilogue, the compiler has done that half.

second test, portable, about 1 h: `scan_test.cc` on luna, orin and any linux laptop gives scanner ns per base on each machine. we have no per-machine scanner number today.

**7. sources.** S1 (two-stacks, deterministic branch), S4 (pop condition, per-l-mer return); repo `s17_patch.py`, `s18_patch.py`, `06_S11.md`, `13_S18.md`, `perf_s19.data` shares.

---

### idea 3. faster, parallel decompression for .gz input, picked at startup

**1. name and output check.** startup-picked decompressor plus read-ahead. **byte-identical**: gzip is lossless, so classify sees the same bytes. check: S19 on `.fastq.gz` vs stock on the plain `.fastq`, through `check.sh`.

**2. mechanism.**
- *wrong intuition:* "S13 cut the parse to 3.9 s, so the input side is done."
- *that is true for our plain test file only.* real nanopore inputs are often `.fastq.gz` [guess: neither ONT document i fetched states the default]. upstream's changelog fixes a hang "when processing compressed inputs" [external S4], so kraken2 users do send them. kraken2 decompresses in its perl wrapper: for each file it opens `$compression_program -dc $qm_file |` and hands classify a `/dev/fd/N` path [external S4]. so decompression is one external single-threaded `gzip` process per file. with S8's in-order stream, only the file being read makes progress; the others sit blocked behind full pipe buffers [guess: linux pipes buffer 64 KB by default, not fetched]. the input rate is one gzip. and the wrapper auto-detects compression from the first file only [external S4].
- *how fast is one gzip:* rapidgzip reaches 8.7 GB/s on 128 cores, "a speedup of 55 over single-threaded GNU gzip", and 5.6 GB/s (33x) on the Silesia corpus [external S8]. so GNU gzip ran at about 158-170 MB/s on their machine [arith: 8.7 / 55, 5.6 / 33].
- *worked example:* our 12.5 GB input, gzipped, needs about 74-79 s just to inflate at that rate [arith: 12.5 / 0.158..0.170]. S19's whole run is 8.88 s (50MB) to 20.08 s (103GB) [measured]. so gz input would make S19 roughly 4-9x slower than plain input on luna [arith, on the guess that fastq inflates at the paper's rate]. every S-stage would sit behind it.
- *on the laptop (H1):* 16 threads classify 50MB in about 234 / 16 = 14.6 s of luna-core time [arith; laptop cores differ], while one gzip needs 50-78 s [arith on a guessed 0.16-0.25 GB/s]. gz-bound by about 3.5-5x [arith on guess]. a parallel inflater at 1-2 GB/s on those 16 threads [guess] would take 6-12 s, hidden under the 14.6 s.
- *the fix, step a (wrapper only):* at startup, pick the fastest decompressor present, in order `rapidgzip -P <threads>`, `igzip`, `pigz`, then `gzip`, and detect compression per file. step b (in-process): decompress file i+1 (and i+2) in helper threads while file i is parsed, bounded by free ram, so even a single-threaded inflater uses several cores across a 16-file input.

**3. gain per class** (only when the input is .gz; 0 for plain input by construction).

| class | gain | tag |
|---|---|---|
| H1 laptop | gz-bound 3.5-5x today; a parallel inflater removes most of that | [arith on guess] |
| H2 orin | also a storage win. emmc at about 0.25-0.33 GB/s reads the plain 12.5 GB in about 38-50 s cold [arith on context's unverified emmc number]; gz at a 3-4x ratio [guess] is about 10-17 s of reading [arith on guess], but only a parallel inflater turns that into a speedup. and a 3-4 GB gz input [guess] fits in orin's 8.5 GB free [repo], which would open E2's 1,872,777-read column | [arith], [guess], [repo] |
| H3 8 GB box | as H1; read-ahead must be capped by free ram | [guess] |
| H4 luna | gz input 74-79 s of serial inflate [arith on external] down to under about 5 s [guess] | |
| warm vs cold | strongest cold (fewer bytes from the device). warm is still bound by the inflate | [guess] |

**4. days.** 0.5 (wrapper) + 2-3 (in-process read-ahead).

**5. risk.** rapidgzip / igzip may not be installed (a new optional dependency, with gzip as the fallback). read-ahead memory on H3. null: if ck's and sir's pipeline only ever feeds plain fastq (our dorado output is plain [repo: `reads_hac.fastq`]), the gain is 0 for us, though not for kraken2 users.

**6. cheapest kill test.** 10 min on luna: `gzip -k reads_hac.fastq` (703 MB [repo]), `time gzip -dc reads_hac.fastq.gz > /dev/null`, then S19 on 8GB at 32 threads on the `.fastq` vs the `.fastq.gz`. kill if the gz run is within 10% of the plain run.

**7. sources.** S8 (gzip throughput), S4 (wrapper code, changelog).

---

### idea 4. take the parser out of the input lock (port upstream's fast_reader)

**1. name and output check.** out-of-lock parsing. **needs a check:** upstream calls it a "Stricter FASTQ parser i.e. no empty records, missing quality strings" [external S4], so malformed records may be handled differently. on well-formed input it should be identical [guess]. check: `check.sh` + `modes.sh` (fasta, paired, 3-file) + one deliberately malformed file.

**builds on E5.** E5 measures whether the 3.88 s serial parse is the wall. this idea is the fix if it is. we do not need to write it: upstream did it in 10 commits from 2026-09-04 to 2026-10-16 [external S4].

**2. mechanism.**
- *wrong intuition:* "a parallel parser has to split the file up front, and fastq can't be split safely because '@' can also start a quality line."
- *the real design* (langmead et al.): don't split in advance. inside the lock, only read raw bytes and find the end of the last complete record. parse afterwards, outside the lock, in each thread's own buffer. they call the variants deferred (D), batch (B) and block-deferred (L) parsing. B beat D in "basically every scenario tested", and L with striped output was best in 11 of 18 cases, on machines up to 272 threads [external S3]. upstream kraken2's `fast_reader.h` does exactly this and credits that paper [external S4].
- *what moves out of the lock:* in v2.17.1, `LoadBlock` runs `kseq_read` + `copy_from_kseq` inside `critical(seqread)` [repo: `seqreader.h:107-126`, `classify.cc:522`]. the line scan (S13), the record logic and the copies of header, sequence and quality into strings are all serial. upstream also hands out views into the block buffer "instead of copying each record" [external S4], so the copy disappears.
- *worked example:* a 3 MB block holds about 480 reads [arith: 3,145,728 bytes / about 6,546 bytes per record (3,223 bases + 3,223 quality + about 100 header)]. the input is about 3,974 blocks [arith: 12.5e9 / 3,145,728]. the serial parse costs 0.98 ms per block [arith: 3.88 s / 3,974]. classifying a block on 50MB costs about 59 ms of core time [arith: 234 core-s / 3,974]. so one serial parser feeds at most about 60 threads before workers queue on the lock [arith: 59 / 0.98]. that matches E5's "binds near 60+ threads" prediction [repo]. with the parse outside the lock, what stays serial is the raw `read()` copy from page cache plus the boundary cut, maybe 0.3-0.5 ms per block [guess: a single-thread copy at 6-10 GB/s]. the knee moves to about 120-200 threads [arith on guess].

**3. gain per class.**

| class | gain | tag |
|---|---|---|
| H1 laptop | 0-3%: 16 threads are far below the ~60-thread knee. the only gain is the removed copy; memmove is 3.1% of cpu [measured], an upper bound, since the share from `copy_from_kseq` is unknown | [arith], [UNCLEAR] |
| H2 orin | 0-3%, same reason (12 threads) | [guess] |
| H3 8 GB box | 0-3% | [guess] |
| H4 luna | 50MB and 8GB at 64+ threads: E5's predicted 4-5 s plateau could move toward the classify bound, maybe 2.5-3.5 s at 96 threads | [repo: E5 guess] |
| warm vs cold | the raw read stays inside the lock in both designs, so cold-input i/o stays serial. no change cold | [external S4], [guess] |

**4. days.** 2-4 to port `fast_reader` into S19. S8's multi-file stream lives in the old `seqreader.h` [repo: `s8_patch.py`], so S8 must be redone on the new reader; upstream's own multi-file handling is [UNCLEAR]. or 3-6 days to rebase the whole S-chain onto v2.18.0-RC1 [guess]. upstream moved to C++17 on 2026-10-14 [external S4], so orin's compiler must support it [UNCLEAR: E2 step 1 prints the gcc version].

**5. risk.** different output on malformed input. S8 interplay. paired mode. and it only pays on H4.

**6. cheapest kill test.** E5 (already planned). plus section 0's run of v2.18.0-RC1 at 32, 64 and 96 threads on 50MB next to S19: if upstream does not beat S19's 96-thread plateau, the lock is not the wall.

**7. sources.** S3, S4; repo `seqreader.h` line refs, `parse_test.cc`, `s8_patch.py`, next_steps_plan 4a and E5.

---

### idea 5. a simd scanner with runtime dispatch (avx2 / avx-512 / neon), only after idea 2

**1. name and output check.** multi-lane scanner, path chosen at startup. **byte-identical** if the per-k-mer stream matches (the same test as idea 2).

**builds on E3 and idea 2.** E3's `-march=native` will not vectorize the scanner by itself [guess: each base's state depends on the previous base's]. so SIMD needs hand-written code, and to stay portable the binary must pick its code path at startup.

**2. mechanism.**
- *wrong intuition:* "simd-minimizers is 6.8x faster than scalar at w = 5 [external S1], so a SIMD kraken2 scanner gets about 6.8x too."
- *kraken2's order is different.* simd-minimizers compares a 32-bit hash, only its top 16 bits, 8 lanes per avx2 register [external S1]. kraken2 takes the minimum of 62-bit values: the canonical 31-base l-mer at 2 bits per base, spaced-seed masked and xor-toggled [external S4]. byte-identical output needs that exact order, so each lane must be 64 bits:
  - **avx2** (laptop zen 3, luna): 4 lanes of 64. avx2 has only a *signed* 64-bit compare, `vpcmpgtq` "compare packed signed qwords" [external S6], and no 64-bit min; `vpminuq` exists only with avx-512 [external S6]. signed is enough if every candidate fits in 63 bits [UNCLEAR: whether the toggle mask is cut to the l-mer's 62 bits]; if not, each compare needs one extra xor.
  - **avx-512** (luna's sapphire rapids): 8 lanes of 64 with `vpminuq` [external S6]. but simd-minimizers found its 16-lane avx-512 build about 20% slower than avx2 [external S1], so wider is not automatically faster.
  - **neon** (orin): 128-bit registers, so 2 lanes of 64 [UNCLEAR: not fetched this cycle]. no sve: gcc-11's `-march=native` on orin expands to `armv8.2-a+crypto+fp16+rcpc+dotprod+flagm`, with no `+sve` [external S7].
- *so the gain is upside down relative to need:* biggest on the big server, smallest on the jetson, which has the weakest cores. that is why idea 2 (branch-free scalar) comes first: it helps every isa the same way.
- *layout:* split each read into L chunks that overlap by k - 1 = 34 bases, as simd-minimizers overlaps its chunks [external S1]. worked example: a 3,223-base read in 4 avx2 lanes is 4 chunks of about 806 bases, so 4.2% repeated work [arith: 34 / 806]. with 8 lanes it is about 8.4% [arith: 34 / 403]. the output must be put back into k-mer order for the prefetch pipeline. simd-minimizers names exactly this de-interleaving plus dedup as its main bottleneck [external S1].
- *ambiguous bases:* simd-minimizers leaves non-ACGT to preprocessing [external S1]. kraken2 must flag every k-mer that contains an N, so each lane carries an ambiguity mask [guess: one shift and one or per base per lane, like `last_ambig_`].
- *dispatch:* gcc's `target_clones` builds a function "into multiple versions compiled with different target options" and picks one at run time. on aarch64 it "works similarly" to `target_version`, and it needs glibc 2.23 or newer [external S5]. a simpler option we fully control: check the cpu once when the scanner is built (gcc's `__builtin_cpu_supports("avx2")` [guess: standard builtin, not fetched]), with idea 2's scalar code as the fallback. glibc already does this for `memchr` and `memmove`: the S19 profile shows `__memmove_avx512_unaligned_erms` [measured], picked at run time inside a portable binary. so S13 already carries to any cpu glibc supports [guess].

**3. gain per class** (on top of idea 2).

| class | gain | tag |
|---|---|---|
| H1 laptop (zen 3, avx2) | scanner 1.2-2x, so 2-8% wall on cpu-bound cells | [guess] |
| H2 orin (neon) | 1.0-1.3x, so 0-4%; may be a null | [guess] |
| H3 8 GB box | depends on its cpu | [UNCLEAR] |
| H4 luna (avx-512) | 1.5-3x, so 3-12% on 50MB-class cells, less on 103GB | [guess] |
| warm vs cold | 0 cold | [guess] |

**4. days.** 8-12: avx2 first, then neon. avx-512 only if avx2 gains.

**5. risk.** the highest code risk in my list: three code paths that must stay identical, plus the scalar fallback. S11 showed scanner work can hide a stall and null out [repo].

**6. cheapest kill test.** after idea 2: if the branch-free scalar scanner is already at most about 10% of cpu, stop. the remaining ceiling is then at most 1 / (1 - 0.10) = 1.11x [arith]. before any SIMD code, run idea 2's `scan_test.cc` on luna, the laptop and orin for a scalar ns-per-base baseline per machine.

**7. sources.** S1, S5, S6, S7; repo `perf_s19.data` (memmove symbol), `06_S11.md`.

---

## 3. notes that build on E3 and E5 (not new ideas, not ranked)

1. **E3 on orin will hit a compiler trap.** gcc-11's `-march=native` expands to `...+flagm` and the assembler rejects it; gcc-9 resolves it to plain `armv8-a`, i.e. no tuning at all [external S7]. so on orin: read `gcc --version` first (E2 step 1 already prints it), then pass an explicit `-mcpu=cortex-a78ae` or `-march=armv8.2-a+crypto+fp16+rcpc+dotprod` [guess: whether orin's binutils accepts these is UNCLEAR].
2. **one portable x86 binary.** `-march=native` binaries do not run on other cpus. a middle level like `-march=x86-64-v3` (the avx2 level) would run on the zen 3 laptop and on luna but not on older cpus [guess, not fetched]. suggestion: E3 adds one more tree with `-march=x86-64-v3` beside `-march=native`. if they tie, ship v3, or v2 plus idea 5's dispatch.
3. **fp contraction on arm.** E3 adds `-ffp-contract=off` on x86 to protect `--confidence` maths. on aarch64 a fused multiply-add always exists, so even a plain build may fuse those doubles [guess: gcc's default in gnu mode, not fetched]. E2's cross-machine output check (step 7) could then show arm vs x86 differences the S-chain did not cause. add `-ffp-contract=off` to the orin builds of both stock and S19.
4. **PGO profiles are per source version.** clang: "As you make changes to your code, clang may no longer be able to use the profile data" [external S10]. so a shipped profile must be regenerated after each source change. whether an x86 profile helps an arm build is [UNCLEAR]; the docs i read do not say. per-machine PGO, as E3 plans, is the safe default.
5. **BOLT later, not now.** BOLT's case is "very large and complex" data-center binaries, up to 8.0% on top of FDO and LTO [external S9]. kraken2's hot code is six functions holding 88.3% of cycles [arith, measured shares], so code layout is unlikely to be the limit [guess].
6. **the default is one thread.** the wrapper sets `$threads = $ENV{"KRAKEN2_NUM_THREADS"} || 1` [external S4]. a user who forgets `--threads` runs S19 on one core, on every machine. defaulting to the physical core count is byte-identical (thread count does not change output: `modes.sh` checks 1 and 7 threads [repo]). zero gain in our benchmarks, large for real users [guess].
7. **upstream's loader has the same ordering issue.** it loads before `omp_set_num_threads` and takes its thread count from `K2_DB_READ_THREADS`, default 8, no cap [external S4]. passed to a2_storage.
8. **E5 could add a no-code variant:** `OMP_PROC_BIND=close OMP_PLACES=cores`, which keeps each thread on one core and fills one socket first [guess: standard openmp variables, not fetched]. it tests one candidate cause of the 64-thread plateau. H4 only.
9. **output at high thread counts is unmeasured.** langmead et al. found output "becomes the bottleneck on very large numbers of threads" and that lock type matters on numa [external S3]. our sweeps used `--output /dev/null` [repo], so kraken2's ordered output path at 64-192 threads has never been timed. upstream now spills a block to a temp file when the output lock is busy [external S4].

---

## 4. my ranking

ranked by: works on every isa, byte-identical, cheapest kill test, quality of evidence for the mechanism.

| rank | idea | byte-identical | days | headline gain | why this rank |
|---|---|---|---|---|---|
| 1 | dedupe hash + prefetch in `fill()` | yes | 0.5-1 | about 4.7% cpu on 50MB [arith on the 1/3 density guess], 2-6% on H1-H3 [guess] | the waste is visible in our own code, upstream already avoids it, every isa gains, half a day |
| 2 | batch scanner, branch-free min-of-5 | yes (stream test) | 3-4 | 5-25% cpu on cpu-bound cells [guess] | attacks the 38.5% on every isa; a 15-minute `perf stat` decides it before any code |
| 3 | parallel / faster decompression for .gz | yes | 0.5 + 2-3 | on luna gz input costs 74-79 s of serial inflate [arith on external] vs 8.9-20.1 s for the whole S19 run [measured] | possibly the biggest real-world lever, but 0 for plain input; a 10-minute test decides it |
| 4 | out-of-lock parser (port upstream) | needs check | 2-4 | H4 only, at 64+ threads [repo: E5 guess]; 0-3% elsewhere | E5 decides; upstream already wrote it |
| 5 | SIMD scanner with runtime dispatch | yes (stream test) | 8-12 | 3-12% on luna, 0-4% on orin [guess] | gain is inverted vs need (avx-512 most, neon least); only after idea 2 |

**dissent i expect, and my answer:** "idea 3 should be first: it is the biggest number." it is the biggest number only if the input is gzipped, and ours is not. if ck or sir confirm their real inputs are `.fastq.gz`, or the 10-minute test shows a big gap, i move it to rank 1.

---

## 5. questions for the other agents

- **a5_skeptic:** S19 vs v2.18.0-RC1 has never been run (section 0). is "1.9x-4.8x vs stock" still the right headline? also, please check my density 1/3 and the 234 core-s base in section 1.
- **a1_dsa:** idea 1 removes about 2/3 of hash calls [arith on guess]. does any table-format idea of yours change the cost per lookup enough that this matters more or less?
- **a2_storage:** idea 3 is a storage lever on the *input* side (fewer bytes from a cold disk). does it overlap with your cold-disk ideas for the db?
- **a4_hw:** idea 2's `scan_test.cc` would give scanner ns per base on each class. which machines can you get it run on? and do you have a sourced branch-miss penalty for zen 3 and a78ae?
