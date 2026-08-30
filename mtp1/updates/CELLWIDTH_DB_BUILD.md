# Narrow-Cell Kraken2 Databases — Build & Reproduction Spec

How the 24-, 20- and 16-bit compact-hash databases were built on top of kraken2 2.17.1,
and everything needed to rebuild them byte-for-byte on another machine.

| | |
|---|---|
| **Base** | kraken2 2.17.1 @ commit `7c0eb918d600555e7dc384259ffca32dbd1e7602` |
| **Library** | 6 ESKAPE genomes, 17 sequences, 28,061,107 bp |
| **Written** | 2026-08-26 |

Stock kraken2 stores each compact-hash cell in 32 bits. This project adds narrower cells —
24, 20 and 16 bits — to trade fingerprint precision for a smaller index, and measures what
that costs in classification accuracy. The narrow widths do not exist upstream; they come
from a local patch that must be applied before anything here will build.

---

## 1. What you need first

Three inputs, none of which ship with kraken2.

| Input | What it is | Where it comes from |
|---|---|---|
| `kraken2 @ 7c0eb91` | Upstream source, version 2.17.1 | Clone the fork repo, check out that commit |
| `kraken2_cellsize_v2.patch` | Adds 16/20/24-bit cells to build, classify and dump | `scripts/kraken2_cellsize_v2.patch` — send with this doc |
| `eskape_cs/` | 6 FASTAs + seqid2taxid.map + NCBI taxonomy | Copy from `databases/eskape_cs/`, or rebuild per Step 3 |

> **⚠ READ THIS BEFORE YOU CLONE**
>
> The cell-width changes were **never committed**. On the original machine they live as
> uncommitted working-tree edits to six files on top of `7c0eb91`. The older
> `scripts/kraken2_fork_cellsize.patch` is **stale** — it predates the 20-bit cell and omits
> the `build_db.h` change that makes 20-bit work at all. Use
> `scripts/kraken2_cellsize_v2.patch`, not that file.

---

## 2. Build procedure

### Step 1 — Get the source at the right commit

The patch applies to one specific commit. A newer checkout will conflict in `compact_hash.h`.

```bash
git clone <kraken2-fork-repo> kraken2
cd kraken2
git checkout 7c0eb918d600555e7dc384259ffca32dbd1e7602
cat VERSION   # 2.17.1
```

### Step 2 — Apply the cell-width patch

Six files change: `build_db.cc`, `build_db.h`, `classify.cc`, `compact_hash.h`,
`dump_table.cc`, `kv_store.h` — 152 insertions.

```bash
git apply --check kraken2_cellsize_v2.patch   # dry run first
git apply kraken2_cellsize_v2.patch
make -C src -j4
./src/build_db 2>&1 | grep -- -C
# -C INT  CHT cell size: 16, 20, 24, 32 or 40 (default: 32)
```

If that `-C` line lists 20, the patch took. The build uses
`g++ -std=c++11 -O3 -fPIC -DLINEAR_PROBING` straight from the stock Makefile — no flag
changes needed.

### Step 3 — Assemble the reference library

Six complete ESKAPE genomes, 17 sequences (chromosomes plus plasmids), 28,061,107 bp total.
Small on purpose: the whole sweep rebuilds in minutes, so cell width is the only variable
that moves.

| Accession | Organism | taxid | seqs |
|---|---|---:|---:|
| GCF_000005845.2 | *Escherichia coli* K-12 MG1655 | 511145 | 1 |
| GCF_000006765.1 | *Pseudomonas aeruginosa* PAO1 | 208964 | 1 |
| GCF_000013425.1 | *Staphylococcus aureus* NCTC 8325 | 93061 | 1 |
| GCF_000025565.1 | *Klebsiella pneumoniae* HS11286 | 1125630 | 7 |
| GCF_000174395.2 | *Enterococcus faecium* DO | 333849 | 4 |
| GCF_000240185.1 | *Enterobacter cloacae* ATCC 13047 | 716541 | 3 |

Layout on disk, exactly as `build_db` expects it:

```
eskape_cs/
├── library/          # the 6 *.fna files, unmodified from NCBI
├── seqid2taxid.map   # 17 lines: "NC_000913.3<TAB>511145"
└── taxonomy/         # NCBI names.dmp + nodes.dmp (~500 MB)
```

Only `names.dmp` and `nodes.dmp` are read. You do **not** need the 51 GB `accession2taxid`
file — the `seqid2taxid.map` replaces it, which is why the map is written by hand rather
than looked up.

### Step 4 — Build one database per cell width

Identical parameters across all four; only `-C` changes. `build_db` reads the concatenated
library from stdin.

```bash
for W in 32 24 20 16; do
  OUT=databases/eskape_${W}bit; mkdir -p "$OUT"
  cat eskape_cs/library/*.fna | ./src/build_db \
      -H "$OUT/hash.k2d" -t "$OUT/taxo.k2d" -o "$OUT/opts.k2d" \
      -n eskape_cs/taxonomy -m eskape_cs/seqid2taxid.map \
      -c 12200000 -k 35 -l 31 -p 1 -C $W \
      2>&1 | tee "$OUT/build.log"
done
```

| Flag | Value | Why |
|---|---|---|
| `-c` | `12200000` | Hash capacity in cells. Fixed across widths so file size varies only by bytes-per-cell. |
| `-k` | `35` | k-mer length. |
| `-l` | `31` | Minimizer length. |
| `-p` | `1` | Single-threaded. **Required** — see gotchas. |
| `-C` | `32/24/20/16` | Cell width. The patched flag. |
| `-r` | *(omitted)* | Taxid bits. Left at default, so it is derived from the library — 6 bits here. |

> **⚠ `-p 1` is not optional.** Multi-threaded `build_db` segfaults on our hardware at
> `-p 16`, and has hung at 100% CPU on larger libraries. Single-threaded also makes the
> build deterministic, which is what lets you verify against the MD5s below.

> **Taxid bits are derived, not fixed.** With `-r` omitted, kraken2 computes the taxid bits
> from the number of distinct taxa in *your* library. Six genomes gives 6 bits, so key bits
> are `width − 6`: 26 at 32-bit, 10 at 16-bit. Change the library and that split changes —
> which silently changes every hash. Confirm your build log says
> `CHT created with 6 bits reserved for taxid` before comparing checksums.

### Step 5 — Record occupied cells

`build_db` does not report table occupancy, and it is the cleanest build-time signal of
collision pressure. Pull it out with `dump_table`:

```bash
for W in 32 24 20 16; do
  OUT=databases/eskape_${W}bit
  ./src/dump_table -H "$OUT/hash.k2d" -t "$OUT/taxo.k2d" -o "$OUT/opts.k2d" -s \
    | awk -F': ' '/Table size/{print $2}' > "$OUT/occupied_cells.txt"
done
```

---

## 3. Verify your build

The build is deterministic at `-p 1`, so a correct rebuild reproduces these exactly.

| Database | hash.k2d bytes | bytes/cell | occupied cells | MD5 of hash.k2d |
|---|---:|---:|---:|---|
| eskape_32bit | 48,800,032 | 4 | 8,903,388 | `b3ba6e934934e0f3f4258068d303a0c2` |
| eskape_24bit | 36,600,032 | 3 | 8,903,335 | `cc89ad98b89170fd2bdd06e16196a176` |
| **eskape_20bit** | **36,600,032** | **3** | 8,902,669 | `b22a9dcc1ed8f79f0c9a2ac267fde2ec` |
| eskape_16bit | 24,400,032 | 2 | 8,891,740 | `8031d922444f725c34f9d3116ecbf5b3` |

File size is `12,200,000 × bytes-per-cell + 32`; the 32 bytes are the header holding
capacity, size, key bits and value bits. Each build log should read `Using <W>-bit cells`
and `Completed processing of 17 sequences, 28061107 bp`.

### Why 20-bit is the same size as 24-bit

That row looks wrong and is not. A 20-bit cell has no byte-aligned home, so it is stored in
the same packed 3-byte word as the 24-bit cell, with the top 4 physical bits left zero. The
file is therefore identical in size to the 24-bit database while carrying four fewer
fingerprint bits.

```
20-bit cell in 3 bytes (24 physical bits):

  [ 14 key bits ][ 6 taxid bits ][ 4 unused ]
   <------------ 20 logical ---->
   <-------------- 24 physical ------------>
```

Two consequences worth knowing. Reading the header is the only way to tell a 20- from a
24-bit database — `GetKVStoreCellType()` dispatches on `key_bits + value_bits`, not on file
size. And 20-bit buys no disk savings over 24-bit; it exists purely to place a data point
between 16 and 24 on the accuracy curve.

> **The subtle part of the patch.** Stock `build_db.h` derived cell width from
> `sizeof(Cell) * 8`. That is correct for 16/24/32/40 but wrong for 20, where the struct is
> 3 bytes and would report 24. The patch changes it to read `opts.cht_cell_size` — the
> logical width — instead. **Without this one-line change the 20-bit build silently produces
> a 24-bit database.**

---

## 4. What we measured

Included so you know what a correct build should score. Full sweep: 16 pod5 files,
1,872,777 reads.

| Database | -T 0 | Δ vs 32-bit | -T 0.05 | Δ vs 32-bit |
|---|---:|---:|---:|---:|
| eskape_32bit | 83.76% | — | 79.83% | — |
| eskape_24bit | 83.78% | +0.02 | 79.83% | +0.00 |
| eskape_16bit | 90.96% | +7.20 | 80.10% | +0.27 |

> **⚠ The +7.20 at 16-bit is false positives, not sensitivity.**
>
> With only 10 key bits, distinct minimizers collide and reads match taxa that are not in
> them. The tell is Gram-positive assignments in a Gram-negative-dominated sample, summed
> over all 16 files at `-T 0`:
>
> | Taxon | 32-bit | 24-bit | 16-bit |
> |---|---:|---:|---:|
> | *S. aureus* (1280) | 12 | 31 | **7,071** |
> | *E. faecium* (1352) | 48 | 102 | **10,014** |
>
> A confidence threshold of 0.05 collapses the effect almost entirely (+0.27), which is
> consistent with collision-driven noise rather than real signal. Report the 16-bit number
> as precision loss.

24-bit, by contrast, tracks the 32-bit baseline to within 0.02 points while cutting the
index by a quarter — that is the result the sweep exists to establish.

### Single-file smoke test

Quickest check that a fresh build is sane. On `pod5_15.fastq` (180 MB, 30,377 reads),
`--threads 16 --confidence 0`:

| Database | classified | % |
|---|---:|---:|
| eskape_32bit | 25,331 | 83.39 |
| eskape_24bit | 25,340 | 83.42 |
| eskape_20bit | 25,587 | 84.23 |
| eskape_16bit | 27,622 | 90.93 |

---

## 5. Gotchas

**16-bit classify segfaults sporadically.** Multi-threaded classification against the
16-bit database crashes at random — not on every run, and not on the same file twice. Wrap
it in a retry loop; `scripts/classify_pod5_cellsize.sh` retries up to 4 times and logs
give-ups to `FAILURES.txt`. The 20-, 24- and 32-bit paths have never crashed for us.

**Do not mix builders.** Stock kraken2 2.1.2 has no `-C` flag and cannot build anything
narrower than 32-bit. Build all four with the patched 2.17.1 so the only difference between
databases is cell width. We verified this is safe: a 32-bit database built with patched
2.17.1 is byte-identical to one built with stock 2.1.2 — same MD5, same 8,903,388 occupied
cells, and identical classification reports.

**Rebuild all four together.** Because taxid bits are derived from the library, a database
built against a different `eskape_cs` is not comparable to one built against yours, even at
the same width. If you change the library, rebuild the whole set.

---

## 6. File map

Where each piece lives on the original machine.

```
summer/
├── kraken2/                        # patched source, 2.17.1 @ 7c0eb91
│   └── src/                        # 6 modified files, uncommitted
├── kraken2_bin/                    # installed patched build — use this
├── scripts/
│   ├── kraken2_cellsize_v2.patch   # complete patch (send this)
│   ├── kraken2_fork_cellsize.patch # STALE — no 20-bit, do not use
│   ├── build_cellsize_dbs.sh       # build driver
│   ├── classify_pod5_cellsize.sh   # classify sweep, with retry
│   └── analyze_cellsize.py         # roll-up tables
├── databases/
│   ├── eskape_cs/                  # library + taxonomy + seqid2taxid.map
│   └── eskape_{32bit_fork,24bit,20bit,16bit}/
├── perpod5/                        # pod5_0..15.fastq, the read set
└── result/cellsize_sweep/          # reports, outputs, logs
```

**To hand this off:** send three things — this document,
`scripts/kraken2_cellsize_v2.patch`, and the `databases/eskape_cs/` directory. The taxonomy
dumps inside it are ~500 MB; everything else is small. The read set (`perpod5/`, 12 GB) is
only needed to reproduce the accuracy numbers, not the databases.

---

*Built from the working tree at `/home/dell/summer` on 2026-08-26 · kraken2 2.17.1 (fork,
self-versioned; upstream base `7c0eb91`) · all figures measured, not estimated*
