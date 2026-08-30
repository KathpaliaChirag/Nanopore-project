# Implementation prompt: frequency-selected minimizer→taxon lookaside table

Hand this to another session (or to a project partner) to build and benchmark
the lookaside-table idea end to end. It is self-contained: it carries the
measured baseline, the two entry formats to try, and the four failure modes that
have already produced wrong answers on this box.

**Why three size tiers.** The sweep is ordered L3 → L2 → L1 because that is the
order of decreasing promise, not increasing:

| tier | table size | entries (12 B / 4 B) | simulated hit rate | verdict to test |
|---|---:|---:|---:|---|
| **L3** | 4 MB | 349 K / 1 M | 15% LRU, **25% oracle** | the only tier that might win |
| L2 | 256 KB | 21 K / 64 K | ~2% | around break-even at best |
| L1 | 4 KB | 341 / 1,024 | **0.34%** | predicted net −0.3% to −0.6% |

Break-even needs a 1.3–2.2% hit rate (probe cost 3–5 cycles ÷ 225 cycles saved
per hit). Running all three tiers is what makes the result decisive rather than
a single point that can be argued with.

**The prompt is an oracle experiment by design** — pass 1 counts minimizer
frequencies over the same file that pass 2 then times. That cannot be deployed
as-is, but it gives the ceiling. If the ceiling does not beat baseline, no
realistic version will and the idea is closed. If it does, the next question is
how to obtain that frequency profile cheaply.

---

## The prompt (3,438 characters)

```
TASK: Prototype and benchmark a frequency-selected minimizer->taxon lookaside table in kraken2, swept across L3-, L2-, and L1-resident sizes. Decide empirically whether it beats baseline.

MACHINE: i7-11700, 8C/16T. L1d 48KB/core, L2 512KB/core, L3 16MB shared.

BASELINE (measured, reproduce before changing anything):
  D=databases/eskape_32bit_fork   # 48.8MB, 12.2M cells, 8.9M occupied
  ./kraken2_bin/classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d -p 16 -g 2 -T 0 perpod5/pod5_15.fastq
  0.511s @ -p16 | 4.207s @ -p1 | 83.39% classified
  CompactHashTable::Get = 43.4% of cycles; stalls_l3_miss = 27.4%
  0.96 DRAM accesses/lookup; L3 hit rate 42.3%; MLP = 1.33
  29,054,665 lookups after the existing depth-1 skip; 708 cyc/lookup, 225 of them DRAM stall
  Prior exact-LRU simulation: 1K entries 0.34% hit, 64K 2.06%, 1M 14.97%, 4M 36.34%.
  Oracle frequency selection at 1M entries: 25.28%. Treat these as predictions to test, not facts.

IMPLEMENTATION
1. Work in a SCRATCH COPY of kraken2/. Never modify kraken2_bin/, databases/, or kraken2/src in place.
   Restore point: scripts/kraken2_cellsize_v2.patch.
2. Add a read-only, SHARED (not per-thread) direct-mapped table, probed in ClassifySequence
   (kraken2/src/classify.cc ~line 847) immediately before `taxon = hash->Get(*minimizer_ptr)`.
   Index = (MurmurHash3(min) >> 32) & (N-1). Per-thread copies would multiply footprint by 16 - do not.
3. Build BOTH entry formats:
   A) exact  {uint64_t key; uint32_t value;} packed to 12B - no false hits, results provably identical
   B) compact - reuse kraken2's 4B CompactHashCell packing (fingerprint+value); 3x denser but can
      return a wrong taxon on tag collision. Measure and report collision frequency, do not hide it.
4. Sweep sizes so the table lands in each level: L3 = 4MB, L2 = 256KB, L1 = 4KB. Both formats each.
5. Population: two-pass. Pass 1 (untimed) counts minimizer frequency over the input; pass 2 (timed)
   preloads the top N. This is an ORACLE upper bound, not deployable - label it as such in results.

DO NOT BREAK
- Keep the existing depth-1 last_minimizer/last_taxon skip intact.
- minimizer_hit_groups++ must stay in its current branch. A prior patch moved it and silently changed
  hit-group counts at frame boundaries.
- Raw `classify` defaults to -g 0 while the wrapper passes -g 2. Always pass -g 2 or results will look
  like a regression that isn't real.

VERIFY BEFORE BENCHMARKING
Output file AND report must be byte-identical to kraken2_bin/classify at -p 1 and -p 16, on pod5_15
and pod5_0. Format A must match exactly; report any divergence in format B.

BENCHMARK
- INTERLEAVE reps (base, variant, base, variant...). Never run sequential blocks - the powersave
  governor's boost behaviour produced a false 24% result on this box before.
- 5 reps each, report median.
- perf stat -e cycles,cycle_activity.stalls_l3_miss,LLC-loads,LLC-load-misses,\
  l1d_pend_miss.pending,l1d_pend_miss.pending_cycles,dtlb_load_misses.walk_active
- Per variant report: runtime, table hit rate, MLP, L3 miss rate, net cycles/lookup vs baseline.

BUILD NOTE: keep -DLINEAR_PROBING in CXXFLAGS. After changing flags run `rm classify.o` first - make
will not rebuild otherwise (this bit us before: all variants came out md5-identical).

DELIVER: a table of size x format x (runtime, hit rate, net %), and a one-line verdict on whether any
configuration beats baseline. If none does, say so plainly.
```

---

## Related documents

- `CACHE_TABLE_ANALYSIS.md` — the analysis this prompt tests, including the exact
  LRU stack-distance measurement and the `-M 4000000` result (−26.7%).
- `CELLWIDTH_DB_BUILD.md` — how the 16/20/24/32-bit databases were built.
- `scripts/kraken2_cellsize_v2.patch` — the source restore point.
