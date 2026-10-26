# cycle 2, round 1, a1_dsa (data structures and algorithms)

nothing was run. tags follow `00_context.md` section 6. ids follow `cycle_1_conclusion.md`. new ids start at M26.

---

## (a) sources read this cycle

all fetched 2026-10-26. none appears in a `cycle_1_*` file. the only earlier mention is a4's failed AMAC fetch, so its claims were never used.

1. **Kocberber, Falsafi, Grot, "asynchronous memory access chaining" (AMAC), pvldb 9(4) 2015.** https://www.vldb.org/pvldb/vol9/p252-kocberber.pdf, read through `r.jina.ai` because the pdf itself is binary. claims used:
   - existing group prefetching (GP) and software-pipelined prefetching (SPP) fix N stages per lookup, and "lookups might require more than N stages as the data structure is irregular"
   - AMAC keeps "all in-flight requests ... in a software-managed circular buffer", so it can "initiate a new lookup as soon as any of the in-flight lookups complete"
   - hash join on a xeon x5670, uniform keys: GP 2.8x, SPP 3.8x, AMAC 4.3x. skewed: GP 1.4-2x, SPP 1.2-2.2x, AMAC "3x on average"
   - "little sensitivity to the exact number of memory lookups beyond eight or so"

   supports M26, and the counter to M19.
2. **Psaropoulos et al., "interleaving with coroutines: a practical approach for robust index joins", pvldb 11(2) 2017.** https://www.vldb.org/pvldb/vol11/p230-psaropoulos.pdf, via `r.jina.ai`. claims used:
   - "coroutines make interleaving practical for use in real DBMS codebases"
   - the overhead is "equivalent to two function calls"
   - binary search over arrays bigger than the cache: GP 2.7-3.7x, coroutines and AMAC 2.0-2.4x
   - delta runtime improved "for all dictionary sizes", including a 10% cut at 1 MB

   supports M26's implementation choice.
3. **Polychroniou, Raghavan, Ross, "rethinking SIMD vectorization for in-memory databases", sigmod 2015.** http://www.cs.columbia.edu/~orestis/sigmod15.pdf, via `r.jina.ai`. claims used:
   - "process a different key per SIMD lane using gathers"
   - finished lanes are refilled "by selectively loading new keys"
   - on haswell, a "smaller speedup for cache resident hash tables"
   - interleaved build and probe on xeon phi: 2.6-4x in L1, 2.4-2.7x in L2, "1.2–1.4X out of the cache"

   supports the counter to M7 and M8b.
4. **smhasher `MurmurHash3.cpp`.** https://raw.githubusercontent.com/aappleby/smhasher/master/src/MurmurHash3.cpp. claim used: `fmix64` is three `k ^= k >> 33` steps and two 64-bit multiplies (`0xff51afd7ed558ccd`, `0xc4ceb9fe1a85ec53`). supports the hash note in section b.
5. **kraken2 master `src/kv_store.h`.** https://raw.githubusercontent.com/DerrickWood/kraken2/master/src/kv_store.h. claim used: kraken2's `MurmurHash3(hkey_t key)` is exactly that `fmix64`. `KeyValueStore` now has pure virtual `Get` and `GetBatch`. supports the hash note.
6. **kraken2 v2.18.0-RC1 `src/compact_hash.h`, `GetBatch`.** https://raw.githubusercontent.com/DerrickWood/kraken2/v2.18.0-RC1/src/compact_hash.h. this was re-fetched to answer a new question. claims used:
   - the only prefetch is `if (i + PREFETCH_DIST < n) { ... __builtin_prefetch(&table_[hc % capacity_], 0, 1); }`, then `out[i] = Get(keys[i])`
   - "there is no prologue. keys 0 through PREFETCH_DIST-1 are never prefetched"

   supports M27.

---

## (b) counters to cycle_1_conclusion.md

**moves i want in the build list:**
1. **add M27 (new) at rank 3.** it is a 0.25-day, byte-identical upstream fix. on short reads and capped dbs, RC1 issues almost no useful prefetch (section c).
2. **merge M8a into M26 (new), keeping rank 6.** M8a guesses which lookups will cross into the next line, and pays 12.5-37.5% extra line fetches for the guess [arith]. M26 prefetches the next line only when a probe actually reaches it. M8a stays as M26's 0.25-day first step.
3. **M13 drops below the line**, displaced by M27. it is cold-only, ≥ 1.37x on the load, and fights M9's map branch [repo: conclusion row 10].

**facts still wrong or weak in the conclusion:**
- **section 1.2, "a gprof undercount of `Get` could also explain part of it".** the WSL2 db is named. it is "`~/eskape_db` - pre-built 8 GB standard k2 database" [repo: `dorado-kraken-research/docs/knowledge_base.md` 18.1]. a3's vote said the gprof file never names its db. the file does not, but its setup section does.
  - so two capped standard-8 runs, on two machines with two builds, agree: 1/36 and 1/30 lookups per position [repo]
  - a4's 7.2 µs per `Get` call fits the same setup note: the run "stays at 0 for ~10 minutes while the OS lazily pages the 8 GB mmap'd database" [repo: 18.2]. a profiling timer would charge that fault time to the faulting `Get` [guess]
  - so the undercount is the weaker reading. M22's exact counters settle it either way
- **section 1.3 and row 1 (M2).** the hash. kraken2's `MurmurHash3` is `fmix64`: 2 multiplies and 3 xor-shifts [external: src 4, 5]. the slot is `hc % capacity`, so a cheaper hash moves every key, which needs a rebuild and loses byte identity. keep the hash and compute it once per real lookup.
  - RC1 hashes a real lookup up to 3 times on a capped db: once in phase 1 for the cap check, once for the prefetch, once in `Get` [external: src 6; R1 src 2]
  - on an uncapped db it hashes twice, because the cap check short-circuits
  - removing the extras belongs inside M2
- **below the line, M19 (prefetch-depth probe).** AMAC's "little sensitivity ... beyond eight or so" [external: src 1] agrees with luna's s20 null [measured] and upstream's default of 8 [external]. one more reason to leave it below the line.
- **below the line, M7, and M8b inside M8.** multi-key simd probing needs gathers. its gain shrinks to 1.2-1.4x out of cache even on xeon phi, and it is smaller for cache-resident tables on haswell [external: src 3]. neon has no gather instruction [guess, not fetched]. M8b's single-key 64-byte compare needs no gather, but a hit probes only 2.17 cells [arith], so it saves little (a3). both stay below the line.
- **row 7 (M11), "record design disputed".** i concede to a2's merged design:
  - one table sweep, 4-byte in-slice offsets in arrival order, tokens kept in ram when they fit, re-scan only when they do not [repo: `cycle_1_r2_a2_storage.md` 2.2]
  - my 16-byte records are needed only for M25's dedupe
  - "probe runs past slice edges" is not a risk: read past the slice end to the first empty cell, where every linear probe stops [external: cycle-1 a1 src 3]
  - on a capped db (f ≈ 0.09), the full input's queue is ~0.2B x 4 B ≈ 0.8 GB [arith], so no spill at all

---

## (c) ideas

### M27. prefetch prologue in upstream `GetBatch`, then pool lookups across reads

1. **name.** `GetBatch` prologue, plus cross-read pooling. **byte-identical**: every `Get` result is unchanged, and only the prefetch timing moves.
2. **mechanism.**
   - wrong intuition: "upstream prefetches 8 keys ahead, so every lookup is covered."
   - real: RC1 calls `GetBatch` once per read, on that read's distinct, uncapped minimizers [external: R1 src 2]. inside it, key i + 8 is prefetched while key i is resolved, and nothing prefetches keys 0-7 [external: src 6]. so the first 8 lookups of every read are plain demand misses, one after another.
   - lookups per read = (read length - 34) x d x f, with d ≈ 0.316 and f ≈ 0.09 on capped dbs [repo: conclusion 1.2]. worked example [arith]:

| read | uncapped db | capped db |
|---|---|---|
| nanopore, 3,223 bp | ~1,008 lookups, 8 unprefetched (0.8%) | ~90-105, 8 unprefetched (8-9%) |
| illumina, 150 bp | ~37 lookups, 8 unprefetched (22%) | ~3, none prefetched |

   - so a short-read user on a prebuilt capped db, which is the typical laptop setup [guess], gets no prefetch from RC1.
   - **fix a (0.25 day):** before the loop, prefetch keys 0 to min(8, n) - 1. those 8 misses then overlap instead of running in series. per read that is roughly 8 x ~107 ns ≈ 0.86 µs down to about one miss [arith on external spr latency via a4, guess on overlap].
   - **fix b (2-3 days):** collect the lookups of a whole block of reads, call `GetBatch` once, and replay each read in order. that removes the warm-up completely.
   - S19 does not have this hole, because S16's first batch per read is resolved only after a second batch is filled [repo: `s16_patch.py`].
3. **gain per class.**
   - our nanopore data, any class: under 1% [arith: 0.8% of lookups unprefetched].
   - short reads on uncapped big dbs (103GB-class), H4 and H1: about 5-7% of classify [arith on luna's 1.46x 1-thread prefetch gain x 22%, crude].
   - short reads on capped dbs, every class: 0-10% [guess]. lookups are sparse there, so lookup waiting is a smaller share of the run.
   - H2 and H1, where every db misses the cache: the high end of each range [guess].
   - cold vs warm: none.
4. **days.** a: 0.25. b: 2-3.
5. **risk.** a cannot change output. b changes memory use per block. null if the out-of-order core already overlaps those 8 misses [guess]. novelty: a small upstream bug, so the value is real only for short-read users.
6. **cheapest kill test.** M28 below.
7. **sources.** 6, R1 src 2.

### M26. AMAC-style `GetBatch`: lookups that cross a line yield instead of stall (absorbs M8a)

1. **name.** AMAC-style `GetBatch`. **byte-identical**: each lookup checks the same cells in the same order as `Get`, and results are written by index.
2. **mechanism.**
   - wrong intuition: "prefetching the home line covers the probe." it covers the probe only when the probe ends inside that line.
   - real: at load 0.70, 7% of hits and 32% of misses walk into a line that nobody prefetched [arith]. on one measured sample with 67% misses, that is 0.24 extra ram trips per lookup [arith]. S9, S16 and RC1's distance-8 are GP and SPP: they assume one stage per lookup. AMAC's paper says these break when "lookups might require more than N stages" [external: src 1].
   - **the change:** keep a circular buffer of W ≈ 8-12 lookup states (key, hc, idx, out slot). check the cells of the current line from idx:
     - match, or an empty cell: write the answer, start the next key and prefetch its home line
     - reached the line's end: prefetch the next line, store idx, move to the next entry
   - worked example: a miss whose home is cell 13 of its line, and whose run ends 6 cells later. today: cells 13, 14 and 15, then a stall of ~107 ns [external, spr, via a4] for the next line. with M26: the next line is requested at cell 15, and the core works on 8-11 other lookups while it arrives.
   - implementation: a hand-written state machine. C++20 coroutines would do the same job ("two function calls" of overhead [external: src 2]), but RC1 builds as C++17 [external: a3 cycle 1].
3. **gain per class.**
   - AMAC over SPP on a uniform hash-join probe: 4.3 / 3.8 = 1.13x [arith on external, xeon x5670, chained buckets, not kraken2].
   - for kraken2 [guess]:
     - H1 and H2, where every uncapped db is ram-bound: 0-8%
     - H4: 0-8% on 103GB, 0 on 50MB (it sits in L3)
     - capped dbs: ~0, because lookups are sparse
   - no extra lines are fetched, unlike M8a's +12.5-37.5% [arith].
   - cold: none.
4. **days.** 1.5-2, inside RC1's `GetBatch`. it can go upstream.
5. **risk.** more code in the hot loop. null if the hardware's adjacent-line prefetch or out-of-order execution already hides the crossings [UNCLEAR].
6. **cheapest kill test.** the free gate already listed: `perf annotate GetAt` on the saved `perf_s14_103.data`. plus one counter of line crossings per lookup in M22's throwaway build. kill it if crossings cost under 2% of classify.
7. **sources.** 1, 2.

### M28 (measure). a short-read axis for the benchmark

1. byte-identical check: compare S19's output with RC1's on the same cut input.
2. **mechanism.**
   - wrong intuition: "our 16 cells cover the input-size axis." they cover read *count*, not read *length*. every read here is ~3.2 kb nanopore [repo].
   - per-read costs grow as reads shorten: pipeline warm-up (M27), `ResolveTree`, one output line per read. kraken2's typical input is short reads [guess].
   - test: cut `reads_hac.fastq` into 150 bp pieces with awk, which is deterministic. run S19, RC1 and RC1 + M27a on the 8GB and 103GB dbs, 3 reps.
3. **gain.** none itself. it decides M27, and whether any luna ratio transfers to short-read users.
4. **days.** ~30 min.
5. **risk.** pieces cut from long reads are not real illumina errors or quality profiles. that is fine for timing, not for accuracy.
6. **kill.** if RC1 + M27a is within 2% of RC1, drop M27.
7. **sources.** 6, repo.

### M11, revised: a2's merged design, plus the exact tail rule

the design is in section b. no new number. its rank stays 8 (cycle-1 rank 7, pushed down one by M27), gated by M12.

### the hash: no idea, a firm "do not"

`fmix64` costs two multiplies [external: src 4, 5], and it is fixed by the db layout. changing it means a rebuild with different output. the only lever is computing it once per real lookup, which is inside M2 and M3.

---

## (d) rankings

### top 10 build

1. **M2 (+M3)**: the residual stages onto upstream, with one hash per real lookup. the binary users install.
2. **M20**: default threads = physical cores. measured 11.4x / 4.5x on orin for default users [measured].
3. **M27 (new)**: the `GetBatch` prologue. 0.25 day, byte-identical, fixes a short-read and capped-db hole upstream.
4. **M9**: the load planner, with positions x d x f.
5. **M4**: the branch-free min-of-5 scanner. every isa.
6. **M26 (new, absorbs M8a)**: an AMAC-style probe. no speculative line fetches. gated by the GetAt annotate.
7. **M5**: parallel gunzip. 0 for our inputs, real for users.
8. **M11**: a2's merged design, gated by M12.
9. **M21**: portable build tiers.
10. **M10**: huge pages that land, part A first.

below the line: M13 (cold only, fights M9), M15, M16, M18, M19, M14, M7, M6, M25 (measure first).

### top 5 measure-first

1. **M22**: the lookup census. add one counter, line crossings per lookup, for M26.
2. **M1**: re-baseline. add two riders: an RC1 + M27a column, and the M28 short-read input.
3. **E1**: `-M` vs S19 per db, plus the cold pair.
4. **M12**: small-ram emulation, capped and uncapped dbs.
5. **the orin probe**: on the first campus visit.

M28 (~30 min) rides inside M1. so the measure order is unchanged from cycle 1, and i agree with it.
