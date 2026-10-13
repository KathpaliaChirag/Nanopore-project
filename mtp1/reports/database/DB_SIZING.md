# Sizing the eskape database: every size that is possible, and how to pick one

**One flag (`build_db -M`) sets the database size exactly. This document gives the
formula, every reachable size for 32- and 24-bit cells, the measured accuracy at each,
and a stopping rule for choosing.**

| | |
|---|---|
| Date | 2026-09-08 |
| Baseline | `databases/eskape_32bit_fork` — 48,800,032 B, `-c 12200000 -k 35 -l 31 -C 32` |
| Library | `databases/eskape_cs/library/*.fna` — 6 files, 17 sequences, 28,061,107 bp |
| Accuracy workload | `perpod5/pod5_15.fastq` — 30,378 reads, 90.55 Mbp |
| Classify settings | `-T 0`, **`-g` filter off** (see §2) |
| Baseline accuracy | **83.94%** classified |
| Machine | i7-11700, 8C/16T, 16 MiB L3 |

Accuracy figures are **measured**, not modelled — see §6 for the method. Speed figures
are a fitted model and are labelled as such.

---

## 1. The size formula

```
hash.k2d = 32 + bytes_per_cell x M
```

Exact — no rounding, no padding, no alignment slack:

- `build_db.cc:83` — `actual_capacity = opts.maximum_capacity`, so `-M` is used verbatim
  as the table length. Nothing rounds it to a power of two or a page boundary.
- `compact_hash.h:346-350` — the file is four `uint64` header fields
  (`capacity_`, `size_`, `key_bits_`, `value_bits_`) followed by
  `sizeof(*table_) * capacity_` bytes.
- The cell structs are `__attribute__((packed))`.

Note `capacity_` is written, **not** the occupied count: an empty table costs the same
as a full one. That is what makes the size deterministic before you build.

### Bytes per cell

| `-C` | struct | bytes | `key_bits` (= cell bits − 6) |
|---|---|---:|---:|
| 32 | `CompactHashCell` | **4** | 26 |
| 24 | `CompactHashCell24` (`uint8_t b[3]`) | **3** | 18 |
| 20 | `CompactHashCell20` (`uint8_t b[3]`) | **3** | 14 |
| 16 | `CompactHashCell16` | **2** | 10 |

`value_bits` = 6 for eskape (`bits_for_taxid`, from the taxonomy node count).
**`key_bits` does not depend on `M`** — shrinking the database never shortens the
fingerprint, so it does not raise the false-positive rate on its own.

> **`-C 20` is strictly dominated — never build it.** It uses the same 3-byte struct as
> `-C 24`, so `eskape_20bit/hash.k2d` is byte-identical in size to `eskape_24bit`
> (36,600,032 B), but with 4 fewer fingerprint bits — 16x the false-positive rate for
> zero saving.

## 2. What `-g` does, and why this document assumes it is off

`-g NUM` is "minimum number of hit groups needed for call" (`classify.cc:1234`). A *hit
group* is a run of consecutive identical minimizers that hit the database — the counter
at `classify.cc:900` increments only when the minimizer differs from the previous one
**and** the lookup succeeded. It answers "how many separate places in this read matched?"

It runs last, and can only veto (`classify.cc:939-941`):

```c
call = ResolveTree(hit_counts, taxonomy, total_kmers, opts);
if (call && minimizer_hit_groups < opts.minimum_hit_groups)
  call = 0;
```

**Measured on pod5_15, `-p 1`, byte-identical md5s:**

```
(flag omitted)  C=25498  83.94%   md5 b236e2a47982bd79
-g 0            C=25498  83.94%   md5 b236e2a47982bd79
-g 1            C=25498  83.94%   md5 b236e2a47982bd79
-g 2            C=25331  83.39%   md5 cb306f70b967011b
-g 3            C=25208  82.98%   md5 02ce8ce1ed53faff
```

- **Omitting the flag gives `-g 0`** (`classify.cc:114`), which disables the veto:
  `minimizer_hit_groups < 0` is never true.
- **`-g 0` is identical to `-g 1`** because a call structurally requires at least one hit
  group — `hit_counts` only increments for a non-zero taxon, and the first minimizer of a
  read is never marked `dup`, so any non-zero taxon has already counted one group.
- **Beware the two defaults:** the raw `classify` binary defaults to **0**, but the
  `kraken2` wrapper script defaults to **2** and always pushes it (`scripts/kraken2:50`,
  `:141`).

**Why this matters enormously for sizing.** With the filter off, a read is lost only if
*every* one of its `H` hit groups is dropped:

```
   -g 2:   P(lost) = (1-f)^H  +  H*f*(1-f)^(H-1)
   -g 1:   P(lost) = (1-f)^H                        <- second term gone
```

Mean `H` is **459**, so a typical read is untouchable and the losses come entirely from
the low-`H` tail. Measured, dropping the filter is worth **exactly 2x the database size**
at equal accuracy. It costs nothing and needs no rebuild.

Its normal price is false positives — with the filter off, one stray hit classifies a
read. That is safe here only because `-C 32`'s 26-bit fingerprint yields roughly **3**
false-positive hits across the whole file. It would be reckless at `-C 16`.

## 3. What sizes are possible

`M` is an integer, so sizes step by `bytes_per_cell` — 4 B at `-C 32`, 3 B at `-C 24`.
That is effectively continuous. The only bound is `build_db.cc:80`:

```c
double frac = opts.maximum_capacity * 1.0 / opts.capacity;
if (frac > 1)
  errx(EX_DATAERR, "maximum capacity larger than requested capacity");
```

so **1 <= M <= 12,200,000** (the `-c` value eskape is built with):

| `-C` | smallest | largest |
|---|---|---|
| 32 | 36 B | **48,800,032 B (48.80 MB)** |
| 24 | 35 B | **36,600,032 B (36.60 MB)** |

Everything downstream follows from one number, the keep fraction:

```
f    = M / 12,200,000                      fraction of minimizers stored
T    = (1 - f) * (2^64 - 1)                threshold written to opts.k2d word 5
load = 8,903,388 / 12,200,000 = 0.7298     CONSTANT at every M
```

`MurmurHash3` here is `fmix64`, a bijection with uniform output, so `hash >= T` selects
exactly `f` of minimizer space — deterministically, statelessly, and identically at
build time (`build_db.h:209`) and query time (`classify.cc:875`).

**Load factor is preserved at every `M`**, because occupied cells scale with `M` too
(`8,903,388 x f` entries in `M` slots). Probe chains therefore do not degrade as the
database shrinks. This is what makes size a clean single variable.

## 4. Every size, both cell widths

### `-C 32` — 4 bytes/cell, `key_bits` = 26, max 48,800,032 B (48.80 MB)

| target | `-M` | exact bytes | keep | clsfd | Δpp | pred. speed | threshold |
|---|---:|---:|---:|---:|---:|---:|---|
| 48.80 MB | 12,199,992 | 48,800,000 | 100.00% | 83.94% | -0.00 | -0.0% | `0x00000b005f3b3800` |
| 36.00 MB | 8,999,992 | 36,000,000 | 73.77% | 83.77% | -0.17 | -6.0% | `0x4325d03f52a42000` |
| 32.00 MB | 7,999,992 | 32,000,000 | 65.57% | 83.69% | -0.25 | -7.9% | `0x58219de2feb4f000` |
| 24.00 MB | 5,999,992 | 24,000,000 | 49.18% | 83.52% | -0.42 | -11.7% | `0x8219392a56d68000` |
| 20.00 MB | 4,999,992 | 20,000,000 | 40.98% | 83.36% | -0.58 | -13.6% | `0x971506ce02e74800` |
| 16.00 MB | 3,999,992 | 16,000,000 | 32.79% | 83.17% | -0.77 | -15.5% | `0xac10d471aef81000` |
| 12.00 MB | 2,999,992 | 12,000,000 | 24.59% | 82.77% | -1.17 | -17.2% | `0xc10ca2155b08e000` |
| 10.00 MB | 2,499,992 | 10,000,000 | 20.49% | 82.48% | -1.46 | -18.0% | `0xcb8a88e731114000` |
| 8.00 MB | 1,999,992 | 8,000,000 | 16.39% | 82.03% | -1.91 | -18.8% | `0xd6086fb90719a800` |
| 6.00 MB | 1,499,992 | 6,000,000 | 12.30% | 81.33% | -2.61 | -19.6% | `0xe086568add220800` |
| 5.00 MB | 1,249,992 | 5,000,000 | 10.25% | 80.75% | -3.19 | -20.0% | `0xe5c549f3c8264000` |
| 4.00 MB | 999,992 | 4,000,000 | 8.20% | 79.82% | -4.12 | -20.4% | `0xeb043d5cb32a7000` |
| 3.00 MB | 749,992 | 3,000,000 | 6.15% | 77.85% | -6.09 | -20.8% | `0xf04330c59e2ea000` |

### `-C 24` — 3 bytes/cell, `key_bits` = 18, max 36,600,032 B (36.60 MB)

| target | `-M` | exact bytes | keep | clsfd | Δpp | pred. speed | threshold |
|---|---:|---:|---:|---:|---:|---:|---|
| 36.60 MB | 12,199,989 | 36,599,999 | 100.00% | 83.94% | -0.00 | 1.7% | `0x00000f2082f17000` |
| 32.00 MB | 10,666,656 | 32,000,000 | 87.43% | 83.86% | -0.08 | -1.1% | `0x202cd283fe469000` |
| 24.00 MB | 7,999,989 | 23,999,999 | 65.57% | 83.69% | -0.25 | -5.9% | `0x5821a203226b2000` |
| 20.00 MB | 6,666,656 | 20,000,000 | 54.64% | 83.58% | -0.36 | -8.4% | `0x741c0912ae89b800` |
| 16.00 MB | 5,333,322 | 15,999,998 | 43.72% | 83.41% | -0.53 | -10.8% | `0x90167182468fb000` |
| 12.00 MB | 3,999,989 | 11,999,999 | 32.79% | 83.17% | -0.77 | -13.1% | `0xac10d891d2ae4800` |
| 10.00 MB | 3,333,322 | 9,999,998 | 27.32% | 82.92% | -1.02 | -14.1% | `0xba0e0cc99eb14000` |
| 8.00 MB | 2,666,656 | 8,000,000 | 21.86% | 82.58% | -1.36 | -15.2% | `0xc80b3fa15ecce000` |
| 6.00 MB | 1,999,989 | 5,999,999 | 16.39% | 82.03% | -1.91 | -16.3% | `0xd60873d92acfd800` |
| 5.00 MB | 1,666,656 | 5,000,000 | 13.66% | 81.56% | -2.38 | -16.9% | `0xdd070d450adda800` |
| 4.00 MB | 1,333,322 | 3,999,998 | 10.93% | 80.96% | -2.98 | -17.4% | `0xe405a810f6d2d800` |
| 3.00 MB | 999,989 | 2,999,999 | 8.20% | 79.82% | -4.12 | -17.9% | `0xeb04417cd6e0a000` |


## 5. The math for choosing a size

Both curves bend, but in **opposite directions**:

- **Speed saturates.** Once the lookups are gone there is nothing left to remove. The
  lookup path is only 26.5% of runtime at `-B 29`, and a skipped lookup still costs the
  hash and the compare (~25% of a full one). The asymptote is near −21%.
- **Accuracy accelerates.** `(1-f)^H` is flat while `f` is large, then collapses.

Separately, table size barely matters. **Measured** on the three existing databases,
which share capacity 12,200,000 and do byte-identical work (29,054,665 lookups on all
three), 5 interleaved reps at `-B 29`:

| table | p=1 | p=16 |
|---:|---:|---:|
| 23.27 MiB | **−0.84%** | **−1.57%** |
| 34.90 MiB | +1.74% | +2.54% |
| 46.54 MiB | 0.00% | 0.00% |

A 2x size cut at constant work buys **1.57%**. And `cycle_activity.stalls_l3_miss` is
only **1.3–2.9%** of cycles, which caps any residency gain — you cannot save more stall
cycles than exist. **So the gain from `-M` is the lookup cut, not L3 residency.**

Dividing the two curves gives the decision rule:



| step | `-C 32` | `-C 24` |
|---|---:|---:|
| 24 → 20 MB | 11.79 | 22.04 |
| 20 → 16 MB | 9.93 | 15.02 |
| 16 → 12 MB | 4.29 | 9.28 |
| 12 → 10 MB | 2.81 | 4.29 |
| 10 → 8 MB | 1.81 | 3.19 |
| 8 → 6 MB | 1.16 | 1.99 |
| 6 → 5 MB | 0.70 | 1.16 |
| 5 → 4 MB | 0.44 | 0.90 |
| 4 → 3 MB | 0.21 | 0.48 |

**The ratio falling through 1.0 is the stopping rule** — below it you pay more accuracy
than you buy speed. That happens at **~6 MB for `-C 32`** and **~5 MB for `-C 24`**.
Above 16 MB the exchange is 10–20% per pp, essentially free. The interesting region is
where the ratio runs 2–4.

### Cell width at matched size

At the same file size `-C 24` holds 4/3x more cells, so it keeps more minimizers, and
its advantage **grows as you shrink**:

| file size | `-C 32` | `-C 24` | gain |
|---|---:|---:|---:|
| 16 MB | 83.17% | 83.41% | +0.24 pp |
| 12 MB | 82.77% | 83.17% | +0.40 pp |
| 8 MB | 82.03% | 82.58% | **+0.55 pp** |

Against that, `-C 24` carries a **measured +3.5% instructions / +2.5% cycles** penalty:
3-byte cells straddle 64 B lines (64/3 = 21.33 cells per line). At full size it is
*slower* than `-C 32` despite being 25% smaller. It only nets ahead below ~12 MB.

**The one unmeasured risk.** `-C 24`'s 18-bit fingerprint implies ~700 false-positive
hits file-wide against ~3 at `-C 32`. With the `-g` filter off, a single stray hit
classifies a read. That estimate is calculated (`6.27 / (frac * 2^key_bits)`), not
measured — one `-C 24` build settles it by comparing S. aureus / E. faecium counts
against 0 / 1.

## 6. How the accuracy figures were measured

**No builds were needed.** `-M` can be simulated exactly by copying a database's
`opts.k2d`, patching word 5 with the target threshold, and querying the *full* table:

- a minimizer with `hc >= T` is stored in both the real and simulated database
- load factor is identical in both (0.7298), so probe chains match
- `compacted_key = hc >> (64 - key_bits_)` is the **top** bits, so a stored entry with
  `hc < T` can never match a query with `hc >= T`

**Validation:** it reproduces the one real `-M` build on record — 24-bit `-M 4,000,000`,
recorded at 82.07% — to **0.01 pp** (82.06%).

The method understates false positives by exactly `1/frac`, which is why §5's FP note
needs a real build. It is exact for classification rate at `-C 32` and `-C 24`.

## 7. The commands

### Recommended build — 10 MB

```bash
cd /home/dell/summer
OUT=databases/eskape_C32_M2500000
mkdir -p "$OUT"
cat databases/eskape_cs/library/*.fna | kraken2_bin/build_db \
    -H "$OUT/hash.k2d" -t "$OUT/taxo.k2d" -o "$OUT/opts.k2d" \
    -n databases/eskape_cs/taxonomy \
    -m databases/eskape_cs/seqid2taxid.map \
    -c 12200000 -k 35 -l 31 -p 1 -C 32 -M 2500000 \
    2>&1 | tee "$OUT/build.log"
```

The only difference from the baseline eskape build is `-M 2500000`. Everything else —
`-c 12200000 -k 35 -l 31 -C 32` — is held identical so the comparison is single-variable.

**`-p 1` is not a typo:** `build_db` segfaults at `--threads 16` on this box. The library
is 28 Mbp, so a build is ~7 minutes.

### Any other size

Pick `M` from §4, or compute it from a target size:

```bash
# M for a target size in MB, at a given cell width
python3 -c "
import sys
mb, C = float(sys.argv[1]), int(sys.argv[2])
B = {32:4, 24:3, 20:3, 16:2}[C]
M = min(int((mb*1e6 - 32)//B), 12200000)
print('-C %d -M %d   -> %d bytes (%.2f MB), keep %.2f%%, threshold 0x%016x'
      % (C, M, B*M+32, (B*M+32)/1e6, 100*M/12200000,
         int((1-M/12200000)*((1<<64)-1))))" 10 32
```

### Build several at once

```bash
cd /home/dell/summer
for spec in "32 6000000" "32 4000000" "32 3000000" "32 2500000" "24 2666666"; do
  set -- $spec; C=$1; M=$2
  OUT=databases/eskape_C${C}_M${M}; mkdir -p "$OUT"
  cat databases/eskape_cs/library/*.fna | kraken2_bin/build_db \
      -H "$OUT/hash.k2d" -t "$OUT/taxo.k2d" -o "$OUT/opts.k2d" \
      -n databases/eskape_cs/taxonomy -m databases/eskape_cs/seqid2taxid.map \
      -c 12200000 -k 35 -l 31 -p 1 -C "$C" -M "$M" 2>&1 | tee "$OUT/build.log"
done
```

### Verify every build

Both outputs are predictable in closed form, so a bad build is caught immediately:

```bash
python3 -c "
import struct, sys, os
d, M, C = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
B = {32:4, 24:3, 20:3, 16:2}[C]
v = struct.unpack('<8Q', open(d+'/opts.k2d','rb').read())
sz, exp = os.path.getsize(d+'/hash.k2d'), B*M+32
print('size %9d  expect %9d  %s' % (sz, exp, 'OK' if sz==exp else 'FAIL'))
print('thr  0x%016x  expect 0x%016x  %s' % (v[5], int((1-M/12200000)*((1<<64)-1)),
      'OK' if v[5]==int((1-M/12200000)*((1<<64)-1)) else 'FAIL'))
" databases/eskape_C32_M2500000 2500000 32
```

Expected for the 10 MB build: `hash.k2d` = 10,000,032 bytes, threshold
`0xcb8a7de6d1d60800`.

### Classify against it

**Do not pass `-g`** — that is the whole point of §2:

```bash
D=databases/eskape_C32_M2500000
scratch_lookaside/bin/classify_nodup \
    -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 1 -T 0 -B 29 perpod5/pod5_15.fastq > /dev/null
```

Keep `-T 0`. **`-M` is structurally incompatible with `-T > 0`**: `classify.cc:763`
computes `required_score = ceil(confidence_threshold * total_minimizers)` where
`total_minimizers` counts the positions `-M` skipped, so confidence collapses in
proportion to the keep fraction. At `-T 0.10`, `M = 2,000,000` gives **32.53%** against
a 78.13% baseline.

## 8. Caveats

- **Speed figures are modelled, not measured.** No sub-16 MiB eskape table has ever been
  built on this box; every point below 23 MiB is an extrapolation from three databases
  all >= 23 MiB. The model reproduces the one historical `-M` datapoint within 4 pp.
- **Expect ~13-20%, not the 26.7% in older notes.** That figure was measured against a
  non-prefetching baseline. Prefetch and `-M` are substitutes — both attack the lookup
  path — so `-M`'s benefit against today's `-B 29` default is roughly half.
- **Aggregate `clsfd%` understates the damage to rare taxa.** E. cloacae (n=135) was
  already at 78.5% retention when the aggregate was 95.8%. For an ESKAPE panel that is
  the metric that matters, and it argues for stopping at 10-12 MB rather than at the
  ratio knee near 6 MB.
- **One sample.** All accuracy figures are pod5_15. Confirm the chosen size on a second
  pod5 before adopting it as a default.
- **This box returns silently wrong output at `-p 16` with exit code 0.** Do all accuracy
  work at `-p 1`, which is byte-identical every run.
- **Does not generalise.** These ratios are a property of a 28 Mbp / 17-sequence
  reference, not of kraken2.
