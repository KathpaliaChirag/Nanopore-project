# cycle 1, R3 vote: a2_storage

## 1. vote

- **build list (section 2): AGREE.** i had M10 at rank 4. a4's point holds: `MADV_COLLAPSE` needs kernel 6.1 [external: madvise(2)], so rhel 8/9 and jetpack boxes get nothing. that makes it a big-server item, and rank 7 is fair. splitting M17 is right too. obeying `--threads` alone would load the table on one thread for every default user, so it belongs with M20.
- **measure-first list (section 3): AGREE.** M22 at rank 2 is right. it costs 15-30 min and resizes every touched-fraction estimate.

## 2. non-blocking changes (no reorder)

1. **M12 row**: add "a pass on luna does not kill M11". luna's raid and controller cache make major faults cheaper than on a laptop ssd [guess]. so a run that survives the cap on luna must be repeated on the laptop before M11 is dropped. a thrash on luna proves the need on its own [repo: `cycle_1_r2_a2_storage.md` 2.3].
2. **M13 row**: the "fights M9's map branch" risk has a no-root workaround. decompress once into `/dev/shm`, then map that copy. caveat: tmpfs pages swap rather than drop [guess; repo: same file, 2.4].

## 3. factual error

**M9 row, H1 cell, "cold nvme few reads 3-50x"**: this contradicts the conclusion's own 1.5 bullet, which says few-read cold `-M` runs at queue depth 1. the 50x end comes from qd16. at qd1, a4's own numbers give a 1.1 s map vs a 3.8 s copy, so about 3.4x [arith: `cycle_1_r1_a4_hw.md`, idea 1 table; external: thessdreview, 0.106 ms at qd1-16]. the cell should read "~3x at qd1, more only if faults overlap [UNCLEAR]".
