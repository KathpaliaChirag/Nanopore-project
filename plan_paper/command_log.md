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
