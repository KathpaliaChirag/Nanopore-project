# To-do experiments on Luna

You need everything in this one folder to run the Kraken-2 optimisation experiments on Luna. Copy the whole folder over and follow the steps below.

> **Goal:** beat the current best wall time of **4.405 s** on
> `~/results/basecalling/reads_hac.fastq` (32T, `numactl --cpunodebind=0 --membind=0`).
> Stretch target after all patches stack: **≤ 2.6 s** (≈ −40 % vs 4.405 s).

---

## Files in this folder

Here's what's in the folder and why you'd open each one.

| File | Purpose |
|---|---|
| `README.md` | this file - step-by-step instructions |
| `pending_measurements.md` | M1-M7 baseline measurements to run **first** |
| `kraken2_opt_v1.patch` | unified diff with phase-1 patches (flags + huge pages + prefetch + thread-local LRU) |
| `run_kraken2_opt_v1.sh` | one-shot script: builds base + patched binary, runs both 3x under perf, prints SUMMARY |

The companion design docs live in the repo root and are referenced from here:
`kraken2_optimisation_report.md`, `kraken2_get_optimizations.md` (v1),
`kraken2_get_optimizations_v2.md` (v2), `kraken2_execution_checklist.md`.

---

## Prerequisites on Luna

Before running anything, confirm these paths exist - they should already, from prior sessions:

```bash
test -d ~/kraken2-src/src        && echo "src ok"
test -x ~/tools/kraken2/classify && echo "classify ok"
test -f ~/data/kraken2_db/hash.k2d                  && echo "hash ok"
test -f ~/results/basecalling/reads_hac.fastq       && echo "fastq ok"
which perf numactl python3 git make g++             && echo "tools ok"
```

If any line prints nothing, install / restore that piece before continuing.

Confirm `perf_event_paranoid=1` (required for LLC counters):
```bash
cat /proc/sys/kernel/perf_event_paranoid    # must be 1 or 0
```

Confirm THP is at least `madvise`:
```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# expect: always [madvise] never   OR   [always] madvise never
# If [never]:
#   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

---

## Step 0 - Copy this folder onto Luna

From the local Windows machine (or wherever this repo lives):
```bash
# From repo root on local machine
scp -r "to do experiments on luna" student@luna.cse.iitd.ac.in:~/kraken2_opt
```

Or, on Luna, pull the latest commit:
```bash
cd ~/Nanopore-project        # wherever this repo is cloned
git pull
cp -r "to do experiments on luna" ~/kraken2_opt
chmod +x ~/kraken2_opt/run_kraken2_opt_v1.sh
```

All subsequent commands assume `cd ~/kraken2_opt`.

---

## Step 1 - Run the baseline measurements (M1-M7, ~10 min total)

Run these first, because they answer which patches actually matter and how to tune their parameters, before you touch any source code.

Open `pending_measurements.md` and run **M1 through M7 in order**. They produce
files in `~/results/profiling/pending/`. Each measurement has a short
`Decision:` block telling you what the result implies.

Look at these first, they matter most:
- **M1** - confirms 32-bit vs 40-bit cells (decides prefetch stride)
- **M4** - DRAM utilisation: are you latency-bound (expected) or bandwidth-bound?
- **M5** - minimizer reuse rate: >= 0.20 means apply the LRU cache, otherwise skip it

When done, fill in the reporting template at the bottom of
`pending_measurements.md` and **paste it back to chat** so the next patch
parameters can be tuned.

---

## Step 2 - Apply Phase-1 patches and benchmark

The patch file bundles four patches together (flags + huge pages + prefetch + thread-local
LRU cache) so you don't have to apply them one at a time. The script handles git-stash, apply, build, bench, restore.

```bash
cd ~/kraken2_opt
bash run_kraken2_opt_v1.sh
```

The script:
1. Saves a clean copy of `~/kraken2-src/src` and builds `classify.base` (master).
2. Applies `kraken2_opt_v1.patch` and builds `classify.opt1`.
3. Runs each binary 3x under `perf stat` with `numactl --cpunodebind=0 --membind=0`.
4. Prints a `SUMMARY` block at the end with wall, LLC misses, dTLB misses, IPC,
   and delta vs baseline.
5. Cleans up so your source tree is back to master.

It writes raw outputs to `~/results/profiling/opt_v1/` so you can re-inspect later.

**Paste the SUMMARY block back to chat.** It looks like:
```
==================== SUMMARY (paste this back) ====================
wall  base = 4.40X s   opt = X.XXX s   delta = -XX.XX%
vs prior best 4.405 s: delta = -XX.XX%
LLC-load-misses  base = ...   opt = ...
dTLB-load-misses base = ...   opt = ...
IPC              base = ...   opt = ...
===================================================================
```

---

## Step 3 - Decide on Patch 4 (LRU) using M5

M5's reuse rate tells you whether the LRU cache is worth keeping, so check it before doing anything else here.

If your M5 minimizer reuse rate is >= 0.20, the LRU cache is already in the
patch and is contributing to the SUMMARY delta above. **No further action.**

If M5 < 0.10, the LRU was wasted memory pressure. Edit
`~/kraken2-src/src/classify.cc` and remove the `lru_cache` block (or apply only
the prefetch + huge-pages + flag patches by editing `kraken2_opt_v1.patch` first
to delete the LRU hunk, then rerun `run_kraken2_opt_v1.sh`).

If 0.10 <= M5 < 0.20, halve the cache: change `LRU_BITS = 14` to `LRU_BITS = 13`
in the patch (8K entries, 128 KB/thread) and re-bench.

---

## Step 4 - Verify correctness (script does this automatically)

Optimisations must not change the classification output, so don't skip this check even if the wall time looks good. The script
asserts byte-identical `--report` between base and patched binaries. If it
fails, the patched binary is rejected and the SUMMARY says so. Investigate
the patch before doing anything else.

---

## Step 5 - Iterate (only if Phase 1 leaves wall > 3.0 s)

If you still want more, the v2 patches in
`../kraken2_get_optimizations_v2.md` add, in order:
- Patch 6: `final` keyword + concrete dispatch (devirtualises `hash->Get`)
- Patch 7: single MurmurHash via `GetByHash`
- Patch 8: `ResolveTree` O(N^2) to O(N)
- Patch 9: skip output formatting when `-O /dev/null`

Apply each by editing the source by hand (the diffs are in the v2 doc), rebuild,
re-run `run_kraken2_opt_v1.sh`. The script always re-applies the v1 patch
on top of master, so to test v2-on-top-of-v1 you'd apply v2 to the working
tree before running the script, and remove the `git stash` lines from the script
temporarily.

Or, simpler: paste the Phase-1 SUMMARY back to chat and we'll hand you a
combined `kraken2_opt_v2.patch` for Phase 2.

**Stop rule:** when two consecutive patches each give < 2% wall reduction,
you've hit diminishing returns. Stop and write up the result.

---

## Reporting back

After every patch round, paste back:
1. The full SUMMARY block.
2. (Phase 1 only) the M1-M7 results table from `pending_measurements.md`.

That's enough to drive the next iteration. The deliverable
`kraken2_optimisation_report.md` (in the repo root, section 6 results tables) is
where the measured numbers should be recorded.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make` fails on `MADV_HUGEPAGE` undeclared | Old headers | Add `#include <sys/mman.h>` to `mmap_file.cc` (should already be via `kraken2_headers.h`) |
| `perf stat` says "Operation not permitted" | paranoid > 2 | `sudo sysctl -w kernel.perf_event_paranoid=1` |
| `report` files differ between base and opt1 | A patch hunk broke semantics | Revert that hunk; rebuild; re-bench |
| Wall time *increases* | THP not active, prefetch wasted, or false sharing in LRU | Re-check M2, M5; halve LRU_BITS; test with prefetch-only build |
| Script exits with `git apply` error | Patch already applied or master moved | `cd ~/kraken2-src && git reset --hard HEAD && git pull` then rerun script |
| Cell type mismatch (40-bit DB but built with 32-bit) | Wrong `cht_cell_size` at build time | Confirm via M1 - DB and binary must agree |
