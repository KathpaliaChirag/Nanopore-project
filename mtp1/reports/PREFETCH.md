# Software prefetch for kraken2 (`-B`)

**A 12% speedup with byte-identical output.** The classifier's inner loop now
looks up minimizers in batches, starting several memory fetches before waiting
for any of them.

Binary: `scratch_lookaside/bin/classify_prefetch`
Measurements: `../results/prefetch/` (99 raw perf files + `TABLE.txt`)

---

## 1. The problem

`perf` says `CompactHashTable::Get` is where the time goes. But *why* it is slow
matters, because it decides what can fix it.

| measured on pod5_2, 16 threads | |
|---|---:|
| cycles per lookup | 868 |
| DRAM accesses per lookup | 0.938 |
| DRAM latency | ~200 cycles |
| latency exposed per lookup | ~187 cycles (**21% of runtime**) |
| **memory-level parallelism** | **1.24** |
| what the core can sustain | **~12** |

The last two lines are the finding. The processor can have about a dozen memory
requests outstanding at once. This loop has **1.24**. Every fetch is waited out
in full before the next one starts.

That is not a property of the hash table — it is a property of the *loop*:

```c
while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {
  ...
  taxon = hash->Get(*minimizer_ptr);    // <-- blocks ~200 cycles
  ...                                   //     then we fetch the NEXT minimizer
}
```

Each iteration asks for one answer and needs it immediately. There is no
opportunity for the hardware to overlap anything.

## 2. The idea

Prefetching does **not** avoid a single memory access. It **overlaps** them.

Four minimizers, stock:

```
A - hash - load ########  200cy - use A
                                  B - hash - load ########  200cy - use B
                                                            C - ...
                                       total ~ 800 cycles of waiting
```

Four minimizers, batched:

```
PASS 1   hash A -> prefetch  ########
         hash B -> prefetch   ########     four fetches
         hash C -> prefetch    ########    in flight at once
         hash D -> prefetch     ########
PASS 2   use A - use B - use C - use D
                                       total ~ 200 cycles of waiting
```

Same four accesses, same order of results. They just no longer queue behind each
other.

**Why two passes are necessary.** `__builtin_prefetch` does not deliver data
instantly — it *starts* a fetch that still takes ~200 cycles. Prefetching a
minimizer and immediately using it would wait exactly as long as before. The
batch exists to give the fetches time to land: while pass 1 is busy hashing B, C
and D, A's cache line is already on its way.

## 3. The code

Three files. The hash table gains two entry points; the loop is split in half.

### `kv_store.h` (+5)

```c
virtual hvalue_t GetWithHash(hkey_t key, uint64_t hc) const = 0;
virtual void     Prefetch(uint64_t hc) const = 0;
```

### `compact_hash.h` (+10)

```c
hvalue_t CompactHashTable<Cell>::Get(hkey_t key) const {
  return GetWithHash(key, MurmurHash3(key));      // Get is now a wrapper
}

template<typename Cell>
void CompactHashTable<Cell>::Prefetch(uint64_t hc) const {
  __builtin_prefetch(&table_[hc % capacity_], 0, 3);
}
```

`0` = prepare for read, `3` = high temporal locality (keep in all levels).
The instruction issues the load and returns immediately.

Splitting `Get()` into `Get()` and `GetWithHash()` lets the caller compute the
hash once and hand it to both the prefetch and the lookup. Stock hashes twice
per minimizer — once for the `-M` check, once inside `Get()`.

### `classify.cc` — the loop, cut in half at the stall

Everything **before** the blocking load becomes pass 1; everything **after** it
becomes pass 2, unchanged.

```c
while (! frame_done) {

  // ---- PASS 1: scan, hash, fire the fetches, never wait ----
  int n_pf = 0;
  while (n_pf < la_batch) {
    minimizer_ptr = scanner.NextMinimizer();
    if (minimizer_ptr == nullptr) { frame_done = true; break; }
    pf[n_pf].min = *minimizer_ptr;
    pf[n_pf].amb = scanner.is_ambiguous();     // captured, see below
    if (! pf[n_pf].amb) {
      pf[n_pf].hc = MurmurHash3(pf[n_pf].min); // hashed once
      hash->Prefetch(pf[n_pf].hc);             // starts the fetch
    }
    n_pf++;
  }

  // ---- PASS 2: resolve in the original order ----
  for (int pf_i = 0; pf_i < n_pf; pf_i++) {
    // ... stock body, reading pf[pf_i] instead of *minimizer_ptr ...
    taxon = hash->GetWithHash(pf[pf_i].min, pf[pf_i].hc);   // line already here
    // ...
  }
}
```

## 4. Three subtleties the split forced

**`is_ambiguous()` must be captured, not re-asked.** It reports on whichever
minimizer the scanner is currently at. Pass 1 advances the scanner past all B of
them, so asking in pass 2 would give the wrong answer for every entry but the
last. Hence the `amb` field in `PfSlot`.

**`add_kmer(scanner.last_minimizer())` became `add_kmer(pf[pf_i].min)`** for the
same reason. This is only safe because `NextMinimizer()` returns
`&last_minimizer_` (`mmscanner.cc:146,156,188`), making the captured value
identical to what the scanner would report. **If that ever changes upstream,
this line breaks silently** — it is the one place where correctness depends on
an implementation detail of another file.

**A prefetch that turns out to be unnecessary is harmless.** If a minimizer
repeats and the depth-1 skip catches it in pass 2, or if `quick_mode` exits
early, the prefetch was simply wasted work. It cannot produce a wrong answer.

Left untouched on purpose: the depth-1 `last_minimizer`/`last_taxon` skip,
`minimizer_hit_groups++` and its position, `hit_counts`, `taxa.push_back`
ordering, and the `quick_mode` `goto`. An earlier patch in this project moved
that increment and silently changed hit-group counts at frame boundaries.

## 5. Correctness

Output file **and** report compared byte-for-byte against unmodified
`kraken2_bin/classify`:

| | pod5_15 | pod5_2 |
|---|---|---|
| `-B 1`, `-p 1` / `-p 16` | identical | identical |
| `-B 8`, `-p 1` / `-p 16` | identical | identical |
| `-B 16`, `-p 1` / `-p 16` | identical | identical |
| `-B 32`, `-p 1` / `-p 16` | identical | identical |

**16 of 16 exact.** Unlike the lookaside-cache work, there is no accuracy
trade-off here at all — the same lookups happen, in the same order, with the
same results.

## 6. Results

pod5_2.fastq: 151,591 reads, 499.98 Mbp, 160,625,038 lookups.
Database `eskape_32bit_fork` (48.8 MB). `-p 16 -g 2 -T 0`.
Mean of 3 interleaved reps; `sd` is the standard deviation of those 3 times.

| `-B` | clsfd% | elapsed (s) | sd | LLC-loads | LLC-ld-miss | llc% | IPC | DRAM/lookup | ins/lookup | cyc/lookup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **stock** | 84.26 | 2.893 | 0.007 | 258,717,057 | 150,734,517 | 58.26 | 1.13 | 0.938 | 983.6 | 868.5 |
| `1` | 84.26 | 2.908 | 0.288 | 94,469,202 | 29,837,313 | 31.58 | 1.21 | 0.186 | 1156.6 | 954.3 |
| `2` | 84.26 | 2.748 | 0.284 | 88,164,247 | 25,389,678 | 28.80 | 1.26 | 0.158 | 1125.8 | 892.0 |
| `3` | 84.26 | 2.657 | 0.280 | 83,867,494 | 23,237,304 | 27.71 | 1.31 | 0.145 | 1115.3 | 854.0 |
| `4` | 84.26 | 2.572 | 0.284 | 83,284,261 | 22,863,265 | 27.45 | 1.35 | 0.142 | 1110.0 | 821.7 |
| `5` | 84.26 | 2.579 | 0.296 | 80,644,443 | 22,807,542 | 28.28 | 1.36 | 0.142 | 1107.1 | 818.6 |
| `6` | 84.26 | 2.684 | 0.083 | 80,800,087 | 22,565,329 | 27.93 | 1.38 | 0.140 | 1105.1 | 801.3 |
| `8` | 84.26 | 2.678 | 0.020 | 79,616,559 | 22,255,630 | 27.95 | 1.41 | 0.139 | 1102.4 | 782.2 |
| `12` | 84.26 | 2.623 | 0.035 | 80,686,632 | 22,306,938 | 27.65 | 1.45 | 0.139 | 1099.7 | 758.2 |
| `16` | 84.26 | 2.612 | 0.047 | 79,592,032 | 22,438,701 | 28.19 | 1.45 | 0.140 | 1098.7 | 758.1 |
| `20` | 84.26 | 2.578 | 0.017 | 78,149,542 | 22,492,987 | 28.78 | 1.48 | 0.140 | 1097.6 | 743.0 |
| `24` | 84.26 | 2.563 | 0.021 | 80,395,019 | 22,497,725 | 27.98 | 1.48 | 0.140 | 1097.1 | 740.2 |
| `28` | 84.26 | 2.566 | 0.025 | 78,196,314 | 22,569,789 | 28.86 | 1.49 | 0.141 | 1096.8 | 738.8 |
| `29` | 84.26 | 2.553 | 0.006 | 79,200,878 | 22,592,668 | 28.53 | 1.49 | 0.141 | 1096.7 | 736.0 |
| `32` | 84.26 | 2.561 | 0.015 | 80,446,021 | 22,656,315 | 28.16 | 1.49 | 0.141 | 1096.5 | 735.9 |

Full 33 rows: `../results/prefetch/TABLE.txt`.

### What the numbers say

**The result never changes.** `clsfd%` is 84.26 on every row.

**Nearly all of the memory benefit arrives by a batch of four.** DRAM accesses
per lookup fall 0.938 -> 0.186 at `-B 1`, reach 0.142 at `-B 4`, then stay flat.
From 4 to 32 the figure moves by 0.001.

**What improves past 4 is IPC, slowly** — 1.35 at `-B 4` to 1.49 at `-B 29`,
worth roughly another 0.7% of runtime.

**The `sd` column is the one to read.** At `-B` 1-5 the spread across three runs
is 0.28-0.30 s. From `-B 6` onward it collapses to 0.006-0.047. Small batches
are still latency-bound and therefore at the mercy of whatever else the machine
is doing; large batches are steady. `-B 29` gives sd 0.006 — steadier than
stock. This means the attractive times at `-B 4` carry an uncertainty forty
times larger than the rows below them, and should not be quoted alone.

**`-B 1` costs ~17% more instructions than stock** (1156.6 vs 983.6 per lookup)
while doing identical work. That is the buffering machinery itself, and every
batch size pays it. It is why a batch of one is no faster than stock despite
already cutting memory trips by 80%.

**Best measured:** `-B 29` at 2.553 s, **11.77% faster than stock**. Anything
from 16 to 32 is within noise of it and equally steady. The curve is flat by 32
(735.9 vs 736.0 cycles/lookup at 29), so raising the batch limit past 64 would
not help.

### Why instructions go up and time goes down

| | stock | `-B 29` |
|---|---:|---:|
| instructions / lookup | 983.6 | 1096.7 (+11%) |
| cycles / lookup | 868.5 | 736.0 (−15%) |
| IPC | 1.13 | 1.49 (+32%) |

The processor executes **more** work and finishes **sooner**, because it stops
standing still. That is the entire mechanism in one table.

## 7. Usage

```bash
cd /home/dell/summer
D=databases/eskape_32bit_fork

scratch_lookaside/bin/classify_prefetch \
    -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0 \
    -B 29 \
    perpod5/pod5_2.fastq > /dev/null
```

`-B 1` is the stock path. Useful range is 16-32. Maximum is 64 (`PF_MAX`).
Off by default, so the binary behaves exactly like stock unless `-B` is given.

## 8. Limits of this measurement

- **One input file.** All timings are pod5_2. Correctness was checked on
  pod5_15 as well, but the 12% figure is single-file.
- **One database.** `eskape_32bit_fork`, 32-bit cells. The 24-bit database has a
  different memory profile and has not been tested with `-B`.
- **One machine.** i7-11700, 8 cores / 16 threads, 16 MB L3, `powersave`
  governor. This box has shown bimodal timing behaviour; interleaved reps and
  the `sd` column are how that was controlled for.
- **Not merged.** `kraken2_bin/` and `kraken2/src/` are untouched. This lives in
  `scratch_lookaside/`.

## 9. What to try next

1. **Confirm across the other pod5 files** and on the 24-bit database.
2. **Trim the 17% instruction overhead.** If the buffering cost came down, more
   of the 13% improvement over `-B 1` would survive against stock.
3. **Combine with `-M 4000000`** (measured −26.7% on its own). The two attack
   different costs — prefetch overlaps latency, `-M` removes accesses by making
   the database L3-resident — so they should compose.
