# cycle 1 R3 vote: a5_skeptic

**build list (section 2): DISSENT, one change.**
- move M20 to rank 2 and M9 to rank 3. M20 takes under a day, is byte-identical, and has the table's only measured gain cells. M9's size rests on two things nobody has measured: E1, and queue-depth-1 fault latency.

**measure-first list (section 3): AGREE.**

**errors and overclaims:**
1. **1.2 "settles it" / "cross-check".** the cross-check is the same ratio rearranged, so it is not independent. f×hit rate = 3.22M / (354M × d), which equals hit positions / positions. "that capped db" is unverified: a gprof undercount still fits [repo: `gprof_report.txt`]. f = 0.088 belongs to the WSL2 db. ours stay [UNCLEAR] until M22. so "a capped db does 1 per 30" is a transfer, not a measurement. 1.3 inherits this.
2. **1.4.** the PR #1033 pair mixes isa, cores, smt, clang vs gcc and the whole bundle. it supports no prefetch-only claim, including "helps most where two threads share a core" [external: PR #1033].
3. **M9 H1 "3-50x".** the 50x end uses queue-depth-16 iops. section 1.5 says few-read cold faults run at queue depth 1. at a4's 0.106 ms: 10.7K × 0.106 ms = 1.1 s vs a 3.8 s copy, so ≈3.4x [arith on a4 src 6]. H2's 30x likewise assumes 11K iops at an unstated queue depth.
4. **M11 "40-236x".** this assumes f = 1. by 1.2's own logic, capped dbs do ~10x fewer lookups. scope it to uncapped dbs bigger than ram until M22.
5. **M5 H4 tag.** the rate is gzip on base64 data. the fastq rate was not readable [external: arxiv.org/html/2308.08955].
6. **M20 H4 30x.** this is one run, and it includes the unexplained superlinear low-thread effect [repo: talk track section 6].
