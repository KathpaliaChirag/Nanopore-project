# cycle 3 round 5, implementer I2: scalar bulk scanner (ScanBulk), built and stream-verified, not benchmarked

## what was built

all work is in a new luna directory, ~/e1/impl_scanner (copy of ~/e1/src_final). nothing else was touched and no kraken2 or classify run was started.

1. src/mmbulk.h (new, header only, also saved as code/mmbulk.h). `ScanBulk(state, params, seq, n, mins, amb, max_items)` is a resumable scalar scanner. state lives in locals during a call (lm, rc, run, the four previous window slots c1..c4, the pair mins p1/p2, stale, next index) and is written back at the end, so a chunk of any size can stop and resume. per base it does one table lookup, a keep mask instead of any branch on N, a saturating run counter, canonical min of lm and rc, the spaced mask and toggle, a sentinel (all ones) when the l-mer is not complete (so no queue clears), and a 5-slot window min with pair sharing (3 mins per base). it emits one item per char from index k-1 with amb = (run < k-1), which copies the stock off-by-one at run = 34. stale value (last emitted real minimizer, ~0 at start) is emitted for incomplete l-mers, exactly like last_minimizer_.
2. `BulkSupported(dna, revcom_version, k, l)` is true only for dna, revcom_version != 0, k > l, k - l == 4 (the 5-slot window) and 2 <= l <= 31. anything else, plus translated search, takes the old NextMinimizer path unchanged. bytes >= 0x80 map to ambiguous in the bulk code (the old code is undefined behaviour there; the harness does not generate them).
3. src/classify.cc, in ClassifySequence: `#include "mmbulk.h"`, an env switch `K2_BULK=1` (read once, default off), and per frame state (BulkState, BulkParams, a cursor into per-thread thread_local heap vectors of 4096 values and 4096 flags). when bulk is on, scanner.LoadSequence is skipped and fill() takes items from the chunk buffer, calling ScanBulk for the next chunk when the cursor drains. everything after the item is obtained (the E6 dedupe, hash, prefetch, the capped-db skip, the PfSlot contents, the whole resolve loop) is untouched. the batch is only short when the sequence is truly exhausted (the refill happens inside the fill loop), so the `exhausted = (n < la_batch)` logic is unchanged and chunk boundaries cannot end a batch early.
4. src/Makefile: classify.o now also depends on mmbulk.h. built with `cd ~/e1/impl_scanner/src && nice make -j4 classify` (clean, only the old warnings).
5. runnable dir ~/e1/bin_scanner (copy of kraken2-fresh-bin-s19, new classify, kraken2 wrapper path rewritten, grep confirms the edit).

## harness result

~/e1/impl_scanner/mmcmp.cc (saved as code/mmcmp.cc). links src/mmscanner.o plus mmbulk.h. it reads the real IndexOptions from standard_8gb/opts.k2d (64 bytes: k=35 l=31 spaced=3ffffffff3333333 toggle=e37e28c4271b5a2d dna=1 revcom=1; note the real db has a non-zero spaced seed mask, so that path is tested on real parameters). for every sequence it runs the old class (LoadSequence plus NextMinimizer loop, recording value and is_ambiguous) and ScanBulk with chunk sizes 1, 7, 64, 4096, and compares length, then every (value, amb) pair exactly, including the stale values on ambiguous items.

inputs: the first 20000 reads of pod5_0.fastq (chunk 1 on every 10th read only, for speed), plus 100,818 synthetic sequences: lengths 0,1,2,30..41,70,71,100,200 as clean, all N, all A, all T; N runs of length 1..40 at offsets 0,1,20,33,34,35,36,50,100; clean runs of exactly 1..40 chars between Ns (covers r = 33/34/35); N at index 0,1,29..39,n-1 for n = 35,36,40,80; an N exactly l chars before the end; all-lowercase and mixed case; IUPAC letters, '-', '*', '.', '?', 'X', tab, NUL at positions 0,10,33,34,35,50,99; homopolymers, palindromes, period-1/2/4/8 tie reads; 100,000 random reads at N density 0, 0.001, 0.01, 0.1, 0.5 (half with IUPAC and lowercase mixed in); 30 long reads of 20 to 50 kb to exercise chunk joins.

parameter sets (all with k - l == 4): real db; k35 l31 mask 0 default toggle; k35 l31 mask 0 toggle 0; k35 l31 with a different spaced mask; k34 l30; k19 l15.

result (nice -n 10, 33 s single thread): 2,791,632 sequence comparisons, 1,893,992,308 items compared, 0 length mismatches, 0 value mismatches, 0 amb mismatches. each of the six sets individually reports 0 mismatches (about 314 million items per set).

## benchmark commands for you (not run by me)

same input, same db, interleave the two settings, and diff the outputs first:

```
cd ~/e1
K2_BULK=0 ./bin_scanner/kraken2 --db <db> --threads 48 --output /tmp/o_bulk0.txt <reads.fastq> > /tmp/r0.txt
K2_BULK=1 ./bin_scanner/kraken2 --db <db> --threads 48 --output /tmp/o_bulk1.txt <reads.fastq> > /tmp/r1.txt
cmp /tmp/o_bulk0.txt /tmp/o_bulk1.txt && cmp /tmp/r0.txt /tmp/r1.txt
```
use the same extra flags (-M, --report, memory options) as your validate_matrix.sh runs, and time with `/usr/bin/time -v` plus `perf stat -e instructions,branch-misses,cycles` to check instructions per base against the 267 baseline (target about 140) and branch-misses per base (target about 0.5). does the kraken2 wrapper pass the environment through to classify? it normally does (plain exec of the child), so `K2_BULK=1 ./bin_scanner/kraken2 ...` should reach classify; confirm with one tiny 50 MB run first by checking instructions differ.

## known risks

1. only the scanner is proven exact; the end-to-end byte-identical check on the real dbs is not done. run the cmp above on 50 MB and 8 GB before timing anything.
2. window is hard-coded to 5 slots (k - l == 4); other k, l silently use the old path (correct, just no speedup).
3. the compiler may turn the ternaries (min, valid, keep) into branches; I did not inspect the disassembly (no objdump pass yet). if instructions per base do not fall, check `objdump -d classify` around ScanBulk for jcc inside the loop. the function is noinline so it is easy to find.
4. per-frame overhead in ClassifySequence: a static-guard check for the env flag and thread_local vector access once per read (not per base); negligible, but the thread_local vectors are heap allocated on first use per thread (deliberately not a static TLS array, because of the old S2 static-TLS problem).
5. the harness shares the same table construction idea as the scanner (both treat only ACGTacgt as clean), so it cannot catch a shared misunderstanding of the alphabet beyond what the old class does; but the comparison is against the real old class, so this is covered for all ASCII bytes tested. bytes >= 0x80 are excluded.
6. mmcmp builds against the old mmscanner.o from the same tree (-O3 build); the old scanner is the oracle, unchanged.
7. the classify-side mispredict (pf.min != last_minimizer, about 0.35 per base) is untouched, as in the design.

## summary
1. built ScanBulk (scalar, resumable, sentinel gating, 5-slot pair-shared window) in mmbulk.h and wired it into fill() behind K2_BULK (default off) with exact fallback.
2. classify compiles; runnable dir ~/e1/bin_scanner is ready, nothing was run on real data or by kraken2.
3. mmcmp compared 1.89 billion items over 20000 real reads plus 100,818 edge and random sequences, chunk sizes 1/7/64/4096, six (k, l, mask, toggle) sets including the real db.
4. mismatches: 0 length, 0 value, 0 amb.
5. files: code/impl_scanner.diff, code/mmcmp.cc, code/mmbulk.h, this note; luna: ~/e1/impl_scanner, ~/e1/bin_scanner.
6. not yet done: end-to-end byte-identical classify output and the timing, which are yours to run with the commands above.

harness reports zero mismatches: yes.
