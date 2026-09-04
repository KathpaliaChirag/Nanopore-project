# command_log.md

running receipt of every command actually run for the cache_simulation track, in order.
mirrors the pattern used in `plan_paper/command_log.md`. machine: Luna (`student@dell-R760`) unless noted.

---

### [1] Persistent, internet-connected tmux session

**Why:** Luna has no direct internet - `iitd-login.py` authenticates through the IITD proxy and
sends a heartbeat every ~100s to keep the session alive. running it inside tmux means it survives
an SSH disconnect. the login handshake itself needs the proxy vars unset (direct access), which is
why the login command starts with `env -u http_proxy ...` even though step 2 sets those vars globally
for everything else.

```bash
tmux new -s cache_sim
env -u http_proxy -u https_proxy -u HTTP_proxy -u HTTPS_proxy python3 ~/iitd-login.py -d
# entered kerberos ID + password, detached with Ctrl+B, D
```

**Status:** done - authenticated, heartbeat running.

---

### [2] Set proxy env vars for all other tools

**Why:** `iitd-login.py` only authenticates the proxy server itself - every other tool (git, pip,
apt, curl, wget) needs `http_proxy`/`https_proxy` (and the uppercase variants some tools check
instead) actually set to route traffic through it, or they'll try direct access and fail/hang on
a machine with no direct route.

```bash
echo 'export http_proxy=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
echo 'export https_proxy=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
echo 'export HTTP_proxy=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
echo 'export HTTPS_proxy=http://proxy61.iitd.ac.in:3128' >> ~/.bashrc
source ~/.bashrc
```

**Status:** done.

---

### [3] Verify proxy works, create cache_simulation folder

**Why:** confirm the shell actually uses the proxy (separate from the login script authenticating
it) before building anything on top of it - avoids a confusing hang/timeout later if a tool silently
ignored the env vars or the login session had already expired.

```bash
wget -q --spider http://google.com && echo "internet OK" || echo "internet FAILED"
mkdir -p ~/cache_simulation
cd ~/cache_simulation
pwd
```

**Result:** `internet OK`, folder created at `/home/student/cache_simulation`.

---

### [4] Clone Sniper, confirm "latest version"

**Why:** Sniper ships as source, no package manager install. cloned to inspect its own build docs
before guessing dependencies. checked for release tags first since "latest version" could mean
either latest tagged release or latest commit on `master` - repo turned out to have **no tags**,
so `master` HEAD *is* the latest version by definition here.

```bash
cd ~/cache_simulation
git clone https://github.com/snipersim/snipersim.git
cd snipersim
git tag --sort=-creatordate | head -10
git log -1 --format="%H %ci"
```

**Result:** no tags exist. HEAD = `56505e42fd98bca863fac181e769bd3c98d2bb3`, dated 2026-05-23.
cloned into `/home/student/cache_simulation/snipersim`.

---

### [5] Read build docs, extract real dependency list

**Why:** `COMPILATION` turned out to document building *target apps to run under* Sniper, not
Sniper itself. `Makefile`/`Makefile.config` are the real build entry point (requires GCC >= 5).
`docker/Dockerfile*` gave the maintainers' own dependency list per Ubuntu version - more reliable
than guessing package names from the manual.

```bash
cat README.md | head -60
cat COMPILATION | head -80
cat Makefile | head -40
cat Makefile.config | head -60
find docker -iname "Dockerfile*" -exec cat {} \;
```

**Result - dependency list (Ubuntu 22.04/24.04 lines, closest match to Luna):**
`python3 python3-dev python3-venv screen tmux binutils libc6:i386 libncurses5:i386 libstdc++6:i386`
(needs i386 arch added: `dpkg --add-architecture i386`),
`automake build-essential cmake curl wget libboost-dev libsqlite3-dev zlib1g-dev libbz2-dev libdb++-dev`.
RISC-V toolchain deps and helper utils (gdb, gfortran, git, g++, vim) also listed but not required
for a pure x86 build.

---

### [6] Environment check before installing anything (sudo, existing packages)

**Why:** Luna is a shared account (`student`) - `apt-get install` needs sudo, and installing i386
architecture support system-wide affects the whole shared machine, not just this user. checking
what's already installed and whether sudo actually works before touching packages, rather than
blindly running the full Docker install list.

```bash
sudo -n true 2>&1 && echo "HAVE SUDO" || echo "NO PASSWORDLESS SUDO"
gcc --version | head -1
g++ --version | head -1
dpkg --print-foreign-architectures
for pkg in automake build-essential cmake libboost-dev libsqlite3-dev zlib1g-dev libbz2-dev libdb++-dev; do
  dpkg -s "$pkg" >/dev/null 2>&1 && echo "$pkg: installed" || echo "$pkg: MISSING"
done
```

**Result:** no passwordless sudo (password prompt required, not a permissions block - fine since CK
runs these interactively). gcc/g++ 11.4.0 (>=5 requirement met). i386 foreign arch already
registered. missing: `automake`, `libboost-dev`, `libsqlite3-dev`, `libbz2-dev`, `libdb++-dev`.
already present: `build-essential`, `cmake`, `zlib1g-dev`.

---

### [7] Install missing build dependencies

**Why:** installs the packages step 6 found missing. added three i386 runtime libs
(`libc6:i386`, `libncurses5:i386`, `libstdc++6:i386`) not covered by the step-6 check, since Sniper
links against Intel Pin (32-bit-capable even on a 64-bit target) - skipping these tends to surface
as a cryptic linker/runtime error deep into the build rather than a clear missing-package message
now. this is a machine-wide `apt install` on a shared account, not scoped to just `student`'s home.

```bash
sudo apt-get update
sudo apt-get install -y automake libboost-dev libsqlite3-dev libbz2-dev libdb++-dev libc6:i386 libncurses5:i386 libstdc++6:i386
```

**Result:** clean install, no errors. 18 new packages (incl. transitive deps: `libboost1.74-dev`,
`libdb5.3++-dev`, `autoconf`, `m4`, `libtinfo5:i386`, `libgpm2:i386`). `libc6:i386` was already the
newest version.

---

### [8] Build Sniper

**Why:** actual compile - `make` runs the `all` target: `dependencies` step first (downloads the
Intel Pin toolkit over the network via the proxy), then compiles the simulator. run inside the
`cache_sim` tmux session (already open) so an SSH drop mid-build doesn't kill it, output teed to a
log file for post-mortem if it failed.

```bash
cd ~/cache_simulation/snipersim
make 2>&1 | tee build.log
```

**Result:** `[SUCCESS]` - full build completed clean (dependencies, standalone lib, pin-frontend,
sift lib, all linked) with no errors in the tail output.

---

### [9] Disk space check (shared machine)

**Why:** Sniper builds + later trace-based simulation runs (SIFT trace files, run outputs) can eat
disk fast, and this is shared across several accounts - checking headroom now before a big run
fills the disk and breaks everyone, not just this work. `sudo` needed on the per-user `du` or it
hits permission-denied on other users' homes and gives an incomplete total.

```bash
df -h /home
sudo du -sh /home/*/ 2>/dev/null | sort -rh
```

**Result:** `/` (938G total) at 85% used, **138G free**. per-user: `chayanika` 401G, `student`
(this account) 324G, `dell` 63M, `vijay` 16M, `kolin` 720K. flagged as tight headroom - worth
watching once trace generation starts, not blocking yet.

---

### [10] Smoke test - fast-forward and detailed mode on `/bin/true`

**Why:** a clean `make` doesn't guarantee the simulator actually runs correctly. these are the two
commands from Sniper's own README, verified by the maintainers. `/bin/true` is the smallest
possible target (does nothing, exits immediately) - the point is isolating "does the harness itself
work" from "is the workload configured right", before touching any real workload.

```bash
cd ~/cache_simulation/snipersim
./run-sniper -n 1 --fast-forward -d /tmp/sniper-smoke-$$ -caddress_translation_schemes/baseline -- /bin/true
./run-sniper -n 1 -d /tmp/sniper-smoke-$$-detailed -caddress_translation_schemes/baseline -- /bin/true
```

**Result:** both exit 0. fast-forward mode skips the timing model entirely (its printed
`166684.00 IPC` is not a real number, ignore it) - it just confirms the harness boots, builds the
memory hierarchy, runs the trace, and exits clean. detailed mode is the meaningful one: interval
core model actually engaged, produced a physically believable `0.66 IPC` / `0.3M cycles`, and the
internal memory-model sanity check (`74 unique VA->PA mappings, 0 violations detected`,
`1983 unique data cache lines accessed`) confirms address translation and cache-line tracking
stayed consistent through a real run.

**Note for later:** the cache hierarchy printed (L1-I 64 sets/16-way, L1-D 64 sets/12-way, L2 2048
sets/16-way) is Sniper's shipped default config, not yet set to model Luna's or Orion's real cache
geometry - that's a config file to point at once we reach the actual associativity study, not
something this smoke test was meant to set.

**Status: build verified working end-to-end.**

---

### [11] Read Luna's real cache geometry from sysfs

**Why:** project memory flags generic vendor-spec-sheet associativity claims as a repeated citation
trap on this exact silicon (e.g. the retracted Orion "8-way L2" claim) - Linux's own
`/sys/devices/system/cpu/cpu0/cache/index*/` exposes the kernel's read of the real hardware
topology, authoritative for *this* machine specifically, not a generic SKU spec sheet. sizes were
already known from `lscpu` but associativity ("ways") was not, for any level.

```bash
for i in 0 1 2 3; do
  echo "--- index$i ---"
  for f in size ways_of_associativity number_of_sets coherency_line_size shared_cpu_list; do
    echo "$f: $(cat /sys/devices/system/cpu/cpu0/cache/index$i/$f 2>/dev/null)"
  done
done
```

**Result - real, hardware-read cache geometry:**

| Level | Size | Ways | Sets | Line |
|---|---|---|---|---|
| L1d | 48K | 12-way | 64 | 64B |
| L1i | 32K | 8-way | 64 | 64B |
| L2 (private/core) | 2048K | 16-way | 2048 | 64B |
| L3/LLC (shared, 96 cores/socket) | 107520K (~105MB) | 15-way | 114688 | 64B |

L1d/L2 geometry happens to match Sniper's shipped default config exactly (coincidence, not by
design); L1i and L3 associativity differ from the default and needed this real read.

---

### [12]-[13] Learn Sniper's config format from real examples

**Why:** rather than guess `.cfg` key names, read `base.cfg` (the shared per-cache-level template:
`cache_size`, `associativity`, `cache_block_size`, `replacement_policy`, `shared_cores`, etc.) and
`gainestown.cfg` (a real Xeon config, showing how a per-machine file `#include`s a base topology
then overrides specific sections - `l3_cache`, `dram`, `network` - while leaving L1/L2 to whatever
the included base already sets).

```bash
cd ~/cache_simulation/snipersim/config
ls
cat base.cfg | head -20
grep -n -A 30 "^\[perf_model/l1_dcache\]\|^\[perf_model/l1_icache\]\|^\[perf_model/l2_cache\]\|^\[perf_model/l3_cache\]" *.cfg
cat gainestown.cfg
```

**Result:** confirmed format. key fields per cache section: `cache_size` (KB), `associativity`,
`cache_block_size`, `replacement_policy`, `shared_cores` (how many cores share this level - this is
how a machine-wide LLC gets encoded, not per-core). `gainestown.cfg` pattern: `#include nehalem`
pulls in a base topology, then overrides `[perf_model/l3_cache]`, `[perf_model/dram]`, `[network]`
with machine-specific real numbers, `[perf_model/core] frequency = 2.66` for clock speed.
`luna.cfg` will follow the same pattern: include a base, override L1/L2/L3 with the real sysfs
numbers from step 11, `shared_cores` set to reflect a 96-core-per-socket LLC.

---

### [15] Get real clock frequency

**Why:** the last missing real number for `luna.cfg`'s `[perf_model/core] frequency` field.

```bash
lscpu | grep -i "MHz\|model name"
```

**Result:** Intel Xeon Platinum 8468 (Sapphire Rapids). `lscpu` gives min/max turbo range
(800/3800 MHz), neither of which is the right value - existing Sniper machine configs
(`gainestown.cfg`) use the documented **base** clock, not turbo. used **2.1 GHz**, the 8468's
published Intel base-clock spec - flagged in the config as a looked-up spec value, not something
read off the running hardware like the cache geometry.

---

### [16] Write `luna.cfg`

**Why:** assembled from steps 11-15's real numbers, following the `nehalem.cfg`/`gainestown.cfg`
inheritance pattern from steps 12-14. written first into the repo (`cache_simulation/configs/luna.cfg`)
so it's version-controlled, then mirrored onto Luna itself.

**What's real (sysfs-measured, step 11) vs. not:** L1i/L1d/L2/L3 size, associativity, block size are
real. L3 `data_access_time`/`tags_access_time` are placeholders (sysfs exposes geometry, not
latency) carried from `beckton.cfg`'s similarly-sized LLC - need a real membench/pointer-chase
measurement later. `replacement_policy = lru` for L3 is Sniper's standard default, not verified -
project memory already flags this exact machine's real LLC policy as an undocumented adaptive
bimodal scheme, only reverse-engineered through Skylake-gen chips, not confirmed for Sapphire
Rapids. `[perf_model/dram]` section and the core timing model itself (`interval_timer`, branch
predictor) are inherited from Sniper's stock "nehalem" core model, since Sniper ships no
Sapphire-Rapids/Golden-Cove core model - only the cache hierarchy is asserted as this-machine-real.

file committed to repo at `cache_simulation/configs/luna.cfg`. next: mirror onto Luna at
`~/cache_simulation/snipersim/config/luna.cfg` and smoke-test with it.
