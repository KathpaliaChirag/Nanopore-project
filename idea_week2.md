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

### Kun-peng — differentiation from the "smaller database" pitch (2026-08-17 close read)

You want to know if Kun-peng steals Thesis 2's headline before you finalize the framing. It doesn't — but it does steal a *word*, and you need to stop using that word the way we have been.

**What Kun-peng actually does.** Chen, Zhang, Peng, Huang, Liu, Shen & Jiang, *Kun-peng: an ultra-memory-efficient, fast, and accurate pan-domain taxonomic classifier* (bioRxiv Dec 2024 → *Briefings in Bioinformatics* 27(2), March 2026, DOI 10.1093/bib/bbag119 — [paper](https://academic.oup.com/bib/article/27/2/bbag119/8525000), [code](https://github.com/eric9n/Kun-peng)) is a Rust reimplementation of Kraken2's classification algorithm. It keeps Kraken2's hash function, cell width, and linear-probing collision resolution completely unchanged — the paper states it plainly: Kun-peng is "fully compatible with Kraken2's hash-table format." What it changes is how that *unmodified* hash table gets loaded. Kraken2 pulls the whole table into RAM at once; Kun-peng slices it into sequential ~4GB blocks on disk (its "Intelligent Block-Partitioned Database Structure") and loads only the block a query batch actually needs, on demand.

> [!IMPORTANT]
> The on-disk database is the *same size* as Kraken2's — the paper's own build-comparison table lists it as identical (~81GB for their 75,796-genome reference). Kun-peng does not build a smaller database. It builds the same database and avoids holding all of it in RAM at once.

That's the correction to make before Wednesday: "smaller database" is our word, and Kun-peng hasn't taken it — the stored structure is byte-for-byte the same size either way. What Kun-peng *has* taken is "less memory," and it's taken it at a scale that makes our number look small if Thesis 2 gets framed as a memory-reduction story: 24x less build memory, up to 473x less query memory, 4.73x faster classification (Kun-peng-F mode), all benchmarked up to a 4.3TB, 204,477-genome pan-domain database built with only 4.1GB peak RAM, on an AMD EPYC 7742 (128 cores, 512GB RAM), 10 threads. Centrifuge and Centrifuger are both in their comparison too — both showed higher false-positive rates than Kun-peng across several CAMI-II-style datasets. Metabuli isn't mentioned. No LLC/cache-hierarchy discussion anywhere in the paper — the memory story stops at block-file granularity.

**Why this doesn't compete with Thesis 2 — it composes with it.** Kun-peng operates one level up the stack from where Thesis 2 lives. Thesis 2 shrinks the *cell*: fewer bits per hash-table entry (32→24→16-bit), plus double hashing to hold back the false-positive cliff as cells get smaller. That changes what's stored. Kun-peng shrinks nothing stored — it changes how an unmodified table streams off disk, in coarse 4GB blocks, with no eviction policy below the block-file level. Run Thesis 2's narrower cells through Kun-peng-style block-partitioning and you'd get smaller blocks, fewer blocks per genome set, and a lower peak-RAM number than either technique gets alone. That's a genuine "future work" sentence for the write-up, not a defensive one.

**Why this doesn't compete with Thesis 1 either.** Thesis 1 lives at the CPU-cache tier — KB/MB-scale, LLC-topology-aware, evicting on access pattern. Kun-peng lives at the RAM/disk tier — GB-scale, block-file streaming, confirmed no eviction policy, no cache-awareness at all. Different memory-hierarchy level, no overlap. Cite it as sibling prior art for "table lookup dominates cost," same treatment as MegIS already gets.

**Open question for sir.** Kun-peng is live, maintained, Kraken2-DB-compatible, and has a March 2026 peer-reviewed paper — that's a stronger case for the *comparator table* (next to Metabuli/Centrifuger) than for cite-only treatment like kache-hash and MegIS get. Worth raising directly on Wednesday: if it goes in the table, it needs an ARM64/Orion buildability check (Rust toolchain — likely fine, but unverified) before it can be scheduled alongside the existing Metabuli/Centrifuger install work.

### kache-hash — differentiation from Thesis 1's adaptive cache (2026-08-17 close read)

Kun-peng got let off easy because it lives at a completely different memory tier than either thesis — an easy defense. kache-hash doesn't give you that out. It genuinely targets the same tier Thesis 1 does — CPU cache lines, KB/MB-scale residency — so this differentiation has to be argued on mechanism, not geography.

**What kache-hash actually is:** Khan, Patro & Pandey, *kache-hash: A dynamic, concurrent, and cache-efficient hash table for streaming k-mer operations* (bioRxiv, Feb 2026, [github.com/jamshed/kache-hash](https://github.com/jamshed/kache-hash)). It's an Iceberg-hashing-based table (front yard / backyard / overflow, ≤4 probe locations — coincidentally also "4," but an unrelated reuse of the number, not a shared concept with Thesis 1's 4-way baseline). Its real contribution: swap Iceberg's generic hash function for a **minimizer-based** one, so consecutive k-mers from a streaming sequence land in the *same* 64-byte-aligned bucket instead of scattering randomly, with SIMD (AVX2) slot lookup. Bucket capacity, metadata size, and probe width are all fixed constants decided at build time — confirmed identically from the paper and the GitHub README, with zero mention of reading LLC size or any hardware topology at startup, and zero eviction policy of any kind (it's a persistent insert/query/delete dictionary, not a bounded cache — skewed access gets absorbed by a generic overflow table, not by any hot/cold logic).

> [!IMPORTANT]
> kache-hash is not integrated with, benchmarked against, or meaningfully compared to Kraken2. Kraken2 appears exactly once, as a one-line example of what "metagenomic classification" is — zero numbers reported for it. Benchmarks are entirely against IcebergHT, libcuckoo, and Boost's `concurrent_flat_map`, on k-mer counting and de Bruijn graph workloads (2.15-2.22x insertion throughput, 4.42-5.12x negative-query throughput, 7.39x fewer cache misses vs. IcebergHT — all against those three, not Kraken2).

**Why the two ideas don't actually compete.** kache-hash optimizes for the case where access order is sequential/streaming — assembly, k-mer counting — and locality comes free from minimizer structure baked into the hash function itself. Thesis 1 targets Kraken2's read-*classification* access pattern, where locality comes from species/gene skew across reads, not sequence order — a k-mer's neighbors in the read aren't what makes it hot, its taxon's prevalence in the sample is. That's a different kind of locality, and it needs a different fix: kache-hash answers it with a smarter, static hash function; Thesis 1 answers it with a runtime-adaptive, bounded, evictable cache sitting in front of the big table. Three concrete differences: (a) Thesis 1 is a genuinely separate small structure in front of Kraken2's existing table, not a re-engineered version of the table itself; (b) it reads actual LLC size from the running machine at startup and sizes itself live — a behavior kache-hash's paper explicitly doesn't have; (c) it applies real eviction (W-TinyLFU/ARC-style, biology-skew-driven) to decide what to *keep*, versus kache-hash's "keep everything, just lay it out so streaming happens to be cache-friendly."

**Recommended framing for the write-up:** cite kache-hash as the closest CPU-cache-tier prior art and lean on the contrast explicitly — "hash-function-level static locality for streaming workloads" vs. "runtime-adaptive bounded cache with skew-aware eviction for classification workloads." Pre-empt the obvious reviewer question ("why not just use kache-hash's bucket layout for Kraken2's table?") with exactly that distinction, since the overlap here is real enough that the question will come up.

## Novelty claims confirmed safe to state

13. No existing work combines adaptive caching + reduced-width/double hashing + a small fixed organism panel — this project's exact combination.
14. No existing study runs a cache-miss/hardware comparison across Kraken2/Centrifuge/Centrifuger/Metabuli — this project's comparison table is filling a real gap, not just working around one.
