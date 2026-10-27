# cycle 2, R3 vote: a2_storage

## vote

- **build list (section 2): AGREE.** i ranked M30 at 4 and M4 at 5. the borda order swaps them, and both are gated by cheap tests, so the order changes little. M27a inside M2 and M13 folded into M64 match what i asked for.
- **measure list (section 3): AGREE.** M60 riding inside E1 as a rider is fine. so are the qd1-vs-qd16 timing and the exit column.

## factual nit (no reorder)

- **M32's below-the-line reason** cites luna's 20.2 s vs 13.1-13.3 s pattern as evidence that a back-to-back run loses its huge pages. that 20.2 s run came right after a small-page binary [repo: `explanations/09_S14.md`], not during an overlapping teardown. the reasoning is plausible, but it is an analogy, so tag it [guess]. E1's exit column and a back-to-back pair with `thp_gb` logged would test it directly.

no other errors found. the numbers i can re-derive check out: M11 H5 111 GB / 131 MB/s ≈ 847 s [arith], M30 H1 1.13 s → 0.07 s ≈ 16x [arith], and the exit-tax scaling [external: lkml rfc].
