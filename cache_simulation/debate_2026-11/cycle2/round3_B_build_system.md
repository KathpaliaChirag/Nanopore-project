# cycle 2 round 3, agent B: build and system-level speedups (read-only pass, 2026-11-23)

scope: no algorithm change, output must stay byte-identical. only read-only ssh was used (cat, grep, ls, lscpu, numactl --hardware). nothing was run or built. every gain below is an estimate with its reasoning, not a measurement.

## facts gathered (tagged)

[M] = read on luna today, [R] = from repo docs, [W] = web search.

- [M] cpu: 2x Xeon Platinum 8468, 48 cores per socket, 2 threads per core, 192 hardware threads. smt siblings are cpu N and N+96. numa node 0 holds the even cpu ids, node 1 the odd ones. numa distance 10 local, 21 remote.
- [M] free memory right now: node 0 has 63 GB, node 1 has 71 GB. the 103GB db needs about 111 GB of anonymous memory, so it cannot sit on one node today. it will straddle both, whatever we do.
- [M] numa_balancing = 1. thp enabled = madvise, thp defrag = madvise (direct compaction on fault for madvised regions), khugepaged defrag = 1. no hugetlb pages reserved.
- [M] kptr_restrict = 1, so perf cannot resolve kernel symbols for us. the two big unresolved kernel addresses in p32_summary.txt (0xffffffffb3247ff8 at 11.4% to 14.2%, 0xffffffffb3ba2be7 at 9.7% to 10.6%, both 103GB T=32) stay anonymous.
- [M] gcc 11.4.0 on luna. no clang, no llvm-bolt, no jemalloc. libtcmalloc_minimal.so.4 and libtcmalloc.so.4 ARE installed (usable with LD_PRELOAD, no root).
- [M] s19 Makefile: `-std=c++11 -O3 -fPIC` plus `-DLINEAR_PROBING` on line 4. so -O3 is already on. no -march, no LTO, no PGO. changing CXXFLAGS on the make command line drops -DLINEAR_PROBING and breaks output (plan_paper/next_steps_plan_2026-10-21.md line 33), so edit the Makefile.
- [M] compact_hash.cc: the non-mmap load does posix_memalign at 2 MB alignment, madvise(MADV_HUGEPAGE), then parallel pread in 64 MB chunks into that buffer, with the thread count capped at min(omp_get_max_threads(), 32). so every byte is: read from page cache, copied by the kernel into freshly zeroed huge pages. the kernel zeroes 111 GB and then overwrites it.
- [M] no numa calls, no thread pinning anywhere in the source (grep for numa, setaffinity, OMP_ found only omp_set_num_threads and locks). placement is whatever the scheduler and first touch decide.
- [R] 10-read run on 103GB is 3.0 s, so load plus exit is about 3 s of a 12.2 s wall, classification about 9.2 s (round1_A_ledger item 14). the 103GB wall also swings 13 to 21 s with thp state (s6_s15 report line 61).
- [R] user cpu at T=32: 50MB 234 s, 8GB 215 s, 16GB 240 s, 103GB 268 s after the hll guard (round6). 234 s / 32 = 7.3 s against a 7.9 s wall, so at 50MB the 32 threads are busy almost the whole wall. that says the run is cpu-bound, not waiting on a serial reader, unless the reader is the pace-setter and workers spin in OpenMP barriers (user time would include spin). this is the first thing the thread sweep settles.
- [R] T=32 profile 8GB: NextMinimizer 38.6%, ClassifySequence 21.6% (ostringstream and AddHitlistString inlined there), PrefetchIndex 11.8%, kernel under 4%. malloc does not appear in the top 9 symbols at any size. so the allocator is not a visible cost in the p32 profile.
- [R] 103GB T=32: kernel is about 11.4 + 9.7 + 0.7 = about 22% of samples. the 8GB profile has under 4% kernel, so the kernel share is db-size dependent, which points at load and teardown, not read() of fastq or output.
- [W] web search found no Kraken2, Centrifuge or BWA specific PGO or LTO number. the nearest hit (arxiv 2507.16649, a survey of PGO) gives general ranges only. no hash-table specific numactl --interleave benchmark was found either. the numa literature found says remote access is about 30% slower on recent hardware and that interleave helps when access is uniformly random. so every gain below is an inference from profile shape, not a cited result.

## where the kernel 22% most likely comes from

the evidence points at the db load, not at classification:
1. it scales with db size (under 4% at 8GB, 22% at 103GB) while read count is fixed.
2. the load writes 111 GB of zero pages (clear_huge_page) and then copies 111 GB from page cache (copy_user). two full passes over 111 GB. at 3 s total this is about 70 GB/s of memory traffic, plausible for two sockets, so the load is bandwidth and zeroing bound, not syscall bound.
3. the two top kernel addresses are both near 10% to 14%, the shape you expect from one zeroing function and one copy function. unproven, since kptr_restrict hides names.
4. the fastq side cannot be it: input is plain fastq (no gzip in seqreader, memchr newline scan from S13), about a few GB, read once.
5. exit teardown of a 2 MB-page table is only about 55k pages, so it should be cheap once thp took. with 4 KB fallback pages it is 27M pages and costs seconds. that is the likely cause of the 13 to 21 s variance, and it is what the diagnostic in lever 5 checks.

this is a hypothesis. the cheapest test is lever 5's vmstat diff.

## the levers, each with gain, test, kill

### L1. thread count: 64 and 96 instead of 32

- why: at 50MB and 8GB the db fits in cache or near it, so the work is core bound (NextMinimizer, ClassifySequence). 32 of 96 physical cores are busy. the box has 192 hardware threads. if the pipeline (one reader, workers) scales, 64 threads should cut classification wall close to half. at 103GB more threads also means more prefetches in flight (32 threads x batch of 16 now), which helps a latency-bound run.
- expected gain: 1.3x to 1.8x on 50MB and 8GB if the serial reader is not the wall, 1.1x to 1.4x at 103GB (load part is capped at 32 loader threads and does not shrink). if the serial parse is the wall, about 0%. an old note says the 50MB thread sweep tells these apart: flat from 16 to 192 means serial wall.
- test (about 20 minutes, no build): existing ~/threads_sweep.sh style run on 8GB and 103GB with --threads 32, 48, 64, 96, 128, 3 reps each, plain --report, output to /dev/null, byte-compare against T=32 output (cmp, no sort). also record user cpu: if wall barely moves but user cpu rises, the extra threads are spinning.
- kill: under 5% wall gain from 32 to 64 on both 8GB and 103GB. caveat: sharing the box with about 65 other users, so run reps interleaved and report spread. also note that every earlier comparison (stock vs S19) was at T=32. a T=64 win is a deployment recommendation, not a new patch, and stock should be re-run at T=64 for a fair comparison.
- smt: 96 threads or fewer can sit one per physical core, 128 forces siblings to pair. watch for the knee at 96 (siblings share L1, L2, and the load/store ports; the scanner is integer and branchy so smt may still give 15% to 25% extra, not 2x).

### L2. numa placement: numactl for 8GB and 16GB, interleave for 103GB

- why: nothing pins threads or memory. at 8GB and 16GB the table fits on one node (node 0 has 63 GB free). today the 32 loader threads run on both sockets, so first touch scatters the table across both nodes by chunk, and the unpinned classify threads land on both sockets too. about half of the random lookups are then remote at distance 21 vs 10 (2.1x idle latency on paper, 30% in the web source for newer hardware). the prefetching hides latency but not the cross-socket link bandwidth or the load on the other socket's memory controller.
- expected gain: `numactl --cpunodebind=0 --membind=0` for 8GB and 16GB, 3% to 10% (remote fraction roughly 50% to about 0%, times the exposed memory share of runtime, about 12% lookup share at 8GB plus the scanner running on local cache). but it halves the usable threads to 96 hw threads and one L3 (105 MB), which is fine at T=32.
- for 103GB: the table cannot fit on one node, so try `numactl --interleave=all`. expected 0% to 6%. interleave balances controllers but forces 50% remote. it also makes page placement deterministic, which may remove run to run swings, and it may stop numa_balancing from migrating pages of the table (balancing hinting faults inflate minflt on a 111 GB table, per the old plan). this part is a guess, not verified for interleave policy.
- test (under 30 minutes): three arms on 8GB, 3 interleaved reps each: default, `--cpunodebind=0 --membind=0`, `--interleave=all`. then the same default vs interleave on 103GB. add `numastat -p <pid>` once mid-run to see the node split. note membind to node 0 with 63 GB free fails the 111 GB case by design (do not run it there). byte compare the outputs.
- kill: under 2% wall on 8GB for the membind arm, and under 3% on 103GB for interleave.
- risk: numactl --membind on a shared box can push other users' memory, ask nobody for root, no root needed.

### L3. PGO and LTO on gcc 11 (the E3 build never ran)

- why: NextMinimizer is 19% to 39% of samples and is called per k-mer across a translation unit boundary (mmscanner.cc to classify.cc), so without LTO it is a real call every time, and its branches (is the next base valid, is the window min replaced, ambiguous base) are data dependent and well suited to profile-guided layout. -O3 is already on, so remaining gain is cross-file inlining and branch layout.
- expected gain: LTO 1% to 4%, PGO 5% to 12% on the cpu-bound cells (50MB, 8GB, 16GB, and the scanner part at 103GB), about 3% to 6% at 103GB where the memory stall and load do not move. no kraken-specific published number exists (web search), so 5% to 12% is the typical range for branchy c++ and should be treated as a prior, not a promise.
- test (about 45 minutes): copy ~/tools/kraken2-src-s19 to a new tree, edit the Makefile line 3 in place to add `-flto=auto -ffp-contract=off` (keep -DLINEAR_PROBING). for PGO: build with `-fprofile-generate -fprofile-update=atomic` (atomic because of 32 threads), run 105k reads on 8GB once, rebuild with `-fprofile-use -fprofile-correction`, install as s21. do `-march=native` as its own variant (s21a) only, since AVX is unlikely to matter for integer 2-bit code (glibc memchr already runs avx512 per the S19 profile).
- must check: byte compare on all 16 db x read cells and the modes.sh check from plan_paper. -ffp-contract=off protects the --confidence double math. profile data must come from a representative run, but train on 8GB and also test on 103GB to see if the profile generalises. a binary trained on one db and tested on another is the honest test.
- kill: under 2% wall on 8GB and 50MB for LTO+PGO combined at 1.87M reads, or any byte mismatch. portability: PGO and -march=native binaries are per machine, say so in the paper. orion is arm64 and needs its own profile.

### L4. allocator and openmp environment, env-only (no rebuild)

- tcmalloc: `LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4`. per-read ostringstream buffers, Sequence strings and vectors all hit malloc. but malloc does not show in the p32 top 9, so the ceiling is small.
- expected gain: 0% to 2%. glibc already uses a per-thread arena, so lock contention is low. ostringstream xsputn and AddHitlistString are an inline cost of about 1% to 2% that an allocator does not touch.
- openmp: `OMP_PROC_BIND=spread OMP_PLACES=cores` (one thread per physical core, spread over both sockets), and `OMP_WAIT_POLICY=passive` or `GOMP_SPINCOUNT` tuning (is the reader feeding workers, do workers burn cpu in barriers). expected 0% to 5%. the upside is stopping the scheduler from pairing two workers on one core's smt siblings while 96 cores sit idle, and keeping each worker on one core so its L2 stays warm. with 65 other users the scheduler already does some of this, so the gain is uncertain.
- do NOT combine with L2 membind at the same time: test one environment change per arm.
- test (about 15 minutes): arms default, tcmalloc, proc_bind+places, both, 3 reps each on 8GB and 103GB. check user cpu as well as wall.
- kill: under 2% on both sizes. drop tcmalloc first, since it adds a dependency to the paper's artifact for little gain.

### L5. load path and kernel share (diagnose first, then maybe 2 small edits)

- diagnostic (10 minutes, read-only plus one run): before and after one 103GB run, `grep -E "thp_fault_alloc|thp_fault_fallback|compact_stall|compact_fail|pgfault|numa_pte_updates|numa_hint_faults|numa_pages_migrated" /proc/vmstat` and diff. if thp_fault_fallback is large, the run fell back to 4 KB pages (that is the 13 to 21 s variance, and the kernel share is teardown and 27M faults). if compact_stall is large, direct compaction on fault is stalling the loader (defrag=madvise). if numa_pages_migrated is large, balancing is moving pages of the table under us. run it on one fast run and one slow run.
- edit A (cheap): the loader cap `if (nthr > 32) nthr = 32` could go to 64 or 96. expected 0.3 to 1 s off a 3 s load at 103GB (2% to 8% wall) if the load is not already at the zeroing bandwidth limit. test: change one line and time `processed in` versus total wall on the 10-read run, 4 reps each.
- edit B: fault the table in with madvise(MADV_POPULATE_WRITE) (kernel 6.8 supports it) from all loader threads before the pread, so zeroing and compaction happen in a parallel, well-spread pass. expected 0% to 3%, maybe only helps variance. low confidence.
- not recommended: -M mmap on s19 (ext4 file pages on 6.8 have no large folios, so the table loses 2 MB pages and takes 27M faults; the plan already flags this). MAP_POPULATE on the file map has the same problem.
- fastq input: plain fastq, memchr line scan, one reader. no change needed unless the thread sweep (L1) shows a serial wall, in which case a second reader is an algorithm-level change and out of scope for this axis.
- output formatting (ostringstream, AddHitlistString, xsputn about 1% to 2%): any fix is a code change (snprintf into a reused buffer) and the ceiling is 2%. skip.
- kill: if thp_fault_fallback is near zero and compact_stall is flat, the variance is not thp and edit B is dead. if the loader already runs at bandwidth, edit A is dead.

## other items, rejected or low value

- clang: not installed on luna, no root to install. a user-space clang download is possible but PGO with gcc already covers most of what clang would bring.
- BOLT: not installed, needs perf LBR (sapphire rapids has it) and llvm-bolt. possible gain 2% to 5% after PGO, at a high setup cost. only after L3 if L3 pays.
- static linking, -fno-plt, jemalloc: all under 1% for a binary that spends its time in two hot loops and the memory system. skip.
- hugetlb reserved pages: removes the thp variance, needs root (vm.nr_hugepages). not available. say so in the paper's limitations.
- -O2 vs -O3: -O3 is already on. only a regression check if PGO changes the picture.

## ranking by (expected gain x ease)

| rank | lever | gain | ease | why this rank |
|---|---|---|---|---|
| 1 | L1 thread sweep 64/96 | 10% to 80% (or 0%) | 5, no build | largest possible gain, 20 minutes, also settles whether a serial reader is the wall |
| 2 | L2 numactl membind (8/16GB) and interleave (103GB) | 3% to 10% | 5, no build | no code, a command prefix, byte-identical by construction |
| 3 | L3 LTO + PGO | 5% to 12% | 3, one 45 minute build | the only lever that attacks the 19% to 39% scanner share |
| 4 | L5 vmstat diagnostic then loader cap 32 to 64 | 2% to 8% at 103GB, variance fix | 4 | a 10 minute diagnostic explains the 22% kernel share and the 13 to 21 s swing |
| 5 | L4 OMP_PROC_BIND/PLACES and tcmalloc | 0% to 5% | 5, env only | cheap but small and uncertain, malloc is not in the profile |

order of execution: L1 first (it sets the thread count every other test should use), then L2 and L4 as env arms on the winning thread count, then L5 diagnostic, then L3 build.

## cautions for whoever runs these

- compare against stock S19 at the same T, interleaved reps, and report spread. luna is shared with about 65 other users.
- T=32 results in the repo (1.64x from the hll guard and so on) must stay labelled T=32. a different T changes the baseline, not only the patch.
- cmp every output, no sort. for the plain --report variants, the known report order change from the hll guard applies, so compare the per-read output file, not the report.
- the cycle 2 oracle result already told us any bound beats a build: measure the ceiling before building. here the ceilings are cheap: L1, L2, L4 need no build at all.

## summary

1. best lever: T=64/96 thread sweep, no build, up to 1.3x to 1.8x on cpu-bound cells (kill under 5%), also reveals a serial-reader wall.
2. numactl membind (8/16GB) and interleave (103GB): 3% to 10%, a command prefix only, since nothing in the code pins threads or memory and the table is 63+71 GB free across nodes.
3. LTO+PGO on gcc 11 (-O3 already on, tcmalloc installed, clang and bolt absent): 5% to 12% estimated on the scanner, no kraken-specific published figure found.
4. the 22% kernel share at 103GB is most likely load (zeroing plus copy of 111 GB) and teardown, not fastq or output; /proc/vmstat thp and compaction counters before and after a run will confirm.
5. rejected: clang, BOLT, static link, jemalloc, -M mmap on s19, ostringstream rewrite, hugetlb (no root); tcmalloc and OMP env are small (0% to 5%).
6. every gain here is an inference from the profile shape and luna's topology, no measurement was taken and web search found no direct evidence for PGO or NUMA on this class of tool.
