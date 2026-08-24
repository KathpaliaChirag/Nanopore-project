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
