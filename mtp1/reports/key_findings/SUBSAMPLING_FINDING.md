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
| Instrumented build | `scratch_probe/` (`scratch_lookaside/` untouched) |
| Raw data | `result/seedcmp/` (9 perf files + `meta.txt`) |

---

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

## 4. Where the threshold comes from

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

### The skips are correctness, not a shortcut

The table only ever stored minimizers above the threshold. A lookup below it is a
**guaranteed miss** that would still cost a full random DRAM access and a probe
chain to an empty cell. Skipping returns the same answer for free. The build-time
rule and the query-time rule are the same rule; the approximation was made once,
at build time, when 89.6% of the library was discarded.

For a database with threshold 0, the `if` is false and the check is bypassed
entirely — every candidate goes to memory, because every one *might* be present.

### Worked example

Treating `MurmurHash3(minimizer)` as a number in [0, 1), the threshold sits at
0.8962:

| minimizer | hash | ESKAPE (thr. 0) | standard_8gb (thr. 0.8962) |
|---|---:|---|---|
| `ACGTT…A` | 0.1043 | look up → DRAM | *skip* — not stored |
| `GGCAT…C` | 0.4471 | look up → DRAM | *skip* |
| `TTACG…G` | 0.6698 | look up → DRAM | *skip* |
| `CAGTT…T` | 0.8107 | look up → DRAM | *skip* |
| `GATCC…A` | 0.9134 | look up → DRAM | **look up → DRAM** |
| `ACCGT…G` | 0.2250 | look up → DRAM | *skip* |
| `TGCAA…C` | 0.9776 | look up → DRAM | **look up → DRAM** |

7 lookups vs 2. At scale: 206,485,766 vs 21,436,003.

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

## 10. Reproduction

```bash
# 1. inspect any database's header
python3 -c "
import struct
v=struct.unpack('<8Q',open('databases/<DB>/opts.k2d','rb').read())
print(f'k={v[0]} l={v[1]} seed=0x{v[2]:016x} toggle=0x{v[3]:016x}')
print(f'min_acceptable_hash_value=0x{v[5]:016x} -> skips {100*v[5]/2**64:.2f}% of lookups')"

# 2. instrumented counts
./scratch_probe/classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0 subset.fastq 2>&1 >/dev/null | grep PROBESTAT

# 3. the interleaved timing comparison
bash /home/dell/.claude/jobs/a307ba6a/tmp/seedcmp.sh
```

## 11. Limits

- **Counts come from a 200,000-read subset** scaled ×9.357, assuming the rest of
  the file behaves the same.
- **The fork↔std8 residual match in §5 is partly circular** — the per-lookup cost
  was solved from those two points, so their "other" columns are forced to agree.
  The genuine validation is `spaced`, a third point the model was *not* fitted to,
  whose extra work lands in the "other" bucket at the magnitude the mechanism
  predicts.
- **The model is linear in lookups.** It ignores that `std8`'s surviving lookups
  have shorter probe chains (4.45 vs 6.27), a difference absorbed into the fitted
  constant.
- **`spaced` has 2 usable runs, not 3.** Run 2 segfaulted — stock
  `kraken2_bin/classify`, 1.5 s in, on a freshly rebooted machine. This box has
  now produced sporadic SIGSEGVs in `classify`, in `python3`, a `perf` process
  that survived `kill -9`, and an unexplained reboot. Hardware instability is the
  most likely explanation and should be ruled out with a memory test before more
  timing work.
