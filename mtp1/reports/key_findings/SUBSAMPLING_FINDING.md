# Why the 8 GB database beats the 47 MB one

**Finding: `standard_8gb` is ~1.75× faster than `eskape_32bit_fork` because it
skips 89.62% of its hash-table lookups before touching memory.** The threshold
that causes this is stored inside `opts.k2d` and applied automatically by
`classify`. It is not a command-line option, it was not requested at query time,
and it cannot be turned off.

| | |
|---|---|
| Date | 2026-09-01 |
| Workload | `results/merged_pod5_profiling/merged_fast.fastq` — 1,871,478 reads / 6047.42 Mbp |
| Machine | i7-11700, 8C/16T, 16 MB L3, 31 GB RAM, `powersave` |
| Cause | `-M` subsampling baked into the downloaded database (§7), not anything about its size |
| Skip rate | **89.62%** of hash-table lookups, predicted exactly by `opts.k2d`'s stored threshold (§3, §4) |
| Instrumented build | `scratch_probe/` (`scratch_lookaside/` untouched) |
| Raw data | `result/seedcmp/` (9 perf files + `meta.txt`) |

**Contents**

- **Part I — The anomaly** · §1 the anomaly · §2 method
- **Part II — Where the lookups go** · §3 where the minimizers go
- **Part III — The mechanism** · §4 where the threshold comes from (flag & capacities, build time, query time, why a hash, deriving it, the hash function itself, worked example)
- **Part IV — Cost accounting** · §5 cost model
- **Part V — Context** · §6 two hypotheses this killed · §7 provenance · §8 implications · §9 next step
- **Part VI — Practical** · §10 reproduction · §11 limits

---

# Part I — The anomaly

## 1. The anomaly

A single stock run on each database, same reads, same `-p 16 -g 2 -T 0`:

| database | `hash.k2d` | elapsed | IPC |
|---|---:|---:|---:|
| `eskape_32bit_fork` | 47 MB | 29.919 s | 1.034 |
| `standard_8gb` | 7.6 GB | **17.162 s** | **1.595** |

A database **170× larger** ran in **57% of the time**, at an IPC 54% higher.
That contradicts everything the rest of this project has established about the
memory hierarchy — a 7.6 GB table is 500× the L3, so essentially every lookup it
performs must reach DRAM.

Two explanations were proposed and both turned out to be wrong. They are recorded
in §6 because the way they died is part of the result.

## 2. Method

Hardware counters can show *that* memory work differs, not *why*. So an
instrumented copy of the classifier was built with per-thread counters (no
atomics, no serialisation of the hot loop) at every decision point in the lookup
path:

```
scanned      minimizers emitted by the scanner
ambig        ambiguous spans (no lookup)
dup_skip     depth-1 duplicate skip fired
mhv_skip     minimum_acceptable_hash_value check fired
lookups      GetWithHash() actually entered
probes       iterations of the linear-probing loop
hits         probe found a matching fingerprint
empty_break  probe terminated on an empty cell
```

Two data sources:

- **Counts** — instrumented binary, 200,000-read subset, all three databases,
  scaled to the full file by ×9.357
- **Timing and counters** — stock `kraken2_bin/classify`, full file, three
  **interleaved** rounds per database, page-cache flush + 90 s idle before every
  single run

Interleaving matters. Earlier sweeps in this project ran each configuration as a
consecutive block, which let the box's warm-up masquerade as a treatment effect.
With only three configurations and the comparison between them being the entire
result, round-robin ordering was used so thermal drift hits all three equally.

# Part II — Where the lookups go

## 3. Where the minimizers go

All three databases scan **identically** — same reads, same k=35, ℓ=31:

```
637,052,979  scanned
  −430,567,213  duplicate skip      67.6%   ← IDENTICAL on all three
=  206,485,766  candidates
  −185,041,869  -M skip             89.6%   ← standard_8gb ONLY
=   21,436,003  lookups issued
```

| | fork | spaced | **standard_8gb** |
|---|---:|---:|---:|
| scanned | 637,052,979 | 637,052,979 | 637,052,979 |
| ambiguous | 0 | 0 | 0 |
| duplicate skips | 430,567,213 | 430,575,107 | 430,575,107 |
| **`-M` skips** | **0** | **0** | **185,041,869** |
| **lookups issued** | **206,485,766** | **206,477,872** | **21,436,003** |
| probes | 1,294,068,487 | 1,247,515,042 | 95,381,736 |
| probes / lookup | 6.27 | 6.04 | **4.45** |
| classified (subset) | 78.13% | 80.15% | 81.46% |

The threshold in the file header predicts the skip rate exactly:

```
min_acceptable_hash_value = 0xe5703cec83cdd800 = 89.62% of 2^64
measured                    185,041,869 / 206,477,872 = 89.62%
```

### The two kinds of skip — and which one affects the vote

The tree above contains two different skips. They reduce lookups by similar
amounts but are not the same kind of thing, and conflating them would misread the
whole result.

**Duplicate skip — a depth-1 memoisation. Free, and present on every database.**

```c
if (pf[pf_i].min != last_minimizer) {
  taxon = hash->GetWithHash(...);   // query the table
  last_taxon = taxon;                // remember the answer
  last_minimizer = pf[pf_i].min;
}
else {
  taxon = last_taxon;                // same as previous minimizer: reuse
}
```

It fires only when the **immediately preceding** minimizer was identical — not
"seen anywhere before". That is common because minimizers come from a sliding
window: consecutive windows usually select the same ℓ-mer, so the scanner emits
long runs of one value. Measured here: **430,567,213 / 637,052,979 = 67.6%**.

The table is read-only during classification, so the same minimizer must yield the
same taxon. Reusing the answer is exactly equivalent to querying again.

**Duplicates still vote.** The vote is cast *outside* the branch:

```c
    else {
      taxon = last_taxon;            // duplicate path
    }
    if (taxon) {                     // ← OUTSIDE the if/else
      hit_counts[taxon]++;           // ← EVERY minimizer votes
    }
  }
  taxa.push_back(taxon);             // ← EVERY minimizer recorded
```

`ResolveTree` scores each taxon by summing `hit_counts` over its root-to-leaf
ancestry, takes the maximum, breaks ties by LCA, then walks up the tree until the
confidence threshold is met. Its input is `hit_counts`, which includes every
duplicate. **So the duplicate skip changes the lookup count and nothing else.**

Two counters deliberately *do* exclude duplicates, because they live inside the
`if` branch:

| counter | counts | why |
|---|---|---|
| `hit_counts[taxon]` | **every** minimizer | the vote — abundance should reflect how much of the read matched |
| `minimizer_hit_groups` | **distinct runs** | the `-g` threshold: how many *separate* places matched, so one long run cannot fake several independent hits |
| `add_kmer` (HLL) | **distinct** minimizers | the report's distinct-k-mer estimate |

With `-g 2`, `minimizer_hit_groups` gates whether a read is classified at all, and
it is the one counter that must not see duplicates. This is also why the prefetch
loop split had to preserve minimizer order exactly: `last_minimizer` carries state
across iterations, so reordering would break runs apart differently, shift
`minimizer_hit_groups`, and silently reclassify reads.

**`-M` skip — an approximation. Only on subsampled databases.**

| | duplicate skip | `-M` skip |
|---|---|---|
| present on | **all** databases | only subsampled ones |
| result | **identical** — reuses a known-correct answer | `taxon = 0`, treated as a miss |
| affects the vote? | **no** | **yes** — those minimizers never vote |
| is it an approximation? | no | **yes**, made at build time |

Both remove memory traffic; only `-M` removes information. That the duplicate skip
is identical across all three databases (430.57 M, varying by 0.002%) is what
isolates `-M` as the sole cause of the speed difference.

# Part III — The mechanism

## 4. Where the threshold comes from

### The flag, and the two capacities

```bash
build_db -M 2000000000 ...        # maximum_capacity, in CELLS
```

`kraken2-build --max-db-size 8` converts GB to cells: 8 GB / 4 bytes =
2,000,000,000. Two capacities are in play:

| | | |
|---|---|---|
| `opts.capacity` | what the library **needs** | from `estimate_capacity`, or `-c` |
| `opts.maximum_capacity` | what you will **allow** | from `-M` |

### It is set at build time

`kraken2/src/build_db.cc:78`:

```c
if (opts.maximum_capacity) {                      // only when a CAP is given
  double frac = opts.maximum_capacity * 1.0 / opts.capacity;
  opts.min_clear_hash_value = (uint64_t)((1 - frac) * UINT64_MAX);
  actual_capacity = opts.maximum_capacity;
}
```

`min_clear_hash_value` is initialised to 0 at line 50 and this `if` is its **only
writer in the entire codebase**. A non-zero value therefore proves a maximum
capacity was passed. It is copied to the index options at line 111 and written
into `opts.k2d`.

Reversing it from the file:

```
threshold  = 0xe5703cec83cdd800  →  10.3756% of minimizers kept
capacity   = 2,000,000,000       (8 GB ÷ 4-byte cells)
⇒ uncapped capacity needed = 19,275,968,731 cells  =  71.8 GB
⇒ distinct minimizers in library ≈ 13,504,793,136   (1,517× ESKAPE's 8,903,388)
```

The library needed 71.8 GB and was capped at 8 GB, so kraken2 kept 10.38% of it.

### It is applied at query time, with no flag

`classify.cc:327` loads the options straight from the file, and line 875 uses them
in the inner loop:

```c
IndexOptions idx_opts = index_data.options;      // ← from opts.k2d
...
if (idx_opts.minimum_acceptable_hash_value) {
  if (pf[pf_i].hc < idx_opts.minimum_acceptable_hash_value)
    skip_lookup = true;                          // 185 M times
}
```

**`classify` has no option for this.** Its `-M` is `use_memory_mapping`
(`classify.cc:1174`) — an unrelated flag that happens to share the letter with
`build_db`'s maximum-capacity flag. This name collision is why the behaviour is
invisible from the command line.

### The same test runs at build time

The threshold is not only a query-time filter. `build_db.h:209` applies it while
deciding what to store:

```c
while ((minimizer_ptr = scanner.NextMinimizer())) {
  if (scanner.is_ambiguous())
    continue;
  if (min_clear_hash_value && MurmurHash3(*minimizer_ptr) < min_clear_hash_value)
    continue;                        // <- DISCARDED, never enters the table
  ...
  hash.CompareAndSet(*minimizer_ptr, new_taxid, &existing_taxid);
}
```

and again at `build_db.h:254` in the capacity-estimation pass, so the estimate and
the contents agree. **89.62% of the library was discarded here.**

The build-side and query-side tests are byte-for-byte the same comparison:

```
BUILD:   MurmurHash3(min) <  min_clear_hash_value          -> do not store
QUERY:   MurmurHash3(min) <  minimum_acceptable_hash_value  -> do not look up
```

Same hash function, same operator, same constant — carried between them in
`opts.k2d`.

### Why a hash rather than a random sample

The selection has to be **deterministic** (the same minimizer must get the same
verdict at build time and at query time, months apart, on a different machine),
**stateless** (no list of "which ones I kept" to store or consult), and **uniform**
(an unbiased sample of k-mer space, not clustered).

`MurmurHash3` gives all three, and the hash is *already computed* for the table
index, so the test costs one comparison against a constant. A random sample would
require recording the kept set — which is precisely the thing that did not fit.

### Deriving the threshold

`MurmurHash3` output is uniform over [0, 2^64), so `hash >= T` selects exactly
(2^64 - T)/2^64 of all minimizers. Setting that equal to the fraction that fits:

```
frac = maximum_capacity / capacity = 2,000,000,000 / 19,275,968,731 = 0.103756
T    = (1 - frac) * UINT64_MAX
     = 0.896244 * 18446744073709551615
     = 0xe5703cec83cdd800          <- matches the stored value exactly
```

Verified in both directions: the stored threshold recovers frac = 0.103756, and
frac regenerates the stored threshold bit for bit.

### The skips are correctness, not a shortcut

The table only ever stored minimizers above the threshold. A lookup below it is a
**guaranteed miss** that would still cost a full random DRAM access and a probe
chain to an empty cell. Skipping returns the same answer for free. The build-time
rule and the query-time rule are the same rule; the approximation was made once,
at build time, when 89.6% of the library was discarded.

For a database with threshold 0, the `if` is false and the check is bypassed
entirely — every candidate goes to memory, because every one *might* be present.

### The hash function itself

`kraken2/src/kv_store.h:67` — the whole thing:

```c
uint64_t inline MurmurHash3(hkey_t key) {
  uint64_t k = (uint64_t) key;
  k ^= k >> 33;
  k *= 0xff51afd7ed558ccd;
  k ^= k >> 33;
  k *= 0xc4ceb9fe1a85ec53;
  k ^= k >> 33;
  return k;
}
```

Despite the name this is not full MurmurHash3; it is **`fmix64`, MurmurHash3's
finalizer** (the avalanche step). Kraken2 uses it alone because its input is
already a fixed 64-bit integer, not a byte stream.

**The input is already a number.** An l-mer is 2 bits per base
(`mmscanner.cc:42-45`): `A=00 C=01 G=10 T=11`. A 31-mer is therefore 62 bits:

```
A  C  G  T  T  G  C  A  A  G  G  C ...
00 01 10 11 11 10 01 00 00 10 10 01 ...  =  502,444,362,787,516,835
```

No string hashing happens.

**What each step does:**

| step | purpose |
|---|---|
| `k ^= k >> 33` | mixes the high half into the low half |
| `k *= 0xff51afd7ed558ccd` | multiplication propagates bits **upward** |
| `k ^= k >> 33` | pushes that influence back **downward** |
| `k *= 0xc4ceb9fe1a85ec53` | second, different constant |
| `k ^= k >> 33` | final mix |

Multiplication alone only carries influence upward; XOR-shift only downward.
Alternating them gives every input bit a route to every output bit, and the two
constants were found by search to maximise that spread. **Flipping one base
changes about half the output bits** — that uniformity is what makes "hash >= T"
a fair sample.

**It is a bijection.** XOR-shift and multiplication by an odd constant are both
invertible on 64-bit integers, so this is a *permutation* of the 64-bit space:
distinct minimizers always get distinct hashes, with no collisions at this stage.
(Table collisions arise later, when `hc % capacity_` folds 2^64 values into
12.2 M slots.)

**It is deterministic and stateless.** No seed, no table, no randomness. The same
l-mer gives the same value on any machine, in any year, in `build_db` and in
`classify` alike — which is precisely why the same test can be applied twice and
be guaranteed to agree.

**One hash, three uses:**

```c
uint64_t hc = MurmurHash3(minimizer);

hc < minimum_acceptable_hash_value    // 1. the -M subsampling test
hc % capacity_                        // 2. the table slot
hc >> (64 - key_bits_)                // 3. the stored fingerprint
```

Low bits pick the slot, high bits form the fingerprint — safe only because
avalanche makes all 64 bits equally well mixed. This reuse is also what the
prefetch work exploits: `Get()` recomputed the hash, so splitting it into
`Prefetch(hc)` + `GetWithHash(key, hc)` saved one `MurmurHash3` per minimizer.

### Worked example — real computed values

> An earlier draft of this report used **illustrative** hash values (0.1043,
> 0.4471, ...) invented to show the rule. They are replaced here by values
> computed from the actual `fmix64` implementation and the actual 2-bit encoding.
> The snippet in §10 reproduces them.

```
threshold T = 0xe5703cec83cdd800   (normalised 0.8962)
```

| l-mer (l=31) | 2-bit encoding | MurmurHash3 | norm | ESKAPE | std8gb |
|---|---:|---|---:|---|---|
| `ACGTTGCAAGGCTTACGATCCGATTACGGAT` | 502444362787516835 | `0xf1bd73b9d57192ea` | **0.9443** | look up | **look up** |
| `GGCATTACGGATCCGTTAACGGCATTACGGA` | 2971365126523403368 | `0xd75963f5bc4f1b7f` | 0.8412 | look up | *skip* |
| `TTACGGATCCGTTAACGGCATTACGGATCCG` | 4352965367899646166 | `0x7d0162450e043383` | 0.4883 | look up | *skip* |
| `CAGTTGGCCAATTCCGGAATTCCGGAATTCC` | 1367494452758028533 | `0x25c888f968b01b2e` | 0.1476 | look up | *skip* |
| `GATCCGATTACGGATCCGATTACGGATCCGA` | 2547051273152209752 | `0x29ea115d575c9c14` | 0.1637 | look up | *skip* |
| `ACCGTTAACGGCCATTACGGATCCGTTAACG` | 413234212927008518 | `0xc9d98904d9530d16` | 0.7885 | look up | *skip* |
| `TGCAAGGCCTTAACGGATCCGTTAACGGCCA` | 4110202091676305044 | `0x2f63d57905621f91` | 0.1851 | look up | *skip* |

**1 of 7 survives.** Close to the expected 10.4%, but with n = 7 that is
coincidence, not confirmation — the measured rate over 206 M real lookups was
10.38%.

Note row 2: `0.8412` is above the middle of the range but still below 0.8962, so
it is discarded. The cut is at 89.62%, not 50%.

At scale: **206,485,766 lookups vs 21,436,003.**

# Part IV — Cost accounting

## 5. Cost model

Two unknowns — a fixed cost and a per-lookup cost — solved from the fork/std8
pair on full-file measurements:

| | per lookup | fixed base | base as % of fork total |
|---|---:|---:|---:|
| **cycles** | **424.91** | 986,421,113,166 | 54.6% |
| instructions | 92.58 | 1,690,611,064,193 | 90.4% |
| cache-references | 3.53 | 3,248,263,445 | 32.2% |
| **cache-misses** | **2.27** | 2,213,546,144 | 33.5% |
| LLC-load-misses | 0.68 | 602,765,337 | 31.3% |

**Independent physical check:** 424.91 cycles ÷ 2.27 DRAM accesses =
**187 cycles per DRAM access**, consistent with this machine's ~200-cycle memory
latency allowing for partial overlap. The model was fitted to cycles and misses,
not to latency, so this is a genuine consistency check.

### Decomposition

| | lookup cycles | lookup instr | **lookup IPC** | other cycles | other instr | **other IPC** |
|---|---:|---:|---:|---:|---:|---:|
| fork | 820,997,437,744 | 178,880,098,812 | **0.218** | 986,423,931,913 | 1,690,613,559,505 | **1.714** |
| spaced | 820,966,050,917 | 178,873,260,206 | 0.218 | 1,025,625,269,187 | 1,749,931,176,702 | 1.706 |
| std8 | 85,230,589,346 | 18,570,163,003 | 0.218 | 986,421,405,842 | 1,690,611,323,251 | **1.714** |

**What this table does and does not prove.** The arithmetic is exact — each row's
lookup and other columns sum to the measured totals to the unit. But two of its
apparent regularities are forced, not observed:

- **"lookup IPC 0.218" is identical on every row by definition.** It equals
  `INS_PER / CYC_PER` = 92.58 / 424.91, the ratio of the two fitted constants. It
  is a restatement of the fit, not a measurement.
- **fork and std8 having identical "other" columns is forced.** The constants were
  solved from exactly that pair, so subtracting `lookups x CYC_PER` guarantees
  equal residuals. This is algebra.
- **`spaced` is a weaker check than it first appears.** Its lookup count is within
  0.004% of fork's, so any timing difference between them lands in "other"
  automatically. Only the *magnitude* is informative: +59.3 G instructions over
  5.96 G scanned minimizers = **+9.95 instructions per scanned minimizer**, a
  plausible cost for applying a spaced-seed mask per minimizer. That is a
  plausibility check, not a validation of the model.

The decomposition is therefore **illustrative** — a way to see where the time sits
once you accept the per-lookup cost. It is not independent evidence for it. The
evidence for the finding is in §3 and §4: directly counted lookups, and a
threshold that predicts the observed skip rate to four significant figures.

Share of runtime in the lookup path:

| | | |
|---|---:|---|
| fork | **45.4%** | 13.59 s of 29.92 s |
| spaced | 44.5% | 13.77 s of 30.97 s |
| **std8** | **8.0%** | **1.36 s of 17.16 s** |

### Why IPC rises to 1.59

The program is two workloads with wildly different efficiency:

- **Hash lookups — IPC 0.218.** ~93 instructions costing ~425 cycles, stalled
  almost throughout on 2.27 DRAM accesses.
- **Everything else — IPC 1.714.** Scanning, hashing, bookkeeping, I/O:
  cache-friendly and well pipelined.

Overall IPC is the weighted average. On `fork` the terrible half is 45% of cycles
and drags it to 1.034. On `std8` it is 8%, so the average rises toward 1.714 and
lands at 1.595.

**Nothing runs faster.** The same code executes at the same speed on both
databases. Nine-tenths of the slowest work simply stops happening.

Predicting `std8` from `fork` using only the lookup delta:

```
fork cycles                  1,807,421,369,657
cycles saved by -M skips      −735,766,848,398
predicted std8 cycles        1,071,654,521,259
measured  std8 cycles        1,071,651,995,188     diff +0.0%
```

# Part V — Context

## 6. Two hypotheses this killed

### H1 — "the spaced seed collapses the lookup count"

`standard_8gb` uses a spaced seed (`0x3ffffffff3333333`, kraken2's default
`--minimizer-spaces 7`); the ESKAPE database does not. The proposed mechanism was
that masking bits makes neighbouring windows produce identical minimizers more
often, firing the duplicate-skip more and cutting lookups.

**Stated prediction:** `cache-references` should fall sharply while `instructions`
barely move.

To test it, `eskape_32bit_spaced` was built — identical library, k, ℓ, capacity
and cell width, with only the seed changed.

**Result: refuted.**

| | fork | spaced | change |
|---|---:|---:|---:|
| duplicate skips | 430,567,213 | 430,575,107 | **+0.002%** |
| lookups | 206,485,766 | 206,477,872 | −0.004% |
| cache-references | 10,076,492,917 | 10,085,977,200 | **+0.09%** |
| elapsed | 29.919 s | **30.973 s** | **+3.5% slower** |

Not one predicted effect appeared, and the spaced database is slightly *slower*.

What the seed actually does: shortens probe chains a little (6.27 → 6.04), raises
classification 78.13% → 80.15%, and costs **+9.95 instructions per scanned
minimizer** for the masking — visible as `spaced`'s "other instructions" being
59.3 G above the other two in §5's table. It changes *which* minimizers are
stored, not *how many lookups happen*.

### H2 — "database size explains it"

Also wrong, and backwards. 7.6 GB is a far worse shape for a 16 MB L3 than 47 MB
is. The large database wins **despite** its size, not because of it. Once
subsampling is controlled for, size is a handicap.

## 7. Provenance — the database was downloaded, not built here

| evidence | |
|---|---|
| timestamps | all files 03:32–03:38, an **18-minute window** for an 8 GB index |
| build log | **absent** — both local ESKAPE builds wrote one |
| local build cost | 7 min for a 47 MB DB at `--threads 1`; a standard build is hours and needs ≫31 GB RAM |
| file set | `inspect.txt`, `library_report.tsv`, `ktaxonomy.tsv`, `unmapped_accessions.txt`, seven Bracken `.kmer_distrib` files — none produced by `build_db` |

These are the published **Standard-8** / **Standard-16** prebuilt indexes. The
"-8" and "-16" *are* the cap. The chain is:

```
someone else:  kraken2-build --standard --max-db-size 8
               → 71.8 GB needed, capped to 8 GB
               → threshold written into opts.k2d
                          ↓
you:           downloaded and extracted
                          ↓
you:           classify -H hash.k2d -t taxo.k2d -o opts.k2d -p 16 -g 2 -T 0
               → classify reads opts.k2d, finds the threshold
               → skips 89.62% of lookups automatically
```

**Subsampling was never requested and could not be declined.** The decision was
made elsewhere and travelled inside `opts.k2d`.

## 8. Implications

**This is `-M` subsampling — already item #2 in the improvement plan**, recorded
at **−26.7% standalone** and flagged as "the one proven lever, never tested with
prefetch." `standard_8gb` is that lever pre-baked into a database, which is why it
looked anomalous.

**It caps what prefetch can achieve on such a database.** `-B` hides latency in
the lookup path — 45.4% of `fork`'s runtime but only 8.0% of `std8`'s. Amdahl's
law puts the ceiling near 8% there. This is consistent with the partial 8 GB
sweep, where `-B 1` cost **+46%** against +9% on ESKAPE, and it predicts that a
full `-B` sweep on a subsampled database will look disappointing for reasons that
have nothing to do with prefetch working.

**Any cross-database comparison in this project must check `opts.k2d` first.**
`eskape_32bit_fork` vs `standard_8gb` differs in *three* variables — seed, size,
subsampling — and the third dominates so completely that the other two are
invisible. The relevant header fields are k, ℓ, spaced-seed mask, toggle mask and
`minimum_acceptable_hash_value`.

**Accuracy is not established by this work.** Classification rose 78.13% → 81.46%,
but that is confounded: `standard_8gb` is also vastly more comprehensive. This
says nothing about subsampling's own accuracy cost, which an earlier standalone
measurement put at **−1.3 pp sensitivity**.

## 9. Next step this suggests

Build ESKAPE **with subsampling and nothing else changed** — same library, seed,
k, ℓ, cell width, only `-M` added. That isolates subsampling's speed benefit and
accuracy cost on identical content, and composes directly with the existing
prefetch results. It is the same single-variable method that settled the seed
question here, and it is cheap: ~7 minutes per build.

# Part VI — Practical

## 10. Reproduction

```bash
# 1. inspect any database's header
python3 -c "
import struct
v=struct.unpack('<8Q',open('databases/<DB>/opts.k2d','rb').read())
print(f'k={v[0]} l={v[1]} seed=0x{v[2]:016x} toggle=0x{v[3]:016x}')
print(f'min_acceptable_hash_value=0x{v[5]:016x} -> skips {100*v[5]/2**64:.2f}% of lookups')"

# 2. reproduce the hash for any l-mer
python3 -c "
M=(1<<64)-1
def murmur(k):
    k&=M
    k^=k>>33; k=(k*0xff51afd7ed558ccd)&M
    k^=k>>33; k=(k*0xc4ceb9fe1a85ec53)&M
    k^=k>>33; return k
E={'A':0,'C':1,'G':2,'T':3}
s='ACGTTGCAAGGCTTACGATCCGATTACGGAT'
k=0
for c in s: k=(k<<2)|E[c]
print(s, k, hex(murmur(k)), murmur(k)/2**64)"

# 3. instrumented counts
./scratch_probe/classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0 subset.fastq 2>&1 >/dev/null | grep PROBESTAT

# 4. the interleaved timing comparison
bash /home/dell/.claude/jobs/a307ba6a/tmp/seedcmp.sh
```

## 11. Limits

- **Counts come from a 200,000-read subset** scaled ×9.357, assuming the rest of
  the file behaves the same.
- **§5's decomposition is illustrative, not evidential.** The per-lookup cost was
  solved from the fork/std8 pair, so their matching "other" columns are forced;
  "lookup IPC 0.218" is likewise just the ratio of the two fitted constants.
  `spaced` is a weaker check than first described — its lookup count matches
  fork's, so its difference lands in "other" automatically, and only the
  magnitude (+9.95 instructions per scanned minimizer) is a plausibility check.
  **The finding does not rest on the model.** It rests on §3's directly counted
  lookups and §4's threshold arithmetic. The one genuinely independent check on
  the model is 424.91 cycles / 2.27 DRAM accesses = 187 cycles per access, which
  matches this machine's memory latency and was not fitted to it.
- **The model is linear in lookups.** It ignores that `std8`'s surviving lookups
  have shorter probe chains (4.45 vs 6.27), a difference absorbed into the fitted
  constant.
- **`spaced` has 2 usable runs, not 3.** Run 2 segfaulted — stock
  `kraken2_bin/classify`, 1.5 s in, on a freshly rebooted machine. This box has
  now produced sporadic SIGSEGVs in `classify`, in `python3`, a `perf` process
  that survived `kill -9`, and an unexplained reboot. Hardware instability is the
  most likely explanation and should be ruled out with a memory test before more
  timing work.
