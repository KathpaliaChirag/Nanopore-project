# prompt for opus: decide and plan the next speedup work (2026-10-21)

paste everything below the line into opus. it is self-contained.

---

you are helping ck (a student, supervisor "sir" = prof. kolin paul) decide what to build and measure next on a kraken2 speedup project, then plan it in enough detail that he can execute it one command at a time. think hard before answering. do not start running anything until you have given the plan and ck approves it.

## 1. what the project is

stock kraken2 (v2.1.x/2.17 source) classifies reads by looking up each read's minimizers in a hash table (`hash.k2d`) of taxon labels. ck has built a stack of byte-identical speedups called S6 to S19 on top of stock. every stage has a file in `plan_paper/explanations/` (00_INDEX.md lists them): original code, issue, new code, why it is correct, result. read those first. also read `plan_paper/s6_s15_speedup_report_2026-09-24.md`, `plan_paper/research_brief_next_speedups_2026-10-21.md` (the lever table and a ranking), `plan_paper/handoff_s2_speedup_investigation_2026-09-23.md`, `plan_paper/research_brief_associativity_case_study_2026-09-02.md`, and `plan_paper/command_log.md`.

already done, do not redo: S8 one input stream, S9/S16 batched then software-pipelined prefetch, S10 parallel pread table load (capped at 32 threads), S12 reciprocal-multiply modulo, S13 memchr newline scan, S14 2MB-aligned table + MADV_HUGEPAGE, S15/S17/S18 run-length hit counts, rolling reverse complement, ring buffer. S19 = portability guards. ruled out by ablation: the 4-way k-mer cache (the real wins were pipeline, load and hugepage fixes), first scanner rewrite (S11, null).

headline so far: S19 is 1.8x to 4.4x faster than stock at 1.87M reads and 10-17x at small read counts, byte-identical in all 16 cells (4 dbs x 4 read counts), one machine, warm page cache, thp variance on 103GB (13 to 21 s).

## 2. machines and ground truth

| | luna | orin | lenovo laptop |
|---|---|---|---|
| cpu | 2x xeon platinum 8468, 96 cores / 192 threads, 2 numa nodes, cpu ids interleaved (even=node0, odd=node1), 210MB L3 | jetson agx orin 64GB, 12x cortex-a78ae, 4MB slc | ryzen 7 5800h, 8c/16t, 16MB L3 |
| ram | 503GB, 8x64GB ddr5-4800 (so at most 4 channels filled per socket, split not verified), 361GB sits in page cache | 64GB lpddr5 unified with gpu, ~205 GB/s (external knowledge, unverified) | 1x16GB ddr4-3200, single channel, ~25.6 GB/s peak, 13.9GB usable |
| storage | 7TB hardware raid volume (perc h755), ssd-backed, root disk 97% full, 35GB free | 57GB emmc, 8.5GB free (as of 2026-06) | 512GB nvme |
| access | `ssh -i ~/.ssh/luna_claude student@luna.cse.iitd.ac.in`, sudo works (ck knows the password, ask him, never store it) | `jetsonagx@10.154.233.173` on campus network only, ck must provide credentials | local windows 11, no wsl, no python-based linux tooling, kraken2 cannot run natively |
| dbs | 50MB (sample_targeted), 8GB, 16GB, 103GB (pluspf) under `~/AccuracyDrift/databases/` | up to 16GB only, 103GB cannot fit | only 50MB and maybe 8GB |

binaries live in `~/tools/kraken2-fresh-bin-sNN/` on luna (s0 = stock baseline, s10, s19 etc). input = 16 files `~/chirag_K/results/per_pod5_fastq/pod5_*.fastq`, 1,872,777 reads, 12.5GB. scripts: `plan_paper/scripts/s6plus/bench.sh`, `cores.sh`, `matrix.sh`, `modes.sh`, `check.sh` (byte compare), `threads_sweep.sh` (new). a thread sweep (`tmux` session `thsweep` on luna, log `~/chirag_K/results/s6plus/sweep103.log`) is running: s0 vs s10 on 103GB at threads 1,2,4,8,16,32,64,96,128,192, one rep each. first two results: 1 thread, stock 1046 s, s10 685 s (so even at 1 thread the s10 binary is 1.5x faster, because the s10 binary is cumulative with S6-S9, the parallel loader does nothing at 1 thread). do not touch luna benchmarks while it runs; check `tmux ls` and the log before launching anything.

## 3. what we discussed this session (treat as the state of knowledge)

1. sir asked: can we fetch entries from the 103GB db into the 50MB db. answer: not by copying cells (103GB cells hold 16 key bits + 16 value bits, so keys cannot be enumerated), but yes by lookup: take k-mers from reads or genomes and ask the 103GB db `Get(kmer)`, then write the label into the 50MB db (`plan_paper/eskape_teacher_transplant_2026-10-14.md`). 65.6 to 94.4% agreement on held-out pod5, 51MB to 90MB. not a neural network. two limits ck must name: 103GB is treated as ground truth (agreement is imitation, not correctness), and the held-out files are from the same run so generalization is untested.
2. sir asked why 32 threads reading the table is faster when "there is a single channel to disk". answer: storage and ram are not single-channel; one thread keeps queue depth at 1; and the file is in the page cache so the load is a ram to ram copy that parallelizes until memory channels or cores run out. the cold-cache case is untested. orin's emmc is the true narrow channel, so s10 should give ~nothing cold there and something warm, capped by 12 cores. the laptop's single channel should saturate at 2 to 3 threads.
3. levers ranked in the research brief: (1) `-M` memory-mapping vs s19, warm and cold, load and classify timed separately; (2) per-machine `-O3 -march=native` then PGO; (3) parallel fastq parse; (4) flat hit-count array + per-machine prefetch tuning; (5) overlap db load with first parse + hugetlb reserved pages.
4. corrections to the brief that i made and you should keep: (a) the brief says the serial parse is 3.88 s of an 8.88 s run, "44%". parse and classify overlap, so this is a ceiling only if workers starve. the free diagnostic is a thread sweep on the 50MB db: flat from 16 to 192 threads means a serial wall, still falling means the parse is not the limit. (b) `-M` maps the file with 4kb page-cache pages, so it probably loses the S14 hugepage benefit on the random lookups, and 27M page faults for 103GB. the "16 s of a 20 s run" figure for 103GB load in the brief is not trusted, the real load time is wall minus kraken2's own "processed in" time in the sweep `.err` files. (c) `-O3` is probably already in the stock Makefile, unverified; big dbs are memory-bound so compiler flags should give ~0 there.
5. ck's own midterm "plan" slide lists P1 double hashing, P2 sniper modelling, P3 minimizer prefetching. my assessment: P3 is already built (S9/S16), only per-machine tuning is left; P1 double hashing is already in the source behind `-DLINEAR_PROBING` (flip + rebuild the binary and each db), at 0.7 load factor textbook failed-lookup probes go ~6.1 (linear) to ~3.3 (double), but linear probing's adjacent slots share a cache line (16 four-byte cells per 64B) while double hashing jumps lines, so fewer probes does not mean faster, expect null or slower and the real value is the false-positive cliff (thesis 2); output not byte-identical so needs an accuracy table not `check.sh`; luna has 35GB free so a 103GB rebuild is impossible; there is also an unaudited gcd(step, capacity) risk. P2 sniper is a modelling tool, not a speedup; its results were not trusted and were left out of the midterm deck.

## 4. your job

produce a decision and a plan. specifically:

a. challenge section 3. find anything wrong or overclaimed, check it against the files in the repo, and say what you verified vs assumed. tag every claim [repo], [measured], [guess], or [external].
b. decide what to do next. ck wants things he can reliably show sir on wednesday and a story that holds on any machine, not only luna. rank at most 5 experiments. for each give: hypothesis and why it should or should not work in mechanism terms (memory latency, bandwidth, tlb, queue depth, serial fraction, cache lines), prediction per machine with a number range, exact commands (one at a time, in order), the measurement that decides it, a kill criterion (when to stop), correctness check (byte-identical via `check.sh`, or the accuracy metric if not identical), runtime cost, and what could confound it (warm vs cold page cache, thp variance, other users on luna, numa placement, one rep).
c. design the cross-machine story. a single chart or table that shows the same experiment on luna, orin, laptop, and is honest about what is measured vs predicted. say what test could run on the laptop without kraken2 (for example a parallel pread/memcpy scaling test) and write it if useful.
d. include a cold-cache protocol for luna (`sync; echo 3 > /proc/sys/vm/drop_caches` with sudo) and say how to confirm the cache state before and after (e.g. `free -g`, `vmtouch` if present, or fincore).
e. include what to do with the thread sweep once it finishes: how to split load time from classify time from the `.err` files, what plot to make (time and speedup vs threads, both binaries, a marked line at 32 where the s10 loader cap is), and how to read a flat region.
f. give the wednesday story as a short ordered list, and a "do not claim" list.
g. end with the single first command ck should run next and why.

## 5. working rules (from ck's standing preferences)

- one command at a time, each with a plain explanation of why, what we gain, and what we are building. wait for the result and explain it before the next one. log every step in `plan_paper/command_log.md`, commit and push each step.
- ck's writing style: lowercase, no em-dashes, no filler, motivation before definition, name the wrong intuition first. this applies to any file or doc you write.
- always show the full table (4 read counts x 4 dbs) for any benchmark, never a subset.
- never call anything "patch 4" or frame the adaptive cache as recovering old work.
- do not build html slide decks, use markdown.
- luna has two network requirements for internet access (tmux + iitd-login.py auth and the proxy `proxy62.iitd.ac.in:3128`), irrelevant for local benchmarks but remember it if a download is needed.
- do not store credentials in any file. do not run anything on luna that could disturb the running `thsweep` session. do not modify `~/tools/kraken2-fresh-bin-s0` or any existing binary directory, build new trees (for example `kraken2-fresh-bin-s20a`).
- be honest about null results. a measured null is a valid result and should be reported as one.

write the plan as a markdown file `plan_paper/next_steps_plan_2026-10-21.md`, then give a 10-line summary. do not commit it, ck will review first.
