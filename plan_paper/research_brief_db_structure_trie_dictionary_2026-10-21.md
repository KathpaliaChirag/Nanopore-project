# can the kraken2 table be a trie or a dictionary? cost, code change and time (asked by sir 2026-10-21, written 2026-10-26)

sir asked whether we can change the database structure itself: a trie instead of the flat hash table, or a dictionary, so that search gets easier and faster. he also wanted to know whether the lookup is a real function call or inlined, and how much code and time a change like that needs. this brief answers all three. it is a plan for ck to review, nothing here was run on luna.

evidence tags, same as `next_steps_plan_2026-10-21.md`: **[repo]** a file in this repo, **[measured]** read from a saved profile or log, **[arith]** arithmetic from stated inputs, **[guess]** my estimate, **[external]** a paper or web page, **[UNCLEAR]** not known, needs a check.

---

## 0. the answer in 30 seconds

> **say:** "a flat hash table is already the floor for lookups: one random memory access per k-mer. a trie needs one access per level. the top levels can sit in cache but the bottom ones cannot, so at best it ties one ram access and pays extra compute. the structures that do shrink the database, or make it exact, need two or three accesses per lookup, so we predict they lose on speed. their real payoff is space (23-31% smaller) and zero false positives, which is a thesis 2 result, not a speed result. before writing any of it we can put real numbers on this in about two days: one perf run for the ceiling, one small benchmark of the structures side by side. then you decide."

three short answers to sir's three questions:

| question | answer |
|---|---|
| trie instead of a flat table, easier and faster? | predicted no for speed. a trie over the minimizer needs 3 to 24 dependent memory reads, the hash table needs about 1. sections 3 and 4 |
| function or inline? | a real function. `GetAt` and `PrefetchIndex` are virtual functions of `KeyValueStore`, called from another source file. perf lists them as their own symbols. sir's question has a useful side: the table is already behind an interface, so swapping it is a smaller job than it sounds. section 2 |
| how much code and time? | 200 to 600 new lines per structure (builder included) plus 250 to 550 lines of shared glue, 3 to 6 working days to a first result on the 50MB db, 3 to 4 weeks to a defensible 16-cell result. the first measured answer for sir takes about 2 days. section 6 |

---

## 1. what kraken2 stores, so the options make sense

**why this section exists.** every option below is judged against the same three facts about the current table, so they come first.

1. **the table stores a fingerprint, not the key.** each cell is one 32-bit word: the value (a taxon) in the low bits, and the top bits of the key's hash in the high bits [external: `CompactHashCell`, upstream v2.1.3 `compact_hash.h`: one `uint32_t data`]. on the 103GB db that is 16 bits of key and 16 bits of value [repo: `talk_track_sir_2026-10-21.md` section 10]. on the 50MB db it is 26 bits of key and 6 of value [repo: `dorado-kraken-research/CLAUDE.md`, M1].
2. **so you cannot read the keys back out.** two different minimizers can share a fingerprint (that is the false positive), and the full key is gone. this has a hard consequence for this whole brief: **no new structure can be built by converting `hash.k2d`.** it can only be built by re-running the kraken2 build from the library genomes.
3. **the cost of a lookup today.** the table runs at load factor about 0.70 [repo: M1]. with linear probing that gives, by the textbook formulas:
   - a key that is in the table: about 2.17 cells probed, ½(1 + 1/(1-α)) [arith]
   - a key that is not: about 6.06 cells probed, ½(1 + 1/(1-α)²) [arith]
   - 16 cells share one 64-byte cache line, so a probe run crosses into a second line about 7% of the time (hit) and 32% (miss): **1.07 and 1.32 lines per lookup** [arith, assumes the run starts at a random cell]

the wrong intuition to drop early: "a hash table is the naive choice and a smarter structure must be faster." for exact-match lookups of random keys in a table too big for cache, one access is the lower bound. cleverer structures buy other things (space, order, exactness), never fewer accesses than one.

what this means: the question is not "can a trie search faster", it is "what would we trade the one-access lookup for". the next sections price that trade.

---

## 2. function or inline: what the repo shows

**the wrong intuition.** "the lookup is a tiny piece of code, so the compiler already inlined it." it is not tiny and it is not inlined.

- `PrefetchIndex` and `GetAt` are declared `virtual ... = 0` in `kv_store.h`, so every call goes through a pointer to `KeyValueStore` [repo: `plan_paper/scripts/s6plus/s12_patch.py:15-20`]. the call sites are two lines in the S16 loop: `hash->PrefetchIndex(pf[n].hc)` and `hash->GetAt(pf[i].min, pf[i].hc, pf[i].idx)` [repo: `s16_patch.py:25,54`].
- the S19 perf profile lists `GetAt` (12.5%) and `PrefetchIndex` (7.0%) as separate symbols [measured: `perf_s19.data`, 50MB, 32 threads]. inlined code would be charged to the caller, `ClassifySequence`. this is strong evidence, not proof.
- `NextMinimizer` (38.5%) is also its own symbol, called once per base from another file [measured, same profile].

**proof, cheap.** two commands on the S19 binary settle it. `[UNCLEAR: exact path of the S19 classify binary, find the tree with ls -d ~/tools/kraken2-src-s*]`

```bash
$ nm -C <s19 classify binary> | grep -E "GetAt|PrefetchIndex|NextMinimizer"   # symbols present = real functions
$ objdump -d --no-show-raw-insn <s19 classify binary> | grep -cE "call.*(GetAt|PrefetchIndex|NextMinimizer)"   # direct calls; the virtual ones show as "call *%rax" so also count those
```

the same check is already step 4 of experiment 3 (LTO) in `next_steps_plan_2026-10-21.md`, so this is free if E3 runs.

**what this means for sir's real question.**
- good news: the table sits behind one small interface. a new structure is a new subclass of `KeyValueStore` plus a builder. the hot loop touches it in exactly two calls.
- trap: if we add a second subclass and pick it at run time, LTO can no longer turn the virtual call into a direct, inlined one. so choose the structure **at compile time** (a separate binary per structure, the way the S-chain already works). otherwise we lose the 2 to 8% that E3 may give.

---

## 3. how much can any structure change give: the ceiling

**why this section exists.** before pricing 6 structures, find out how much of the run a perfect one could even touch.

the lookup share of cpu time on the 50MB db is `GetAt` + `PrefetchIndex` = 19.5% [measured]. if a structure made the table lookup cost nothing, the run gets 1/(1 - 0.195) = **1.24x faster at most** [arith, Amdahl]. the scanner (38.5%) and the per-read loop (25.1%) are untouched by any table swap.

on the big dbs the lookup is mostly waiting on ram, so its share of wall time is larger, but it is not in the repo. the S14 103GB profile has about 45% of cycles in `NextMinimizer` + `ClassifySequence` + `GetAt` combined [measured: `perf_s14_103.data`, from the plan's row 4c], which does not separate them. **step 0c in section 7 measures it.**

what this means: the best case on 50MB is 1.24x, and every extra memory access a structure adds eats into that. a structure has to be nearly free to be worth building.

---

## 4. the options, priced

the key for a lookup is the hash of the minimizer. the minimizer is 31 letters with 7 ignored by the spaced-seed mask, so it carries 24 letters = **48 bits** `[UNCLEAR: confirm minimizer_spaces=7 and how the mask is applied in the 2.17.1 source, the sizes below use 48 bits; if the key is the full 62 bits, the sorted and directory rows grow by about 14 bits per key]`.

dbs: **103GB** = 111 GB on disk, 27.75 billion cells, about 19.4 billion stored keys at load 0.70. **50MB** = about 12.5 million cells, 8.75 million keys [arith].

| structure | cache lines per lookup | bits per key | 103GB size | 50MB size | exact? |
|---|---|---|---|---|---|
| **current**: 32-bit cell, linear probing, load 0.70 | 1.07 hit, 1.32 miss [arith] | 45.7 | 111 GB | 50 MB | no (fingerprint) |
| **A. 4-letter-per-level trie** | 24 dependent reads; about 12 with path compression at 50MB (11.5 dense levels + 1 leaf), about 18 at 103GB [arith] | n/a | far above the table (a pointer per node) | n/a | yes |
| **B. wide radix tree (ART-like)** | 3 to 6 dependent reads [guess] | 160 to 416 (20 B/key [guess] up to 52 B/key worst case [external: nlnetlabs ART article]) | 390 GB to 1 TB [arith] | 100 to 455 MB (about 100 to 170 MB if built for exactly 8.75 million keys with 4-byte references, see the B bullet) [arith] | yes |
| **C. flat exact dictionary**: 8-byte slot (48-bit key + 16-bit value), linear probing, load 0.70 | 1.15 hit, 1.63 miss [arith, 8 slots per line] | 91 | 222 GB | 100 MB | yes |
| **D. prefix directory + short sorted bucket** (the Kraken 1 shape) | 2 to 3 (directory read, then bucket) [guess] | about 40 | about 95 to 100 GB | about 41 MB | yes |
| **E. mphf + fingerprint cell** (a hash that maps the n known keys to n slots with no gaps and no collisions, so load factor 1.0) | 2 to 3 (mphf tables, then the cell) [guess] | 35 (3 bits mphf [external, unchecked] + 32-bit cell) | 85 GB | 38 MB | no (same fingerprint idea) |
| **F. sorted keys in Elias-Fano** (a compact format for a sorted list of integers) + value array | 2 to 3 (high-bits index, low bits, value) [guess] | 31.8 at 103GB, 32.9 at 50MB [arith] | 77 GB | 36 MB | yes |

how the F row is computed: Elias-Fano costs 2 + log2(u/n) bits per key, with u = 2^48 and n = 1.94 x 10^10, so 2 + (48 - 34.2) = 15.8 bits, plus 16 bits of value = 31.8 bits. at 50MB, n = 8.75 x 10^6 gives 26.9 bits + 6 bits of value = 32.9. [arith]

what each row says:
- **A is dead on arrival.** random 48-bit keys give 24 levels. the top 17 levels are dense (4^17 is about 1.7 x 10^10, close to n), so a trie there is just a slower direct-address table.
- **B pays in bytes and in levels.** a tree built for general keys carries pointers and node headers, up to 52 bytes per key, 3.5 to 9 times the current size at 50MB. that is the generic case. ck asked whether storing only ESKAPE keys, and skipping single-child chains (path compression), rescues it. worked out for exactly 8.75 million keys:
  - the top log4(8.75 million) = 11.5 letter-levels are dense (every prefix exists), the bottom 12.5 are single-child chains that compress into one leaf compare. so path compression halves a letter-per-level trie (24 to about 12) but cannot remove the dense top [arith].
  - with 8-bit levels: 65,536 subtrees after 2 levels, 133 keys each, spread over 256 children, so most children hold 0 or 1 key and become leaves directly. depth is root, level-2 node, level-3 node, leaf = 4 reads, of which the first two (512 KB total) sit in L2 [arith].
  - size: 65,536 level-3 nodes x 256 slots x 4 bytes = 67 MB, plus leaves 8.75 million x 4 bytes = 35 MB, so about 100 to 170 MB with the tail effects, 2 to 3.4x the 50 MB table and right at the edge of the 105 MB L3 [arith].
  - lookup time if everything stays in L3 (about 35 ns per L3 access [external, not measured on luna]): hash 1 access, about 40 ns; tree about 4 + 5 + 35 + 35 = 80 to 90 ns, about 2x. with the lookup at 19.5% of the run, that is about 15 to 25% slower overall, not faster [guess].
  - a miss does not exit early: the dense top is walked for any key, so a k-mer not in the db costs about the same as one that is.
- **C is the honest "dictionary".** it is what a python `dict` or an `unordered_map` does: store the whole key. it is exact, same number of accesses, **twice the memory**. it is the cheapest to build (copy `CompactHashTable`, widen the cell) and gives a clean number for "what does exactness cost".
- **D is the only trie-like shape that works.** a trie collapses to "use the top bits as a direct index, then scan a few entries". that is Kraken 1: an offset index plus a limited-range binary search [external: Kraken 2 paper, Genome Biology 2019]. kraken 2 replaced it with the compact hash table and got a database about 85% smaller [external, same paper]. careful: that win came from two changes at once (storing only minimizers instead of every k-mer, and the compact fingerprint cell), so it is not a clean vote against sorted structures.
  - **the strongest version of D, and of sir's idea.** the 2 to 3 reads in the table assume the directory lives in ram. shrink it until it fits in L3: 2^24 entries at 5 bytes is 84 MB, about one socket's L3 [arith]. each bucket then holds about 1,150 keys (4.6 KB, 72 lines). keys are uniform after hashing, so an interpolation search (guess the position from the key's value, then correct) lands within a few lines of the answer: 2 to 3 adjacent lines in one bucket [guess]. cost = one L3 hit + 2 to 3 adjacent ram lines + a little compute, which is within reach of the hash table's 1.07 to 1.32 lines. caveat: the L3 is shared with the working set of 32 threads, so an 84 MB directory will not stay resident [guess]. this version goes into step 0d so the test is fair to the idea.
- **E and F are the real space candidates.** both shrink the 103GB table, by 23% (E) to 31% (F) [arith]. E keeps the false positives, F removes them.
- **sshash is not a candidate.** it is an exact dictionary for k-mers stored as super-k-mer strings, and the only value it keeps per k-mer is a frequency weight [external: SSHash README]. kraken2 stores minimizers with a taxon each. different problem, would be a rewrite and a new thesis.

**the size win does not buy speed on the big dbs.** nothing in 103GB fits in cache either way, so every lookup is a ram trip whatever the file size. a smaller file only shortens load and exit: 77 GB vs 111 GB would save about 30% of the 6 s load and 4.5 s exit, around 3 s of a 20 s run [arith on measured S19 numbers]. the 2 to 3 accesses per lookup would cost more than that on the full input. **predicted: E and F lose on 103GB wall time** [guess].

**the one place speed could improve:** none of the options. B to F all do at least the work of the current lookup, plus more.

---

## 5. what changes in the outputs: the golden rule moves

the golden rule so far is byte-identical output. an exact structure (A, B, C, D, F) removes false positives, so on rare reads the taxon changes. even E, which keeps a fingerprint, checks one cell where stock checks a run of cells, so a few false positives differ.

so the check becomes the one double hashing already needs [repo: `next_steps_plan_2026-10-21.md` row 5, `not now` list in the talk track]:
1. run both on the full input and count differing read lines. expect a tiny fraction.
2. for every differing line, score it against the 103GB db's answer or the truth set.

the useful framing for thesis 2: the cell-width law says the false-positive rate falls as 2^-(key bits). an exact dictionary is the endpoint of that curve, zero false positives at the full key width. a measured "cost of exactness" (C against current) is one more point on the curve sir already has.

---

## 6. code change and time

**where the code lives.** `[UNCLEAR: confirm with grep on luna, below]` these are the files that touch the table:

| file | what changes | lines (guess) |
|---|---|---|
| `kv_store.h` | nothing, the interface already has `Get`, `GetWithHash`, `Prefetch`, `PrefetchIndex`, `GetAt` [repo: `s12_patch.py`] | 0 |
| new `<structure>.h/.cc` | the subclass: load, lookup, `PrefetchIndex`, `GetAt` | 200 to 400 |
| `build_db.cc` | tap the build to emit every (full hash, taxon) pair, then reduce to the LCA per key. this is the real work, because the current build never keeps the full key | 100 to 300 |
| a builder tool | external sort / mphf build over the pairs. only needed for D, E, F | 250 to 400 |
| `classify.cc` | choose the structure with a compile-time flag, load it. the hot loop does not change | 10 to 40 |
| S10 loader, S14 huge pages, `-M` path | re-do for the new file layout. none of them carry over for free | 60 to 120 |
| a correctness harness | diff vs stock, count differing lines, score them | 80 to 150 |

```bash
$ grep -rln "CompactHashTable\|KeyValueStore" <s19 source tree>/src   # which files touch the table; this decides the real file list above
```

**per option, working days for one person, to a first result on the 50MB db** [guess]:

| option | new code | days |
|---|---|---|
| only inline / LTO (E3) | 0 lines, build flags | 0.25 |
| C. flat exact dictionary | about 120 lines + 100 builder | 2 to 3 |
| D. prefix directory + bucket | about 250 + 250 builder | 3 to 4 |
| E. mphf + fingerprint | about 200 + vendored mphf library [external: PTHash is a header-only C++ library, unchecked] + 300 builder | 4 to 5 |
| F. sorted + Elias-Fano | about 300 + 300 builder (external sort) | 5 to 6 |
| B. radix tree | about 400 + 200 builder | 4 to 5, predicted loss |

**the scale-up cost is the hidden part.**
- the 50MB db is rebuilt from its 6 genomes, so it is easy. the 90 MB transplanted db is the same family.
- the 8GB and 16GB dbs are capped builds of the standard library. a rebuild needs the library genomes on luna `[UNCLEAR: not verified, same open item as plan row 5]`, and the cap rule (`minimum_acceptable_hash_value`) must be reproduced exactly.
- the 103GB db cannot be rebuilt on luna: 35 GB of free disk against a 111 GB table plus the temporary pairs [repo: talk track section 7, "not now"]. for 103GB we would claim sizes by arithmetic only and say so.
- the S10 parallel loader and S14 huge pages (the two biggest wins in the chain) have to be redone per structure, or the comparison is unfair to the new one.

**total, if the gate in section 7 says go:**
- stage 1, one structure on the 50MB db with byte/diff check: 1 week
- stage 2, 8GB and 16GB, loaders, `-M`, the 12-mode check, the 4 x 4 matrix: 1 to 2 weeks
- stage 3, write-up and chart: 3 to 4 days
- about **3 to 4 weeks** in all `[guess, assumes no other thesis work in parallel]`

---

## 7. what to do first: stage 0, two days, then a gate

**why stage 0 exists.** every cost above is a prediction. two cheap measurements turn them into numbers, and they decide whether stage 1 is worth a week.

| step | what | why | time |
|---|---|---|---|
| 0a | the grep in section 6 | fixes the real file list | 5 min |
| 0b | the `nm` / `objdump` check in section 2 | answers "function or inline" with proof | 10 min |
| 0c | `perf record` S19 on the 8GB db, full input, 32 threads, same recipe as `perf_s19.data` (see `command_log.md`) | gives the lookup share p on a big db, so the ceiling 1/(1-p) is measured, not guessed | 30 min |
| 0d | `structbench.cpp`: one file, single thread, batch-16 prefetch like S16. structures: current, C, D in two versions (directory in ram, and the L3-sized directory with interpolation search from section 4), and a path-compressed radix tree with 8-bit levels built for exactly 8.75 million keys (the B bullet in section 4). the test must also measure real L2, L3 and ram access latency on luna, since the 35 ns above is a textbook figure. key sets of 8.75 million (50MB), 1 billion, and 4 billion random 48-bit keys. report ns per lookup, hits and misses separately | the head-to-head, without touching kraken2 or any db. random keys are the right input because the hash makes real keys uniform | 1 to 1.5 days |

step 0d is where the decision comes from. it needs no rebuild, no library genomes, no byte-check. it is written on luna because the laptop has no compiler we rely on. `[UNCLEAR: laptop toolchain, if gcc exists there the first draft can be written locally]`

**the gate, decided before running so we cannot move it afterwards:**
- if the measured ceiling p on 50MB is under 25% **and** the best alternative is more than 1.3x slower per lookup at the 1 billion key size, stop. report it as a measured negative result: "why kraken2 uses a flat table". that answers sir's question with numbers and costs 2 days.
- if some structure is within 1.15x of the current lookup cost at every size **and** at least 20% smaller, go to stage 1 with that structure. that is a space result.
- anything in between: show sir the table and let him pick.

---

## 8. other things this brief found on the way

- **a cheap micro-experiment on the current table.** `PrefetchIndex` prefetches one line, `table_[idx]`. a miss lookup crosses into a second, unprefetched line 32% of the time [arith, section 1]. prefetching the next line when `idx % 16 > 10` costs a few lines of code. the intel adjacent-line prefetcher may already cover part of it `[UNCLEAR]`. worth one interleaved run if E3 finishes early. [guess]
- **the same table tells us why Kraken 2 beat Kraken 1.** distinct query minimizers only trigger table accesses, and the table is a third the size of a standard hash table [external: Kraken 2 paper]. this is the argument for sir if he asks "why did kraken change structure".
- **no published trie versus hash measurement for kraken-class lookups turned up in two searches** [external: web search 2026-10-26, indirect evidence only: ART is "comparable to hash tables" in its own paper, burst tries were used in a k-mer counter to cut cache misses]. so stage 0d is also a small original result.

---

## 9. open items

- `[UNCLEAR]` effective key width (48 or 62 bits). decides the size of rows D and F.
- `[UNCLEAR]` which of sir's words meant "inline". this brief reads it as "is the lookup a real function call, and is the table behind an interface we can swap". ck to confirm at the next meeting, section 2 answers both readings.
- `[UNCLEAR]` are the 8GB and 16GB library genomes still on luna.
- `[UNCLEAR]` S19 binary path and source tree name.
- `[MISSING]` whether E1 to E5 ran since 2026-10-21. check `command_log.md` before scheduling stage 0.

## sources

- kraken 2 paper: Wood, Lu and Langmead, Genome Biology 2019, https://link.springer.com/doi/10.1186/s13059-019-1891-0 (Kraken 1 sorted list plus minimizer offset index, Kraken 2 compact hash table, 85% smaller, 10.6 GB vs 72.4 GB on 9.1 Gbp)
- upstream `compact_hash.h` v2.1.3, https://raw.githubusercontent.com/DerrickWood/kraken2/v2.1.3/src/compact_hash.h (32-bit `CompactHashCell`, `Get`/`FindIndex`/`CompareAndSet` declared in the header and defined in the `.cc`)
- SSHash README, https://github.com/jermp/sshash (exact k-mer dictionary, per-k-mer value is a frequency weight only); Pibiri and Patro 2026 follow-up, https://pmc.ncbi.nlm.nih.gov/articles/PMC12871628/ (not readable through the fetch tool, only the abstract-level summary was seen)
- adaptive radix tree: Leis et al., https://db.in.tum.de/~leis/papers/ART.pdf (pdf not readable through the fetch tool); worst case 52 bytes per key from https://blog.nlnetlabs.nl/adapting-radix-trees/
