# Centrifuge — Command Log

Every command run for the Centrifuge baseline, in the order it was run. One entry per command: why we ran it, the command itself, and what happened. Analysis and decisions belong in `observations.md`, not here — this file is just the record.

---

### [Storage 1] Check overall disk usage on Luna
**Why:** baseline free space before Centrifuge's build, index, and any re-fetched taxonomy data start consuming disk.
**Machine:** Luna (`student@dell-R760`)
```bash
df -h
```
**Result:**
```
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda3       938G  742G  149G  84% /
```
(other mounts are tmpfs/efi, not relevant to storage planning) — 149 GB free, 84% used.

---

### [Storage 2] Check student home folder total usage
**Why:** the 742 GB used on `/` is shared across all accounts on Luna — need to know how much of it is actually ours.
**Machine:** Luna (`student@dell-R760`)
```bash
du -sh ~ 2>/dev/null
```
**Result:**
```
315G    /home/student
```
315 GB of the machine's 742 GB used belongs to `student`.

---

### [Storage 3] Break down student home folder by subdirectory
**Why:** find which folders are actually worth cleaning before deleting anything.
**Machine:** Luna (`student@dell-R760`)
```bash
du -h --max-depth=1 ~ 2>/dev/null | sort -rh
```
**Result:**
```
315G    /home/student
138G    /home/student/AccuracyDrift
111G    /home/student/data
51G     /home/student/results
6.1G    /home/student/snn
5.2G    /home/student/tools
3.2G    /home/student/.cache
467M    /home/student/.local
302M    /home/student/dna_r10.4.1_e8.2_400bps_sup@v5.2.0
34M     /home/student/dna_r10.4.1_e8.2_400bps_hac@v5.2.0
27M     /home/student/.debug
11M x4  /home/student/.tmp_pod5_v3_v4_migration_*  (4 folders)
5.7M    /home/student/matmul_gpu
1.8M    /home/student/dna_r10.4.1_e8.2_400bps_fast@v5.2.0
800K    /home/student/matmul
```
Top-level `ls` also showed two loose tarballs not covered by the `du` breakdown above (files, not dirs): `kraken_runs_small.tar.gz`, `runs_txt_only.tar.gz`.

---

### [Storage 4] Break down ~/data, the biggest unexplained folder
**Why:** CLAUDE.md only documents an 8 GB Kraken2 DB inside `~/data/kraken2_db/`, but the folder is 111 GB total.
**Machine:** Luna (`student@dell-R760`)
```bash
du -h --max-depth=1 ~/data 2>/dev/null | sort -rh
```
**Result:**
```
111G    /home/student/data
66G     /home/student/data/pod5
36G     /home/student/data/basecalled
9.4G    /home/student/data/kraken_runs
302M x2 /home/student/data/.temp_dorado_model-*  (2 folders)
34M  x3 /home/student/data/.temp_dorado_model-*  (3 folders)
1.8M x3 /home/student/data/.temp_dorado_model-*  (3 folders)
4.0K    /home/student/data/.temp_dorado_model-bb94e7d9e08a08ab
15M+11M /home/student/data/.tmp_pod5_v3_v4_migration_*  (2 folders)
```
`.temp_dorado_model-*` folders total ≈ 740M; `.tmp_pod5_v3_v4_migration_*` here total ≈ 26M.

---

**Decision:** leave all found temp-folder junk (~810M total) in place for now — 149 GB free is enough headroom. Revisit only if space gets tight. `AccuracyDrift/` breakdown and the two loose tarballs not investigated further — resuming Step 1 build.

---

## Step 1 — Install and build Centrifuge on Luna

### [1.1] Clone Centrifuge source
**Why:** everything else (build, PATH, index) depends on the source tree existing on Luna.
**Machine:** Luna (`student@dell-R760`, run from `~`)
```bash
git clone https://github.com/DaehwanKimLab/centrifuge
```
**Result:** Success. 2105 objects, 6.39 MiB, no errors. Repo now at `~/centrifuge`.

---

### [1.2] Build Centrifuge
**Why:** compile the five binaries needed to run Centrifuge — no install step, they land straight in the repo folder.
**Machine:** Luna (`student@dell-R760`, run from `~/centrifuge`)
```bash
cd centrifuge && make
```
**Result:** Success, no errors. g++ (`-O3 -m64 -msse2 -funroll-loops -g3 -std=c++11`) compiled `centrifuge-build-bin`, `centrifuge-class`, `centrifuge-inspect-bin`. Only warnings surfaced: deprecated `std::auto_ptr` usage and signed/unsigned comparison warnings — both harmless, pre-existing code style issues flagged by a newer GCC, not build blockers. Confirms Luna's GCC version builds this cleanly (the open risk flagged in the Week 1 plan).

### [Version check] Confirm we're on the latest Centrifuge code
**Why:** CK asked to confirm we're not building an outdated version.
**How:** checked GitHub's public API directly (no Luna command needed) — not logged as a Luna step, done from the local machine.
**Result:** Latest tagged release is `v1.0.4.2`. Our `git clone` grabbed the tip of `master` (default branch, last pushed 2026-04-15), which defines `CENTRIFUGE_VERSION="1.0.5"` — a version bump ahead of the last official tag. We're on the most current code available, not behind.

### [1.3] Verify all binaries built
**Why:** confirm all 5 expected executables exist before moving to PATH setup.
**Machine:** Luna (`student@dell-R760`, run from `~/centrifuge`)
```bash
ls -la ~/centrifuge/centrifuge*
```
**Result:** All 5 present and executable: `centrifuge`, `centrifuge-build` (wrapper script → `centrifuge-build-bin`), `centrifuge-class`, `centrifuge-inspect` (wrapper script → `centrifuge-inspect-bin`), `centrifuge-download`. Build fully succeeded.

### [1.4] Move to ~/tools/ and add to PATH (session-only)
**Why:** match how Kraken2 is already organized (`~/tools/kraken2/`), and let `centrifuge` be callable by name instead of full path.
**Machine:** Luna (`student@dell-R760`)
```bash
mkdir -p ~/tools && mv ~/centrifuge ~/tools/centrifuge && export PATH=$PATH:~/tools/centrifuge
```
**Result:** Success, no output (expected — none of these three commands print on success). Note: shell was sitting inside `~/centrifuge` when it got moved; prompt still displays the old path but the directory now only exists at `~/tools/centrifuge`. Harmless, but use the new path going forward. PATH change is session-only so far — not yet persisted to `.bashrc`.

### [1.5] Persist PATH in .bashrc + verify
**Why:** make the PATH change permanent across logins, and confirm the shell can actually resolve `centrifuge` by name.
**Machine:** Luna (`student@dell-R760`)
```bash
echo 'export PATH=$PATH:~/tools/centrifuge' >> ~/.bashrc && source ~/.bashrc && which centrifuge
```
**Result:** `/home/student/tools/centrifuge/centrifuge` — exactly as expected. **Step 1 complete: Centrifuge is built, in `~/tools/centrifuge/`, and permanently on PATH.**

---

## Step 3 — Build a Centrifuge index from the ESKAPE genomes

### [3.1] Locate ESKAPE genome files and taxonomy folder
**Why:** need to know where the ~1149 `.fna` files live before concatenating them, and whether the taxonomy folder (`nodes.dmp`/`names.dmp`) survived Kraken2's build cleanup or needs re-fetching.
**Machine:** Luna (`student@dell-R760`)
```bash
find ~ -maxdepth 3 -iname "eskape_genomes*" -o -iname "taxonomy" 2>/dev/null
```
**Result:** Empty — neither found within 3 levels of home. Need to search deeper / check actual `AccuracyDrift/databases/` layout directly.

### [3.2] Check actual AccuracyDrift/databases/ layout + count .fna files machine-wide
**Why:** confirm what's actually on disk vs what the plan assumes is there.
**Machine:** Luna (`student@dell-R760`)
```bash
ls -la ~/AccuracyDrift/databases/ && find ~ -name "*.fna" 2>/dev/null | wc -l && find ~ -name "*.fna" 2>/dev/null | head -5
```
**Result:**
```
~/AccuracyDrift/databases/ contains:
  eskape_650mb_build.log   (log only, no eskape_650mb/ folder)
  eskape_human_4gb_build.log (log only, no eskape_human_4gb/ folder)
  human_download.log
  pluspf_103gb/
  sample_targeted/
  standard_16gb/
  standard_8gb/
```
Machine-wide `.fna` count: **12 total**, all under `sample_targeted/library/added/`.

**FLAG — real blocker, not a dead end:** the `eskape_650mb` and `eskape_human_4gb` database folders (genome library + built `.k2d` files) are gone from `AccuracyDrift/databases/` — only their build logs remain. Only 12 `.fna` files exist machine-wide, all belonging to the small 50MB `sample_targeted` demo DB, not the ~1149-file ESKAPE set the Week 1 plan assumes is still on disk. Needs investigation before Step 3 can proceed as written.

### [3.3] Machine-wide search for any eskape backup + inspect the two loose tarballs
**Why:** rule out a backup/archive existing somewhere before concluding the genome data must be re-downloaded from scratch.
**Machine:** Luna (`student@dell-R760`)
```bash
find / -iname "*eskape*" 2>/dev/null | grep -v "Permission denied"
tar -tzf ~/kraken_runs_small.tar.gz 2>/dev/null | head -20
tar -tzf ~/runs_txt_only.tar.gz 2>/dev/null | head -20
```
**Result:** Every "eskape" hit machine-wide is a run-result text file (`.../AccuracyDrift/runs/*.txt`, `.../AccuracyDrift/reports/*.txt` — perf/report/output logs from prior benchmark runs) or the two build logs already known about. Both tarballs contain only similar perf/report/output logs (`sup/`, `pluspf_103gb`, `sample_targeted`, etc. — pre-existing benchmark data), not genome files or database files. **Confirmed: no backup of the eskape_650mb/eskape_human_4gb genome library or built databases exists anywhere on this machine.**

**Root cause (read locally from `AccuracyDrift/README.md`, not a Luna command):** documented build script unconditionally `rm -rf eskape_genomes` after both DBs build (expected) — but the actual top-level `eskape_650mb/`/`eskape_human_4gb/` DB folders (with `hash.k2d`/`taxo.k2d`/`opts.k2d`) are ALSO gone, which that script never does. Full analysis in `observations.md`. Decision: re-download genomes via `ncbi-genome-download`, keep `eskape_genomes/` this time (Centrifuge needs it, unlike the Kraken2-only script).

### [3.4] Confirm ncbi-genome-download is already installed
**Why:** avoid reinstalling if it survived from the original build.
**Machine:** Luna (`student@dell-R760`)
```bash
~/.local/bin/ncbi-genome-download --version 2>&1 || echo "NOT INSTALLED"
```
**Result:** `0.3.3` — already installed, no action needed.

### [3.5] First download attempt — too slow, killed
**Why:** started the documented re-download command (no parallelism flag, default serial).
**Machine:** Luna (`student@dell-R760`)
```bash
mkdir -p ~/AccuracyDrift/databases/eskape_genomes && cd ~/AccuracyDrift/databases && ~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose
```
**Result:** After ~1 hour, only ~25 MB downloaded (target ~7 GB). Process alive (PID 281594, 5:52 CPU time) but effectively crawling — `ncbi-genome-download` defaults to serial (1 assembly at a time), and with ~1149 assemblies each needing multiple round-trips to NCBI, that's untenably slow. Killed:
```bash
kill 281594 && sleep 2 && ps aux | grep -i genome-download | grep -v grep
```
Confirmed dead (no process listed).

### [3.6] Restart with parallel downloads, detached
**Why:** `-p 25` runs 25 assemblies concurrently instead of 1 (CK chose 25 over the suggested 10/20 — more aggressive, still below where NCBI is likely to start throttling). `nohup ... & disown` detaches it from the shell so it survives even without tmux — closing the terminal won't kill it.
**Machine:** Luna (`student@dell-R760`)
```bash
rm -rf ~/AccuracyDrift/databases/eskape_genomes && mkdir -p ~/AccuracyDrift/databases/eskape_genomes && cd ~/AccuracyDrift/databases && nohup ~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose -p 25 > eskape_download.log 2>&1 & disown
```
**Result:** `[1] 284880` — job started, detached, running in background. Output going to `~/AccuracyDrift/databases/eskape_download.log`.

### [3.7] First health check on the parallel download
**Why:** confirm -p 25 actually spawned parallel workers and isn't silently still serial.
**Machine:** Luna (`student@dell-R760`)
```bash
du -sh ~/AccuracyDrift/databases/eskape_genomes 2>/dev/null && ps aux | grep -i genome-download | grep -v grep && tail -20 ~/AccuracyDrift/databases/eskape_download.log
```
**Result:** 34M so far. Confirmed **25 active worker processes** (PIDs 284883-284908, each ~13% CPU) — real parallelism this time, not serial. Log shows repeated `ERROR: No entry for file ending in '_genomic.fna.gz'` for some records — expected/benign, some NCBI assembly entries don't ship a genomic FASTA; tool skips and continues. Final assembly count may land a bit under 1149 because of this, not a failure.

### [3.8] Second health check — download had already stopped
**Why:** routine re-check, same command as 3.7.
**Machine:** Luna (`student@dell-R760`)
```bash
du -sh ~/AccuracyDrift/databases/eskape_genomes 2>/dev/null && ps aux | grep -i genome-download | grep -v grep && tail -20 ~/AccuracyDrift/databases/eskape_download.log
```
**Result:** 64M, but `ps` returned **no processes at all** — the job had already exited on its own between checks. Needed the log tail to find out why.

### [3.9] Diagnose why the download stopped
**Why:** 64 MB is far short of the ~7 GB target; needed to know if it finished or crashed.
**Machine:** Luna (`student@dell-R760`)
```bash
tail -60 ~/AccuracyDrift/databases/eskape_download.log && find ~/AccuracyDrift/databases/eskape_genomes -name "*.fna.gz" -o -name "*.fna" | wc -l
```
**Result:** Dozens of `ERROR: Checksum mismatch` lines, every single one reporting the **identical** `got` MD5 (`14aa54cecceebc1536a4d1ee4a5c08ec`) regardless of which assembly/expected checksum. That means every failed download received byte-for-byte identical content — almost certainly a generic NCBI rate-limit/error response, not real genome data. **`-p 25` triggered exactly the throttling risk flagged before choosing it**, just partway through the run rather than immediately. Only **200 `.fna`/`.fna.gz` files** landed successfully out of the ~1149 target. `ncbi-genome-download`'s own checksum verification correctly caught and rejected the bad downloads — no corrupt data got kept, but a large fraction of the run failed as a result.

---

## Fast path — Centrifuge index from sample_targeted (while big download runs in background)

### [FastPath.1] Inspect sample_targeted's surviving files
**Why:** unlike eskape_650mb/eskape_human_4gb, this DB folder wasn't cleaned up — check what's actually reusable before assuming we need to regenerate anything.
**Machine:** Luna (`student@dell-R760`)
```bash
ls -la ~/AccuracyDrift/databases/sample_targeted/ && ls -la ~/AccuracyDrift/databases/sample_targeted/library/added/ 2>/dev/null && ls -la ~/AccuracyDrift/databases/sample_targeted/taxonomy 2>/dev/null
```
**Result:** `hash.k2d`/`taxo.k2d`/`opts.k2d`, `seqid2taxid.map` (329B), and full `taxonomy/` (`nodes.dmp`, `names.dmp`, etc.) all intact. `library/added/` has 12 `.fna` files (6 `GCF_`-named + 6 randomly-named, e.g. `0GY9zJXjkl.fna`), each pair near-identical in size.

### [FastPath.2] Disambiguate which 6 genomes are the real reference set
**Why:** `prelim_map.txt` and `seqid2taxid.map` are auto-generated by kraken2-build from the files actually used — reading them tells us definitively which 6 files are real vs. duplicate, instead of guessing from filenames.
**Machine:** Luna (`student@dell-R760`)
```bash
cat ~/AccuracyDrift/databases/sample_targeted/library/added/prelim_map.txt && cat ~/AccuracyDrift/databases/sample_targeted/seqid2taxid.map
```
**Result:** 17 sequences across exactly 6 taxids (511145, 208964, 93061, 716541, 1125630, 333849 — matching the 6 ESKAPE species). File-size pairing confirms the 6 `GCF_`-named files are the real reference genomes; the 6 randomly-named files are unrelated duplicates to exclude. Full breakdown in `observations.md`. **Decision: reuse `seqid2taxid.map` + `taxonomy/` as-is, concatenate only the 6 `GCF_` files, skip `centrifuge-download` entirely for this fast path.**

### [FastPath.3] Retry big download at -p 8 (detached), concatenate + verify sample_targeted headers
**Why (retry):** give NCBI a safer parallelism after the -p 25 throttling; re-running is safe since ncbi-genome-download skips already-good files by checksum.
**Why (fast path):** concatenate the 6 real genomes into one FASTA, then confirm every header actually has a taxid match before trusting it (plan's own warning — Centrifuge silently drops unmapped sequences).
**Machine:** Luna (`student@dell-R760`)
```bash
# Retry (separate terminal/background)
cd ~/AccuracyDrift/databases && nohup ~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose -p 8 > eskape_download2.log 2>&1 & disown

# Fast path
cd ~/AccuracyDrift/databases/sample_targeted/library/added && \
cat GCF_000005845.2_ASM584v2_genomic.fna GCF_000006765.1_ASM676v1_genomic.fna GCF_000013425.1_ASM1342v1_genomic.fna GCF_000025565.1_ASM2556v1_genomic.fna GCF_000174395.2_ASM17439v2_genomic.fna GCF_000240185.1_ASM24018v2_genomic.fna > ~/AccuracyDrift/databases/sample_targeted_combined.fasta && \
grep ">" ~/AccuracyDrift/databases/sample_targeted_combined.fasta | cut -d' ' -f1 | tr -d '>' | sort -u > ~/headers.txt && \
cut -f1 ~/AccuracyDrift/databases/sample_targeted/seqid2taxid.map | sort -u > ~/mapped.txt && \
diff ~/headers.txt ~/mapped.txt && echo "CLEAN: all headers mapped"
```
**Result (fast path):** `CLEAN: all headers mapped` — no diff output, every sequence header matches a taxid entry. `sample_targeted_combined.fasta` ready for `centrifuge-build`. (Retry download result pending, checked separately.)

### [FastPath.4] First centrifuge-build attempt — failed, missing `python`
**Why:** actually build the index.
**Machine:** Luna (`student@dell-R760`)
```bash
~/tools/centrifuge/centrifuge-build --conversion-table ~/AccuracyDrift/databases/sample_targeted/seqid2taxid.map \
  --taxonomy-tree ~/AccuracyDrift/databases/sample_targeted/taxonomy/nodes.dmp \
  --name-table ~/AccuracyDrift/databases/sample_targeted/taxonomy/names.dmp \
  ~/AccuracyDrift/databases/sample_targeted_combined.fasta \
  ~/AccuracyDrift/databases/centrifuge_sample_targeted/cf_base
```
**Result:** `/usr/bin/env: 'python': No such file or directory`. Checked the wrapper's shebang (`head -5 ~/tools/centrifuge/centrifuge-build`): `#!/usr/bin/env python` — Luna only has `python3`, no plain `python` symlink (common on newer Debian/Ubuntu).

### [FastPath.5] Fix: symlink python -> python3, retry build
**Why:** `centrifuge-build` is a Python wrapper script; `env` needs `python` resolvable on PATH. User-local fix, no root needed.
**Machine:** Luna (`student@dell-R760`)
```bash
mkdir -p ~/.local/bin && ln -sf /usr/bin/python3 ~/.local/bin/python && echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && export PATH="$HOME/.local/bin:$PATH" && which python && \
~/tools/centrifuge/centrifuge-build --conversion-table ~/AccuracyDrift/databases/sample_targeted/seqid2taxid.map \
  --taxonomy-tree ~/AccuracyDrift/databases/sample_targeted/taxonomy/nodes.dmp \
  --name-table ~/AccuracyDrift/databases/sample_targeted/taxonomy/names.dmp \
  ~/AccuracyDrift/databases/sample_targeted_combined.fasta \
  ~/AccuracyDrift/databases/centrifuge_sample_targeted/cf_base
```
**Result:** SUCCESS. `which python` → `/home/student/.local/bin/python`. Build completed in **12 seconds** (`Total time for call to driver() for forward index: 00:00:12`). Wrote `cf_base.1.cf` (17,744,597 bytes) and `cf_base.2.cf` (3,507,644 bytes) to `~/AccuracyDrift/databases/centrifuge_sample_targeted/`. **First Centrifuge index ever built in this project.**

### [FastPath.6] Verify all 4 index files exist
**Why:** confirm the build produced everything Centrifuge needs to classify with (not just the 2 files mentioned in the driver's forward-index summary).
**Machine:** Luna (`student@dell-R760`)
```bash
ls -la ~/AccuracyDrift/databases/centrifuge_sample_targeted/
```
**Result:** All 4 present: `cf_base.1.cf` (17.7M), `cf_base.2.cf` (3.5M), `cf_base.3.cf` (2.4K), `cf_base.4.cf` (216B) — ~20.3 MB total. **Step 3 (fast path) complete.**

### [3.10] Second download attempt (-p 8) also stopped — checked size only, log check pending
**Why:** routine check while confirming the index build.
**Machine:** Luna (`student@dell-R760`)
```bash
du -sh ~/AccuracyDrift/databases/eskape_genomes 2>/dev/null && ps aux | grep -i genome-download | grep -v grep && tail -10 ~/AccuracyDrift/databases/eskape_download2.log
```
**Result:** 357M (up from 64M — real progress). `ps` found no process again (chain short-circuited before the `tail`, so log wasn't seen yet) — needs a follow-up check.

### [3.11] Check second attempt's log directly
**Why:** find out if -p 8 actually did better, or hit the same wall.
**Machine:** Luna (`student@dell-R760`)
```bash
tail -30 ~/AccuracyDrift/databases/eskape_download2.log && find ~/AccuracyDrift/databases/eskape_genomes -name "*.fna.gz" -o -name "*.fna" | wc -l
```
**Result:** Same two error types as before — benign `No entry for file ending in '_genomic.fna.gz'` (some records genuinely lack this file) mixed with the same **identical-MD5 checksum mismatches** (`got '14aa54cecceebc1536a4d1ee4a5c08ec'`, unchanged from the first attempt). **`.fna` count is still exactly 200** — no growth at all despite folder size growing to 357M and a much lower parallelism. This weakens the pure-concurrency theory: a request-count-based rate limit (or network-level block) that the first attempt already tripped, inherited by the retry, fits better than "too many simultaneous connections."

### [3.12] Diagnostic curl tests + root cause found: missing proxy config
**Why:** determine whether this is NCBI-side throttling or a Luna-side network issue.
**Machine:** Luna (`student@dell-R760`)
```bash
# test 1 (URL built wrong - missing a path segment)
curl -sI "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/045/690/395/GCF_045690395.1_ASM4569039v1_genomic.fna.gz"
# -> proxy CONNECT tunnel shown, then real 404 from NCBI (fast)

# test 2 (corrected URL, verbose)
curl -v "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/045/690/395/GCF_045690395.1_ASM4569039v1/GCF_045690395.1_ASM4569039v1_genomic.fna.gz" -o ~/test_dl.gz
# -> IPv6 "Network unreachable", IPv4 hung 3.5 min then timed out. No proxy tunnel line this time.

# checked for proxy env vars - none set anywhere
echo "http_proxy=$http_proxy"; cat /etc/environment
```
**Result:** No proxy configured anywhere in the shell, yet behavior was proxy-tunnel-shaped on one test and direct-connection-hung on another. **CK identified the actual root cause: IIT Delhi's institutional proxy (`proxy62.iitd.ac.in:3128`) was never set.** Luna needs BOTH an authenticated network login (`tmux` + `~/iitd-login.py`) AND these proxy env vars for reliable outbound internet — documented in `dorado-kraken-research/CLAUDE.md` ("Luna internet access" section) and in persistent memory, since this is exactly the kind of gotcha that looks like a rate-limit/flaky-tool problem instead of a proxy problem.

### [3.13] Set proxy, verify the fix
**Why:** confirm the proxy actually resolves the hanging-connection symptom before retrying the big download.
**Machine:** Luna (`student@dell-R760`)
```bash
export HTTP_proxy=http://proxy62.iitd.ac.in:3128
export HTTPS_proxy=http://proxy62.iitd.ac.in:3128
export https_proxy=http://proxy62.iitd.ac.in:3128
export http_proxy=http://proxy62.iitd.ac.in:3128
# persisted to ~/.bashrc too
time curl -sI "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/045/690/395/GCF_045690395.1_ASM4569039v1/GCF_045690395.1_ASM4569039v1_genomic.fna.gz"
```
**Result:** **Confirmed fixed.** Same URL that hung for 3.5 minutes now returns real headers (`HTTP/1.1 200 OK`, correct `Content-Length: 1614736`) in **1.137 seconds**.

### [3.14] Third download attempt, proxy now active
**Why:** retry with the actual root cause fixed.
**Machine:** Luna (`student@dell-R760`)
```bash
cd ~/AccuracyDrift/databases && nohup ~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose -p 8 > eskape_download3.log 2>&1 & disown
```
**Result:** Job ran and exited on its own (15,847-line log, reached near the end of the catalog). **Zero `Checksum mismatch` errors** (`grep -c` confirms) — the proxy fix genuinely resolved the garbage-content bug. But `.fna`/`.fna.gz` count is still exactly 200, only 41 files were touched during this run, and 8221 total files exist in the folder (mostly metadata/stub files, not real genomes). The log shows `ERROR: No entry for file ending in '_genomic.fna.gz'` far more often than expected for "complete genome" RefSeq records. **New theory: `ncbi-genome-download`'s directory-listing step likely uses FTP-protocol requests separately from the HTTPS file downloads** — the HTTP-only proxy may not tunnel FTP listings correctly, causing the tool to see "no file" for assemblies that actually have one, even though direct HTTPS fetches of known filenames (our earlier `curl` test) work fine through the same proxy.

### [3.15] Checked --help, found a better explanation than the FTP theory
**Why:** verify the FTP-listing theory before acting on it.
**Machine:** Luna (`student@dell-R760`)
```bash
~/.local/bin/ncbi-genome-download --help 2>&1 | head -60
~/.local/bin/ncbi-genome-download --help 2>&1 | sed -n '60,110p'
```
**Result:** FTP theory disproven — `-u/--uri` defaults to `https://ftp.ncbi.nih.gov/genomes` (already HTTPS, not FTP). Two better findings instead: **`-r/--retries` defaults to `0`** (zero automatic retries on any transient failure), and the log's first line (`INFO: Using cached summary`) means it reused a cached copy of NCBI's genome catalog — likely cached during an earlier flaky-network attempt, before the proxy fix. A corrupted/incomplete cached catalog would explain "no entry" errors on records that actually do have files.

### [3.16] Clear stale cache, add retries, run again
**Why:** force a fresh catalog fetch now that the proxy actually works, and add resilience against any remaining transient blips.
**Machine:** Luna (`student@dell-R760`)
```bash
rm -rf ~/.cache/ncbi-genome-download && \
cd ~/AccuracyDrift/databases && nohup ~/.local/bin/ncbi-genome-download --taxids 1352,1280,573,470,287,547 --formats fasta --assembly-levels complete bacteria -o eskape_genomes --verbose -p 8 -r 3 > eskape_download4.log 2>&1 & disown
```
**Result:** `[1] 290158` — running. Without the cache, it re-fetches NCBI's full bacterial genome catalog first (large file), so expect a quiet stretch before real downloads resume — checked again after a few minutes, not immediately.

---
