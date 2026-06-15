# Minerva — Sudo To-Do List
> Run everything in this file as `chayanika` (the sudo account).
> **No `sudo apt install` commands** — tool installs use source builds or dpkg.
> Work top to bottom. Each section has a verify step — confirm it passes before moving on.

---

## Before Anything — Prerequisites

### Check 1: Internet is working
The IITD proxy must be logged in before wget will work. Run this to confirm:
```bash
curl -s http://example.com | grep -o "Example Domain"
```
Expected output: `Example Domain`

If it prints nothing or errors → internet is not active. Start the login script first:
```bash
tmux new -s internet
python3 ~/iitd-login.py -d
# Ctrl+B then D to detach once you see "Logged in."
```

### Check 2: Disk space — CRITICAL
Root partition was at 100% as of 2026-05-27. Check current state before installing anything:
```bash
df -h /
```

| Free space | What you can do |
|---|---|
| < 2 GB | Stop. Disk needs clearing before any installs. |
| 2–6 GB | Safe for Steps 1–4. Skip VTune. |
| > 6 GB | Safe for everything including VTune (~5 GB). |

---

## Step 1 — Fix perf Hardware Counters [ DONE]

Already set to 1. Confirmed. No action needed.

---

## Step 2 — Fix nsys PATH System-Wide [ DONE]

Already added to `/etc/profile.d/nsys.sh`. Confirmed working.

---

## Step 3 — Install valgrind [ ]

**What this does:** Needed for cachegrind — simulates the full L1/L2/L3 cache hierarchy and gives per-function LLC miss counts for `CompactHashTable::Get()`. The key data WSL2 couldn't provide.

```bash
git clone https://sourceware.org/git/valgrind.git ~/valgrind-src
cd ~/valgrind-src
./autogen.sh
./configure --prefix=/usr/local
make -j8
sudo make install
```

**Verify:**
```bash
valgrind --version
# Expected: valgrind-3.x.x
```

**Possible error:** `./autogen.sh: command not found` or `autoconf not found`
→ autogen tools may be missing. Try:
```bash
conda install -c conda-forge autoconf automake libtool -y
./autogen.sh
```

**Possible error:** `make -j8` fails with compilation errors
→ Try with a single thread to see the actual error:
```bash
make -j1 2>&1 | tail -30
```

---

## Step 4 — LIKWID Kernel Module [ ]

**What this does:** LIKWID measures real memory bandwidth in GB/s by reading MSR (Model-Specific Register) counters. The `msr` kernel module must be loaded and LIKWID binaries need the setuid bit so regular users can run them without sudo.

> **Note:** Install LIKWID first (see `install_tools.md`), then come back to this step.

**Check if msr is already loaded:**
```bash
lsmod | grep msr
```
If a line appears → module already loaded, skip the modprobe line.

**Load the module and persist:**
```bash
sudo modprobe msr
echo 'msr' | sudo tee -a /etc/modules
```

**Set setuid on LIKWID binaries:**
```bash
sudo chmod +s /usr/local/bin/likwid-perfctr
sudo chmod +s /usr/local/bin/likwid-pin
```

**Verify:**
```bash
lsmod | grep msr
# Expected: msr line appears

su - CK -c "likwid-perfctr -C 0 -g CLOCK -- ls" 2>&1 | tail -5
# Expected: a table with frequency/clock data — NOT "permission denied"
```

**Possible error:** `modprobe: FATAL: Module msr not found`
→ Kernel was built without MSR support. LIKWID hardware counters won't work — everything else in the pipeline still works fine.

**Possible error:** `chmod: cannot access '/usr/local/bin/likwid-perfctr': No such file or directory`
→ LIKWID was installed to a different prefix. Find it:
```bash
which likwid-perfctr
```
Use that path instead.

---

## Step 5 — Intel VTune [ ]

**What this does:** The most detailed CPU profiler for Intel hardware. Gives a CPI waterfall (frontend bound / backend bound / memory bound / core bound) and per-source-line memory stall attribution — tells us exactly which line in `CompactHashTable::Get()` is stalling. No other tool provides this.

> **Disk check before starting:** VTune is ~5 GB.
> ```bash
> df -h /
> ```
> Only proceed if `Avail` shows at least 6 GB free.

**Step 5a — Download the standalone installer:**

Download the Linux offline installer from Intel's website:
`https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html`

Download to your local machine / WSL2 and transfer to Minerva:
```bash
# From WSL2:
rsync vtune_profiler_*.sh chayanika@minerva:~/
```

**Step 5b — Run the installer:**
```bash
chmod +x ~/vtune_installer.sh
sudo ~/vtune_installer.sh -a --eula accept --install-dir /opt/intel/vtune
```

**Step 5c — Make available to all users:**
```bash
echo 'source /opt/intel/vtune/latest/env/vars.sh' | sudo tee /etc/profile.d/vtune.sh
source /etc/profile.d/vtune.sh
```

**Verify:**
```bash
vtune --version
# Expected: Intel(R) VTune(TM) Profiler x.x
```

**Possible error:** `vtune: command not found` after sourcing
→ Find the actual env script path:
```bash
find /opt/intel -name "vars.sh" 2>/dev/null
```
Update the profile.d line with whatever path it returns.

---

## Step 6 — NVIDIA DCGM [ ]

**What this does:** Monitors the A40 GPUs during Dorado runs — tracks power draw over time, GPU temperature, whether the GPU is thermal-throttling, and sustained memory bandwidth. Tells us if the A40 is running at full capacity or being limited during long jobs.

**Step 6a — Download the .deb directly from NVIDIA:**
```bash
# Get the latest Ubuntu 22.04 .deb URL from: https://developer.nvidia.com/dcgm
wget <dcgm-ubuntu2204-deb-url> -O ~/dcgm.deb
```

**Step 6b — Install via dpkg:**
```bash
sudo dpkg -i ~/dcgm.deb
```

**Step 6c — Start the service:**
```bash
sudo systemctl enable nvidia-dcgm
sudo systemctl start nvidia-dcgm
```

**Verify:**
```bash
sudo systemctl status nvidia-dcgm
# Expected: active (running)

dcgmi discovery -l
# Expected: lists GPU 0 and GPU 1 (both A40s)
```

**Possible error:** `dpkg: dependency problems`
→ DCGM needs NVIDIA libraries. Check what's installed:
```bash
dpkg -l | grep nvidia | head -10
```
If CUDA libraries are present, dependencies should already be satisfied.

**Possible error:** `Unit nvidia-dcgm.service not found`
→ Try the host engine directly:
```bash
sudo nv-hostengine
dcgmi discovery -l
```

---

## Step 7 — Final Verification [ ]

Run this after all steps above are done:
```bash
echo "=== perf paranoia ===" && cat /proc/sys/kernel/perf_event_paranoid
echo "=== nsys ===" && nsys --version 2>/dev/null | head -1 || echo "FAIL"
echo "=== valgrind ===" && valgrind --version 2>/dev/null || echo "FAIL"
echo "=== msr module ===" && lsmod | grep msr || echo "not loaded"
echo "=== likwid setuid ===" && ls -la $(which likwid-perfctr) 2>/dev/null || echo "not installed"
echo "=== vtune ===" && vtune --version 2>/dev/null | head -1 || echo "not installed yet"
echo "=== dcgm ===" && dcgmi discovery -l 2>/dev/null || echo "not installed yet"
echo "=== disk ===" && df -h /
```

---

## Summary Checklist

```
[ ] Check 1: internet working (iitd-login.py running in tmux)
[ ] Check 2: disk space confirmed
[x] Step 1:  perf_event_paranoid = 1
[x] Step 2:  nsys PATH fixed
[ ] Step 3:  valgrind installed (source build)
[ ] Step 4:  msr module loaded + persisted + LIKWID setuid
[ ] Step 5:  VTune standalone installer run (only if disk >= 6 GB free)
[ ] Step 6:  DCGM dpkg installed + service running
[ ] Step 7:  Final verification passes

--- Tool installs (no sudo needed) ---
See: Minerva/install_tools.md
```
