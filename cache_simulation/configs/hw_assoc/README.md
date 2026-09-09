# Hardware LLC associativity sweep configs

Six tiny overlay configs, each loaded AFTER `luna.cfg` (which itself loads after
`address_translation_schemes/baseline`), so the invocation for each is:

```
./run-sniper -c address_translation_schemes/baseline -c luna -c hw_assoc/luna_assocN ...
```

Each overrides ONLY `[perf_model/nuca]` (Luna's real, physically-shared LLC, modeled as
per-core NUCA slices) - `cache_size`, `associativity`, `address_hash`. Everything else
(core frequency, L1i, L1d, L2, DRAM) stays at Luna's real measured values from `luna.cfg`.

This is the counterpart to every associativity experiment run so far in this project:
those all varied the **software S2 lookup cache's** width (1/4/8/16-way) while holding
real hardware fixed. This sweep does the opposite - holds the software side fixed at
"no cache" (base kraken2, the `S0` binary, no S2 at all) and varies the **real hardware
LLC's own associativity** instead. Directly answers: does hardware cache associativity,
independent of any software cache, matter to kraken2's own access pattern?

## Why these six values

Per-core NUCA slice size is fixed at Luna's real 1125 KB (1200 sets * 15-way * 64B,
see `luna.cfg`'s own derivation notes) - `total_blocks = 1152000 bytes / 64B = 18000`.
Associativity values below were chosen because 18000 divides evenly for each of them
(Sniper aborts rather than rounding if `size != sets * ways * blocksize`), so no
approximation/rounding was needed anywhere in this sweep (unlike the original 1120KB ->
1125KB derivation in `luna.cfg`, which did need a small rounding step):

| Associativity | Sets (18000 / assoc) | Note |
|---|---|---|
| 1-way  | 18000 | direct-mapped extreme |
| 4-way  | 4500  | matches the software-cache sweep's low end |
| 8-way  | 2250  | matches the software-cache sweep's mid point |
| 15-way | 1200  | Luna's REAL measured value (sysfs, see `luna.cfg`) - the control |
| 16-way | 1125  | matches the software-cache sweep's high end |
| 30-way | 600   | 2x Luna's real value, upper extreme |

None of these set counts are a power of 2, so all six configs use `address_hash = mod`
(same reasoning as `luna.cfg`'s own header comment: `xor_mod` only stays in-bounds when
`sets` is a power of 2).

## Workload

Run against the fast 50-read workload (50MB DB) for quick turnaround (~3 min/run based
on the fair-batch precedent), not the slow 2000-read workload - this is a hardware-only
sweep meant to isolate one variable cheaply, not a scale study.
