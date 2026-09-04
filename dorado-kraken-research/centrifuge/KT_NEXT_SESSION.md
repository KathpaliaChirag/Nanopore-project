# Knowledge transfer — Centrifuge week 1 → next session

written 2026-08-01, end of the session that did all of week 1's hands-on Centrifuge work. this document exists so a **new chat with zero memory of that session** can pick up cold. read this whole thing before doing anything else.

---

## Part 1 — how CK works in this kind of session (read this first)

CK set explicit working rules partway through the previous session, specifically for any session doing hands-on work on a real remote machine (Luna/Orion/Minerva). if your task involves SSH-based machine work, these rules apply by default unless CK says otherwise. they're also saved as a permanent memory (`feedback_ck_session_workflow.md`), check memory for the current version, this is a snapshot.

1. **One command at a time.** give a short "why" before each command, then the command itself. don't batch multiple commands into one turn unless they're trivial/sequential with no decision point in between.
2. **Wait for the result.** CK runs commands himself (Claude has no direct SSH access to Luna/Orion) and pastes back the output. never assume success and chain ahead speculatively.
3. **Explain every pasted output, briefly.** a plain-English explanation of what the output means, alongside logging it, not just a silent log entry.
4. **Log everything.** every command and its result goes into a running `commands_log.md`; findings/decisions/gotchas go into `observations.md`, with Mermaid diagrams and tables added as they come up, not deferred.
5. **Commit and push after every single step.** `git add` just the relevant files (never unrelated pre-existing changes elsewhere in the repo), commit with a short message, push to `origin main` immediately. repo: `KathpaliaChirag/Nanopore-project` on GitHub.
6. **Context handoff ritual.** when context gets close to full (~90%, though CK may ask for this at any point), produce a long, detailed knowledge-transfer document, like this one, that also explains this workflow itself, since the next session won't have seen it.
7. prose in project docs (README-style files, not raw logs) follows a separate "CK writing style guide" memory: motivation before definition, direct address ("you"), short sentences, Mermaid diagrams, GitHub callouts sparingly, tables always followed by interpretation. check memory (`feedback_ck_writing_style.md`) for the full spec before writing anything reader-facing.

**this specific handoff is different from a normal mid-task KT.** CK's instruction for the next session is *not* "keep executing the plan." it's: **spend the session thinking and planning, run multiple iterations of reasoning about what should happen next, and write out that thinking as plain text in the conversation first, before touching any file, memory, or git commit.** don't jump into Luna commands or start editing docs immediately. the deliverable for at least the first phase of the next session is a well-reasoned written plan, presented in chat, that CK can react to before anything gets acted on.

---

## Part 2 — what actually happened this session (full context)

### The project, one level up

this is `Nanopore-project`, currently in its "kraken2 thesis" phase (pivoted back from a paused Mamba-as-MHA ML direction on 2026-07-25). Kolin sir (the supervisor, always call him "sir") asked for two thesis pieces: a hardware-aware adaptive k-mer cache, and cell-width reduction + double hashing, both needing a **Centrifuge baseline** to compare against (Centrifuge had never been evaluated in this project before). `mtpweek1plan.md` at the repo root is the detailed week 1 plan that set this up, read it if you need the original intent, but this document supersedes it for "what's actually true now."

### What got built and found this session

everything is logged step-by-step in `dorado-kraken-research/centrifuge/commands_log.md` (raw command history) and `dorado-kraken-research/centrifuge/observations.md` (analysis/decisions), and synthesized in `dorado-kraken-research/centrifuge/WEEK1_FINDINGS.md` (the readable summary, **start here** if you want the short version). all three are pushed to `origin main`.

in order:
1. **Step 1 (install Centrifuge on Luna): done.** cloned, built (`make`, no errors), installed to `~/tools/centrifuge/`, added to `PATH` permanently.
2. **Step 3 (build a Centrifuge index): done, at two scales**, not the one originally planned:
   - the genome files Kraken2's `eskape_650mb`/`eskape_human_4gb` databases were built from are **gone**, deleted by this project's own documented build cleanup script (expected), and the finished `.k2d` databases themselves are *also* gone (unexplained, a separate loss).
   - re-downloading the full ~1149-genome ESKAPE set hit a long chain of real problems, in order: too-slow serial download -> parallel download corrupting data (all failures returning an identical bogus checksum) -> root cause found: **Luna's outbound internet needs an IIT Delhi proxy that was never configured** -> fixed the proxy -> still capped at exactly 200/1149 genomes across three independent attempts (parallelism change, proxy fix, fresh-cache-+-retries) -> accepted 200 genomes as a real, reproducible ceiling (likely an outdated `ncbi-genome-download` version vs. NCBI's current catalog format, not root-caused further).
   - built two working indexes instead: `centrifuge_sample_targeted/` (6 genomes, already on disk, no download needed, the fast path) and `centrifuge_eskape_200/` (200 genomes, real re-downloaded data, ~1.1 GB combined FASTA, took 1h08m to build).
3. **Step 4 (baseline run + metrics): done**, with real head-to-head data against Kraken2 (whose numbers were already in `dorado-kraken-research/AccuracyDrift/RESULTS.md` from before this session, not re-measured, just reused for comparison). full tables in `WEEK1_FINDINGS.md`. the headline result: **Centrifuge is ~5.5x slower than Kraken2 at each tool's best config (32 threads on Luna), and collapses to 14-18x slower at 96 threads**, not because of cache misses (Centrifuge's cache-miss rate is consistently *better* than Kraken2's, the opposite of what the plan's own literature review predicted), but because of a genuine thread-scaling problem: IPC collapses from ~1.5 to ~0.2-0.3 at 96 threads, a classic lock-contention/synchronization signature. confirmed at two different database scales, so it's a real Centrifuge behavior, not a fluke or a small-index artifact.
4. **Step 2 (Orion ARM64 install): explicitly dropped for now**, not attempted. reasoning (also in `WEEK1_FINDINGS.md`): if Centrifuge already struggles to use Luna's 96 cores efficiently, porting to a much weaker ARM64 Jetson edge device (12 cores) isn't a good use of time, especially given the ARM64 build was already flagged high-risk in the original plan (a known Bowtie2-lineage x86-only CPUID bug). not abandoned, worth reopening if there's a concrete reason (e.g. if the threading collapse turns out to be a Luna-specific NUMA quirk, which an Orion data point would help settle).
5. **Step 6 (Fibonacci hashing reading): never started.** still fully open. this is background reading for Thesis 2's `h1`/`h2` double-hashing design, see `mtpweek1plan.md` step 6 for the reading list and mechanism explanation.

### What's not resolved, worth knowing

- **the exact cause of Centrifuge's thread-scaling collapse is unknown.** we know *that* it happens and roughly *why* (thread contention, not cache misses), but not the specific function/lock. the week 1 plan's own stretch goal (`perf record --call-graph dwarf` + `perf report`) was never run. this is probably the single most valuable next technical step if profiling continues.
- **the missing `eskape_650mb`/`eskape_human_4gb` Kraken2 databases are still unexplained.** nothing in this project's documented build process should have deleted them (only the genome library and taxonomy scratch folders are supposed to go). worth a note to Kolin sir, any future Kraken2 rerun against those two specific DBs needs a full rebuild too, not just a Centrifuge-side fix.
- **the 200-genome ceiling on `ncbi-genome-download` was never actually root-caused**, just accepted as a wall after three fixes didn't move it. if anyone ever needs the full 1149-genome set, that's still open, likely fixable by upgrading the tool (`pip3 install --user --upgrade ncbi-genome-download`, we had v0.3.3) but this was never tried.
- **accuracy/classification numbers throughout are explicitly labeled "unvalidated"**, Kraken2 and Centrifuge use different confidence thresholds, so any comparison there is directional, not a settled conclusion.

### Key facts you'll need if you touch Luna again

- SSH: `student@luna.cse.iitd.ac.in` (shared account).
- **Luna needs proxy setup for internet access**, this bit us hard this session. full procedure now documented in `dorado-kraken-research/CLAUDE.md` under "Luna internet access" and in memory (`project_luna_network_proxy.md`): `tmux` -> `env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY python3 ~/iitd-login.py -d` -> enter kerberos ID/password -> `Ctrl+B, D` to detach -> then `export HTTP_proxy=http://proxy62.iitd.ac.in:3128` (and the https/lowercase variants). should already be in `~/.bashrc` from this session, but verify if anything network-related seems to hang.
- Centrifuge binaries: `~/tools/centrifuge/` (on `PATH`).
- indexes: `~/AccuracyDrift/databases/centrifuge_sample_targeted/cf_base.*` and `~/AccuracyDrift/databases/centrifuge_eskape_200/cf_base.*`.
- test reads: `~/results/basecalling/reads_hac.fastq` (104,918 reads, the project's standard test input, already used for all Kraken2 baselines).
- standard perf command pattern (32T): `perf stat -e cache-misses,cache-references,LLC-loads,LLC-load-misses,instructions,cycles numactl --cpunodebind=0 --membind=0 ~/tools/centrifuge/centrifuge -p 32 -x <index> -U ~/results/basecalling/reads_hac.fastq -S /dev/null --report-file /dev/null`.

---

## Part 3 — the actual task for this new session

CK's instruction: **run multiple iterations of thinking about what should happen next, and present that reasoning as plain text in the conversation before writing to any file, memory, or git.**

some real open threads to reason about, not a prescribed order, figure out what actually matters most:

- go deeper on the thread-scaling collapse with `perf record --call-graph dwarf` (the plan's own stretch goal, never done), would tell us *which* function/lock is responsible, directly useful for both thesis pieces (Thesis 1's cache design and Thesis 2's hashing work both care about Centrifuge's real bottleneck if it's going to be the comparison baseline).
- start the Fibonacci hashing reading (step 6), pure reading/notes, no machine access needed, feeds directly into Thesis 2's `h1`/`h2` design.
- try to root-cause or fix the 200-genome download ceiling (e.g. upgrade `ncbi-genome-download`) if the full 1149-genome comparison is actually needed for the thesis, or decide it isn't worth it.
- decide what to actually tell Kolin sir this week: the missing Kraken2 databases, the Centrifuge threading finding, the Orion decision, what's meeting-worthy vs. just log detail.
- think about whether week 2 should start on Thesis 1 or Thesis 2 directly, now that a Centrifuge baseline exists (even if partial/small-scale), or whether more Centrifuge groundwork is needed first.

don't treat this list as the plan, it's context for what's actually available to reason about. the point of this session is CK wants to see the *thinking*, not just another list of tasks executed.
