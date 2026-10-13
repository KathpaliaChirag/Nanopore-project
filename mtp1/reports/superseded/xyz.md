> ## ⚠ RETRACTED — 2026-09-08, superseded
>
> **§3's model, the "−20 pp" headline, and §4(a)'s "5× cheaper" claim are wrong.**
> `rho` was **9.357× too small**: `SUBSAMPLING_FINDING.md` §3's counts are unscaled
> 200k-read subset data presented against full-file Mbp. The sanity check that catches
> it in one line: `mmscanner` emits ~1 minimizer per bp, and the figure used implied
> 0.105/bp. True mean hit groups per read is **459**, not ~110.
>
> Corrected by direct measurement (no model): **Standard-8's ratio costs 6.08 pp, not
> 20 pp.** `-C 24`'s advantage at matched bytes is **+0.5 pp**, not 5×, and it is more
> than cancelled by a measured **+2.5% cycle penalty** from 3-byte cells straddling
> 64 B lines.
>
> Also wrong here: the framing that L3 residency is the lever. Measured, a 2× table cut
> at constant work buys **1.57%** of cycles; `cycle_activity.stalls_l3_miss` is only
> 1.3–2.9%, which caps it.
>
> **Superseded by `~/.claude/plans/vast-strolling-dove.md`.** Sections 1, 2, 5, 6 and 7
> below remain accurate.

# Shrinking the eskape database with `-M`

**Can we do to eskape what `--max-db-size` did to the 71 GB Standard library?
Yes — one build flag. But not at Standard-8's ratio: the arithmetic says that
setting would cost ~20 pp of sensitivity, and the useful window is 3–4× larger.**

| | |
|---|---|
| Date | 2026-09-08 |
| Baseline | `databases/eskape_32bit_fork` — 48,800,032 B, `-c 12200000 -k 35 -l 31 -C 32` |
| Reference | `databases/standard_8gb` — 8,000,000,032 B, prebuilt Standard-8 |
| Accuracy workload | `perpod5/pod5_15.fastq` — 30,378 reads, 90.5 Mbp, mean 2,981 bp |
| Prior art | `SUBSAMPLING_FINDING.md` (§14 asks for exactly this experiment), `CACHE_TABLE_ANALYSIS.md` Addendum 3 |
| Status | **analysis only — nothing built** |

---

## 1. The mechanism, re-confirmed against the files on disk

`kraken2/src/build_db.cc:77-84` is the only writer of the threshold in the codebase:

```c
auto actual_capacity = opts.capacity;
if (opts.maximum_capacity) {
  double frac = opts.maximum_capacity * 1.0 / opts.capacity;   // = M / -c
  if (frac > 1)
    errx(EX_DATAERR, "maximum capacity larger than requested capacity");
  opts.min_clear_hash_value = (uint64_t) ((1 - frac) * UINT64_MAX);
  actual_capacity = opts.maximum_capacity;                     // allocate the SMALL table
}
```

The threshold travels to query time inside `opts.k2d`, where `classify.cc:875`
applies the identical comparison. Decoded from the two databases just now:

| | `eskape_32bit_fork` | `standard_8gb` |
|---|---|---|
| `opts.k2d` word 5 | `0x0000000000000000` | `0xe5703cec83cdd800` |
| keeps | 100% | 10.3756% |
| `hash.k2d` | 48,800,032 B | 8,000,000,032 B |
| capacity / occupied | 12,200,000 / 8,903,388 | 2,000,000,000 / — |

The wrapper route (`kraken2-build --max-db-size 8G`) only converts bytes to cells —
`scripts/build_kraken2_db.sh:114` divides by 4, `scripts/k2:2961` divides by
`cht_cell_size/8`. Both apply it **only as a cap**, when the requested size is below
what the library needs. eskape is built by calling `build_db` directly, so `-M` goes
on that command line.

`hash.k2d` = `bytes_per_cell × M + 32` **exactly**. The size is guaranteed, not
estimated.

**This is not compression.** It stores fewer minimizers. The information is discarded
at build time and cannot be recovered.

## 2. Why eskape's fixed `-c` makes this a clean experiment

`frac` divides by `opts.capacity` — for eskape the hand-specified `-c 12200000`,
not an `estimate_capacity` output. Because `fmix64` is a bijection with uniform
output, the same fraction of *stored* minimizers survives as of all minimizers:

```
occupied(M) = 8,903,388 × M/12,200,000
load(M)     = occupied(M)/M = 8,903,388/12,200,000 = 0.7298    ← independent of M
```

**Load factor is preserved at every M.** Probe chains do not lengthen, so the only
variables are table bytes and lookups kept. Every other database property is held
fixed. That is what makes this worth measuring.

## 3. Why Standard-8's ratio does not transfer

Standard-8's stored threshold implies its library needed **19,275,968,731** cells
(71.8 GB) and was capped to 2,000,000,000. eskape needs **12,200,000**. That is a
**1,517×** difference in reference redundancy.

Standard tolerates a 90% cut because thousands of genomes cover each read many times
over — throw away nine of ten minimizers and plenty of independent evidence remains.
eskape has **17 sequences**: one genome per read, and no redundancy to spend.

### The read-level model

Classification with `-g 2` requires **two distinct hit groups**
(`minimizer_hit_groups`). Subsampling keeps each independently with probability
`f = M/12,200,000`, so a read with `H` hit groups at full size is lost when:

```
P(lost) = P(Binom(H, f) < 2) = (1-f)^H + H·f·(1-f)^(H-1)
```

`H` is emphatically **not** constant, and that is where the whole result lives. The
mean pod5_15 read is 2,981 bp — but **35% of reads are under 500 bp**, and those are
what the cut destroys. So `H = ρ·L` over the real length distribution:

```
  <200 bp     471   1.55%
  200-500  10,202  33.58%
  500-1k    4,941  16.27%
  1k-2k     3,288  10.82%
  2k-5k     6,073  19.99%
  >5k       5,403  17.79%
```

with `ρ = 206,485,766 / 6,047.42 Mbp = 0.03414` candidate minimizers per bp
(measured, `SUBSAMPLING_FINDING.md` §3 — one per 29 bp).

One free parameter: the length floor below which reads are already unclassified at
baseline. Fitted to the single measured `-M` datapoint on record:

```
fit:        24-bit -M 4,000,000   f = 0.3279   83.39% -> 82.07%  (-1.32 pp)
            => classified population = reads >= 287 bp (92.2% of reads, mean H = 110)

held out:   16-bit -M 6,000,000   f = 0.4918   model 0.114%   measured 0.121%   ✓
```

**The 16-bit point was not used in the fit** and the model lands within 6% relative
on it. One parameter, one fit, one independent check — enough to choose where to
sample, not enough to be a result.

### The curve (32-bit cells, baseline 83.39% classified)

| M | keep | `hash.k2d` | < 16 MiB L3 | loss `-g 2` | clsfd | loss `-g 1` | pred. speed |
|---:|---:|---:|:--|---:|---:|---:|---:|
| 8,903,388 | 72.98% | 35.61 MB | no | 0.00% | 83.39% | 0.00% | −12% |
| 6,000,000 | 49.18% | 24.00 MB | no | 0.11% | 83.29% | 0.01% | −23% |
| 5,000,000 | 40.98% | 20.00 MB | no | 0.47% | 83.00% | 0.05% | −27% |
| 4,500,000 | 36.89% | 18.00 MB | no | 0.88% | 82.66% | 0.11% | −29% |
| **4,000,000** | 32.79% | **16.00 MB** | boundary | **1.59%** | 82.06% | 0.24% | −31% |
| **3,500,000** | 28.69% | **14.00 MB** | **yes** | **2.79%** | 81.07% | 0.48% | −32% |
| 3,000,000 | 24.59% | 12.00 MB | yes | 4.72% | 79.45% | 0.94% | −34% |
| 2,500,000 | 20.49% | 10.00 MB | yes | 7.77% | 76.91% | 1.82% | −36% |
| 2,000,000 | 16.39% | 8.00 MB | yes | 12.45% | 73.01% | 3.48% | −38% |
| ~~1,265,825~~ | ~~10.38%~~ | ~~5.06 MB~~ | yes | **23.85%** | **63.50%** | 8.98% | −41% |
| 610,000 | 5.00% | 2.44 MB | yes | 41.82% | 48.52% | 22.00% | −43% |

Speed is Amdahl on the measured lookup share (45.4% of `fork` cycles,
`SUBSAMPLING_FINDING.md` §10): `0.546 + 0.454·f`. It excludes any L3-residency bonus,
so it is a **floor**. Sanity check: it predicts −30.5% at the M where −26.7% was
actually measured.

The last row is the point. **Copying Standard-8's 10.38% onto eskape costs roughly
20 pp of sensitivity** — 83.39% → 63.5%. The knees:

```
1% loss  at M = 4,394,046   (36.0% kept, 17.6 MB)
2% loss  at M = 3,799,683   (31.1% kept, 15.2 MB)
5% loss  at M = 2,943,379   (24.1% kept, 11.8 MB)
```

**The useful window is M = 3.0 M – 5.0 M**, which is exactly where `hash.k2d` crosses
the 16 MiB L3 boundary. That coincidence is the whole opportunity.

## 4. Two levers that beat pushing M down

### (a) Cell width buys keep-fraction at the same byte budget

`hash.k2d = (C/8) · M + 32`, so at a fixed size narrower cells store more minimizers:

| budget | `-C 32` | `-C 24` | `-C 16` |
|---|---|---|---|
| **16 MB** | M=4.00 M, 32.8% kept, **−1.59%** | M=5.33 M, 43.7%, **−0.30%** | M=8.00 M, 65.6%, −0.00% |
| **12 MB** | M=3.00 M, 24.6%, −4.72% | M=4.00 M, 32.8%, −1.59% | M=6.00 M, 49.2%, −0.11% |

At the same 16 MB, **`-C 24` is 5× cheaper in sensitivity than `-C 32`**.

`-C 16` looks free and is not. Narrower cells mean shorter fingerprints and more
collisions: the recorded 16-bit runs show S.aureus false positives at **128** against
**0** at 24- and 32-bit, which is also why their classified% *rises* to 90.93%. That
is contamination, not sensitivity. **`-C 24` is the pick.**

### (b) `-g 1` moves the entire curve

The loss is `P(Binom < g)`. Dropping `g` from 2 to 1 deletes the dominant
`H·f·(1-f)^(H-1)` term — at M = 2,000,000 the cost falls from **12.45% to 3.48%**.

This is a *classify* flag, free at build time, so it costs one extra arm in a sweep
and may be worth more than any choice of M. Its price is false positives, which the
pod5_15 S.aureus / E.faecium counts measure directly.

## 5. The commands

Direct `build_db` (the way eskape is built — pattern from
`scripts/build_cellsize_dbs.sh`). `-p 1` because `build_db` segfaults at 16 threads on
this box; each build is ~7 minutes for a 28 Mbp library.

```bash
cd /home/dell/summer
for spec in "32 5000000" "32 4000000" "32 3500000" "24 5333322" "24 4000000"; do
  set -- $spec; C=$1; M=$2
  OUT=databases/eskape_C${C}_M${M}; mkdir -p "$OUT"
  cat databases/eskape_cs/library/*.fna | kraken2_bin/build_db \
      -H "$OUT/hash.k2d" -t "$OUT/taxo.k2d" -o "$OUT/opts.k2d" \
      -n databases/eskape_cs/taxonomy \
      -m databases/eskape_cs/seqid2taxid.map \
      -c 12200000 -k 35 -l 31 -p 1 -C "$C" -M "$M" \
      2>&1 | tee "$OUT/build.log"
done
```

Plus one deliberate **failure probe** at Standard-8's exact ratio, to put the
predicted collapse on record as a measurement rather than a model output:

```bash
# M = round(12,200,000 × 0.1037561) = 1,265,825
#   -> hash.k2d 5,063,332 B, threshold 0xe5703cb38d724000
#   -> within 0.000001% of standard_8gb's 0xe5703cec83cdd800
```

**Verify every build before trusting it** — size and threshold are both predictable
in closed form:

```bash
python3 -c "
import struct,sys,os
d,M,C = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
v = struct.unpack('<8Q', open(d+'/opts.k2d','rb').read())
print('%-28s size %9d exp %9d | thr 0x%016x exp 0x%016x' % (
      d, os.path.getsize(d+'/hash.k2d'), (C//8)*M+32,
      v[5], int((1-M/12200000)*((1<<64)-1))))" databases/eskape_C32_M4000000 4000000 32
```

Measurement, using the same canonical command as the prefetch work:

```bash
perf stat -e cycles,instructions,cycle_activity.stalls_l3_miss,\
LLC-misses,offcore_requests.all_data_rd \
  scratch_lookaside/bin/classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0 -B 29 perpod5/pod5_2.fastq > /dev/null
```

Read `LLC-misses` **together with** `offcore_requests.all_data_rd` — the first alone
is misleading (`PREFETCH.md` §15).

## 6. Prerequisite: gate the prefetch on `-M`

`scratch_lookaside/src/classify.cc` pass 1 issues a prefetch for every non-duplicate
minimizer and applies the `-M` threshold only in pass 2. On a database that rejects
70% of minimizers, **~7 of every 10 prefetches become wasted random DRAM fetches** —
and unlike duplicate prefetches (already gated, `CHANGELOG.md` 2026-09-02) these
target lines that are genuinely **not** resident.

Measuring `-M` without this fix would understate it. The change mirrors the duplicate
gate exactly:

```c
else {
  pf_last_min = pf[n_pf].min;
  pf[n_pf].hc = MurmurHash3(pf[n_pf].min);
  if (idx_opts.minimum_acceptable_hash_value &&
      pf[n_pf].hc < idx_opts.minimum_acceptable_hash_value)
    pf[n_pf].skip = true;          // -M rejects it; fetch nothing
  else
    hash->Prefetch(pf[n_pf].hc);
}
```

`PfSlot` gains a `skip` flag; pass 2 reads it instead of recomputing the test. The
hash is still computed — the threshold test needs it — so this removes memory
traffic, not instructions. Build as `bin/classify_mskip` and keep `classify_nodup`
for A/B; the gap between the two binaries on one subsampled DB is the value of this
change, and decides whether it belongs in the default build.

## 7. Measurement protocol, and the constraint on it

**Correctness is not byte-identity here** — `-M` changes results by design. The only
byte-identity check is the no-op case: `classify_mskip` on `eskape_32bit_fork`
(threshold 0) must match `classify_nodup` exactly. After that the bar is the accuracy
table.

This box has a live defect: it returns **silently wrong output at `-p 16` with exit
code 0**. Five runs of an *unmodified* binary on identical input gave 3 correct, 1
wrong-with-exit-0 (44,126,678 vs 44,126,663 bytes), 1 SIGSEGV. `-p 1` is
byte-identical every time. So:

- establish a `-p 1` reference md5 per (binary, DB) pair
- run extra `-p 16` reps and **discard any whose md5 differs from it**
- report **instruction counts** as primary — stable to ~0.1%, while elapsed on this
  box is bimodal (1.55–2.83 s for the same binary)
- iterate on `perpod5/sample_50mb.fastq` (0.81 s), confirm on pod5_2

Accuracy per `CACHE_TABLE_ANALYSIS.md` Addendum 3: `clsfd%` from classify's stderr,
plus S.aureus / E.faecium false-positive counts from the `-R` report, against
`eskape_32bit_fork` as ground truth. Run **both `-g 2` and `-g 1`** on the two most
promising databases — per §4(b) that axis may dominate M.

## 8. What to expect, and what could be wrong

**Expect −27% to −32%** in the useful window, plus an unquantified residency bonus
once `hash.k2d` drops below 16 MB. Not Standard-8's margin — that came from an
unusually expensive baseline, not from a better database.

**`-B` and `-M` are substitutes, not complements.** Both attack the same lookup path.
`SUBSAMPLING_FINDING.md` §13 predicts a `-B` sweep on a subsampled DB will look
disappointing for reasons unrelated to prefetch working — the lookup path is only 8%
of `standard_8gb`'s runtime against 45.4% of `fork`'s, so Amdahl caps prefetch near
8% there. Expect the combined gain well below the product of the two.

**Risks, in order:**

1. **The model has one fitted parameter, one fit point, one held-out check.** It is
   used only to choose where to sample. The proposed sweep spans 12–20 MB, wide
   enough that a mis-fit moves the optimum *within* the range rather than outside it.
2. **Independence is assumed.** Hit groups are treated as independent Bernoulli
   draws. `fmix64` makes the *hashes* independent, but hit groups are runs over a
   sliding window and may be spatially correlated along a read. Correlation would
   make the real loss **worse** than modelled, not better.
3. **pod5_15 is one file.** The prior `-M` measurement used it alone too. Confirm on
   at least one other pod5 before treating any M as the project default.
4. **The length floor is a proxy.** "Reads ≥ 287 bp are the classified population"
   fits the data but is not directly observed. Measuring the true per-read
   `minimizer_hit_groups` distribution with `scratch_probe/` would replace the whole
   model with counts, and is the single cheapest way to strengthen this.

**The `-M 1265825` probe is expected to fail** at ~63% classified. That is the point:
seven minutes of build time converts "Standard-8's ratio does not transfer" from a
prediction into a measurement.

---

## Reproduction

```bash
# threshold and implied library size for any database
python3 -c "
import struct
v = struct.unpack('<8Q', open('databases/standard_8gb/opts.k2d','rb').read())
f = 1 - v[5]/((1<<64)-1)
print('k=%d l=%d  threshold=0x%016x' % (v[0], v[1], v[5]))
print('keeps %.4f%%  -> implied uncapped capacity %.0f cells' % (100*f, 2e9/f))"

# the sensitivity model
python3 -c "
L=[len(l.strip()) for i,l in enumerate(open('perpod5/pod5_15.fastq')) if i%4==1]
rho=206485766/6047.42e6
sel=[rho*l for l in L if l>=287.0]
def loss(f,g=2):
    t=0
    for H in sel:
        p=(1-f)**H; s=p
        for k in range(1,g): p=p*(H-k+1)/k*f/(1-f); s+=p
        t+=s
    return t/len(sel)
for M in (5000000,4000000,3500000,3000000,2000000,1265825):
    print('%-9d keep %5.2f%%  loss %6.3f%%  clsfd %5.2f%%' %
          (M, 100*M/12200000, 100*loss(M/12200000), 83.39*(1-loss(M/12200000))))"
```
