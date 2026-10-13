# Future update: making the file-read path faster

**Once the database is subsampled to 8 MB, kraken2 stops being memory-bound and becomes
scanner-bound. The hash lookups fall to 21% of runtime and the read + parse + scan path
rises to 79%. This document is the roadmap for that 79%: what it is made of, what is worth
fixing, in what order, and what to leave alone.**

| | |
|---|---|
| Date | 2026-09-09 |
| Measured on | `eskape_C32_08MB` (8,000,000 B), pod5_2, i7-11700 8C/16T, 16 MiB L3 |
| Binary | `scratch_lookaside/bin/classify_mode`, no `-B` (single pass, no prefetch) |
| Related | `ESKAPE_SIZE_LADDER.md` §9 (the control arm), `PREFETCH.md` (the lookup path) |
| Status | **F = confirmed upstream bug, top priority.** D landed (−0.88%). B2 works (−6.4%) and C works (−1.7%), both reverted. B1 rejected. A, B3, E open. |

> ## ⚠ CONFIRMED UPSTREAM BUG — kraken2 is non-deterministic at `-p 16`
>
> **Unmodified upstream kraken2 produces silently wrong output at `-p 16`, exit code 0.**
> Reproduced 2026-09-09. This is not our code and not this machine — see item F.
>
> Consequence for everything below: **verify correctness at `-p 1` only**, md5-filter
> threaded reps against a `-p 1` reference, and prefer cycles/instructions (stable to ~1%)
> over elapsed. Every threaded measurement in this document followed that protocol.


## 1. Why this matters now

Every previous optimisation in this project targeted the **hash lookup**: prefetching
(`-B`), duplicate gating, cell width, and `-M` subsampling. Those worked. The consequence
is that they worked themselves out of a job.

Isolating the two halves by patching `opts.k2d` so that ~every lookup is skipped
(threshold set to `0xffff...ffff`, no rebuild needed):

```
total (8 MB DB, -p 16, no -B)   89,645,112,985 cycles
  read + parse + scan           70,893,120,702  = 79.1%
  hash lookups                  18,751,992,283  = 20.9%
```

**The bottleneck moved.** At the 48.8 MB baseline the lookups dominated; at 8 MB they do
not. Anything further spent on the lookup path is now chasing a fifth of the runtime.

And that remaining 79% is **not** waiting on memory:

```
IPC              1.808          <- compute-bound, near 2 instructions/cycle
stalls_l3_miss   1.45% of cycles
stalls_mem_any  12.23% of cycles   (88% of those resolve in L1/L2, not DRAM)
```

## 2. Where the 79% actually goes

`perf record`, `-p 1`, zero-lookup configuration, pod5_15:

| symbol | of read path | of TOTAL runtime |
|---|---:|---:|
| `MinimizerScanner::NextMinimizer()` | 58.90% | **46.59%** |
| `MinimizerScanner::reverse_complement()` | 11.47% | 9.07% |
| `ClassifySequence` (loop body) | 8.72% | 6.90% |
| `MinimizerScanner::canonical_representation()` | 4.43% | 3.50% |
| `ks_getuntil2` (kseq parsing) | 3.81% | 3.01% |
| `[kernel]` `read()` / `copy_to_user` | 3.63% | 2.87% |
| `AddHitlistString` (output formatting) | 2.14% | 1.69% |
| `__memmove_evex_unaligned_erms` (the copies) | 2.12% | 1.68% |
| `malloc` / `free` churn | 2.85% | 2.25% |

Grouped:

| subsystem | of read path | of TOTAL |
|---|---:|---:|
| **minimizer scanner** | **74.80%** | **59.17%** |
| copy + allocator | 4.97% | 3.93% |
| kseq parsing | 3.81% | 3.01% |
| read() syscall | 3.63% | 2.87% |
| other (output, loop) | 10.86% | 8.59% |

**The scanner is 59% of total runtime.** Everything else in the read path is single digits.

> **Correction on the record.** An earlier version of this analysis ranked the kseq buffer
> size and the `copy_from_kseq` copy as the top levers. They are worth 2.87% and 3.93%.
> That ranking came from reading code structure rather than profiling, and it was wrong.

## 3. The data flow, for orientation

Every byte of the 1 GB file is copied **three times** before a minimizer is scanned:

```
  page cache  ->  ks->buf          (1) kernel copy_to_user, inside read()
  ks->buf     ->  kseq_->seq.s     (2) kputsn, in __KS_GETUNTIL
  kseq_->seq.s -> seq.seq          (3) copy_from_kseq: std::string::assign
  seq.seq     ->  MinimizerScanner     the scan itself
```

The buffer at step 1 is **16,384 bytes** (`kseq.h:225`), refilled **63,361 times** for
pod5_2. All of this happens inside `#pragma omp critical(seqread)` (`classify.cc:587`).

---

# The roadmap

## A. Fix the critical-section serialization  — biggest recoverable win

**The problem.** `classify.cc:587` wraps the whole of `LoadBlock` — file read, kseq
parsing, and `copy_from_kseq` — in one OpenMP critical section. Fifteen threads block
while one reads.

**Measured cost.** CPU time for *identical work* on the read+scan path:

| threads | CPU-ms | vs 1 thread |
|---|---:|---:|
| `-p 1` | 8,484.9 | 1.00x |
| `-p 4` | 9,177.4 | 1.08x |
| `-p 16` | **16,461.6** | **1.94x** |

**The read path burns 1.94x more CPU at 16 threads than at 1**, for byte-identical work.
That is roughly 8 seconds of CPU spent spinning on a lock.

**Approaches, cheapest first.**

1. **Move the copy out of the lock.** Only `kseq_read` genuinely needs serializing (it
   advances shared file state). `copy_from_kseq` writes to thread-local `seqs_` and does
   not. Shrinking the critical section to just the kseq calls is a local change.
2. **Double-buffer.** One thread loads block N+1 while the others process block N. Needs a
   second buffer set and a handoff, but removes the serialization rather than shortening it.
3. **Per-thread file offsets.** Give each thread its own `pread` region with FASTQ record
   boundary repair at the seams. Fastest in principle, most invasive, and risks changing
   block ordering — which the output priority queue depends on.

**Expected gain:** up to the 1.94x inflation, so potentially tens of percent of wall time
at `-p 16`. This is the only item on the list whose payoff grows with thread count.

**Risk:** block ordering feeds `output_queue` and `block_id`; any reordering changes output
byte order. Byte-identical output against the current binary is the acceptance test.

## B. The scanner  — two approaches tried, one works

### B1. `-march=native`  — TESTED AND REJECTED, +0.92%

**Status: measured 2026-09-09. Do not adopt.** It is slightly *slower*.

The compiler did its part — BMI2 genuinely emitted (25 `shlx`, 24 `shrx`, 4 `lzcnt`, 1
`andn` against **zero** in baseline), instructions fell **1.1%**, output byte-identical.
Cycles nonetheless rose 0.92% at 8 MB and 0.18% at 48 MB, and `cpu-ms` rose 26% at 8 MB
while cycles barely moved — consistent with AVX-512 downclocking dragging the package.

**Why it failed:** the scanner is not instruction-throughput-bound. It runs at IPC 1.808
on a 5-wide machine, and `NextMinimizer` carries a rolling-hash serial dependency —
each window depends on the previous. BMI2 makes individual operations cheaper; it cannot
shorten a dependency chain.

### B2. Incremental reverse complement  — WORKS, −6.4%, currently reverted

**Status: implemented, measured, reverted on request 2026-09-09.** Full recipe in
`CHANGELOG.md`.

`reverse_complement()` recomputes a full 64-bit nucleotide-wise bit reversal — five
mask/shift/or stages, ~17 ops — **once per base** (11.47% of runtime, plus
`canonical_representation` at 4.43%). The forward l-mer already updates incrementally, so
its reverse complement can too, in three operations:

```c
lmer_    = ((lmer_ << 2) | code) & mask                       // existing
rc_lmer_ = (rc_lmer_ >> 2) | ((3 ^ code) << rc_shift_)        // new
canonical = min(lmer_, rc_lmer_)
```

| build | DB | cycles | instructions | vs base |
|---|---|---:|---:|---:|
| base | 8 MB | 9.812e10 | 1.6264e11 | — |
| incremental | 8 MB | **9.179e10** | 1.4968e11 | **−6.44%** (instr −7.97%) |
| base | 48 MB | 1.1716e11 | 1.6854e11 | — |
| incremental | 48 MB | **1.0959e11** | 1.5557e11 | **−6.46%** (instr −7.69%) |

Byte-identical output on two inputs. Near-identical gain at both DB sizes confirms this is
scanner work, independent of the hash table.

**Guards required:** DNA only; `revcom_version_ != 0` only (version 0 keeps pre-K2.0.8
behaviour); reset `rc_lmer_` on ambiguous bases.

**The contrast with B1 is the lesson.** B1 cut instructions 1.1% and lost time; B2 cut
them 8% and gained 6.4%. Both reduced instruction count — only B2 removed operations from
*inside the dependency chain*. When a loop is dependency-bound, what matters is the length
of the chain, not the number or encoding of instructions around it.

### B3. Multi-sequence interleaving  — not attempted

The original step-6 proposal: process 2-4 sequences concurrently per thread so independent
`lmer_` chains interleave and fill issue slots. Still open. B2 shortens the chain; B3 would
fill the gaps around it, so they compose rather than overlap. Substantially more invasive —
`MinimizerScanner` holds all state in members, and `ClassifySequence` would need to consume
N sequences while keeping per-read output ordered.

## C. Delete `shrink_to_fit()`  — one line, ~2.85% of the read path

**The problem.** `seqreader.h`, `copy_from_kseq`:

```c
seq.seq.assign(kseq_->seq.s, kseq_->seq.l);
seq.seq.shrink_to_fit();          // <- forces capacity down to exact length
```

`seqs_` is a **reused** vector. Without `shrink_to_fit()`, `assign()` reuses the existing
capacity and allocates nothing. With it, capacity is trimmed to the current sequence, so
the next longer sequence must reallocate and copy. Nanopore reads here run 117 bp to over
5 kb, so a large fraction of the 151,591 sequences trigger a realloc.

**The evidence:** allocator symbols total **2.85%** of the read path — *more* than the
2.12% spent on the copying itself. A line intended to save memory is costing more in
malloc traffic than the copy it accompanies.

**Expected gain:** most of 2.85% of the read path = **~2.25% of total**, for deleting one
line. **Cost:** `seqs_` retains peak-length capacity per slot — bounded by the longest read
times the slot count, not by the file.

## D. Enlarge the kseq buffer  — DONE, measured −0.88%

**Status: implemented 2026-09-09.** Default is now **256 KiB**, down from a first attempt
at 1 MiB which measurement showed was past the knee.

**The problem.** `KSEQ_INIT` hardcodes a 16 KB stream buffer — the literal in
`KSEQ_INIT2` (`kseq.h:224`). At 16 KB a 1 GB FASTQ costs **63,361 `read()` syscalls**,
every one inside `omp critical(seqread)` where 15 threads block.

**The change** (`seqreader.h:14`). `KSEQ_INIT2` is expanded by hand so the size lives in
our file and the vendored `kseq.h` is untouched:

```c
#ifndef K2_KSEQ_BUFSIZE
#define K2_KSEQ_BUFSIZE (256 * 1024)   /* override with -DK2_KSEQ_BUFSIZE=N */
#endif

KSTREAM_INIT(int, read, K2_KSEQ_BUFSIZE)
__KSEQ_TYPE(int)
__KSEQ_BASIC(static, int)
__KSEQ_READ(static)
```

`__bufsize` feeds three places from this one value: the `malloc` in `__KS_BASIC`
(`kseq.h:59`) and the `read()` in both `__KS_GETC` (`:76`) and `__KS_GETUNTIL` (`:105`).

**Memory cost is one buffer per file, not per thread.** `BatchSequenceReader`'s copy
constructor (`seqreader.h:85`) shares the `kseq_` pointer, which is exactly why
`LoadBlock` needs the critical section.

**Measured** — pod5_2, `-p 16 -B 29`, 8 MB DB, medians of 3, output byte-identical at
every size and against upstream:

| buffer | syscalls | cycles | cv | cpu-ms | vs 16 KB |
|---|---:|---:|---:|---:|---:|
| 16 KB | 63,361 | 9.857e10 | 0.60% | 23,289 | — |
| 64 KB | 15,840 | 9.806e10 | 0.32% | 23,172 | −0.53% |
| **256 KB** | **3,960** | **9.771e10** | 0.20% | 22,953 | **−0.88%** |
| 1024 KB | 990 | 9.816e10 | 0.20% | 23,110 | −0.42% |
| 4096 KB | 247 | 9.838e10 | 0.43% | 32,090 | −0.19% |

**Two things the sweep taught that the estimate got wrong.**

The gain is **0.88%, not the ~1.4% projected**. The projection assumed roughly half the
2.87% kernel time was per-call overhead; it is less. Most of that time is `copy_to_user`,
proportional to bytes and indifferent to call count.

**The curve turns around.** 256 KB is optimal; 1 MB and 4 MB are both worse despite far
fewer syscalls. Instruction counts are flat across all five sizes (1.6258–1.6278e11), so
this is purely cache pressure — past ~256 KB the buffer stops being L2-resident and starts
evicting the working set. Reducing syscalls further stops paying.

**The 4 MB row is the most informative.** cpu-ms jumps 22,953 → 32,090 (**+40%**) while
cycles barely move. A larger buffer means each `read()` holds the lock longer, so
contention worsens even as syscall count falls. That is item A showing through: the
critical section, not the syscall count, is the binding constraint.

## E. Eliminate the third copy entirely  — ~1.68% of total, invasive

Point `Sequence` at kseq's buffers instead of copying into `seqs_`. Recovers the 2.12%
`__memmove` share.

**Why it is last:** the kseq buffer is overwritten on the next refill, so every `Sequence`
would have to be consumed before the next `LoadBlock` — a lifetime change across the whole
threading structure. Poor value against the risk when item C gets most of the same benefit
for one line.

---

## F. BUG REPORT — upstream kraken2 is non-deterministic at `-p 16`

**Status: confirmed 2026-09-09, unexplained, unfixed. Highest-priority open item.**
Not caused by any change in this project — demonstrated below.

### Symptom

`classify` intermittently emits **different, silently wrong output at `-p 16` with exit
code 0**. No warning, no error, no crash. `-p 1` is byte-identical every time.

### Reproduction

Unmodified `kraken2_bin/classify` (stock upstream, none of our code), 15 runs at `-p 16`
on identical input, interleaved against our binary as a control:

```
DB     : databases/eskape_sizes/eskape_C32_08MB
input  : perpod5/pod5_2.fastq   (151,591 reads / 499.98 Mbp)
flags  : -p 16 -T 0
-p 1 reference md5 (both binaries agree): 034a3473f9cd390a

stock kraken2 : 13/15 correct, 2 WRONG   -> 822275e06d893770  (rep 12)
                                            354b792d37e26b13  (rep 14)
our binary    : 15/15 correct, 0 wrong
```

The two wrong md5s **differ from each other**, so this is not one deterministic
corruption. Earlier observations on a different input: 5 runs gave 3 correct, 1 wrong with
exit 0 (44,126,678 vs 44,126,663 bytes — 15 bytes short), 1 SIGSEGV.

### What has been ruled out

**Not our changes.** Stock fails; our binary did not in the same 15-rep run. Both produce
the identical `-p 1` reference. ThreadSanitizer on both binaries returns **identical race
sets** — 13 shared sites, **zero unique to either**. Our 185 changed lines in
`classify.cc` (the `PfSlot` batching, `la_prefetch`, duplicate gating, BEFORE/AFTER split)
touch nothing in the output or initialization paths: `diff` of the flagged region against
upstream is empty, and 0 of our changed lines mention `outputs.` or `InitializeOutputs`.

**Probably not failing hardware.** It reproduces on demand in stock, `-p 1` never fails
across dozens of runs, and the kernel log shows no MCE or EDAC errors (only an unrelated
i915 display FIFO underrun). Bad RAM would corrupt single-threaded work too. Caveat: this
is consumer non-ECC memory, so absence of MCE is not proof.

### What ThreadSanitizer could and could not show

TSan reported 62 races in stock and 65 in ours across the same 13 sites. **12 of the 13
are on data guarded by an `omp critical` section**, and GCC's `libgomp` is not
TSan-instrumented, so TSan cannot see those locks and reports the protected data anyway.
Those 12 are unfalsifiable by this method — they may be correctly locked or not.

The one site **outside every lock** is a genuine finding, and it is upstream:

```c
// kraken2/src/classify.cc:652   (our classify.cc:687 -- identical text)
if (!outputs.initialized) {              // unsynchronized read
  InitializeOutputs(opts, outputs, reader1.file_format());
}
```

`InitializeOutputs` re-checks under `critical(output_init)`, so this is classic
double-checked locking, and `OutputStreamData::initialized` is a plain `bool`, not
`std::atomic<bool>` (`classify.cc:116`). A thread observing `initialized == true` has no
happens-before edge guaranteeing it also sees the writes to `kraken_output` and the other
stream pointers.

**Almost certainly not the cause of this bug**: `outputs.initialized = true` is the last
write in the critical section and x86 TSO does not reorder stores, so it is benign on this
hardware in practice. Its failure mode would be a null stream pointer or a crash, not 15
missing bytes of otherwise-valid classification output. It is still worth reporting
upstream as a correctness defect.

### Next step

TSan needs to see the OpenMP locks. Three routes, cheapest first:

1. **Swap the four `omp critical` sections for `std::mutex` in a TSan-only build.** TSan
   intercepts pthread mutexes, so it would then flag only genuine races. Four sections
   (`seqread`, `output_stats`, `output_queue`, `update_taxon_counters`) plus one
   `omp_lock_t output_lock`.
2. **Archer** — LLVM's OpenMP-aware race detector, built for exactly this case.
3. **Clang + libomp compiled with `LIBOMP_TSAN_SUPPORT=ON`.**

Suspect regions, in order: the output priority queue and `next_output_block_id` handoff
(`classify.cc:713-742`); the shared `kseq_` (`BatchSequenceReader`'s copy constructor
shares the pointer, which is why `LoadBlock` needs a lock at all); and the
`buffers` recycling vector.

### Why this outranks everything else here

Every threaded measurement in this project — the whole `-B` sweep, the size ladder, the
read-path work — was taken from a program that intermittently produces wrong output under
threads. The `-p 1` verification protocol contains the risk for *our* results, but the
defect itself is shipped upstream and affects anyone running kraken2 multithreaded.

**This connects directly to item A.** The suspect code is the same critical-section
machinery item A proposes to restructure. A correct producer-consumer design with clear
ownership would be far easier to reason about than the current shared-`kseq_`-plus-four-
critical-sections arrangement — so fixing A may fix F, and F is a reason to do A properly
rather than minimally.

## What NOT to do: software prefetch in the read loop

Rejected after analysis. Four independent reasons, any one sufficient:

1. **You cannot prefetch across a syscall.** `__KS_GETUNTIL` refills a fixed 16 KB buffer
   in place. Addresses beyond `ks->end` do not hold upcoming file content — they hold
   **stale bytes from the previous refill**. The next block only exists after `read()`
   returns, at which point the kernel's copy has already warmed the lines. The compulsory
   misses happen inside `copy_to_user`, in kernel code `__builtin_prefetch` never reaches.
2. **The pattern is sequential.** Intel's L2 streamer locks onto a stride after two misses
   in a 4 KB page and runs ~20 lines ahead unaided. Software prefetch would have to reach
   further to add anything — which puts it past `ks->end`, into the stale region.
3. **The misses are compulsory.** Touching 1 GB once means 16.22 M cold lines. Prefetching
   moves latency earlier; it cannot reduce the count.
4. **The ceiling is 1.14%.** `stalls_l3_miss` is 1.45% of the read path. A perfect,
   zero-cost oracle prefetcher recovers 1.14% of total runtime. A real one adds
   instructions to a path already at **IPC 1.808**, with no spare issue slots — it could
   come out negative.

**Contrast with why `-B` works on the lookup path:**

| | hash lookup | read loop |
|---|---|---|
| address pattern | `hc % capacity_`, uniformly random | strictly sequential |
| hardware prefetcher | cannot predict it | handles it natively |
| address known early? | yes, hash computable ahead | **no**, not until `read()` returns |
| misses avoidable? | yes, ~200 touches per line | no, compulsory |
| stall exposure | **23.60%** of cycles | **1.45%** |

## Ranked summary

| # | change | share attacked | effort | risk |
|---|---|---:|---|---|
| **A** | critical-section serialization | 1.94x CPU inflation at `-p 16` | moderate | output ordering |
| **F** | **upstream `-p 16` non-determinism** | **correctness, not speed** | investigation | see item F |
| ~~**B1**~~ | ~~`-march=native`~~ | **+0.92% SLOWER, rejected** | one flag | measured |
| **B2** | incremental reverse complement | **−6.4% measured**, reverted on request | two files | guards needed |
| **B3** | multi-sequence interleaving | unknown, composes with B2 | large | output ordering |
| **C** | delete `shrink_to_fit()` | 2.25% of total | one line | memory high-water |
| **D** | kseq buffer 16 KB -> 256 KB | **−0.88% measured, DONE** | one constant | none, kseq.h untouched |
| **E** | remove third copy | 1.68% of total | invasive | lifetimes |
| — | ~~software prefetch in read loop~~ | <=1.14% | — | **rejected** |

## Caveats

- **The profile is `-p 1`**, so it excludes thread contention entirely. Item A's cost is
  measured separately (the 1.94x figure) and is not visible in the §2 table.
- **The profile is the zero-lookup configuration.** At the 48.8 MB baseline the hash
  lookups return and dilute every share here. These numbers describe the workload *after*
  subsampling, which is the configuration we intend to ship.
- **One machine, one input file.** i7-11700, pod5_2 / pod5_15. The scanner share should
  generalise; the syscall and allocator shares depend on kernel and libc.
- **Two of the five estimates have now been falsified by measurement.** Item D was 60%
  too high; item B was the wrong sign entirely. Both were inferred from code structure and
  profiles rather than measured. Treat A, C and E as ranking hints, not magnitudes.
- **Item D's estimate was 60% too high before measurement** (~1.4% projected vs 0.88%
  actual), and its optimum was not where predicted. Treat the unmeasured estimates for
  A, B, C and E the same way — they indicate ranking, not magnitude.
- **This box returns silently wrong output at `-p 16` with exit code 0** and can deadlock
  in `futex_wait_queue`. Verify correctness at `-p 1`; guard long sweeps with `timeout`.
