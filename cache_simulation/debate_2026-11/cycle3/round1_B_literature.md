# cycle 3, round 1, agent B (literature): what faster kraken2 work exists for the scanner, input and db load

method: read cycle2 round3_A_scanner.md first (its numbers are reused, not re-derived), then 6 web searches. tags: [snippet] = only a search-result summary was read, [unverified] = not opened, [guess] = my reasoning. no full paper was opened and there was no luna access in this round, so every number below is from a snippet or is my arithmetic.

## 1. fast minimizer extraction

### 1a. SimdMinimizers (the main prior art)
- Groot Koerkamp R, Martayan I. "SimdMinimizers: Computing random minimizers, fast." SEA 2025 (LIPIcs vol 338, article 20). https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SEA.2025.20 ; code https://github.com/rust-seq/simd-minimizers (crate simd-minimizers 2.3.x). [snippet]
- numbers [snippet]: 3.2 Gbp human genome, all forward minimizers in 5.2 s, canonical in 6.7 s, one thread (the preprint gave 4.1 and 6.0 s). canonical is under 50 percent slower than forward. 3.4x (w=19) to 6.8x (w=5) over the fastest non-SIMD method; over 15x faster than the minimizer-iter crate. needs AVX2 or NEON.
- mechanism [snippet]: split each sequence into 8 chunks, one per lane; the rolling hash and the sliding window min run lane-parallel and branch-free, then the positions are compacted and de-duplicated.
- per base: 5.2 s / 3.2e9 = 1.6 ns forward, 2.1 ns canonical. our S19 scanner is estimated at up to 15 ns per base (round3_A, an upper bound), so the literature says several-fold headroom exists in principle. caveat: their output is minimizer positions under a random hash order, not a kraken2 value (spaced-seed mask, toggle xor, l=31 canonical, 62-bit). it is the same kind of order (min of a function of the l-mer), so the SIMD structure ports, but the exact bits must be rebuilt.
- bit-identical risk: medium. the value is a pure function of the l-mer, so lanes compute exactly what scalar computes. risk lives in chunk joins (k-1 base overlap) and reads with N. fix: scalar fallback for any read with a non-ACGT byte.
- expected gain: scanner 3 to 5x, end to end 17 to 29 percent at 8GB, 10 to 17 percent at 103GB [guess: share x (1 - 1/speedup), as in round3_A].

### 1b. the algorithmic cores
- sliding-window min: monotone deque (what stock kraken2 and S19 use; Wood, Lu, Langmead, "Improved metagenomic analysis with Kraken 2", Genome Biology 2019, https://link.springer.com/doi/10.1186/s13059-019-1891-0 [snippet, architecture only, no scanner timings]); van Herk / Gil-Werman (about 3 compares per element, block prefix and suffix minima, branch free); two-stacks (amortized O(1) but branchy). [unverified, textbook]. for w=5 the fixed 5-input min tree (4 vpminuq) is the natural fit.
- ntHash / ntHash2 (Mohamadi et al, Bioinformatics 2016; Kazemi et al 2022) [unverified]: rolling hash for large k. kraken2 orders l-mers by value xor toggle, not by a hash, so ntHash would change the output. skip.
- minimizer-iter crate: scalar Rust baseline in the paper, beaten 15x [snippet]. not useful.

### 1c. kraken2-compatible reimplementations
- Kun-peng / kr2r (Rust; bioRxiv 2024-12-19 https://www.biorxiv.org/content/10.1101/2024.12.19.629356.full.pdf ; later Briefings in Bioinformatics, doi 10.1093/BIB/BBAG119) [snippet]. claims up to 4.73x faster than Kraken2 and up to 24x less memory on CAMI II; full-speed mode under half of kraken2 time. mechanism is not a faster scanner: it splits the db into chunks, sorts minimizer records, and processes one chunk at a time so lookups are sequential. new db format, so not bit-identical to kraken2 output paths. per-thread throughput was not found. lesson: the published multi-x win is on the lookup/memory side, which matches our 103GB profile, but it is out of scope for an identical-output goal. use as related work.
- kraken2_rs (Rust crate 0.6.x): its own description says accuracy is lower than kraken2 [snippet]. no usable numbers.
- K2Rmini (Oxford, "Accelerating k-mer-based sequence filtering", https://www.expmedndm.ox.ac.uk/publications/publication_modal/2441155) [snippet only]: minimizer sketching plus SIMD in Rust for streaming filtering. closest published SIMD-on-kraken-like-scanning work; not opened. fetch next round.
- Centrifuger, Ganon2, taxor, Metabuli, KrakenUniq: no per-thread scanner throughput found in these searches; not searched in depth. i found no source reporting a faster kraken2-identical scanner than ours, so a result here would be new.
- KMC3 (Kokot, Dlugosz, Deorowicz, Bioinformatics 2017) [unverified]: minimizer signatures with 2-bit packing; the idea of a per-byte table that advances 4 bases per step is used in idea 3 below.

## 2. FASTQ input

- needletail benchmark [snippet]: counting all bases of a 2.1 GB HiSeq FASTQ in 1.1 s vs 2.6 s for readfq (kseq-like), about 1.9 GB/s on one thread including the counting, 2017 hardware. https://github.com/jguhlin/needletail
- paraseq (Rust, record-set parallel parsing) claims parity with needletail on one thread and better scaling with threads [snippet, plot only, no numbers]. fastp (Chen et al, Bioinformatics 2018, https://pubmed.ncbi.nlm.nih.gov/30423086/) is 2 to 5x faster than Trimmomatic or Cutadapt [snippet]; it is a preprocessor, not a parser, no GB/s given.
- our input [guess]: 1.87M reads, 6.04 Gbp, about 12 GB of FASTQ text. at about 1.9 GB/s that is about 6 s if one thread parses everything, close to the 7.5 s wall at 8GB. kraken2 reads batches in one thread under a lock and emits output in batch order, so a serial reader could cap throughput at T=32. nobody has measured it here. cheap check: time the reader alone (stub classifier) or per-thread perf. [unmeasured]
- io_uring or readahead: no benchmark found for this workload; with a warm page cache there is nothing to gain. skip unless the reader thread shows at 100 percent.
- ordered parallel output: no literature beyond fastp's ordered writer; likely under 2 percent.

## 3. database loading (kernel about 22 percent at 103GB)

sources: kernel THP doc https://www.kernel.org/doc/html/v5.15/admin-guide/mm/transhuge.html [snippet]; Choi et al, "Efficient Memory Mapped File I/O for In-Memory File Systems", HotStorage 2017, https://lrita.github.io/images/posts/filesystem/hotstorage17-paper-choi.pdf [snippet]; notes in the fcoreutils Rust crate io.rs on MADV_HUGEPAGE before prefault (secondary, no benchmark) [snippet]; a pmem mailing-list thread (8 threads, 4K pages: read 15 GB/s vs mmap 10 GB/s; 16K pages: 20 vs 24 GB/s) [snippet]. no source has 100 GB numbers.

mechanism of the copy load [guess, from kernel behavior]: kraken2 mallocs about 111 GB and reads the file into it. each destination page is first touched inside copy_to_user, which faults, zeroes the page (4 KB, or 2 MB if THP is on), then copies from page cache. every byte is written twice and read once, plus page-table and fault overhead. the 14.2 + 10.6 percent kernel frames at 103GB are consistent with clear_page, copy and fault handling. the source side is warm page cache, so no disk cost.

ideas:
- (a) with -M: madvise(MADV_HUGEPAGE) first, then MAP_POPULATE or MADV_POPULATE_READ. the crate notes say hint-first gives about 50 faults instead of 25,600 per 100 MB [snippet, secondary]. file-backed THP needs CONFIG_READ_ONLY_THP_FOR_FS with khugepaged, or large-folio filesystems on recent kernels [unverified on Luna]. Choi et al found populate 1.02 s vs 1.42 s default mmap vs 1.06 s read on their test [snippet].
- (b) parallel populate: a few helper threads populate slices while classification starts. load of 103 GB at 32 GB/s is about 3.3 s, small vs wall; the 22 percent is a cpu-share across 32 threads and may not be wall. need a wall breakdown first [guess].
- (c) MAP_HUGETLB 1 GB destination: removes zero/fault variance but needs reserved hugepages (root), not portable. skip for the paper.
- (d) userfaultfd lazy load: reads touch most of the table anyway [unverified]; rejected.
- bit-identical risk: none, db bytes unchanged.
- expected gain: 0 to 8 percent at 103GB wall, about 0 at 8GB [guess].

## 4. prefetch only when needed / dedup before hashing

dedup already shipped (1.6 to 4.4 percent, byte-identical, cycle2 round 5). literature agrees: kraken2 only queries distinct minimizers [snippet, Genome Biology 2019], and SimdMinimizers de-duplicates equal consecutive minimizers in its output compaction [snippet]. moving dedup into the scan loop (round3_A section 6) also skips murmur and the ambiguity check on repeats: 1 to 3 percent extra [guess].

## 5. top 6 ideas, ranked by value per day (all keep identical output)

1. bulk scan plus branchless 5-slot window min, scalar (round3_A changes 1+2). one tight loop per read, state in registers, dna templated, fixed min tree instead of the deque; replaces the per-call NextMinimizer. gain 12 to 17 percent at 8GB, 7 to 10 at 103GB [guess]. 2 to 3 days. risk low (stream harness). first run perf branch-misses per base; under 0.2 means the branch story is wrong.
2. AVX-512 8-lane chunked scan with scalar fallback for N reads. our values are 62-bit, so 64-bit lanes are needed: AVX-512 gives 8 lanes and native vpminuq, AVX2 only 4 and a sign-flip trick. SimdMinimizers runs 8 chunks on AVX2 with narrower hash values, so the lane count is not directly comparable [guess]. gain scanner 3 to 5x, end to end 17 to 29 percent at 8GB, 10 to 17 at 103GB [guess ceiling from 1.6 to 2.1 ns/base]. 5 to 7 days. risk medium (chunk joins; AVX-512 frequency drop on Sapphire Rapids is mild [unverified]).
3. 4-bases-per-step table update (KMC3-style byte table) on 2-bit packed input: advance lmer and rc_lmer a whole byte at a time. gain 5 to 10 percent [guess]. 3 days. risk low. composes with idea 1.
4. in-loop dedup (section 4). 1 to 3 percent, 0.5 day, risk none.
5. -M with MADV_HUGEPAGE-then-populate, optional parallel populate (section 3). 0 to 8 percent at 103GB, 1 day, risk none. first measure db-load seconds vs classify seconds at 103GB (1-minute check).
6. reader-thread check, then paraseq-style parallel record-set parsing with ordered output only if the reader is serial-bound at T=32. 0 to 5 percent, measure first. same bucket: LTO/-march (E3 s21a/s21b, 2 hours), which inlines NextMinimizer into fill and sets the baseline for ideas 1 to 3.

not ranked: ntHash (changes ordering, breaks identity), Kun-peng style sorted chunk lookup (new db format, only published route to multi-x, related work), userfaultfd, io_uring.

## 6. gaps and next fetches
- open the SimdMinimizers full text (https://drops.dagstuhl.de/storage/00lipics/lipics-vol338-sea2025/html/LIPIcs.SEA.2025.20/LIPIcs.SEA.2025.20.html) for the canonical lane layout and the compaction step; open K2Rmini. both unverified here.
- no published kraken2-identical scanner speedup found.
- all percentages are share x speedup guesses; the cycle2 lesson (perf share is not wall share) applies, so run round3_A test A (double-scan slope) before building.

## summary
1. best prior art is SimdMinimizers (SEA 2025): about 1.6 ns/base forward, 2.1 canonical, one thread, 3.4 to 6.8x over scalar and best at w=5, our window; our scanner is up to 15 ns/base [guess].
2. rank 1 is a scalar bulk scan with a branchless 5-slot min (2 to 3 days, 12 to 17 percent at 8GB); rank 2 is an AVX-512 8-lane port with scalar fallback (5 to 7 days, up to 29 percent).
3. no published kraken2-identical faster scanner exists; Kun-peng (up to 4.73x) wins by changing the db format, so it is related work, not a plan.
4. fastq parsing is about 1.9 GB/s per thread (needletail benchmark), so a serial reader could matter at T=32; unmeasured, check before building.
5. db load: set MADV_HUGEPAGE before populating the -M mapping; sources are secondary and none have 100 GB numbers, so expect 0 to 8 percent at 103GB only.
6. every percentage is a guess from share x speedup; gate on perf branch-misses per base and the double-scan slope test first.
