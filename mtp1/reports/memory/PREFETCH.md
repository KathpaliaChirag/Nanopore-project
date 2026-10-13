# Software prefetch for kraken2 (`-B`)

**A 12–20% speedup with byte-identical output.** The classifier's inner loop now
looks up minimizers in batches, starting several memory fetches before waiting
for any of them.

| | |
|---|---|
| Binary | `scratch_lookaside/bin/classify_prefetch` |
| Flag | `-B N` (batch size; default 1 = stock behaviour) |
| Best measured | **−20.3%** on pod5_2 (§12), **−12.0%** on merged_fast (§14) |
| Best `-B` | **31** on the large workload; anything 16–32 is equivalent |
| Accuracy | unchanged — byte-identical output, 29/29 checks |
| Source | `scratch_lookaside/src/` (`kraken2/src/` untouched) |
| Patch | `scripts/kraken2_prefetch.patch` |

**Contents**

- **Part I — The problem** · §1 where time goes · §2 memory hierarchy · §3 the real bottleneck
- **Part II — The idea** · §4 overlap don't avoid · §5 worked example · §6 structure before/after
- **Part III — The code** · §7 three files · §8 the traps · §9 the flag
- **Part IV — Correctness** · §10 verification
- **Part V — Measurements** · §11 protocol · §12 32-bit · §13 24-bit · §14 large workload · §15 counter observation
- **Part VI — Practical** · §16 usage · §17 limits · §18 next

---

# Part I — The problem

## 1. Where the time goes

Kraken2 identifies which organism a DNA read came from. From each read it
extracts short chunks called **minimizers**, and for each one it asks a lookup
table a single question: *which organism does this chunk belong to?*

| | |
|---|---:|
| reads in the test file | 151,591 |
| bases | 499.98 Mbp |
| **lookups performed** | **160,625,038** |
| lookup table `hash.k2d` | **48.8 MB**, 8.9 M entries |

Essentially all runtime is those 160 million lookups. `perf` puts the time in
`CompactHashTable::Get`. But *why* it is slow decides what can fix it.

## 2. The memory hierarchy

The CPU does not read RAM directly. The differences are enormous:

| where | size | cost to fetch |
|---|---|---:|
| registers | bytes | 0 cycles |
| L1 cache | 48 KB | ~4 cycles |
| L2 cache | 512 KB | ~14 cycles |
| L3 cache | **16 MB** | ~50 cycles |
| **main RAM** | 31 GB | **~200 cycles** |

Two facts collide:

> **The table is 48.8 MB. The L3 cache is 16 MB. It does not fit.**

> **A hash table scatters entries at random — that is what makes it a hash
> table.** Consecutive lookups land in unrelated places, so there is no pattern
> for the hardware prefetcher to learn.

At best about a third of lookups can hit L3. The rest go to DRAM: ~200 cycles,
160 million times.

## 3. The real bottleneck

Here is the stock loop:

```c
while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {
  taxid_t taxon;
  ...
  taxon = hash->Get(*minimizer_ptr);   // ◄── blocks ~200 cycles
  ...                                  //     only then scan the next minimizer
}
```

Measured on pod5_2, 16 threads:

| | |
|---|---:|
| cycles per lookup | 868 |
| DRAM accesses per lookup | 0.938 |
| DRAM latency | ~200 cycles |
| latency exposed per lookup | ~187 cycles (**21% of runtime**) |
| **memory-level parallelism** | **1.24** |
| what the core can sustain | **~12** |

The last two lines are the finding.

The processor can keep about **twelve** memory requests in flight at once — think
of a shop with twelve service counters. This loop keeps **1.24**. It stands at
one counter, asks for one item, waits, then asks for the next. Eleven counters
sit idle.

**Why?** The loop structure forbids anything else. The line after `Get()` needs
the answer immediately, and the CPU cannot start fetching the *next* minimizer
because it has not been scanned yet — and it cannot be scanned until this
iteration finishes.

> **This is not a slow hash table. It is a loop that refuses to ask more than one
> question at a time.**

---

# Part II — The idea

## 4. Overlap, don't avoid

Prefetching does **not** remove a memory access. It **overlaps** them.

Four minimizers, stock — the waits queue up:

```
A ─ hash ─ load ▓▓▓▓▓▓▓▓ 200cy ─ use A
                                  B ─ hash ─ load ▓▓▓▓▓▓▓▓ 200cy ─ use B
                                                                   C ─ ...
                                            total ≈ 800 cycles of waiting
```

Four minimizers, batched — the waits overlap:

```
PASS 1   hash A → prefetch ▓▓▓▓▓▓▓▓
         hash B → prefetch  ▓▓▓▓▓▓▓▓     four fetches
         hash C → prefetch   ▓▓▓▓▓▓▓▓    travelling at once
         hash D → prefetch    ▓▓▓▓▓▓▓▓
PASS 2   use A ─ use B ─ use C ─ use D
                                            total ≈ 200 cycles of waiting
```

Same four accesses, same order of results, same answers. They simply stop
queueing behind each other. Four dishes cooked one after another, versus four
pans on the stove at once.

**The tool.** `__builtin_prefetch(address, 0, 3)` means *"start bringing this
address into cache; do not wait for it; return immediately."* (`0` = prepare for
read, `3` = keep in all cache levels.) It is a request, not a fetch — it places
the order and walks away.

**Why two passes are unavoidable.** A prefetch does not deliver data instantly;
it *starts* a journey that still takes ~200 cycles. So this gains nothing:

```c
prefetch(A);
use(A);        // ◄── still waits the full 200 cycles
```

You need real work between "ask" and "use" so the data has time to arrive. Pass 1
hashing B, C and D **is** that work — and it is work that had to happen anyway.
A's line arrives during time already being spent.

## 5. A worked example

Batch size 4. Say the scanner is about to produce minimizers **A B C D**, of
which **C is ambiguous** (a run of `N` in the read).

### Pass 1 — scan, hash, fire. Nothing waits.

| step | action | `pf[]` after | memory |
|---|---|---|---|
| 1 | `NextMinimizer()` → A | `pf[0].min = A` | |
| 2 | `is_ambiguous()` → false | `pf[0].amb = false` | |
| 3 | `MurmurHash3(A)` → slot 4,812,003 | `pf[0].hc = …` | |
| 4 | `Prefetch(hc)` | | **A's line requested** ▓ |
| 5 | `NextMinimizer()` → B | `pf[1].min = B` | A still travelling |
| 6–8 | hash B → slot 91,447 → prefetch | `pf[1]` filled | **B requested** ▓ |
| 9 | `NextMinimizer()` → C | `pf[2].min = C` | |
| 10 | `is_ambiguous()` → **true** | `pf[2].amb = true` | |
| 11 | **no hash, no prefetch** — C needs no lookup | | |
| 12–15 | D: scan, hash → slot 7,003,918, prefetch | `pf[3]` filled | **D requested** ▓ |

Pass 1 ends. `n_pf = 4`. **Three fetches are in flight simultaneously.** The scan
and hash work for B, C and D was the cover that let A's line arrive.

### Pass 2 — resolve, in the original order

| `pf_i` | what happens |
|---|---|
| 0 | `pf[0].amb` false → `GetWithHash(A, pf[0].hc)`. **The line is already in L1** — no 200-cycle wait. Hit → `minimizer_hit_groups++`, `hit_counts[taxon]++`, `taxa.push_back(taxon)` |
| 1 | same for B, also already arrived |
| 2 | `pf[2].amb` **true** → `taxon = AMBIGUOUS_SPAN_TAXON`, no lookup at all, `taxa.push_back` |
| 3 | same for D |

Output order is **A, B, C, D** — exactly the stock order. The only thing that
changed is *when the memory was requested*.

### The same batch if a minimizer repeats

Suppose B and C are the same minimizer. Pass 1 prefetches both — the second is
wasted work, harmless. Pass 2 hits the duplicate-skip branch (`pf[i].min ==
last_minimizer`) and reuses `last_taxon` without a lookup, exactly as stock does.

> **A wasted prefetch can never produce a wrong answer.** It fetched something
> that went unused. That is the property that makes the whole transformation
> safe.

## 6. The structure, before and after

### Before — one loop, one wait per minimizer

```
┌─ while (NextMinimizer() != nullptr) ─────────────┐
│                                                  │
│   scan one minimizer                             │
│   check if ambiguous                             │
│   hash it (for the -M check)                     │
│   ►►► hash->Get()  ── WAIT ~200 cycles ◄◄◄       │
│   count the hit                                  │
│   record it                                      │
│                                                  │
└──────────── repeat 160,000,000 times ────────────┘
```

### After — one loop containing two

```
┌─ while (! frame_done) ───────────────────────────────────┐
│                                                          │
│  ┌─ PASS 1: while (n_pf < B) ─────────────────────────┐  │
│  │   scan one minimizer         ─┐                    │  │
│  │   check if ambiguous → SAVE   │  no waiting        │  │
│  │   hash it            → SAVE   │  anywhere          │  │
│  │   Prefetch()  ── fire & go   ─┘  in here           │  │
│  └────────────── repeat B times ──────────────────────┘  │
│                                                          │
│            ↓ B fetches now travelling in parallel ↓      │
│                                                          │
│  ┌─ PASS 2: for (pf_i = 0 .. n_pf) ───────────────────┐  │
│  │   GetWithHash()  ── data already arrived           │  │
│  │   count the hit          ─┐                        │  │
│  │   record it               │ identical to stock     │  │
│  └───────────────────────────┴────────────────────────┘  │
│                                                          │
└──────────────── repeat 160,000,000 / B times ────────────┘
```

### The change in one sentence

> **The stock loop body was cut at the memory access. Everything above the cut
> became pass 1; everything below became pass 2.**

The cut point is `hash->Get()` — the one line that blocks.

### Where each stock line went

| stock line | now lives in |
|---|---|
| `scanner.NextMinimizer()` | pass 1 |
| `scanner.is_ambiguous()` | pass 1 → **saved** into `pf[].amb` |
| `MurmurHash3(...)` | pass 1 → **saved** into `pf[].hc` |
| **`hash->Get()`** ← **the cut** | split: `Prefetch()` in pass 1, `GetWithHash()` in pass 2 |
| `minimizer_hit_groups++` | pass 2 |
| `add_kmer(...)` | pass 2 |
| `hit_counts[taxon]++` | pass 2 |
| `taxa.push_back(taxon)` | pass 2 |

Everything in the bottom half is the **stock code unchanged**, reading
`pf[pf_i].min` where it read `*minimizer_ptr`.

### Three structural details

**The exit condition moved.** Stock exits when `NextMinimizer()` returns
`nullptr` — the `while` condition itself. That scan now happens in pass 1, so
exhaustion sets a **`frame_done` flag** and the outer loop tests that. Pass 1
breaks immediately, but **pass 2 still runs on the partial batch** — otherwise
the last few minimizers of every read would be silently dropped.

**`n_pf` matters, not `la_batch`.** Pass 2 iterates over the number actually
scanned, which on a read's final batch is usually fewer than `B`.

**The state variables stayed outside both loops.** `last_minimizer`,
`last_taxon`, `minimizer_hit_groups`, `hit_counts` and `taxa` are exactly where
they were. Pass 2 walks minimizers in the same order the stock loop did, so it
sees the same sequence of states. **That is why the output is byte-identical:
pass 2 is the stock loop, fed from an array instead of straight from the
scanner.**

---

# Part III — The code

## 7. Three files

### `kv_store.h` (+5) — declare two new abilities

```c
virtual hvalue_t GetWithHash(hkey_t key, uint64_t hc) const = 0;
virtual void     Prefetch(uint64_t hc) const = 0;
```

**Why:** `Get()` welds "work out where it is" to "go and get it". The caller now
needs those as two separate steps, far apart in program time.

### `compact_hash.h` (+14/−1) — split the operation

Stock:

```c
hvalue_t CompactHashTable<Cell>::Get(hkey_t key) const {
  uint64_t hc = MurmurHash3(key);     // step 1: where is it?
  size_t idx = hc % capacity_;        // step 2: go and get it
  ... search ...
}
```

Now three functions:

```c
// unchanged from the outside — a wrapper
hvalue_t CompactHashTable<Cell>::Get(hkey_t key) const {
  return GetWithHash(key, MurmurHash3(key));
}

// NEW: start the fetch, return instantly
template<typename Cell>
void CompactHashTable<Cell>::Prefetch(uint64_t hc) const {
  __builtin_prefetch(&table_[hc % capacity_], 0, 3);
}

// the old body, minus its first line
template<typename Cell>
hvalue_t CompactHashTable<Cell>::GetWithHash(hkey_t key, uint64_t hc) const {
  uint64_t compacted_key = hc >> (64 - key_bits_);
  size_t idx = hc % capacity_;
  ... search ...          // ◄── identical to stock
}
```

Two things to notice:

**Every existing caller still works.** `Get()` does what it always did, so
nothing else in kraken2 needed changing.

**A free bonus.** `hc` is now computed once and given to both the prefetch and
the lookup. Stock hashed every minimizer **twice** — once for the `-M` check,
once inside `Get()` — because the two sites could not share. Now they do.

### `classify.cc` (+79/−34) — cut the loop in two

The buffer:

```c
static int la_batch = 1;          // the -B value
struct PfSlot {
  uint64_t min;   // the minimizer
  uint64_t hc;    // its hash, computed once in pass 1
  bool     amb;   // is_ambiguous() AT SCAN TIME — captured, see §8
};
static const int PF_MAX = 64;
```

**Pass 1:**

```c
PfSlot pf[PF_MAX];
bool frame_done = false;
while (! frame_done) {
  int n_pf = 0;
  while (n_pf < la_batch) {
    minimizer_ptr = scanner.NextMinimizer();
    if (minimizer_ptr == nullptr) { frame_done = true; break; }
    pf[n_pf].min = *minimizer_ptr;
    pf[n_pf].amb = scanner.is_ambiguous();
    if (! pf[n_pf].amb) {
      pf[n_pf].hc = MurmurHash3(pf[n_pf].min);
      hash->Prefetch(pf[n_pf].hc);            // fire, no wait
    }
    n_pf++;
  }
```

**Pass 2** — the stock body, reading `pf[pf_i]`:

```c
  for (int pf_i = 0; pf_i < n_pf; pf_i++) {
    taxid_t taxon;
    if (pf[pf_i].amb) {                       // was: scanner.is_ambiguous()
      taxon = AMBIGUOUS_SPAN_TAXON;
    }
    else {
      if (pf[pf_i].min != last_minimizer) {
        bool skip_lookup = false;
        if (idx_opts.minimum_acceptable_hash_value) {
          if (pf[pf_i].hc < idx_opts.minimum_acceptable_hash_value)
            skip_lookup = true;               // was: MurmurHash3(...) a 2nd time
        }
        taxon = 0;
        if (! skip_lookup)
          taxon = hash->GetWithHash(pf[pf_i].min, pf[pf_i].hc);
        last_taxon = taxon;
        last_minimizer = pf[pf_i].min;
        if (taxon) {
          minimizer_hit_groups++;
          if (!opts.report_filename.empty())
            curr_taxon_counts[taxon].add_kmer(pf[pf_i].min);  // was: scanner.
        }
      }
      else { taxon = last_taxon; }
      if (taxon) {
        if (opts.quick_mode && minimizer_hit_groups >= opts.minimum_hit_groups) {
          call = taxon;
          goto finished_searching;
        }
        hit_counts[taxon]++;
      }
    }
    taxa.push_back(taxon);
  }
}
```

## 8. The traps the split created

These are where a careless version silently corrupts results.

**Trap 1 — `is_ambiguous()` must be captured, not re-asked.** It reports on
wherever the scanner is *now*. Pass 1 advances it past all B minimizers, so
asking in pass 2 would return minimizer B's answer while processing minimizer 1 —
wrong for every entry but the last. Hence `pf[].amb`.

**Trap 2 — `scanner.last_minimizer()` became `pf[pf_i].min`.** Same reason.

> ⚠ This is only safe because `NextMinimizer()` returns `&last_minimizer_`
> (`mmscanner.cc:146,156,188`), making the captured value provably identical.
> **If that changes upstream this line breaks silently** — no crash, no warning,
> just wrong `add_kmer` counts. It is the one place where correctness depends on
> another file's internals.

**Trap 3 — what was deliberately left alone.** The depth-1 duplicate skip,
`minimizer_hit_groups++` *and its exact position*, `hit_counts`, the
`taxa.push_back` ordering, and the `quick_mode` `goto`. An earlier patch in this
project moved that one increment and silently changed hit-group counts at frame
boundaries. Restructuring a loop is the easiest way to introduce an invisible
bug, so nothing not strictly required was touched.

## 9. The `-B` flag

```c
while ((opt = getopt(argc, argv, "h?H:t:o:T:p:R:C:U:O:Q:g:B:nmzqPSMKD")) != -1) {
  ...
  case 'B' :
    la_batch = atoi(optarg);
    if (la_batch < 1 || la_batch > PF_MAX)
      errx(EX_USAGE, "-B expects a batch size between 1 and %d", PF_MAX);
    break;
```

`B:` was inserted without disturbing the existing letters — an earlier version of
this work collided with kraken2's own `-K`. **Default is 1, and a batch of 1 is
the stock path**, so the binary behaves exactly like stock unless `-B` is given.

---

# Part IV — Correctness

## 10. Verification

Output file **and** report compared byte-for-byte against unmodified
`kraken2_bin/classify`:

| | pod5_15 | pod5_2 |
|---|---|---|
| `-B 1`, `-p 1` / `-p 16` | identical | identical |
| `-B 8`, `-p 1` / `-p 16` | identical | identical |
| `-B 16`, `-p 1` / `-p 16` | identical | identical |
| `-B 32`, `-p 1` / `-p 16` | identical | identical |

**16 of 16 exact**, and 29/29 across the wider sweep (16 pod5 files, 10 option
paths, 4 cell-size databases). Unlike the lookaside-cache work there is no
accuracy trade-off at all — the same lookups happen, in the same order, with the
same results.

---

# Part V — Measurements

## 11. Protocol

pod5_2.fastq: 151,591 reads, 499.98 Mbp, 160,625,038 lookups.
`-p 16 -g 2 -T 0`. Six perf events: `cache-misses`, `cache-references`,
`LLC-loads`, `LLC-load-misses`, `instructions`, `cycles`.

Earlier sweeps interleaved repetitions to average out machine drift. **That was
not enough:** on this box the same binary measured 1.850 s and 2.898 s in one
batch of 20 runs while executing an *identical* instruction count (176.05–176.20
G, a 0.09% spread). The work is perfectly reproducible; only the clock is not.

These figures use a **cooldown protocol** instead: three consecutive runs per
configuration, then 240 s idle before the next. That equalises machine state at
the start of every group. Package temperature held **59–65 °C across all 33
groups**; standard deviations are **0.004–0.021 s**, against up to 0.32 s
interleaved. **0 crashes in 99 runs.**

> **Read the `sd` column first.** A time quoted from a group with sd 0.3 s means
> something different from one with sd 0.005 s.

## 12. Results — 32-bit database

`eskape_32bit_fork`, 48.8 MB. Mean of 3 runs per row.

| `-B` | clsfd% | elapsed | sd | cache-refs | cache-misses | cm% | LLC-loads | LLC-ld-miss | llc% | instructions | IPC | cycles | cyc/lk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **stock** | 84.26 | 2.349 | 0.005 | 730,972,419 | 454,930,772 | 62.24 | 255,888,559 | 152,454,910 | 59.58 | 157,981,272,421 | 1.04 | 151,765,582,656 | 944.8 |
| `1` | 84.26 | 2.475 | 0.010 | 745,396,841 | 461,418,715 | 61.90 | 96,729,737 | 31,488,040 | 32.56 | 185,726,608,917 | 1.15 | 161,499,507,153 | 1005.4 |
| `2` | 84.26 | 2.310 | 0.006 | 748,758,770 | 466,137,680 | 62.25 | 88,736,222 | 27,168,501 | 30.62 | 180,733,146,717 | 1.20 | 150,404,025,151 | 936.4 |
| `3` | 84.26 | 2.217 | 0.008 | 744,203,705 | 462,980,640 | 62.21 | 87,002,922 | 25,074,062 | 28.83 | 179,080,136,342 | 1.24 | 144,487,318,252 | 899.5 |
| `4` | 84.26 | 2.131 | 0.008 | 713,475,256 | 442,271,998 | 61.99 | 84,341,728 | 24,742,116 | 29.34 | 178,264,297,924 | 1.28 | 139,432,856,289 | 868.1 |
| `5` | 84.26 | 2.098 | 0.008 | 689,925,138 | 426,704,869 | 61.85 | 81,863,640 | 24,646,622 | 30.13 | 177,745,106,453 | 1.30 | 137,190,830,239 | 854.1 |
| `6` | 84.26 | 2.042 | 0.008 | 679,117,401 | 419,542,865 | 61.78 | 80,749,983 | 24,604,419 | 30.48 | 177,411,985,302 | 1.33 | 133,588,013,629 | 831.7 |
| `7` | 84.26 | 2.025 | 0.021 | 670,065,619 | 414,109,825 | 61.80 | 79,280,538 | 24,717,304 | 31.18 | 177,158,921,653 | 1.35 | 131,387,041,241 | 818.0 |
| `8` | 84.26 | 1.992 | 0.010 | 669,218,369 | 411,427,953 | 61.48 | 81,154,425 | 24,703,873 | 30.47 | 176,976,722,060 | 1.36 | 129,561,797,065 | 806.6 |
| `9` | 84.26 | 1.975 | 0.010 | 662,825,739 | 407,856,694 | 61.53 | 80,280,393 | 24,827,445 | 30.93 | 176,848,987,709 | 1.37 | 128,776,476,612 | 801.7 |
| `10` | 84.26 | 1.967 | 0.008 | 660,243,826 | 405,736,076 | 61.45 | 80,688,409 | 24,825,273 | 30.77 | 176,741,184,918 | 1.38 | 128,099,559,505 | 797.5 |
| `11` | 84.26 | 1.950 | 0.016 | 659,221,786 | 405,838,881 | 61.57 | 79,057,360 | 24,904,311 | 31.50 | 176,635,804,528 | 1.39 | 126,861,619,116 | 789.8 |
| `12` | 84.26 | 1.932 | 0.004 | 657,666,230 | 404,864,355 | 61.56 | 78,807,199 | 24,884,458 | 31.58 | 176,577,374,201 | 1.40 | 125,943,874,624 | 784.1 |
| `13` | 84.26 | 1.923 | 0.011 | 659,492,598 | 404,162,728 | 61.29 | 82,111,716 | 24,884,957 | 30.35 | 176,514,292,144 | 1.41 | 125,474,692,525 | 781.2 |
| `14` | 84.26 | 1.923 | 0.007 | 660,533,118 | 405,595,036 | 61.40 | 80,964,157 | 24,884,163 | 30.75 | 176,459,619,810 | 1.41 | 124,767,205,659 | 776.8 |
| `15` | 84.26 | 1.916 | 0.008 | 656,446,742 | 403,165,554 | 61.42 | 80,711,716 | 24,979,035 | 30.99 | 176,441,213,665 | 1.41 | 125,221,255,116 | 779.6 |
| `16` | 84.26 | 1.913 | 0.013 | 654,034,565 | 402,756,223 | 61.58 | 78,644,878 | 24,967,170 | 31.76 | 176,357,802,793 | 1.42 | 124,424,276,628 | 774.6 |
| `17` | 84.26 | 1.901 | 0.006 | 654,057,592 | 401,897,734 | 61.44 | 79,944,308 | 24,994,435 | 31.27 | 176,323,026,749 | 1.42 | 123,884,866,197 | 771.3 |
| `18` | 84.26 | 1.900 | 0.009 | 654,582,850 | 401,761,655 | 61.38 | 80,896,735 | 25,029,135 | 30.94 | 176,309,130,490 | 1.42 | 123,912,259,541 | 771.4 |
| `19` | 84.26 | 1.896 | 0.010 | 653,883,080 | 401,990,986 | 61.48 | 79,250,140 | 25,083,823 | 31.66 | 176,287,915,980 | 1.43 | 123,608,468,941 | 769.5 |
| `20` | 84.26 | 1.885 | 0.010 | 654,505,532 | 402,124,482 | 61.44 | 79,819,640 | 25,064,437 | 31.44 | 176,222,587,841 | 1.44 | 122,638,595,035 | 763.5 |
| `21` | 84.26 | 1.889 | 0.007 | 649,793,026 | 399,909,850 | 61.54 | 79,074,712 | 25,062,600 | 31.70 | 176,235,243,378 | 1.43 | 123,634,116,288 | 769.7 |
| `22` | 84.26 | 1.888 | 0.004 | 652,122,200 | 400,561,275 | 61.42 | 79,722,435 | 25,081,616 | 31.46 | 176,196,027,833 | 1.43 | 122,973,464,875 | 765.6 |
| `23` | 84.26 | 1.890 | 0.016 | 654,553,008 | 401,885,870 | 61.40 | 80,700,871 | 25,159,155 | 31.18 | 176,157,216,452 | 1.44 | 122,443,274,404 | 762.3 |
| `24` | 84.26 | 1.881 | 0.013 | 652,596,117 | 400,376,158 | 61.35 | 81,410,262 | 25,145,550 | 30.89 | 176,130,495,999 | 1.44 | 122,351,143,344 | 761.7 |
| `25` | 84.26 | 1.890 | 0.014 | 651,443,004 | 400,554,252 | 61.49 | 78,936,773 | 25,203,207 | 31.95 | 176,180,431,434 | 1.43 | 122,938,588,289 | 765.4 |
| `26` | 84.26 | 1.874 | 0.011 | 650,120,546 | 400,700,970 | 61.63 | 78,135,930 | 25,195,326 | 32.25 | 176,114,703,479 | 1.44 | 122,041,480,222 | 759.8 |
| `27` | 84.26 | 1.877 | 0.015 | 652,458,525 | 400,819,357 | 61.43 | 79,623,869 | 25,194,501 | 31.64 | 176,102,998,666 | 1.44 | 122,089,327,597 | 760.1 |
| `28` | 84.26 | 1.876 | 0.008 | 653,975,071 | 401,809,330 | 61.44 | 79,995,724 | 25,161,421 | 31.48 | 176,063,994,231 | 1.45 | 121,364,074,957 | 755.6 |
| `29` | 84.26 | 1.875 | 0.012 | 650,027,400 | 399,197,443 | 61.41 | 79,981,942 | 25,258,127 | 31.60 | 176,104,159,269 | 1.44 | 121,935,282,175 | 759.1 |
| `30` | 84.26 | 1.871 | 0.005 | 651,581,402 | 399,432,191 | 61.30 | 81,239,978 | 25,230,346 | 31.07 | 176,074,747,671 | 1.44 | 121,871,672,040 | 758.7 |
| `31` | 84.26 | 1.875 | 0.005 | 650,324,429 | 400,084,937 | 61.52 | 78,908,305 | 25,304,497 | 32.08 | 176,086,751,200 | 1.45 | 121,650,576,957 | 757.4 |
| `32` | 84.26 | 1.875 | 0.016 | 653,410,862 | 400,146,736 | 61.24 | 81,316,733 | 25,298,841 | 31.16 | 176,043,755,461 | 1.45 | 121,401,335,598 | 755.8 |

Raw perf output, 99 files: `result/prefetch/sleep_sweep/`.
Plain-text copy: `result/prefetch/TABLE.txt`.

### What the numbers say

**The result never changes.** `clsfd%` is 84.26 on every row.

**stock 2.349 s → `-B 30` 1.871 s = −20.34%.** With noise removed this is nearly
double the −11.8% measured under the interleaved protocol. The earlier figures
were not wrong; they were measured through 10–15% of noise that hid most of the
effect.

**`-B 1` costs +5.37%** (sd 0.010, so this is reliable). It runs the identical
algorithm to stock but executes 185.7 G instructions against 158.0 G — **17.6%
more**. That is the batching machinery itself, and every batch size pays it
before it can win anything.

**The curve descends smoothly to about `-B 20`, then flattens**: 2.475 → 2.131
(B=4) → 1.992 (B=8) → 1.913 (B=16) → 1.885 (B=20) → 1.871 (B=30). Beyond 20 the
gain is under 1%. Earlier sweeps appeared to show the knee at 4 because noise
swamped everything past it.

**Instructions fall as the batch grows** (185.7 G at B=1 → 176.0 G at B=32) while
IPC rises 1.04 → 1.45. Larger batches amortise the per-batch loop overhead, so
they are both cheaper and better pipelined.

### Why more instructions finish sooner

| | stock | `-B 30` |
|---|---:|---:|
| instructions / lookup | 983.6 | 1096.7 **(+11%)** |
| cycles / lookup | 944.8 | 758.7 **(−20%)** |
| IPC | 1.04 | 1.44 **(+38%)** |

The processor executes **more** work and finishes **sooner**, because it stops
standing still. The old version's cycles were largely spent doing nothing; IPC
rising from 1.04 to 1.44 is that idleness disappearing. That is the entire
mechanism in one table.

## 13. Results — 24-bit database

Run identically — `-B` 1–32 plus stock, cooldown protocol, same six events, same
workload — against `eskape_24bit`. 99 runs, **0 crashes**, 60–68 °C, spreads
0.002–0.022 s. `clsfd%` is 84.27 on every row.

Raw perf output: `result/prefetch24/perf/` (99 files).
Plain-text table: `result/prefetch24/TABLE.txt`.

### Why this database is different

| | eskape_32bit_fork | eskape_24bit |
|---|---:|---:|
| size | 46.5 MB | **34.9 MB** |
| 4 KB pages | 11,914 | **8,935** |
| cell | 4 bytes, naturally aligned | **3 bytes, unaligned** |

Smaller table means less memory pressure. Unaligned 3-byte cells mean every
access goes through packed accessors that assemble the value byte by byte, so
more instructions. The two effects pull in opposite directions.

| `-B` | clsfd% | elapsed | sd | cache-refs | cache-misses | cm% | LLC-loads | LLC-ld-miss | llc% | instructions | IPC | cycles | cyc/lk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **stock** | 84.27 | 2.309 | 0.005 | 730,574,199 | 430,699,867 | 58.95 | 239,070,040 | 136,437,017 | 57.07 | 163,721,448,664 | 1.10 | 149,391,553,561 | 930.1 |
| `1` | 84.27 | 2.451 | 0.004 | 758,089,404 | 444,142,892 | 58.59 | 80,875,450 | 30,076,318 | 37.19 | 191,967,277,466 | 1.20 | 160,242,393,773 | 997.6 |
| `2` | 84.27 | 2.296 | 0.003 | 755,228,718 | 445,065,223 | 58.93 | 77,853,973 | 27,810,470 | 35.72 | 187,052,535,575 | 1.25 | 150,267,730,693 | 935.5 |
| `3` | 84.27 | 2.211 | 0.009 | 739,342,134 | 438,090,160 | 59.26 | 74,685,600 | 26,318,173 | 35.26 | 185,373,501,640 | 1.28 | 144,479,519,284 | 899.5 |
| `4` | 84.27 | 2.122 | 0.013 | 715,443,742 | 424,452,516 | 59.33 | 72,459,826 | 26,276,597 | 36.27 | 184,545,050,961 | 1.32 | 139,323,221,276 | 867.4 |
| `5` | 84.27 | 2.087 | 0.006 | 688,981,379 | 408,177,276 | 59.24 | 70,930,319 | 26,343,701 | 37.15 | 184,055,373,694 | 1.34 | 137,164,307,443 | 853.9 |
| `6` | 84.27 | 2.057 | 0.013 | 676,115,624 | 399,125,468 | 59.03 | 71,495,985 | 26,562,989 | 37.17 | 183,707,606,699 | 1.36 | 134,956,370,735 | 840.2 |
| `7` | 84.27 | 2.013 | 0.011 | 659,286,966 | 389,554,088 | 59.09 | 69,662,061 | 26,615,131 | 38.21 | 183,463,473,758 | 1.38 | 132,713,246,880 | 826.2 |
| `8` | 84.27 | 2.001 | 0.008 | 653,210,069 | 384,435,704 | 58.85 | 70,897,665 | 26,785,148 | 37.79 | 183,322,724,394 | 1.39 | 131,730,165,220 | 820.1 |
| `9` | 84.27 | 1.986 | 0.014 | 649,767,122 | 383,311,955 | 58.99 | 69,680,316 | 26,780,142 | 38.45 | 183,117,045,038 | 1.41 | 130,073,290,835 | 809.8 |
| `10` | 84.27 | 1.963 | 0.015 | 647,932,784 | 381,483,070 | 58.88 | 70,387,442 | 26,796,203 | 38.09 | 183,008,183,685 | 1.42 | 128,756,566,545 | 801.6 |
| `11` | 84.27 | 1.973 | 0.021 | 643,404,668 | 378,781,208 | 58.87 | 70,324,710 | 26,982,995 | 38.39 | 182,975,058,569 | 1.41 | 129,710,897,083 | 807.5 |
| `12` | 84.27 | 1.950 | 0.004 | 644,013,378 | 379,055,902 | 58.86 | 70,708,914 | 26,949,761 | 38.17 | 182,865,429,283 | 1.43 | 127,703,283,784 | 795.0 |
| `13` | 84.27 | 1.934 | 0.013 | 644,072,625 | 379,482,580 | 58.92 | 69,611,632 | 26,942,247 | 38.71 | 182,788,028,854 | 1.44 | 126,488,326,338 | 787.5 |
| `14` | 84.27 | 1.945 | 0.007 | 641,934,324 | 377,795,172 | 58.85 | 70,741,047 | 27,043,123 | 38.25 | 182,756,412,181 | 1.44 | 127,525,552,672 | 793.9 |
| `15` | 84.27 | 1.928 | 0.006 | 640,774,305 | 377,610,699 | 58.93 | 69,647,087 | 27,026,600 | 38.81 | 182,699,384,515 | 1.45 | 125,931,409,326 | 784.0 |
| `16` | 84.27 | 1.933 | 0.022 | 641,063,675 | 376,818,149 | 58.78 | 70,585,664 | 27,085,183 | 38.41 | 182,661,023,334 | 1.44 | 126,545,533,352 | 787.8 |
| `17` | 84.27 | 1.906 | 0.005 | 638,135,699 | 376,867,948 | 59.06 | 68,857,585 | 27,084,065 | 39.35 | 182,626,373,406 | 1.46 | 125,193,030,756 | 779.4 |
| `18` | 84.27 | 1.907 | 0.005 | 640,638,335 | 376,757,451 | 58.81 | 70,569,315 | 27,083,168 | 38.44 | 182,589,874,117 | 1.46 | 124,897,519,714 | 777.6 |
| `19` | 84.27 | 1.908 | 0.006 | 639,575,015 | 376,413,083 | 58.85 | 70,517,585 | 27,206,761 | 38.59 | 182,596,293,082 | 1.46 | 125,049,522,382 | 778.5 |
| `20` | 84.27 | 1.903 | 0.010 | 640,255,776 | 377,073,435 | 58.89 | 69,795,504 | 27,221,135 | 39.01 | 182,516,792,294 | 1.47 | 124,211,350,443 | 773.3 |
| `21` | 84.27 | 1.905 | 0.010 | 636,633,362 | 375,193,438 | 58.94 | 69,492,533 | 27,255,529 | 39.25 | 182,550,416,673 | 1.46 | 125,091,648,873 | 778.8 |
| `22` | 84.27 | 1.897 | 0.004 | 637,832,974 | 375,588,973 | 58.89 | 70,426,592 | 27,293,976 | 38.76 | 182,497,857,513 | 1.47 | 124,385,809,942 | 774.4 |
| `23` | 84.27 | 1.897 | 0.006 | 636,299,912 | 375,323,052 | 58.99 | 69,847,750 | 27,294,149 | 39.09 | 182,446,408,657 | 1.47 | 124,037,000,338 | 772.2 |
| `24` | 84.27 | 1.892 | 0.005 | 635,973,310 | 374,451,221 | 58.88 | 70,939,350 | 27,320,121 | 38.55 | 182,452,955,596 | 1.47 | 124,347,271,243 | 774.1 |
| `25` | 84.27 | 1.897 | 0.002 | 636,051,910 | 374,451,429 | 58.87 | 70,794,544 | 27,324,024 | 38.69 | 182,479,735,532 | 1.47 | 124,405,847,362 | 774.5 |
| `26` | 84.27 | 1.893 | 0.010 | 635,603,567 | 374,748,747 | 58.96 | 69,980,894 | 27,373,173 | 39.14 | 182,424,799,806 | 1.47 | 123,847,968,227 | 771.0 |
| `27` | 84.27 | 1.880 | 0.012 | 637,089,881 | 375,391,360 | 58.92 | 69,315,509 | 27,329,289 | 39.43 | 182,358,834,628 | 1.48 | 122,794,704,261 | 764.5 |
| `28` | 84.27 | 1.887 | 0.007 | 636,227,762 | 374,865,960 | 58.92 | 69,319,033 | 27,396,950 | 39.53 | 182,372,607,654 | 1.48 | 123,508,860,927 | 768.9 |
| `29` | 84.27 | 1.885 | 0.002 | 634,242,118 | 373,129,821 | 58.83 | 71,095,338 | 27,444,361 | 38.62 | 182,393,516,867 | 1.47 | 123,758,414,753 | 770.5 |
| `30` | 84.27 | 1.880 | 0.011 | 634,313,776 | 374,499,290 | 59.04 | 68,384,494 | 27,376,673 | 40.03 | 182,329,080,165 | 1.49 | 122,987,044,575 | 765.7 |
| `31` | 84.27 | 1.876 | 0.007 | 635,628,834 | 374,312,501 | 58.89 | 70,442,592 | 27,383,819 | 38.95 | 182,336,150,774 | 1.48 | 123,025,690,626 | 765.9 |
| `32` | 84.27 | 1.880 | 0.007 | 633,346,127 | 373,280,638 | 58.94 | 69,901,541 | 27,431,777 | 39.25 | 182,334,434,333 | 1.48 | 123,151,257,461 | 766.7 |

### What it shows

**Prefetch works just as well on the smaller database.** stock 2.309 s →
`-B 31` 1.876 s = **−18.8%**, against −20.3% on 32-bit.

That refutes a hypothesis stated before the run: that a smaller table would leave
less latency for prefetch to hide, so the gain would shrink noticeably. It did
not. At 34.9 MB the table is still more than twice the 16 MB L3, so it remains
just as memory-bound. **Prefetch's value tracks whether the working set exceeds
L3 — not by how much.**

**The 24-bit database genuinely reduces memory traffic.** This is the first thing
measured in this project that moves `cache-misses` at all:

| | 32-bit | 24-bit | change |
|---|---:|---:|---|
| stock `cache-misses` | 454.9 M | **430.7 M** | −5.3% |
| stock `cm%` | 62.24% | **58.95%** | −3.3 pp |
| stock `LLC-ld-miss` | 152.5 M | **136.4 M** | −10.5% |
| best `cache-misses` | 399.4 M | **373.3 M** | −6.5% |

Prefetching never moved `cm%` because it re-routes traffic rather than removing
it. A smaller table removes it. That is the whole distinction.

**But the saving is handed straight back in instructions.** 163.7 G vs 158.0 G at
stock, 182.3 G vs 176.0 G at the best setting — about **+3.6%**, all of it from
unaligned 3-byte cell access. The two databases therefore finish within 5 ms of
each other (1.876 s vs 1.871 s) despite 24-bit doing measurably less memory work.

### The implication

The 24-bit database demonstrates the only mechanism that actually reduces the
miss rate — **make the table smaller** — and also why narrowing the *cell* is the
wrong way to do it. The memory win is real and the instruction cost cancels it.

That is the argument for `-M` subsampling instead: it shrinks the table by
sampling fewer minimizers while keeping the 4-byte naturally-aligned cell, so it
should capture the memory saving without paying the unaligned-access tax. It was
measured at **−26.7%** standalone and has still never been tested together
with `-B`.

## 14. A third workload — `merged_fast.fastq` (6047 Mbp)

Both sweeps above use pod5_2 (499.98 Mbp, HAC basecall). This one repeats them on
a file **12× larger**, to test whether the result holds at scale and on a
different basecall model.

| | pod5_2 | merged_fast |
|---|---:|---:|
| reads | 151,591 | **1,871,478** |
| bases | 499.98 Mbp | **6047.42 Mbp** |
| file size | ~1 GB | **12.5 GB** |
| basecall model | HAC | **FAST** |
| `clsfd%` | 84.26 | **78.66** |

The two datasets are **not comparable to each other** — different basecall model,
hence the different classification rate. Only the `-B` sweep within each is.

### Protocol

Same six perf events, `-p 16 -g 2 -T 0`. Three consecutive runs per
configuration, then a **page-cache flush** of the fastq and all three `.k2d`
files (`scripts/drop_file_cache.py`), then 180 s idle. 33 configurations × 3 runs
× 2 databases = **198 runs**, ~5 h. Crashed runs were detected by the absence of
`processed in` and re-run; no crashed run enters an average.

The flush was added deliberately so run 1 of each group starts from cold page
cache — modelling a first run rather than a re-run.

`run1` below is that post-flush run; `run2-3` is the mean of the two warm ones.

Raw perf output: `result/merged_32bit/perf/` and `result/merged_24bit/perf/`
(99 files each). Plain-text tables: `TABLE.txt` in each directory.

### Results — 32-bit (`eskape_32bit_fork`)

| `-B` | clsfd% | elapsed | sd | run1 | run2-3 | cache-refs | cache-misses | cm% | LLC-loads | LLC-ld-miss | llc% | instructions | IPC | crash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **stock** | 78.66 | 33.604 | 1.162 | 32.285 | 34.263 | 9,967,936,475 | 6,370,956,580 | 63.91 | 3,240,763,676 | 1,882,367,304 | 58.08 | 1,860,376,759,196 | 1.09 | 0 |
| `1` | 78.66 | 36.682 | 1.590 | 34.851 | 37.597 | 10,089,558,837 | 6,445,400,612 | 63.88 | 1,249,310,187 | 385,253,329 | 30.84 | 2,193,892,317,692 | 1.19 | 0 |
| `2` | 78.66 | 33.859 | 1.556 | 32.066 | 34.755 | 9,967,358,089 | 6,344,742,498 | 63.66 | 1,125,515,516 | 304,150,882 | 27.02 | 2,133,314,421,365 | 1.25 | 0 |
| `3` | 78.66 | 33.081 | 1.259 | 31.657 | 33.794 | 9,670,889,914 | 6,132,185,593 | 63.41 | 1,080,579,279 | 283,275,857 | 26.22 | 2,113,411,530,859 | 1.28 | 1 |
| `4` | 78.66 | 32.084 | 1.228 | 30.679 | 32.786 | 9,302,263,303 | 5,878,415,413 | 63.19 | 1,057,458,576 | 277,997,902 | 26.29 | 2,103,305,861,977 | 1.31 | 0 |
| `5` | 78.66 | 32.193 | 1.186 | 30.835 | 32.873 | 9,036,350,303 | 5,686,843,507 | 62.93 | 1,042,955,839 | 278,553,639 | 26.71 | 2,097,399,227,048 | 1.31 | 0 |
| `6` | 78.66 | 31.696 | 1.210 | 30.311 | 32.389 | 8,905,750,863 | 5,584,439,776 | 62.71 | 1,047,654,555 | 279,292,402 | 26.66 | 2,093,338,290,604 | 1.33 | 0 |
| `7` | 78.66 | 31.405 | 1.376 | 29.841 | 32.187 | 8,799,666,043 | 5,506,742,584 | 62.58 | 1,053,370,705 | 281,902,630 | 26.76 | 2,090,589,038,070 | 1.33 | 0 |
| `8` | 78.66 | 31.226 | 1.304 | 29.725 | 31.977 | 8,703,757,812 | 5,471,663,677 | 62.87 | 1,010,445,953 | 282,442,675 | 27.95 | 2,088,281,630,050 | 1.35 | 0 |
| `9` | 78.66 | 30.894 | 1.414 | 29.282 | 31.700 | 8,695,321,962 | 5,458,213,537 | 62.77 | 1,020,799,358 | 283,383,719 | 27.76 | 2,086,539,723,062 | 1.36 | 0 |
| `10` | 78.66 | 30.785 | 1.303 | 29.285 | 31.535 | 8,680,459,517 | 5,434,020,609 | 62.60 | 1,033,494,171 | 284,324,028 | 27.51 | 2,085,407,966,976 | 1.36 | 0 |
| `11` | 78.66 | 30.451 | 1.517 | 28.710 | 31.321 | 8,645,649,163 | 5,421,339,374 | 62.71 | 1,017,671,662 | 284,768,169 | 27.98 | 2,083,966,740,984 | 1.37 | 0 |
| `12` | 78.66 | 30.366 | 1.375 | 28.786 | 31.155 | 8,606,883,345 | 5,407,138,229 | 62.82 | 1,001,674,742 | 286,304,475 | 28.58 | 2,083,175,146,654 | 1.37 | 0 |
| `13` | 78.66 | 30.247 | 1.375 | 28.668 | 31.036 | 8,631,748,341 | 5,411,977,992 | 62.70 | 1,019,386,944 | 285,337,164 | 27.99 | 2,082,484,392,224 | 1.38 | 0 |
| `14` | 78.66 | 30.108 | 1.454 | 28.437 | 30.943 | 8,595,490,998 | 5,396,900,818 | 62.79 | 1,006,170,303 | 286,465,896 | 28.47 | 2,081,785,271,058 | 1.39 | 0 |
| `15` | 78.66 | 30.126 | 1.335 | 28.591 | 30.893 | 8,603,067,383 | 5,385,849,247 | 62.60 | 1,023,486,386 | 287,297,731 | 28.07 | 2,081,243,697,758 | 1.38 | 0 |
| `16` | 78.66 | 30.187 | 1.567 | 28.386 | 31.088 | 8,586,933,981 | 5,404,982,512 | 62.94 | 1,001,276,263 | 286,808,977 | 28.64 | 2,080,984,074,688 | 1.39 | 1 |
| `17` | 78.66 | 30.013 | 1.426 | 28.368 | 30.835 | 8,576,449,921 | 5,381,002,114 | 62.74 | 1,011,585,905 | 288,113,263 | 28.48 | 2,080,401,837,846 | 1.39 | 0 |
| `18` | 78.66 | 29.827 | 1.681 | 27.918 | 30.782 | 8,546,993,060 | 5,376,681,960 | 62.91 | 992,755,417 | 288,651,598 | 29.08 | 2,079,762,625,720 | 1.40 | 0 |
| `19` | 78.66 | 29.943 | 1.322 | 28.421 | 30.704 | 8,567,972,766 | 5,371,023,890 | 62.69 | 1,013,302,789 | 288,819,885 | 28.50 | 2,079,590,219,388 | 1.40 | 0 |
| `20` | 78.66 | 30.143 | 1.473 | 28.447 | 30.991 | 8,552,500,763 | 5,387,371,603 | 62.99 | 992,281,669 | 288,943,953 | 29.12 | 2,079,502,438,899 | 1.40 | 2 |
| `21` | 78.66 | 29.846 | 1.298 | 28.352 | 30.593 | 8,552,446,065 | 5,359,230,105 | 62.66 | 1,015,307,867 | 289,088,056 | 28.47 | 2,078,888,895,770 | 1.40 | 0 |
| `22` | 78.66 | 29.740 | 1.372 | 28.168 | 30.526 | 8,548,332,756 | 5,361,976,417 | 62.73 | 1,007,684,132 | 289,460,010 | 28.73 | 2,078,677,792,865 | 1.40 | 0 |
| `23` | 78.66 | 29.818 | 1.487 | 28.125 | 30.665 | 8,564,141,948 | 5,365,276,569 | 62.65 | 1,027,037,779 | 289,843,759 | 28.22 | 2,078,698,237,461 | 1.40 | 0 |
| `24` | 78.66 | 29.965 | 1.650 | 28.150 | 30.872 | 8,530,625,592 | 5,355,584,752 | 62.78 | 1,001,378,990 | 289,908,039 | 28.95 | 2,078,335,501,793 | 1.40 | 0 |
| `25` | 78.66 | 29.626 | 1.441 | 27.972 | 30.453 | 8,528,273,009 | 5,347,337,221 | 62.70 | 1,008,453,645 | 290,239,337 | 28.78 | 2,077,907,325,667 | 1.41 | 0 |
| `26` | 78.66 | 29.566 | 1.552 | 27.780 | 30.459 | 8,535,006,348 | 5,344,308,596 | 62.62 | 1,018,496,956 | 291,116,665 | 28.58 | 2,077,792,948,798 | 1.41 | 0 |
| `27` | 78.66 | 29.685 | 1.332 | 28.166 | 30.444 | 8,549,102,749 | 5,343,550,273 | 62.50 | 1,035,537,792 | 291,243,958 | 28.12 | 2,077,785,183,840 | 1.41 | 0 |
| `28` | 78.66 | 29.675 | 1.438 | 28.024 | 30.501 | 8,516,856,440 | 5,336,771,232 | 62.66 | 1,013,396,773 | 291,103,099 | 28.73 | 2,077,251,959,834 | 1.41 | 0 |
| `29` | 78.66 | 29.676 | 1.583 | 27.859 | 30.585 | 8,508,273,187 | 5,335,939,629 | 62.71 | 1,008,911,087 | 291,834,777 | 28.93 | 2,077,211,950,267 | 1.41 | 0 |
| `30` | 78.66 | 29.663 | 1.404 | 28.069 | 30.460 | 8,495,255,692 | 5,331,714,924 | 62.76 | 1,001,319,403 | 291,824,374 | 29.14 | 2,077,043,777,580 | 1.41 | 0 |
| `31` | 78.66 | 29.571 | 1.358 | 28.013 | 30.351 | 8,513,452,028 | 5,328,250,046 | 62.59 | 1,019,038,430 | 292,242,509 | 28.68 | 2,076,974,877,804 | 1.41 | 0 |
| `32` | 78.66 | 29.801 | 1.262 | 28.349 | 30.527 | 8,515,705,926 | 5,345,265,346 | 62.77 | 1,013,526,318 | 292,885,466 | 28.90 | 2,077,264,313,055 | 1.41 | 0 |

### Results — 24-bit (`eskape_24bit`)

| `-B` | clsfd% | elapsed | sd | run1 | run2-3 | cache-refs | cache-misses | cm% | LLC-loads | LLC-ld-miss | llc% | instructions | IPC | crash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **stock** | 78.69 | 33.353 | 1.250 | 31.927 | 34.066 | 9,530,803,070 | 5,689,422,305 | 59.70 | 2,958,936,072 | 1,645,878,255 | 55.62 | 1,957,146,614,274 | 1.15 | 0 |
| `1` | 78.69 | 36.502 | 1.249 | 35.063 | 37.222 | 9,659,116,847 | 5,744,550,906 | 59.47 | 1,005,529,965 | 340,688,220 | 33.88 | 2,297,220,932,745 | 1.25 | 1 |
| `2` | 78.69 | 34.060 | 1.075 | 32.831 | 34.675 | 9,562,263,222 | 5,684,846,983 | 59.45 | 944,195,782 | 300,754,627 | 31.85 | 2,236,900,533,347 | 1.31 | 1 |
| `3` | 78.69 | 32.907 | 1.232 | 31.491 | 33.615 | 9,292,773,214 | 5,539,604,985 | 59.61 | 909,707,961 | 292,693,371 | 32.17 | 2,216,462,709,568 | 1.34 | 0 |
| `4` | 78.69 | 32.279 | 1.204 | 30.908 | 32.964 | 8,969,935,978 | 5,344,544,138 | 59.58 | 893,799,820 | 293,665,529 | 32.86 | 2,206,288,140,765 | 1.37 | 0 |
| `5` | 78.69 | 32.472 | 1.198 | 31.096 | 33.160 | 8,740,260,122 | 5,199,585,925 | 59.49 | 896,870,465 | 297,222,592 | 33.14 | 2,200,547,320,199 | 1.36 | 0 |
| `6` | 78.69 | 31.973 | 1.179 | 30.623 | 32.648 | 8,601,746,907 | 5,111,998,357 | 59.43 | 886,317,221 | 299,203,185 | 33.76 | 2,196,489,506,017 | 1.38 | 0 |
| `7` | 78.69 | 31.863 | 1.066 | 30.663 | 32.463 | 8,507,699,790 | 5,046,246,565 | 59.31 | 885,157,468 | 302,202,027 | 34.14 | 2,193,544,236,369 | 1.39 | 0 |
| `8` | 78.69 | 31.543 | 1.122 | 30.248 | 32.190 | 8,445,310,533 | 5,019,166,211 | 59.43 | 865,979,545 | 303,137,123 | 35.01 | 2,191,387,589,159 | 1.40 | 0 |
| `9` | 78.69 | 31.184 | 1.314 | 29.690 | 31.931 | 8,430,357,670 | 5,005,496,496 | 59.37 | 878,295,415 | 304,254,410 | 34.64 | 2,189,522,279,279 | 1.41 | 0 |
| `10` | 78.69 | 30.912 | 1.427 | 29.278 | 31.729 | 8,411,838,597 | 4,996,442,762 | 59.40 | 876,348,050 | 305,342,338 | 34.84 | 2,188,306,847,760 | 1.42 | 0 |
| `11` | 78.69 | 30.805 | 1.418 | 29.170 | 31.623 | 8,387,402,919 | 4,987,932,597 | 59.47 | 863,825,771 | 306,256,767 | 35.45 | 2,187,011,427,668 | 1.43 | 0 |
| `12` | 78.69 | 30.641 | 1.353 | 29.098 | 31.413 | 8,379,991,502 | 4,981,030,899 | 59.44 | 874,295,098 | 306,626,876 | 35.07 | 2,186,240,128,025 | 1.43 | 0 |
| `13` | 78.69 | 30.528 | 1.438 | 28.876 | 31.355 | 8,360,582,527 | 4,969,745,243 | 59.44 | 867,084,366 | 307,901,211 | 35.51 | 2,185,408,102,847 | 1.43 | 0 |
| `14` | 78.69 | 30.463 | 1.404 | 28.855 | 31.267 | 8,378,174,839 | 4,968,423,464 | 59.30 | 888,574,061 | 308,305,622 | 34.70 | 2,184,693,957,816 | 1.44 | 0 |
| `15` | 78.69 | 30.626 | 1.238 | 29.200 | 31.340 | 8,338,043,800 | 4,953,808,775 | 59.41 | 865,066,666 | 309,255,826 | 35.75 | 2,184,325,993,643 | 1.43 | 0 |
| `16` | 78.69 | 30.267 | 1.469 | 28.579 | 31.111 | 8,357,174,459 | 4,962,790,968 | 59.38 | 882,668,135 | 308,766,319 | 34.98 | 2,183,632,400,520 | 1.45 | 1 |
| `17` | 78.69 | 30.209 | 1.358 | 28.652 | 30.988 | 8,330,642,999 | 4,956,696,120 | 59.50 | 859,063,516 | 309,389,185 | 36.01 | 2,183,060,468,568 | 1.45 | 0 |
| `18` | 78.69 | 30.507 | 1.652 | 28.713 | 31.404 | 8,314,627,722 | 4,953,579,856 | 59.58 | 854,648,723 | 310,215,881 | 36.30 | 2,182,712,868,455 | 1.44 | 1 |
| `19` | 78.69 | 30.077 | 1.367 | 28.508 | 30.861 | 8,314,626,636 | 4,954,208,922 | 59.58 | 854,257,322 | 310,884,709 | 36.39 | 2,182,416,846,480 | 1.46 | 0 |
| `20` | 78.69 | 30.261 | 1.327 | 28.740 | 31.022 | 8,322,315,578 | 4,943,068,039 | 59.40 | 873,027,644 | 310,786,914 | 35.60 | 2,182,399,571,397 | 1.45 | 0 |
| `21` | 78.69 | 30.602 | 0.916 | 29.679 | 31.064 | 8,328,567,862 | 4,944,395,838 | 59.37 | 880,121,678 | 310,945,872 | 35.33 | 2,181,787,851,405 | 1.44 | 0 |
| `22` | 78.69 | 30.002 | 1.429 | 28.354 | 30.827 | 8,311,737,371 | 4,942,260,932 | 59.46 | 872,480,198 | 312,548,078 | 35.82 | 2,181,581,731,684 | 1.46 | 0 |
| `23` | 78.69 | 30.168 | 1.125 | 28.890 | 30.807 | 8,294,109,749 | 4,933,133,763 | 59.48 | 863,582,773 | 312,423,717 | 36.18 | 2,181,847,480,223 | 1.45 | 0 |
| `24` | 78.69 | 30.003 | 1.358 | 28.444 | 30.783 | 8,286,969,688 | 4,934,228,462 | 59.54 | 855,119,541 | 313,037,956 | 36.61 | 2,181,124,027,889 | 1.46 | 0 |
| `25` | 78.69 | 29.965 | 1.634 | 28.108 | 30.893 | 8,282,619,360 | 4,931,316,587 | 59.54 | 856,943,281 | 314,178,258 | 36.66 | 2,180,867,736,965 | 1.46 | 0 |
| `26` | 78.69 | 29.902 | 1.486 | 28.198 | 30.754 | 8,315,852,526 | 4,930,258,929 | 59.29 | 890,687,568 | 313,608,210 | 35.21 | 2,180,736,846,483 | 1.46 | 0 |
| `27` | 78.69 | 29.916 | 1.360 | 28.356 | 30.696 | 8,330,698,526 | 4,930,321,057 | 59.18 | 908,013,320 | 313,890,115 | 34.57 | 2,180,511,849,985 | 1.46 | 0 |
| `28` | 78.69 | 29.907 | 1.508 | 28.167 | 30.777 | 8,298,069,499 | 4,927,744,497 | 59.38 | 876,043,188 | 314,865,459 | 35.94 | 2,180,317,279,273 | 1.46 | 0 |
| `29` | 78.69 | 29.809 | 1.367 | 28.239 | 30.595 | 8,272,614,551 | 4,921,445,216 | 59.49 | 866,420,329 | 314,694,666 | 36.32 | 2,180,220,564,792 | 1.46 | 0 |
| `30` | 78.69 | 29.724 | 1.604 | 27.875 | 30.649 | 8,281,167,706 | 4,922,778,037 | 59.45 | 868,269,015 | 315,689,694 | 36.36 | 2,180,155,228,170 | 1.46 | 0 |
| `31` | 78.69 | 29.590 | 1.844 | 27.464 | 30.654 | 8,283,863,161 | 4,922,387,893 | 59.42 | 882,993,335 | 316,810,374 | 35.88 | 2,180,116,798,827 | 1.46 | 0 |
| `32` | 78.69 | 29.654 | 1.755 | 27.653 | 30.655 | 8,262,914,045 | 4,912,734,013 | 59.46 | 870,086,060 | 316,655,850 | 36.39 | 2,179,863,550,084 | 1.46 | 0 |

### What it shows

**Prefetch holds up at scale, but the headline number is smaller.**

| | best `-B` | stock | best | change |
|---|---|---:|---:|---:|
| 32-bit | `31` | 33.604 | 29.571 | **−12.0%** |
| 24-bit | `31` | 33.353 | 29.590 | **−11.3%** |
| 32-bit, run 1 only | `31` | 32.285 | 28.013 | −13.2% |
| 24-bit, run 1 only | `31` | 31.927 | 27.464 | −14.0% |

**−12% here against −20% on pod5_2 — and the gap is not prefetch working less
well.** The memory counters improve by the same proportions as before:

| | stock | `-B 31` | change | pod5_2 equivalent |
|---|---:|---:|---:|---:|
| `LLC-ld-miss` | 1,882 M | 292 M | **−84.5%** | −83% |
| `cache-misses` | 6,371 M | 5,328 M | −16.4% | −12% |
| IPC | 1.09 | 1.41 | +29% | +38% |

What changed is the **denominator**. At 12.5 GB, reading the input and writing
output occupy a much larger share of runtime, and prefetch cannot touch that.
Same engine improvement, larger vehicle.

> Stated as the leading explanation, not a settled one. Confirming it requires
> measuring the I/O time separately, which this sweep does not do.

**`-B 1` costs +9.2%** (33.604 → 36.682), consistent with the +5.4% seen on
pod5_2 — the batching overhead is real and paid before anything is won.

**The knee is around `-B 10–15`, with a long flat tail.** 33.604 → 32.084 (B=4)
→ 31.226 (B=8) → 30.187 (B=16) → 29.571 (B=31). Everything from 22 to 32 sits
within 0.4 s, i.e. within the run-to-run spread.

### Read the `run1`/`run2-3` split, not `sd`

The `sd` column here is 0.9–1.8 s, far above the 0.004–0.021 s of the cooldown
sweeps. **That is not noise.** Run 1 is faster than runs 2–3 by a consistent
~2.4 s on **every one of the 66 rows**. Pooling all three inflates the spread and
hides a clean signal; both columns rank the configurations identically.

**This reverses a prediction made before the run.** The expectation was that
run 1 would be *slower*, having to re-read 11.7 GB from disk after the flush. It
is reliably the **fastest** of the three. The 180 s idle sits immediately before
run 1, so thermal recovery outweighs the cold-cache penalty: on this box the heat
costs more than the flush does.

That is worth carrying forward — **a "warm cache" run on this machine is not the
fast case.** A cool CPU matters more than a warm page cache.

### `cm%` is flat, again

62.5–63.9% across all 33 32-bit rows; 59.2–59.7% across all 33 24-bit rows.
Third independent confirmation of §15: prefetch re-routes memory traffic rather
than removing it, so the honest ratio does not move. `llc%` meanwhile falls
58.08% → 28.68%, which continues to be the misleading column.

The 24-bit database again shows genuinely lower `cache-misses` (5,689 M vs
6,371 M at stock, −10.7%) and again hands the saving back in instructions
(1,957 G vs 1,860 G, +5.2%). The two databases finish **within 0.02 s of each
other**, exactly as on pod5_2.

### Crashes

**8 aborts in 206 attempts (3.9%)**, every one succeeding on retry.

| database | crashed at |
|---|---|
| 32-bit | `-B 3`, `-B 16`, `-B 20` (×2) |
| 24-bit | `-B 1`, `-B 2`, `-B 16`, `-B 18` |

Stock was clean in all 6 attempts in this sweep — but **stock crashed in an
earlier, discarded run of the same sweep**, and `-B 1` (which is the stock code
path) crashed here. So nothing yet attributes these to batching.

**No diagnosis is possible from this data.** The retry loop reopened each output
file with `>`, overwriting the failed attempt's stderr before it could be read;
`dmesg` logged nothing and no coredumps were configured. There is a count and
nothing else. Settling it needs per-attempt log files, recorded exit codes
(139 = SIGSEGV vs 134 = abort separates the hypotheses immediately), coredumps
enabled, and ~200 repeats at a fixed configuration.

## 15. The counter observation: `cache-misses` vs `LLC-load-misses`

Read across the table and the two miss counters tell opposite stories.

| | stock | `-B 30` | change |
|---|---:|---:|---|
| `cache-refs` | 730.9 M | 651.6 M | −11% |
| **`cache-misses`** (all L3 misses) | **454.9 M** | **399.4 M** | **−12%** |
| `cm%` | 62.24% | 61.30% | −0.9 pp |
| `LLC-loads` (demand loads reaching L3) | 255.9 M | 81.2 M | **−68%** |
| **`LLC-load-misses`** (demand only) | **152.5 M** | **25.2 M** | **−83%** |
| `llc%` | 59.58% | 31.07% | −28.5 pp |

### Why they disagree

Prefetching does not remove a trip to memory. It changes **which instruction
makes it**.

Stock — the demand load makes the trip:

```
demand load → miss L1 → miss L2 → miss L3 → DRAM
                                   counted by: LLC-load, LLC-load-miss,
                                               cache-reference, cache-miss
```

With `-B` — the prefetch makes it, and the load arrives later to find the line
already there:

```
prefetch    → miss L1 → miss L2 → miss L3 → DRAM   (line lands in cache)
                                   counted by: cache-reference, cache-miss
                                   NOT an LLC-load (not a demand load)
...
demand load → HIT in L1/L2 → done
                                   never reaches L3, counted by nothing there
```

Same single DRAM access. But the demand-load counters no longer see it.

### Which to believe

**`cache-misses`.** It counts every L3 miss regardless of which instruction
caused it, so it measures actual memory traffic. It says traffic fell **12%** —
and prefetch was never meant to reduce traffic at all, so even that is a bonus.
The likeliest cause is better line reuse: 30 minimizers resolved together are
more likely to share a 64-byte line than 30 resolved seconds apart.

**`llc%` is the trap.** Dropping 59.58% → 31.07% looks like the cache behaviour
halved in badness. It did not. The numerator was re-attributed from demand loads
to prefetches while the denominator shrank alongside it. Nothing about the memory
system improved by that margin.

Note `cm%` barely moves — 62.24% → 61.30%. Because both its numerator and
denominator count all traffic it is stable, and **its stability is the real
signal: the memory system is doing the same work throughout.**

### The same trap, mirrored, in the lookaside cache

Worth recording because it is the same column misleading in the opposite
direction. The lookaside cache also drove `llc%` down — 58.81% → ~37% — but there
the mechanism was **denominator inflation**: every cache probe was itself an L3
access that mostly hit, adding ~160 M LLC-loads while removing no misses. Real
DRAM traffic went **up** (0.938 → 1.611 accesses per lookup at 16 MB).

So `llc%` fell in both projects. In one, real traffic was unchanged; in the
other, it worsened by 72%.

> **A ratio whose denominator the code controls is not a performance metric.**
> Absolute counts — `cache-misses`, or misses per lookup — are what should be
> quoted.

---

# Part VI — Practical

## 16. Usage

```bash
cd /home/dell/summer
D=databases/eskape_32bit_fork

scratch_lookaside/bin/classify_prefetch \
    -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0 \
    -B 29 \
    perpod5/pod5_2.fastq > /dev/null
```

`-B 1` is the stock path. **Useful range is 16–32**; maximum is 64 (`PF_MAX`).
Off by default, so the binary behaves exactly like stock unless `-B` is given.

## 17. Limits of this measurement

- **Two input files.** pod5_2 (499.98 Mbp, HAC) in §12–13 and merged_fast
  (6047.42 Mbp, FAST) in §14. **The gain differs between them — −20% and −12%** —
  so no single figure describes `-B`; the workload's I/O share matters. The other
  14 pod5 files are verified for correctness but untimed.
- **Two databases.** `eskape_32bit_fork` and `eskape_24bit`, both on both files.
  They finish within 0.02 s of each other every time. The 16- and 20-bit
  databases are untested with `-B`.
- **One machine.** i7-11700, 8 cores / 16 threads, 16 MB L3, `powersave`
  governor. This box is bimodal: the same binary measured 1.850 s and 2.898 s in
  one batch of 20 runs while executing instruction counts within 0.09% of each
  other. The cooldown protocol (§11) controls for it; the `sd` column is how to
  check it worked.
- **Not merged.** `kraken2_bin/` and `kraken2/src/` are untouched. This lives in
  `scratch_lookaside/`.
- **Intermittent crashes, cause unknown (§14).** On merged_fast, 8 of 206
  attempts (3.9%) abort and succeed on retry. Stock and `-B 1` both crashed, so
  nothing currently implicates batching — but no stderr, signal or stack was
  preserved for any of them. Unresolved.

## 18. What to try next

1. **Huge pages.** Now that prefetch removed the data stall, address translation
   dominates: page-walk-outstanding is 54.9% of cycles at `-B 29`, and walks
   completed are *unchanged* at 150 M. `hash.k2d` is 11,914 4 KB pages against a
   2,048-entry STLB; in 2 MB pages it is **24 pages**. Costs one `madvise()` and
   cannot change results.
2. **Combine with `-M 4000000`** (measured −26.7% standalone). Prefetch overlaps
   latency, `-M` removes accesses by making the database L3-resident — different
   costs, so they should compose. Costs 1.3 pp sensitivity.
3. **Trim the 17% instruction overhead.** `PfSlot` is 24 bytes; packing `amb`
   into a spare bit of `hc` makes it 16. The array is stack-allocated per frame
   and could be hoisted.
4. **Separate I/O from compute time.** §14 shows the gain falling from −20% to
   −12% on a 12.5 GB input while every memory counter improves identically. The
   explanation — that I/O dilutes the share prefetch can address — is inferred,
   not measured, and should be confirmed.
5. **Settle the crashes.** Per-attempt logs, exit codes, coredumps, ~200 repeats
   at one configuration.
