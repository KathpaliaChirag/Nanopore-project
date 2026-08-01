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

---
