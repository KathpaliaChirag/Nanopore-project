# Track A — One-Page Recap

**Since Meeting 11 (2026-08-19):** finished building the adaptive k-mer cache you asked for — 4-way, hardware-sized, tested for a smart eviction rule — and found three real bugs along the way, one of which reversed our own headline eviction result. No Meeting 12 record exists; treat this as the first full report-back.

## The stages, one line each

| Stage | Built | Result |
|---|---|---|
| S0 | Rebaselined on v2.17.1 (your call, not v2.1.3) | New anchor: 0.576s, `sample_targeted`/32T |
| S1 | Extended Kraken2's existing 1-slot cache to remember across reads | No benefit on the DBs that matter — the evidence that motivated S2 |
| S2 | Built the 4-way cache | Looked like nothing; **5-agent audit** found a wiring bug + missing checks; fixed checks, real cause was capacity (0.14–0.40% hit rate) |
| — | Eviction policy test | **+25.2%** relative hit-rate gain from "protect proven-useful entries" — the reason S4 exists |
| S3 | Fixed a crash + a slowdown, built a real LLC-sizing formula | All three real bugs; full benchmark = clean null, fully explained |
| S4 | Found the cache's hashing was broken (one slot took 225× the load) | Fixed it: **8.9× hit-rate win** — but re-testing eviction on the fixed hash **reverses** it to **−3.9%**. Caught before more work was built on the disproven basis. |
| S5 | Ported a collaborator's prefetch-batching patch onto our tree | Built, merged, **not yet run on Luna — zero numbers exist** |

## What this means

- Every "no benefit" result has a diagnosed, evidenced cause — not a shrug.
- The eviction win that justified S4's design turned out to be a hash bug wearing a disguise. We found this ourselves, before it went further.
- The single biggest untested lever right now is S5 (prefetch-batching) — 2–3 Luna days from a real number.
- **Track B: zero commits**, by your explicit sequencing call, not neglect. Two live corrections: B2 (bitmask) doesn't need B1 (double hashing) first — confirmed at source level; B1 is a real function to write plus a DB rebuild, not a flag flip. ESKAPE panel is structurally capped at 4 of 6 species.

## Decisions needed from you

1. **Pace** — how much more Track A time before we shift fully to Track B? (~12 days left to Sept 13.)
2. **Scope** — is double hashing required, or stretch? You named 3 items at Meeting 11; it wasn't one.
3. **ESKAPE** — report as a 4-organism result, or chase the other 2 first?
4. **Prefetch spike** — spend 2–3 Luna days getting S5.0 a real number?

*Full detail: `presentations/track_a_progress_2026-09-02.md`. Every stat: `presentations/track_a_appendix_2026-09-02.md`.*
