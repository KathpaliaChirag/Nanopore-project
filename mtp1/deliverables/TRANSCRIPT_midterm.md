# Speaking transcript — my slides (PDF pages 3, 5, 7, 9)

Total target: **8–10 minutes** · roughly 2–2.5 min per slide.
Say the **bold numbers** out loud — those are what the professor will latch onto.

---

## SLIDE 1 of mine — PDF page 3 · "Motivation and The problem" (~2.5 min)

### Open — the pipeline (30 sec)

- "This is the full pipeline, from patient to answer."
- Patient sample → flow cell gives a **Pod5** file of raw signals.
- Dorado runs on the **GPU** and turns signals into DNA letters — basecalling.
- Kraken2 runs on the **CPU** and says which species each read came from.
- Then a species report.
- **"Our work is only on the Kraken2 box."** The GPU part is already fast. This one is not.

### The three problems (1 min)

Say them as three separate problems:

1. **Database size is a trade-off.**
   - A small database misses things — that means a wrong diagnosis.
   - A big database is accurate, but slow, and the cache misses go up.

2. **The same k-mer repeats again and again** — but every repeat still pays a full memory lookup. We are re-fetching something we already looked at.

3. **The CPU can ask for many things from memory at once** — but Kraken2 asks for only one at a time, and waits.

### The chart (1 min)

- "X-axis is database size, from 50 MB up to 103 GB."
- "Blue bars are accuracy. The red dashed line is the cache-miss rate."
- Read out the two ends:
  - 50 MB → **84.8%** accurate, **1.28 s**, only **11.9%** cache misses.
  - 103 GB → **98.9%** accurate, but **53.6 s**, and **90.2%** cache misses.
- **The line to land:** "So accuracy goes up, but we pay for it in cache misses and in time. Our goal is to get the accuracy of the big database without paying that full price."

> If asked "why is 142 MB only 65%?" → that database covers fewer organisms, so many reads find no match. Size alone is not accuracy — what is *in* the database matters too.

---

## SLIDE 2 of mine — PDF page 5 · "State-of-the-Art Kraken2 Benchmarking" (~2.5 min)

### What this slide is (20 sec)

- "Before changing anything, we measured stock Kraken2 — so we know what we are comparing against."
- Tools: **perf, gprof, cachegrind**.

### The five stages, right side (40 sec)

Walk down the column:

1. **Read in** — FASTQ record streamed off disk.
2. **Minimizer scan** — extract and canonicalise each k-mer window.
3. **Hash probe** — `CompactHashTable::Get()`, **once per minimizer**. ← point here
4. **LCA classify** — weighted vote up the taxonomy tree.
5. **Report** — the taxon call.

- **"Step 3 is where the time goes."** Profiling showed `Get()` is about **96% of all last-level cache misses**.

### The chart (1 min 20)

- "Four database sizes, four workload sizes. X-axis is number of reads, from 10 up to 1.87 million. Log scale on both."
- Give two comparisons only — don't read every bar:
  - **At 10 reads:** 50 MB takes **0.08 s**, 103 GB takes **51.3 s**. Almost no real work in either case — that time is just *loading the database*.
  - **At 1.87 million reads:** 50 MB takes **13.9 s**, 103 GB takes **79.5 s**.
- Then the cache-miss line: **71% → 98%** as the database grows.
- **The line to land:** "Two separate costs. A fixed start-up cost to load the database, and a per-read cost that gets worse as the table stops fitting in cache."

---

## SLIDE 3 of mine — PDF page 7 · "Exp 1: Cell-width reduction" (~2.5 min)

### The idea (30 sec)

- "Each entry in Kraken2's table is **32 bits** wide."
- "Part of it is the taxon ID; the rest is a fingerprint used to check we found the right key."
- "We asked: what if we make the entry narrower? The table gets smaller, so more of it fits in cache."
- "We built it at **24, 20 and 16 bits**."

### The results — left chart (1 min)

Read the two ends of the row:

| width | size | runtime | cache-miss | classified |
|---|---|---|---|---|
| 32-bit | 48.8 MB | **23.61 s** | **59.4%** | 84.26% |
| 24-bit | 36.6 MB | 22.78 s | 53.4% | 84.27% |
| 20-bit | 36.6 MB | 22.82 s | 53.2% | 85.00% |
| 16-bit | 24.4 MB | **20.20 s** | **41.2%** | 91.29% |

- "Database halves — **48.8 MB down to 24.4 MB**."
- "Cache misses fall from **59% to 41%**."
- "And it runs about **14% faster**."

### The catch — right chart (1 min) ← most important part

- "But look at the right-hand chart. This is reads assigned per species."
- "For the top four species the four bars are basically the same — good."
- "Now look at the bottom two:"
  - **E. faecium: 5 → 10 → 93 → 802**
  - **S. aureus: 3 → 3 → 66 → 552**
- "Those two are barely present in this sample. So those extra reads are **not real** — they are false positives."
- **Why:** "A narrower entry means a shorter fingerprint. A shorter fingerprint collides more often, so the table says 'found it' when it did not."
- **The line to land:** "So 16-bit looks faster and looks more accurate, but it is not. **24-bit is the safe point** — it matches 32-bit to **0.01 percentage points** and still saves space."

---

## SLIDE 4 of mine — PDF page 9 · "PLAN" (~2 min)

### The one-line summary at the top (20 sec)

- "Everything we measured points to one conclusion:"
- **"Kraken2 is memory-latency bound, not compute bound."**
- "One lookup equals one round trip to DRAM, and they are issued one at a time."
- "So all three of our next steps attack waiting, not computing."

### P1 — Double hashing (35 sec)

- "Right now the table uses **linear probing**: slot = hash mod capacity, and on a collision it just tries the **next** slot."
- "So collisions pile up next to each other — clusters — and lookups have to walk further."
- "**Double hashing** uses a second hash to decide the step size, so collisions scatter instead of clustering."
- "Expected: about **6 probes per lookup down to about 2.5**."
- Tagline: **fewer probes.**

### P2 — Sniper modelling (35 sec)

- "Sniper is a CPU simulator. It models the processor and its cache hierarchy."
- "We run the classifier inside the model, then change cache size or replacement policy — **without changing our code**."
- "It tells us what a bigger last-level cache would actually buy, before anyone builds it."
- Tagline: **fewer surprises.**

### P3 — Minimizer prefetching (35 sec)

- "Every lookup waits on main memory, and that wait is most of the runtime."
- "But here is the key point: **we know the addresses in advance.** The minimizers are already scanned."
- "So we can start those fetches early, and let the waits **overlap instead of adding up**."
- Tagline: **less waiting.**

### Close (10 sec)

- "That is the plan for the second half. Thank you — happy to take questions."

---

## Quick timing plan

| slide | topic | time |
|---|---|---|
| p3 | Problem + pipeline | 2.5 min |
| p5 | Benchmarking | 2.5 min |
| p7 | Cell-width | 2.5 min |
| p9 | Plan P1–P3 | 2.0 min |
| | **total** | **9.5 min** |

If running long, cut: on p5 skip the five-stage list detail; on p9 shorten P2.

---

## Likely questions

**"Why not just use the 16-bit table if it's faster?"**
→ Because the extra reads it classifies are false positives — E. faecium goes 5 to 802 in a sample that has almost none. 24-bit gives the space saving without the collisions.

**"Why is a big database slower per read?"**
→ The table stops fitting in last-level cache, so most lookups go all the way to DRAM. That is the 90% cache-miss figure on slide 3.

**"Isn't the hardware prefetcher already doing P3?"**
→ No. The hardware prefetcher only spots regular patterns. Our lookups are at `hash % capacity` — effectively random addresses, so hardware cannot predict them. We have to issue the prefetch ourselves.

**"How much of the runtime is the database load vs the classification?"**
→ Visible on slide p5: at 10 reads, almost all of the 51 s for 103 GB is load time. That is what Exp 0 (memory mapping) addresses.

---

## One slide bug to fix before presenting

**PDF page 7, bullet list.** Three bullets are duplicated — "A smaller table fits cache better: misses fall from 59% to 41%..." appears three times, and the bullet that starts "The catch:" repeats that same sentence instead of stating the catch.

The bullet should read something like:

> **The catch:** at 16 bits the fingerprint is too short — collisions rise, and E. faecium jumps from 5 reads to 802. Those are false positives.

Worth fixing — if the professor reads the slide while you speak, the repetition is noticeable.
