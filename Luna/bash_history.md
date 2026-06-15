# Luna Bash History

Chronological log of commands run on Luna (dell-R760) as `student` user, with explanations.
**Partial log — covers Sessions 1 (setup) through Step 51 (tmpfs experiment, 2026-06-15). AccuracyDrift and AccuracyChase commands are logged separately in `AccuracyDrift/COMMANDS.md`.**
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

---

### 23. perf stat + per-core CPU capture — fast model
**Run as:** `student`
```bash
# Run mpstat in background to capture per-core CPU utilisation at 1s intervals.
# Kill it after perf stat finishes. perf stat stderr redirected to file.
mpstat -P ALL 1 > ~/results/profiling/mpstat_fast.txt &
MPSTAT_PID=$!

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
  --report ~/results/profiling/report_fast.txt \
  --output /dev/null \
  ~/results/basecalling/reads_fast.fastq \
  2> ~/results/profiling/perf_stat_fast.txt

kill $MPSTAT_PID
```
**Status:** ✅ Done — IPC 1.47, LLC miss 82.0%, 51.8% stall cycles, wall 5.84s

---

### 24. perf stat + per-core CPU capture — sup model
**Run as:** `student`
```bash
mpstat -P ALL 1 > ~/results/profiling/mpstat_sup.txt &
MPSTAT_PID=$!

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
  --report ~/results/profiling/report_sup.txt \
  --output /dev/null \
  ~/results/basecalling/reads_sup.fastq \
  2> ~/results/profiling/perf_stat_sup.txt

kill $MPSTAT_PID
```
**Status:** ✅ Done — IPC 1.65, LLC miss 82.0%, 48.5% stall cycles, wall 5.63s

---

### 25. Also capture mpstat for hac (retroactive — was not done in step 21)
**Run as:** `student`
```bash
# hac perf stat was already run without mpstat. Re-run with mpstat this time.
# DB should be warm in page cache so this also gives the warm-cache wall time.
mpstat -P ALL 1 > ~/results/profiling/mpstat_hac.txt &
MPSTAT_PID=$!

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
  --report ~/results/profiling/report_hac_warm.txt \
  --output /dev/null \
  ~/results/basecalling/reads_hac.fastq \
  2> ~/results/profiling/perf_stat_hac_warm.txt

kill $MPSTAT_PID
```
**Status:** ✅ Done — IPC 1.58 (identical cold/warm), wall time same ~5.6s, DB already in page cache. See results_kraken2.md.

---

### 26. TMA breakdown — fast model
**Run as:** `student`
```bash
perf stat -M tma_memory_bound,tma_core_bound \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_fast.fastq \
  2> ~/results/profiling/tma_fast.txt
```
**Status:** ✅ Done — memory_bound 28.1%, core_bound 22.4%

---

### 27. TMA breakdown — sup model
**Run as:** `student`
```bash
perf stat -M tma_memory_bound,tma_core_bound \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_sup.fastq \
  2> ~/results/profiling/tma_sup.txt
```
**Status:** ✅ Done — memory_bound 26.2%, core_bound 20.8%

---

### 28. Thread scaling experiment — fast model (5 runs per thread count)
**Run as:** `student`
```bash
# Each thread count runs 5 times. Wall time measured with millisecond precision
# using date +%s%3N (start/end timestamps). kraken2 stderr suppressed.
# avg computed with bc. Output tee'd to file and printed to terminal.
for T in 2 4 8 16 32 64 96 128 192; do
  echo "=== threads=$T ==="
  sum=0
  for i in 1 2 3 4 5; do
    START=$(date +%s%3N)
    kraken2 --db ~/data/kraken2_db --threads $T \
      --report /dev/null --output /dev/null \
      ~/results/basecalling/reads_fast.fastq 2>/dev/null
    END=$(date +%s%3N)
    W=$(echo "scale=3; ($END - $START) / 1000" | bc)
    echo "  run $i: ${W}s"
    sum=$(echo "$sum + $W" | bc)
  done
  AVG=$(echo "scale=3; $sum / 5" | bc)
  echo "  avg: ${AVG}s"
  echo ""
done 2>&1 | tee ~/results/profiling/thread_scaling_fast.txt
```
**Status:** ✅ Done — sweet spot 32 threads (5.507s avg). Beyond 32 threads perf degrades. Only 2.13x speedup despite 16x more threads — DRAM bandwidth wall confirmed.

---

### 29. Thread scaling — perf stat with 5-run avg per thread count
**Run as:** `student`
```bash
# perf stat -r 5 runs 5 repetitions and reports mean ± stddev per counter automatically.
# Saves each thread count to its own file, summary to combined file.
# Takes ~5-6 minutes total.
for T in 2 4 8 16 32 64 96 128 192; do
  echo "=== threads=$T ==="
  perf stat -r 5 \
    -e cycles,instructions \
    -e LLC-load-misses,LLC-loads \
    -e cycle_activity.stalls_total \
    -e memory_activity.stalls_l3_miss \
    kraken2 --db ~/data/kraken2_db --threads $T \
    --report /dev/null --output /dev/null \
    ~/results/basecalling/reads_fast.fastq \
    2> ~/results/profiling/thread_scaling_perf_T${T}.txt
  cat ~/results/profiling/thread_scaling_perf_T${T}.txt
  echo ""
done 2>&1 | tee ~/results/profiling/thread_scaling_perf_summary.txt
```
**Status:** ✅ Done — IPC 1.81 peak at 4T, degrades to 1.28 at 192T. DRAM saturates at 8T. Sweet spot 32T (5.52s). See results_kraken2.md Step 5f.

---

### 30. Thread scaling — wall time, hac model (5 runs each)
**Run as:** `student`
```bash
for T in 2 4 8 16 32 64 96 128 192; do
  echo "=== threads=$T ==="
  sum=0
  for i in 1 2 3 4 5; do
    START=$(date +%s%3N)
    kraken2 --db ~/data/kraken2_db --threads $T \
      --report /dev/null --output /dev/null \
      ~/results/basecalling/reads_hac.fastq 2>/dev/null
    END=$(date +%s%3N)
    W=$(echo "scale=3; ($END - $START) / 1000" | bc)
    echo "  run $i: ${W}s"
    sum=$(echo "$sum + $W" | bc)
  done
  AVG=$(echo "scale=3; $sum / 5" | bc)
  echo "  avg: ${AVG}s"
  echo ""
done 2>&1 | tee ~/results/profiling/thread_scaling_hac.txt
```
**Status:** ✅ Done — sweet spot 32T (5.235s), same curve as fast

---

### 31. Thread scaling — wall time, sup model (5 runs each)
**Run as:** `student`
```bash
for T in 2 4 8 16 32 64 96 128 192; do
  echo "=== threads=$T ==="
  sum=0
  for i in 1 2 3 4 5; do
    START=$(date +%s%3N)
    kraken2 --db ~/data/kraken2_db --threads $T \
      --report /dev/null --output /dev/null \
      ~/results/basecalling/reads_sup.fastq 2>/dev/null
    END=$(date +%s%3N)
    W=$(echo "scale=3; ($END - $START) / 1000" | bc)
    echo "  run $i: ${W}s"
    sum=$(echo "$sum + $W" | bc)
  done
  AVG=$(echo "scale=3; $sum / 5" | bc)
  echo "  avg: ${AVG}s"
  echo ""
done 2>&1 | tee ~/results/profiling/thread_scaling_sup.txt
```
**Status:** ✅ Done — sweet spot 32T (4.560s), lowest floor of all 3 models; 2T→32T = 2.51x speedup

---

### 32. perf record — hac model, 32 threads
**Run as:** `student`
```bash
sudo perf record -g -F 99 -o ~/results/profiling/perf_hac_32t.data \
  ~/tools/kraken2/kraken2 \
  --db ~/data/kraken2_db \
  --threads 32 \
  --output ~/results/profiling/perf_record_hac_32t_out.txt \
  ~/results/basecalling/reads_hac.fastq
```
**Status:** ✅ Done — 2142 samples, 0.239 MB, data saved to `perf_hac_32t.data`

---

### 33. Generate flamegraph from perf record data
**Run as:** `student`
```bash
sudo perf script -i ~/results/profiling/perf_hac_32t.data | \
  ~/tools/FlameGraph/stackcollapse-perf.pl | \
  ~/tools/FlameGraph/flamegraph.pl > ~/results/profiling/flamegraph_hac_32t.svg
```
**Status:** ✅ Done — SVG saved to `~/results/profiling/flamegraph_hac_32t.svg`, copied to `Luna/profiling/flamegraph_hac_32t.svg` in repo

---

### 34. NUMA topology check
**Run as:** `student`
```bash
numactl --hardware
```
**Status:** ✅ Done — 2 nodes, even CPUs = node 0, odd = node 1, distance 10/21, DB on node 0 (202 GB used there)

---

### 35. NUMA wall time experiment — default vs node 0 vs node 1 pinned (hac, 32T, 5 runs each)
**Run as:** `student`
```bash
for i in 1 2 3 4 5; do START=$(date +%s%3N); kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null; END=$(date +%s%3N); echo "default run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"; done

for i in 1 2 3 4 5; do START=$(date +%s%3N); numactl --cpunodebind=0 --membind=0 kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null; END=$(date +%s%3N); echo "node0 run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"; done

for i in 1 2 3 4 5; do START=$(date +%s%3N); numactl --cpunodebind=1 --membind=1 kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null; END=$(date +%s%3N); echo "node1 run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"; done
```
**Status:** ✅ Done — default 5.261s, node 0 4.405s, node 1 5.083s — 16.3% penalty from cross-NUMA traffic confirmed

---

### 36. perf stat — all 4 NUMA configs (hac, 32T): node0+node0, node1+node1, cross-socket both ways
**Run as:** `student`
```bash
numactl --cpunodebind=0 --membind=0 perf stat -e cycles,instructions -e LLC-load-misses,LLC-loads -e cycle_activity.stalls_total -e memory_activity.stalls_l3_miss kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq
numactl --cpunodebind=1 --membind=1 perf stat [same events] ...
numactl --cpunodebind=1 --membind=0 perf stat [same events] ...
numactl --cpunodebind=0 --membind=1 perf stat [same events] ...
```
**Status:** ✅ Done — LLC miss% unchanged (~82% all configs); DRAM stalls 6.44B (local) vs 12.2B (cross); IPC 1.86 (local) vs 1.59 (cross)

---

### 37. TMA breakdown — all 4 NUMA configs (hac, 32T)
**Run as:** `student`
```bash
numactl --cpunodebind=X --membind=Y perf stat -M tma_memory_bound,tma_core_bound kraken2 --db ~/data/kraken2_db --threads 32 --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq
```
**Status:** ✅ Done — memory_bound 23.9% (local) vs 31.7% (cross); core_bound consistent ~15% across all NUMA configs (thread-count effect, not NUMA); retiring best at 30.7% with node0+node0

---

### 38. Thread scaling — all 4 NUMA configs (hac, 2/4/8/16/32/48/64/96T, 5 runs each)
**Run as:** `student`
```bash
# Repeated for all 4 numactl configs: --cpunodebind=0/1 --membind=0/1
for T in 2 4 8 16 32 48 64 96; do
  for i in 1 2 3 4 5; do
    numactl --cpunodebind=X --membind=Y kraken2 --db ~/data/kraken2_db --threads $T \
      --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null
  done
done
```
**Status:** ✅ Done — sweet spot stays 32T for ALL 4 configs; node0+node0 floor 4.405s (best), cross-socket floor ~5.53-5.60s, node1+node1 floor 5.037s; DRAM bandwidth wall confirmed independent of NUMA topology

---

### 39. Recompile kraken2 with -pg for gprof
**Run as:** `student`
```bash
# Add -pg to Makefile
sed -i 's/CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3/CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -pg/' ~/tools/kraken2-src/src/Makefile

# Build instrumented binary
cd ~/tools/kraken2-src/src && make clean && make

# Install to separate pg directory
mkdir -p ~/tools/kraken2-pg
cp ~/tools/kraken2-src/src/classify ~/tools/kraken2-pg/
cp ~/tools/kraken2/kraken2 ~/tools/kraken2-pg/kraken2-pg
cp ~/tools/kraken2/kraken2lib.pm ~/tools/kraken2-pg/

# Revert Makefile and rebuild production binary
sed -i 's/ -pg//' ~/tools/kraken2-src/src/Makefile
cd ~/tools/kraken2-src/src && make clean && make
cp ~/tools/kraken2-src/src/classify ~/tools/kraken2/classify
```
**Status:** ✅ Done — `~/tools/kraken2-pg/kraken2-pg` (gprof), `~/tools/kraken2/kraken2` (production), both `kraken2 2.1.3`

---

### 40. gprof run — hac model, 1 thread (primary)
**Run as:** `student`
```bash
cd ~/results/profiling
time ~/tools/kraken2-pg/kraken2-pg --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null
gprof ~/tools/kraken2-pg/classify gmon.out > gprof_hac_1t.txt
head -40 gprof_hac_1t.txt
```
**Status:** ✅ Done — wall 22.843s, user 18.617s; MinimizerScanner 53.35% (351M calls), CompactHashTable::Get 23.23% (11.6M calls), reverse_complement 6.69%

---

### 41. gprof run — hac model, 32 threads (secondary, partial)
**Run as:** `student`
```bash
cd ~/results/profiling
time ~/tools/kraken2-pg/kraken2-pg --db ~/data/kraken2_db --threads 32 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null
gprof ~/tools/kraken2-pg/classify gmon.out > gprof_hac_32t.txt
```
**Status:** ✅ Done — wall 43.4s (10x -pg overhead), MinimizerScanner 68.08%, CompactHashTable 10.09% (partial: one thread only, DB pre-warmed by other threads reduces hash miss fraction)

---

### 42. valgrind cachegrind — first attempt (failed silently)
**Run as:** `student`
```bash
cd ~/results/profiling && time valgrind --tool=cachegrind \
  --cachegrind-out-file=cachegrind_hac_1t.out \
  ~/tools/kraken2/kraken2 --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null
```
**Status:** ❌ Failed — output file not created. `2>/dev/null` suppressed valgrind's own stderr, masking the failure. kraken2 is a Perl wrapper — valgrind instrumented the shell, not the C++ binary.

---

### 43. valgrind cachegrind — without stderr redirect (diagnosis)
**Run as:** `student`
```bash
valgrind --tool=cachegrind \
  --cachegrind-out-file=cachegrind_hac_1t.out \
  ~/tools/kraken2/kraken2 --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```
**Status:** ❌ Failed — output file still not created. Confirmed root cause: `~/tools/kraken2/kraken2` is a Perl script that exec's the actual C++ binary (`classify`) as a child process. valgrind instruments the parent Perl process and does not follow into the child. Fix: use `--trace-children=yes`.

---

### 44. valgrind cachegrind — with --trace-children=yes (success)
**Run as:** `student`
```bash
valgrind --tool=cachegrind --trace-children=yes \
  --cachegrind-out-file=cachegrind_hac_1t.out \
  ~/tools/kraken2/kraken2 --db ~/data/kraken2_db --threads 1 \
  --report /dev/null --output /dev/null \
  ~/results/basecalling/reads_hac.fastq
```
**Status:** ✅ Done — wall 362s (~20x overhead), 227 KB output file created at `~/results/profiling/cachegrind_hac_1t.out`. brk segment overflow warning (benign — valgrind internal limit, does not affect results).

---

### 45. cg_annotate — per-function cache miss breakdown
**Run as:** `student`
```bash
cg_annotate cachegrind_hac_1t.out | head -80
```
**Status:** ✅ Done — CompactHashTable::Get accounts for 96.24% of all LL read misses (DLmr). MinimizerScanner::NextMinimizer has zero LL misses despite 48% of instructions. See results_kraken2.md Step 11.

---

### 46. Copy FASTQ to tmpfs
**Run as:** `student`
```bash
cp ~/results/basecalling/reads_hac.fastq /dev/shm/reads_hac.fastq
ls -lh /dev/shm/reads_hac.fastq
```
**Status:** ✅ Done — 703 MB written to /dev/shm (RAM-backed tmpfs)

---

### 47. Run from tmpfs — warm cache (5 runs, 32T node0)
**Run as:** `student`
```bash
for i in 1 2 3 4 5; do
  START=$(date +%s%3N)
  numactl --cpunodebind=0 --membind=0 kraken2 --db ~/data/kraken2_db --threads 32 \
    --report /dev/null --output /dev/null /dev/shm/reads_hac.fastq 2>/dev/null
  END=$(date +%s%3N)
  echo "run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"
done
```
**Status:** ✅ Done — avg 4.395s vs SSD baseline 4.405s — 0.010s difference, within noise. tmpfs gives no benefit on a warm page cache.

---

### 48. Drop page cache to get cold baseline
**Run as:** `student`
```bash
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
free -h
```
**Status:** ✅ Done — page cache flushed, RAM dropped from ~290 GB used to 6.8 GB used. /dev/shm file survived (tmpfs pages not dropped by drop_caches).

---

### 49. Cold SSD run + warm SSD run (3 runs, 32T node0)
**Run as:** `student`
```bash
for i in 1 2 3; do
  START=$(date +%s%3N)
  numactl --cpunodebind=0 --membind=0 kraken2 --db ~/data/kraken2_db --threads 32 \
    --report /dev/null --output /dev/null ~/results/basecalling/reads_hac.fastq 2>/dev/null
  END=$(date +%s%3N)
  echo "SSD run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"
done
```
**Status:** ✅ Done — run 1 (cold): 10.894s, runs 2-3 (warm): 4.628s / 4.631s. Cold overhead = 6.25s for loading 8 GB DB + 703 MB FASTQ from NVMe.

---

### 50. tmpfs run after cache drop (warm DB, tmpfs FASTQ)
**Run as:** `student`
```bash
for i in 1 2 3; do
  START=$(date +%s%3N)
  numactl --cpunodebind=0 --membind=0 kraken2 --db ~/data/kraken2_db --threads 32 \
    --report /dev/null --output /dev/null /dev/shm/reads_hac.fastq 2>/dev/null
  END=$(date +%s%3N)
  echo "tmpfs run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"
done
```
**Status:** ✅ Done — avg 4.649s vs warm SSD 4.648s — identical. Confirms tmpfs = warm SSD = same DRAM copy overhead.

---

### 51. Cleanup tmpfs
**Run as:** `student`
```bash
rm /dev/shm/reads_hac.fastq
```
**Status:** ✅ Done

---

## Next Steps

**Note (2026-06-15):** Dorado GPU profiling (Step 13) is DEPRIORITIZED as of Meeting 4 (2026-05-28). Summer focus is Kraken2 source optimisation.

AccuracyDrift experiment commands (2026-05-30 to 2026-06-13) are NOT logged here — they are in `AccuracyDrift/COMMANDS.md`. That experiment ran all 3 read models × 5 databases × all thread counts on Luna and Orion, plus AccuracyChase PlusPF 103 GB cold runs.

Next Luna work: Kraken2 optimisation implementation (proposals A/D/E/F). Commands will be logged in a new session below or in the AccuracyDrift/COMMANDS.md per the relevant experiment.
