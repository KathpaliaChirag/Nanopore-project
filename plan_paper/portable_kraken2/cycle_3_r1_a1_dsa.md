# cycle 3, round 1, a1_dsa

nothing was run. tags follow `00_context.md` section 6. new ids: M70-M72.

---

## (a) sources read this cycle

all fetched 2026-10-27. i grepped the folder, and none appears in any `cycle_1_*` or `cycle_2_*` file.

1. **Balkesen, Teubner, Alonso, Özsu, "main-memory hash joins on multi-core cpus: tuning to the underlying hardware", icde 2013.** https://www.comp.nus.edu.sg/~hebs/course/cs6284/papers/Balkesen-icde2013.pdf, via `r.jina.ai`. claims used:
   - "join algorithms that are hardware conscious perform better than hardware-oblivious approaches"
   - "the number of available TLB entries defines an upper bound on the number of partitions" per pass, so multi-pass radix partitioning keeps "the partitioning fan-out" under it
   - after partitioning, hash tables "are very small and always fully cache resident"
   - radix join is ~3.5x faster than no partitioning on intel, ~2.5x on amd and sun
   - "no partitioning does very well when the build relation is very small compared to the large relation"
   - smt "does not help the no partitioning strategy at all or only brings negligible improvement"

   supports M70 and M72, plus a note on M20'.
2. **nvidia, "cuda for tegra" app note.** https://docs.nvidia.com/cuda/cuda-for-tegra-appnote/index.html. claims used:
   - "both the CPU (Host) and the iGPU share SoC DRAM memory"
   - "I/O coherency is supported on Tegra devices starting with Xavier SOC"
   - pageable `malloc` memory is directly gpu-accessible "only ... from Thor SoC onwards"
   - `cudaHostRegister()` "is supported only on platforms which are I/O coherent". registered memory is uncached on the igpu without full coherency, which arrives with Thor
   - pinned memory is "preferable for large buffers if the access pattern is not cache friendly on iGPU"

   orin is compute capability 8.7 in the doc's own deviceQuery example. supports M71.
3. **nvidia cuCollections readme.** https://github.com/NVIDIA/cuCollections. claim used: "`cuco::static_map` is a fixed-size hash table using open addressing with linear probing by default". so kraken2's layout is a standard gpu table layout. supports M71.
4. **Awad et al., "better gpu hash tables", arxiv 2108.07232.** https://arxiv.org/abs/2108.07232. claims used: their bucketed cuckoo table needs "at most 1.39 and 2.8 average probes per key" for positive and negative queries, and only "the probing scheme is the factor affecting the performance". the abstract gives no throughput figure, so i quote none. supports the M71 note on probe counts.

failed or empty: the cuCollections readme gives no throughput numbers, and the Awad abstract gives none either. so every gpu speed below is [UNCLEAR].

---

## (b) counters to cycle_2_conclusion.md

**list unchanged: agree.** both the build list and the measure list.

- the R3 fixes match my R3 file (150 bp: all lookups unprefetched on a capped db).
- the other agents' fixes (M20' at 96 threads, M9 H2 capped ~36-290x, the gp3 instance cap, Coriolis having no in-ram baseline) re-derive [arith].
- nothing new this cycle moves a rank. the three new ids below are measure-first, and they sit behind the current top 5.

two small additions, neither a reorder:
- **support for M20' using physical cores, not smt siblings.** in Balkesen's optimized no-partitioning join, which is random probes into a big table like kraken2's lookups, smt gave "negligible improvement" [external: src 1]. that matches luna: 192 threads slower than 96 [measured].
- **the per-block lookup list (M2's rider) now has more consumers.** M70, M71 and M72 need it too. one more reason to build it first.

---

## (c) ideas

### M70 (measure). sort-probe-unsort against batched random probes

1. **name.** a radix-partitioned block lookup microbenchmark. it is a measurement, and its output is a decision rule. its build is M72.
2. **mechanism.**
   - wrong intuition: "a hash table is already the best layout for random lookups, so sorting the queries cannot help."
   - real: for one lookup, that is true. for a *batch*, a database hash join partitions both sides so each probe hits the cache. Balkesen measured 2.5-3.5x over no partitioning [external: src 1].
   - kraken2's table is already in slot order, so the "build side" needs no partitioning. only the block's queries do.
   - the steps:
     1. radix-partition the block's lookups by slot range (one pass if the fanout stays under the tlb limit [external: src 1])
     2. for each table slice that fits in the last-level cache, probe its queries: every probe is a cache hit
     3. scatter the answers back to their positions with a second radix pass
   - sorting also makes duplicates adjacent, so cross-read repeats (up to 70% within one 104,918-read file [arith on repo M5 + d]) are found for free. that is M25's dedupe at no extra cost.
   - **the byte budget is roughly equal:**
     - random path: about one 64 B line per lookup, plus 0.24 extra lines for crossings [arith]
     - sort path: about 4 x 16 B = 64 B of sequential traffic per lookup (write and read in two passes), plus one table read per block
   - so the sort path wins only where random lookups are latency-limited well below sequential bandwidth. that is the number to measure.
   - **worked example: orin, 50MB db.**
     - the table is 48.8 MB against 2 MB of L3 per cluster plus a 4 MB system cache [repo, external via a4], so even 50MB misses there (79-83% llc miss [repo: RESULTS 1.4])
     - a 100,000-read block on this uncapped db has ~100M lookups [arith: 3,189 x 0.316 x 1e5]. the table stream per block is 48.8 MB, ~5% of the records' 1 GB of partition traffic [arith]
     - 1 MB slices make a fanout of 49, which is one pass [arith]
     - so every probe becomes an L2/L3 hit, at the price of ~64 B of sequential traffic per lookup
   - the inverse case is a capped 8GB db with a 10-read block, ~900 lookups: there the table stream (7.6 GB) dwarfs the queries. this is Balkesen's "build relation very small compared to the large" situation, reversed, so the random path wins [arith].
3. **gain per class.** none itself. predicted direction [guess]:
   - most likely to win: panel dbs (50MB-class) on small-cache boxes (H1, H2, H5) at full input
   - maybe: H4 103GB at full input, where lookups ≈ table lines (1.9B vs 1.73B [arith])
   - never: few-read runs
4. **days.** 1. add two arms to the trie brief's stage-0d `structbench.cpp` [repo]: "batched random prefetch" (S16-like) vs "partition, probe per slice, unpartition", at 8.75M, 1B and 4B keys, on luna and orin.
5. **risk.** the result may be a clean null: equal bytes and good prefetch mean no win. that would still settle M25 and M72 for 1 day.
6. **kill.** if sort-probe-unsort is not ≥ 1.3x faster per lookup at the 8.75M-key size on orin, kill M72 for panel dbs.
7. **sources.** 1; repo trie brief section 7.

### M71 (measure, then build). orin igpu lookups over the shared table, zero-copy

1. **name.** gpu-assisted `GetBatch` on jetson-class socs. **byte-identical**: the kernel runs `GetAt`'s integer logic unchanged (linear probe, compacted-key compare, stop at an empty cell), with results by index.
2. **mechanism.**
   - wrong intuition: "a gpu would need the table copied into its own memory, and 15 GB doesn't fit."
   - real: on tegra "both the CPU (Host) and the iGPU share SoC DRAM memory" [external: src 2]. orin is i/o coherent (cc 8.7 ≥ 7.2 [external: src 2]).
   - the copy path's table is a `posix_memalign` buffer [repo: S14]. `cudaHostRegister` makes it gpu-visible with no copy [external: src 2]. it is then uncached on the igpu, which costs little for random lookups that are "not cache friendly" anyway [external: src 2].
   - open addressing with linear probing is cuCollections' default gpu layout [external: src 3], so kraken2's table needs no format change.
   - so: the cpu scans a block and builds the lookup list (M2's rider). one kernel launch probes the whole list, with thousands of requests in flight, far beyond what 12 a78ae cores can keep outstanding [UNCLEAR: a78ae miss buffers]. the cpu then replays in order.
   - worked example: a 480-read block on an uncapped db is ~484K lookups [arith]. one launch at a [guess] ~10 µs launch cost is ~0.02 ns per lookup. random 64 B reads against 204.8 GB/s peak lpddr5 [external, via a4]: even at an assumed 25% efficiency [guess], that is ~0.8B lines/s, about 0.6 s for the full uncapped input [arith on guess].
   - the cpu baseline on orin is [UNCLEAR]. stock took ~424 ns per lookup at 1 thread [arith, a4].
3. **gain per class.**
   - H2 only. [UNCLEAR] until the probe below, on uncapped dbs at full input.
   - ~0 on capped dbs (lookups are sparse) and on few-read runs.
   - **0 while dorado basecalls on the same gpu**, so a live pipeline gains nothing [guess].
   - H1/H5 with a discrete gpu: excluded, because a table copy across pcie is a different design.
4. **days.** probe 0.5. build 3-5: a cuda path, a cpu fallback, and a build flag.
5. **risk.**
   - a second toolchain (cuda on jetpack)
   - `cudaHostRegister` on a 15 GB buffer: limits are [UNCLEAR]
   - the GPU and CPU share the memory controller, so the scanner slows a little [guess]
   - for a portable kraken2 it is an optional backend, never the default
6. **kill.** a 50-line cuda microbenchmark on orin: random 4-byte reads at a uniform slot of a 15 GB registered buffer, one per thread, with 10M lookups. compare against 12 cpu threads with batched prefetch on the same buffer. kill if the gpu is < 2x the cpu per lookup.
7. **sources.** 2, 3, 4.

### M72 (build, only if M70 passes). in-ram sweep mode: run M11's machinery on a table that fits

1. **name.** sorted block lookup for big inputs on small-cache boxes. **byte-identical**, for the same reason as M11.
2. **mechanism.** M11 already does partition by slice, a sweep, and an ordered replay, for dbs bigger than ram. if M70 shows that sorted probing beats random probing in ram, the same code path runs warm. slices are sized to the last-level cache (sysfs [external, via a4]), not to free ram. there is a dedupe in sorted order.
3. **gain.** [UNCLEAR], from M70. target: 50MB-class panel dbs on H1, H2 and H5 at full input. H4 103GB only if M70's 4B-key arm wins.
4. **days.** +1-2 on top of M11 (switch, cache-sized slices, dedupe).
5. **risk.** it inherits M11's complexity. off for few-read runs and capped dbs by construction.
6. **kill.** M70.
7. **sources.** 1.

---

## (d) rankings

### top 10 build (unchanged from cycle 2)

1. M2 (+M3, M27a, M40, per-block lookup list)
2. M20' (+M17, M62)
3. M9 (+M24, M51, M33)
4. M4
5. M30
6. M41
7. M5
8. M26 (+M8a)
9. M11 (+M64)
10. M21 (+M42)

below the line, new: M72 (waits on M70), M71 (waits on its probe; H2 only).

### top 5 measure-first (unchanged)

1. M22
2. M1 (with its riders)
3. E1 (with its riders)
4. the cpu gate
5. M61

next in line: M70 (1 day, structbench arms). M71's probe goes with the campus visit, alongside the orin probe.
