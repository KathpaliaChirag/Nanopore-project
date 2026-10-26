# cycle 1, round 2: a5_skeptic (2026-10-26)

role: the skeptic. this round i counter the other four agents' top picks, re-derive their headline arithmetic, revise my own R1, rank by M-id, and give a prior-art and evidence verdict for every M-id. tags follow `00_context.md` section 6.

---

## sources read this round

new fetches (none were cited in cycle 1 R1 files):

| # | source | exact claim used | supports |
|---|---|---|---|
| R1 | kraken2 release 2.17.2, https://github.com/DerrickWood/kraken2/releases/tag/2.17.2 | "Multiple performance improvements to classify by @tfenne in #1033"; "We have another release pending that will see significant speed ups to classification."; shown date "23 Sep" | section 2, M1, M2, M3 |
| R2 | x86 reference, PREFETCHh, https://www.felixcloutier.com/x86/prefetchh | the instruction "is merely a hint and does not affect program behavior". the page does not say what happens on a non-present page, so "a prefetch never pages a file page in" is my inference from "does not affect program behavior" [external + guess] | counters to M9 and M11 |
| R3 | rapidgzip, Knespel and Brunst, HPDC 2023, https://arxiv.org/html/2308.08955 | single-thread "decompression with gzip with 157 MB" on base64 data; machine: two AMD EPYC 7702, 2 GHz base. the fastq section gives rapidgzip's 4.9 GB/s peak, but the single-thread gzip number for fastq is only in a figure the fetch could not read | counter to M5 |
| R4 | ONT MinKNOW output structure, https://software-docs.nanoporetech.com/output-specifications/latest/minknow/output_structure/ | the example tree under `fastq_pass/` names "PAA12345_pass_dca6f6d1_d11637af_0.fastq.gz". the page does not say whether gzip is the default | counter to M5 |

failed or empty: openbenchmarking jetson storage result (https://openbenchmarking.org/result/2011176-FI-JETSON39290) returned 403, so no claim from it. a search for an orin emmc random 4 KB benchmark found none.

repo files read this round: the relay brief, all four other R1 files, `dorado-kraken-research/docs/reports/kraken2_get_optimizations_v2.md` (S3), `dorado-kraken-research/AccuracyDrift/README.md` (db build commands), `dorado-kraken-research/WSL2/kraken2/gprof_report.txt` (again, all of the top 30 rows).

---

## 0. two findings that move several M-ids at once

### 0a. v2.17.2 is a stable release and already has PR #1033

my R1 said the S-chain's prior art shipped in v2.18.0-RC1 on 2026-10-20. it shipped earlier. the stable release 2.17.2 (shown "23 Sep") lists "Multiple performance improvements to classify by @tfenne in #1033" [external: R1]. that is one day before our S6-S15 report (2026-09-24) [repo]. so the baseline that matters most is **v2.17.2**, a stable release, not only the RC. RC1 adds the out-of-lock parser and the output-changing fixes [external: R1 cycle-1 S1].

### 0b. lookups per base is not one number: it is about (1/3) x f_db

this settles relay conflict 1, and it retracts my own R1 A7.

**the wrong intuition (mine, in R1):** "the old gprof run made 9.87M `Get` calls for 354M scanner calls, so a run may do 1 lookup per 36 bases, not per 3."

**what the same file says.** read two more rows of `gprof_report.txt` [repo]:
- `unordered_map<unsigned long, unsigned long>::operator[]` (that is `hit_counts[taxon]++`): 10,284,204 calls
- `HyperLogLogPlusMinus::insert` (called by `add_kmer`): 3,220,914 calls

in v2.17.1-style code, `hit_counts[taxon]++` runs for every k-mer position that has a taxon, repeats included. `add_kmer` runs only for a new minimizer that hits, when a report is asked for [external: cycle-1 S5]. so 10,284,204 / 3,220,914 = **3.19 positions per distinct hit minimizer** [arith]. that is the minimizer run length. for random minimizers with w = 5 the expected run is (w + 1) / 2 = 3 [arith on the density formula a1 sourced]. so the **per-position density is about 1/3**, as a1 and a3 assumed.

**so where does 1/36 come from?** two candidates, and the file cannot tell them apart:
1. a gprof undercount of `Get` (partial devirtualization or inlining, or racy call counts under threads) [guess]
2. a **capped** db. kraken2 skips the lookup when `MurmurHash3(minimizer) < minimum_acceptable_hash_value` [external: a1 src 2]. a db built with `--max-db-size` keeps only a fraction f of hash space. then lookups per base = (1/3) x f. 9.87M / (354M / 3.19) gives f ≈ 0.09 for that db [arith]

**why this matters now: our 8GB and 16GB dbs are capped builds** [repo: `00_context.md` section 4, "capped standard builds"]. three measured facts fit a small f there:
- at 1 thread, 8GB runs faster per read than 50MB on both machines: luna 16.78 s vs 19.73 s, orin 21.19 s vs 47.53 s [repo: `RESULTS.md` 2.3, via a4]. on luna the 50MB table fits the 105 MB L3 and the 8GB table does not. with equal lookup counts, 8GB should be the slower one
- S9's batched prefetch did nothing on 8GB and 16GB, and S16 tied on 8GB, while S16 gave -10% on 103GB [repo: talk track section 4]
- orin's 8GB run has IPC 2.24 vs 0.93-1.08 for the ESKAPE dbs [repo: `RESULTS.md` 1.4]. fewer ram waits per base fits fewer lookups
- against it: one repo note says standard_8 has `minimum_acceptable_hash_value == 0` [repo: `kraken2_get_optimizations_v2.md` S3]. the note shows no measurement behind it

so: per-position density ≈ 1/3 [arith, supported]. lookups per base = f_db / 3, with f_db [UNCLEAR] for 8GB and 16GB, maybe 0.1-0.3 [guess: cap size / uncapped standard size]. 50MB is probably uncapped [guess]; 103GB is [UNCLEAR].

**every estimate that multiplies "bases / 3" on 8GB or 16GB may be off by up to 1/f**: a2's 925 s thrash, a1's 3,300-13,000 s, a4's 4,500 s and the E1 touched fractions. the test is 5 minutes: read the value from each db's `opts.k2d`, as a1 already proposed. i give it its own id, **M22** (measure).

---

## 1. counters to the other four agents' top 3

each block: what breaks, which class it hurts, what is cheaper, and the headline arithmetic re-derived.

### a1_dsa

**a1 #1 = M3 (hash and prefetch only changed minimizers).**
- arithmetic re-derived, holds: 3,166 positions, 1,055 lookups at d = 1/3, 2,111 saved per read; 6.036e9 x 2/3 = 4.0e9 calls; 7.0% x 2/3 = 4.7% [arith]. 0b now supports d ≈ 1/3 per position.
- what breaks: nothing in correctness. the 4.7% assumes `PrefetchIndex`'s 7% is instruction cost, not waiting [UNCLEAR, a1 and a3 both say so].
- prior art: upstream has had it since 2.17.2. PR #1033's classify change resolves "distinct minimizers in a batch" [external: cycle-1 S3, R1]. so if M2 (rebase onto upstream) happens, M3 costs 0 days.
- a new angle from 0b: on a capped db, S16's `fill()` prefetches the slot of every position, including minimizers the resolve loop then skips [repo: `s16_patch.py` lines 48-50, via a1]. if f ≈ 0.1-0.3, most of those prefetches fetch lines nobody reads [arith on guessed f]. they hold miss buffers (the slots that track outstanding misses). that may cost more on a one-channel laptop than the 4.7% instruction estimate [guess]. it also may explain why S9 did nothing on 8GB.
- cheaper: M22 first (5 min), then M2.

**a1 #2 = M8 (line-aware probe).**
- arithmetic re-derived, holds: (2.17 - 1) / 16 = 0.073 and (6.06 - 1) / 16 = 0.316 line crossings [arith]; 0.07 x 0.5 + 0.32 x 0.5 = 0.195; 62.5M x 0.195 x 100 ns = 1.22 s per thread [arith].
- what is weak:
  - part a is not new. the trie brief already listed it: "prefetching the next line when `idx % 16 > 10`" [repo: `research_brief_db_structure_trie_dictionary_2026-10-21.md` section 8]
  - the miss fraction 0.5 is a guess. a1's free awk over output column 5 settles it
  - "none hidden" is a ceiling. the probe's next cell address is known before the first line arrives, so the core can issue that load early when the loop branch predicts "keep probing" [guess]. intel's spatial prefetcher may already bring the paired line [UNCLEAR, no source fetched by anyone]
  - 62.5M lookups per thread assumes 103GB is uncapped [UNCLEAR, 0b]
- which class: part a adds 37.5% line fetches. a1's 48 GB extra over the full input [arith] is small even on one channel. no class is hurt.
- cheaper: the free `perf annotate` on `perf_s14_103.data` (a1's own kill test), then part a alone (0.25 day). part b only if part a shows the crossings cost something.

**a1 #3 = M11 (sorted block lookup, out of core).** shared with a2 #3 and my R1 B4.
- arithmetic re-derived, holds as arithmetic: 2.0e9 x 2/3 = 1.33e9 faults; / 100K-400K iops = 3,300-13,000 s [arith].
- what breaks: it uses 2.0e9 lookups on the 16GB db, which is bases / 3 with f = 1. if f_16GB ≈ 0.2 [guess], the thrash is 5x smaller (0b).
- prior art: KrakenUniq's `--preload-size` already does exact chunked classification, "identical to running in the default mode", 48 h mapped vs 47 min at 8 GB chunks [external: cycle-1 S13]. what is new is only "on kraken2's own table".
- cheaper: M22, then M12. and today, with no code: upstream's `k2` multi-db path classifies split dbs one part at a time [external: cycle-1 S6]. not exact, but it runs in low ram.

### a2_storage

**a2 #1 = M9 (one loader that picks map / copy / direct read).**
- arithmetic re-derived, holds: orin cold 8GB copy 7.6 / 0.294 = 25.9 s; map with `MADV_RANDOM` 10.7K x 4 KB = 44 MB; default readahead 10.7K x 128 KB = 1.37 GB = 4.7 s at 0.294 GB/s [arith].
- what breaks:
  - the warm thresholds come from E1, which has not run
  - **faults are serial on few-read runs.** 10 reads sit in one input block, so one thread does all ~10.7K lookups [arith: a3's ~480 reads per 3 MB block]. a software prefetch "is merely a hint and does not affect program behavior" [external: R2], so S9/S16 cannot pull a non-resident file page in ahead of time [guess from R2]. each major fault blocks that one thread. the device sees queue depth 1. the map cost is 10.7K x (queue-depth-1 latency), and that latency is unmeasured on every machine we have
  - on a capped db, f < 1 means fewer lookups, so the map wins by more (0b)
- which class: none hurt if a2's guard holds ("never pick map above the measured crossover").
- prior art: KrakenUniq leaves mmap vs preload to the user [external: cycle-1 S13]. MegIS found load-first slightly better when most of the db is touched [external: cycle-1 S12]. i found no tool that picks automatically [UNCLEAR: not searched exhaustively]. so the planner is new.
- cheaper: E1 and one cold pair. M9 is the same idea as a4 #1, which adds the device model. merge them.

**a2 #2 = M10 (`MADV_COLLAPSE`, huge file mappings).**
- arithmetic re-derived, holds: 111e9 / 4096 = 27.1M entries x 8 B = 217 MB; 52.9K x 8 B = 423 KB [arith]. the 13-16 s "bad session" result is [arith + guess].
- what is weak: the claim that luna's 12.3-21.6 s spread is huge-page coverage is a hypothesis. the talk track's "a run right after a small-page binary gave 20.2 s" fits it [repo], but nothing proves it. part B needs `CONFIG_READ_ONLY_THP_FOR_FS` [UNCLEAR on luna]. orin's 5.10 kernel has neither path [repo].
- which class: H4, and H1/H3 only on new kernels. on a shared box, collapse triggers reclaim of other users' cache (a2 says so).
- cheaper: a2's free test, `thp_gb` vs wall over 6 runs, already logged by `grid.sh`.

**a2 #3 = M11.** see a1 #3. one more check on a2's own numbers:
- thrash re-derived, holds: 355M / 3 = 118M; x 0.625 = 74M; / 80K iops = 925 s [arith]. but it sits on f = 1 (0b) and on the guess of 6 GB of usable page cache
- the partitioned 15-25 s re-derived: 16 GB / 2.09 GB/s = 7.7 s of reading [arith], where 2.09 GB/s is a 256 MB, 2-thread, 1-rep smoke test [repo]. classify on luna's 16GB at 104,918 reads is roughly 0.6 s at 32 threads [arith: 1.39 s minus the 0.77 s 10-read cell, repo matrix], so a few seconds on 8 cores, a bit more with the scanner run twice [guess]. so 12-25 s is plausible [arith on guesses]
- the shape is supported by a real measurement on another tool: KrakenUniq mapped 48 h vs 8 GB chunks 47 min, about 61x [external: cycle-1 S13]. a2's 40-60x is the same order. different tool and hardware, so this is support, not proof

### a3_cpu

**a3 #1 = M3.** see a1 #1. a3's numbers re-derive: 3,189 k-mers, 1,063 lookups, 2,126 wasted; 2.7 ns per call x 2/3 = 1.8 ns of 38.8 ns = 4.7% [arith].

**a3 #2 = M4 (branch-free min-of-5 window).**
- arithmetic re-derived, holds: 234 core-s / 6.036e9 = 38.8 ns per base; x 0.385 = 14.9 ns; 45-57 cycles at 3.0-3.8 GHz [arith].
- what is weak:
  - it mixes a 32-thread perf share with an 8-core core-second total (a3 says so). at 32 threads the all-core clock is lower [UNCLEAR], so 45 cycles may be nearer 30-40
  - "4 instructions per cycle, so 6-10 cycles" is a guess. the only measured IPC we have for kraken2 is 1.47-1.65, whole program, stock, 8GB [repo: `dorado-kraken-research/README.md` 8j]
  - branch misses are not measured. S11 shows a scanner rewrite can measure nothing [repo]
- which class: none hurt. byte identity rests on the stream-equivalence test.
- prior art: SimdMinimizers' deterministic sliding window [external: a3 S1]. upstream still pops in a loop [external: cycle-1 S4].
- cheaper: a3's own 15-minute `perf stat -e branch-misses` kill test, before any code.

**a3 #3 = M5 (faster gz decompression).**
- arithmetic re-derived: 12.5 / 0.158 = 79 s and 12.5 / 0.170 = 74 s [arith]. the arithmetic holds; the input to it does not.
- what breaks:
  - **our input is not gz.** the 16 files and `reads_hac.fastq` are plain fastq from dorado [repo]. for ck's pipeline the gain is 0
  - the 157 MB/s is GNU gzip on base64 data on a 2 GHz EPYC 7702 [external: R3]. the paper's single-thread gzip rate for fastq sits only in a figure the fetch could not read [external: R3]. fastq may inflate faster or slower per output byte [UNCLEAR]
  - for kraken2 users it is real. ONT's own MinKNOW output example names its files `.fastq.gz` [external: R4], though the page does not say gzip is the default
- which class: H2 gets a side benefit. a gz copy of the 12.5 GB input may fit orin's 8.5 GB free [repo] and open E2's 1,872,777-read column [guess on the gz size].
- prior art: rapidgzip, pigz and igzip exist [external: a3 S8]. kraken2's wrapper uses one `gzip -dc` per file [external: a3 S4].
- cheaper: a3's 10-minute test on luna.

### a4_hw

**a4 #1 = M9, cold-start planner with a device model.** this is the ~30x claim.
- arithmetic re-derived, holds as arithmetic: copy 7.6 / 0.25 = 30.4 s; map 10.7K / 11K = 0.97 s; crossover D = 30.4 x 11K = 334K pages, P = 1.86M, L = -P ln(1 - D/P) = 368K lookups, about 344 reads [arith].
- what breaks:
  - **11,000 iops is an emmc 5.1 class row from wikipedia**, from a table the fetch tool flattened (a4 says so) [external: a4 src 3]. it was never measured on our board, and its queue depth is not stated
  - **the 10-read run is queue depth 1** (see the a2 #1 counter). so the right number is orin's 4 KB random read latency at queue depth 1 [UNCLEAR]. if it is 0.2-0.5 ms [guess], the map takes 2.1-5.4 s, and the win is 6-15x, not 31x [arith on the guess]
  - the copy side rests on 0.25 GB/s, also unmeasured on our board
  - pulling the other way: if f_8GB ≈ 0.1-0.3 (0b), 10 reads do only 1.1K-3.2K lookups [arith], and the map wins by more
  - two unmeasured numbers pull in opposite directions. so "~30x" is not a planning number. the direction (map beats copy for few reads on cold flash) holds
- the same issue hits a4's H3 line: "680M random reads, ~4,500 s" uses 2.0e9 lookups on the capped 8GB db with f = 1 [arith], so it may be several times too high (0b).
- cheaper: a4's own 10-minute cold test on orin (evict, copy; evict, `-M`; evict, `MADV_RANDOM`). add one `dd iflag=direct` for the sequential rate and a short loop of single 4 KB direct reads at random offsets for the queue-depth-1 latency.

**a4 #2 = M18 (online thread controller).**
- arithmetic re-derived, holds: 13.32 / 11.75 = 1.134; probe cost 3 x 2% x 13% = 0.78% [arith].
- what is weak: the spread is stock and s10, one run per point, on 103GB, where reps differ by ±4% [repo]. so the 96 vs 64 gap (3%) is inside the noise. only 192 vs 64 (13%) is clearly real. S19's own spread is unmeasured (E5).
- cheaper: M20 with "physical cores, not hardware threads" removes the 192-thread case with no controller. the rest waits on E5.

**a4 #3 = M17 (loader thread plan).**
- arithmetic re-derived, holds: 512 KB per 10 ms = 51 MB/s [arith], but both inputs are guesses.
- what holds: the order bug is measured [repo]: the loader ignores `--threads`. fixing it is one line and byte-identical. upstream has the same ordering and a separate env knob, default 8 [external: cycle-1 S4].
- what is weak: no hdd exists in this project. the hdd worry is real enough that the PR author raised it [external: cycle-1 S3], but nobody has a number.
- cheaper: ship the order fix inside M2. leave the device-aware count until an hdd or usb disk is tested.

---

## 2. my own revisions

1. **baseline (R1 section 0, B1 = M1).** compare against **v2.17.2**, the stable release with PR #1033, first. RC1 second. the headline "S19 is 1.9x-4.8x faster than stock" now needs "than v2.17.1, a version superseded on 2026-09-23" [external: R1].
2. **R1 A7 retracted.** 1/36 is not a property of kraken2. per-position density is ≈ 1/3 (0b). the open number is f_db, now M22.
3. **B2 = M2.** port the residual stages onto v2.17.2 first, since PR #1033 claims byte-identical output vs stock [external: cycle-1 S3]. then RC1, where the output-changing fixes need a diff. M3 and the loader order fix ride along. M6 (the out-of-lock parser) comes free with RC1.
4. **B3 = M12.** a1 and a2 proposed the same test on their own; three agents agree. add M22 first, because the thrash on 8GB/16GB scales with f.
5. **B4 = M11.** i drop my 12-byte spill design for a2's: 4 bytes per lookup, scanner run twice [repo: `cycle_1_r1_a2_storage.md` idea 3]. it needs the least temp space. RC1's token stream (scan, resolve, replay) is the natural host [external: cycle-1 S4].
6. **B5 = M13.** a2's zero-cell bitmap floor, 32 / (1 + 0.70 x 32) = 32 / 23.4 = **1.37x** [arith], is exact. it is a better floor than my entropy guess. the ceiling stays 1.7-2.0x on 103GB [arith on a guessed value entropy]. the value of M13 now depends on orin's device speed, which nobody has measured.

---

## 3. rankings

### 3a. top 10 build list

| rank | M-id | one-line reason |
|---|---|---|
| 1 | M2 | the only way a gain reaches every class is through the binary people install. carries S8, S12, S15, S17 and, for free, M3 and the loader order fix |
| 2 | M20 | tiny, byte-identical, every class. a user who forgets `--threads` runs on 1 core today [external: a3 S4]. default to physical cores within the affinity mask, not all hardware threads |
| 3 | M9 | the biggest gains with a direction we trust: few-read cells, cold flash, small ram. thresholds from E1 and orin's cold test, not from guesses |
| 4 | M17 (order fix only) | one line, measured bug [repo]. the device-aware part waits for an hdd test |
| 5 | M11 | the only route for a db bigger than free ram (H3, ck's laptop at 3-4 GB free). build only if M22 and M12 say the thrash is real |
| 6 | M4 | the scanner is the largest cpu share and the fix is isa-free. build only if the 15-minute branch-miss test shows ≥ 0.2 misses per base |
| 7 | M8 (part a) | 0.25 day. matters where every db is ram-bound (H1, H2). build only if the free annotate shows crossing cost |
| 8 | M10 (part A) | fixes luna's 103GB variance if the variance is huge-page coverage. build only if `thp_gb` tracks wall |
| 9 | M13 | cold slow storage only. build only if zstd beats 1.3x and orin's device reads under ~1 GB/s |
| 10 | M5 | real for MinKNOW `.fastq.gz` users, 0 for our dorado fastq. build the wrapper half (0.5 day) only after the 10-minute gap test |

not in the top 10: M3 (inside M2; if M2 is refused, M3 takes rank 2), M6 (comes with RC1), M7 (gain inverted vs need, after M4), M14 (H4 only, interleave is one `numactl` flag), M15 (not byte-identical, canonical scheme unresolved), M16 (one class, one db size band), M18 (M20 covers the measured case), M19 (s20 null, E2 step 6 decides for free), M21 (E3 decides).

### 3b. top 5 measure-first list

| rank | what | cost | what it decides |
|---|---|---|---|
| 1 | M1: S19 vs v2.17.2 and RC1, 16 cells, 3 reps, plus sorted byte compares RC1 vs v2.17.1 | ~1.5 h | every headline, novelty, M2's value |
| 2 | M22 (new): read `minimum_acceptable_hash_value` from each db's `opts.k2d`, then count lookups once in one run (one counter in a throwaway tree, or the gprof build at `~/tools/kraken2-pg` [repo]) | 5-15 min | lookups per base per db. moves M3, M8, M9, M11, E1's touched fractions |
| 3 | E1: `-M` vs S19 warm, with the correctness gate | ~20 min | M9's warm branch |
| 4 | M12: cgroup `MemoryMax` after evicting the db file, 8GB and 16GB, 3 read counts | ~1 h | whether M11 is needed, M9's ram branch |
| 5 | orin storage and state probe: `dd iflag=direct` sequential, a queue-depth-1 4 KB random read loop, `transparent_hugepage/enabled`, then a4's 10-minute cold copy vs `-M` vs `MADV_RANDOM` test | ~30 min on campus | M9's cold magnitude, M13, whether S14 does anything on orin |

also free or nearly free, run alongside: the awk miss fraction over output column 5 (M8, M16), `perf annotate` on `perf_s14_103.data` (M8), `perf stat -e branch-misses` on S19 50MB (M4), `zstd -1 -T0` ratio on two dbs (M13), `thp_gb` vs wall over 6 runs (M10), and the `.fastq.gz` timing (M5).

---

## 4. prior-art and evidence verdict for every M-id

"upstream" means DerrickWood/kraken2 v2.17.2 or v2.18.0-RC1. "holds / weak / fails" judges the evidence behind the claimed gain, not the idea.

| id | prior art | evidence | one line |
|---|---|---|---|
| M1 | n/a, a measurement | holds | upstream facts fetched twice, by me and by the relay [external: R1, cycle-1 S1-S4] |
| M2 | new: S8, S12, S15, S17 are absent from upstream source [external: cycle-1 S4] | weak | per-stage gains are luna-measured; the residual over v2.17.2 is unmeasured, 1.14x on 50MB is [arith] |
| M3 | upstream has it (2.17.2, PR #1033 resolves distinct minimizers) | holds for the mechanism, weak for the gain | 4.7% rests on `PrefetchIndex` being instruction cost; the capped-db waste may matter more (0b) |
| M4 | other tool: SimdMinimizers' deterministic window | weak | the cycle budget assumes 4 IPC; branch misses unmeasured; S11 precedent |
| M5 | other tools: rapidgzip, pigz, igzip | weak (fails for our input) | rate is from base64 data, not fastq [external: R3]; our input is plain fastq [repo]; MinKNOW users do get `.fastq.gz` [external: R4] |
| M6 | upstream has it (RC1 `fast_reader`) | holds | knee re-derived: 59 ms / 0.98 ms ≈ 60 threads [arith], so H4 only |
| M7 | other tool: SimdMinimizers (32-bit hash order, not kraken2's 64-bit order) | weak | all gains [guess]; widest on the box that needs it least |
| M8 | other tool: swiss-table group compare; part a already in the trie brief section 8 [repo] | weak | line-crossing arithmetic holds; miss fraction guessed; hardware prefetch overlap [UNCLEAR] |
| M9 | new as an automatic planner; KrakenUniq leaves the choice to the user | holds for direction, weak for size | ~30x rests on a class iops row at unknown queue depth; few-read faults are queue depth 1 |
| M10 | new: no classifier uses `MADV_COLLAPSE` | weak | variance cause unproven; dead on orin 5.10; kernel config unknown |
| M11 | other tool: KrakenUniq `--preload-size` (exact); Kun-peng, MetaCache, `k2` multi-db (not exact) | holds for shape, weak for size | KrakenUniq's measured 61x supports it; our thrash estimates assume f = 1 |
| M12 | n/a, a measurement | holds | cgroup charging rule fetched [external: cycle-1 S16]; eviction first is required |
| M13 | other tool: Centrifuger compresses its index (different structure) | holds for the 1.37x floor, weak for the gain | gain needs a slow device, and orin's device speed is unmeasured |
| M14 | other tool: `numactl --interleave` needs no code; Mitosis for page tables | weak | H4 only. the one clean luna hint is stale: stock, 8GB, 32 threads, node-0 pinned 4.405 s vs unpinned 5.261 s [repo: `dorado-kraken-research/README.md` 8f] |
| M15 | literature: mod-minimizer; SKiM's syncmers for a kraken-like tool [external: a1 src 5, 6, 12] | weak | 0.226 is for forward schemes; canonical sampling at (5, 31) unresolved; not byte-identical |
| M16 | other tools use filters (binary fuse); new in front of kraken2's table | holds for the arithmetic, weak for the gain | 1 - e^(-8.53M / 2^26) = 11.9% re-derived [arith]; helps H1 with a panel db only; luna would lose |
| M17 | upstream partly: env knob `K2_DB_READ_THREADS`, default 8, still before `--threads` | holds for the order bug, weak for the device part | no hdd in the project; the PR author shares the worry [external: cycle-1 S3] |
| M18 | [UNCLEAR], not searched; new for kraken2 | weak | one rep per point; only the 192-thread case clears the noise; M20 covers it |
| M19 | upstream has the manual knob `K2_PREFETCH_DIST` | weak | s20 null on luna [repo]; orin's miss-buffer count [UNCLEAR] |
| M20 | upstream default is 1 thread [external: a3 S4] | holds | output does not depend on thread count [repo: `modes.sh` 1 and 7 threads] |
| M21 | common practice [UNCLEAR, not fetched]; the orin `-march=native` failure is sourced [external: a3 S7] | weak | E3 has not run |
| M22 | n/a, a measurement (new id) | holds | 0b: the gprof internal ratio, the 8GB-faster-than-50MB timings and the S9 null on 8GB all point to f < 1 on capped dbs |

---

## 5. claims to keep out of the cycle-1 conclusion

- "~30x on cold emmc" (M9). say "map beats copy on cold flash for few reads; size unmeasured".
- "900 s" or "4,500 s" thrash on 8GB/16GB before M22 reads f.
- "74-79 s of gz inflate" as our case. our input is plain fastq.
- "1 lookup per 36 bases" (my own R1 A7, retracted) and "bases / 3 lookups" on capped dbs.
- "S9/S10/S13/S14 are new" or "upstream only has this in an RC". it is in stable 2.17.2 [external: R1].
- any M3, M4 or M8 percentage as measured. all rest on [guess] or on a 32-thread share applied to other machines.
