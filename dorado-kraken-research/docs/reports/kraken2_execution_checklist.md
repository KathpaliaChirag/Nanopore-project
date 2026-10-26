# Kraken2 Optimisation: Master Execution Checklist

This is the single linear path from where we are today to the target of ≤ 2.6 s wall on hac,
32T, node0. Follow it top-to-bottom. After every block, paste the SUMMARY line back in chat,
or commit it to `Luna/profiling/results_kraken2.md`.

**Today's baseline (locked):** 4.405 s wall, 32 threads, `numactl --cpunodebind=0 --membind=0`
on hac fastq (104,918 reads, 355 Mbp).

---

## Phase 0: Measure first (no rebuilds yet)

Before touching any code, we need to know which patches actually matter here, and that's
what M1-M7 answer. Run all of `Luna/experiments/pending_measurements.md` (M1-M7). It takes
under 10 minutes total.

After Phase 0 you should know:
- cell size (32 or 40 bit)
- load factor
- DTLB miss rate
- DRAM bandwidth utilisation
- minimizer reuse rate
- AVX-512 status

Decision gates from Phase 0:
- M4 ratio < 0.5 → we are **latency-bound**, proceed with v1 patches as planned.
- M4 ratio > 0.7 → **bandwidth-bound**, escalate to DB compression or shrink the k-mer
  acceptance threshold instead. Do NOT spend cycles on LRU.

These gates decide the whole rest of the checklist, so don't skip Phase 0 even though it's tempting to jump straight to patching.

---

## Phase 1: Apply Patches 1-3 (zero-risk, no semantic changes)

These three go first because they're the cheapest, lowest-risk wins available, so we take
them before anything riskier. Source patches are in `kraken2_get_optimizations.md` §2.

```bash
cd ~/kraken2-src
git -C . status         # ensure clean
cp ~/Luna/experiments/kraken2_opt_v1.patch .
git apply --whitespace=nowarn kraken2_opt_v1.patch
cd src && make clean && make -j 96
cp classify ~/kraken2-build/classify.v1
```

Benchmark:
```bash
bash ~/Luna/experiments/run_kraken2_opt_v1.sh    # produces a SUMMARY block
```

Acceptance:
- wall drops by ≥ 5% vs 4.405 s (target: ≤ 4.18 s).
- `kraken2 --report` output is byte-identical to baseline (the script asserts this).

If wall doesn't drop, undo the patches one at a time and re-run to isolate which one is at
fault.

---

## Phase 2: Decide on Patch 4 (thread-local LRU) using M5

Patch 4 only pays off if k-mers actually get reused across lookups, so the M5 reuse rate is
what decides whether to apply it, and at what size. Read `m5_minimizer_histogram.txt`'s
`reuse_rate`:

| reuse_rate | action | LRU_BITS |
|---|---|---:|
| > 0.30 | apply Patch 4 as written | 14 (16K entries, 256 KB/thread) |
| 0.10-0.30 | apply with smaller cache | 13 (8K entries, 128 KB/thread) |
| < 0.10 | **skip Patch 4** | n/a |

If applying: edit `src/classify.cc` per `kraken2_get_optimizations.md` §2 Patch 4, rebuild,
and re-run the same benchmark script. Acceptance is another ≥ 5% drop, or a final wall
≤ 3.5 s.

---

## Phase 3: Layer v2 patches if Phase 2 leaves > 3.0 s

If we're still above 3.0 s after Phase 2, there's a second round of smaller patches in
`kraken2_get_optimizations_v2.md` worth stacking on top. Apply in order:
1. Patch 6: `final` keyword + concrete-typed dispatch (-2% to -5%).
2. Patch 7: single MurmurHash via `GetByHash` (-1% to -3% on std_8).
3. Patch 8: `ResolveTree` O(N²) → O(N) (-2% to -6%).
4. Patch 9: skip output formatting when output is `/dev/null` (-1% to -2%).

After each patch, run the same benchmark, check report-identity, and append the SUMMARY.

**Stop rule:** if two consecutive patches each deliver less than 2%, that's diminishing
returns. Stop there.

---

## Phase 4: Only if still > 3.0 s wall

If the checklist gets this far, the remaining wins are heavier and riskier, so weigh them
against the effort before starting. Two options remain:

- **Patch 10** (batched Get with cross-call prefetch pipeline), sketched in v2 §Patch 10.
  It's invasive, it changes the ClassifySequence loop structure, and it's only worth it if
  the simpler patches stack to less than expected.

- **DB rebuild** with `LINEAR_PROBING` off → on confirmed, a smaller `value_bits_` if the
  value range allows it, and minimizers sorted by genomic locality. Each of these is
  multi-day work and needs storage for a fresh DB.

Discuss with Kolin sir before starting Phase 4.

---

## Phase 5: Final reporting

Everything above only counts once it's written down where sir and future us can find it.
Write to `kraken2_optimisation_report.md` (the 2026-05-31 deliverable):
- Phase 0 measurement table (M1-M7 results).
- Per-patch SUMMARY block (wall, LLC misses, dTLB misses, IPC).
- One paragraph each on which patches stacked cleanly and which did not.
- Final stack: cumulative speedup vs 4.405 s and vs 5.635 s (96T default).

Then commit `kraken2_get_optimizations.md`, `kraken2_get_optimizations_v2.md`, and
`Luna/experiments/{kraken2_opt_v1.patch, run_kraken2_opt_v1.sh, pending_measurements.md}`
to the project repo. That closes the checklist out.

---

## Quick checklist (printable)

This is the same five phases above, flattened into one printable list so you can tick items
off without flipping back and forth.

- [ ] M1: header read
- [ ] M2: dTLB miss rate
- [ ] M3: perf annotate Get
- [ ] M4: DRAM bandwidth
- [ ] M5: minimizer reuse
- [ ] M6: c2c HITM
- [ ] M7: SIMD instruction mix
- [ ] Patch 3 (flags) measured
- [ ] Patch 2 (huge pages) measured
- [ ] Patch 1 (prefetch) measured
- [ ] Patch 4 (LRU) decision made and measured
- [ ] Patch 6 (final/devirt) measured
- [ ] Patch 7 (single hash) measured
- [ ] Patch 8 (ResolveTree O(N)) measured
- [ ] Patch 9 (output skip) measured
- [ ] Final report written
