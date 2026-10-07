# kraken2 speedup, stage by stage

one file per stage, in the order they were built. each stage is a tree copied
from the previous one (or from stock, where noted) plus one patch script in
`plan_paper/scripts/s6plus/`. every file follows the same shape: what the code
was doing, what the issue was, what changed (real code, not paraphrased),
why the result is still correct, and the measured number.

S1 to S5 are earlier work, from before this round, and are **not** part of
this chain - this round started over from pristine stock kraken2 v2.17.1
(see `01_S06.md` for why).

| file | stage | kept in the final build (S19)? |
|---|---|---|
| [01_S06.md](01_S06.md) | S6 - revived the old 4-way cache | no - real effect traced to something else |
| [02_S07.md](02_S07.md) | S7 - S6 + batched prefetch | no - null result |
| [03_S08.md](03_S08.md) | S8 - stream all input files as one | **yes** |
| [04_S09.md](04_S09.md) | S9 - batched prefetch, no cache | **yes** |
| [05_S10.md](05_S10.md) | S10 - parallel hash-table load | **yes** |
| [06_S11.md](06_S11.md) | S11 - first scanner attempt | no - null result |
| [07_S12.md](07_S12.md) | S12 - remove divisions from the lookup | **yes** |
| [08_S13.md](08_S13.md) | S13 - memchr in the fastq parser | **yes** |
| [09_S14.md](09_S14.md) | S14 - huge pages for the table | **yes** |
| [10_S15.md](10_S15.md) | S15 - run-length hit counting | **yes** |
| [11_S16.md](11_S16.md) | S16 - pipelined prefetch | **yes** |
| [12_S17.md](12_S17.md) | S17 - rolling reverse-complement | **yes** |
| [13_S18.md](13_S18.md) | S18 - fixed a cpu stall in S11's own fix | **yes** |
| [14_S19.md](14_S19.md) | S19 - portability guards only | **yes** (final build) |

so the final chain actually is: **S0 (stock) + S8 + S9 + S10 + S12 + S13 +
S14 + S15 + S16 + S17 + S18 + S19**. S6, S7 and S11 were real attempts that
were tested and found to add nothing, and are left out on purpose - they are
still documented here because a tried-and-discarded idea is still a result.

the full combined report with every table in one place is
`plan_paper/s6_s15_speedup_report_2026-09-24.md`. these per-stage files exist
so each change can be read, cited, or questioned on its own.
