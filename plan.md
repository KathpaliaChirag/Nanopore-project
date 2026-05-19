# Profiling Plan — Nanopore Pipeline (Dorado + Kraken-2)
## Goal: Produce a baseline profiling report for Kolin sir

> This document is a learning + execution guide. Read it top to bottom.
> Each tool section goes: what it is → how to set it up → what to run → what to note (beginner → intermediate → advanced).
> Everything ties back to one question: **where is the pipeline slow and why?**
>
> At every step, instructions are split:
> - **Windows/WSL2** — for Chirag's setup
> - **Native Linux** — for anyone running Ubuntu/Debian directly (Rishabh, Rohit, or lab server)

---

## The Big Picture (read this first)

Before touching any tool, understand what you are trying to find out.

The pipeline is:
```
POD-5 file
    ↓  Dorado (GPU) — basecalling
BAM / FASTQ
    ↓  Kraken-2 (CPU) — species identification
Species report
```

Both steps are slow. You do not know *why* yet. There are two possible reasons for any program being slow:

1. **Compute-bound** — the CPU/GPU is doing too many calculations. Fix: SIMD, better algorithms.
2. **Memory-bound** — the CPU/GPU is waiting for data to arrive from RAM or disk. Fix: caching, better data layout.

The profiling tools tell you which one it is. You cannot guess — the answer is almost always surprising.

**Your job in this plan:** run the tools, collect the numbers, understand what they mean. That is the 2-page report Kolin sir wants.

---

## Phase 0 — Setup (do this once)

### 0.1 Linux environment setup

**If Windows/WSL2:**
Open WSL2 (search "Ubuntu" or "WSL" in Start menu) and run:
```bash
# Confirm you are inside WSL2 (not PowerShell)
uname -a   # should print "Linux"

cat /etc/os-release   # shows your distro

# Update packages
sudo apt update && sudo apt upgrade -y

# Install all tools you will need
sudo apt install -y \
    build-essential \
    git \
    binutils \
    valgrind \
    linux-tools-common \
    linux-tools-generic \
    cmake \
    wget \
    curl
```

**If native Linux (Ubuntu/Debian):**
Open a terminal and run the exact same commands — no difference here.
```bash
uname -a   # confirm you are on Linux

sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    build-essential \
    git \
    binutils \
    valgrind \
    linux-tools-common \
    linux-tools-$(uname -r) \
    cmake \
    wget \
    curl
```
> Note: `linux-tools-$(uname -r)` installs the perf version matched to your exact kernel — more reliable than `linux-tools-generic` on native Linux.

**What to note (beginner):** just confirm each install succeeds with no errors.

**Check perf works (both WSL2 and Linux):**
```bash
perf stat ls
```

**If Windows/WSL2:** hardware counters often blocked by the hypervisor. You may see:
```
Error: The sys_perf_event_open() syscall returned with 1 (Operation not permitted)
```
→ This is normal for WSL2. Software events still work. Note this happened.

**If native Linux:** hardware counters almost always work. If you see permission denied, fix with:
```bash
sudo sysctl kernel.perf_event_paranoid=1
```
Then re-run `perf stat ls` — should now show cache-misses and instructions counts.

**Note which case you are in — this determines what you can collect in Tool C.**

---

### 0.2 Nsight Systems (for Dorado GPU profiling)

Nsight Systems is NVIDIA's free profiling tool for GPU programs. It records a full timeline of GPU kernels, memory transfers, and CPU activity.

**If Windows/WSL2:**
- Download the **Windows** installer from `developer.nvidia.com/nsight-systems`
- Install on Windows (not inside WSL2 — the GPU is on the Windows side)
- After install, verify in PowerShell:
```powershell
nsys --version
# Should print: NVIDIA Nsight Systems version 2024.x.x
```
- You will also get the **Nsight Systems GUI** — a visual timeline viewer. It opens `.nsys-rep` files.

**If native Linux:**
- Download the **Linux** installer (`.deb` or `.run`) from `developer.nvidia.com/nsight-systems`
- Install with:
```bash
# If .deb package
sudo dpkg -i NsightSystems-linux-*.deb

# If .run package
chmod +x NsightSystems-linux-*.run
sudo ./NsightSystems-linux-*.run

# Verify
nsys --version
```
- The GUI is included — launch with `nsys-ui` from terminal or find it in your app launcher.
- Dorado runs natively on Linux, so you can wrap it directly (no WSL needed).

**What to note (beginner):** the version number printed by `nsys --version`. Write it down for the report.

---

### 0.3 Get Kraken-2 source code (needed for gprof)

gprof requires the program to be compiled with a special flag (`-pg`). Pre-installed Kraken-2 binaries do not have this. You need to build it from source.

**If Windows/WSL2:**
```bash
# Run inside WSL2
cd ~
git clone https://github.com/DerrickWood/kraken2.git
cd kraken2

# Edit the Makefile — find the CXXFLAGS line and add -pg
# It currently looks like: CXXFLAGS = -O2 -Wall
# Change it to:            CXXFLAGS = -O2 -Wall -pg
nano Makefile
# (Ctrl+W to search for "CXXFLAGS", add -pg, Ctrl+X then Y to save)

# Build
./install_kraken2.sh ~/kraken2-build
```

**If native Linux:**
Exact same steps — no difference. Just run in your regular terminal:
```bash
cd ~
git clone https://github.com/DerrickWood/kraken2.git
cd kraken2
nano Makefile   # add -pg to CXXFLAGS line
./install_kraken2.sh ~/kraken2-build
```

**What to note (beginner):** whether the build succeeds. If errors appear, copy them — they are almost always a missing library that `apt install` fixes (e.g., `sudo apt install zlib1g-dev`).

---

## Phase 1 — Dorado Profiling with Nsight Systems (GPU)

### What is Nsight Systems?

Nsight Systems records a **timeline** of everything that happens while your program runs:
- Which GPU kernels ran, for how long
- When data moved between CPU RAM and GPU memory
- What the CPU was doing at the same time

Think of it like a flight recorder for your GPU. After the run it gives you a visual timeline you can zoom into.

### Why does this matter for the project?

Dorado runs a neural network (Transformer) on the GPU. If you find that 80% of time is in attention kernels and only 5% in data transfer — the bottleneck is compute, not I/O. That tells you exactly where a cache would help and where it would not.

---

### 1.1 Run Dorado under Nsight Systems

**If Windows/WSL2:**
Open PowerShell (not WSL — Dorado uses the Windows GPU directly):
```powershell
# Set your paths
$nsys   = "C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.x.x\target-windows-x64\nsys.exe"
$dorado = "C:\Users\chira\OneDrive\Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe"
$pod5   = "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\pod5 data\FBE01990_24778b97_03e50f91_10.pod5"
$outdir = "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\results\nsight"

# Create output folder
New-Item -ItemType Directory -Force $outdir

# Run Dorado wrapped in nsys
& $nsys profile `
    --output "$outdir\dorado_fast_profile" `
    --trace cuda,nvtx,osrt `
    --stats true `
    -- `
    & $dorado basecaller fast $pod5 --output-dir "$outdir\bam" --batchsize 64
```

**If native Linux:**
Open a terminal. Dorado has a Linux binary — download the Linux version from `cdn.oxfordnanoportal.com` if you have not already.
```bash
# Set your paths
NSYS="nsys"   # nsys is on PATH after install
DORADO=~/dorado/bin/dorado   # adjust to where you installed it
POD5=~/data/FBE01990_24778b97_03e50f91_10.pod5   # adjust to your pod5 path
OUTDIR=~/results/nsight

mkdir -p $OUTDIR

# Run Dorado wrapped in nsys
nsys profile \
    --output $OUTDIR/dorado_fast_profile \
    --trace cuda,nvtx,osrt \
    --stats true \
    -- \
    $DORADO basecaller fast $POD5 --output-dir $OUTDIR/bam --batchsize 64
```

Both produce the same output: `dorado_fast_profile.nsys-rep` + a terminal stats summary.

This will:
1. Run Dorado fast mode (~5 min)
2. Record everything into `dorado_fast_profile.nsys-rep`
3. Print a summary table in the terminal when done

---

### 1.2 What to note — Beginner level

When the run finishes, the terminal prints a stats summary (same on both Windows and Linux):
```
Time (%)  Total Time (ns)  Instances  Avg (ns)   Name
--------  ---------------  ---------  ---------  ----
   xx.x%   xxxxxxxxxx           xxx   xxxxxxxxx  <kernel name>
   ...
```

**Note:**
- The top 3 kernels by time percentage — what are their names?
- Total runtime of the Dorado run
- How much time is CUDA kernel execution vs CPU time

**What these mean at beginner level:**
- High % on one kernel = that kernel is the bottleneck
- Many small kernels = overhead from launching too many small GPU operations

---

### 1.3 What to note — Intermediate level

Open the `.nsys-rep` file in the Nsight Systems GUI.

**If Windows/WSL2:** double-click the `.nsys-rep` file in Explorer — Nsight Systems GUI opens it.

**If native Linux:** run `nsys-ui` from terminal, then File → Open → select the `.nsys-rep` file.

You will see a timeline with multiple rows. Look at:

**Row: CUDA HW (your GPU)**
- Green blocks = GPU kernels running
- Gaps between blocks = GPU is idle (bad — CPU is not feeding it fast enough)
- **Note: what % of time is the GPU actually doing work vs sitting idle?**

**Row: Memory transfers (DtoH / HtoD)**
- DtoH = Device to Host = GPU → CPU RAM
- HtoD = Host to Device = CPU RAM → GPU
- **Note: how much time is spent on memory transfers vs actual computation?**
- If memory transfer time > 20% of total — memory bandwidth is a bottleneck

**Zoom into a single kernel (click on it):**
- Duration: how long did one call take?
- Grid/Block size: how many GPU threads were launched?
- **Note: the name of the longest single kernel**

---

### 1.4 What to note — Advanced level

Run Nsight Compute to get per-kernel throughput metrics.

**If Windows/WSL2:**
```powershell
$ncu    = "C:\Program Files\NVIDIA Corporation\Nsight Compute 2024.x.x\ncu.exe"
$dorado = "C:\Users\chira\OneDrive\Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe"
$pod5   = "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\pod5 data\FBE01990_24778b97_03e50f91_10.pod5"
$outdir = "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\results\nsight"

& $ncu --target-processes all `
    --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,`
             dram__throughput.avg.pct_of_peak_sustained_elapsed `
    --output "$outdir\ncu_report" `
    -- & $dorado basecaller fast $pod5 --output-dir "$outdir\bam2"
```

**If native Linux:**
```bash
ncu --target-processes all \
    --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,\
dram__throughput.avg.pct_of_peak_sustained_elapsed \
    --output ~/results/nsight/ncu_report \
    -- $DORADO basecaller fast $POD5 --output-dir ~/results/nsight/bam2
```

**What to note:**
- `sm__throughput` — what % of peak GPU compute are you using? (100% = compute-bound, <50% = memory-bound)
- `dram__throughput` — what % of peak memory bandwidth are you using?
- These two numbers together tell you if Dorado on your GPU is compute-bound or memory-bound

**Why this matters for Kolin sir's cache:**
- If memory-bound: a cache that reduces data movement will help a lot
- If compute-bound: need algorithmic changes, not just caching

---

## Phase 2 — Kraken-2 Profiling (CPU)

Three tools, each giving different information. Run all three — they complement each other.

**If Windows/WSL2:** run everything inside WSL2.
**If native Linux:** run everything directly in your terminal — no difference in commands.

The only difference is how you get your data files:

**If Windows/WSL2 — copy files from Windows into WSL2:**
```bash
# FASTQ from Dorado output (adjust path to wherever yours is)
cp "/mnt/c/Users/chira/OneDrive/Desktop/Nanopore project/Nanopore project/results/hac/barcode02.fastq" ~/

# ESKAPE database
cp -r "/mnt/c/Users/chira/OneDrive/Desktop/Nanopore project/Nanopore project/eskape_db" ~/
```

**If native Linux — files are already local:**
```bash
# Just set variables pointing to where your files are
FASTQ=~/data/barcode02.fastq      # adjust to your path
DB=~/data/eskape_db               # adjust to your path
```

All commands below use `~/barcode02.fastq` and `~/eskape_db` — adjust if your paths differ.

---

## Tool A — gprof (Call Graph Profiling)

### What is gprof?

gprof tells you: **which functions in Kraken-2 take the most CPU time.**

Think of it as a stopwatch attached to every function. After the run it prints a table like:
```
  %   cumulative   self              self     total
 time   seconds   seconds    calls   ms/call  ms/call  name
 60.00      3.60     3.60  1234567     0.00     0.00  lookup_kmer_in_db
 20.00      4.80     1.20   104478     0.01     0.01  hash_kmer
 ...
```

That tells you: 60% of Kraken-2's time is in `lookup_kmer_in_db`. That is where you focus.

### What it helps in the project

If `lookup_kmer_in_db` is the hotspot — that is exactly where Kolin sir's Hot-K-mer LRU cache sits. The gprof output is the justification for building that cache.

---

### A.1 Run gprof

**If Windows/WSL2 — run inside WSL2:**
```bash
# Make sure you built Kraken-2 with -pg (Phase 0.3)
# Make sure barcode02.fastq and eskape_db are copied to ~/ (see Phase 2 intro above)

# Run Kraken-2 — the -pg build automatically generates gmon.out
~/kraken2-build/kraken2 \
    --db ~/eskape_db \
    --report ~/kraken2_report.txt \
    ~/barcode02.fastq \
    > ~/kraken2_output.kraken

# Generate the gprof report
gprof ~/kraken2-build/kraken2 gmon.out > ~/gprof_report.txt

# View it
less ~/gprof_report.txt
```

**If native Linux — same commands, just run in your terminal:**
```bash
# Same — just make sure paths point to your files
~/kraken2-build/kraken2 \
    --db ~/eskape_db \
    --report ~/kraken2_report.txt \
    ~/barcode02.fastq \
    > ~/kraken2_output.kraken

gprof ~/kraken2-build/kraken2 gmon.out > ~/gprof_report.txt
less ~/gprof_report.txt
```

No difference between WSL2 and Linux for this tool.

---

### A.2 What to note — Beginner level

Look at the **Flat Profile** section at the top of `gprof_report.txt`:
```
Flat profile:
Each sample counts as 0.01 seconds.
  %   cumulative   self     ...   name
 time   seconds   seconds  ...
 XX.X      X.XX     X.XX   ...   function_name
```

**Note:**
- Top 5 functions by % time
- The total runtime (`cumulative seconds` on the last line)
- What is the single biggest function?

---

### A.3 What to note — Intermediate level

Look at the **Call Graph** section below the flat profile.

It shows for each function: who called it, how many times, how long each call took.
```
index  % time   self  children  called  name
                0.36    2.89  1234567  lookup_kmer_in_db [1]
                0.00    0.00  1234567      hash_kmer [3]
```

**Note:**
- `self` = time spent inside the function itself
- `children` = time spent in functions it called
- `called` = number of times it was called
- **If a function has very high `called` count and even small `self` time — it is a hot loop**

**Calculate:** `self_seconds / called` = average time per call. If this is tiny (microseconds) but called millions of times — that inner loop is where SIMD would help.

---

### A.4 What to note — Advanced level

Find the k-mer lookup function in the call graph. Note:
- How many times is it called? (should be ~35 × number of reads × avg read length)
- What is `self` time vs `children` time?
- Is the hash function itself a significant fraction?

Cross-reference with cachegrind (Tool B) — if the lookup function has high cache miss rate AND appears at top of gprof — you have confirmed the bottleneck with two independent tools. That is strong evidence for the report.

---

## Tool B — Valgrind / Cachegrind (Cache Miss Analysis)

### What is Cachegrind?

Cachegrind simulates the CPU cache and counts every cache miss your program causes.

A **cache miss** happens when the CPU needs data that is not in the fast L1/L2/L3 cache — it has to go to slow RAM. For Kraken-2, looking up a k-mer in a 180 GB hash table causes massive cache misses because the data is scattered randomly across memory.

Think of it like this: L1 cache access = 1 ns. RAM access = 100 ns. If Kraken-2 misses cache on every k-mer lookup, it is 100x slower than it could be.

### What it helps in the project

Cachegrind gives you the **exact cache miss count per function**. If `lookup_kmer_in_db` has 10 million LLC (Last Level Cache) misses — that number goes directly into the profiling report and justifies building a cache.

---

### B.1 Run Cachegrind

**If Windows/WSL2 — run inside WSL2:**
```bash
# Warning: Valgrind runs 10-50x slower than normal — that is expected
# Use a single barcode FASTQ (small input) to keep runtime under 10-15 min

valgrind \
    --tool=cachegrind \
    --cachegrind-out-file=~/cachegrind.out \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report ~/kraken2_report_cg.txt \
        ~/barcode02.fastq \
        > ~/kraken2_output_cg.kraken

# Generate the human-readable report
cg_annotate ~/cachegrind.out > ~/cachegrind_report.txt

# View it
less ~/cachegrind_report.txt
```

**If native Linux — same commands, same output:**
```bash
valgrind \
    --tool=cachegrind \
    --cachegrind-out-file=~/cachegrind.out \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report ~/kraken2_report_cg.txt \
        ~/barcode02.fastq \
        > ~/kraken2_output_cg.kraken

cg_annotate ~/cachegrind.out > ~/cachegrind_report.txt
less ~/cachegrind_report.txt
```

No difference between WSL2 and Linux for this tool.

---

### B.2 What to note — Beginner level

At the top of `cachegrind_report.txt` you will see a summary:
```
I   refs:      xxx,xxx,xxx        (instructions executed)
I1  misses:    xxx,xxx            (L1 instruction cache misses)
LLi misses:    xxx,xxx            (Last-level instruction cache misses)
D   refs:      xxx,xxx,xxx        (data reads+writes)
D1  misses:    xxx,xxx,xxx        (L1 data cache misses)
LLd misses:    xxx,xxx,xxx        (Last-level data cache misses — THIS IS THE KEY NUMBER)
LL  misses:    xxx,xxx,xxx        (total last-level cache misses)
```

**Note:**
- `LLd misses` — Last Level Data cache misses. This is the most important number.
- `LLd miss rate` = LLd misses / D refs × 100%. Write this down.
- A miss rate above 5% is high. Above 20% is severe.

---

### B.3 What to note — Intermediate level

Below the summary, cachegrind lists miss counts **per function**, annotated with source lines.
```
         Ir    I1mr   ILmr    Dr    D1mr   DLmr    Dw    D1mw   DLmw   file:function
xxx,xxx,xxx       0      0   xxx   x,xxx  x,xxx     xx      0      0   kraken2.cpp:lookup_kmer
```

**Note:**
- `DLmr` — data reads that missed the last-level cache
- `DLmw` — data writes that missed the last-level cache
- Find which function has the highest `DLmr` count
- **That function is where you have a memory access pattern problem**

---

### B.4 What to note — Advanced level

Cachegrind also shows **line-level annotation** — it points to the exact line of code causing misses.

**Both WSL2 and Linux — same command:**
```bash
cg_annotate --auto=yes ~/cachegrind.out > ~/cachegrind_annotated.txt
less ~/cachegrind_annotated.txt
```

Find the inner loop of the k-mer lookup. It will show which line is causing cache misses.

**What to look for:**
- Is the miss happening on the hash table read (`table[hash % size]`)? — classic random access miss
- Is it happening on the k-mer string itself? — data layout issue
- If the hash table access is the culprit — this is exactly what blocking and caching fixes

**Cross-reference with gprof:** same function, high time in gprof + high cache misses in cachegrind = confirmed bottleneck.

---

## Tool C — perf (Hardware Counters)

### What is perf?

perf reads the CPU's built-in hardware performance counters — tiny registers that count events like cache misses, branch mispredictions, and instructions per cycle.

Unlike Valgrind (which simulates the cache), perf reads the actual hardware — real numbers from real execution.

**Key difference between WSL2 and Linux here:**
- **Native Linux:** hardware counters almost always work — you get the full picture.
- **Windows/WSL2:** hardware counters are often blocked by the Hyper-V hypervisor — you may only get software events. Still useful, just less complete.

---

### C.1 Try running perf

**Both WSL2 and Linux — same command to test:**
```bash
perf stat -e cache-misses,LLC-load-misses,instructions,cycles \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report ~/kraken2_report_perf.txt \
        ~/barcode02.fastq \
        > /dev/null
```

**Outcome A — hardware counters work (likely on native Linux, possible on WSL2):**
```
Performance counter stats:

    10,234,567    cache-misses
     8,123,456    LLC-load-misses
 1,234,567,890    instructions
   456,789,012    cycles

       3.456789 seconds time elapsed
```
→ Note all numbers. This is the best possible output.

**Outcome B — hardware counters blocked (common on WSL2):**
```
Error: The sys_perf_event_open() syscall returned with 1 (Operation not permitted)
```
→ Fall back to software events — these always work on both WSL2 and Linux:
```bash
perf stat -e task-clock,page-faults,context-switches \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report ~/kraken2_report_perf.txt \
        ~/barcode02.fastq \
        > /dev/null
```
`task-clock` = CPU time used. `page-faults` = how many times data had to be loaded from disk.

**If native Linux and still getting permission denied:**
```bash
# One-time fix — lower the paranoia level
sudo sysctl kernel.perf_event_paranoid=1
# Then retry the perf stat command above
```

---

### C.2 What to note — Beginner level

Whichever outcome you get, note:
- Total wall-clock time (`seconds time elapsed`)
- If hardware counters work: `cache-misses` and `LLC-load-misses` counts
- If only software events: `page-faults` count (high page faults = DB not fitting in RAM, disk reads happening)
- **Note whether you got hardware or software events** — this goes in the report as a setup detail

---

### C.3 What to note — Intermediate level

If hardware perf works (native Linux most likely), calculate:

**Cache miss rate:**
```
LLC miss rate = LLC-load-misses / instructions × 100
```
Above 1% is notable. Above 5% is severe for a lookup-heavy program like Kraken-2.

**Instructions per cycle (IPC):**
```
IPC = instructions / cycles
```
IPC < 1.0 = memory-bound (CPU is stalling waiting for data to arrive from RAM)
IPC > 2.0 = compute-bound (CPU is doing lots of arithmetic)

**Note both numbers — they directly classify the bottleneck.**

---

### C.4 What to note — Advanced level

Use `perf record` for line-level hotspots.

**Both WSL2 and Linux — same command (works better on native Linux):**
```bash
perf record -g \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report /dev/null \
        ~/barcode02.fastq \
        > /dev/null

perf report
```

This opens an interactive view. Navigate with arrow keys, press `a` to annotate source lines.

**Note:** the top 3 source lines by sample count. These are where SIMD/blocking changes would land.

**If on WSL2 and `perf record` fails:** skip this step — cachegrind already gives line-level data via `cg_annotate --auto=yes`.

---

## Phase 3 — Making Sense of the Numbers

After running all tools, you will have:

| Number | Source | What it tells you |
|---|---|---|
| Top 3 hotspot functions | gprof flat profile | Where Kraken-2 spends its time |
| LLd miss rate (%) | cachegrind summary | How often it waits for RAM |
| Exact lines causing misses | cachegrind annotated | Where to apply blocking/caching |
| LLC-load-misses count | perf (if hardware works) | Hardware confirmation of cache misses |
| IPC | perf (if hardware works) | Memory-bound vs compute-bound verdict |
| Top GPU kernels (%) | Nsight Systems | Where Dorado spends GPU time |
| Memory transfer % | Nsight Systems | Is GPU starved of data? |
| SM throughput % | Nsight Compute | Is GPU at compute capacity? |

---

### How to read the verdict

**If Kraken-2 is memory-bound (IPC < 1, LLd miss rate > 10%):**
→ Kolin sir's Hot-K-mer LRU cache is the right fix
→ Reducing DB size (Bloom filters) also helps
→ Cache blocking on hash table access is worth trying

**If Kraken-2 is compute-bound (IPC > 2, low miss rate):**
→ SIMD / AVX2 on the hash function is the right fix
→ Caching helps less

**If Dorado is memory-bound (SM throughput < 50%, high DtoH/HtoD time):**
→ Signal-to-Base cache in CUDA shared memory is the right fix

**If Dorado is compute-bound (SM throughput > 80%):**
→ Need algorithmic changes — cache alone won't help much

---

## Phase 4 — The 2-Page Report Structure

```
Page 1: Kraken-2 CPU Profile
  - Setup: WSL2 or Linux, Kraken-2 built from source with -pg,
           ESKAPE DB (650 MB), barcode02.fastq input, note if perf gave hardware or software events
  - gprof results: top 5 functions + % time table
  - cachegrind results: LLd miss rate + top miss-causing functions
  - perf results: IPC + LLC miss count (or page-faults if hardware counters unavailable)
  - Verdict: memory-bound or compute-bound, with the numbers

Page 2: Dorado GPU Profile
  - Setup: Windows or Linux, GPU model + VRAM, fast mode, 104k reads
  - Nsight Systems: top 3 kernels + % time, memory transfer %
  - SM throughput + DRAM throughput (from Nsight Compute if run)
  - Verdict: where GPU time goes, memory or compute bound
  - Connection to cache: what % of time a cache could theoretically recover
```

---

## Quick Reference — Command Cheatsheet

```bash
# === Kraken-2 profiling (WSL2 or native Linux — same commands) ===

# gprof
~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null
gprof ~/kraken2-build/kraken2 gmon.out > ~/gprof_report.txt

# cachegrind
valgrind --tool=cachegrind --cachegrind-out-file=~/cg.out \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null
cg_annotate --auto=yes ~/cg.out > ~/cachegrind_report.txt

# perf — try hardware first
perf stat -e cache-misses,LLC-load-misses,instructions,cycles \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null

# perf — fallback software events (always works)
perf stat -e task-clock,page-faults,context-switches \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null

# perf hotspots (native Linux recommended)
perf record -g ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null
perf report
```

```powershell
# === Dorado profiling — Windows/WSL2 (run in PowerShell) ===

nsys profile --output results\nsight\dorado_fast_profile --trace cuda,nvtx,osrt --stats true `
    -- dorado.exe basecaller fast "pod5 data\file.pod5" --output-dir results\nsight\bam

ncu --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,dram__throughput.avg.pct_of_peak_sustained_elapsed `
    --output results\nsight\ncu_report `
    -- dorado.exe basecaller fast "pod5 data\file.pod5" --output-dir results\nsight\bam2
```

```bash
# === Dorado profiling — native Linux (run in terminal) ===

nsys profile \
    --output ~/results/nsight/dorado_fast_profile \
    --trace cuda,nvtx,osrt \
    --stats true \
    -- ~/dorado/bin/dorado basecaller fast ~/data/file.pod5 --output-dir ~/results/nsight/bam

ncu \
    --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,dram__throughput.avg.pct_of_peak_sustained_elapsed \
    --output ~/results/nsight/ncu_report \
    -- ~/dorado/bin/dorado basecaller fast ~/data/file.pod5 --output-dir ~/results/nsight/bam2
```

---

## What Order to Do This In

```
Day 1 (Setup):
  [ ] Windows/WSL2: install Nsight Systems on Windows, verify nsys --version
      Native Linux: download and install Nsight Systems Linux package, verify nsys --version
  [ ] WSL2: apt install build-essential valgrind linux-tools-common linux-tools-generic
      Native Linux: apt install build-essential valgrind linux-tools-common linux-tools-$(uname -r)
  [ ] Clone Kraken-2, edit Makefile to add -pg to CXXFLAGS, build with install_kraken2.sh
  [ ] WSL2: copy barcode02.fastq and eskape_db from Windows into WSL2 home directory
      Native Linux: confirm barcode02.fastq and eskape_db are accessible, note their paths
  [ ] Test: run kraken2 once WITHOUT profiling to confirm it works before adding tools
  [ ] Test perf: run "perf stat ls" — note whether hardware counters work or not

Day 2 (Dorado profiling):
  [ ] Run Dorado fast mode under nsys (~5 min + overhead)
  [ ] Open .nsys-rep in Nsight Systems GUI — note top kernels + memory transfer %
  [ ] Run Nsight Compute on the top kernel — note SM throughput + DRAM throughput
  [ ] Write up Page 2 of the report from these numbers

Day 3 (Kraken-2 profiling):
  [ ] Run gprof version of kraken2 — note top 5 functions + % time
  [ ] Run cachegrind — note LLd miss rate + top miss functions (will take ~20 min — normal)
  [ ] Run perf stat (hardware if available, software fallback) — note IPC and miss counts
  [ ] Write up Page 1 of the report from these numbers

Day 4 (Report):
  [ ] Combine into 2-page report
  [ ] Push to GitHub repo
  [ ] Share with Kolin sir
```
