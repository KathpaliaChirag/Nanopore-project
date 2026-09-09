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

---

### [17] Mirror luna.cfg onto Luna

pasted the file content directly via heredoc (Luna has no clone of this GitHub repo set up -
separate from the `kraken2-src-fresh` checkout used elsewhere). Verified via `wc -l` (47 lines) and
`tail -5` matching the source file - a self-referential `diff` check in the same command was a
mistake (nested heredoc doesn't expand that way) and can be ignored, it wasn't testing anything.

---

### [18]-[21] Debugging: three bugs found getting `-c luna` to actually apply

**Bug 1 - wrong invocation syntax.** First attempt: `-c config/luna.cfg`. Silently fell back to
defaults with no error (identical output to the very first no-config smoke test) - `run-sniper
--help` showed the real syntax is `-c <name[.cfg]>`, resolved by basename from `config/`
internally, not a path.

**Bug 2 - two separate `-c` flags don't merge.** Fixed to `-c luna` but paired with a second,
separate `-caddress_translation_schemes/baseline` flag (copied from the original README smoke
test) - still identical default output. `-c` takes a **comma-joined list in one flag**
(`-c name1,name2,...`), not multiple `-c` invocations; the second flag was silently replacing the
first entirely.

**Bug 3 - load order matters, and the "default" chain isn't what luna.cfg was built on.** Fixed to
`-c luna,address_translation_schemes/baseline` (single flag, comma-joined) - this time got a real
error: `Configuration value general/enable_userspace_mimicos not found`, but also confirmed
`Core 0 at 2.10 GHz` in the output, proving `luna.cfg` *was* now loading. Root cause, found by
reading `run-sniper`'s source and the actual include chain:
- `run-sniper` always auto-prepends `-c config/base.cfg` - that was never the missing piece.
- `address_translation_schemes/baseline.cfg` is the real "full system" config: it `#include`s
  `common_configs/base_system_sniperspace.cfg` (sets `enable_userspace_mimicos` and other required
  generals), `core_configs/meteor_lake_pcore.cfg` (a 2023 Redwood Cove P-core model - **not**
  `nehalem`, which is what `luna.cfg` was originally built on), MMU/pagetable/DRAM configs.
- with `luna,address_translation_schemes/baseline` in that order, `baseline`'s
  `meteor_lake_pcore.cfg` loaded **after** `luna.cfg` and silently clobbered our cache overrides -
  explains why L1-I kept showing 16-way (meteor's default) instead of our real 8-way across every
  earlier attempt.
- separately: `meteor_lake_pcore.cfg` sets `[perf_model/cache] levels = 2` and models the LLC as
  **NUCA** (distributed per-core mesh slices), not a flat `[perf_model/l3_cache]` - the
  `l3_cache` section `luna.cfg` originally wrote was dead code in this chain, never read at all.

**Fix applied:** rewrote `luna.cfg` as a pure override layer (no `#include`, meant to load *after*
`address_translation_schemes/baseline` via `-c address_translation_schemes/baseline,luna`).
Rebuilt on `meteor_lake_pcore` instead of `nehalem` - L1d/L2 already matched Luna's real numbers
exactly by coincidence, only L1i and the NUCA LLC slice needed overriding. Real 107520 KB total
LLC / 96 real cores per socket = exactly 1120 KB/core slice (clean division), associativity 15
carried from the sysfs aggregate reading (assumed uniform per slice - not independently verified,
since sysfs only exposes the logical whole-cache view). NUCA latency/bandwidth left at
`meteor_lake_pcore`'s own placeholders (still not real, just no worse than the beckton-derived
guess the old l3_cache section had). committed, next: re-test with the corrected file and
invocation order.

---

### [22]-[24] Bug 2/3 correction, real cache-size validation bug, final working invocation

**Correction to Bug 2/3 above:** the `-c name1,name2` comma-joined single-flag theory was itself
wrong, found by reading `run-sniper`'s actual argument parser (`grep`'d for the `-c` handling
block). The real logic:
- `-c key=value` -> a sniper-option override
- `-c obj:name` or **any `-c` value containing a comma** -> routed to `make_hetero_config()`, which
  assigns **different configs to different cores** in a heterogeneous multi-core setup - NOT
  general file-chaining. our `luna,address_translation_schemes/baseline` was silently
  misinterpreted as a heterogeneous-core request the whole time, which is why it kept behaving
  strangely regardless of comma order.
- a **plain name with no comma** -> appended to a `configfiles` list via `configfiles.extend(...)`

So **separate `-c` flags DO chain correctly** (later files override earlier on conflicting keys) -
the comma-list "fix" in step 20 was the actual bug, not a fix. Correct form:
`-c address_translation_schemes/baseline -c luna` (two separate flags, baseline first).

```bash
grep -n "config_list\|configs.append\|split(',')\|'-c'\|args.config\|def.*config" ~/cache_simulation/snipersim/run-sniper
sed -n '230,270p' ~/cache_simulation/snipersim/run-sniper
```

**Retest with corrected invocation surfaced a real, separate bug:**

```bash
./run-sniper -c address_translation_schemes/baseline -c luna -n 1 -d /tmp/sniper-luna-smoke7-$$ -- /bin/true
```

Result: `*ERROR* Invalid cache configuration: size(1120 Kb) != sets(1194) * associativity(15) *
block_size(64)`, process killed by SIGABRT. Sniper strictly validates `size = sets * associativity
* block_size` and aborts rather than rounding - our NUCA per-core slice target (1120 KB, from
107520/96) doesn't factor evenly at 15-way/64B (needs a fractional 1194.67 sets). **Fix:** rounded
to the nearest value that does divide evenly - **1125 KB** (1200 sets exactly), a further 0.45%
deviation on top of the already-approximate even-split-across-cores assumption. Documented both
approximation layers explicitly in `luna.cfg`'s comments rather than presenting 1125 as if it were
as real as the sysfs-measured numbers.

**Status:** `luna.cfg` corrected (1120 -> 1125 KB), invocation corrected (two separate `-c` flags,
baseline first). next: re-test on Luna with both fixes applied together.

---

### [25] Retest with both fixes - new bug: SIGSEGV in CacheSet::find

```bash
./run-sniper -c address_translation_schemes/baseline -c luna -n 1 -d /tmp/sniper-luna-smoke8-$$ -- /bin/true
```

**Result:** cache creation now correct and matches real numbers exactly (`nuca-cache 1200 sets,
15-way`, `L1-I 8-way`, `L1-D 12-way`, `L2 16-way`) - the invocation/config-loading bugs are fully
resolved. But crashed with `SIGSEGV` inside `cache_set.cc:CacheSet::find`, called from
`cache.cc:Cache::peekSingleLine`, called from `dram_directory_cntlr.cc:handleMsgFromL2Cache` - a
real memory-access bug during simulation, not a config-loading problem.

---

### [26] SSH access granted for direct inspection

CK generated a dedicated ed25519 keypair (`claude-code-luna-inspect`) locally and added the public
half to `~/.ssh/authorized_keys` on Luna - grants login only, easily revocable by removing the line.
CK still runs all substantive/build/rerun commands; direct SSH is for read-only source inspection
only, to cut round-trip time on debugging.

---

### [27] Root cause of the SIGSEGV, found via direct source inspection

Initial hypothesis (non-power-of-2 `num_sets` requires `address_hash != mask`) was checked against
`cache_base.cc`'s actual `parseAddressHash`/hash enum and ruled out - our NUCA section inherits
`address_hash = "xor_mod"` from `meteor_lake_pcore.cfg`, not `mask`, so the `HASH_MASK`-specific
assert doesn't even apply.

Real bug, found in `common/core/memory_subsystem/cache/cache_base.cc`'s `splitAddress()`,
`HASH_XOR_MOD` case:

```cpp
UInt64 si = block_num % m_num_sets;
UInt64 ti = (block_num >> m_log_num_sets) % m_num_sets;
set_index = (si ^ ti);
```

`si` and `ti` are each `< m_num_sets`, but **XOR of two values only stays within `[0, m_num_sets)`
when `m_num_sets` is a power of 2** - for our 1200-set NUCA slice (not a power of 2), `si ^ ti` can
exceed 1200, producing an out-of-bounds `set_index` that indexes past the real sets array -
exactly the `CacheSet::find` segfault. `HASH_MASK` and `HASH_PRIME_DIS` have the same power-of-2
dependency (both use `m_log_num_sets` as a bit-shift); only plain-modulo hashes (`HASH_MOD`,
`HASH_MER_MOD`) are safe for an arbitrary set count.

**Fix:** added `address_hash = mod` explicitly to `luna.cfg`'s `[perf_model/nuca]` section only
(our sole non-power-of-2 cache - L1i/L1d/L2 keep the inherited `xor_mod` since their set counts,
64/64/2048, are already powers of 2 and unaffected by this bug). Preserves the real 1125KB/1200-set
numbers rather than distorting them further to force a power-of-2 count. committed, next: retest.

---

### [28] Retest with the hash fix - clean run

```bash
./run-sniper -c address_translation_schemes/baseline -c luna -n 1 -d /tmp/sniper-luna-smoke9-$$ -- /bin/true
```

**Result: clean end-to-end run.** `1.09 IPC` (real, believable detailed-mode number, no crash),
`[SNIPER] End` reached normally, MMU sanity check clean (74 unique VA->PA/PA->VA mappings, 0
violations). `luna.cfg` is now fully working with Luna's real cache hierarchy - L1i 32K/8-way,
L1d 48K/12-way, L2 2MB/16-way, LLC modeled as 96x 1125KB/15-way NUCA slices (`mod` hash) -
correctly loaded via `-c address_translation_schemes/baseline -c luna`.

**Status: luna.cfg complete and verified. Toolchain + real-machine cache config both done.**

**Workflow note:** from this point, CK granted direct SSH access (step 26) to run commands, not
just inspect - narrating each command/why/output here same as before, still committing+pushing
after every step.

---

### [29]-[35] First real workload attempt: tracing kraken2's S2 baseline binary

**Goal:** trace a real kraken2 classify run through Sniper (not just `/bin/true`), scoped to a tiny
synthetic workload first per CK's explicit choice, to prove the pipeline works before any real
associativity/eviction experiment. Chose `sample_targeted` DB (50MB `hash.k2d`) since it's the same
DB the real associativity sweep already used on native hardware - future Sniper numbers are
directly comparable to real measurements CK already has.

**[29] Created a tiny workload:** `head -40` (10 FASTQ reads) of a real basecalled file into
`~/cache_simulation/workloads/tiny_10reads.fastq` (20K).

**[30] Native sanity check** (isolate "does the workload work" from "does Sniper handle it"):
```bash
~/chirag_K/tools/kraken2-fresh-bin-s2-baseline/kraken2 --db .../sample_targeted --threads 1 \
  --output ... --report ... tiny_10reads.fastq
```
Result: exit 0, 7/10 classified, 51ms.

**[31] First Sniper fast-forward attempt with the same command - failed silently.** Reported only
`0.2M instructions` (identical to the trivial `/bin/true` baseline) and produced no output files -
kraken2 never actually ran, no error surfaced through the normal log.

**[32] Verbose mode (`-v`) revealed the real mechanism:** `run-sniper` calls a `record-trace` tool
which launches Intel **SDE** (Software Development Emulator, Pin-family instruction-level
instrumentation) on the target. Running SDE directly (bypassing Sniper's wrapper) surfaced the
real error: `zfstream.cc:182: cvifstream::cvifstream(...): assertion "this->stream != NULL" failed`.

**[33] Isolated the cause via elimination:**
- `kraken2 --help` (zero real file access) under SDE hit the **exact same crash** - ruled out
  DB/fastq file access as the trigger; failure is at process-start time.
- grepped kraken2's own source tree for `cvifstream`/`zfstream` - **not found**, ruling out a
  kraken2-side bug.
- `ldd` on the `kraken2` binary returned `not a dynamic executable` - the real tell.
- `file` on the binary confirmed it: **`kraken2: Perl script text executable`.**

**Root cause: `kraken2` is a Perl wrapper, not a compiled program.** The command users normally run
parses arguments in Perl then `exec`s the real compiled classifier as a subprocess. SDE/Sniper only
instruments compiled x86 machine code - pointing it at a Perl script meant it was instrumenting the
Perl interpreter's own startup, not kraken2, explaining every symptom (crash regardless of args,
"not a dynamic executable", near-zero simulated instructions).

**[34] Found the real binary and its exact invocation:**
```bash
file ~/chirag_K/tools/kraken2-fresh-bin-s2-baseline/*   # "classify" = real ELF, dynamically linked
strace -f -s 1000 -e trace=execve -o /tmp/strace_full.txt <kraken2 wrapper command>
grep classify /tmp/strace_full.txt
```
The Perl wrapper's friendly flags (`--db`, `--threads`, `--output`, `--report`) translate to
`classify`'s low-level flags: `-H <hash.k2d> -t <taxo.k2d> -o <opts.k2d> -p <threads> -T 0
-O <output> -Q 0 -R <report> -g 2 <fastq>`.

**[35] Verified the real binary directly, then through Sniper fast-forward:**
```bash
/home/student/chirag_K/tools/kraken2-fresh-bin-s2-baseline/classify \
  -H .../sample_targeted/hash.k2d -t .../taxo.k2d -o .../opts.k2d \
  -p 1 -T 0 -O ... -Q 0 -R ... -g 2 tiny_10reads.fastq
./run-sniper -c address_translation_schemes/baseline -c luna -n 1 --fast-forward -d ... -- <same classify command>
```

**Result: success.** Native run: exit 0, matches earlier. Sniper fast-forward: `25.1M instructions,
25.0M cycles, 1.01 IPC`, correct classification output (7/10 classified, matching native exactly),
clean `[SNIPER] End`. This is a genuine, non-trivial instruction count - the real pipeline works.

**Feasibility estimate for detailed mode:** fast-forward ran at ~5958 KIPS; earlier detailed-mode
smoke tests ran at ~32 KIPS. Extrapolating: `25.1M / 32K ≈ 784s (~13 min)` for a full detailed-mode
run of this same tiny workload - long but tractable for a first real experiment. next: run it.

---

### [36] First real detailed-mode run - launched in background

```bash
nohup ./run-sniper -c address_translation_schemes/baseline -c luna -n 1 \
  -d /home/student/cache_simulation/results_classify_detailed -- \
  /home/student/chirag_K/tools/kraken2-fresh-bin-s2-baseline/classify \
  -H .../hash.k2d -t .../taxo.k2d -o .../opts.k2d -p 1 -T 0 -O ... -Q 0 -R ... -g 2 \
  tiny_10reads.fastq > detailed_run.log 2>&1 < /dev/null &
disown
```

**Why background:** the ~13 minute estimate exceeds a reasonable synchronous wait; `nohup`+`disown`
means it survives an SSH disconnect same as the tmux session does. PID `3950949`, output to
`~/cache_simulation/detailed_run.log`. This is the first real detailed-mode (cycle-timing-accurate)
simulation of an actual kraken2 workload against Luna's real cache hierarchy - not yet an
associativity comparison (that needs multiple S2 binary variants run the same way), just proving a
full real run completes and produces sane stats.

Run used `-n 1` (single simulated core, matching `classify -p 1` single-threaded) - deliberately
the simplest case to validate the whole pipeline before adding thread-count complexity. Scaling to
multiple simulated cores later won't be "free" even though Luna has 96 real cores - project memory
already found Sniper simulating more target cores doesn't scale with host parallelism (16 target
cores only ran ~4x faster than 1, not 16x, since the simulator itself is the bottleneck).

---

### [37] Detailed-mode run completed - full results

**Result: completed in 113.63s** (much faster than the ~784s/13min estimate - that estimate came
from the trivial `/bin/true` test where fixed per-run overhead dominated; with more real
instructions, throughput amortizes much higher: **227.8 KIPS** actual vs. ~32 KIPS estimated).

- **25.1M instructions, 14.3M cycles, IPC = 1.76** - a real, physically plausible number (vs. the
  meaningless inflated/trivial numbers from `/bin/true` tests)
- Classification output correct: 7/10 classified, matching the native run and the earlier
  fast-forward run exactly
- MMU sanity check clean: 3146 unique VA->PA / PA->VA mappings, 0 violations
- **51,558 unique data cache lines accessed** - first real cache-footprint number from an actual
  workload run against Luna's real, sysfs-measured cache hierarchy
- Clean `[SNIPER] End`, no errors

**Status: first real, correctness-verified, detailed-mode simulation complete.** Toolchain, real
machine config, and a real traced workload are all now working end to end. Next decision: how to
scale this into an actual comparative experiment (multiple S2 cache-design binaries, thread counts,
larger/more representative workload sizes) for the thesis work itself.

---

### [38] First real comparative experiment: noatomics associativity sweep

**Why this specific comparison:** `ls ~/chirag_K/tools/kraken2-fresh-bin-s2-*` showed the
`lru-noatomics-{4,8,16,32,64}way` binaries are already built - contrary to
[[project_associativity_case_study_brief_sept2026]]'s note that they'd "never been built or
benchmarked" (that memory is now stale/superseded). This is exactly the highest-value comparison
that research brief identified: the *original* associativity sweep (more ways = worse wall-clock)
was contaminated by an atomics-contention confound; these noatomics binaries isolate real
associativity effects from that confound. Verified `lru-noatomics-4way`'s `classify` binary works
identically to baseline (exit 0, 7/10 classified) before batch-running.

**Batch script** (`~/cache_simulation/run_associativity_sweep.sh`): runs `baseline` +
5 noatomics widths through Sniper detailed mode sequentially, same tiny 10-read workload, same
`luna.cfg` real cache config, parses each run's instruction count/cycles/IPC/unique-cache-lines/
elapsed-time into `results_associativity_sweep/summary.txt`. Launched via `nohup`+`disown`
(PID 3952699), ~11 min estimated (6 runs x ~110s each, based on the single baseline run's actual
time). next: check results.

---

### [39] Associativity sweep results

All 6 runs completed clean. `results_associativity_sweep/summary.txt`:

| Variant | Instructions (M) | Cycles (M) | IPC | Unique cache lines | Wall time (s) |
|---|---|---|---|---|---|
| baseline | 25.1 | 14.2 | 1.77 | 51,557 | 114.9 |
| lru-noatomics-4way | 25.2 | 14.3 | 1.76 | 55,585 | 115.5 |
| lru-noatomics-8way | 25.4 | 14.4 | 1.76 | 67,873 | 121.3 |
| lru-noatomics-16way | 25.8 | 14.7 | 1.76 | 92,449 | 129.5 |
| lru-noatomics-32way | 26.8 | 15.1 | 1.78 | 141,600 | 138.6 |
| lru-noatomics-64way | 28.6 | 15.9 | 1.80 | 239,904 | 164.6 |

**Finding, stated carefully:** instructions, cycles, and unique cache lines touched all rise
**monotonically** with associativity (64-way touches ~4.7x more distinct cache lines than 4-way,
executes ~13% more instructions) - **even with the atomics-contention confound fully removed**
(these are the noatomics binaries). This does not reverse the original real-hardware finding
(more ways = worse wall-clock, from the Sept 2 sweep) - it **reproduces it under cleaner
conditions**, which is stronger evidence than the original real-hardware data alone: it shows the
slowdown-with-more-ways pattern is not an atomics artifact.

**More specific mechanism signal:** IPC stays essentially flat (1.76-1.80) across all widths - it
does not degrade as ways increase. This is consistent with (not proof of) the Sept 2 debate's
locked diagnosis that allocation/first-touch cost (touching a bigger per-set structure) dominates,
not scan cost - if scan cost or cache-miss stalls were the driver, IPC would be expected to *drop*
as ways increase; instead the slowdown shows up purely as *more total instructions executed*, with
each instruction costing about the same. Worth stating as "consistent with, adds simulation-based
evidence for" rather than "proves" - this is a 10-read synthetic workload, not yet a
representative-scale experiment.

**Status:** first real comparative cache-associativity experiment complete via Sniper. Summary CSV
committed at `cache_simulation/measurements/associativity_sweep_2026-09-08_summary.csv` (not
`results/` - that's repo-gitignored root-wide for large raw dumps; small summary tables belong in
`measurements/` instead).

---

### [40] Identifying true "no associativity" (S0) - the earlier "baseline" binary was mislabeled

CK asked for a proper proof-quality comparison of no-associativity vs 4-way vs 8-way. Before
running it, checked what `kraken2-fresh-bin-s2-baseline` (used as "baseline" in the step 38-39
sweep) actually is: `strings ... classify | grep s2_cache` found the `s2_cache` symbol present -
**it already has an S2 cache compiled in, it is NOT a true no-cache reference point.** The real
no-cache original is a separate source checkout: `kraken2-src-baseline/src/classify` - confirmed
via source grep (`grep -c s2_cache classify.cc` = 0) and binary strings (no S2 symbols at all).
This is the correct "S0" (true no-associativity) baseline going forward - the step 38-39 "baseline"
row should be understood as "an S2 cache config", not "no cache".

---

### [41] Scaled-up workload, gauged timing, launched full comparison

Created a 50-read workload (`workloads/50reads.fastq`, 5x the original 10-read sample) for a more
statistically meaningful sample. Verified S0 binary works correctly (34/50 classified, consistent
rate). Timed one S0 detailed run at 50 reads standalone first: **188.64s** - only ~1.6x longer than
the 10-read run despite 5x more reads, confirming most of the fixed cost is DB load, not
per-read classify work (~96s fixed/load cost + ~1.85s/read, derived from the 10-vs-50-read delta).

CK then asked about testing large DBs ("the 4gb ones"). No ~4GB DB actually exists as a built
index on Luna (`eskape_human_4gb_build.log` is a log only, never actually built) - real options are
50MB (`sample_targeted`), 7.5GB (`standard_8gb`), 15GB (`standard_16gb`), 104GB (`pluspf_103gb`).
Extrapolated from the fixed-cost measurement: if load cost scales ~linearly with DB size (default
kraken2 behavior, no `-M`, eagerly reads the whole DB into RAM - CK explicitly wants default
behavior tested, not `-M`), `standard_8gb` (~150x larger than `sample_targeted`) could take **~4
hours to load alone**, per binary. CK's call: time is not a concern, proceed on both `sample_targeted`
(50MB) and `standard_8gb` (~8GB) DBs, S0 vs 4-way vs 16-way, with live-updating output so progress
can be checked without waiting for the whole batch.

**Launched:** `~/cache_simulation/run_big_comparison.sh` (PID 4000205), 6 runs total (3 variants x
2 DBs, small DB first for fast feedback). Appends one row to
`results_big_comparison/live_summary.csv` after each run completes (instructions/cycles/IPC/unique
cache lines, plus real **L1/L2/NUCA-LLC hit-rate percentages** pulled from each run's `sim.stats` -
`L1-D.loads-where-data-{L1,L2,nuca-cache}` counts, giving an actual hardware-level hit-rate proof,
not just instruction counts). Timestamped start/done events also logged to
`results_big_comparison/progress.log`. next: monitor and report as rows land.

---

### [42] Second axis: real read-count scaling (reads_fast.fastq subsets)

CK asked to also test with a real, larger read-count workload (initially referenced as "4GB pod5" /
"1.04k reads" - clarified through investigation, not literally either). Found the actual file CK
meant: `~/chirag_K/results/basecalling/reads_fast.fastq` (708MB, **104,832 reads**, already used in
CK's prior real `perf`-based cache-miss profiling - a good apples-to-apples reference). Flagged the
full-file cost (~54 hours just for classification, extrapolated from the ~1.85s/read fixed-cost
measurement) before running it blind - CK chose to subsample instead: **2,000-read and 10,000-read
subsets** (`head -8000`/`head -40000` lines respectively - real reads from the front of the file,
not synthetic).

**Launched:** `~/cache_simulation/run_readcount_comparison.sh` (PID 4000993), running in **parallel**
with the DB-size job (independent experiments, Luna has 96 real cores, no reason to serialize).
Same S0/4-way/16-way variants, same `sample_targeted` (50MB) DB - deliberately NOT combined with
the 8GB DB axis, since combining both large-DB and large-read-count would multiply an already
multi-hour job further. Same live-updating pattern:
`results_readcount_comparison/live_summary.csv` (one row per completed run) and `progress.log`
(timestamped start/done). Estimated ~3hrs (2000-read x3 variants) + ~15.5hrs (10000-read x3
variants) ~= 18-19hrs total. next: monitor both jobs, report as they complete.

---

### [43] First results from the DB-size job: the cache's value flips with DB size

5 of 6 runs complete (8gb/16way still running). All completed cleanly with matching, correct
classification output (48/50 classified, 4% unclassified, identical across variants - not a bug).

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Unique cache lines | Wall time (s) |
|---|---|---|---|---|---|---|
| 50mb | S0 | 35.8 | 24.4 | 1.47 | 76,605 | 188.7 |
| 50mb | 4way | 39.7 | 26.7 | 1.48 | 76,963 | 204.4 |
| 50mb | 16way | 44.0 | 28.7 | 1.53 | 113,831 | 360.3 |
| 8gb | S0 | 68.1 | 51.7 | 1.32 | 186,523 | 748.3 |
| 8gb | 4way | 52.0 | 28.3 | 1.84 | 64,091 | 391.8 |

**Finding:** on the 50MB DB, the 4-way cache costs slightly more than no cache (matches the step
38-39 associativity-sweep pattern: cache bookkeeping overhead exceeds its benefit when direct
lookups into a small table are already cheap). **On the 7.5GB DB this completely flips** - the
identical 4-way cache uses **~24% fewer instructions**, touches **~2.9x fewer unique cache lines**
(64,091 vs 186,523), runs at **substantially higher IPC** (1.84 vs 1.32 - fewer stalls per
instruction, not just less total work), and finishes **~1.9x faster** (392s vs 748s) than no-cache
on the same DB and workload.

**Mechanism:** without a cache, every minimizer lookup re-probes the raw hash table directly -
cheap on a 50MB table (mostly stays warm), expensive on a 7.5GB table (scattered, mostly-cold
memory). A small thread-local cache intercepts repeated/nearby minimizers before they reach the
big table, so its payoff scales with how expensive a raw probe into the underlying table actually
is - i.e. with DB size. This is real, load-bearing evidence for the adaptive-cache thesis: the
associativity benefit is DB-size-dependent, not a fixed cost/benefit - worth checking whether
8gb/16way (still running) keeps improving or starts giving the gain back, matching the 50mb
pattern where wider associativity costs more.

**Status:** DB-size job 5/6 done, read-count job still on first run (2000reads/S0 in progress,
~62 min estimated). Both still logging live.

---

### [44] Third job: extending to 16GB and 103GB databases

CK asked to also test `standard_16gb` (15G) and `pluspf_103gb` (104G). **Correction to the earlier
~4hr/DB extrapolation:** the actual measured 50MB->7.5GB ratio only took DB load from 190s to 748s
(~4x), not the ~150x a naive byte-for-byte-linear assumption predicted - real bulk file reads use
vectorized/wide copy instructions, not one CPU instruction per byte, so cost scales far more gently
than that earlier estimate assumed. Power-law fit from the two real measured points suggests
~15min for 15GB, ~26min for 103GB - genuinely tractable, correcting the earlier pessimistic
warning. Verified disk headroom first (137G free, existing result dirs only a few MB each - no
concern).

**Launched:** `~/cache_simulation/run_bigdb_comparison.sh` (PID 4004452), same S0/4way/16way x
same 50-read workload, running as a **third parallel job** alongside the DB-size and read-count
jobs already in progress. Writes to `results_bigdb_comparison/live_summary.csv`. next: monitor all
three jobs together.

---

### [45] DB-size job (results_big_comparison) complete - the case for 4-way

All 6 runs done. Full table:

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Unique cache lines | Wall time (s) |
|---|---|---|---|---|---|---|
| 50mb | S0 | 35.8 | 24.4 | 1.47 | 76,605 | 188.7 |
| 50mb | 4way | 39.7 | 26.7 | 1.48 | 76,963 | 204.4 |
| 50mb | 16way | 44.0 | 28.7 | 1.53 | 113,831 | 360.3 |
| 8gb | S0 | 68.1 | 51.7 | 1.32 | 186,523 | 748.3 |
| 8gb | 4way | 52.0 | 28.3 | 1.84 | 64,091 | 391.8 |
| 8gb | 16way | 52.6 | 28.9 | 1.82 | 100,952 | 410.3 |

**The 4-way-is-the-sweet-spot case, quantified:** at 7.5GB scale, 4-way->16-way barely moves the
needle (+1.2% instructions, +4.7% wall time) - the extra ways buy almost nothing once the cache is
already intercepting most of the expensive raw-table probes. At 50MB scale, the same width increase
is expensive (+10.8% instructions, **+76% wall time**, 204s->360s) - overhead with no corresponding
payoff, since a small DB's direct probes are already cheap. **4-way sits at or near the optimum at
both scales**: close to break-even where caching doesn't help much (50MB), and captures nearly all
of the achievable win where it does (7.5GB), while 16-way's extra cost is either wasted (large DB)
or actively harmful (small DB). This directly answers CK's original ask for a quantified case for
4-way/8-way over both no-associativity and higher-associativity.

**Status:** this job fully complete. Two jobs still running (readcount, bigdb-extended).

---

### [46] Verified read-count job wasn't hung (false alarm) + bigdb 16GB results

Read-count job's 2000reads/S0 run was still on its first run past the ~62min estimate - checked
`ps` for the wrong process name (`sde64`) first, found nothing, briefly suspected a hang. Full
process tree check found the real simulator core (`lib/sniper`, not `sde64` - that binary is only
used transiently during initial trace recording) actively consuming 58.8% CPU with 50+ min of real
accumulated compute time - genuinely working, just costing more than the earlier per-read
extrapolation suggested, not stuck.

**bigdb job 16GB results (all 3 variants done):**

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Unique cache lines | Wall time (s) |
|---|---|---|---|---|---|---|
| 16gb | S0 | 77.3 | 60.7 | 1.27 | 200,423 | 861 |
| 16gb | 4way | 51.9 | 29.6 | 1.75 | 56,897 | 390 |
| 16gb | 16way | 53.0 | 30.3 | 1.75 | 93,761 | 431 |

Confirms the 7.5GB pattern even more cleanly: 4-way beats S0 by **33% fewer instructions, 2.2x
faster**; 16-way barely differs from 4-way (+2.1% instructions) while touching 65% more memory and
costing 10% more wall time. 103gb/S0 now running.

---

### [47] Queued: full-file (104,832-read) comparison, auto-starts after readcount job

CK asked to add a full-file run of `reads_fast.fastq` after the 2000/10000-read subsets finish.
Rather than manually catch the exact completion moment, wrote a watcher script
(`run_fullfile_comparison.sh`, PID 4007675) that polls every 30s for `run_readcount_comparison.sh`
to exit, then automatically launches S0/4way/16way on the full 104,832-read file, writing to
`results_fullfile_comparison/live_summary.csv`. Genuinely long-running (the ~1.85s/read estimate
looks conservative given how long the 2000-read run is taking) - queued to run unattended
regardless. next: monitor all jobs, report as each completes.

---

### [48] 103GB results (partial) - the largest gap yet, trend continues to strengthen

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Unique cache lines | Wall time (s) |
|---|---|---|---|---|---|---|
| 103gb | S0 | 102.9 | 94.3 | 1.09 | 306,921 | 1262 |
| 103gb | 4way | 70.3 | 47.7 | 1.47 | 88,782 | 616 |

4-way beats S0 by **~32% fewer instructions, ~71% fewer cache lines, 2.05x faster wall-clock** -
the largest gap of any DB size tested (50MB -> 7.5GB -> 16GB -> 103GB all show the same direction,
with the 4-way advantage growing as DB size grows). 103gb/16way still running.

Also verified (second time) the readcount job's 2000reads/S0 run is genuinely still computing, not
stalled: 63+ min of real accumulated CPU time, 58% CPU utilization live-checked - just taking far
longer than any extrapolation predicted. No action needed, continuing to monitor.

---

### [49] bigdb job (16GB + 103GB) fully complete - pattern holds across every DB size tested

`ALL DONE` at 21:50:34. Full 6-row table (consolidated into
`measurements/bigdb_16gb_103gb_full_2026-09-08_summary.csv`, superseding the earlier partial file):

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Unique cache lines | Wall time (s) |
|---|---|---|---|---|---|---|
| 16gb | S0 | 77.3 | 60.7 | 1.27 | 200,423 | 861 |
| 16gb | 4way | 51.9 | 29.6 | 1.75 | 56,897 | 390 |
| 16gb | 16way | 53.0 | 30.3 | 1.75 | 93,761 | 431 |
| 103gb | S0 | 102.9 | 94.3 | 1.09 | 306,921 | 1262 |
| 103gb | 4way | 70.3 | 47.7 | 1.47 | 88,782 | 616 |
| 103gb | 16way | 74.6 | 49.6 | 1.50 | 125,646 | 671 |

103gb/16way closes the loop: +6.1% instructions, +42% more cache lines, +8.9% more wall time than
4-way, for no meaningful benefit - same shape as every other DB size tested. **The full pattern
across all four sizes (50MB, 7.5GB, 16GB, 103GB) is now consistent and complete: 4-way is at or
near the optimum at every scale, and its advantage over no-cache grows monotonically with DB size**
(50MB: near break-even: 7.5GB: -24% instr/1.9x faster: 16GB: -33% instr/2.2x faster: 103GB: -32%
instr/2.05x faster - 103GB roughly matches 16GB's gain rather than continuing to grow, suggesting
the benefit may be approaching a ceiling past a certain DB size, worth noting rather than
overclaiming unbounded growth).

readcount job (2000reads/S0) still running, verified alive again (91+ min CPU time, up from 63 min
last check) - genuinely slow, not stalled.

---

### [50] Investigated why the read-count job is so slow: unrepresentative sample, not a bug

2000reads/S0 still on its first run after 150+ min real CPU time (verified alive throughout via
`ps`, steadily climbing - never actually stalled). Investigated whether the workload itself
explains this, since read-count scaling alone (2000/50 = 40x) didn't predict this much slowdown.

**Root cause: read-length composition, not read count.** Nanopore reads vary enormously in length,
and `head -N` on a fastq file grabs whatever happens to be at the front - not a random sample.
Measured directly:

| Workload | Reads | Mean length | Total bases |
|---|---|---|---|
| 50reads.fastq (original) | 50 | 1,827 | 91,372 |
| reads_fast_2000.fastq | 2,000 | 17,526 | 35,051,400 |
| reads_fast_10000.fastq | 10,000 | 6,019 | 60,185,436 |
| reads_fast.fastq (full file) | 104,832 | 3,411 (true average) | 357,616,061 |

The 2000-read subset's mean (17,526) is **5.1x the file's true average** (3,411) - the front of the
file happens to be unusually long-read-heavy (some individual reads run up to 496,132 bases).
Total bases, not read count, is what drives classify cost (minimizer scanning is per-base) - by
that measure the 2000-read run is processing far more real work than "2000 reads" suggests, which
fully explains the extreme slowness without anything being broken.

**Reframed expectation for the remaining jobs, by total bases rather than read count:** current
2000-read run (35.1M bases, in progress) -> 10000-read run (60.2M bases, only ~1.7x more) -> full
file (357.6M bases, ~5.9x more than the 10K run) - a much gentler progression than the raw
52x/read-count jump to the full file would have suggested. Still a real, multi-stage long-running
job, but not the runaway blowup the naive read-count math implied.

---

### [51] Fifth job: adding 8-way to the DB-size comparison

CK asked to also test 8-way across all 4 DB sizes, and clarified an assumption about S0 worth
recording precisely: **S0 is true no-cache, not "cache present but no associativity."**
`kraken2-src-baseline/src/classify` has zero `s2_cache`-related code compiled in at all (verified
via `strings`/source grep in step 40) - every lookup goes straight to the raw hash table, no
intercepting structure whatsoever. Not a 1-way/direct-mapped cache - the complete absence of one.

Current DB-size table only bracketed 4-way and 16-way, so the true optimum (is it 4-way or 8-way?)
was never actually confirmed. Launched `~/cache_simulation/run_8way_dbsize.sh` (PID 4018464),
`kraken2-fresh-bin-s2-lru-noatomics-8way/classify` across all 4 DBs, same 50-read workload as the
original comparison for direct comparability. Writes to `results_8way_dbsize/live_summary.csv`.
~25-30 min estimated based on similarly-scoped prior runs. next: monitor, merge into full table.

---

### [52] Building a 1-way (direct-mapped) variant from scratch - no such binary existed

CK asked to add 1-way associative as the missing lower bound between S0 (no cache) and 4-way.
No `*-1way*` binary existed among the built variants - had to build one.

**Hit two real problems finding the correct source base to patch:**
1. Copied `kraken2-src-baseline` (the true no-cache reference) first - the 4-way patch script's
   exact-text-match assertions failed (`signature not found exactly once`). Diagnosis: `baseline`'s
   `classify.cc` has different line-wrapping than what the noatomics patch scripts expect - it's a
   different source snapshot, not just "baseline + no patch."
2. Copied `kraken2-src-fresh` instead (the actual base the other noatomics variants were built
   from) - but its checked-out working tree is *dirty* with later uncommitted work (S4.0b/c, S5.0
   prefetch patches), and even its clean `HEAD` commit already has S2 cache code baked into git
   history (`grep -c s2_cache` = 8) - S1 through S5 were committed directly into this repo's
   history, not applied as one-off patches each time. Found the real pristine base by walking
   `git log -- src/classify.cc` back to `fbf993d` ("S1.1: promote same-adjacent-minimizer cache to
   thread_local" - the first S-series commit) and checking its **parent** commit
   (`5e2aa928d00b96d61f204d517437637863da1d8c`): zero `s2_cache` references, exact signature format
   match. This is the correct base the noatomics patch scripts were actually designed against.

**Built:** `kraken2-src-1way` = copy of `kraken2-src-fresh`, `classify.cc` reset to that pristine
parent commit via `git checkout <sha> -- src/classify.cc`, patched with a new
`s2_lru_1way_noatomics_patch.py` (identical structure to the 4-way script, `S2_WAYS = 1` - with one
way per set the eviction loop naturally never executes, so every insert overwrites the set's single
slot, which is exactly direct-mapped semantics - no special-casing needed). `make classify` built
clean (only pre-existing benign sign-compare/unused-result warnings).

**Verified correctness before using it:** ran natively against the 50-read workload - 34/50
classified (68%), matching S0/4-way/16-way exactly, and a direct diff of per-read taxid assignments
against S0's output came back empty (identical). Confirms the cache is a pure lookup optimization
here, not altering classification results, as expected.

**Launched:** `~/cache_simulation/run_1way_dbsize.sh` (PID 4019763), same pattern as the 8-way job -
across all 4 DBs, same 50-read workload. Writes to `results_1way_dbsize/live_summary.csv`. next:
monitor both new jobs (8-way, 1-way), merge into the full comparison table once done.

---

### [53] Data-integrity catch: 1-way/8-way wall-clock contaminated by host contention

Both jobs progressed through 50mb/8gb/16gb (103gb still running for each). Before reporting,
noticed 1-way's 50MB wall-clock (454s) was *slower* than 8-way (341s) and 16-way (360s) at the same
DB size - backwards from expected, since 1-way is structurally the simplest cache. Checked whether
this was a real finding or a measurement problem: 1-way's **simulated** metrics (38.2M
instructions, 27.0M cycles) are nearly identical to 4-way's (39.7M / 26.7M, ~1% apart) - a 1%
difference in simulated cycles cannot produce a 122% difference in real wall-clock under normal
conditions.

**Root cause: these two jobs were launched while the read-count job (2000reads/S0) was still
running**, and briefly overlapped each other too - so their wall-clock timings were recorded under
2-3 concurrent Sniper simulations competing for real CPU on Luna. The original S0/4-way/16-way
numbers in the published report ran strictly sequentially, one at a time, with no such contention.

**Verdict:** instructions/cycles/IPC/cache-lines (Sniper's own internal simulated metrics) remain
valid and comparable - they come from the simulator's internal model, not real-world scheduling.
**Wall-clock time for the 1-way and 8-way DB-size runs is NOT comparable to the original sequential
numbers and should not be reported as such.**

**Fix, per CK's call:** report instructions/cycles/IPC now (valid), queue a clean isolated re-run
for honest wall-clock. Wrote `~/cache_simulation/run_1way8way_clean_rerun.sh` (watcher PID 4029858)
- polls for both `run_readcount_comparison.sh` and `run_fullfile_comparison.sh` to have no running
instance (true single-job isolation, not just "readcount done"), then re-runs 1-way and 8-way alone
across all 4 DBs. Writes to `results_1way8way_clean/live_summary.csv`.

**Valid data so far (instructions/cycles/IPC only - wall-clock excluded as unreliable):**

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Cache lines |
|---|---|---|---|---|---|
| 50mb | 1way | 38.2 | 27.0 | 1.41 | 67,749 |
| 50mb | 8way | 41.3 | 27.8 | 1.48 | 89,254 |
| 8gb | 1way | 51.7 | 28.6 | 1.81 | 54,874 |
| 8gb | 8way | 52.2 | 28.7 | 1.82 | 76,380 |
| 16gb | 1way | 51.6 | 30.1 | 1.71 | 47,680 |
| 16gb | 8way | 52.3 | 30.1 | 1.74 | 69,187 |

Interesting real signal even from just instructions/cycles: 1-way touches noticeably *fewer* cache
lines than 4-way/8-way at every DB size (e.g. 47,680 vs 8-way's 69,187 at 16GB) - direct-mapped's
lack of associativity means it can't hold as much live data, consistent with expected higher
conflict-miss/thrashing behavior for a 1-way design, worth confirming once clean wall-clock timing
is available to see if that thrashing shows up as a real cost.

---

### [54] 1-way and 8-way jobs fully complete (all 4 DB sizes) - full 5-variant picture

Both jobs finished all 4 databases (wall-clock still excluded as unreliable - see step 53).
Complete instructions/cycles/IPC/cache-lines table, all 5 variants:

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Cache lines |
|---|---|---|---|---|---|
| 50mb | S0 | 35.8 | 24.4 | 1.47 | 76,605 |
| 50mb | 1way | 38.2 | 27.0 | 1.41 | 67,749 |
| 50mb | 4way | 39.7 | 26.7 | 1.48 | 76,963 |
| 50mb | 8way | 41.3 | 27.8 | 1.48 | 89,254 |
| 50mb | 16way | 44.0 | 28.7 | 1.53 | 113,831 |
| 8gb | S0 | 68.1 | 51.7 | 1.32 | 186,523 |
| 8gb | 1way | 51.7 | 28.6 | 1.81 | 54,874 |
| 8gb | 4way | 52.0 | 28.3 | 1.84 | 64,091 |
| 8gb | 8way | 52.2 | 28.7 | 1.82 | 76,380 |
| 8gb | 16way | 52.6 | 28.9 | 1.82 | 100,952 |
| 16gb | S0 | 77.3 | 60.7 | 1.27 | 200,423 |
| 16gb | 1way | 51.6 | 30.1 | 1.71 | 47,680 |
| 16gb | 4way | 51.9 | 29.6 | 1.75 | 56,897 |
| 16gb | 8way | 52.3 | 30.1 | 1.74 | 69,187 |
| 16gb | 16way | 53.0 | 30.3 | 1.75 | 93,761 |
| 103gb | S0 | 102.9 | 94.3 | 1.09 | 306,921 |
| 103gb | 1way | 68.8 | 48.8 | 1.41 | 79,560 |
| 103gb | 4way | 70.3 | 47.7 | 1.47 | 88,782 |
| 103gb | 8way | 71.9 | 49.0 | 1.47 | 101,066 |
| 103gb | 16way | 74.6 | 49.6 | 1.50 | 125,646 |

**Nuance worth stating precisely, not oversimplified:** by raw instruction count, 1-way is
sometimes lowest (e.g. 103gb: 68.8M vs 4-way's 70.3M) - but by **cycles**, 4-way is consistently the
best or tied-best at every DB size (e.g. 103gb: 47.7M vs 1-way's 48.8M). 1-way's lower IPC across
the board (1.27-1.81 range, always below the wider variants at the same DB) shows it does less
total work but stalls more per instruction - consistent with direct-mapped's higher conflict-miss
rate (any two colliding minimizers fight over one slot). 1-way also consistently touches noticeably
*fewer* cache lines than 4/8/16-way at every DB size, since it can't hold as much live data at once.
**Cycles-based verdict: 4-way remains the best or tied-best choice at every database size tested,**
with 1-way a close but real second, and 8/16-way never actually winning on cycles anywhere in this
table.

readcount job still genuinely alive (322 min CPU time, still climbing) - clean re-run watcher not
yet triggered.

---

### [55] Cancelled read-count/full-file jobs, launched clean 1way/8way re-run immediately

CK's call: the read-count job (2000reads/S0) had run ~533 min CPU time (~8.9 hours) without
finishing even its first of 6 runs, with the 10000-read and full-file jobs both queued behind it -
too long a critical path for too little payoff right now. Cancelled the tail of the plan and
reprioritized getting clean 1-way/8-way wall-clock numbers immediately instead.

**Killed:** full process tree of the readcount job (`run_readcount_comparison.sh` wrapper +
`run-sniper` python + `record-trace` + the live `classify` process + the `sniper` simulator core
and its threads - 5 PIDs), the full-file watcher (`run_fullfile_comparison.sh`, was just polling,
never started), and the old 1way/8way clean-rerun watcher (`run_1way8way_clean_rerun.sh`, was
waiting on the two jobs just killed). Verified via `ps aux` that nothing Sniper-related remained
running before proceeding - a genuinely idle machine.

**Launched:** `run_1way8way_clean_immediate.sh` (PID 4047935) - same script as the queued version,
minus the wait condition, since the machine is now actually idle. Runs 1-way and 8-way across all
4 DBs with no contention this time, for wall-clock numbers that are finally directly comparable to
the original sequential S0/4-way/16-way timings. next: monitor, expect well under an hour given no
competing load.

**Dropped from the plan (not run):** 10000-read and full-file (104,832-read) real workload-scaling
experiments - the proof-of-concept 10/50-read results and the 4-DB-size sweep remain the primary
evidence.

**Correction:** CK clarified the 2000-read experiment itself was NOT meant to be dropped - only the
10000-read/full-file tail chained behind it. Requeued it as a standalone job (not re-chained to
10K/full-file), all 5 variants (S0/1way/4way/8way/16way) on the 2000-read workload, 50MB DB only.

---

### [56] Publication-quality figures built locally (not on Luna)

CK asked for beautiful, paper-publishable charts, generated with Python on the local machine (not
Luna). Installed matplotlib/numpy locally. Wrote `cache_simulation/scripts/make_slide_charts.py` -
serif academic typography, 300 DPI, vector PDF + PNG both saved (PDF for LaTeX inclusion, `pdf.fonttype
= 42` so fonts embed properly rather than as paths), standard single/double-column widths. Four
figures from the complete, committed experiment data: width sweep (10-read), cycles by variant
across all 4 DB sizes (small multiples), wall-clock speedup vs no-cache, memory footprint touched.
Caught and fixed a real legibility bug on first render (x-axis labels overlapping in the 4-panel
small-multiples layout) by reviewing the actual rendered PNG before finalizing, not just trusting
the code - rotated labels 40 degrees, widened panel height. Committed to `cache_simulation/charts/`.

---

### [57] Orion edge-device idea, explored then paused; new confound found on Luna

CK asked about simulating a smaller (edge-device / consumer-laptop) hardware cache, not just
associativity. Confirmed Sniper's cache-config parameters go well beyond associativity -
`replacement_policy` (including a built-in adaptive scheme, `mplru`, directly relevant to Thesis
1's eviction-policy piece), `address_hash`, latency, prefetcher, `shared_cores`/topology, plus
core-level frequency/branch-predictor/TLB/DRAM params.

CK initially wanted to physically power on Orion and run the real DynamoRIO/ARM route (Sniper's
x86 SDE frontend can't instrument ARM binaries directly - confirmed by reading `README.arm64`:
ARM traces are recorded on the ARM board via DynamoRIO, then replayed on the x86 host with an ARM
core config). Then chose the much simpler alternative: just override `cache_size` in a new Sniper
config and re-run the existing x86 binaries - answers the "LLC-topology-aware sizing" thesis
question directly, without new hardware. **Paused before building it** - CK asked to focus back on
Luna first.

**While reviewing the new 1way/8way clean-rerun data, found a second, different confound:** 1-way
at 8GB just ran in 223s with cycles (28.6M) nearly identical to the earlier "clean sequential"
4-way run's 28.3M cycles at 391.8s - same warning shape as the contention bug already caught once,
but CPU contention is ruled out this time (verified via `ps`, nothing else running). Checked
`free -h`: 280GB of OS page cache on Luna, easily enough to hold all four databases (126.5GB total)
simultaneously. Computed seconds-per-million-simulated-cycles for both batches: the original
S0/4way/16way sequential job ran consistently around ~14 s/Mcycle across all three variants (no
internal unfairness), but this new batch runs at ~8 s/Mcycle - the **entire new batch**, not one
variant, is running roughly 1.8x faster per simulated cycle than the original batch did hours
earlier. Conclusion: **wall-clock is comparable within a single batch, but not across batches run
at different times** (disk-cache warmth or other host conditions drift between sessions) -
validates cycles as the metric to trust throughout, per the earlier decision.

**Fix:** queued a single fresh batch running all 5 variants together
(`run_final_fair_batch.sh`, watcher PID 4050075) so wall-clock is finally comparable end-to-end,
one batch, one set of host conditions. Had to fix a scheduling bug of my own making: the 2000-read
job (watcher PID 4048357) was queued on the same start condition as this new fair-batch job - both
would have launched simultaneously once the current job finished, recreating the exact contention
problem being fixed. Killed and requeued the 2000-read watcher (new PID 4050181) to wait for BOTH
the current job AND the fair batch, keeping the whole chain strictly sequential: 1way/8way clean
(running) -> final fair batch (queued) -> 2000-reads (queued).

**Correction:** CK flagged (correctly) that 2 of the 4 committed figures used wall-clock numbers
from before the cross-batch drift finding above - premature to call final. Deleted all 4 chart
files from the repo (`git rm -r cache_simulation/charts/`) rather than leave stale ones around.
`cache_simulation/scripts/make_slide_charts.py` stays (reusable, just needs its hardcoded data
dicts refreshed) - will regenerate once the fair batch's wall-clock data is in and verified.

---

### [58] Hardware cache-size comparison: desktop and Orion-sized configs (config-only)

CK asked to also test the 50-read workload under smaller HARDWARE caches - a typical consumer
desktop and Orion (edge device) sized caches - using the config-only approach (not real Orion
hardware/DynamoRIO, which stays paused). Removed 2000-reads from the queue temporarily, then CK
asked to re-add it at the very end, after this new comparison.

**Built two new overlay configs**, same pattern as `luna.cfg`:

`cache_simulation/configs/desktop.cfg` - AMD Ryzen 5 5600X (a real, well-documented mainstream
desktop CPU, not an invented "typical" number): L1d/L1i 32KB/8-way, L2 512KB/8-way, L3 32MB/16-way
shared across 6 cores (5461 KB/core NUCA slice). All values are AMD's real published spec.

`cache_simulation/configs/orion_sizes.cfg` - Jetson AGX Orin sizes from prior project research:
L1d/L1i 64KB, L2 256KB/core, SLC 4MB shared across 12 cores (342 KB/core NUCA slice).
Associativity NOT independently verified for this SKU (flagged explicitly, same caveat already on
record in project memory) - L1/L2 use ARM Cortex-A78AE TRM typical-config values (a real reference
default, not a guess); SLC associativity is NVIDIA proprietary IP, kept at 16 as an explicit
placeholder only.

**Both are config-only, x86-core stand-ins** - they test hardware cache SIZE sensitivity using the
same x86 binaries and `meteor_lake_pcore` core timing model as every other run, not Orion's real
ARM microarchitecture. That distinction is written directly into both config files' headers so it
can't get lost later.

Smoke-tested both before committing to a full run - `/bin/true` fast-forward confirmed exact
correct cache creation (desktop: 5461 sets/16-way NUCA, 64 sets/8-way L1i/L1d, 1024 sets/8-way L2;
orion_sizes: 342 sets/16-way NUCA, 256 sets/4-way L1i/L1d, 512 sets/8-way L2), no errors.

**Launched:** `run_hwsize_comparison.sh` (watcher PID 4051600) - S0 and 4-way, both new hw configs,
50MB and 8GB DBs, 50-read workload (8 runs total). Chained to start after both the current 1way/8way
clean job AND the fair batch finish.

**Re-queued 2000-reads at the end of the whole chain** (new watcher PID 4051646, waits on all three
jobs ahead of it). Full order now: 1way/8way clean (running) -> fair batch (queued) -> hwsize
comparison (queued) -> 2000-reads (queued, last).

---

### [59] 1way/8way clean re-run fully complete; fair batch in progress, looks genuinely fair

`results_1way8way_clean` finished all 8 runs cleanly (`ALL DONE`). Fair batch started immediately
after, now 8/20 runs in (50mb complete, 8gb in progress). Checked seconds-per-Mcycle across the
completed rows this time: 6.44-7.90 s/Mcycle across all variants and both DB sizes so far - a tight
range, genuinely internally consistent (vs. the ~14-vs-~8 mismatch caught in step 57). This batch
looks trustworthy.

**Early signal, not yet final** (waiting for the full 20 runs before drawing conclusions or
touching charts): at 50MB this time, 1-way (174s) and 4-way (182s) come out *faster* than no-cache
(188s) - different from the earlier batch's numbers (which had all cache variants slower than S0 at
50MB). This is a real, useful illustration of exactly why the fair-batch re-run mattered - even the
"small DB = slight net cost" framing may need revisiting once this completes. At 8GB, the ~1.8-1.9x
speedup for 1-way/4-way over S0 matches earlier findings closely, a reassuring cross-check.

**Status:** fair batch continuing (8gb/8way running now, then 8gb/16way, then all of 16gb and
103gb - 12 more runs). Not regenerating charts or updating the artifact until this fully completes,
per instruction.

**Update:** 15/20 runs complete (50mb, 8gb, 16gb all done; 103gb's 5 runs remain, currently on
16gb/16way per the last check but that DB's 5 rows are already in the summary - progress.log is
slightly ahead of what's shown). Per-cycle rate holds steady across all three completed DB sizes
(7.5-8.2 s/Mcycle) - still internally consistent. Still not touching charts/artifact until the
remaining 103gb runs land.

---

### [60] Fair batch complete (20/20) - and a bigger correction: wall-clock was never the right metric

All 20 runs done, `ALL DONE` confirmed. Classification correctness re-verified at the widest gap
(S0 vs 16-way at 103GB - identical output, diff empty). Per-cycle rate stayed consistent through
103gb too (7.09-7.90 s/Mcycle range).

**Computed the wall-clock speedup table from this genuinely fair batch - and got a different
answer than the cycles-based verdict: 1-way comes out fastest on wall-clock at every DB size**,
narrowly ahead of 4-way (e.g. 103gb: 1-way 346s vs 4-way 360s). This contradicted the established
cycles-based finding, which was worth stopping to understand rather than just reporting both
numbers side by side.

**Root cause, and the actual correction:** `wallclock_s` in every one of these summaries is **how
long Sniper itself took to compute the simulation** - real time spent by the simulation tool,
which tracks roughly with instruction count (more instructions = more simulator work). It is
**not** a measure of how fast kraken2 would run on real hardware. The metric that actually
represents real-hardware time is **cycles**, converted through the core's clock frequency
(cycles / 2.1GHz for Luna) - that is what a real chip would experience. 1-way has fewer
instructions than 4-way at most DB sizes (e.g. 103gb: 68.8M vs 70.3M) which is why it simulates
*faster* (less simulator work) even though 4-way is *cycle-for-cycle* the better design.

**Recomputed real-hardware-equivalent speedup vs S0, from cycles (the correct metric):**

| DB | 1-way | 4-way | 8-way | 16-way |
|---|---|---|---|---|
| 50MB | 0.90x | 0.91x | 0.88x | 0.85x |
| 7.5GB | 1.81x | **1.83x** | 1.81x | 1.79x |
| 16GB | 2.02x | **2.05x** | 2.02x | 2.00x |
| 103GB | 1.93x | **1.97x** | 1.92x | 1.89x |

**4-way wins or ties at every single database size** on this corrected metric - consistent with
every earlier cycles-based finding in this log. The whole cross-batch wall-clock-drift investigation
(steps 53-57) was a legitimate and correctly-diagnosed bug (Sniper's own simulation speed genuinely
does drift between sessions), but fixing it was never actually necessary for the core proof, since
cycles never had that contamination problem - this is exactly why cycles was flagged as the
trustworthy metric from the start. Going forward: **report cycles-derived real-time-equivalent
numbers as the headline metric, not Sniper's own `wallclock_s`/`elapsed_s` columns** - those
describe simulator performance, not simulated program performance, and conflating the two is an
easy, subtle mistake worth flagging clearly for anyone reading this log later.

**Full final dataset (20 rows, fully verified):**

| DB | Variant | Instructions (M) | Cycles (M) | IPC | Cache lines | Sim wall-clock (s, NOT real-HW time) |
|---|---|---|---|---|---|---|
| 50mb | S0 | 35.8 | 24.4 | 1.47 | 76,606 | 188 |
| 50mb | 1way | 38.2 | 27.0 | 1.41 | 67,751 | 174 |
| 50mb | 4way | 39.7 | 26.8 | 1.48 | 76,966 | 182 |
| 50mb | 8way | 41.3 | 27.8 | 1.49 | 89,255 | 194 |
| 50mb | 16way | 44.0 | 28.7 | 1.53 | 113,831 | 209 |
| 8gb | S0 | 68.1 | 51.8 | 1.32 | 186,526 | 409 |
| 8gb | 1way | 51.7 | 28.6 | 1.81 | 54,874 | 220 |
| 8gb | 4way | 51.9 | 28.3 | 1.84 | 64,091 | 223 |
| 8gb | 8way | 52.2 | 28.7 | 1.82 | 76,379 | 230 |
| 8gb | 16way | 52.6 | 28.9 | 1.82 | 100,954 | 236 |
| 16gb | S0 | 77.3 | 60.7 | 1.27 | 200,423 | 464 |
| 16gb | 1way | 51.6 | 30.1 | 1.71 | 47,681 | 226 |
| 16gb | 4way | 51.9 | 29.6 | 1.76 | 56,898 | 232 |
| 16gb | 8way | 52.3 | 30.1 | 1.74 | 69,185 | 237 |
| 16gb | 16way | 53.0 | 30.4 | 1.75 | 93,761 | 248 |
| 103gb | S0 | 102.9 | 94.3 | 1.09 | 306,921 | 700 |
| 103gb | 1way | 68.8 | 48.8 | 1.41 | 79,566 | 346 |
| 103gb | 4way | 70.3 | 47.8 | 1.47 | 88,782 | 360 |
| 103gb | 8way | 71.9 | 49.1 | 1.46 | 101,070 | 375 |
| 103gb | 16way | 74.6 | 50.0 | 1.49 | 125,646 | 395 |

**Status: this dataset is final and verified.** Next: regenerate charts using cycles-derived
speedup (not sim wall-clock), update the published artifact.

---

### [61] Regenerated final figures and published artifact with corrected data

Rewrote `make_slide_charts.py`'s hardcoded data with the final fair-batch numbers; fig3 (speedup)
now shows all 4 widths (1/4/8/16-way) using cycles-derived speedup instead of 2 widths using
Sniper's own wall-clock. Caught and fixed a legend-overlap bug on review before finalizing (legend
moved above the plot, single row). Reviewed all 4 rendered PNGs before committing.

Rewrote the published artifact (https://claude.ai/code/artifact/ccbd8008-8fbd-47cd-b8a2-7bf4baf76c6f)
from scratch with: the corrected 4-width speedup chart, the full verified 20-row table (all 5
variants x 4 DB sizes, columns relabeled "Sim. time" vs "Speedup (cycles)" to make the distinction
unmissable), a new callout explaining the wall-clock-vs-cycles mistake directly (rather than
burying it in a caveat), and an updated trend caveat reflecting the corrected 103gb number (1.97x,
a mild recession from 16gb's 2.05x, not the earlier 1.88x/2.21x pair). Removed the stale "2 further
runs in progress" status chip (2000-reads/10000-reads/full-file were dropped from the plan).

---

### [62] Hardware cache-size comparison started

`run_hwsize_comparison.sh` began right after the fair batch finished. 2/8 runs done so far
(desktop config, 50mb S0 and 4way). Early signal: desktop's cycles-based speedup at 50MB is
~0.92x (28.2M -> 30.7M cycles, S0 vs 4way) - same direction and similar magnitude to Luna's own
50MB result (~0.91x), a reassuring cross-check that the "small DB = slight cache cost" pattern
isn't specific to Luna's particular cache geometry. Now running desktop/8gb. 2000-reads job still
queued behind this one.

---

### [63] Hardware cache-size comparison complete (8/8) - a non-monotonic result

All 8 runs done, `ALL DONE`. Cycles-derived speedup (S0/4-way, same correct metric as everywhere
else in this log):

| Hardware | 50MB speedup | 8GB speedup |
|---|---|---|
| Luna (real server cache) | 0.910x | 1.830x |
| Desktop-sized (AMD Ryzen 5 5600X specs) | 0.919x | 1.936x |
| Orion-sized (Jetson AGX Orin specs) | 0.902x | 1.649x |

**Finding 1 - cross-validation:** all three hardware configs agree closely at 50MB (0.90-0.92x) -
the "cache is a slight net cost on a tiny DB" result isn't specific to Luna's particular cache
geometry, it holds across genuinely different hardware cache sizes/associativities.

**Finding 2 - NOT simply monotonic with cache size:** at 8GB, desktop (smaller L2 than Luna, 512KB
vs 2MB, but a comparably generous 32MB shared L3) sees an even *stronger* win (1.94x) than Luna.
Orion (the smallest cache overall - 256KB L2, only 342KB/core L3-slice-equivalent) sees a distinctly
*weaker* win (1.65x) than both Luna and desktop. Explicitly avoiding the tempting but unsupported
generalization "smaller hardware cache -> bigger software-cache benefit" - that's not what this
data shows. A plausible partial explanation (not verified): Orion's baseline no-cache cycle count
is itself already lower than desktop's at 8GB (55.9M vs 60.6M), suggesting Orion's larger L1 (64KB
vs desktop's 32KB) already absorbs some of what S2 would otherwise intercept, leaving less room for
S2 to help - worth deeper investigation before asserting as fact.

**Caveat already on record, restated:** both configs are config-only (real x86 core model, only
cache sizes changed) - this tests hardware cache SIZE sensitivity, not real ARM/Orion behavior.

2000-reads job now started (`2026-09-09 09:12:48`).

---

### 2000-reads job progress - S0 variant complete (`2026-09-09 21:38:04`)

S0 (no software cache) finished after 44,716s wallclock (~12.42 hours) - longer than the ~9.8hr
extrapolation in fig8 (that model was fit from the tiny 10/50-read runs and clearly underestimates
at this scale; treat fig8's 2000-read row as a rough lower bound, not the real number, until the
comparison variant confirms the actual ratio). `1way` variant started immediately after, ~20 min in
as of this check.

Result row (from `results_2000reads/live_summary.csv`):

| workload | variant | instructions_M | cycles_M | ipc | unique_cache_lines | l1d_hit_pct | l2_hit_pct | nuca_hit_pct | wallclock_s |
|---|---|---|---|---|---|---|---|---|---|
| 2000reads | S0 | 10053.7 | 6354.0 | 1.58 | 1,615,102 | 99.04 | 0.21 | 0.0297 | 44716 |

Sanity check: cycles/instructions = 6354.0/10053.7 = 0.6321 -> IPC = 1/0.6321 = 1.582, matches the
reported 1.58 IPC. Internally consistent.

Notable: `unique_cache_lines` (1.6M) dwarfs anything seen in the 10/50-read runs (tens of thousands)
- this is the first run in this whole project actually large enough to plausibly separate from a
tiny-workload artifact, which is the whole point of running it. `nuca_hit_pct` is extremely low
(0.03%) at this scale with no software cache, consistent with a workload whose working set blows far
past what on-chip caches (even LLC) can hold for a 50MB DB - most lookups are genuinely going to
DRAM. This is the baseline S0 will be compared against once 4way (the variant that won every DB size
in the fair batch) finishes.

No verdict yet - only 1 of 5 variants done. At the current per-variant rate (~12.4hrs for S0), the
remaining 4 variants (1way, 4way, 8way, 16way) would take roughly 2 more days if each runs at a
similar pace, though variants with a software cache do more instructions/cycle-of-work than S0 in
past experiments, so actual time-per-variant may differ. Continuing to monitor.

---

### To-do (not started - logged for later, per CK's requests during Q&A)

1. **Simulate L3 as a single naive flat block, not distributed NUCA slices.** For comparison against
   the current mesh-slice model. Would need switching away from `meteor_lake_pcore`'s NUCA-based
   chain to an older-style flat `l3_cache` config (like `nehalem`/`gainestown` originally had),
   applied with Luna's real total L3 size (105MB) and 15-way associativity as one block instead of
   split across slices.

2. **Sweep real HARDWARE cache associativity in isolation**, distinct from every experiment so far
   which varied the *software* S2 cache's width. Hold the S2 software cache fixed (either "no
   cache" throughout, or one fixed width like 4-way) and vary only Luna's real L2 or L3
   associativity value (e.g. 1-way, 4-way, 8-way, 15-way [real], 16-way, 30-way) across one DB
   size, same cycles-based methodology as everything else. Directly answers "does the hardware's
   own associativity matter to kraken2, independent of any software cache" - a question never
   actually isolated so far, since the desktop/orion hardware comparison changed hardware
   associativity only as a side effect of using each hardware's real spec, with S2 still varying
   too (S0 vs 4-way) in that experiment.
