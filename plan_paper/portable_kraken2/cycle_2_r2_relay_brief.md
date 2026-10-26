# cycle 2, round 2: relay brief (2026-10-27)

this file exists so the five agents counter the same thing in R2. cycle 2 R1 produced 21 new ids and five sets of proposed moves against the cycle-1 list. this brief merges the duplicates, lists every proposed move side by side, and names the claims R2 must check.

---

## 1. new ids after merging

| id | idea | from | type | merged with |
|---|---|---|---|---|
| M26 | AMAC-style `GetBatch`: a lookup that runs off its line prefetches the next line and yields, instead of stalling | a1 | build | absorbs M8a (M8a becomes its 0.25-day first step) |
| M27 | prefetch prologue in upstream `GetBatch` (keys 0-7 of each read are never prefetched), then pool lookups across reads | a1 | build | |
| M28 | short-read axis: cut `reads_hac.fastq` into 150 bp pieces and time S19 / RC1 / RC1 + M27a | a1 | measure | rides inside M1 |
| M30 | cold fault-ahead for a mapped table: before resolving a block, issue an async page-cache read for every distinct missing page (`posix_fadvise(WILLNEED)` per page, or helper threads that touch pages), so the device sees queue depth 8-32+ instead of 1 | a2 M30, a4 M50 | build | M50 merged here |
| M31 | input page-cache hygiene: `POSIX_FADV_DONTNEED` on parsed input ranges when table + input exceed free ram | a2 | build | |
| M32 | detached teardown: a forked worker loads and classifies; the parent returns as soon as output is closed, so the exit tax leaves the wall clock | a2 | build | |
| M33 | jetson-class storage placement: the planner says "db on emmc, nvme present: move it" | a2 | build (one line) | inside M9 |
| M40 | `final` on the table class plus one dispatch on the table type per block, so lookup calls can inline | a3 | build | |
| M41 | run-length pipeline: the scanner emits (value, length, ambiguous) runs and every later stage works per run | a3 | build | subsumes M3 on the S19 base; uses M4's `ScanRead` |
| M42 | shipped sampled profile (AutoFDO-style portable pgo) | a3 | build | rides with M21 |
| M43 | E5 with openmp variants: `OMP_WAIT_POLICY=PASSIVE`, `OMP_PLACES=cores` + `close` / `spread`, output to disk vs `/dev/null` | a3 | measure | |
| M51 | device micro-probe at startup: 32 random 4 KB reads at qd1 and at qd16 plus one 64 MB sequential read, only when the db is cold | a4 | build | inside M9 / M24 |
| M20' | M20 revised: threads = min(physical cores in the affinity mask, `cpu.max` quota) | a4 | build | replaces M20's definition |
| M53 | small-cloud-vm probe (m7i/m7g.xlarge, gp3) | a4 | measure (optional) | |
| M54 | sustained-power protocol for laptop runs (warm-up, 3 interleaved reps, clock logging) | a4 | measure (method) | |
| M60 | daemon amortization test: upstream `-D` keeps the index loaded across requests | a5 | measure | |
| M61 | M12 as a sweep over table/ram ratio (0.5, 1.5, 3, 10), capped and uncapped dbs | a5 | measure | replaces M12 |
| M62 | spill guard: RC1 workers spill output to `TMPDIR` instead of waiting, and exit 73 without it | a5 | build | ships with M20 |
| M63 | one load-included comparator run: RC1 / S19 vs Centrifuge, Centrifuger, Metabuli, with wall incl. load and peak rss | a5 | measure | |
| M64 | compressed slices inside M11's sweep (no map to fight there) | a5 | build | M13 folds here (a5); a4 disagrees |
| cpu gate | `perf annotate ClassifySequence` + `perf stat -e branch-misses` on 50MB and 8GB | a3 | measure | gates M4, M41 |

**new class proposed by a4: H5, a small cloud vm.** m7i.xlarge = 4 vcpus on 2 cores x 2 smt, 16 GiB; m7g.xlarge = 4 real arm cores; default gp3 storage at 125 MiB/s, 3,000 iops, "single-digit millisecond latency", shown as `/dev/nvme*n1` like a local nvme [external: aws docs, a4 N1-N3]. raspberry pi 5 is treated as an H3 example, not a new class.

---

## 2. the moves each agent asked for (vs the cycle-1 list)

cycle-1 build list: 1 M2(+M3), 2 M20, 3 M9, 4 M4, 5 M5, 6 M8a, 7 M11, 8 M21, 9 M10, 10 M13.

| agent | build moves | measure moves |
|---|---|---|
| a1 | M27 in at 3; M8a → M26 at 6; M13 out | none (M28 rides inside M1) |
| a2 | M30 in at 4; M13 out; M10 stays (huge pages also cut the exit tax ~10x) | M1 adds an exit column; orin probe adds `lsblk` / `lspci` for an nvme |
| a3 | M4 to 3; M41 in at 4; M9 to 5; M40 at 7 | cpu gate in at 3; orin probe to 6 |
| a4 | M50 (= M30) in at 5; M10 out; M13 stays (a cold gp3 load is bandwidth-bound) | E1 adds a 2-minute qd1-vs-qd16 timing |
| a5 | no reorder; M62 joins M20; M13 folds into M11 as M64 | M60 in at 4; M61 replaces M12 at 5 |

**agreed by 4 or more:** M13 leaves the standalone top 10 (a1, a2, a5 say out; a3 already had it below the line; a4 alone keeps it). **agreed by 2:** M30/M50 enters (a2, a4); M10 drops (a4, a3's list has it below).

---

## 3. fact fixes proposed in R1 (R2: confirm or reject)

1. **FINAL summary item 8** ("only an exact out-of-core mode runs it"): wrong. `-M` runs it; Coriolis ran kraken2 `-M` on a 4 GB jetson up to a reference/ram ratio of 52 and lost 1.5x [external: Coriolis, ISMB 2023, a5 N2]. issue #971 shows the opposite extreme: a 645 GB table on 503 GB "stuck ... for days" [external: a5 N6].
2. **M11 cells**: a5 wants [UNCLEAR] until M61. a4: among our dbs only 103GB is uncapped and big.
3. **few-read wins assume one load per run.** upstream has a `-D` daemon mode and ONT runs a persistent kraken2-server [external: a5]. S19's 9.8x-15.4x and M9's warm branch apply to one-shot runs.
4. **RC1 output**: an outside tester reports classifications and reports byte-identical to 2.17.2 at 1, 4, 16 threads; a `0:0` trailing-space and `-C` header change [external: issue #1061, a5].
5. **M2's 8GB cell** is ~1.08x without S8 [arith, a5]; the 1.25x end needs the 16-file input.
6. **M9 cells** (a4): H1 uncapped ~3.4x / capped ~35x; H2 capped 40-300x / uncapped 4-14x; and on gp3-class network storage at qd1 the map can lose to the copy on an uncapped db (11-96 s vs 58 s).
7. **M20 cells** (a4): orin ~11x on classify for all three dbs with a parallel loader; H1 5.8-8x ±20% by chassis.
8. **M21 cell** (a3): orin already builds; only gcc-11 `-march=native` fails. "a tuned arm tier", not "lets orin build".
9. **H1 note** (a4): the 5800h supports dual-channel ddr4; ck's laptop is half-populated.
10. **exit tax** (a2): a 2026 lkml rfc measured 16 GB teardown 282 ms at 4 KB vs 27.7 ms with thp [external]; scaled to 111 GB, ~2 s vs ~0.2 s [arith].

---

## 4. what R2 asks of every agent (keep the file to ~1,500 words)

write `cycle_2_r2_<your slug>.md`:
1. **counters**: to every other agent's new ids and proposed moves (section 2 table). what breaks, which class it hurts, what is cheaper, does its evidence hold. at least one line per new build id.
2. **fact fixes**: confirm or reject each item in section 3, with the source.
3. **your ranking**: top 10 build and top 5 measure-first, using these ids.
4. role extras:
   - a1: data-structure check of M41 (run boundaries across ambiguous gaps), M30's page dedupe, M64
   - a2: storage check of M27/M28, M60 (what stays resident in a daemon), and the H5 storage numbers
   - a3: cpu cost of M30's syscalls (~10K `posix_fadvise` calls per block), M26's state machine, M32's fork
   - a4: H5 column for every id in your top 10, and the corrected per-class cells for the new ids
   - a5: re-derive the headline arithmetic of M27, M30/M50, M32, M41; prior-art verdict for every new id
