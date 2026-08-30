# Metabuli vs Kraken2 — A Plain-Language Walkthrough

This document explains, from zero background, how Kraken2 and Metabuli each figure out which species a DNA read came from — and walks **one single example** all the way through both tools, so you only ever have to hold one scenario in your head. Every term is defined the moment it's first needed. Nothing below assumes prior biology knowledge.

> [!NOTE]
> The example in this report is a small, hand-built teaching construction — short toy DNA sequences chosen so every step can be checked by hand. It is not real sequencing data or a benchmark run. It exists purely to make the mechanism visible.

## 0. What problem are we even solving?

A sequencer hands you a DNA read — just a string of letters. The question both tools answer is: **which known species did this read most likely come from?** They answer it by comparing the read against a database built from genomes whose species is already known.

## 1. The alphabet everything is built on

DNA is a string written in a 4-letter alphabet: **A, T, C, G** (each letter is called a **base**). A **gene** is a meaningful stretch of that string.

Genes get **translated** into **proteins**, the molecules that actually do things in a cell. Translation reads the DNA in **non-overlapping groups of 3 letters** — each group is a **codon** — and every codon maps to one **amino acid** via a fixed lookup table (the same table across almost all life; e.g. `ATG` → the amino acid Methionine). A protein is just a chain of amino acids.

One quirk that matters a lot below: several *different* codons can produce the *same* amino acid (`TTT` and `TTC` both mean the amino acid Phenylalanine). So two organisms can have different DNA in a gene while ending up with the *identical* protein. This is completely normal between closely related species — it's called a **synonymous** difference.

Because codons are read in fixed groups of 3, *where you start counting* matters — there are 3 possible starting points, called **reading frames**. Codons never overlap and never slide: codon 2 always starts exactly 3 letters after codon 1, locked to wherever you started. Keep this in mind — it's the single most important fact in this whole document.

> [!IMPORTANT]
> **A common mix-up worth correcting here.** Take `ATGCAT` (6 letters). It's tempting to generate codons the way you'd generate DNA k-mers — sliding one letter at a time: `ATG → TGC → GCA → CAT`. That's wrong. Sliding by 1 letter is how k-mers work (§3 below), not codons.
>
> Codons come from **3 separate, independent attempts**, each locked to one starting point and jumping 3 letters at a time — never overlapping within an attempt:
> ```
> Frame 0 (start at letter 1):  [ATG][CAT]                    → codons: ATG, CAT
> Frame 1 (start at letter 2): A[TGC](AT left over, discarded) → codon:  TGC
> Frame 2 (start at letter 3): AT[GCA](T left over, discarded) → codon:  GCA
> ```
> Same 4 codon texts either way, but a completely different shape: 3 separate chains, not 1 sliding list. This is exactly why a single indel behaves so differently for codons than for k-mers — see §6. If codons slid by 1 like k-mers do, they'd self-heal near an error the same easy way Kraken2's windows do; because they instead jump by 3 from one fixed start, a single dropped letter throws off *every* codon after it in that frame, and recovering means discarding the whole attempt and restarting from a different offset.

## 2. Reads, and why they sometimes have errors

A **read** is the sequencer's output for one strand of DNA. This project uses **Nanopore sequencing**, where DNA threads through a tiny pore and the machine guesses each letter from an electrical signal. That guess is sometimes wrong: a letter can be misread (**substitution**), skipped (**deletion**), or an extra one can appear (**insertion**). Deletions and insertions together are called **indels**. An indel doesn't damage the letters around it — it just shifts everything downstream by one position relative to where it should be.

## 3. Meet the two classifiers, in one sentence each

- **Kraken2** only ever looks at raw DNA letters. It chops genomes and reads into short overlapping chunks (**k-mers**) and checks for exact matches.
- **Metabuli** looks at *both* raw DNA and the translated protein. It's built specifically to survive the kind of error described in §2.

Now let's build one scenario and watch both of them work on it.

## 4. The one example we'll use for everything

Two reference species sit in the database. Their genes differ letter-by-letter, but — because of the codon quirk from §1 — they translate to the **identical protein**:

```
Taxon 100 gene:  ATG GCT AAA CGT GAT CCA TTT GGA AAT CAA GAA TGG CAT ...
Taxon 200 gene:  ATG GCC AAG CGC GAC CCG TTC GGC AAC CAG GAG TGG CAC ...
Shared protein:   M   A   K   R   D   P   F   G   N   Q   E   W   H
```

This is realistic — closely related bacterial strains routinely differ only at these "doesn't change the protein" positions.

Now, a real sample comes in — genuinely from **Taxon 100** — and the Nanopore machine drops one letter while reading it (the `G` starting the 5th codon):

```
True DNA:  ATGGCTAAACGT [G] ATCCATTTGGAAATCAAGAATGGCAT...
Read:      ATGGCTAAACGT      ATCCATTTGGAAATCAAGAATGGCAT...
```

The job for both tools: figure out this read is Taxon 100, despite the missing letter.

## 5. Round 1 — what Kraken2 does with it

Kraken2 slides a short window across the read, one letter at a time, and checks whether each window's exact text shows up anywhere in the reference database (using a 6-letter window here instead of Kraken2's real ~31–35, just to keep the example small).

| Region | What happens |
|---|---|
| Windows starting before the missing letter | All match Taxon 100's DNA exactly — clean |
| **5 windows overlapping the gap** (e.g. one of them reads `AACGTA`) | **No match anywhere** — this exact 6-letter text never occurs in the true reference; it's an artificial "seam" formed by gluing pre-error and post-error letters together |
| Windows starting well after the missing letter | Match Taxon 100 again — clean, because sliding windows don't care about position, only content |

Out of every window in this read, only the small handful sitting right on top of the gap goes dark; everything before and after resumes matching normally, with no extra step required.

One thing worth noticing: because Kraken2 never leaves the DNA level, it can never confuse Taxon 100 with Taxon 200 — their DNA differs almost everywhere, so Kraken2's matches are automatically specific to the true species. **Verdict: Kraken2 correctly calls Taxon 100, confidently, on the strength of its many surviving clean windows — with a small dead zone right at the error and no ambiguity anywhere else.**

## 6. Round 2 — what Metabuli does with it

**First attempt — the "natural" reading frame** (the one that was correct before the error):

| Codon | Letters | Amino acid |
|---|---|---|
| 1 | ATG | M ✓ |
| 2 | GCT | A ✓ |
| 3 | AAA | K ✓ |
| 4 | CGT | R ✓ |
| 5 | **ATC** | **I** ✗ |
| 6 | **CAT** | **H** ✗ |
| 7 | **TTG** | **L** ✗ |

Remember §1: codons jump by 3 from a fixed starting point and never slide back into alignment on their own. So once codon 5 is knocked out of position by the missing letter, **every codon after it in this attempt is wrong, all the way to the end of the read** — not just a small dead zone like Kraken2 had, but a full, permanent breakdown within this one attempt.

**Second attempt — a different starting offset.** Metabuli doesn't stop at one frame; it restarts the whole translation from a different starting point:

| Letters | Amino acid | True protein here |
|---|---|---|
| CCA | P | P ✓ |
| TTT | F | F ✓ |
| GGA | G | G ✓ |
| AAT | N | N ✓ |
| CAA | Q | Q ✓ |
| GAA | E | E ✓ |
| TGG | W | W ✓ |
| CAT | H | H ✓ |

`P F G N Q E W H` — a full, clean recovery, just from picking a different place to start counting. Nothing about the DNA changed; only where the grouping began.

**But here's the catch.** `P F G N Q E W H` is the identical protein chunk for *both* Taxon 100 and Taxon 200 — remember, that's how they were set up in §4. So this recovered evidence, on its own, is a **tie**. This is the price of working at the protein level: you gain the ability to recover from the error, but you lose the automatic specificity Kraken2 had for free.

**Breaking the tie.** Alongside the protein match, Metabuli also keeps the raw 24 DNA letters underneath that same window (its "metamer" carries both). Compare those letters against what each candidate species actually has there:

```
Read:      C C A T T T G G A A A T C A A G A A T G G C A T
Taxon 100: C C A T T T G G A A A T C A A G A A T G G C A T   → 24/24 match (100%)
Taxon 200: C C G T T C G G C A A C C A G G A G T G G C A C   → 17/24 match (~71%)
```

The read's DNA lines up perfectly with Taxon 100 and only partially with Taxon 200. **Verdict: Metabuli also correctly calls Taxon 100** — but it took an extra step (trying a second frame, then checking raw DNA underneath) to get there, where Kraken2 got there in one pass.

## 7. Side-by-side scorecard

| | Kraken2 | Metabuli |
|---|---|---|
| What broke at the error | A small handful of windows, right on top of the gap | *Every* codon downstream of the gap, in the frame first tried |
| How it recovered | Automatically — other windows never needed the broken ones | Had to explicitly retry translation from a different starting point |
| Was the recovered evidence specific to Taxon 100? | Yes, immediately — DNA matching is inherently specific | No — tied with Taxon 200 until the embedded DNA letters were checked |
| Extra step needed? | None | Yes — the DNA-identity check |
| Final answer | Taxon 100 ✓ | Taxon 100 ✓ |

The honest takeaway: for *this single, isolated error*, both tools land on the right answer. The real-world case for Metabuli isn't that Kraken2 fails here — it's that Kraken2's "small dead zone, no recovery needed" story gets worse as errors pile up (a long noisy Nanopore read has many, not one), while Metabuli's frame-retry mechanism gives it a way to actively fight back against that — at the cost of speed, since trying multiple frames and checking DNA-identity is more work than one exact lookup.

## 8. Bonus — what if the "recovered" match had been wrong?

The 5 dead Kraken2 windows, and Metabuli's garbled first-attempt codons, are artificial "seam" content that doesn't really exist in nature. In a big database, that seam text could, by pure coincidence, match some unrelated species — the same way a typo can accidentally spell a different real word.

- **For Kraken2:** one stray wrong match among dozens of correct ones for a read is easily outvoted — that read still classifies correctly. The real damage shows up at the *whole-sample* level: across millions of reads, many different species each pick up a few of these coincidental hits, producing a long list of low-abundance species that were never actually in the sample (this is a documented, real effect — see `WEEK2_PLAN.md`'s citation of Portik et al. 2022).
- **For Metabuli, if it only used one frame:** a coincidental match wouldn't be one stray vote — because a single indel wrecks *every* codon downstream in that frame, a coincidental match there could mean many consecutive wrong votes, genuinely risking that read's own classification. This is exactly why trying multiple frames (and requiring the DNA-identity check to agree) matters — it's damage control against this bigger risk, not just a nice-to-have.

## 9. Bonus — how would you actually know a letter was missing?

Neither tool tells you. Kraken2 and Metabuli never say "there's a deletion at position 13" — they just try matches and keep whatever works, discovering the error only indirectly through which attempts succeeded or failed. To actually pinpoint an indel, you need different tools entirely:

- **Quality scores** — the sequencer's per-letter confidence score; low confidence hints an error is nearby, without saying what it was.
- **Alignment** — a separate class of software (e.g. `minimap2`) that lines the read up against a trusted reference and explicitly marks every match, mismatch, insertion, and deletion, position by position.
- **Comparing many reads that cover the same spot** — if most reads agree on a base at some position and a few don't, those few likely have an error there.

## 10. TL;DR

| | Kraken2 | Metabuli |
|---|---|---|
| Compares | Raw DNA only | Raw DNA + translated protein |
| Database built from | Reference genomes + taxonomy | Same reference genomes + taxonomy (reused, different index) |
| Error tolerance | Local — only windows touching the error are lost | Structural — can lose everything downstream of an error in one frame, but can also actively recover it by retrying frames |
| Specificity | Automatic (DNA is always specific) | Needs an extra DNA-identity check to regain what protein-level matching gives up |
| Speed / memory | Fast, light — the baseline | Slower, heavier (documented ~22–25x slower in `WEEK2_PLAN.md`'s sourced comparison) |
| Best suited for | Speed- and memory-constrained runs | Long, error-heavy (Nanopore) reads where sensitivity matters more than speed |
