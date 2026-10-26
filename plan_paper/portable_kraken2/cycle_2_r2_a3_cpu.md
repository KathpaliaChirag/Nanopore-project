# cycle 2, round 2: a3_cpu

no new fetches. sources: the cycle-2 R1 files ("a1 src N" etc.) and my N1-N8. new id: M44.

---

## 1. counters

**M27 (a1), prologue: agree, in a better form.**
- on a capped db RC1's phase 1 already hashes each changed minimizer for the cap check [external: a1 cycle-2 b]. so prefetch the first 8 keys of each read right there, when they are pushed. the read's whole scan then becomes lead time.
- example: a 150 bp read has ~116 positions; at 15-39 ns per base that is ~2-4 µs, or 20-40 dram latencies [arith on cycle-1 numbers and a4's ~107 ns].
- the cap at 8 keys keeps long reads from flooding L1 [guess]. it merges with M2's hash-once. 0.25 day.

**M26 (a1), AMAC: build it as a fast path, and gate it on table > llc.**
- save state only when a probe reaches its line's end: 7% of hits, 32% of misses [arith]. then the coroutine-class cost ("two function calls" [external: a1 src 2]) falls only on those lookups.
- the 3-way outcome branch will mispredict on them [guess].
- on luna 50MB the next line comes from L3 (~33 ns [external: a4 cycle-1 src 8]), so it is pure overhead there.
- AMAC's 1.13x over SPP comes from chained buckets that always multi-hop [external: a1 src 1]. kraken2 resolves 68-93% of lookups in one line [arith], so 1.13x is a ceiling.
- luna: M8a at m = 2 is cheaper. one channel (H1): M26 wins, because it fetches no extra lines.

**M28 (a1), short reads: add a thread axis.**
- a 3 MB block of 150 bp reads holds ~8-10K records vs ~480 nanopore reads [arith], so per-record parse cost rises per base.
- S19's in-lock parse should bind at fewer threads than ~60 [repo: next_steps 4a; guess on direction].
- time S19 vs RC1 at 32, 64 and 96 threads. that measures RC1's out-of-lock parser for short reads.

**M30 (a2 + a4), fault-ahead. role extra: the cost of ~10K `posix_fadvise` calls.**
- calls: ~10.7K per 10-read block on an uncapped db, ~1K on a capped one [arith]. at an assumed 1-2 µs each (a2's guess) that is 11-21 ms on one thread [arith on guess].
- what it hides: ≥ 1.1 s on nvme and 11-96 s on gp3 at queue depth 1 [arith: a4]. so the cpu cost is ~1-2% of the hidden time.
- page numbers come from the slot S12 already computes: (32 + idx x 4) / 4096 [external: a2 cycle-1 header]. the sort is under 1 ms [guess].
- merging adjacent pages buys little: 10.7K of 1.86M pages is 0.6% density [arith].
- cautions: a call may block when the device queue is full [guess], so issue the calls outside every lock. gate on `mincore` residency, so warm runs make 0 calls.
- same effect with no new syscall type: 8-16 helper threads touching pages. verdict: the cpu cost is fine; queue-depth scaling decides.

**M31 (a2), input `DONTNEED`: never inside `critical(seqread)`.**
- S19 reads input inside the lock [repo]. one call per block at an assumed 50-100 µs, over 3,974 blocks [arith], is 0.2-0.4 s added to a 3.88 s serial floor [measured; cost guessed].
- issue it after the lock, for the previous block's range.

**M32 (a2), detached teardown. role extra: the fork.**
- the fork is safe only before any thread exists: first thing in `main`, before the parallel load and libgomp's team [guess: posix fork-in-threads rule, not fetched]. the worker must close stdout before signalling the parent, or a pipe consumer misses EOF.
- **the real cost is that back-to-back runs pay it.** run N+1 allocates while run N's orphan still frees 111 GB, so its huge pages can fail. that is luna's measured variance mechanism: 20.2 s right after a small-page binary vs 13.1-13.3 s in a row [repo: talk track S14]. on H4 it can cost the next run more than the 4.5 s it hides [arith].
- remove the cost instead: M44.

**M33, M51 (a2, a4): agree.** no cpu cost. M51's `O_DIRECT` needs aligned buffers only.

**M20' (a4): agree.** libgomp starts "one thread per CPU" and ignores quotas [external: a4 N8]. the same cap must drive the loader, or the quota stall comes back during the load.

**M62 (a5): agree,** but only wait for the output lock when `TMPDIR` is missing or full. waiting by default brings back the serial output wall [external: cycle-1 a3 S3].

**M64 (a5): decode is not the limit.** a branch-free bitmap expand runs ~1-2 GB/s per core [guess, cycle-1 a3 r2], above emmc and sata rates. it stays gated by M61.

**M41, M40 (mine).**
- M41: break runs on a value change. ambiguous runs keep the last non-ambiguous value, which resets only per frame [repo: `s9_patch.py` line 47].
- M40: the 10-minute `objdump` kill test stands.

### M44 (new). parallel table release before exit
- **byte-identical:** yes, it runs after all output is closed.
- *wrong intuition:* "exit cost belongs to the kernel, so only hiding it or huge pages can help."
- *mechanism:* teardown "runs synchronously in the dying task's context" [external: a2 cycle-2 src 4], on one thread. S10 split page work across threads and the load went 56 s to ~6 s [measured]. at exit, N threads can each `madvise(MADV_DONTNEED)` their own 64 MB chunks, so the process exits with little left to free. whether `DONTNEED` on one mapping scales across threads is [UNCLEAR: mmap-lock behaviour not fetched].
- *example:* s10's 4.5 s exit on 103GB at 4 KB pages [measured] would be ~0.5 s if it splits like the load (~9x) [arith on guess]. with thp it is already ~0.2 s [arith: a2 src 4].
- **gain:** H4 103GB few-read runs, 1-4 s when thp fails [guess]; ~0 for tables ≤ 16 GB. **days:** 0.5.
- **kill:** E1's exit column, then a 20-line test (touch 100 GB, free it with 1 vs 16 threads).

---

## 2. fact fixes

1. **FINAL item 8: confirm** [external: a5 N2]. reword: "`-M` runs it; exact out-of-core is the only byte-identical route at device speed when `-M` thrashes."
2. **M11 cells [UNCLEAR] until M61: confirm.** the outside evidence runs from 1.5x [a5 N2] to "days" [a5 N6].
3. **one-shot assumption: confirm** [external: RC1 `-D`, EPI2ME, a5].
4. **RC1 output: confirm as one outside test** [external: a5 N5]. M1 still runs `cmp`, plus a whitespace-aware compare.
5. **M2 8GB ~1.08x: confirm.** 1 / (0.98 x 0.97 x 0.97) = 1.084 [arith].
6. **M9 cells: capped H1 ~35x and H2 40-300x hold** [arith]. **reject H2 uncapped "4-14x".** a4's own inputs (copy 19-30 s; faults 1.1-5.4 s) give **3.6-28x** [arith]. the gp3 flip holds.
7. **M20 orin ~11.6x: the arithmetic holds** [arith on repo]. but the 4.23 s is sys cpu time used as load time [repo: `RESULTS.md` 1.4], so that split is [UNCLEAR].
8. **M21: confirm.** "a tuned arm tier".
9. **H1 dual-channel: confirm** [external: a4 N7].
10. **exit scaling: arithmetic holds** (1.96 s, 0.19 s). luna's measured 3.9-11.4 s shows it does not transfer [measured]. a prediction for E1 only.

**concession.** the WSL2 run's db is named in its setup notes: "`~/eskape_db` - pre-built 8 GB standard" [repo: `knowledge_base.md` 18.1, via a1]. my cycle-1 vote was wrong.

---

## 3. rankings

### top 10 build

| rank | id | one line |
|---|---|---|
| 1 | M2 (+M3, M27 push-time) | the installed binary; hash once, prefetch at push |
| 2 | M20' (+M17, M62) | default users; quota-aware; the cap also drives the loader |
| 3 | M4 | per-position work, every isa; ~60% of cycles on a capped db [measured gprof] |
| 4 | M41 | per-position work in `ClassifySequence` (25.1%); subsumes M3 on S19 |
| 5 | M9 (+M24, M51, M33) | cold and small-ram runs, f-aware |
| 6 | M30 | queue depth 1 → many for M9's cold map; cpu cost ~1-2% of what it hides |
| 7 | M5 | both wrappers inflate gz serially |
| 8 | M27 | short-read users, 0.25 day; own row so it is not lost |
| 9 | M40 | 0.5 day, or 10 minutes to kill |
| 10 | M26 (M8a first) | uncapped dbs on small-cache boxes; gated on table > llc |

below: M11 (+M64, after M61), M21 (+M42, with E3), M44 (after E1), M31, M32 (use M44), M10, M13, M7, M14, M15, M16, M18 (M43 may kill it), M19, M6.

### top 5 measure-first

| rank | id | one line |
|---|---|---|
| 1 | M22 | f and d per db |
| 2 | M1 (+M28 at 32/64/96 threads, exit column, RC1 `objdump`) | base, plus evidence for M27, M6 and M40 |
| 3 | cpu gate | gates M4 and M41, ~20 min |
| 4 | E1 (+cold pair, qd1 vs qd16, exit column) | gates M9, M30, M44, M32 |
| 5 | M61 | gates M11 |

next: M60, the orin probe, M43.

---

## 4. strongest counter

**M32 hides the exit tax by moving it into the next run.** a back-to-back run allocates while the orphan still frees the old table, so its huge pages fail. that is luna's measured 103GB variance (20.2 s vs 13.1-13.3 s [repo]). remove the cost (M44), and only if E1 shows it exists.
