# kraken2 speedup: the whole story from zero, and what comes next (2026-10-21)

this explains the kraken2 speedup work from the very beginning, for someone who knows or remembers nothing about it. it is also ck's talk track for sir. it goes in this order:
- what kraken2 does
- the few computer ideas you need
- where we started
- every stage we built and what it bought
- what we found this week
- what we want to do next

lines starting with **say:** are meant to be said to sir roughly as written. every number is measured on luna unless it is marked as a prediction.

---

## 0. the whole story in 30 seconds

> **say:** "we started from stock kraken2 on luna. a run spends its time in three places: loading the database table, waiting on ram during lookups, and cpu work per read. we built a chain of fixes, S8 to S19, that attacks all three. every fix gives exactly the same output as stock. the final build, S19, is 1.9x to 4.8x faster on the full input and 10x to 15x faster on small inputs. that's on luna only. next we want to show it holds on other machines, and test five specific things."

---

## 1. what kraken2 does, from zero

you need this first, because every speedup only makes sense once you can picture where kraken2 spends its time.

**the job.** a nanopore sequencer reads DNA from a sample and writes out reads: strings of the letters A, C, G and T. in our data a read is about 3,200 letters long on average. for each read we want to know which organism it came from. in this project that means spotting the ESKAPE pathogens (the six bacteria behind most drug-resistant hospital infections).

**the trick: short fingerprints.** comparing every read against every known genome letter by letter would be far too slow. kraken2 instead cuts each read into short overlapping pieces called k-mers. a k-mer is just k letters in a row, and kraken2 uses k = 35. a 35-letter piece is long enough that it usually appears in only one species, or one small group of related species. so each piece works like a fingerprint.

**minimizers: fewer lookups.** looking up every 35-letter piece would still mean one lookup per letter. so inside each 35-letter window, kraken2 picks one 31-letter piece by a fixed rule (roughly "the smallest one after scrambling the letters"). that piece is called the **minimizer**. neighbouring windows usually pick the same minimizer, and kraken2 skips the lookup when it hasn't changed. the code that slides along the read and picks minimizers is called the **scanner**.

**the database is one giant table.** kraken2's database file, `hash.k2d`, is a **hash table**. that's a big array where a key's position is computed from the key itself, so you jump straight to it instead of searching. the key is a minimizer. the value is a **taxon**, meaning an organism or a group of organisms in the tree of life. a lookup goes like this:
1. scramble the minimizer into a big number, its hash
2. take the hash modulo the table size to get a slot number
3. check that slot. if a different key sits there, check the next slot, then the next (this is called linear probing)

we use four databases: 50MB, 8GB, 16GB and 103GB. the 103GB one is 111 GB on disk; "103GB" is its size in GiB.

**counting and deciding.** for each read, kraken2 counts how many minimizers hit each taxon. it adds those counts up along the tree of life, picks the most specific taxon with strong enough support, and writes one output line per read: read id, chosen taxon, and the list of hits.

**one run, start to finish:**
1. **load the table**: read the whole `hash.k2d` into the program's memory
2. **read the input**: read the fastq files in blocks of reads
3. **classify each read**: scanner, then lookups, then counting, then the decision
4. **write** the output lines
5. **exit**

**threads and the lock.** a thread is one worker inside the program; luna runs 32 at once, each classifying different reads. reading and parsing the input file, though, happens inside a **lock** (a rule that only one thread at a time may run that piece of code), because all the threads share one file. anything inside the lock is serial. while one thread parses, every other thread that needs new reads has to wait.

**our test setup.**
- machine: **luna**, a server with 2 intel xeon platinum 8468 cpus, 96 cores, 192 threads and 503 GB of ram
- **16 cells**: 4 databases x 4 input sizes. the inputs are:
  - 10 reads
  - 1,000 reads
  - 104,918 reads (one pod5 file)
  - 1,872,777 reads (all 16 pod5 files, 12.5 GB)
- why 16 cells: small vs big db and small vs big input stress completely different parts of the program, so every fix gets checked in all of them
- **the golden rule**: the output must be byte-identical to stock kraken2. a fix may change how fast, never what answer. we check by sorting both output files and comparing them byte for byte

what this means: a run spends its time in three places. every stage below attacks one of them:
- loading the table
- waiting on ram during lookups
- cpu work per read (parsing, scanner, counting)

---

## 2. the computer ideas you need, in plain words

the stages only make sense once these are clear, so each gets one short paragraph.

**cache vs ram.** the cpu has a small amount of very fast memory built in (cache) and a large amount of slower memory outside it (ram). reading from cache takes a few nanoseconds. reading from ram takes about 100 ns, which is hundreds of cpu steps (cycles). luna's biggest cache, the L3, is 105 MB per cpu. the 50MB table fits in it. the 8GB, 16GB and 103GB tables don't, so almost every lookup in them is a trip to ram.

**the three regimes.** this splits our 16 cells into three situations that behave differently:
- **small db (50MB)**: lookups are cheap, so cpu work dominates. fixes that save cpu steps show up here
- **big db (8GB and up)**: lookups wait on ram. fixes that hide or cut ram waits show up here
- **few reads (10 or 1,000)**: almost the whole run is loading the table. fixes to loading show up here

most "why did this fix help one db and not another" questions are answered by these three.

**page cache.** when a program reads a file, linux keeps a copy of it in spare ram, so the next read is fast. our db files were already sitting there, which is called "warm". so in every run so far, "loading the table" never touched the disk. it copied ram to ram.

**pages and page faults.** linux hands out memory in **pages** of 4 KB. the first time a program touches a page, the cpu stops, and the kernel (the core of the operating system) finds a free page, fills it with zeros and connects it to the program. that stop is a **page fault**, about 2 µs each on luna. the 103GB table is 27 million pages, so loading it means 27 million page faults.

**TLB.** a program uses made-up "virtual" addresses, and the cpu has to translate each one to a real location in ram. the **TLB** is the cpu's small notebook of recent translations, a few thousand entries. with 27 million pages and random lookups, the notebook almost never has the right entry. so before reading the data, the cpu has to do extra memory reads (a "page walk") just to find where the data lives.

**prefetch.** a prefetch is an instruction that says "start fetching this address now, I'll need it soon", without waiting for the answer. it lets several ram trips overlap instead of happening one after another. think of ordering several parts at once, instead of ordering one, waiting for delivery, then ordering the next.

**division is slow.** adding two numbers takes about 1 cpu cycle. dividing two 64-bit numbers takes 20 to 40. a "%" (remainder) is a division.

**perf.** a linux tool that samples what the cpu is doing thousands of times a second. it tells you which functions, and even which single instructions, take the time. most of the fixes below started from a perf profile.

what this means: every stage below is one of five moves:
- remove page faults
- hide ram trips
- remove divisions
- make the serial part shorter
- stop the cpu from stalling

---

## 3. where we started: stock kraken2 (S0)

every speedup is measured against this.

stock kraken2 v2.17.1 (the latest release) on luna, 32 threads, output written to disk:

| db | 10 reads | 1,000 reads | 104,918 reads | 1,872,777 reads |
|---|---|---|---|---|
| 50MB | 0.40 s* | 0.30 s | 1.31 s | 16.71 s |
| 8GB | 4.52 s | 4.58 s | 5.72 s | 21.17 s |
| 16GB | 8.40 s | 8.25 s | 10.35 s | 25.81 s |
| 103GB | 58.20 s | 55.68 s | 57.20 s | 95.62 s |

\* a one-off slow start; an earlier run of the same cell measured 0.08 s.

how to read it:
- on 103GB, classifying 10 reads takes 58 s, almost the same as 104,918 reads. so nearly all of that time is loading the table, not classifying
- on 50MB there's almost nothing to load, so its time is real classification work

**the detour first: the software cache (S1 to S7).** the original idea, thesis 1, was a small per-thread cache in front of the table. it would remember recent minimizers and their taxa, so repeated lookups could skip the slow table. here's what happened:
- we built it: a 1-slot version (S1), then a 4-way version (S2)
- we fixed a crash (S3) and a bad hash (S4)
- we measured it carefully. the hit rate stayed small, about 3.6% at the 4-way default
- making it bigger raised the hit rate to 28%, but the program got slower, because a bigger cache costs more to check and to set up than it saves
- then came an ablation (the same binary with the cache removed). it showed S6's early speedup didn't come from the cache at all. it came from a file-handling change in the same binary, and that change became S8

so from S8 on, we went after where the time actually goes.

> **say:** "we started from stock kraken2 v2.17.1 on luna. on 103GB even 10 reads took 58 s, because loading the table took about 56 s on one thread. we first tried the software cache, but the hit rate was too low to matter, and an ablation showed the early speedup came from a pipeline fix instead. so from S8 on we went after where the time actually goes."

---

## 4. what we built: S8 to S19, one stage at a time

each stage is the previous stage plus one change, built as its own binary so it can be measured on its own. each was checked byte-identical against stock. unless noted, numbers are wall time at 32 threads on the full 1,872,777-read input, from 3 interleaved runs. interleaved means alternating old and new binary, so background noise on the shared machine hits both equally.

the final chain is S0 + S8 + S9 + S10 + S12 + S13 + S14 + S15 + S16 + S17 + S18 + S19. S11 was tried and dropped.

### S8: one input stream instead of 16 (pipeline)

**the problem.** our input is 16 fastq files, because the sequencer writes one file per chunk of the run. stock kraken2 handles them one at a time. for each file it starts its 32 threads, they classify that file, and then all 32 wait at a **barrier** (a point where everyone waits for the slowest one) before the next file starts. 16 files means 16 rounds of "start everyone, then wait for the slowest".

**the fix.** hand all 16 files to one round. the file reader switches to the next file by itself when one ends, so the threads see one continuous stream of reads.

**why the answer doesn't change.** same reads, same order, same content.

**result:**

| db | stock | S8 | speedup |
|---|---|---|---|
| 50MB | 15.6 s | 11.1 s | 1.41x |
| 8GB | 19.7 s | 14.6 s | 1.35x |
| 16GB | 25.1 s | 19.1 s | 1.32x |
| 103GB | 89.9 s | 85.3 s | 1.05x |

it's biggest on small dbs, where the barrier waits are a bigger share of a short run. only the 16-file input benefits; the smaller inputs are single files.

> **say:** "S8 makes the 16 input files one stream, so the 32 threads stop waiting at 16 barriers. 1.41x on 50MB."

### S9: batched prefetch (ram waits). sir has seen this

**the problem.** stock looks up one minimizer, waits the full ~100 ns ram trip, then moves to the next: one at a time. earlier profiling on luna found ram bandwidth only 5 to 11% used. the cpu wasn't moving much data, it was waiting.

**the fix.** it has two passes:
- scan a batch of 16 minimizers and issue a prefetch for each one's table slot
- go back and resolve them in the original order

the 16 ram trips now overlap. this builds on Chirag Suthar's batched-prefetch idea, so credit him. the batch size comes from the `K2_B` setting, 16 by default.

**why the answer doesn't change.** the first pass only starts fetches. the second pass does exactly what stock did, in the same order.

**result.** 103GB went from about 87 s to about 76 s. 8GB and 16GB didn't change at the time, because other costs hid it.

> **say:** "S9 overlaps the ram trips by prefetching a batch of 16 lookups before using them, building on Chirag Suthar's batched-prefetch idea. 87 s to 76 s on 103GB."

### S10: parallel table load (loading). sir has seen this

**the problem.** stock loads the table with one read call on one thread. on 103GB that took about 56 s, 60% of a 90 s run, before a single read was classified.

**the wrong intuition.** "the load is a disk read, so it's limited by the disk." the file was already in ram (page cache). the time went into 27 million page faults plus the copying, all done by one thread, one after another.

**the fix.** split the table into 64 MB chunks. up to 32 threads each `pread` their own chunks at the same time, straight into the table's memory. `pread` means "read from this exact position in the file", so the threads never get in each other's way. if anything fails, it falls back to the old single read.

**why the answer doesn't change.** the same bytes land in the same places.

**result.** this is the S10 binary, which also includes S8 and S9:

| db | stock | S10 | speedup |
|---|---|---|---|
| 50MB | 16.45 s | 11.61 s | 1.42x |
| 8GB | 20.73 s | 11.96 s | 1.73x |
| 16GB | 25.42 s | 13.80 s | 1.84x |
| 103GB | 90.47 s | 34.46 s | 2.63x |

16GB with only 10 reads, where loading is the whole run, went 9.14 s to 1.89 s.

> **say:** "S10 loads the table with 32 threads instead of one. the file is already in ram, so this spreads page faults and copying across cores. 90 s to 34 s on 103GB."

### S11: first scanner rewrite (tried, measured nothing, dropped)

**the problem.** perf showed the scanner at about a third of all cpu time. it keeps its candidate minimizers in a `std::deque`, a general-purpose queue with some overhead.

**what we tried.** two changes:
- a fixed-size ring buffer (a simple circular array) instead of the deque
- a single-instruction byte swap instead of a 3-step one inside the reverse complement

**result.** cpu time 300.44 s vs 301.90 s. nothing. it was dropped. the reason only came to light in S18, so keep it in mind.

> **say:** "S11 was a scanner rewrite that measured nothing. we found out why later, in S18."

### S12: remove the hidden divisions (cpu work in the lookup)

**the wrong intuition.** "a division is one instruction, so it's cheap." it takes 20 to 40 cycles, against 1 for an add.

**the problem.** every lookup needs `slot = hash % table_size`. the code computed it twice: once for the prefetch, then again for the real read of the same slot. every probe step to the next slot divided again. that's billions of divisions per run.

**the fix.** three parts:
- compute the slot once. the prefetch step computes it and hands it on
- replace `%` with an exact multiply. a constant `floor(2^64 / table_size)` is computed once when the table loads; then one multiply and at most one subtract give exactly the same remainder
- on probe steps, only divide when the step actually wraps past the end of the table

**why the answer doesn't change.** it is the exact same remainder. the table and the probe order don't change at all.

**result.** 50MB 11.62 s to 10.98 s, 5.5% faster. 8GB didn't change, because there the lookup waits on ram, not on arithmetic. that's the regime idea from section 2.

> **say:** "S12 replaces two or three 64-bit divisions per lookup with one multiply. 5.5% on 50MB, none on 8GB, which is memory-bound."

### S13: memchr in the fastq parser (the serial part)

**the wrong intuition.** "parsing is only a few percent of the cpu, so a faster parser can't matter."

**why it matters anyway.** the parse runs inside the lock, one thread at a time. it's serial, so its time is on everyone's clock.

**the problem.** the parser looked for the end of each line one byte at a time:

```cpp
for (i = ks->begin; i < ks->end; ++i) if (ks->buf[i] == '\n') break;
```

a parse-only test on the full 12.5 GB input showed this loop was 65% of all parsing time.

**the fix.** use `memchr`, the C library's "find this byte" function. it checks 16 to 64 bytes per instruction using SIMD (one instruction working on many bytes at once). it returns exactly the same position.

**result:**
- parse only, one thread, 12.5 GB: 10.53 s to 3.88 s (2.7x)
- end to end, 8GB, 32 threads: 11.94 s to 10.41 s, 12.8% faster

that 3.88 s is still serial today. we call it the "parse floor", and it comes back in section 7.

> **say:** "the input parse runs inside a lock, so it's serial. S13 swaps a byte-by-byte newline search for memchr. the parse went from 10.5 s to 3.9 s, and 8GB got 13% faster."

### S14: huge pages for the table (loading and ram waits)

**the problem.** the table used normal 4 KB pages, which costs twice:
- **during the load**: 27 million page faults on 103GB. kernel time was 220 s out of 675 cpu-seconds
- **during classification**: random lookups across 27 million pages miss the TLB almost every time, so each lookup first needs a page walk

**the fix.** allocate the table aligned to 2 MB and ask linux for 2 MB "huge pages":

```cpp
posix_memalign(&hp, 2 << 20, tbytes);       // 2 MB-aligned memory
madvise(hp, tbytes, MADV_HUGEPAGE);          // please back this with 2 MB pages
```

one 2 MB page replaces 512 small ones, so 103GB goes from 27 million pages to about 53 thousand. that's far fewer faults and far fewer TLB misses. if linux can't supply huge pages, it quietly uses small ones and everything still works.

**why the answer doesn't change.** same bytes, same addresses. only the page size behind them changes.

**result:**
- 8GB: 10.36 s to 8.29 s (20% faster)
- 16GB: 11.9 s to 9.15 s (23% faster)
- 103GB: 35 s to somewhere between 13 s and 20 s

the 103GB range is real variance. a huge page needs 2 MB of physically contiguous free memory, and when memory is fragmented linux can't always supply it. four back-to-back runs gave 13.1-13.3 s. a run right after a small-page binary gave 20.2 s.

> **say:** "S14 puts the table on 2 MB pages instead of 4 KB. that's 512x fewer pages, so fewer page faults while loading and fewer TLB misses on lookups. 20-23% on 8GB and 16GB, and 103GB went from 35 s to 13-20 s. the range is because huge pages need contiguous free memory."

### S15: run-length hit counting (cpu work per read)

**the problem.** every resolved minimizer did `hit_counts[taxon]++` on a hash map, about 5 to 6% of cpu time. long stretches of a read usually hit the same taxon, so it was the same map entry over and over.

**the fix.** keep a local "current run" (which taxon, how many in a row). only write to the map when the taxon changes, or at the end of the read.

**why the answer doesn't change.** every hit is still counted exactly once. map entries are still created in the same first-seen order, and that matters, because kraken2 breaks ties by that order.

**result.** small but everywhere: 1.6% to 2.2% faster.

> **say:** "S15 counts runs of the same taxon locally instead of updating a hash map per hit. about 2% everywhere."

### S16: pipelined prefetch (ram waits, building on S9)

**the wrong intuition.** "S9 already prefetches, so prefetching is done." timing matters. a prefetch that arrives after you needed it is wasted. S9 used each batch right after prefetching it, so the first few fetches in every batch hadn't arrived yet.

**the fix.** keep two batches in flight. while resolving batch N, already scan and prefetch batch N+1. by the time batch N+1 is used, its fetches have had a whole batch of work's time to land. it's like ordering the next set of parts while you assemble the current set.

**why the answer doesn't change.** same lookups, same order. only when the prefetches are issued changes.

**result:**
- 103GB: 19.18 s to 17.21 s (10% faster)
- 16GB: 1.4% faster
- 8GB: tied

it helps where lookups really wait on ram.

> **say:** "S16 prefetches the next batch while working on the current one, so the fetches have time to land. 10% on 103GB."

### S17: rolling reverse complement (cpu work per read)

**why it exists.** a read can come from either strand of the DNA double helix. so kraken2 uses the smaller of a k-mer and its reverse complement (the same stretch read from the other strand), and both strands give the same key. that's called the canonical form.

**the problem.** stock recomputed the reverse complement of the whole k-mer from scratch at every position, with 5 rounds of bit shuffling, even though the window only moves one letter at a time.

**the fix.** update it incrementally. when the window moves one letter, drop the oldest letter off one end and put the complement of the new letter on the other end: one shift and one insert. a tiny example with 3 letters:
- the window is `ACG`, and its reverse complement is `CGT`
- the next letter is `T`, so the window becomes `CGT`
- shifting `CGT` drops its last letter and leaves `_CG`
- putting the complement of `T` (which is `A`) in front gives `ACG`, exactly the reverse complement of `CGT`

this stage also added a guard so S12's multiply trick falls back to a plain `%` on compilers without 128-bit integers.

**correctness.** checked against stock in 12 kraken2 modes, byte-identical.

**result:**
- 50MB: 8.72 s to 8.40 s (3.7% faster)
- 8GB: 8.17 s to 7.92 s (3% faster)
- cpu time 5% lower on 8 cores

> **say:** "S17 updates the reverse complement one letter at a time instead of recomputing it. 3-4%."

### S18: the S11 mystery, solved (a cpu stall)

**one idea first: store forwarding.** when the cpu writes a value and reads it back soon after, it can hand over the value straight from its queue of pending writes, without waiting for the write to reach the cache. this only works if the read has the same shape as the write.

**the problem.** S11's ring buffer built each new entry as two 8-byte writes, then copied the entry as one 16-byte read. the shapes don't match, so the cpu can't hand the value over. it stalls until both writes reach the cache, on every single insert. `perf annotate` (perf at the level of single instructions) found this one instruction eating **21% of the scanner's time**. the old `std::deque` had the same stall, which is exactly why S11 measured nothing.

**the fix.** write the two fields straight into their slot, and never read them back as 16 bytes:

```cpp
inline void push(uint64_t candidate, ssize_t pos) {
  MinimizerData &d = buf[(head + n) & MASK]; d.candidate = candidate; d.pos = pos; n++;
}
```

**result:**
- 50MB 2% faster, 8GB 3% faster
- the stalling instruction fell from 21% to 3.9% of the scanner

the lesson: S11's idea was right all along; one hidden stall cancelled it out.

> **say:** "S18 found a store-forwarding stall in the scanner, a 16-byte load right after two 8-byte stores, at 21% of the scanner's time. fixing it gave 2-3%. it also explains why S11 measured nothing."

### S19: portability guard (final build)

S14's huge-page call uses a linux-only constant. S19 wraps it in a check, so the code still compiles on systems without it. on luna nothing changes. **S19 is the final build.**

### s20: tried after S19 (measured nothing, not kept)

s20 raised the prefetch batch from 16 to 64. over 3 runs on all 4 dbs it stayed within ±0.6% of S19, so it was not kept.

### all stages side by side

| stage | change | measured effect (32 threads, 1,872,777 reads) |
|---|---|---|
| S8 | one input stream | 50MB 15.6 → 11.1 s (1.41x), 103GB 89.9 → 85.3 s |
| S9 | batched prefetch | 103GB ~87 → ~76 s |
| S10 | parallel table load | 103GB 90.5 → 34.5 s (cumulative with S8, S9) |
| S11 | ring buffer + byte swap | cpu 300.44 s vs 301.90 s, **nothing** |
| S12 | no division | 50MB 11.62 → 10.98 s (-5.5%), 8GB no change |
| S13 | memchr newline search | parse 10.53 → 3.88 s; 8GB 11.94 → 10.41 s (-12.8%) |
| S14 | 2 MB huge pages | 8GB -20%, 16GB -23%, 103GB 35 s → 13-20 s |
| S15 | run-length hit counts | -1.6% to -2.2% |
| S16 | pipelined prefetch | 103GB 19.18 → 17.21 s (-10%) |
| S17 | rolling reverse complement | 50MB -3.7%, 8GB -3% |
| S18 | store-forwarding stall fix | 50MB -2%, 8GB -3% |
| S19 | portability guard | none, by design |
| s20 | prefetch batch 64 | ±0.6%, **nothing** |

these per-stage numbers only cover the full-input column, and not every db for every stage. only the final S19 was measured on all 16 cells (section 5). the pattern matches the three regimes:
- cpu fixes (S12, S15, S17, S18) show on 50MB and 8GB
- ram fixes (S14, S16) show on the big dbs
- load fixes (S10, S14) show most with few reads

---

## 5. the result: stock vs S19, all 16 cells

this is the table to put on screen. 32 threads, one run per cell, output and report byte-compared against stock:

| db | reads | stock (S0) | S19 | speedup | output vs stock |
|---|---|---|---|---|---|
| 50MB | 10 | 0.40 s* | 0.06 s | ~1.3x* | identical |
| 50MB | 1,000 | 0.30 s | 0.23 s | 1.3x | identical |
| 50MB | 104,918 | 1.31 s | 0.84 s | 1.6x | identical |
| 50MB | 1,872,777 | 16.71 s | 8.88 s | 1.9x | identical |
| 8GB | 10 | 4.52 s | 0.46 s | 9.8x | identical |
| 8GB | 1,000 | 4.58 s | 0.45 s | 10.2x | identical |
| 8GB | 104,918 | 5.72 s | 1.08 s | 5.3x | identical |
| 8GB | 1,872,777 | 21.17 s | 9.18 s | 2.3x | identical |
| 16GB | 10 | 8.40 s | 0.77 s | 10.9x | identical |
| 16GB | 1,000 | 8.25 s | 0.67 s | 12.3x | identical |
| 16GB | 104,918 | 10.35 s | 1.39 s | 7.4x | identical |
| 16GB | 1,872,777 | 25.81 s | 10.94 s | 2.4x | identical |
| 103GB | 10 | 58.20 s | 3.79 s | 15.4x | identical |
| 103GB | 1,000 | 55.68 s | 3.95 s | 14.1x | identical |
| 103GB | 104,918 | 57.20 s | 4.50 s | 12.7x | identical |
| 103GB | 1,872,777 | 95.62 s | 20.08 s | 4.8x | identical |

\* stock's cell here was a one-off slow start; against the earlier 0.08 s it is about 1.3x.

how to read it:
- **10x to 15x on big dbs with few reads.** there, loading used to be the whole run, and S10 plus S14 cut the 103GB load from about 58 s to under 4 s
- **1.9x to 4.8x on the full input.** real classification dominates there, and only the cpu and ram fixes help it
- **1.3x to 1.9x on 50MB.** there's almost nothing to load, so only the cpu fixes count

**correctness beyond these 16 cells.** S15 to S19 also pass 12 kraken2 modes on 50MB, and S19 passes them on 8GB too: confidence threshold, minimum hit groups, quick mode, base-quality masking, names, zero counts, fasta input, paired reads, 3-file input, 1 thread, 7 threads.

**the honest limits, say them before sir asks:**
- one machine, luna
- warm page cache: the db files were already in ram
- this table is one run per cell. the per-stage numbers in section 4 are 3 interleaved runs
- S19 on 103GB has measured anywhere from 12.3 s to 20.1 s across sessions, because huge pages are not always available

> **say:** "all 16 cells are byte-identical to stock, output and report, and S19 passes 12 kraken2 modes. on the full input it's 1.9x on 50MB up to 4.8x on 103GB. with few reads the big dbs get 10x to 15x, because loading used to be the whole run. limits: one machine, warm cache, one run per cell, and 103GB varies between 12 and 20 s because of huge-page availability."

### the small-machine test (stock vs S15, luna limited to N cores)

to mimic a smaller computer, we limited luna to 16, 8 and 4 cores, with threads = cores, on the full input:

| cores | 50MB | 8GB | 16GB | 103GB |
|---|---|---|---|---|
| 16 | 22.84 → 16.18 s (1.41x) | 21.34 → 14.91 s (1.43x) | 30.62 → 16.93 s (1.81x) | not run |
| 8 | 42.48 → 31.37 s (1.35x) | 35.21 → 28.83 s (1.22x) | 49.55 → 32.92 s (1.50x) | not run |
| 4 | 82.10 → 61.80 s (1.33x) | 64.18 → 57.03 s (1.13x) | 88.58 → 64.91 s (1.36x) | not run |

smaller inputs were not run here. a caveat found this week: the way the cores were picked (`taskset -c 0-7`) took half of them from each of luna's two cpus. so this was a two-cpu 8-core setup, not a laptop-like 8-core.

### where the time goes now (S19, 50MB, 32 threads, perf)

| part of the program | share of cpu time | what it is |
|---|---|---|
| scanner (`NextMinimizer`) | 38.5% | picking minimizers; now the biggest piece |
| per-read loop (`ClassifySequence`) | 25.1% | the prefetch pipeline, counting, the decision |
| table lookup (`GetAt`) | 12.5% | checking slots |
| slot computation + prefetch (`PrefetchIndex`) | 7.0% | hash to slot, start the fetch |
| copying sequences | 3.1% | moving read data around |
| building output lines | 2.1% | |
| the hit-count hash map | under 0.8% | S15 finished this off |

what this means: the scanner is the next big target. that's where experiment 3 in section 7 goes.

---

## 6. what we found this week: sir's single-channel question

sir asked: "why is reading the table with 32 threads faster when there's a single channel to the disk?"

**the short answer.** the file was already in ram (page cache), so the load was never a disk read. the cost was one thread doing 27 million page faults plus the copying: 56 s divided by 27 million pages is about 2 µs per page. S10 spreads that work over 32 threads, and the load drops to about 6 s. luna's memory isn't one channel either: it has 8 memory channels, 4 per cpu, and we checked this on the machine this week. the 32-thread load uses roughly a fifth of their bandwidth. the cold case, where the file really comes from disk, is still untested. that's where disk channels and queue depth would matter.

**how we checked: a thread sweep.** we ran the same job (stock vs the S10 binary, 103GB, full input) at 1, 2, 4, 8, 16, 32, 64, 96, 128 and 192 threads, one run each. kraken2 prints a line when loading finishes and another when classification finishes, and we timestamped every line. that splits each run into three parts:
- **load**: start to "loading done"
- **classify**: "loading done" to "classification done"
- **exit**: "classification done" to the program actually ending. that's the time linux takes to free the 111 GB table

| threads | stock total | stock load | stock classify | stock exit | S10 total | S10 load | S10 classify | S10 exit |
|---|---|---|---|---|---|---|---|---|
| 1 | 1,046.04 s | 56.23 s | 981.73 s | 8.09 s | 685.43 s | 6.37 s | 672.04 s | 7.03 s |
| 2 | 516.38 s | 57.00 s | 454.62 s | 4.76 s | 368.04 s | 5.70 s | 350.98 s | 11.36 s |
| 4 | 304.47 s | 57.72 s | 236.71 s | 10.04 s | 156.39 s | 6.17 s | 141.15 s | 9.07 s |
| 8 | 172.88 s | 58.35 s | 107.57 s | 6.96 s | 81.28 s | 6.51 s | 66.67 s | 8.10 s |
| 16 | 115.43 s | 57.88 s | 52.87 s | 4.68 s | 41.22 s | 5.94 s | 30.21 s | 5.07 s |
| 32 | 91.22 s | 58.06 s | 29.16 s | 4.00 s | 26.40 s | 6.50 s | 15.38 s | 4.52 s |
| 64 | 82.57 s | 58.19 s | 20.38 s | 4.01 s | 22.74 s | 6.44 s | 11.75 s | 4.55 s |
| 96 | 84.81 s | 58.53 s | 22.24 s | 4.04 s | 22.40 s | 5.78 s | 12.12 s | 4.50 s |
| 128 | 84.52 s | 58.06 s | 22.57 s | 3.89 s | 23.34 s | 6.14 s | 12.54 s | 4.66 s |
| 192 | 85.28 s | 58.05 s | 23.30 s | 3.93 s | 24.32 s | 6.30 s | 13.32 s | 4.69 s |

(only the 103GB db with the full input was swept; the other 15 cells were not part of this sweep.)

**what it shows.**
1. **the load never changes with the thread count**: about 58 s for stock and about 6 s for S10 in every row. kraken2 loads the table before it applies the thread count you ask for, so S10's loader always uses 32 threads. stock's always uses 1. so even at 1 thread, S10's loader saved about 50 s.
2. **exit costs 4 to 5 s** (more at low thread counts). freeing 111 GB of small pages takes real time. that's 17% of S10's run at 32 threads, and nobody had counted it.
3. **classification speeds up well to 64 threads, then gets slightly worse.** S10 is best at 64 threads (11.75 s), 3% worse at 96 and 13% worse at 192. 96 threads is still one thread per physical core, so this isn't the cores being shared. the cause isn't known yet.
4. **at 1 thread, S10 classifies 1.46x faster than stock** (981.7 s to 672.0 s). that's prefetch hiding ram trips inside a single core. it needs no extra cores, so it's the part we most expect to carry over to a small machine like the jetson or a laptop.

two more measured cautions:
- at 1 to 4 threads, classification sped up more than the thread count alone explains (S10: 2.49x going from 2 to 4 threads). one run each, cause unknown, so don't read anything into it
- the same S10 binary at 32 threads took 26.4 s today but 34.5 s a month ago, while stock stayed at about 91 s. 103GB numbers must only be compared within one session

> **say:** "the load was never a disk read: the file was already in ram. one thread paid 27 million page faults at about 2 µs each, 56 s. S10 spreads them over 32 threads and gets about 6 s. luna has 8 memory channels and that load uses about a fifth of them. the sweep also showed three things. the loader uses 32 threads no matter what thread count you pass. freeing the table at exit costs 4 to 5 s. and classification stops improving after 64 threads. at 1 thread, prefetch alone makes classification 1.46x faster, which is why we expect it to carry over to small machines. the cold, from-disk case is still to be tested."

---

## 7. what we propose next: five experiments

the open question now is whether all of this holds on other machines, and what's left on luna. there are five experiments, in this order. each is explained from zero. the expected numbers are **predictions**, not measurements.

### experiment 1: memory-mapping (`-M`) against S19

**what it is.** today kraken2 copies the whole table into its own memory before starting. kraken2 already has a flag, `-M` (memory-mapping), that skips the copy and lets the program use the file's pages directly. linux brings each part in the first time it's touched.

**why it might win.**
- no load step at all
- it needs the table in ram only once. a copy needs two: the page cache's copy plus the program's own
- no 4-5 s exit to free a private copy

**why it might lose.** mapped file pages are 4 KB, with no huge pages, so big runs get the TLB misses back that S14 removed. and every first touch of a region costs a page fault during classification.

**what we expect.**
- a big win with few reads on big dbs: 103GB at 10 reads from 3.8 s to maybe 0.1-0.3 s
- a loss on the full input: 103GB maybe 18-30 s against S19's 13-20 s

**cost.** no code change, about 20 minutes. a correctness check comes first: `-M` on S19 has never been compared with stock.

**what it decides.** whether kraken2 should choose how to load the table based on how much input there is.

### experiment 2: stock vs S19 on orin (the jetson)

**what it is.** orin is an nvidia jetson agx orin: a small arm computer with 12 cores, 64 GB of memory shared with its gpu, a 4 MB cache (luna has 105 MB per cpu), and slow emmc storage with about 8.5 GB free. it's the honest "different machine": different cpu design, far fewer cores, tiny cache, slow storage. its installed kraken2 is an older version (v2.1.3), so we would build stock v2.17.1 and S19 there from our source.

**what can run there.** 9 of the 16 cells: the 50MB, 8GB and 16GB dbs with 10, 1,000 and 104,918 reads. the 103GB db doesn't fit in 64 GB, and the 12.5 GB full input doesn't fit on its storage.

**what we expect** (predictions):
- 3x to 10x with few reads on 8GB and 16GB
- 1.5x to 3.5x at 104,918 reads on 8GB and 16GB
- 1.1x to 1.6x on 50MB

**cost.** about an hour on campus, plus orin login access.

**what it decides.** whether the speedup chain holds on a completely different machine.

### experiment 3: compiler settings (`-march=native`, LTO, PGO)

**what it is.** the compiler turns our code into machine instructions, and flags change how hard it tries. the highest normal level (`-O3`) is already on. three things are left, each built as a separate new binary so we can see what each one gives:
- **`-march=native`**: use every instruction this specific cpu has. the binary then only runs on that kind of cpu
- **LTO (link-time optimization)**: lets the compiler optimize across source files. right now the scanner lives in a different file from the loop that calls it once per letter, so every call pays the cost of entering and leaving a function. that's about 9% of the scanner's own time. LTO can merge the two
- **PGO (profile-guided optimization)**: build once with counters, run on real data, then rebuild using those counts, so the busiest paths are laid out best

**what we expect** (predictions): `-march=native` 0-3%, LTO 2-8%, PGO 4-15% on the cpu-bound cells (50MB, and the full input on all dbs). about 0% where loading dominates.

**cost.** about 2 hours. every build goes into a new folder; nothing existing is touched.

**what it decides.** whether cheap compiler work shrinks the scanner's 38.5% before anyone spends days rewriting it with SIMD.

### experiment 4: load speed vs threads on three machines, warm and cold

**what it is.** measure how fast the table loads with 1, 2, 4, 8, 16 and 32 loader threads. "warm" means the file is already in ram. "cold" means the file has been pushed out of ram first, so the load really reads the disk. we can push out just our own file without admin rights, so other luna users aren't affected.

we run it on three machines:
- **luna**
- **orin**
- **ck's laptop**: a lenovo with one memory channel. kraken2 can't run on windows, so a small benchmark program does the same kind of copy there. it's written and smoke-tested

**what we expect** (predictions):
- **luna warm**: keeps getting faster well past 16 threads, because 8 memory channels have room to spare
- **laptop**: flattens at 1-2 threads, because one memory channel fills up almost at once
- **orin warm**: in between
- **orin cold**: no gain from more threads, because its emmc storage only reads about 0.3 GB/s whatever you do

**cost.** about an hour on luna, 30 minutes on orin, 5 minutes on the laptop.

**what it decides.** it answers sir's channel question properly, with data per machine. it also tells us whether to lift the 32-thread limit on the loader.

### experiment 5: S19 thread sweep on 50MB and 8GB

**what it is.** the same kind of sweep as section 6, but for S19 on the small dbs, with threads from 8 to 192. the parse runs inside the lock and takes at least 3.9 s (S13), so at some thread count it must become the wall. this finds where.

**what we expect** (prediction): the time keeps falling until about 48-64 threads, then flattens near 4-5 s.

**cost.** about 25 minutes.

**what it decides.**
- if it flattens near the parse time, a parallel parser (every thread parses its own chunk) is worth building, and it would help big machines like luna
- if it keeps falling, drop the idea

it also tells us the best thread count for S19 on luna, which is a free speedup.

**timing.** experiments 1, 3 and 5 can run this week on luna. 2 and 4 need orin.

### not now, and why (if sir asks)

- **double hashing (thesis 2).** it changes which slots keys land in, so the output changes and needs an accuracy comparison instead of a byte check. rebuilding the 103GB db doesn't fit in luna's 35 GB of free disk.
- **SIMD scanner.** do it after experiment 3 shows how much plain compiler work gives.
- **the software cache.** tested three times, see section 9.

> **say:** "next we want to answer whether this holds on other machines. five experiments, in order.
> one: memory-mapping against S19. it should win big with few reads and lose with many; it decides whether the load strategy should depend on input size.
> two: stock vs S19 on orin, the 9 cells that fit there.
> three: compiler settings, `-march=native`, LTO and PGO, aimed at the scanner, which is now 38.5% of the time.
> four: load speed vs threads on luna, orin and a one-channel laptop, warm and cold, which answers the channel question properly.
> five: an S19 thread sweep, to see if a parallel parser is worth building.
> one, three and five can run this week on luna. two and four need orin."

---

## 8. what ck needs from sir

- an ok on the order of the five experiments
- orin access: the login, or a time slot on campus (orin is only reachable on the campus network)
- whether cold-from-disk numbers are worth the effort
- whether thesis 2 (double hashing, the bitmask cell) should come before or after this

---

## 9. if sir asks

**"is this only luna?"**
"yes, so far. that's why experiments 2 and 4 are next. the code has no intel-only parts, and the two places that could be machine-specific have fallbacks, so it should build on the jetson. but it hasn't been tested there."

**"where is the cache, thesis 1?"**
"we tested it three times. at the 4-way default the hit rate is about 3.6%. bigger caches raised it to 28% but made the program slower, because checking and setting up the bigger cache cost more than it saved. an ablation showed the early speedup came from the file-streaming fix, S8. the cache can be re-tested on top of S19, where the remaining costs are much clearer."

**"why is 103GB a range?"**
"huge pages need 2 MB blocks of contiguous free memory. luna had about 100 GB free, with 359 GB used as file cache, so sometimes linux can't supply enough of them and falls back to small pages."

**"why not just use more threads?"**
"on 103GB, classification stops improving after 64 threads, and the loader is fixed at 32 threads anyway."

**"is the output really the same?"**
"byte-identical in all 16 cells, output and report, sorted by read id. S15 to S19 also pass 12 kraken2 modes on 50MB, and S19 passes them on 8GB too."

**"what about the single-channel laptop?"**
"a quick smoke test suggests plain copying fills its one memory channel at 1 to 2 threads. the real run is part of experiment 4."

---

## 10. the other thing sir asked: teaching the 50MB db from the 103GB db

sir asked whether we can bring entries from the 103GB db into the 50MB db. this is separate from the speedup work; it's here in case it comes up.

**why copying doesn't work.** each slot in the 103GB table stores only 16 bits of the key. the slot's position tells you more, but not enough to recover the original minimizer, so you can't list what's inside the table and copy it over.

**what does work: asking it.** we can't list its keys, but we can look any minimizer up. so:
1. rebuild the 50MB db from its own 6 genomes
2. for every minimizer of those genomes, ask the 103GB db what it says, and move the small db's answer up the tree when the big db says it's shared more widely
3. for every minimizer in some training reads, ask the 103GB db. keep the answer only if it falls inside an ESKAPE genus, so the db stays ESKAPE-only
4. add the competitor species the big db sees as their own taxonomy entries

**result.** agreement with the 103GB db on held-out reads (a file not used for training) went from 65.6% to 94.4%. the db grew from 51 MB to 90 MB. speed on the full input: 7.9 s (50MB), 8.3 s (90 MB version) and 12.3 s (103GB), all with S19.

**three limits to say out loud:**
- it's not a neural network; it's direct lookups
- the 103GB db is treated as the truth, so "agreement" means imitation, not proven correctness
- the held-out reads come from the same sequencing run. the version that uses no reads at all, only genomes, reaches 78.3%, and that's the sample-independent number

---

## 11. do not say

- "the loader does nothing at 1 thread". it uses 32 threads every time.
- "faster on every machine". only luna has been measured.
- "1.8x to 4.4x" for S19. that was S15; S19 is 1.9x to 4.8x.
- that the load time is "total minus classification time". that includes the 4-5 s exit.
- s20 as an improvement. it measured nothing.
- any prediction from section 7 as if it were measured.
- "patch 4".

---

## glossary (one line each)

- **k-mer**: k letters in a row from a read. kraken2 uses 35.
- **minimizer**: the one 31-letter piece kraken2 picks from each 35-letter window. it's what gets looked up.
- **scanner**: the code that slides along a read and picks minimizers.
- **taxon**: an organism or group of organisms in the tree of life.
- **hash table**: an array where a key's position is computed from the key, so you jump straight to it.
- **linear probing**: if a slot is taken by another key, try the next slot.
- **thread**: one worker inside the program. luna runs 32 at a time in our tests.
- **lock**: a rule that only one thread at a time may run a piece of code. that piece becomes serial.
- **barrier**: a point where all threads wait for the slowest one.
- **cache vs ram**: small fast memory inside the cpu vs big slow memory outside it. about 100 ns per ram trip.
- **page cache**: linux's copy of recently read files in spare ram. "warm" means the file is already there.
- **page / page fault**: memory comes in 4 KB pages. the first touch of a page stops the cpu while linux sets it up, about 2 µs.
- **huge page**: a 2 MB page, replacing 512 small ones.
- **TLB**: the cpu's small notebook of where pages live. a miss means extra memory reads.
- **prefetch**: "start fetching this now, I'll need it soon".
- **store forwarding**: the cpu handing a just-written value straight to a read. it breaks if the shapes differ.
- **SIMD**: one instruction working on many bytes at once.
- **perf**: the linux tool that shows where cpu time goes.
- **byte-identical**: the output files match exactly, byte for byte, after sorting by read id.
- **interleaved runs**: alternating old and new binary, so background noise hits both equally.
- **thread sweep**: running the same job at many thread counts to see how the time scales.
- **`-M` / memory-mapping**: using the db file's pages directly instead of copying the table into the program.
- **LTO / PGO**: compiler modes that optimize across files, and that lay out code using counts from a real run.
- **orin**: the nvidia jetson agx orin, a small 12-core arm computer, campus network only.
