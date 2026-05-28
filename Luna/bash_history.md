# Luna Bash History

Chronological log of all commands run on Luna (dell-R760) as `student` user, with explanations.
Status: ✅ Done | 🔜 Upcoming | ❌ Failed

---

## Session 1 — 2026-05-29 | User Setup & Tool Installation

---

### 1. Give sudo access to student user
**Run as:** `chayanika`
```bash
# Adds 'student' to the sudo group so they can run privileged commands.
# Without this, student can't install packages or do admin tasks.
# Takes effect after student logs out and back in.
sudo usermod -aG sudo student
```
**Status:** ✅ Done

---

### 2. Verify sudo was granted
**Run as:** `chayanika`
```bash
# Lists all groups the student user belongs to.
# Should show 'sudo' in the output confirming step 1 worked.
groups student
```
**Status:** ✅ Done

---

### 3. Copy iitd-login.py to student home
**Run as:** `chayanika`
```bash
# Copies the IITD proxy login script from chayanika's home to student's home.
# This script authenticates with proxy61.iitd.ac.in:3128 and sends heartbeats
# every 100s to keep the session alive. Without it, no internet on Luna.
sudo cp ~/iitd-login.py /home/student/
sudo chown student:student /home/student/iitd-login.py
sudo chmod 700 /home/student/iitd-login.py
```
**Status:** ✅ Done

---

### 4. Set up proxy environment variables
**Run as:** `student`
```bash
# Adds IITD proxy settings to ~/.bashrc so they persist across sessions.
# http_proxy / https_proxy are read by wget, curl, pip, conda, apt, git etc.
# Without these, even after iitd-login.py authenticates, tools won't route
# traffic through the proxy and will fail to reach the internet.
echo 'export http_proxy=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
echo 'export https_proxy=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
echo 'export HTTP_PROXY=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
echo 'export HTTPS_PROXY=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
source ~/.bashrc
```
**Status:** ✅ Done

---

### 5. Start internet session in tmux
**Run as:** `student`
```bash
# tmux creates a persistent terminal session that survives SSH disconnects.
# We name it 'internet' so it's easy to reattach later.
# iitd-login.py -d runs in verbose mode: shows login steps and heartbeat logs.
# After entering userid/password, press Ctrl+B then D to detach (not kill).
tmux new -s internet
python3 ~/iitd-login.py -d
# [enter IITD userid and password]
# Ctrl+B, D  →  detach from tmux
```
**Status:** ✅ Done

---

### 6. Verify internet connectivity
**Run as:** `student`
```bash
# Fetches example.com through the proxy to confirm internet is working.
# If it returns HTML with "Example Domain", proxy auth succeeded.
curl http://example.com
```
**Status:** ✅ Done — `index.html` saved in home dir

---

### 7. Install numactl, valgrind, gperftools
**Run as:** `student`
```bash
# numactl: controls NUMA memory/CPU binding — useful for profiling memory
#          locality on Luna's dual-socket Xeon Platinum 8468.
# valgrind: memory error detector; includes cachegrind for cache miss analysis.
# google-perftools: low-overhead CPU sampling profiler (gperftools/pprof).
# libgoogle-perftools-dev: headers needed to link gperftools into C++ programs.
sudo apt install -y numactl valgrind google-perftools libgoogle-perftools-dev
```
**Status:** ✅ Done

---

### 8. Download and build Kraken2
**Run as:** `student`
```bash
# Downloads Kraken2 v2.1.3 source tarball from GitHub via IITD proxy.
# Kraken2 is the k-mer based genome classification tool we are optimising.
# We build from source (not apt) so we can later recompile with profiling
# flags (-pg for gprof, -g for debug symbols, custom -march=native for AVX-512).
wget -O ~/kraken2.tar.gz https://github.com/DerrickWood/kraken2/archive/refs/tags/v2.1.3.tar.gz

# Extracts the tarball into home directory, creating ~/kraken2-2.1.3/
tar -xzf ~/kraken2.tar.gz -C ~/

# Renames the extracted folder to a cleaner name for easy reference.
mv ~/kraken2-2.1.3 ~/kraken2-src

# Runs the official install script which compiles all binaries (kraken2,
# kraken2-build, kraken2-inspect) and copies them to ~/kraken2/
cd ~/kraken2-src && ./install_kraken2.sh ~/kraken2
cd ~

# Adds ~/kraken2 to PATH so 'kraken2' works from anywhere.
echo 'export PATH=$HOME/kraken2:$PATH' >> ~/.bashrc
```
**Status:** ✅ Done (first attempt failed — missing zlib.h, fixed in step 9)

---

### 9. Install zlib dev headers (fix for Kraken2 build failure)
**Run as:** `student`
```bash
# Kraken2's k2mask component requires zlib for compressed file support.
# zlib1g-dev provides the zlib.h header file needed during compilation.
# Without it the build stops at k2mask.cc:18 with "fatal error: zlib.h"
sudo apt install -y zlib1g-dev
```
**Status:** ✅ Done

---

### 10. Rebuild Kraken2 after zlib fix
**Run as:** `student`
```bash
# Re-runs the install script now that zlib.h is available.
# Previous partial build artifacts are overwritten automatically.
cd ~/kraken2-src && ./install_kraken2.sh ~/kraken2
cd ~

# Confirms kraken2 binary is accessible and prints its version.
kraken2 --version
```
**Status:** ✅ Done — Kraken 2.1.3 installed at ~/kraken2/

---

### 11. Install Dorado (Oxford Nanopore basecaller)
**Run as:** `student`
```bash
# Downloads the pre-built Dorado v1.4.0 binary for Linux x64.
# Dorado is the GPU-accelerated ONT basecaller — converts raw nanopore
# signals (pod5/fast5) to FASTQ. We'll profile it with nsys/ncu later.
wget -O ~/dorado.tar.gz https://cdn.oxfordnanoportal.com/software/analysis/dorado-1.4.0-linux-x64.tar.gz

# Extracts into ~/, creating ~/dorado-1.4.0-linux-x64/
tar -xzf ~/dorado.tar.gz -C ~/

# Adds dorado binary to PATH.
echo 'export PATH=$HOME/dorado-1.4.0-linux-x64/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Confirms dorado is accessible.
dorado --version
```
**Status:** ✅ Done — Dorado 1.4.0+ba44a013 installed at ~/dorado-1.4.0-linux-x64/bin/

---

### 12. Install FlameGraph
**Run as:** `student`
```bash
# Downloads FlameGraph (Brendan Gregg's tool) for visualising perf profiles.
# stackcollapse-perf.pl converts perf script output into flamegraph input.
# flamegraph.pl renders an interactive SVG showing where CPU time is spent.
wget -O ~/flamegraph.tar.gz https://github.com/brendangregg/FlameGraph/archive/refs/heads/master.tar.gz
tar -xzf ~/flamegraph.tar.gz -C ~/
mv ~/FlameGraph-master ~/FlameGraph

# Adds FlameGraph scripts to PATH.
echo 'export PATH=$HOME/FlameGraph:$PATH' >> ~/.bashrc
source ~/.bashrc
```
**Status:** ✅ Done — installed at ~/FlameGraph/

---

### 13. Final verification of all tools
**Run as:** `student`
```bash
# Checks that all tool binaries are findable in PATH.
# 'which' prints the resolved path — 'not found' means PATH or install failed.
which perf gprof kraken2 dorado flamegraph.pl numactl valgrind

# Prints versions to confirm correct installs.
perf --version
kraken2 --version
dorado --version
valgrind --version
gprof --version
```
**Status:** ✅ Done — all tools verified working (2026-05-29 04:12)

---

### 14. Download Kraken2 standard-8 database
**Run as:** `student`
```bash
# Downloads the pre-built standard-8 database (8GB compressed, ~15GB extracted).
# This is the standard Kraken2 database capped at an 8GB hash table —
# covers bacteria, archaea, viral, and human reference sequences.
# We use this instead of the full 100GB build to fit within disk constraints.
# Hosted on AWS S3 so download routes through the IITD proxy.
wget -O ~/kraken2_db.tar.gz https://genome-idx.s3.amazonaws.com/kraken/k2_standard_08gb_20240112.tar.gz

# Create a dedicated directory and extract the database into it.
# The database consists of three files: hash.k2d, taxo.k2d, opts.k2d
mkdir -p ~/data/kraken2_db
tar -xzf ~/kraken2_db.tar.gz -C ~/data/kraken2_db

# Confirm the three database files are present and check their sizes.
ls -lh ~/data/kraken2_db/
```
**Status:** Done — database extracted to ~/data/kraken2_db/

---

### 15. Transfer pod5 file from local machine
**Run as:** local Windows machine
```powershell
# Copies the raw nanopore signal file (pod5 format) from the local machine
# to Luna over SCP. pod5 is Oxford Nanopore's binary format storing
# raw electrical signals per read — input to Dorado for basecalling.
# File: FBE01990_24778b97_03e50f91_10.pod5 (~4GB)
scp "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\pod5 data\FBE01990_24778b97_03e50f91_10.pod5" student@luna.cse.iitd.ac.in:~/
```
**Status:** Done — file transferred to ~/

---

### 16. Reorganise home directory
**Run as:** `student`
```bash
# Creates a clean directory structure to separate tools, data, results,
# scripts, and archives. Avoids a cluttered home directory as more
# pod5 files and output files accumulate over time.
mkdir -p ~/tools ~/data/pod5 ~/data/kraken2_db ~/results/basecalling ~/results/classification ~/results/profiling ~/scripts ~/archives

# Move all tool directories into ~/tools/
mv ~/dorado-1.4.0-linux-x64 ~/tools/dorado
mv ~/kraken2 ~/tools/kraken2
mv ~/kraken2-src ~/tools/kraken2-src
mv ~/FlameGraph ~/tools/FlameGraph

# Move database and pod5 file into ~/data/
mv ~/kraken2_db/* ~/data/kraken2_db/
mv ~/*.pod5 ~/data/pod5/

# Move all tarballs and scratch files into ~/archives/
mkdir -p ~/archives
mv ~/dorado.tar.gz ~/archives/
mv ~/kraken2.tar.gz ~/archives/
mv ~/kraken2_db.tar.gz ~/archives/
mv ~/flamegraph.tar.gz ~/archives/
mv ~/index.html ~/archives/

# Update PATH entries in .bashrc to reflect new tool locations.
sed -i 's|$HOME/dorado-1.4.0-linux-x64/bin|$HOME/tools/dorado/bin|g' ~/.bashrc
sed -i 's|$HOME/kraken2:|$HOME/tools/kraken2:|g' ~/.bashrc
sed -i 's|$HOME/FlameGraph:|$HOME/tools/FlameGraph:|g' ~/.bashrc
source ~/.bashrc
```
**Status:** Done — final home layout:
```
~/
├── archives/         tarballs and scratch files
├── data/
│   ├── kraken2_db/   standard-8 database (hash.k2d, taxo.k2d, opts.k2d)
│   └── pod5/         FBE01990_24778b97_03e50f91_10.pod5
├── results/
│   ├── basecalling/  dorado output
│   ├── classification/ kraken2 output
│   └── profiling/    perf, nsys, flamegraph outputs
├── scripts/
├── tools/
│   ├── dorado/       v1.4.0
│   ├── FlameGraph/
│   ├── kraken2/      v2.1.3 binaries
│   └── kraken2-src/  source code
└── iitd-login.py
```

---

### 17. Install sysstat for per-core CPU monitoring
**Run as:** `student`
```bash
# sysstat provides mpstat — shows per-core CPU utilization in real time.
# Needed to see how many of the 96 cores Kraken2 actually uses during a run.
sudo apt install -y sysstat
```
**Status:** Done

---

### 18. Dorado basecalling — all three models
**Run as:** `student`
```bash
# Basecalls the pod5 file with all three accuracy tiers.
# fast: lowest quality, fastest. hac: production standard. sup: highest accuracy.
# --emit-fastq outputs FASTQ instead of BAM — needed as Kraken2 input.
dorado basecaller fast ~/data/pod5/FBE01990_24778b97_03e50f91_10.pod5 --emit-fastq > ~/results/basecalling/reads_fast.fastq
dorado basecaller hac  ~/data/pod5/FBE01990_24778b97_03e50f91_10.pod5 --emit-fastq > ~/results/basecalling/reads_hac.fastq
dorado basecaller sup  ~/data/pod5/FBE01990_24778b97_03e50f91_10.pod5 --emit-fastq > ~/results/basecalling/reads_sup.fastq
```
**Status:** Done — fast: 104,832 reads, hac: 104,918 reads, sup: 104,980 reads

---

### 19. Kraken2 classification — all three models
**Run as:** `student`
```bash
kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/classification/report_fast.txt \
  --output ~/results/classification/output_fast.txt \
  ~/results/basecalling/reads_fast.fastq

kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/classification/report_hac.txt \
  --output ~/results/classification/output_hac.txt \
  ~/results/basecalling/reads_hac.fastq

kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/classification/report_sup.txt \
  --output ~/results/classification/output_sup.txt \
  ~/results/basecalling/reads_sup.fastq
```
**Status:** Done — fast: 82.66%, hac: 95.77%, sup: 97.09% classified

---

### 20. Set perf_event_paranoid to 0
**Run as:** `student`
```bash
# Lowers the perf security level so hardware counters are accessible to all users.
# paranoid=1 blocks CPU events for users without CAP_PERFMON — student has neither.
sudo sh -c 'echo 0 > /proc/sys/kernel/perf_event_paranoid'
echo 'kernel.perf_event_paranoid = 0' | sudo tee -a /etc/sysctl.conf
```
**Status:** Done — paranoid set to 0, made permanent in /etc/sysctl.conf

---

### 21. perf stat baseline — hac model (comprehensive)
**Run as:** `student`
```bash
# Full hardware counter profiling of Kraken2 hac run.
# Covers IPC, cache hierarchy miss rates, per-level stall cycles, branch prediction.
# stalled-cycles-backend replaced with cycle_activity.stalls_* (Sapphire Rapids).
perf stat \
  -e cycles,instructions \
  -e cache-misses,cache-references \
  -e LLC-load-misses,LLC-loads \
  -e L1-dcache-load-misses,L1-dcache-loads \
  -e branch-misses,branch-instructions \
  -e cycle_activity.stalls_total \
  -e cycle_activity.stalls_l1d_miss \
  -e cycle_activity.stalls_l2_miss \
  -e cycle_activity.stalls_l3_miss \
  -e memory_activity.stalls_l3_miss \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/profiling/perf_report_hac_full.txt \
  --output ~/results/profiling/perf_output_hac_full.txt \
  ~/results/basecalling/reads_hac.fastq
```
**Status:** Done — IPC 1.58, LLC miss rate 81.9%, 48.7% stall cycles. See results_kraken2.md.

---

### 22. TMA breakdown — hac model
**Run as:** `student`
```bash
# TMA (Top-down Microarchitecture Analysis) gives a high-level slot breakdown.
# Uses -M flag (metrics), not -e (events) — different perf subsystem.
perf stat -M tma_memory_bound,tma_core_bound \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```
**Status:** Done — memory_bound 25.4%, core_bound 21.7%. See results_kraken2.md.

---

## Next Steps

- perf record + flamegraph to confirm CompactHashTable::Get() as hotspot on Luna
- Second Kraken2 pass after DB is in page cache to isolate classification-only time
- NUMA analysis with numactl
- perf stat for fast and sup models for comparison
- nsys profiling of Dorado GPU run
