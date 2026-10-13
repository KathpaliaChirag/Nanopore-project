# `mtp1/` restructure proposal

Analysis of branch `hobbbit` of `KathpaliaChirag/Nanopore-project` and a proposed
layout for the Dell PC work. **Nothing has been changed.** Date: 13 Oct 2026.

---

## 1. What is on the branch now

```
Nanopore-project/  (hobbbit)                 1,009 tracked files, 91 MB
├── .claude/                                     1
├── .gitattributes, .gitignore
├── kraken2opti/                                57   Dorado / basecalling / knowledge base
│   ├── reports/            13 .md                   (has index.md — good convention)
│   ├── results/            23
│   ├── backups/            11                       claude memory + settings
│   ├── matrix_mul/          5                       png/svg
│   └── index.md, report.md, summer_report1.md, knowledge_base.md, daily_summary.md
└── mtp1/                                      949   kraken2 optimisation, this PC
    ├── reports/             8 .md  220 KB
    │   └── key_findings/    1      SUBSAMPLING_FINDING.md
    ├── results/           915      3.7 MB
    │   ├── centrifuge_pod5/  914   raw 864, class 32, reports 16, 2 summaries
    │   └── lookaside_sweep/    1   REPORT.md
    ├── scratch_lookaside/bin/ 19   **67 MB of compiled binaries**
    ├── scripts/             1      kraken2_prefetch.patch
    ├── papers/              1      kache_hash.md
    ├── stale/               1      to_be_erased_2026-08-30.txt
    ├── weekly/week2/        2
    └── thesis_plan.md, thesis_plan_analysis.md
```

## 2. Problems, in order of how much they cost

### 2.1 67 MB of binaries are 74% of the whole repo

`mtp1/scratch_lookaside/bin/` holds 19 compiled `classify` variants. The
`.gitignore` comment says they are "rebuildable from
`mtp1/scripts/kraken2_prefetch.patch`, kept as-is on request".

Three reasons to drop them:

- **18 of the 19 are now obsolete.** `classify_comp_L1/L2/L3`,
  `classify_exact_L1/L2/L3` and their `_s_` stats twins were compile-time
  variants. They have been replaced by a single binary with runtime flags
  (`-L l1|l2|l3`, `-F exact|compact`, `-N 1|2|4|8|16`) in
  `scripts/kraken2_lookaside.patch`. One patch now reproduces all 18.
- **Binaries are opaque to git.** No diffs, no blame, no review.
- They make every `git clone` 4x heavier than it needs to be.

**Caveat worth knowing:** deleting them from `HEAD` does **not** shrink an
existing clone, because git history keeps every blob forever. Getting the 67 MB
back out requires rewriting history (`git filter-repo`) and a force-push, which
breaks anyone else's clone. **Recommendation: stop adding binaries now, delete
them from `HEAD` for tidiness, and only consider a history rewrite if clone size
actually becomes a problem.**

### 2.2 914 of 949 files belong to a tool no longer in the project

`mtp1/results/centrifuge_pod5/` is **96% of `mtp1`'s file count** (864 raw perf
captures + 32 class files + 16 reports). Centrifuge was removed from the project
— the local tree has no `centrifuge/` directory and the README is kraken2-only.

The data is only 3.7 MB, so this is a *navigation* problem, not a size problem:
any file listing, search, or `git log --stat` is swamped by it.
**Recommendation: move to `mtp1/archive/`, do not delete** — it is real measured
data and the report that cites it is still valid history.

### 2.3 `mtp1` has no index, while `kraken2opti` does

`kraken2opti/index.md` opens with *"Master overview of all files in this memory
repo. Update this every time a new major topic is pushed."* That is exactly the
right convention and `mtp1` does not follow it. A reader landing on `mtp1/`
cannot tell which of the 8 reports is current, which is superseded, or where to
start.

### 2.4 `reports/` is flat, with no status and no theme

Eight documents sit side by side spanning three unrelated themes (database
sizing, memory optimisation, reference) with no marker for what is current. One
of them, `xyz.md` locally, is explicitly **RETRACTED** and would be
indistinguishable from live work once added.

### 2.5 Documents are isolated — zero cross-links

`grep` finds **no relative links between any two `mtp1` markdown files**. Each
document restates its own context, and findings that supersede each other do not
say so. This is how `ESKAPE_DB_SCALING.md` came to re-derive a result that
`SUBSAMPLING_FINDING.md` already established.

### 2.6 Smaller things

- `weekly/` contains only `week2/` — a convention started and abandoned.
- `stale/` holds a single file; too thin to justify a directory.
- `results/lookaside_sweep/REPORT.md` is ALL-CAPS where siblings are not.
- No document records **which machine** produced it, though the project spans
  Dell, laptop, Luna and Minerva. `kraken2opti` encodes it in filenames
  (`accuracydrift_dell_optiplex.md`) — inconsistently.
- **6 local documents were never pushed** and 2 are out of sync, with no
  mechanism that would reveal this.

---

## 3. Proposed layout

Grouped by **theme**, with status made explicit. Themes follow the project's
actual spine: how kraken2 works -> how databases are sized -> how memory
behaviour was optimised.

```
mtp1/
├── README.md                          ← NEW. index, status table, start-here
├── CHANGELOG.md                         chronological log, stays at top level
│
├── reports/
│   ├── findings/                      ← load-bearing conclusions
│   │   ├── SUBSAMPLING_FINDING.md       why 8 GB beats 47 MB
│   │   ├── ESKAPE_DB_REPORT.md          NEW. bigger ESKAPE DB
│   │   └── LOOKASIDE_REPORT.md          does a lookaside cache work (no)
│   ├── database/                      ← theme: size and build
│   │   ├── CELLWIDTH_DB_BUILD.md        partner handoff spec
│   │   ├── DB_SIZING.md                 NEW to repo
│   │   ├── ESKAPE_SIZE_LADDER.md        NEW to repo. 13-database -M ladder
│   │   └── ESKAPE_DB_SCALING.md         NEW. technical backing for the above
│   ├── memory/                        ← theme: cache, TLB, prefetch
│   │   ├── CACHE_TABLE_ANALYSIS.md
│   │   ├── PREFETCH.md
│   │   └── FUTURE_UPDATE.md             NEW to repo. faster file-read path
│   ├── reference/                     ← stable, how things work
│   │   ├── KRAKEN2_CHANGES.md
│   │   └── LOOKASIDE_TABLE_PROMPT.md
│   └── superseded/                    ← kept for the record, clearly separated
│       └── xyz.md                       NEW to repo, marked RETRACTED
│
├── deliverables/                      ← things shown to other people
│   ├── MIDTERM_SLIDES.md                NEW to repo
│   ├── TRANSCRIPT_midterm.md            NEW to repo
│   └── midterm_presentation.pdf         NEW to repo (needs a .gitignore line)
│
├── plan/
│   ├── thesis_plan.md
│   └── thesis_plan_analysis.md
│
├── scripts/
│   ├── kraken2_cellsize_v2.patch        NEW to repo. cell-width restore point
│   ├── kraken2_lookaside.patch          NEW. replaces 18 binaries
│   └── kraken2_prefetch.patch
│
├── papers/
│   └── kache_hash.md
│
├── results/
│   ├── lookaside_sweep/report.md        renamed from REPORT.md
│   ├── perf_threadsweep/                NEW to repo. 18 summaries from result/
│   └── cellsize_sweep/                  NEW to repo
│
└── archive/
    ├── centrifuge_pod5/                 moved from results/; tool removed
    ├── to_be_erased_2026-08-30.txt      moved from stale/
    └── weekly/week2/                    moved; convention abandoned
```

### 3.1 A header convention for every report

Four lines at the top of each document, solving §2.4, §2.5 and §2.6 at once:

```markdown
# <Title>

**Status:** current | superseded by [X](../path/X.md) | retracted
**Machine:** Dell i7-11700 | laptop | Luna | Minerva
**Date:** 2026-10-13
**Related:** [SUBSAMPLING_FINDING.md](../findings/SUBSAMPLING_FINDING.md)
```

### 3.2 What `README.md` should contain

1. One paragraph: what `mtp1` is, which machine, which kraken2 version (2.17.1,
   32-bit cell baseline).
2. **Start here** — the 3 findings worth reading first.
3. A status table: every document, its theme, its status, one-line summary.
4. The database inventory — 17 databases exist locally and none are in the repo;
   the table is the only record of what they are.
5. Reproduction pointers: which patch reproduces which report.

---

## 4. Effect

| | before | after |
|---|---:|---:|
| tracked files in `mtp1` | 949 | 949 (914 moved to `archive/`) |
| files above `archive/` | 949 | **35** |
| repo size at `HEAD` | 91 MB | **24 MB** |
| documents with a status marker | 0 | all |
| cross-links between documents | 0 | explicit |
| unpushed local documents | 6 | 0 |
| binaries tracked | 19 | 0 |
| patches tracked | 1 | 3 |

The big win is the middle row: **35 files you navigate instead of 949.**

---

## 5. Order of work, when we continue

1. Write `mtp1/README.md` from the inventory above — highest value, zero risk.
2. Reconcile `ESKAPE_DB_SCALING.md` §7.1 against `SUBSAMPLING_FINDING.md` so the
   duplicate finding becomes a cross-reference. **Do this before committing the
   new documents.**
3. Create the new directories and `git mv` the 8 existing reports. History is
   preserved by `git mv`, and nothing links to them, so nothing breaks.
4. Add the 6 unpushed documents and sync `CHANGELOG.md` (+731 lines) and
   `KRAKEN2_CHANGES.md` (+14 lines).
5. Add the two patches, with `.gitignore` exceptions in the existing commented
   style.
6. `git rm` the 19 binaries, noting in the commit that
   `kraken2_lookaside.patch` reproduces them.
7. Move `centrifuge_pod5/`, `stale/`, `weekly/` into `archive/`.

Suggested commits, matching the existing `mtp1:` prefix convention:

```
mtp1: add README index with document status table
mtp1: cross-reference ESKAPE scaling against SUBSAMPLING_FINDING
mtp1: group reports into findings/database/memory/reference
mtp1: add ESKAPE database scaling report and backing analysis
mtp1: sync backlog docs — DB_SIZING, SIZE_LADDER, FUTURE_UPDATE, midterm set
mtp1: add cellsize and lookaside patches, drop 19 rebuildable binaries
mtp1: archive centrifuge results and abandoned weekly/ convention
```

---

## 6. Open questions

1. **`xyz.md`** is RETRACTED — add under `superseded/`, or leave out entirely?
2. **The 67 MB binaries** — delete from `HEAD` only (safe), or rewrite history
   (recovers the space, breaks existing clones)?
3. **`midterm_presentation.pdf`** (3.7 MB) — currently no PDF is tracked at all.
   Add it, or keep deliverables markdown-only?
4. **`kraken2opti/` vs `mtp1/`** — is `kraken2opti` earlier work that should also
   move under a machine or phase label, or does it stay as a sibling?
5. **Should `result/` summaries come across?** 18 markdown summaries under the
   local `result/` are not in the repo but are the evidence behind the
   thread-sweep and cell-size figures.
