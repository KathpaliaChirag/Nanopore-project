# Prompt for generating the Wednesday deck (paste into Gamma/Tome/similar)

Copy everything below the line into the tool. It's written as one long brief on purpose — these tools produce generic output when given a vague topic, and produce something that actually looks like it came from a systems lab when given real content, real numbers, and explicit anti-cliché constraints.

---

**Role:** You are a presentation designer who specializes in technical systems-research talks — the kind of deck used at a conference like OSDI, ASPLOS, or a PhD committee check-in, not a startup pitch deck. The audience is a single computer science professor who supervises this thesis work and already understands hash tables, CPU caches, and hashing theory deeply. Do not explain basic CS concepts to him. Do not use marketing language anywhere.

**What this deck is for:** a short progress/planning meeting update on two thesis pieces extending Kraken2 (a metagenomic DNA classifier). The goal is to show the supervisor exactly what's been decided, what's genuinely our own contribution versus what he assigned, and what needs his decision. This is a working meeting deck, not a pitch — it needs to read as precise and slightly restrained, not exciting or persuasive.

**Hard visual constraints — avoid every one of these, they read as AI-generated immediately:**
- No gradient blob backgrounds, no glassmorphism cards, no "hero" full-bleed photo slides
- No generic icon rows (lightbulb = idea, rocket = launch, puzzle piece = solution, handshake = partnership, etc.)
- No stock photography of people in meetings, laptops, or abstract "technology" imagery
- No emoji anywhere
- No "Our Mission" / "Why It Matters" / "Key Takeaways" marketing-deck section headers
- No forced three-column-equal-height "feature card" layouts unless the content is genuinely three parallel things
- No slide that exists only to say "Thank You" or "Questions?" with decorative art — end on the actual open-questions content instead
- Avoid centering everything — technical diagrams and tables should anchor to a grid, left-aligned body text

**What to do instead:**
- Real system diagrams: boxes and arrows showing actual data flow (a read being chopped into k-mers, hashed, looked up in a table), memory-hierarchy diagrams (L1/L2/L3 cache → RAM → disk, drawn as nested or stacked tiers with real size labels), bit-layout diagrams for hash table cells (a rectangle divided into labeled bit-ranges, e.g. 16 bits split into a 4-bit index + 12-bit fingerprint)
- Tables with real numbers and real citations (author, venue, year) wherever a claim is being made — never a vague bar chart with unlabeled axes
- A restrained palette: one dark neutral (near-black or dark slate) for backgrounds or text, one muted accent color used consistently for "our contribution" markers, and nothing else — no rainbow category coloring
- Monospace or a technical sans (e.g. IBM Plex Mono / Plex Sans, JetBrains Mono, Inter) for anything that's a number, a formula, a filename, or a citation
- Dense is fine. This audience reads fast and wants information, not breathing room. Prefer one information-rich slide over two sparse ones.
- Where something is explicitly *our* contribution versus *the supervisor's* assigned scope, mark it visually and consistently the same way on every slide it appears (e.g. a small accent-colored tag reading "OUR DESIGN" next to it) — this distinction matters throughout and should never require the reader to remember it from an earlier slide.

**Slide-by-slide content** (use this structure, don't invent extra filler slides, don't merge or split unless a slide is genuinely overloaded):

1. **Title.** "Adaptive K-mer Caching + Cell-Width/Hashing Redesign for Kraken2" — subtitle: two thesis pieces, project status update, date, presented to Prof. Kolin Paul.

2. **The bottleneck, stated precisely.** Kraken2 classification is memory-latency-bound, not compute-bound: DRAM bandwidth measured at only 4.9–10.7% of peak during real runs, meaning the CPU is mostly waiting on memory fetches, not calculating. The dominant cost is looking up minimizers (representative short k-mers) in a hash table built from reference genomes, tens to hundreds of GB, with an essentially random access pattern that defeats CPU prefetching. Two independent levers follow directly from this: shrink the table so more fits in fast memory, or catch repeat lookups before they hit the table.

3. **Kraken2's classification pipeline, as a diagram.** Read → split into k-mers → pick minimizers → hash → look up in the big table → cell returns the lowest-common-ancestor taxon → combine per-read. Label where the two theses each intervene (Thesis 2 changes the table/cell itself; Thesis 1 sits in front of the lookup).

4. **What already exists: Patch 4.** A thread-local, direct-mapped, 16,384-entry cache (256KB/thread, fits L2), designed by the supervisor, sitting in front of the big table. Real measured k-mer reuse rate: 90.7%. Applied and benchmarked 2026-08-03: real but modest gain, shrinks as thread count rises, grows with database size. State this plainly with the real numbers — this is the credibility slide, not a sales slide.

5. **Two thesis directions — scope as assigned.** State exactly what was assigned, no more: Thesis 1 = 4-way set-associative cache baseline + hardware-topology-aware sizing + biology-driven adaptive eviction. Thesis 2 = double hashing to replace linear probing + a 6-bit-per-organism bitmask cell + a merged lookup cache, extending an already-published cell-width reduction (32→24→16 bit) with a derived exponential false-positive law. Make clear this slide is *scope*, not *method* — the next slides show the method is ours.

6. **Thesis 1 architecture diagram.** Memory-hierarchy stack (L1 → L2/L3 → RAM → disk) with the adaptive cache explicitly placed at the L2/L3 tier. Side-by-side comparison: direct-mapped (one candidate slot, forced eviction on any collision) vs. 4-way set-associative (four candidate slots per key).

7. **Thesis 1 — our contribution: the eviction and sizing mechanisms.** Tag as "OUR DESIGN." Show a small table: four unrelated fields — LLM inference KV-cache eviction, Mixture-of-Experts expert caching, recommendation-system embedding-table caching, general skew-resistant indexing — independently converging on the same principle (decayed historical importance beats pure recency; protect a small set of universally-hot items unconditionally). Name the specific papers being drawn from (Scissorhands, StreamingLLM, PIM-Tree, CachedEmbedding). Separately: trace-driven cache sizing (à la Bandana) instead of guessing a fixed fraction of available cache.

8. **Thesis 1 — new idea: organism-blocked predictive partitioning.** Tag as "OUR DESIGN, NEW THIS WEEK." Diagram: the small fixed 6-organism reference panel, each organism given its own unevenly-sized slice of the cache, plus a short sliding window over the current read's last several k-mer lookups used to predict and pre-protect the likely-relevant organism's slice before reactive evidence accumulates. Explicitly credit this as a translation of a competing tool's RAM-tier trick (Kun-peng's on-demand block loading) down to the CPU-cache tier — same principle, different scale of the machine.

9. **Thesis 2 architecture diagram.** A single hash table cell drawn as a labeled bit-rectangle, showing the 32→24→16-bit progression, plus the false-positive-vs-load-factor relationship as a simple labeled curve (already derived/published, not new).

10. **Thesis 2 — double hashing and the bitmask cell.** Two small diagrams: (a) collision resolution — linear probing (check the next cell) vs. double hashing (a second calculation sets the jump distance); (b) the bitmask cell — one bit per organism, and what happens on collision (bits OR together, a spurious extra bit rather than a destroyed value) versus Kraken2's normal collision (whole value overwritten).

11. **Thesis 2 — our contribution.** Tag as "OUR DESIGN." Two items: reusing the double-hash pair to also generate multiple candidate bucket positions at build time (power-of-d-choices, cheap add-on, real deployed precedent in libcuckoo); and the derivation strategy for the bitmask cell's false-positive formula (borrowed technique: Count-Min Sketch's one-sided error bound, adapted because both problems share the same shape — something OR'd/combined into a shared slot instead of overwriting it). State plainly that nobody has published this derivation.

12. **Prior-art check — a table, not prose.** Four tools, each closely read this week: Kun-peng, kache-hash, Chimera/TAXICF, Taxor. Columns: what it does, what it threatens, verdict. Chimera is the one honest caveat — it does shrink an on-disk database via a different structure (cuckoo filters), for a different scale (300,000+ species vs. this project's fixed 6). State that plainly, don't downplay it.

13. **Open questions for the supervisor.** Not proposals dressed as questions — actual undecided items: should Kun-peng and Chimera/TAXICF be added to the benchmark comparator table (both are live, maintained, peer-reviewed, and directly compare against Kraken2)? Confirm build order. A possible third angle — measuring whether Thesis 1 and Thesis 2 help or fight each other when combined — flagged as a real open question, not a commitment.

14. **Proposed build order.** A short ranked list, five items, framed as a recommendation awaiting sign-off: double hashing, then combined bucket-placement, then the eviction policy, then trace-driven sizing, then the bitmask-cell derivation.

**Tone check before finishing:** every claim about "novelty" or "nobody has done this" should be stated as "confirmed via literature search, not found in [specific tools checked]" — never as an unqualified assertion. Every number should trace to something real from this project's own measurements or a named external paper — no invented statistics for visual effect.

---

## If you'd rather I build this directly instead

I can build this as a real HTML slide deck (an Artifact) with hand-drawn architecture diagrams matching this exact spec, rather than routing it through an external tool — likely more accurate on the technical diagrams than a generic AI deck generator, since I can draw the actual bit-layouts and memory-hierarchy stacks precisely instead of approximating them. Say the word and I'll do that instead of the copy-paste route.
