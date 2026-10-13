# mtp1 — kraken2 memory and database-size optimisation

Work done on the **Dell OptiPlex** (Intel i7-11700, 8 cores / 16 threads,
L1d 48 KB/core, L2 512 KB/core, L3 16 MB shared, 31 GB RAM).

**Project standard: kraken2 2.17.1 throughout. The 32-bit-cell ESKAPE database
is the benchmark baseline.** Test data is 16 nanopore FASTQ files
(`pod5_0` … `pod5_15`); most single-file results use `pod5_15` (30,378 reads,
90.55 Mbp).

---

## Start here

Three results carry the project. Read them in this order.

1. **[`reports/findings/SUBSAMPLING_FINDING.md`](reports/findings/SUBSAMPLING_FINDING.md)**
   — why a 7.6 GB database classifies the same reads **43% faster** than a 47 MB
   one. `-M` subsampling discards 89.62% of lookups before any memory access, and
   lookups run at IPC 0.218 against 1.714 for everything else.
2. **[`reports/findings/ESKAPE_DB_REPORT.md`](reports/findings/ESKAPE_DB_REPORT.md)**
   — a rebuilt 48 MB ESKAPE database, **same size as the current one**, that
   classifies **8.5 points more reads and runs 25% faster**. Also answers whether
   a read produces the same hash and key in the 50 MB and 16 GB databases.
3. **[`reports/findings/LOOKASIDE_REPORT.md`](reports/findings/LOOKASIDE_REPORT.md)**
   — whether a minimizer→taxon lookaside cache helps. It does not: best case
   −1.3%, and it needs a profile that cannot be obtained in production.

---

## Documents

### `reports/findings/` — load-bearing conclusions

| document | status | summary |
|---|---|---|
| `SUBSAMPLING_FINDING.md` | current | `-M` subsampling, not size or spaced seed, is why big databases win |
| `ESKAPE_DB_REPORT.md` | current | bigger ESKAPE database; breadth beats completeness at fixed size |
| `LOOKASIDE_REPORT.md` | current | lookaside cache measured and rejected |

### `reports/database/` — sizing and building

| document | status | summary |
|---|---|---|
| `CELLWIDTH_DB_BUILD.md` | current | build spec for 16/20/24/32-bit cell widths — **partner handoff** |
| `DB_SIZING.md` | current | every achievable database size and how to pick one |
| `ESKAPE_SIZE_LADDER.md` | current | 13 `-M` databases built and measured on the 6-genome library |
| `ESKAPE_DB_SCALING.md` | current | technical backing for `ESKAPE_DB_REPORT.md` |

### `reports/memory/` — cache, TLB, prefetch

| document | status | summary |
|---|---|---|
| `CACHE_TABLE_ANALYSIS.md` | current | can a minimizer table be pinned in L1/L2/L3? Addendum 4 has the built result |
| `PREFETCH.md` | current | software prefetch (`-B`) — overlapping DRAM latency instead of avoiding it |
| `FUTURE_UPDATE.md` | current | making the file-read path faster |

### `reports/reference/` — stable, how things work

| document | status | summary |
|---|---|---|
| `KRAKEN2_CHANGES.md` | current | what kraken2 is, and every part this project changed |
| `LOOKASIDE_TABLE_PROMPT.md` | current | self-contained spec used to implement and benchmark the lookaside table |
| `MTP1_STRUCTURE_PROPOSAL.md` | current | the analysis behind this directory layout |

### `reports/superseded/`

| document | status | why |
|---|---|---|
| `xyz.md` | **retracted** | marked retracted 2026-09-08, kept for the record only |

### Other

- **`reports/CHANGELOG.md`** — chronological log of every change, dated.
- **`deliverables/`** — midterm slides and speaking transcript.
- **`plan/`** — thesis plan and its analysis.
- **`papers/`** — background reading notes.
- **`results/`** — measurement summaries: thread sweep, cell-size sweep, lookaside sweep.
- **`archive/`** — centrifuge results (centrifuge is no longer part of the
  project), the stale-file manifest, and the abandoned `weekly/` convention.

---

## Reproduction

Source patches live in `scripts/`. Each reproduces one report's results against
stock kraken2 2.17.1; apply with `patch -p1` from the kraken2 source root.

| patch | flags it adds | reproduces |
|---|---|---|
| `kraken2_cellsize_v2.patch` | `-C 16\|20\|24\|32\|40` | `reports/database/CELLWIDTH_DB_BUILD.md` |
| `kraken2_lookaside.patch` | `-L l1\|l2\|l3`, `-F exact\|compact`, `-N 1\|2\|4\|8\|16`, `-A`, `-W`, `-Z` | `reports/memory/CACHE_TABLE_ANALYSIS.md` Addendum 4 |
| `kraken2_prefetch.patch` | `-B` | `reports/memory/PREFETCH.md` |

These three patches replace the 19 compiled `classify` binaries that used to be
tracked here (67 MB). The lookaside patch alone supersedes 18 of them, because
what were separate compile-time builds are now runtime flags.

### Two gotchas that have each produced wrong numbers

- **Always pass `-g 2`.** The `kraken2` wrapper script passes it by default; the
  raw `classify` binary defaults to `-g 0`. Omitting it inflates classification
  rates.
- **Never benchmark in sequential blocks.** Interleave A/B repetitions. The
  powersave governor's boost behaviour, and thermal drift over a long run, have
  both produced false results on this machine — once a spurious 24%.
- **`build_db` must run with `-p 1`.** Multi-threaded builds segfault here.

---

## Databases

None are in this repo — they total 30 GB. This table is the record of what
exists locally under `databases/`.

| database | hash.k2d | cells | skip rate | notes |
|---|---:|---:|---:|---|
| `standard_16gb` | 15 GB | 4.0 B | 79.25% | prebuilt NCBI download; no source library |
| `standard_8gb` | 7.6 GB | 2.0 B | 89.62% | subject of `SUBSAMPLING_FINDING.md` |
| `eskape_human_4gb` | 3.8 GB | 1.0 B | 14.96% | ESKAPE + human |
| `eskape_big` | 208 MB | 52.0 M | 0% | **175 genomes, 7 species, complete** |
| `eskape_sizes/` | 224 MB | — | various | the 13-database `-M` ladder |
| `eskape_650mb` | 142 MB | 37.0 M | 0% | |
| `eskape_32bit_spaced` | 47 MB | 12.2 M | 0% | **correct baseline for cross-database work** |
| `eskape_32bit_fork` | 47 MB | 12.2 M | 0% | cell-width series baseline; `spaced_seed_mask = 0` |
| `eskape_big_M12000000` | 48 MB | 12.0 M | 76.92% | **same size as the above, +8.5 pp, 25% faster** |
| `eskape_24bit` / `eskape_20bit` | 35 MB | 12.2 M | 0% | cell-width series |
| `eskape_16bit` | 24 MB | 12.2 M | 0% | cell-width series |
| `eskape_big_M4000000` | 16 MB | 4.0 M | 92.31% | L3-resident; **unusable above `-T 0`** |
| `eskape_cs/` | 28 MB | — | — | the original 6-genome source library |

> **Note on the baseline.** `eskape_32bit_fork` was built by calling `build_db`
> directly without `-S`, so `spaced_seed_mask = 0`, while every wrapper-built
> database uses kraken2's default 7 minimizer spaces. The same read therefore
> yields almost entirely different minimizers (**0.02% overlap**). The
> 16/20/24/32-bit series is internally consistent and its comparisons are valid,
> but it cannot be compared against any other database. Use
> `eskape_32bit_spaced` for that. See `reports/findings/ESKAPE_DB_REPORT.md` §2.3.

---

## Open items

- False-positive rates have **not** been measured on `eskape_big`,
  `eskape_big_M12000000` or `eskape_big_M4000000`. Every number in
  `ESKAPE_DB_REPORT.md` §5 is classification *rate*, not correctness.
- All `eskape_big*` results are from `pod5_15` only; the other 15 files are
  untested.
- Huge pages (`madvise(MADV_HUGEPAGE)` on the hash table) remain untested, and
  matter far more at 16 GB than at 50 MB — at 16 GB every lookup misses the TLB.
