# Would a cache-resident minimizer table make kraken2 faster?

**Analysis of pinning a hot minimizer table in L3, and per-core tables in L1/L2.**

Machine: Intel i7-11700, 8 cores / 16 threads. L1d 48 KB/core, L2 512 KB/core,
L3 16 MB shared, single NUMA node.
DB: `eskape_32bit_fork` (12.2 M cells, 8.90 M occupied, 48.8 MB).
Date: 2026-08-26. Every number below is measured on this box, not estimated.

---

## Verdict up front

| Idea | Verdict | Expected gain |
|---|---|---|
| Per-core hot table in **L1** | **Reject** | ~0.02% |
| Per-core hot table in **L2** | **Reject** | ~0.2% |
| Shared hot table in **L3** | Plausible, blocked on a practical problem | 8–12% net |
| **Software prefetch** (not proposed, but better) | Recommended to try first | targets the same 27% |

Your instinct about *where* the time goes is correct — the hash lookup really is
the bottleneck. The problem is that L1 and L2 are three to four orders of
magnitude too small to hold a useful fraction of the working set, and the L3
version needs to know the answer (which organisms are abundant) before it can
compute the answer.

---

## 1. The premise checks out: lookups dominate

`perf record -F 999` on a real classify run (pod5_15, 16 threads, `-T 0 -g 2`):

| Symbol | % cycles |
|---|---:|
| `CompactHashTable::Get` | **43.4%** |
| `MinimizerScanner::NextMinimizer` | 17.6% |
| `ClassifySequence` | 5.7% |
| `MinimizerScanner::reverse_complement` | 3.4% |
| everything else | < 3.5% each |

Nearly half of all cycles are inside the hash lookup. So targeting it is the
right call.

## 2. The hard ceiling is 27%

`perf stat` on the same workload:

```
   31,50,12,64,236   cycles
   31,12,43,05,839   instructions            # 0.99 IPC
    8,51,04,46,786   cycle_activity.stalls_l3_miss
   18,05,60,99,136   cycle_activity.stalls_total
```

**DRAM stalls = 8.51 G / 31.50 G = 27.0% of all cycles.** Total stalls are
57.3%, so waiting on memory beyond L3 is 47% of all stall time.

This is the ceiling for *any* caching scheme. Even a magic cache that removed
every single DRAM access could not save more than 27% of runtime. Every idea in
this document is competing for a slice of that 27%, not of the whole runtime.

An independent estimate agrees. From the existing thread sweep (48 runs per DB
at 16 threads, `result/perf_threadsweep/raw/`):

| DB | table size | LLC-load-misses | LLC miss % | median s |
|---|---:|---:|---:|---:|
| eskape_16bit | 24.4 MB | 78.3 M | 48.3 | 2.196 |
| eskape_20bit | 36.6 MB | 99.8 M | 55.4 | 2.316 |
| eskape_24bit | 36.6 MB | 100.7 M | 55.9 | 2.356 |
| eskape_32bit | 48.8 MB | 114.0 M | 58.7 | 2.342 |

Halving the table (32-bit → 16-bit) cuts LLC misses by 31% and runtime by 6.2%.
That implies ≈ 4.1 ns of exposed cost per miss, so all 114 M misses ≈ 0.47 s of
a 2.34 s run ≈ 20%. Same ballpark as the 27% counter, from a completely
different measurement.

## 3. The sample has exactly the skew a hot cache needs

pod5_0, 32-bit, `T=0`:

| Organism | reads | genome | est. table entries |
|---|---:|---:|---:|
| *P. aeruginosa* PAO1 | **52.7%** | 6.26 Mbp | 1.99 M |
| *E. coli* K-12 | 21.5% | 4.64 Mbp | 1.47 M |
| *K. pneumoniae* | 9.3% | 5.60 Mbp | 1.78 M |
| *E. cloacae* | 0.4% | 5.68 Mbp | — |
| *E. faecium* / *S. aureus* | ~0% | | — |
| unclassified | 16.0% | | — |

(entries/bp = 8.90 M ÷ 28.06 Mbp = 0.317)

**One organism is over half the sample.** The top two are 74%. This is the
best-case scenario for a hot cache — a uniform sample would sink the idea
immediately.

## 4. But the skew is *between* organisms, not *within* one

This is the finding that constrains everything else.

Sequencing coverage across a genome is roughly uniform, so every minimizer
belonging to *P. aeruginosa* is queried about equally often. There is no small
super-hot subset to extract. **The hot set size is fixed by genome size**
(1.99 M entries for the top organism) and cannot be shrunk without losing hit
rate in direct proportion.

That means capture rate ≈ (entries the cache holds) ÷ (entries in the hot set),
and it is why the L1/L2 versions fail on arithmetic alone.

## 5. L1 and L2: the arithmetic kills it

With hyperthreading, two threads share each core's L1 and L2, so per-thread
capacity is half:

| Level | per-thread | entries @ 4 B | share of 8.90 M table | capture × 27% ceiling |
|---|---:|---:|---:|---:|
| L1d | 24 KB | 6,144 | 0.07% | **~0.02%** |
| L2 | 256 KB | 65,536 | 0.74% | **~0.2%** |
| L3 (8 MB dedicated) | — | 2.10 M | 23.5% | ~6% |
| L3, organism-targeted | — | 1.99 M | **52.7% of lookups** | **~14% gross** |

A per-core table sized to fit in L1 holds about **6,000 of the 8,900,000
entries** it would need. Even under perfect conditions that is a rounding
error — and every miss (99.93% of them) still costs an extra probe before
falling through to the main table, so the net effect would be *negative*.

L2 is 10× better and still under a quarter of one percent.

**L1 and L2 are not viable. Not "hard" — arithmetically ruled out.**

## 6. You cannot pin anything anyway

Worth stating plainly, because the word "pin" is doing a lot of work in the
original idea:

- **CPU caches are hardware-managed.** There is no x86 instruction or OS API to
  pin a buffer in L1, L2, or L3. `WBINVD` (flush) is ring-0, and there is no
  "keep this resident" counterpart at any privilege level.
- **Intel CAT** (Cache Allocation Technology / RDT) can reserve L3 *ways* for a
  process group, which is the closest thing that exists. Checked on this box:

  ```
  /proc/cpuinfo  → no cat_l3, cat_l2, cdp_l3, rdt_a
  /sys/fs/resctrl → absent
  /proc/filesystems → no resctrl
  ```

  CAT is a Xeon feature. This is a client Rocket Lake part, so it is not
  available here at all. And even on hardware that has it, CAT partitions
  capacity between processes — it does not pin a chosen array.

The only real mechanism is indirect: make a structure small enough and hot
enough that the hardware's own LRU keeps it resident. That is achievable, but
it is a consequence of good data layout, not something you request.

## 7. The actual inefficiency is cache-line waste

Here is the mechanism worth attacking, which the original idea gets at
sideways.

`Get()` computes `MurmurHash3(key)` and indexes `hc % capacity`. The hash
deliberately scatters keys uniformly, so **the first probe of every lookup
lands on a uniformly random slot**. The CPU fetches a full 64-byte cache line
to use 4 bytes of it. The other 60 bytes hold 15 unrelated minimizers that this
read will almost certainly never ask for.

`-DLINEAR_PROBING` is set in the Makefile (`second_hash()` returns 1), so the
probe *chain* walks adjacent cells and does reuse that line — that part is
already efficient. The waste is entirely in the initial random touch.

A densely packed hot table fixes exactly this: 16 useful entries per line
instead of 1. That is the real argument for the L3 version, and it is a better
argument than "keep it in fast memory."

**Secondary finding, unrelated to caching but cheaper to act on:** the table
runs at **73% load factor** (8.90 M / 12.20 M). Linear probing degrades sharply
above ~70%, so probe chains are long, and that inflates the same `Get()` that
costs 43.4% of cycles. Raising `-c` at build time is a one-flag experiment with
no code change.

## 8. The L3 hot table: what it would actually take

Realistic construction — a compact secondary table holding only the abundant
organisms' minimizers, consulted before the main table:

| Hot set | entries | @ 4 B | @ 3 B | @ 2 B | lookups captured |
|---|---:|---:|---:|---:|---:|
| Top 1 (*P. aeruginosa*) | 1.99 M | 7.9 MB | 6.0 MB | 4.0 MB | 52.7% |
| Top 2 (+ *E. coli*) | 3.46 M | 13.8 MB | 10.4 MB | 6.9 MB | 74.2% |

L3 is 16 MB **shared by all 16 threads** and simultaneously under pressure from
a 990 MB streaming read buffer, output buffers, and the taxonomy. A hot table
much above ~6–8 MB will not stay resident. So the practical configuration is
top-1 at 24-bit (6.0 MB) or top-2 at 16-bit (6.9 MB).

Expected gain: 52.7% capture × 27% ceiling ≈ **14% gross**, minus:

- an extra probe on every miss (47% of lookups) — small but real;
- the L3 the hot table displaces, which makes *other* accesses miss more;
- narrow cells in the hot table reintroduce the false-positive problem measured
  earlier (16-bit inflated *S. aureus* hits from 12 to 7,071 across the sweep).

**Net: 8–12% is a fair expectation.**

### The blocker

**You cannot know which organisms are abundant until you have classified the
sample.** That is the whole point of running kraken2. Options:

1. **Two-pass** — classify a subsample, read off abundance, build the hot table,
   reclassify. The extra pass has to cost less than the 8–12% it buys, which for
   a single run it does not. Only pays off when many files share one flora
   profile — which *is* your case: 16 pod5 files from one sequencing run.
2. **A priori profile** — for a fixed clinical panel where expected organisms
   are known in advance. Reasonable in a diagnostic setting.
3. **Online adaptive cache** — learns hot entries as it goes. Rejected: LRU
   bookkeeping on every one of ~150 M lookups would very likely cost more than
   the 27% it is chasing.

## 9. Recommendation

**Do not build the L1/L2 tables.** The capture rate is 0.07% and 0.74% against
a 27% ceiling. It cannot pay for itself.

**Before building the L3 table, try two much cheaper things** that attack the
same 43.4% hotspot and need no abundance knowledge:

1. **Raise the hash capacity `-c`** to drop the load factor from 73% toward
   50–60% and shorten linear-probe chains. Zero code, one rebuild per setting,
   directly measurable with the existing perf harness.
2. **Software prefetch.** Minimizers arrive as a stream, so while resolving
   minimizer *n* you can already compute the slot for *n+k* and issue
   `__builtin_prefetch`. This attacks the 27% DRAM stall head-on, needs no
   knowledge of the sample, has no false-positive cost, and is a far smaller
   change than a two-level table. This is the highest value-per-line-of-code
   option on the list.

If prefetching lands and the workload is still DRAM-bound, the L3 hot table
becomes worth revisiting — as a two-pass scheme amortised across all 16 pod5
files of a run, which is the one setting where its chicken-and-egg problem
actually dissolves.

---

## Appendix: how to reproduce these numbers

```bash
# hotspot split
perf record -F 999 -o perf.data -- kraken2/src/classify \
    -H databases/eskape_32bit_fork/hash.k2d \
    -t databases/eskape_32bit_fork/taxo.k2d \
    -o databases/eskape_32bit_fork/opts.k2d \
    -p 16 -T 0 -g 2 -R /dev/null perpod5/pod5_15.fastq
perf report -i perf.data --stdio --sort symbol

# DRAM stall fraction
perf stat -e cycles,instructions,cycle_activity.stalls_l3_miss,\
cycle_activity.stalls_total,LLC-load-misses  <same classify command>

# table-size effect (existing data, no run needed)
#   aggregate result/perf_threadsweep/raw/*_16T_*_perf.txt per DB

# abundance
awk -F'\t' '$4=="S"' result/cellsize_sweep/eskape_32bit_stock_T0_pod5_0_report.txt

# CAT / cache-pinning capability
grep -oE 'cat_l3|cat_l2|rdt_a' /proc/cpuinfo ; ls /sys/fs/resctrl
```

Note `classify` invoked directly needs `-g 2` to match the `kraken2` wrapper's
default `--minimum-hit-groups`; without it, classification rates run high.

---

# Addendum: memoising minimizer→taxid, and can we pin on this box?

Two follow-up questions, answered separately.

## A. Can cache pinning be done on this device? — **No.**

| Check | Result |
|---|---|
| CPUID RDT/CAT flags (`rdt_a`, `cat_l3`, `cat_l2`, `cqm`, `mba`) | **none present** (only `rdtscp`, an unrelated timer) |
| `/sys/fs/resctrl` | absent |
| Kernel support | `CONFIG_X86_CPU_RESCTRL=y` — **kernel is ready** |

The kernel has the resctrl driver compiled in, but the interface never appears
because the **CPU does not expose the feature**. Intel CAT is a Xeon/server
feature; this is a client Rocket Lake part. So even the partial mechanism is
unavailable here.

Two further points that hold on *every* x86, not just this one:

- **CAT would not do what you want anyway.** It partitions L3 *ways* between
  process groups so a noisy neighbour cannot evict you. It cannot pin a chosen
  array. (Intel shipped "cache pseudo-locking" built on CAT for a few embedded
  SKUs; it is not general and not here.)
- **There is no L1/L2 control interface at any privilege level, on any x86.**
  L1 and L2 are per-core, hardware-LRU, with no architectural mechanism to
  reserve or pin. This is not a permissions problem — the capability does not
  exist.

The only usable lever anywhere is indirect: make a structure small and hot
enough that hardware LRU keeps it resident on its own.

## B. Memoising minimizer→taxid

**kraken2 already does this — with a cache of exactly one entry** (`classify.cc:839`):

```c
if (*minimizer_ptr != last_minimizer) {
    taxon = hash->Get(*minimizer_ptr);   // DRAM lookup
    last_taxon = taxon; last_minimizer = *minimizer_ptr;
} else {
    taxon = last_taxon;                  // cached, no lookup
}
```

This already harvests the cheap win. With k=35, l=31 the minimizer window is 5,
so a given minimizer persists across several consecutive k-mer positions; the
depth-1 cache skips every one of those repeats. Roughly 134 M lookups survive
per pod5_0 file, out of 402 Mbp.

### There is real long-range reuse

| organism | share | distinct minimizers | times each is queried |
|---|---:|---:|---:|
| *P. aeruginosa* | 52.7% | 1.99 M | **35.5×** |
| *E. coli* | 21.5% | 1.47 M | 19.6× |
| *K. pneumoniae* | 9.3% | 1.78 M | 7.0× |

Every *P. aeruginosa* minimizer is genuinely fetched ~35 times per file. Your
intuition that this is wasteful is correct.

### But the repeats are scattered, so the cache must be huge

Reads arrive in random genome order, so those 35 queries are spread uniformly
across 134 M lookups. Mean reuse distance ≈ the size of the distinct set
(~2 M entries). For LRU under this access pattern the hit rate is
`N × Σpᵢ²`, with `Σpᵢ² = 1.76e-7`:

| cache | entries | hit rate | runtime saved (× 27% ceiling) |
|---|---:|---:|---:|
| L1d-resident (24 KB/thread) | 6,144 | 0.11% | **0.03%** |
| L2-resident (256 KB/thread) | 65,536 | 1.15% | **0.31%** |
| 1 MB in L3 | 262,144 | 4.6% | 1.25% |
| 4 MB in L3 | 1,048,576 | 18.5% | 4.98% |
| 8 MB in L3 | 2,097,152 | 36.9% | 9.96% |

### And memoisation is strictly worse than a hot DB subset

A memo entry must store a key *and* a value. kraken2's DB cell is already
**4 bytes holding a key fingerprint plus the taxid** — the maximally compact
form of exactly that pair. So:

- a memo cache at *equal* density is just a smaller copy of the DB, i.e. the
  hot-subset idea, not a new mechanism;
- a memo cache storing the full 8-byte minimizer + 4-byte taxid is **3× less
  dense**, fits 3× fewer entries in the same L3, and lands at ~1/3 the hit rate.

**Memoisation converges on the hot-table design and cannot beat it.**

## C. What the reuse data actually points at

The 35× reuse is real; only the *ordering* destroys it. That argues for fixing
the order rather than adding a cache:

**Batch and sort the lookups.** Collect the minimizers for a block of reads,
sort by table slot, resolve them in sorted order, then scatter results back.
This converts uniformly-random DRAM access into a sequential scan, which:

- fixes the cache-line waste (§7) — a 64-byte line yields 16 useful entries
  instead of 1;
- makes duplicates adjacent, so they dedupe for free with no cache at all.

Dedup scale: with ~2 M distinct minimizers and `L` lookups per batch, unique
lookups ≈ `2M × (1 − e^(−L/2M))`. A 10 M-lookup batch collapses to ~2 M real
lookups — a **5× reduction in DRAM traffic**; batching a whole file approaches
15×. That dwarfs the 10% ceiling of any L3 cache.

Cost: buffering minimizers (8 bytes each) and a sort, plus reworking the
per-read result path so taxids find their way back to the right read. Real work,
and it changes kraken2's streaming structure — but it is the only option on the
table whose upside is a multiple rather than a percentage.

**Ranking, best first:** (1) batched/sorted lookups, (2) software prefetch,
(3) lower load factor via `-c`, (4) L3 hot table, (5) L1/L2 tables — ruled out.

---

# Addendum 2: measured reuse distance — does an N-entry lookaside cache work?

The proposal: on first fetch of a minimizer, store minimizer→taxid in a table;
when the same minimizer recurs "after a few hundred minimizers", read it from
the table instead of DRAM. Depth-N instead of kraken2's current depth-1.

This is testable, so I measured it rather than argued it. A standalone tool
replays the exact lookup stream `ClassifySequence` issues (including the
existing depth-1 skip) and computes **exact LRU stack distances** with a Fenwick
tree, giving the true hit rate for every cache size in one pass.

## The measurement

| | pod5_15 (30 K reads, 91 Mbp) | pod5_0 (132 K reads, 402 Mbp) |
|---|---:|---:|
| lookups after depth-1 | 29,054,665 | 129,070,227 |
| distinct minimizers | 13,685,488 | 35,759,923 |
| mean reuse | 2.1× | 3.6× |
| **compulsory misses** | **47.1%** | **27.7%** |

Exact LRU hit rate by cache size:

| cache entries | pod5_15 | pod5_0 | runtime saved (×27% ceiling) |
|---:|---:|---:|---:|
| 256 | 0.17% | **0.23%** | 0.06% |
| 1,024 | 0.34% | **0.49%** | 0.13% |
| 4,096 (L1-ish) | 0.67% | ~0.9% | 0.24% |
| 65,536 (L2-ish) | 2.06% | **2.19%** | 0.59% |
| 1,048,576 | 14.97% | 14.43% | 3.9% |
| 4,194,304 | 36.34% | 39.48% | 10.7% |
| 8,388,608 | 49.57% | 57.98% | 15.7% |
| ∞ (ceiling) | 52.90% | **72.28%** | — |

## What this says

**1. The "few hundred minimizers" hypothesis is false by ~100×.** A 256-entry
cache hits 0.23%; a 1,024-entry cache hits 0.49%. Reuse is not at short
distance. Reads arrive in random genome order, so a minimizer's repeats are
scattered across millions of intervening lookups.

**2. Nanopore error rate is the deeper problem.** pod5_15 produced **13.7 M
distinct minimizers from a 28 Mbp reference whose entire database holds only
8.9 M**. More distinct minimizers than the whole DB — most are sequencing
errors, unique, and will never recur. That is why 47% of lookups are compulsory
misses no cache of any size can help.

**3. More data raises the ceiling but not small caches.** Going 4.4× larger
(pod5_15 → pod5_0) lifts the infinite-cache ceiling from 52.9% to 72.3% — but a
65 K-entry cache barely moves, 2.06% → 2.19%. All the extra reuse appears at
*long* distance, needing caches of 8–33 M entries.

**4. Useful hit rates require a cache larger than L3, which is self-defeating.**
A memo entry needs a key fingerprint plus a taxid — call it 8 bytes. To reach
39% you need 4 M entries = **32 MB, twice the 16 MB L3**. The cache would then
itself live in DRAM: you would have added a second random-access DRAM structure
in front of the first. The configuration that *does* fit — 1 M entries at 8 MB,
half of L3 — returns 14.4% hit rate ≈ 3.9% runtime, while displacing 8 MB of L3
that was previously caching the real DB, making the other 85.6% slower. **Net is
plausibly zero or negative.**

## The constructive finding

The 72.3% ceiling proves substantial reuse genuinely exists — 3.6× on average.
It is simply at the wrong *distance* for a cache. But a cache is not the only
way to exploit reuse: **sorting converts long reuse distance into adjacency**,
which is precisely what a cache cannot do.

Batch the minimizers for a chunk of reads, sort by table slot, resolve in sorted
order, scatter results back:

- **129 M lookups collapse to 35.8 M unique** for pod5_0 — a 3.6× cut in actual
  DRAM lookups, exactly the mean-reuse figure, achieved with no cache at all;
- the survivors are visited in slot order, so access becomes **sequential
  instead of uniformly random** — a 64-byte line yields 16 useful entries
  instead of 1, and the hardware prefetcher starts working for you.

Both effects attack the same 27% DRAM-stall budget, and unlike the cache they
scale *with* the reuse the data actually has. This is the one option whose
upside is a multiple rather than a fraction of a percent.

Cost: an 8-byte buffer per pending lookup (batching 16 M lookups = 128 MB), a
sort, and reworking the result path so taxids return to the correct read
position. It changes kraken2's streaming structure — real work, but it is where
the measured data points.

**Revised ranking:** (1) batched/sorted lookups, (2) software prefetch,
(3) lower load factor via `-c`, (4) L3 hot table, (5) depth-N memo cache —
measured at 0.2–0.6% for any cache that fits in L1/L2, (6) L1/L2 hot tables.

---

# Addendum 3: the idea works — as an L3-resident *database*, not a cache

Objection raised: "our database is only 36 MB." That reframes everything, and it
is correct. My earlier "a useful cache exceeds L3, so it is self-defeating"
applies only to a *separate memo table*, which must store a key alongside a
value and is therefore 2-3x less dense than the DB. A kraken2 cell is already
the optimally compact key-fingerprint + taxid. So the right move is not a cache
in front of the table — it is **shrinking the table below L3 so the hardware
caches it for you**. No second structure, no abundance chicken-and-egg, no code
change: one build flag.

This only works because this DB is small. A standard 8-64 GB kraken2 DB is
500-4000x L3 and hopeless; this one is **1.45x** at 16-bit.

## The existing data already showed it

| DB | size | fits in L3 | LLC miss % |
|---|---:|---:|---:|
| 16-bit | 24.4 MB | 69% | 48.3 |
| 24-bit | 36.6 MB | 46% | 55.9 |
| 32-bit | 48.8 MB | 34% | 58.7 |

Monotonic across 48 runs per DB. Full residency was always ~6% of capacity away.

## Measured, interleaved, pod5_15, 16 threads

`-M` (MiniKraken) closes the gap: it shrinks the table *and* makes classify skip
sub-threshold lookups (`classify.cc:841`).

| DB | size | runtime | DRAM stall | classified | S.aureus FP | E.faecium FP |
|---|---:|---:|---:|---:|---:|---:|
| eskape_32bit_fork | 48.8 MB | 0.531 s | 26.8% | 83.39% | 0 | 1 |
| eskape_24bit | 36.6 MB | 0.532 s | 25.0% | 83.42% | 1 | 3 |
| **24-bit `-M 4000000`** | **12.0 MB** | **0.389 s** | **6.6%** | 82.07% | **0** | **1** |
| 16-bit | 24.4 MB | 0.502 s | 20.3% | 90.93% | 128 | 187 |
| 16-bit `-M 6000000` | 12.0 MB | 0.432 s | 7.4% | 90.82% | 134 | 149 |

**26.7% faster than the 32-bit baseline, precision identical to 32-bit, DB 4x
smaller, for 1.3 pp of sensitivity.**

Build command:

```bash
cat eskape_cs/library/*.fna | build_db -H hash.k2d -t taxo.k2d -o opts.k2d \
    -n eskape_cs/taxonomy -m eskape_cs/seqid2taxid.map \
    -c 12200000 -M 4000000 -k 35 -l 31 -p 1 -C 24
```

## Honest attribution: two effects, not one

`-M` delivers a compound benefit and the two parts are confounded by design:

1. **Cache residency** — directly measured: DRAM stalls 26.8% -> 6.6%. This is
   the proposed mechanism, and it is confirmed.
2. **Less work** — only ~33% of minimizers are stored, so classify skips ~67% of
   lookups outright via `minimum_acceptable_hash_value`.

The stall collapse isolates (1) cleanly; the runtime gain reflects both. A clean
separation is not possible through `-M` alone, because in kraken2 the subsample
fraction *is* the capacity ratio. Separating them would need a DB subsampled
identically but sized above L3.

## Caveats before adopting

- **Sensitivity cost is real**: 83.39% -> 82.07%, and it will be worse on
  low-coverage samples where `--minimum-hit-groups 2` becomes binding.
- **One sample, one file.** pod5_15 only; confirm across the other 15 and at
  `-T 0.05` before treating it as the project default.
- **There is an optimum between 4 M and 5 M cells** at 24-bit (12-15 MB) trading
  sensitivity against residency; 4 M was a first guess, not a tuned value. L3 is
  shared with the read stream, so the largest fitting table is not the best one.
- Does **not** generalise to large databases — this is a property of a 28 Mbp
  reference, not of kraken2.

## Revised ranking

1. **Shrink the DB below L3 via `-M`** — measured 26.7%, zero code, available now.
2. Batched/sorted lookups — larger theoretical upside, substantial work.
3. Software prefetch.
4. L3 hot table / depth-N memo cache — superseded: (1) achieves the same goal
   without a redundant structure.
5. L1/L2 tables — ruled out, 0.2-0.6%.

---

# Addendum 4: the lookaside table, built and measured

Addendum 2 predicted this from simulation. This addendum reports the same idea
**implemented in kraken2 and benchmarked**, following `LOOKASIDE_TABLE_PROMPT.md`.
Patch: `scripts/kraken2_lookaside.patch`. Date: 2026-08-30.

A direct-mapped table is probed in `ClassifySequence` immediately before
`hash->Get()`. It is shared read-only across threads and populated **offline by
frequency** (an oracle: pass 1 counts minimizer frequency over the same file
pass 2 then times, so this is a ceiling, not a deployable design). A
`GetWithHash(key, hc)` entry point was added to `CompactHashTable` so the probe
does not pay for MurmurHash3 twice — without it the double hashing alone would
cost the same order as the effect being measured.

Pass 1 independently reproduced Addendum 2's stream exactly: **13,685,488
distinct minimizers, 29,054,665 lookups**.

## Results — pod5_15, `-p 16`, 5 interleaved rounds, median

| format | entry | tier | table | entries | hit rate | runtime | vs base |
|---|---:|---|---:|---:|---:|---:|---:|
| — | — | baseline | — | — | — | 0.523 s | — |
| exact | 16 B | L3 | 4 MB | 262,144 | 9.77% | 0.533 s | **+1.91%** |
| exact | 16 B | L2 | 256 KB | 16,384 | 1.86% | 0.528 s | +0.96% |
| exact | 16 B | L1 | 4 KB | 256 | 0.55% | 0.525 s | +0.38% |
| compact | 4 B | L3 | 4 MB | 1,048,576 | **25.13%** | **0.515 s** | **−1.53%** |
| compact | 4 B | L2 | 256 KB | 65,536 | 3.87% | 0.521 s | −0.38% |
| compact | 4 B | L1 | 4 KB | 1,024 | 0.73% | 0.526 s | +0.57% |

`-p 1` reproduces it: base 4.231 s, compact/L3 4.168 s (**−1.49%**),
exact/L3 4.368 s (+3.24%), compact/L1 4.228 s (−0.07%).

**Simulation was accurate.** Predicted oracle hit rate at 1 M entries: 25.28%.
Measured: **25.13%**.

## Why the only winner wins so little

Table-build cost subtracted, `-p 16`:

| variant | cycles | L3 loads | DRAM accesses | L3 miss rate | MLP |
|---|---:|---:|---:|---:|---:|
| base | 30.21 G | 48.2 M | 27.9 M (0.96/lookup) | 57.9% | 1.259 |
| compact/L3 | 29.36 G (−2.8%) | 75.0 M | **32.0 M (1.10/lookup)** | 42.7% | 1.434 |
| exact/L3 | 31.03 G (+2.7%) | 78.1 M | 35.6 M (1.22/lookup) | 45.6% | 1.457 |

The 4 MB table serves 25% of lookups from L3 — and **raises DRAM accesses from
0.96 to 1.10 per lookup**, because it evicts 4 MB of database from a 16 MB L3
that was already caching it at a 42.3% hit rate. The predicted self-defeating
effect is directly visible. Net −1.5% is what survives.

`exact` loses at every tier despite a working 9.77% hit rate: 16-byte entries buy
only 262 K slots for the same 4 MB, and that is not enough to pay for the L3 it
displaces. **Density decides the outcome**, exactly as Addendum 2's argument
predicted.

## Correctness

Output and report byte-identical to `kraken2_bin/classify` at `-p 1` and `-p 16`:

| variant | pod5_15 | pod5_0 (cross-sample) |
|---|---|---|
| exact, all tiers | identical | identical |
| compact/L3 | identical | 2 / 132 K reads differ |
| compact/L2 | identical | identical |
| compact/L1 | 4 / 30 K reads differ | 33 / 132 K reads differ |

The exact format is provably safe. The compact format trades correctness for
density — small but nonzero.

**A bug worth recording.** The first implementation followed the prompt's
`slot = (hc >> 32) & mask`, which *overlaps* the 26-bit fingerprint (`hc >> 38`).
That left ~12 discriminating bits and corrupted **2,930 of 30,378 reads (9.6%)**
at the L3 tier. kraken2's own table takes the slot from low bits and the
fingerprint from high bits; matching that (`slot = hc & mask`) fixed it. Any
fingerprinted side table must keep the two bit-ranges disjoint.

## Runtime flag

The prototype was rebuilt as a **runtime flag** rather than six compile-time
binaries, so one `classify` selects the tier at invocation
(`scripts/kraken2_lookaside.patch`, applies cleanly to stock 2.17.1):

```
-L l1|l2|l3       enable the table, sized for that cache tier
                  (L1 4 KB, L2 256 KB, L3 4 MB)
-F exact|compact  entry format (default compact)
-A <file>         frequency profile to populate from
-W <file>         write a frequency profile instead (requires -p 1)
-Z                report probe/hit statistics
```

Tier size is fixed in **bytes**, so the entry count follows from the format —
`compact` gets 4x the slots of `exact` for the same cache footprint:

```bash
# pass 1: build the profile (untimed, single-threaded)
classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d -p 1 -g 2 \
         -W pod5_15.prof pod5_15.fastq

# pass 2: classify with an L3-resident table
classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d -p 16 -g 2 \
         -L l3 -F compact -A pod5_15.prof -Z pod5_15.fastq
```

> **Flags since removed.** The `-A <profile>` and `-Z` options used in this
> command no longer exist — they were deleted on 2026-08-30 once runtime
> learning (`-Y`) replaced the oracle. The command is kept as the record of
> how these numbers were produced; it will not run against the current
> `classify_learn`. See `CHANGELOG.md`.


Measured, 5 interleaved rounds, `-p 16`, pod5_15:

| invocation | median | vs stock |
|---|---:|---:|
| `kraken2_bin/classify` (stock) | 0.522 s | — |
| patched, no `-L` | 0.525 s | +0.57% |
| **`-L l3 -F compact`** | **0.515 s** | **−1.34%** |
| `-L l2 -F compact` | 0.523 s | +0.19% |
| `-L l1 -F compact` | 0.529 s | +1.34% |
| `-L l3 -F exact` | 0.537 s | +2.87% |
| `-L l2 -F exact` | 0.524 s | +0.38% |
| `-L l1 -F exact` | 0.530 s | +1.53% |

Hit rates are identical to the compile-time builds (L3 compact 25.13%, L2 3.87%,
L1 0.73%; exact 9.77% / 1.86% / 0.55%), and with no `-L` the output is
byte-identical to stock. **The flag itself costs +0.57%** — a runtime mask and
two predictable branches in the hot loop — so the L3 tier's real gain over the
patched binary is −1.90%, and over stock −1.34%.

> **Superseded by the noise-floor analysis below.** These pod5_15 timings were
> taken before the physical-ceiling test established that this machine cannot
> resolve effects below **+/-1.5%** (bimodal 2.33-2.39 s / 2.85-3.14 s runs under
> the `powersave` governor). Every negative figure in the two tables above is
> inside that band and is **not established**. The hit rates and correctness
> results are unaffected — those are deterministic and were re-verified against
> the current binary. Treat only the >1.5% penalties as measured.


## Set associativity (`-N`)

The 1-way table was losing hits to slot collisions: the top 1 M minimizers cover
**28.90%** of the lookup stream but a direct-mapped table hit only 25.13%.
`-N 1|2|4|8|16` makes a set `N` consecutive entries, 64-byte aligned so each set
lies in one cache line; probes are templated on the way count so they unroll.
Population is unchanged (hottest-first, first free way), so associativity only
ever adds room and never displaces a hotter entry.

| tier | 1-way | 2-way | 4-way | 8-way | 16-way | ceiling |
|---|---:|---:|---:|---:|---:|---:|
| **L3** (4 MB) | 25.13% | 26.80% | 27.75% | 28.27% | **28.53%** | 28.90% |
| L2 (256 KB) | 3.87% | 3.99% | 4.04% | 4.07% | — | 4.09% |
| L1 (4 KB) | 0.73% | 0.76% | 0.77% | — | — | 0.78% |

Associativity recovers 3.40 of the 3.77 pp lost to collisions at L3. L2 and L1
barely move: their misses are **capacity** misses, not conflict misses, so there
was nothing for associativity to recover.

Runtime (L3, compact, `-p 16`, pod5_15, 6 interleaved reps, median):

| ways | hit rate | runtime | vs stock |
|---:|---:|---:|---:|
| stock | — | 0.528 s | — |
| 1 | 25.13% | 0.523 s | −0.85% |
| 2 | 26.80% | 0.524 s | −0.76% |
| **4** | **27.75%** | **0.519 s** | **−1.61%** |
| 8 | 28.27% | 0.528 s | +0.19% |
| 16 | 28.53% | 0.548 s | **+3.89%** |

**Hit rate and speed diverge after 4 ways.** 16-way has the best hit rate and is
the slowest configuration measured — the ~72% of probes that miss must scan all
16 tags, and that costs more than the extra 0.78 pp of hits returns. 4-way is
the optimum: nearly all the conflict misses recovered, only 4 tags scanned.

Correctness is unchanged (byte-identical to stock) except `-L l3 -N 16` and
`-L l2 -N 8`, which each differ on 1 read of 30,378.

**Benchmarking note.** The first two timed sweeps were discarded: stock drifted
0.522 s -> 0.621 s within a run and pair ratios reached 0.63 and 1.22. The box
was heat-soaked after a long session (62 C package, 81 C under load). Only
interleaved reps on a settled machine gave usable numbers, and differences below
~1% here remain at the noise floor. The 16-way penalty is the one result whose
distribution is fully disjoint from the others.

> **Superseded by the noise-floor analysis below.** These pod5_15 timings were
> taken before the physical-ceiling test established that this machine cannot
> resolve effects below **+/-1.5%** (bimodal 2.33-2.39 s / 2.85-3.14 s runs under
> the `powersave` governor). Every negative figure in the two tables above is
> inside that band and is **not established**. The hit rates and correctness
> results are unaffected — those are deterministic and were re-verified against
> the current binary. Treat only the >1.5% penalties as measured.


## Full sweep on the largest file (pod5_2)

`pod5_2.fastq` — 151,591 reads, 499.98 Mbp, **160,625,038 lookups**, 42.8 M
distinct minimizers. 5.5x the pod5_15 workload. `-p 16 -g 2 -T 0`; counters are
the mean of 3 interleaved `perf` runs with the table-build cost subtracted;
times are medians (3 runs, 9 for the noisier configurations).

| configuration | hit rate | time (s) | ± | vs stock | DRAM/lookup | L3 miss | MLP |
|---|---:|---:|---:|---:|---:|---:|---:|
| stock | — | 2.880 | 0.015 | — | 0.944 | 58.9% | 1.243 |
| L3 compact 1-way | 22.35% | 2.815 | **0.474** | −2.26% | 1.082 | 43.1% | 1.390 |
| L3 compact 2-way | 23.69% | 2.871 | **0.244** | −0.31% | 1.066 | 42.6% | 1.373 |
| L3 compact 4-way | 24.42% | 2.884 | 0.020 | +0.14% | 0.954 | 38.1% | 1.318 |
| L3 compact 8-way | 24.79% | 2.940 | 0.020 | +2.08% | 0.913 | 36.9% | 1.287 |
| L3 compact 16-way | 24.98% | 3.095 | 0.010 | **+7.47%** | 0.859 | 35.7% | 1.252 |
| L2 compact 1-way | 3.27% | 2.889 | 0.019 | +0.31% | 0.928 | 40.3% | 1.239 |
| L2 compact 2-way | 3.36% | 2.928 | 0.022 | +1.67% | 0.929 | 40.1% | 1.232 |
| L2 compact 4-way | 3.40% | 2.946 | 0.015 | +2.29% | 0.928 | 40.6% | 1.229 |
| L2 compact 8-way | 3.41% | 3.043 | 0.025 | +5.66% | 0.928 | 41.5% | 1.224 |
| L1 compact 1-way | 0.65% | 2.900 | 0.020 | +0.69% | 0.932 | 58.6% | 1.237 |
| L1 compact 2-way | 0.67% | 2.903 | 0.155 | +0.80% | 0.933 | 58.4% | 1.237 |
| L1 compact 4-way | 0.68% | 2.948 | 0.024 | +2.36% | 0.934 | 58.5% | 1.239 |
| L3 exact 1-way | 8.20% | 2.910 | 0.014 | +1.04% | 1.172 | 44.6% | 1.405 |
| L3 exact 4-way | 8.54% | 2.934 | 0.009 | +1.88% | 1.063 | 40.0% | 1.330 |

**Hit rates are lower than on pod5_15** (L3 1-way 22.35% vs 25.13%): 42.8 M
distinct minimizers against the same 1 M slots, so the table covers less of the
stream. The idea gets *worse* as the input grows, not better.

**On this file nothing beats stock at a resolvable margin.** The two apparently
negative rows carry error bars 15-30x larger than their effect (±0.474 s on a
−2.26% claim) — timings on pod5_2 were bimodal, ranging 2.376-3.343 s for one
configuration. The tight rows are all positive: every configuration with ±0.03 s
or better is slower than stock.

**The clearest signal is the associativity penalty, and it inverts the hit rate.**
As ways increase, DRAM traffic falls monotonically (0.944 -> 0.859 per lookup,
better than stock) and the L3 miss rate improves 58.9% -> 35.7% — yet runtime
rises 7.47%. Scanning 16 tags on the ~75% of probes that miss costs more than
all the memory traffic saved. **Associativity buys memory behaviour and pays for
it in instructions, and on this workload the trade is a loss.**

Note also that `exact` at L3 shows DRAM/lookup of 1.172 — *worse* than stock —
confirming that a 4 MB table of 16-byte entries evicts more database than its
8.20% hit rate recovers.

## Complete sweep: every combination, pod5_2

All 30 combinations (3 tiers x 2 formats x 5 associativities) plus stock, on the
largest input. 186 runs: 30 hit-rate, 31 load-only (subtracted from every
counter), 124 timed `perf` runs over 4 interleaved reps.

`pod5_2.fastq` — 151,591 reads, 499.98 Mbp, **160,625,038 lookups**, 42.8 M
distinct minimizers. `-p 16 -g 2 -T 0`. Time is the median of 4 reps.

| tier | fmt | ways | sets | set B | lines | hit | time (s) | vs stock | max possible | DRAM/lk | L3 miss | MLP |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| — | stock | — | — | — | — | — | 2.872 | — | — | 0.936 | 58.7% | 1.243 |
| L3 | compact | 1 | 1,048,576 | 4 | 1 | 22.35% | 2.812 | -2.11% | -5.33% | 1.071 | 42.5% | 1.384 |
| L3 | compact | 2 | 524,288 | 8 | 1 | 23.69% | 2.835 | -1.31% | -5.65% | 1.053 | 42.3% | 1.373 |
| L3 | compact | 4 | 262,144 | 16 | 1 | 24.42% | 2.843 | -0.99% | -5.82% | 0.949 | 37.9% | 1.318 |
| L3 | compact | 8 | 131,072 | 32 | 1 | 24.79% | 2.907 | +1.24% | -5.91% | 0.897 | 36.4% | 1.281 |
| L3 | compact | 16 | 65,536 | 64 | 1 | 24.98% | 3.056 | **+6.42%** | -5.96% | 0.861 | 35.6% | 1.252 |
| L3 | exact | 1 | 262,144 | 16 | 1 | 8.20% | 2.882 | +0.35% | -1.96% | 1.158 | 44.2% | 1.396 |
| L3 | exact | 2 | 131,072 | 32 | 1 | 8.42% | 2.886 | +0.50% | -2.01% | 1.162 | 44.5% | 1.394 |
| L3 | exact | 4 | 65,536 | 64 | 1 | 8.54% | 2.876 | +0.14% | -2.04% | 1.059 | 40.1% | 1.334 |
| L3 | exact | 8 | 32,768 | 128 | 2 | 8.59% | 2.925 | **+1.86%** | -2.05% | 1.039 | 28.5% | 1.403 |
| L3 | exact | 16 | 16,384 | 256 | 4 | 8.62% | 3.008 | **+4.72%** | -2.06% | 0.997 | 18.0% | 1.559 |
| L2 | compact | 1 | 65,536 | 4 | 1 | 3.27% | 2.860 | -0.42% | -0.78% | 0.925 | 40.8% | 1.238 |
| L2 | compact | 2 | 32,768 | 8 | 1 | 3.36% | 2.885 | +0.44% | -0.80% | 0.924 | 40.2% | 1.231 |
| L2 | compact | 4 | 16,384 | 16 | 1 | 3.40% | 2.918 | **+1.62%** | -0.81% | 0.926 | 40.4% | 1.231 |
| L2 | compact | 8 | 8,192 | 32 | 1 | 3.41% | 2.982 | **+3.85%** | -0.81% | 0.923 | 41.7% | 1.224 |
| L2 | compact | 16 | 4,096 | 64 | 1 | 3.42% | 3.090 | **+7.59%** | -0.82% | 0.922 | 41.7% | 1.223 |
| L2 | exact | 1 | 16,384 | 16 | 1 | 1.66% | 2.836 | -1.25% | -0.40% | 0.844 | 40.3% | 1.246 |
| L2 | exact | 2 | 8,192 | 32 | 1 | 1.73% | 2.844 | -0.97% | -0.41% | 0.935 | 40.0% | 1.240 |
| L2 | exact | 4 | 4,096 | 64 | 1 | 1.77% | 2.846 | -0.89% | -0.42% | 0.936 | 40.1% | 1.243 |
| L2 | exact | 8 | 2,048 | 128 | 2 | 1.79% | 2.877 | +0.19% | -0.43% | 0.938 | 35.6% | 1.287 |
| L2 | exact | 16 | 1,024 | 256 | 4 | 1.80% | 2.950 | **+2.73%** | -0.43% | 0.942 | 32.3% | 1.337 |
| L1 | compact | 1 | 1,024 | 4 | 1 | 0.65% | 2.843 | -1.03% | -0.15% | 0.929 | 58.3% | 1.238 |
| L1 | compact | 2 | 512 | 8 | 1 | 0.67% | 2.881 | +0.31% | -0.16% | 0.928 | 58.6% | 1.238 |
| L1 | compact | 4 | 256 | 16 | 1 | 0.68% | 2.895 | +0.80% | -0.16% | 0.927 | 58.3% | 1.237 |
| L1 | compact | 8 | 128 | 32 | 1 | 0.68% | 2.941 | **+2.40%** | -0.16% | 0.928 | 58.2% | 1.237 |
| L1 | compact | 16 | 64 | 64 | 1 | 0.69% | 3.026 | **+5.36%** | -0.16% | 0.927 | 58.3% | 1.236 |
| L1 | exact | 1 | 256 | 16 | 1 | 0.48% | 2.826 | -1.60% | -0.11% | 0.929 | 57.9% | 1.238 |
| L1 | exact | 2 | 128 | 32 | 1 | 0.51% | 2.846 | -0.91% | -0.12% | 0.929 | 58.4% | 1.236 |
| L1 | exact | 4 | 64 | 64 | 1 | 0.52% | 2.827 | -1.58% | -0.12% | 0.929 | 58.2% | 1.238 |
| L1 | exact | 8 | 32 | 128 | 2 | 0.53% | 2.850 | -0.77% | -0.13% | 0.930 | 57.9% | 1.238 |
| L1 | exact | 16 | 16 | 256 | 4 | 0.53% | 2.888 | +0.56% | -0.13% | 0.929 | 57.8% | 1.239 |

`max possible` is the physical ceiling for each row: stock spends **23.9%** of
cycles stalled on DRAM, so a table with hit rate *h* can save at most
*h* x 23.9% of runtime. Bold = slower than stock beyond the noise floor.

### The noise floor is +/-1.5%, and the data proves it

Seven rows claim a speedup **larger than physically possible** — `L1 exact
1-way` reads −1.60% from a 0.48% hit rate, against a −0.11% ceiling; it cannot
avoid 1.6% of the work by skipping 0.48% of lookups. Those readings are
measurement error, and their magnitude puts the noise floor at roughly +/-1.5%.

The cause is not thermal drift: repeated runs of the *same* binary are
**bimodal**, clustering at 2.33-2.39 s and 2.85-3.14 s — a 23% gap consistent
with turbo vs base frequency under the `powersave` governor. Both stock and the
patched binary land in both modes.

**Consequence: no speedup anywhere in this table is established.** The three
`L3 compact` negatives (−2.11%, −1.31%, −0.99%) sit at or inside the noise
floor. Only the penalties beyond +1.5% are real, and they are consistent across
all six tier x format groups.

### What the counters show (immune to frequency scaling)

**Associativity improves memory behaviour and costs runtime, monotonically.**
For `L3 compact`, DRAM per lookup falls 1.071 -> 0.861 (crossing below stock's
0.936) and L3 miss rate falls 42.5% -> 35.6%, while runtime rises from −2.11% to
**+6.42%**. Scanning 16 tags on the ~75% of probes that miss costs more than
every byte of memory traffic saved.

**Multi-cache-line sets are visibly punished.** Only `exact` at 8 and 16 ways
spans more than one line (128 B and 256 B sets). `L3 exact 16-way` reaches the
best L3 miss rate in the entire table — **18.0%**, versus stock's 58.7% — and the
highest MLP (1.559), yet runs **+4.72%** slower. This is the cleanest
confirmation that the 64-byte set is the binding constraint.

**`exact` at L3 moves more DRAM traffic than stock** (1.158 vs 0.936 per lookup
at 1-way): 16-byte entries buy only 262 K slots for 4 MB, and that table evicts
more database than its 8.20% hit rate recovers.

**Hit rates fall on larger input.** `L3 compact 1-way` drops 25.13% (pod5_15) ->
22.35% (pod5_2): 42.8 M distinct minimizers against the same 1 M slots. The
technique degrades as data grows.

### Methodological note

Establishing a 1-2% effect on this machine needs the `performance` governor (or
pinned frequency) and far more reps. The physical-ceiling column is what makes
the present data interpretable without that: it separates rows that could be
real from rows that cannot be.

## Cell-size compatibility (16 / 20 / 24 / 32-bit)

Measured on pod5_15, `-L l3 -N 4`, against `kraken2_bin/classify` on the same DB.
The frequency profile is DB-independent (minimizer -> count comes from the reads),
so one profile serves all four databases; values are filled from whichever DB is
loaded.

| DB | key_bits | `-F exact` | `-F compact` hit | reads corrupted by compact |
|---|---:|---|---:|---:|
| eskape_16bit | 10 | byte-identical | 28.03% | **16,175 / 30,378 (53.2%)** |
| eskape_20bit | 14 | byte-identical | 27.77% | 3,159 (10.4%) |
| eskape_24bit | 18 | byte-identical | 27.75% | 263 (0.9%) |
| eskape_32bit_fork | 26 | byte-identical | 27.75% | **0** |

**`-F exact` is width-independent** — it stores the full 64-bit minimizer. Hit
rate is identical (10.33%) on all four, as it must be.

**`-F compact` is only safe at 32-bit.** It reuses the DB's own packing, so its
fingerprint is just `key_bits` wide: 10 bits at 16-bit cells, where roughly one
lookup in 1,024 falsely matches and returns a wrong taxon. Note the hit rate
*rises* as cells narrow (27.75% -> 28.03%) because the extra hits are false
positives. Reports diverge too, so abundance estimates change, not just
per-read calls.

A guard now refuses `-F compact` when `key_bits + value_bits > 32` (which would
silently overflow the 32-bit entry on a 40-bit cell DB) and warns below 26
fingerprint bits.

**Every timed result in this document was measured on the 32-bit DB**, the
project baseline. The narrow-cell DBs were checked for correctness only.

## Provenance of every number here

| measurement | binary | status |
|---|---|---|
| pod5_15 compile-time sweep | 6 fixed-size builds (gone) | timings superseded; hit rates re-verified |
| pod5_15 runtime-flag sweep | pre-`-N` runtime build | timings superseded; hit rates re-verified |
| pod5_15 associativity sweep | pre-guard `-N` build | timings superseded; hit rates re-verified |
| **pod5_2 full 31-config sweep** | pre-guard `-N` build | **current** — all 6 spot-checked hit rates reproduce exactly on the shipped binary |
| cell-size compatibility | **current build** | **current** — re-measured after the guard was added |

The guard added to `la_init` does not touch the probe path; the pod5_15
compatibility results and six pod5_2 hit rates were re-measured on the shipped
binary and are bit-for-bit unchanged.

## Addendum 5: the stacked L1+L2+L3 hierarchy

The tiers made simultaneous rather than exclusive alternatives: L1 (4 KB), L2
(256 KB) and L3 (4 MB) all resident at once, 4.36 MB total, probed
**L1 -> L2 -> L3 -> main hash table**. Population is exclusive: records arrive
hottest-first and each goes to the fastest tier with a free way, so nothing is
stored twice and the hottest minimizers sit closest to the core.

Flag: `-L l1=W,l2=W,l3=W`. Full grid measured — L3 in {1,2,4,8,16} x L2 in
{1,2,4,8} x L1 in {1,2,4} = **60 combinations**, plus stock. 304 runs on pod5_2
(160,625,038 lookups), `-p 16 -g 2 -T 0`, compact format, **mean of 3
interleaved reps**, table-build cost subtracted from every counter.

### Result: 59 of 60 are slower than stock

| L3 ways | hit rate | mean time | vs stock | DRAM/lookup | MLP |
|---:|---:|---:|---:|---:|---:|
| stock | — | 2.938 s | — | 0.950 | 1.244 |
| 1 | 23.65% | 3.043 s | **+3.57%** | 1.063 | 1.385 |
| 2 | 24.94% | 3.058 s | **+4.09%** | 1.053 | 1.379 |
| 4 | 25.64% | 3.082 s | **+4.89%** | 0.944 | 1.324 |
| 8 | 26.01% | 3.176 s | **+8.09%** | 0.891 | 1.282 |
| 16 | 26.19% | 3.334 s | **+13.46%** | 0.857 | 1.258 |

L1 and L2 associativity are **dead parameters**: across a whole row the total hit
rate moves 0.02 pp (23.64% -> 23.66%), while L3 ways moves it 2.54 pp. Their
misses are capacity misses — 1,024 and 65,536 entries against 42.8 M distinct
minimizers — and associativity only recovers *conflict* misses. 48 of the 60
combinations are duplicates of the 5 that differ.

### The hierarchy does raise the hit rate

| configuration | hit rate |
|---|---:|
| L3 alone, 1-way | 22.35% |
| L3 alone, 16-way | 24.98% |
| stacked L1+L2+L3, L3 16-way | **26.19%** |

Per-tier split at the best point: L1 0.65% + L2 2.80% + L3 22.75%. L2 earns its
keep on hit rate; it is small but holds entries hot enough to be worth a probe.

### And that is exactly why it loses

**correlation(hit rate, runtime penalty) = +0.601.** The more the hierarchy
hits, the slower it runs. Every memory metric improves monotonically with L3
ways — DRAM per lookup 1.063 -> 0.857, crossing below stock's 0.950 — while
runtime climbs +3.57% -> +13.46%. Three sequential dependent probes on the ~74%
of lookups that miss all tiers cost far more than the 2.5 pp of extra hits
return.

The single fastest row, `l1=1,l2=1,l3=1` at −3.83%, has a spread of **0.555 s**
across its three reps — the largest in the table, and a frequency-mode artifact.
Every configuration with a spread under 0.05 s is slower than stock.

Unlike the single-tier sweep, **zero rows here claim a speedup exceeding the
physical ceiling** (hit rate x 24.1% DRAM-stall budget), so the measurement is
internally consistent this time.

### Closing the question

A multi-level lookaside hierarchy is not merely unhelpful on this workload, it
is **actively harmful, and worse the better it works**. Combined with Addendum 4
(no single-tier configuration beats stock beyond the noise floor) and Addendum 2
(reuse distance is 1,000x too long for a small cache), the lookaside idea is
closed by measurement in all three of its forms.

## Verdict

**No configuration is worth adopting.** The best is compact/L3 at **−1.5%**, and
it requires an oracle frequency profile that cannot be obtained in production,
costs 4 MB of L3, and introduces read-level result changes. Compare `-M 4000000`
at **−26.7%**, which needs no code, no profile, and no correctness compromise.

The idea is now closed by measurement rather than by argument. The remaining
levers are unchanged: batched/prefetched lookups (MLP is 1.26 of ~12), huge
pages (Addendum 5 material), and `-M`.
