# MTP Week 2 — Command Log

Running command-by-command log for executing `mtpweek2.md` on Luna (and Orion once reached): installing Metabuli and Centrifuger, building ESKAPE indexes, and classifying reads. Written 2026-08-10, day 1 of the week's schedule. Every command below was run individually by CK in their own SSH session, explained before running, verified after — same convention as `Luna/experiments/patch/commands_log.md`.

---

### 1
```bash
tmux ls 2>&1; echo ---; grep -c proxy62 ~/.bashrc 2>/dev/null; echo ---; echo $http_proxy
```
**Why:** check Luna's two-part internet-access requirement (tmux-resident login daemon + proxy env vars) before attempting any install, per `dorado-kraken-research/CLAUDE.md`'s documented gotcha.
**Result:** 19 old tmux sessions present (dating back to May 2026), `proxy62` found 4 times in `.bashrc`, `$http_proxy` already set to `http://proxy62.iitd.ac.in:3128`.
**Finding:** proxy env vars already persisted from a previous session. Internet-access state unconfirmed pending an actual connectivity test.

---

### 2
```bash
tmux
```
**Result:** `[exited]` — immediately kicked back to the normal prompt instead of an interactive session.
**Finding:** something about attaching to a new interactive tmux session was broken (at this point in the session — see command 4, later attempts worked fine, cause never fully isolated).

---

### 3
```bash
df -h ~ /tmp; echo TERM=$TERM; tmux new-session -d -s test123 && echo "detached session OK" && tmux kill-session -t test123
```
**Why:** rule out disk-full or `$TERM` issues, and check whether tmux session *creation* works at all when detached (`-d`), isolating whether the bug is specifically in the interactive-attach path.
**Result:** disk 84% used, 144G free (not full). `TERM=xterm-256color` (normal). Detached session created and killed successfully.
**Finding:** tmux server itself is healthy; the bug (command 2) was specific to interactive attach, not session creation.

---

### 4
```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY python3 iitd-login.py -d
```
**Why:** CK's normal login routine — unset proxy vars first since the login portal rejects requests that arrive via a proxy, then authenticate directly.
**Result:** failed 5/5 attempts: `You can't login from a proxy server ip 10.10.78.62 ... Correct your Proxy Setting`.
**Finding (root cause):** `env | grep -i proxy` showed the actual variables set are `HTTP_proxy`/`HTTPS_proxy` (mixed case), not `HTTP_PROXY`/`HTTPS_PROXY` (all caps) as the unset command targeted. Env var names are case-sensitive on Linux, so those two were never actually unset — Python's `urllib` lowercases names when checking for a proxy, so the leftover mixed-case vars alone were enough to keep routing the login request through the proxy. This is a real bug in this project's own documented login snippet (`dorado-kraken-research/CLAUDE.md` line 33), not just a one-off typo — fixed in commit `1635e48`.

---

### 5
```bash
env -u HTTP_proxy -u HTTPS_proxy -u https_proxy -u http_proxy python3 iitd-login.py -d
```
**Why:** corrected version of command 4, matching the actual (case-sensitive) variable names.
**Result:** logged in; `tmux` afterward showed `[detached (from session 30)]`, confirming both the login and the interactive-attach path worked this time (attach issue from command 2 did not recur — treat as resolved/transient, not root-caused).

---

### 6
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://github.com
```
**Why:** confirm real outbound internet access (not just "no error"), before attempting any install.
**Result:** `200`.
**Finding:** Luna's internet access is fully working (login + proxy both correct) as of this session.

---

### 7
```bash
which conda; conda --version
```
**Why:** mtpweek2.md's plan assumes bioconda is set up "same pattern as everything else on Luna so far."
**Result:** `conda: command not found`.

---

### 8
```bash
ls -d ~/miniconda3 ~/anaconda3 ~/miniforge3 2>/dev/null; find ~ -maxdepth 2 -iname "conda" -type f 2>/dev/null
```
**Why:** rule out conda being installed-but-not-on-PATH before concluding it's absent entirely.
**Result:** nothing found.
**Decision (CK):** skip conda entirely for both Metabuli and Centrifuger this week — despite the plan doc's "same pattern as everything else" framing, this project's actual history (Kraken2, Centrifuge) was built from source via `git clone` + `make`, not conda. Go straight to the documented from-source fallback path for both tools.

---

### 9
```bash
which git cmake make g++ 2>&1
```
**Why:** confirm Metabuli's from-source build dependencies are present before cloning.
**Result:** `git`, `make`, `g++` found; `cmake` missing.

---

### 10
```bash
find / -iname "cmake" -type f 2>/dev/null | head -5; echo ---; sudo -n true 2>&1
```
**Why:** check whether cmake exists anywhere system-wide under a different PATH entry, and whether sudo is usable at all before assuming an install is needed.
**Result:** no cmake found anywhere; `sudo: a password is required` (i.e. sudo exists, just needs interactive auth — not blocked entirely).

---

### 11
```bash
sudo apt update && sudo apt install -y cmake
```
**Why:** install cmake system-wide via apt (confirmed Debian-based from the `cuda-keyring_1.1-1_all.deb` file already present in the home directory). Flagged to CK beforehand that this changes shared-account (`student`) system state, not just a personal config — CK confirmed proceeding, entered sudo password interactively in their own terminal.
**Result:** installed successfully.

---

### 12
```bash
cmake --version
```
**Result:** `cmake version 3.22.1`. Confirmed working.

---

### 13
```bash
ls ~/tools/
```
**Why:** confirm the established per-tool-subfolder convention (`~/tools/kraken2-src/`, `~/tools/centrifuge/`, etc.) before cloning Metabuli, to keep it consistent.
**Result:** `centrifuge  dorado  FlameGraph  kraken2  kraken2-pg  kraken2-src  kraken2-src-baseline`.

---

### 14
```bash
cd ~/tools && git clone --recurse-submodules https://github.com/steineggerlab/Metabuli.git
```
**Why:** clone Metabuli into the conventional tools folder, pulling in its bundled `mmseqs2` submodule (and mmseqs2's own nested regression submodule) in the same step — a plain clone would leave those folders empty and break the cmake configure step.
**Result:** clean clone, all three submodules (`fasta_validator`, `mmseqs`, and mmseqs's nested `util/regression`) checked out successfully, no errors.

---

### 15
```bash
cd Metabuli && mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release ..
```
**Why:** out-of-source cmake configure step, Release build type per mtpweek2.md's documented command.
**Result:** GNU 11.4.0 compiler detected, AVX2/AVX/SSE4.2/SSE4.1/SSE3/SSE2/SSE all detected successfully, ZLIB found, OpenMP found. Only "Could not find BZLIB" (optional, non-blocking). `-- Configuring done`, `-- Generating done`.

---

### 16
```bash
make -j
```
**Why:** compile Metabuli and its bundled mmseqs2 dependency, parallelized across cores.
**Result:** `[100%] Built target metabuli`. No compile errors (one informational compiler note about an unused variable in `IndexCreator.cpp`, non-blocking).

---

### 17
```bash
src/metabuli version
```
**Why:** confirm the compiled binary actually runs (not just compiles), from inside `~/tools/Metabuli/build/`. (First attempts at `./metabuli` and `build/src/metabuli` failed with "No such file or directory" — wrong relative path, since the shell was already inside `build/`; corrected to `src/metabuli`.)
**Result:** printed full usage/help text and version hash `fb921a32eccc9e9d28c6c1147f1fe227f5501579`. "Invalid Command: version" is expected — `version` isn't a real subcommand, but the version string printed in the banner above it either way, confirming the binary is fully functional.

**Metabuli install on Luna: done.** Binary at `~/tools/Metabuli/build/src/metabuli`.

---

### 18
```bash
cd ~/tools && git clone https://github.com/mourisl/centrifuger.git
```
**Why:** clone Centrifuger, same conventional `~/tools/` folder. No submodules needed here (only dependency is `pthreads`, part of the standard C library).
**Result:** clean clone, no errors.

---

### 19
```bash
cd centrifuger && make
```
**Why:** Centrifuger ships a plain Makefile (no cmake step needed, unlike Metabuli).
**Result:** compiled successfully with many warnings (unused variables etc., non-blocking, did not stop the build).

---

### 20
```bash
ls -la centrifuger centrifuger-build centrifuger-quant 2>&1; ./centrifuger --help 2>&1 | head -10
```
**Why:** confirm all three expected binaries exist and at least one runs without crashing.
**Result:** all three present, executable, real file sizes. `--help` isn't a recognized flag, but `centrifuger` fell back to printing its usage text instead of crashing, confirming it runs.

**Centrifuger install on Luna: done.** Binaries at `~/tools/centrifuger/{centrifuger,centrifuger-build,centrifuger-quant}`.

---

## Building Metabuli's ESKAPE database

### 21
```bash
find ~ -maxdepth 4 \( -iname "eskape_genomes*" -o -iname "*.fna" -o -iname "nucl_gb.accession2taxid*" -o -iname "nodes.dmp" -o -iname "names.dmp" -o -iname "seqid2taxid.map" \) 2>/dev/null
```
**Why:** locate the existing ESKAPE genome/taxonomy files from Week 1's Centrifuge build, to reuse rather than re-download.
**Result:** found `~/AccuracyDrift/databases/eskape_genomes/` (folder), `eskape_genomes_seqid2taxid.map`, `eskape_genomes_combined.fasta`. No `nucl_gb.accession2taxid.gz` found anywhere in this search depth.

---

### 22-23
```bash
~/tools/Metabuli/build/src/metabuli build --help 2>&1
head -5 ~/AccuracyDrift/databases/eskape_genomes_seqid2taxid.map
find ~/AccuracyDrift/databases/eskape_genomes -iname "*.fna" | wc -l
```
**Why:** check Metabuli's actual required inputs against the plan doc rather than trust it blindly (two smaller inaccuracies already found earlier this session), inspect the existing map file's format, and get the real genome-file layout/count.
**Result:** `metabuli build <db dir> <FASTA list> <accession2taxid> [options]` confirmed. Existing map file is 2-column (`accession.version`, `taxid`), no header. Genomes are nested under `eskape_genomes/refseq/bacteria/<assembly accession>/*.fna` (not flat as the plan assumed) — 200 files total. 200 matches the known `ncbi-genome-download` 200-genome ceiling bug already on the Week 1 punch list.

---

### 24-26 — reading the source to determine the real accession2taxid format
```bash
grep -rn "accession2taxid" ~/tools/Metabuli/src --include=*.cpp --include=*.h -l
grep -n "fillAcc2TaxIdMap" -A 30 ~/tools/Metabuli/src/commons/IndexCreator.cpp
grep -n "^.*fillAcc2TaxIdMap" ~/tools/Metabuli/src/commons/*.cpp ~/tools/Metabuli/src/commons/*.h
sed -n '264,360p' ~/tools/Metabuli/src/commons/common.cpp
```
**Why:** rather than guess whether the existing 2-column map file would work, read the actual parser (`fillAcc2TaxIdMap` in `common.cpp:264`).
**Finding:** the parser (1) explicitly skips line 1 as a header, and (2) parses each remaining line with `sscanf(line, "%s\t%*s\t%d\t%*d")` — i.e. expects NCBI's real 4-column `accession2taxid` format (`accession`, `accession.version` [ignored], `taxid`, `gi` [ignored]), using the **bare, version-stripped accession** (column 1) as the lookup key. The existing `seqid2taxid.map` (versioned accession + taxid, 2 columns, no header) does not match this shape at all.

---

### 27 — synthesizing a compliant accession2taxid file
```bash
awk -F'\t' 'BEGIN{print "accession\taccession.version\ttaxid\tgi"} {acc=$1; sub(/\.[0-9]+$/,"",acc); print acc"\t"$1"\t"$2"\t0"}' ~/AccuracyDrift/databases/eskape_genomes_seqid2taxid.map > ~/AccuracyDrift/databases/eskape_accession2taxid.tsv
```
**Why:** rather than download NCBI's full official `nucl_gb.accession2taxid.gz` (multi-GB, covers all of GenBank) just to get taxIDs for 200 genomes we already have mapped, generate a minimal correctly-shaped file from data already on disk.
**Result:** produced a properly-headed, 4-column file with bare accession in column 1, matching the parser's expectations exactly.

---

### 28-29 — locating the real taxonomy directory
```bash
ls -la ~/tools/kraken2-src/data/*.dmp
ls -la ~/AccuracyDrift/databases/pluspf_103gb/*.dmp
find ~ -iname "taxdump*" -o -iname "merged.dmp" 2>/dev/null
ls -la ~/AccuracyDrift/databases/sample_targeted/taxonomy/
```
**Why:** the first `nodes.dmp`/`names.dmp` found (in `kraken2-src/data/`) were only ~2KB each — too small to be the real NCBI taxonomy (~2.5M taxa), almost certainly toy test fixtures bundled with the Kraken2 source repo.
**Result:** `sample_targeted/taxonomy/` has the real, complete taxdump: 216MB `nodes.dmp`, 290MB `names.dmp`, 1.9MB `merged.dmp`, plus the original `taxdmp.zip`. Used as `--taxonomy-path`.

---

### 30
```bash
find ~/AccuracyDrift/databases/eskape_genomes -iname "*.fna" > ~/AccuracyDrift/databases/eskape_fasta_list.txt
wc -l ~/AccuracyDrift/databases/eskape_fasta_list.txt
```
**Result:** 200 genome paths written, confirmed.

---

### 31 — the actual build
```bash
mkdir -p ~/AccuracyDrift/databases/metabuli_eskape
cd ~/tools/Metabuli/build
time src/metabuli build ~/AccuracyDrift/databases/metabuli_eskape \
    ~/AccuracyDrift/databases/eskape_fasta_list.txt \
    ~/AccuracyDrift/databases/eskape_accession2taxid.tsv \
    --taxonomy-path ~/AccuracyDrift/databases/sample_targeted/taxonomy/ \
    --threads 32 \
    --max-ram 400
```
**Result:** succeeded. Real taxonomy loaded correctly (2,840,139 nodes, 99,346 merged nodes). "All accessions are mapped to taxonomy" — no skipped/unmapped accessions. 693 observed accessions across 200 genome files. 478,999,005 k-mers extracted, 24,977,880 unique k-mers written.
**Wall time: 2m35.570s real (23m48.6s user, 2m5.6s sys — reflects the 32-thread parallelism).**

---

### 32-33 — species-coverage finding
```bash
cut -f2 ~/AccuracyDrift/databases/eskape_genomes_seqid2taxid.map | sort -u
grep -P "^(1280|287|470|573)\t" ~/AccuracyDrift/databases/sample_targeted/taxonomy/names.dmp | grep "scientific name"
```
**Why:** the build reported only "4 unique taxIDs / 4 unique species" across 200 genomes — surprising for a 6-species ESKAPE panel, worth confirming against the source data rather than assuming a Metabuli bug.
**Finding (important, not Metabuli-specific):** the source `eskape_genomes_seqid2taxid.map` itself only contains 4 distinct taxIDs: 287 (*Pseudomonas aeruginosa*), 470 (*Acinetobacter baumannii*), 573 (*Klebsiella pneumoniae*), 1280 (*Staphylococcus aureus*). **Enterococcus faecium and Enterobacter species are completely absent** from this "ESKAPE" genome set — almost certainly a downstream effect of the already-known `ncbi-genome-download` 200-genome-ceiling bug. This affects every classifier benchmarked against this dataset, not just Metabuli — Kraken2 and Centrifuge's existing Week 1 numbers were run against the same 4-of-6-species panel. Worth an explicit caveat in this week's write-up, and a candidate follow-up once the DB-rebuild punch-list item is eventually picked up.

**Metabuli ESKAPE database build: done.** Database at `~/AccuracyDrift/databases/metabuli_eskape/`.

---

## Classifying reads_hac.fastq with Metabuli

### 34
```bash
src/metabuli classify --help 2>&1 | head -20
```
**Why:** verify the plan's classify command against the real tool before running it (build step already needed two corrections).
**Result:** `--seq-mode INT Single-end: 1, Paired-end: 2, Long read: 3 [2]` confirmed, positional argument order (`query file`, `database dir`, `output dir`, `job ID`) confirmed. Plan's classify command was accurate as written.

---

### 35 — first run: 32 threads, default RAM (128 GiB)
```bash
mkdir -p ~/AccuracyDrift/results/metabuli
time src/metabuli classify --seq-mode 3 \
    ~/results/basecalling/reads_hac.fastq \
    ~/AccuracyDrift/databases/metabuli_eskape \
    ~/AccuracyDrift/results/metabuli \
    eskape_run \
    --threads 32
```
**Result:** 104,918 reads processed, 705,675,816 query k-mers extracted, 93,958,406 k-mer matches. **Wall time: 13.438s** (user 2m30.4s, sys 0m14.3s). Much faster than the plan's cited "22-25x slower than Kraken2" Movi Color figure — that number was measured on a 75,166-genome database; ours is a 4-species ESKAPE panel, entirely different scale, not a contradiction.

---

### 36 — second run: 32 threads, --max-ram 400 (matching the build step)
```bash
time src/metabuli classify --seq-mode 3 \
    ~/results/basecalling/reads_hac.fastq \
    ~/AccuracyDrift/databases/metabuli_eskape \
    ~/AccuracyDrift/results/metabuli \
    eskape_run_32t_ram400 \
    --threads 32 --max-ram 400
```
**Result:** same read/k-mer counts as run 35 (expected, deterministic classification). **Wall time: 27.366s** (user 2m28.4s, sys 0m27.3s) — nearly double the first run's wall time despite near-identical user CPU time. Single-run result, direction is counter-intuitive (more RAM headroom, slower wall time) — flagged as possible noise, not a confirmed finding; would need repeat runs to verify before citing in the write-up.

---

### 37 — third run: 96 threads, default RAM
```bash
time src/metabuli classify --seq-mode 3 \
    ~/results/basecalling/reads_hac.fastq \
    ~/AccuracyDrift/databases/metabuli_eskape \
    ~/AccuracyDrift/results/metabuli \
    eskape_run_96t \
    --threads 96
```
**Result:** same read/k-mer counts again. **Wall time: 11.996s** (user 4m47.99s, sys 0m56.5s) — marginally faster wall-clock than 32T (13.4s → 12.0s, ~11% improvement) but roughly triple the total CPU effort (user+sys combined). Same "beyond the sweet-spot thread count, contention outweighs added parallelism" pattern this project already documented for Kraken2 at 32T — a useful cross-tool consistency note for the write-up.

---

### 38 — verifying real output
```bash
ls -la ~/AccuracyDrift/results/metabuli/
cat ~/AccuracyDrift/results/metabuli/eskape_run_report.tsv
```
**Result:** all three runs produced `_classifications.tsv`, `_krona.html`, and `_report.tsv` outputs. Report shows sensible classification: 92.41% of reads classified, distributed exactly across the 4 known-present species (*P. aeruginosa* 59.27%, *K. pneumoniae* 32.33%, *A. baumannii* 0.21%, *S. aureus* 0.055%), 7.59% unclassified. 6-column report shape confirmed (`clade_proportion, clade_count, taxon_count, rank, taxID, name`) — same Kraken2-style shape the plan described, minor column-name differences only.

**Metabuli classification on Luna: done.** Three runs captured (32T/default-RAM, 32T/400GiB-RAM, 96T/default-RAM) for the tradeoff write-up.

---

### 39 — perf stat cache-miss capture, matching Kraken2/Centrifuge's exact methodology
```bash
cd ~/tools/Metabuli/build
time perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  src/metabuli classify --seq-mode 3 \
  ~/results/basecalling/reads_hac.fastq \
  ~/AccuracyDrift/databases/metabuli_eskape \
  ~/AccuracyDrift/results/metabuli \
  eskape_run_perf \
  --threads 32
```
**Why:** CK asked for a Kraken2/Centrifuge/Metabuli comparison including cache-miss data, not just wall-time. Existing Kraken2 numbers on the comparable ESKAPE-scale DB (`eskape_650mb`, 32T) already in `AccuracyDrift/RESULTS.md`, and existing Centrifuge numbers (`eskape_200`, 32T) already in `centrifuge/commands_log.md` §4.5 — reused both rather than re-running. Only Metabuli needed a fresh perf-stat capture, using the identical event list and `numactl` pinning both prior tools were measured with, so all three are genuinely comparable.
**Result:**

| Metric | Kraken2 (`eskape_650mb`, 32T) | Centrifuge (`eskape_200`, 32T) | Metabuli (`metabuli_eskape`, 32T) |
|---|---|---|---|
| Wall time | 1.045s | 5.653s | 12.731s |
| Cache Miss Rate% | 36.23% | 21.90% | 78.97% |
| LLC Miss Rate% | 30.53% | 23.82% | 44.57% |
| IPC | 1.37 | 1.46 | 2.07 |

**Finding:** Metabuli has by far the worst cache locality of the three (LLC miss rate ~1.5x Kraken2, ~1.9x Centrifuge) — the mechanistic cache-level reason behind its wall-clock cost, consistent with its accuracy-over-efficiency design. Counter-intuitively, it also has the *highest* IPC (2.07 vs 1.37/1.46) despite the worst miss rates — likely the amino-acid translation/scoring compute partially hides DRAM latency behind real work rather than idling on stalls. Worth citing as a genuine nuance in the write-up, not just "Metabuli is slower."

---

### 40-41 — Metabuli thread sweep: 1T and 96T perf-stat
```bash
# 1T (no numactl, matching how this project measured Kraken2/Centrifuge's own 1T rows)
time perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  src/metabuli classify --seq-mode 3 ~/results/basecalling/reads_hac.fastq \
  ~/AccuracyDrift/databases/metabuli_eskape ~/AccuracyDrift/results/metabuli \
  eskape_run_perf_1t --threads 1

# 96T (numactl restored)
time perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles \
  numactl --cpunodebind=0 --membind=0 \
  src/metabuli classify --seq-mode 3 ~/results/basecalling/reads_hac.fastq \
  ~/AccuracyDrift/databases/metabuli_eskape ~/AccuracyDrift/results/metabuli \
  eskape_run_perf_96t --threads 96
```
**Result — full Metabuli thread sweep on `metabuli_eskape`, same reads_hac.fastq:**

| Threads | Wall time | Cache Miss Rate% | LLC Miss Rate% | IPC |
|---|---|---|---|---|
| 1 | 127.977s | 83.10% | 73.55% | 2.43 |
| 32 | 12.731s | 78.97% | 44.57% | 2.07 |
| 96 | 11.491s | 71.39% | 37.74% | 1.16 |

**Finding:** LLC miss rate falls monotonically as thread count rises (73.55%→44.57%→37.74%) — the opposite of the naive "more threads, more LLC contention" expectation. Likely explanation: at 1T a single thread sorts/searches the full 705M-k-mer buffer serially over one large diffuse working set, whereas at higher thread counts that same work is partitioned into smaller per-thread chunks with better individual locality, and that win outweighs added LLC-sharing pressure. IPC's drop from 32T→96T (2.07→1.16) matches the familiar "past the thread sweet spot, contention costs you" pattern already documented for Kraken2's own 32T/96T numbers (`eskape_650mb`: IPC 1.37→1.13). At 1T, Metabuli's wall time (128.0s) lands close to Centrifuge's 1T number on `eskape_200` (134.46s) — both far slower than Kraken2's 1T (21.98s).

**Metabuli thread-sweep profiling: done** (1T/32T/96T, wall-time + full perf-stat cache-miss/IPC data).

---

## Building Centrifuger's ESKAPE index

### 42
```bash
~/tools/centrifuger/centrifuger-build 2>&1 | head -30
```
**Why:** verify actual required flags before running (Metabuli's build needed two corrections; check Centrifuger too).
**Result:** `-r`/`--taxonomy-tree`/`--name-table`/`--conversion-table`/`-o`/`-t`/`--build-mem` all confirmed exactly as the plan documented. No corrections needed this time.

---

### 43 — 32T build
```bash
mkdir -p ~/AccuracyDrift/databases/centrifuger_eskape
cd ~/tools/centrifuger
time ./centrifuger-build -r ~/AccuracyDrift/databases/eskape_genomes_combined.fasta \
    --taxonomy-tree ~/AccuracyDrift/databases/sample_targeted/taxonomy/nodes.dmp \
    --name-table ~/AccuracyDrift/databases/sample_targeted/taxonomy/names.dmp \
    --conversion-table ~/AccuracyDrift/databases/eskape_genomes_seqid2taxid.map \
    -o ~/AccuracyDrift/databases/centrifuger_eskape/cg_base \
    -t 32 --build-mem 400G
```
**Why:** reuses the exact same combined FASTA Centrifuge itself used in Week 1 (same 200-genome/4-species panel, same caveat about the missing 2 ESKAPE species applies here too), plus the real taxonomy and the existing `seqid2taxid.map` as `--conversion-table` (this file's format matches Centrifuger's expectation directly — no reformatting needed here, unlike Metabuli).
**Result:** succeeded. 693 sequences, 1,105,382,541 bp total reference. **Wall time: 2m55.995s** (user 23m54.4s, sys 0m19.6s).

---

### 44-45 — 1T and 96T builds, completing the thread sweep
```bash
# 1T
time ./centrifuger-build -r ~/AccuracyDrift/databases/eskape_genomes_combined.fasta \
    --taxonomy-tree ~/AccuracyDrift/databases/sample_targeted/taxonomy/nodes.dmp \
    --name-table ~/AccuracyDrift/databases/sample_targeted/taxonomy/names.dmp \
    --conversion-table ~/AccuracyDrift/databases/eskape_genomes_seqid2taxid.map \
    -o ~/AccuracyDrift/databases/centrifuger_eskape/cg_base_1t -t 1 --build-mem 400G

# 96T
time ./centrifuger-build -r ~/AccuracyDrift/databases/eskape_genomes_combined.fasta \
    --taxonomy-tree ~/AccuracyDrift/databases/sample_targeted/taxonomy/nodes.dmp \
    --name-table ~/AccuracyDrift/databases/sample_targeted/taxonomy/names.dmp \
    --conversion-table ~/AccuracyDrift/databases/eskape_genomes_seqid2taxid.map \
    -o ~/AccuracyDrift/databases/centrifuger_eskape/cg_base_96t -t 96 --build-mem 400G
```
**Result — full Centrifuger build thread sweep, same 693-sequence/1.1Gbp reference:**

| Threads | Wall time | Speedup vs 1T |
|---|---|---|
| 1 | 20m39.114s (1239.1s) | 1.00x |
| 32 | 2m55.995s (176.0s) | 7.04x |
| 96 | 2m6.643s (126.6s) | 9.79x |

**Finding:** unlike every classify-time thread sweep seen so far this session (Kraken2 peaks at 32T then degrades; Metabuli's IPC drops 32T→96T), Centrifuger's *build* step keeps improving all the way to 96T — a further 1.39x gain from 32T→96T, no degradation. Mechanistic reason: index building is suffix-array sorting split into many independent chunks (17 chunks at 32T, 66 at 96T per the log output) — far more embarrassingly parallel than the memory-bound hash/k-mer lookups that dominate classify-time workloads, so it doesn't hit the same LLC-contention wall. 1T→32T speedup (7.04x for 32x threads) is well sub-linear, reflecting real coordination/merge overhead across chunks even in this favorable case.

**Centrifuger ESKAPE index build: done.** Three indexes at `~/AccuracyDrift/databases/centrifuger_eskape/cg_base{,_1t,_96t}`.

---
