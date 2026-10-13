# Midterm presentation — database size reduction for kraken2

| | |
|---|---|
| For | Prof. Kolin Paul, midterm review (presentation ~25th) |
| Due to reviewer | Thursday noon |
| Budget | 10 minutes, 10 slides max |
| Scope | **My slice of the project: making the kraken2 database smaller.** The prefetch (`-B`) and scanner work belong to the other slides/teammates and are referenced, not claimed. |
| Machine for every number | i7-11700, 8C/16T, 16 MiB L3 |
| Baseline | `eskape_32bit_fork` — 48.80 MB, kraken2 2.17.1, `-c 12200000 -k 35 -l 31 -C 32` |
| Workloads | speed: `pod5_2` (151,591 reads, 500 Mbp) · accuracy: `pod5_15` (30,378 reads, 90.55 Mbp) |

**Timing plan:** slides 2–3 fast (2 min), slides 4–7 are the substance (5 min), 8–10 close (3 min).

---

## Slide 1 — Title

**Shrinking the kraken2 database without losing the call**

Size/accuracy/speed trade-offs for nanopore ESKAPE classification

*<your name> · <roll no> · Advisor: Prof. Kolin Paul · Dept. of CSE, IIT Delhi · September 2026*

> *Say:* one line only — "My part of the project is the database itself: how small can it get, and what does it cost."

---

## Slide 2 — Motivation and the problem

**The problem:** kraken2 classifies nanopore reads against a hash table that must be resident in memory. The table is the system. It sets the memory footprint, it sets the cache behaviour, and — measured on our baseline — **the hash lookup is 43.4% of all cycles.**

Three reasons size is the lever worth pulling:

- **Deployment.** An ESKAPE panel database at 48.8 MB is already small; the general-purpose Standard database is 71 GB. Anything that runs at the sequencer — not in a datacentre — is bounded by what fits.
- **Speed.** A smaller table means fewer cache misses. With no prefetching, `stalls_l3_miss` on the baseline is **23.6% of cycles.**
- **It is one build flag.** `build_db -M` sets the table size *exactly* — `hash.k2d = 32 + bytes_per_cell × M`, no rounding, no padding.

**The question I am answering:** *how far can the database be cut before the classification is worse, and what exactly is the exchange rate?*

> *Say:* the honest framing — this is not compression. `-M` discards minimizers at build time. The information is gone. So the whole question is what that costs.

---

## Slide 3 — State of the art we want to beat

| | Stock kraken2 2.17.1 | This work |
|---|---|---|
| Size control | `--max-db-size` wrapper | `build_db -M` called directly |
| How it behaves | applied **only as a cap** — ignored when the library already fits | applied always, as a deliberate design point |
| Published operating point | Standard-8: keeps **10.38%** of minimizers | characterised curve, 3 MB → 48.8 MB |
| Cell width | 32-bit cells only | fork supports **16/20/24/32/40-bit** cells |
| Published trade-off curve | **none** | measured, 13 builds |

**The specific SOTA claim we contest:** Standard-8's 90% cut is safe *because Standard has enormous redundancy* — its library needs 19.3 billion cells, ESKAPE needs 12.2 million. That is a **1,517× difference in reference redundancy.** Standard has thousands of genomes covering each read; ESKAPE has 17 sequences. **The published ratio does not transfer**, and treating it as a default is wrong for a clinical panel.

> *Say:* so the contribution is not "we made it smaller" — the flag already exists. It is "we measured what the flag actually costs on a non-redundant panel, and it is not what the defaults assume."

---

## Slide 4 — The plan (5 stages), and where I am

| # | Stage | Status |
|---|---|---|
| 1 | Fork kraken2 for variable cell width (16/20/24/32/40-bit) | ✅ **done** — in use |
| 2 | Decide the right cell width by measurement | ✅ **done** — answer: 32-bit (slide 5) |
| 3 | Build + verify an `-M` size ladder | ✅ **done** — 13 databases (slide 6) |
| 4 | Measure the size ↔ speed ↔ accuracy surface | ✅ **done** — (slides 6–7) |
| 5 | Pick and defend an operating point; push below 8 MB | 🔄 **in progress** |

**Where that puts me:** stages 1–4 complete and verified; stage 5 is the remaining work and is what slide 10 promises.

> *Say:* the honest sentence — the measurement phase is finished, the recommendation phase is not.

---

## Slide 5 — Result 1: cell width is the wrong lever (32-bit wins)

Narrower cells store fewer bytes per entry but shorten the **fingerprint** that tells minimizers apart. Measured across all 16 pod5 files, `-T 0`:

| DB | classified % | S. aureus calls | E. faecium calls |
|---|---:|---:|---:|
| 32-bit (stock width) | 83.76 | **12** | **48** |
| 24-bit | 83.78 | 31 | 102 |
| **16-bit** | **90.96** | **7,071** | **10,014** |

**16-bit's +7.20 pp "accuracy gain" is false positives.** This is a Gram-negative-dominated sample; those Gram-positive calls are collisions, inflated ~590× and ~209×.

Three findings that close this axis:

- **`-C 20` is strictly dominated — never build it.** It uses the *same 3-byte struct* as `-C 24`, so the file is byte-identical in size, with 4 fewer fingerprint bits = **16× the false-positive rate for zero saving.**
- **`-C 24` is dominated at every size** — slower than `-C 32` at all matched sizes *and* FP-contaminated. Its apparent accuracy edge is fake: `eskape_C24_32MB` scores 84.06%, *above* the full-database 83.94% — impossible for a subsampled database.
- **`-C 40` is implemented in the fork but is not a size-reduction candidate** (it is larger, and would overflow the 32-bit entry path). Not built, not benchmarked.

**Conclusion: hold the cell width at 32-bit. Size reduction has to come from `-M`.**

---

## Slide 6 — Result 2: the `-M` size ladder — 13 builds, verified before measured

Thirteen databases, 8–32 MB, at two cell widths. **Every build structurally verified against closed-form predictions before a single timing run:**

| check | result |
|---|---|
| `hash.k2d` = (C/8) × M + 32 | **13/13 exact** |
| threshold word = (1 − M/12,200,000) × UINT64_MAX | **13/13 exact** |
| `capacity_` header = M | **13/13 exact** |
| taxonomy identical across all builds | **one md5 for all 14** |

**Why this is a clean experiment:** the hash (`fmix64`) is a bijection with uniform output, so the same fraction of stored minimizers survives as of all minimizers. Occupied cells scale with `M` too, so **load factor is constant at 0.7298 across a 5.3× range of `M`** (measured 0.7297–0.7303). Probe chains do not lengthen. **Size is a clean single variable.**

**The `-C 32` curve — 6.1× smaller for 1.91 pp:**

| size | keeps | classified | Δpp |
|---:|---:|---:|---:|
| 48.8 MB (baseline) | 100% | 83.94% | — |
| 32 MB | 65.6% | 83.68% | −0.25 |
| 16 MB | 32.8% | 83.17% | −0.77 |
| 12 MB | 24.6% | 82.77% | −1.17 |
| **8 MB** | **16.4%** | **82.03%** | **−1.91** |

Speed at 8 MB: **−36.8% cycles** against the no-prefetch control (1.398e11 → 8.828e10, monotonic, no break-even point).

---

## Slide 7 — Result 3: the method is validated, and one free 2× win

**The simulation method is exact.** Predicted accuracy by patching the threshold in `opts.k2d` (no rebuild) vs. actually building:

> 7 builds · predicted 82.03 / 82.48 / 82.77 / 83.17 / 83.36 / 83.52 / **83.69** · measured 82.03 / 82.48 / 82.77 / 83.17 / 83.36 / 83.52 / **83.68** — **all within 0.01 pp.**

Checked at read level too: the real 10 MB build vs. the full table carrying the same patched threshold, on all 30,378 reads — **call, read ID, taxid and length identical on 30,378/30,378.** One read differs in the k-mer-mapping field only, explained by a different collision layout at different `capacity_`. *The set of stored minimizers is identical; the collision layout is not.*

**Consequence: I can now predict any size without building it.** Each build takes 12 seconds, but the curve is free.

**One free win found along the way:** the `-g` hit-group filter is **off** for the raw binary but the `kraken2` wrapper silently forces `-g 2`. With the filter off, a read is lost only if *every* one of its hit groups is dropped, not all-but-one. Measured, **dropping the filter is worth exactly 2× the database size at equal accuracy** — no rebuild, no cost. It is only safe because `-C 32`'s 26-bit fingerprint produces ~3 false-positive hits in the whole file; it would be reckless at `-C 16`.

---

## Slide 8 — What the size work uncovered for the rest of the project

Shrinking the table to 8 MB **moved the bottleneck off the table.**

| | 48.8 MB baseline | 8 MB |
|---|---:|---:|
| hash lookups | dominant (43.4% of cycles) | **20.9%** |
| read + parse + scan | — | **79.1%** |
| IPC | 1.48 | **1.81** (compute-bound) |
| `stalls_l3_miss` | 23.6% (no prefetch) | **1.45%** |

At 8 MB, `MinimizerScanner` alone is **59.2% of total runtime**, and 79% of remaining LLC misses are compulsory input-file traffic no cache can avoid.

**This is a result, not a failure:** the size work has taken the memory system off the critical path. Further database shrinking now chases a fifth of the runtime. *This is the handoff to the scanner/read-path workstream.*

> *Say:* if the prof asks "why stop at 8 MB" — this slide is the answer.

---

## Slide 9 — Honest status: what is settled and what is not

**Settled:**
- 32-bit cells; 20-bit and 24-bit are dominated, with evidence.
- Size is exactly controllable and its accuracy cost is predictable to 0.01 pp.
- 48.8 MB → 8 MB costs 1.91 pp and buys 36.8% of cycles.

**Not settled — and I will say so:**
- **No operating point is recommended yet.** The two curves bend in opposite directions (speed saturates near −21% from lookups; accuracy collapses as `(1−f)^H`), so there is a knee — I have not yet defended where it is.
- **Below 8 MB is unmeasured.** Predicted 3 MB = 77.85% (−6.09 pp), but predicted, not built.
- **Accuracy = "% classified" on one file.** It is not precision/recall against truth labels. The false-positive columns are a proxy, not a ground-truth evaluation.
- **This project has retracted results before** — an earlier "−20 pp" model was wrong by 9.357× and was corrected by direct measurement. Everything on slides 5–8 is measured, not modelled.

> *Say this slide out loud.* It is the one that earns trust in the rest.

---

## Slide 10 — What I promise for the final presentation

1. **A defended operating point.** A stated size for the ESKAPE panel database with the knee of the size/accuracy curve identified and argued, not asserted.
2. **The curve extended below 8 MB.** Build and measure 3/4/5/6 MB, and report where accuracy actually collapses — including the case where the answer is "don't go there."
3. **A ground-truth accuracy evaluation.** Move off "% classified" to precision/recall on a labelled set, so the false-positive claims about 16/24-bit are quantified rather than indicated.
4. **The `-g` finding turned into a recommendation** — a one-line statement of when the filter should be off and what fingerprint width makes that safe.
5. **Combined with the prefetch and scanner work:** a single end-to-end number — *this much smaller, this much faster, this much accuracy given up* — against stock kraken2 2.17.1.

**Stretch (will not promise):** validation on a second, non-ESKAPE panel to test whether the redundancy argument generalises.
