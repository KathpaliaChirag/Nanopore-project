# cycle 3 round 2, agent B: a bit-identical bulk minimizer scanner (design only, nothing run)

sources read (read-only ssh): kraken2-src-s19/src/mmscanner.{h,cc} in full (e1/src_dedup copy is diff-identical), classify.cc lines 773-870 (fill lambda and the resolve loop), mmtest.cc (a 10-line toy, unusable as a harness), plus the cycle 3 round 1/2 and cycle 2 files. tags: [read] from source, [A] my arithmetic, [G] guess, nothing here was measured.

## 1. what the code does, exactly (standard db: dna, k=35, l=31, revcom v1, w = k-l+1 = 5)

classify.cc: LoadSequence(seq) once per read, then fill() calls NextMinimizer() until nullptr, copies *ptr, calls is_ambiguous(), and only for non-ambiguous items does MurmurHash3 and PrefetchIndex. ambiguous items get AMBIGUOUS_SPAN_TAXON and their value is never used (last_minimizer dedupe is only updated for non-ambiguous items). aa_translate (translated search) is not used here: it feeds protein strings with dna_=false. the bulk path must only be enabled for dna_ && revcom_version != 0 && k > l, everything else falls back to the old class.

the stream contract, derived by walking the code (let n = read length, i = 0-based char index, r(i) = number of consecutive ACGTacgt chars ending at i):
1. items are emitted for exactly the chars i = k-1 .. n-1, one per char, so n-k+1 items for n >= k and zero for n < k. proof: the first call loads chars until str_pos_ = k (returns by the queue break or by the "loaded_ch_ < l" early return), and every later call consumes exactly one char and returns (after an N the early return fires per char while the l-mer refills). a read of all N still yields n-k+1 items, all ambiguous.
2. c(i) = number of l-mers completed since the last reset = max(0, r(i)-l+1). queue_pos_ after the increment equals c(i), so is_ambiguous = (c < k-l) = (r < k-1 = 34). the last_ambig_ word is redundant: any N forces a full l-mer refill, and by the time loaded_ch_ == l the N has shifted out of the 62-bit mask. note the quirk: r = 34 means only 4 l-mers are in the window yet the item is flagged NOT ambiguous (off by one in stock kraken2). bit-identical means we copy it.
3. value: for c >= 1 the item is (min over the last min(c,5) candidates) ^ toggle, where candidate(l-mer) = ((min(lmer, rc_lmer)) & spaced_mask) ^ toggle, lmer = 62-bit window of the 2-bit codes, rc_lmer = rolling reverse complement ((rc >> 2) | ((3-code) << 2(l-1))). for c = 0 (refilling after an N, or the first 34 chars with an N) the value is the stale last_minimizer_: the value of the last item with c >= 1 in this read, or UINT64_MAX if none yet. LoadSequence resets it to ~0. stale values are never consumed by classify, so a relaxed test may ignore them, but the stream-compare should check them exactly.
4. the deque is exactly a sliding min over the last 5 candidates (expiry keeps pos >= pos_new-4; push pops only strictly greater, so equal values stay). only the value is emitted, never the position, so tie-breaking cannot change the output: any exact min over the same 5 values is bit-identical. that answers question (b) on ties: the deque keeps the OLDER of two equal candidates at the front, but it is unobservable.
5. lowercase maps like uppercase (lookup table). every other byte, IUPAC codes, '-', '\0', is "ambiguous". bytes >= 0x80 index the table with a negative int in the old code (undefined behaviour); the bulk code treats them as ambiguous. exclude them from the exactness test and say so.
6. an N resets: queue cleared, queue_pos_ = 0, lmer = rc = 0, loaded_ch_ = 0 (so the next l-1 chars still return items, ambiguous, with the stale value).

## 2. where 267 instructions and 1.30 mispredicts per base come from [A/G, no per-instruction profile exists]

per call (one base), the scanner side, roughly: prologue/epilogue 15 (it is an out-of-line function), entry check plus computing bits_per_char and ambig_code from the runtime dna_ flag 12, the loaded_ch_ == l test and decrement 4, char loading loop 35 (reload str_ data pointer through the std::string*, table lookup, UINT8_MAX test, two variable shifts, rolling rc with a runtime shift 2*(l-1), two mask ands, loop condition with str_pos_ and finish_ re-read), canonical + spaced mask + toggle 12 (spaced_seed_mask_ and toggle_mask_ are loaded from this, every `this` field is reloaded because the ring-buffer stores may alias them), k_ == l_ test 2, pop loop about 0.8 iterations x 10 = 8 plus 5 for the loop test, queue_.empty() branch 4, push 12, expiry test 10, queue_pos_ == k-l test and increment 6, break test 3, final front load, xor, store 10. that is about 150. fill() adds is_ambiguous (8), pf stores (6), loop (4), MurmurHash3 and PrefetchIndex (about 25 per non-ambiguous item). the classify resolve loop (compare to last_minimizer, run counting, taxa.push_back) adds about 40 per item. sum is near 267 and the scanner share (about 48% of cpu, [measured] by the slope test) is about 130 to 150 instructions, which is the target.

mispredicts, per base [G]: (1) pop loop exit count is 0..4 and data dependent, about 0.4 to 0.5; (2) expiry test and queue_.empty() test, each true about 1/3 or 1/5 of the time at random, about 0.3 combined; (3) in classify, `pf[i].min != last_minimizer` is true about 1/3 of the time (minimizer density 2/(w+1) = 1/3) and is random, about 0.35, and the taxon / run-count branches add about 0.15. so roughly 0.8 of the 1.30 are inside the scanner and 0.5 in the classify loop. the scanner part is removable by branch-free code, the classify part is not touched by this design (see 6).

## 3. (a) scalar bulk scan: state in registers, same stream

interface (new file mmbulk.h, no change to MinimizerScanner, which stays as the fallback and as the test oracle):

```
struct BulkState {            // everything needed to resume, so long reads can be chunked
  uint64_t lm, rc, run;       // run = consecutive clean chars, saturated at 64
  uint64_t c1, c2, c3, c4, a1p, a2; // ce_t-1..ce_t-4, p_t-1, p_t-2
  uint64_t stale;             // starts at ~0
  size_t   i;                 // next char index
};
size_t ScanBulk(BulkState &st, const char *s, size_t n, uint64_t *mins, uint8_t *amb, size_t max_items);
```
per-thread arrays mins[CHUNK], amb[CHUNK] with CHUNK = 4096 (32 KB + 4 KB, fits L1d/L2; reads average 3,225 bases so most reads are one chunk). ScanBulk copies st into locals, runs, writes st back. it returns the number of items written (n-k+1 total across calls, items start at i = k-1).

per base, in the main loop (i >= k-1; a warm-up loop for i < k-1 is the same body without the stores and without touching `stale`):
```
code = tab[(uint8_t)s[i]];            // 0..3, or 0xFF  (same table as the class, uppercase+lowercase)
keep = (code <= 3) ? ~0ull : 0;       // setcc + neg
lm = (((lm << 2) | (code & 3)) & LM) & keep;
rc = (((rc >> 2) | ((uint64_t)(3 - (code & 3)) << SH)) ) & keep;   // SH = 2*(l-1)
run = keep ? min(run + 1, 64) : 0;    // cmov, saturating
cand = ((lm < rc ? lm : rc) & SM) ^ TG;   // SM = spaced mask, or ~0 if zero; TG = toggle & LM
ce = (run >= l) ? cand : ~0ull;       // sentinel when the l-mer is not complete
a1 = min(ce, c1);                     // p_t = pair min of ce_t and ce_t-1 (c1 = ce_t-1)
m  = min(min(a1, a2), c4);       // a2 = p_t-2, c4 = ce_t-4
valid = run >= l;
val = valid ? (m ^ TG) : stale;  stale = val;
mins[o] = val;  amb[o] = (run < k-1);  o++
shift: ce_t-4=ce_t-3; ce_t-3=ce_t-2; ce_t-2=ce_t-1; ce_t-1=ce; p_t-2=p_t-1; p_t-1=a1   (see recurrence note below)
```
the window recurrence needs care so the test catches it: with ce_t the newest, window = {ce_t, ce_t-1, ce_t-2, ce_t-3, ce_t-4}. keep p_t = min(ce_t, ce_t-1) every step and q = p_{t-2} = min(ce_t-2, ce_t-3); window min = min(p_t, p_{t-2}, ce_t-4). registers: ce_t-1, ce_t-2, ce_t-3 -> shift, p_{t-1}, p_{t-2} -> shift. unroll by 2 so the moves vanish.

invariants for identical output: (i) sentinel ~0 is above every real candidate (candidates < 2^62), so a window containing N-era slots returns the min over the valid ones only; after an N, ce = ~0 for at least l-1 = 30 >= 5 steps, which flushes all 5 slots, so no explicit queue clear is needed. (ii) when c in 1..4 the window has c valid slots and the rest sentinel, matching the deque that holds only c entries. (iii) `stale` changes only on valid items and is only reset by a new ScanBulk start (~0), matching last_minimizer_. (iv) warm-up must run the full recurrences for chars 0..k-2 but not emit and not update stale. (v) amb uses run < k-1 with run NOT saturated below k (saturation at 64 is fine).

fill() consumption: keep a per-read cursor. fill(pf): `while (n < la_batch && cur < have) { pf[n].min = mins[cur]; pf[n].amb = amb[cur]; ...hash/prefetch as now...; n++; cur++ }`, and when cur == have and the read is not exhausted, call ScanBulk again for the next chunk. the end-of-stream test (`n < la_batch` means exhausted) must then be `exhausted flag` rather than the short batch, because a chunk boundary can end a batch early: set exhausted only when ScanBulk returns 0 and the cursor is drained. LoadSequence analogue = init BulkState{stale=~0, i=0}, then if n < k, zero items. the whole-read-at-once variant is the same code with CHUNK >= n and is the simplest first landing.

expected cost [A]: about 45 to 55 instructions per base, almost no data-dependent branches (loop only; cmovs). the longest dependency chain is one cycle per op (lm update, run, stale cmov), so IPC near 3.5 gives 14 to 17 cycles per base against about 55 cycles now (48% of 116). scanner cpu share falls from 48% to about 14%, total cpu 214 -> about 150 to 160 cpu-s at 8 GB (-25 to -30%) [G]. mispredicts fall by about 0.8 per base (0.8 x 17 cycles = 14 cycles per base of the saved 40) leaving about 0.5 per base, all in the classify loop.

## 4. (b) the 5-slot branchless window min: summary of what is exact and cheap

min over 5 is 4 two-input mins naively (8 instructions as cmp+cmov); the pair-sharing form above does 3 mins per step (6 instructions) because the pair p_t is reused two steps later. there is no tie-breaking requirement (section 1 item 4); a strict or non-strict compare gives the same value. the only things that must match the deque are the sentinel handling after an N and the c < 5 start-up windows, both covered. if the compiler turns `lm < rc ? lm : rc` into a branch, force cmov with `__builtin_expect_with_probability(..., 0.5)` or inline asm; check the disassembly for jcc inside the loop.

## 5. (c) stretch: AVX-512 lane-parallel, 8 segments

the item at index i depends only on chars i-34 .. i (the last k chars) plus the `stale` chain. so a clean read (no non-ACGT char; the common case for dorado fastq, the files are ~/chirag_K/results/per_pod5_fastq/pod5_*.fastq) splits exactly: S = ceil((n-k+1)/8) items per lane, lane j owns items [k-1+jS, k-1+(j+1)S) and starts 34 chars earlier (overlap k-1, a 34-char warm-up costing 34/S = 8% for S = 400). there are no resets inside a clean read, so no sentinel gating, run is implicit, amb is all false, stale never matters (all c >= 5 after the first item).
- clean test: one vector pass, vpermb or vpshufb LUT over 64 bytes (or `c & 0xDF` compares for A,C,G,T), OR-reduce, about 0.1 instr per base. any non-clean read goes to the scalar bulk (a), never to a lane path with N logic (this is the key simplification, and the fallback is exact).
- per step, 8 lanes of u64 (zmm): code = x ^ (x >> 1) with x = (c >> 1) & 3 (maps A,C,G,T to 0,1,2,3 for both cases); lm = ((lm << 2) | code) & LM; rc = (rc >> 2) | ((3-code) << SH); cand = ternlog((vpminuq lm,rc) & SM) ^ TG as one vpternlogq; window min = 3 vpminuq with the same pair-sharing; final ^ TG. about 14 zmm instructions per step = about 1.75 instructions per base, plus data movement: gathering the 8 chars per step by 8x8 byte transpose every 8 steps (about 1 instruction per base) and writing output with the reverse qword transpose (about 1 per base). total about 4 to 5 instructions per base, 1 to 1.5 cycles per base, 10 times better than scalar bulk. SimdMinimizers reports 1.3 to 2 ns per base on AVX2 including compaction (round 1 literature); the SPR AVX-512 estimate here is under 1 ns [G]. sentinel for the last lane's shorter tail: pad S with a scalar tail loop.
- bonus: MurmurHash3 of 8 candidates is 2 vpmullq (AVX512DQ) plus shifts, so hash coding can be fused into the same block; the PrefetchIndex remains scalar (it needs the hash table base and FastMod).
- risks: transpose bugs and the chunk joins, both caught by the stream compare below; AVX-512 frequency licence on 8468 is mild for integer ops.

## 6. interface note: what stays untouched

the `pf[i].min != last_minimizer` branch (about 0.35 mispredicts per base) lives in classify. a phase-2 option that is not bit-identical in the stream but identical in classify output: the bulk scanner also writes a `changed` byte (val != previous non-ambiguous val) so fill can compact to (value, runlength) pairs branch-free (out[no] = v; no += changed), then lookup is done once per pair and taxa.push_back replays the run. that removes the largest remaining mispredict but changes the taxa fill loop, so do it only after (a) is landed and proven.

## 7. test harness: stream-compare tool (new file mmcmp.cc, builds against mmscanner.cc and mmbulk.cc)

```
for each input sequence s (each fastq record's sequence line, plus the synthetic cases below):
  old: MinimizerScanner sc(35,31,mask,true,toggle,1); sc.LoadSequence(s);
       while ((p = sc.NextMinimizer())) { vo.push_back({*p, sc.is_ambiguous()}); }
  new: BulkState st = init; while (produced = ScanBulk(st, s, n, mins, amb, CHUNK)) append;
  compare lengths, then every (value, amb) pair exactly; also compare with CHUNK in {1, 7, 64, 4096} to test the resume logic;
  count mismatches, print the first 5 with index, s window of 80 chars around it, then exit nonzero.
```
parameters tested: the real db's (k, l, spaced_seed_mask, toggle) read from hash.k2d options (copy the three values printed by the classify binary, or hard-code from the 8 GB db options), plus a second set k=35 l=31 mask 0 toggle default, plus (k=31, l=15) to prove the general formulas (amb = run < k-1, w = k-l+1; the ring must then be sized w). the bulk code takes w as a template parameter with 5 specialized.
inputs: (1) all reads of pod5_*.fastq (real data, about 6.04 Gbp; 1.87M reads, runtime of the old scanner at single thread about 100 s per 1e9 bases, so run with 48 omp threads and compare per-thread, about 3 to 4 minutes); (2) edge cases generated in the tool: n = 0, 1, 30, 31, 34, 35 (exactly k), 36; all N of length 20, 35, 100; N at index 0, at k-2, k-1, k, n-1; a run of 1, 5, 30, 31, 33, 34, 35, 36 N's inside a clean read (r = 33, 34, 35 hits the off-by-one amb rule); an N exactly l chars before the end; lowercase whole read, mixed case; IUPAC (R, Y, K, M, S, W, B, D, H, V, '-', '*', '.') in each of the positions listed; homopolymers (AAAA..., TTTT...), a palindromic (reverse-complement equal) read, a read whose candidates tie (a repeated 40-mer period 4 and a period 1); random 1e5 sequences with N density 0, 0.001, 0.01, 0.1, 0.5. skip bytes >= 0x80 (old code is UB there).
end-to-end check after the stream test passes: classify output (--output file and the plain --report) byte-identical to the previous best build on 50 MB, 8 GB, 16 GB and 103 GB, as in data/ser_correct.txt.

## 8. time-only oracle, run FIRST, and the kill criterion

why not the "cheap pseudo-minimizer" oracle: a fake value changes DB hit behaviour. real minimizers hit the db at a high rate for reads from db genomes, random l-mers at the 1/3 sampling rate hit at about 1/3 of that, so the taxa, run counting and ResolveTree work all change and the wall is not comparable. [G] the distortion is large enough to flip the conclusion, so I do not trust it.

use a record/replay oracle instead (exact downstream work, zero scanner cost), about 60 lines in classify.cc under an env var:
1. K2_ORACLE=record K2_ORACLE_N=468000 (the first quarter of the reads, about 1.5 Gbp): the reader already serializes under critical(seqread), so assign a serial number there; ClassifySequence with the old scanner appends each read's (value, amb) items into a file in /dev/shm (about 14 GB; luna has the memory, the 103 GB db fits) and an offset array indexed by serial. this phase does the normal classification, its output is the reference.
2. K2_ORACLE=replay: fill() copies items from the mmap'd /dev/shm file at offset[serial] instead of calling the scanner (it still does hash, prefetch, resolve). output must be byte-identical to the record run or the plumbing is wrong.
3. time (interleaved, 5 reps each): normal vs replay on the same N reads, 8 GB db, at T = 48 and T = 16, plus the 103 GB db at T = 48. replay pays a sequential 9 B per item read from page cache, so it slightly understates the gain (conservative).
the replay wall is a hard upper bound on any scanner rewrite, including the AVX-512 one.

kill criterion [G, thresholds chosen from the numbers we have]: after the serial-section fix the wall is 5.18 s against a cpu-bound 207/48 = 4.3 s, so at T=48 the front end is still part of the wall. proceed to (a) if replay is at least 8% faster than normal at T=48 on 8 GB (that is 0.4 s) OR at least 25% faster at T=16 (a cpu-bound regime where the cpu cut of 25 to 30% must show up as wall). kill the wall justification if replay is under 4% at T=48 and under 15% at T=16; then the scanner rewrite only has the cpu-seconds story (energy, fewer cores), which is a different paper claim and not worth the 3 to 5 days. between the thresholds, do (a) only, not (c).

predicted: T=16 replay about 20 to 28% faster (wall about 4.5 x ... = cpu 207 x 0.72 / 16 vs 207/16 plus floors); T=48 5.18 s -> about 4.7 to 4.9 s if the reader floor is near 4.5 s [G]. at 103 GB the memory stalls (IPC 1.59) shrink the scanner share to about 23% so expect 5 to 9%.

## 9. build order and cost

1. oracle (half a day). 2. mmbulk.cc scalar + mmcmp.cc stream test (one day), wire into fill(), run the 4-db byte-identical end-to-end (half a day), time T = 16, 32, 48. 3. only if the oracle says the ceiling is high and (a) closes most of it, do (c) with the clean-read fast path (two days). compile with -O3, check the loop has no jcc besides the loop branch (objdump on mmbulk.o) and re-run perf stat for instructions and branch-misses per base against the targets: instructions per base 267 -> about 140 after (a) (scanner 130-150 down to 45-55), branch-misses 1.30 -> about 0.5.

## summary
1. stream contract found: one item per char from index k-1, amb = (run < k-1) with a stock off-by-one at run = 34, stale value ~0-seeded for ambiguous items; position/tie-break is unobservable so any exact 5-way min is identical.
2. the 267 instructions are a one-base-per-call out-of-line function with reloads of every member, a branchy deque and per-call bookkeeping; about 0.8 of the 1.30 mispredicts are in the scanner (pop count, expiry, empty), 0.5 in the classify dedupe branch.
3. design (a): resumable ScanBulk with state in registers, sentinel ~0 gating instead of queue clears, pair-shared 3-min window, expected 45-55 instr/base and about -25 to -30% total cpu at 8 GB.
4. design (c): AVX-512 8-lane clean-read fast path with scalar fallback for any read containing non-ACGT, about 4-5 instr/base.
5. test: exact (value, amb) stream compare vs the old class over all reads, 4 chunk sizes and a long edge-case list, then byte-identical kraken output on 4 dbs.
6. run first the record/replay oracle (not a fake minimizer, which distorts hit rates); kill the wall claim if replay gives under 4% at T=48 and under 15% at T=16.
