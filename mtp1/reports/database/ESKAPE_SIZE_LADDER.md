# The eskape `-M` size ladder: 13 databases built and measured

**Thirteen subsampled eskape databases were built spanning 8–32 MB at two cell widths,
verified structurally, and measured for speed and accuracy. Three results overturn the
predictions this project was working from.**

| | |
|---|---|
| Date | 2026-09-09 |
| Databases | `databases/eskape_sizes/` — 13 builds + `eskape_32bit_fork` as baseline |
| Build script | `scripts/build_eskape_sizes.sh` (idempotent) |
| Manifest | `databases/eskape_sizes/MANIFEST.tsv` |
| Speed workload | `perpod5/pod5_2.fastq` — 151,591 reads, 499.98 Mbp |
| Accuracy workload | `perpod5/pod5_15.fastq` — 30,378 reads, 90.55 Mbp |
| Classify settings | `-p 16 -B 29 -T 0` (speed), `-p 1 -B 29 -T 0` (accuracy), **no `-g`** |
| Binary | `scratch_lookaside/bin/classify_nodup` |
| Machine | i7-11700, 8C/16T, 16 MiB L3 |

---

## Headline findings

> **Revised 2026-09-09** after adding a true no-prefetch control arm (no `-B`:
> single-pass, no batching). Findings 1 and 2 below were measured against a `-B 29`
> baseline and are **artifacts of that choice** — see finding 4. Findings 3 and 5
> stand.

**1. ~~Subsampling is a net LOSS above ~20 MB.~~ RETRACTED.** Under `-B 29` every
database from 24 MB up measured *slower* than the 48.8 MB baseline (+5.52% at 32 MB).
Against the real no-prefetch control this reverses completely: cycles fall monotonically
1.3979e11 → 8.8281e10 across the whole ladder, with no break-even point. The penalty was
an artifact of comparing against a prefetching baseline.

**2. ~~Gains are half the projection.~~ RETRACTED for the same reason.** In BEFORE mode
the 8 MB database is **−36.8%** against baseline, not −15.43%.

**3. `-C 24` is dominated at every size** — slower than `-C 32` at all matched sizes and
contaminated by false positives (3–10 S. aureus against 0 at `-C 32`). Its apparent
accuracy edge is partly collisions: `eskape_C24_32MB` classifies 84.06%, *above* the
83.94% full-database baseline, which is impossible for a subsampled database.

**4. Memory stalls were never small — prefetch was hiding them.** `cycle_activity.stalls_l3_miss`
on the baseline is **23.60%** of cycles with no prefetch, against **1.88%** under `-B 29`.
Every earlier statement in this project that stalls are "capped at 1.3–2.9%" was measured
through a binary that had already absorbed them. This also **reinstates** a result I had
wrongly flagged as unreproducible: `CACHE_TABLE_ANALYSIS.md` Addendum 3's "DRAM stall
26.8% → 6.6%" reproduces here as 23.60% → 6.14% at 16 MB.

**5. `-C 32` accuracy predictions were exact** — seven builds matched their simulated
values to 0.01 pp (§4).

**6. Most LLC misses are the input file, not the hash table** — see §6.4. At 8 MB, 79% of
all LLC misses are compulsory read-stream traffic that no cache can avoid.


**7. At 8 MB the bottleneck moves off the hash table entirely.** With the database
subsampled, lookups fall to 20.9% of runtime and read+parse+scan rises to 79.1%, at
IPC 1.808 with only 1.45% of cycles stalled on L3 misses. Profiling that 79% puts
`MinimizerScanner` at **59.17% of total runtime**. The roadmap for it is in
**`FUTURE_UPDATE.md`**.

---

## 1. What was built

Sizes were chosen as round byte targets, floor 8 MB, at both viable cell widths.
`M` follows from the target: `M = (target_bytes − 32) / bytes_per_cell`.

All builds share `-c 12200000 -k 35 -l 31 -p 1` and the same library
(`databases/eskape_cs/library/*.fna`, 17 sequences, 28,061,107 bp), so **the only
variables are `M` and `-C`**.

`-p 1` because `build_db` segfaults at `--threads 16` on this box. **Each build takes 12
seconds**, not the ~7 minutes assumed in earlier planning documents — the full ladder
completed in under 3 minutes.

## 2. Build parameters and thresholds

| database | `-C` | `-M` | `hash.k2d` | keep | occupied | load | `key_bits` | threshold |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `eskape_32bit_fork` | 32 | 12,200,000 | 48,800,032 | 100.00% | 8,903,388 | 0.72979 | 26 | `0x0000000000000000` |
| `eskape_C32_32MB` | 32 | 7,999,992 | 32,000,000 | 65.57% | 5,840,995 | 0.73013 | 26 | `0x58219de2feb4f000` |
| `eskape_C32_24MB` | 32 | 5,999,992 | 24,000,000 | 49.18% | 4,380,299 | 0.73005 | 26 | `0x8219392a56d68000` |
| `eskape_C32_20MB` | 32 | 4,999,992 | 20,000,000 | 40.98% | 3,649,796 | 0.72996 | 26 | `0x971506ce02e74800` |
| `eskape_C32_16MB` | 32 | 3,999,992 | 16,000,000 | 32.79% | 2,919,273 | 0.72982 | 26 | `0xac10d471aef81000` |
| `eskape_C32_12MB` | 32 | 2,999,992 | 12,000,000 | 24.59% | 2,189,001 | 0.72967 | 26 | `0xc10ca2155b08e000` |
| `eskape_C32_10MB` | 32 | 2,499,992 | 10,000,000 | 20.49% | 1,825,075 | 0.73003 | 26 | `0xcb8a88e731114000` |
| `eskape_C32_08MB` | 32 | 1,999,992 | 8,000,000 | 16.39% | 1,460,591 | 0.73030 | 26 | `0xd6086fb90719a800` |
| `eskape_C24_32MB` | 24 | 10,666,656 | 32,000,000 | 87.43% | 7,786,807 | 0.73001 | 18 | `0x202cd283fe469000` |
| `eskape_C24_24MB` | 24 | 7,999,989 | 23,999,999 | 65.57% | 5,840,945 | 0.73012 | 18 | `0x5821a203226b2000` |
| `eskape_C24_20MB` | 24 | 6,666,656 | 20,000,000 | 54.64% | 4,868,368 | 0.73026 | 18 | `0x741c0912ae89b800` |
| `eskape_C24_16MB` | 24 | 5,333,322 | 15,999,998 | 43.72% | 3,894,001 | 0.73013 | 18 | `0x90167182468fb000` |
| `eskape_C24_12MB` | 24 | 3,999,989 | 11,999,999 | 32.79% | 2,919,225 | 0.72981 | 18 | `0xac10d891d2ae4800` |
| `eskape_C24_08MB` | 24 | 2,666,656 | 8,000,000 | 21.86% | 1,946,506 | 0.72994 | 18 | `0xc80b3fa15ecce000` |


## 3. Performance

| database | cycles | vs baseline | cv | instructions | IPC | stalls_l3_miss | LLC-misses | offcore_rd |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` | 1.1469e+11 | +0.00% | 1.53% | 1.6999e+11 | 1.482 | 1.88% | 2.318e+07 | 5.079e+08 |
| `eskape_C32_32MB` | 1.2103e+11 | +5.52% | 0.77% | 1.9162e+11 | 1.583 | 1.35% | 1.923e+07 | 4.263e+08 |
| `eskape_C32_24MB` | 1.1860e+11 | +3.41% | 0.84% | 1.9006e+11 | 1.603 | 1.21% | 1.827e+07 | 3.827e+08 |
| `eskape_C32_20MB` | 1.1426e+11 | -0.38% | 0.61% | 1.8640e+11 | 1.631 | 1.13% | 1.764e+07 | 3.634e+08 |
| `eskape_C32_16MB` | 1.0971e+11 | -4.35% | 0.63% | 1.8085e+11 | 1.649 | 1.08% | 1.711e+07 | 3.407e+08 |
| `eskape_C32_12MB` | 1.0373e+11 | -9.55% | 0.59% | 1.7341e+11 | 1.672 | 1.02% | 1.649e+07 | 3.229e+08 |
| `eskape_C32_10MB` | 1.0116e+11 | -11.80% | 0.67% | 1.6900e+11 | 1.671 | 0.99% | 1.624e+07 | 3.101e+08 |
| `eskape_C32_08MB` | 9.6994e+10 | -15.43% | 0.58% | 1.6411e+11 | 1.692 | 0.98% | 1.594e+07 | 3.005e+08 |
| `eskape_C24_32MB` | 1.2002e+11 | +4.65% | 0.26% | 1.8731e+11 | 1.561 | 1.92% | 2.192e+07 | 4.735e+08 |
| `eskape_C24_24MB` | 1.2200e+11 | +6.37% | 0.17% | 1.9562e+11 | 1.603 | 1.47% | 1.980e+07 | 4.232e+08 |
| `eskape_C24_20MB` | 1.2092e+11 | +5.43% | 0.38% | 1.9479e+11 | 1.611 | 1.31% | 1.886e+07 | 3.980e+08 |
| `eskape_C24_16MB` | 1.1662e+11 | +1.68% | 0.50% | 1.9054e+11 | 1.634 | 1.15% | 1.782e+07 | 3.705e+08 |
| `eskape_C24_12MB` | 1.1032e+11 | -3.81% | 0.62% | 1.8294e+11 | 1.658 | 1.02% | 1.682e+07 | 3.434e+08 |
| `eskape_C24_08MB` | 1.0176e+11 | -11.27% | 0.47% | 1.7197e+11 | 1.690 | 0.94% | 1.601e+07 | 3.180e+08 |


All five counters ran at `enabled=100.00%` — no multiplexing.

## 4. Accuracy

| database | classified | unclassified | clsfd% | Δpp | S. aureus FP | E. faecium FP | E. cloacae | P. aeruginosa |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` | 25,498 | 4,880 | 83.94% | +0.00 | 0 | 1 | 144 | 15,924 |
| `eskape_C32_32MB` | 25,421 | 4,957 | 83.68% | -0.25 | 0 | 1 | 139 | 15,875 |
| `eskape_C32_24MB` | 25,372 | 5,006 | 83.52% | -0.41 | 0 | 1 | 133 | 15,844 |
| `eskape_C32_20MB` | 25,324 | 5,054 | 83.36% | -0.57 | 0 | 1 | 134 | 15,816 |
| `eskape_C32_16MB` | 25,265 | 5,113 | 83.17% | -0.77 | 0 | 1 | 129 | 15,784 |
| `eskape_C32_12MB` | 25,143 | 5,235 | 82.77% | -1.17 | 0 | 1 | 125 | 15,715 |
| `eskape_C32_10MB` | 25,057 | 5,321 | 82.48% | -1.45 | 0 | 1 | 125 | 15,657 |
| `eskape_C32_08MB` | 24,919 | 5,459 | 82.03% | -1.91 | 0 | 1 | 123 | 15,567 |
| `eskape_C24_32MB` | 25,535 | 4,843 | 84.06% | +0.12 | 10 | 6 | 156 | 15,921 |
| `eskape_C24_24MB` | 25,478 | 4,900 | 83.87% | -0.07 | 5 | 10 | 157 | 15,881 |
| `eskape_C24_20MB` | 25,435 | 4,943 | 83.73% | -0.21 | 2 | 8 | 141 | 15,865 |
| `eskape_C24_16MB` | 25,431 | 4,947 | 83.72% | -0.22 | 4 | 12 | 166 | 15,842 |
| `eskape_C24_12MB` | 25,331 | 5,047 | 83.39% | -0.55 | 5 | 8 | 141 | 15,797 |
| `eskape_C24_08MB` | 25,149 | 5,229 | 82.79% | -1.15 | 3 | 6 | 135 | 15,688 |

`-C 32` reproduced the simulated predictions **exactly**: 82.03 / 82.48 / 82.77 / 83.17 /
83.36 / 83.52 / 83.68% measured against 82.03 / 82.48 / 82.77 / 83.17 / 83.36 / 83.52 /
83.69% simulated — seven builds, all within 0.01 pp. The `opts.k2d`-patching method is
validated.

`-C 24` did **not** reproduce its predictions, running 0.17–0.31 pp high. That gap is the
false-positive contamination, confirmed by the FP columns.

## 5. Structural verification

Every database was checked against closed-form predictions before any measurement:

| check | result |
|---|---|
| `hash.k2d` = `(C/8) × M + 32` | **13/13 exact** |
| `opts.k2d` word 5 = `(1 − M/12,200,000) × UINT64_MAX` | **13/13 exact** |
| `capacity_` header field = `M` | **13/13 exact** |
| all other `opts.k2d` fields match baseline (k=35, l=31, seed, toggle, revcom) | **13/13 identical** |
| `taxo.k2d` identical across all builds + baseline | **one md5 for all 14** |
| build logs: errors or warnings | **none** |
| input processed | all 13: "17 sequences, 28061107 bp" |
| cell width in log | 7× "Using 32-bit cells", 6× "Using 24-bit cells" |

**Load factor holds at 0.7297–0.7303 across a 5.3× range of `M`**, and occupancy is within
**0.070%** of `8,903,388 × M/12,200,000` in the worst case. That is the strongest single
indicator the subsampling behaved correctly: the hash sampled uniformly at every threshold.

### Read-level equivalence with the simulation method

The real 10 MB build was compared against the full 48.8 MB table carrying the *same*
patched threshold, read by read on pod5_15:

```
30,378 reads
  fields 1-4 (call, read ID, taxid, length):  IDENTICAL on all 30,378
  field 5 (k-mer mapping):                    1 read differs
```

The single difference is explainable and expected. On that read the 10 MB build reports
two hits to taxid 1125630 that the full table does not. The slot is `hc % capacity_`, and
capacity differs (2,499,992 vs 12,200,000), so an absent minimizer probes a different
chain and can collide with a different stored entry. **The set of stored minimizers is
identical; the collision layout is not.**

This validates the `opts.k2d`-patching method at read level and characterises its one
limitation precisely.

## 6. Interpretation

### Why subsampling loses above 20 MB  — SUPERSEDED by §9

> This subsection explains an effect that only exists relative to a `-B 29`
> baseline. Against the no-prefetch control (§9) subsampling wins at every
> size and there is no break-even point. Retained for the record.


IPC climbs monotonically as the table shrinks — 1.482 at the baseline to 1.692 at 8 MB —
so the surviving work *does* become more efficient exactly as predicted. But at high keep
fractions there is not enough lookup elimination to pay for whatever the smaller table
costs. Note the baseline has the **highest** `stalls_l3_miss` (1.88%) and the **worst**
IPC (1.482), yet still wins on total cycles against everything above 20 MB.

The mechanism behind the penalty is not established by this data. Candidates: the
`-M` threshold test itself costs a compare on every non-duplicate minimizer whether or not
it fires; and probe chains on a smaller table terminate differently. Neither was isolated.

### Why the gains are half the projection  — SUPERSEDED by §9

> Same cause. In BEFORE mode the 8 MB database is −36.8%, not −15.43%.


`-B 29` prefetching and `-M` subsampling are substitutes — both attack the lookup path.
The model was calibrated with a lookup-path share of 26.5%, but the measured saturation
suggests prefetch had already recovered more of that path than assumed. Against a
non-prefetching baseline `-M` would look considerably better; against today's default it
does not.

### Why `-C 24` fails

Two independent penalties compound:

- **Cache line straddling.** 64/3 = 21.33 cells per line, so cells cross line boundaries.
  Measured +3.5% instructions in earlier work; here it shows as up to 6.0 pp of cycles.
- **Fingerprint collisions.** 18 `key_bits` against `-C 32`'s 26 — a 256× higher
  false-positive rate per probe. `eskape_C24_32MB` classifies **84.06%, above the 83.94%
  full-database baseline**, which is impossible for a subsampled database and is the
  clearest possible signature of contamination.

## 7. Recommendation

**`eskape_C32_08MB`** — 8,000,000 bytes, `-M 1999992`, threshold `0xd6086fb90719a800`.

- **−15.43% cycles**, the fastest on the ladder
- **6.1× smaller** than baseline
- **82.03% classified**, −1.91 pp
- **false positives unchanged at 0/1**, identical to baseline at every `-C 32` size

```bash
D=databases/eskape_sizes/eskape_C32_08MB
scratch_lookaside/bin/classify_nodup \
    -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -B 29 -T 0 <reads.fastq>
```

If 1.91 pp is too much, **`eskape_C32_10MB`** gives −11.80% for −1.46 pp.

## 8. Limits and open questions

- **The curve has not flattened at 8 MB.** Cycles were still falling steeply at the floor
  of this ladder (−11.80% → −15.43% between 10 and 8 MB). The optimum may well lie below
  8 MB; this study cannot say, because 8 MB was the specified floor.
- **The baseline arm is the noisiest.** cv 1.53% against 0.17–0.84% for the subsampled
  builds, so the "vs baseline" column carries more uncertainty than the others.
- **The +5.52% penalty at high keep is unexplained.** It reproduces cleanly across both
  cell widths and all five reps, but no mechanism was isolated.
- **One accuracy sample.** All accuracy figures are pod5_15. Speed is pod5_2. Neither was
  replicated on a second file.
- **`-T 0` only.** `-M` is structurally incompatible with `-T > 0`: `classify.cc:763`
  divides by `total_minimizers`, which counts `-M`-skipped positions, so confidence
  collapses in proportion to the keep fraction. Any pipeline using confidence must
  recalibrate.
- **E. cloacae is the sensitive taxon.** It falls 144 → 123 (−14.6%) at 8 MB while the
  aggregate falls 2.3%. For an ESKAPE panel, per-species retention matters more than
  `clsfd%`, and this argues for 10–12 MB over 8 MB if low-abundance detection is the goal.
- **This box returns silently wrong output at `-p 16` with exit code 0.** All accuracy work
  was done at `-p 1`, which is byte-identical every run. Speed used cycle counts, which are
  stable to under 1% and were taken as medians of 5 interleaved reps.

## 9. BEFORE mode: the no-prefetch control arm

Added 2026-09-09. Every earlier table in this document used `-B 29` as its
reference, so "cycles" meant *cycles relative to a prefetching baseline*. This section
adds the real control: `classify_mode` with **no `-B` flag**, a single-pass loop that
scans one minimizer, hashes it, blocks on `GetWithHash()`, counts and records it — no
`PfSlot` array, no second pass, no prefetch.

Fidelity check: it executes **158.97 G instructions against upstream kraken2's 158.00 G,
within 0.6%**, and its output is byte-identical to upstream and to every `-B` setting.
(An earlier attempt that merely suppressed the prefetch inside the two-pass loop sat at
176 G — the batching bookkeeping is ~11% on its own, which is why it was not a valid
control.)

pod5_2 · 151,591 reads / 499.98 Mbp · `-p 16 -T 0`, no `-g` · medians of 3 reps,
`enabled=100.00%` on all counters.

| database | MB | clsfd% | wall s | cycles | vs base | instructions | IPC | stall% | L1 miss% | LLC miss% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` | 48.8 | 84.78 | 2.919 | 1.3979e+11 | +0.00% | 1.5781e+11 | 1.129 | 23.60% | 2.246% | 59.61% |
| `eskape_C32_32MB` | 32.0 | 84.49 | 2.787 | 1.3092e+11 | -6.35% | 1.7965e+11 | 1.372 | 14.04% | 1.582% | 54.66% |
| `eskape_C32_24MB` | 24.0 | 84.31 | 2.598 | 1.2015e+11 | -14.05% | 1.7816e+11 | 1.483 | 10.14% | 1.381% | 51.06% |
| `eskape_C32_20MB` | 20.0 | 84.15 | 2.456 | 1.1418e+11 | -18.32% | 1.7453e+11 | 1.529 | 8.13% | 1.298% | 47.97% |
| `eskape_C32_16MB` | 16.0 | 83.93 | 2.319 | 1.0600e+11 | -24.17% | 1.6905e+11 | 1.595 | 6.14% | 1.226% | 45.12% |
| `eskape_C32_12MB` | 12.0 | 83.52 | 2.129 | 9.7149e+10 | -30.50% | 1.6164e+11 | 1.664 | 4.25% | 1.158% | 40.62% |
| `eskape_C32_10MB` | 10.0 | 83.19 | 2.038 | 9.3150e+10 | -33.37% | 1.5725e+11 | 1.688 | 3.28% | 1.128% | 38.22% |
| `eskape_C32_08MB` | 8.0 | 82.77 | 1.937 | 8.8281e+10 | -36.85% | 1.5240e+11 | 1.726 | 2.37% | 1.102% | 37.19% |
| `eskape_C24_32MB` | 32.0 | 84.87 | 2.905 | 1.3665e+11 | -2.24% | 1.7501e+11 | 1.281 | 17.95% | 1.920% | 53.55% |
| `eskape_C24_24MB` | 24.0 | 84.70 | 2.770 | 1.2901e+11 | -7.71% | 1.8348e+11 | 1.422 | 12.25% | 1.562% | 48.75% |
| `eskape_C24_20MB` | 20.0 | 84.57 | 2.652 | 1.2283e+11 | -12.14% | 1.8265e+11 | 1.487 | 9.42% | 1.427% | 45.42% |
| `eskape_C24_16MB` | 16.0 | 84.45 | 2.490 | 1.1476e+11 | -17.91% | 1.7848e+11 | 1.555 | 6.83% | 1.313% | 41.33% |
| `eskape_C24_12MB` | 12.0 | 84.12 | 2.293 | 1.0576e+11 | -24.35% | 1.7102e+11 | 1.617 | 4.68% | 1.215% | 36.24% |
| `eskape_C24_08MB` | 8.0 | 83.53 | 2.070 | 9.3346e+10 | -33.22% | 1.6008e+11 | 1.715 | 2.28% | 1.136% | 32.85% |

**Subsampling wins at every size here.** Cycles fall monotonically from 1.3979e11 to
8.8281e10 — a **−36.8%** span with no break-even point, against the `-B 29` table where
everything above 20 MB was a net loss.

**Stalls are an order of magnitude larger than previously recorded.** 23.60% of cycles at
baseline, falling to 2.37% at 8 MB. Under `-B 29` the same range reads 1.88% → 0.96%.
Prefetching was absorbing the latency, not eliminating the misses.

### 9.1 Why an 8 MB table still shows a high LLC miss rate

The table fits in L3 (8 MB against 16.78 MB) and *is* resident. The miss rate is
measuring something else.

pod5_2 is 1,038,110,684 bytes = **16.22 M cache lines**, every one read from DRAM exactly
once. That is a compulsory floor no cache can avoid, identical at every table size:

| database | MB | LLC-loads | LLC-misses | read stream | table | table lines |
|---|---:|---:|---:|---:|---:|---:|
| `eskape_32bit_fork` | 48.8 | 2.5194e+08 | 1.5019e+08 | 1.622e+07 | 1.3397e+08 | 762,500 |
| `eskape_C32_32MB` | 32.0 | 1.6729e+08 | 9.1444e+07 | 1.622e+07 | 7.5224e+07 | 500,000 |
| `eskape_C32_24MB` | 24.0 | 1.2819e+08 | 6.5450e+07 | 1.622e+07 | 4.9230e+07 | 375,000 |
| `eskape_C32_20MB` | 20.0 | 1.0997e+08 | 5.2751e+07 | 1.622e+07 | 3.6531e+07 | 312,500 |
| `eskape_C32_16MB` | 16.0 | 9.0685e+07 | 4.0916e+07 | 1.622e+07 | 2.4696e+07 | 250,000 |
| `eskape_C32_12MB` | 12.0 | 7.2905e+07 | 2.9615e+07 | 1.622e+07 | 1.3395e+07 | 187,500 |
| `eskape_C32_10MB` | 10.0 | 6.4026e+07 | 2.4473e+07 | 1.622e+07 | 8.2528e+06 | 156,250 |
| `eskape_C32_08MB` | 8.0 | 5.5242e+07 | 2.0544e+07 | 1.622e+07 | 4.3235e+06 | 125,000 |

**At 8 MB, 79% of all LLC misses are the read stream** — 16.22 M of 20.54 M. Only 4.32 M
come from the table. Confirmed directly at `-p 1`, where misses tracked *file* size, not
table size, to within 2–3%:

```
pod5_2   16.22 M lines in file  ->  15.70 M LLC misses   (97%)
pod5_15   2.95 M lines in file  ->   2.90 M LLC misses   (98%)
```

Two things inflate the *rate*:

- **The denominator is pre-filtered.** `LLC-loads` counts only accesses that already
  missed L1 and L2 — 5.5e7 of 3.97e10 L1 loads, about **0.14%**. Everything easy is gone;
  what reaches L3 is random hash probes plus compulsory stream lines.
- **Shrinking the table removes L3 *hits*, not misses.** 48.8 MB -> 8 MB drops LLC-loads
  2.52e8 -> 5.52e7 while misses drop 1.50e8 -> 2.05e7. The numerator cannot fall below the
  16.22 M stream floor, so the ratio worsens while absolute misses improve **7.3x**.

The table is genuinely hot: 125,000 lines against L3's 262,188, and ~26 M lookups over
those lines is ~200 touches each. Its residual 4.32 M misses are eviction pressure from
the 1 GB stream flowing past, not capacity. The 48.8 MB baseline shows the converse —
762,500 lines against 262,188 available, **2.9x oversubscribed**, hence 134 M table
misses. That is what shrinking fixes, and why cycles fall 1.398e11 -> 8.828e10.

**Read `LLC-misses` with `offcore_requests` and absolute counts, never the rate alone**
(`PREFETCH.md` §15).

