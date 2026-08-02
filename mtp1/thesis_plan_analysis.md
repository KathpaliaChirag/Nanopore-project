# Analyse the MTP thesis plan and produce a corrected copy

## Context

`mtp1/thesis_plan.md` (saved this session) proposes two theses off the summer Kraken2 work. I verified its load-bearing claims against `kraken2opti/` — the reports, the measured sweeps, and the vendored Kraken2 source.

Most of the plan holds up. But **three claims that carry the most weight are contradicted by the project's own data**, and one of them sinks Thesis 2's central hypothesis. The plan also proposes as new work two things the repo already contains designs for.

The user wants the original preserved and a corrected copy written alongside, plus the findings written up. The `dorado-kraken-research/` repo the plan links to is not on this machine (it lives on Luna) — claims sourced only from there are marked unverified, and retrieving it becomes an explicit prerequisite step.

---

## Findings that drive the rewrite

### F1 — Double hashing cannot rescue 16-bit cells. This is arithmetic, not opinion.

Thesis 2's central hypothesis is that switching to double hashing "should let the 16-bit version work accurately without needing the confidence threshold." The project's own formula says otherwise.

From `kraken2opti/reports/eskape_cellsize_fp_analysis.md` §3–5:

```
FP_per_minimizer ≈ probe_length × 2^(−key_bits)
a foreign read fails once N_minimizers × FP ≳ 1   (N ≈ 1,000)
```

Probe length at the built load factor α = 0.70 (Knuth, unsuccessful search):

| scheme | probe length | cliff (check bits) |
|---|---:|---:|
| linear probing (today) | ½(1 + 1/(1−α)²) = **6.06** | 12.6 |
| double hashing | 1/(1−α) = **3.33** | 11.7 |

**Double hashing moves the cliff by 0.86 bits.** 16-bit cells have 10 check bits — below the cliff either way. False hits per foreign read go from 5.9 to 3.25; they need to be under 1.0.

Even the theoretical floor doesn't reach: at probe → 1 (unachievable, that's α → 0) the product is 0.98 — exactly at the cliff with zero margin. Probe length is a **linear** factor multiplying an **exponential** in `key_bits`, so it can never buy back a bit of cell width. The plan's "~6 → ~2.5" is roughly the right direction but the wrong conclusion is drawn from it.

### F2 — Double hashing probably makes the latency bottleneck *worse*

Kraken2's own source says so, at `kraken2opti/tools/kraken2/src/compact_hash.h:438`:

> `// Double hashing can have shorter probing paths, but less cache efficiency`

With 16-bit cells, 32 cells fit in one 64-byte line. A ~6-probe linear run stays inside 1–2 cache lines — **1–2 DRAM trips**. A ~3.3-probe double-hash chain scatters across ~3.3 random lines — **~3.3 DRAM trips**. Fewer probes, more misses.

This matters because the entire project is about DRAM trips. And it gets worse as cells get narrower — so **the two halves of Thesis 2 actively fight each other**: cell-width reduction increases cells-per-line, which is exactly what double hashing throws away.

### F3 — Thesis 1's headline deliverables are already designed

`kraken2opti/reports/kraken2_perf_lru_cache.md` §6 specifies: 8192 sets × **4 ways** × 16 B = 512 KB/thread, **LRU eviction**, per-thread and lock-free, wrapping the single `Get()` call site in `ClassifySequence()`.

Thesis 1's first bullet ("make it 4-way set-associative") and third ("give it real eviction logic") are that document. The genuinely new increment is **auto-sizing to the machine** and **LFU-vs-LRU**. That is a real contribution but a thinner one than the plan presents — worth rebalancing scope now rather than discovering it mid-thesis.

*(Caveat: "Patch 4" itself lives in the Luna repo and may differ from this design — the plan describes it as 16,384 slots / direct-mapped / no eviction, which does not match. Reconciling the two is a prerequisite, not a detail.)*

### F4 — The ~91% cache hit rate is an upper bound, not a prediction

The plan's top diagram asserts "cache hit, ~91% of the time," from the M5 measurement that 90.7% of lookups are repeats. But repeat rate is **capacity-independent** — it says a k-mer was seen before at *some* point in the run, not that it survived in a 16K-entry cache against 8.5 M distinct minimizers (`eskape_bitmask_plan.md`: 8,533,848).

Real hit rate is unknown and could be far lower. It is also **cheap to settle offline** — dump the minimizer stream once, replay it through a cache simulator at several sizes/associativities/policies. No Kraken2 rebuild, no Luna time. This should be step 0 of Thesis 1: it derisks the entire thesis, and it simultaneously answers the plan's own "nobody has measured how often the current design collides" risk.

### F5 — The auto-sizing rule as written overshoots by the thread count

The cache is **per-thread private**, so N threads × per-thread size must fit the **shared** LLC. Sizing each thread's cache to "half the per-socket cache" overshoots by N×. Correct form is `(½ × per-socket LLC) ÷ threads`: Luna ≈ 560 KB/thread (105 MB, 96 threads), Orion ≈ 256 KB/thread (4 MB, 8 threads). The existing design doc gets this right (8 MB total ÷ 16 threads = 512 KB). The plan also needs to reconcile "sized to fit L2" (private) against "fraction of LLC" (shared) — they are different targets.

### F6 — The bitmask is proposed on top of the one cell width already proven broken

The plan's diagram shows the bitmask cell as 10 check bits + 6 species flags. Those 10 check bits are exactly the configuration measured at 1-in-170 FP and +16.87% over-classification. The repo's actual bitmask design (`eskape_bitmask_plan.md`) uses a **40-bit cell — 34 check bits, FP 1-in-2³⁴**, which is why it works there.

Three further problems, all already in the repo:
- §9 measured **cross-organism minimizer sharing at 0.23%** — which refutes the bitmask's motivating advantage (lossless multi-membership applies to 0.23% of cells) and **explicitly recommends taxon-ID instead** for this project.
- The plan calls this "the least-precedented part" while a 577-line design doc for it already exists.
- 6 presence/absence flags discard the 35-node strain-level taxonomy the plan cites two paragraphs earlier.

### F7 — The headline bottleneck number needs one stated provenance

Three incompatible figures are in play for `Get()`:

| source | figure |
|---|---|
| gprof (`report.md`, `phase1_...md`, `plandoc.md`) | 80.65% of CPU time |
| perf record (`kraken2_perf_lru_cache.md` §3) | ~1% of CPU time |
| thesis plan | 0.65% of work / 96.24% of LLC misses |

`kraken2_perf_lru_cache.md` §3 and `plandoc.md` §0 already document why these diverge (`-pg`/mcount distortion, ~18% overhead). The plan's framing — negligible instruction share, dominant miss share — is the **physically coherent** one for a latency-bound function, and is likely the corrected figure from the Luna repo. It just needs its source named, because as written it silently contradicts every number in `kraken2opti/`. Memory also flags 80.65% as a known `report.md` error, which supports the plan's version — but that has to be stated, not assumed.

### F8 — What holds up (keep as-is)

- **The cell-width chart is real.** 83.73 / 83.75 / 84.48 / 90.95 trace exactly to `results/perf_threadsweep/perf_threadsweep_summary.md`.
- **The "16-bit looks higher, that's the problem" reading is exactly right** and matches `eskape_cellsize_fp_analysis.md`.
- **The double-hashing bit-slice caveat is correct** — `compact_hash.h:444` is literally `return (first_hash >> 8) | 1`, gated behind `#ifdef LINEAR_PROBING`, with `-DLINEAR_PROBING` set at `Makefile:4`. The plan is right that it can't just be re-enabled.
- **The DB-rebuild / format-autodetect risk is real** and correctly identified.
- **Prior art and Centrifuge sections are sound** — accurate, well-sourced, correctly scoped.

### F9 — The unclaimed win: 20-bit cells

14 check bits sits **above the ~13-bit cliff even with linear probing**. That is a 37.5% DB shrink with no confidence threshold, no probing change, no format break — and it is already measured (84.48%). The plan explicitly sets it aside as "not a shipped option." It is the cheapest real result on the table and should be promoted to a first-class option.

---

## Deliverables

Leave `mtp1/thesis_plan.md` untouched as the original record.

### 1. `mtp1/thesis_plan_analysis.md`

The findings above, written as a standalone review: claim → what the repo says → file:line → verdict. Ordered by how much it changes the plan. Explicit "verified / contradicted / unverifiable-from-here" status on each. Includes the probe-length arithmetic worked out in full so it can be checked independently.

### 2. `mtp1/thesis_plan_v2.md`

The corrected plan, same structure and register as the original so it stays readable to sir. Changes:

- **Thesis 2 reframed.** Drop "double hashing rescues 16-bit" as the hypothesis — it is refuted by F1. Replace with: (a) **20-bit as the recommended free win**; (b) double hashing investigated for what it actually affects — probe count vs. cache-line traffic, with F2's prediction that it *loses* on this workload stated up front as the thing being tested. A negative result there is publishable and defensible; the original framing would have produced one by accident.
- **Bitmask corrected** to a 40-bit / 34-check-bit cell, cross-referenced to `eskape_bitmask_plan.md`, with §9's 0.23% finding and its taxon-ID recommendation stated. Demoted from "least-precedented" to "designed, measured, and currently not recommended — here is what would change that."
- **Thesis 1 rescoped** around what is actually new: offline hit-rate/collision study first, then auto-sizing (with F5's corrected formula), then LFU-vs-LRU. The 4-way build becomes "implement the existing §6 design," not a research contribution.
- **Hit-rate claim downgraded** from ~91% to "upper bound; to be measured," with the trace-replay method as step 0.
- **Bottleneck number** given one sourced provenance with the gprof/perf discrepancy explained in a footnote rather than left silent.
- **Build order revised**: retrieve `dorado-kraken-research` from Luna and reconcile Patch 4 against `kraken2_perf_lru_cache.md` §6 becomes step 0; the offline cache study moves ahead of any rebuild since it needs neither.
- All broken `dorado-kraken-research/...` links marked `[Luna]` so they aren't mistaken for local paths; local equivalents linked where they exist.
- Mermaid diagrams updated where the corrections change them (the 16-bit-bitmask cell, the probing comparison, the order-of-operations flow).

---

## Verification

- Every number cited in both documents carries a `file:line` reference into `kraken2opti/`; re-grep each before finalising.
- The probe-length arithmetic (F1) is reproducible from the two Knuth formulas at α = 0.70 — include the worked values so a reader can check it without rerunning anything.
- Cross-check the v2 plan against `eskape_cellsize_fp_analysis.md` §5–6 and `eskape_bitmask_plan.md` §9 specifically, since those two sections carry most of the corrections.
- Confirm no claim in v2 rests solely on a `dorado-kraken-research` source without being marked unverified.
- Both files are documentation only — no code, no builds, no changes to `kraken2opti/`.
