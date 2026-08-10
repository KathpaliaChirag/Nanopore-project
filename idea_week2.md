# Idea Bank — Week 2 (LLM deep-research pass, 2026-08-10)

Short, point-wise list of ideas found for Thesis 1 and Thesis 2, from a 7-agent research + verification pass. Full detail/citations are in chat history — this is the quick-reference version.

---

## Thesis 1 — Adaptive K-mer Cache

1. **Victim cache / filter cache** (Jouppi 1990, Kin 1997) — a small buffer sitting in front of a bigger structure, catching exactly the misses a 1-slot design causes. *Not novel itself* — this is the real textbook reason "go 4-way set-associative" works. Use it as the citation instead of general caching theory.
2. **Runtime cache-topology auto-sizing** — read the machine's actual cache size at startup and size the k-mer cache to it. *Novel* — no paper found doing this; existing tools (e.g. ATLAS) only tune at install time, not on every run.
3. **Heracles-style adaptive sizing** (Google, 2015) — start the cache small (~10% of LLC) and grow/shrink it live based on whether classification stays fast, instead of a fixed "half the socket cache" guess. Better-grounded method, not a novel idea on its own.
4. **Slice-aware cache placement** (Farshin, 2019) — real measured +12% throughput on a key-value store using CPU cache-partitioning tricks. Confirms this class of trick helps hash-lookup workloads.
5. **Skew-aware eviction** (W-TinyLFU / ARC, from the earlier round) — eviction that adapts to one-species-dominates-the-sample access patterns. *Novel in this context* — nobody's applied it to bioinformatics caching before.

## Thesis 2 — Cell-Width + Double Hashing

6. **Bitmask-cell false-positive formula** — nobody has derived the math for "one collision flips one flag bit in a shared cell" (a paper that looked like a match, COBS, turned out to use a different structure on closer check). *Genuinely novel* — real open math, worth deriving yourselves.
7. **Color vectors** (Bifrost) — genomics already stores a presence-bitmask-per-k-mer over a fixed genome set, just compressed differently (colored de Bruijn graphs). Confirms the *idea* is sound, not novel as a concept — what's novel is doing it in a raw, check-bit-gated hash cell.
8. **BioBloom vs. miBF precedent** — existing tools use one filter per species when the species count is small, and a merged structure only once it gets large. At 6 species you sit in a real, under-explored gap between the two — good framing for why a packed cell is worth trying.
9. **Elastic / Funnel Hashing** (2025) — proven better worst-case bounds than double hashing for a build-once table like Kraken2's. *Stretch goal, not a replacement* — it's pure theory, zero real implementations exist anywhere, so building and benchmarking it would itself be new.
10. **Iceberg hashing — considered, rejected.** Its whole benefit is handling live inserts/deletes; Kraken2's table is built once and never changes, so that benefit doesn't apply here. Worth noting so it doesn't get suggested later.
11. **Keep the h1/h2 formula as planned** — literature (Mitzenmacher) backs the simple two-multiplier approach already designed; no need to complicate it with tabulation hashing.

## New comparator tool

12. **Kun-peng** — a real, actively maintained tool (Rust, March 2026 paper) that reuses Kraken2's own database format and claims up to 24x less build memory, 473x less query memory, and 4.73x faster classification than Kraken2. Directly competes with the "smaller database" pitch — read it closely before finalizing that framing, the way `kache-hash` already gets an explicit differentiation paragraph.

## Novelty claims confirmed safe to state

13. No existing work combines adaptive caching + reduced-width/double hashing + a small fixed organism panel — this project's exact combination.
14. No existing study runs a cache-miss/hardware comparison across Kraken2/Centrifuge/Centrifuger/Metabuli — this project's comparison table is filling a real gap, not just working around one.
