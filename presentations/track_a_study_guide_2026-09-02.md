# Track A — Full Study Guide

This is the deep version: every code change, exactly where it lives, why it was written that way, how it was measured, what it found, and the questions most likely to come up. Built to study from, not to present from — read `track_a_progress_2026-09-02.md` first if you want the narrative shape before diving into this.

**How this is organized:** one section per build stage (S0 → S5). Each stage has the same five parts — *Why*, *The code*, *How it was measured*, *Results*, *Likely questions*. After the stages: the four structured reviews in full, Track B, a master Q&A bank, the full commit ledger, and a glossary at the very end for anything unfamiliar on first read.

---

## Glossary — read this first if a term below is unfamiliar

- **k-mer** — a short, fixed-length substring of a DNA read (Kraken2 uses length *k*, typically 35). A read gets sliced into overlapping k-mers.
- **minimizer** — the lexicographically smallest k-mer inside a sliding window of the read. Kraken2 looks up *minimizers*, not every k-mer, to cut the number of lookups.
- **hash table lookup / `Get()`** — Kraken2 stores a giant table mapping minimizer → taxon (species/genus ID), built once from reference genomes. Classifying a read means calling `Get()` once per minimizer. This table is tens to hundreds of gigabytes — essentially random access into RAM.
- **LLC / L3 cache** — the Last-Level Cache, the biggest, slowest tier of on-chip CPU cache before you fall all the way to RAM. Luna's is 105 MiB *per socket* (measured, not assumed — see S3). A "cache miss" here means the CPU had to go all the way to RAM, which is slow.
- **cache line** — the smallest unit a CPU cache moves at a time (typically 64 bytes). Structs are often sized/aligned with this in mind.
- **`thread_local`** — a C++ storage class: each OS thread gets its own private copy of the variable. Used here so each of Kraken2's parallel worker threads has its own cache, no locking needed.
- **TLS (Thread-Local Storage)** — the mechanism the OS/runtime uses to actually implement `thread_local`. There are two flavors that matter here: **static TLS** (space reserved in a fixed block at thread-creation time, size-limited, competes with the thread's stack budget) vs. a **`thread_local` pointer to heap memory** (the pointer itself is tiny and static-TLS-resident; the actual data lives on the heap with no size ceiling). S3.0's whole fix is switching from the first to the second.
- **glibc / NPTL** — the C library and threading library on Linux. `NPTL`'s `allocate_stack()` is the function that computes how much stack space a new thread gets, and it's the one that subtracts static-TLS size from the requested stack size — the mechanism behind the S2/S3 crash.
- **`calloc` vs `new[]`** — both allocate memory, but `calloc` promises zero-initialized memory and, for large allocations, the OS can satisfy that lazily (see next entry). `new[]` on a type with non-trivial default member initializers runs a real constructor loop that touches every byte immediately, right away, no matter what.
- **Lazy zero-page / copy-on-write allocation** — when you ask the OS for a large block of guaranteed-zero memory, it doesn't actually go touch every page — it maps all of it to one shared, already-zeroed physical page, and only allocates a real, private page the first time your program *writes* to a given page. This is fast if you don't touch most of the memory. S3.3 is entirely about not defeating this optimization.
- **MurmurHash3** — a well-mixed, non-cryptographic hash function already used elsewhere in Kraken2. "Mixing" a value through it means every output bit depends on every input bit — the opposite of a raw bit-mask, which only looks at a value's low bits and ignores the rest.
- **Set-associative cache** — instead of one specific slot per key (direct-mapped) or "anywhere" (fully associative), a key hashes to one *set*, and within that set there are a few *ways* (candidate slots) it could occupy. S2 is 4-way: 4 candidate slots per set.
- **Eviction policy** — the rule for which entry gets thrown out of a full set to make room for a new one. Round-robin (cycle through ways in order), pinned/"protect on hit" (never evict something that's ever been used), pseudo-LRU (evict the least-recently-used), admission control (a different lever entirely — decide whether to let a new entry in at all, rather than which old one to evict).
- **Reuse distance** — for a repeated lookup, how many *other* lookups happened in between the two times it was seen. A cache with N slots can only "catch" a repeat if its reuse distance is smaller than roughly N (for that eviction policy).
- **Occupancy / max-over-mean** — how evenly lookups spread across a cache's sets. A raw bit-mask with no hash mixing can send wildly uneven traffic to different sets; `max/mean` close to 1 means even spread, `max/mean` of 225 (S4.0's finding) means one set got 225× its fair share.
- **IPC (instructions per cycle)** — how much useful work the CPU does per clock tick. Drops when the CPU is stalled waiting on memory.
- **Memory-level parallelism (MLP)** — how many memory requests are "in flight" (outstanding) at once. A modern core can have roughly a dozen outstanding; one lookup at a time (MLP ≈ 1) wastes that capacity. Software prefetching (S5) is entirely about raising this number.
- **Software prefetching / batching** — instead of "look up A, wait, look up B, wait, ...", issue prefetch hints for A, B, C, D all at once, then resolve them once the data has had time to arrive — overlapping the wait time instead of paying it serially.
- **NUMA node / socket / Sub-NUMA Clustering (SNC)** — Luna has 2 CPU sockets, each with its own local RAM and its own L3 cache. `numactl --cpunodebind=0 --membind=0` pins a run to one socket so it doesn't pay cross-socket latency. SNC (not enabled on Luna, confirmed via `lscpu -e`) would otherwise split a socket's L3 into smaller independent chunks.
- **Page-cache confound** — the OS caches recently-read file bytes in RAM. If you benchmark A, then B, right after, B can look artificially fast just because A already warmed the OS's file cache — nothing to do with either binary's code. Fixed throughout this project by *interleaving* runs (A, B, A, B, A, B...) instead of running them back to back in blocks.
- **CV% (coefficient of variation)** — standard deviation ÷ mean, as a percentage, across repeated runs of the same config. Low CV% (this project's threshold: ≤5%) means the measurement is trustworthy, not buried in noise.
- **Double hashing vs. linear probing** — Kraken2's hash table handles a collision (two keys hashing to the same cell) by looking at the *next* cell (linear probing, clumps) or by computing a second, independent hash to decide how far to jump (double hashing, spreads out). This is Track B's B1, not part of Track A.

---

## The big picture, before any code

**What Kraken2 does, in one paragraph.** Kraken2 identifies which species a DNA sequencing read comes from. It does this by chopping every read into overlapping short fragments (k-mers), picking one representative fragment per window (a minimizer — see glossary), and looking each one up in a giant table built once from reference genomes. That table is tens to hundreds of gigabytes and lives mostly in RAM, not cache — so almost every lookup is a genuine trip out to main memory, which is slow. Classifying a read is, computationally, "do millions of these lookups, as fast as possible."

**What "the adaptive k-mer cache" (Track A) is trying to do, in one paragraph.** If the same minimizer gets looked up more than once — which happens a lot, because real genomes repeat sequences — then remembering the answer the first time and reusing it the second time skips an expensive trip to RAM. A cache is just that: a small, fast piece of memory that remembers recent answers. The word "adaptive" is doing three jobs, one per stage group below: **S1–S2** ask "how many things can it remember, and how" (capacity/structure), **S3** asks "how big should it be, automatically, on whatever machine it's running on" (hardware-awareness), and **S4** asks "when it's full, what should it forget first" (eviction policy). **S5** is a related but different idea — instead of trying to *avoid* the expensive lookup, make the expensive lookup itself faster by overlapping many of them at once.

**Why every stage below has a "Why" and a "Results" that can genuinely disagree.** This work follows real evidence, not a plan written in advance. Several stages built something with a clear rationale and then measured a real, honest **null result** — no benefit — and that null result became the *reason* for the next stage rather than a discouragement. One stage (S4) went further: a result we'd already reported as a win turned out to be wrong once a separate bug was fixed, and we reversed our own conclusion in public rather than quietly building on top of it. That's not a detour from the "real" story — reporting it honestly *is* the story, and it's the part worth being able to explain clearly if asked about it directly.

**The stage map:**

| Stage | One-line question it answers |
|---|---|
| S0 | What's our honest starting-point measurement, on the version of Kraken2 we're actually building on? |
| S1 | Does Kraken2 already remember *anything*? Can we get more out of that for free? |
| S2 | Can we build the multi-slot cache sir specifically asked for? |
| S3 | Can we make that cache size itself correctly to whatever machine it's running on, without crashing or slowing things down? |
| S4 | When the cache is full, what should it throw away first? |
| S5 | Different question: can we make the *expensive lookup itself* faster, instead of trying to avoid it? |

---

## S0 — Rebaselining before writing any cache code

### Why

We had an old number (4.405s) from the cell-width report — but that was measured on Kraken2 **v2.1.3**. Before writing a single line of cache code, you'd already told us to build on current upstream instead: **v2.17.1**. This matters because v2.1.4 rewrote the exact FASTA/FASTQ parser code this project profiles — the two versions aren't doing comparable work at the byte level, so comparing a v2.17.1 number against the old v2.1.3 number would be comparing apples to a different, related fruit. Everything from S1 onward needed a fresh, honest starting point on the tree we were actually going to modify.

### What we did (no cache code yet — this is pure measurement)

```bash
cd ~/tools
for i in $(seq 1 30); do
  rm -rf kraken2-src-fresh
  git clone https://github.com/DerrickWood/kraken2.git kraken2-src-fresh && break
  sleep 5
done
cd kraken2-src-fresh
git fetch --tags
git checkout v2.17.1          # confirmed the latest tag via `git tag --sort=-creatordate`
```

Then a 3-database × 5-thread sweep (15 configurations, 1 run each — directional, not the project's usual 5-run/CV-checked treatment):

```bash
for db in sample_targeted standard_8gb pluspf_103gb; do
  for t in 1 16 32 64 96; do
    perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
      numactl --cpunodebind=0 --membind=0 \
      ~/tools/kraken2-fresh-bin/kraken2 --db ~/AccuracyDrift/databases/$db \
      --threads $t --output /dev/null --report /dev/null \
      ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
  done
done
```

**What each flag means, since this exact command reappears at every stage from here on:**
- `perf stat -e ...` — wraps the run and reports hardware counters: how many memory accesses missed cache (`cache-misses`), how many missed specifically at the last level (`LLC-load-misses`), and how many CPU instructions completed (used to compute IPC).
- `numactl --cpunodebind=0 --membind=0` — pins the process to CPU socket 0 and forces its memory to come from socket 0's local RAM, so a two-socket machine's cross-socket latency doesn't contaminate the numbers.
- `--threads N` — how many OpenMP worker threads classify reads in parallel.
- `--output /dev/null --report /dev/null` — discards Kraken2's actual classification output; at this stage we only care about speed, not correctness (that gap gets closed explicitly at S2).

### Results

| DB | Threads | Elapsed | Cache-miss % | LLC-miss % | IPC |
|---|---|---|---|---|---|
| sample_targeted (50MB) | **32** | **0.576s** | 14.85% | 12.65% | 1.75 |
| standard_8gb (7.6GB) | 32 | 4.233s | 93.18% | 90.47% | 1.65 |
| pluspf_103gb (103.4GB) | 32 | 51.897s | 96.45% | 95.59% | 1.08 |

*(Full 15-row table in `track_a_appendix_2026-09-02.md`.)* **`sample_targeted`/32T (0.576s) becomes the anchor number every later stage compares against.** Notice the cache-miss% pattern: `sample_targeted` is small enough to mostly fit in cache already (~13-15% miss), while `standard_8gb` and `pluspf_103gb` are the two databases where an actual cache stands to matter — they're missing 85-96% of the time already, meaning almost every lookup is a real trip to RAM.

### Likely questions

**Q: "Why does the anchor number use 32 threads specifically?"**
A: 32–64 threads is the practical sweet spot on this machine across all three databases — IPC (instructions per cycle, a measure of how much useful work the CPU is doing per clock) drops steadily as thread count climbs past that, and 96 threads is measurably worse everywhere in this sweep. It matches the thread count the project has used as its standard config since before this pivot.

**Q: "Is 0.576s a real, trustworthy number?"**
A: Directionally yes, but it's explicitly flagged in our own log as 1 run per configuration — not the project's usual 5-run, coefficient-of-variation-checked treatment. If a specific number from this table needs to go in the paper as a final, citable figure, it should be re-run with that fuller methodology first.

---

## S1 — Kraken2 already had a 1-slot cache; we gave it memory

### Why

Before writing anything new, we went looking at Kraken2's actual `Get()` call site to understand exactly what we'd be modifying. We found stock Kraken2 already does *something* here: if the current minimizer is identical to the one immediately before it, it skips the lookup and reuses the previous answer. But this memory is scoped to a single function call (`ClassifySequence`, called once per read/mate/translated-search-frame) and is wiped every time that function returns — so it only ever catches "the same minimizer twice in a row," never "I saw this minimizer three reads ago." The fix: make that memory live for a whole thread's lifetime instead of one function call.

**Why this is safe:** `hash->Get()` is a *pure function* — same minimizer in, same taxon out, every time, no matter what else has happened. So whatever a thread most recently learned for a given minimizer stays correct for that thread to reuse on any future read it processes, not just the very next one.

### The code

**File:** `classify.cc`. Two new variables declared at file scope, immediately above `ClassifySequence()`:

```cpp
// S1.1 - thread-local single-slot minimizer cache. One instance per OS
// thread (each OpenMP worker owns its own copy), persisting across every
// read/mate/frame that thread processes - unlike the old last_minimizer/
// last_taxon pair below, which used to be local to one ClassifySequence
// call and forgot everything the moment that call returned. Safe to
// share this widely because hash->Get() is a pure function of the
// minimizer value: whatever thread last computed an answer for a given
// minimizer, that answer is still correct for any other read that thread
// processes next.
static thread_local uint64_t s1_last_minimizer = UINT64_MAX;
static thread_local taxid_t s1_last_taxon = TAXID_MAX;
```

The old function-local pair that used to live inside `ClassifySequence()`'s loop gets deleted outright:

```cpp
// BEFORE (removed):
      uint64_t last_minimizer = UINT64_MAX;
      taxid_t last_taxon = TAXID_MAX;
      while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {

// AFTER:
      while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {
```

...and every reference to the old names inside the function body is renamed to point at the new thread-local pair:

| Old | New |
|---|---|
| `*minimizer_ptr != last_minimizer` | `*minimizer_ptr != s1_last_minimizer` |
| `last_taxon = taxon;` | `s1_last_taxon = taxon;` |
| `last_minimizer = *minimizer_ptr;` | `s1_last_minimizer = *minimizer_ptr;` |
| `taxon = last_taxon;` | `taxon = s1_last_taxon;` |

**A real risk that was checked, not assumed away:** `MinimizerScanner` has its own unrelated method called `last_minimizer()` elsewhere in the file. A careless find-and-replace across the whole file could have accidentally mangled `scanner.last_minimizer()` into `scanner.s1_last_minimizer()`, which wouldn't compile (it's a method call, not a variable). The patch script's replacements target the variable in assignment/comparison position specifically, which doesn't textually match the method-call syntax — confirmed safe by a full-file grep before the patch ever ran, not by luck.

### How it was measured — and a real confound we caught and fixed

**First attempt (flawed):** rebuilt with the patch, ran the exact same 1-run sweep used for S0. Result looked promising but was actually broken: `pluspf_103gb` at 1 thread showed a 22% wall-clock improvement but its LLC-miss rate got *10 points worse* — a contradiction that shouldn't happen from a real code change. Diagnosis: a **page-cache confound** (see glossary) — the S1 sweep ran right after the S0 sweep had already read that same 103GB file once, so parts of it were sitting in the OS's file cache, making S1 look artificially fast for reasons that had nothing to do with the code.

**Fixed methodology:** built two separate, permanent binaries (`kraken2-fresh-bin-s0` unpatched, `kraken2-fresh-bin-s1` patched), then ran both **interleaved** — S0, S1, S0, S1, S0, S1 per configuration, 3 reps each, never in back-to-back blocks — so neither binary gets an unfair page-cache head start. This interleaved-3-run pattern becomes the standard methodology for every comparison in this project from here on.

### Results

| DB | Result |
|---|---|
| `standard_8gb` | LLC-miss% flat (diffs <0.7pp, no direction), wall-clock within ~2% — noise |
| `pluspf_103gb` | LLC-miss% flat, wall-clock 62.03s (S0) vs 61.95s (S1) at T=1 — 0.1% diff, noise |
| `sample_targeted` | Real 5–13% wall-clock speedup at 16T–96T, but **no** corresponding cache-metric change — real, unexplained, not claimed as a caching effect |

**Why this counts as a real, useful result and not a failed step:** a single cache slot's odds of matching the *next* lookup shrink toward zero as the number of distinct minimizers in a database climbs into the millions — that's exactly the pattern we see: no benefit on the two big, genuinely cache-miss-heavy databases. This is direct, measured evidence (not a guess) that a 1-slot design has a hard ceiling, and it's the concrete reason S2 (a multi-slot cache) is worth building next.

### Likely questions

**Q: "Didn't Kraken2 already have this? What did you actually add?"**
A: Kraken2 already had the *comparison logic* (is this minimizer the same as the last one). What it didn't have was *memory* — the old version forgot everything the instant one read finished processing. We changed where that memory lives (from a local variable to `thread_local` storage), not the comparison logic itself.

**Q: "Why didn't this help on the big databases?"**
A: Because remembering only the *one* most recent minimizer only pays off if the very next lookup happens to be a repeat of that exact one. On a database with millions of distinct minimizers, the odds of that happening are vanishingly small — you need to remember more than one thing at a time, which is exactly what S2 does next.

---

## S2 — the 4-way set-associative cache, and the audit that caught a real wiring bug

### Why

Sir's specific ask for Thesis 1's baseline was a 4-way set-associative cache — instead of one candidate slot per minimizer, give each minimizer 4 candidate slots (a "set" of 4 "ways"), so two different, both-useful minimizers landing in the same set don't have to fight over one spot. S1 gave S2 a concrete, evidenced reason to exist rather than being redundant: a 1-slot cache's hit odds vanish on large databases, so give it real capacity.

### The code

**File:** `classify.cc`, built directly on top of S1.1's patch. New state, inserted at file scope:

```cpp
static const size_t S2_NUM_SETS = 4096;              // must be a power of 2
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;      // "nothing here yet" - matches S1's convention

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
};

static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};  // S2.3: round-robin eviction pointer per set
```

`S2Entry` is exactly two 8-byte fields (`tag` is `uint64_t`; `taxon` is `taxid_t`, itself a `uint64_t` typedef in Kraken2) — **16 bytes, zero padding.** At 4,096 sets × 4 ways × 16 bytes, that's 256KB per thread — small enough to live comfortably inside one CPU's L2 cache.

Three new functions:

```cpp
// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

// S2.2: check all 4 ways in the target set. Returns true and fills
// *out_taxon on a hit; on a miss, *out_taxon is left untouched.
static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      return true;
    }
  }
  return false;
}

// S2.3: insert/overwrite via simple round-robin - always evict whichever
// way is "next" for this set, then advance the pointer. Deliberately
// simple; S4 replaces this with a smarter policy later.
static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx][way].tag = minimizer;
  s2_cache[set_idx][way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}
```

> [!IMPORTANT]
> **`S2SetIndex` is a raw bitmask (`minimizer & (S2_NUM_SETS - 1)`) — it does not mix the minimizer's bits at all before picking a set.** This looks completely reasonable and is exactly what S4.0's diagnostic, months later, finds is badly broken (one set absorbing 225× the average load). It's worth being able to point at this exact line when the S4 story comes up — the bug was present from S2's very first commit, not introduced later.

**A correctness bug caught before it was ever written to disk — the actual comment left in the code:**

```cpp
// IMPORTANT - correctness boundary: S2Lookup/S2Insert decide ONLY whether
// hash->Get() needs to run again. They must NEVER be used to decide whether
// minimizer_hit_groups gets incremented or curr_taxon_counts gets updated
// below - that gating stays tied to "different from the immediately
// preceding minimizer" (s1_last_minimizer), exactly as stock Kraken2 always
// did it. Wiring S2's broader cache into that decision would silently
// change what gets counted in the classification report (species counts,
// --quick-mode's early-exit threshold) - a correctness bug, not a
// performance change. Speed and statistics are kept deliberately separate.
```

In plain terms: Kraken2's classification report counts how many times each species' k-mers showed up, and `--quick-mode` uses a running count to decide when it has enough evidence to stop early. Stock Kraken2 only updates those counts when a minimizer differs from the one immediately before it — S2's cache, if wired in carelessly, would have caught *far more* repeats than that (across a much wider span than just "immediately before"), which would have silently suppressed far more counts than intended and changed the actual report output. The fix was to keep S2's cache completely separate from that counting logic — S2 only ever decides "do I need to call the expensive lookup again," never "does this count toward the report."

**Where S2 actually plugs in — and this is where the nesting bug lives, visible directly in the diff:**

```cpp
// BEFORE:
            taxon = 0;
            if (! skip_lookup)
              taxon = hash->Get(*minimizer_ptr);
            s1_last_taxon = taxon;

// AFTER:
            taxon = 0;
            if (! skip_lookup) {
              // S2.2/S2.3 - try the 4-way cache before paying for a real
              // hash table lookup. This ONLY decides whether Get() runs -
              // it does not touch the stats-counting logic below.
              if (! S2Lookup(*minimizer_ptr, &taxon)) {
                taxon = hash->Get(*minimizer_ptr);
                S2Insert(*minimizer_ptr, taxon);
              }
            }
            s1_last_taxon = taxon;
```

`skip_lookup` is set elsewhere in the function based on S1's check (`*minimizer_ptr != s1_last_minimizer`). **`S2Lookup`/`S2Insert` only run inside that existing `if` block** — meaning whenever a minimizer matches the one immediately before it, `skip_lookup` is true, the whole block (S2 included) gets skipped, and S2 never even sees that lookup. S2 only ever receives the *residual* stream that already failed S1's filter — not the full lookup stream, the way "sir's baseline" implies it should. This is exactly what the independent audit found (below), and it's a direct, mechanical consequence of the minimal-diff approach: touching only the `Get()` call site and leaving everything around it alone meant the new code inherited the *existing* conditional's scope.

### The audit — 5 agents, 3 rounds, run from a fresh session with zero prior context

First read of S2 looked like "no benefit" (LLC-miss% differences vs. S0/S1 all within ~0.5 percentage points). Rather than trust that, we ran an independent verification audit specifically to check it — a fresh Claude session with no memory of building S2, given only the log of what was claimed, and told explicitly not to take the summary as ground truth.

| Q | Question | Verdict |
|---|---|---|
| Q1 | Is S2 nested inside S1's gate? | CONCERN FOUND (4/5 agents) — real, but weaker bite than it sounds: S1 fires at ~0% on the two databases (`standard_8gb`, `pluspf_103gb`) the "no benefit" conclusion actually rests on |
| Q2 | Is the correctness-boundary comment's argument actually sound? | CONCERN FOUND (5/5) — sound as narrated, but rests on two things nobody had verified yet: that `Get()` really has no side effects, and that `S2Lookup` can't accidentally match the wrong minimizer to the wrong tag |
| Q3 | Is "no benefit" real, or a symptom of a bug? | CANNOT VERIFY (3/5) — because **zero internal hit/miss counters existed** at this point. Every conclusion up to now rested only on external proxies (wall-clock time, `perf`'s LLC-miss%), which can't distinguish "the cache rarely hits" from "the cache never even gets a chance to" |
| Q4 | Is the memory-init-cliff theory (from an earlier size sweep) right? | CONFIRMED as the leading hypothesis, arithmetic checked directly: 4,194,304 sets × 4 ways × 16 bytes ≈ 256MB *per thread*, × 96 threads ≈ 24GB touched before any real classification work even starts |
| Q5 | Does the missing correctness check block trusting anything? | CONCERN FOUND (5/5, no dissent — the strongest consensus of the eight) — every benchmark up to this point used `--output /dev/null`, meaning classification correctness had never actually been checked, only speed |
| Q6 | Does the v2.1.3→v2.17.1 version switch put any paper claims at risk? | CONCERN FOUND (5/5 by round 2) — and broader than first thought: nobody had checked whether `kraken2-build`'s own hash-construction logic changed across the ~2.5 years between versions, only the read-side parser |
| Q7 | Is the project on pace? | CONCERN FOUND (5/5) — second consecutive week missing its own stated target |
| Q8 | Anything else? | Eight numbered items, including: the shared Luna account already has a data-loss precedent (2 ESKAPE databases lost before); `-M`/memory-mapping (this project's own prior 12–14× finding) had never been used in any S0/S1/S2 benchmark; a stale ledger; a ~5.5-hour timestamp drift in the log's early entries; and — worth noting because it shows the audit checking *itself*, not just us — the audit's own setup brief claimed "real diffs are embedded in the log," which the audit found to be false |

**What we fixed, and how we know it worked — not by taking the audit's word for it, by testing directly:**

We built a **standalone** variant (`s2_standalone_patch.py`, code below) that wraps `hash->Get()` directly, with no S1 layer in front of it at all, plus real hit/miss counters this time. This let us test Q1 and Q3 directly.

```cpp
// New in the standalone variant - real, live counters:
static std::atomic<uint64_t> s2_hits{0};
static std::atomic<uint64_t> s2_misses{0};
static void S2PrintStats() {
  uint64_t hits = s2_hits.load(), misses = s2_misses.load();
  uint64_t total = hits + misses;
  fprintf(stderr, "[S2-STANDALONE] size=%zu ways=%zu hits=%llu misses=%llu total=%llu hit_rate=%.4f%%\n",
          S2_NUM_SETS, S2_WAYS, hits, misses, total, total ? (100.0 * hits / total) : 0.0);
}
struct S2StatsRegistrar { S2StatsRegistrar() { atexit(S2PrintStats); } };
static S2StatsRegistrar s2_stats_registrar;
```

The lookup site is un-nested — the new cache check now wraps `hash->Get()` directly, gated only by stock Kraken2's own original (unmodified, function-local, resets every call) adjacent-repeat check, not S1's widened thread-local one:

```cpp
            taxon = 0;
            if (! skip_lookup) {
              if (! S2Lookup(*minimizer_ptr, &taxon)) {
                taxon = hash->Get(*minimizer_ptr);
                S2Insert(*minimizer_ptr, taxon);
              }
            }
            last_taxon = taxon;
```

**Result: un-nesting changed nothing, statistically, on the two databases that matter.** Real hit rate, flat across every thread count: **0.403% on `standard_8gb`, 0.141% on `pluspf_103gb`/`sample_targeted`.** The nesting bug was real, worth fixing eventually, but not the reason S2 showed no benefit — **capacity is the actual limit**: 4,096 sets × 4 ways is tiny compared to the millions of distinct minimizers these databases contain.

**One more thing this test found, unprompted:** the hit/miss counters above are *global* `std::atomic` variables, incremented from every thread on every single lookup. On `sample_targeted` specifically (where each `Get()` call is already fast), this created real cache-line contention that made that database's run ~3× slower — an artifact of the *measurement technique*, not the cache design. `standard_8gb`/`pluspf_103gb` were unaffected (their `Get()` calls are already so slow that the counter overhead is noise by comparison). Lesson: `sample_targeted`'s counter-instrumented wall-clock numbers from this specific test shouldn't be trusted; the hit-rate percentages themselves are fine.

**Correctness, finally checked directly (closing Q5):**

```bash
~/tools/kraken2-fresh-bin-s0/kraken2 --db .../sample_targeted --threads 1 \
  --output s0_output.txt --report s0_report.txt ...
~/tools/kraken2-fresh-bin-s2/kraken2 --db .../sample_targeted --threads 1 \
  --output s2_output.txt --report s2_report.txt ...
diff s0_output.txt s2_output.txt && echo "IDENTICAL"
diff s0_report.txt s2_report.txt && echo "REPORT IDENTICAL TOO"
```
Both diffs came back completely empty. **The cache never changes which species a read gets classified as** — it only changes whether a lookup goes through the real hash table or the cache.

### Eviction policy — a real, separate lever, discovered by testing it directly

**Why we asked this:** the hit rate (0.14–0.40%) is low, but a much earlier finding in this project measured 90.7% *global* k-mer reuse. Those two numbers aren't actually in tension — high global reuse can coexist with a near-zero *cache* hit rate if repeats are separated by more distinct lookups than the cache has room to remember, and plain round-robin evicts a proven-useful entry the instant its turn comes up, no matter how recently or often it was hit. We tested whether protecting proven-useful entries would help.

**The code** (`s2_pinned_patch.py` — one new field, one new line in `S2Lookup`, and `S2Insert` rewritten):

```cpp
struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
  bool was_hit = false;   // NEW - "has this entry proven itself since it was inserted"
};
```

`tag` (8B) + `taxon` (8B) + `was_hit` (1B, but padded to the next 8-byte boundary by the struct's alignment) = **24 bytes, not 16** — a real, ~50% growth in per-entry footprint that's easy to miss if you only look at the outcome and not the code.

```cpp
static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      s2_cache[set_idx][way].was_hit = true;   // NEW - mark proven-useful
      s2_hits.fetch_add(1, std::memory_order_relaxed);
      return true;
    }
  }
  s2_misses.fetch_add(1, std::memory_order_relaxed);
  return false;
}

static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  // Prefer evicting a way that has NEVER been hit - the "pinning" rule.
  uint8_t victim = S2_WAYS;   // sentinel: "no unproven way found yet"
  for (uint8_t way = 0; way < S2_WAYS; way++) {
    if (! s2_cache[set_idx][way].was_hit) { victim = way; break; }
  }
  if (victim == S2_WAYS) {
    // Every way in this set has proven itself - fall back to round-robin
    // so we always make forward progress and never get stuck.
    victim = s2_next_way[set_idx];
    s2_next_way[set_idx] = (victim + 1) % S2_WAYS;
  }
  s2_cache[set_idx][victim].tag = minimizer;
  s2_cache[set_idx][victim].taxon = taxon;
  s2_cache[set_idx][victim].was_hit = false;   // the new entry hasn't proven itself yet
}
```

In plain terms: on every insert, scan the 4 ways left-to-right and evict the first one that's *never* been hit. Only if all 4 ways have proven themselves does it fall back to plain round-robin. A brand-new entry always starts "unproven" — so it's immediately eligible to be evicted again if nothing hits it before the next insert into that set.

**Result:** hit rate on `standard_8gb`, T=1, 4,096 sets: round-robin **0.4035%** vs. pinned **0.5050%** — a **+25.2% relative gain**, same set/way count. Real evidence eviction policy is an independent lever, worth the effort S4 later spends on it. *(Caveat worth remembering: the entry-size growth above means this isn't a perfectly isolated variable — see the S4 reversal section for why this ends up not changing the final conclusion's direction.)*

**Full sweep across three sizes** confirmed the trend generalizes, and shrinks as capacity grows:

| Size | RR hit rate | Pinned hit rate | Pinned's relative gain |
|---|---|---|---|
| 4,096 | 0.4035% | 0.5050% | +25.2% |
| 65,536 | 0.7675% | 0.8346% | +8.7% |
| 262,144 | 1.4229% | 1.4843% | +4.3% |

Also found in the same sweep: **262,144 sets segfaults at 16+ threads** (clean at T=1) — a genuine crash, distinct from an earlier-found slowdown at ≥1,048,576 sets. This becomes S3.0's problem to fix.

### Likely questions

**Q: "Is the nesting bug still in the code right now?"**
A: It's tested and shown not to matter for the "no benefit" conclusion — but no, it was never actually merged into the tree everything else (S3, S4, S5) is built on. That tree still has S2 nested inside S1's gate. It's a real cleanup item before publication, but it's a documentation/tidiness issue now, not a live bug affecting any of our numbers, because we specifically tested the un-nested version and got the same result.

**Q: "If the hit rate is under 1%, why does any of this matter?"**
A: Because the low hit rate itself is a real, diagnosed finding, not a dead end — it's exactly what motivated checking whether the *hashing* (which set a minimizer goes to) was working correctly, which is what S4.0 checks next, and finds it wasn't.

---

## S3 — fixing the crash, sizing the cache to real hardware

### Why

Two problems needed solving before the cache could safely grow past the 4,096-set default: a real **crash** at 262,144+ sets under multi-threading (found at the end of S2), and the cache needed to size *itself* to whatever machine it's running on, per sir's ask — not stay hardcoded at 4,096 forever. Before writing any fix, a second structured design debate (5 agents, 3 rounds) checked our assumptions:

- **`S2Entry` is exactly 16 bytes, zero padding** — confirmed directly from the struct (not assumed).
- **Luna's real per-socket LLC is ~105MB, not 210MB** — 210MB is the *two-socket* sum; every benchmark in this project runs pinned to one socket via `numactl`, so the number that actually matters is half that.
- **None of the four closest comparator tools** (kache-hash, MegIS, MetaCache-GPU, GPMeta) **implement any eviction policy for a k-mer lookup cache** — confirmed independently by all 5 agents, a real citable gap.

### Confirming the crash mechanism directly, before writing a fix

```bash
ulimit -s        # -> 8192 (8MB default stack per thread)
ulimit -a         # -> every other limit (memory, virtual memory) is "unlimited" - rules out
                   #    a cgroup/ulimit memory cap as an alternate theory
```

The crashing array at 262,144 sets is **16MB per thread — literally twice a thread's entire default stack budget**, before any other arithmetic. And confirming the real LLC size directly rather than continuing to assume it:

```bash
lscpu -e                          # confirms 1:1 NUMA-node <-> socket mapping (no Sub-NUMA Clustering)
lscpu | grep -iE "l3|numa|socket"  # L3 cache: 210 MiB (2 instances) = 105 MiB per socket
```

### S3.0 — the crash fix: heap-allocated pointer instead of a static array

**Before** (the array itself lives directly in glibc's fixed-size static TLS block):
```cpp
static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};
```

**After** (only an 8-byte *pointer* lives in that block; the real data is heap-allocated, lazily, the first time each thread touches the cache):
```cpp
#include <memory>

static thread_local std::unique_ptr<S2Entry[]> s2_cache;
static thread_local std::unique_ptr<uint8_t[]> s2_next_way;

static inline void S2EnsureInit() {
  if (! s2_cache) {
    s2_cache.reset(new S2Entry[S2_NUM_SETS * S2_WAYS]);
    s2_next_way.reset(new uint8_t[S2_NUM_SETS]());
  }
}
```

Note the array becomes **flat 1D** here (`S2_NUM_SETS * S2_WAYS` elements) — a `unique_ptr<S2Entry[]>` can't be subscripted `[][]` the way a real 2D array can, so every access site needs manual index math from here on: `s2_cache[set_idx][way]` becomes `s2_cache[set_idx * S2_WAYS + way]`. `S2EnsureInit()` is called at the top of both `S2Lookup` and `S2Insert`; the `if (! s2_cache)` check (a `unique_ptr`'s bool conversion) is true only the very first time a given thread touches the cache, so the heap allocation happens exactly once per thread.

**Verified crash-free** at 16T (0.511s), 32T (0.500s), 96T (0.515s) — all classifying the identical 25,645/30,378 reads — where the pre-fix binary segfaulted (exit code 139) at every one of those thread counts. Correctness re-checked: byte-identical output vs. S0. Tagged `safe/S3.0`.

### S3.1/S3.2 — the real sizing formula

**Before:** `S2_NUM_SETS` is a hardcoded compile-time constant (4,096), and `S2SetIndex` masks against it directly.

**After** — replaced with a live, thread-count-aware formula:
```cpp
static const uint64_t S3_LLC_PER_SOCKET_BYTES = 105ULL * 1024 * 1024;   // confirmed via lscpu
static const double S3_LLC_FRACTION = 0.25;     // safety fraction - placeholder, not yet tuned
static const size_t S3_MAX_SETS = 262144;        // S3.0's confirmed crash-free ceiling
static const size_t S3_MIN_SETS = 4096;          // this project's long-validated floor

static thread_local size_t s2_num_sets = 0;

static inline size_t S3ComputeNumSets() {
  int t = omp_get_num_threads();
  if (t < 1) t = 1;
  uint64_t raw = (uint64_t) (S3_LLC_FRACTION * S3_LLC_PER_SOCKET_BYTES
                             / (S2_WAYS * sizeof(S2Entry) * (uint64_t) t));
  size_t sets = S3_MIN_SETS;
  while (sets * 2 <= raw && sets * 2 <= S3_MAX_SETS)
    sets *= 2;
  return sets;
}
```

**How the arithmetic actually works, in plain terms:** `raw` is the ideal number of sets — how many sets would exactly fill `S3_LLC_FRACTION` (a quarter) of the machine's real per-socket cache, given how many bytes one entry costs (`S2_WAYS × sizeof(S2Entry)` per set) and how many threads are going to be dividing that cache up between them. The `while` loop then rounds that down to the nearest power of 2 (`S2SetIndex` needs a clean bitmask, so the set count must be a power of 2) by doubling from the floor as long as doing so wouldn't overshoot either the ideal value or the hard ceiling — which also automatically enforces the `[4096, 262144]` clamp for free, with no separate bounds-check needed.

`omp_get_num_threads()` returns the real `--threads N` value specifically *because* this function only ever gets called from inside the live OpenMP parallel classification region (via `S2EnsureInit()`, called from `S2Lookup`/`S2Insert`) — outside a parallel region, that same call would just return 1.

**Result:** T=1 → 262,144 sets; T=96 → 4,096 sets — correctly shrinking as more threads compete for the same fixed 105MB. Verified byte-identical vs. S0, crash-free and consistent at every tested thread count. Tagged `safe/S3.1-S3.2`.

> [!NOTE]
> `S3_LLC_FRACTION = 0.25` is explicitly a **placeholder** in the code's own comment — it happens to land exactly on 262,144 sets at T=1 (the confirmed ceiling) and exactly 4,096 at T=96 (the long-validated size), which is a sane range, not proof 0.25 is the right number. It hasn't been empirically tuned against real hit-rate data yet.

### S3.3 — the separate slowdown fix

**Why a second fix was needed:** S3.0 solved the *crash*. A related but distinct problem remained — a real slowdown at ≥1,048,576 sets. The cause: `S2Entry`'s old sentinel values (`tag = UINT64_MAX`, `taxon = TAXID_MAX`, both non-zero) forced the compiler to run a real constructor loop writing every single entry on allocation — defeating the OS's normal "large zeroed allocations are lazy" optimization (see glossary: lazy zero-page allocation), regardless of *where* the array lived.

**The fix — three coordinated changes:**

```cpp
// 1. The empty-sentinel value becomes 0 instead of UINT64_MAX, so calloc's
//    naturally zero-filled memory is already a valid "empty" cache:
static const uint64_t S2_EMPTY_TAG = 0;

// 2. No default member initializers - required for the struct to be
//    "trivially constructible", which is what lets calloc-backed memory
//    skip a constructor loop entirely:
struct S2Entry {
  uint64_t tag;
  taxid_t taxon;
};

// 3. A custom deleter, because calloc'd memory must be released with
//    free(), not delete[] (mismatching the two is undefined behavior):
struct S2FreeDeleter {
  void operator()(void *p) const { free(p); }
};
static thread_local std::unique_ptr<S2Entry[], S2FreeDeleter> s2_cache;
```

`S2EnsureInit()` switches from `new[]` to `calloc`, with explicit error handling `new[]` never needed (it throws automatically on failure; `calloc` just returns `NULL`):
```cpp
static inline void S2EnsureInit() {
  if (! s2_cache) {
    s2_num_sets = S3ComputeNumSets();
    S2Entry *cache_mem = static_cast<S2Entry *>(calloc(s2_num_sets * S2_WAYS, sizeof(S2Entry)));
    uint8_t *way_mem = static_cast<uint8_t *>(calloc(s2_num_sets, sizeof(uint8_t)));
    if (! cache_mem || ! way_mem) errx(EX_OSERR, "unable to allocate S2 cache memory");
    s2_cache.reset(cache_mem);
    s2_next_way.reset(way_mem);
  }
}
```

And one small correctness edge case, added to both `S2Lookup` and `S2Insert` now that 0 means "empty": a *real* minimizer whose value happens to be exactly 0 (vanishingly rare) is handled as a permanent, harmless cache-miss — it's never cached and always falls through to the real hash table, so correctness is unaffected, that one specific value just never benefits from caching.

**A load-bearing detail easy to miss:** the `calloc(s2_num_sets * S2_WAYS, sizeof(S2Entry))` call depends on S3.0's earlier flattening of the array to 1D — a single `calloc` call can allocate one flat block cleanly, but couldn't as neatly allocate a 2D structure without an array-of-pointers plus a separate `calloc` per row, reintroducing the small-object overhead this whole fix is trying to avoid. S3.0's indexing change, made three patches earlier for a different reason (the crash), turns out to be a quiet prerequisite for S3.3.

**Measured effect** (forced to 4,194,304 sets, `sample_targeted`, 96T, interleaved old→new→old→new):

| | Wall-clock | Cache-miss | sys time |
|---|---|---|---|
| OLD (S3.0+S3.1/S3.2, no S3.3) | 1.181s / 1.184s | 41.72% / 43.15% | 4.85s / 5.32s |
| NEW (+S3.3) | 0.609s / 0.619s | 14.69% / 14.75% | 0.75s / 0.97s |

**~2× wall-clock, ~3× cache-miss improvement from S3.3 alone.** The elevated `sys` time (kernel time) on the OLD run is itself independent evidence this is a page-fault story — `sys` time is where the kernel's page-fault handling shows up.

> [!IMPORTANT]
> **A correction we made to our own earlier framing, worth being able to explain directly.** Our original 2026-08-26 finding was "22× slower, 85% LLC-miss" at large sizes — but that number was measured on the *pre-S3.0* build, where the array was still a static `thread_local` array with its own separate, worse per-thread-creation cost (glibc copying a full TLS initialization template for every new thread), not just an eager-write problem. **S3.0 alone had already eliminated almost all of that original 22×; S3.3 adds a real, smaller ~2×/~3× on top — the two don't stack to 22×, and it would be wrong to claim they do.**

Tagged `safe/S3.3`. S3 is now feature-complete: crash fixed (S3.0), real sizing formula (S3.1/S3.2), residual slowdown fixed (S3.3).

### S3.4 — the full benchmark, and a real, explained null result

3 databases × 6 thread counts (1/8/16/32/64/96) × 3 binaries (S0 no-cache / S2-baseline exact-original-committed-state / S2-final fully-fixed) × 3 interleaved runs. **All three land within noise of each other at every single cell** (CV% mostly under 1%, a trustworthy, low-variance measurement).

**Why, precisely — two findings that are easy to conflate but aren't the same:**
1. The 2026-08-26 finding already established the cache gets essentially no hit-rate benefit at the sizes it actually runs at (even the best-tested config, 262,144 sets with pinning, only reached a 1.48% hit rate).
2. S3.0/S3.3 fix bugs that only manifest at **large** sizes (≥262,144 for the crash, ≥1,048,576 for the slowdown) — sizes the sizing formula, correctly and conservatively (`f=0.25`, clamped), never asks for at the thread counts that matter for production (32–96T). The bugs and the formula's actual operating range simply don't overlap.

**Honest conclusion:** S3's fixes are real, necessary correctness/safety work — they unblock safely exploring larger sizes later — but they don't themselves produce a measurable wall-clock win, and now we know precisely why instead of guessing. This is exactly what the earlier S3/S4 debate predicted ("a properly-scaled formula mostly avoids the ceilings by construction") — today's data confirms that prediction directly.

### Likely questions

**Q: "If S3 doesn't produce a wall-clock win, why does it matter?"**
A: Because it's the safety work that lets the cache explore larger sizes at all without crashing or slowing down — without S3, S4's later eviction-policy experiments couldn't safely test larger capacities. It's also real, citable engineering: a documented crash fix and a documented slowdown fix, each independently verified.

**Q: "Why 105MB and not 210MB?"**
A: 210MB is the total L3 cache across *both* CPU sockets on the machine. Every benchmark in this project runs pinned to one socket (`numactl --cpunodebind=0`), so the number that actually matters for sizing the cache is one socket's share — confirmed directly via `lscpu`, not assumed from a spec sheet.

**Q: "What does f=0.25 mean, and is it final?"**
A: It's the fraction of that one socket's 105MB the cache is allowed to claim. It's explicitly a placeholder in the code's own comment — chosen because it lands in a sane range (262,144 sets at 1 thread, 4,096 at 96 threads), not because it's been empirically proven optimal. Tuning it against real hit-rate data is still open work.

---

## S4 — a real hashing bug, an 8.9× fix, and a result that reversed itself

### Why

With S3 closed out, the natural next step was S4's eviction-policy design work. Before writing that, though, we built one more diagnostic — a way to actually *see* how lookups spread across the cache's 4,096 sets, since nothing up to this point had ever measured that directly.

### The diagnostic — what it actually measures, in code

Built as a standalone variant (same pattern as `s2_standalone_patch.py`: no S1 layer, wraps `hash->Get()` directly), with two new things added: a per-set **occupancy** counter, and a **reuse-distance histogram**.

```cpp
static thread_local uint64_t s2_occupancy[S2_NUM_SETS] = {0};

static thread_local std::unordered_map<uint64_t, uint64_t> s2_last_seen;
static thread_local uint64_t s2_lookup_idx = 0;
static thread_local uint64_t s2_distance_hist[8] = {0};  // buckets: <10,<100,<1e3,<1e4,<1e5,<1e6,<1e7,>=1e7

static inline void S2RecordReuse(uint64_t minimizer) {
  auto it = s2_last_seen.find(minimizer);
  if (it != s2_last_seen.end()) {
    uint64_t distance = s2_lookup_idx - it->second;
    int bucket = 0;
    uint64_t threshold = 10;
    while (distance >= threshold && bucket < 7) { threshold *= 10; bucket++; }
    s2_distance_hist[bucket]++;
  }
  s2_last_seen[minimizer] = s2_lookup_idx;
  s2_lookup_idx++;
}
```

**In plain terms:** every time a minimizer is looked up, `S2RecordReuse` checks a map of "when did I last see this exact minimizer." If it's been seen before, the gap (in number of lookups, not time) gets sorted into a bucket — bucket 0 is "seen again within the last 10 lookups," bucket 7 is "seen again, but not until at least 10 million lookups later." This is a **T=1-only, non-timed** build — the `unordered_map` alone costs an estimated 1.3–1.6GB per thread at this database's scale, so it's never used for wall-clock or multi-threaded comparisons, only to understand the *shape* of repeat behavior.

`S2Lookup` calls both the occupancy counter and the reuse tracker on every lookup, hit or miss:

```cpp
static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  s2_occupancy[set_idx]++;
  S2RecordReuse(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      s2_hits.fetch_add(1, std::memory_order_relaxed);
      return true;
    }
  }
  s2_misses.fetch_add(1, std::memory_order_relaxed);
  return false;
}
```

### Results — a real bug, found by looking

Run against `standard_8gb`, T=1, 4,096 sets, 3,006,550 total lookups:

```
[S4.0-OCCUPANCY] min=0 max=165460 mean=734.02 max_over_mean=225.42
[S4.0-REUSE-DISTANCE] lt1e5=341228 lt1e6=978748 ...
```

**One set absorbed 225× the average load; at least one set was never touched at all.** The cause, sitting right there in the code we'd written back at S2 and never revisited:

```cpp
// S2SetIndex, unchanged since S2 - a raw bit-mask, no mixing:
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}
```

This only ever looks at a minimizer's *lowest* bits (whichever ones survive the `&` mask) — if those low bits aren't evenly distributed across real minimizer values (and they aren't), traffic piles up unevenly no matter how the rest of the cache is designed.

**The reuse-distance histogram, read correctly:** each field (`lt1e5`, `lt1e6`, etc.) is a **bucket count** — the number of repeats whose distance fell in that specific range (`[10⁴,10⁵)`, `[10⁵,10⁶)`) — not a running total. Summed: 341,228 + 978,748 = 1,319,976, which is **81.3%** of the ~1,623,537 total repeats measured. In plain terms: when a minimizer does get looked up again, four times out of five that repeat happens somewhere between 10,000 and 1,000,000 lookups later — far beyond what a 16,384-entry cache (4,096 sets × 4 ways) can possibly still be holding onto. *(This specific number is measured on `standard_8gb` at T=1 only — it hasn't been confirmed to hold on the other databases or at real thread counts.)*

### The fix — one line

```cpp
// BEFORE:
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

// AFTER:
static inline size_t S2SetIndex(uint64_t minimizer) {
  return MurmurHash3(minimizer) & (S2_NUM_SETS - 1);
}
```

`MurmurHash3` was already declared in `kv_store.h` (already `#include`d by `classify.cc`) and already used by Kraken2's own main hash table for exactly this purpose — mixing a value's bits so every output bit depends on every input bit, instead of only looking at whichever bits happen to survive a mask. No new includes needed.

**Validated twice before trusting it:** first on a synthetic distribution check (256 of 4,096 sets used before the fix → all 4,096 used after; max/mean 16.06 → 1.84), then measured for real:

| | Old hash (raw mask) | Fixed hash (MurmurHash3) |
|---|---|---|
| Hit rate, 4,096 sets | 0.4035% | **3.5758%** (8.9×) |
| Occupancy max/mean | 225.42 | 3.95 |

Ported into the real production tree (where `S2SetIndex` reads the runtime `s2_num_sets` variable from S3.1/S3.2's formula, not a fixed constant), byte-identical correctness re-confirmed, crash-free at 16T/32T/96T. Tagged `safe/S4.0-hashmix`.

**Still no wall-clock win.** Interleaved comparison at `sample_targeted`/`standard_8gb`, T=32/T=96: all statistically indistinguishable (0.4–1.8% differences, within noise). One real secondary signal: `sample_targeted`'s LLC-load-miss% dropped a consistent ~30% relative amount — real, reproducible, but 95,377 additional hits out of ~3 million lookups is still only ~3.2% of the total stream, too small a slice to move end-to-end time.

### The reversal — the part worth being able to explain clearly

Re-running the exact "pinning" eviction test from S2 on the now-correctly-hashed cache:

| | Old hash | Fixed hash |
|---|---|---|
| Round-robin | 0.4035% | 3.5758% |
| Pinned ("protect on first hit") | 0.5050% (**+25.2%** relative) | 3.4367% (**−3.9%** relative) |

**What actually happened, mechanically:** with the broken hash, a handful of sets were absorbing 225× their fair share of traffic — round-robin, blindly cycling through 4 ways in order, was doing an especially bad job specifically in those overloaded sets, because it had no way to know some entries in a set were far more valuable than others. "Protect anything that's been hit once" looked like a big win because it was rescuing exactly those catastrophically overloaded sets. **Once the hash spreads load evenly, round-robin's baseline is already reasonable** — pinning has nothing obvious left to rescue, and can even mildly hurt (a one-hit-wonder can now squat on a slot indefinitely, since nothing forces it back out once it's "proven" itself once).

*(Caveat worth remembering here too: the pinned variant's `S2Entry` is 24 bytes, not 16 — the extra `was_hit` byte, padded to the next 8-byte boundary. This means the reversal isn't from a perfectly isolated single variable. It doesn't change the direction of the result, but it's honest to mention if asked exactly how clean this comparison was.)*

**Why this matters more than just "one experiment changed":** S4.1 (the next planned step, a saturating-counter design) was a direct refinement of the same "protect proven-useful entries" idea. Its entire empirical justification — the +25.2% pinning result — no longer holds once the hash bug is fixed. We caught this *before* writing S4.1's code, not after.

### Likely questions

**Q: "How did a bug like this survive from S2 all the way to S4 without being caught earlier?"**
A: Because every prior measurement was an *external* proxy — wall-clock time, `perf`'s LLC-miss percentage — and none of those distinguish "the cache is working but has low hit rate" from "the cache's internal load distribution is badly broken but happens to land on a similar hit-rate number." It took building a diagnostic that looks *inside* the cache (per-set occupancy) to see it directly. That's exactly why the verification audit's Q3 finding ("zero internal instrumentation existed") mattered — it took until S4.0 to actually build that instrumentation.

**Q: "Doesn't the reversal mean S2's original eviction-policy finding was wrong, and we published something false?"**
A: We reported it honestly as a real, reproducible measurement at the time — that's still true, +25.2% was genuinely what the (broken-hash) code produced. What's changed is *why* it happened: not because eviction policy is a strong lever in general, but because it happened to rescue a specific, unrelated bug. That distinction is exactly what we're now able to explain, because we kept testing instead of stopping at the first result.

**Q: "What happens to S4's eviction-policy work now?"**
A: It doesn't get built on the disproven basis. If eviction work continues at all, the two ideas worth trying are genuinely different from "protect what's been hit": pseudo-LRU (the literal mechanism real hardware caches use at 4-way associativity) and admission control (deciding what gets *let into* the cache in the first place, not just what gets evicted later) — both recommended by the 7-agent pivot debate, discussed further below.

---

## S5 — prefetch-batching, ported and merged, not yet measured

### Why

A collaborator on this project, Chirag Suthar, independently built a different kind of optimization on his own branch of this work: instead of trying to *avoid* the expensive `hash->Get()` call (which is what the whole S1–S4 cache line of work does), make the call itself faster by overlapping many of them. A 7-agent debate (below) recommended porting this onto our tree as a time-boxed addition — it targets the ~88–96% of lookups that *miss* the cache regardless of eviction policy, which S1–S4's approach can't touch at all.

**The core idea, in plain terms:** normally, Kraken2 resolves one minimizer lookup completely before starting the next one — hash it, wait for the memory fetch, get an answer, move to the next minimizer, repeat. A modern CPU core can actually have roughly a dozen memory requests "in flight" at once (see glossary: memory-level parallelism), but one-at-a-time processing never uses more than 1 of those slots. **Software prefetching** issues the memory-fetch *hint* for several minimizers up front, then goes back and resolves them once the data's had time to arrive — overlapping the wait instead of paying it serially. This project's own earlier profiling (a finding called "M4") found Luna's DRAM bandwidth utilization sits at only 4.9–10.7% of peak — genuinely latency-bound, not bandwidth-bound — meaning there's real headroom for this to help rather than just moving the bottleneck.

**A real risk, checked directly:** we deliberately did not cite Suthar's own numbers as ours. His own measurements disagreed with each other across three same-day documents on the same nominal experiment (−11.77%, −5.99%, −20.34%), traced to a documented turbo-frequency artifact on his desktop machine — the same binary measured 1.85s and 2.90s in the same 20-run batch, purely from CPU clock-speed variation, not code behavior. And his setup differs from Luna's in three compounding ways: his machine has a 16MB L3 cache vs. Luna's 105MB per socket; his test database behaves like our smallest one (`sample_targeted`), not the two that actually bottleneck (`standard_8gb`, `pluspf_103gb`); and his patch targets his own forked, modified Kraken2 tree, not the real upstream one this project builds on.

### The code — four files, seven changes, and it's a real merge, not a flag-flip

**Why "not a flag-flip":** Suthar's original patch re-declares `last_minimizer`/`last_taxon` as fresh function-local variables in the exact scope where S1.1 had already promoted those same names to `thread_local`. Applied blindly, his patch would have silently shadowed S1's fix and quietly reverted to stock Kraken2's depth-1, non-persistent repeat-check — undoing real, verified work without any error or warning. Reconciling this by hand was the actual engineering effort here.

**1. `kv_store.h`** — the abstract interface Kraken2's hash table implements gains two new methods:
```cpp
class KeyValueStore {
  public:
  virtual hvalue_t Get(hkey_t key) const = 0;
  // S5.0: look up with a hash the caller already computed, and start the
  // memory fetch for that hash without waiting for it - together these
  // let a caller issue several lookups before consuming any of them.
  virtual hvalue_t GetWithHash(hkey_t key, uint64_t hc) const = 0;
  virtual void Prefetch(uint64_t hc) const = 0;
  virtual ~KeyValueStore() { }
};
```
(Confirmed via `grep -rn "public KeyValueStore" src/` that `CompactHashTable` is the *only* class implementing this interface — adding two new required methods can't silently break some other subclass.)

**2. `compact_hash.cc`** — Kraken2's real lookup function is split into a thin wrapper plus the actual logic, now able to accept a precomputed hash:
```cpp
// BEFORE
hvalue_t CompactHashTable::Get(hkey_t key) const {
  uint64_t hc = MurmurHash3(key);
  uint64_t compacted_key = hc >> (32 + value_bits_);
  size_t idx = hc % capacity_;
  size_t first_idx = idx;
  size_t step = 0;
  while (true) {
    if (! table_[idx].value(value_bits_)) break;
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0) step = second_hash(hc);
    idx += step; idx %= capacity_;
    if (idx == first_idx) break;
  }
  return 0;
}

// AFTER
hvalue_t CompactHashTable::Get(hkey_t key) const {
  return GetWithHash(key, MurmurHash3(key));
}

void CompactHashTable::Prefetch(uint64_t hc) const {
  __builtin_prefetch(&table_[hc % capacity_], 0, 3);
}

hvalue_t CompactHashTable::GetWithHash(hkey_t key, uint64_t hc) const {
  uint64_t compacted_key = hc >> (32 + value_bits_);
  size_t idx = hc % capacity_;
  size_t first_idx = idx;
  size_t step = 0;
  while (true) {
    if (! table_[idx].value(value_bits_)) break;
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0) step = second_hash(hc);
    idx += step; idx %= capacity_;
    if (idx == first_idx) break;
  }
  return 0;
}
```
`GetWithHash`'s body is byte-identical probe logic to the original `Get()` — the only change is that the hash arrives as a parameter instead of being computed inside the function. `Prefetch()` issues a read-hint (`__builtin_prefetch(ptr, 0, 3)` — 0 means "read," 3 means "keep this in cache as long as possible") for exactly the *first* probe address. It does **not** prefetch every address a collision chain might visit — only the first slot.

**3. `classify.cc` — `S2SetIndex`/`S2Lookup`/`S2Insert` now take the hash as a parameter, removing a duplicate hash computation:**
```cpp
// BEFORE (S4.0's version - computes its own hash):
static inline size_t S2SetIndex(uint64_t minimizer) {
  return MurmurHash3(minimizer) & (s2_num_sets - 1);
}

// AFTER (S5.0 - takes the hash pass 1 already computed):
static inline size_t S2SetIndex(uint64_t hc) {
  return hc & (s2_num_sets - 1);
}
```
`S2Lookup`/`S2Insert` both gain an `hc` parameter the same way. Before S5.0, `S2SetIndex` called `MurmurHash3` itself — a second, redundant hash of the same minimizer value the prefetch pass was *also* going to hash for its own purposes. Moving the one real `MurmurHash3` call to pass 1 (below) and threading its result everywhere it's needed removes that duplicate without changing which bits pick the set.

**4. `classify.cc` — the loop itself, restructured into two passes:**
```cpp
static int la_batch = 1;               // -B flag; 1 = exact stock behavior
static const int PF_MAX = 64;
struct PfSlot {
  uint64_t min;   // the minimizer
  uint64_t hc;    // MurmurHash3(min), computed once - reused for the -M
                  // skip check, S2's set index, and GetWithHash
  bool     amb;   // scanner.is_ambiguous() captured AT SCAN TIME - the
                  // scanner has moved on by the time this is resolved
};
```
```cpp
      PfSlot pf[PF_MAX];
      bool frame_done = false;
      while (! frame_done) {
        // pass 1: scan a batch, hash it, start the memory fetches
        int n_pf = 0;
        while (n_pf < la_batch) {
          minimizer_ptr = scanner.NextMinimizer();
          if (minimizer_ptr == nullptr) { frame_done = true; break; }
          pf[n_pf].min = *minimizer_ptr;
          pf[n_pf].amb = scanner.is_ambiguous();
          if (! pf[n_pf].amb) {
            pf[n_pf].hc = MurmurHash3(pf[n_pf].min);
            hash->Prefetch(pf[n_pf].hc);
          }
          n_pf++;
        }
        // pass 2: resolve in the original order, by which time the
        // fetches issued above have had time to land
        for (int pf_i = 0; pf_i < n_pf; pf_i++) {
          taxid_t taxon;
          if (pf[pf_i].amb) {
            taxon = AMBIGUOUS_SPAN_TAXON;
          } else {
            if (pf[pf_i].min != s1_last_minimizer) {
              // ... same body as before, but reading pf[pf_i].min/.hc
              // instead of *minimizer_ptr, and calling GetWithHash
              // instead of Get:
              if (! S2Lookup(pf[pf_i].min, pf[pf_i].hc, &taxon)) {
                taxon = hash->GetWithHash(pf[pf_i].min, pf[pf_i].hc);
                S2Insert(pf[pf_i].min, pf[pf_i].hc, taxon);
              }
              s1_last_taxon = taxon;
              s1_last_minimizer = pf[pf_i].min;
              // ...
            } else {
              taxon = s1_last_taxon;
            }
            // ... unchanged quick-mode / hit_counts logic
          }
          taxa.push_back(taxon);
        }
      }
```

**Exactly how this preserves S1's fix:** `s1_last_minimizer`/`s1_last_taxon` are the *same* `thread_local` variables S1.1 created — untouched, not re-declared, not shadowed. What changed is only *where in the flow* the comparison against them happens: instead of comparing immediately after each minimizer is scanned, it now compares during pass 2, against a minimizer that was scanned and hashed during pass 1 (up to `la_batch` positions earlier in the loop). The comparison logic itself, and the two assignments right after it, are the exact same lines of code as before — just fed `pf[pf_i].min` (the value captured in the batch) instead of `*minimizer_ptr` (the scanner's live current position, which has already moved on by pass 2).

**`-B` flag, wired into argument parsing:**
```cpp
      case 'B' :
        // -B batch size, 1..PF_MAX. 1 (the default) is the exact stock
        // one-at-a-time path - nothing changes unless this flag is passed.
        la_batch = atoi(optarg);
        if (la_batch < 1 || la_batch > PF_MAX)
          errx(EX_USAGE, "-B expects a batch size between 1 and %d", PF_MAX);
        break;
```

**Why `-B 1` is claimed to be byte-identical to stock, not just "close":** at `la_batch=1`, pass 1 runs exactly once before pass 2 resolves that one slot — scan one minimizer, hash it, prefetch it, then immediately resolve it. That's the same sequence of operations as the original single-pass loop, just mechanically split across two nested loops instead of one. This is the basis for treating `-B 1` as the verified stock-equivalent baseline in every S5.0 measurement, without a separate correctness re-check for that specific value.

### What's NOT yet done — stated plainly

- **Every minimizer in a batch gets hashed and prefetched unconditionally**, even ones pass 2 will discover are an immediate repeat of `s1_last_minimizer` (and so never needed a real lookup at all) — a deliberately accepted "wasted" hash on those, since tracking repeat-status across a batch boundary wasn't judged worth the added complexity.
- **`Prefetch()` only touches the very first probe address**, not the full chain a collision might walk through — so the technique's benefit likely concentrates on lookups that resolve (hit or confirmed-empty) on the first probe.
- **No results exist yet.** The sweep script (below) has never been run on Luna.

### How it will be measured, once run

```bash
tmux new -s s5sweep
python3 /tmp/compare_s5_0_prefetch_sweep.py | tee ~/s5_0_prefetch_sweep.txt
```

3 databases × 6 thread counts (1/8/16/32/64/96) × 5 batch sizes (`-B` = 1, 4, 8, 16, 32 — matching Suthar's own tested points, plus 1 as the verified stock-equivalent baseline) × 3 interleaved reps = **270 runs**, comparable in scale to S3.4's 162-run sweep but larger — expected to take a few hours, unattended, hence running inside `tmux` so it survives a disconnect.

**One real gotcha already found and fixed in the sweep script itself:** the sweep calls Kraken2's internal `classify` binary directly, not the usual `kraken2` wrapper script — because the wrapper's argument parser has no idea what `-B` means, and passing it through silently misrouted the value "1" as if it were an input filename. Caught the hard way (a real failed run), not anticipated in advance. The sweep script's flags are copied exactly from what the wrapper itself builds internally before invoking `classify` (confirmed by reading the wrapper's own source, lines 119–137), plus `-B`.

**Why the grid is the full 3×6, not a narrower slice:** an earlier draft of this sweep only tested `standard_8gb`/`pluspf_103gb` at 32T/96T (the two databases and thread counts that matter most for the paper). Reconsidering: prefetching's benefit depends on how much of the core's spare memory-level-parallelism capacity is available, and many threads compete for that same shared capacity — so the effect could plausibly be *largest* at low thread counts (less contention) and smallest at exactly the 32T/96T range a narrower sweep would have focused on. The full grid catches that either way, rather than assuming where the effect will show up.

### Likely questions

**Q: "Why should this work when the cache (S1–S4) didn't move the needle?"**
A: Because it targets a completely different slice of the problem. The cache tries to *avoid* paying for a lookup at all — but even in the best-measured case, over 96% of lookups on the databases that matter still miss the cache and pay full price regardless. Prefetching doesn't try to avoid those lookups; it tries to make *all* of them cheaper by overlapping their memory-wait time instead of paying it one at a time.

**Q: "If it's not measured yet, why include it at all?"**
A: Because it's real, committed, working code — merged carefully rather than naively, with the specific risk of silently undoing S1's fix identified and avoided. It's honest to present it as "built, not yet measured" rather than either hiding it or overstating it with someone else's numbers.

**Q: "What's the actual risk if this doesn't pan out?"**
A: Low. The 7-agent debate rated this the lowest crash/stability risk of any Track A step so far — `PfSlot pf[PF_MAX]` is a small (~1–2KB) stack array, not the kind of large `thread_local` allocation that caused the S2/S3 crash. If the sweep comes back null, that's a clean, reportable negative result using infrastructure that already exists — not wasted effort.

---

## The four structured reviews, in full

Across these two weeks, four separate multi-agent review exercises ran — an audit and three debates. Each one used the same basic shape: multiple independent AI agents read the same primary sources with **zero visibility into each other's work**, form their own conclusions, then cross-examine and reconcile in a second round, producing a consensus-or-documented-disagreement report in a third. This section exists so you can explain *why* this process matters, not just *that* it happened — sir cares about rigor as much as results, and "we checked our own work independently, four separate times, and each time it found something real" is a genuinely strong methodological story.

### Review 1 — S1/S2 verification audit (2026-08-26, 5 agents, 3 rounds)

**Setup:** a fresh Claude session, with zero memory of building S1/S2, was handed a brief explicitly telling it *not* to trust the brief's own summary as ground truth, and given 8 specific questions to independently verify against the actual code and logs.

**Full results:**

| Q | Question | Verdict |
|---|---|---|
| Q1 | Is S2's cache nested inside S1's gate rather than standing in front of every lookup? | CONCERN FOUND (4/5 agents) — real, but its practical bite is weaker than it sounds, because S1's filter fires at close to 0% on the two databases the "no benefit" conclusion actually rests on |
| Q2 | Is the code's own correctness-boundary argument (the comment explaining why S2 can't corrupt the stats-counting logic) actually sound? | CONCERN FOUND (5/5) — sound as written, but rests on two things nobody had independently verified yet: that `Get()` really has no side effects, and that `S2Lookup` can't accidentally match the wrong minimizer to the wrong cached answer |
| Q3 | Is the "no benefit" finding a real property of the cache, or a symptom of a bug? | CANNOT VERIFY (3/5 converged) — because zero internal hit/miss instrumentation existed at this point; every conclusion so far rested only on external proxies (wall-clock, `perf`'s LLC-miss%) that can't tell "the cache rarely hits" from "the cache never gets a fair chance to" |
| Q4 | Is the memory-init-cliff theory (from an earlier size sweep) the right explanation? | CONFIRMED as the leading hypothesis — arithmetic independently re-checked: 4,194,304 sets × 4 ways × 16 bytes ≈ 256MB per thread, × 96 threads ≈ 24GB touched before real work starts; the added cost at the largest size was DB-invariant across baselines from 0.6s to 52s, consistent with a fixed per-thread cost rather than workload-scaled thrashing |
| Q5 | Does the missing correctness check (every prior benchmark used `--output /dev/null`) block trusting anything built on top of it? | CONCERN FOUND (5/5, no dissent) — the single strongest consensus of the eight questions |
| Q6 | Does building on v2.17.1 instead of the originally-planned v2.1.3 put any existing claims at risk? | CONCERN FOUND (5/5 by round 2, 3 agents revised their view upward after cross-examination) — splits 2 of the paper's 3 claimed contributions across non-comparable baselines, and the risk was broader than first scoped: nobody had checked whether `kraken2-build`'s own hash-construction logic changed across the ~2.5 years between the two versions, only whether the read-side parser changed |
| Q7 | Is the project on pace against its own stated targets? | CONCERN FOUND (5/5) — this was the second consecutive week missing its own explicit safe-zone target |
| Q8 | Anything else worth flagging? | Eight numbered items: (1) S2 was sitting uncommitted on a shared Luna account with an existing data-loss precedent (2 ESKAPE databases already lost, root cause never resolved) — rated the single most urgent action, independent of anything else; (2) `-M`/memory-mapping (this project's own prior finding of a 12–14× effect on large databases) had never been used in any S0/S1/S2 benchmark; (3) `week4plan.md`'s tracking ledger was stale; (4) the audit's own setup brief had claimed real code diffs were embedded in the log — checked and found **false**, the audit catching an error in its own instructions, not just in the work under review; (5) a ~5.5-hour systematic clock-time drift in the log's early entries (the *order* of events is reliable, the literal timestamps aren't); (6) an "89%" LLC-miss figure cited elsewhere wasn't actually supported by the log, which only backs "~13% to 85%"; (7) two ESKAPE reference databases were still missing; (8) whether double hashing (B1) was even a confirmed paper claim was unresolved at this point |

**The go/no-go outcome:** not a clean pass. A conditional go for S3.1–S3.3 (design work only — don't touch the live cache code yet), and a 6-item checklist required before trusting anything past that point: commit and tag S2 immediately (data-safety, independent of anything else), add real hit/miss instrumentation, re-run the standalone un-nested comparison, run a real (non-`/dev/null`) correctness diff, run a pre-touch experiment for the memory-init theory, and fix the stale ledger. **Every one of these six items was actually executed and closed before S3 design work proceeded** — worth being able to say plainly if asked "did you actually act on the audit's findings, or just note them?"

### Review 2 — S3/S4 design debate (2026-08-27, 5 agents, 3 rounds)

**Setup:** debated `research_brief_s3_s4_2026-08-26.md`, and explicitly supersedes parts of an earlier single-pass (non-debated) document, `week6plan.md`, that had answered the same brief without the cross-examination step.

**Full results:**

| Q | Finding |
|---|---|
| Q1 (the TLS crash) | Confirmed the heap-pointer fix pattern is race-free (each thread's `thread_local` pointer is inherently private, no lock needed). Sharpened the mechanism from a generic "glibc static TLS limit" to something more specific and directly checkable: NPTL's `allocate_stack()` computes a new thread's usable stack as `requested − guard_page − static_tls_size`, so a large file-scope `thread_local` array directly eats into a thread's stack budget. **Also flagged that the heap-pointer fix alone would NOT fix the separate slowdown cliff** — both bugs share a root cause in the entry struct's non-zero sentinel values defeating the OS's lazy zero-page optimization, and fixing the crash doesn't automatically fix that. This is exactly what became two separate fixes, S3.0 and S3.3. |
| Q2 (LLC sizing) — rated "the single most load-bearing correction in this whole exercise" | Luna's real *per-socket* L3 is ~105MB, not 210MB — 210MB is the two-socket sum, and every benchmark in this project runs pinned to one socket via `numactl`. The safety fraction `f` was deliberately left open rather than guessed at by averaging — Round 1's independent guesses spanned 0.1 to 1.0, a 12× range, which the debate judged too wide to resolve by consensus and instead flagged for an empirical sweep. A full trace-simulation approach (modeled on a technique called Bandana, used for large multi-table key-value caching) was explicitly considered and rejected as the wrong shape of problem for this project's single-structure, single-parameter case. |
| Q3 (S4 eviction design) | Corrected a wrong assumption 3 of 5 agents initially made: `taxid_t` is a `uint64_t` (8 bytes), not a smaller type — meaning the original `S2Entry` is exactly 16 bytes with zero padding (matches the code directly), and the "pinned" variant (adding one `bool was_hit` field) grows to 24 bytes once alignment padding is accounted for — a real, ~50% growth that's easy to miss if you only look at outcomes and not the struct layout. Confirmed, independently, across all 5 agents: **none** of the four closest comparator tools (kache-hash, MegIS, MetaCache-GPU, GPMeta) implement any eviction policy for a k-mer lookup cache at all — each for a different structural reason (one does placement-only, one operates at a different memory tier entirely, two are throughput-focused hash-table redesigns with no notion of "what to forget"). This is a real, independently-confirmed gap in the field, not just this project's framing of one. |
| Q4 (the M5 reuse-rate tension) | Reframed as substantially a metric-definition mismatch rather than a real contradiction: the earlier 90.7% figure measures *global, unbounded-distance* reuse across the entire run, while a fixed-capacity cache can only ever realize hits within a *bounded* window — so the two numbers aren't actually in tension by construction. One fair dissent kept in the report: this reframing explains *why* the two numbers can coexist, but doesn't by itself establish how large the gap should be — which is exactly what the S4.0 diagnostic (reuse-distance histogram) was later built to measure directly. The debate's own text specifically flags checking hash quality (`S2SetIndex`'s bit-mixing) as a prerequisite before further eviction-policy work — which is precisely what S4.0 found broken, months before it broke S4.1's basis. |
| Q5 (prioritize S4 over further S3 work) | Unanimous 5/5, described as the strongest, most robustly corroborated conclusion the exercise produced — reached independently via four separate argument chains (the pinning experiment's own diminishing-returns-with-capacity trend; the corrected LLC arithmetic landing squarely in that same small-capacity regime; S4's next planned increment being cheap to build; and schedule pressure from two consecutive missed weekly targets). |

### Review 3 — two-thesis strategy debate (2026-08-30, 5 agents, 3 of 5 planned rounds — stopped early once genuine convergence was reached)

**Setup:** a broader strategic question than the first two reviews — not "is this specific piece of code right," but "given real time pressure, is the current plan for both theses (Track A and Track B) achievable, and is the current sequencing the right one."

**Full results:**
- **A live self-correction, right at the start:** the exercise had been framed assuming 17 days remained until the Sept 13 target; the real number was 14 (as of 2026-08-30). The debate itself calls this out as "a live instance of the exact governance-latency pattern flagged elsewhere in this project" — 3 days had just passed producing more planning documents but zero new Luna commits.
- **Neither thesis at full original scope is achievable by Sept 13 (5/5).** Applying this project's own measured velocity (roughly 4.8 sub-steps/day during genuinely active periods, but with real multi-day idle gaps already observed) to the ~29 sub-steps still remaining implied 6 days in an unrealistic best case, more realistically 10–20+ calendar days — before write-up or review even starts.
- **B2 (the bitmask cell) does not need B1 (double hashing) first — confirmed by reading Kraken2's actual `Get()` source directly, not by analogy.** The function that decides *which cell to probe next* on a collision (`second_hash()`, the step function) and the logic that decides *what a cell's contents mean* (`hashed_key()`, `value()`) are genuinely separate code paths, operating on different data. Building B2 directly on top of the existing linear-probing table (called "B0" in this framing) is not skipping a step — B2 was also literally what Meeting 11 named as required; double hashing wasn't named there at all, only in an older report's future-work list.
- **B1's real cost was previously underestimated.** `second_hash()` already exists as a named, wired-in hook in the real Kraken2 source — but it's **hardcoded to `return 1`** under the default build flag, not a working alternate implementation sitting dormant. B1's actual work is "write one real hash function," smaller than designing a new probing scheme from scratch, but genuinely more than a flag flip — and there's a real, previously unscheduled cost: turning off the linear-probing flag requires a full database *rebuild* to test against real data, not just a recompile of the classifier.
- **The ESKAPE panel's ceiling is structural, not a data-loss bug.** Checking the project's own earlier records: only 4 of the 6 named panel species (*E. faecium* and *Enterobacter* excluded) were ever actually downloaded in the first place — this is separate from, and predates, two other database files that were separately lost later. Even a perfect data recovery effort would still cap the panel at 4 organisms; any writeup needs to say "4-organism panel," not 6, unless the other two are actively sourced.
- **No record of a Meeting 12 exists.** The last logged entry is Meeting 11 (2026-08-19), which itself named 2026-08-26 as the next meeting — nothing is logged for that date or any date since, until this current session's meeting prep.
- Also flagged: the comparator sweep against Centrifuge predates the fresh v2.17.1 clone and all of S1–S4's code, so it isn't actually measuring the same thing this report describes; and a `-DLINEAR_PROBING` build-flag detail (confirmed directly from source) that hadn't previously been documented anywhere in the project.

### Review 4 — Track A pivot debate (2026-08-30, 7 agents + a coordinator cross-examination)

**Setup:** the largest and most recent of the four — 7 independent agents in round 1 (each reading every primary source in full, including this project's own earlier May-2026 design notes and a collaborator's separate `PREFETCH.md`/`LOOKASIDE_REPORT.md` documents), then a coordinator-run round 2 after two attempts to launch a second batch of fresh cross-examination agents hit session-wide rate limits — rather than risk a third failed batch, the coordinating session itself re-verified the two most load-bearing factual disputes directly against source. Round 3 is the consensus synthesis.

**Full verdicts:**

| Q | Verdict | Confidence |
|---|---|---|
| Q1 — is there a genuinely different eviction policy worth trying, if S4 continues? | 7/7: no large-scale systems eviction algorithm (ARC, 2Q, LRU-K, CLOCK-Pro, TinyLFU's sketch machinery) actually fits a structure this small (4 candidate slots per set) — each assumes either bookkeeping overhead this project's cache doesn't have room for, or a key-universe size this problem doesn't have. Two genuinely different, cheap, worth-trying ideas: **pseudo-LRU** (2 bits of state per set — cheaper than the already-tried `was_hit` byte — the literal mechanism real hardware caches use at 4-way associativity, and structurally can't reproduce the exact failure mode the pinning reversal exposed, since a stale entry naturally rotates out over time) and **admission control** (a different lever entirely — gate what's allowed *into* the cache in the first place, rather than which existing entry to evict; independently supported by two unrelated pieces of evidence — this project's own reuse-distance histogram, and a separate real measurement on a collaborator's branch showing 63.4% of distinct minimizers appear exactly once, meaning "the junk is already inside by the time you're choosing what to evict"). Both are bounded by the same reuse-distance ceiling — no eviction policy, however clever, can rescue a repeat that arrives further apart than the cache's realistic capacity survives. | High |
| Q2 — does raising capacity deserve a second look, now that the hash is fixed? | Yes, one bounded re-sweep (fixed hash, a raised size clamp already proven crash/slowdown-safe by S3.3, at low thread counts T=1/8/16 specifically, since that combination has never been tested post-fix) — cheap, closes a real gap in the record. But no wall-clock payoff is expected: the thread counts that actually matter for production (32–96T) are already tested post-fix and came back null, and the same 8.9× hit-rate jump that S4.0 already measured moved wall-clock by exactly zero — there's no reason to expect a further capacity-driven gain to behave differently. | High |
| Q3 — should effort pivot toward prefetch-batching? | 7/7: yes, as a time-boxed 2–3 day Luna spike, **additive** to S4's remaining work, not a replacement for it — this is exactly what became S5.0. Porting is a real ~2–3 day merge (confirmed by directly reading the source patch, not estimated abstractly), not a flag-flip, specifically because of the overlap with S1's already-modified hot loop. Carries lower crash risk than any Track A step so far, since the new state (`PfSlot pf[64]`) is a small stack array, nowhere near the scale of `thread_local` allocation that caused the S2/S3 crash. | High |
| Q4 — pace and sequencing | What's agreed 7/7: Track A's wall-clock track record across S2.4, S3.4, and the S4.0/S4.1 reversal is four consecutive, well-powered null-or-reversed results — a legitimate, citable *negative* finding with a diagnosed mechanism, not something to hide. Track B gets the bulk of the remaining runway. **What genuinely doesn't converge, reported honestly rather than smoothed over:** how fast to fully close out Track A's remaining engineering (independent estimates ranged from "1–2 days, full stop" to "~3 more days" to "the prefetch spike is small enough to run in parallel without forcing any pivot decision at all"), and whether today's evidence (a design's empirical basis being *directly disproven*, a different category of information than ordinary schedule pressure) licenses overriding your own standing "finish Track A before Track B" instruction, or whether that call needs to go to you explicitly rather than being decided unilaterally. The report treats this as a real, unresolved question for you to decide — not something more research settles. | Medium — the disagreement itself is the finding |
| Q5 — anything else that changes the picture | The most consequential unprompted finding: a stale claim in `dorado-kraken-research/CLAUDE.md` (that an older optimization patch was never applied) turned out to be false — it was applied and benchmarked back on 2026-08-03, real but modest, fading with thread count, growing with database size — already banked, not an available lever for the remaining days, and a concrete instance of exactly the kind of docs-drift this project's own memory index had already flagged as a recurring risk. The hash-mix fix stands as a legitimate result on its own regardless of the pivot decision (a 2.5× hit-rate improvement using 1/64th the memory of the largest broken-hash config tested). An external, independently-sourced check on the whole cache-based approach: a collaborator's own separate lookaside-cache experiment found that even a cache reaching 26.2% hit rate — far above anything this project's cache has measured — still lost to stock Kraken2, because the per-lookup cost of checking the cache outweighed the memory savings once the cache actually worked well enough to matter. A pre-registered go/no-go threshold from this project's own original May-2026 design notes ("worth building if reuse_rate > 0.20") was never actually checked against — measured hit rates across all of S1–S4 top out at 3.58%, an order of magnitude under that threshold, though it's not proven that metric is defined identically to what S1–S4 actually measured. | Medium-high on the facts; the disagreement itself stays open |

**One honesty-preserving detail worth being ready to mention if asked directly:** the report also carries a low-confidence, explicitly-unresolved provenance flag — one agent noticed that the volume of work logged on 2026-08-30 (multiple Luna rebuilds, several benchmark sweeps) works out to a tighter margin of raw execution time than any other day in the log, and recommended a cheap spot-check (confirming the raw output files referenced actually exist on Luna with timestamps spread across the claimed window) before treating that day's numbers as unchallenged. No other agent found or could independently corroborate a problem — it's flagged as "worth checking because nobody has, not because something looks wrong."

---

## Track B — what it is, and where it actually stands

### What Track B actually is, explained from scratch

Track B extends a *different*, already-published piece of prior work in this project: the cell-width reduction experiment, which showed Kraken2's hash table cells (each cell stores which species a k-mer belongs to) could be shrunk from 32 bits down to 24 or 16 bits, at a mathematically well-understood cost in false-positive rate. Track B is three follow-on pieces from that report's own "future work" section:

1. **B1 — double hashing.** Right now, when two different k-mers hash to the same cell (a collision), Kraken2 resolves it by checking the *next* cell, then the next, and so on (linear probing) — collisions clump together, which hurts lookup speed and false-positive behavior. Double hashing instead computes a *second*, independent hash to decide how far to jump on a collision, spreading collisions out instead of letting them clump. No published genomics hash table uses this — a real, citable gap.
2. **B2 — the bitmask cell.** Instead of a cell storing *which one* species a k-mer belongs to (an ID), it stores one yes/no bit *per species* in a small, fixed panel (the ESKAPE panel — six clinically important drug-resistant bacteria species: *Enterococcus faecium*, *Staphylococcus aureus*, *Klebsiella pneumoniae*, *Acinetobacter baumannii*, *Pseudomonas aeruginosa*, *Enterobacter* species — hence "ESKAPE"). When two k-mers collide in this scheme, their answer bits get OR'd together instead of one overwriting the other — the correct answer survives, you just sometimes pick up one extra, incorrect "maybe" bit. A gentler kind of mistake than what happens today, where a collision can silently erase the correct answer.
3. **B3 — the merged lookup cache**, tying B1/B2 back to Track A's cache work.

### What we found, verified directly against the real source code

**B2 does not need B1 built first.** This isn't an assumption or an analogy — it's confirmed by reading Kraken2's real `Get()` function directly: the code that decides *where to probe next* on a collision (`second_hash()`, the step function) and the code that decides *what a cell's contents mean* (`hashed_key()`, `value()`) are genuinely separate, non-overlapping pieces of logic. Changing one doesn't require touching the other. And B2 is also, simply, what you actually asked for by name at Meeting 11 — double hashing wasn't on that list.

**B1's real code cost, corrected from an earlier, too-optimistic understanding:**

```cpp
// second_hash() already exists in the real Kraken2 source, already wired
// into every probe - but under the default build flag, it's a stub:
uint64_t second_hash(uint64_t hc) {
#ifdef LINEAR_PROBING
  return 1;
#else
  return ((hc >> 8) | 1);   // (illustrative - the real alternate branch)
#endif
}
```
We'd previously believed this meant "a complete, working double-hashing implementation already exists, dead behind a flag — B1 is a flag flip and a rebuild." That's not accurate: under the default flag, `second_hash()` unconditionally returns the constant 1 (which makes every "jump" in the probe sequence exactly 1 cell — linear probing, by construction). Turning on real double hashing means writing an actual second hash function, not just flipping a switch — smaller work than designing an entirely new probing scheme, but real engineering, not free. And there's a cost with no code-side workaround: Kraken2 databases are *built* with a probing scheme baked in, so testing double hashing against real data means rebuilding a database from scratch, not just recompiling the classifier.

**The ESKAPE panel's real ceiling.** Checking this project's own earlier records directly: only 4 of the 6 named species were ever actually downloaded in the first place (*E. faecium* and *Enterobacter* were never pulled) — a structural gap that predates, and is separate from, two other database files that were later lost from disk for unrelated reasons. Report B2's results as covering a 4-organism panel unless the other two get sourced first.

**Current status: zero Luna commits for any of B1/B1b/B2/B3, entirely by your own explicit instruction** to finish Track A completely before starting Track B work — not from neglect or lack of planning. `B2.1` (deriving the math for how often the bitmask's "gentler mistake" happens — pure paper/math work, zero Luna dependency) is the one piece that could start in parallel with zero cost regardless of how the Track A pace question resolves.

---

## Master Q&A bank — cross-cutting questions likely to come up

**"Walk me through the whole thing in two minutes."**
We rebaselined on the Kraken2 version you asked us to use (S0), found Kraken2 already had a tiny built-in cache and gave it real memory (S1) — which showed us a single memory slot isn't enough on large databases. We built the 4-way cache you specifically asked for (S2), audited our own work independently and found a real wiring bug, fixed the parts that mattered, and confirmed the cache's low hit rate is a genuine capacity limit, not a bug. We fixed a crash and a slowdown and built a real hardware-aware sizing formula (S3) — necessary work, but it didn't move wall-clock time, and we can explain exactly why. Then we found the cache's set-selection hashing was badly broken, fixed it for a real 8.9× hit-rate win (S4) — and that fix reversed an earlier result we'd already reported, so we're telling you that directly instead of quietly building past it. Right now we're pivoting toward making the lookup itself faster via prefetching (S5), which is built and merged but hasn't been measured yet. Track B hasn't started, exactly as you asked.

**"Why should I trust any of these numbers?"**
Because every comparison in this project uses the same disciplined methodology: interleaved runs (never back-to-back blocks, to rule out page-cache and thermal confounds), a 5%-coefficient-of-variation trust threshold, and — critically — four separate rounds of independent multi-agent review that each caught real, concrete errors (a wiring bug, a wrong struct-size assumption, a wrong cache-size assumption, a stale doc claim). We report null results and reversed results as plainly as wins.

**"What's the single most important thing that happened in the last two weeks?"**
The S4 reversal. We found a real bug (broken hash-mixing), fixed it, and that fix invalidated a result we'd already reported as a win — and we caught this ourselves, before building the next planned step on top of the now-disproven basis.

**"What's actually still open/unknown right now?"**
S5's real number (built, not measured); the sizing formula's `f=0.25` safety fraction (a placeholder, not empirically tuned); whether the reuse-distance shape holds beyond `standard_8gb`/T=1; the S2 nesting cleanup (tested as irrelevant, never actually merged out); and the pace question the pivot debate explicitly left for you to decide.

**"If eviction policy 'doesn't matter,' why does Thesis 1 (the adaptive cache) still make sense?"**
Because "eviction policy as currently tested doesn't matter" and "an adaptive cache doesn't matter" are different claims. The capacity constraint, the hardware-aware sizing, and the correct-hashing fix are all real, working, verified pieces. What's genuinely open is whether more eviction-policy sophistication is worth the remaining time — and the pivot debate's answer is "only pseudo-LRU or admission control, both cheap, both bounded by the same reuse-distance ceiling" — not "eviction is a dead end."

---

## Commit / tag reference

| Tag | What it is | Commit |
|---|---|---|
| `safe/S1.2` | S1.1 thread_local promotion, measured | `fbf993d9` |
| `safe/S2.4` | S2.1–S2.3, 4-way cache (nesting bug documented in the message) | `75f908e4` |
| `safe/S3.0` | Heap-pointer crash fix | `c2981a7` |
| `safe/S3.1-S3.2` | LLC-topology-aware sizing formula | `f686002` |
| `safe/S3.3` | Zero-sentinel + calloc fix | `b8c1ee0` |
| `safe/S4.0-hashmix` | MurmurHash3 set-index fix | `a240d60` |
| *(none yet)* | S5.0 prefetch-batching | patch committed to this repo (`plan_paper/scripts/s5_0_prefetch_batch_patch.py`), not yet applied+tagged on Luna's `kraken2-src-fresh` tree |

All tags live in `~/tools/kraken2-src-fresh` on Luna (a separate git repo from this project's own history), as detached-HEAD tags off the `v2.17.1` checkout — this project has never used branches for checkpoints, only tags, going back to `safe/S1.2`.
