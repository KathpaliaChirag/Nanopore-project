# plan_paper/ — How to Reproduce This Work on a Fresh System

This folder is where the actual build/benchmark work for the Sept 13 paper push happens. `command_log.md` is the running receipt of every command actually run (see that file for full narrative and reasoning) — this doc is the condensed "how do I actually run this" reference, for setting up on a machine that doesn't already have any of it.

## What's in here

```
plan_paper/
  README.md                          <- this file
  command_log.md                     <- the running log: every command, why, and result
  verification_audit_brief.md        <- brief for an independent multi-agent correctness audit
  patches/
    s1_thread_local_cache.diff       <- captured diff output for the S1.1 patch (documentation)
    s2_4way_associative_cache.diff   <- captured diff output for the S2 patch (documentation)
  scripts/
    s1_patch.py                      <- applies the S1.1 patch to classify.cc
    s2_patch.py                      <- applies the S2.1-S2.3 patch to classify.cc (run AFTER s1_patch.py)
    build_size_variants.sh           <- builds the 3 extra S2 cache-size binaries for the size sweep
    compare_s0_s1.py                 <- interleaved 3-run S0-vs-S1 benchmark
    compare_s0_s1_s2.py              <- interleaved 3-run S0-vs-S1-vs-S2 benchmark
    compare_sizes_full.py            <- interleaved 3-run benchmark across all 6 binaries (S0, S1, 4 S2 sizes)
```

The `.diff` files are **documentation of what changed**, captured from real `diff` command output — they're not meant to be applied with `patch`. To actually apply the changes, run the `.py` scripts against a real `classify.cc`, in order.

## Prerequisites (Luna-specific)

All of this runs on Luna (`student@luna.cse.iitd.ac.in`), a bare-metal Sapphire Rapids machine — bare Kraken2 profiling numbers are not meaningful on WSL2 or other virtualized environments (hardware counters are unreliable there). See `dorado-kraken-research/CLAUDE.md` for the full machine list and standard profiling commands this project relies on.

**Before anything that needs internet** (git clone, etc.), Luna needs two separate things active, or connections silently hang instead of failing outright:

```bash
tmux new -s freshbuild
```

Inside the tmux pane — **use `unset`, not just `env -u`**, since the proxy exports are baked into `~/.bashrc` and get auto-loaded into every new shell (confirmed the hard way — `env -u` alone does not survive that):

```bash
unset http_proxy https_proxy HTTP_proxy HTTPS_proxy
env | grep -i proxy    # must print nothing before proceeding
python3 ~/iitd-login.py -d
```

Enter your Kerberos ID/password when prompted, wait for `Logged in.`, then detach cleanly (`Ctrl+B`, `D` — never kill this session). Back in your normal shell:

```bash
export HTTP_proxy=http://proxy62.iitd.ac.in:3128
export HTTPS_proxy=http://proxy62.iitd.ac.in:3128
export https_proxy=http://proxy62.iitd.ac.in:3128
export http_proxy=http://proxy62.iitd.ac.in:3128
```

**The login session only stays alive ~100 seconds per cycle**, then the daemon auto-relogs. Any single command can land in a "dead" window by bad luck — retry real operations in a loop rather than trying to time it manually:

```bash
for i in $(seq 1 40); do
  echo "attempt $i: $(date +%T)"
  timeout 6 curl -sI https://github.com && echo "SUCCESS" && break
  sleep 3
done
```

## 1. Fresh clone

Pinned to current upstream (`v2.17.1` as of 2026-08-25 — verify this is still latest with `git tag --sort=-creatordate | head -5` before trusting it, since upstream moves):

```bash
mkdir -p ~/tools && cd ~/tools
git clone https://github.com/DerrickWood/kraken2.git kraken2-src-fresh
cd kraken2-src-fresh
git checkout v2.17.1
git log -1 --format='%H %ci' > PROVENANCE.txt

# sanity check - must print nothing. If it matches, this tree secretly
# isn't clean (e.g. accidentally cloned from a patched fork).
grep -n "MMK" src/classify.cc
```

## 2. Build the unpatched baseline (S0)

```bash
./install_kraken2.sh ~/tools/kraken2-fresh-bin-s0
```

## 3. Apply S1.1, build S1

```bash
cd src
cp classify.cc classify.cc.pre-s1.1.bak   # keep an explicit pre-patch copy
# copy plan_paper/scripts/s1_patch.py onto Luna, e.g. to /tmp/s1_patch.py
python3 /tmp/s1_patch.py
diff classify.cc.pre-s1.1.bak classify.cc   # should match patches/s1_thread_local_cache.diff
cd ..
./install_kraken2.sh ~/tools/kraken2-fresh-bin-s1
```

## 4. Apply S2, build S2 (at the default 4,096-set size)

```bash
cd src
cp classify.cc classify.cc.pre-s2.bak
# copy plan_paper/scripts/s2_patch.py onto Luna, e.g. to /tmp/s2_patch.py
python3 /tmp/s2_patch.py
diff classify.cc.pre-s2.bak classify.cc   # should match patches/s2_4way_associative_cache.diff
cd ..
./install_kraken2.sh ~/tools/kraken2-fresh-bin-s2
```

## 5. (Optional) Build the size-sweep variants

Copy `plan_paper/scripts/build_size_variants.sh` onto Luna and run it from `~/tools/kraken2-src-fresh/src` — it builds `kraken2-fresh-bin-s2-65536`, `-1048576`, and `-4194304`, then restores `classify.cc` to the 4,096-set version. Verify the restore worked before trusting the working tree:

```bash
diff classify.cc classify.cc.s2-4096.bak && echo "MATCHES - safe to commit/continue"
```

## 6. Run the benchmarks

Copy whichever comparison script you need onto Luna (e.g. `/tmp/compare_s0_s1_s2.py`) and run it directly — no arguments, all paths are hardcoded to the layout above:

```bash
python3 /tmp/compare_s0_s1_s2.py | tee ~/s0_s1_s2_3run_compare.txt
```

`compare_sizes_full.py` covers all 3 DBs × 5 thread counts × 6 binaries and takes **~80-90 minutes** — run it inside `tmux` so a dropped SSH connection doesn't kill it:

```bash
tmux new -s sizecompare
python3 /tmp/compare_sizes_full.py | tee ~/s2_size_sweep_full.txt
# Ctrl+B, D to detach; reattach later with: tmux attach -t sizecompare
```

**Every script's methodology matters, not just its output:** they interleave binaries within each cell (not run in separate blocks) specifically because an earlier, non-interleaved comparison produced a misleading result — a dramatic-looking improvement that turned out to be a page-cache warmth artifact from one binary's sweep benefiting from a prior sweep having already read the same large database file. Don't "simplify" these scripts back to sequential blocks without re-reading `command_log.md`'s explanation of why that's wrong.

## 7. Committing your own changes

`kraken2-src-fresh` is its own git repo (upstream Kraken2's history), separate from this Nanopore-project repo. Set a local identity **without `--global`** if Luna's shared `student` account doesn't have one configured yet — `--global` would affect every repo on the shared account, including anyone else's:

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
git add src/classify.cc
git commit -m "..."
git tag safe/<step-id>   # e.g. safe/S1.2 - matches this project's safe-zone ledger convention
```

## Known gaps as of 2026-08-26 (check `command_log.md` for current status)

- All benchmarking so far used `--output /dev/null --report /dev/null` — classification **correctness** (do S1/S2 produce identical species calls to stock Kraken2?) has not yet been empirically verified, only performance.
- S2's patch was applied and measured but, as of this writing, had not yet been committed/tagged in `kraken2-src-fresh` (S1's was: commit `fbf993d`, tag `safe/S1.2`).
