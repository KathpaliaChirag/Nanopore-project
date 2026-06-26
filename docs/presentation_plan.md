# Kolin Sir Presentation Plan
## 20-Agent Consensus (2 Iterations × 10 Agents)

---

## VERDICT BEFORE YOU START

**NO-GO to present optimisation results without:**
1. **Run M1–M7 on Luna** (~1 hour, commands ready in `Luna/experiments/pending_measurements.md`)
2. **Apply `kraken2_opt_v1.patch` and record the before/after delta** (even one number converts "plan" to "result")
3. **Run M5 specifically** — k-mer reuse rate decides whether Kolin sir's LRU cache (Patch 4) is useful at all

**Everything else is presentable as-is.** The diagnostic half (slides 1–9) is fully supported by data.

---

## PRE-MEETING FIXES (do before walking in)

| # | Action | Time | Why critical |
|---|--------|------|-------------|
| 1 | Run M5 on Luna (reuse rate) | 30 min | Kolin sir designed Patch 4 — he WILL ask |
| 2 | Run M1, M2, M4 (hash header, DTLB, DRAM BW) | 30 min | Gates patch parameters |
| 3 | Drop MADV_WILLNEED from patch | 5 min | It conflicts with MADV_RANDOM — fix before being called out |
| 4 | Apply patch, run benchmark, record delta | 1 hour | Section 6 cannot be blank |
| 5 | Add A. baumannii note to sample_targeted DB description | 5 min | Disclose proactively |

---

## REVISED SLIDE ORDER
*(Agent 9 corrected the original — accuracy moved to slide 2; behavioral classes before NUMA)*

---

### Slide 1 — The Thesis (90s)
**Visual:** Horizontal paired bar chart — two bars per function (Instructions% vs LLC Read Misses%)
- `CompactHashTable::Get()`: 0.65% instructions — **96.24% LLC read misses**
- `MinimizerScanner::NextMinimizer()`: 48.23% instructions — **0% LLC read misses**
- All others: remainder

**Annotation:** Red callout box on Get() row: "0.65% of work, 96.24% of DRAM reads"

**Takeaway:** One function causes essentially all DRAM traffic despite negligible CPU share.

**Caveat on slide:** "(cachegrind: simulated 104 MB cache — attribution robust, absolute counts approximate)"

---

### Slide 2 — Database Choice = Diagnosis (90s)
**Visual:** Species comparison table — same 104,918 reads, three databases:

| Species | eskape_650mb | standard_8gb | pluspf_103gb |
|---------|-------------|-------------|-------------|
| *P. aeruginosa* | **65.28%** | 31.41% | ~38% |
| *E. coli* | **0%** | 14.45% | ~18% |
| *K. pneumoniae* | **0%** | 4.52% | ~7% |
| *A. baumannii* | **0%** | 0% | **0.25%** |
| Total classified | 65.28% | 95.77% | 98.86% |

**Annotation:** Red box over eskape_650mb zeros: "~33,000 reads force-assigned to Pseudomonas — E. coli and Klebsiella invisible"

**Takeaway:** Wrong DB → wrong species report → wrong antibiotic. Accuracy forces large DBs.

**Note for speaker:** Mention A. baumannii gap: "sample_targeted DB is missing A. baumannii — reference was suppressed on NCBI; PlusPF detects it at 0.25%."

**Critical transition to slide 3:** *"Since accuracy forces us to large databases, and large databases are DRAM-bound, the only lever is the lookup itself."*

---

### Slide 3 — Hardware Re-orientation (45s)
**Visual:** Side-by-side hardware table

| | Luna | Orion |
|--|------|-------|
| CPU | Xeon Platinum 8468 (Sapphire Rapids) | ARM Cortex-A78AE |
| Cores | 96c / 192t | 12c |
| LLC | **210 MB** | **4 MB SLC** |
| RAM | 503 GB DDR5 | 64 GB LPDDR5 |
| NUMA | 2 sockets | 1 node |

**Takeaway:** The 50× difference in cache capacity (210 MB vs 4 MB) determines every machine-specific result.

---

### Slide 4 — Why gprof Was Wrong + Flamegraph (2.5 min)
**Part A — gprof correction table:**

| Tool | What it measures | Get() share |
|------|-----------------|-------------|
| WSL2 gprof | User-space time only, different DB | 67% (wrong) |
| Luna gprof | User-space time only | 23.23% |
| Luna perf flamegraph | Wall time | 12.10% |
| Cachegrind | DRAM read attribution | 96.24% |

All four are consistent: gprof 23.23% × 18.6s user = 2.43s = 12.1% of 22.8s wall. Three tools, one answer.

**Part B:** Embed `Luna/profiling/flamegraph_hac_32t.svg` with three callout annotations:
- MinimizerScanner: 25.6% (pure compute)
- I/O / page-cache copy: ~20% (NOT disk — see tmpfs slide)
- CompactHashTable::Get: 12.1%

**Takeaway:** Tool choice changed the optimization target. perf and cachegrind agree; gprof user-space framing is misleading.

---

### Slide 5 — Three Behavioral Classes (2.5 min)
**Visual:** Multi-line speedup vs thread count chart
- X-axis: Thread count (1, 2, 4, 8, 16, 32, 64, 96) — log2 scale
- Y-axis: Speedup over 1T (0–25×) — linear
- One line per DB, colored by class:
  - Green (pre-cliff): sample_targeted 50 MB → peaks **21.26×** at 32T
  - Orange (bandwidth-sat): eskape_650mb 142 MB → peaks **21.96×** at 64T; eskape_human_4gb 3.8 GB → peaks **10.57×**
  - Red (Amdahl-limited): standard_8gb 7.6 GB → **3.47×**; standard_16gb 15 GB → **2.93×**
  - Dark red: pluspf_103gb 103 GB → **1.72×**
- Horizontal dashed lines at each class ceiling
- Bracket annotation between 50 MB and 142 MB lines: "Cache cliff: 50 MB fits LLC, 142 MB doesn't"

**Takeaway:** DB size class determines the scaling ceiling — adding threads cannot overcome the cache cliff.

---

### Slide 6 — Luna vs Orion: The Cliff Is Machine-Specific (2 min)
**Visual:** Grouped bar chart — LLC miss rate% by DB size, Luna vs Orion

| DB | Luna LLC miss% | Orion LLC miss% |
|----|---------------|-----------------|
| sample_targeted 50 MB | **10.19%** | **78.92%** |
| eskape_650mb 142 MB | 30.70% | 80.75% |
| eskape_human_4gb 3.8 GB | 56.85% | 77.28% |
| standard_8gb 7.6 GB | 76.59% | 68.19% |
| standard_16gb 15 GB | 80.15% | 71.36% |

**Annotation:** Vertical dashed line between sample_targeted and eskape_650mb on Luna bars: "Luna cliff". Bracket over all Orion bars: "Orion: ALL DBs post-cliff (SLC = 4 MB)"

**Takeaway:** The 50 MB DB that fits in Luna's 210 MB LLC still overflows Orion's 4 MB SLC. There is no pre-cliff regime on Orion for any database in this experiment.

---

### Slide 7 — NUMA: 21.8% Free (30s)
**Visual:** Four-row before/after table:

| Config | Wall time | IPC | DRAM stalls |
|--------|-----------|-----|-------------|
| 96T, default | 5.635s | 1.58 | 12.19B cycles |
| 32T, node0+node0 | **4.405s** | **1.86** | **6.44B cycles** |

**Annotation:** Arrow: "21.8% faster — zero code change"

**Takeaway:** Already captured. Memory pinning halved DRAM stall cycles without touching source.

---

### Slide 8 — Latency-Bound, Not Bandwidth-Starved (90s)
**Visual:** Horizontal gauge + key data points
- DDR5 theoretical peak: ~300 GB/s (8-channel, single socket)
- Observed DRAM bandwidth (M4, all DBs): **5–11% of peak**
- IPC at pluspf_103gb, 96T: **0.90** (below 1.0 — more stalls than completions per cycle)
- DRAM stalls at 32T node0: 6.44B cycles / 25.38B total stalls = 25.4%

**Takeaway:** The memory bus has 90% headroom. The bottleneck is latency per lookup, not bandwidth. Prefetch and LRU cache address the right problem.

---

### Slide 9 — tmpfs Negative Result (90s)
**Visual:** Two-row comparison
- Normal run: 4.405s
- tmpfs run (FASTQ in /dev/shm): **4.395s** (no improvement)

Flamegraph crop showing I/O tower (~20%) with annotation: "This is `copy_page_to_iter` — page-cache → userspace copy. Not disk I/O."

**Takeaway:** An entire optimization class (storage I/O) was eliminated with one experiment. The 20% flamegraph tower is a memory-to-memory copy, not disk access — Luna's 503 GB RAM had already cached the 703 MB FASTQ.

---

### Slide 10 — Patch Design (2 min)
**Visual:** 4-row table

| Patch | Target | Mechanism | Gate |
|-------|--------|-----------|------|
| 1 | Compiler | `-march=sapphirerapids -flto -funroll-loops` | M7 SIMD baseline |
| 2 | mmap | `MADV_HUGEPAGE + MADV_RANDOM` | M2 dTLB miss rate |
| 3 | `compact_hash.h Get()` | `__builtin_prefetch` one cache line ahead | M1 cell size + load factor |
| **4** | `classify.cc` | **Thread-local 16K-entry direct-mapped k-mer cache, 256 KB/thread, L2-resident** | **M5 reuse rate** |

**Credit Patch 4:** "Patch 4 is Kolin sir's design — thread-local Fibonacci-hashed direct-mapped cache targeting L2 residency."

**Note for speaker:** "TBB was considered but thread_local avoids scheduling overhead for this latency-bound workload. Fibonacci hash over LSH — uniform distribution with O(1) lookup. Happy to revisit either."

**Important:** Do NOT quote any improvement percentages. State: "Projected gains are gated on M1–M7 results."

---

### Slide 11 — Phase 2: M1–M7 Ready (90s)
**Visual:** Two-phase Gantt

```
Phase 1 COMPLETE — Cross-DB Characterisation
  ✓ 6 DBs × 3 models × 2 machines × 192 thread levels
  ✓ Three behavioral classes + LLC cliff located
  ✓ DRAM bandwidth confirmed latency-bound
  ✓ NUMA free win captured (21.8%)

Phase 2: Pre-Implementation Calibration (M1–M7)
  M1  Hash table geometry      → prefetch stride (Patch 3)
  M2  dTLB pressure            → huge pages decision (Patch 2)
  M3  perf annotate            → confirms miss line in Get()
  M4  DRAM bandwidth (IMC)     → latency vs bandwidth
  M5  Minimizer reuse rate     → LRU cache expected gain (Patch 4) ← RUN TODAY
  M6  perf c2c                 → false-sharing check
  M7  SIMD status              → AVX-512 baseline

Time to run M1–M7: ~10 minutes on Luna.
Decision gate: if M5 reuse rate < 5%, Patch 4 is dropped.
```

**Takeaway:** M1–M7 are calibration measurements, not exploration. Each one sets a patch parameter. Standard practice: measure first, then optimise with numbers in hand.

---

### Slide 12 — Summary + Next Steps (60s)
**Visual:** Three columns

| Confirmed | Designed & Ready | Next |
|-----------|-----------------|------|
| 96.24% LLC misses from Get() | 4-patch set staged | Run M1–M7 on Luna |
| NUMA: 21.8% free | kraken2_opt_v1.patch | Apply patch, measure delta |
| Latency-bound (5–11% DDR5 BW) | M1–M7 scripted | Fill Section 6 of report |
| tmpfs: disk I/O ruled out | | Orion reads_fast |
| 3 behavioral classes | | Bisect 50–142 MB cliff |
| PlusPF ceiling: 98.86% | | |

---

## OPENING SCRIPT (3 min — exact words)

> "Good morning Kolin sir, welcome back.
>
> Just to quickly re-orient — we're profiling Kraken2, the k-mer classifier, running on clinical samples from AIIMS. The input is nanopore reads from ICU patients — P. aeruginosa, E. coli, K. pneumoniae — and the question is: where does the time actually go?
>
> The answer, and this is the number I want you to hold onto for the whole talk, is this: CompactHashTable::Get() executes zero-point-six-five percent of all instructions. Just 0.65%. But it generates ninety-six-point-two-four percent of every last-level cache miss in the entire run. That's from cachegrind on Luna, single thread, HAC reads. So the classifier is spending almost all of its time waiting on one tiny function that's hammering DRAM.
>
> And it's not because we're doing a lot of work there. The other heavy function, MinimizerScanner, does forty-eight percent of all instructions — and it has zero LLC misses. Pure compute, never touches DRAM. So we have a clean separation: compute on one side, memory on the other, and the memory side is the wall.
>
> I also want to flag something we got for free. Just pinning to 32 threads on NUMA node zero dropped runtime from 5.6 seconds to 4.4 — a 21.8% improvement without touching a line of code. That's already captured.
>
> The four-patch set is written — compile flags, huge pages, prefetch, and your 16K LRU cache design. But M1 through M7 need to run first to calibrate the parameters. We can run M5 today and know the reuse rate within the hour."

---

## CLOSING SCRIPT (2 min — exact words)

> "So to summarise where we stand.
>
> Three things are firmly established. First, tmpfs makes no difference — the DB is hot in the page cache either way, so storage I/O is ruled out as a direction. Second, we have a clean three-class taxonomy of database behaviour: pre-cliff below 50 MB, bandwidth-saturated from 142 MB, and Amdahl-limited at 8 GB and above. Third, NUMA pinning gives 21.8% free.
>
> What separates 'characterized' from 'optimized' is two things: M1 through M7 — the pre-patch measurements that will tell us the prefetch stride, TLB pressure, and crucially the k-mer reuse rate inside Get() — and then the actual patch benchmark against those baselines.
>
> My ask today is simple: we can run M5 right now on Luna and know the k-mer reuse rate within the hour. That's the number that decides whether your LRU cache is a 10% win or a 40% win.
>
> The full picture is close. The bottleneck is identified, the patches are written, and the machine is idle."

---

## Q&A PREP — 8 Hard Questions

**Q1: "What is the k-mer reuse rate?"**
> "M5 has not been run yet — it is the first thing in Phase 2. The LRU cache design is architecturally sound regardless, but M5 confirms whether the hit rate justifies the 256 KB/thread cost. We can run it today."
*Proactively raise: Yes — mention M5 before being asked.*

**Q2: "Did you apply the patch? What is the actual speedup?"**
> "The patch has not been applied. M1–M7 must run first so we have a clean calibrated baseline for each delta. Projected improvement is positive but I won't quote a number until it's measured."
*Proactively raise: Yes — own this upfront.*

**Q3: "Why didn't you use TBB and LSH as I specified?"**
> "TBB was evaluated but `thread_local` avoids its task-stealing overhead for this latency-bound workload — we're not scheduling tasks, we're hiding DRAM latency. Fibonacci hashing gives uniform distribution with O(1) lookup, no training cost. Happy to prototype TBB if you'd prefer to compare."
*Proactively raise: Yes, one sentence when describing Patch 4.*

**Q4: "What happened with the neural prefetcher work?"**
> "No documented progress on the neural prefetcher — it was deprioritised in favour of completing the AccuracyDrift cross-DB characterisation. I can propose a timeline for a literature survey and prototype."
*Raise: Only if asked.*

**Q5: "MADV_HUGEPAGE and MADV_RANDOM together — those may conflict, no?"**
> "Yes sir — MADV_WILLNEED triggers readahead that MADV_RANDOM suppresses. WILLNEED has been dropped; the patch now applies MADV_HUGEPAGE + MADV_RANDOM only. HUGEPAGE reduces TLB pressure; RANDOM prevents wasteful sequential prefetch. M2 will confirm whether TLB was actually the bottleneck."
*Raise: Yes, proactively as "one patch correction before M1–M7."*

**Q6: "Why is Section 6 blank? This was due a month ago."**
> "The AccuracyDrift cross-DB experiment — six databases, two machines, 192 thread levels — was your Meeting 5 assignment and ran through June. Section 6 requires M1–M7 data and patch delta, both of which are Phase 2. The delay is real; the path forward is one Luna session."
*Raise: Yes, acknowledge before it's pointed out.*

**Q7: "The cache cliff bracket is 92 MB wide. Can you narrow it?"**
> "Not yet — no intermediate database was tested in that range. The effective random-access capacity of the 210 MB LLC for a uniform random workload is roughly 40–60% of nominal, which brackets the cliff at ~85–126 MB. Building a ~90 MB database and bisecting is a concrete next step."
*Raise: Only if asked.*

**Q8: "All your profiling is from one sample. How does this generalize?"**
> "It's a stated limitation. The LLC miss pattern depends on k-mer diversity, which varies with sample composition. This sample — dominated by three species — is a good clinical archetype for ESKAPE diagnostics, but generalisation to diverse metagenomics needs validation with additional samples."
*Raise: Only if asked, one sentence when discussing LRU.*

---

## CHART SPECIFICATIONS

### Chart A — 0.65%/96.24% Split
- Type: Horizontal paired bar (Instructions% = blue, LLC Misses% = red)
- Rows: Get(), MinimizerScanner, All Others
- Key callout: red box on Get() row

### Chart B — Three Behavioral Classes
- Type: Multi-line speedup vs threads, log2 x-axis, color-coded by class
- Data: 5 DB lines from RESULTS.md §1.1 Luna reads_hac tables
- Annotate: class name brackets + speedup ceiling dashed lines

### Chart C — NUMA Free Win
- Type: Grouped bar, normalized to 96T=1.0
- Metrics: Wall time, IPC, DRAM stalls (3 bars per config)
- 2 configs: 96T interleaved (grey), 32T node0 (blue)

### Chart D — Luna vs Orion Cache Cliff
- Type: Grouped bar, LLC miss rate% by DB size
- Luna (blue), Orion (orange)
- Annotate: "Luna cliff" between 50MB and 142MB; "Orion: all post-cliff" bracket

### Chart E — Accuracy vs DB Size
- Type: Line chart with two series (reads_hac solid, reads_sup dashed)
- X-axis: DB size log scale; Y-axis: classified% (60–100%)
- Annotate: red circle at 142MB "accuracy trap"; arrow to 7.6GB "jump to 95%+"

---

## EXISTING FILES USABLE AS SLIDES

- `Luna/profiling/flamegraph_hac_32t.svg` — use directly as Slide 4 Part B
- `Luna/profiling/matmul/report/graphs/05_tma_stacked.png` — appendix (TMA breakdown)
- `Luna/profiling/matmul/report/graphs/06_l3_bound_headline.png` — appendix (L3-bound cost)
- `Luna/profiling/matmul/report/graphs/10_gpu_vs_cpu_speedup.png` — appendix (why GPU won't help)

---

## STORY ARC (critical transitions Agent 9 identified)

The narrative spine:
1. **Accuracy forces large DBs** (slide 2) → *"we can't just shrink the DB"*
2. **Large DBs are structurally DRAM-bound** (slides 3–6) → *"no config change fixes this"*
3. **NUMA free win already captured** (slide 7) → *"every config lever is exhausted"*
4. **Therefore, only source-level intervention remains** (slides 8–10) → *"the patch is the only path"*
5. **Patch parameters gate on M1–M7** (slide 11) → *"Phase 2 starts now"*

**Missing transition that must be spoken aloud between slides 6 and 7:**
> *"So we have the cross-machine picture. The same 50 MB database that fits Luna's 210 MB LLC completely overflows Orion's 4 MB SLC. There's no configuration that makes a large database behave like a small one. The only lever is making each DRAM lookup faster or eliminating it entirely."*

---

## ONE-SENTENCE FRAME

*"We have proven the bottleneck with four independent tools; the patch is written; Phase 2 runs today."*
