# What We're Building — Briefing for Sir

Rewritten 2026-08-18. Written as if speaking directly to sir in the meeting: here's what we've already built ourselves, and here's what we're going to build next. No prior context assumed for anyone else reading this.

## First — a correction to make plain up front

Sir, everything in this project runs on base Kraken2's real source code — nothing was ever handed to us as a patch or a working implementation. Every line of code so far was written by us. When we say a piece of work "was your design," we mean you pointed us at an idea; we did the engineering. That distinction matters for what follows, because the same is about to be true of both thesis pieces: you've given us three targets each, no method attached to any of them, and everything below is us telling you how we're going to hit those targets.

## What we've already built: the cache in front of the table (Patch 4)

Before either thesis existed, you suggested we put something in front of Kraken2's giant lookup table to catch repeat lookups. We built it. Here's what it is, in our own words, since we wrote it:

Kraken2 classifies a read by chopping it into short DNA fragments (**k-mers**), picking a representative one per window (a **minimizer**), and looking each one up in a hash table built once from reference genomes — tens to hundreds of gigabytes, essentially random access. We measured that the same k-mer gets looked up again and again in real data — a **90.7% reuse rate**. So we wrote a small, fast cache — one private copy per CPU thread, 16,384 slots, 256 kilobytes, small enough to live entirely inside a CPU's L2 cache — and put it in front of the big table. Every lookup checks this small cache first; only a miss pays the cost of reaching into the giant table.

We built it **direct-mapped**: every k-mer maps to exactly one possible slot, no choice. That's the simplest version, and it has an obvious weakness — if two different, both-useful k-mers land on the same slot, one gets thrown out immediately even if the cache has room elsewhere. We applied it to the real source and benchmarked it on 2026-08-03: real gain, but it shrinks as thread count rises and grows as the database gets bigger. That weakness is exactly what we're about to fix.

## Thesis 1 — here's what we're going to build

You gave us three targets, sir, no method specified for any of them:
1. Turn that direct-mapped cache into something with multiple candidate slots per key.
2. Make the cache size itself to the actual machine it's running on.
3. Give it a smart eviction rule that understands real sequencing data isn't uniform.

Here's exactly how we're going to build each one.

**One — 4-way set-associative.** Instead of one candidate slot per k-mer, we'll give each one 4 candidates. Two colliding k-mers won't have to fight over a single spot anymore — only if all 4 candidates are full does anything get evicted.

**Two — hardware-aware sizing, with a real method behind it, not a guess.** We'll read the actual cache size of whatever machine the code is running on at startup. But instead of just picking a fixed fraction of that to use, we'll simulate a handful of candidate cache sizes against real recorded read-access data and pick whichever one is cheapest while still hitting our performance target. That's a technique we found built for exactly this kind of sizing decision in a different domain (large-scale key-value caching), and we're applying it here.

**Three — the eviction rule, and this is where we found something worth telling you about.** We went looking for how other systems solve "what do I keep in a small fast cache when the important things aren't just the most recently used ones" — and found the same answer, worked out independently, in four completely unrelated corners of computer science: caching for large language model inference, caching for a different large-scale AI system called Mixture-of-Experts, caching for recommendation-engine lookup tables, and general database indexing research. None of those four fields cite each other. All four land on the same idea: track a *decaying history* of how important something has been, not just whether it was touched a moment ago, and permanently protect the small set of items that are universally important instead of letting them get evicted just because something newer showed up. We're building that: track decayed importance per k-mer, and permanently protect the handful of k-mers that show up constantly across almost every sample — highly conserved genetic regions.

**A fourth piece, sir — not something you asked for, we're adding it.** Our reference panel is a small, fixed set of 6 species. Because it's small and fixed, we can do something a general-purpose cache can't: give each species its own dedicated slice of the cache, sized by how common it actually is, instead of one shared pool every species competes for equally. On top of that, we track a short rolling window of the last several k-mers scanned in the current read — real reads are compositionally consistent, so if the last 20 k-mers came from one species, the rest of the read almost certainly does too — and use that window to protect the right slice *before* enough evidence has piled up to justify it reactively. We're borrowing this idea from a competing tool, Kun-peng, which does something similar but at a completely different scale of the machine (it partitions a huge database into multi-gigabyte blocks on disk, we're partitioning a small on-chip cache by species) — same underlying principle, translated down to a scale nobody's applied it at before.

## Thesis 2 — here's what we're going to build

Three more targets from you, sir, again with the concept named but not the method:
1. A merged caching layer, tied to Thesis 1.
2. Replace the current collision-handling method with something better.
3. A compact cell that stores presence-per-organism instead of a species ID.

Here's how we're going to build each one. Background first: earlier work already shrank each cell in the hash table from 32 bits down to 24, then 16, and worked out the mathematical relationship between cell width and how often two unrelated k-mers accidentally collide (a false positive). Everything below extends that.

**One — double hashing.** Right now, when two k-mers collide into the same cell, Kraken2 just checks the next cell, then the next, until it finds room — collisions clump together. We'll use a second, independent calculation to decide how far to jump on a collision instead, so collisions spread out rather than pile up. We checked, sir — no genomic hash table published anywhere uses this. It's a real gap.

**Two — a piece we're adding on top, not something you asked for.** Once we've built that second calculation for double hashing, we can reuse it for something extra: generating 2 to 4 candidate slots for a k-mer up front, and placing it wherever's emptiest when the database is built. Nearly free — same two calculations, used differently — and there's real deployed precedent for this exact approach in production systems.

**Three — the 6-bit presence cell.** Instead of storing which species a k-mer belongs to as an ID, each cell stores one yes/no bit per species — 6 bits for our 6-species panel. When two k-mers collide here, the two answers combine instead of one destroying the other — the true answer survives, we just pick up one extra, incorrect "maybe" bit. That's a much gentler kind of mistake than what Kraken2 does today, where a collision wipes out the correct answer entirely.

**Four — the math nobody's written down, and we're going to derive it.** You named the bitmask cell as something to build, sir, but nobody — not us, not anyone published — had worked out the formula for how often that gentler mistake happens. We found the right mathematical toolkit to derive it: a technique built for a completely different counting problem (Count-Min Sketch) that shares the same shape as ours — something gets combined into a shared slot instead of overwriting it — and we've worked out how to adapt it.

## Making sure none of this is already someone else's published work

Before bringing any of this to you, sir, we did close reads of the four competing tools most likely to have already done this:

| Tool | What it does | Does it threaten our plan? |
|---|---|---|
| Kun-peng | Streams a database in on-demand blocks from disk, cutting RAM use | No — completely different scale of the machine, database stays the same size |
| kache-hash | A hash table engineered for cache-friendly streaming access | No, but closest overlap — it's a fixed layout decided once at build time; ours adapts live and actively decides what to keep |
| Chimera / TAXICF | Uses a different filter structure to genuinely shrink a database on disk | Partially — it really does shrink a database, for a very different scale (300,000+ species vs. our fixed 6). We're being upfront about this rather than hiding it |
| Taxor | Gives each species its own separate storage, never shares a slot | No — it can't have the gentle-collision problem our bitmask cell is specifically built to have and handle well |

## What we're asking you to decide, sir

1. Kun-peng and Chimera/TAXICF are both live, maintained, peer-reviewed, and already benchmark directly against Kraken2 — should they go in our actual comparator table next to Metabuli and Centrifuger, or stay cite-only the way kache-hash and Taxor do?
2. We're proposing to build double hashing first, since it extends work we've already done — does that order make sense to you, or would you rather we prioritize the eviction policy first, given how well-grounded it turned out to be?
3. One more idea, not yet built into either thesis: do Thesis 1 and Thesis 2 help each other or fight each other when combined? Narrower cells raise the collision rate, which could make the cache less trustworthy about what it's holding. Worth us measuring, or out of scope for now?
