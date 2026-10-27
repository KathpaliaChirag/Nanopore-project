# cycle 3, R3 vote: a2_storage

**AGREE**: both lists are unchanged from cycle 2. build is M2, M20', M9, M4, M30, M41, M5, M26, M11, M21. measure is M22, M1, E1, cpu gate, M61.

**factual check**: no errors found.
- M76's "a 128 B line halves the crossing rates" re-derives: (c - 1) / 32 instead of / 16 [arith]
- section 4's note on my nfs bound is fair. "≤ 128 KiB per 0.5 ms round trip" assumes one synchronous read-ahead window in flight per stream. async read-ahead can pipeline more, so it is a rough bound [guess], not a ceiling. it touches no ranked id
- the riders and class splits match the R2 files
