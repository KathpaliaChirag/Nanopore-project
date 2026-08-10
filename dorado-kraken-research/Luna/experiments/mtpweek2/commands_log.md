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
