# cycle 3, round R2, a2_storage (2026-10-27)

i read the relay brief and the four other `cycle_3_r1_*` files. nothing was run, and nothing new was fetched.

## 1. one line per item

| id | verdict | storage note |
|---|---|---|
| M75 | keep as a rider in M9 / M33 | "never map from lustre" should read "never at scale". at few reads, a map plus M30's async reads touches ~10.7K pages [arith], while a copy moves the whole file. random i/o on lustre "slows down considerably" with operation count [external, via a4 N3], so many-read runs copy or stage. few-read runs are [UNCLEAR] until M78 |
| M76 | keep as a rider | a3's and my worked examples are both right. on 16K pages a 4096-based index makes 4x the `fadvise` calls, and it also reads the wrong `mincore` byte. one rule fixes both: `sysconf(_SC_PAGESIZE)` |
| M77 | keep as a rider in M9 | it can also go upstream as a small `fast_reader` patch, next to M2 |
| M82 | keep inside M21 | no storage effect |
| M86 | keep as a rider in M24 / M9 | on wsl2, refuse `-M` for a db under `/mnt/*` (DrvFs [external, via a4 N1]). a5's snippet says huge files cannot be mapped there [guess]. the vm's disk is a file on the windows host, so a "cold" wsl2 read may come from the host's own cache [UNCLEAR] |
| M90 | keep as a rider in M1 / E2 | orin's 2.1.3 loads with one thread [repo: stock], so E2 there measures the whole chain, loader included |
| M91 | keep as a rider in the cpu gate | no storage effect |
| M70 | unranked measure | on a one-channel box, the sort path's ~64 B of sequential traffic per lookup [arith: a1] competes with the lookups for the channel. run its orin and laptop arms, not only luna |
| M71 | below the line | `cudaHostRegister` pins memory [external, via a1 src 2]. a pinned 15 GB table cannot be reclaimed, and on orin that ram is shared with dorado's gpu memory [repo]. if it ever moves up, it needs M9's fit rule |
| M72 | below the line | it shares M11's sweep code, so it costs little once M11 exists |
| M78 | unranked measure; it is the H4-hpc test | add a4's slot facts to it: run inside a job with `--mem` below the table size. page cache is charged to the job [external, via a4 / cycle-1 a5 S16], so it is also M61 on a parallel fs |
| M85 | campus visit | add `iostat` on the emmc. dorado writing fastq while kraken2 reads the db and input puts both on one ~82-125 MB/s write and ~250-400 MB/s read device [external, cycle 1-2 class numbers] |
| M88 | unranked measure | time a cold reload as well as `fincore`. if the vm's disk is served from the windows cache [UNCLEAR], residency can read 0 while the reload is still fast |
| M89 | unranked measure | macOS has no `posix_fadvise`. its advice call, and whether M30 can work there at all, are [UNCLEAR] |

**class splits**: accept H1-wsl2, H1-mac and H4-hpc. one storage nuance for H4-hpc:
- page cache counts against the job's memory limit [external, via a4]
- a copy-load still fits a `--mem` of about one table, because its page-cache half is reclaimed inside the group during the load [guess]
- `-M` can start below one table, but then it thrashes. that is M61's question, asked on a parallel fs

## 2. wording fixes

| # | verdict |
|---|---|
| 1 | confirm: bioconda and brew ship 2.17.2, debian sid 2.1.3 [external, via a5 T3-T5] |
| 2 | confirm: "its own", merged 2026-06-24 [external]. aligners already prefetch [external, via a5 T7, T8] |
| 3 | confirm. the 0.106 ms and 151K iops come from one enterprise nvme review [external, via a4 cycle-1 src 6]. that is my M30 source chain too |
| 4 | confirm: put [UNCLEAR] back on orin's ~11.6x (sys time used as load time) |
| 5 | confirm: drop "only" |

## 3. verdict

**list unchanged: agree.** both the build top 10 and the measure top 5. every item above is a rider, an unranked measure, or below the line.
