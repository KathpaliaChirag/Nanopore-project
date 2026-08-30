# Command Log — Sept 13 Paper Push

Running record of every command actually run toward the 3-piece paper package (LLC-adaptive cache, bitmask cell, cell-width reduction) set at Meeting 11 (2026-08-19), executed per `planning/week5plan.md` onward. This is the log of what happened, not what was planned — `planning/weekNplan.md` files are the plan, this file is the receipt.

> [!NOTE]
> One entry per command (or tight command group). Each entry: what, why, result. Append only — don't rewrite history here, correct forward instead. Commit this file alongside whatever code/data change it describes, not in a separate batch later.

**Format per entry:**

```
### YYYY-MM-DD HH:MM — <short label, e.g. "S1.1 — thread-local cache slot">
**Command:**
​```bash
<exact command run>
​```
**Why:** <one line — what step this is, from which plan>
**Input → Output:** <optional — see below>
**Result:** <what happened — output, benchmark numbers, pass/fail, commit hash if applicable>
```

**When to add "Input → Output":** only where the command transforms something and that transform isn't obvious from the command text alone — a build (source tree → binary), a benchmark (fastq + DB → latency/cache-miss numbers), a data step (raw pod5 → basecalled fastq). One line, plain terms, no ML/systems jargon left undefined — whoever reads this later may not have touched this exact command before. Skip it for anything mechanical where there's nothing to explain (`cd`, `ls`, `git commit`, the proxy/auth setup) — the field exists to save a future reader from re-deriving what a command does, not to pad every entry.

**Example (illustrative only — no real run has happened yet, don't treat these numbers as data):**

```
### YYYY-MM-DD HH:MM — S1.2 — first benchmark of the single-slot cache
**Command:**
​```bash
perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  ~/tools/kraken2-src-fresh/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 32 --output /dev/null --report /dev/null \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
​```
**Why:** S1.2 in week5plan.md — first real number for the single-slot cache, logged against the 4.405s S0 baseline.
**Input → Output:** takes a fastq of reads + a kraken2 database, classifies every read against it; perf stat wraps the run and reports cache-miss counts and wall-clock time alongside kraken2's own classification output.
**Result:** <wall-clock time>, <LLC miss rate> — compare against the S0 baseline, log honestly either way, tag `safe/S1.2` if it's a real safe zone.
```

---

## Log

### 2026-08-25 02:39 — Housekeeping: reorganized Luna home into ~/chirag_K/
**Command:**
```bash
mkdir -p ~/chirag_K
mv ~/AccuracyDrift ~/chirag_K/AccuracyDrift        && ln -s ~/chirag_K/AccuracyDrift ~/AccuracyDrift
mv ~/data           ~/chirag_K/data                 && ln -s ~/chirag_K/data ~/data
mv ~/tools          ~/chirag_K/tools                && ln -s ~/chirag_K/tools ~/tools
mv ~/results        ~/chirag_K/results              && ln -s ~/chirag_K/results ~/results
mv ~/scripts        ~/chirag_K/scripts              && ln -s ~/chirag_K/scripts ~/scripts
mv ~/Documents      ~/chirag_K/Documents            && ln -s ~/chirag_K/Documents ~/Documents
mv ~/matmul         ~/chirag_K/matmul               && ln -s ~/chirag_K/matmul ~/matmul
mv ~/matmul_gpu     ~/chirag_K/matmul_gpu           && ln -s ~/chirag_K/matmul_gpu ~/matmul_gpu
mv ~/perf.data      ~/chirag_K/perf.data            && ln -s ~/chirag_K/perf.data ~/perf.data
mv ~/kraken_runs_small.tar.gz ~/chirag_K/kraken_runs_small.tar.gz && ln -s ~/chirag_K/kraken_runs_small.tar.gz ~/kraken_runs_small.tar.gz
mv ~/runs_txt_only.tar.gz     ~/chirag_K/runs_txt_only.tar.gz     && ln -s ~/chirag_K/runs_txt_only.tar.gz ~/runs_txt_only.tar.gz
mv ~/cuda-keyring_1.1-1_all.deb ~/chirag_K/cuda-keyring_1.1-1_all.deb && ln -s ~/chirag_K/cuda-keyring_1.1-1_all.deb ~/cuda-keyring_1.1-1_all.deb
mv ~/headers.txt    ~/chirag_K/headers.txt          && ln -s ~/chirag_K/headers.txt ~/headers.txt
mv ~/mapped.txt     ~/chirag_K/mapped.txt           && ln -s ~/chirag_K/mapped.txt ~/mapped.txt
mv "$HOME/dna_r10.4.1_e8.2_400bps_fast@v5.2.0" ~/chirag_K/ && ln -s "$HOME/chirag_K/dna_r10.4.1_e8.2_400bps_fast@v5.2.0" "$HOME/dna_r10.4.1_e8.2_400bps_fast@v5.2.0"
mv "$HOME/dna_r10.4.1_e8.2_400bps_hac@v5.2.0"  ~/chirag_K/ && ln -s "$HOME/chirag_K/dna_r10.4.1_e8.2_400bps_hac@v5.2.0" "$HOME/dna_r10.4.1_e8.2_400bps_hac@v5.2.0"
mv "$HOME/dna_r10.4.1_e8.2_400bps_sup@v5.2.0"  ~/chirag_K/ && ln -s "$HOME/chirag_K/dna_r10.4.1_e8.2_400bps_sup@v5.2.0" "$HOME/dna_r10.4.1_e8.2_400bps_sup@v5.2.0"
```
**Why:** Luna's `student` account is shared with at least one labmate (`rohit`); before starting the fresh-clone + benchmark work for this paper push, moved everything that's ours into one folder for clarity, without breaking any existing path. Chose move+symlink over a full move specifically so every hardcoded path in CLAUDE.md/week5plan.md/scripts (`~/tools/...`, `~/AccuracyDrift/databases/...`, `~/data/basecalled/...`) keeps working unchanged.
**Input → Output:** each `mv` relocates one top-level item into `~/chirag_K/`; each `ln -s` immediately after recreates the old name as a symlink pointing into the new location, so every existing absolute-path reference still resolves to the same file, just via one extra hop.
**Result:** all 16 items moved successfully — `ls -la ~` confirms every symlink resolves correctly into `~/chirag_K/...`. `rohit/`, `snap/`, and `iitd-login.py` deliberately left untouched (not ours / needed at top level). `du -sh` beforehand measured our footprint at ~312G total (AccuracyDrift 143G, data 111G, results 52G, tools 5.7G, rest <1G combined) out of 750G used / 938G disk. Surfaced several previously-hidden dotfile directories worth checking for cleanup: 4× `.tmp_pod5_v3_v4_migration_*`, `.temp_dorado_model-e5a4d564d3600e14`, `.debug`, `snn` — sizes not yet checked, nothing deleted yet.

### 2026-08-25 04:36 — Luna proxy login troubleshooting (fresh-build Step 1)
**Command:**
```bash
tmux new -s <session>
unset http_proxy https_proxy HTTP_proxy HTTPS_proxy   # inside the tmux pane, before login
python3 ~/iitd-login.py -d
# then, back in the normal shell:
export HTTP_proxy=http://proxy62.iitd.ac.in:3128
export HTTPS_proxy=http://proxy62.iitd.ac.in:3128
export https_proxy=http://proxy62.iitd.ac.in:3128
export http_proxy=http://proxy62.iitd.ac.in:3128
```
**Why:** week5plan.md's Fresh Build Step 1 — needed working outbound internet before `git clone` would work.
**Result:** two real problems found and fixed, not user error alone:
1. The four proxy `export` lines are already baked into `~/.bashrc` from an earlier session, so every *new* shell (including a fresh tmux pane) auto-loads them at startup. This meant `env -u http_proxy ... python3 ~/iitd-login.py -d` wasn't actually running login proxy-free — the login request looped back through the proxy to itself, which the login CGI correctly rejects ("You can't login from a proxy server ip..."). Fixed by explicit `unset` of all four vars inside the shell before running login, not just `env -u` on the one child process.
2. Once login genuinely succeeded, the authenticated session only stays alive for **~100 seconds**, then expires for ~100 seconds before the daemon (`-d` flag) auto-relogs — so roughly half the time, any request will hang/timeout through no fault of the command itself. Worked around by retrying the actual operation (not just a connectivity probe) in a loop with a short sleep, until one attempt lands in a live window, rather than trying to time it manually. Worth flagging to whoever maintains `iitd-login.py`/the proxy if this keeps happening — a ~100s session lifetime is unusually short.

### 2026-08-25 19:32 — Fresh clone of Kraken2, pinned to v2.1.3 (fresh-build Step 2)
**Command:**
```bash
cd ~/tools
for i in $(seq 1 30); do
  rm -rf kraken2-src-fresh
  git clone https://github.com/DerrickWood/kraken2.git kraken2-src-fresh && break
  sleep 5
done
cd kraken2-src-fresh
git checkout v2.1.3
git log -1 --format='%H %ci' > PROVENANCE.txt
cat PROVENANCE.txt
grep -n "MMK" src/classify.cc
```
**Why:** week5plan.md's Fresh Build Step 2 — a genuinely clean Kraken2 tree, separate from the already-patched `~/tools/kraken2-src`, pinned to v2.1.3 to stay comparable with the existing 4.405s baseline and the cell-width report's numbers.
**Input → Output:** clones upstream Kraken2's full git history into `~/tools/kraken2-src-fresh` (resolves through the `~/tools` symlink into `~/chirag_K/tools/kraken2-src-fresh`), then moves that tree's HEAD to the exact `v2.1.3` release tag.
**Result:** clone succeeded on the first retry-loop attempt (no timeout hit this time). `git checkout v2.1.3` landed at commit `8f82a7ded7816c7ceed5086598b2979f80c970d8`, dated 2023-06-06, recorded in `kraken2-src-fresh/PROVENANCE.txt`. `grep -n "MMK" src/classify.cc` printed nothing — tree confirmed clean, no leftover patch code.

### 2026-08-25 19:45 — Switched fresh clone to latest (v2.17.1), reversing the v2.1.3 plan
**Command:**
```bash
git fetch --tags
git tag --sort=-creatordate | head -5
git checkout v2.17.1
git log -1 --format='%H %ci' > PROVENANCE.txt
cat PROVENANCE.txt
grep -n "MMK" src/classify.cc
```
**Why:** user explicitly chose to build on current upstream (v2.17.1) instead of the v2.1.3 pin week5plan.md had planned, after being shown the tradeoff (breaks comparability with the existing 4.405s baseline and the cell-width report, since v2.1.4 rewrote the FASTA/Q parser in the exact hot path this project profiles). Decision made knowingly, not a default.
**Input → Output:** `git fetch --tags` pulls any new tags from upstream; `git tag --sort=-creatordate` lists them newest-first, confirming `v2.17.1` really is the latest release (not just trusting earlier research); `git checkout v2.17.1` moves the same clone's HEAD to that tag.
**Result:** confirmed `v2.17.1` is genuinely the latest tag (`v2.17.1`, `v2.17`, `v2.1.6`, `v2.1.5`, `v2.14` in that order). Checked out clean — HEAD now at `5e2aa928d00b96d61f204d517437637863da1d8c`, dated 2025-11-24, matching the expected v2.17.1 release date. `grep -n "MMK"` still printed nothing. **Consequence:** S0's baseline needs to be re-measured on this tree before any S1-S3 number means anything — the old 4.405s figure was v2.1.3-specific.

### 2026-08-25 20:15 — Built kraken2-fresh-bin, re-measured S0 as a 3-DB × 5-thread sweep
**Command:**
```bash
./install_kraken2.sh ~/tools/kraken2-fresh-bin

for db in sample_targeted standard_8gb pluspf_103gb; do
  for t in 1 16 32 64 96; do
    echo "=== DB=$db THREADS=$t ==="
    perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
      numactl --cpunodebind=0 --membind=0 \
      ~/tools/kraken2-fresh-bin/kraken2 --db ~/AccuracyDrift/databases/$db \
      --threads $t --output /dev/null --report /dev/null \
      ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq 2>&1
    echo ""
  done
done | tee ~/s0_sweep_v2.17.1.txt
```
**Why:** week5plan.md Step 2's build, then a re-measurement of S0 on v2.17.1 (required — the old 4.405s number was v2.1.3-specific). User expanded scope from the plan's single 32T/sample_targeted number to a 3-DB × 5-thread sweep, 1 run per cell (not the plan's usual 5-run/CV/CI treatment — a deliberate, lighter-weight exploratory pass, not this week's final statistically-validated S0).
**Input → Output:** `install_kraken2.sh` compiles the v2.17.1 tree into `~/tools/kraken2-fresh-bin/{kraken2,kraken2-build,kraken2-inspect,...}` (build was clean, only benign `-Wsign-compare`/unused-variable warnings, no errors). The sweep then runs the standard profiling command across all 15 (DB × thread-count) combinations against the same `_15.fastq` input, saving raw output to `~/s0_sweep_v2.17.1.txt`.
**Result:** all 15 runs completed. Full table:

| DB | Threads | Elapsed | Cache-miss % | LLC-miss % | IPC |
|---|---|---|---|---|---|
| sample_targeted (50MB) | 1 | 5.110s | 6.92% | 8.26% | 1.98 |
| sample_targeted (50MB) | 16 | 0.556s | 13.66% | 12.21% | 1.85 |
| sample_targeted (50MB) | 32 | 0.576s | 14.85% | 12.65% | 1.75 |
| sample_targeted (50MB) | 64 | 0.569s | 15.38% | 13.07% | 1.57 |
| sample_targeted (50MB) | 96 | 0.597s | 15.26% | 12.96% | 1.23 |
| standard_8gb (7.6GB) | 1 | 7.208s | 88.85% | 88.22% | 1.82 |
| standard_8gb (7.6GB) | 16 | 4.226s | 92.85% | 90.01% | 1.70 |
| standard_8gb (7.6GB) | 32 | 4.233s | 93.18% | 90.47% | 1.65 |
| standard_8gb (7.6GB) | 64 | 4.259s | 92.59% | 89.68% | 1.52 |
| standard_8gb (7.6GB) | 96 | 4.318s | 92.32% | 89.27% | 1.30 |
| pluspf_103gb (103.4GB) | 1 | 78.459s | 90.18% | 85.52% | 1.14 |
| pluspf_103gb (103.4GB) | 16 | 54.511s | 95.35% | 93.85% | 1.09 |
| pluspf_103gb (103.4GB) | 32 | 51.897s | 96.45% | 95.59% | 1.08 |
| pluspf_103gb (103.4GB) | 64 | 51.814s | 96.43% | 95.55% | 1.07 |
| pluspf_103gb (103.4GB) | 96 | 52.150s | 96.40% | 95.49% | 1.04 |

The `sample_targeted` × 32T row (0.576s) is the direct v2.17.1 successor to the old v2.1.3 4.405s figure — that's this week's S0 anchor for S1-S3 comparisons at the plan's standard 32T config. 32T-64T holds up as the practical sweet spot across both larger DBs on v2.17.1 too (matches the original v2.1.3-era finding); 96T is measurably worse everywhere (IPC drops steadily with thread count past the sweet spot). `pluspf_103gb` at 1 thread pays a ~78s DB-load penalty vs ~52s at 32T+, since loading isn't thread-parallelized. **Caveat:** single run per cell, no CV/variance check — treat as directional, not a citable final number, until re-run with the plan's normal 5-run treatment if these need to go in the paper.

### 2026-08-25 — S1.1 investigation: located the Get() call site and existing cache behavior
**Command:**
```bash
cd ~/tools/kraken2-src-fresh/src
grep -n "\.Get(\|->Get(" classify.cc
sed -n '760,820p' classify.cc
sed -n '745,764p' classify.cc
grep -n "omp parallel\|ClassifySequence\|ProcessFiles" classify.cc | head -20
```
**Why:** S1.1 needs a thread-local single-slot cache in front of `CompactHashTable::Get()` (96.24% of all LLC misses per this project's own profiling, despite being 0.65% of instructions). Before writing any code, needed to find the real call site, its surrounding types/loop structure, and confirm the calling function actually runs inside a persistent OpenMP worker thread — required for a `thread_local` variable to behave the way S1 needs (one real slot per worker thread across many reads, not something that resets or gets shared unexpectedly).
**Result:** one call site, `classify.cc:803`, inside `ClassifySequence()` (line 757), called once per read (per mate, per translated-search frame). **Key finding: stock Kraken2 already has a same-adjacent-minimizer cache** — `last_minimizer`/`last_taxon`, function-local variables reset every call — that skips `Get()` only when the current minimizer is identical to the *immediately preceding* one. It has zero memory across reads (reset every `ClassifySequence` call) and zero memory once a different minimizer interrupts a repeat streak. Confirmed `ClassifySequence` is called (`classify.cc:563,568`) from inside `#pragma omp parallel` (`classify.cc:484`, in `ProcessFiles`) — each OpenMP worker thread does call it repeatedly across many reads, so a `thread_local` variable here is safe and meaningful. **S1.1's actual scope, now well-defined:** promote `last_minimizer`/`last_taxon` from function-local to `thread_local` storage at file scope, remove the per-call reset — same comparison logic, but now remembers across reads/mates/frames on the same thread instead of just the immediately-previous minimizer.

### 2026-08-25 — S1.1 patch applied: promoted the cache to thread_local
**Command:** Python find-and-replace script (backed up `classify.cc` first as `classify.cc.pre-s1.1.bak`) — added `static thread_local uint64_t s1_last_minimizer` / `static thread_local taxid_t s1_last_taxon` at file scope above `ClassifySequence`, removed the old per-call reset, renamed the 4 in-function references to point at the new pair. Full script and reasoning in the S1.1 investigation entry above.
**Result:** `diff` confirmed the change was exactly as intended — declaration added, reset removed, all 4 renames landed correctly. Explicitly verified `scanner.last_minimizer()` (a `MinimizerScanner` *method call* on line 820, coincidentally similar-looking, unrelated to our variables) survived untouched — this was a real risk a blind bare-word rename would have hit, caught by grepping every occurrence of both names first.

### 2026-08-25 — S1.2 measured: naive single-run sweep found a page-cache confound, fixed with a controlled 3-run interleaved re-measurement
**Command (first attempt, flawed):** rebuilt `kraken2-fresh-bin` with the S1.1 patch, re-ran the same 3-DB × 5-thread, 1-run sweep used for S0, saved to `~/s1_sweep_v2.17.1.txt`.
**Result (first attempt):** mixed and partly misleading. `pluspf_103gb` at 1 thread showed a dramatic 22% wall-clock improvement (78.5s → 61.1s) but LLC-miss rate got **10 points worse** (85.5% → 95.6%) — a contradiction that shouldn't happen from a real code effect. Diagnosed as a **page-cache confound**: the S1 sweep ran right after the S0 sweep had already read the same 103GB file once, and Luna's 503GB RAM is easily enough to cache large chunks of it, making S1's read faster for reasons unrelated to the code change. `standard_8gb` showed a consistent-looking ~1-1.7pp LLC-miss improvement at every thread count, but wall-clock got *slower* (+1.6-3.2%) — flagged as possibly TLS-access overhead outweighing the benefit, but not trusted without a controlled re-run.

**Command (fixed methodology):** built two separate, permanent binaries — `kraken2-fresh-bin-s0` (unpatched, from `classify.cc.pre-s1.1.bak`) and `kraken2-fresh-bin-s1` (patched) — then ran a Python script (`/tmp/compare.py`) doing 3 runs each of S0/S1, **interleaved** (S0,S1,S0,S1,S0,S1 per cell, not blocked) across all 15 DB×thread cells, computing per-cell mean and coefficient-of-variation (CV%) for elapsed time. Saved to `~/s0_s1_3run_compare.txt`.
**Result (controlled):** all cells came back with low CV% (mostly <2%, worst case 4.66%, all within the plan's ≤5% "trust the mean" threshold) — this data is trustworthy. **The page-cache artifact vanished**: `pluspf_103gb` T=1 is now S0=62.03s vs S1=61.95s (0.1% difference, noise). **`standard_8gb`'s earlier LLC-miss "improvement" also washed out** — now flat between S0/S1 at every thread count (differences under 0.7pp, no consistent direction). **Honest conclusion: on `standard_8gb` and `pluspf_103gb` (the two DBs where `Get()` is genuinely expensive, 88-96% cache-miss rate), S1.1 produces no measurable difference** — LLC-miss% statistically flat, elapsed time within ~2% either way, all noise-level. `sample_targeted` shows a real, low-CV 5-13% wall-clock speedup at 16T-96T, but with no corresponding change in cache-miss metrics (under 0.3pp) — the cause is unclear and not claimed to be a caching effect.

**Why this is still a useful result, not a failed step:** a single cache slot's odds of matching the *next* lookup shrink toward zero as the number of distinct minimizers in the database grows into the millions (`standard_8gb`/`pluspf_103gb`) — this is real evidence, not assumption, that S1's one-slot design has a real ceiling, and gives S2 (sir's required 4-way associative cache, 4 remembered slots instead of 1) a concrete, evidenced reason to exist as the next step rather than a redundant one.

### 2026-08-25 — S1.1/S1.2 committed and tagged in kraken2-src-fresh; ledger updated
**Command:**
```bash
cd ~/tools/kraken2-src-fresh
git config user.name "Chirag Kathpalia"      # local to this repo only - shared Luna account
git config user.email "chiragkathpalia1@gmail.com"
git add src/classify.cc
git commit -m "S1.1: promote same-adjacent-minimizer cache to thread_local"
git tag safe/S1.2
```
**Why:** `kraken2-src-fresh` is its own git repo (separate history from this Nanopore-project repo) — the patch had only existed as an uncommitted working-tree edit until now. The plan's own fallback framework calls for a real, tagged commit per Measured sub-step so there's always a findable "last known-good state" to return to, not just a file backup.
**Result:** first commit attempt failed ("Author identity unknown" — no git identity configured on this account yet); the `git tag safe/S1.2` line right after it still ran anyway (not `&&`-chained), tagging the *wrong* commit (the pre-patch `v2.17.1` checkout, `5e2aa928...`). Caught via `git log -1 safe/S1.2` before it could cause confusion later. Fixed: set `user.name`/`user.email` locally (not `--global`, since `student` is a shared account), re-ran the commit successfully (`fbf993d9ee204850622a2365af52f6db4e870e8f`), deleted the stale tag, re-tagged `safe/S1.2` pointing at the real commit, verified with `git log -1 safe/S1.2 --format='%H %s'`. `planning/week4plan.md`'s safe-zone ledger updated: S1/S1.1/S1.2 all marked 🔵 done, with the real commit hash and the honest S1.2 result (no measurable benefit on `standard_8gb`/`pluspf_103gb`, unexplained modest speedup on `sample_targeted` only) recorded in the ledger cell, pointing back to this log for full detail.

### 2026-08-25 — S2.1/S2.2/S2.3 implemented: 4-way set-associative cache
**Command:** Python find-and-replace script (same pattern as S1.1's patch — backup first as `classify.cc.pre-s2.bak`, exact-string replacements with `assert content.count(...) == 1`). Two changes: (1) added `S2Entry`/`s2_cache[4096][4]`/`s2_next_way[4096]` plus `S2SetIndex`/`S2Lookup`/`S2Insert` right after the S1.1 declarations; (2) wrapped only the `hash->Get()` call inside the existing `if (*minimizer_ptr != s1_last_minimizer)` block with an `S2Lookup`/`S2Insert` check.
**Why:** S2 is sir's literal required Thesis 1 baseline ("Baseline 4-way set associative"), motivated directly by S1's result — a single slot's hit odds vanish once a DB has millions of distinct minimizers, so this gives the cache real capacity (4096 sets × 4 ways = 16,384 entries, ~256KB/thread, thread_local like S1) while keeping lookups cheap (a bitmask picks the set, at most 4 comparisons per lookup). Size is a placeholder — S3 tunes it properly later.
**A real correctness bug caught before it was written, not after:** the natural-looking implementation would have used S2's cache hit/miss to also decide whether `minimizer_hit_groups` gets incremented and `curr_taxon_counts` gets updated — but those two counters feed `--quick-mode`'s early-exit threshold and the classification report's per-species k-mer counts (via HyperLogLog), and stock Kraken2 deliberately only updates them when a minimizer differs from the *immediately preceding one* (collapsing a repeated-minimizer run into one count). S2's cache catches repeats across a much wider span — using it to gate those counters would have silently suppressed far more counts than stock Kraken2 intends, changing the actual classification report output, not just performance. **Fix:** kept the two concerns fully separate — the `s1_last_minimizer` adjacent-check still gates *all* stats-counting, completely unchanged from stock behavior; S2's cache is used *only* to decide whether `hash->Get()` needs to run again, which is safe since `Get()` is a pure function (same input, same output, cached or not).
**Result:** `diff` confirmed the patch landed exactly as designed — both insertions in the right places, nothing else touched. Not yet built or benchmarked (S2.4 next).

### 2026-08-26 — S2.4 measured: 4-way cache (16,384 entries) shows no benefit vs S0/S1
**Command:** built `kraken2-fresh-bin-s2`, ran the same validated 3-run interleaved methodology (S0/S1/S2, all 3 DBs × 5 thread counts).
**Result:** LLC-miss% differences between S0/S1/S2 were all within ~0.5pp on `standard_8gb`/`pluspf_103gb`, no consistent direction — statistically flat. **The 4-way structure at this size does not beat the single slot.** Full comparison tables in chat; raw data in `~/s0_s1_s2_3run_compare.txt` on Luna.

### 2026-08-26 — Size sweep: 4,096 → 4,194,304 sets, found a catastrophic cliff, not a gradual improvement
**Why:** user asked whether S2's placeholder size (4,096 sets) might just be too small for Luna's real working set — a reasonable hypothesis, since S2's own comment said "size is a placeholder, S3 tunes it properly." Rather than build S3's full topology-detection/trace-simulation machinery on a guess, tested the hypothesis cheaply first: built 3 more S2 binaries at 65,536 / 1,048,576 / 4,194,304 sets (16×/256×/1024× the original) and re-ran the full validated methodology (3 DBs × 5 threads × 6 binaries, 3 interleaved runs each — `/tmp/compare_sizes_full.py`, saved to `~/s2_size_sweep_full.txt`).
**Result — the opposite of "too small," and clearer than expected:** performance is flat and unremarkable from S0 through 65,536 sets, then falls off a cliff. Worst case: `sample_targeted` at 96 threads, `S2-4194304` — **12.51s vs a 0.56s baseline (22× slower)**, LLC-miss rate jumping from ~13% to **85%**. The effect scales with thread count (worse at 96T than at 16T), which points directly at the cause: this cache is `thread_local` — every thread gets its own private, freshly-zeroed copy. At 4,194,304 sets × 4 ways × 16 bytes ≈ 256MB *per thread*; at 96 threads that's ~24GB of brand-new memory touched on every single process run, before any actual classification happens. That memory-initialization/page-fault cost, not cache behavior, is almost certainly what dominates at the largest sizes — this is a different failure mode than "cache too small," and a real methodological finding for S3: sizing has a hard ceiling that has nothing to do with hit-rate math, driven purely by per-thread allocation cost. Full interactive chart + tables published: https://claude.ai/code/artifact/096bb2bd-fa61-45cd-a90e-2fe9721dab82 (some cells — `standard_8gb` T=1/S0, `pluspf_103gb` T=96/S0 — exceeded the 5% CV threshold and are flagged as noisy, not trusted).
**Implication for S3:** LLC-topology-aware sizing isn't just "bigger within budget" — it needs to account for *per-thread* multiplication (size × ways × bytes × thread count), not just fitting one copy in the LLC. A size that's fine for 1 thread can be catastrophic at 96.

### 2026-08-26 — Independent verification audit: found S2 is nested inside S1's gate, not standalone
**Command:** 5-agent/3-round `/goal`-triggered audit run from a fresh session, per `plan_paper/verification_audit_brief.md`. Full report: `plan_paper/verification_report_2026-08-26.md`.
**Result — critical finding:** `S2Lookup`/`S2Insert` are called inside the existing `if (*minimizer_ptr != s1_last_minimizer)` block, not standalone in front of `hash->Get()`. When a minimizer matches the immediately-preceding one, execution takes the `else { taxon = s1_last_taxon; }` branch entirely — **S2 never sees that lookup.** S2 only ever receives the residual stream that already failed S1's filter, not the full lookup stream "sir's baseline" framing implies. Every S2 "no benefit" conclusion measured so far is therefore untrusted until re-measured with this fixed.
**Other confirmed findings:** no hit/miss instrumentation exists inside `S2Lookup` (external proxies only — wall-clock, `perf stat` LLC-miss% — can't distinguish "cache rarely hits" from "cache never hits due to a bug"); classification-output correctness was never checked (`--output /dev/null` throughout); the memory-init cliff diagnosis is confirmed as the leading hypothesis but likely a two-mechanism story (fixed per-thread init cost + a smaller DB-size-dependent effect); the v2.1.3→v2.17.1 version-switch risk is broader than logged (`kraken2-build`'s own hash-construction logic across 5 releases was never checked, only the parser); this is the second consecutive week missing its own explicit target; `week4plan.md`'s ledger was stale (fixed in the next entry below).
**Action taken:** committed and tagged S2 on Luna immediately per the audit's #1 recommendation (data safety, independent of the bug) — see next entry.

### 2026-08-26 — S2 committed + tagged on Luna (with known bug documented in the commit message)
**Command:**
```bash
cd ~/tools/kraken2-src-fresh
git add src/classify.cc
git commit -m "S2.1-S2.3: 4-way set-associative cache (4,096 sets)

Known issue, flagged by independent audit 2026-08-26: S2Lookup/S2Insert
are nested inside S1's adjacent-minimizer gate, not standalone in front
of hash->Get() - fix pending (see plan_paper/verification_report_2026-08-26.md, Q1)."
git tag safe/S2.4
git log -1 safe/S2.4 --format='%H %s'
```
**Why:** S2 had been sitting uncommitted on a shared Luna account (`student`) with an already-documented data-loss precedent (two ESKAPE databases lost, root cause unresolved) — audit's #1 recommendation, unconditional on resolving anything else. Committing with the bug documented in the message means nobody (including future us) mistakes this for a clean baseline.
**Result:** committed as `75f908e46ea9242e7b34bf4be88a05233f78920c`, tagged `safe/S2.4`. `planning/week4plan.md`'s stale ledger (S2 rows still showed `⬜ not started` despite S2.1-S2.4 being implemented and measured) fixed to reflect the real commit hash and the honest, bug-flagged status.
**Next:** rewire S2 to check every lookup (not just the residual stream after S1's filter), add hit/miss counters, run a real `--output` correctness diff against S0, then re-measure.

### 2026-08-26 — Built S2-standalone (fixes the nesting bug for testing) + real hit/miss counters; audit's Q1/Q3 concern resolved
**Command:** `plan_paper/scripts/s2_standalone_patch.py` applied to the ORIGINAL unpatched `classify.cc.pre-s1.1.bak` (not on top of S1) — wraps `hash->Get()` directly with S2's cache, no S1 layer in between, plus real `std::atomic` hit/miss counters printed via `atexit()`. Built as `kraken2-fresh-bin-s2-standalone`. Compared against S0/S1/S2-nested with `plan_paper/scripts/compare_s2_standalone.py` (same validated interleaved 3-run methodology, extended to 4 binaries, all 3 DBs × 5 threads).
**Why:** directly tests the audit's Q1 finding (S2 nested inside S1's gate) and Q3 concern (no instrumentation existed to tell "cache rarely hits" from "cache never hits due to a bug") in one build.
**Result — Q1/Q3 resolved, on the DBs that matter:**
- **Hit rate is real, tiny, and completely flat across all 5 thread counts**: ~0.403% on `standard_8gb`, ~0.141% on `pluspf_103gb`/`sample_targeted`, identical at 1T through 96T. This flatness is itself evidence it's a genuine property of the data, not noise or a thread-count artifact.
- **Fixing the nesting bug changed nothing on `standard_8gb`/`pluspf_103gb`** — `S2-nested` vs `S2-standalone` elapsed time and LLC-miss% are statistically indistinguishable at every thread count on both DBs (e.g. `standard_8gb`/32T: nested 4.66s/87.81% vs standalone 4.65s/87.72%). **The nesting bug is not why S2 shows no benefit where it counts — capacity (16,384 entries vs. millions of distinct minimizers) is the real, confirmed bottleneck.** The bug was still real and worth fixing (a genuine architecture defect), just not the explanation for the "no benefit" result.
- **A new, self-inflicted artifact found and diagnosed, not attributed to the cache design**: `sample_targeted`/`S2-standalone` runs ~3x slower than everything else at 16T-96T (e.g. 1.84s vs a 0.55s baseline), with elevated LLC-miss% (15-16% vs 13%). Root cause: the hit/miss counters are global `std::atomic` variables, incremented via `fetch_add` on every single lookup from every thread — classic cache-line contention that scales badly with thread count. This overhead is invisible on `standard_8gb`/`pluspf_103gb` (where each `Get()` call is already slow/memory-bound, dwarfing the contention cost) but dominates on `sample_targeted` (where `Get()` is fast enough that the counter contention becomes the largest cost). **`sample_targeted`'s `S2-standalone` elapsed-time numbers from this run should not be trusted as telling us anything about the cache** — fixing this would require `thread_local` counters aggregated once at exit, not global atomics.
- Side observation: `sample_targeted` and `pluspf_103gb` share an identical hit rate (0.1412%) while `standard_8gb` differs (0.4032%) — likely because the two former DBs were built with matching k-mer/minimizer parameters while `standard_8gb`'s differ, producing a different minimizer stream from the same input reads.
**Audit checklist status:** items 2 (rewire) and 3 (instrumentation) from `verification_report_2026-08-26.md`'s pre-S3.4 checklist are done. Item 4 (real `--output` correctness diff) is still outstanding.

### 2026-08-26 — S2 correctness-verified: real classification output identical to S0
**Command:**
```bash
mkdir -p ~/correctness_check
~/tools/kraken2-fresh-bin-s0/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 1 --output ~/correctness_check/s0_output.txt --report ~/correctness_check/s0_report.txt \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
~/tools/kraken2-fresh-bin-s2/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 1 --output ~/correctness_check/s2_output.txt --report ~/correctness_check/s2_report.txt \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
diff ~/correctness_check/s0_output.txt ~/correctness_check/s2_output.txt && echo "IDENTICAL"
diff ~/correctness_check/s0_report.txt ~/correctness_check/s2_report.txt && echo "REPORT IDENTICAL TOO"
```
**Why:** the one remaining gap on the audit's pre-S3.4 checklist (Q2/Q5) — every prior benchmark used `--output /dev/null`, so classification correctness (not just performance) had never actually been checked. Real (single-threaded, to remove any scheduling-order confound) `--output`/`--report` files from `kraken2-fresh-bin-s0` (unpatched) and `kraken2-fresh-bin-s2` (the currently-committed nested S2, `75f908e`/`safe/S2.4`) diffed directly against each other.
**Result:** both `diff`s came back completely empty — **classification output and the summary report are byte-for-byte identical between S0 and S2.** The cache never changes which species a read gets called as; it only changes whether a lookup goes through the hash table or the cache. Combined with the earlier standalone test (which showed the nesting bug doesn't meaningfully affect the performance conclusion either), **S2 is now fully verified: correct and honestly measured.** Audit checklist items 2, 3, and 4 are all closed. Remaining: item 6 (pre-touch/page-faults experiment for the memory-init cliff, relevant before finalizing S3's sizing formula) and updating `week4plan.md`'s ledger to drop the now-resolved "known bug" framing.

### 2026-08-26 — Exploring beyond the audit: does eviction policy matter, not just capacity?
**Why:** with S2 fully verified, the open question became *why* the hit rate is so low (0.14-0.40%) and whether it's fixable without hitting the memory-init cliff again. This project's own prior M5 finding measured 90.7% k-mer reuse — high global reuse can coexist with near-zero cache hit rate if repeats are separated by more distinct intervening minimizers than the cache's capacity, and round-robin evicts a proven-useful entry the instant its turn comes up, regardless of how recently or often it was hit. Tested this directly rather than assuming it.
**Command:** `plan_paper/scripts/s2_pinned_patch.py` — same standalone wiring as `s2_standalone_patch.py` (built from the original unpatched `classify.cc`, no S1 layer, same 4,096-set size, same instrumentation), with ONE change: eviction now protects any entry that's been hit at least once (a "grace period"), only falling back to round-robin once every entry in a set has proven itself. Built as `kraken2-fresh-bin-s2-pinned`. Same single-run sanity check as the standalone variant (`standard_8gb`, 1 thread, same fastq) for direct comparability.
**Result:** `hit_rate=0.5050%` (15,183 hits / 2,991,367 misses) vs. round-robin's `0.4035%` on the identical test — **a real ~25% relative improvement in hit rate from eviction policy alone, same capacity.** Still a 99.5% miss rate in absolute terms, but this is genuine evidence the locality story is right: eviction policy is a real, independent lever from capacity, not a wash. Directly supports S4's premise (biology-dependent eviction) with real numbers, not just theory. Not yet run across the full DB/thread matrix — single sanity-check run only.

### 2026-08-26 — Full capacity × eviction-policy experiment: real findings, plus a new crash mode distinct from the memory-init cliff
**Command:** both patches updated to print their own configured size (`size=%zu ways=%zu`) in every run, so a binary can never be silently mislabeled again. `plan_paper/scripts/build_pinning_experiment.sh` built 6 binaries (round-robin and pinned, each at 4,096 / 65,536 / 262,144 sets — deliberately stopping short of the confirmed memory-init cliff at 1M+). `plan_paper/scripts/compare_pinning_experiment.py` ran the full 3-DB × 5-thread × 3-run matrix, cross-checking every run's reported size against what was expected.
**Result — a second, distinct failure mode found:** `262,144` sets at 16+ threads **segfaults** (confirmed directly: exit code 139, "Segmentation fault (core dumped)"), while the exact same size at 1 thread runs cleanly. This is NOT the earlier memory-init slowdown (that kicked in around 64MB+/thread and got progressively slower, never crashed) — `262,144` sets is only 16MB/thread, trivial in absolute RAM terms (16MB × 96 threads ≈ 1.5GB on a 503GB machine), yet crashes hard the moment OpenMP creates multiple worker threads simultaneously. Leading hypothesis: `thread_local` arrays this large are hitting glibc's static TLS (thread-local storage) allocation limit — each new thread needs its slice of that storage reserved at thread-creation time, and that budget has historically been much smaller than "however much RAM is free," independent of total memory available. **Real fix for later: don't put large arrays directly as `thread_local` — use a `thread_local` pointer instead, heap-allocated (`new`) once per thread on first use, which doesn't have this ceiling.** Not implemented today — flagged as a real constraint for S3's design, not something to rush a fix for under time pressure.
**Valid data (T=1 all sizes; all thread counts at 4,096/65,536 sets; T=16-96 at 262,144 discarded due to the crash):**

| Size | RR hit rate (T=1) | Pinned hit rate (T=1) | Pinned's relative gain |
|---|---|---|---|
| 4,096 | 0.4035% (`standard_8gb`) | 0.5050% | +25.2% |
| 65,536 | 0.7675% | 0.8346% | +8.7% |
| 262,144 | 1.4229% | 1.4843% | +4.3% |

**Real finding: pinning's relative advantage over round-robin shrinks as capacity grows** — smart eviction matters most when capacity is severely constrained (protecting the few useful entries counts for a lot), and matters progressively less as there's simply more room for everything anyway. Given capacity can't grow arbitrarily (both the slowdown cliff at 1M+ and now this crash ceiling at 262K+ under multi-threading), this makes S4's eviction work *more* valuable, not less — it's the lever that matters most in exactly the constrained-capacity regime S3 will likely have to operate in. Hit rate also scales sub-linearly and consistently with capacity across both eviction policies (roughly doubling from 4,096→65,536, then a smaller jump to 262,144) — a clean, sensible trend, not noise. `sample_targeted` and `pluspf_103gb` continue to show identical hit rates to each other (consistent with the earlier finding that they share minimizer-scheme parameters), distinct from `standard_8gb`. Full raw data: `~/pinning_experiment_full.txt` on Luna.

### 2026-08-30 — P.0/P.1 pre-checks confirm the crash mechanism and the real per-socket LLC, then S3.0 lands and fixes the crash
**Why:** per `plan_paper/s3_s4_debate_report_2026-08-27.md`'s Q1/Q2, two cheap measurements were recommended before writing any code — confirm the static-TLS/stack-budget theory for the 262,144-set crash, and confirm Luna's real per-socket L3 size instead of continuing to assume the spec-sheet-derived 105MB. User confirmed sequencing: finish S3+S4 (Track A) completely before starting any Track B work.

**Command (P.0):**
```bash
ulimit -s
ulimit -a
numactl --cpunodebind=0 --membind=0 ~/tools/kraken2-fresh-bin-s2-standalone-262144/kraken2 \
  --db ~/AccuracyDrift/databases/sample_targeted --threads 16 \
  --output /dev/null --report /dev/null ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
```
**Result:** `ulimit -s` = 8192 KB (8MB default stack per thread) vs. the crashing array's confirmed 16MB footprint at 262,144 sets — the array is **twice the size of a thread's entire default stack budget**, before any guard-page arithmetic. `ulimit -a` shows every relevant limit (`max memory size`, `virtual memory`, `data seg size`) as `unlimited` — no cgroup/ulimit memory cap exists on the `student` account, ruling out the one alternative theory raised in the debate report. The crash itself reproduced cleanly: `Segmentation fault (core dumped)`, `EXIT CODE: 139`, no glibc error text — consistent with a thread faulting into its own guard page from stack exhaustion, not an allocator refusing a request. All three checks converge on the same mechanism.

**Command (P.1):**
```bash
lscpu -e
lscpu | grep -iE "l3|numa|socket"
```
**Result:** `lscpu -e` shows a strict 1:1 NODE↔SOCKET mapping (every NODE 0 CPU is SOCKET 0, every NODE 1 CPU is SOCKET 1, 96 logical CPUs per node = 48 cores × 2 SMT threads) and a single shared L3 index per socket — two independent structural confirmations that Sub-NUMA Clustering is **not** enabled. `lscpu` confirms `L3 cache: 210 MiB (2 instances)` directly — **105 MiB per socket**, exactly matching the spec-sheet calculation every prior benchmark implicitly assumed, now confirmed on the real machine instead of assumed.

**Command (S3.0 — the fix):** `plan_paper/scripts/s3_0_heap_fix_patch.py`, applied against the currently-committed `classify.cc` (`75f908e`/`safe/S2.4`) from `~/tools/kraken2-src-fresh/src`:
```bash
cp classify.cc classify.cc.pre-s3.0.bak
python3 /tmp/s3_0_heap_fix_patch.py        # "patched OK"
diff classify.cc.pre-s3.0.bak classify.cc  # confirmed only the intended 4 hunks changed
cd .. && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s2 && cd src   # default 4,096-set rebuild
```
**Why this patch:** converts `s2_cache`/`s2_next_way` from file-scope `thread_local` arrays (placed in glibc's static TLS block, competing directly with each new thread's stack budget per P.0's confirmed mechanism) to `thread_local unique_ptr`s pointing at heap-allocated arrays, lazily initialized per thread via a new `S2EnsureInit()` helper. Required flattening `S2Lookup`/`S2Insert`'s indexing from 2D (`s2_cache[set_idx][way]`) to 1D (`s2_cache[set_idx * S2_WAYS + way]`) since `unique_ptr<S2Entry[]>` isn't a 2D array. Deliberately scoped to the crash only — does **not** address the separate slowdown cliff at ≥1,048,576 sets (the eager first-touch cost of writing non-zero sentinels into every entry), which stays open per the debate report's Q1.

**Correctness check:**
```bash
~/tools/kraken2-fresh-bin-s2/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 1 --output ~/correctness_check/s2_heapfix_output.txt --report ~/correctness_check/s2_heapfix_report.txt \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
diff ~/correctness_check/s0_output.txt ~/correctness_check/s2_heapfix_output.txt   # OUTPUT IDENTICAL
diff ~/correctness_check/s0_report.txt ~/correctness_check/s2_heapfix_report.txt   # REPORT IDENTICAL
```
**Result:** both diffs empty — classification output and report are byte-for-byte identical to the S0 (no-cache) reference at the default 4,096-set config. The 2D→1D indexing change introduced no correctness regression.

**Crash-fix confirmation (temporary 262,144-set build, same technique as the 2026-08-26 size-sweep binaries):**
```bash
cp classify.cc classify.cc.s3.0-4096.bak
sed -i "s/static const size_t S2_NUM_SETS = 4096;/static const size_t S2_NUM_SETS = 262144;/" classify.cc
cd .. && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s3-0-262144 && cd src
# then re-ran the P.0 crash-reproduction command at 16T, 32T, and 96T against this binary
cp classify.cc.s3.0-4096.bak classify.cc   # restored to the real, permanent (4,096-set, heap-fixed) state
```
**Result:** **crash-free at every thread count tested** — 16T (0.511s), 32T (0.500s), 96T (0.515s), all exit code 0, all reporting the identical 25,645/30,378 classified — where the pre-fix binary segfaulted (exit 139) at every one of these thread counts on 2026-08-26. **S3.0 is done: the crash is fixed, correctness is unchanged, and the fix is isolated from the still-open slowdown cliff.** Committed and tagged on `~/tools/kraken2-src-fresh` as `safe/S3.0` (`c2981a7`, detached HEAD off `v2.17.1`, same tag-checkpoint pattern as `safe/S1.2`→`safe/S2.4` — this repo has never used a branch for real checkpoints, tags are the intentional persistence mechanism).

**Command (S3.1/S3.2 — the sizing formula):** `plan_paper/scripts/s3_1_s3_2_sizing_formula_patch.py`, applied against the S3.0-patched `classify.cc`:
```bash
cp classify.cc classify.cc.pre-s3.1-3.2.bak
python3 /tmp/s3_1_s3_2_sizing_formula_patch.py        # "patched OK"
diff classify.cc.pre-s3.1-3.2.bak classify.cc          # confirmed only the intended hunks changed
cd .. && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s2 && cd src
```
**Why this patch:** replaces the hardcoded `S2_NUM_SETS = 4096` with `N_sets(T) = floor_pow2(f × 105MiB / (4 ways × 16B × T))`, clamped to `[4096, 262144]`, computed once per thread inside `S2EnsureInit()` via a new `S3ComputeNumSets()` helper. `LLC_per_socket = 105MiB` uses today's `lscpu`-confirmed number directly (no longer the spec-sheet-derived assumption). `T` is read live via `omp_get_num_threads()` from inside the active classification parallel region — `Options.num_threads` is passed to `omp_set_num_threads()` before that region starts (`classify.cc:270`), so this correctly reflects `--threads N` without threading `opts` through `S2Lookup`/`S2Insert`'s signatures. `f = 0.25` is an interim placeholder, **not yet empirically resolved** — chosen because it lands at exactly 262,144 sets (S3.0's confirmed ceiling) at T=1 and exactly 4,096 sets (this project's long-validated size) at T=96, a sane range, not a claim that 0.25 is correct. `S2SetIndex`'s bitmask changed from the removed compile-time constant to the new `thread_local s2_num_sets` variable.

**A paste-corruption near-miss, worth logging:** the first attempt to get this ~130-line script onto Luna via a raw heredoc paste got silently scrambled mid-transit (several lines merged into one garbled line) — caught before running anything by inspecting the pasted terminal output, not by a build failure. Recovered by base64-encoding the script into a 97-line, special-character-free block, heredoc'ing *that* instead, decoding locally, and verifying the decoded file's SHA-256 against the hash of the file actually committed to GitHub before running it. The patch itself was also dry-run locally against a reconstructed copy of the live file before ever being sent to Luna. Worth repeating for any future patch of comparable length.

**Correctness + crash/consistency check:**
```bash
~/tools/kraken2-fresh-bin-s2/kraken2 --db ~/AccuracyDrift/databases/sample_targeted \
  --threads 1 --output ~/correctness_check/s3_formula_output.txt --report ~/correctness_check/s3_formula_report.txt \
  ~/data/basecalled/hac/FBE01990_24778b97_03e50f91_15.fastq
diff ~/correctness_check/s0_output.txt ~/correctness_check/s3_formula_output.txt   # OUTPUT IDENTICAL
diff ~/correctness_check/s0_report.txt ~/correctness_check/s3_formula_report.txt   # REPORT IDENTICAL
# then 16T/32T/96T sanity runs against the same DB/fastq
```
**Result:** byte-identical output/report vs. S0 at T=1 (now sized at 262,144 sets under the new formula — much larger than the old 4,096 default, expected and correct, since fewer threads means more LLC budget per thread). Crash-free and classification-consistent (`25,645`/`30,378` every time) at 16T (16,384 sets), 32T (8,192 sets), and 96T (4,096 sets) — confirming the formula both computes sane values and shrinks correctly as thread count rises, with no correctness regression at any tested T. **S3.1/S3.2's formula is implemented and verified.** Committed and tagged as `safe/S3.1-S3.2` (`f686002`). Still open: S3.2's real empirical sweep of `f` against benchmark hit-rate data (today's 0.25 is a placeholder), and S3.3's pre-touch experiment for the separate slowdown cliff at ≥1,048,576 sets.

**Command (S3.3 — zero-sentinel + calloc, for the separate slowdown cliff):** `plan_paper/scripts/s3_3_zero_sentinel_calloc_patch.py`, applied against the S3.1/S3.2-patched `classify.cc`:
```bash
cp classify.cc classify.cc.pre-s3.3.bak
python3 /tmp/s3_3_zero_sentinel_calloc_patch.py        # "patched OK"
diff classify.cc.pre-s3.3.bak classify.cc              # confirmed only the intended hunks changed
cd .. && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s2 && cd src
```
**Why this patch:** `S2Entry`'s sentinels (`tag=UINT64_MAX`, `taxon=TAXID_MAX`) forced a real constructor loop to eagerly write every entry on allocation, defeating the OS's normal lazy-zero-page optimization regardless of where the array lived — this, not the array's storage location, is what caused the ≥1,048,576-set slowdown cliff. Fix: `S2_EMPTY_TAG` changed to `0`, `S2Entry`'s default member initializers removed (making it trivially constructible), and the allocator switched from `new[]` to `calloc` via a custom `free()`-based `unique_ptr` deleter (`S2FreeDeleter`) — for allocations above glibc's ~128KB mmap threshold (true for every size in `[4096, 262144]`, even the smallest), `calloc`'s backing pages are OS-zero-filled for free, never eagerly touched. A real minimizer of exactly `0` is handled as a permanent, harmless cache-miss special case in `S2Lookup`/`S2Insert` (never cached, always falls through to `hash->Get()`; correctness is unaffected). `S3_MAX_SETS` deliberately left at 262,144 in this patch, not raised.

**Verification, in order:** (1) a standalone compile-and-run harness, isolated from the full Kraken2 codebase (not just a text diff) — confirmed freshly-`calloc`'d memory reads as empty before any insert, insert/lookup round-trips correctly, the minimizer==0 edge case never corrupts state, `sizeof(S2Entry)` unchanged at 16 bytes, zero compiler warnings under `-Wall -std=c++11`. (2) On Luna: byte-identical `--output`/`--report` vs. S0 at the default 4,096 sets. (3) Crash-free and classification-consistent at 16T/32T/96T.

**Proving the actual slowdown-cliff fix — a temporary forced-4,194,304-set build (same technique as every prior size test), and a real, honest correction to the record:**
```bash
cp classify.cc.s3.3-4096.bak classify.cc   # (real state already patched with S3.3)
sed -i "s/static const size_t S3_MAX_SETS = 262144;/static const size_t S3_MAX_SETS = 4194304;/" classify.cc
sed -i "s/static const size_t S3_MIN_SETS = 4096;/static const size_t S3_MIN_SETS = 4194304;/" classify.cc
cd .. && ./install_kraken2.sh ~/tools/kraken2-fresh-bin-s3-3-4194304 && cd src
# separately, from classify.cc.pre-s3.3.bak (S3.0+S3.1/S3.2 but WITHOUT S3.3), same sed, built as
# kraken2-fresh-bin-s3-2-old-4194304 - isolates S3.3 as the only variable, unlike the original
# 2026-08-26 binary which also lacked S3.0's heap fix and S3.1/S3.2's formula
```
Correctness re-confirmed at this forced size: byte-identical `--output`/`--report` vs. S0.

Then an interleaved (old→new→old→new) same-session comparison at `sample_targeted`/96T/4,194,304 sets, `perf stat` on both binaries:

| | Wall-clock | Cache-miss | sys time |
|---|---|---|---|
| OLD (S3.0+S3.1/S3.2, no S3.3), 2 runs | 1.181s / 1.184s | 41.72% / 43.15% | 4.85s / 5.32s |
| NEW (+S3.3), 2 runs | 0.609s / 0.619s | 14.69% / 14.75% | 0.75s / 0.97s |

**Real finding, tightly reproducible across both runs of each:** S3.3 delivers a genuine, real **~2× wall-clock and ~3× cache-miss improvement** on top of S3.0+S3.1/S3.2. **But this corrects the original 2026-08-26 framing, not just extends it:** today's "OLD" baseline (~1.18s) is nowhere near the originally-logged 12.51s/85%-LLC-miss, because that measurement was taken on the *pre-S3.0* binary — a `thread_local` **static array** embedded directly in glibc's TLS block, not a heap-allocated array. **S3.0's heap-pointer fix alone already eliminated the vast majority of the originally-measured slowdown** — a giant static-TLS array apparently has its own, more severe per-thread-creation cost (likely glibc copying a full TLS initialization template into every new thread) distinct from and worse than plain eager-write cost. The dramatically elevated `sys` time on the OLD-here run (4.85–5.32s vs. 0.75–0.97s) — kernel time, consistent with page-fault servicing — independently corroborates this. **Honest framing for any write-up: S3.0 was the dominant fix for both the crash and most of the slowdown; S3.3 is a smaller, still-real, still-worth-keeping additional win, not an independently-comparable second fix stacking to the original 22×.**

**S3.3 is done, verified, and committed+tagged on Luna as `safe/S3.3` (`b8c1ee0`).** S3 (sizing) is now feature-complete per this week's scope: S3.0 (crash fix) + S3.1/S3.2 (LLC-topology-aware, thread-scaled formula) + S3.3 (residual-slowdown fix). Still open: S3.2's empirical sweep of `f` (currently 0.25, a placeholder) and S3.4's full DB×thread-count benchmark of the final wired-up formula against plain S2 — next up, per the user's suggestion, as a proper orchestration script (matching this project's `compare_*.py` convention) rather than by-hand runs, covering all 3 DBs and a fuller thread-count sweep.
