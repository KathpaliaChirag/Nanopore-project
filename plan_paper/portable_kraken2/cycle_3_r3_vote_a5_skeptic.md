# cycle 3 R3 vote: a5_skeptic

**AGREE: both lists are unchanged from cycle 2.**

two small fixes, no reorder:
1. **H2 "dorado idle" (section 2).** BWLOCK++ measured cpu traffic slowing *gpu* kernels [external: arxiv 1712.08738]. the risk named here is the reverse: dorado on the gpu slowing kraken2 on the cpu. no source has measured that direction [UNCLEAR]. say so, so the 4x is not read as a kraken2 number.
2. **M91's "0.29%".** it is gprof self time for `ResolveTree` plus `IsAAncestorOfB` (0.08 + 0.23 s of 105.86 s) [arith on repo]. gprof's denominator leaves out kernel time [repo: `dorado-kraken-research/README.md` 8e], and that was the WSL2 run. tag it "user time only, one old run".
