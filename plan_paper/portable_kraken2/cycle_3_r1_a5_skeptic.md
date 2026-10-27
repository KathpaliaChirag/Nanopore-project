# cycle 3, round 1: a5_skeptic (2026-10-27)

tags as in `00_context.md` section 6. i read `cycle_2_conclusion.md` (with the vote), `FINAL.md`, the other agents' cycle-2 R2 files and their R3 votes.

---

## (a) sources read this cycle

all new: i grepped `plan_paper/portable_kraken2/` for each url and found none in a `cycle_1_*` or `cycle_2_*` file.

| # | source | exact claim used |
|---|---|---|
| T1 | kraken2 pull requests, sorted by update, https://github.com/DerrickWood/kraken2/pulls?q=is%3Apr+sort%3Aupdated-desc | no 2.18.0 final and no RC2 yet (the releases page still shows v2.18.0-RC1 as "Latest"). recent merges are BenLangmead's multi-db and spill fixes, e.g. #1053 "Fix classify's output spill files for multi-threaded --classified-out/--unclassified-out" (Oct 16) and #1059 "Run merge serially when OpenMP provides only one thread". no open or merged pr touches mmap, prefetch, huge pages, nfs, macOS or arm |
| T2 | kraken2 PR #1063, https://github.com/DerrickWood/kraken2/pull/1063 (open, Oct 22, 2026) | "Optimize ResolveTree scoring and confidence fallback": "start with t's direct votes and walk its parent chain" instead of testing every hit against every candidate. microbenchmarks on a Ryzen 7 8845H: 256 taxa, confidence 0: 198.9 → 3.75 µs (52.99x); 16 taxa: 0.69 → 0.14 µs (4.89x); 2-hit chain: 1.001x. not end-to-end runs. it claims it preserves "the resolver's output and existing arithmetic", checked on 32,934 differential cases, and makes no byte-identity claim. no maintainer reply |
| T3 | homebrew formula, https://formulae.brew.sh/formula/kraken2 | stable 2.17.2. bottles for macOS on Apple Silicon and for Linux ARM64 and x86_64. 573 installs in 365 days |
| T4 | bioconda recipe, https://bioconda.github.io/recipes/kraken2/README.html | latest "2.17.2-0". additional platforms: linux-aarch64 and osx-arm64 |
| T5 | debian package, https://packages.debian.org/sid/kraken2 | sid ships 2.1.3-1 (arm64: 2.1.3-1+b2), built for amd64, arm64, armhf and more. a search result also lists bookworm at 2.1.2-2 (that page was not fetched, so i do not use it) |
| T6 | Drexel URCF HPC page, https://docs.urcf.drexel.edu/software/compiling/Compiling_kraken/ (Kraken 1 era) | "Storing the database on a network filesystem (NFS) partition can cause Kraken's operation to be very slow"; jobs "**must** use local scratch, given by the environment variable `TMPDIR`"; "Use of Lustre has not been tested" |
| T7 | Intel, architecture-aware BWA-MEM, https://arxiv.org/abs/1907.12931 | kernels sped up by "improving cache reuse", larger contiguous allocations, "software prefetching" and SIMD. "up to 3.5x and 2.4x speedups on end-to-end compute time" on one thread and one socket of a Skylake Xeon. the prefetch share is not separated |
| T8 | minibwa, Li and Homer, https://arxiv.org/abs/2606.15357 (June 2026) | "It speeds up BWA-MEM2 further with additional prefetch for seeding"; "about four times as fast as BWA-MEM and over twice as fast as BWA-MEM2" |

searches with nothing usable:
- kraken2 apple silicon issues
- bio tools using `posix_fadvise` / `MADV_WILLNEED` index prefetch: "new for bio tools" stays [UNCLEAR, one search]
- kraken2 on wsl2: one search snippet (a blog, not fetched) says the `/mnt` 9p bridge "cannot memory-map huge files". i use that as a [guess] only

---

## (b) counters to `cycle_2_conclusion.md` and `FINAL.md`

**list unchanged: agree.** none of the new evidence reorders the top 10 or the measure top 5. it adds riders and fixes wording.

1. **FINAL rank 1 and summary item 3, "the binary everyone installs".** that depends on the install channel.
   - bioconda and homebrew ship 2.17.2, so PR #1033 is already there, on arm too [external: T3, T4]
   - debian sid ships 2.1.3 on amd64 and arm64 [external: T5], so apt users get none of it. our orin runs v2.1.3 [repo: `RESULTS.md` 1.4]
   - so an upstream merge reaches conda and brew users in weeks, and apt users only when debian updates [guess on lag]
   - say "the binary conda and brew users install". add a v2.1.3 column where the channel matters (M90 below)

2. **FINAL summary item 1, "already ships *our* prefetch, parallel load, memchr parser and huge pages".**
   - PR #1033 was merged on 2026-06-24 [external: cycle-1 S3], before S8 was built [repo: `command_log.md` 2026-08-25]
   - "our" reads as if upstream took them from us. say "its own"
   - batched index prefetch is also established in aligners: BWA-MEM's architecture-aware rewrite used "software prefetching" [external: T7], and minibwa adds "prefetch for seeding" [external: T8]
   - so no talk or paper text should present S9/S16-style prefetch as new for bioinformatics

3. **FINAL summary item 7, "~16x on nvme".**
   - it comes from one enterprise drive's 0.106 ms at queue depth 1-16 and 151K iops at depth 16 (a4 cycle-1 src 6)
   - say "on an enterprise nvme". laptop nvme scaling is [UNCLEAR] until the 2-minute qd1-vs-qd16 timing runs
   - FINAL rank 5's H1 cell needs the same word

4. **FINAL summary item 4, "classify with all 12 cores is ~11.6x faster".**
   - it takes stock's 4.23 s of *sys* time as the load time [repo: `RESULTS.md` 1.4], which the conclusion tags [UNCLEAR]
   - FINAL drops that tag. put it back

5. **the cpu gate is missing per-read decision cost.**
   - upstream has an open PR that speeds `ResolveTree` 4.9x at 16 hit taxa and 53x at 256, in microbenchmarks only [external: T2]
   - our profiles show no `ResolveTree` symbol in the S19 50MB top list [measured: `perf_s19.data` shares in `00_context.md`]. it may be inlined into `ClassifySequence`'s 25.1% [UNCLEAR]
   - on the 103GB db, with many taxa per read, and on M28's short reads (more reads per base), its share is unmeasured
   - so the cpu gate should report it (M91 below)

6. **the "residual over v2.17.2" can move again.**
   - if #1063 merges, upstream gains a per-read speedup that S19 does not have [external: T2]
   - M1's RC1 column would then be stale before M2 ships
   - M2's port must target whatever upstream master holds when it starts, and M1 should record the upstream commit hash

7. **HPC is part of H4, and nothing in the list covers a db on a network filesystem.**
   - kraken docs and an HPC centre say a db on nfs is "very slow" and require local scratch (`TMPDIR`) [external: T6]
   - upstream's own pr author worried that parallel reads may hurt on nfs [external: cycle-1 S3]
   - M9's device probe has no block device to read there (a2, cycle 1)
   - so M9 needs one filesystem-type rule (M92 below). that is an advice line, not a new rank

8. **M62 may shrink.** upstream is fixing spill paths (#1053) [external: T1]. on hpc, `TMPDIR` is local scratch [external: T6]. the guard still matters on small roots like orin's 8.5 GB free [repo].

9. **cycle_2_conclusion 1.2 opens with "lost only 1.5x".** drop "only", so the clause cannot be quoted without its "no in-ram baseline" caveat.

---

## (c) ideas

### M90. channel-aware baseline (measure)
1. **name:** add v2.1.3 (debian / ubuntu apt, and what orin runs) next to v2.17.2 (bioconda, brew) in M1, and in E2 on orin. byte compare across versions, expecting differences in 2.1.3's parser era [UNCLEAR].
2. **mechanism:**
   - wrong intuition: "stock is one version."
   - real: users run what their channel ships [external: T3, T4, T5].
   - worked example: a jetson user on apt runs 2.1.3. for that user, the gain to report is 2.1.3 → (2.17.2 or S19), the whole chain. a conda user's gain is only the residual (~1.08x on 8GB [arith])
3. **gain per class:** none itself. it decides which headline each class may quote.
4. **days:** +1 build column, ~20 min.
5. **risk:** 2.1.3 predates the v2.1.4 parser rewrite [repo: `command_log.md`], so outputs may differ. report a diff count, not a ratio alone.
6. **kill test:** none needed. it is a column.
7. **sources:** T3-T5.

### M91. `ResolveTree` share in the cpu gate, then adopt upstream #1063 if it matters (measure first)
1. **name:** `perf annotate` / `perf report` for `ResolveTree` (or its inlined lines) on 50MB, 8GB and 103GB, at 1,872,777 nanopore reads and on M28's 150 bp input. #1063 preserves the resolver's output by differential test [external: T2]. byte identity must be checked by `cmp`.
2. **mechanism:**
   - wrong intuition: "the decision is a tiny per-read step."
   - real: the old resolver scores every hit taxon against every candidate, so its cost grows roughly with taxa² per read [external: T2's description].
   - worked example: at 16 taxa a call is 0.69 µs [external: T2]. at 1,872,777 reads that is ~1.3 s of cpu [arith], about 0.5% of S19's ~234 core-s on 50MB [repo]. at 256 taxa it is 199 µs per call [external], which would be ~370 core-s for the same read count [arith], more than the whole 50MB run. so the real taxa-per-read distribution decides it [UNCLEAR]
3. **gain per class:** if the share is real, it is per read, so every class gains the same share. largest on short reads and many-taxa dbs [guess].
4. **days:** 0.1 to measure. 0.5 to cherry-pick #1063 into the M2 base, if it merges.
5. **risk:** it is an open, unreviewed pr [external: T2]. the microbenchmarks are synthetic.
6. **kill test:** if `ResolveTree` is under 1% of cycles on 103GB and on short reads, drop it.
7. **sources:** T2.

### M92. filesystem-type rule inside M9 (build, an advice line)
1. **name:** byte-identical (advice and the load path only).
2. **mechanism:**
   - wrong intuition: "every slow disk is a block device the probe can time."
   - real: nfs, lustre and wsl's 9p mounts have no block device to time (a2). kraken's own docs and an hpc centre say to use local scratch [external: T6].
   - the rule: if the db's filesystem type is a network or 9p type (read once at startup [guess: `statfs`]), print "copy the db to local scratch, or run a daemon (`-D`)", and use the sequential copy path with M51's stream count, not `-M`
   - worked example [guess]: none, because no kraken2 nfs timing exists in any source we found
3. **gain per class:** H4 on hpc clusters, H1 under wsl with the db on `/mnt/c` [guess]. 0 elsewhere.
4. **days:** 0.25, inside M9.
5. **risk:** filesystem-type names differ by kernel [UNCLEAR]. advice only, so it cannot break output.
6. **kill test:** none cheap here. no network fs is available to us [UNCLEAR on luna's mounts].
7. **sources:** T6, cycle-1 S3.

---

## (d) rankings (unchanged from cycle 2)

### top 10 build

| rank | id | note this cycle |
|---|---|---|
| 1 | M2 (+M3, M27a, M40, block list) | target upstream master at start, and record its hash (counter 6). say "conda and brew users" (counter 1) |
| 2 | M20' (+M17, M62) | M62 may shrink as upstream fixes spill paths [T1] |
| 3 | M9 (+M24, M51, M33, **M92**) | adds the filesystem-type rule |
| 4 | M4 | unchanged |
| 5 | M30 | "enterprise nvme" in its cells (counter 3) |
| 6 | M41 | unchanged |
| 7 | M5 | unchanged |
| 8 | M26 (+M8a) | unchanged. aligners already prefetch [T7, T8]; no interleaving prior art found in bio tools [UNCLEAR, one search] |
| 9 | M11 (+M64) | unchanged |
| 10 | M21 (+M42) | unchanged |

### top 5 measure-first

| rank | id | new rider |
|---|---|---|
| 1 | M22 | none |
| 2 | M1 | **M90**: a v2.1.3 column, and the upstream commit hash |
| 3 | E1 | none |
| 4 | cpu gate | **M91**: the `ResolveTree` share on 103GB and on short reads |
| 5 | M61 | none |

the orin probe still rides the campus visit. E2 there should include v2.1.3, v2.17.2 and S19 (M90).
