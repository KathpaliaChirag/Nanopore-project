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

### 2000-reads job progress - 1way variant complete (`2026-09-10 ~09:57 IST`)

1way finished after 44,497s wallclock (~12.36hrs) - almost identical wallclock to S0's 44,716s,
confirming host conditions stayed consistent between the two runs (no contention drift this time).
4way started immediately after, ~4h41m in as of this check.

Result row:

| workload | variant | instructions_M | cycles_M | ipc | unique_cache_lines | l1d_hit_pct | l2_hit_pct | nuca_hit_pct | wallclock_s |
|---|---|---|---|---|---|---|---|---|---|
| 2000reads | S0 | 10053.7 | 6354.0 | 1.58 | 1,615,102 | 99.04 | 0.21 | 0.0297 | 44716 |
| 2000reads | 1way | 11350.6 | 8336.3 | 1.36 | 2,272,676 | 99.21 | 0.17 | 0.0153 | 44497 |

Sanity check: 8336.3/11350.6 = 0.7345 cycles/instruction -> IPC = 1/0.7345 = 1.361, matches reported
1.36. Consistent.

**Real cycles-based comparison, 1way vs S0 at 2000-read scale:** cycles_1way / cycles_S0 =
8336.3 / 6354.0 = **1.312x - 1-way is 31% SLOWER (more cycles) than no cache at all**, not faster.
This matches the direction of every prior width-sweep result in this project (1-way has consistently
been the worst-performing associativity, sometimes even worse than no cache) - a direct-mapped
software cache's high conflict-miss rate plus the fixed overhead of checking/maintaining the cache
array outweighs any benefit, and unique_cache_lines rose 40.7% (1.615M -> 2.273M) versus S0, meaning
the cache structure itself is adding real extra memory footprint, not just redirecting existing
traffic. Waiting for 4way (the variant that has won or tied at every DB size in the fair batch) to
know whether the *real, useful* width actually helps at this larger, more realistic 2000-read scale
- that comparison (4way vs S0) is the one that actually answers this week's open question against
last week's real-hardware null result.

---

### 2000-reads job progress - 4way and 8way complete (`2026-09-11 ~16:06 IST`) - HEADLINE RESULT

4way finished at 45,600s wallclock (`2026-09-10 22:39:41`), 8way finished at 49,055s
(`2026-09-11 12:17:16`). 16way is now running. Full table so far:

| workload | variant | instructions_M | cycles_M | ipc | unique_cache_lines | l1d_hit_pct | l2_hit_pct | nuca_hit_pct | wallclock_s |
|---|---|---|---|---|---|---|---|---|---|
| 2000reads | S0 | 10053.7 | 6354.0 | 1.58 | 1,615,102 | 99.04 | 0.21 | 0.0297 | 44716 |
| 2000reads | 1way | 11350.6 | 8336.3 | 1.36 | 2,272,676 | 99.21 | 0.17 | 0.0153 | 44497 |
| 2000reads | 4way | 11829.2 | 8159.1 | 1.45 | 2,281,890 | 98.49 | 0.81 | 0.0600 | 45600 |
| 2000reads | 8way | 12391.2 | 8508.1 | 1.46 | 2,294,178 | 98.12 | 1.03 | 0.1485 | 49055 |

Sanity checks (cycles/instructions -> IPC): 4way: 8159.1/11829.2=0.6899 -> 1/0.6899=1.450, matches
1.45. 8way: 8508.1/12391.2=0.6866 -> 1/0.6866=1.456, matches 1.46. Both internally consistent.

**Real cycles-based ratios vs S0 (no cache), at 2000-read scale:**

| variant | cycles_M | ratio vs S0 | verdict |
|---|---|---|---|
| S0 | 6354.0 | 1.000x | baseline |
| 4way | 8159.1 | **1.284x** | 28.4% SLOWER than no cache |
| 1way | 8336.3 | 1.312x | 31.2% slower |
| 8way | 8508.1 | 1.339x | 33.9% slower |

**This is the headline finding of the whole 2000-reads job.** At this scale, EVERY software-cache
variant tested so far - including 4-way, the width that won or tied at every database size in the
smaller-scale fair batch - is slower in real cycles than having no software cache at all. 4-way is
still the *best* among the cache variants (matches the width-sweep's earlier conclusion that 4-way is
the optimal associativity relative to other cache widths), but "best of the cache variants" is not
the same as "better than no cache" - and at this scale it clearly is not.

**This directly reconciles this week's simulated finding with last week's real-hardware null result
(commit 84436dd)** - and goes a step further than "null." Last week's real hardware measured zero
measurable speedup from the software cache at production scale. This week's Sniper simulation at a
comparably large scale (2000 reads, 35.1M bases, vs the 10-50 read/91K-base runs the ~2x "speedup"
figure came from) shows the software cache actively HURTING performance, not just failing to help.
The two findings now agree in direction (cache stops helping as workload scale grows) and this
result is *stronger* in the same direction real hardware already showed - not a contradiction to
explain away, but the missing piece: the earlier ~2x speedup was a small-workload artifact (10-50
reads is tiny and unrepresentative), and the software cache's own overhead (maintaining/checking the
array, the extra 40-43% memory footprint every cache variant added over S0's unique_cache_lines) only
becomes visible once the workload is large enough for that overhead to matter relative to the actual
lookup savings.

Only 16way remains to complete the full picture (it's expected to also come in slower than S0, based
on this pattern, but not yet confirmed). hw_assoc_sweep is still correctly queued behind it.

---

### CORRECTION (`2026-09-11 ~16:20 IST`) - the reconciliation mechanism above is wrong

The previous section's claim that "the earlier ~2x speedup was a small-workload (10-50 read)
artifact" is **incorrect** and needs to be walked back. Checked which DB `run_2000reads_standalone.sh`
actually uses: `DB=/home/student/chirag_K/AccuracyDrift/databases/sample_targeted` - this is the
SAME 50MB database as the fair batch's `50mb` column, not a different, bigger one.

Looking at the fair batch's own `50mb` row (`make_slide_charts.py`'s `CYCLES["50mb"]`): S0=24.4,
1way=27.0, 4way=26.8, 8way=27.8, 16way=28.7 - **the cache was ALREADY worse than no-cache on this
same 50MB DB at just 50 reads.** The ~2x speedup this project has been calling "this week's
headline result" came entirely from the 8GB/16GB/103GB DB rows of that same fair batch, where S0 is
much slower (51.8/60.7/94.3M cycles) and the cache variants cluster much lower (~28-30M) - a
DATABASE-SIZE effect, not a read-count effect.

**What the 2000-reads job actually shows:** the cache was already known to hurt on the 50MB DB at 50
reads; running 2000 reads on that SAME 50MB DB confirms the cache continues to hurt at a much larger,
more realistic read count too - ruling out "maybe 50 reads just wasn't enough for the cache to warm
up" as an excuse for the small-DB result. That's a real and useful finding, but it is NOT a test of
whether the ~2x speedup (which lives on the 8GB+ DBs) holds up at large read counts - that
comparison has never been run and remains open. Also relevant: last week's real-hardware null result
(commit 84436dd) was itself already DB-size-independent ("3 DBs x 6 thread counts x 3 runs: all
statistically indistinguishable everywhere... <2% hit rate at these sizes regardless of
implementation") - so it doesn't specifically corroborate the 50MB-DB finding over the 8GB one either;
it was a null across multiple DB sizes using a dynamically-sized cache formula, not the fixed-width
binaries used in this week's Sniper sweeps.

**Correct framing going forward:** the 2000-reads job is a large-read-count study on the SMALL
(50MB) DB specifically, and it reconfirms/strengthens that DB's already-known negative result. The
open question of whether the ~2x speedup on LARGE (8GB+) DBs survives at large read counts remains
untested and would need a separate 2000-read run against e.g. the 8GB DB to answer.

---

### 2000-reads job COMPLETE - 16way finished, full 5-variant verdict (`2026-09-12 03:17:14`)

16way finished at 53,998s wallclock (~15.0 hours) - the longest of all 5 variants, confirming a
clean monotonic pattern in wallclock too (S0=44716s < 1way=44497s < 4way=45600s < 8way=49055s <
16way=53998s; 1way's wallclock being marginally below S0's is noise, not signal - cycles is the
metric that matters and 1way is unambiguously worse there). Full final table (2000-read workload,
sample_targeted/50MB DB):

| variant | cycles_M | ipc | unique_cache_lines | l2_hit_pct | nuca_hit_pct | wallclock_s | ratio vs S0 |
|---|---|---|---|---|---|---|---|
| S0 | 6354.0 | 1.58 | 1,615,102 | 0.21 | 0.0297 | 44716 | 1.000x (baseline) |
| 1way | 8336.3 | 1.36 | 2,272,676 | 0.17 | 0.0153 | 44497 | 1.312x slower |
| 4way | 8159.1 | 1.45 | 2,281,890 | 0.81 | 0.0600 | 45600 | 1.284x slower |
| 8way | 8508.1 | 1.46 | 2,294,178 | 1.03 | 0.1485 | 49055 | 1.339x slower |
| 16way | 8805.9 | 1.51 | 2,313,682 | 1.12 | 0.2182 | 53998 | **1.386x slower** |

Sanity check 16way: 8805.9/13322.2=0.6610 cycles/instruction -> IPC=1/0.6610=1.513, matches reported
1.51. Consistent.

**Final ranking, best (least bad) to worst, at 2000-read/50MB-DB scale: 4way < 1way < 8way < 16way.**
Every single cache variant is slower than no cache - confirming (per the correction logged above)
that this DB's already-known negative result at 50 reads holds, and slightly *worsens*, all the way
out to 2000 reads. Two distinct cost mechanisms are visible in the data:
- **1-way is bad from conflict misses**: a direct-mapped cache with almost no ability to keep two
  competing k-mers resident at once, despite the lowest per-lookup comparison overhead of any width.
- **8-way and 16-way are bad from comparison overhead**: L2/NUCA hit rates climb steadily with width
  (0.21% -> 1.12% l2_hit at S0->16way, 0.03%->0.22% nuca_hit) - the wider cache genuinely does cache
  more distinct entries and serve more hits from itself - but cycles get WORSE anyway, because the
  software cache's own lookup is a sequential comparison loop (CK's own hypothesis, confirmed
  earlier in the associativity case study) and checking 16 slots one at a time before falling
  through to the real hash table costs more than the hits it wins back save.
- **4-way sits in the middle of both failure modes** - not immune to either, but least exposed to
  each - which is exactly why it was the width that won or tied at every DB size in the original
  fair batch (a different, more cache-friendly regime: 8GB/16GB/103GB DBs).

Charts fig9 (`cache_simulation/scripts/make_2000reads_charts.py`), fig10, and fig11
(`cache_simulation/scripts/make_2000reads_table.py`) still need to be regenerated with this real
16way row in place of the earlier placeholder/missing entry.

---

### hw_assoc_sweep COMPLETE - hardware LLC associativity alone has NO measurable effect (`2026-09-14 21:22:51`)

All 24 runs finished (6 associativities x 4 workload sizes). This sweep holds the SOFTWARE side
fixed at none (base kraken2, `S0` binary) and varies only the REAL hardware LLC associativity
(1/4/8/15[real]/16/30-way) - the mirror image of every other experiment in this project. Full data
in `cache_simulation/measurements/hw_assoc_sweep_2026-09-14.csv`.

| reads | assoc=1 | assoc=4 | assoc=8 | assoc=15 (real) | assoc=16 | assoc=30 | spread |
|---|---|---|---|---|---|---|---|
| 10 | 13.6 | 13.7 | 13.6 | 13.7 | 13.7 | 13.7 | 0.1M (0.7%) |
| 50 | 24.4 | 24.4 | 24.4 | 24.4 | 24.4 | 24.4 | 0.0M (identical) |
| 100 | 870.0 | 877.2 | 869.9 | 870.4 | 869.8 | 877.3 | 7.5M (0.86%) |
| 500 | 4528.2 | 4524.0 | 4537.9 | 4534.5 | 4526.4 | 4523.2 | 14.7M (0.32%) |

**Verdict: NULL RESULT, and a clean one.** Cycles do not move in any consistent direction as
hardware associativity changes, at any of the 4 workload sizes tested - the small variation present
(well under 1% everywhere) shows no monotonic trend with associativity and is consistent with
run-to-run simulation noise, not a real effect. `unique_cache_lines` is also essentially constant
across every associativity value at a given read count (e.g. 500 reads: 1,614,997-1,614,998 across
all six - a 1-line difference), confirming the working set itself doesn't change; only microscopic
`nuca_hit_pct` differences appear (all still under 0.04% at every size), meaning almost nothing is
ever actually being resolved at the LLC layer to begin with, on this database, at these workload
sizes - so it wouldn't matter how that layer is organized.

**Why this matters, and how it explains the 2000-reads result above:** on the 50MB DB, kraken2's
lookups are overwhelmingly either L1 hits or full DRAM misses (l2_hit_pct and nuca_hit_pct are both
under 1-2% even in the best case) - almost nothing is being caught by mid-level or last-level cache
regardless of its associativity, because the working set relative to what L1 already holds doesn't
create the kind of repeat-access, capacity-bound conflict pattern that associativity is designed to
help with. This is the same underlying reason BOTH results land the way they do: hardware LLC
associativity can't help what it never gets asked to resolve, and a SOFTWARE cache sitting in front
of that same access pattern only adds its own fixed per-lookup overhead without enough genuine
repeat-hit benefit to pay for itself. The real lever for this database size is DRAM latency, not
cache organization at any level - consistent with (and a mechanistic explanation for) the ~2x
speedup instead showing up on the 8GB+ DBs in the original fair batch, where the working set is
large enough that repeat k-mer lookups plausibly do get evicted from hardware cache between visits,
leaving real room for a software cache (or, by the same logic, hardware associativity) to matter.

This satisfies to-do item 2 below (marked DONE).

---

### To-do (per CK's requests during Q&A)

1. **Simulate L3 as a single naive flat block, not distributed NUCA slices.** NOT STARTED. For
   comparison against the current mesh-slice model. Would need switching away from
   `meteor_lake_pcore`'s NUCA-based chain to an older-style flat `l3_cache` config (like
   `nehalem`/`gainestown` originally had), applied with Luna's real total L3 size (105MB) and 15-way
   associativity as one block instead of split across slices.

2. **~~Sweep real HARDWARE cache associativity in isolation~~ - DONE, see hw_assoc_sweep section
   above (`2026-09-14`).** Null result: hardware associativity alone has no measurable effect on
   this DB at any tested workload size (10/50/100/500 reads), which mechanistically explains why the
   50MB DB is also where the software cache experiments hurt rather than help - almost nothing ever
   reaches the LLC layer for either kind of cache to act on.

---

### Step 0 (research brief `RESEARCH_PROMPT_optimal_cache_size.md`) - located the sizing code, confirmed rebuild-per-size (`2026-09-15`)

**Why:** the brief's open question is whether SOFTWARE cache SIZE (never independently swept) reveals
a win/loss pattern different from what associativity alone showed. Before building anything, had to
confirm whether size is a compile-time constant (needs a rebuild per value) or a runtime flag.

**Found:** `/home/student/chirag_K/tools/kraken2-src-fresh/src/classify.cc` (the same base every
noatomics-width binary was built from) computes cache size via `S3ComputeNumSets()`
(lines ~841-853): `raw = floor(S3_LLC_FRACTION x S3_LLC_PER_SOCKET_BYTES / (S2_WAYS x sizeof(S2Entry)
x T))`, rounded down to the nearest power of 2, clamped to `[S3_MIN_SETS, S3_MAX_SETS]`
(`4096`-`262144` by default) - all four of those are `static const`, compile-time constants. **No
CLI flag or env var controls it** - checked `getopt` string (`"h?H:t:o:T:p:R:C:U:O:Q:g:nmzqPSMKD"`)
and confirmed `-C` is `classified_output_filename`, not cache size; `grep getenv classify.cc` found
nothing. **Confirms the brief's concern: size requires a real rebuild per value**, same technique
already proven in `plan_paper/command_log.md` (2026-08-26 size-cliff investigation): sed both
`S3_MIN_SETS` and `S3_MAX_SETS` to the same target value, so the clamp loop
(`sets = S3_MIN_SETS; while (sets*2 <= raw && sets*2 <= S3_MAX_SETS) sets *= 2;`) never executes and
`sets` stays pinned at exactly the target, independent of thread count or the `0.25`-fraction formula.

**Math check before trusting the pin technique:** `sizeof(S2Entry)` = `{uint64_t tag (8B); taxid_t
taxon}`, and `taxid_t` is `typedef uint64_t taxid_t` (`kraken2_data.h:27`) - so `sizeof(S2Entry) = 16`
bytes exactly, no padding. At the *default* range and T=1: `raw = floor(0.25 x 110100480 / (4 x 16 x
1)) = floor(27525120 / 64) = 430080`; the clamp loop from `4096` doubles through `8192, 16384, 32768,
65536, 131072, 262144` (each `<= 430080` and `<= S3_MAX_SETS=262144`), then stops (`524288 >
S3_MAX_SETS`) - **confirms the already-built `kraken2-fresh-bin-s2-lru-noatomics-4way` binary is
already, at T=1, the 262144-set point** by coincidence of the default formula's own clamp. Considered
reusing that binary for the sweep's 262144 point to save a build, but **decided against it**: that
binary was built 2026-09-02, and the *current* `kraken2-src-fresh` tree already has the S4.0 hashmix
fix (`MurmurHash3` bit-mixing in `S2SetIndex`, an 8.9x hit-rate change) baked in - verified via
`strings ... | grep MurmurHash` that the old binary ALSO already has the hashmix symbol, so it's
probably fine, but "probably fine" isn't good enough for a paper-facing sweep where every other point
is freshly built from today's exact source state. **Built all 6 points fresh from the same current
tree instead**, for guaranteed internal consistency, at the cost of one redundant build.

**Status: Step 0 complete.** Size is a compile-time constant; the pin-both-bounds technique is
mathematically confirmed to work; proceeding to build.

---

### Size ladder built and verified (`2026-09-15`)

Built 6 real `classify` binaries from `kraken2-src-fresh` (current state: S1+S2 4-way noatomics +
S3.0/S3.1/S3.2/S3.3 + S4.0 hashmix), each a fresh copy with `S3_MIN_SETS`/`S3_MAX_SETS` both sed'd to
one target: `2048, 4096, 16384, 65536, 262144, 1048576` (the brief's ladder - default clamp bounds
plus one point below, one above). Install dirs:
`kraken2-fresh-bin-s2-lru-noatomics-4way-sizepin-{N}` for each N. All 6 `make`/install runs completed
clean (`install_kraken2.sh` succeeded, binaries present).

**Correctness verified** the same way every prior binary in this project was checked: ran each
natively against `~/cache_simulation/workloads/tiny_10reads.fastq` on `sample_targeted` (50MB DB).
All 6 produced **exactly 7/10 classified**, and a pairwise `diff` of the 2048-set output against
every other size (4096/16384/65536/262144/1048576) came back **empty** - byte-identical
classification, as expected (the cache is a pure lookup-path optimization; size cannot change *what*
gets classified, only how fast). Also diffed against true-no-cache S0 (`kraken2-src-baseline`):
**empty diff** - matches every earlier correctness check in this project (step 40, step 54, etc.).

**Disk headroom checked before building:** 137G free on `/` - six more ~small source/build trees is
negligible relative to that.

---

### Size sweep launched (`2026-09-15 20:21 IST`)

Wrote `cache_simulation/scripts/run_size_sweep.sh` (mirrors the exact pattern of
`run_hw_assoc_sweep.sh`/`run_laptop_sweep.sh`: same `./run-sniper -c address_translation_schemes/baseline
-c luna -n 1 -d <outdir> -- <classify invocation>` syntax, same log-parsing regexes for
instructions/cycles/IPC/unique-cache-lines/L1-L2-NUCA hit rates from `sim.stats`, same
`live_summary.csv` + `progress.log` live-append pattern). 12 runs: 6 sizes x 2 DBs (`sample_targeted`
50MB, `standard_8gb` 8GB), workload fixed at `tiny_10reads.fastq` (10 reads - the read-count axis is
already characterized per the brief's methodology, kept fixed and small here so each run stays in the
1-4 minute range based on prior 10-read timings).

Mirrored to Luna (`~/cache_simulation/run_size_sweep.sh`), launched via `nohup ... & disown` so it
survives disconnect - **PID 485896** (the wrapper script; the actual `run-sniper`/simulator
subprocesses spawn under it, first one confirmed live via `ps aux` ~3s after launch, already
running `size2048_50mb`). Runs alongside the pre-existing, unrelated `run_laptop_sweep.sh` job (PID
484181, mid-way through its own 8GB/16GB queue) - no interference expected, Luna has 96 real cores and
every prior parallel-job precedent in this log (steps 42, 44) confirms independent Sniper jobs don't
meaningfully contend at this scale (the earlier contention bug, step 53, was specifically about
*wall-clock* timing validity across concurrent jobs, not about correctness or the *cycles* metric -
cycles stays the trustworthy metric here regardless).

Output: `results_size_sweep/live_summary.csv` (columns: `size,db,instructions_M,cycles_M,ipc,
unique_cache_lines,l1d_loads,l1d_hit_pct,l2_hit_pct,nuca_hit_pct,elapsed_s,wallclock_s`) and
`results_size_sweep/progress.log` (timestamped start/done per run). Estimated total time: 12 runs x
~1-4 min/run (10-read workload precedent) = roughly 15-45 min, though running alongside the other job
may slow wall-clock (cycles metric unaffected either way). Check progress via:
```bash
ssh -i ~/.ssh/luna_claude student@luna.cse.iitd.ac.in "tail -20 ~/cache_simulation/results_size_sweep/progress.log; cat ~/cache_simulation/results_size_sweep/live_summary.csv"
```

**Status: sweep running, not yet complete.** Next: monitor, merge results into the Iteration
1 Analyse-phase context, regenerate charts (fig14+) once done.

---

### Iteration 1 (Analyse -> Plan -> Discuss) - conclusion (`2026-09-15`)

5 independent agents (A-E) read the brief + `command_log.md` + all 5 CSVs + the scripts/configs,
each took an independent first-pass position on H1-H4 before any cross-talk, then drafted an
iteration-1 plan, then were put in Discuss together. Full per-agent Analyse/Plan text is not
reproduced here (available in this session's transcript) - this entry is the Discuss-phase
synthesis: where they agreed, where they genuinely disagreed, and what iteration 2 inherits.

**Convergence (4-5 of 5 agents independently landed here):**
- H1 (small-DB loss is structural): all 5 lean "likely holds," none claim it's proven - correctly,
  since no agent's evidence actually varied SOFTWARE cache size on the 50MB DB before this
  synthesis. The shared reasoning is the hw_assoc NULL result (findings 1/2) plus the fact that
  L2/LLC hit rates stay under ~1-2% at every tested associativity/read-count on this DB.
- H2 (large-DB win plateaus/reverses, not monotonic): all 5 lean toward refuted-as-monotonic,
  citing the already-logged 103GB dip below 16GB (1.97x vs 2.05x, `final_fair_batch`) even at the
  DEFAULT cache size, before capacity is touched at all - i.e. there's already a non-monotonicity
  signal in existing data, just along the DB-size axis rather than the cache-size axis.

**The most important catch, surfaced by Agent C, that the other 4 agents did not flag on their
own:** it is a live methodological risk to treat the hw_assoc_sweep NULL result (fig12/13) as
dispositive evidence against a SOFTWARE size win on the 50MB DB. Hardware LLC associativity and a
software S2 lookup cache intercept at genuinely different points in the pipeline - the hardware
LLC only gets consulted on an L1 miss for whatever physical address the raw hash-table probe
touches, while the S2 cache sits BEFORE that probe and intercepts by minimizer identity, not
address. A workload that never pushes traffic past L1 tells you hardware associativity is moot: it
says nothing directly about whether repeat MINIMIZER lookups exist for an identity-keyed structure
to catch, since that's a question about logical reuse in the access pattern, not physical cache
residency. **Verdict: H1 stays a genuinely open, not a foregone, conclusion until the real
size-ladder data lands on sample_targeted** - the group explicitly declines to let the hw_assoc
null pre-decide it.

**The sharpest real disagreement, between Agent D and Agent E, carried forward as the specific
thing Iteration 2 must resolve with real data:** what mechanism would drive a "size costs more
than it helps" reversal (the thing H2 predicts), and does it look like width's reversal did?
- **Agent E's position:** size and width are effectively the same dial - both grow the amount of
  cache structure/metadata touched per operation, so a size sweep should reproduce the same
  gradual, monotonic-with-scale cost curve already seen going 4-way -> 8-way -> 16-way (instructions
  and unique_cache_lines climbing steadily, IPC flat, cycles worsening in step).
- **Agent D's position, mechanistically sharper:** in a fixed-4-way set-associative cache, a
  lookup only ever scans the 4 ways of ONE set - growing the total set count (S3_MIN_SETS/MAX_SETS,
  what this sweep actually varies) does NOT increase per-lookup comparison work the way growing
  WAYS did. So size's cost, if any, should come from a structurally different source: allocation /
  first-touch / page-fault cost of a much bigger `calloc`'d array, which the log's own S3.3 section
  already identified as a real, separate failure mode on real hardware (`>=1,048,576`-set slowdown
  cliff, 22x, driven by PER-THREAD memory multiplication) - a CLIFF at a specific large size, not a
  gradual climb.
- **Why this matters for what the data should look like:** if E is right, cycles-vs-size should
  rise smoothly across the whole ladder, same shape as the width curve. If D is right, cycles-vs-size
  should stay roughly FLAT from 2048 through 262144 (no extra per-lookup cost, only one set's 4 ways
  ever get scanned regardless of table size) and only jump sharply at/near 1,048,576 (the allocation
  cliff). One important caveat the group flagged explicitly: D's cited real-hardware cliff mechanism
  was measured under many-thread contention (96 threads x per-thread multiplication); every Sniper
  run in this sweep is `-n 1`/`-p 1` (T=1) - so even if a cliff exists at T=1, the underlying cost
  driver may be pure first-touch/page-fault latency for one large allocation, not the
  thread-multiplied blowup the real-hardware finding described. The two mechanisms could still
  produce a similarly-shaped cliff at a similar size, or could diverge - genuinely unresolved,
  Iteration 2's first job is to check the ACTUAL SHAPE of the curve (flat-then-cliff vs. gradual
  climb), not just compare endpoints.

**H3 (absolute vs. fractional optimum):** no agent had real cross-DB size data; two (A, E)
independently offered the same weak prior (footprint/cache_lines touched at 4-way stays in a
similar order of magnitude across 8GB/16GB/103GB in the existing default-size data, suggesting the
"useful working set" a cache can capture may be bounded by workload/read characteristics more than
DB size) - both explicitly flagged this as their shakiest, least-evidenced position. Carried
forward as a weak lean toward H3 refuted (near-constant absolute optimum), to be tested for real
once the 50MB and 8GB size-sweep rows can be compared directly.

**H4, the sharpest scoping catch, from Agent D:** the real-hardware null (commit `84436dd`,
`f=0.25` clamped `[4096,262144]`, "<2% hit rate regardless of implementation") and this project's
Sniper sweeps may not be adjudicating the same claim. Three concrete incompatibilities: (1) the
real-hardware result spans 6 THREAD COUNTS with one SHARED cache under contention; every Sniper run
here is single-threaded, no contention - not the same regime. (2) the wallclock-vs-cycles metric
discipline (this log's own step 60 correction) was locked down AFTER that Aug 2026 real-hardware
work; unclear if it used comparable rigor. (3) the real-hardware null is a uniform "<2% everywhere"
claim across multiple DB sizes, stronger and broader than anything the DB-size-dependent Sniper
data has shown. **Group conclusion: Iteration 3's H4 verdict must be explicitly SCOPED** - a
single-thread, capacity-varied Sniper finding can support or complicate H4 for that regime, but
cannot by itself confirm or refute the real-hardware multi-thread null. State both regimes'
findings side by side at the end rather than collapsing them into one verdict.

**Iteration 1 conclusion (per the brief's requirement that each iteration end in something
decided, not "more research needed"):** the group adopts the size-ladder-x-2-DB Sniper sweep already
launched (see above) as satisfying Iteration 1's Plan phase exactly - no agent's proposed plan
materially diverged from what the fork was already executing, only emphasis differed. The one
substantive addition Discuss produced beyond the launched sweep: **Iteration 2 must read the SHAPE
of the cycles-vs-size curve on both DBs (flat-then-cliff vs. gradual climb), not just the
2048-vs-1048576 endpoints**, to adjudicate the D-vs-E mechanism disagreement - this determines how
the eventual fig14 chart should be built (log-x with attention to a possible discontinuity, not a
simple two-point bar comparison). H1 remains open pending real 50MB size data (explicitly NOT
pre-decided by the hw_assoc null, per Agent C's catch). H2 leans toward "non-monotonic, mechanism
TBD" using existing DB-size-axis evidence as a proxy, to be replaced by real cache-size-axis
evidence in Iteration 2. H3 and H4 remain open with explicit scoping caveats attached, carried
forward as-is.

---

### Size sweep redirected mid-run: 50MB queue stopped, retargeted to pluspf_103gb (`2026-09-15 20:44`)

**Why:** a peer Claude session working this same repo relayed CK's explicit instruction (given in
that other session): stop queuing more 50MB (`sample_targeted`) size-sweep runs - that DB is already
established (hw_assoc_sweep, every prior associativity/read-count sweep) to structurally never
benefit from any software cache regardless of organization, so further size points there add
confirmation, not new signal. The peer's own equivalent script had already been redirected to cover
`standard_8gb` + `standard_16gb` concurrently - to avoid duplicating that coverage, this session
retargeted its own sweep to the one DB regime neither covers: `pluspf_103gb` (104GB).

**What happened operationally:** `run_size_sweep.sh` (PID 485896) had completed 4 of its planned 6
50MB points (2048/4096/16384/65536, all recorded in `results_size_sweep/live_summary.csv`) and had
just started `262144/50mb` when the redirect decision landed. Attempting to stop it hit a real,
instructive bug: `pkill -f "run_size_sweep.sh"` run over SSH matches against full command lines,
and the remote shell invocation *of that very SSH command* contains the literal substring
"run_size_sweep.sh" - so the kill command killed its own remote shell (and, as a side effect, the
wrapper's parent process group), dropping the SSH connection with exit 255 and orphaning the
in-flight `262144/50mb` run's child processes. Diagnosed via reconnecting and checking `ps`/exit
codes directly rather than guessing - confirmed the orphaned run-sniper/record-trace processes had
also died (no separate `nohup`/`disown` of their own, only the wrapper had it) rather than
completing, so `262144` and `1048576` on 50MB were never produced and don't appear in the CSV. Net
effect: **the 50MB portion stops cleanly at 4 real points (2048/4096/16384/65536)** - not the full
6-point ladder, but enough to see the shape of the curve where it's already expected to be flat/null
(per Iteration 1's synthesis), and no runs were left dangling or half-written.

**New script:** `cache_simulation/scripts/run_size_sweep_103gb.sh` - identical structure/binaries/
workload (`tiny_10reads.fastq`, same 6 pinned 4-way binaries, same `luna.cfg`, same
`live_summary.csv`/`progress.log` schema) as `run_size_sweep.sh`, DB fixed to `pluspf_103gb`. Full
6-point ladder queued (2048/4096/16384/65536/262144/1048576), since 103GB is a regime where the
default-size cache already shows the largest measured win (1.97x) and where H2's plateau/reversal
question matters most. Mirrored to Luna, launched via `nohup`+`disown` (PID `490326`), confirmed live
~1s after launch on `size2048_103gb`. Output: `results_size_sweep_103gb/{live_summary.csv,
progress.log}`. Running alongside 3 other concurrent Sniper jobs on Luna now (peer's 8GB/16GB size
sweep, the pre-existing `run_laptop_sweep.sh`) - correctness/cycles unaffected by concurrency per
every prior precedent in this log (step 53's contention bug was specifically about wall-clock
validity across batches, not cycles); wall-clock timings from this run should not be compared
cross-batch against earlier sequential runs, per the established discipline.

**Status: 50MB portion of the size sweep is done (4/6 points, by design). 103GB portion running.**

---

### Iteration 2 (Analyse -> Plan -> Discuss) - conclusion (`2026-09-15 21:1X`)

Same 5-agent structure as Iteration 1, this time working against REAL landed data (not just
extrapolation from prior sweeps): 4 points on 50MB (2048/4096/16384/65536), 4 points on 103GB (same
sizes, 65536 landed mid-iteration), 3 points on 8GB (peer's sweep, stopped at 16384 as of this
writing). Each agent was given the same real CSV rows plus Iteration 1's conclusion and told to
independently re-check/revise their own prior Iteration-1 position against the real numbers.

**The headline real finding, confirmed by 3 of 5 agents independently:** cycles are FLAT (identical
to 1 decimal) from 2048 through 16384 sets on every DB tested, then jump at 65536 - **and the jump
recurs at the exact same absolute set count on both 50MB (14.2->15.1M cycles, +6.3%) and 103GB
(15.1->16.0M cycles, +6.0%)**, two DBs 2000x apart in size, with l1d_loads jumping by a similar
absolute magnitude on both (+660,776 on 50MB, +621,424 on 103GB). This is strong, DB-independent
evidence that whatever's happening at 65536 is a property of the S2 cache's own pinned array size
(65536 x 4 ways x 16 bytes = 4,194,304 bytes = 4MB), not of the underlying database.

**Mechanism, resolved further than Iteration 1 left it:** three candidate explanations were live
going into this iteration (Agent D's original per-thread S3.3-style cliff; Agent E's original
gradual-growth; a new hardware-boundary theory from Agent A that the 4MB array crosses Luna's real
2MB private L2). All three took real damage from the data:
- **Agent D's original cliff-near-1,048,576 prediction is wrong on location** (the real onset is
  65536, four ladder-steps early) **and wrong on cited mechanism** (S3.3's per-thread multiplication
  can't apply at T=1, which every run in this sweep uses) - Agent D explicitly retracted it.
- **Agent E's original "gradual growth" is refuted outright** by the flat 2048->16384 region - there
  is no gradual per-step cost at any point in this data. Agent E, re-examining the associativity/width
  CSVs it had originally cited as "gradual," found width is ALSO flat-then-step (1-way->4-way is flat
  or slightly negative; the real jump is 4-way->8-way), not smooth as characterized in Iteration 1 -
  a real self-correction, not just data catching the prediction out.
- **Agent A's L2-boundary theory (4MB array vs. Luna's 2MB private L2) is mechanistically clean but
  empirically wrong**, per Agent D's direct measurement: a real hardware-boundary/latency effect
  should show IPC DROPPING at the jump (more stall cycles per instruction). The data shows the
  OPPOSITE - IPC rises at 65536 on both DBs (50MB: 1.78->1.84; 103GB: 1.68->1.74). Agent D also
  directly grepped `sim.stats` for `size16384_50mb` vs `size65536_50mb` and found the page-table-walk
  and DRAM-read counter deltas (1,088 and 1,387 respectively) are three orders of magnitude too small
  to explain the 660,776-load jump - ruling out TLB-reach and page-walk artifacts by direct
  measurement, not guesswork.

**Leading mechanism after Discuss (not yet fully confirmed, but the best-supported candidate):**
Agent D's revised proposal - a linear, one-time O(sets x ways) initialization/bookkeeping cost
(e.g. an explicit per-slot sentinel write, or some other linear pass over the newly-allocated array)
that scales with total entry count, not DB size and not thread count. This explains every constraint
the data imposes at once: (1) same absolute onset regardless of DB (it's a property of the array,
matching Agents A/C/D's cross-DB observation), (2) IPC flat-or-rising rather than falling (it's
throughput work, not a latency stall, matching Agent D's own sim.stats check and independently
Agent B's observation that "more instructions/loads with flat-to-better IPC" is the signature of
doing more real work, not the same work stalling harder), (3) Agent B's original "hash-collision
artifact specific to this one sample" concern is substantially weakened (not eliminated) by the
cross-DB recurrence at 103GB, since an artifact of one specific minimizer sample shouldn't
reappear at the identical absolute threshold against a completely different DB's completely
different minimizer distribution.

**Real gap found and filled this iteration:** Agent A and Agent C both independently discovered that
no genuine true-S0 (no-cache) baseline exists anywhere in this project's logged data for the EXACT
config this size sweep uses (10 reads, `sample_targeted`, `luna.cfg`) - the closest candidate
(`associativity_sweep_2026-09-08_summary.csv`'s `baseline` row) is the same mislabeled binary flagged
back in step 40 (has `s2_cache` compiled in, not true no-cache). This is a real, fillable, cheap gap
- the coordinating session ran it directly rather than deferring: `kraken2-src-baseline` (source-grep
and `strings`-confirmed zero `s2_cache` symbols) against the same 10-read/`sample_targeted` config,
launched on Luna (`results_size_sweep/S0_50mb`), in progress as of this entry - see next entry for
the result once it lands.

**H1 (small-DB structural loss):** every software-cache size tested on 50MB (14.2-15.1M cycles) is
close to but has not yet been directly compared against a genuine matched-config S0 number - that
comparison is the very next thing this log will report. Provisionally, Agent A's argument (using the
best available, if imperfectly-matched, prior data) that the cache loses at every size and the
margin WORSENS at 65536 rather than improving is the strongest evidence so far for H1 leaning
confirmed - but per Agent C's explicit caution, this should not be called fully confirmed until the
matched S0 number lands.

**H2 (large-DB plateau/reversal):** still open - 103GB's 65536 point shows a COST increase (not
further speedup) relative to smaller sizes within the software-cache-only comparison, consistent
with the same linear-init mechanism rather than a size-driven improvement. Whether this holds through
262144/1,048,576 (still queued on 103GB) or whether hit-rate gains eventually outrun the linear cost
at larger sizes remains the single biggest open question for Iteration 3.

**H3 (absolute vs. fractional optimum):** this iteration produced the sharpest evidence yet, and it
points toward REFUTED (absolute count, not DB fraction) - three DBs spanning a 2000x size range
(50MB/103GB directly measured, 8GB pending its own 65536 point) show the transition at the identical
absolute set count, not a size scaled to each DB. If 8GB's 65536 point (still queued in the peer's
sweep) confirms the same ~6% jump at the same point, H3-refuted becomes a 3-for-3 finding.

**Iteration 2 conclusion, carried into Iteration 3:** (1) get the true-S0 comparison landed and
state H1 with real numbers, not inference; (2) get 8GB's 65536 point and 103GB's 262144/1,048,576
points to complete the mechanism/H2/H3 picture; (3) Iteration 3's H4 verdict should explicitly state
that this project's own real-hardware S3.3 cliff mechanism (per-thread allocation multiplication)
has now been actively RULED OUT as the explanation for what this sweep found at T=1 - a different,
DB-independent, throughput-bound linear-initialization mechanism is the current best account, and
this distinction matters for whether kraken2's real multi-threaded default formula should change
(the fix, if any, would need to address a fixed initialization tax per rebuild-time size choice, not
a per-thread-scaling problem).

---

### This session's parallel jobs - progress check (`2026-09-15 21:17 IST`)

Three jobs owned by this session, running in parallel with the peer session's `run_size_sweep_103gb`:

**`cache_size_sweep` (8GB+16GB, size axis, 4-way fixed)** - 3 of 12 rows in on 8GB:

| size | cycles_M | ipc | unique_cache_lines | l2_hit_pct |
|---|---|---|---|---|
| 2048 | 27.9 | 1.87 | 53,769 | 0.90 |
| 4096 | 27.9 | 1.87 | 54,949 | 0.90 |
| 16384 | 27.9 | 1.87 | 56,942 | 0.89 |

Sanity check (16384): 27.9/52.1=0.5355 cycles/instr -> IPC=1.867, matches reported 1.87. Cycles are
completely FLAT across these first 3 sizes despite `unique_cache_lines` climbing (the cache is
genuinely holding more distinct entries as it grows) - consistent with the peer's Iteration 1/2
finding that small-to-mid sizes don't move cycles on the 8GB DB either; watching for whether the same
~6% jump the peer found at 65536 on 103GB also appears here once 8GB's own 65536 row lands (still
running as of this check).

**`hw_assoc_sweep_bigdb` (8GB+16GB, hardware-only associativity, S0/no software cache)** - 1 of 12
rows in: assoc=1 (18000 sets) on 8GB -> 51.8M cycles, 1.32 IPC (sanity: 51.8/68.1=0.7606 ->
IPC=1.315, matches). `instructions_M`=68.1 exactly matches the historical `desktop,8gb,S0` row from
`hwsize_comparison_2026-09-09.csv` - expected, since instruction count comes from the trace and is
hardware-config-independent. Too early to say whether associativity matters on this DB (only 1 of 6
associativities done); the 50MB DB's null result does NOT necessarily carry over here, since more of
this DB's working set plausibly reaches the LLC layer - genuinely open until more rows land.

**`laptop_sweep`** - 13/32 rows done, now on `50 reads/16GB/S0`. On schedule, no anomalies.

All three CSVs pulled to `cache_simulation/measurements/` (`cache_size_sweep_8gb16gb_2026-09-15.csv`,
`hw_assoc_sweep_bigdb_2026-09-15.csv`, `laptop_sweep_2026-09-15.csv`).

---

### 103GB size sweep COMPLETE (6/6) + true-S0 baseline landed - Iteration 2's leading mechanism overturned (`2026-09-15 21:3X`)

**True S0 (`kraken2-src-baseline`, zero `s2_cache` symbols) on 50MB, 10 reads, matched exactly to
the size sweep's own config:** `23.9M instructions, 14.1M cycles, 1.69 IPC, 35,798 unique cache
lines`. This is the real comparison Agents A/C flagged as missing in Iteration 2. Against it: every
software-cache size tested on 50MB (2048/4096/16384: 14.2M cycles, +0.7%; 65536: 15.1M, +7.1%) is at
best a wash and at worst a real loss - **no size tested beats true S0 on this DB.** This is now a
direct, matched-config confirmation of H1, not an inference from a mislabeled baseline.

**103GB's full 6-point ladder finished** (`ALL DONE 2026-09-15 21:29:42`) and it overturns
Iteration 2's leading "linear O(sets x ways) init cost" hypothesis:

| size | cycles_M | l1d_loads | l2_hit_pct |
|---|---|---|---|
| 2048 | 15.1 | 6,744,761 | 1.57 |
| 4096 | 15.1 | 6,744,754 | 1.57 |
| 16384 | 15.1 | 6,744,614 | 1.56 |
| 65536 | **16.0** | **7,366,038** | 1.75 |
| 262144 | 15.1 | 6,744,722 | 1.54 |
| 1048576 | 15.1 | 6,744,732 | 1.54 |

**Cycles and l1d_loads both REVERT to the flat baseline at 262144 and 1,048,576** - the 65536 point
is an isolated spike, not a threshold that persists or grows at larger sizes. A linear
init-cost-proportional-to-capacity mechanism (Iteration 2's leading candidate) predicts monotonic
growth or at minimum persistence past the onset point - it does not predict a full reversion at 4x
and 16x past the spike. **The 8GB sweep (peer session, still running) shows the identical shape**:
flat 27.9M cycles at 2048/4096/16384, spike to 28.6M at 65536 (+2.5%, smaller relative jump than
50MB/103GB's ~6-7% but same direction), reverting to 27.9M at 262144. Three DBs (50MB was stopped
before reaching 262144/1048576, tail run launched - see below) now show the same isolated-spike
shape, two of three (8GB, 103GB) confirmed reverting afterward.

**Revised mechanism position: this looks like a genuine hash-distribution/load-factor artifact
specific to a table with exactly 65536 buckets, for this specific minimizer set, not a general
size-cost law.** `S2SetIndex` masks `MurmurHash3(minimizer)` against `(sets - 1)` - every power-of-2
set count consults a different, non-overlapping window of hash bits, and it is entirely possible for
one specific window (the bits selected at exactly 2^16) to produce worse-than-average bucket
occupancy for a specific minimizer sample than either its neighbors (2^14, 2^18) do, by ordinary hash
variance - MurmurHash3 is not perfectly uniform for every possible mask/input combination, especially
at modest sample sizes (10-50 reads). This retroactively vindicates Agent B's Iteration-2 skepticism
("workload/hash-interaction artifact... not a general size-cost law") over Agent D's revised linear
mechanism - though the fact that it recurs at the SAME size (65536) across three independent DBs with
different minimizer content is still real and needs an honest account: the shared factor across all
three runs isn't the DB, it's the MurmurHash3-mixed low bits of whatever minimizers this project's
fixed 10-read (`tiny_10reads.fastq`) / 50-read workload files contain - the workload is the same
FASTQ file's minimizers hitting the hash function the same way at the same mask width, regardless of
which DB's k2d file backs the lookup. **This is now the leading, most parsimonious explanation**:
a real but narrow, workload-file-specific hash-distribution effect at one particular table size, not
a property of kraken2's cache design that would recur for other read samples or persist as DB/cache
sizes scale up.

**Launched a tail run to complete 50MB's ladder** (`run_size_sweep_50mb_tail.sh`, sizes 262144 and
1,048,576, same binaries/DB/workload as the original 50MB sweep) to check whether 50MB shows the same
revert-after-spike shape as 103GB/8GB just confirmed - PID 496143, running. This is the last real

---

### 50MB tail complete, 8GB complete (6/6) - 3-for-3 on the revert pattern; a script bug caught and fixed (`2026-09-15 21:45`)

**8GB (peer's sweep) finished its own remaining points:** 262144=27.9M cycles, 1048576=27.9M cycles
- both back at the flat baseline, exactly mirroring 103GB's shape. 8GB is now a complete 6-point
ladder, fully confirming the isolated-spike-at-65536-then-revert pattern independently.

**50MB tail run finished** (`TAIL ALL DONE 2026-09-15 21:45:42`), but hit a real bug: the tail
script (`run_size_sweep_50mb_tail.sh`) logged progress-log lines correctly but was written without
the parsing/CSV-append block the original `run_size_sweep.sh` has - both runs completed and produced
valid `sim.stats`, but never wrote rows into `live_summary.csv`. Caught by checking the CSV directly
after the "Done" lines appeared in `progress.log` and finding it short two rows. **Fix: recovered
both rows manually from the raw logs/`sim.stats`** rather than re-running (the simulation output
itself is valid, only the parsing step was missing from the script):

| size | cycles_M | instructions_M | ipc | unique_cache_lines | l1d_loads | l2_hit_pct |
|---|---|---|---|---|---|---|
| 262144 | 14.2 | 25.2 | 1.77 | 49,974 | 6,615,895 | 1.45 |
| 1048576 | 14.3 | 25.2 | 1.77 | 50,458 | 6,615,882 | 1.44 |

**50MB reverts too** - 14.2M/14.3M cycles, both back at (or within noise of) the 14.2M flat baseline
seen at 2048/4096/16384, l1d_loads back at ~6.616M (matching the pre-spike baseline exactly, not the
~7.28M seen at the 65536 spike). **This makes it 3-for-3 across every DB tested (50MB, 8GB, 103GB):
cycles are flat, spike sharply and specifically at 65536 sets, then fully revert at 262144 and
1,048,576.** This is now a fully confirmed, cross-DB-replicated finding, not a hypothesis - the
isolated-spike-at-one-specific-table-size explanation (a hash-distribution artifact tied to this
project's fixed workload file's minimizer set at exactly the 2^16 mask width) is the best-supported
account, and no further real runs are needed to establish the SHAPE of the curve. Iteration 3 has
everything it needs for a fully evidence-backed H1-H4 verdict.

**Status: size sweep fully complete on all 3 DB regimes. Ready for Iteration 3.**

---

### 8GB size sweep COMPLETE (6/6) - confirms the size=65536 anomaly on a 2nd DB (`2026-09-15 21:49 IST`)

This session's `cache_size_sweep` finished all 6 sizes on the 8GB DB. Combined with the peer
session's now-also-complete 103GB sweep, the size=65536 spike the peer flagged in Iteration 2 is
confirmed on a SECOND, very differently-sized database - it is an isolated point anomaly, not a
trend, on both:

| DB | 2048/4096/16384 | **65536** | 262144/1048576 |
|---|---|---|---|
| 8GB | 52.1M instr / 27.9M cycles (flat) | **54.4M instr / 28.6M cycles (+4.4%)** | back to 52.1M / 27.9M |
| 103GB | 25.4M instr / 15.1M cycles (flat) | **28.0M instr / 16.0M cycles (+10.2%)** | back to 25.4M / 15.1M |

Sanity checks: 8GB/65536: 28.6/54.4=0.5257 -> IPC=1.902, matches reported 1.90. 103GB/65536:
16.0/28.0=0.5714 -> IPC=1.750, matches reported 1.74 (rounding). Both internally consistent - this
is a real simulated effect (cycles move, not just wallclock), not a logging artifact.

**This satisfies H3's outstanding requirement from Iteration 2** ("if 8GB's 65536 point confirms
the same jump at the same point, H3-refuted becomes a 3-for-3 finding") - the spike sits at the
identical ABSOLUTE entry count (65536 = 2^16) on both DBs despite a ~13x difference in DB size,
strong evidence this is an absolute-count effect (H3 refuted: the anomaly is NOT scaled to DB size)
rather than something DB-size-relative. Magnitude does scale with DB size though (4.4% on 8GB vs.
10.2% on 103GB) - worth noting as a nuance for whoever writes the final H3 verdict: the TRIGGER point
is absolute, but the SEVERITY may still be DB-size-dependent.

Leading hypothesis (not yet confirmed): 65536 = 2^16 is a suspicious round number to spike at
specifically - possibly a hash-table internal representation boundary (e.g. a 16-bit index/counter
type overflowing or changing behavior exactly at this size), a load-factor/rehash threshold
coinciding with this entry count, or a build-specific quirk in that one sizepin binary's compilation.
Whoever picks this up next should check `kraken2-src-sizepin-65536`'s build log/diff against its
neighbors (`16384`, `262144`) for anything size-specific in the generated code, not just the size
constant itself.

Notified the peer session (`nanopore-project-c1`) of this confirmation since it completes their
Iteration 2 evidence request. Both size sweeps (8GB+16GB mine, 103GB theirs) have now fully covered
the size axis on every big DB planned so far. `hw_assoc_sweep_bigdb` (this session) is 2/12 in
(assoc=1: 51.8M cycles, assoc=4: 51.7M cycles - nearly flat so far, too early to call). `laptop_sweep`
is 16/32.

---

## ITERATION 3 (FINAL) - Analyse -> Plan -> Discuss - citable verdict on H1-H4 (`2026-09-15 22:0X`)

5 agents, each assigned one final deliverable against the complete dataset (all three size-sweep
CSVs, fully landed, no more real runs needed): Agent A -> H1 verdict, Agent B -> H2 verdict, Agent C
-> H3 verdict, Agent D -> H4 verdict, Agent E -> fig14 chart + independent cross-check of the core
numeric claims. This entry is the Discuss-phase synthesis and closes the research brief.

**A cross-session note first, since it bears directly on the numbers below:** a peer session
reported +4.4% (8GB) and +10.2% (103GB) for the 65536 anomaly, differing from this session's own
+2.5%/+6.0%. Traced the discrepancy: the peer's numbers are the **instructions_M** delta (52.1->54.4
= +4.4%; 25.4->28.0 = +10.2%), not cycles_M - this project has a hard-learned, explicitly logged rule
(step 60) about never conflating these two metrics, and this is exactly that mistake recurring in a
new form. Agent E's independent cross-check (below) confirms +2.5%/+6.0% is the correct cycles-based
figure. **Every number in this final verdict is cycles-based**, per that discipline.

### H1 - CONFIRMED: small-DB (50MB) loss is structural, not a sizing problem.

True S0 (no cache, matched exactly to the sweep's 10-read/`sample_targeted` config) = **14.1M
cycles**. Every one of the six tested sizes on 50MB is at or above it: 14.2/14.2/14.2/15.1/14.2/14.3M
- zero out of six beat S0, several tie within noise, one (65536) is 7.1% worse. Counterargument
addressed directly: could a size beyond 1,048,576 still flip this? No - the curve's shape (flat,
isolated spike, full revert) is not a rising trend that leaves room open at the far end; it's evidence
of near-zero reuse in this workload (consistent with findings 1/2's <2% L2/LLC hit rate), not a
capacity shortfall. The hardware-associativity NULL result (findings 1/2) is now promoted from
"corroborating" to **confirmed** - two independent axes (hardware associativity, software cache
capacity) now triangulate on the same zero-reuse mechanism.

### H2 - REFUTED (with a scoping correction): capacity does not drive the large-DB win, at all.

Across the full capacity range (2048 to 1,048,576 sets) on both 8GB and 103GB, cycles are IDENTICAL
at five of six sizes (27.9M / 15.1M) - capacity contributes zero additional speedup anywhere in
range. The one size that differs (65536) is a loss, not a gain. **The original H2 framing conflated
two different axes**: the default-size trend across increasing DB size (1.83x -> 2.05x -> 1.97x,
real, from Iteration 1's context) and the capacity axis this sweep actually varied - these are not
the same lever. The DB-size trend's cause remains open (workload/hit-rate structure, not cache
capacity) but is now explicitly ruled OUT as a capacity-driven effect. Practical takeaway: the
default-size cache is already at its ceiling for this workload past 2048 sets; there is no
capacity-driven headroom on 8GB/103GB left to capture.

### H3 - REFUTED, with a nuance the cross-session exchange surfaced: absolute count sets the trigger, but magnitude still scales with DB size.

The 65536 anomaly lands at the **identical absolute set count** on 50MB, 8GB, and 103GB (a 2000x
DB-size range) - if H3's DB-fraction model were correct, this would appear at wildly different
set counts per DB; it does not. **H3 refuted on trigger location.** The nuance, raised by the peer
session and confirmed here on the corrected cycles-based numbers: the anomaly's MAGNITUDE is not
DB-size-invariant - 50MB +6.3%, 8GB +2.5%, 103GB +6.0% (no clean monotonic relationship with DB size,
but clearly not identical either). **Correct final statement: WHERE the size axis matters is a fixed
absolute threshold (H3 refuted for location), but HOW MUCH it matters when it does is DB-dependent**
- a hash-collision artifact's severity plausibly depends on how many real lookups collide against
that specific bad mask width, which is itself a function of workload/DB content, even though the mask
width triggering it is fixed. Outside that one anomalous point, capacity and DB size don't interact
at all (Agent E's per-DB-median deviation check: every non-65536 size is within <=0.7% of its own
DB's median, on all three DBs) - reinforcing that "optimal size" isn't a meaningful search question
in this regime; there's a flat plane with one narrow, DB-content-sensitive hole in it, not a hill to
climb.

### H4 - CONFIRMED for the tested (T=1, capacity-varied) regime; explicitly UNABLE to speak to the real (T>1, contention) regime the production formula actually governs.

At T=1, kraken2's own default formula lands on 262144 sets - indistinguishable from every other
size in the flat region (2048 through 1,048,576), so "near-optimal" is confirmed only in the trivial
sense that nothing beats it, because nothing beats anything else either (capacity isn't the active
variable at T=1). This does NOT validate the formula for its real operating regime: the real-hardware
S3.4 null (commit `84436dd`, T>1, shared cache under contention, <2% hit rate "regardless of
implementation") is driven by a fundamentally different mechanism (thread contention thrashing a
shared structure) than what this sweep exercised (a T=1, no-contention, hash-distribution artifact at
one specific set count). A null in one regime provides zero evidence about the other - this was
Iteration 1's scoping caveat, and Iteration 3 confirms it holds all the way to the end rather than
resolving it. **Concrete recommendation: do not change f=0.25 or the clamp bounds** - this sweep found
no capacity value worth moving to, in either direction, at T=1, and the actionable fix for the real
production problem is orthogonal to sizing entirely - pursue S4-class eviction/sharding/partitioning
work instead of re-tuning the formula. Any future "is the formula wrong" question must be tested at
T>1 with real contention; a single-thread Sniper capacity sweep is structurally the wrong instrument
for that question, not just an incomplete one.

### Deliverable: fig14

Built (`cache_simulation/scripts/make_size_sweep_chart.py`, following fig1-fig13's exact matplotlib
style: serif font, `pdf.fonttype=42`, 300 DPI, PNG+PDF): a 3-panel small-multiples chart (one panel
per DB: 50MB/8GB/103GB), log2-x axis over the 6 tested sizes, y=cycles_M, the 65536 anomaly
visually called out with a distinct marker and its exact % deviation annotated per panel. Caption
explicitly distinguishes software cache CAPACITY (fixed 4-way) from every prior associativity/width
sweep (fig1/fig2/fig9-13) - the exact confusion this project has repeatedly had to correct. A real
legibility bug (rotated tick labels overlapping the axis-label text) was caught on first render and
fixed by increasing figure height/margin before finalizing, per this project's own "review the
rendered PNG, don't just trust the code" discipline (step 56). Files:
`cache_simulation/charts/fig14_size_sweep_all_db.{png,pdf}`.

**Independent cross-check (Agent E, computed directly from the three raw CSVs, not from any other
agent's summary):** confirmed every one of 50MB's six sizes is >= true S0 (14.1M); confirmed the
65536 anomaly is the only size showing any DB-size-correlated deviation (+2.5% to +6.3%), with every
other size within <=0.7% of its own DB's median cycles - no hidden second effect anywhere in the
data.

## FINAL VERDICT SUMMARY

| Hypothesis | Verdict | Key number |
|---|---|---|
| H1 - small-DB loss is structural | **CONFIRMED** | 14.1M cycles (true S0) <= every one of 6 tested sizes on 50MB |
| H2 - large-DB win grows with capacity | **REFUTED** | 5/6 sizes on 8GB/103GB are cycle-identical; capacity buys zero extra speedup anywhere |
| H3 - optimal size is a DB-size fraction | **REFUTED** (trigger location); magnitude is DB-dependent (nuance) | anomaly at identical 65536 across a 2000x DB-size range; severity +2.5%/+6.3%/+6.0%, not uniform |
| H4 - default formula (f=0.25, clamp) is near-optimal | **CONFIRMED at T=1 (trivially)**; cannot be adjudicated for the real T>1 regime | 262144 (formula's own T=1 output) indistinguishable from every other tested size |

**Practical recommendation for the two thesis pieces:** do not spend further effort tuning the
software cache's SIZE (Thesis 1's cache-sizing axis) on either DB regime - this research brief's
entire point was to test exactly that, and the answer is a clean no-benefit-from-tuning-size result
on all four hypotheses. Redirect that effort toward what this same investigation kept surfacing as
higher-leverage: eviction-policy work under real contention (S4), and Thesis 2's cell-width/double-
hashing track, which this sweep never touched and which remains fully open.

**Status: research brief complete.** All 3 iterations, all 4 hypotheses, real Luna data throughout,
fig14 delivered. Remaining open thread (not blocking): the peer session's suggestion to check
`kraken2-src-sizepin-65536`'s build log/diff against its `16384`/`262144` neighbors for a build-quirk
explanation of the anomaly, as an alternative to pure hash-collision - flagged for whoever picks up
Thesis 1 next, not resolved here.

---

### CORRECTION (`2026-09-15 21:52 IST`) - size=65536 anomaly magnitude was wrong

The previous entry's magnitude numbers (+4.4% on 8GB, +10.2% on 103GB) were **wrong** - caught by
the peer session cross-checking the same CSV. Those were the `instructions_M` deltas
(52.1->54.4 and 25.4->28.0), mislabeled as `cycles_M` deltas. The correct cycles-based figures:

- 8GB: 27.9M -> 28.6M cycles = **+2.5%**, not +4.4%
- 103GB: 15.1M -> 16.0M cycles = **+6.0%**, not +10.2%

The underlying finding (an isolated spike at exactly size=65536, absolute entry count not
DB-relative, confirmed on two DBs) is unaffected - only the magnitude numbers were wrong. Any
Iteration 3 write-up should cite +2.5%/+6.0% (cycles), not the earlier +4.4%/+10.2% figures.
Lesson: when multiple similarly-scaled columns exist in the same CSV row (instructions_M and
cycles_M here), explicitly name which column a percentage was computed from in the log entry
itself, not just in a table header - this is exactly the kind of transcription error this
project's `mtpweek2.md` memory already flagged as a recurring bug class ("mis-derived ratios/
misattributed numbers, always re-derive from source table").

---

### Hourly brief (`2026-09-15 23:25 IST`): flatl3_comparison + cache_size_sweep(16gb) both DONE

**flatl3_comparison (4/4)**: flat L3 is SLOWER than NUCA on both DBs - 50MB: 24.4M->31.9M cycles
(+30.7%), 8GB: 51.8M->60.4M cycles (+16.6%). Sanity checked (both IPCs match cycles/instr). Real
finding: the mesh-slice NUCA model isn't just "more realistic," it's meaningfully faster in this
sim than a naive flat bank - plausibly because the flat model's much larger set count (114,688 vs
NUCA's 1,200/slice) changes tag-lookup/collision behavior, not just latency. Closes to-do item 1.

**cache_size_sweep (16GB, 6/6)**: complete, not yet cross-checked for the 65536 anomaly on this 3rd
DB size within the 8GB/16GB pair - next check should confirm/refute it there too.

**Still running**: `hw_assoc_sweep_bigdb` 8/12 (on 16gb/assoc4). `laptop_sweep` 17/32 (on slow
100-read/8gb tier, expected ~4-5hrs for this row).

---

### Hourly brief (`2026-09-16 00:22 IST`)

**hw_assoc_sweep_bigdb**: 11/12 done (last row running). Null result HOLDS on big DBs too - 8GB
cycles flat 51.7-51.8M across all associativities, 16GB flat at 60.7M exactly. Hardware associativity
alone doesn't matter on 8GB/16GB either, same as the original 50MB null.

**laptop_sweep**: still 17/32, same row (100-read/8gb/S0) as last check - this run is long
(~4-5hr estimate), no new completion yet.

---

### hw_assoc_sweep_bigdb COMPLETE (12/12) (`2026-09-16 00:32 IST`)

Final row (16gb/assoc30) confirms: 16GB cycles flat at 60.7M across ALL six associativities
(1/4/8/15/16/30-way). 8GB likewise flat 51.7-51.8M. **Verdict: hardware associativity null result
holds on 8GB and 16GB, same as the original 50MB finding** - associativity alone doesn't move
performance at any DB size tested in this project so far.

---

### Hourly brief (`2026-09-16 01:22 IST`)

hw_assoc_sweep_bigdb: already complete (logged prior entry) - null holds on 8GB/16GB.

**laptop_sweep**: 18/32. New row: 100-read/8gb/S0 = 813.6M cycles (sanity: 813.6/1392.2=0.5844 ->
IPC=1.71, matches). Now on 100-read/8gb/1way. Still in the slow tier.

---

### Hourly brief (`2026-09-16 02:58 IST`)

**laptop_sweep**: 19/32. New row: 100-read/8gb/1way = 859.1M cycles (sanity: 859.1/1447.0=0.5938 ->
IPC=1.68, matches). Notable: 1way is now SLOWER than S0 (813.6M) at this scale - 1.056x, first
sign the cache's big win at 10/50 reads may not hold as read count grows further, worth watching
closely through 4way/8way and the 500-read tier. Now on 100-read/8gb/4way.

---

### Hourly brief (`2026-09-16 04:34 IST`) - 4-way also flips to slower at 100 reads/8GB

**laptop_sweep**: 20/32. New row: 100-read/8gb/4way = 839.1M cycles (sanity: 839.1/1453.0=0.5775 ->
IPC=1.73, matches). **4-way is now ALSO slower than S0 (813.6M)** - 1.031x (+3.1%), following 1-way's
+5.6%. This matters because 4-way was the best/winning width everywhere else in this project (small
DB, large DB, every prior scale). At 100 reads on the 8GB DB, EVERY width tested so far loses to no
cache - the large-DB win from 10/50 reads has fully reversed by 100 reads, mirroring what happened on
the small DB between 50 and 2000 reads. Now on 100-read/8gb/8way - expect the same pattern to hold,
watching to confirm.
