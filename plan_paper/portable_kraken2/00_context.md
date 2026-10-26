# portable kraken2: shared ground truth for every agent (2026-10-26)

this file exists so all five debate agents start from the same facts. the debate's question is "how do we make kraken2 fast as a general program on any machine, not tuned to luna". read this whole file before anything else. it is a summary; the sources it points to are the real record.

---

## 1. what is already built (do not re-propose)

the final build is **S19** = stock kraken2 v2.17.1 + S8 + S9 + S10 + S12 + S13 + S14 + S15 + S16 + S17 + S18 + S19 [repo: `plan_paper/explanations/00_INDEX.md`].

| stage | what it does | measured effect on luna (32 threads, 1,872,777 reads) |
|---|---|---|
| S8 | all 16 input files as one stream, no per-file barrier | 50MB 15.6 to 11.1 s |
| S9 | batch of 16 prefetches before resolving lookups | 103GB ~87 to ~76 s |
| S10 | parallel `pread` table load, 64 MB chunks, `min(omp_get_max_threads(), 32)` threads | 103GB 90.5 to 34.5 s (with S8, S9) |
| S12 | exact reciprocal multiply instead of `%`, slot computed once | 50MB -5.5%, 8GB no change |
| S13 | `memchr` newline search in the fastq parser | parse 10.53 to 3.88 s; 8GB -12.8% |
| S14 | table `posix_memalign` 2 MB + `madvise(MADV_HUGEPAGE)` | 8GB -20%, 16GB -23%, 103GB 35 s to 13-20 s |
| S15 | run-length hit counting before the `unordered_map` | -1.6% to -2.2% |
| S16 | two prefetch batches in flight (software pipelining) | 103GB -10% |
| S17 | rolling reverse complement | 50MB -3.7%, 8GB -3% |
| S18 | removed a store-forwarding stall in the scanner ring buffer | 50MB -2%, 8GB -3% |
| S19 | portability guards (`__int128`, `MADV_HUGEPAGE` ifdefs) | none by design |

tried and dropped: S6/S7 the 4-way software k-mer cache (hit rate ~3.6%, bigger caches slower; ruled out three times), S11 first scanner rewrite (null, explained by S18), s20 prefetch batch `K2_B` 16 to 64 (within ±0.6%, null) [repo: talk track sections 3-4].

**planned but not run** (2026-10-21, `plan_paper/next_steps_plan_2026-10-21.md`): E1 `-M` memory-mapping vs S19, E2 stock vs S19 on orin, E3 `-march=native` / LTO / PGO builds, E4 load scaling warm and cold on three machines, E5 S19 thread sweep (parallel-parse diagnostic). you may build on these, but say so; they are not new ideas. the trie/dictionary brief (`plan_paper/research_brief_db_structure_trie_dictionary_2026-10-21.md`) predicted a trie loses on speed and proposed a 2-day stage 0 microbenchmark. also not run.

---

## 2. facts that constrain every idea

1. **the table stores a fingerprint, not the key.** each cell is 32 bits: low bits = taxon, high bits = part of the key's hash. 103GB: 16 key bits + 16 value bits. 50MB: 26 key bits + 6 value bits [repo: trie brief section 1]. so the keys cannot be listed out of `hash.k2d`. **any new table format needs a full db rebuild from the library genomes.**
2. **load factor ~0.70, linear probing.** the Makefile sets `-DLINEAR_PROBING` on line 4. double hashing exists in the source behind that flag [repo: next_steps_plan row 5].
3. **the golden rule is byte-identical output vs stock.** checked by sorting both outputs by read id and comparing bytes. any change that is lossy, or exact-instead-of-fingerprint, changes some answers and needs an accuracy check instead (count differing lines, score them against the 103GB db or a truth set).
4. **where the cpu goes now** (S19, 50MB db, 32 threads, perf) [measured: `perf_s19.data`]:

| function | share | what it is |
|---|---|---|
| `NextMinimizer` | 38.5% | the scanner, called once per base from another source file; prologue/epilogue ~9% of its samples |
| `ClassifySequence` | 25.1% | per-read loop: prefetch pipeline, counting, decision |
| `GetAt` | 12.5% | probing table cells |
| `PrefetchIndex` | 7.0% | hash to slot, issue prefetch |
| memmove | 3.1% | copying sequences |
| `AddHitlistString` | 2.1% | building output lines |
| `unordered_map` hit counts | < 0.8% | dead lever after S15 |

so lookup (`GetAt` + `PrefetchIndex`) is 19.5% of cpu on 50MB, and a perfect table could give at most 1 / (1 - 0.195) = 1.24x there [arith]. there is no profile that separates lookup on the big dbs.

5. **the loader ignores `--threads`.** `classify.cc:260` loads the table before `classify.cc:273` calls `omp_set_num_threads`, so S10 always runs `min(machine default, 32)` loader threads [measured on luna's tree]. on a 4-core laptop that would be 4 (or 8 with SMT) threads; on orin 12.
6. **exit tax.** freeing the 111 GB private copy of the table at exit costs 3.9-11.4 s on 103GB for stock and s10 [measured]. S19 with huge pages probably shrinks it, unmeasured.
7. **the serial parse floor.** fastq parsing runs inside `#pragma omp critical(seqread)` (`seqreader.h:107-126`, `classify.cc:522`). on the 12.5 GB input it takes 3.88 s on one thread after S13 [measured]. it overlaps with classification, so it is a wall only when cpu-time / threads drops below it [repo: next_steps_plan 4a].
8. **`-M` exists already** in kraken2 (`--memory-mapping`): `mmap(MAP_PRIVATE)`, no `MAP_POPULATE`, no copy. file-backed pages are 4 KB on ext4 (no huge pages for file mappings, [guess] for kernel 6.8). correctness on S19 not yet checked [repo].
9. **build traps.** `install_kraken2.sh` has no `make clean`. overriding `CXXFLAGS` on the make command line drops `-DLINEAR_PROBING` and silently breaks output [measured].
10. **one data point.** every speed number in this repo is from luna (or a luna-pinned subset), warm page cache. luna is never "a typical machine".

---

## 3. the sweep and the small-core test (the only scaling data)

103GB, 1,872,777 reads, `--output /dev/null`, one run per point [measured]:

| threads | S0 wall | S0 load | S0 classify | S0 exit | s10 wall | s10 load | s10 classify | s10 exit |
|---|---|---|---|---|---|---|---|---|
| 1 | 1,046.04 | 56.23 | 981.73 | 8.09 | 685.43 | 6.37 | 672.04 | 7.03 |
| 8 | 172.88 | 58.35 | 107.57 | 6.96 | 81.28 | 6.51 | 66.67 | 8.10 |
| 32 | 91.22 | 58.06 | 29.16 | 4.00 | 26.40 | 6.50 | 15.38 | 4.52 |
| 64 | 82.57 | 58.19 | 20.38 | 4.01 | 22.74 | 6.44 | 11.75 | 4.55 |
| 192 | 85.28 | 58.05 | 23.30 | 3.93 | 24.32 | 6.30 | 13.32 | 4.69 |

(seconds; full table with 2, 4, 16, 96, 128 threads in `next_steps_plan_2026-10-21.md` section 6.) at 1 thread, s10 classifies 1.46x faster than stock: prefetch hiding ram latency inside one core.

small-core test, stock vs S15, luna pinned with `taskset -c 0-(N-1)` [measured]. caveat: this took half the cores from each socket, so it is a two-socket N-core box, not a laptop:

| cores | 50MB | 8GB | 16GB |
|---|---|---|---|
| 16 | 1.41x | 1.43x | 1.81x |
| 8 | 1.35x | 1.22x | 1.50x |
| 4 | 1.33x | 1.13x | 1.36x |

the full S19 vs stock 16-cell matrix is in `talk_track_sir_2026-10-21.md` section 5: 1.9x (50MB) to 4.8x (103GB) at 1,872,777 reads, 9.8x-15.4x on the big dbs at 10 and 1,000 reads.

---

## 4. the hardware classes the debate must cover

every idea gets a gain estimate for each class. these are classes, not just our three machines.

| class | example we know | what is special | measured kraken2 data? |
|---|---|---|---|
| **H1 laptop** | ck's lenovo: ryzen 7 5800h, 8c/16t, 16 MB L3, **1 dimm** ddr4-3200 (25.6 GB/s peak), nvme | one memory channel; only 2.9-3.8 GB ram was free when checked; windows, so kraken2 needs linux to run | none. a load microbenchmark smoke test only (`laptop_loadscale.ps1`) |
| **H2 arm / jetson** | orin agx 64GB: 12x cortex-a78ae, 4 MB system cache, 64 GB lpddr5 shared with the gpu, 57 GB emmc with ~8.5 GB free (june) | arm isa (neon, no avx), small cache, slow emmc (~0.25-0.33 GB/s [external, unverified]), kraken2 v2.1.3 installed | stock v2.1.3 timings only (`RESULTS.md` 1.4) |
| **H3 small-ram box** | none of ours; a generic 8 GB ram machine | the 8GB db does not fit twice (page cache + private copy), 16GB and 103GB do not fit at all | none |
| **H4 big server** | luna: 2x xeon platinum 8468, 96c/192t, 503 GB, **4 of 8 channels populated per socket**, 105 MB L3 per socket, numa_balancing=1, raid ssd, read_ahead_kb=1024 | numa, many cores, the serial parse becomes the wall at high thread counts | all of it |
| **storage axis** | warm (file in page cache) vs cold: emmc, sata ssd, nvme, hdd, network fs | every luna number is warm | cold never measured |

dbs: 50MB (`sample_targeted`, ESKAPE), 8GB and 16GB (capped standard builds), 103GB (pluspf, 111 GB on disk, ~27.75 billion cells). input: 16 fastq files, 1,872,777 nanopore reads, 12.5 GB, ~3,200 bases per read.

---

## 5. prior art the skeptic will check (and everyone should know)

[repo: memory `project_comparator_tools_aug2026`, unverified since 2026-08-06]
- **Centrifuger** (Genome Biology 2024): FM-index with run-block compressed BWT, ~2x lower memory than Centrifuge.
- **Metabuli** (Nat. Methods 2024): dna + amino-acid metamers, RAM-capped, runs in 8 GB.
- **kache-hash** (bioRxiv 2026): cache-conscious k-mer hash table, minimizer-based bucket placement for locality.
- **MegIS** (ISCA 2024): kraken2-class lookup as the bottleneck, solved at the storage / in-storage-processing tier.
- **SSHash**: exact k-mer dictionary over super-k-mer strings, per-k-mer value is only a weight [repo: trie brief].
- MetaCache-GPU, GPMeta: gpu hash classifiers.

---

## 6. rules (all agents, every round)

**scope.** research and writing only. no ssh, no remote builds, no local benchmarks, no git commands (the relay commits). write only your own files in `plan_paper/portable_kraken2/`.

**literature.** before every R1, read at least **3 new** real sources for your area (arxiv, pmc, biorxiv, vldb, usenix, acm, kernel docs, gcc/llvm docs, vendor manuals). "new" means not cited in any earlier cycle file. fetch them with WebFetch or WebSearch. cite each as: url, plus the exact claim you use (quote or close paraphrase), plus which idea it supports. never cite from memory. if a fetch fails, say so and do not use the claim.

**evidence tags** on every number and claim: **[repo]** a file here (give the path), **[measured]** a number from a log or profile in the repo, **[arith]** arithmetic from stated inputs (show it), **[guess]** your estimate, **[external]** a fetched source (give the url), **[UNCLEAR]** unknown. never invent a number. unknown stays [UNCLEAR].

**writing style** (ck's, mandatory): lowercase, no em-dashes, short sentences, no filler. define every technical term in brackets on first use. state the wrong intuition before the right answer. give a worked number example for each mechanism. luna numbers are one data point: never write "this gives X% on any machine".

**idea format** (R1): for each idea, give
1. name, and whether it is byte-identical or needs an accuracy check
2. mechanism from zero (wrong intuition first, then the real mechanism, then a worked number example)
3. gain per class: H1 laptop, H2 arm/jetson, H3 8 GB box, H4 big server, and cold vs warm disk, each tagged
4. days of work for one person
5. risk (correctness, portability, what could make it a null)
6. cheapest test that could kill it
7. sources

**files.** cycle N, round R, agent X writes `cycle_N_rR_X.md`. agent slugs: `a1_dsa`, `a2_storage`, `a3_cpu`, `a4_hw`, `a5_skeptic`. the relay writes `cycle_N_conclusion.md` and `FINAL.md`.
