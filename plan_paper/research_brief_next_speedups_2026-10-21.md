# next speedups after S19 (research brief, 2026-10-21)

motivation: S19 is 1.9x to 4.8x faster than stock on luna at 1.87M reads, and 10-17x at small read counts, byte-identical in all 16 cells. every number so far is one machine (luna, warm page cache). sir's question is "what else gives a speedup that holds on any machine". this brief lists every lever that is not already built, ranks them, and says what to run first. nothing here was run; no luna or orin command was issued while writing it (the `thsweep` thread sweep is running on luna).

evidence tags: **[repo]** = from a file in this repo, **[guess]** = my estimate, **[ext]** = outside knowledge, unverified.

## 1. already done, do not redo

| stage | what | source |
|---|---|---|
| S8 | one input stream instead of one parallel region per file | `explanations/03_S08.md` |
| S9, S16 | batched, then software-pipelined, prefetch | `explanations/04_S09.md`, `11_S16.md` |
| S10 | parallel `pread` table load (capped at 32 threads) | `explanations/05_S10.md` |
| S12 | one exact reciprocal-multiply modulo per lookup | `07_S12.md` |
| S13 | `memchr` newline scan in kseq | `08_S13.md` |
| S14 | 2MB-aligned table + `MADV_HUGEPAGE` | `09_S14.md` |
| S15, S17, S18 | run-length hit counts, rolling reverse complement, ring buffer without the store-forwarding stall | `10_S15.md`, `12_S17.md`, `13_S18.md` |
| S19 | portability guards only | `14_S19.md` |
| ruled out | 4-way k-mer cache (S6, S7: real effect was pipeline, not cache), first scanner rewrite (S11, null) | `s6_s15_speedup_report_2026-09-24.md` |

## 2. the bottleneck today

the final chain at 32 threads, 1.87M reads (`s6_s15_speedup_report_2026-09-24.md`): 50MB 8.88s, 8GB 9.18s, 16GB 10.94s, 103GB 20.08s (13 to 21s because of THP variance). two facts set the floor:

- the serial fastq parse of the 12.5GB input is 3.88s on its own (S13 doc **[repo]**). it runs inside `critical(seqread)` per the report **[repo]**, so it caps how fast any number of workers can be fed.
- the scanner (minimizer extraction) is still about 25% of cpu after S18 **[repo]**.

everything below is aimed at one of: the serial parse, per-read cpu, db load, or the memory system.

## 3. full lever table

gain columns: NUMA = luna-class big memory, ARM = orin (12 cores, eMMC, 64GB), 1ch = single-channel laptop. h = hours to build and verify. "identical" = how output equality is checked (the repo's `check.sh` byte compare, plus `modes.sh` for 12 modes).

### db load

| lever | NUMA | ARM | 1ch | h | risk | identical | dbs |
|---|---|---|---|---|---|---|---|
| adopt `-M` (mmap, no load) as the baseline and compare S19 with and without it | big on short runs and low-RAM boxes **[guess]**; old -M result was 12-14x on 103GB vs stock, measured before S10 and S14 **[repo: associativity brief]** | likely helps (loads only touched pages from eMMC) **[guess]** | helps when db is near RAM size **[guess]** | 1 (no code) | -M random faults on cold eMMC may be slow | `check.sh` | all, most on 103GB |
| `MAP_POPULATE` / `madvise(WILLNEED)` with `-M` | small | maybe large on eMMC (sequential readahead) | small | 2 | extra RAM pressure | `check.sh` | 16GB, 103GB |
| overlap table load with opening/parsing the first input batch | up to ~3s of 103GB, per report "still on the table" **[repo]** | small | small | 4 | thread-pool restructure | `check.sh` | 103GB mostly |
| NUMA interleave or per-socket table copy (`numactl --interleave=all`, or two copies) | unknown; sweep pending **[guess]** | none (one node) | none | 1 to 8 | copy doubles RAM; 103GB x2 = 206GB fits luna | `check.sh` | 16GB, 103GB, luna only |
| hugetlb reserved pages instead of THP (needs root) | removes the 13s-to-21s THP variance on 103GB **[repo]** | unknown kernel support **[guess]** | n/a | 3 | needs `vm.nr_hugepages`, root | `check.sh` | 103GB |
| compress `hash.k2d` (zstd) to cut cold-read bytes | none warm | only if eMMC bound; hash cells are near random so ratio is poor **[guess]** | none | 6 | decode cost, new file format | `check.sh` | none worth it |
| thread cap in S10 loader (32) lifted to core count | measured by `thsweep` | cap not binding (12 cores) | not binding | 0.5 | none | `check.sh` | 103GB |

### classification

| lever | NUMA | ARM | 1ch | h | risk | identical | dbs |
|---|---|---|---|---|---|---|---|
| per-machine build: `-O3`, `-march=native`, LTO, PGO | 5-15% cpu typical for PGO on branchy code **[ext]** | same, built on orin | same | 2 | -march=native binary not portable; floating point not involved so output should not change | `check.sh` + `modes.sh` | all |
| replace `unordered_map` hit counts with a small flat array (it was 5-6% of cycles before S15 **[repo]**) | 2-4% cpu **[guess]** | larger share, fewer cores **[guess]** | larger share **[guess]** | 4 | `ResolveTree` tie-break depends on insertion order (S15 note **[repo]**), array must keep first-occurrence order | `check.sh` + `modes.sh` | all |
| tune prefetch batch size and distance per machine (batch 16-64 today) | small | possibly large, A78 has a different memory-level parallelism **[guess]** | prefetch helps most when dram-latency bound, 1ch is bandwidth bound **[guess]** | 2 | none | `check.sh` | 16GB, 103GB |
| SIMD minimizer scanner (AVX2 / NEON), the 25% | 10-20% cpu **[guess]** | NEON version needed, 4x less core count so share is higher | same | 20+ | highest effort, S11 shows scanner tweaks can null out | `check.sh` + `modes.sh` | all, most small dbs |
| shrink key/value bits (cell width) | fewer cache lines and bytes to load | big on eMMC load | big on bandwidth | thesis 2 | **not byte-identical**: raises false positives (`kraken2opti_report.tex`) | accuracy table, not `check.sh` | all |
| double hashing (flag flip + db rebuild) | speed effect unknown, main value is accuracy **[repo: associativity brief]** | same | same | 4 | gcd(step, capacity) risk **[repo]** | not identical (db differs) | rebuilt dbs |
| sort or bucket reads by minimizer to raise locality | maybe 10% on 103GB **[guess]** | unknown | unknown | 15 | changes processing order, needs reorder at the end | `check.sh` sorted by id | 103GB |
| revive the k-mer cache | ruled out (S6/S7 ablation) | | | | | | |

### pipeline

| lever | NUMA | ARM | 1ch | h | risk | identical | dbs |
|---|---|---|---|---|---|---|---|
| parallelize the fastq parse: split the mapped input into big blocks at record boundaries, each worker parses its own block | the serial 3.88s is 44% of S19's 8.88s on 50MB **[repo]**; likely 15-30% wall on 50MB/8GB **[guess]** | smaller (12 cores are compute bound) | small | 10 | record-boundary bugs, multi-line fastq/fasta, `--paired`, gz input | `check.sh` + `modes.sh` | 50MB, 8GB, 16GB |
| output formatting and writing | untested: benchmarks used `--output /dev/null` so real output cost is unmeasured **[repo: bench.sh]** | disk is eMMC, so maybe visible | visible if disk slow | 1 to measure | none | `check.sh` | all |
| thread and NUMA pinning (`--cpunodebind=0` with 48 threads vs 96 threads across sockets) | sweep pending; report: 64 threads helped 103GB 12.9s to 10.8s **[repo]** | not applicable | not applicable | 1 | none | `check.sh` | 103GB |
| default thread count (stock default is 1) | users get the S19 speedup only if they pass `--threads` | | | 0.5 | none | n/a | n/a |
| early exit | `--quick` exists, but changes classification | | | | not identical | | |

## 4. ranking and first experiment for each

ranked by: holds on every machine, output byte-identical, cheap, and measurable in one session.

**1. `-M` (memory-mapping) against S19, warm and cold.** zero code. the old 12-14x came from before S10 and S14 existed, so the real question is whether `-M` still wins now. it changes how the db gets into RAM, so it should matter most where RAM and disk are small (orin eMMC, laptop with an 8GB db) and for short runs on 103GB where load is ~16s of a ~20s run.
first command (after `thsweep` finishes, so they do not share the page cache): `bench.sh s19_M 3 "8GB 16GB 103GB" "kraken2-fresh-bin-s19" "-M"` against the same without `-M`, then once more after dropping caches (root, we have it on luna).

**2. per-machine compile flags: `-O3 -march=native`, then PGO.** it needs no logic change, so there is no new correctness risk, and the build is rerun on each machine. the repo never isolated compile flags (associativity brief item 4 **[repo]**) so the gain is unmeasured.
first command: read the Makefile flags used for the S19 build on luna (`grep -n 'CXXFLAGS' ~/tools/kraken2-src-s19/src/Makefile`), then rebuild with `-O3 -march=native` into a new tree `s20a` and run `modes.sh` plus the 4-db bench.

**3. parallel fastq parse.** the biggest unmeasured structural cost: 3.88s serial parse inside an 8.88s run on 50MB. this is the same kind of fix as S8 (remove a serial section), and S8 was the biggest win on small dbs.
first command: a parse-only timer. build the standalone parser test used for S13 (`scripts/s6plus/parse_test.cc`) with 1, 2, 4, 8 parse threads on the 12.5GB input, to see the ceiling before touching kraken2 itself.

**4. flat hit-count array plus per-machine prefetch tuning.** two small cpu-side changes that should show on the machines where cpu is the limit (orin, laptop), which is where S17/S18 style wins were largest.
first command: `perf record` S19 on 8GB at 8 threads and read how much `unordered_map` is left after S15 (it was 5-6% before). if it is under 2%, drop this lever.

**5. overlap db load with the first parse, plus hugetlb reserved pages for 103GB.** the first hides up to ~3s of load; the second removes the 13s-to-21s variance, so the 103GB number can be quoted as one number. both only matter for the biggest db.
first command: `grep -i hugepages /proc/meminfo` and `cat /sys/kernel/mm/transparent_hugepage/enabled` on luna (read-only), then 4 back-to-back S19 103GB runs after `sudo sysctl vm.nr_hugepages=<n>` to see if the spread closes.

not in the top 5 on purpose: cell-width and double hashing are not byte-identical and belong to thesis 2, not to "speedup with the same answer". the SIMD scanner has the highest ceiling but costs 20+ hours and S11 already showed this area can hide a stall; do it after profiling says the scanner is still above 25%.

## 5. what to show sir on wednesday (thread sweep still pending)

1. **the S10 mechanism, with the machine table.** show the three machines side by side: luna (2x 8468, 8 DIMMs at 4800 MT/s, hardware RAID SSD), orin (12 A78AE, eMMC, LPDDR5 ~205 GB/s **[ext]**), the lenovo (Ryzen 7 5800H, one DIMM, NVMe, 25.6 GB/s peak). state the prediction: parallel loader scales until the memory channels or the core count run out. the laptop should saturate at 2 to 3 threads, luna much later.
2. **the sweep, if finished, or its design if not.** `sweep103` on luna: S0 vs S10, 103GB, 1 to 192 threads, load time as wall minus kraken2's own "processed in" time. say plainly that the S10 loader is capped at 32 threads, so beyond 32 only the classify step can change.
3. **the honest caveat slide.** warm page cache everywhere (the 103GB db sits in 361GB of buff/cache), one machine measured, orin and cold-cache not tested. cold-cache run needs root on luna, which we have.
4. **the transplant result** (65.6% to 94.4% agreement, 51MB to 90MB), with the two limits named up front: no neural network, and 103GB is treated as ground truth.
5. **the next-step table**: levers 1 to 5 above, with the first command for each, so sir can pick.

what not to claim: "faster on every machine" (only luna measured), any orin or laptop speedup (predictions only), any of the guessed percentages in section 3.
