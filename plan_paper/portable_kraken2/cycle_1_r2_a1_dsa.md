# cycle 1, round 2, a1_dsa (data structures and algorithms)

agent a1_dsa. this round counters the other four R1 files, revises my own ideas after the upstream v2.17.2 / v2.18.0-RC1 facts, and ranks the merged M-ids. nothing was run. tags follow `00_context.md` section 6.

**evidence used this round:**
- repo: the old WSL2 gprof run (`dorado-kraken-research/WSL2/kraken2/gprof_report.txt`) and its setup (`dorado-kraken-research/docs/knowledge_base.md` section 18.1)
- repo: `dorado-kraken-research/AccuracyDrift/RESULTS.md` 2.3, the S-stage files and patch scripts, and the five R1 files
- one new fetch: kraken2 master `src/build_db.cc`, https://raw.githubusercontent.com/DerrickWood/kraken2/master/src/build_db.cc. claim used: `double frac = opts.maximum_capacity * 1.0 / opts.capacity;` then `opts.min_clear_hash_value = (uint64_t) ((1 - frac) * UINT64_MAX);`, stored as `index_opts.minimum_acceptable_hash_value`. so a capped db keeps a fraction f = frac of hash space, and f can be read back from `opts.k2d`
- R1 sources reused, not new: kraken2 master `classify.cc` (`TOK_SKIP` before `lookup_keys`) and `compact_hash.h` (`GetBatch`), from my R1 list items 2 and 3

---

## 0. conflict 1, lookups per base: settled from the repo's own counts

**the wrong intuition:** "a3 and i say 1 lookup per 3 bases, a5's gprof says 1 per 36, so one side is wrong." both are right, for different dbs. the missing variable is the db's hash cap (a build-time rule that keeps only minimizers whose hash is above a threshold).

**what the gprof run counted** [repo: `gprof_report.txt`; setup: `knowledge_base.md` 18.1]. the input was `barcode02.fastq`, 104,829 reads. the db was "`~/eskape_db` - pre-built 8 GB standard k2 database". the flags were `-p 1` and `-R <report>`, so a report was requested.
- `NextMinimizer`: 354,164,193 calls. that is once per k-mer position (3,378 per read) [arith]
- `CompactHashTable::Get`: 9,871,933 calls
- `HyperLogLogPlusMinus::insert`, called from `ClassifySequence`: 3,220,914. in the v2.17-era loop this runs once per *new* minimizer that *hit*, when a report is requested [external: a5's S5, v2.17.1 `classify.cc`]
- `unordered_map::operator[]`, called from `ClassifySequence`: 10,179,375. this is the per-position `hit_counts[taxon]++` for a nonzero taxon, repeats included [repo: `s16_patch.py` lines 68-82 keep the same per-position branch]

**three numbers fall out:**
1. **density d** (how often the minimizer changes between neighbouring k-mers). positions per hit minimizer = 10,179,375 / 3,220,914 = 3.16, so **d ≈ 0.316** [arith]. it assumes a minimizer's run length does not depend on whether it hits. the scanner never sees the table, so this is a safe [guess]. it matches the random-order 0.333 for (5, 31) [external: R1 source 5].
2. **kept fraction f.** distinct minimizers ≈ 354.16M x 0.316 = 111.9M [arith]. only 9.87M reached `Get`, so **f ≈ 0.088** [arith]. so about 91% of distinct minimizers were skipped by `minimum_acceptable_hash_value`, the cap that `build_db.cc` sets to (1 - f) x UINT64_MAX [external: build_db.cc].
3. **the miss fraction among real lookups.** 3.22M of the 9.87M lookups hit, which is 32.6%. so **67% of lookups missed**, on this sample and db [arith].

**cross-check, two independent counts.** the predicted share of nonzero positions is f x hit rate = 0.088 x 0.326 = 0.0287. the measured share is 10,179,375 / 354,164,193 = 0.0287 [arith]. they agree to three digits.

**the rule:** lookups per position = d x f, with d ≈ 0.32 and f = 1 - threshold / 2^64.

| db | f | lookups per position | full input (≈ 6.0e9 positions [repo]) |
|---|---|---|---|
| 50MB (custom build, far under any cap) | 1 [guess] | 0.316 | ~1.9B [arith] |
| 8GB (prebuilt standard, if luna's file is the gprof db's build) | ~0.088 [arith] | ~0.028 | ~0.17B [arith] |
| 16GB (prebuilt standard) | [UNCLEAR]; ~0.18 if it caps the same library at 2x the size [guess] | ~0.056 [guess] | ~0.34B [guess] |
| 103GB (pluspf) | ~1 [inferred, below] | 0.316 | ~1.9B [arith] |

**why 103GB looks uncapped.** stock's 1-thread classify is 981.7 s for 6.036e9 positions [measured], 163 ns per position [arith]:
- at f = 0.088, that would be 163 / 0.0278 = 5.9 µs per lookup. that is impossible with a warm table [arith]
- at f = 1, it is 163 / 0.316 = 515 ns per lookup, close to a4's ~488 ns [arith]

**three measured luna results line up with a sparse-lookup 8GB:**
- at 1 thread, standard_8gb (7.6 GB) takes 16.78 s, faster than sample_targeted (50 MB) at 19.73 s and eskape_human_4gb (3.8 GB) at 29.82 s [repo: `RESULTS.md` 2.3]
- S12 gave 50MB -5.5% and 8GB no change [repo]
- S9 and S16 gave 8GB no change, or a tie [repo]

**a conflict inside the repo.** `kraken2_get_optimizations_v2.md` S3 says standard_8 "has `minimum_acceptable_hash_value == 0`", with no evidence given [repo]. the gprof counts contradict it, unless the WSL2 `eskape_db` and luna's `standard_8gb` are different builds [UNCLEAR]. the 5-minute settle is to read the threshold out of each `opts.k2d`, which is measure item 1 below.

**what moves because of this:**
- **touched fraction** (E1's -M model, with 64 KB fault-around windows) [arith]:
  - 8GB (116K windows): 10 reads → ~890 lookups → 0.8%. 1,000 reads → ~89K → 54%. 104,918 reads → ~100%
  - 103GB (1.69M windows): 1,000 reads → ~1.0M lookups → 45%
  - so a5's A7 "~5% at 1,000 reads on 103GB" applied 1/36 to a db that looks uncapped. E1's 47% stands for 103GB
- **M3.** on capped dbs, S19's `fill()` issues about 10 fresh ram prefetches for every real lookup: capped-out distinct minimizers are 0.316 x 0.912 = 0.288 per position, real lookups are 0.028 [arith]. section 1 has the counter to a3.
- **M9 / E1 / M12.** every crossover and fault estimate must use positions x d x f, not bases / 3.
- **M11.** on 8GB the full input is ~0.17B records x 16 B = 2.7 GB [arith], so an 8 GB box needs one sweep of the table, not eleven.
- **M8 and M16** matter on uncapped dbs only. there the lookups are dense.

---

## 1. counters

### a2_storage (top 3: M9, M10, M11)

**M9, the path-picking loader.**
- what breaks: the "input size → touched fraction" probe uses lookups ≈ bases / 3 [repo: a2 R1 idea 1, step 1]. on a capped db that overestimates lookups about 11x [arith, section 0]. so the planner switches from map to copy about 11x too early.
- which class it hurts: H2 and H1 running the prebuilt 8GB / 16GB dbs, which are the dbs small boxes actually use.
- what is cheaper: nothing new. read `minimum_acceptable_hash_value` from `opts.k2d` at startup (one 8-byte field, already loaded by classify) and compute lookups = positions x d x f.
- evidence: the branch logic holds. one prediction needs revising. on a capped db, `-M` at 4 KB pages pays page walks on ~0.17B lookups, not ~1.9B [arith]. so E1's predicted full-input loss for `-M` on 8GB/16GB (0.8-0.97x [repo: plan E1]) may not happen [guess]. test that inside E1, per db.

**M10, huge pages that land.**
- what breaks: nothing in the data structure. but its gain scales with lookups, because each lookup at 4 KB pages pays a page walk. on capped 8GB/16GB that is ~11x fewer walks than a2's 103GB arithmetic implies [arith].
- one twist that supports part A, as a [guess]: S14 gave 8GB -20% [repo], which is a lot for a db with ~0.17B real lookups. the S9 pipeline was also issuing ~1.74B capped-out prefetches on 8GB [arith], each needing its own page walk at 4 KB. so some of S14's 8GB gain may have been page walks for garbage prefetches. if so, M3 removes that cost a second way.
- class: H4 and H1 kernels that are new enough. H2 cannot use it on 5.10 [repo: a2 kernel table].
- evidence: part A's link to the 12.3-21.6 s variance is [UNCLEAR]. a2's own kill test (wall vs `thp_gb` over 6 runs) is the right one.

**M11, out-of-core.**
- merge: a1 i3, a2 i3 and a5 B4 are one idea. the brief already merged them.
- two corrections:
  1. a5 says the probe tail "must cover the longest run of filled cells in the table, which is [UNCLEAR]". it does not need a global maximum. read past b until the first empty cell, a few 64 KB blocks at a time. a linear probe that starts in [a, b) stops at that cell [external: R1 source 3, empty = value 0]. so the rule is exact, and its length is found on the fly. the last range wraps to the table start the same way.
  2. a2 re-runs the scanner in the replay pass (+38.5% cpu [repo]). that is fine on H3, which is i/o-bound. on a capped db the record stream is tiny (2.7 GB for the full input [arith]), so storing tokens or answers is cheap either way.
- prior art: a5 found KrakenUniq's `--preload-size`, chunked and "identical" to the default mode. on a 392 GB db it took 47 min at 8 GB chunks, against 14 min fully preloaded and 48 h memory-mapped [external: a5 S13]. that is ~3.4x slower than all-in-ram but ~61x faster than mmap thrash [arith]. it is the best outside support for a 10-100x H3 gain, and it means M11's novelty is only "on kraken2's hash table".
- class: H3, low-free-ram H1, and H2 with the 103GB db on an external disk.

### a3_cpu (top 3: M3, M4, M5)

**M3, dedupe the hash and prefetch in `fill()`.**
- agree on the mechanism. counter on the gain: a3 says "instruction savings only: a repeated prefetch targets a line already in flight, so no dram traffic is saved". that holds for repeats and for uncapped dbs. it is wrong on capped dbs:
  - there, 0.288 distinct minimizers per position are capped out [arith, section 0]
  - S16's `fill()` still prefetches each one [repo: `s16_patch.py` lines 24-25 run before the cap check at lines 48-50]
  - each is a fresh random ram line, about 10x the traffic of the real lookups
- a3's fix must skip two things: repeats *and* `hc < minimum_acceptable_hash_value`.
- on 8GB, luna full input, that is ~1.74B lines, 111 GB of wasted ram reads, about 12 GB/s over a 9.18 s run [arith]. that is small next to luna's channels. on one channel (H1) it is a larger share, and it also pollutes the caches [UNCLEAR how much].
- upstream RC1 already marks these `TOK_SKIP` before `GetBatch` [external: R1 source 2].
- the gain in a3's and my R1 rests on d ≈ 1/3, which section 0 now supports (d ≈ 0.316).

**M4, a branch-free min-of-5 window.**
- the data-structure argument holds. kraken2 outputs only the window minimum's value, and ties are equal values, so any correct sliding minimum gives the same stream [external: R1 source 1, pop rule `>`].
- extra support for a3's branch-miss hypothesis: for random order, the monotone queue (a queue that keeps only candidates that could still become the minimum) holds H_5 = 1 + 1/2 + 1/3 + 1/4 + 1/5 = 2.28 entries on average. each insert pops one on average, with a 0 to 4 trip count [arith on the standard harmonic-number result, guess that it applies to the xor-toggle order]. a loop whose exit count is that random is hard to predict.
- what is cheaper: nothing. but E3's LTO should run first, as a3 says.
- class: all.

**M5, parallel gz.**
- outside my lens. one evidence note: the 158-170 MB/s gzip rate is from base64 and Silesia data [external: a3 S8]. fastq inflate speed is [UNCLEAR].
- our own inputs are plain fastq [repo], so it is zero for every number in this repo. real-user value is real [guess]. i keep it just outside my top 10.

### a4_hw (top 3: M9, M18, M17)

**M9, the cold planner.**
- a4's crossover table uses 1,070 lookups per read [arith on 1/3]. for a capped 8GB db it is ~95 lookups per read (3,378 x 0.028 [arith]).
- so the emmc crossover moves from ~345 reads to ~3,900 reads [arith, a4's own method with L = 368K lookups]. the planner keeps `-M` far longer on the dbs a jetson would carry.
- a4's H3 thrash estimate (680M random reads, ~4,500 s) becomes ~58M reads and ~380 s on a capped 8GB at 34% non-resident [arith on a4's own iops guess]. that is still bad, so a4's conclusion holds. but for capped dbs the fix is M11's single sweep, not only "a smaller-cell db".

**M18, the online thread controller.**
- nothing in the data structure. a ranking counter: the measured 64-vs-192 spread is from S0 and s10, not S19 [repo]. M20 (default = physical cores) captures most of the user-facing loss for a few lines [guess].
- so: M20 first, M18 only if E5 shows S19 keeps the spread.

**M17, the loader thread plan.**
- agree, tiny. the `omp_set_num_threads` order fix should land anyway. RC1 has the same ordering [external: a3 S4, a5 S4].

### a5_skeptic (top 3: M1, M2, M12; plus A7, A11, B5)

**M1, re-baseline against RC1.**
- agree. add one prediction that tests section 0's mechanism. RC1 skips capped minimizers before prefetching; S19 does not, but S19 has S12, S15, S17 and S18. so S19's lead over RC1 should be smallest on 8GB/16GB and largest on 50MB [guess]. if RC1 beats S19 on 8GB/16GB at the full input, that is M3's garbage-prefetch cost, measured.

**M2, port the residual stages onto RC1.**
- agree. one data-structure item belongs in the port. RC1's `GetBatch` hashes each prefetched key with `MurmurHash3` and `hc % capacity_`, then `Get` hashes it again and divides again, with `idx %= capacity_` on every probe [external: a3 S4, a5 S4]. phase 1 also hashed it once for the cap check [external: R1 source 2]. so a real lookup on a capped db pays 3 hashes and 2-3 divisions.
- S12's split (`PrefetchIndex` returns idx, `GetAt` reuses it, the hash is carried from phase 1) removes 2 hashes and 1-2 divisions per lookup [arith]. M8 should ride in the same port.

**M12, cgroup small-ram emulation.**
- agree as the gate for M11. a5's worked example now needs f: 16GB at 104,918 reads is ~20M lookups if f ≈ 0.18 [guess], not 117M. the run itself is unchanged. log `majflt` and compare against positions x d x f.

**A7.** answered in section 0. the 1/36 is a capped-db artifact. the same gprof run gives d ≈ 0.316.

**A11, "minimizer locality is already built in".**
- holds for consecutive locality. kraken2 stores only minimizers and skips repeats, so kache-hash's 1/r is there by construction [external: a5 S5, S9].
- it does not cover cross-read reuse. M5's M5a recipe emitted once per position [repo: `pending_measurements.md`], giving 351.8M positions and 32.8M unique minimizers [repo]. at d = 0.316 that is ~111M real lookups, so 70% repeat an earlier minimizer in the same 104,918-read file [arith]. the hash cap is independent of repetition, so the share should hold on capped dbs [guess].
- the 4-way cache caught 3.6% [repo] because the repeats are far apart. a sort over a big block of reads finds them at any distance. see M22 below. it is measure-first, not a build.

**B5 / M13, compressibility.**
- the entropy form is right: H(0.30) + 0.70 x (key bits + value entropy).
- two additions:
  1. the key bits are truly incompressible. the stored fingerprint is the top bits of the hash, the slot is `hc % capacity`, and for a capacity that is not a power of two the two are close to independent [guess]. so no slot-to-fingerprint redundancy can be squeezed out.
  2. zstd underestimates the ceiling on bit-packed fields, as a5 says. a 20-line pass that histograms the value field of `hash.k2d` gives the exact order-0 bound (the best ratio a coder can reach using symbol frequencies alone). run it before zstd.

### other ids ranked wrong, or missing a data-structure check

- **M6 (out-of-lock parser).** upstream has it. it is not a separate build; it arrives with M2.
- **M7 (simd scanner).** a3 says byte identity needs 64-bit lanes, so 4 lanes on avx2 and 2 on neon [external: a3 S6]. a cheaper order is possible:
  - compare only the top 32 bits of each 62-bit candidate. order on those equals the full order, except when two candidates share all top 32 bits
  - in a window of 5 candidates that is 10 pairs x 2^-32, about 2.3e-9 per window [arith]. a rare scalar fallback handles it
  - that doubles the lanes: 8 on avx2, 4 on neon
  - still after M4
- **M16 (my prefilter).** on capped dbs the hash cap already skips ~91% of distinct minimizers for free [arith, section 0]. only the 50MB-class panel case is left. it drops out of my top 10.
- **M19 (mlp probe).** on capped dbs real lookups are sparse, so prefetch depth barely matters. on luna, s20 was a null [repo]. orin, uncapped dbs only.
- **M14 (numa).** H4 only; nothing to add from my side.

---

## 2. does the data-structure reasoning hold? (my lens)

| id | verdict | why |
|---|---|---|
| M3 | holds, and stronger than R1 said on capped dbs | d ≈ 0.316 from the gprof counts [arith]. on capped dbs it also removes ~10 garbage ram prefetches per real lookup [arith]. upstream RC1 already does it [external] |
| M8 | holds in mechanism; matters on uncapped dbs only | the line-crossing rates (1.07 / 1.32 lines [repo: trie brief]) assume 64-byte-aligned cells and a uniform start offset. on the one sample with a count, 67% of real lookups miss [arith], which gives 0.07 x 0.33 + 0.32 x 0.67 = 0.24 unhidden trips per lookup [arith]. it must come after M3, or the next-line prefetch doubles the garbage on capped dbs. RC1's `GetBatch` also prefetches only the home line, so M8 can go upstream |
| M11 | holds, and exactly | the tail rule (read to the first empty cell past b) is exact without a global run bound. KrakenUniq shows chunked exactness on its own format [external: a5 S13]. on capped dbs one sweep covers the full input on an 8 GB box [arith] |
| M15 | holds for speed on uncapped dbs; changes meaning on capped dbs | with d measured at 0.316, mod-mini's 0.226 [external: R1 source 5] is -28.5% lookups and -28.5% stored minimizers [arith]. on a capped db the size is fixed by the cap, so a lower density raises f at the same size: more sensitivity per byte, not more speed [arith on build_db.cc's frac rule]. the canonical risk stays [UNCLEAR] |
| M16 | holds, but it is mostly redundant | the hash cap is an exact, free prefilter on capped dbs. b-lite (a fingerprint bitmap) helps only on panel dbs with many key bits (50MB: 26 bits [repo]) on machines whose cache is smaller than the table |
| M13 | the bounds hold | 1.37x floor from the zero-cell bitmap [arith, a2]. the ceiling is set by value entropy only. fingerprints are incompressible. cold-only, and it cannot be memory-mapped |
| A11 | holds for consecutive locality | not for cross-read reuse: 70% of real lookups repeat within one 104,918-read file [arith on repo M5 + d]. only a block sort reaches that (M22) |

---

## 3. my own revisions after v2.17.2 / RC1 and the other R1 files

1. **M3 (my idea 1).** still the cheapest fix while S19 is the vehicle. on RC1 it already exists, so if the team rebases (M2), M3 costs nothing. the capped-db half (skip prefetches below the threshold) is the bigger half on 8GB/16GB, not the side note R1 called it. R1's gain range stands for 50MB: PrefetchIndex 7.0% x (1 - 0.316) = -4.8% cpu [arith on measured share]. for capped dbs, a new [guess] of -2 to -8%, from fewer hash and FastMod calls plus fewer wasted lines.
2. **M8 (my idea 2).** unchanged in design. it now applies to RC1 too and should be offered upstream with M2. its gain moves to the uncapped dbs: 50MB on small-cache machines, and 103GB. on capped 8GB/16GB it is ~0 [guess].
3. **M11 (my idea 3).** merged. the tail rule above replaces a5's [UNCLEAR] about the longest run. on capped dbs the full input fits one record buffer [arith]. KrakenUniq is now the main prior art.
4. **M15 (my idea 4).** the gain is -28.5%, not -32%, against the measured d [arith]. db sizes for uncapped dbs [arith]:
   - 103GB: 111 GB to ~79 GB
   - 50MB: 48.8 MB to ~35 MB
   on capped dbs it is an accuracy-per-byte lever (thesis 2), not a speed lever.
5. **M16 (my idea 5).** downranked. the cap does its job on capped dbs, and luna's 50MB fits L3. the free awk test (column-5 miss fraction) stays as a gate.
6. **new id, M22: block-sorted dedupe of lookups, in ram.** sort a block's real lookups by slot, look up each distinct minimizer once, scatter the answers back.
   - byte-identical, because `GetAt` is a pure function of the minimizer
   - ceiling: 70% fewer table reads at a 104,918-read block [arith on repo M5 + d]
   - cost: a radix sort plus a random scatter, which may eat the win on H4 [UNCLEAR]
   - this is where the M5 reuse actually lives. measure first: the repeat share vs block size, from a hash dump of one run. not a build yet.

---

## 4. ranking

### (a) top 10 build list

1. **M3**: 0.5 day, byte-identical. it removes ~2/3 of hash and prefetch calls everywhere, and ~10 garbage ram prefetches per real lookup on capped dbs. upstream already does it, so it also makes S19 vs RC1 fair.
2. **M2**: the portable vehicle: S8, S12 (one hash and one modulo per lookup in place of RC1's three hashes), S15 and S17 onto RC1. it is the binary users will actually run.
3. **M4**: the scanner is 38.5% of cpu on every isa [measured, luna]. the value-only argument makes the min-of-5 byte-identical.
4. **M8**: line-aware probe, after M3. uncapped dbs on ram-bound machines, and it can go upstream into `GetBatch`.
5. **M9**: the load planner, fed with positions x d x f from `opts.k2d`. it is the only way one binary picks map, copy or direct per machine.
6. **M11**: exact out-of-core, gated by M12. a single sweep on capped dbs makes H3 run.
7. **M17**: the loader obeys `--threads`. tiny, and RC1 has the same ordering issue.
8. **M20**: default thread count = physical cores. tiny, byte-identical, and large for users who forget `--threads` [guess].
9. **M10**: part A (collapse after the copy) for H4/H1 kernels. part B only if the kernel config check passes.
10. **M15**: lower-density canonical sampling. the broadest uncapped-db lever, but it needs a rebuild and an accuracy check, and the laptop density test must pass first.

just outside: M7 (with 32-bit prefix lanes, after M4), M5 (gz, zero for our inputs), M13 (cold-only, after the histogram), M18, M14, M16, M19.

### (b) top 5 measure-first list

1. **K1, the lookup count (new).** read `minimum_acceptable_hash_value` from all four `opts.k2d` files (f = 1 - threshold / 2^64). add two counters (positions, real lookups) to one throwaway S19 tree, and run 50MB and 8GB at 104,918 reads. ~30 min. it fixes the inputs of M3, M8, M9, M11, M12 and E1.
2. **M1, S19 vs RC1 on 16 cells, plus RC1 vs v2.17.1 byte compare.** report capped and uncapped dbs apart. the prediction above tests M3's mechanism for free.
3. **M12, the cgroup small-ram emulation after eviction.** it gates M11 and M9's H3 branch. compare `majflt` with positions x d x f.
4. **E1, `-M` vs S19 per db.** on capped dbs `-M` may hold up even at the full input, because lookups are ~11x sparser [arith, guess on the outcome].
5. **the zero-cost gates:**
   - awk over column 5 of an existing 50MB S19 output, for the miss fraction (M16)
   - `perf annotate` of `GetAt` in the saved `perf_s14_103.data`, for the next-line share (M8)
   - a3's `perf stat` branch-misses on S19 50MB, for the window branch (M4)

---

## 5. notes for later rounds

- if K1 shows luna's standard_8gb has threshold 0, section 0's 8GB rows are wrong for luna. they still hold for the prebuilt db the gprof run used, and the d ≈ 0.316 estimate stands either way.
- ask a4: add the f column to the class grid. capped dbs change every H3 row.
- ask a3: does M4's stream-equivalence test cover the cap-skip path? the cap acts after the scanner, so it should not matter. confirm.
- M22 needs a hash dump. check whether the M5a `mmk.txt` or `m5_minimizer_histogram.txt` still exists on luna [UNCLEAR].
- the ordered-linear-probing note from R1 is still unsourced. not raised this round.
