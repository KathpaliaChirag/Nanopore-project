# Summer Report: Profiling and Optimising the ESKAPE Nanopore Pipeline

Chirag Kathpalia, MTech CSE, IIT Delhi
with Chirag Suthar (Lab Desktop thread-scaling data)
under the guidance of Prof. Kolin Paul
summer 2026

---

## why this report exists

i already walked Kolin sir through this work in slide form (`presentations/june.pptx`, 26 slides). this is not that deck again. its job is the *why* behind the numbers, in prose, with honest bookkeeping of what's measured versus what's still a projection. a slide can show a bar chart. it can't easily show four independent tools converging on one root cause, or admit a projected number hasn't been run yet. that's what this is for.

the project: take a clinical nanopore sequencing pipeline for identifying **ESKAPE pathogens** (six antibiotic-resistant bacteria: *E. faecium, S. aureus, K. pneumoniae, A. baumannii, P. aeruginosa, E. cloacae*) from patient samples, and find where it's slow and why. two tools do the heavy lifting: **dorado**, a GPU neural network that turns raw nanopore electrical signal into DNA base calls, and **kraken2**, a CPU tool that matches those reads against a reference database to identify species. both got profiled to the hardware counter level on **Luna**, a Dell server with 96 CPU cores and two NVIDIA L40S GPUs.

## the pipeline, and where the two bottlenecks sit

```
patient sample --> flow cell --> raw signal (pod5 file, gigabytes)
                                        |
                                dorado (GPU, neural network basecaller)
                                        |
                            DNA reads (ATGC letters, one file per patient)
                                        |
                        kraken2 (CPU, k-mer hash table lookup)
                                        |
                        species report: "patient has X, Y, Z"
```

dorado and kraken2 turn out to have almost opposite bottlenecks. dorado is GPU-bound: the CPU spends 96 to 99% of its time waiting on the GPU, no matter which model runs. kraken2 is memory-bound: the CPU is fast enough, but one specific function spends its whole life waiting on trips to main memory. both conclusions come from hardware counters, not guesses.

## dorado: the gpu basecaller (measured, complete)

dorado ships three model sizes: **fast**, **hac** (high accuracy), and **sup** (super accuracy). i profiled all three on Luna's L40S GPU using Nsight Systems, which traces every GPU kernel call and every CPU-to-GPU synchronization point. the headline result is in Table 1.

**Table 1. dorado wall time and GPU speedup, Luna L40S vs Luna CPU (96 cores), same input, 104,918 reads**

| model | architecture | GPU wall time | CPU wall time | GPU speedup |
|---|---|---|---|---|
| fast | LSTM (small) | 33.9s | 9m 40s | 28.6x |
| hac | LSTM (large) | 55.0s | 43m 26s | 107x |
| sup | Transformer, FP8 | 4m 26s | ~9 days (estimated) | ~3,000x (estimated) |

the fast-to-hac-to-sup jump isn't just "bigger model, slower." each model runs on a genuinely different hardware path. fast and hac are LSTM-based (a type of recurrent neural network), dominated by matrix multiply (GEMM) and LSTM kernels. sup is architecturally a **Transformer**, the same family as GPT, using **FP8**, an 8-bit floating point format Ada Lovelace GPUs accelerate natively. that one fact explains the ~3,000x number: no CPU architecture, including Luna's Xeon with its AMX matrix extensions, has native FP8 support. on CPU, dorado falls back to FP32 for every FP8 op, slower per-operation and roughly double the memory traffic, and the GPU's fused kernels (matmul plus activation in one pass) split into separate unfused CPU ops. sup pays a "no GPU" tax and a "no native FP8" tax at once, which is why its CPU penalty is an order of magnitude worse than fast or hac's.

the CPU-sync number matters as much as the speedup: across all three models, 96 to 99% of CUDA API time is `cudaStreamSynchronize`, the CPU idle and waiting on the GPU almost the entire run. dorado is entirely GPU-paced, which rules out a category of optimisation before it starts, there's no CPU-side slack to reclaim. any real speedup has to come from the GPU doing less work per read.

one honest caveat: the sup CPU number and Orion's hac/sup numbers are estimates, not completed runs. sup on CPU was cancelled after 12 minutes with a progress bar showing roughly 9 days remaining; Orion's hac estimate came from a progress bar reading before an SSH session dropped. the order of magnitude is the point, not the exact hour count, but these are not measured wall-clock numbers the way the GPU numbers are.

clinically, the accuracy gap is what decides which model you'd use: fast to hac buys 13 percentage points of accuracy for about 5x the compute cost, and resolves species mixtures fast alone gets wrong. hac to sup buys 1.3 more points for 6x further cost, and doesn't change any species calls in this dataset. **hac is the clinical sweet spot** - Luna's GPU makes every option fast enough that the choice is now about accuracy, not feasibility.

## kraken2: finding the real bottleneck

kraken2 looks up each DNA read's constituent k-mers (short subsequences) against a hash table built from reference genomes. the natural guess is "the hash table is big, so the CPU is doing a lot of work." that guess is wrong, and proving it wrong took four separate tools that all land on the same answer.

`CompactHashTable::Get()`, the function that does the hash table lookup, executes **0.65% of all instructions** in the program, and is responsible for **96.24% of all last-level cache read misses** (measured with cachegrind, a cache simulator, against a 7.6 GB reference database). this one function is almost never called, in instruction-count terms, and almost everything it does is a trip to main memory the CPU has to sit and wait for.

three more tools independently confirm the same story, which is why i trust this isn't a measurement artifact (Table 2).

**Table 2. four independent tools, one root cause**

| tool | what it measures | finding |
|---|---|---|
| cachegrind | per-function cache miss attribution | `Get()` = 96.24% of LLC read misses, 0.65% of instructions |
| uncore IMC counters | DRAM bandwidth actually used | 5 to 11% of DDR5's peak bandwidth, across every database size tested |
| NUMA pinning | cost of remote vs local memory | pinning to the local memory node cuts DRAM stall cycles by 47% |
| TMA (top-down microarchitecture analysis) | where CPU pipeline slots go | only 26.9% of pipeline slots do useful work at default settings |

the DRAM bandwidth number rules out the obvious fix. if kraken2 were bandwidth-bound, a smaller database would help, since it'd move less data. it isn't: the database sits 94% below the memory bus's peak throughput at every size tested. the problem is **latency**, not bandwidth. each hash table probe is a roughly 100-nanosecond round trip to DRAM, and the CPU issues them one at a time and waits. the DRAM highway is nearly empty; the CPU just keeps stopping to ask one question and waiting for the answer before asking the next.

a free win came out of this before any code changed: kraken2 defaults to all 96 cores with no memory pinning, but the sweet spot is 32 threads pinned to one CPU's local memory node. that single config change (no source edits) cuts wall time from 5.635s to 4.405s, a 21.8% improvement, by avoiding the roughly 2x latency penalty of reaching across sockets for memory that didn't need to be remote.

## the fix: designed, not yet run

given a latency problem, there are two honest levers: hide the latency (start the memory request earlier so it overlaps with other work) or avoid it entirely (don't go to memory if the answer's already cached). i designed four patches around those two levers, each verified against the specific measurement that justifies it, written as a patch file (`kraken2_opt_v1.patch`): compiler flags to enable AVX-512 vector instructions (the profiled binary uses zero of them, only old-style SSE, despite hardware that fully supports AVX-512), huge-page memory hints so the database load doesn't page-fault constantly, a one-line `__builtin_prefetch` in the hot lookup loop to start the next memory request before the current one returns, and a thread-local cache designed by Kolin sir, a small fast lookup table that catches repeated k-mers before they reach the slow hash table.

that last one is worth a specific number: **90.7%** of lookups within a run are repeats of a k-mer already seen (32.8 million unique across 351.8 million total lookups), far higher than the 20% the cache design originally assumed. clinical samples have a dominant species, so the same k-mers really do repeat heavily, and a cache sized to fit in a CPU core's L2 (256 KB) catches almost all of that without ever touching DRAM. the projected benefit got revised upward accordingly, from roughly 20% faster to 40 to 50% faster.

on projected outcome: baseline is 4.405s (32 threads, pinned). the first four patches together project to roughly **3.0s, a 32% cut**. a further set of smaller patches (dropping an unnecessary virtual call, reusing a hash computation instead of doing it twice, fixing a quadratic-time taxonomy lookup) projects to roughly **2.6s, a 41% cut**, if they pay off as estimated.

here's the honest part, stated once and plainly: **i haven't run the patch yet.** every pre-implementation measurement that justifies these four patches is done and points the same direction, apply them, but `run_kraken2_opt_v1.sh` has never been executed against the patched binary. the numbers above are projections built from measured per-mechanism deltas, not a number i clocked on a real run. running the patch and measuring the real delta is the single highest-priority remaining task on the kraken2 side.

## what database size actually costs you

kraken2's accuracy depends heavily on which reference database it's pointed at, and the tradeoff isn't just "bigger database, slower, more accurate." i built and tested six databases, from a tiny 50 MB custom panel of six reference genomes up to a 103 GB gold-standard RefSeq database, all against the same 104,918 reads from a real AIIMS ICU sample.

classification accuracy rose from 84.80% (50 MB) to 98.86% (103 GB) as the database grew. that part is intuitive. what isn't intuitive is what happens to the *wrong* answers along the way, and this is where the systems story and the clinical story meet.

the 650 MB ESKAPE-only database assigns **100% of its classified reads to *P. aeruginosa***, because it holds reference genomes for *P. aeruginosa* but none for *E. coli* or *K. pneumoniae*. the true sample, confirmed against the 103 GB gold-standard database, is a **polymicrobial infection**: roughly 35% *P. aeruginosa*, 16% *E. coli*, 5% *K. pneumoniae*, a classic ICU ventilator-associated or catheter-related profile. a report from the 650 MB database would read as a *P. aeruginosa* mono-infection, and the correct antibiotic for that (an anti-pseudomonal agent) is not the correct choice for a polymicrobial infection that may need carbapenems for ESBL producers. the wrong database doesn't just lose accuracy points, it maps directly to the wrong antibiotic. this is the clearest "so what" this project produced: a systems tradeoff has a direct line to a patient safety outcome.

the systems reason is a cache cliff. Luna's last-level cache (LLC) is 210 MB. the 50 MB database fits inside it, giving a 10.19% cache miss rate and near-linear speedup with threads (up to 21x at 32 threads). every database above 142 MB exceeds the effective cache capacity, and the miss rate jumps to 30% and climbs toward 90%+ for the 103 GB database. bigger databases are more accurate and structurally slower to query - no size gets you both. see the figure spec below.

## two side results worth a paragraph

**halving the hash table cells.** the hash table stores each entry in a 32-bit cell. i built and tested 24-bit and 16-bit variants against a real ESKAPE database (1.87 million reads). 24-bit shrinks the table by 25% and matches the 32-bit results almost exactly, a genuinely free win. 16-bit shrinks it by half, but without a confidence threshold the false-positive rate floods in: one species, *E. faecium*, saw its read count inflate by **7,118x** purely from hash collisions, sharing essentially no real k-mers with the Gram-negative bacteria dominating this sample. a confidence threshold (`-T 0.05`) collapses that inflation to under 1%, making 16-bit usable for memory-constrained deployments willing to accept the flag. **24-bit is the one i'd recommend as a default.**

**early hardware counters were wrong, and that mattered.** the first round of profiling ran on WSL2 on a laptop. Hyper-V virtualizes the CPU's performance monitoring unit, which inflates measured IPC by 4 to 14x and silently returns zero for cache-miss counters instead of failing loudly. some early conclusions (an initial cache-hotspot percentage from gprof) turned out to be a denominator error, not the real picture. every number that matters in this report comes from Luna, bare metal. i'm flagging this as a methodology correction i made partway through the project: know what your measurement tool can actually see before trusting its answer.

## luna vs orion: the cache gap that explains everything

i also profiled on **Orion**, a Jetson AGX Orin edge device standing in for a deployable, non-server target. Orion's system-level cache is 4 MB against Luna's 210 MB LLC, a 52x gap. that number explains almost every cross-machine difference: the 50 MB database that gets 10.19% cache miss rate on Luna gets **78.92%** on Orion, because that database is 12.5x larger than Orion's entire cache. Orion never gets a "pre-cliff" operating point at any practical database size, it's always past the cliff.

it isn't uniformly worse, though. on the two largest, database-load-dominated configurations, Orion actually *out-scales* Luna in relative speedup (5.54x vs 3.47x on the 7.6 GB database), because Luna's fixed serial database-load time eats a bigger fraction of its faster overall wall time. classification accuracy is identical across both machines given the same database and reads, so the algorithm is deterministic - the divergence is entirely in cache behavior and throughput, not correctness.

## what's proven, what's estimated, what's next

three pieces of this summer's work are complete, measured results, not projections: the dorado GPU profiling (Table 1), the six-database accuracy and cache-cliff sweep across Luna and Orion, and the hash cell-width experiment. one piece has a complete diagnosis behind it but hasn't been executed: the kraken2 optimisation patch. running it and recording the real delta is the concrete next step. a few smaller items remain genuinely open and i'm listing them rather than letting the report imply otherwise: `reads_fast` thread-scaling is missing for two of the six databases, Orion has never been run against the `fast` basecalling model at all, and a proposed GPU-side optimisation for dorado (a signal-to-base cache, projected at roughly 25% GPU time savings) was designed on paper but never built or tested.

## where this goes from here

as of july 2026, the project's direction has shifted. i'm now looking at a different research question: whether Mamba, a newer sequence model architecture, can be reformulated to run on the same GPU hardware paths that attention-based Transformers use, instead of its own bespoke sequential computation. that's a separate line of work and this report isn't the place to explain it. i want to say clearly, though, that the dorado/kraken2 work above is **paused, not abandoned**. the patch, the signal-to-base cache design, and the remaining AccuracyDrift gaps are all still open items that could be picked back up.

---

## figures to build

two figures would make this report land better than the tables alone. both are described here with exact data so they can be handed to a design tool directly.

**figure 1: where the CPU's time actually goes (kraken2, default settings).** a pie or donut chart, five slices, from the TMA breakdown at 96 threads, no NUMA pinning: retiring (useful work) 26.9%, memory bound 25.4%, core bound 21.7%, bad speculation 16.9%, frontend bound 9.6%. the point of the chart: less than a third of CPU cycles do real work. use it right after the "four tools" table.

**figure 2: database size vs. accuracy vs. cache pressure.** a combo chart (bars for classification accuracy, a line overlay for LLC cache miss rate), x-axis the six databases in size order. accuracy values: 50 MB = 84.80%, 142 MB = 65.28%, 3.8 GB = 66.13%, 7.6 GB = 95.77%, 15 GB = 97.77%, 103 GB = 98.86%. cache miss rate values (same order): 14.64%, 30.53%, 59.03%, 82.90%, 85.03%, 91.13%. note in a callout that the 142 MB and 3.8 GB databases have *lower* accuracy than the 50 MB one despite being bigger, because they add irrelevant reference genomes without adding the missing ones (*E. coli*, *K. pneumoniae*), the exact database that caused the *P. aeruginosa* misdiagnosis discussed above. place this right after the clinical-danger paragraph.

---

*a note on process: i used Claude Code to help pull together and cross-check the numbers in this report against the underlying profiling data, and to help draft prose from that data. the measurements, experiments, and analysis are mine; the writing pass had AI assistance, and i'd rather say that plainly than not.*
