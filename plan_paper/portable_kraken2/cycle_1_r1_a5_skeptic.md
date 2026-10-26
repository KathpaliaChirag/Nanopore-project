# cycle 1, round 1: a5_skeptic (2026-10-26)

role: the skeptic. i check evidence, attack assumptions and look for prior art. evidence tags follow `00_context.md` section 6.

---

## sources read this cycle

every source below was fetched today with WebFetch or WebSearch. "S#" is how the body cites them.

| # | source (url) | exact claim used | supports |
|---|---|---|---|
| S1 | kraken2 CHANGELOG at master, https://raw.githubusercontent.com/DerrickWood/kraken2/master/CHANGELOG.md | the `[2.18.0-RC1]` entry lists: "Batched minimizer lookups with software prefetching - Restructured classification into three phases to overlap memory access latencies, significantly improving performance on large databases (especially on aarch64/Graviton). Tunable via K2_PREFETCH_DIST environment variable (default: 8)."; "Parallel hash table loading - Load compact hash tables with parallel reads to saturate fast storage"; "Huge page support - Back compact hash table with huge pages where available"; "New FASTA/FASTQ parser that Keeps parsing out of the input critical section for better parallelism"; "Configurable CHT cell size ... (32 and 40 bytes currently supported)"; "Fixed issue causing minimizers to be undercounted"; "Fixed double-free of index data at classify exit"; "Keep the minimizer window in a vector rather than a deque"; "Stricter FASTQ parser i.e. no empty records, missing quality strings, etc." | section 0, A1, A3, A9, A10, B1, B2 |
| S2 | kraken2 releases page, https://github.com/DerrickWood/kraken2/releases and https://github.com/DerrickWood/kraken2/releases/tag/v2.18.0-RC1 | v2.18.0-RC1 released "20 Oct", commit 8e35df5, marked "Latest"; v2.17.2 released 23 Sep; v2.17.1 is 2025-11-24. the master commit list (https://github.com/DerrickWood/kraken2/commits/master) dates "Update documentation for 2.18.0-RC1" to Oct 20, 2026 and "Replace seqreader with fast_reader" to Oct 16, 2026 | section 0, A1 |
| S3 | kraken2 pull request #1033, https://github.com/DerrickWood/kraken2/pull/1033 | 4 commits dated June 20, 2026, merged June 24, 2026: huge pages, "several concurrent `pread` streams over disjoint regions" (`K2_DB_READ_THREADS`, default 8), upstream kseq with `memchr()` and a 64KB buffer, batched prefetched lookups (`K2_PREFETCH_DIST`, default 8). benchmark: 5 GB/side paired fastq, 8 threads, ~34-35 GB db: Graviton4 266 s to 202 s (1.32x), x86 r7i 337 s to 204 s (1.65x); cold load on Graviton4 ~100 s to 34 s. "Output is byte-identical to stock." author: "I wonder if perhaps on NFS or large spinning disks, if this is counterproductive." huge-page commit: "The effect is most pronounced on aarch64 (e.g. Graviton), where page-walk costs are relatively higher." | section 0, A1, A3, A6, B1, B2 |
| S4 | kraken2 v2.18.0-RC1 source: https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/src/classify.cc, `.../src/compact_hash.h`, `.../src/mmscanner.cc`, `.../src/Makefile`, `.../CMakeLists.txt` | classify.cc: `load_index` runs before `classify()` calls `omp_set_num_threads`; reading stays in `critical(seqread)` but "parsing happens afterwards, outside the lock"; one `#pragma omp parallel` region per input file; `hit_counts[taxon]++` per token, no run-length counting; repeat tokens call `increaseKmerCount(1)`; no memory budget option. compact_hash.h: `posix_memalign` 2 MB + `#ifdef MADV_HUGEPAGE` madvise; `pread_parallel(..., db_read_threads(), ...)` with `K2_DB_READ_THREADS` default 8; `GetBatch` prefetches `table_[hc % capacity_]` 8 keys ahead; probe uses `idx %= capacity_`; `CompactHashCell40` exists. mmscanner.cc: `reverse_complement()` runs five shift-and-mask rounds per l-mer, not rolling; `NextMinimizer` is defined out of line in the .cc; candidates pushed as one struct. Makefile and CMakeLists both keep `-DLINEAR_PROBING`; no `-march`, no `-flto` | section 0, A1, A9, B1, B2 |
| S5 | kraken2 v2.17.1 classify.cc, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.17.1/src/classify.cc | repeat branch is `taxon = last_taxon;` with "no hash lookup, no `add_kmer` call"; `add_kmer` only on new minimizers and only when a report is requested | section 0 item 6, B1 |
| S6 | kraken2 v2.18.0-RC1 `k2` wrapper, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/scripts/k2 | `classify_multi_dbs` loops `for db in dbs: ... classify(args, temp_pathnames)`, sequentially; parts are merged by the `merge` binary with LCA re-scoring; quick mode is rejected because "the per-database calls cannot be merged into the call a single combined database would make"; gtdb parts are split by phylum | B4 |
| S7 | Centrifuger, Song and Langmead, Genome Biology 2024, https://pmc.ncbi.nlm.nih.gov/articles/PMC11046777 | "For the classification speed, Kraken2 was the fastest method."; at 8 threads on 67M read pairs "Kraken2 was the fastest method (finished in about 7 min)"; "The reported classification speed was calculated by taking the fastest runtime after excluding index loading time."; 41 GB index for 140 GBp, 43 GB memory; hardware "2.8 GHz AMD EPYC 7543 32-core processor machine with 512 GB memory". (fetch covered 100,000 of 106,086 characters; the last 6,086 were not read) | A4, B5, positioning |
| S8 | Metabuli, Kim and Steinegger, bioRxiv full text, https://www.biorxiv.org/content/10.1101/2023.05.31.543018.full | "Query metamers from reads are sorted and compared to the reference metamer list"; "because both query and reference metamers are sorted, a single iteration through the lists is enough"; "designed to utilize a user-specified size of RAM, it can classify reads against any size database as long as it fits in the machine's hard disk"; "able to complete the tasks on a notebook with just 8 GiB RAM and 8 threads" (MacBook Air 2020, M1); "Of all, Kraken2X was the fastest and used the least RAM". i read the preprint, not the Nature Methods version | A4, B3, positioning |
| S9 | kache-hash, Khan et al., bioRxiv 2026, https://www.biorxiv.org/content/10.64898/2026.02.13.705625v1.full | placement by minimizer: "Since consecutive k-mers share minimizers, they hash to the same buckets, preserving locality for streaming workloads."; "𝒪(1/r) amortized cache misses per operation, where r is the minimizer run length" (theory, r not measured); hardware: 2x Xeon Gold 5218, 768 GB ddr4; no prefetching, no huge pages; kraken2 not benchmarked | A11 |
| S10 | SSHash, Pibiri, Bioinformatics 2022, https://academic.oup.com/bioinformatics/article/38/Supplement_1/i185/6617506 | each k-mer "is associated to a unique integer identifier"; random lookups ~1,338 ns/k-mer (positive) vs streaming ~311 ns/k-mer (human, regular); single core of an i9-9940X | A11 |
| S11 | SSHash follow-up, "Optimizing sparse and skew hashing: faster k-mer dictionaries", bioRxiv 2026, https://www.biorxiv.org/content/10.64898/2026.01.21.700884v1.full | "a new layout that reduces the number of cache misses per query"; 2-3x faster streaming queries than the previous SSHash; Threadripper PRO 7985WX; stores no per-k-mer values; no mention of kraken2, prefetching or huge pages | A11 |
| S12 | MegIS, Mansouri Ghiasi et al., ISCA 2024 (arXiv html), https://arxiv.org/html/2406.19113 | R-Qry tools "commonly perform random accesses to search their database. A state-of-the-art tool in this category is Kraken2."; "Compared to SSD-C (SSD-P), No-I/O leads to 9.4x (1.7x) better performance in R-Qry"; footnote: loading the whole db performed slightly better than mmap because "the application accesses most parts of the database", with a 100 million read sample. the PDF url (https://arxiv.org/pdf/2406.19113) failed: the fetch tool returned raw binary | A4, A5, B3 |
| S13 | KrakenUniq on low-memory computers, Pockrandt, Zimin, Salzberg, JOSS 2022, https://pmc.ncbi.nlm.nih.gov/articles/PMC10438097/ | `--preload-size` loads one chunk, classifies all reads against it, repeats; "Classification results will be identical to running in the default mode."; 392 GB db, 9.4M reads: default memory mapping 48 h, whole preload 14 min, 8G chunks (49) 47 min, 16G 32 min, 64G 19 min; hardware not stated | A4, B3, B4 |
| S14 | Kun-peng, bioRxiv 2024, https://www.biorxiv.org/content/10.1101/2024.12.19.629356v1.full | "Kun-peng loads one 4GB block at a time, storing others on disk"; table "resembles Kraken2's but divides the table into ordered 4GB blocks"; standard db: Kun-peng-M peak 4.5 GB, 7.96% of kraken2's memory, 78.9% of kraken2's time; identity is claimed only between its own two modes, not vs kraken2; tested on a MacBook Pro and an M1 Max Mac Studio | B4 |
| S15 | MetaCache partitioning doc, https://github.com/muellan/metacache/blob/master/docs/partitioning.md | "Querying can always be done one partition at a time on a system that can only fit a single partition into memory."; results "have to merged afterwards"; no claim that merged output equals an unpartitioned db | B4 |
| S16 | linux cgroup v2 doc, https://docs.kernel.org/admin-guide/cgroup-v2.html | "A memory area is charged to the cgroup which instantiated it and stays charged to the cgroup until the area is released."; tracked usage includes "page cache and anonymous memory"; memory.max reaching the limit triggers reclaim, then "the OOM killer is invoked in the cgroup" | B3 |

**fetches that failed or came back empty** (claims not used):
- MegIS PDF: binary only. i used the arXiv html instead (S12).
- Metabuli GitHub README (https://github.com/steineggerlab/Metabuli): has none of the matching, mmap or speed claims. i used the preprint (S8).
- first kache-hash search: no hit. a second, exact search found it (S9).
- a search for the "minimizers undercounted" issue: no hit. so what that fix changes stays [UNCLEAR], see section 0 item 6.
- a web search for `K2_PREFETCH_DIST`: no hit. i found it in the source instead (S4).
- `src/compact_hash.cc` at v2.18.0-RC1 is an empty file. the table code lives in `compact_hash.h` (S4).

**repo files read:** `00_context.md`, `talk_track_sir_2026-10-21.md`, `next_steps_plan_2026-10-21.md`, both 2026-10-21 research briefs, `explanations/00_INDEX.md`, `command_log.md` (v2.17.1 tag check, 2026-08-25), `dorado-kraken-research/AccuracyDrift/RESULTS.md` section 1.4 (orin), `dorado-kraken-research/AccuracyDrift/machines/Orion.md`, `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`, `dorado-kraken-research/README.md` sections 8e and 8j, and greps of the two earlier debate files.

---

## 0. the finding that changes the debate: upstream kraken2 already shipped most of the S-chain

**the wrong intuition.** "stock kraken2 is v2.17.1. so S19's 1.9x-4.8x (full input) and 9.8x-15.4x (few reads) say how much faster we made kraken2."

**what is true.** kraken2 kept moving. on 2026-08-25 the repo checked that v2.17.1 was the latest **tag** [repo: `command_log.md`]. but upstream **master** (the main development branch) had already merged pull request #1033 on 2026-06-24 [external: S3]. a pull request (PR) is a proposed code change. it was merged before S8 was built. then on 2026-10-20, one day before meeting 13, upstream released **v2.18.0-RC1** (RC = release candidate, a near-final test release), with that PR plus more [external: S1, S2].

stage by stage, from reading the v2.18.0-RC1 source [external: S4] and PR #1033 [external: S3]:

| our stage | in v2.18.0-RC1? | how upstream does it |
|---|---|---|
| S8 one input stream | **no** | still one `omp parallel` region per input file |
| S9 batched prefetch | **yes** (PR #1033) | `GetBatch`: whole read's distinct minimizers, prefetch 8 keys ahead |
| S10 parallel load | **yes** (PR #1033) | `pread` streams, `K2_DB_READ_THREADS`, default 8 |
| S12 no division | **no** | `hc % capacity_` in prefetch and in `Get`, `idx %= capacity_` per probe |
| S13 memchr parser | **yes** (PR #1033) | upstream kseq with `memchr()`, 64 KB buffer |
| S14 huge pages | **yes** (PR #1033) | `posix_memalign` 2 MB + `MADV_HUGEPAGE` |
| S15 run-length counts | **no** | `hit_counts[taxon]++` per token |
| S16 two batches in flight | different design | a rolling prefetch distance of 8 is already a form of pipelining |
| S17 rolling revcomp | **no** | five shift-and-mask rounds per l-mer |
| S18 store-forward fix | [UNCLEAR] | vector window, one struct push, `erase(begin())`. needs its own perf annotate |
| S19 portability guards | **yes** (PR #1033) | `#ifdef MADV_HUGEPAGE` |
| (not built) parallel parse | **yes** | `fast_reader`: raw block read inside the lock, `Parse()` outside |

what this means:
1. **"stock" now needs a version number.** a new user who installs kraken2 from now on gets 2.18 [UNCLEAR: when bioconda ships it]. the honest headline is S19 vs v2.18.0-RC1, and nobody has measured it.
2. **novelty.** S9, S10, S13, S14 and S19 have prior public work, merged 2026-06-24 [external: S3]. the paper must cite PR #1033. what is still ours: S8, S12, S15, S17, probably S18, the loader-ignores-`--threads` finding, the exit-tax finding, and the luna sweep analysis.
3. **the 15.4x at 103GB / 10 reads** came from S10 + S14 [repo: talk track section 5]. upstream has both, with 8 loader streams instead of 32. against RC1 that cell is [guess] 1-4x, not 15x.
4. **the parallel parser** that E5 would decide on is already upstream. nobody should propose building it.
5. **the first non-luna numbers for these mechanisms** come from upstream, not us: 1.32x on Graviton4 and 1.65x on x86 at 8 threads for the bundle, and a cold load of ~100 s to 34 s on Graviton4 [external: S3]. one author, one run each as far as the PR says, cloud machines.
6. **the golden rule moves.** RC1 changed counting. v2.17.1 skips `add_kmer` for a repeated minimizer [external: S5]. RC1 calls `increaseKmerCount(1)` for it [external: S4]. the changelog calls this "Fixed issue causing minimizers to be undercounted" [external: S1]. from the code, the per-read output lines look unchanged and the report's k-mer counts change [guess from code reading, UNCLEAR until diffed]. the parser is also "stricter" and may refuse records v2.17.1 accepted [external: S1]. so "byte-identical vs stock" must say which stock.

---

## part A: the 12 weakest assumptions i expect the other four agents to lean on

ordered from most damaging to least. each one: the assumption, who will lean on it, why it is weak, what settles it, and the cost.

**A1. "stock is v2.17.1, and the S-chain's numbers are the speedup over kraken2."**
- who: everyone, every gain column.
- weak because: section 0. upstream RC1 holds S9, S10, S13, S14 and a parallel parse [external: S1, S3, S4].
- settles it: build v2.18.0-RC1 on luna with its own Makefile (it keeps `-DLINEAR_PROBING` [external: S4]), then the 16-cell grid S19 vs RC1 with `grid.sh`, plus a sorted byte compare of RC1 vs v2.17.1.
- cost: ~1.5 h. idea B1.

**A2. "50MB is the cpu-bound regime and 8GB+ is the ram-bound regime."**
- who: a3_cpu (scanner, SIMD, LTO aimed at "the cpu cells"), a4_hw.
- weak because: a regime is a property of db size **vs the last-level cache (LLC)**, not of the db. luna's L3 is 105 MB per socket [repo], so 50MB fits. orin's system cache is 4 MB and the laptop's L3 is 16 MB [repo]. orin stock v2.1.3 on 50MB already shows an LLC miss rate of 78.9% at 1 thread and 82.8% at 12 threads [measured: `AccuracyDrift/RESULTS.md` 1.4]. on orin the 50MB db is a ram-bound db. so on H1 and H2, the ram stages (prefetch, huge pages) should matter on 50MB, and the cpu stages should matter less than on luna [guess].
- settles it: `perf stat -e LLC-loads,LLC-load-misses` on S19 50MB on orin, added to E2.
- cost: +5 min inside E2.

**A3. "prefetch and huge pages help arm as much as x86."**
- who: a3_cpu, a4_hw (orin and laptop columns).
- weak because: the only cross-isa measurement is upstream's. the bundle gave 1.32x on Graviton4 and 1.65x on x86 (266 to 202 s vs 337 to 204 s) [external: S3]. the changelog says "especially on aarch64" [external: S1]. the measured ratio says the opposite for the bundle. arm's stock was already faster, and both end near 203 s. also Graviton4 (neoverse v2 server core) is not orin's cortex-a78ae. the a78ae's limit on outstanding cache misses (memory-level parallelism, MLP: how many ram trips one core can have in flight) is [UNCLEAR].
- settles it: E2 on orin, including the 1-thread classify ratio S19 vs stock and the `K2_B` sweep (E2 step 6).
- cost: ~1 h on campus.

**A4. "`-M` (memory-mapping) is the small-ram answer because it needs the db in ram only once."**
- who: a2_storage, a4_hw (H3 column).
- weak because: "once" only helps if the db fits in **free** ram. if it does not, a random lookup on an evicted page is a major fault (the kernel must read the page from disk), and the next lookups evict it again. KrakenUniq measured this on a 392 GB db and 9.4M reads: memory mapping 48 h, whole preload 14 min, 8 GB chunks 47 min [external: S13]. MegIS found a whole load slightly beat mmap for kraken2 at 100M reads, because "the application accesses most parts of the database" [external: S12]. E1 runs on a 503 GB box, so it says nothing about H3.
- settles it: idea B3 (cgroup-capped runs after evicting the file).
- cost: ~1 h.

**A5. "orin's emmc reads ~0.25-0.33 GB/s, so a cold load there takes ~25-35 s on 8GB."**
- who: a2_storage, a4_hw.
- weak because: the number is [external, unverified] in `00_context.md`. the only orin "cold" run says something else: stock 8GB at 1 thread, run 1 "cold" 23.17 s vs warm 20.20 s [measured: `RESULTS.md` 1.4]. if those 2.97 s were all device time, 7.6 GB came in at ~2.6 GB/s [arith]. so either that run was not really cold (no `fincore` proof exists), or the device is far faster than assumed. either way the 0.3 GB/s constant is not a planning number.
- settles it: `dd if=hash.k2d of=/dev/null bs=64M iflag=direct` on orin, the device-ceiling recipe already in `next_steps_plan` section 5.
- cost: 2 min.

**A6. "more loader streams always help, so lift the 32-thread cap."**
- who: a2_storage, a3_cpu.
- weak because: every luna load number is warm [repo]. upstream picked 8 streams by default, and the PR author worried that on "NFS or large spinning disks ... this is counterproductive" [external: S3]. on a hard disk, parallel streams turn one sequential read into seeks [guess]. upstream's cold win (100 s to 34 s) was on cloud block storage provisioned at 1 GB/s [external: S3], which likes deep queues.
- settles it: E4 cold with 1, 2, 4, 8 streams on at least one hdd or usb stick, plus the laptop nvme.
- cost: ~1 h per device.

**A7. "a run does about one lookup per 3 bases."**
- who: a1_dsa, a2_storage (the `-M` touched-fraction model in E1, the "~2G lookups" bandwidth estimate).
- weak because: it is a [guess] in `next_steps_plan` E1. the one count in the repo disagrees: an old WSL2 gprof run made 354,164,193 `NextMinimizer` calls and 9,871,933 `Get` calls, about 1 lookup per 36 bases [repo: `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`]. caveats: old version, 650 MB ESKAPE db, and gprof call counts under threads are not fully trusted. but a 12x gap moves E1's predictions: at 1 per 36 bases, the 103GB 1,000-read cell touches ~5% of the table, not ~47% [arith: 1 - e^(-0.63) vs 1 - e^(-0.053)].
- settles it: count lookups once. the gprof build at `~/tools/kraken2-pg` exists on luna [repo: `dorado-kraken-research/CLAUDE.md`], or add one counter to a throwaway tree.
- cost: ~15 min.

**A8. "a smaller table is a faster table."**
- who: a1_dsa (mphf, elias-fano, bitmask cells), thesis 2 talk.
- weak because: if the table misses the LLC either way, one lookup is still about one ram line [repo: trie brief section 4]. smaller only helps in three places: (a) a size that crosses an LLC (50MB fits luna, misses orin and the laptop), (b) a size that decides "fits in ram or not" on H3, (c) cold reads on a slow device. upstream just added a 40-bit cell, the other direction [external: S1].
- settles it: per-class arithmetic first, then B3 and B5.
- cost: arithmetic, then the B3/B5 tests.

**A9. "LTO will inline the scanner, and `-march=native` is a free portable win."**
- who: a3_cpu.
- weak because: `NextMinimizer` is out of line in `mmscanner.cc`, upstream too [external: S4]. gcc inlines by size heuristics, and `GetAt` sits behind a virtual `KeyValueStore*` call [repo: trie brief section 2]. the 2-8% (LTO) and 4-15% (PGO) are [guess] [repo: next_steps_plan E3]. they sit near luna's noise (A12). and a `-march=native` binary is not portable by definition: a binary for any machine needs per-target builds or runtime dispatch.
- settles it: E3 step 8, `nm -C classify | grep -c NextMinimizer` on the LTO build.
- cost: ~15 min after the build.

**A10. "the serial parse is a wall, so we should build a parallel parser."**
- who: a3_cpu.
- weak because: upstream RC1 already parses outside the lock [external: S1, S4]. and by the repo's own arithmetic it binds only near 60+ threads [repo: next_steps_plan 4a], so H4 only.
- settles it: E5 run on RC1 next to S19.
- cost: ~25 min.

**A11. "minimizer-bucketed hashing (kache-hash) or streaming lookups (SSHash) would give kraken2 locality it lacks."**
- who: a1_dsa.
- weak because: kache-hash's win is that consecutive k-mers share a minimizer, so they land in the same bucket, for O(1/r) misses per operation [external: S9]. SSHash's streaming lookups are ~4x cheaper than random ones for the same reason [external: S10]. kraken2 already stores **only** minimizers, and already skips the lookup when the minimizer repeats [external: S5]. it has that 1/r by construction. consecutive **distinct** minimizers hash to random slots. the repo's own cache test found a 3.6% hit rate [repo: talk track section 3]. also: kache-hash used no prefetching and no huge pages, ran on one intel box, and never ran kraken2 [external: S9]. SSHash stores only an id per k-mer, no taxon [external: S10, S11], so a taxon needs a second access.
- settles it: nothing to build. if someone insists, count how often two consecutive distinct minimizers of a read land in the same 64-byte line (one counter).
- cost: ~15 min.

**A12. "a 2-3% luna difference is a result."**
- who: everyone with a small predicted gain.
- weak because: 103GB reps differ by ±4% (86.58 s vs 92.93 s) and the same binary moved 23% across sessions (34.46 s to 26.40 s) [measured: next_steps_plan section 6]. one rep per cell cannot show 2-3%.
- settles it: 3+ interleaved reps in one session, CV reported, as the repo already did for S12-S18.
- cost: 3x the runtime of whatever is tested.

---

## part B: my 5 ideas, ranked

rank 1 and 3 are measure-first. rank 2 is the main build. rank 4 is a minutes-long kill test before anyone builds compression. rank 5 is a build that only happens if rank 3 says so.

### B1 (rank 1). re-baseline: S19 vs upstream v2.18.0-RC1, all 16 cells, plus RC1 vs v2.17.1

**1. name and output.** a measurement, no code. it also answers whether RC1 is byte-identical to v2.17.1 (it may not be, see section 0 item 6).

**2. mechanism.**
- wrong intuition: "the baseline is fixed, so our speedup is a fixed fact."
- real mechanism: a speedup is a ratio, and upstream moved the denominator. the main levers in S19's big ratios are in RC1 now (section 0 table).
- worked example, few reads: S19 on 103GB at 10 reads is 3.79 s against stock's 58.20 s [measured]. stock's load alone was ~56-58 s [measured: sweep]. S10 + S14 removed it. RC1 loads with 8 `pread` streams plus huge pages [external: S4]. if luna's warm load scales near-linearly from 8 to 32 streams (unknown, that is E4), RC1's load is up to ~4x S19's, so [guess] 4-15 s. against RC1 that cell is then [guess] 1-4x, not 15.4x.
- worked example, full input on 50MB: the stages RC1 lacks are S12 (-5.5%), S15 (~-2%), S17 (-3.7%), S18 (-2%) [measured, luna]. if they compose and carry over, 1 / (0.945 x 0.98 x 0.963 x 0.98) = 1 / 0.874 ≈ **1.14x** [arith]. S8 adds more on the 16-file input only (it was 1.41x on 50MB at its own step [measured]). RC1's parse outside the lock pulls the other way at high thread counts [guess].

**3. gain per class.** none directly. it sets the real headroom for every class. luna only, warm [repo].

**4. days.** 0.5.

**5. risk.**
- RC1 is a release candidate. the final 2.18 may change.
- RC1's stricter fastq parser may refuse a record in our 16 files [UNCLEAR].
- RC1 has two build systems. use its Makefile, and grep that `-DLINEAR_PROBING` survived, as for every s21 tree.
- what makes it a null: nothing. either result decides the story.

**6. cheapest test that could kill it** (kill = show that S19 still has a big lead and v2.17.1 is still the right reference). build RC1, run 50MB at 104,918 reads, sort and compare against S19's output. ~20 min. then `grid.sh rc_vs "s19=... rc1=..."`, 16 cells, 3 reps, ~25 min.

**7. sources.** S1, S2, S3, S4, S5.

### B2 (rank 2). "s22" = RC1 + the residual stages, sent upstream as a pull request

**1. name and output.** port S8, S12, S15, S17 (and S18 if RC1 has the same stall) onto v2.18.0-RC1. the target is byte-identical vs RC1.

**2. mechanism.**
- wrong intuition: "to be fast on any machine we need new machine-aware tricks."
- real mechanism: the most portable speedup is one that lives in the binary everyone installs. a jetson or laptop user will run upstream 2.18, not our S19. the residual stages are pure instruction savings with no luna constant in them. RC1 still divides per lookup and per probe step, increments a hash map per token, recomputes the reverse complement from scratch, and runs one parallel region per input file [external: S4].
- worked example: S12 removes 2-3 64-bit divisions per lookup at 20-40 cycles each [repo: talk track S12], so 40-120 cycles per lookup. at a 3 GHz core that is 13-40 ns per lookup [arith], the same order as an L3 hit. on luna it measured 5.5% on 50MB and nothing on 8GB [measured], because 8GB waits on ram.
- precedent: upstream merged PR #1033 in four days, after the author showed byte-identical output on two isas [external: S3].

**3. gain per class.**
- H1 laptop: the 50MB db misses a 16 MB L3, so the cpu stages count for less of the run than on luna's 50MB [guess]. S8 helps any multi-file input [guess].
- H2 orin: same direction. on orin, 50MB is ram-bound (A2). the 64-bit divide's latency on a78ae is [UNCLEAR], so S12's share is [UNCLEAR].
- H3 8 GB box: same as H1 where the db fits.
- H4 big server: measured vs stock on luna. vs RC1 [UNCLEAR] until B1. [guess] ~1.1-1.2x on 50MB and 8GB full input.
- cold vs warm: cpu stages give nothing to a cold load.

**4. days.** 3-5. RC1 restructured `ClassifySequence` into three phases, so the S15/S16 patch scripts will not apply as they are. S12, S17 and S8 should port with small edits [guess]. plus upstream review time.

**5. risk.**
- correctness: S8 changes how multi-file and paired input is fed; S12 needs its `__int128` guard on every compiler; S15 must keep first-seen order (it does on v2.17.1 [repo: talk track S15]).
- portability: none new; these are integer savings.
- null: if B1 shows S19 ≤ 1.05x over RC1 in the 50MB and 8GB full-input cells, the residual is not worth porting.

**6. cheapest test that could kill it.** B1's matrix. no new code.

**7. sources.** S3, S4, plus repo stage files `explanations/03_S08.md`, `07_S12.md`, `10_S15.md`, `12_S17.md`, `13_S18.md`.

### B3 (rank 3). small-ram emulation: cgroup-capped runs after evicting the db file, before any `-M` or chunking decision

**1. name and output.** a measurement. same binaries, so output stays comparable by byte compare.

**2. mechanism.**
- wrong intuition: "`-M` needs the db in ram once, so it solves the 8 GB box."
- real mechanism: page cache (linux's copy of file pages in spare ram) can only hold what fits. when the 15 GB 16GB db [repo: `dorado-kraken-research/CLAUDE.md` sizes] meets an 8 GB box, maybe 5 GB of it stays resident [guess: 8 GB minus os, input buffers and the process]. so about two lookups in three hit an evicted page. each is a major fault: a disk read of the page plus its readahead (luna's sda reads 1 MB around a fault [measured: next_steps_plan E4]).
- worked example: 104,918 reads ≈ 350 Mbp [arith: 703 MB fastq at ~2 bytes per base, and the gprof count of 354M scanner calls agrees]. at 1 lookup per 3 bases that is ~117M lookups, at 1 per 36 it is ~9.8M (A7). two thirds of them fault: ~78M or ~6.6M faults. at [guess] 100 µs per fault and 8 faults in flight, that is ~980 s or ~80 s, against ~1-2 s for a warm full load. stock and S19 cannot even allocate the 15 GB private copy on that box. KrakenUniq saw the same shape: 48 h mapped vs 14 min preloaded [external: S13].
- the emulation trap: cgroup v2 (the kernel's per-group memory limit) charges a page to the group that first brought it into memory, and it stays charged there [external: S16]. luna's db files are already in the global page cache from earlier runs. so a capped run on a warm file is **not** a small-ram run. the file must be evicted first (`dd iflag=nocache count=0`, already in `next_steps_plan` section 5), then run inside the cap, so the pages it reads get charged to it.
- what to run: stock, S19, S19 `-M`, RC1 and RC1 `-M` on 8GB and 16GB, at 10, 1,000 and 104,918 reads, under `systemd-run --user --scope -p MemoryMax=8G`, and again at 4G (the laptop had only 2.9-3.8 GB free [repo]). log `majflt` and wall.

**3. gain per class.** a measurement, so no gain itself. it decides H3 and the low-free-ram H1 case. predicted [guess]: 8GB db with `-M` survives at 10 reads and degrades by 104,918 reads; 16GB thrashes for every option. H2 orin (64 GB) and H4 are unaffected at these db sizes. it only means something cold, which is the point.

**4. days.** 0.5.

**5. risk.**
- whether luna's systemd hands the memory controller to user scopes is [UNCLEAR]. if not, it needs root or another linux box.
- luna's raid and controller cache make its "disk" faster than a laptop ssd [guess]. the cap emulates ram capacity only, not one memory channel or a small LLC.
- null: if `-M` under the cap stays within ~2x of uncapped warm, small ram is not a problem worth building for, and B4 dies.

**6. cheapest test that could kill it.** one run: S19 `-M`, 16GB, 104,918 reads, `MemoryMax=8G`, after eviction, with `majflt` and `fincore` before and after. ~15 min.

**7. sources.** S8 (the comparator bar: Metabuli ran on an 8 GiB M1 laptop), S12, S13, S16.

### B4 (rank 4 by value if B3 says go, built last). exact chunked pass over one table, for a db bigger than free ram

i rank it 5th in build order because it only happens after B3. i keep it as an idea because no kraken2 path does it exactly today.

**1. name and output.** byte-identical to the monolithic db, by design. KrakenUniq claims exactly this for its version [external: S13].

**2. mechanism.**
- wrong intuition: "split the db into smaller dbs that each fit." that is what MetaCache partitions [external: S15] and upstream's `k2` multi-db path do. `k2` classifies against each part in turn and merges hit lists with LCA re-scoring, and it refuses `--quick` because "the per-database calls cannot be merged into the call a single combined database would make" [external: S6]. parts are built and LCA'd on their own (gtdb is split by phylum [external: S6]), so answers can change. that needs an accuracy check.
- real mechanism: keep the one table and cut it by slot range.
  1. scan every read once. write each read's distinct minimizers (hash and slot) to a spill array (a temporary list, on disk if needed).
  2. for each chunk of slots [a, b), plus a tail for probe runs that cross b: load the chunk, resolve every spilled lookup whose slot falls in it, write the taxon back.
  3. replay each read's tokens in order and classify. RC1 already has this scan / resolve / replay shape in memory [external: S4], so phase 3 is its existing code.
  the hit list, the LCA and the tie-breaks are then the same as with the whole table in ram.
- worked example: 16GB db (15 GB), 4 GB chunks → 4 chunks. 104,918 reads → ~117M lookups at 1 per 3 bases [guess] → x 12 bytes (8-byte hash or slot + 4-byte taxon) = 1.4 GB spill [arith]. the db is read once, sequentially. at [guess] 2-3.5 GB/s nvme that is 4-8 s, against B3's [guess] 80-980 s of faulting. for the full 1.87M reads: ~2.0G lookups x 12 B = 24 GB spill [arith], so reads must also be batched, and each read batch re-reads the db. 10 batches x 15 GB = 150 GB of sequential reads, 43-75 s on that nvme [arith].
- kun-peng shows a kraken2-like table cut into 4 GB blocks runs at 4.5 GB peak and 78.9% of kraken2's time [external: S14]. it does not claim identical output to kraken2.

**3. gain per class.**
- H1 laptop with ~3-4 GB free [repo]: turns the 8GB db from "does not fit" into "runs" [guess].
- H2 orin: only for dbs over ~50 GB, the 103GB one [arith: 64 GB ram shared with the gpu]. cold, one sequential pass at the device's [UNCLEAR] speed (A5).
- H3 8 GB box: the main target. "cannot run" becomes "runs at device speed" [guess].
- H4 big server: none, everything fits.
- cold vs warm: reading the db once, in order, is the best possible cold pattern.

**4. days.** 6-10.

**5. risk.**
- correctness: probe runs that cross a chunk edge. the tail must cover the longest run of filled cells in the table, which is [UNCLEAR] (one pass over the table measures it). `--quick` stops early per read, so it cannot run chunked; fall back. paired reads and `--minimum-hit-groups` must replay exactly.
- portability: spill files need disk space and a tmp dir.
- null: B3 shows `-M` under the cap is fine, or upstream's `k2` multi-db path is accurate enough that nobody needs exact.

**6. cheapest test that could kill it.** B3. second: run upstream's `k2` multi-db path on a split db under the same cap and count differing read lines vs the monolithic db.

**7. sources.** S6, S13, S14, S15.

### B5 (rank 5 in value, minutes to test). measure `hash.k2d` compressibility before anyone builds compression for cold slow storage

**1. name and output.** lossless compression, so byte-identical. the measurement comes first.

**2. mechanism.**
- wrong intuition 1 (in the repo's own brief): "the cells are near random, so the ratio is poor" [repo: `research_brief_next_speedups` load table, a [guess]].
- wrong intuition 2: "a hash table is mostly empty, so it compresses a lot."
- real mechanism: count the information per cell (entropy: the minimum bits needed on average). about 30% of cells are empty at load 0.70 [repo]. the key fingerprint bits are random. the value bits are skewed, because a few taxa get most cells [guess]. bits per cell ≈ H(0.30) + 0.70 x (key bits + value entropy).
- worked example: H(0.30) = 0.88 bits [arith]. 103GB: 0.88 + 0.70 x (16 + 6 to 10) = 16.3-19.1 bits per 32-bit cell, a best-case ratio of **1.7-2.0x** [arith on a guessed value entropy of 6-10 bits]. 50MB: 0.88 + 0.70 x (26 + 1.5 to 3) = 20.1-21.2 bits, **1.5-1.6x** [arith]. a general compressor like zstd will land below these, since fields are bit-packed [guess].
- why only cold: warm, decompression costs cpu and saves nothing. cold, the load time is bytes / device speed. if orin's device really is 0.3 GB/s (A5 doubts it), 15 GB takes ~50 s, and 1.5-2x makes it ~25-33 s [arith]. compress in independent 64 MB frames, so S10's chunked parallel load becomes a parallel decompress.
- prior art: Centrifuger's whole design is lossless compression of the index, half the memory of a plain fm-index [external: S7]. kraken2 stores its table raw.

**3. gain per class.**
- warm, every class: 0 or slightly negative [guess].
- cold H2 orin: large if the device is slow, nothing if A5's doubt holds [UNCLEAR].
- cold H1 laptop nvme: small. at [guess] 2-3.5 GB/s, 15 GB takes 4-8 s raw.
- cold H3: depends on the device; an sd card or usb hdd gains most [guess].
- cold H4 raid: small [guess].
- a compressed file cannot be memory-mapped, so it competes with `-M` rather than adding to it.

**4. days.** test 0.1. build 3-4: a framed format, the builder step, the loader, and keeping `-M` on the raw file.

**5. risk.** a second db format and the disk space for both. the gain only shows on the first cold run after a reboot or eviction. null: ratio under ~1.3x, or a fast device.

**6. cheapest test that could kill it.** `zstd -3 -T0 -c hash.k2d | wc -c` on the 50MB and 8GB dbs, on luna or the laptop, a few minutes. kill if under 1.3x. and A5's `dd iflag=direct` on orin: kill for H2 if the device reads above ~1.5 GB/s.

**7. sources.** S7, S12 (cold i/o dominates kraken2 when the db is not cached: 9.4x on a sata ssd).

### ranking summary

| rank | idea | type | byte-identical | days | what it decides |
|---|---|---|---|---|---|
| 1 | B1 re-baseline vs RC1 | measure | n/a (measures it) | 0.5 | every "vs stock" number, novelty |
| 2 | B2 residual stages onto RC1, upstream | build | yes vs RC1 | 3-5 | the portable gain everyone gets |
| 3 | B3 cgroup small-ram emulation | measure | n/a | 0.5 | whether H3 needs anything built |
| 4 | B5 compressibility check | measure, then build | yes | 0.1, then 3-4 | whether cold slow storage has a lever |
| 5 | B4 exact chunked pass | build | yes by design | 6-10 | H3 and low-free-ram H1 runnable |

---

## re-proposal watch list for the relay

reject these fast, or demand the new angle:
- **parallel fastq parse**: upstream RC1 `fast_reader` [external: S1, S4].
- **huge pages, parallel load, batched prefetch**: S14, S10, S9/S16, and upstream PR #1033 [repo, external: S3].
- **prefetch distance on luna**: s20 null [repo]; upstream default 8 [external: S4]. only orin is open.
- **software k-mer cache, minimizer-locality hashing**: S6/S7 at 3.6% hit rate [repo]; kraken2 already skips repeats (A11).
- **flat hit-count array**: dead, under 0.8% [measured].
- **smaller or larger cells**: thesis 2. upstream now ships a 40-bit cell [external: S1]; thesis 2 must cite it.
- **split db for small ram**: upstream `k2` multi-db, sequential parts, not exact [external: S6].
- **`-M` + madvise flags**: already in the plan's "not now" list [repo: next_steps_plan]. the old `kraken2_opt_v1.patch` also set `MADV_HUGEPAGE + MADV_WILLNEED + MADV_RANDOM` in `mmap_file.cc` [repo: `dorado-kraken-research/CLAUDE.md`]; whether it was ever measured is [UNCLEAR], check `command_log.md`.
- **trie or dictionary db**: the 2026-10-21 brief predicts a loss and has a 2-day stage 0 [repo].
- **numa replication**: luna only [repo].

## claims to keep out of any agent's text

- "S9/S10/S13/S14 are new." prior public work: PR #1033, merged 2026-06-24 [external: S3].
- "S19 is 15x faster than kraken2." it is 15.4x faster than v2.17.1 in one cell; vs RC1 it is unmeasured.
- "byte-identical vs stock" without naming the version.
- "upstream shows prefetch helps arm more." its own numbers show the bundle helped arm less (1.32x vs 1.65x) [external: S3].
- "orin cold = 0.3 GB/s" as a measurement (A5).
- "~2G lookups per run" or "1 lookup per 3 bases" as a measurement (A7).
- comparator speeds without load time. Centrifuger's paper reports speed "after excluding index loading time" [external: S7], and loading is exactly where S10 and S14 win.
