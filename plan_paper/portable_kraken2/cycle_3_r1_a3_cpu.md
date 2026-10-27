# cycle 3, round 1: a3_cpu

agent a3_cpu. i read `cycle_2_conclusion.md`, `FINAL.md`, and every cycle-2 R2 and R3 file. research and writing only. new ids M80-M82.

---

## (a) sources read this cycle

all fetched 2026-10-27. none of these urls appears in any `cycle_1_*` or `cycle_2_*` file (grep of the folder).

| # | source | exact claim used | supports |
|---|---|---|---|
| P1 | bioconda kraken2 recipe, https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/recipes/kraken2/meta.yaml and `.../build.sh` | version "2.17.2". host and run requirements: `libgomp # [linux]`, `llvm-openmp # [osx]`. `additional-platforms`: `linux-aarch64` and `osx-arm64`. `build.sh`: `export CXXFLAGS="${CXXFLAGS} -O3"`, with no `-march`, `-mcpu` or openmp flags of its own. its only macOS branch adds `-headerpad_max_install_names` | M80, M82, M20' note |
| P2 | asahi linux, "broken software", https://asahilinux.org/docs/sw/broken-software/ | aarch64 "can use 4K, 16K _or_ 64K pages", unlike x86. a 4K kernel on apple silicon "requires some very hacky patches" because "the IOMMUs only support 16K-aligned pages". packages are "sometimes built assuming a 4K page size". a chromium bug, "crashes ... w/ 16KiB pages because of hardcoded kGuardPageSize" | M81 |
| P3 | aws graviton getting-started, c/c++ guide, https://raw.githubusercontent.com/aws/aws-graviton-getting-started/main/c-c%2B%2B.md | "use `-march=armv8.2-a`" to target all current gravitons; per generation `-mcpu=neoverse-n1` / `-v1` / `-v2`; "Graviton3, Graviton4, and Graviton5 support SVE, earlier Gravitons do not"; "All Graviton processors after Graviton1 have support for the Large-System Extensions (LSE)"; `-moutline-atomics` gives "runtime detection and use of LSE atomics"; "We have seen 15% better performance on Graviton2 when using gcc-10 instead of ... gcc-7" | M82, M7 note |

failed, so no claim is used from them:
- apple's "addressing architectural differences in your macOS code" page returned only its title (javascript). so the 16 KB macOS page size and apple's affinity rules stay [UNCLEAR] for macOS itself. P2 covers linux on apple silicon only.
- intel's hardware-prefetcher disclosure page redirected to a 404. a search found only conflicting forum and lkml descriptions of MSR 0x1A4. so whether the l2 adjacent-line prefetcher already covers M26's line crossings stays [UNCLEAR]. luna's student account cannot write MSRs anyway [repo: shared account].

---

## (b) counters to cycle_2_conclusion.md

**list unchanged: agree**, both lists.
- my M4/M41-above-M9 view stays on record (section 4 of the conclusion). i do not ask for the move, because all three wait on cheap gates.
- this cycle's findings are riders and fixes, not reorders.

**riders and fixes (no reorder):**
1. **the stock most users actually run is the bioconda build of v2.17.2** [external P1]:
   - its build adds only `-O3`, with no `-march` [external P1]. so it is the "default flags" binary sir's "any machine" question is about
   - bioconda ships it for `linux-aarch64` and `osx-arm64`, with openmp on both: `libgomp` on linux, `llvm-openmp` on macOS [external P1]
   - so M1's v2.17.2 column and E2's orin stock can be the conda binary, with no build at all (M80)
2. **M21's user reach is limited.** users get the bioconda binary, built with `-O3` and no arch flag [external P1]. a tier (M21) reaches them only if bioconda's `build.sh` adopts it. say so in the M21 row.
3. **M20' needs an apple-silicon note.** bioconda's macOS build has openmp [external P1], so a mac runs the team too. "physical cores" there mixes performance and efficiency cores [guess]. kraken2's workers pull blocks one at a time under `critical(seqread)` [repo: `classify.cc:522`], so slower cores take fewer blocks and the load balances itself. the only cost is a tail: the last block may land on a slow core [guess]. how to read the core count on macOS (no cgroup, no linux affinity mask) is [UNCLEAR: not fetched].
4. **every hardcoded 4 KB or 2 MB constant in the list is a portability bug on non-4K arm64 kernels** [external P2]. this is M81.

---

## (c) ideas

### M80 (measure). the bioconda binary as the stock on every class

- **byte-identical check:** compare its output with our v2.17.2 build on luna. bioconda builds with its own compiler, so they may differ only in fp contraction [guess: cycle-1 a3 note 3].
- **mechanism:**
  - *wrong intuition:* "to measure stock on orin or a mac, we must build v2.17.2 there."
  - *real:* bioconda ships v2.17.2 for linux-aarch64 and osx-arm64 with openmp [external P1]. one `conda install` on orin gives a stock binary from a current conda compiler. that avoids orin's gcc, where `-march=native` already broke under gcc-11 [external: cycle-1 a3 S7].
  - on a mac it gives the first native apple-silicon kraken2 run this project could have, if a mac is available [UNCLEAR].
- **worked example:** E2's plan builds two trees on orin from tarballs [repo: next_steps E2 steps 2-3]. M80 replaces the stock build with a conda install, so only S19 or RC1 + M2 needs a build there.
- **gain:** none itself. it gives the stock every non-luna cell should be quoted against.
- **days:** ~0.25, rides on the orin campus visit [guess on install time].
- **risk:** conda needs network on orin [UNCLEAR: campus proxy]. bioconda may move to 2.18 before E2 runs, so pin the version.
- **kill:** none needed. if conda cannot install on orin, fall back to E2's tarball build.

### M81 (rider on M2, M9, M30, M44). page-size-aware constants

- **byte-identical:** yes. it only changes alignment and page arithmetic.
- **mechanism:**
  - *wrong intuition:* "a page is 4 KB and a huge page is 2 MB everywhere linux runs."
  - *real:* aarch64 kernels "can use 4K, 16K _or_ 64K pages", and linux on apple silicon needs 16K [external P2]. at 64K base pages the pmd huge page is 512M [external: cycle-1 a4 src 13].
  - in the current list:
    - S14 and upstream align the table to `1 << 21` [external: cycle-1 a2 src 2]
    - M30 computes pages as `(32 + 4 x idx) / 4096` [repo: cycle-2 a1 r2]
    - M9's touched-page model and M44's 64 MB chunks assume 4 KB pages
  - the fix: read `sysconf(_SC_PAGESIZE)` and `/sys/kernel/mm/transparent_hugepage/hpage_pmd_size` [external: cycle-1 a4 src 12, which names `hpage_pmd_size`] at startup, and use them everywhere.
- **worked example:** on a 16K kernel, M30 with a hardcoded 4096 would issue 4x too many `fadvise` calls, since each 16 KB page is requested 4 times. its dedupe would also count 4x too many distinct pages [arith].
- **gain:** correctness and no waste on 16K/64K arm64 kernels: asahi linux, and 64K server distros [guess on which]. ~0 on 4K kernels.
- **days:** 0.25, inside each host id.
- **risk:** none. it is a review checklist item.
- **kill:** none; it costs nothing.

### M82 (revision of M21). the arm tier is `armv8.2-a`, and the compiler version matters as much as the flag

- **byte-identical:** yes, with `-ffp-contract=off` kept (cycle-1 note).
- **mechanism:**
  - *wrong intuition:* "the arm tier means finding the right `-mcpu` per board."
  - *real:* aws's own advice for one binary across generations is `-march=armv8.2-a` [external P3]. that covers orin's a78ae, whose gcc-11 native string starts with `armv8.2-a` [external: cycle-1 a3 S7], and graviton 2 and later.
  - the same guide reports 15% from gcc-10 over gcc-7 on graviton2 [external P3]. that is another workload, so for kraken2 it is [guess]. but it says a current compiler is worth as much as a flag.
  - orin's system gcc is old [UNCLEAR: E2 step 1 prints it]. the conda compiler (M80) is the cheap way around it.
  - sve: gravitons 3-5 have it, earlier ones don't [external P3], and orin does not (no `+sve` in its native string [external: cycle-1 a3 S7]). so M7's sve path helps H5's arm example (m7g, graviton3 [external: cycle-2 a4 N2]) and not the jetson.
  - LSE atomics come with `armv8.2-a` [external P3]. kraken2's atomics run once per block, so the effect is negligible [guess].
- **worked example:** one arm binary at `-march=armv8.2-a`, built by a current compiler, runs on orin, graviton 2-4 and linux on apple silicon (16K pages if M81 is in) [external P2, P3; guess on apple silicon].
- **gain:** 0-3% from flags [repo: E3 guess], plus an unmeasured compiler-version effect [UNCLEAR].
- **days:** 0.5 with E3.
- **kill:** E3's s21a. on orin, compare the system-gcc build with the conda-gcc build of the same source (rides on M80).

---

## (d) rankings

### top 10 build (unchanged from cycle 2)

| rank | id | riders this cycle |
|---|---|---|
| 1 | M2 (+M3, M27a, M40, block list) | M81 (alignment from `hpage_pmd_size`) |
| 2 | M20' (+M17, M62) | macOS core count [UNCLEAR] |
| 3 | M9 (+M24, M51, M33) | M81 (page math) |
| 4 | M4 | |
| 5 | M30 | M81 (page size in the page math) |
| 6 | M41 | |
| 7 | M5 | |
| 8 | M26 (+M8a) | adjacent-line prefetcher overlap [UNCLEAR]; the `GetAt` annotate decides |
| 9 | M11 (+M64) | |
| 10 | M21 (+M42, now M82's armv8.2-a tier and current compiler) | user reach only via bioconda's `build.sh` |

### top 5 measure-first (unchanged from cycle 2)

| rank | id | riders this cycle |
|---|---|---|
| 1 | M22 | |
| 2 | M1 | add the bioconda v2.17.2 binary as a fifth column on luna (M80) |
| 3 | E1 | |
| 4 | cpu gate | |
| 5 | M61 | |

next, unranked: the orin probe on campus, now with M80 (conda install of v2.17.2 for linux-aarch64 as orin's stock) and M82's system-gcc vs conda-gcc build pair; M43; M53; M60.
