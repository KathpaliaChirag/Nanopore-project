# Software prefetch for kraken2 (`-B`)

**A 12% speedup with byte-identical output.** The classifier's inner loop now
looks up minimizers in batches, starting several memory fetches before waiting
for any of them.

Binary: `scratch_lookaside/bin/classify_prefetch`
Measurements: `result/prefetch/` (99 raw perf files + `TABLE.txt`)

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

**Protocol.** Earlier sweeps interleaved repetitions to average out machine
drift. That was not enough: on this box the same binary measured 1.850 s and
2.898 s in the same batch of 20 runs while executing an *identical* instruction
count (176.05-176.20 G, a 0.09% spread). The work is perfectly reproducible;
only the clock is not.

These figures use a **cooldown protocol** instead: three consecutive runs per
configuration, then 240 seconds idle before the next. That equalises machine
state at the start of every group. Package temperature held **59-65 C across all
33 groups**, and the resulting standard deviations are **0.004-0.021 s**, against
up to 0.32 s in the interleaved sweeps. **0 crashes in 99 runs.**

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
Plain-text copy of this table: `result/prefetch/TABLE.txt`.

### What the numbers say

**The result never changes.** `clsfd%` is 84.26 on every row.

**stock 2.349 s -> `-B 30` at 1.871 s = -20.34%.** With the noise removed this is
nearly double the -11.8% measured under the interleaved protocol. The earlier
figures were not wrong; they were measured through 10-15% of noise that was
hiding most of the effect.

**`-B 1` costs +5.37%** (sd 0.010, so this is now a reliable figure). It runs the
identical algorithm to stock but executes 185.7 G instructions against 158.0 G --
17.6% more. That is the batching machinery itself, and every batch size pays it
before it can win anything.

**The curve descends smoothly to about `-B 20`, then flattens**: 2.475 -> 2.131
(B=4) -> 1.992 (B=8) -> 1.913 (B=16) -> 1.885 (B=20) -> 1.871 (B=30). Beyond 20
the gain is under 1%. Earlier sweeps appeared to show the knee at 4 because noise
swamped everything past it.

**Instructions fall as the batch grows** (185.7 G at B=1 to 176.0 G at B=32)
while IPC rises 1.04 -> 1.45. Larger batches amortise the per-batch loop
overhead, so they are both cheaper and better pipelined.

### The counter observation: `cache-misses` vs `LLC-load-misses`

Read across the table and the two miss counters tell opposite stories.

| | stock | `-B 30` | change |
|---|---:|---:|---|
| `cache-refs` | 730.9 M | 651.6 M | −11% |
| **`cache-misses`** (all L3 misses) | **454.9 M** | **399.4 M** | **−12%** |
| `cm%` | 62.24% | 61.30% | −0.9 pp |
| `LLC-loads` (demand loads reaching L3) | 255.9 M | 81.2 M | **−68%** |
| **`LLC-load-misses`** (demand only) | **152.5 M** | **25.2 M** | **−83%** |
| `llc%` | 59.58% | 31.07% | −28.5 pp |

#### Why they disagree

Prefetching does not remove a trip to memory. It changes **which instruction
makes it**.

Stock — the demand load makes the trip:

```
demand load -> miss L1 -> miss L2 -> miss L3 -> DRAM
                                      counted by: LLC-load, LLC-load-miss,
                                                  cache-reference, cache-miss
```

With `-B` — the prefetch makes it, and the load arrives later to find the line
already there:

```
prefetch    -> miss L1 -> miss L2 -> miss L3 -> DRAM   (line lands in cache)
                                      counted by: cache-reference, cache-miss
                                      NOT counted as an LLC-load (not a demand load)
...
demand load -> HIT in L1/L2 -> done
                                      never reaches L3, counted by nothing there
```

Same single DRAM access. But the demand-load counters no longer see it.

#### Which to believe

**`cache-misses`.** It counts every L3 miss regardless of which instruction
caused it, so it measures actual memory traffic. It says traffic fell **12%** —
and prefetch was never meant to reduce traffic at all, so even that is a bonus.
The likeliest cause is better line reuse: 30 minimizers resolved together are
more likely to share a 64-byte line than 30 resolved seconds apart.

**`llc%` is the trap.** Dropping 59.58% → 31.07% looks like the cache behaviour
halved in badness. It did not. The numerator was re-attributed from demand loads
to prefetches while the denominator shrank alongside it. Nothing about the
memory system improved by that margin.

Note `cm%` barely moves — 62.24% → 61.30%. Because both its numerator and
denominator count all traffic, it is stable, and its stability is the real signal:
**the memory system is doing the same work throughout.**

#### The same trap, mirrored, in the lookaside cache

Worth recording because it is the same column misleading in the opposite
direction. The lookaside cache also drove `llc%` down — 58.81% → ~37% — but there
the mechanism was **denominator inflation**: every cache probe was itself an L3
access that mostly hit, adding ~160 M LLC-loads while removing no misses. Real
DRAM traffic went **up** (0.938 → 1.611 accesses per lookup at 16 MB).

So `llc%` fell in both projects. In one, real traffic was unchanged; in the
other, it worsened by 72%. **A ratio whose denominator the code controls is not a
performance metric.** Absolute counts — `cache-misses`, or misses per lookup —
are what should be quoted.

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
