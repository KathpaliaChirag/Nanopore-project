# cycle 3 round 1, agent C: classify-side code audit (read-only)

source read: ~/chirag_K/tools/kraken2-src-s19/src (classify.cc, seqreader.h, kseq.h, taxonomy.cc) and the diff against ~/e1/src_dedup/src. tags: [R] read in code, [M] measured number from cycle2 data, [E] my estimate, [U] unverified.

## 1. per-read work in ClassifySequence after the scan

the 21.6% self time is mostly per minimizer work, not per read work. gcc inlined these into ClassifySequence [R]: the `fill` lambda (MurmurHash3 of every minimizer, a 32 byte PfSlot store, then a call into PrefetchIndex which is its own symbol at 11.8%), the resolve loop (last_minimizer compare, S15 run merge, branches), `taxa.push_back`, ResolveTree, the koss output and AddHitlistString. NextMinimizer (38.6%) and PrefetchIndex are separate symbols, so they are not in the 21.6%.

step by step for one read:
- `taxa.clear()` and `hit_counts.clear()`. `taxa` is a thread local vector<taxid_t>, 4 bytes per minimizer including repeats and misses. capacity survives across reads, so push_back is a store plus a capacity check, no malloc after warm up. [R]
- `hit_counts` is std::unordered_map<taxid_t,uint64_t> (kraken2_data.h:30). clear() keeps the bucket array but frees every node, so each distinct hit taxon costs one node malloc and free per read. S15 run merging cut operator[] calls from one per minimizer to one per run of equal taxa, so it is now a handful per read (zero for a read with no hits). this is the only per read heap use inside ClassifySequence itself. [R]
- ResolveTree is a double loop over hit_counts (n squared) calling IsAAncestorOfB. IsAAncestorOfB is O(depth): it walks b up through nodes_[b].parent_id until b <= a. it is not precomputed. nodes_ is the whole taxonomy, so each step is a dependent load, cold for rare taxa. a read with 0 taxa costs nothing, with 1 to 3 taxa well under a microsecond. then `hit_counts[max_taxon]` is one more hash lookup. the confidence climb loop only runs when the confidence threshold is above 0. [R]
- output line. `koss` is one ostringstream per thread per block, reset with str("") per block, so it is not reallocated per read. per read it does: `<<` of "C\t" or "U\t", the header, the taxid and seq.size() (both through locale num_put, the slow iostream path), then AddHitlistString, which walks all of `taxa` once and emits `ext_code << ":" << count << " "` per run (3 stream inserts per run). cost scales with the number of runs, which is not measured. [R][U]
- per block: `kraken_oss.str()` copies the block output into a temporary, then `out_data.kraken_str.assign(...)` copies it again. 2 memcpys of about 100 to 300 bytes per read. small. [R]
- stock kraken2 quirk, found in the loop in ProcessFiles: for every read the code does `if (call) { sprintf(...); seq1->header += buffer; c1_oss << seq1->to_string(); } else { u1_oss << seq1->to_string(); }` with no check that -C or -U was given. so each read pays a sprintf (classified only), a header append, a to_string that rebuilds the whole record (header, comment, seq, quals appended into str_representation), and a `<<` copy into c1_oss or u1_oss. both streams then get copied again by str() and assign() into out_data, and thrown away at output time because classified_output1 and unclassified_output1 are nullptr. cost per read is about 3 to 4 copies of the full record, so for long reads it is real memory bandwidth, plus realloc doubling of c1_oss/u1_oss across the 3 MiB block. this fits memmove at 2.2%. [R][M] caveat: [U] confirm the benchmark command has no -C/-U.

perf accounting [M, p32_summary 8GB T=32]: ClassifySequence 21.6%, memmove 2.2%, xsputn 1%, _int_malloc 0.8%. visible string, stream and allocator cost is about 4%. the other roughly 18 to 20 points of ClassifySequence self time is the per minimizer loop: hash, slot stores, data dependent branches (hit/miss alternation mispredicts), push_back. at 103GB ClassifySequence falls to 14% but GetAt rises to 8% and unresolved kernel addresses to about 25%, so some of its cycles there are stalls on loads the prefetch did not cover. [E]

## 2. parallel structure and serialisation at 48 threads

[R] one `#pragma omp parallel` region, every thread runs the same loop. there is no dedicated reader thread. each thread takes `critical(seqread)`, calls `reader1.LoadBlock(3 MiB of bases)` into its own seqs_ vector, releases the lock, classifies the block, then publishes output. reading is therefore serial, one thread at a time, while the other 47 compute or wait at that critical.

work inside the lock per block:
- kseq_read for every record. kseq uses a 16384 byte buffer (kseq.h:225), so a 3 MiB FASTQ block (about 6 MiB of file with quals) is about 370 read() syscalls under the lock. [R]
- copy_from_kseq assigns header, comment, seq, quals into the thread's Sequence, then `seq.seq.shrink_to_fit()`, which reallocates to exact size (malloc, copy, free) whenever the old capacity was larger. about one malloc/free pair per read inside the lock plus a second copy of the sequence. [R]
- block size is counted in bases, not reads: about 2000 reads for 1.5 kb reads, about 20000 for 150 bp reads.

serial time estimate [E]: parse plus copy at 1 to 2 GB/s of file bytes is 3 to 6 ms per block. compute per block: user cpu 215 to 245 s for 1.87M reads at T48 [M]. if the dataset is about 3 Gbp (about 1000 blocks) that is about 220 ms of compute per block, so the lock saturates near 220/4 = 55 threads, the same order as 48. [U] this depends on total bases, which I did not verify. measure bases and block count first.

output [R]: after classify a thread pushes its block into a priority_queue under the short `critical(output_queue)`, then loops: if the top block id equals next_output_block_id it takes `output_lock`, pops, writes to the ofstream outside the critical, and continues while the next block is ready. this is opportunistic, at most one writer at a time, and other threads keep computing. output is small (under about 0.5 GB for 1.87M reads), so the write is cheap unless the disk is slow. `critical(output_stats)` runs `isatty` once per block, trivial. with -r, `critical(update_taxon_counters)` merges a map per block, small.

tail [E]: no balancing below block granularity, so the last block per thread ends unevenly. about 0.1 to 0.3 s of a 7 s run, 1.5 to 4%. blocks are big, so the tail is larger than it would be with smaller blocks.

parallel efficiency [M] = user cpu / (wall x threads), mean of 3 reps, from cycle2/data/stack.csv:

| db | stock T32 | stock T48 | hll T48 | dedup T48 |
|---|---|---|---|---|
| 50MB | 0.93 | 0.81 | 0.76 | 0.72 |
| 8GB | 0.85 | 0.64 | 0.64 | 0.64 |
| 16GB | 0.82 | 0.68 | 0.69 | 0.69 |
| 103GB | 0.52 | 0.40 | 0.55 | 0.55 |

at T48 on the 50MB db (almost no memory stalls) 19 to 28% of thread-time is idle: 1.3 to 1.9 s of a 6.8 s run. the same db at T32 loses only 7%. the gap that grows with thread count is the signature of a serial section (reader lock, serial startup and exit, tail) rather than memory stalls. wall includes serial taxonomy and DB load and exit, so part of the gap is not classify loop idle. the split is unknown. the machine is a Xeon 8468, 2 sockets x 48 cores x 2 threads (192 hw threads), so T48 is not oversubscribed. [M lscpu]

## 3. five code level optimisations

gains are [E] fractions of cpu or wall at T48, bounded by the shares cited.

1. skip building classified/unclassified record strings when no -C/-U output exists (gate on the output pointers or opts filenames). removes sprintf, header append, to_string, 3 to 4 record copies, growth of c1_oss/u1_oss, and the block level str()/assign of those. gain 2 to 4% (memmove 2.2% plus part of the ClassifySequence and malloc shares). byte-identical risk: none for the kraken output, since those strings were discarded. the header mutation disappears, but the kraken line is written before it and never reads it again. effort 1 hour. oracle: env flag that skips the whole `if (call) ... else ...` block, 3 interleaved reps at 8GB T48, md5 of the kraken output.
2. take the reader off the critical path. (a) raise the kseq buffer from 16 KB to 1 MB (kseq.h:225, one line). (b) delete `shrink_to_fit` in copy_from_kseq. (c) later, split into raw read under the lock and parse outside, or a prefetching reader. gain: bounded by the 19 to 28% idle, realistic 3 to 8% [E], unknown until test 0. risk: none for order, block ids are assigned inside the lock; (c) must handle records straddling the block edge. effort (a)+(b) 1 hour, (c) 8 to 12 hours. oracle: time the critical section with omp_get_wtime, or replay one cached parsed block for 90% of calls and see whether wall drops.
3. replace the unordered_map hit_counts with a per thread flat array of (taxid,count) pairs, linear search, no heap. gain 0.5 to 1% (_int_malloc 0.8% total, only part of it is this). risk: iteration order changes. the result should be order independent (final max taxon is the LCA of all taxa tied at the maximum, and a strictly larger score resets it), but verify with md5. effort 2 to 3 hours. oracle: md5 plus a run that skips hit_counts.clear() node frees.
4. O(1) ancestor test: Euler tour entry/exit times (a is an ancestor of b iff tin[a] <= tin[b] < tout[a]), two uint32 arrays, about 20 MB for 2.6M nodes [U exact node count]. replaces the pointer chase through the nodes. gain 0.5 to 1.5% of cpu, larger for reads with many taxa. risk: none, same tree same relation. effort 3 to 4 hours. first: add a counter of hit_counts size and IsAAncestorOfB calls per read; if the mean is under 5 skip this item.
5. replace ostringstream line building with a per thread char buffer and a hand written itoa (also in AddHitlistString). gain 2 to 3% (xsputn 1% plus the num_put and locale work inlined into ClassifySequence). risk: byte-identical only if the format matches exactly (tab separators, single space between runs, no trailing space, newline); md5 catches drift. effort 4 to 6 hours. oracle: skip AddHitlistString for all reads and write "0:0"; the wall gain bounds the rewrite.

not recommended now: smaller blocks to cut the tail (raises lock rate), a lock free output ring (output is already cheap and off the critical path).

ranked by gain per hour: 1, then 2a+2b, then 5, 3, 4, 2c.

## time only oracle tests, in order (outputs are not byte-identical, timing only unless stated)

0. idle split, 15 minutes, env gated timer: wrap the `critical(seqread)` body with omp_get_wtime and sum, per thread, time waiting for the lock and time inside it. print at exit. if wait plus in lock time is under 3% of thread-time, item 2 is dead and the idle gap is startup or tail.
1. skip the classified/unclassified build (item 1), 8GB and 50MB, T48, 3 interleaved reps against S19. md5 of kraken output must match.
2. skip AddHitlistString (write "0:0"): bounds items 5 and part of 3.
3. return 0 from ResolveTree: bounds items 3 and 4. stats change, timing only.
4. run with `-o -` so kraken_output is nullptr: drops the output write but not the build, isolating write cost from formatting.

## 6 line summary
1. ClassifySequence's 21.6% is mostly the per minimizer loop (hash, slots, branches, push_back); visible string, stream and allocator cost is about 4% (memmove 2.2, xsputn 1, malloc 0.8).
2. found: stock code builds classified/unclassified record strings (sprintf, to_string, c1_oss/u1_oss) for every read even with no -C/-U; removing it is about 2 to 4% cpu and byte-identical, 1 hour.
3. reading is serial: every thread takes critical(seqread), parses a 3 MiB block with a 16 KB kseq buffer and a shrink_to_fit realloc per read; ordered output via priority_queue is cheap and not a bottleneck.
4. parallel efficiency at T48 is 0.64 to 0.81 (0.40 to 0.55 at 103GB) versus 0.82 to 0.93 at T32, so 19 to 36% of thread-time is idle at 48 threads; test 0 (15 min) splits reader lock, startup and tail.
5. hit_counts (unordered_map) and IsAAncestorOfB (O(depth) pointer chase) are each under about 1.5%; do them after items 1, 2a, 2b.
6. all gains are estimates bounded by the p32 shares; the stack dataset's total bases is unverified and decides whether the reader saturates near 55 threads.
