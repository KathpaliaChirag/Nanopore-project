# cycle 1, round 2: a3_cpu (counters, revisions, ranking)

agent a3_cpu. lens: what each idea costs the cpu, and what the scanner, threads, input path and compiler say about it. research and writing only: nothing was built, run or committed. ids are the relay's M1-M21 (`cycle_1_r2_relay_brief.md`); i add M22 and M23 (two measurements) in section 5.

---

## sources read this round

new fetches (2026-10-26):

| # | source | exact claim used | used for |
|---|---|---|---|
| N1 | kraken2 v2.18.0-RC1 `scripts/k2`, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/scripts/k2 | for compressed input, `classify()` makes a fifo (`os.mkfifo(fifo1_pathname, 0o600)`), and writer threads run `write_to_fifo` → `read_from_files`, where `get_reader` opens each file with `gzip.open`, `bz2.open` or `lzma.open` and writes the decompressed records into the fifo from python. `--threads` default: `os.environ.get("KRAKEN2_NUM_THREADS") or 1` | M5, M9, M17, M20 |
| N2 | kraken2 v2.17.1 `src/dump_table.cc` (the backend of `kraken2-inspect`), https://raw.githubusercontent.com/DerrickWood/kraken2/v2.17.1/src/dump_table.cc | prints `"# Min clear hash value = " << idx_opts.minimum_acceptable_hash_value`, plus k, l, `# Table size:` and `# Table capacity:` | conflict 1, M22 |

repo files read for the first time this round:
- `dorado-kraken-research/Luna/bash_history.md` step 40: stock v2.1.3 gprof build, `--db ~/data/kraken2_db`, 1 thread, `reads_hac.fastq`: "MinimizerScanner 53.35% (351M calls), CompactHashTable::Get 23.23% (11.6M calls), reverse_complement 6.69%" [measured]. `dorado-kraken-research/CLAUDE.md` names `~/data/kraken2_db` as the "standard 8 GB DB".
- `dorado-kraken-research/WSL2/kraken2/gprof_report.txt`: `NextMinimizer` 354,164,193 calls, `Get` 9,871,933 calls, `reverse_complement` 354,478,588 calls [measured]. the db is not named in the file [UNCLEAR].
- `dorado-kraken-research/AccuracyDrift/AccuracyChase.md`: "Standard-8 | Standard capped at 8 GB | 7.5", "Standard-16 ... 14.9", "Standard ... 96.8", "PlusPF ... 103.4" (GB, post-extraction) [repo].
- `dorado-kraken-research/docs/reports/kraken2_get_optimizations_v2.md` S3: says standard_8 "has `minimum_acceptable_hash_value == 0`" [repo]. no source or measurement is given for it. i argue below that it is wrong.

the other four R1 files and the relay brief were read in full.

---

## 0. settling conflict 1 (lookups per base), and with it conflict 4 (M3's gain)

**wrong intuition:** "the minimizer changes about once every 3 positions, so a run does about 1 lookup per 3 bases on every db." (a1's and my R1 assumption.) a5's counter, "1 per 36 bases", came from a gprof file and looked like evidence that the density was wrong.

**what the counts really say.** two numbers have to be kept apart:
- **d**, the density: how often the minimizer changes from one position to the next.
- **f**, the kept fraction: which share of changed minimizers the db actually looks up.

a capped db ("standard capped at 8 GB") is built by keeping only minimizers whose hash is above a threshold. classify then skips any changed minimizer whose `MurmurHash3` is below `minimum_acceptable_hash_value`, before any `Get` [repo: `s9_patch.py` lines 72-80 keep stock's check]. so the lookups per position come to d x f, not d.

- d cannot be near 1/36. a window holds 5 l-mers [external: a1 src 1], so on non-repetitive sequence the same minimizer position wins at most 5 windows in a row, and d ≥ 1/5 [arith]. the random-order value is 0.333 [external: a1 src 5].
- the luna gprof run was on the **capped standard 8GB db** [repo: bash_history step 40, CLAUDE.md]: 11.6M `Get` for 351M scanner calls, 0.0330 lookups per position [arith on measured].
- the capped db's size suggests its kept fraction: 7.5 GB of a 96.8 GB standard db gives f ≈ 0.077 [arith on repo sizes; that the hash-space fraction tracks file size is a guess].
- then d ≈ 0.0330 / 0.077 ≈ 0.43 [arith]. that is in the same range as 1/3. if instead d = 1/3, then f ≈ 0.099 [arith]. either way, **a capped db does about 1 lookup per 30 positions, and an uncapped one about 1 per 2.3-3** [arith].
- this also explains a4's "50MB is slower than 8GB at 1 thread" puzzle [repo: RESULTS.md 2.3]. the 8GB db looks up ~10x fewer minimizers.
- the repo note that says standard_8 has a cap of 0 has no measurement behind it [repo]. it contradicts the gprof counts. the one-line check is `kraken2-inspect`, whose header prints `# Min clear hash value =` [external N2]; whether it can skip the full table walk is [UNCLEAR: flag name not checked]. that check is M22 (section 5).

| db | capped? | lookups per position | tag |
|---|---|---|---|
| 50MB `sample_targeted` | [UNCLEAR] (our own 6-genome build) | ~d if uncapped | [UNCLEAR] |
| 8GB standard-8 | yes, "capped at 8 GB" | ~0.033 | [measured gprof] + [repo] |
| 16GB standard-16 | yes, "capped at 16 GB" | ~0.05-0.07, if f ≈ 14.9 / 96.8 = 0.154 | [arith on guess] |
| 103GB pluspf | not a capped build | ~d, about 0.33-0.43 | [guess] |

**what this changes in other ideas:**
1. **M3 is bigger on 8GB and 16GB than anyone said.** S16's `fill()` hashes and prefetches every position. it never checks the cap; resolve does that [repo: `s16_patch.py` lines 23-26 vs 46-50]. on the 8GB db, ~2.0-2.6e9 positions change minimizer, but only ~0.20e9 pass the cap [arith: 6.036e9 x d, 6.036e9 x 0.033]. so S16 sends about **1.8-2.4e9 prefetches to random lines that nobody reads, 115-154 GB of useless dram traffic per full input** [arith, 64 B lines]. RC1 never issues them: phase 1 marks capped minimizers `TOK_SKIP` before `GetBatch` [external: a1 src 2].
2. **capped dbs are cpu-bound, not ram-bound.** with 1 lookup per 30 positions, the scanner dominates: the 8GB gprof shows scanner 53.35% + reverse complement 6.69% vs `Get` 23.23% [measured, stock v2.1.3, 1 thread]. so a5's A2 ("on orin and the laptop even 50MB is ram-bound") is right for uncapped dbs. but the **capped 8GB and 16GB dbs are the most scanner-bound cells on every class**. that moves M4 up for H1, H2 and H3.
3. **every lookup-count estimate for capped dbs is ~10x too high**: E1's touched fraction, M9's crossovers, M11's thrash baselines, M16's savings, a4's per-lookup costs. worked example: 10 reads on 8GB is about 10 x 3,189 x 0.033 ≈ 1,050 lookups, not 10.7K [arith]. a4's emmc crossover for 8GB moves from ~345 reads to ~3,500 reads [arith: 368K lookups / 105 per read].

**conflict 4, settled as far as arithmetic can:**
- 50MB (cap [UNCLEAR]) and 103GB: instruction savings only. dropping 2/3 of `PrefetchIndex` (7.0% of cpu [measured]) is 4.7% [arith on d = 1/3], plus 2/3 of the inlined `MurmurHash3` [UNCLEAR share]. so a1's -4 to -7% and my ~4.7% agree. **planning range 3-7% on luna 50MB** [guess range]. it is lower if part of `PrefetchIndex`'s 7% is the prefetch waiting for a free fill buffer.
- 8GB and 16GB: the 2/3 dedupe, plus ~90% fewer prefetch calls, plus the useless dram lines above. on luna, bandwidth has headroom: 115-154 GB over S19's 9.18 s is 12.5-16.8 GB/s [arith], against two sockets of 92-132 GB/s each [external: a4 src 7, arith]. so luna should see the instruction part only, [guess] 3-8%. on a one-channel laptop (15-23 GB/s achievable [a4 arith]), 115-154 GB is 5-10 s of channel time [arith], which can be a real share of the run: [guess] 5-25% there.

---

## 1. counters

### a1_dsa top 3

**M3 (a1 i1, my i1). agree, and it is bigger (section 0).**
- evidence holds: the per-position hash and prefetch is in `s16_patch.py` [repo]. stock hashed only on a change [external: a5 S5].
- a1 doubted the cap half ("an older repo note says standard_8 has 0"). that note is unsourced and the gprof counts contradict it (section 0). the cap half is the larger half on 8GB and 16GB.
- order of the two checks: dedupe first (it removes 2/3 of the hashes), then the cap check (the hash is needed for it), then prefetch. byte-identical: the resolve loop never reads a skipped or repeated slot.
- if we rebase on RC1 (M2), M3 is moot: RC1 already does both.

**M8 part a (next-line prefetch). keep it, but start with a narrower trigger.**
- evidence check: a1's 1.07 lines per hit and 1.32 per miss hold. at load 0.70 the expected probe is ½(1 + 1/(1-α)) = 2.17 cells on a hit and ½(1 + 1/(1-α)²) = 6.06 on a miss. with a uniform home offset, a run crosses a 16-cell line with probability (c - 1) / 16: 0.073 and 0.32 [arith].
- what breaks: m = 6 adds 37.5% more line fetches [a1 arith]. on an uncapped db on the one-channel laptop that is ~48 GB extra per full input [a1 arith], 2.1-3.2 s of channel time at 15-23 GB/s [arith]. if the laptop is bandwidth-bound (section 0, M16), that extra traffic can cost more than it hides.
- cheaper: trigger at offset ≥ 14 (m = 2) first, 12.5% extra lines [arith: 2/16]. it covers most hit crossings (hit runs average 2.17 cells) and some misses. widen it only if a1's annotate test shows boundary stalls.
- on capped dbs it matters ~10x less, because lookups are ~10x rarer (section 0).

**M8 part b (simd compare inside the line). rank it below part a.**
- cpu cost: a hit probes 2.17 cells on average [arith]. the scalar loop is ~2 iterations. the vector path is a fixed sequence: load 64 B (1 avx-512, 2 avx2 or 4 neon loads), shift out the key field, two compares, a move-mask, a shift by the home offset, a bit scan, one branch: ~10-14 instructions [guess]. so for hits it is about even on instructions. it wins on misses (6.06 cells) and by removing the loop-exit misprediction.
- arm: neon has no single move-mask instruction, so turning the compare into a bit mask costs extra instructions [UNCLEAR: not fetched]. so again the jetson gains least.
- the probe loop is part of `GetAt`'s 12.5% [measured], so the 50MB ceiling is a few percent [guess]. a1's -2 to -5% is a fair upper range.
- cheapest kill: one counter for mean probe length per `GetAt`, plus a1's free miss-fraction awk. if the mean probe is ≤ 2.5 cells, part b is ≤ 1-2% [guess]: drop it.

**M11 (a1 i3, a2 i3, a5 B4). build only after M12, and use a1's record design, not a2's replay.**
- cpu cost: a2's pass 3 re-runs the scanner, which is +38.5% cpu on 50MB-class cells [measured share]. on capped dbs the scanner is ~60% of cycles [measured gprof], so a replay costs even more there. a1's records (hash plus back-reference, 16 B per lookup) avoid the second scan.
- section 0 shrinks the problem. a2's worked case (16GB, 104,918 reads, 118M lookups, ~925 s thrash) becomes ~18-23M lookups at f ≈ 0.154 [arith], so about 140-180 s on the same model [arith on a2's numbers]. that is still far worse than warm, so M11 is not dead. but M12 may show that capped dbs cope under `-M`, which leaves M11 mainly for uncapped big dbs (103GB pluspf) on small boxes.
- a1's record buffer also shrinks ~10x on capped dbs [arith], so fewer read blocks and fewer table sweeps.

**M15 (lower-density sampling) has a cpu cost nobody priced.**
- mod-sampling takes the smallest t-mer in each 35-base window. that is 35 - t + 1 = 30 candidates for t = 6, or 25 for t = 11 [arith], against kraken2's 5 l-mers.
- M4's branch-free min-of-5 does not scale to 30 (29 cmovs per base). it needs the two-stacks window [external: round-1 S1] or a monotone queue, plus the canonical handling that a1 says is unresolved.
- on luna 50MB: lookups are 19.5% of cpu, so 32% fewer lookups saves at most ~6% [a1 arith]. the scanner is 38.5%, so a scanner that costs [guess] 0-50% more would add 0-19%. **net: possibly a loss on cpu-bound cells**, a win on ram-bound ones.
- cheapest check: time the candidate scheme in M23's `scan_test.cc` before any rebuild or accuracy work.

**M16 (miss prefilter): mostly an H1 idea, and it needs to be branch-free.**
- cpu cost: the filter answer is a dependent load, followed by a branch on "maybe" vs "no". at a1's guessed ~60% miss rate that branch is unpredictable, so each filtered lookup can pay a misprediction unless the code is branch-free. the table prefetch also has to wait for the filter, which makes the pipeline 3 stages (a1 says so).
- why it may still pay on H1: an uncapped db on the one-channel laptop does ~2.0e9 lookups x ~1.2 lines x 64 B ≈ 154 GB of traffic per full input [arith on d = 1/3 and a1's lines per lookup], 6.7-10 s of channel time at 15-23 GB/s [arith]. b-lite cutting ~53% of those trips [a1 arith] is a bandwidth saving, not a latency one.
- keep it after M3 and M8a, and only after a1's free miss-fraction awk.

### a2_storage top 3

**M9 (a2 i1, a4 i1). agree with the design. three cpu and input-side gaps.**
1. **the input size is often unknown.** both upstream wrappers feed compressed input through a pipe: perl through `/dev/fd/N` pipes [external: round-1 S4], `k2` through a fifo [external N1]. stdin is possible too. `stat` on a pipe gives no size. the planner needs a default for "unknown". a4's variant 1b (map, plus a background thread streaming the file into page cache) is the safe one [guess].
2. **it must use d x f, not d.** the cap is in `opts.k2d` (printed as "Min clear hash value" [external N2]), so the planner can read it for free. without it, the crossovers on capped dbs are off by ~10x (section 0).
3. probe cost is small: `mincore` on the 111 GB mapping returns 27.1M bytes in one call [arith: 111e9 / 4096] [guess: tens of ms].
- cheaper first: E1 (planned). nothing else.

**M10 (huge pages that land). a cheaper first check for part A.**
- part A runs `MADV_COLLAPSE` synchronously in the loader threads, so on a bad session each missing 2 MB costs a copy plus compaction [external: a2 src 2]. on a 66-user box that compaction also takes cpu and page cache from others.
- cheaper kill: read the thp fallback counter in `/proc/vmstat` (`thp_fault_fallback` [external: a4 src 12 names it]) before and after one slow S19 103GB load. if slow sessions show no fallbacks, coverage is not the variance and part A dies without the 6-run test.
- part B: no cpu counter. it is dead on orin's 5.10 kernel [a2], and a2's 20-line test decides luna.

**M11.** see a1 above.

**M13 (compressed container) decode cost is not the problem.**
- the zero-cell bitmap decode is an "expand": put each stored cell back into its slot. scalar and branch-free it is `out[i] = bit ? src[j] : 0; j += bit`, ~4-5 instructions per cell [guess], so roughly 1-2 GB/s of output per core [guess]. avx-512 may have a native expand [UNCLEAR: not fetched this round]. avx2 and neon need a shuffle table [guess].
- cold on orin, 12 cores at that rate far exceed an emmc-class 0.25 GB/s [external: a4 src 3]. warm on luna it is an extra pass of about the same cost as the page-cache copy (~2 GB/s per thread for stock [arith on measured 111 GB / 56.2 s]) [guess].
- the real questions are the ratio (a5's 5-minute zstd test) and losing `-M`, as a2 says.

### a4_hw top 3

**M9 (a4 i1).** see M9 above. a4's crossover table uses 1,070 lookups per read. on capped dbs it is ~105 (section 0), so the "map" region of the table is ~10x wider there.

**M18 (online thread controller). rank it low: openmp reality and noise.**
1. **parking is more than a counter.** kraken2's workers run one `omp parallel` loop that pulls blocks under `critical(seqread)` [repo: `classify.cc:522`]. a thread that just leaves the loop waits at the region's implicit barrier. libgomp spins there for a while before sleeping [UNCLEAR: spin count not fetched]. on an smt core a spinning sibling takes issue slots from the working thread. so a parked thread must block on a condition variable, and un-parking needs a wake-up. doable, but it is real code.
2. **the signal is noisy.** a 3 MB block is ~480 reads [arith], the full input is ~3,974 blocks [arith]. a 2% window is ~80 blocks, ~1.2 blocks per thread at 64 threads [arith], so the window rate depends on which threads happen to finish. a 10% window is safer, but then the probe cost is ~3 x 10% x 13% ≈ 4% [arith], a third of the 11% gain.
3. **at M20's default it is ~3%.** with the default at physical cores (96 on luna), the measured gap to the best point is s10 classify 12.12 s vs 11.75 s [measured], 3%, inside luna's ±4% noise [measured, a5 A12]. the 13% only exists for a user who passes 192.
- cheaper: E5 (planned), then M20, then a static "one socket if the table fits one node" rule from M14. revisit M18 only if E5 shows a big S19 spread at the physical-core count.
- evidence check: the 13-14% is measured, one run per point, s0 and s10 on 103GB only [measured].

**M17 (loader thread plan). the "obey `--threads`" part regresses the default user.**
- both wrappers default to 1 thread: perl `$threads = $ENV{"KRAKEN2_NUM_THREADS"} || 1` [external: round-1 S4], `k2` the same [external N1].
- so a loader that obeys `--threads` would load 103GB on 1 thread for every user who doesn't pass the flag. stock's 1-thread load was 56-58 s [measured], against S19's 3.79 s for the whole 10-read run [measured]: up to ~15x slower on the load [arith on measured].
- fix: ship M17 together with M20, or keep loader threads separate from `--threads`, as upstream does with `K2_DB_READ_THREADS` (default 8) [external: relay brief, PR #1033]. my proposal: loader threads = min(cpus in the affinity mask, cap), lowered only when the user passes `--threads` explicitly. whether libgomp's default follows the affinity mask, and whether it sees cgroup cpu quotas, is [UNCLEAR: not fetched].
- the hdd branch is untestable here (no hdd), as a4 says.

**M19 (mlp probe).** agree with a4's own low rank. E2 step 6 decides it for free.

### a5_skeptic top 3

**M1 (re-baseline vs RC1). agree, rank 1 to measure. four additions.**
1. add **S19 + M3** (a half-day build) to the same grid. otherwise the capped-db cells compare RC1 against an S19 that sends 1.8-2.4e9 useless prefetches (section 0), a known waste rather than a design difference.
2. add one `perf record` of RC1 on 50MB. per a5's source read, RC1's scanner recomputes the reverse complement in five rounds, pushes candidates as one struct, and expires with `erase(begin())` [external: a5 S4]. the struct push is the shape S18 found stalling at 21% [repo: `13_S18.md`]. `erase(begin())` shifts up to 4 entries of 16 B per expiry [arith]. this sizes M2's scanner part.
3. RC1 still runs one `omp parallel` region per input file [external: a5 S4], so the 16-file column includes S8's barrier effect. read the 104,918-read single-file column for per-read cost.
4. include a capped db (8GB) and the uncapped 103GB in the byte compare. RC1's counting change ("minimizers undercounted") may only show in reports [a5].

**M2 (port the residuals onto RC1). agree, rank 1 to build after M1. cpu details:**
- S12 is bigger on RC1 than on v2.17.1: `GetBatch` hashes each key twice (once for the prefetch, once in `Get()`) and uses `%` twice [external: round-1 S4]. the port is "hash once, keep `hc` and the slot per key in arrays".
- S16 does not port as written. keep RC1's rolling distance-8 design and tune the distance only where E2 step 6 / M19 say so.
- S15 maps onto phase 3's replay loop. S17, S18 and M4 all live in `mmscanner`, which in RC1 is still the stock scanner plus a vector.
- S8 has to be rewritten, because RC1 replaced `seqreader.h`, which S8 patches [repo: `s8_patch.py`], with `fast_reader` [external: round-1 S4].
- a5's 1.14x residual for 50MB is luna-only. but on capped dbs the cpu residual applies on every class (section 0).

**M12 (small-ram emulation). agree. run it on both kinds of db.**
- capped (8GB, 16GB) and uncapped (103GB, or whatever fits the cap), because lookups differ ~10x (section 0). prediction [guess]: capped dbs thrash far less than a5's and a2's arithmetic says.
- expect S19's copy path to be oom-killed under `MemoryMax=8G` on 16GB. the charge rule [external: a5 S16] counts its anonymous copy. log it as a result, not a failure.

**a5's A2 and A9: accepted, with one correction.**
- A2: on H1 and H2 an *uncapped* 50MB db is ram-bound, so M4 and M7 gains on those cells are [UNCLEAR], not just [guess]. but the capped 8GB and 16GB dbs are scanner-bound everywhere (section 0).
- A9: `NextMinimizer` is a big out-of-line function, so LTO may not inline it. that strengthens M4: one call per 16 positions (or per read on RC1) does not depend on the inliner at all.

### M20 and M21

**M20 (default threads = physical cores). support, as one change with M17.**
- byte-identical: `modes.sh` passes at 1 and 7 threads [repo].
- physical rather than logical cores: s10 classify 12.12 s at 96 vs 13.32 s at 192 [measured, luna 103GB, one run each].
- risks: a 96-thread default is rude on a 66-user box. on hpc nodes cgroup quotas may not show in the core count [guess]. so: physical cores in the affinity mask, printed to stderr.

**M21 (portable build tiers). do it with E3, rank it low as a speed idea.**
- E3 predicts 0-3% for `-march` [repo guess], and kraken2's hot code is integer. its real value is packaging: never ship `-march=native`, keep one x86 tier and one armv8.2 tier, and give M7 a place to dispatch from.
- every tier needs `-ffp-contract=off` (my R1 note 3). and orin's `-march=native` with gcc-11 fails on `flagm` [external: round-1 S7].
- 0.5 day.

---

## 2. my own revisions after RC1 and round 1

- **M3.** on S19, do it first (half a day); it is larger on capped dbs (section 0). on RC1 it is already done. so its value hangs on M1.
- **M4 ports onto RC1, more cleanly than onto S19.** RC1's phase 1 already scans a whole read before any lookup [external: a1 src 2]. so M4 becomes `ScanRead(seq, out_min[], out_amb[])`, one call per read: no per-base call and no dependence on LTO. the min-of-5 ring replaces the window whatever container was there (deque, vector, ring). RC1's scanner lacks S17 and keeps the struct push and `erase(begin())` [external: a5 S4], so M4 there bundles S17 + S18 + the branch-free window. the stream-equivalence test is unchanged. RC1 is C++17, which changes nothing here. and section 0 says M4 matters on capped dbs on every class, not only luna's 50MB.
- **M5 is still new against both upstream wrappers.** perl decompresses with one `gzip -dc` per file into pipes [external: round-1 S4]. `k2` decompresses in python (`gzip.open`) into one fifo [external N1]. both are single-threaded, and the python path may be slower than `gzip -dc` [guess]. the 10-minute kill test stands.
- **M6 drops off my build list.** upstream has it, and it comes free with M2. it only comes back if M1 says stay on S19.
- **M7 is unchanged:** after M4, x86-first, may be a null on neon.
- **lookup counts:** every estimate of mine that used d is right for uncapped dbs and ~10x high for capped ones (section 0).

---

## 3. ranked top 10 build list

| rank | id | one line of reason |
|---|---|---|
| 1 | **M3** | half a day, byte-identical, every isa. it removes 1.8-2.4e9 useless prefetches per full 8GB input [arith] and makes M1's S19 column fair |
| 2 | **M2** | the portable gain only reaches users through the release they install. gated by M1. it includes "hash once" in `GetBatch` (S12) |
| 3 | **M4** | the scanner is 38.5% on 50MB and ~60% on the capped 8GB db [measured]. it ports cleanly into RC1's phase 1. gated by the 15-minute `perf stat` |
| 4 | **M20 + M17** (one change) | both wrappers default to 1 thread [external]. physical cores by default, loader threads not tied to an implicit 1. byte-identical, under a day |
| 5 | **M5** | both wrappers decompress gz on one thread [external]. huge when the input is gz, 0 otherwise. gated by a 10-minute test |
| 6 | **M9** | the biggest load-side wins on emmc, nvme and small ram. gated by E1. needs an unknown-size default and the d x f lookup model |
| 7 | **M10** | part A for luna's 103GB variance, part B for a `-M` that wins on big inputs. gated by the `thp_fault_fallback` check and a2's 20-line test. dead on orin 5.10 |
| 8 | **M8 part a** | 0.25 day. start with offset ≥ 14 (12.5% extra lines). mostly H1 and H2, uncapped dbs |
| 9 | **M21** | packaging, not speed: no `-march=native` binaries, fp-contract off, a home for M7's dispatch. do it with E3 |
| 10 | **M11** (a1's record design) | only for uncapped big dbs on small boxes, and only if M12 shows thrash |

below the line, with the reason: M7 (after M4, inverted gain), M13 (after the ratio test, fights `-M`), M14 (H4 only), M16 (H1 only, after M3 and M8a), M15 (accuracy check plus an unpriced scanner cost), M18 (~3% at M20's default), M19 (E2 step 6 decides it), M6 (comes with M2).

## 4. ranked top 5 measure-first list

| rank | id | one line |
|---|---|---|
| 1 | **M1**, plus S19+M3, a perf of RC1's scanner, and a capped db in the byte compare | sets the base for every build above. ~1.5 h on luna |
| 2 | **M22** lookup census | `kraken2-inspect` header "Min clear hash value" on all 4 dbs [external N2], plus 3 counters (positions, changed, looked up) in one throwaway run. ~15 min. settles conflict 1 and resizes M3, M8, M9, M11, M16 and E1 |
| 3 | **M4's kill test** | `perf stat -e cycles,instructions,branches,branch-misses` on S19 50MB and 8GB, plus `perf record -e branch-misses`. 15 min, no build |
| 4 | **E1** (`-M` correctness and timing) | gates M9 and M10 part B. 20 min, planned |
| 5 | **M12** on one capped and one uncapped db | gates M11 and M9's small-ram branch. ~30 min |

next in line: M5's 10-minute gz test, then E5 (decides M18 and M14).

---

## 5. new ids and open dissent

- **M22 (measure): lookup census.** read the cap of every db, count positions, changed minimizers and real lookups once. it replaces three guessed numbers (d, f, lookups per run) with measured ones. it is the dependency of half the list.
- **M23 (measure): `scan_test.cc` on every class.** a scanner-only timer (like `parse_test.cc` [repo]) that also dumps the (value, ambiguous) stream. it gives scanner ns per base on luna, orin and any linux laptop, it is M4's equivalence test, and it prices M15's scanner before any rebuild.
- **dissent i expect from a2 and a4:** "M9 should be rank 1, the load wins are 10-30x." those are cold, few-read cells on emmc and nvme, and no class model number for orin cold is measured yet (conflict 2). M9 is rank 6 here only because E1 has to run first. if E1 confirms `-M` wins in the small-read cells, i would move M9 to rank 2.
- **dissent i expect from a1:** "M8 part b is cheap and byte-identical." agreed on both. but at 2.17 cells per hit it saves few instructions, and neon pays extra for the mask. measure probe length first.
