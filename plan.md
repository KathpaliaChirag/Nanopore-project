# Profiling Plan — Nanopore Pipeline (Dorado + Kraken-2)
## Goal: Produce a baseline profiling report for Kolin sir

> This document is a learning + execution guide. Read it top to bottom.
> Each tool section goes: what it is → how to set it up → what to run → what to note (beginner → intermediate → advanced).
> Everything ties back to one question: **where is the pipeline slow and why?**

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

### 0.1 WSL2 (for Kraken-2 profiling)

You already have WSL2. Open it and run:

```bash
# Check your Linux distro version
cat /etc/os-release

# Update packages
sudo apt update && sudo apt upgrade -y

# Install all tools you will need
sudo apt install -y \
    build-essential \
    git \
    gprof \
    valgrind \
    linux-tools-common \
    linux-tools-generic \
    cmake \
    wget \
    curl
```

**What to note (beginner):** just confirm each install succeeds. No errors = good.

**Check perf works:**
```bash
perf stat ls
```
If it prints hardware counters (cache-misses, instructions) — great, full perf works.
If it says "Permission denied" or "not supported" — only software events work (still useful).
**Note which case you are in.**

---

### 0.2 Nsight Systems (for Dorado profiling — Windows)

Nsight Systems is NVIDIA's free profiling tool for GPU programs.

**Download:** go to `developer.nvidia.com/nsight-systems` → download the Windows installer.
Install it. It creates two things:
- **Nsight Systems GUI** — the visual timeline viewer
- `nsys` — the command-line tool that actually does the recording

**Verify install:**
```powershell
nsys --version
```
Should print something like `NVIDIA Nsight Systems version 2024.x.x`.

**What to note (beginner):** the version number. Write it down for the report.

---

### 0.3 Get Kraken-2 source code (needed for gprof)

gprof requires the program to be compiled with a special flag (`-pg`). The pre-installed Kraken-2 binary does not have this. You need to build it yourself.

```bash
# In WSL2
cd ~
git clone https://github.com/DerrickWood/kraken2.git
cd kraken2

# Open the Makefile and find the CXXFLAGS line — add -pg to it
# It will look like: CXXFLAGS = -O2 -Wall
# Change to:         CXXFLAGS = -O2 -Wall -pg

nano Makefile   # or use any editor
# Find CXXFLAGS line, add -pg, save

# Build
./install_kraken2.sh ~/kraken2-build
```

**What to note (beginner):** whether the build succeeds. If errors appear, copy them — they are almost always a missing library that `apt install` fixes.

---

## Phase 1 — Dorado Profiling with Nsight Systems (Windows, GPU)

### What is Nsight Systems?

Nsight Systems records a **timeline** of everything that happens while your program runs:
- Which GPU kernels ran, for how long
- When data moved between CPU RAM and GPU memory
- What the CPU was doing at the same time

Think of it like a flight recorder for your GPU. After the run it gives you a visual timeline you can zoom into.

### Why does this matter for the project?

Dorado runs a neural network (Transformer) on the GPU. If you find that, say, 80% of time is spent in the attention kernels and only 5% in data transfer — then the bottleneck is compute, not I/O. That tells you exactly where a cache or optimization would help and where it would not.

---

### 1.1 Run Dorado under Nsight Systems

Open PowerShell (not WSL — this runs on Windows where the GPU is).

```powershell
# Set your paths
$nsys    = "C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.x.x\target-windows-x64\nsys.exe"
$dorado  = "C:\Users\chira\OneDrive\Desktop\Nanopore project\dorado\dorado-1.4.0-win64\bin\dorado.exe"
$pod5    = "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\pod5 data\FBE01990_24778b97_03e50f91_10.pod5"
$outdir  = "C:\Users\chira\OneDrive\Desktop\Nanopore project\Nanopore project\results\nsight"

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

This will:
1. Run Dorado fast mode (~5 min)
2. Record everything into `dorado_fast_profile.nsys-rep`
3. Print a summary table in the terminal when done

---

### 1.2 What to note — Beginner level

When the run finishes, the terminal prints a stats summary. **Write down these numbers:**

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

Open the `.nsys-rep` file in the Nsight Systems GUI (just double-click it).

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

In the GUI, right-click on the top kernel → "Analyze in Nsight Compute" (if available).

Or run Nsight Compute separately:
```powershell
$ncu = "C:\Program Files\NVIDIA Corporation\Nsight Compute 2024.x.x\ncu.exe"

& $ncu --target-processes all `
    --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,`
             dram__throughput.avg.pct_of_peak_sustained_elapsed `
    --output "$outdir\ncu_report" `
    -- & $dorado basecaller fast $pod5 --output-dir "$outdir\bam2"
```

**What to note:**
- `sm__throughput` — what % of peak GPU compute are you using? (100% = compute-bound, <50% = memory-bound)
- `dram__throughput` — what % of peak memory bandwidth are you using?
- These two numbers together tell you if Dorado on GTX 1650 is compute-bound or memory-bound

**Why this matters for Kolin sir's cache:**
- If memory-bound: a cache that reduces data movement will help a lot
- If compute-bound: need algorithmic changes, not just caching

---

## Phase 2 — Kraken-2 Profiling (WSL2, CPU)

Three tools, each giving different information. Run all three — they complement each other.

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

```bash
# In WSL2 — make sure you built Kraken-2 with -pg (Phase 0.3)

# Copy your FASTQ file into WSL2 (if not already there)
# From Windows path: /mnt/c/Users/chira/OneDrive/Desktop/...
cp "/mnt/c/Users/chira/OneDrive/Desktop/Nanopore project/Nanopore project/results/hac/barcode02.fastq" ~/

# Copy your ESKAPE database into WSL2
cp -r "/mnt/c/Users/chira/OneDrive/Desktop/Nanopore project/Nanopore project/eskape_db" ~/

# Run Kraken-2 (this generates gmon.out automatically because of -pg flag)
~/kraken2-build/kraken2 \
    --db ~/eskape_db \
    --report ~/kraken2_report.txt \
    ~/barcode02.fastq \
    > ~/kraken2_output.kraken

# Now generate the gprof report
gprof ~/kraken2-build/kraken2 gmon.out > ~/gprof_report.txt

# View it
less ~/gprof_report.txt
```

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

```bash
# In WSL2
# Warning: this runs 10-50x slower than normal — that is normal for Valgrind
# Use a small input (single barcode, not the full dataset) to keep it under 10 min

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

To see this:
```bash
cg_annotate --auto=yes ~/cachegrind.out > ~/cachegrind_annotated.txt
```

Find the inner loop of the k-mer lookup. It will show which line is causing cache misses.

**What to look for:**
- Is the miss happening on the hash table read (`table[hash % size]`)? — classic random access miss
- Is it happening on the k-mer string itself? — data layout issue
- If the hash table access is the culprit — this is exactly what blocking and caching fixes

**Cross-reference with gprof:** same function, high time in gprof + high cache misses in cachegrind = confirmed bottleneck. Two tools agree = strong evidence.

---

## Tool C — perf (Hardware Counters)

### What is perf?

perf reads the CPU's built-in performance counters — tiny hardware registers that count events like cache misses, branch mispredictions, and instructions per cycle.

Unlike Valgrind (which simulates), perf reads the actual hardware — so the numbers are from real execution, not a model. But it only works if WSL2 exposes those counters (not guaranteed).

### What it helps in the project

perf gives you wall-clock confirmed numbers. If Valgrind says "10M cache misses" and perf says "10M LLC misses" — you have two independent measurements agreeing. That is what makes a good report.

---

### C.1 Try running perf

```bash
# First test — does hardware perf work?
perf stat -e cache-misses,LLC-load-misses,instructions,cycles \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report ~/kraken2_report_perf.txt \
        ~/barcode02.fastq \
        > /dev/null
```

**Two possible outcomes:**

**Outcome A — perf works (hardware counters available):**
```
Performance counter stats:

    10,234,567    cache-misses
     8,123,456    LLC-load-misses
 1,234,567,890    instructions
   456,789,012    cycles

       3.456789 seconds time elapsed
```
→ Note all numbers. This is gold.

**Outcome B — hardware counters not available in WSL2:**
```
Error: The sys_perf_event_open() syscall returned with 1 (Operation not permitted)
```
→ Fall back to software events:
```bash
perf stat -e task-clock,page-faults,context-switches \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report ~/kraken2_report_perf.txt \
        ~/barcode02.fastq \
        > /dev/null
```
Software events always work. Note `task-clock` (CPU time) and `page-faults` (disk reads).

---

### C.2 What to note — Beginner level

Whichever outcome you get, note:
- Total wall-clock time (`seconds time elapsed`)
- If hardware counters work: `cache-misses` count and `LLC-load-misses` count
- If only software: `page-faults` count (high page faults = DB not fitting in RAM, causing disk reads)

---

### C.3 What to note — Intermediate level

If hardware perf works, calculate:

**Cache miss rate:**
```
LLC miss rate = LLC-load-misses / instructions × 100
```
A rate above 1% is notable. Above 5% is severe for a lookup-heavy program.

**Instructions per cycle (IPC):**
```
IPC = instructions / cycles
```
IPC < 1.0 = memory-bound (CPU is stalling waiting for data)
IPC > 2.0 = compute-bound (CPU is churning through calculations)

**Note both numbers — they directly classify the bottleneck.**

---

### C.4 What to note — Advanced level

Use `perf record` for line-level hotspots:
```bash
perf record -g \
    ~/kraken2-build/kraken2 \
        --db ~/eskape_db \
        --report /dev/null \
        ~/barcode02.fastq \
        > /dev/null

perf report
```

This opens an interactive view showing which source lines are hottest. Navigate with arrow keys, press `a` to annotate source.

**Note:** the top 3 source lines by sample count. These are where SIMD/blocking changes would land.

---

## Phase 3 — Making Sense of the Numbers

After running all tools, you will have:

| Number | Source | What it tells you |
|---|---|---|
| Top 3 hotspot functions | gprof flat profile | Where Kraken-2 spends its time |
| LLd miss rate (%) | cachegrind summary | How often it waits for RAM |
| Exact lines causing misses | cachegrind annotated | Where to apply blocking/caching |
| LLC-load-misses count | perf (if works) | Hardware confirmation of cache misses |
| IPC | perf | Memory-bound vs compute-bound verdict |
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
→ Signal-to-Base cache in CUDA shared memory is the right fix (avoids sending similar signals through the full pipeline)

**If Dorado is compute-bound (SM throughput > 80%):**
→ Need algorithmic changes — cache alone won't help much

---

## Phase 4 — The 2-Page Report Structure

When you have your numbers, structure the report like this:

```
Page 1: Kraken-2 CPU Profile
  - Setup: WSL2, Kraken-2 built from source, ESKAPE DB (650 MB), barcode02.fastq input
  - gprof results: top 5 functions + % time table
  - cachegrind results: LLd miss rate + top miss-causing functions
  - perf results: IPC, LLC miss count (or page-faults if hardware counters unavailable)
  - Verdict: memory-bound or compute-bound, with the numbers

Page 2: Dorado GPU Profile
  - Setup: Windows, GTX 1650 (4GB VRAM), fast mode, 104k reads
  - Nsight Systems: top 3 kernels + % time, memory transfer % 
  - SM throughput + DRAM throughput (from Nsight Compute if run)
  - Verdict: where the GPU time goes, is it memory or compute bound
  - Connection to cache: what % of time a cache could theoretically recover
```

---

## Quick Reference — Command Cheatsheet

```bash
# === WSL2 — Kraken-2 profiling ===

# gprof run + report
~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null
gprof ~/kraken2-build/kraken2 gmon.out > ~/gprof_report.txt

# cachegrind run + report
valgrind --tool=cachegrind --cachegrind-out-file=~/cg.out \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null
cg_annotate --auto=yes ~/cg.out > ~/cachegrind_report.txt

# perf (try hardware first, fall back to software)
perf stat -e cache-misses,LLC-load-misses,instructions,cycles \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null

# perf hotspots
perf record -g ~/kraken2-build/kraken2 --db ~/eskape_db --report ~/report.txt ~/barcode02.fastq > /dev/null
perf report
```

```powershell
# === Windows — Dorado profiling ===

# Nsight Systems (timeline recording)
nsys profile --output results\nsight\dorado_fast_profile --trace cuda,nvtx,osrt --stats true `
    -- dorado.exe basecaller fast "pod5 data\file.pod5" --output-dir results\nsight\bam

# Nsight Compute (per-kernel deep metrics)
ncu --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,dram__throughput.avg.pct_of_peak_sustained_elapsed `
    --output results\nsight\ncu_report `
    -- dorado.exe basecaller fast "pod5 data\file.pod5" --output-dir results\nsight\bam2
```

---

## What Order to Do This In

```
Day 1 (Setup):
  [ ] Install Nsight Systems on Windows — verify nsys --version works
  [ ] In WSL2: apt install build-essential valgrind linux-tools-generic
  [ ] Clone Kraken-2, edit Makefile to add -pg, build it
  [ ] Copy barcode02.fastq and eskape_db into WSL2 home directory
  [ ] Test: run plain kraken2 once to confirm it works before adding profiling

Day 2 (Dorado profiling):
  [ ] Run Dorado fast mode under nsys (takes ~5 min + overhead)
  [ ] Open .nsys-rep in GUI — note top kernels + memory transfer %
  [ ] Run Nsight Compute on top kernel — note SM throughput + DRAM throughput
  [ ] Write up Page 2 of the report from these numbers

Day 3 (Kraken-2 profiling):
  [ ] Run gprof version of kraken2 — note top 5 functions
  [ ] Run cachegrind — note LLd miss rate + top miss functions (will be slow, ~20 min)
  [ ] Try perf stat — note whether hardware counters work or not, collect whatever works
  [ ] Write up Page 1 of the report from these numbers

Day 4 (Report):
  [ ] Combine into 2-page report
  [ ] Push to GitHub repo
  [ ] Share with Kolin sir
```
