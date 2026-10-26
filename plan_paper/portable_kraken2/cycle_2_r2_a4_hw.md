# cycle 2, round 2, a4_hw (hardware spread)

no new fetches this round. "c2 N#" = my `cycle_2_r1_a4_hw.md` sources. other agents' sources are cited as theirs.

H5 = small cloud vm: m7i.xlarge (2 cores x 2 smt, 16 GiB) or m7g.xlarge (4 real cores); default gp3 storage at 125 MiB/s, 3,000 iops, "single-digit millisecond latency" [external: c2 N1, N2].

---

## 1. counters, one line per new id

| id | counter (what breaks / which class / cheaper / evidence) |
|---|---|
| M26 AMAC `GetBatch` | holds for uncapped dbs on ram-bound boxes. AMAC's 1.13x over SPP was measured on a xeon x5670 hash join [external: a1 src 1], not on a small core. my [guess]: narrow out-of-order cores (a78ae, the pi 5's a76) gain more from software interleaving, and 2-way smt (H5 x86) already interleaves two threads. ~0 on capped dbs, which is what jetson and laptop users carry [guess]. so its H2 value depends on M22 |
| M27 `GetBatch` prologue | holds. 0.25 day. its value is short reads (M28 decides). on nanopore input < 1% on every class [a1 arith]. no class hurt |
| M30 fault-ahead (= my M50) | agree. a2's source closes my gap: WILLNEED "initiates a nonblocking read", but "may be decreased ... depending on virtual memory load" [external: a2 src 1]. so the gain shrinks on H3 exactly when ram is tight (a2). **its biggest class is H5**: qd1 on gp3 is 1-9 ms per fault [c2 N1], the worst of any class. cheaper first: the qd1-vs-qd16 timing (2 min) |
| M31 input hygiene | **matters more on H5 than a2 says.** a 16 GiB vm with the 8GB db (7.6 GB) plus 12.5 GB of input [repo] overflows ram. if the input evicts the db, the rerun pays a 58 s cold reload at 125 MiB/s [arith on c2 N1], the slowest reload of any class. gate it on table + input > MemAvailable, as a2 says |
| M32 detached teardown | H4 only. tables ≤ 16 GB tear down in ≤ ~0.3 s [external: a2 src 4], so ~0 on H1, H2, H3, H5. E1's exit column decides it |
| M33 storage placement | agree, and it generalises beyond jetsons. on H5, gp3 throughput can be provisioned up to 2,000 MiB/s [c2 N1], 16x the 125 MiB/s default. so one planner line ("db on a 125 MiB/s volume: provision throughput, or copy it to local nvme") beats any code on a cold cloud load. the per-instance ebs cap is 1,250 MB/s max on m7i.xlarge [c2 N2] |
| M40 `final` + dispatch | isa-neutral. indirect-call cost per core is [UNCLEAR]. the objdump kill test is the right gate. no class hurt |
| M41 run-length pipeline | per-base work, so every class gains the same absolute ns. it is the largest share on capped dbs, which is what small boxes run. agree with a3's cells |
| M42 shipped sampled profile | **hardware gap**: autofdo samples branch records from the cpu's performance counters [external: a3 N5]. whether orin's a78ae offers a usable branch-sample source is [UNCLEAR, not fetched]. so a profile may only be collectable on x86, and its transfer to arm builds is [UNCLEAR]. keep it after E3 |
| M62 spill guard | support. small-disk classes (H1, H3, H5 root volumes, orin's 8.5 GB free [repo]) are where spill files fill `TMPDIR` |
| M64 compressed slices in M11 | **i concede M13.** on jetsons M33 (an nvme, ~6x [a2 arith]) beats a 1.37-2x container. on H5, provisioning gp3 (up to 16x [arith on c2 N1]) beats it too. inside M11's sweep there is no map to fight, so compression keeps its value there. decode cost on a76/a78 cores is [UNCLEAR] |
| M51 device probe | stays inside M9. a2's qd1-vs-qd16 test is the same measurement, done once by hand |
| M20' quota | no counter has appeared. a5's M62 must ship with it |

measures:
- **M28**: agree. per-read costs grow the same way on every class.
- **M43**: agree. run the PASSIVE and bind variants on an smt box too (H5 x86 or the laptop), not only luna.
- **M60** (daemon): support. on H2 and H5 a cold load is 19-30 s (emmc) or 58 s (gp3) for 8GB [arith], so a daemon pays most there for repeated small batches, such as real-time nanopore on a jetson [guess]. on luna, watch `-D`'s fixed fifo names in /tmp [external: a5].
- **M61** (dmr sweep): agree. one caution: coriolis's 1.5x slowdown up to DMR 52 ran on a sata ssd at ~250 MB/s [external: a5 N2]. luna's raid is faster, so a luna sweep understates thrash. the laptop-class repeat stays required.
- **M63**: agree, but low for my role.
- **cpu gate**: agree, rank 3.

moves:
- a1's M27 at 3: too high until M28 shows short-read gains. 0.25 day, so it rides at 10.
- a3's M41 at 4: 3-5 days and gated by the cpu gate. i put it at 7.
- a2's and my M30 entry: yes.
- M13 out: yes (above).
- M10: still below the line.

---

## 2. fact fixes (section 3 of the brief)

1. **FINAL item 8: confirm the fix.** coriolis ran kraken2 `-M` up to DMR 52 on a 4 GB jetson tx1 and lost 1.5x [external: a5 N2]. say "the only byte-identical way at device speed, *if* `-M` thrashes".
2. **M11 cells: confirm [UNCLEAR] until M61.** my note stands: among our dbs only 103GB is uncapped and big, and it needs 111 GB of disk.
3. **one load per run: confirm.** `-D` and the ONT server amortise the load [external: a5]. M9's warm few-read cells and S19's 9.8-15.4x are one-shot-run numbers.
4. **RC1 output: confirm**, as a5's issue #1061 report [external]. M1 still needs its own compare: `cmp` plus a whitespace-blind compare.
5. **M2 8GB ~1.08x without S8: confirm.** 1 / (0.98 x 0.97 x 0.97) = 1.085 [arith on luna stage gains].
6. **M9 cells: confirm, merged with a2's.** H1 uncapped ~3.4x, capped ~35x. H2 uncapped 4-14x, capped 40-300x. both use a qd1 latency of 0.1-0.5 ms [UNCLEAR]. on gp3-class storage at qd1 the map can lose on an uncapped db (11-96 s vs 58 s) [arith on c2 N1]. with M30, every one of these qd1 cells is superseded.
7. **M20 cells: confirm.** orin ~11.6x classify on 16GB with a parallel loader [arith on `RESULTS.md` 1.4]. H1 5.8-8x, ±20% by chassis [arith on c2 N7].
8. **M21 cell: confirm a3's fix.** orin already builds and runs kraken2 v2.1.3 [repo]. the cell reads "a tuned arm tier".
9. **H1 note: confirm.** the 5800H "supports dual-channel DDR4-3200" [c2 N7], and ck's laptop has one dimm [repo].
10. **exit tax: confirm as arithmetic only.** the 16 GB numbers are from another machine [external: a2 src 4]. luna measured 3.9-11.4 s at 4 KB [measured], 2-6x above the scaled 1.96 s. so the ~0.2 s with-thp figure is a prediction for E1's exit column, not a luna number.

---

## 3. ranking

### top 10 build

1. **M2 (+M3)**: the binary users install.
2. **M20' (+M17 obey, +M62 guard)**: cores, smt and `cpu.max`. measured 11x on orin classify.
3. **M9 (+M24, M51, M33 lines)**: cold and small-ram branches, plus the storage advice line that wins most on H2 and H5.
4. **M30**: turns M9's map branch from qd1 to qd 8-32+. 1-1.5 days.
5. **M4**: every isa, per position.
6. **M5**: gz users, every class.
7. **M41**: per-run pipeline, after the cpu gate.
8. **M26 (absorbs M8a)**: uncapped dbs on ram-bound boxes.
9. **M11 (+M64)**: after M61.
10. **M21 (+M42)**: one tuned binary per isa tier.

just outside, each with a minute-scale kill test: M27 (M28 decides), M40 (objdump decides), M31 (fincore rerun inside M61). below: M10, M32, M14, M18, M19, M16, M15, M7, M6.

### top 5 measure-first

1. **M22** lookup census.
2. **M1**, with the riders: M28 short-read input, exit column, `TMPDIR` set, whitespace-blind compare.
3. **cpu gate** (20 min).
4. **E1 + cold pair**, plus the qd1-vs-qd16 random 4 KB read timing on `hash.k2d` (kills or keeps M30 and M51).
5. **M61** dmr sweep.

next in line: M60 (daemon, 20 min). the orin probe rides the first campus visit, with `lsblk` / `lspci` added for M33. M43, M53, M54 are optional.

---

## 4. role extras

### H5 column for my top 10

| id | H5 small cloud vm | tag |
|---|---|---|
| M2 | 1.02-1.12x | [guess] |
| M20' | 2-4x for default users (2 smt cores x86, 4 real cores arm) | [guess] |
| M9 | cold few-read: capped 6-55x; uncapped ≤ 1x at qd1, a flip | [arith on c2 N1] |
| M30 | fault part 3-27x on cold few-read cells, capped or uncapped: qd1 1-9 ms per fault → the 3,000-iops volume cap | [arith on c2 N1] |
| M4 | 5-20% | [guess] |
| M5 | 1.5-3x when gz-bound; only 2-4 cores to inflate with | [guess] |
| M41 | 2-8% | [guess] |
| M26 | 0-8% uncapped, ~0 capped | [guess] |
| M11 | 103GB-class only: one 111 GB sweep at 125 MiB/s ≈ 847 s, unless throughput is provisioned | [arith on c2 N1] |
| M21 | one binary across instance generations (sapphire rapids, ice lake, graviton) | [guess; c2 N2 lists those cpus] |

### corrected per-class cells for the new build ids

| id | H1 | H2 | H3 | H4 | cold disk |
|---|---|---|---|---|---|
| M26 | 0-8% uncapped (50MB misses 16 MB l3); ~0 capped [guess] | same [guess] | same where it fits [guess] | 103GB 0-8%, 50MB 0 [guess] | 1.0x |
| M27 | nanopore < 1%; short reads 5-7% uncapped [a1 arith] | short reads, high end of the range [guess] | as H1 [guess] | as H1 [a1 arith] | 1.0x |
| M30 | nvme fault part ~10-16x [a2 arith on enterprise nvme] | emmc 2-5x [guess, command-queue depth UNCLEAR]; nvme numbers if M33 applies | by device [guess] | raid [UNCLEAR] | it is a cold-only idea; warm 1.0x (gated off) |
| M31 | low free ram: saves up to one cold reload per rerun [UNCLEAR size] | only with dorado sharing ram [guess] | up to one reload per rerun: emmc 19-30 s [arith] | 1.0x | first run 1.0x |
| M32 | ~0 (≤ 16 GB tables, ≤ 0.3 s) [external: a2 src 4] | ~0 | ~0 | 1-11 s off 103GB small-read runs when thp fails [measured range]; ~0.2 s with thp [arith, other machine] | same as warm |
| M33 | only if booted from sd or emmc [guess] | ~6x on a cold load if an nvme is fitted [arith on class numbers] | as H1 | 1.0x | the point of it; H5: provisioned gp3 up to 16x [arith on c2 N1] |
| M40 | 0.5-3% cpu-bound cells [a3 guess] | same | same | same | 1.0x |
| M41 | 2-8% [a3 guess] | 2-8% | 2-8% where it fits | 50MB / capped 3-10%, 103GB 1-4% | 1.0x |
| M62 | 0 speed; stops exit 73 on small disks [external: a5 N5] | 0 speed; orin has 8.5 GB free [repo] | 0 speed | 0 | n/a |
| M64 | only where M11 runs: table i/o / 1.37-2x [arith] | 103GB from external storage only | where M11 runs | off | it is cold-only |

### one class note

the brief lists the raspberry pi 5 as an H3 example. agreed. its microSD (sdr104) is the slowest storage in any class [c2 N5; speed UNCLEAR], so M33's advice line ("use nvme over the pcie 2.0 x1 slot") applies there too.

---

**strongest counter:** M30's best class is H5, not H1. a default gp3 volume is 1-9 ms per fault at qd1. so without M30, M9's map branch can lose to the copy on uncapped dbs in the cloud, and M33's "provision throughput" line (up to 16x) is cheaper than any code [arith on c2 N1].
