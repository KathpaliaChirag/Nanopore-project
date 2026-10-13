# A minimizer→taxon lookaside cache for kraken2: does it work?

**Answer: no, in all three forms tested. The better it works, the slower it runs.**

Machine: Intel i7-11700, 8C/16T, L1d 48 KB/core, L2 512 KB/core, L3 16 MB shared,
`powersave` governor. kraken2 2.17.1 (project fork). Baseline DB
`eskape_32bit_fork` — 12.2 M cells, 8.90 M occupied, 48.8 MB, `key_bits=26`,
`value_bits=6`. Primary workload `pod5_2.fastq` — 151,591 reads, 499.98 Mbp,
**160,625,038 lookups**, 42.8 M distinct minimizers. All runs `-p 16 -g 2 -T 0`.

---

## 1. The proposal

Store `minimizer → taxon` in a small table that stays resident in cache. On each
lookup, probe the table first; only on a miss go to the 48.8 MB hash table in
DRAM. Frequently-used minimizers would then never leave cache.

Three progressively stronger forms were built and measured:

1. **Single direct-mapped table**, one cache tier at a time (L1 4 KB / L2 256 KB / L3 4 MB)
2. **Set-associative**, 1–16 ways
3. **Stacked hierarchy** — L1+L2+L3 simultaneously resident, probed in order

All are populated **offline by an oracle**: a first pass counts minimizer
frequency over the very file the timed pass then classifies. This is not
deployable, but it is the ceiling — no online policy can beat knowing the answer
in advance.

## 2. Where the time actually goes

| | |
|---|---:|
| `CompactHashTable::Get` | 43.4% of cycles |
| DRAM stall (`cycle_activity.stalls_l3_miss`) | **23.9% of cycles** |
| DRAM accesses per lookup | **0.936** |
| L3 hit rate (hardware, unassisted) | 41.3% |
| memory-level parallelism | **1.243** of ~12 |

Two facts frame everything below.

**The hash table is already near-optimal on probe count.** At 0.936 DRAM
accesses per lookup you cannot go below 1 for a table that does not fit in
cache. `-DLINEAR_PROBING` makes the probe chain walk adjacent cells — 16 per
64-byte line — so collisions rarely cost a second line. Every classical hash
table improvement (cuckoo, Robin Hood, hopscotch, Swiss) targets probes per
lookup, and there is nothing left to reduce.

**24% is the hard ceiling.** A table with hit rate *h* can save at most
*h* × 23.9% of runtime. This bound is used throughout as a falsifiability test.

## 3. Form 1 and 2 — single tier, 1 to 16 ways

30 combinations (3 tiers × 2 formats × 5 associativities), median of 4
interleaved reps, table-build cost subtracted from all counters.

| configuration | hit rate | time | vs stock | DRAM/lookup | L3 miss | MLP |
|---|---:|---:|---:|---:|---:|---:|
| stock | — | 2.872 s | — | 0.936 | 58.7% | 1.243 |
| L3 compact 1-way | 22.35% | 2.812 s | −2.11% | 1.071 | 42.5% | 1.384 |
| L3 compact 4-way | 24.42% | 2.843 s | −0.99% | 0.949 | 37.9% | 1.318 |
| L3 compact 16-way | 24.98% | 3.056 s | **+6.42%** | 0.861 | 35.6% | 1.252 |
| L3 exact 16-way | 8.62% | 3.008 s | **+4.72%** | 0.997 | **18.0%** | 1.559 |
| L2 compact 1-way | 3.27% | 2.860 s | −0.42% | 0.925 | 40.8% | 1.238 |
| L1 compact 1-way | 0.65% | 2.843 s | −1.03% | 0.929 | 58.3% | 1.238 |

**No speedup here is established.** Seven of the 30 rows claimed a speedup
*larger than physically possible* — `L1 exact 1-way` read −1.60% from a 0.48%
hit rate against a −0.11% ceiling. It cannot avoid 1.6% of the work by skipping
0.48% of lookups. Those readings put the **noise floor at ±1.5%**, and every
negative figure in the table sits inside it.

The cause is not heat: repeated runs of the *same* binary are **bimodal**,
clustering at 2.33–2.39 s and 2.85–3.14 s — a 23% gap matching turbo versus base
frequency under `powersave`. Both stock and patched binaries land in both modes.

Two real effects survive the noise floor:

- **`L3 exact 16-way` achieves the best L3 miss rate in the entire study — 18.0%
  against stock's 58.7% — and runs 4.72% slower.** Its 16 × 16 B = 256 B set
  spans **four cache lines**; every probe fetches four lines instead of one.
- **`L2 compact 16-way` stays within one line and still loses 7.59%**, because
  16 tag comparisons on the ~75% of probes that miss cost more than a 3.42% hit
  rate returns.

Two distinct failure modes: cache-line count, and tag-scan count.

## 4. Form 3 — the stacked hierarchy

All three tiers resident at once (4.36 MB total), probed L1 → L2 → L3 → hash
table. Population is exclusive: hottest-first, each record to the fastest tier
with a free way. Full grid L3 ∈ {1,2,4,8,16} × L2 ∈ {1,2,4,8} × L1 ∈ {1,2,4} =
**60 combinations**, mean of 3 interleaved reps.

### 59 of 60 are slower than stock

| L3 ways | hit rate | mean time | vs stock | DRAM/lookup | MLP |
|---:|---:|---:|---:|---:|---:|
| stock | — | 2.938 s | — | 0.950 | 1.244 |
| 1 | 23.65% | 3.043 s | **+3.57%** | 1.063 | 1.385 |
| 2 | 24.94% | 3.058 s | **+4.09%** | 1.053 | 1.379 |
| 4 | 25.64% | 3.082 s | **+4.89%** | 0.944 | 1.324 |
| 8 | 26.01% | 3.176 s | **+8.09%** | 0.891 | 1.282 |
| 16 | 26.19% | 3.334 s | **+13.46%** | 0.857 | 1.258 |

**L1 and L2 associativity are dead parameters.** Across an entire row the hit
rate moves 0.02 pp; down a column it moves 2.54 pp. Their misses are *capacity*
misses — 1,024 and 65,536 entries against 42.8 M distinct minimizers — and
associativity only recovers *conflict* misses. 48 of the 60 combinations are
duplicates of the 5 that differ.

### Stacking does raise the hit rate

| | hit rate |
|---|---:|
| L3 alone, 1-way | 22.35% |
| L3 alone, 16-way | 24.98% |
| stacked, L3 16-way | **26.19%** |

Split at the best point: L1 0.65% + L2 2.80% + L3 22.75%. L2 earns its keep on
hit rate.

### And that is precisely why it loses

**correlation(hit rate, runtime penalty) = +0.601.**

Every memory metric improves monotonically with L3 ways — DRAM per lookup falls
1.063 → 0.857, crossing *below* stock's 0.950 — while runtime rises +3.57% →
+13.46%. Three sequential dependent probes on the ~74% of lookups that miss all
tiers cost far more than 2.5 pp of extra hits returns.

Unlike §3, **zero rows claim a speedup exceeding the physical ceiling**, so this
sweep is internally consistent. The single fastest row (`l1=1,l2=1,l3=1`,
−3.83%) has a spread of 0.555 s across its three reps — the largest in the table.
**Every configuration with a spread below 0.05 s is slower than stock.**

## 5. Why it fails — three structural reasons

**5.1 Reuse is at the wrong distance.** Exact LRU stack distances over the real
lookup stream: a 1,024-entry cache hits 0.34%; 65,536 hits 2.06%; useful rates
need ≥1 M entries. Reads arrive in random genome order, so a minimizer's repeats
scatter across millions of intervening lookups. 63.4% of distinct minimizers are
seen exactly once (29.9% of all lookups) — nanopore error, unique, never
recurring.

**5.2 A memo table cannot be denser than what it memoises.** kraken2's cell
already packs fingerprint + taxid into 4 bytes at 73% load factor. For any byte
budget, spending it on *more database* dominates spending it on a *cache of the
database*. Visible directly: `L3 exact` moves 1.158 DRAM accesses per lookup,
*worse than stock*, because 16-byte entries buy only 262 K slots for 4 MB and
that table evicts more database than its 8.20% hit rate recovers.

**5.3 The hardware already does this, better.** L3 holds 16/48.8 = 32.8% of the
DB and achieves a 41.3% hit rate — beating uniform random by 8 points. That gap
*is* frequently-accessed minimizers being retained, by 16 MB of true hardware
LRU at zero instruction cost. A software table duplicates a sliver of that while
charging 3–5 cycles per lookup and evicting the database it meant to protect.

**Hit rates also fall as input grows**: L3 compact 1-way drops 25.13% (pod5_15,
91 Mbp) → 22.35% (pod5_2, 500 Mbp). The technique degrades with more data.

## 6. What works instead

| lever | measured | effort |
|---|---:|---|
| **`-M 4000000` on a 24-bit build** (12.0 MB DB, fits L3) | **−26.7%** | build flag, no code |
| **Huge pages for the hash table** | untested | one `madvise` line |
| **Batched/prefetched lookups** | untested | loop restructure |
| Lookaside cache, any form | **not established / +13%** | done, closed |

**`-M` is the real result.** Identical false positives to the 32-bit baseline,
−1.3 pp sensitivity, DRAM stalls collapse 26.8% → 6.6%. It reaches the goal the
lookaside was aiming at — an L3-resident database — by shrinking the table
rather than shadowing it. *Caveat: measured on one file at one capacity; needs
validation across all 16 pod5 files and a 4–5 M capacity sweep.*

**Huge pages** target a cost nothing else does. `hash.k2d` needs **11,914 4 KB
pages** against a 2,048-entry STLB: 27.2 M page walks against 28.0 M L3 misses —
essentially every probe misses the TLB *and* the cache. `walk_active` is 41% of
cycles at `-p 16` and **52.6% at `-p 1`**; 99.7% of walks are 4 KB. In 2 MB pages
the DB is **24 pages** and fits the 32-entry L1 dTLB. It gets none today
(`AnonHugePages: 0 kB`, THP=`madvise`). Cannot change results.

**MLP is 1.243 of ~12.** Every lookup's DRAM latency is fully exposed because
the loop is a strict serial dependency. Batching 8–16 minimizers and issuing
prefetches together is the standard fix, and 2,980 bp nanopore reads mean the
window fits inside one read. The `GetWithHash(key, hc)` entry point added for
this work is the hook it needs.

## 7. Methodology notes

- **Physical-ceiling test.** Every claimed speedup is checked against
  *h* × 23.9%. This caught seven impossible rows in §3 and is what established
  the ±1.5% noise floor. Recommended for any future timing work on this box.
- **Resolving 1–2% here requires the `performance` governor** or pinned
  frequency; `powersave` produces bimodal timings with a 23% gap.
- **Interleave, never run sequential blocks.** An early sequential-block
  benchmark produced a false 24% result that reversed on re-measurement.
- **Subtract the table-build cost** from every counter — loading a 513 MB
  profile and doing 1 M `Get` calls is not part of classification.
- **`-g 2` is mandatory.** Raw `classify` defaults to `-g 0` while the wrapper
  passes 2; forgetting it looks like a regression that isn't real.
- **`rm classify.o` after changing CXXFLAGS**, or make will not rebuild and all
  variants come out md5-identical.

## 8. Correctness and compatibility

`-F exact` (16 B: full 64-bit minimizer + taxid) is **byte-identical to stock**
in every configuration tested — every tier, every associativity, stacked and
single, `-p 1` and `-p 16`, on pod5_15 and pod5_0.

`-F compact` (4 B, reusing kraken2's own packing) inherits the DB's fingerprint
width and is **safe only at 32-bit cells**:

| DB | key_bits | reads changed of 30,378 |
|---|---:|---:|
| eskape_32bit_fork | 26 | **0** |
| eskape_24bit | 18 | 263 |
| eskape_20bit | 14 | 3,159 |
| eskape_16bit | **10** | **16,175 (53.2%)** |

Reports diverge too, so abundance estimates change. A guard now refuses
`key_bits+value_bits > 32` (a 40-bit cell DB would silently overflow the 32-bit
entry) and warns below 26 fingerprint bits.

**A bug worth recording.** The first implementation took the set index from
`hc >> 32`, which *overlaps* the 26-bit fingerprint at `hc >> 38`. That left ~12
discriminating bits and corrupted 2,930 of 30,378 reads. kraken2's own table
takes the index from low bits and the fingerprint from high bits; matching it
(`hc & mask`) fixed it. **Any fingerprinted side table must keep the two bit
ranges disjoint.**

## 9. Reproducing

Patch: `scripts/kraken2_lookaside.patch` — applies to this project's **forked**
`kraken2/src` (which carries the 16/20/24/40-bit cell work), not to upstream
stock 2.17.1.

```
-L SPEC           l1=W,l2=W,l3=W — tiers probed L1→L2→L3→hash table.
                  Sizes fixed in bytes: L1 4 KB, L2 256 KB, L3 4 MB.
                  "-L l3" alone takes its ways from -N.
-N 1|2|4|8|16     associativity for tiers named without =W
-F exact|compact  entry format (default compact)
-A <file>         frequency profile to populate from
-W <file>         write a frequency profile instead (requires -p 1)
-Z                per-tier probe/hit statistics
```

```bash
D=databases/eskape_32bit_fork
# pass 1 — build the oracle profile (untimed, single-threaded)
classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d -p 1 -g 2 -T 0 \
         -W pod5_2.prof perpod5/pod5_2.fastq
# pass 2 — classify through the hierarchy
classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d -p 16 -g 2 -T 0 \
         -L l1=1,l2=1,l3=4 -F compact -A pod5_2.prof -Z perpod5/pod5_2.fastq
```

> **Flags since removed.** The `-A <profile>` and `-Z` options used in this
> command no longer exist — they were deleted on 2026-08-30 once runtime
> learning (`-Y`) replaced the oracle. The command is kept as the record of
> how these numbers were produced; it will not run against the current
> `classify_learn`. See `CHANGELOG.md`.


Raw measurement data: `scratch_lookaside/out/*.tsv`. Detailed chronological
record with every intermediate result: `CACHE_TABLE_ANALYSIS.md`.

---

## Bottom line

The idea is sound in principle and was implemented faithfully — the tables hit
at up to 26.19%, exactly as the simulation predicted (25.28% predicted, 25.13%
measured). It fails for a reason that only measurement could establish: **on
this workload the probe cost dominates the memory saving, and both grow
together**, so improving the cache makes the program slower. The correlation
between hit rate and runtime penalty is **+0.601**.

The path to a faster kraken2 runs through making the database smaller (`-M`,
−26.7% measured), its pages bigger (huge pages, 41–53% of cycles in page walks),
and its misses overlapped (MLP 1.24 of 12) — not through putting another table
in front of it.
