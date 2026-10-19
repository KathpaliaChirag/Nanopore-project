# Nanopore / kraken2 optimisation project

Research project: reduce kraken2's memory footprint and runtime for nanopore
metagenomic classification of ESKAPE pathogens. MTP (thesis) work, IIT Delhi.

**User:** Chirag Suthar (GitHub `Hobbbit31`). The GitHub repo
`KathpaliaChirag/Nanopore-project` is owned by **Chirag Kathpalia** (a
collaborator, a different person); Chirag Suthar is a collaborator with his own
branch **`hobbbit`**. Never attribute commits to Kathpalia. Commit identity:
`Hobbbit31 <sutharchirag1675347@gmail.com>` — matches all 50 prior commits.

---

## Standing rules

1. **kraken2 2.17.1 for all work.** The **32-bit cell ESKAPE database is the
   benchmark baseline.** Do not silently use another version or width.
2. **"Prepare a document" means write a `.md` file**, not an HTML artifact.
3. **This machine is the Dell.** Intel i7-11700, 8 cores / 16 threads, L1d
   48 KB/core, L2 512 KB/core, **L3 16 MB shared**, 31 GB RAM, powersave
   governor, no Intel CAT/RDT. Other machines in the project: laptop, Luna,
   Minerva — results are not interchangeable between them.
4. **Run long jobs one at a time.** Parallel builds and `nohup` have both failed
   here; background tasks can die at session teardown.
5. **Scratch directories get wiped.** Never leave the only copy of a result in
   `/tmp` or a scratchpad. Durable output goes in `result/<name>/`.

---

## Layout

Local tree is 57 GB; only markdown, patches and small summaries go to GitHub.

```
/home/dell/summer/
├── CLAUDE.md                  this file
├── *.md                       working copies of the reports (12 files)
├── kraken2/                   SOURCE, v2.17.1, patched. git remote = UPSTREAM
│                              DerrickWood/kraken2, HEAD detached at 7c0eb91
├── kraken2_bin/               ** THE BINARIES ACTUALLY USED ** (stock build_db)
├── kraken2_laptop/ + _bin/    second checkout, laptop work
├── kraken2_bin_fork.bak/      backup
├── databases/                 30 GB, 17 databases — see table below
├── perpod5/                   12 GB, pod5_0..pod5_15.fastq  ← the test data
├── result/                    40 experiment result sets (durable)
├── results/                   12 GB merged_pod5_profiling (NOTE: separate dir)
├── basecalling/               2.1 GB dorado fast/hac/sup reads
├── scripts/                   4 patches + 11 sweep scripts + analysis python
├── archive/                   frozen kraken2_stock 2.1.2, old 32bit DB
├── scratch_lookaside/         1.4 GB working copy (disposable)
└── scratch_probe/             prefetch working copy (disposable)
```

### GitHub mirror

Docs are mirrored to the repo under **`mtp1/`** (restructured 13 Oct 2026):

```
mtp1/
├── README.md                  index: start-here, status table, DB inventory
├── reports/
│   ├── findings/              load-bearing conclusions
│   ├── database/              sizing and building
│   ├── memory/                cache, TLB, prefetch
│   ├── reference/             stable how-it-works
│   ├── superseded/            retracted, kept for record
│   └── CHANGELOG.md
├── deliverables/  plan/  papers/  scripts/  results/
└── archive/                   centrifuge (tool removed), retired conventions
```

`mtp1/README.md` is the authoritative index — read it before adding a report.
Sibling `kraken2opti/` holds earlier Dorado/basecalling work and has its own
`index.md`.

`.gitignore` is **deny-all** (`*`) with `!*.md` plus named exceptions. Any new
non-markdown file needs an explicit exception, with a comment naming the report
it backs. Commit messages use the **`mtp1:`** prefix.

---

## ⚠ Gotchas that have each produced a wrong result

- **Always pass `-g 2` to raw `classify`.** The `kraken2` wrapper passes it by
  default (`kraken2:141`); the binary defaults to `-g 0`. Omitting it inflates
  classification rates and looks like a regression.
- **Never benchmark in sequential blocks — interleave A/B repetitions.** The
  powersave governor's boost behaviour once produced a spurious 24% result, and
  thermal drift over a ~5 minute run shifts every number by 10-20%. Check
  `/sys/class/thermal/thermal_zone*/temp` if results look odd; use minimum-of-N
  when the box is heat-soaked.
- **`build_db` requires `-p 1`.** Multi-threaded builds segfault here.
- **Verify multi-threaded output at `-p 1`.** Known upstream kraken2 bug on this
  box: `-p 16` can produce wrong output and still exit 0.
- **16-bit-cell `classify` segfaults sporadically** under threads; sweeps retry.
- **`perf stat` totals include the database load phase.** For a 15 GB database
  that dominates everything. Measure a load-only run on a tiny FASTQ and
  subtract, or use kraken2's own "processed in Xs" line.
- **`eskape_32bit_fork` has `spaced_seed_mask = 0`** (built via raw `build_db`
  with no `-S`) while every wrapper-built database uses kraken2's default 7
  spaces. Same read → **0.02% minimizer overlap**. The 16/20/24/32-bit series is
  internally consistent, but for any cross-database comparison use
  **`eskape_32bit_spaced`**.
- **Never evaluate an `-M` database at `-T 0` only.** Skipped minimizers still
  inflate the confidence denominator (`classify.cc:743`), so heavy subsampling
  collapses under a threshold: 92.3% skip costs 33 points at `-T 0.05`, where
  0-79% skip costs only 3-6.
- **`make` will not rebuild on a flag change.** `rm classify.o` first, or every
  variant comes out md5-identical.

---

## Databases

| database | hash.k2d | cells | skip | notes |
|---|---:|---:|---:|---|
| `standard_16gb` | 15 GB | 4.0 B | 79.25% | prebuilt download, **no source library** |
| `standard_8gb` | 7.6 GB | 2.0 B | 89.62% | subject of SUBSAMPLING_FINDING |
| `eskape_human_4gb` | 3.8 GB | 1.0 B | 14.96% | |
| `eskape_big` | 208 MB | 52.0 M | 0% | 175 genomes, 7 species, complete |
| `eskape_sizes/` | 224 MB | — | various | the 13-database `-M` ladder |
| `eskape_650mb` | 142 MB | 37.0 M | 0% | |
| `eskape_32bit_spaced` | 47 MB | 12.2 M | 0% | **cross-database baseline** |
| `eskape_32bit_fork` | 47 MB | 12.2 M | 0% | cell-width baseline, seed mask 0 |
| `eskape_big_M12000000` | 48 MB | 12.0 M | 76.9% | **best drop-in: +9.28 pp over 16 files** |
| `eskape_24bit`/`20bit` | 35 MB | 12.2 M | 0% | cell-width series |
| `eskape_16bit` | 24 MB | 12.2 M | 0% | cell-width series |
| `eskape_big_M4000000` | 16 MB | 4.0 M | 92.3% | L3-resident, unusable above `-T 0` |
| `eskape_cs/` | 28 MB | — | — | original 6-genome library (**no A. baumannii**) |
| `eskape_big/library/` | 786 MB | — | — | 175-genome library + NCBI taxdump |

`skip` = fraction of minimizers never looked up, from
`min_acceptable_hash_value` in `opts.k2d` = `1 - value/2^64`.

---

## Commands

```bash
# classify (always -g 2; -T 0.05 for a realistic threshold)
D=databases/eskape_big_M12000000
./kraken2_bin/classify -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d \
    -p 16 -g 2 -T 0.05 perpod5/pod5_15.fastq

# build (spaced seed = kraken2 default; omit -S only for the fork series)
cat library/*.fna | ./kraken2_bin/build_db \
    -H hash.k2d -t taxo.k2d -o opts.k2d -n taxonomy -m seqid2taxid.map \
    -c 52000000 -k 35 -l 31 -p 1 \
    -S 1111111111111111101010101010101        # add -M <cells> to subsample

# full benchmark
sudo bash run_experiment.sh                    # warm-cache by design
```

The spaced-seed template is `"1"x(l-2*spaces) + "01"x spaces` with `spaces = 7`
(`kraken2-build:347`), expanding to `4611686018212639539`.

### Patches (`scripts/`, apply with `patch -p1` from the kraken2 root)

| patch | adds | backs |
|---|---|---|
| `kraken2_cellsize_v2.patch` | `-C 16\|20\|24\|32\|40` | CELLWIDTH_DB_BUILD.md |
| `kraken2_lookaside.patch` | `-L l1\|l2\|l3 -F exact\|compact -N 1..16 -A -W -Z` | CACHE_TABLE_ANALYSIS.md Add. 4 |
| `kraken2_prefetch.patch` | `-B` | PREFETCH.md |
| `kraken2_fork_cellsize.patch` | — | **STALE, do not use** |

---

## Where things stand

**Established.** `-M` subsampling, not database size, is why big databases win
(lookups run at IPC 0.218 vs 1.714 for everything else). A 48 MB database built
from 175 genomes beats the 6-genome one of the same size by **9.28 points**
(83.73% -> 93.01%, all 16 files, ordering holds in every file, spread 0.55 pp)
while storing *fewer* minimizers — breadth beats completeness at fixed memory.
False positives measured: +173,398 reads classified against 948 spurious
*A. baumannii* calls, **183:1**, caused by forced assignment in a 7-species
database, not hash collisions (*E. faecium* FPs fell 48 -> 1). See
`MEETING_UPDATE_2026-10-20.md`.
`CompactHashTable::Get` is 43.4% of cycles; DRAM stalls 27%; MLP is 1.26 of ~12.

**Rejected by measurement.** Minimizer→taxon lookaside cache (best −1.3%, needs
an unobtainable profile). L1/L2 cache pinning. Replacing the hash table — at
0.96 DRAM accesses per lookup it is already at the floor.

**Open.**
- **Still no labelled ground truth.** All numbers are classification *rate*;
  correctness is bounded only by inter-database agreement, with
  `standard_16gb` (97.60%) used as arbiter. Ask whether the sample is a known
  mock community.
- **No decoy set** — 948 spurious *A. baumannii* calls remain. Fix: add human
  GRCh38 (already on disk in `eskape_human_4gb`) + a *Pseudomonas* phage.
- ***Enterobacter* is the wrong species.** 9.3 M minimizers labelled
  *E. cloacae* (550), but the sample's dominant *Enterobacter* is
  *E. hormaechei* (83 reads vs 36) with 668 complete assemblies to cloacae's 82
  and **0 in the database**. Five lines in the `SPECIES` map.
- **Runtimes indicative only** — the 16-file sweep was sequential on a
  heat-soaking box. The ~13% speedup needs an interleaved A/B when cool.
- `-T 0.05` cliff measured on `pod5_15` only.
- Huge pages (`madvise(MADV_HUGEPAGE)` on the hash table) untested. At 16 GB
  every lookup misses the TLB (1.00 page walk per lookup, 3.9 M 4 KB pages vs a
  2,048-entry STLB); in 2 MB pages it would be 7,630 pages.
- Set-associative lookaside timing unfinished — the box was heat-soaked.
