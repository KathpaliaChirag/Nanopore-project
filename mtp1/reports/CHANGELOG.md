# What we changed — running log

Newest first. Plain words. Every entry says **what** changed, **why**, and
**what it means**.

---

## 2026-09-09 — splitting the cache misses: the read file is a fixed floor, its share is not

**What:** no code change. A measurement that settles what the cache counters in the size
ladder actually mean, and corrects the explanation given earlier the same day.

**The method — a zero-lookup run.** The `-M` threshold lives in `opts.k2d` as a plain
64-bit field, so a copy of that file with the threshold set to its maximum makes every
minimizer fail the test at `classify.cc:896-898`:

```
normal    word5 (threshold) = 0xd6086fb90719a800
patched   word5 (threshold) = 0xffffffffffffffff
```

`hash->GetWithHash()` is then never called. The run still opens the file, reads it, parses
FASTQ, scans every minimizer and computes every hash — it simply never touches the table.
Confirmed by the output: **24,919 classified normally, 0 classified patched.** Same binary,
no recompilation, only a data value differs, and the skipped branch is the one `-M` already
takes for 83.6% of minimizers in production.

Subtracting the two runs separates the halves exactly:

```
full run     =  read + parse + scan + lookups
patched run  =  read + parse + scan
difference   =  lookups alone
```

**Numbers.** 8 MB index, pod5_2, `-p 16`:

| component | cache-refs | cache-misses | miss rate | LLC-loads | LLC-misses | LLC rate |
|---|---:|---:|---:|---:|---:|---:|
| full run | 357,819,564 | 153,686,153 | 43.0% | 56,898,814 | 23,093,946 | 40.6% |
| **read + scan** | 223,995,450 | **115,563,919** | **51.6%** | 19,975,557 | 13,748,053 | **68.8%** |
| lookups | 133,824,114 | 38,122,234 | **28.5%** | 36,923,257 | 9,345,893 | 25.3% |

**What it means.** **75% of all cache misses occur with zero index lookups.** And the
read-only run has a *higher* miss rate than the full run — 51.6% against 43.0% — because
**the index lookups miss far less often than the read stream does**: 28.5% versus 51.6%.
Reading the file is the cache-hostile part of this program, not searching the table.

The cause is physical. pod5_2 is 1,038,110,684 bytes = **16,220,479 cache lines**, each
touched exactly once, so every one is a compulsory miss. The 8 MB index is 125,000 lines
against the 262,188 a 16 MiB L3 holds, and each line is revisited roughly 200 times across
the run, so a large share of its accesses hit.

**This resolves the apparent contradiction** in the throughput tables — the miss rate
climbing while the index shrinks and the machine plainly does less work. Shrinking the index
removes the *low*-miss-rate accesses (28.5%), leaving a mix increasingly dominated by the
read stream (51.6%), so the average is pulled toward that floor. **The rate rises because
the good accesses are the ones being removed.** Absolute misses fall throughout.

It also explains why the accuracy/size curve has no knee at the L3 boundary: the index never
"fits and stays", because a gigabyte of sequence streams past a 16 MiB cache continuously —
and it does not need to. The benefit of `-M` is *performing fewer lookups*, not cache
residency. The gain scales with the fraction of lookups removed, not with whether the index
clears a cache threshold.


**Extended to three index sizes.** The 8 MB result above does not generalise, and saying
"most cache misses come from the read file" without qualification would be wrong. Repeating
the zero-lookup measurement at 8, 24 and 48.80 MB (`result/nolookup_decomp/`, medians of 3):

| index | read+scan misses | its share | lookup misses | lookup miss rate | lookups, % of runtime |
|---|---:|---:|---:|---:|---:|
| 8.00 MB | 115,095,736 | **75%** | 37,694,372 | **28.3%** | 21% |
| 24.00 MB | 115,774,707 | **42%** | 160,344,821 | 53.5% | 44% |
| 48.80 MB | 116,806,903 | **25%** | 344,785,205 | **63.8%** | 50% |

**The read component is genuinely fixed** across a six-fold range of index size — the same
file, read the same way, whatever the index holds:

```
cache-misses   115,095,736 · 115,774,707 · 116,806,903    0.7% spread
LLC-misses      13,746,005 ·  13,706,832 ·  13,814,386    0.5% spread
LLC miss rate       69.0%  ·      69.0%  ·      69.0%
```

Its LLC-misses are **85% of the file's 16,220,479 cache lines** at every size — the
compulsory floor.

**Its share, though, moves from 75% to 25%.** At 48.80 MB the lookups produce 344.8 million
of the 461.6 million misses, so the read file is emphatically *not* the dominant source
there. The claim is a property of the recommended configuration, not of the program.

**And the lookup miss rate crosses over**: 28.3% → 53.5% → 63.8%. At 8 MB the index is
125,000 cache lines against L3's 262,188 and each is revisited ~200 times, so it misses
*less* than the read stream. At 48.80 MB it is 762,500 lines — 2.9x oversubscribed — and it
misses more. That crossing is why the whole-program rate rises with index size while each
component behaves sensibly.

**Supersedes** the earlier explanation in the Day 1 artifact, which inferred read-stream
dominance from misses tracking file size at `-p 1` (92-93% agreement). That inference was
right but indirect; this measures it. Artifact section 09 now carries the decomposition.

---

## 2026-09-09 — full `-B 29` ladder re-run with the gated binary

**What:** no code change — a measurement completing the matched set. `result/B29_gated/`,
168 runs, 14 databases × 4 event groups × 3 reps, using the `-M`-gated binary.

**Numbers.** pod5_2, `-p 16 -T 0 -B 29`, medians of 3, 32-bit ladder:

| index | keep | classified | cycles | IPC | wall s | DRAM % | demand % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 48.80 MB | 100% | 84.78% | 113,924,437,804 | 1.487 | 2.490 | 24.8% | 43.1% |
| 32.00 MB | 65.57% | 84.49% | 121,604,502,442 | 1.565 | 2.651 | 31.7% | 39.8% |
| 24.00 MB | 49.18% | 84.31% | 119,937,438,466 | 1.572 | 2.601 | 39.4% | 39.2% |
| 20.00 MB | 40.98% | 84.15% | 115,756,391,798 | 1.597 | 2.524 | 42.6% | 40.5% |
| 16.00 MB | 32.79% | 83.93% | 109,874,306,444 | 1.631 | 2.411 | 45.2% | 41.8% |
| 12.00 MB | 24.59% | 83.52% | 103,739,177,914 | 1.655 | 2.266 | 49.8% | 40.5% |
| 10.00 MB | 20.49% | 83.19% | 100,509,953,939 | 1.664 | 2.196 | 51.1% | 39.1% |
| 8.00 MB | 16.39% | 82.77% | 96,841,437,125 | 1.676 | 2.119 | 52.8% | 38.8% |

"DRAM %" is `LLC-load-misses / LLC-loads` — traffic, including prefetcher fills.
"demand %" is `mem_load_retired.l3_miss / (l3_hit + l3_miss)` — retired demand loads only.
**The two disagree by up to 14 points and move in opposite directions**, because prefetching
converts demand misses into prefetcher traffic. Reporting either alone is misleading.

**What it means.** Gating helps consistently but slightly: 96.84 G against the ungated
97.76 G at 8 MB (−0.9%), and 113.92 G against 115.16 G at 48.8 MB (−1.1%). The picture is
otherwise unchanged — at 8 MB, no `-B` at all is **88.66 G**, still ~9% ahead of the best
prefetched result, while at 48.8 MB prefetching is worth 19%.

`-B 29` remains **non-monotone**: 32 MB (121.6 G) is slower than the full 48.8 MB index
(113.9 G). The no-`-B` ladder has no such reversal, which is why it is the configuration
reported in the Day 1 artifact.

## 2026-09-09 — gate the prefetch on the `-M` threshold: −6.0% wasted fetches, −0.46% runtime

**What:** `scratch_lookaside/src/classify.cc`. The `-M` threshold test moves from pass 2 into
pass 1, so the prefetch is only issued for minimizers that will actually be looked up.
`PfSlot` gains a `skip` flag; pass 2 reads it instead of recomputing the compare.

```c
pf[n].hc = MurmurHash3(pf[n].min);
if (idx_opts.minimum_acceptable_hash_value &&
    pf[n].hc < idx_opts.minimum_acceptable_hash_value)
  pf[n].skip = true;              // -M rejects it: fetch nothing
else
  hash->Prefetch(pf[n].hc);
```

Binary: `scratch_lookaside/bin/classify_mskip`. Output byte-identical to upstream on both a
thresholded index (`eskape_C32_08MB`) and an un-thresholded one (`eskape_32bit_fork`), with
and without `-B`.

**Why:** on a subsampled index the large majority of minimizers fail the threshold and are
never looked up, yet pass 1 was issuing a prefetch for every non-duplicate one — fetching
lines nobody reads. Unlike duplicate prefetches (gated 2026-09-02), these target lines that
are genuinely **not** resident, so each one is a wasted random DRAM fetch.

**Numbers.** pod5_2, `-p 16`, medians of 3, against the ungated `-B 29` binary:

| index | arm | cycles | instructions | LLC-misses | vs ungated |
|---|---|---:|---:|---:|---:|
| 8 MB | ungated `-B 29` | 97,257,002,336 | 164,097,418,416 | 15,899,154 | — |
| 8 MB | **gated `-B 29`** | 96,807,110,204 | 162,290,960,795 | **14,948,816** | **−0.46%** |
| 8 MB | no `-B` | 88,308,093,971 | 152,336,064,566 | 20,805,182 | **−9.20%** |
| 48 MB | ungated `-B 29` | 114,922,946,733 | 170,014,919,782 | 23,225,929 | — |
| 48 MB | **gated `-B 29`** | 114,285,674,430 | 169,415,502,215 | **19,767,568** | **−0.55%** |

**What it means.** The gating does exactly what it should — **6.0% fewer DRAM fetches** at
8 MB and 1.8 billion fewer instructions — and it helps at both ends of the ladder, so it is
strictly better than the ungated version. But it recovers almost nothing in runtime.

Of the ~10.5 billion instructions `-B 29` adds over no prefetch, only **1.8 billion are the
prefetch itself**; the remaining **8.7 billion is the two-pass bookkeeping** — writing each
minimizer, hash and flags into the slot array and reading them back — which runs whether or
not a prefetch fires, because pass 2 must still walk the array. And the wasted prefetches
were nearly free in cycles anyway: they are fire-and-forget, and at 8 MB only 2.65% of
cycles were stalled on L3 in total.

**Running with no `-B` at all remains 8.8% faster than the gated version at 8 MB.** The
inefficiency was real; it was not the expensive one. To recover the rest the two-pass
structure has to go, which is what omitting `-B` already does.

Raw data: `result/mskip/`. Recorded in the Day 1 presentation artifact, section 10.

## 2026-09-09 — `-p` retune: 16 stays, but scaling efficiency is only 36%

**What:** no code change, no setting change. `-p 16` is already optimal. The value is in
what the sweep exposes about item A.

**Why it was checked:** every measurement in this project used `-p 16` without ever
testing it. With a serialized reader and 8 physical cores, hyperthreading was a plausible
net negative.

**Numbers.** pod5_2, medians of 3, each DB at its own best `-B` (8 MB: none; 48 MB: `-B 64`):

| `-p` | 8 MB wall | speedup | eff% | cycles | cpu-ms |
|---|---:|---:|---:|---:|---:|
| 1 | 11.259 | 1.00x | 100% | 5.466e10 | 11,249 |
| 2 | 6.233 | 1.81x | 90% | 5.497e10 | 12,425 |
| 4 | 3.425 | 3.29x | 82% | 5.504e10 | 13,548 |
| 6 | 2.808 | 4.01x | 67% | 5.578e10 | 16,503 |
| 8 | 2.322 | 4.85x | 61% | 5.615e10 | 18,185 |
| 12 | 2.121 | 5.31x | 44% | 7.516e10 | 24,542 |
| **16** | **1.932** | **5.83x** | 36% | 8.888e10 | 29,280 |

48 MB behaves the same: best at `-p 16` (2.477 s), 5.98x, 37% efficiency.

**The hypothesis was wrong** — hyperthreading is not hurting; wall time falls all the way
to 16. Keep `-p 16`.

**What the sweep actually shows.** Scaling is badly inefficient: 16 threads on 8 physical
cores give **5.83x**, and even at `-p 8` — one thread per physical core, no hyperthreading
— it is only **4.85x (61%)**.

**Cycles rise 63% for byte-identical work**: 5.466e10 at `-p 1` -> 8.888e10 at `-p 16`.
CPU-ms goes 11,249 -> 29,280, a **2.6x inflation** — worse than the 1.94x measured on the
read path alone, because this covers the whole program.

That is **item A quantified from a third independent direction** (after the 1.94x read-path
figure and the `cpu-ms` blowups seen when the 4 MB buffer and `-march=native` lengthened
the lock hold). Roughly 18 seconds of CPU is burned on contention at `-p 16`, and the knee
is visible by `-p 6`.

**Item A's ceiling is larger than estimated.** At even 80% scaling efficiency the 8 MB run
would take ~1.0 s instead of 1.93 s. Raw data: `result/p_retune/`.

## 2026-09-09 — `-B` retune: prefetch HURTS on subsampled databases

**What:** no code change — a measurement that invalidates the flag we have been shipping.
`-B 29` was used for every result in `ESKAPE_SIZE_LADDER.md` and both size sweeps.

**Why it was checked:** two sweeps run separately hinted that prefetch was worth −18% at
48 MB but **+9.9%** at 8 MB. With the BEFORE control arm now in place (no `-B` = genuine
no-prefetch single-pass path), the crossover could be measured directly in one run.

**Numbers.** pod5_2, `-p 16 -T 0`, medians of 3, vs **no prefetch** on the same DB:

| `-B` | 8 MB | 16 MB | 32 MB | 48 MB |
|---|---:|---:|---:|---:|
| none | — | — | — | — |
| 1 | +10.9% | +9.5% | +7.0% | +5.7% |
| 2 | +9.1% | +7.2% | +2.3% | −1.8% |
| 4 | +10.9% | +7.1% | −0.1% | −9.1% |
| 8 | +13.7% | +8.1% | −2.1% | −12.2% |
| 16 | +11.3% | +5.1% | −5.6% | −15.9% |
| 29 | +10.0% | +3.6% | −7.3% | −17.7% |
| 64 | +8.2% | +2.5% | **−7.6%** | **−18.0%** |

```
best per DB:  8 MB -> no prefetch     16 MB -> no prefetch
             32 MB -> -B 64 (−7.6%)   48 MB -> -B 64 (−18.0%)
```

**What it means.** Prefetch hides DRAM latency; `-M` subsampling removes the DRAM
accesses. Once the table is L3-resident there is no latency left to hide, and the prefetch
instructions plus two-pass bookkeeping become pure overhead. **The crossover sits between
16 MB and 32 MB — around the 16 MiB L3.**

Three consequences:

1. **On the 8 MB database we recommend, `-B 29` costs +10.0%.** Ship no `-B` there.
2. **`-B 29` was never optimal even where prefetch pays** — `-B 64` beats it at 32 MB
   (−7.6% vs −7.3%) and 48 MB (−18.0% vs −17.7%). 29 came from an older sweep.
3. **The best absolute config is 8 MB with no prefetch, 8.916e10 cycles** — faster than
   48 MB at its own best setting (`-B 64`, 1.148e11). The DB recommendation stands; the
   flag does not.

**Limits:** 3 reps, one input file, and `-p 16` on a binary with the item-F
non-determinism — though cycle counts, unlike output bytes, have been stable to ~1%.
Raw data: `result/b_retune/`.

## 2026-09-09 — kraken2's `-p 16` non-determinism is an UPSTREAM bug, not ours

**What:** no code change. A finding that corrects a claim this log has carried since
2026-09-02 (see that entry, now superseded).

**Why it matters:** every threaded measurement in this project came from a program that
intermittently produces wrong output under threads. We had blamed the machine.

**The test.** Unmodified `kraken2_bin/classify` — stock upstream, none of our code — 15
runs at `-p 16`, interleaved against our binary as a control, identical DB and input:

```
DB     : databases/eskape_sizes/eskape_C32_08MB
input  : perpod5/pod5_2.fastq  (151,591 reads / 499.98 Mbp)
-p 1 reference (both binaries agree): 034a3473f9cd390a

stock kraken2 : 13/15 correct, 2 WRONG -> 822275e06d893770, 354b792d37e26b13
our binary    : 15/15 correct
```

The two wrong md5s differ from each other, so it is not one deterministic corruption.

**Ruled out.** *Not our changes* — ThreadSanitizer on stock and on our fork returns
**identical race sets** (13 shared sites, zero unique to either); our 185 changed lines in
`classify.cc` touch nothing in the output or initialization paths, and `diff` of the
flagged region against upstream is empty. *Probably not hardware* — reproduces on demand
in stock, `-p 1` never fails across dozens of runs, no MCE or EDAC errors in the kernel
log. (Caveat: consumer non-ECC RAM cannot report single-bit errors, so that is not proof.)

**One real upstream defect found**, at `kraken2/src/classify.cc:652`:

```c
if (!outputs.initialized) {              // unsynchronized read
  InitializeOutputs(opts, outputs, reader1.file_format());
}
```

`InitializeOutputs` re-checks under `critical(output_init)`, so this is double-checked
locking on a plain `bool` (not `std::atomic<bool>`, `classify.cc:116`). Benign on x86 TSO
in practice — the flag is written last and stores are not reordered — and its failure mode
would be a null stream pointer, not 15 missing bytes. Worth reporting upstream anyway.

**What it means:** the `-p 1`-verify / md5-filter protocol we adopted is correct and
non-negotiable, and it is a **kraken2 property, not a property of this box**. TSan could
not settle the rest: 12 of the 13 sites are on data guarded by `omp critical`, and GCC's
`libgomp` is not instrumented, so TSan cannot see those locks. Full report and next steps:
`FUTURE_UPDATE.md` item F.

**Honest limit:** 15 reps is a small sample against an intermittent fault, and our binary
*has* failed in earlier sessions. Both are exposed; the rate is low. Do not read "15/15"
as immunity.

---

## 2026-09-09 — `-B` now selects between two modes, and omitting it means no prefetch

**What:** `scratch_lookaside/src/classify.cc`. The `-B` flag now switches between two
code paths rather than only setting a batch size:

```c
static int la_batch = 1;
static bool la_prefetch = false;   // BEFORE mode until -B is given

// -B parser:
la_prefetch = true;                // -B given: switch to the batched path
```

- **no `-B` — BEFORE / stock.** A single-pass loop: scan a minimizer, hash it,
  `GetWithHash()` blocks, count, record, next. No `PfSlot` array, no second pass, no
  prefetch.
- **`-B N` — AFTER / batched.** Pass 1 scans N minimizers and fires `Prefetch()` for each
  without waiting; pass 2 resolves them in order. Unchanged from before.

**Why:** we had no honest control arm. `-B 1` was assumed to be "the stock path" — a
comment in the source said exactly that — but it still issues a prefetch, just with no
distance to cover, and it still pays the two-pass bookkeeping. Measured, `-B 1` executes
**179.7 G instructions against stock's 158.0 G**, an 11% gap that has nothing to do with
prefetching. Every "prefetch is worth X%" figure in this log was measured against the
wrong baseline.

**Fidelity check:** BEFORE mode executes **158.97 G instructions against upstream's
158.00 G — within 0.6%** — and its output is byte-identical to upstream and to every `-B`
setting.

| mode | cycles | instructions |
|---|---:|---:|
| no `-B` (BEFORE) | 1.5329e11 | 1.5897e11 |
| `-B 1` | 1.5932e11 | 1.7970e11 |
| `-B 29` | 1.1850e11 | 1.6861e11 |
| upstream stock | 1.5130e11 | 1.5800e11 |

**What it means:** this is a **default-behaviour change** — running `classify` with no
`-B` no longer prefetches at all. It also produced the control-arm data in
`ESKAPE_SIZE_LADDER.md` §9, which overturned two headline findings there: subsampling is
not a net loss above 20 MB (that was an artifact of a `-B 29` baseline), and memory stalls
are 23.60% of cycles unprefetched, not the 1.88% we had recorded.

---

## 2026-09-09 — remove `shrink_to_fit()`: −1.7% for +156 MB, REVERTED

**What:** implemented, measured, reverted on request. No code change is in the tree.

The change was deleting one line in `seqreader.h`'s `copy_from_kseq`:

```c
seq.seq.assign(kseq_->seq.s, kseq_->seq.l);
seq.seq.shrink_to_fit();          // <- deleted
```

**Why:** `seqs_` is a reused vector, so `assign()` normally keeps the slot's capacity and
allocates nothing. `shrink_to_fit()` trims capacity to each sequence, forcing the next
longer read to reallocate and copy. Reads here span 117 bp to >5 kb, so it fired
constantly: profiling put malloc/free at **2.85%** of the read path, *more* than the 2.12%
spent copying. Removing it makes the reused vector act as a per-slot arena.

**Numbers.** pod5_2, `-p 16 -B 29`, medians of 5. Output byte-identical on two inputs.

| build | DB | cycles | instructions | peak RSS | vs base |
|---|---|---:|---:|---:|---:|
| base | 8 MB | 9.815e10 | 1.6265e11 | 1180 MB | — |
| no-shrink | 8 MB | **9.646e10** | 1.6279e11 | 1336 MB | **−1.72%** |
| base | 48 MB | 1.1596e11 | 1.6855e11 | 1187 MB | — |
| no-shrink | 48 MB | **1.1417e11** | 1.6876e11 | 1338 MB | **−1.55%** |

**What it means:** instructions barely moved (+0.09%) while cycles fell 1.7% — the same
instructions running better because the allocator stopped churning, not less work. The
cost is **+156 MB peak RSS (~13%)**: each of ~900 slots per thread now holds its
high-water capacity, across 16 threads. Negligible on this 31 GB box, a real tradeoff on a
constrained one, and it scales with thread count and the longest read.

## 2026-09-09 — incremental reverse complement: −6.4% measured, then REVERTED

**What:** implemented, measured, and reverted at the user's request. No code change is in
the tree. Recorded in full so it can be re-applied verbatim.

**The change was**, in `mmscanner.h` / `mmscanner.cc`: carry a `rc_lmer_` member updated
in lockstep with `lmer_` inside the character-loading loop, and use
`min(lmer_, rc_lmer_)` for the canonical l-mer instead of calling
`canonical_representation()`.

```c
// header: two new members
uint64_t rc_lmer_;
uint64_t rc_shift_;                      // = BITS_PER_CHAR_DNA * (l_ - 1)

// ctor: lmer_(0), rc_lmer_(0), and after toggle_mask_ &= lmer_mask_:
rc_shift_ = BITS_PER_CHAR_DNA * (l_ - 1);

// character-loading loop, ambiguous branch: also reset rc_lmer_ = 0
// character-loading loop, normal branch:
lmer_ |= lookup_code;
if (dna_)
  rc_lmer_ = (rc_lmer_ >> BITS_PER_CHAR_DNA)
           | ((uint64_t) (0x3 ^ lookup_code) << rc_shift_);

// l-mer completion:
uint64_t canonical_lmer;
if (! dna_)                        canonical_lmer = lmer_;
else if (revcom_version_ == 0)     canonical_lmer = canonical_representation(lmer_, l_);
else                               canonical_lmer = lmer_ < rc_lmer_ ? lmer_ : rc_lmer_;
```

**Why:** `reverse_complement()` recomputes a full 64-bit nucleotide-wise bit reversal —
five mask/shift/or stages, ~17 operations — **once per base**. Profiling put it at 11.47%
of total runtime, with `canonical_representation` a further 4.43%. The forward l-mer
already updates incrementally as `lmer_ = ((lmer_ << 2) | code) & mask`; its reverse
complement updates in lockstep in three operations, because RC's leading base is the
complement of the forward's newest, and the base falling off the top of `lmer_` falls off
the bottom of `rc_lmer_`.

**Correctness guards:** DNA only (protein never takes the canonical path and its codes are
not 2-bit complements); `revcom_version_ != 0` only (version 0 keeps pre-K2.0.8 behaviour
and still calls `reverse_complement()` — our DBs are version 1, confirmed from `opts.k2d`
word 6); ambiguous bases reset `rc_lmer_` alongside `lmer_`. No reset is needed in
`LoadSequence` — `rc_lmer_` self-cleans over `l_` updates by the same argument that lets
`lmer_` do so.

**Numbers.** pod5_2, `-p 16 -B 29`, medians of 5. Output **byte-identical** on pod5_15 and
sample_50mb.

| build | DB | cycles | cv | instructions | IPC | vs base |
|---|---|---:|---:|---:|---:|---:|
| base | 8 MB | 9.812e10 | 0.16% | 1.6264e11 | 1.658 | — |
| **incremental** | 8 MB | **9.179e10** | 0.60% | **1.4968e11** | 1.631 | **−6.44%** |
| base | 48 MB | 1.1716e11 | 1.29% | 1.6854e11 | 1.439 | — |
| **incremental** | 48 MB | **1.0959e11** | 1.82% | **1.5557e11** | 1.420 | **−6.46%** |

Instructions fell **7.97%** / **7.69%**.

**What it means:** this is the first change in the read-path series where mechanism and
result agree. Contrast `-march=native`, which cut instructions 1.1% and *lost* 0.92%:
BMI2 made individual operations cheaper without shortening the dependency chain, whereas
this removes ~14 operations per base from inside it.

IPC falls slightly (1.658 → 1.631), which is the expected signature of removing work from
a dependency-bound loop — less independent work remains to fill issue slots, but there is
far less work overall. The gain being near-identical at both database sizes (−6.44% /
−6.46%) is the sanity check that this is scanner work, independent of the hash table.

**Status: reverted on request.** The tree is back to the stock `reverse_complement()` path
(output md5 `b236e2a4…` verified). Re-applying is a contained change to two files.

## 2026-09-09 — kseq read buffer 16 KB → 256 KB: −0.88%

**What:** `scratch_lookaside/src/seqreader.h:14` no longer calls `KSEQ_INIT(int, read)`.
It expands `KSEQ_INIT2` by hand so the stream buffer size lives in our file:

```c
#ifndef K2_KSEQ_BUFSIZE
#define K2_KSEQ_BUFSIZE (256 * 1024)   /* override with -DK2_KSEQ_BUFSIZE=N */
#endif

KSTREAM_INIT(int, read, K2_KSEQ_BUFSIZE)
__KSEQ_TYPE(int)
__KSEQ_BASIC(static, int)
__KSEQ_READ(static)
```

`kseq.h` is **untouched** — it is vendored upstream code, and the 16384 literal lives
inside its `KSEQ_INIT2` (`kseq.h:224`). Expanding the macro ourselves avoids carrying a
patch against it. The one value feeds three places: the `malloc` in `__KS_BASIC`
(`kseq.h:59`) and the `read()` in both `__KS_GETC` (`:76`) and `__KS_GETUNTIL` (`:105`).

**Why:** at 16 KB a 1 GB FASTQ costs **63,361 `read()` syscalls**, and every one runs
inside `omp critical(seqread)` (`classify.cc:587`) where 15 threads block. This surfaced
after `-M` subsampling moved the bottleneck: at an 8 MB database the hash lookups are only
20.9% of runtime and read+parse+scan is 79.1%.

**Numbers.** pod5_2, `-p 16 -B 29`, 8 MB DB, medians of 3. Output byte-identical at every
size and against upstream.

| buffer | syscalls | cycles | cv | cpu-ms | vs 16 KB |
|---|---:|---:|---:|---:|---:|
| 16 KB | 63,361 | 9.857e10 | 0.60% | 23,289 | — |
| 64 KB | 15,840 | 9.806e10 | 0.32% | 23,172 | −0.53% |
| **256 KB** | **3,960** | **9.771e10** | 0.20% | 22,953 | **−0.88%** |
| 1024 KB | 990 | 9.816e10 | 0.20% | 23,110 | −0.42% |
| 4096 KB | 247 | 9.838e10 | 0.43% | 32,090 | −0.19% |

**What it means:** smaller than the ~1.4% predicted — most of the kernel time is
`copy_to_user`, which scales with bytes, not call count. **The curve turns around**:
256 KB is optimal and 1 MB/4 MB are worse despite far fewer syscalls. Instruction counts
are flat across all five (1.6258–1.6278e11), so the regression is cache pressure — past
~256 KB the buffer stops being L2-resident.

The 4 MB row is the informative one: `cpu-ms` jumps 22,953 → 32,090 (**+40%**) while
cycles barely move. A bigger buffer holds the lock longer per refill, so contention
worsens even as syscalls fall 256×. **The critical section, not the syscall count, is the
binding constraint** — recorded as item A in `FUTURE_UPDATE.md`.

Memory cost is one buffer per file, not per thread: `BatchSequenceReader`'s copy
constructor (`seqreader.h:85`) shares `kseq_`, which is why `LoadBlock` needs the lock.

---

## 2026-09-09 — `-march=native` tested and REJECTED: +0.92% slower

**What:** nothing. No code or Makefile change was kept. Recorded so it is not retried.

**Why it was tried:** `Makefile:3` carries no `-march` flag at all, so everything compiles
to x86-64 baseline on an i7-11700 with bmi1, bmi2, avx2, avx512f, popcnt, movbe and abm.
Profiling put `MinimizerScanner` at **59.17% of total runtime**, which made a one-flag
change look like the highest-value item available.

**Numbers.** pod5_2, `-p 16 -B 29`, medians of 5. Output byte-identical.

| build | DB | cycles | instructions | cpu-ms | vs base |
|---|---|---:|---:|---:|---:|
| base | 8 MB | 9.847e10 | 1.6268e11 | 23,169 | — |
| native | 8 MB | 9.937e10 | **1.6095e11** | 29,234 | **+0.92%** |
| base | 48 MB | 1.1611e11 | 1.6851e11 | 37,391 | — |
| native | 48 MB | 1.1632e11 | **1.6586e11** | 37,433 | +0.18% |

The compiler did its job — 25 `shlx`, 24 `shrx`, 4 `lzcnt`, 1 `andn` against **zero** in
the baseline, and instructions fell **1.1%**. **Fewer instructions, more cycles.**

**What it means:** the scanner was never instruction-throughput-bound. It runs at IPC
1.808 on a 5-wide machine, and `NextMinimizer` carries a rolling-hash serial dependency —
each window depends on the previous. Replacing two instructions with one BMI2 instruction
does not shorten a dependency chain; it removes work the machine was already absorbing in
spare issue slots. `cpu-ms` rising +26% at 8 MB while cycles barely move is consistent
with AVX-512 downclocking dragging the whole package.

**The lesson, which generalises:** a large share of runtime does not imply improvability
by better instruction selection. The profile said *where* time goes, not *why*. Attacking
the scanner needs its dependency structure changed, not its instruction encoding.

## 2026-09-02 — stop prefetching duplicate minimizers: −3.5% instructions

**What:** Pass 1 now runs the duplicate test one pass early. A minimizer equal to
the previous non-ambiguous one gets no `MurmurHash3` and no `Prefetch()`, because
pass 2 reuses `last_taxon` for it and never looks it up. A new `pf_last_min`
mirrors what `last_minimizer` used to do, over the same sequence and on the same
update condition, so the two agree by construction; pass 2 now branches on a
stored `pf[i].dup` flag instead of re-comparing. Binary: `scratch_lookaside/bin/classify_nodup`.

The `-M` subsampling check was deliberately **left in pass 2** — gating that too
is a separate, untested change.

**Why:** 67.6% of minimizers on this library are consecutive duplicates. We were
spending a hash, a `divq` and a `prefetcht0` on every one of them for a lookup
that never happens.

**Numbers.** Four independent measurements agree on the instruction count:

| workload | threads | elapsed | instructions |
|---|---|---:|---:|
| pod5_0 (799 MB) | `-p 1` | −2.40% | **−3.53%** |
| pod5_0 (799 MB) | `-p 16` | (bimodal) | **−3.52%** |
| sample_50mb | `-p 1` | −2.41% | **−3.46%** |
| pod5_2 (991 MB) | `-p 16` | −2.98% | **−3.50%** |

pod5_2 detail, 8 valid reps each: cycles −3.57%, IPC 1.467 → 1.469 (unchanged),
cache-misses −1.08%, LLC-load-misses +1.43%.

**What it means:** this is an instruction-count win, not a memory win, and the
flat memory counters confirm why — a duplicate's prefetch targeted the line the
*previous* minimizer had already pulled in, so it never generated DRAM traffic.
It cost instructions only. The DRAM win would come from gating the `-M` skip,
which only pays on a subsampled database and is still untested.

Prediction on record that was wrong: this was expected to recover "most of" the
1156.6 vs 983.6 instructions/lookup batching overhead. It recovered 3.5%. The
duplicate share was right; the per-duplicate cost was overestimated.

**Verification:** byte-identical output at `-p 1` across `-B 1 / 8 / 24`,
identical `-R -K` report, identical on `standard_8gb` (exercises the `-M` path),
and all 16 `-p 16` runs on pod5_2 matched the `-p 1` reference `77c89e454964d4ce…`.

**Also created:** `perpod5/sample_50mb.fastq` — 7,069 whole records, 50 MB, head
of pod5_0. Runs in 0.81 s with a 0.02 s spread, which makes it a much better
harness for iterating than the full file. Confirm anything publishable on the
full file; it is the head, not a random sample.

---

## 2026-09-02 — blocker: this box returns silently wrong output at `-p 16`  — SUPERSEDED

> **Superseded 2026-09-09.** This is an *upstream kraken2* bug, reproduced in stock,
> not a fault of this machine. See the 2026-09-09 entry.

**What:** Five runs of the **unmodified** `classify_prefetch`, same input, same
flags: three correct, one **different output with exit code 0** (44,126,678 bytes
vs 44,126,663), one SIGSEGV. `-p 1` was byte-identical every time.

**Why it matters:** a zero exit code is not evidence of a correct run. Any `-p 16`
measurement on this machine — including ones already recorded — can be wrong.
The failure is intermittent: a later 16-run sweep on pod5_2 had zero discards.

**How to work around it until fixed:** verify correctness at `-p 1` only; for
`-p 16` timings, run extra reps and discard any whose md5 differs from the `-p 1`
reference. Prefer instruction counts over elapsed time — they are stable to
~0.1% while elapsed is bimodal.

**Next step:** run `memtester` / memtest86 before trusting further measurements.
This sits alongside the crash record in `PREFETCH.md` §14 "Crashes".

---

## 2026-08-31 — prefetch re-measured properly: −20.3%, not −11.8%

**What:** Re-ran the `-B` sweep with a cooldown protocol — three consecutive runs
per setting, then four minutes idle before the next. Raw data:
`result/prefetch/sleep_sweep/` (99 files), table:
`result/prefetch/TABLE.txt`, write-up: `PREFETCH.md`.

**Why:** Every earlier timing on this machine was measured through heavy noise.
A 20-run test made that undeniable: the same binary took **1.850 s on one run and
2.898 s on another**, while executing an *identical* number of instructions
(176.05–176.20 G, a 0.09% spread). The program does exactly the same work every
time; only the processor's clock speed changes. Averaging interleaved runs was
not enough to remove it.

**What the cooldown achieved:** package temperature stayed between **59 and 65 °C
for all 33 groups**, and run-to-run spread fell to **0.004–0.021 s**, against up
to 0.32 s before. No crashes in 99 runs.

**Result:**

| setting | time | vs stock |
|---|---|---|
| stock | 2.349 s | — |
| `-B 1` | 2.475 s | +5.4% |
| `-B 4` | 2.131 s | −9.3% |
| `-B 8` | 1.992 s | −15.2% |
| `-B 16` | 1.913 s | −18.6% |
| `-B 20` | 1.885 s | −19.8% |
| **`-B 30`** | **1.871 s** | **−20.3%** |

The earlier −11.8% was not wrong, it was measured through noise that hid most of
the effect. Classification output is unchanged: 84.26% on every row.

**Two things the clean data corrected:**

1. **The useful batch size is about 20, not 4.** Earlier sweeps appeared to show
   the benefit arriving by a batch of 4 and flattening. That was noise drowning
   everything past it. The curve actually keeps descending smoothly to ~20.

2. **`-B 1` costs 5.4%,** and that figure is now trustworthy. It does exactly what
   stock does but executes 17.6% more instructions — the cost of the buffering
   itself. Every batch size pays it first.

**Why two "cache miss" numbers disagree — worth understanding:**

Prefetching does not remove a trip to memory. It changes **which instruction
makes the trip**. Normally the real lookup goes all the way to memory and waits.
With prefetching, the *prefetch* makes that trip early and the line is already in
cache when the real lookup runs.

So counters that only watch real lookups (`LLC-load-misses`) fall by 83%, while
counters that watch *all* memory traffic (`cache-misses`) barely move — 454.9 M
to 399.4 M, just 12%.

**`cache-misses` is the honest one.** The `llc%` column dropping from 59.58% to
31.07% looks like a big improvement in cache behaviour and is not — it is the
same traffic wearing a different label. This is the mirror image of the mistake
the lookaside cache invited, where `llc%` also fell while real memory traffic got
*worse*.

---

## 2026-08-30 — saved the prefetch work as a patch

**What:** Created `scripts/kraken2_prefetch.patch` (240 lines).

A patch is not a copy of the source — it is a text file listing only the
differences, with a little surrounding context so the `patch` tool can find the
right place. Three file diffs, about 100 changed lines, instead of three whole
files.

**Why:** Until now the prefetch change existed in exactly one place —
`scratch_lookaside/src/` — and that directory has been treated as scratch all
day and cleared out several times. If it were deleted the work would be gone;
the documents would still describe it but nobody could rebuild it without
redoing the edits by hand.

**Verified, not assumed:** the patch was applied to a fresh copy of
`kraken2/src`, and the result is **byte-identical** to the working tree for all
three files. It then compiled with zero errors and the binary still accepts
`-B`. So the patch genuinely reproduces the work.

**What the header records**, so the file explains itself years from now: what
the change does, that it applies to *this project's forked tree* (git 7c0eb91)
and not to upstream 2.17.1, the measured numbers, the 16-of-16 byte-identical
correctness result, the list of things deliberately left unchanged, and the one
fragile dependency — that `add_kmer()` relies on `NextMinimizer()` returning
`&last_minimizer_`, and would break silently if that ever changed upstream.

**Kept aside, not applied.** `kraken2/src` and `kraken2_bin/` remain untouched,
so the baseline every measurement compares against stays honest. To use it:

```
cd kraken2 && patch -p1 < ../scripts/kraken2_prefetch.patch
```

**Note on the older patch:** `scripts/kraken2_lookaside.patch` is stale. It
describes the lookaside cache including the `-A` and `-Z` flags that were
deleted today, and no source file matches it any more. It should be regenerated
or removed — it currently sits next to a correct patch looking equally
authoritative.

---

## 2026-08-30 — prefetch results across every batch size 1-32

**What:** Swept `-B` through every value from 1 to 32, three interleaved runs
each (99 runs), recording plain `perf stat` counters for each. Raw files:
`result/prefetch/perf/` (99 files). Full 33-row table:
`result/prefetch/TABLE.txt`.

**Measured values** (no comparisons - these are the raw figures):

| -B | clsfd% | elapsed | sd | LLC-loads | LLC-ld-miss | llc% | instructions | IPC | cycles | DRAM/lk | ins/lk | cyc/lk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock | 84.26 | 2.893 | 0.007 | 258,717,057 | 150,734,517 | 58.26 | 157,994,819,090 | 1.13 | 139,495,392,141 | 0.938 | 983.6 | 868.5 |
| 1 | 84.26 | 2.908 | 0.288 | 94,469,202 | 29,837,313 | 31.58 | 185,786,274,993 | 1.21 | 153,284,452,944 | 0.186 | 1156.6 | 954.3 |
| 2 | 84.26 | 2.748 | 0.284 | 88,164,247 | 25,389,678 | 28.80 | 180,823,712,284 | 1.26 | 143,278,819,196 | 0.158 | 1125.8 | 892.0 |
| 3 | 84.26 | 2.657 | 0.280 | 83,867,494 | 23,237,304 | 27.71 | 179,148,955,704 | 1.31 | 137,181,707,867 | 0.145 | 1115.3 | 854.0 |
| 4 | 84.26 | 2.572 | 0.284 | 83,284,261 | 22,863,265 | 27.45 | 178,289,451,484 | 1.35 | 131,984,616,072 | 0.142 | 1110.0 | 821.7 |
| 5 | 84.26 | 2.579 | 0.296 | 80,644,443 | 22,807,542 | 28.28 | 177,822,104,624 | 1.36 | 131,495,215,604 | 0.142 | 1107.1 | 818.6 |
| 6 | 84.26 | 2.684 | 0.083 | 80,800,087 | 22,565,329 | 27.93 | 177,503,796,587 | 1.38 | 128,710,434,851 | 0.140 | 1105.1 | 801.3 |
| 8 | 84.26 | 2.678 | 0.020 | 79,616,559 | 22,255,630 | 27.95 | 177,077,050,548 | 1.41 | 125,638,176,113 | 0.139 | 1102.4 | 782.2 |
| 12 | 84.26 | 2.623 | 0.035 | 80,686,632 | 22,306,938 | 27.65 | 176,632,175,696 | 1.45 | 121,791,935,700 | 0.139 | 1099.7 | 758.2 |
| 16 | 84.26 | 2.612 | 0.047 | 79,592,032 | 22,438,701 | 28.19 | 176,475,057,425 | 1.45 | 121,763,190,952 | 0.140 | 1098.7 | 758.1 |
| 20 | 84.26 | 2.578 | 0.017 | 78,149,542 | 22,492,987 | 28.78 | 176,309,583,824 | 1.48 | 119,343,045,440 | 0.140 | 1097.6 | 743.0 |
| 24 | 84.26 | 2.563 | 0.021 | 80,395,019 | 22,497,725 | 27.98 | 176,221,588,458 | 1.48 | 118,891,378,518 | 0.140 | 1097.1 | 740.2 |
| 28 | 84.26 | 2.566 | 0.025 | 78,196,314 | 22,569,789 | 28.86 | 176,168,238,628 | 1.49 | 118,668,872,564 | 0.141 | 1096.8 | 738.8 |
| 29 | 84.26 | 2.553 | 0.006 | 79,200,878 | 22,592,668 | 28.53 | 176,159,715,697 | 1.49 | 118,222,050,946 | 0.141 | 1096.7 | 736.0 |
| 32 | 84.26 | 2.561 | 0.015 | 80,446,021 | 22,656,315 | 28.16 | 176,122,459,462 | 1.49 | 118,207,438,668 | 0.141 | 1096.5 | 735.9 |

Workload: pod5_2.fastq, 151,591 reads, 499.98 Mbp, 160,625,038 lookups.
Database eskape_32bit_fork (48.8 MB). `-p 16 -g 2 -T 0`. Mean of 3 reps.
`sd` is the standard deviation of elapsed time across those 3 runs.

**What the numbers say:**

1. **The classification result never changes.** `clsfd%` is 84.26 on every row
   including stock. Batching is invisible in the output, as it should be.

2. **Nearly all the memory benefit arrives by a batch of 4.** Memory trips per
   lookup fall 0.938 -> 0.186 at `-B 1`, then 0.142 by `-B 4`, and stay flat
   after that. Going from 4 to 32 changes it by 0.001.

3. **What keeps improving past 4 is IPC, slowly** - 1.35 at `-B 4` up to 1.49 at
   `-B 29`. That is worth roughly another 0.7% of runtime, no more.

4. **The `sd` column is the one to read.** At `-B` 1 to 5 the spread across
   three runs is 0.28-0.30 seconds. From `-B 6` onward it collapses to
   0.006-0.047. Small batches are still waiting on memory and so are at the
   mercy of whatever else the machine is doing; large batches are steady. At
   `-B 29` the spread is 0.006 s - steadier than stock.

   This matters for reading rows 1-5: their timings look good but carry an
   uncertainty forty times larger than the rows below them.

5. **`-B 1` costs about 17% more instructions than stock** (1156.6 vs 983.6 per
   lookup) while doing exactly the same work. That is the price of the buffering
   itself, and every batch size pays it. It is why a batch of one is no faster
   than stock despite already cutting memory trips by 80%.

**Best setting:** `-B 29` at 2.553 s, though anything from 16 to 32 is within
noise of it and all are steady. `-B 4` reaches nearly the same time with far
less buffer, but with a spread wide enough that the figure should not be quoted
on its own.

The curve is flat by 32 (735.9 vs 736.0 cycles per lookup at 29), so raising the
batch limit further is not worth trying.

---

## 2026-08-30 — software prefetch: the first change that actually helps

**What:** Reworked the inner classification loop to look up minimizers in
batches instead of one at a time. New flag `-B NUM` (default 1 = the original
behaviour). Binary: `scratch_lookaside/bin/classify_prefetch`.

The loop used to do: get a minimizer, look it up, wait for memory, repeat. Now
it does two passes — first it scans NUM minimizers, hashes them, and asks the
CPU to start fetching each one's memory *without waiting*; then it goes back and
resolves them in the same order as before. By the time it needs each answer the
memory has usually already arrived.

**Why:** Measured memory-level parallelism was **1.24** outstanding memory
requests where the processor can hold about **12**. Every memory wait was being
paid in full, one after another, because each lookup depended on the previous
one finishing. Prefetching does not remove any memory access — it just starts
them earlier so they overlap.

**Three files changed:**
- `kv_store.h` — one new method, `Prefetch(hc)`
- `compact_hash.h` — implements it (`__builtin_prefetch` on the slot the hash
  lands on), plus `GetWithHash` so the hash is computed once, not twice
- `classify.cc` — the two-pass loop and the `-B` flag

**Results** (pod5_2, 16 threads, mean of 3):

| setting | time | vs stock | memory trips per lookup | IPC |
|---|---|---|---|---|
| stock | 2.700 s | — | 0.942 | 1.10 |
| `-B 1` | 2.922 s | +8.2% | 0.186 | 1.21 |
| `-B 8` | 2.663 s | −1.4% | 0.138 | 1.41 |
| `-B 16` | 2.575 s | −4.6% | 0.139 | 1.46 |
| **`-B 32`** | **2.538 s** | **−6.0%** | 0.141 | **1.49** |

**Correctness: byte-identical to stock** at every batch size, at 1 and 16
threads, on both pod5_15 and pod5_2 — 16 checks, all exact. Unlike the cache
work, there is no accuracy trade here at all.

**Two things worth knowing:**

1. **Memory trips per lookup fell 85%** (0.942 → 0.14). We expected overlapping,
   not removal. The explanation is that the prefetch brings the line in early
   enough that the real lookup finds it already there, so it stops being counted
   as a miss. The work still happens; it has just moved off the critical path.

2. **`-B 1` is 8% slower than stock even though it does the same thing.** That
   is the cost of the restructuring itself: 1,156 instructions per lookup versus
   984 — the buffering, the saved flags, the extra loop. Batching has to earn
   that back before it wins, which is why small batches still lose. Measured
   against the same code path, `-B 1` to `-B 32` is a **13%** improvement; about
   6% of it survives once the overhead is paid.

Timings are also far steadier than stock: `-B 32` gave 2.542 / 2.537 / 2.536
across three runs, where stock swung 2.360-2.879. Less waiting on memory means
less sensitivity to what else the machine is doing.

**Still open:** try a larger `-B` (the gain had not flattened at 32, and the cap
is 64); check whether the instruction overhead can be trimmed; confirm on the
other pod5 files and on the 24-bit database.

---

## 2026-08-30 — simplified to one cache, one policy

**What:** Threw away most of the lookaside code. There is now **one table**, not
three tiers, and **one behaviour**, not four modes. Three flags:

```
-L <MB>    turn the cache on, size in MB (power of two)
-N <ways>  how many slots a minimizer may use (default 4)
-J <n>     admit one miss in n (default 8; 1 admits every miss)
```

Removed: the L1 and L2 tiers, `-Y` and its four learning modes, `-F` (the cache
is always the 4-byte format), `-W` (it wrote files nothing read). Also gave back
`-K`, which is kraken2's own flag for minimizer data in reports — the new code
had taken it over by mistake. Admission moved to `-J`.

**Why:** The L1 and L2 tiers were measured to contribute 0.44% and 1.02% of hits
out of 12.32% — about 12% of the benefit for two extra checks on every miss. And
the four modes were not really four policies: one was on/off, one only existed
because there were three tiers, and the only genuine policy knob (replacement)
was not adjustable at all.

**A bug found while doing this.** The old admission filter did nothing. It was a
table of 4.19 million bits used to remember which minimizers had been seen
before — but there are 42.8 million distinct minimizers, so after about 20
million the table is 99.2% full and reports "seen before" for everything. That
is why the `admit` mode measured the same as plain `learn` (12.32% vs 12.20%):
the filter had been switched off by its own saturation the whole time.

**The replacement policy we chose, and why.** Random, within the set. Reasons,
all from our own measurements:

1. The table is about **43x too small** for the data — 1 million slots against
   42.8 million distinct minimizers. Whatever you throw out was unlikely to be
   needed soon, so being clever about *which* entry to throw out buys very little.
2. **Recency is a weak signal here.** Simulating true LRU on this data gives
   14.97% hits where picking by frequency gives 25.28%. Reads arrive in random
   genome order, so the same minimizer usually reappears millions of lookups
   later — far beyond anything a small table remembers.
3. LRU or LFU need bookkeeping updated on every **hit**. That would turn a table
   all 16 threads only read into one they all write, which is expensive. And the
   4-byte entry is already full (26 bits of fingerprint + 6 bits of value), so
   there is nowhere to put a counter anyway.

**The admission policy, and why it matters more.** 63.4% of distinct minimizers
appear **exactly once** — sequencing errors that never come back. They are 29.9%
of all lookups. Letting them in pushes useful entries out, and no replacement
policy can undo that, because by the time you are choosing what to evict the
junk is already inside. So we only let in one miss out of every `-J`. A
minimizer that appears often gets many chances and almost certainly gets in; one
that appears once usually does not. At the default `-J 8`, something seen once
gets in 12.5% of the time, something seen ten times 74%, something seen a
hundred times essentially always. This costs no memory and cannot saturate the
way the old bit table did.

**What it means:** measured on the big file, every setting is still **7.5% to
9.6% slower** than plain kraken2. Selective admission is better than admitting
everything (`-J 8` +7.50% vs `-J 1` +9.60%) and the ordering matches the
reasoning — but the run-to-run spread on this machine is about twice that gap,
so the difference is suggestive rather than proven.

**Honest limitation:** we deleted `-Z` earlier today, which was the only way to
see the hit rate. So we can measure that one setting is faster than another but
not show *why*. Validating the policy properly needs a throwaway build with a
hit counter.

---

## 2026-08-30 — full audit of the kraken2 tree

**What:** Went through the whole project looking for changes we had not written
down. Wrote `KRAKEN2_CHANGES.md` describing how kraken2 works and every part we
touched. Found and fixed four things.

**What we found:**

1. **A second copy of the cell-size work exists.** `kraken2_laptop/` is a
   separate fork, on an older upstream base (14 May), with its own binaries in
   `kraken2_laptop_bin/`. It implements the *same* five cell widths
   (16/20/24/32/40), accepts the same `--cell-size` values, and has the same
   critical `build_db.h` fix. It differs only in comments and struct layout.
   **`kraken2/src/classify` matches `kraken2_bin/classify` byte for byte**, so
   `kraken2/` is the fork that built everything we measure. The laptop copy is
   used for nothing. Nobody had written this down.

2. **Three documents contained commands that no longer run.** The reproduce
   snippets in `LOOKASIDE_REPORT.md`, `CACHE_TABLE_ANALYSIS.md` and
   `result/run_sweep/REPORT.md` all used `-A` and `-Z`, which we deleted earlier
   today. Each now carries a note saying so, rather than looking runnable.

3. **`scripts/kraken2_lookaside.patch` is stale.** Confirmed: zero references to
   the runtime-learning work, nine references to the removed `-A`/`-Z`. It is a
   snapshot of an older state, not the live code.

4. **`-W` is confirmed orphaned.** It still writes frequency profile files, but
   nothing reads them any more. Zero readers in the source.

**What it means:** Only three source files are modified for the lookaside work —
`classify.cc`, `compact_hash.h`, `kv_store.h` — and that is now verified by
comparing whole directories, not assumed. The second fork is accounted for. The
project has no undocumented changes left that we can find.

**Still open:** remove `-W`; decide whether to keep `kraken2_laptop/` (50 MB) or
delete it now that we know it is redundant.

---

## 2026-08-30 — removed `-A` (profile) and `-Z` (statistics)

**What:** Deleted both flags from the source completely. 3,000 characters of
code gone; no leftover references. Also deleted the backup patch, as asked, so
this is not reversible from a file — only by rewriting the code.

**Why:** The lookaside now learns at runtime, so it no longer needs a
pre-computed profile handed to it.

**What it means:**
- `-L` now **requires** `-Y`. Without runtime learning the tables would start
  empty and stay empty, so that combination is refused instead of silently
  doing nothing.
- We can no longer measure the **hit rate** — that was `-Z`. Every hit-rate
  number in the reports came from it.
- We can no longer measure the **oracle ceiling** — that was `-A`. That was the
  number showing the best a perfect cache could ever do (29.54%).
- Both were measurement instruments, not features. The results they produced are
  already written down in `LOOKASIDE_REPORT.md` and `result/run_sweep/REPORT.md`.

**Loose end:** `-W` still exists. It writes a frequency profile — but nothing
reads those files any more, because `-A` is gone. It should probably be removed
too. Not done yet, waiting on a decision.

---

## 2026-08-30 — fixed the `promote` bug, made learning modes combinable

**What:** Two fixes to the runtime-learning code.

1. **`promote` now moves an entry instead of copying it.** It writes the entry
   into the faster tier and then clears the slot it came from.
2. **The three learning options became combinable.** They used to be one
   either/or setting, so you could not have two at once.

**Why:** Copying let one minimizer sit in two tiers at the same time, which
wasted space and made `promote` look worse than it was. And the old either/or
design made `admit` + `promote` together impossible to test, even though that is
an obvious thing to try.

**What it means:** `-Y` now takes a comma list — `-Y learn`, `-Y admit`,
`-Y promote`, `-Y admit,promote`. Five settings instead of four, including the
one that was previously unreachable. That new combination turned out to be the
**worst** (11.25%): admission lets fewer things in, then promotion pushes those
few into tiers too small to hold them, so the two fight each other.

**Also decided:** when a promotion displaces an existing entry, that entry is
**thrown away**, not pushed down a tier. Pushing it down looks tidier but is
wrong — an entry parked in a slot it does not hash to can never be found again
and can still cause a wrong answer.

---

## 2026-08-30 — added runtime learning (`-Y`)

**What:** The lookaside tables can now fill themselves while classifying,
starting completely empty. Three switches: `learn` (add every minimizer we had
to look up), `admit` (only add one we have missed before), `promote` (move an
entry to a faster tier when it gets used).

**Why:** Everything before this used a profile built by counting the answer in
advance — useful for finding the ceiling, impossible to ship. This is the
version that could actually run in production.

**What it means:** Runtime learning reaches about **12%** where the profile
version reached **29.5%** on the same setup — roughly 40% of what perfect
knowledge gives you. Since the profile version already loses to plain kraken2,
the learning version loses by more.

**How it stays safe with 16 threads:** every write is a single 4-byte store that
the CPU does in one go. A reader sees either the old entry or the new one, never
half of each. No locks. If two threads write at once one simply loses, which
costs a future lookup, not a wrong answer. This is also why `-Y` only works with
`-F compact` — a 16-byte `exact` entry cannot be written in one go.

---

## 2026-08-30 — stacked the tiers into a hierarchy

**What:** L1 (4 KB), L2 (256 KB) and L3 (4 MB) can now all be active at once,
checked in order L1 → L2 → L3 → the real hash table. Flag: `-L l1=2,l2=4,l3=8`.

**Why:** To test the original idea properly — small fast table in front of a
bigger slower one, like a real CPU cache.

**What it means:** Measured all 60 combinations. **All 60 are slower than plain
kraken2**, from +3.7% to +28%. The tables do work — up to 26.2% of lookups are
answered without touching main memory — but the extra checking costs more than
the memory it saves. Full numbers in `result/run_sweep/REPORT.md`.

---

## 2026-08-30 — added set-associativity (`-N`)

**What:** A minimizer can now live in any of N slots instead of exactly one.
`-N 1|2|4|8|16`.

**Why:** With one slot each, two useful minimizers landing on the same slot means
one gets thrown away even when the table is half empty.

**What it means:** It fixes exactly what it was meant to fix — the L3 hit rate
went from 25.1% to 28.5%, nearly the theoretical best of 28.9%. But runtime got
**worse**, because checking 16 slots costs more than the extra hits are worth.
L1 and L2 barely changed, because their problem is being too small, not slot
collisions.

---

## 2026-08-30 — made the tier a runtime flag

**What:** One binary instead of six. `-L l1|l2|l3` picks the cache level.

**Why:** Rebuilding for every size was slow and error-prone.

**What it means:** The flag itself costs about 0.6%, because the table size is
now a variable the CPU reads rather than a constant baked into the code.

---

## 2026-08-30 — first lookaside implementation

**What:** A small table holding minimizer → taxon, checked before the main hash
table. Two entry formats: `exact` (16 bytes, keeps the whole minimizer) and
`compact` (4 bytes, keeps a short fingerprint like kraken2 does).

**Why:** To test the idea that frequently used minimizers could be kept in cache
instead of being fetched from main memory every time.

**What it means:** Best case was about 1.5% faster, which is inside this
machine's measurement noise, so **no speedup was ever proven**. The reason is
that the extra check costs 3–5 cycles on every lookup while only paying off on
the small share that hit.

**A bug worth remembering:** the first version picked the table slot using bits
that overlapped the fingerprint bits. That left only ~12 bits to tell
minimizers apart and gave wrong answers on 9.6% of reads. kraken2's own table
takes the slot from the low bits and the fingerprint from the high bits;
matching that fixed it. **Any table like this must keep the two bit ranges
separate.**

**Cell-size compatibility:** `exact` works with 16/20/24/32-bit databases and
always gives identical results. `compact` is only safe on 32-bit — on 16-bit it
gets 53% of reads wrong, because the fingerprint is only 10 bits there.

---

## 2026-08-30 — added `GetWithHash()` to the hash table

**What:** A second way to look up a key when you have already computed its hash.

**Why:** The lookaside computes the hash to find its slot, and the old `Get()`
computed it again — paying twice for the same work.

**What it means:** No change to results (verified byte-for-byte). It is also the
hook a future prefetching change would need, since prefetching means computing
addresses first and fetching values later.

---

## 2026-08-30 — cleanup

**What:** Deleted 21 GB of per-read output files from `result/`, and the
`standard_16gb` and `standard_8gb` databases (22 GB).

**Why:** The output files were 100% of `result/` by size; everything of value —
reports, perf counters, logs — is 17 MB and was kept. The two databases were
downloads, not local builds, and nothing since June referenced them.

**What it means:** The project went from 63 GB to 20 GB. Every command needed to
regenerate a deleted output file is still in its matching `*_log.txt`. A record
of the two databases is in `archive/deleted_db_manifests.txt`.
