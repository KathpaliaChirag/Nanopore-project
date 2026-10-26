# cycle 2, round R2, a2_storage (2026-10-27)

i read the relay brief and the four other cycle-2 R1 files. nothing was run. one new fetch, to check H5: aws "initialize amazon ebs volumes", https://docs.aws.amazon.com/ebs/latest/userguide/ebs-initialize.html: "For volumes created from snapshots, the data blocks must be downloaded from Amazon S3 ... the volume being initialized might experience increased I/O latency and decreased performance"; "Empty volumes deliver their maximum performance immediately".

---

## 1. counters, one line or more per new id

- **M26** (a1): no objection warm. on a cold mapped table, yielding at a line edge does not help: the next touch is a blocking major fault, not a cache miss. so M26 is warm-only, and M30 is its cold partner.
- **M27** (a1): a1's own arithmetic gives under 1% on our nanopore data [arith: a1]. its target, short reads, is unmeasured (M28). on a cold map, a prologue prefetch starts no disk read [external, via a5 PREFETCHh]. fold M27a (0.25 day) into M2's upstream bundle. M27b builds the same block-wide lookup list M30's pre-pass needs, so build it once for both.
- **M28** (a1): the cut file stays far inside luna's 35 GB free [repo]. but short reads make ~21x more output lines per base [arith: 3,223 / 150], and RC1 spills output to `TMPDIR` under lock contention [external, via a5 N5]. time it with output to disk as well as `/dev/null`.
- **M31-M33** (mine): M31 is gated inside M61. M32 is likely a null wherever huge pages land, at ~0.2 s scaled [arith on cycle-2 R1 src 4]; E1's exit column decides. M33 is one line in M9.
- **M40** (a3): no storage effect. the 10-minute `objdump` kill comes first.
- **M41** (a3): tokens per read drop ~3x [arith: a3], so M11's in-ram token budget covers ~3x more reads before a re-scan.
- **M42** (a3): no storage effect; it rides with M21.
- **M51** (a4): agree. it replaces my sysfs-only device class. three fixes:
  - `O_DIRECT` can fail on some filesystems [guess], so fall back to the class default
  - a snapshot-restored ebs volume reads slowly until initialized [external: aws, above], so the probe must flag "uninitialized?" when qd1 latency is far above the class range
  - skip it on warm files and on dbs under ~1 GB
- **M20'** (a4): agree. keep the loader's stream count separate from the cpu count: a 2-core H5 box still wants ≥ 8 streams on network storage [external, via a4: PR #1033's 8 streams reached the provisioned 1 GB/s].
- **M62** (a5): agree. guard on a missing `TMPDIR` and also on low free space there. orin has 8.5 GB free on an emmc that writes ~82-125 MB/s [repo; external, cycle 1].
- **M64** (a5): agree. inside M11's sweep there is no map to fight, and a bitmap expand (~1-2 GB/s per core [guess, a3]) beats sata and emmc rates. standalone M13 keeps only a4's H5 cell (58 s → ~42 s [arith: a4]), paid once per boot if the db then stays cached. it stays below the line.
- **measures**:
  - M43: agree; on orin, add output to emmc
  - M53 and M54: optional. M53 is the only route to real H5 numbers
  - M61: replaces M12. add the copy path, since its OOM is itself the H3 answer
  - M63: time cold and warm. Metabuli streams its db by design [external, via cycle-1 a1 src 10]
  - M60: see 4a

**proposed moves:**
- a3's "M9 to 5, below M4 and M41": disagree. on H2-cold, H3, H5 and low-ram H1, a cold load or a swap dwarfs a 2-25% cpu gain, and M9 is the only lever there. M4 and M41 wait on their gates either way.
- a4's "M10 out": accept to rank 11. its exit-tax half only shows where huge pages fail, and E1 shows whether they do.
- a4's "M13 stays": reject (above).
- a5's "M62 with M20, M13 into M64": accept.
- a1's "M27 at 3": reject (above).

---

## 2. fact fixes (brief section 3)

| # | verdict | note |
|---|---|---|
| 1 | confirm | `-M` ran it under cgroup caps to DMR 52 [external, via a5 N2]. FINAL item 8 becomes: "the only byte-identical way at device speed, if `-M` thrashes" |
| 2 | confirm | [UNCLEAR] until M61. only 103GB is uncapped and big; 50MB's cap waits on M22 |
| 3 | confirm, with a caveat | a daemon pays the load once [external, via a5], and keeps the table resident (4a) |
| 4 | confirm, as one report | one tester on macos/arm64 [external, via a5 N5]. M1 keeps its own raw and whitespace-aware compare |
| 5 | confirm | 1 / (0.98 x 0.97 x 0.97) ≈ 1.085 [arith] |
| 6 | confirm, one fix | H1 capped ~34x, H2 capped 38-300x [arith]. **H2 uncapped on a4's 0.1-0.5 ms bracket: 1.07-5.35 s vs 19-30 s = 3.5-28x**, not 4-14x [arith]. gp3 flip holds: 10.7-96 s vs 58 s [arith on a4 N1] |
| 7 | confirm | 11.6x [arith], if stock's 4.23 s of sys time is all load [guess, a4] |
| 8 | confirm | orin runs v2.1.3 with default flags [repo] |
| 9 | confirm | [external, via a4 N7] |
| 10 | confirm (mine) | 282.16 vs 27.68 ms for 16 GB [external]. the 111 GB figures are scaled from another machine; luna's 3.9-11.4 s [measured] is 2-6x above them |

---

## 3. ranking

**top 10 build**

| rank | id | one line |
|---|---|---|
| 1 | M2 (+M3, +M27a) | the binary users install |
| 2 | M20' (+M17, +M62) | every class; needed under cpu quotas [external, via a4] |
| 3 | M9 (+M24, +M51, +M33) | the only lever on cold, small-ram and cloud boxes |
| 4 | M30 | without it, M9's map can lose on gp3 [arith: a4] |
| 5 | M4 | ~60% of cycles on a capped db [measured, luna gprof] |
| 6 | M41 | per-position work; shrinks M11's token budget |
| 7 | M5 | gz users |
| 8 | M26 (absorbs M8a) | warm, uncapped, ram-bound boxes |
| 9 | M11 (+M64) | gated by M61 |
| 10 | M21 (+M42) | portable tiers |

just outside: M10, M40 (may die in 10 minutes), M31, M32, M13, M14, M18.

**top 5 measure-first**
1. **M22**: f per db.
2. **M1**: riders are the exit column, RC1 `-M`, M28, a whitespace-aware compare, and `TMPDIR` set.
3. **E1 + cold pair + qd1-vs-qd16 random reads**: decides M9's map branch and M30. the same timing is M51's kill test.
4. **M61 + M31's rerun check**: the thrash curve.
5. **M60, with rss and residency logging**.

free alongside: the cpu gate, `objdump` (M40), `perf annotate GetAt` (M26), `zstd -1` (M64). the orin probe rides the campus visit.

---

## 4. role extras

### 4a. M60: what stays resident in a daemon

- **copy path**: the table stays as private, anonymous memory between requests, and without swap the kernel cannot reclaim it. on H1 (2.9-3.8 GB free [repo]), H3 and orin (64 GB shared with dorado [repo]), that ram is lost to everything else for the daemon's life [guess on impact].
- **`-M`**: the pages are page cache, so the kernel can reclaim them. MGLRU protects mapped pages more strongly than fd-read ones [external: cycle-2 R1 src 2].
- **rule**: daemon + copy (THP) on big boxes, daemon + `-M` on small ones. it is M9's fit rule, applied once at daemon start.
- **log**: rss, `AnonHugePages`, `fincore hash.k2d` between requests, and the first-request latency after an idle period under memory pressure.
- **caveats**: RC1 `-D` keeps "a `std::map` of loaded indexes" [external, via a5], so resident memory is the sum of all dbs. its fixed `/tmp` fifo names can collide [external, via a5]. a daemon pays the exit tax and huge-page setup once, so M32 and M10's exit half are moot there.

### 4b. H5 storage numbers

| number | verdict |
|---|---|
| gp3 125 MiB/s, 3,000 iops, single-digit ms latency [external, via a4 N1] | holds |
| cold 8GB 58 s, 16GB 114 s [arith: a4] | holds |
| instance cap 156.25 baseline / 1,250 MB/s max [external, via a4 N2] | holds; on default gp3 the 125 MiB/s volume limit binds first [arith] |
| M30 batched 10.7K / 3,000 = 3.6 s [arith: a4] | holds as a ceiling |
| **missing: snapshot-restored volumes** | a db delivered as an ebs snapshot [guess: common] reads slowly until every block is pulled from s3 [external: aws], so the first cold load can exceed 58 s. a freshly downloaded db on an empty volume does not have this |
| **missing: fit** | m7i.large has 8 GiB [external, via a4 N2], so the 7.6 GB db cannot be copied: map only. on m7i.xlarge (16 GiB) the copy fits, but part of the file's cache may be evicted, so reruns refetch some of it [guess] |

so H5 is M9's strongest case after H2: a slow first read, a fit rule that flips between 8 and 16 GiB, and millisecond qd1 latency for M30 to lift.

**strongest counter**: M27 should not take rank 3. a1's own arithmetic gives under 1% on our data, its short-read target is unmeasured, and on a cold map a prologue prefetch starts no disk read. M27a goes inside M2's upstream bundle; M27b shares M30's block lookup list.
