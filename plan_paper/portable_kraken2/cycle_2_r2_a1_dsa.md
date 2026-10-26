# cycle 2, round 2, a1_dsa

nothing was run. no new fetches; every claim cites the R1 file that sourced it. tags follow `00_context.md` section 6.

---

## 1. counters to the new ids and the proposed moves

### the strongest counter: four ids need one shared structure

M11, M27b, M30 and M25 all start the same way. each takes a **block** of reads, collects its real lookups (changed, not ambiguous, at or above the cap), and keeps (slot, back-reference) per lookup.

- RC1's phase 1 already builds that list, but only per read [external: cycle-1 a1 src 2].
- so build it once, as a per-block lookup list on top of RC1's phase 1. then each id is a small consumer of it:
  - M27b: one `GetBatch` per block
  - M30: the block's distinct pages, one async read each
  - M11: radix-partition the list by slice
  - M25: sort and dedupe the list
- built separately, they are three or four rewrites of the same loop [guess on effort].
- implementation order: the list first, as part of M2. it is byte-identical by construction, because the per-read replay is unchanged.

### one line per new build id

- **M30 (cold fault-ahead).** agree. the data-structure details are in section 4. it fits RC1's per-read lookup list. it does not fit S19's 16-position `fill()`, which sees ~5 lookups at a time [arith], far too few to raise queue depth. its seconds are largest on uncapped dbs and slow devices. capped few-read runs are already ~0.1 s at qd1 on nvme [arith, a4].
- **M31 (input DONTNEED).** agree it stays outside the top 10. it is gated by its own `fincore` check inside M61.
- **M32 (detached teardown).** it hides a cost that huge pages already cut ~10x [external: a2 src 4]. it is likely a null once S14 / M10 land. E1's exit column decides. outside the top 10.
- **M33 (move the db to nvme).** one advice line inside M9. agree.
- **M40 (`final` + dispatch hoist).** agree, and it is cheaper than a3 says. on RC1, `Get` is called inside `CompactHashTable<Cell>::GetBatch`. on a class that is not final, that call can still be virtual [external: a3 N7, N8]. so on the RC1 base, M40 is one keyword and can ride inside M2's upstream PR, like M3.
- **M41 (run-length pipeline).** agree on the direction. there is one error in it (section 4). on the S19 base it subsumes M3. on RC1 it changes the token format, so it is an upstream design change. the cpu gate decides it.
- **M42 (shipped sampled profile).** rides with M21 after E3. no data-structure objection.
- **M51 (device micro-probe).** inside M9. agree. gp3 at qd1 costs 32 x 1-9 ms = 32-288 ms [arith on a4 N1], acceptable for a cold run.
- **M20' (min of physical cores and `cpu.max`).** agree. it replaces M20's definition.
- **M62 (spill guard).** agree. it ships with M20 on the RC1 base [external: a5 N5].
- **M64 (compressed slices in M11).** agree, details in section 4. it is the right home for M13.

### measure ids

- **M43:** agree, ~30 min, no code. it can kill M18.
- **M60:** agree it reframes the few-read claim. it is a framing test, not a build gate, so it goes 6th on my list.
- **M61:** agree it replaces M12.
- **M63, M53, M54:** paper and method items. none is a gate.
- **cpu gate:** agree it enters the top 5. it decides two builds (M4, M41) for 20 minutes.

### the proposed moves

| proposal | verdict |
|---|---|
| a2: M30 at 4 | M30 at 6, behind M4 and M9. its gain is cold, few-read and mostly uncapped, and a 2-minute qd test gates it |
| a3: M4 to 3, M41 at 4, M9 to 5, M40 at 7 | M4 to 4 (behind M27). M41 to 8 (gated, 3-5 days, the ambiguous-gap fix). M40 rides inside M2 |
| a4: M30 in at 5, M10 out, M13 stays | M10 out: agree. M13 stays: disagree, it folds into M64 |
| a5: no reorder, M62 with M20, M13 → M64 | agree on both folds |

---

## 2. fact fixes (section 3 of the brief)

1. **FINAL item 8.** confirm the fix. `-M` does run a db bigger than ram: Coriolis measured kraken2 `-M` on a 4 GB jetson up to DMR 52, at 611.7 → 403.8 kb/min [external: a5 N2]. issue #971 shows the other extreme, "stuck ... for days" [external: a5 N6]. a caveat from my lens: DMR counts reference bytes, and that db's cap is unknown. if it was capped, its lookups were sparse (d x f), which would explain the mild 1.5x [guess].
2. **M11 cells [UNCLEAR] until M61.** confirm. "only 103GB is uncapped and big" holds once M22 confirms the 8GB / 16GB caps [repo: conclusion 1.2].
3. **one load per run.** confirm. RC1 has `-D` [external: a5, RC1 `classify.cc`], and ONT runs a persistent server [external: a5 N4]. so the few-read multipliers are per one-shot run.
4. **RC1 output.** confirm as reported: one outside tester, macOS/arm64, 1/4/16 threads [external: a5 N5]. M1 still compares on our data. it should use both a raw `cmp` and a whitespace-aware compare, because of the `0:0` trailing-space case.
5. **M2 8GB ≈ 1.08x without S8.** confirm: 1 / (0.98 x 0.97 x 0.97) = 1.085 [arith on luna stage gains]. a capped 8GB does few lookups, so S12's share there stays ~0 even on RC1.
6. **M9 cells (a4).**
   - H1 capped ~35x: confirm. 1,050 x 0.106 ms = 0.11 s against a 3.8 s copy [arith].
   - H2 uncapped "4-14x": correct it. at 0.1-0.5 ms latency, 10.7K faults take 1.07-5.35 s, and the copy takes 19-30 s. unpaired, that gives 3.6-28x. if a slow device is slow in both ways, the paired range is 5.6-18x [arith].
   - H2 capped 40-300x: confirm, 38-300x [arith].
   - gp3 flip: confirm. the map loses once latency passes ~5.4 ms (58 s / 10.7K) [arith on a4 N1].
7. **M20 cells.**
   - orin classify ~11x: confirm the arithmetic, (28.42 - 4.23) / (6.32 - 4.23) = 11.6x [arith]. but it uses the 4.23 s *sys* time as the load, which is an approximation [UNCLEAR].
   - H1 5.8x: confirm, 8 x 3.2 / 4.4 [arith on a4 N7].
8. **M21.** confirm. orin builds today [repo: RESULTS 1.4]; only gcc-11 `-march=native` fails [external: a3 S7].
9. **H1 dual channel.** confirm [external: a4 N7].
10. **exit tax.** confirm the arithmetic as a prediction: 282 x 111 / 16 = 1.96 s and 27.7 x 111 / 16 = 0.19 s [arith]. luna's measured 3.9-11.4 s at 4 KB [measured] is 2-6x above that scaling, so it does not transfer across machines [arith].

---

## 3. ranking

### top 10 build

1. **M2 (+M3, +M40 on RC1, + the block lookup list)**: the binary users install. the shared list makes M27b, M30 and M11 small.
2. **M20' (+M17 obey, +M62)**: cores and quota. measured 11x+ classify on orin [measured].
3. **M27**: the prologue is 0.25 day, byte-identical, and fixes the short-read / capped-db hole [external: cycle-2 a1 src 6].
4. **M4**: per-position work on every isa. the scanner is 60% of cycles on capped dbs [measured: luna gprof].
5. **M9 (+M24, M51, M33)**: cold and small-ram branches, fed with d x f.
6. **M30**: makes M9's map branch pay above qd1. it consumes the block list.
7. **M5**: gz input, real for users, 0 for our inputs.
8. **M41**: per-run pipeline, after the cpu gate, with the gap fix (section 4).
9. **M26 (+M8a as step 1)**: line crossings on uncapped ram-bound dbs. the free annotate gates it.
10. **M11 (+M64)**: uncapped dbs bigger than free ram, after M61.

just outside: M21 (+M42), M10, M31, M32, M14, M18, M16, M19, M15, M7, M6. M13 → M64. M40 → inside M2.

### top 5 measure-first

1. **M22**: lookup census, plus a line-crossing counter for M26.
2. **M1**: riders: an RC1 + M27a column, M28's short-read input, the exit column, `objdump` for M40, `TMPDIR` set, a whitespace-aware compare.
3. **the cpu gate**: 20 min. gates M4 and M41.
4. **E1**: plus the cold pair and the 2-minute qd1-vs-qd16 timing that gates M30 and M51.
5. **M61**: the DMR sweep, replacing M12.

next: M60 (20 min, framing), M43, then the orin probe on the campus visit.

---

## 4. role extras

### M41: run boundaries across ambiguous gaps

a3's mechanism holds except for one claim: "the 'changed?' branch disappears, since every run is a change by construction". that is false right after an ambiguous gap.

- classify's rule [repo: `s16_patch.py` lines 42-66]:
  - an ambiguous position pushes `AMBIGUOUS_SPAN_TAXON` and leaves `last_minimizer` and `last_taxon` untouched
  - the next clean position is compared against the *pre-gap* value
- the scanner clears its window at an ambiguous base [external: cycle-1 a3 S4], and the first clean minimizer after the gap can have the same value as the one before it.
- worked example: runs (v=17, 40 positions), (ambiguous, 31 positions), (v=17, 12 positions).
  - stock: the third run is a repeat. it does no lookup, sets taxon = `last_taxon`, does no `minimizer_hit_groups++` and no `add_kmer` [repo: s16 lines 46-66]
  - a run pipeline that treats every run as a change would look it up again and add a hit group. quick mode could then stop one group early, and the report's distinct k-mer count would change
- the fix: keep `last_clean_value` across ambiguous runs. compare at the start of every clean run that follows an ambiguous run. elsewhere the compare can be dropped.
  - that costs one compare per ambiguous gap, which is rare on reads without N bases
  - `-Q` (base-quality masking) turns low-quality bases into N, so modes.sh's masking case must be in the stream test [repo: modes list, talk track section 5]
- two more boundaries:
  - **mates.** `last_minimizer` resets per frame and per mate [repo: `s9_patch.py` line 47], so runs must never merge across mates, and the hitlist's mate separator must sit between runs
  - **taxon runs vs minimizer runs.** S15 merges adjacent equal *taxa*, which can span several minimizer runs. counting must merge on the taxon, not the run index. the hitlist must also merge equal taxa across minimizer runs, but never across an ambiguous run
- verdict: byte-identical if these three rules hold. add a test read with an N gap whose two sides share a minimizer.

### M30: the page dedupe

- **page of a lookup:** `(32 + 4 x idx) / 4096`. the 32 is the 32-byte header before the cells in the file [external: a2 cycle-1 src 2], and 4 is the cell size in bytes.
- **a probe that crosses a page:** this happens only when the home cell sits in a page's last few cells, about (probe cells - 1) / 1024. that is ~0.1% of hits and ~0.5% of misses [arith on 2.17 / 6.06 cells]. adding the next page when the home is within the last 16 cells covers it.
- **dedupe gains little at few reads:**
  - 10.7K random pages in 8GB's 1.86M pages collide in only ~0.3% of cases [arith: L / 2P]
  - at 1,000 reads uncapped (~1.07M lookups), distinct pages = P(1 - e^(-L/P)) = 0.81M, so dedupe saves 24% [arith]
- **structure:** a per-table page bitmap: 1.86M bits = 233 KB for 8GB, 27.1M bits = 3.4 MB for 103GB [arith].
  - set a bit per lookup, then scan the set bits in order. that gives the distinct pages already sorted, so adjacent pages merge into one `fadvise` range
  - adjacent pairs are rare at few reads (~L² / P ≈ 61 for 10.7K on 8GB [arith])
  - one `mincore` call on the mapping (1 byte per page) removes resident pages before any syscall, so a warm table issues none
- **verdict:** sound. the syscall count, not the dedupe, decides the cost: ~10K `fadvise` calls per few-read block. that cost is a3's to price.

### M64: compressed slices inside M11's sweep

- the decoded slice is bit-identical to the original cells, so M11's probe semantics are unchanged. byte-identical holds.
- the zero-cell bitmap codec helps M11's tail rule. the first empty cell after slice end b is the first 0 bit after b in the bitmap, found with a word scan and no value decoding. so the tail costs a few cell decodes from the next frame.
- frames (64 MB [repo: a2]) should tile slices exactly, so no frame is decoded twice.
- a side benefit: during resolve, a lookup whose home bit is 0 is a miss without touching cell data. that is 30% of misses at load 0.70 [arith]. it is small, because the cells are in ram by then.
- gain: bytes read drop by the ratio, ≥ 1.37x floor [arith: a2]. decode at ~1-2 GB/s per core [guess, a3] hides under emmc or gp3 speeds [arith on class numbers]. on fast nvme it is [UNCLEAR].
- verdict: holds. its only target is the 103GB-class uncapped db on H3 / H2-external (a4).
