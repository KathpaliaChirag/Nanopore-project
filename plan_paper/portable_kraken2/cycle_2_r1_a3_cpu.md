# cycle 2, round 1: a3_cpu

agent a3_cpu. research and writing only. i read `cycle_1_conclusion.md`, `FINAL.md`, every other `cycle_1_r2_*.md` and all five `cycle_1_r3_vote_*.md`. new ids are M40-M43.

---

## (a) sources read this cycle

none of these urls appears in any `cycle_1_*` file (grep of the folder, 2026-10-26).

| # | source | exact claim used | supports |
|---|---|---|---|
| N1 | libgomp, OMP_WAIT_POLICY, https://gcc.gnu.org/onlinedocs/libgomp/OMP_005fWAIT_005fPOLICY.html | "If undefined, threads wait actively for a short time before waiting passively." PASSIVE: "waiting threads should not consume CPU power while waiting" | M43, M18 counter |
| N2 | libgomp, GOMP_SPINCOUNT, https://gcc.gnu.org/onlinedocs/libgomp/GOMP_005fSPINCOUNT.html | "300,000 is used when OMP_WAIT_POLICY is undefined", "30 billion" when ACTIVE, 0 when PASSIVE. with more threads than cpus, "1000 and 100 spins" for ACTIVE or undefined | M43 |
| N3 | libgomp, OMP_PROC_BIND, https://gcc.gnu.org/onlinedocs/libgomp/OMP_005fPROC_005fBIND.html | "Specifies whether threads may be moved between processors". the default is TRUE if `OMP_PLACES` or `GOMP_CPU_AFFINITY` is set, FALSE otherwise. CLOSE keeps threads near the primary; SPREAD gives "a sparse distribution across the place partitions" | M43 |
| N4 | Kutenin, "bit twiddling with arm neon: beating sse movemasks, counting bits and more", arm blog, https://developer.arm.com/community/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/porting-x86-vector-bitmask-optimizations-to-arm-neon | "Arm NEON does not have a PMOVMSKB equivalent". `vshrn_n_u16(equalMask, 4)` gives a 64-bit mask "close to being a PMOVMSKB", each bit "repeated 4 times". no ctz instruction, so `rbit` + `clz`. google swissmap: "optimized all operations of hashtables by 3-8 percent" | M8b and M7 revisions |
| N5 | Chen et al., "AutoFDO: automatic feedback-directed optimization for warehouse-scale applications", https://research.google/pubs/autofdo-automatic-feedback-directed-optimization-for-warehouse-scale-applications/ | "AutoFDO achieves 85% of the gains of traditional FDO, despite imprecision due to sampling", by "sampling hardware performance monitors on production machines". "Profile data is stale by design", with compiler features "to deliver stable speedup across releases" | M42 |
| N6 | clang, LTO visibility, https://clang.llvm.org/docs/LTOVisibility.html | whole-program devirtualization (`-fwhole-program-vtables`) uses "whole-program information, so they require the entire class hierarchy to be visible". "A class defined in a translation unit built without LTO receives public LTO visibility" | M40 |
| N7 | gcc, optimize options, https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html | `-fdevirtualize`: "Attempt to convert calls to virtual functions to direct calls", on at -O2. `-fdevirtualize-speculatively` makes guarded speculative direct calls from the type inheritance graph. `-fdevirtualize-at-ltrans` is off by default | M40 |
| N8 | gcc, c++ dialect options, https://gcc.gnu.org/onlinedocs/gcc/C_002b_002b-Dialect-Options.html | `-Wsuggest-final-types`: declaring a type `final` "allows GCC to more aggressively devirtualize the polymorphic calls". "This warning is more effective with link-time optimization" | M40 |

failed: two older urls for the arm post (301, then 404). the third (N4) worked. a search snippet's "up to 2x slower" was not in the page text, so it is not used.

---

## (b) counters to cycle_1_conclusion.md

**rank moves i ask for:**
1. **M4 from rank 4 to rank 3, and my new M41 at rank 4. M9 goes to 5.**
   - M4 and M41 attack per-position work. the scanner returns once per position on every db [external: cycle-1 a1 src 1], so the absolute cost per base is the same on every db and every isa.
   - its share is largest on the dbs small boxes run. on the capped 8GB db, luna's own profile has scanner + reverse complement at 60.0% of cycles vs `Get` at 23.2% [measured: `Luna/bash_history.md` step 40, stock v2.1.3, 1 thread].
   - M9's multipliers were cut by the vote to ~3x at queue depth 1 (H1) and [UNCLEAR] (H2), all cold and few-read.
   - all three are gated by cheap tests, so the order only decides which test runs first.
2. **measure-first: insert the cpu gate at rank 3**: `perf annotate` of `ClassifySequence` plus `perf stat -e branch-misses`, on 50MB **and 8GB**, about 20 min, no build. it gates two top-5 builds (M4, M41). `ann_classify.txt` is still 0 bytes [repo: next_steps_plan E3 step 0]. the orin probe moves to 6; it rides the campus visit anyway.

**still wrong or overstated:**
1. **M21 "lets orin build at all" (`FINAL.md` rank 8, conclusion H2 cell).** orin already runs kraken2 v2.1.3 built with default flags [repo: `00_context.md` H2, `RESULTS.md` 1.4]. only `-march=native` under gcc-11 fails; gcc-9's native resolves to plain `armv8-a` [external: cycle-1 a3 S7]. correct it to "a tuned arm tier; plain builds already work".
2. **the M4 free gate runs on 50MB only.** add 8GB, the capped and scanner-bound db (the gprof numbers above).
3. **my own cycle-1 claim that neon makes M8b and M7 "pay extra" for the mask was overstated.** neon has no movemask, but a shift-narrow by 4 gives a 64-bit nibble mask in one instruction, and swissmap-style probing got 3-8% on arm that way [external N4]. what still limits M7 on neon is lane width: 2 x 64-bit. a1's top-32-bit prefix compare, with a scalar fallback on ties (~2.3e-9 per window [arith, a1]), doubles that to 4 lanes. i adopt it.
4. **M18's spin worry is now sourced.** by default a libgomp waiter spins up to 300,000 iterations before sleeping [external N2]. M43 below tests whether that matters.

---

## (c) ideas

### M41. run-length pipeline: scanner to output, one entry per minimizer run

**1. byte-identical:** yes. same lookups, counts, hitlists and calls. check with `check.sh`, `modes.sh` (12 modes) and M23's stream test.

**2. mechanism.**
- *wrong intuition:* "S15 already made counting run-length, and repeated positions are cheap because they skip the lookup."
- *what happens:* the information changes once per minimizer run, but the pipeline does per-position work in three places:
  1. the scanner returns every position
  2. S16's resolve loop runs every position: an ambiguity test; `pf[i].min != last_minimizer`, which is true about 32% of the time, so it is an unpredictable branch; a taxon test; the run counter; and `taxa.push_back(taxon)` [repo: `s16_patch.py` lines 40-85]
  3. `AddHitlistString` (2.1% [measured]) walks the per-position `taxa` vector again, only to compress it back into runs
- RC1 does the same. phase 1 pushes one token per position, `TOK_REPEAT` included, and phase 3 replays them all [external: cycle-1 a1 src 2].
- *the fix:* the scanner emits runs (value, length, ambiguous flag). each later stage handles one entry per run:
  - fill hashes and prefetches per run, which is M3 for free
  - resolve looks up per run, and the "changed?" branch disappears, since every run is a change by construction
  - counting adds the run length, which is S15
  - the hitlist merges runs with equal taxa
- the run boundary must be a *value* change, as classify defines it, not a change of the scanner's front position. ambiguous runs must not reset the "last non-ambiguous value", because classify compares across an ambiguous gap.
- quick mode stops at the first position of the run that reaches the threshold, and that position is not emitted [repo: `s16_patch.py` lines 69-73]. this maps onto the run start exactly.
- protein and translated search keep the stock path.
- *worked example:* a read has 3,189 positions [arith: 3,223 - 35 + 1]. at d = 0.316 [arith, conclusion 1.2] that is about 1,008 runs [arith].
  - today: 3,189 resolve iterations, ~3,189 x 0.32 ≈ 1,020 hard-to-predict branch outcomes, and 3,189 `taxa` entries of 8 bytes [UNCLEAR: assumes 64-bit `taxid_t`], so ~25 KB written and read again per read [arith]
  - runs: ~1,008 iterations, no change branch, ~12 KB [arith: 1,008 x 12 B]
- *sizing:* `ClassifySequence` is 25.1% of cpu = 9.7 ns per base [arith: 0.251 x 38.8 ns]. if about half of it is per-position loop overhead [guess] and runs cut iterations ~3x, the saving is ~3.2 ns per base, ~8% of cpu [arith on the guess], plus part of `AddHitlistString`'s 2.1%.

**3. gain per class.** per-base work, so the share is largest where lookups are rare or cheap.

| class | gain | tag |
|---|---|---|
| H1 | 2-8% on capped dbs and other cpu-bound cells | [guess] |
| H2 | 2-8% | [guess] |
| H3 | 2-8% where the db fits | [guess] |
| H4 | 50MB and capped 8GB/16GB 3-10%; 103GB 1-4% | [guess] |
| cold / warm | cold 1.0x (device-bound) | [guess] |

**4. days.** 3-5. it touches the scanner api, the fill/resolve loop and `AddHitlistString`. M3 comes inside it.

**5. risk.**
- correctness at three edges: ambiguous gaps, quick mode, paired reads (the mate separator in the hitlist)
- on RC1 it changes the token format, so it is an upstream design change, not a patch
- null if the resolve loop's per-position share is small

**6. kill test.** the cpu gate (section b, measure rank 3). if the per-position part of `ClassifySequence` (the change compare, `push_back`, the counters) holds under ~30% of its samples, stop. the ceiling is then ≤ 0.3 x 25.1% x 2/3 ≈ 5% [arith].

**7. sources.** repo `s16_patch.py`; conclusion 1.2 (d); cycle-1 a1 src 2 (RC1 tokens).

### M40. one `final`, and the table type fixed once per batch

**1. byte-identical:** yes, no logic change.

**2. mechanism.**
- *wrong intuition:* "LTO will devirtualize it."
- *what happens:* S19 calls `hash->PrefetchIndex(hc)` once per position and `hash->GetAt(...)` once per lookup, through `KeyValueStore*`. S12 made both virtual [repo: `s12_patch.py` line 19]. each call loads the vtable pointer, then the function pointer, makes an indirect call, and runs a prologue, the work and an epilogue.
- the compilers do not reliably remove this:
  - clang's whole-program devirtualization needs "the entire class hierarchy to be visible", and a class from a non-LTO unit gets public visibility [external N6]
  - gcc's speculative devirtualization only guesses from the type inheritance graph [external N7]
  - RC1 has two cell types (32- and 40-bit), so there is more than one target [external: cycle-1 a5 S1]
- gcc says `final` "allows GCC to more aggressively devirtualize the polymorphic calls" [external N8].
- *the fix, two parts:*
  1. mark the table class `final`
  2. in classify, dispatch on the concrete table type once per block (a template on the table type), so the inner loops call `CompactHashTable<Cell>` directly and can inline it
- on RC1 the per-read `GetBatch` is already one virtual call per read, but inside it `Get()` runs per key, and it is virtual too unless devirtualized [UNCLEAR].
- *worked example:* on S19, 50MB, `PrefetchIndex` runs 6.0e9 times [arith]. with M41 or M3 that drops to ~1.9e9 [arith: x d]. M40 then turns each remaining call into ~5 inlined instructions (the FastMod multiply-high and the prefetch) [guess], with no call, return or register spills.

**3. gain per class.** 0.5-3% wherever lookups are cpu-bound: luna 50MB, and the capped dbs everywhere. ~0 where lookups wait on ram [guess]. cold 1.0x.

**4. days.** 0.5.

**5. risk.** none for correctness. null if the compiler already devirtualized.

**6. kill test.** 10 minutes, no run: `objdump -d` on the classify binary (S19 and RC1). look in the fill loop and in `GetBatch` for indirect calls (`call *` on x86, `blr` on arm). if there are none, kill it.

**7. sources.** N6, N7, N8; repo `s12_patch.py`.

### M4, revised: `ScanRead` that emits runs

- on RC1 or S19 alike: one call per read, returning (value, length, ambiguous) runs for M41.
- inside, the branch-free min-of-5 window [cycle-1 a3 R1]. the run boundary falls out for free: the window minimum's value either changes or it doesn't.
- the window width w = k - l + 1 comes from `opts.k2d` (a4). w = 5 takes the min-of-5 path; other widths take a two-stacks fallback.
- gain and kill test unchanged (the branch-miss gate), now also run on 8GB.

### M42. a shipped sampling profile (portable PGO, on top of M21 and E3)

- **byte-identical:** yes, with `-ffp-contract=off` kept on.
- *wrong intuition:* "PGO needs a training run on every machine, so it can't be portable."
- *mechanism:* AutoFDO samples hardware counters on production machines and reaches "85% of the gains of traditional FDO". its profiles are "stale by design", yet give "stable speedup across releases" [external N5]. so one sampled profile, kept in the source tree, can steer every build. the exact flags, and whether arm can sample one at all, are [UNCLEAR].
- *worked example:* if E3's PGO gives 4-15% on luna [repo: E3 guess], a shipped profile gives ~3.4-13% [arith: x 0.85]. M4 removes the scanner's data-dependent branches, which shrinks what PGO can fix [guess].
- **gain:** ~0.85 x E3's PGO gain, every class, cpu-bound cells; cold 1.0x. **days:** 1, after E3. **kill test:** E3's s21c gains under 2%.

### M43 (measure). E5 with openmp wait, bind and output variants

- *wrong intuition:* "the 64-to-192-thread slowdown needs an online controller (M18)."
- *the mechanism, from the docs:*
  - by default, libgomp waiters spin up to 300,000 iterations before sleeping, or 100 when threads outnumber cpus [external N2]
  - threads are unbound and may move between cpus, unless `OMP_PLACES` is set [external N3]
  - kraken2 waits at `critical(seqread)`, at the output lock, and at each region's end barrier, which RC1 hits once per input file [external: cycle-1 a5 S4]
  - on an smt core, a spinning waiter takes issue slots from its sibling worker [guess]
  - whether `critical` itself uses the spin count is [UNCLEAR]
- *what to run* (no code, ~30 min, S19 and RC1, 50MB and 103GB, at 64, 96 and 192 threads):
  - default
  - `OMP_WAIT_POLICY=PASSIVE`
  - `OMP_PLACES=cores OMP_PROC_BIND=close`, and the same with `spread`
  - output to disk vs `/dev/null`. sweeps so far used `/dev/null` [repo]
- *decides:* if PASSIVE or binding removes the 192-thread loss (s10: 13.32 s vs 11.75 s at 64 [measured]), the fix is two env defaults in the wrapper and M18 is dead. spread vs close informs M14. the output column shows whether the in-order writer is a wall.

---

## (d) rankings

### top 10 build

| rank | id | one line |
|---|---|---|
| 1 | M2 (+M3) | the binary users install; S12's hash-once is the main residual inside RC1's `GetBatch` |
| 2 | M20 (+M17 obey) | 1-thread wrapper default, measured 11.4x on orin 50MB with stock [measured]; physical cores, since 192 was slower than 96 on luna for both binaries [measured] |
| 3 | M4 | per-position work, every isa, largest share on capped dbs (~60% scanner [measured gprof]) |
| 4 | **M41** | the second-largest function is per-position too; it subsumes M3 on the S19 base |
| 5 | M9 | cold and small-ram wins, after E1 |
| 6 | M5 | serial gunzip in both wrappers [external: cycle 1] |
| 7 | **M40** | half a day, one keyword plus a dispatch hoist; dies in 10 minutes if the compiler already did it |
| 8 | M8a | cheap, uncapped dbs on small-cache boxes |
| 9 | M11 | gated by M22 and M12 |
| 10 | M21 (+**M42**) | tuned arm and x86 tiers; a shipped sampled profile if E3 shows PGO helps |

below: M10, M13, M7 (now 4 neon lanes with the prefix trick, still after M4), M14, M15, M16, M18 (M43 may kill it), M19, M6.

### top 5 measure-first

| rank | id | one line |
|---|---|---|
| 1 | M22 lookup census | 5-30 min; f per db feeds every lookup estimate |
| 2 | M1 re-baseline | add `objdump` of RC1 for M40, and a perf of RC1's phases 1 and 3 for M41 |
| 3 | **cpu gate** | `perf annotate ClassifySequence` + `perf stat -e branch-misses`, 50MB and 8GB, ~20 min. it gates M4 and M41 |
| 4 | E1 | gates M9 |
| 5 | M12 | gates M11 |

next: the orin probe (campus), then M43 (~30 min, decides M18 and part of M14).
