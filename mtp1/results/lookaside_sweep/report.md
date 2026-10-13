# Lookaside hierarchy sweep — full results

**Every one of the 60 configurations is slower than stock kraken2.** Penalties
run from **+3.74% to +28.09%**, and the configurations that cache *best* are the
ones that run *worst*.

| | |
|---|---|
| workload | `perpod5/pod5_2.fastq` — 151,591 reads, 499.98 Mbp, **160,625,038 lookups** |
| database | `eskape_32bit_fork` — 12.2 M cells, 8.90 M occupied, 48.8 MB, key_bits=26 value_bits=6 |
| grid | L3 ∈ {1,2,4,8,16} × L2 ∈ {1,2,4,8} × L1 ∈ {1,2,4} = **60**, plus stock |
| tiers | L1 4 KB, L2 256 KB, L3 4 MB — all resident, probed L1 → L2 → L3 → hash table |
| format | compact, 4 B/entry |
| flags | `-p 16 -g 2 -T 0` |
| method | **mean of 3 interleaved reps**; table-build cost measured separately and subtracted from every counter |
| runs | 304 (60 hit-rate, 61 load-only, 183 timed) |
| data | `hits.tsv`, `load.tsv`, `perf.tsv`, `sweep_meta.txt` |

Baseline: **2.886 s**, IPC 1.142, DRAM stall **23.9%** of cycles,
0.938 DRAM accesses per lookup, L3 miss 58.8%, MLP 1.240.

## Headline

| | |
|---|---|
| slower than stock | **60 / 60** |
| best | `l1=1,l2=1,l3=2` at **+3.74%** |
| worst | `l1=4,l2=4,l3=1` at **+28.09%** |
| correlation(hit rate, runtime penalty) | **+0.371** |
| rows claiming an impossible speedup | **0** |

The `ceiling` column is the physical bound: stock spends 23.9% of cycles
stalled on DRAM, so a table with hit rate *h* can save at most *h* × 23.9%.
Every row had a **−5.6% to −6.3% budget available and spent it going the wrong
way.** No row exceeds its ceiling, so unlike earlier sweeps on this machine the
measurement is internally consistent throughout.

## Collapsed by L3 associativity

| L3 ways | hit rate | mean (s) | vs stock | DRAM/lookup | MLP | IPC |
|---:|---:|---:|---:|---:|---:|---:|
| stock | — | 2.886 | — | 0.938 | 1.240 | 1.142 |
| 1 | 23.65% | 3.124 | **+8.25%** | 1.081 | 1.390 | 1.205 |
| 2 | 24.94% | 3.055 | **+5.88%** | 1.052 | 1.378 | 1.222 |
| 4 | 25.64% | 3.101 | **+7.47%** | 0.950 | 1.326 | 1.227 |
| 8 | 26.01% | 3.180 | **+10.18%** | 0.894 | 1.283 | 1.225 |
| 16 | 26.19% | 3.314 | **+14.83%** | 0.856 | 1.259 | 1.215 |

This is the core finding in five lines. As L3 ways rise:

- hit rate **improves** 23.65% → 26.19%
- DRAM accesses per lookup **improve** 1.081 → 0.856, crossing *below* stock's 0.938
- L3 miss rate **improves** 32.6% → 26.7%
- **runtime degrades** +8.25% → +14.83%

Every memory metric moves the right way and the program gets slower anyway. The
cost is instructions, not memory: MLP falls 1.390 → 1.259 as the probe chain
lengthens, and the extra tag comparisons land on the ~74% of lookups that miss
all three tiers and gain nothing.

## L1 and L2 associativity are dead parameters

Across an entire row the total hit rate moves **0.02 pp** (23.64% → 23.66%);
down a column it moves **2.54 pp**. L1 holds 1,024 entries and L2 holds 65,536
against 42.8 M distinct minimizers — their misses are **capacity** misses, and
associativity only recovers **conflict** misses. 48 of these 60 combinations are
functional duplicates of the 5 that differ.

## Stacking raises the hit rate — and that is the problem

| configuration | hit rate |
|---|---:|
| L3 alone, 1-way (single-tier sweep) | 22.35% |
| L3 alone, 16-way | 24.98% |
| **stacked L1+L2+L3, L3 16-way** | **26.19%** |

Per-tier split at the best point: L1 0.65% + L2 2.80% + L3 22.75%. L2 genuinely
earns its keep on hit rate. But the +1.2 pp the hierarchy adds over the best
single tier costs two extra sequential dependent probes on every miss, and that
trade is a large net loss.

## Fastest and slowest

| configuration | hit | mean (s) | vs stock | spread |
|---|---:|---:|---:|---:|
| `l1=1,l2=1,l3=2` | 24.93% | 2.994 | +3.74% | 0.017 |
| `l1=1,l2=1,l3=4` | 25.64% | 3.003 | +4.07% | 0.006 |
| `l1=2,l2=1,l3=1` | 23.64% | 3.003 | +4.08% | 0.044 |
| `l1=2,l2=2,l3=2` | 24.94% | 3.008 | +4.25% | 0.016 |
| `l1=2,l2=1,l3=2` | 24.93% | 3.016 | +4.52% | 0.048 |

| configuration | hit | mean (s) | vs stock | spread |
|---|---:|---:|---:|---:|
| `l1=1,l2=8,l3=16` | 26.19% | 3.380 | +17.12% | 0.038 |
| `l1=2,l2=8,l3=16` | 26.19% | 3.386 | +17.33% | 0.014 |
| `l1=4,l2=8,l3=8` | 26.01% | 3.404 | +17.95% | 0.415 |
| `l1=4,l2=8,l3=16` | 26.19% | 3.413 | +18.29% | 0.021 |
| `l1=4,l2=4,l3=1` | 23.66% | 3.696 | +28.09% | 1.892 |

## Full results — all 60

| L1 | L2 | L3 | hit | L1 | L2 | L3 | mean (s) | spread | vs stock | ceiling | DRAM/lk | L3 miss | MLP | IPC |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| — | — | stock | — | — | — | — | 2.886 | — | — | — | 0.938 | 58.8% | 1.240 | 1.142 |
| 1 | 1 | 1 | 23.64% | 0.65 | 2.66 | 20.33 | 3.024 | 0.068 | **+4.81%** | -5.65% | 1.068 | 32.6% | 1.410 | 1.183 |
| 2 | 1 | 1 | 23.64% | 0.67 | 2.64 | 20.33 | 3.003 | 0.044 | **+4.08%** | -5.65% | 1.056 | 32.6% | 1.398 | 1.201 |
| 4 | 1 | 1 | 23.64% | 0.68 | 2.63 | 20.33 | 3.051 | 0.118 | **+5.74%** | -5.65% | 1.067 | 32.6% | 1.408 | 1.207 |
| 1 | 2 | 1 | 23.65% | 0.65 | 2.74 | 20.26 | 3.115 | 0.378 ⚠ | **+7.96%** | -5.65% | 1.104 | 33.5% | 1.408 | 1.196 |
| 2 | 2 | 1 | 23.65% | 0.67 | 2.72 | 20.26 | 3.020 | 0.064 | **+4.67%** | -5.65% | 1.073 | 33.0% | 1.390 | 1.211 |
| 4 | 2 | 1 | 23.65% | 0.68 | 2.71 | 20.26 | 3.033 | 0.050 | **+5.11%** | -5.65% | 1.067 | 32.7% | 1.395 | 1.214 |
| 1 | 4 | 1 | 23.66% | 0.65 | 2.78 | 20.23 | 3.033 | 0.039 | **+5.11%** | -5.66% | 1.067 | 32.9% | 1.385 | 1.202 |
| 2 | 4 | 1 | 23.66% | 0.67 | 2.75 | 20.23 | 3.121 | 0.239 ⚠ | **+8.16%** | -5.66% | 1.071 | 33.0% | 1.381 | 1.206 |
| 4 | 4 | 1 | 23.66% | 0.68 | 2.75 | 20.23 | 3.696 | 1.892 ⚠ | **+28.09%** | -5.66% | 1.182 | 35.6% | 1.421 | 1.191 |
| 1 | 8 | 1 | 23.66% | 0.65 | 2.80 | 20.21 | 3.133 | 0.101 | **+8.58%** | -5.66% | 1.082 | 34.0% | 1.360 | 1.210 |
| 2 | 8 | 1 | 23.66% | 0.67 | 2.77 | 20.21 | 3.107 | 0.029 | **+7.68%** | -5.66% | 1.059 | 33.3% | 1.356 | 1.219 |
| 4 | 8 | 1 | 23.66% | 0.68 | 2.76 | 20.21 | 3.148 | 0.075 | **+9.08%** | -5.66% | 1.073 | 33.6% | 1.365 | 1.224 |
| 1 | 1 | 2 | 24.93% | 0.65 | 2.66 | 21.62 | 2.994 | 0.017 | **+3.74%** | -5.96% | 1.056 | 32.4% | 1.401 | 1.204 |
| 2 | 1 | 2 | 24.93% | 0.67 | 2.64 | 21.62 | 3.016 | 0.048 | **+4.52%** | -5.96% | 1.055 | 32.6% | 1.396 | 1.211 |
| 4 | 1 | 2 | 24.93% | 0.68 | 2.63 | 21.62 | 3.018 | 0.045 | **+4.57%** | -5.96% | 1.055 | 32.4% | 1.400 | 1.223 |
| 1 | 2 | 2 | 24.94% | 0.65 | 2.74 | 21.55 | 3.036 | 0.089 | **+5.21%** | -5.96% | 1.050 | 32.3% | 1.383 | 1.210 |
| 2 | 2 | 2 | 24.94% | 0.67 | 2.72 | 21.55 | 3.008 | 0.016 | **+4.25%** | -5.96% | 1.054 | 32.4% | 1.388 | 1.224 |
| 4 | 2 | 2 | 24.94% | 0.68 | 2.71 | 21.55 | 3.029 | 0.038 | **+4.97%** | -5.96% | 1.047 | 32.2% | 1.385 | 1.229 |
| 1 | 4 | 2 | 24.94% | 0.65 | 2.78 | 21.51 | 3.032 | 0.020 | **+5.08%** | -5.96% | 1.052 | 32.6% | 1.375 | 1.217 |
| 2 | 4 | 2 | 24.94% | 0.67 | 2.75 | 21.51 | 3.081 | 0.103 | **+6.76%** | -5.96% | 1.047 | 32.5% | 1.373 | 1.224 |
| 4 | 4 | 2 | 24.94% | 0.68 | 2.75 | 21.51 | 3.057 | 0.014 | **+5.93%** | -5.96% | 1.042 | 32.3% | 1.374 | 1.233 |
| 1 | 8 | 2 | 24.94% | 0.65 | 2.80 | 21.50 | 3.141 | 0.108 | **+8.85%** | -5.96% | 1.058 | 33.4% | 1.354 | 1.226 |
| 2 | 8 | 2 | 24.94% | 0.67 | 2.77 | 21.50 | 3.108 | 0.004 | **+7.69%** | -5.96% | 1.052 | 33.2% | 1.352 | 1.231 |
| 4 | 8 | 2 | 24.94% | 0.68 | 2.76 | 21.50 | 3.146 | 0.036 | **+9.03%** | -5.96% | 1.053 | 33.2% | 1.352 | 1.231 |
| 1 | 1 | 4 | 25.64% | 0.65 | 2.66 | 22.33 | 3.003 | 0.006 | **+4.07%** | -6.13% | 0.958 | 29.2% | 1.353 | 1.217 |
| 2 | 1 | 4 | 25.64% | 0.67 | 2.64 | 22.33 | 3.134 | 0.403 ⚠ | **+8.62%** | -6.13% | 0.932 | 28.5% | 1.338 | 1.230 |
| 4 | 1 | 4 | 25.64% | 0.68 | 2.63 | 22.33 | 3.042 | 0.007 | **+5.41%** | -6.13% | 0.942 | 28.7% | 1.344 | 1.227 |
| 1 | 2 | 4 | 25.64% | 0.65 | 2.74 | 22.25 | 3.195 | 0.363 ⚠ | **+10.73%** | -6.13% | 0.942 | 28.8% | 1.327 | 1.224 |
| 2 | 2 | 4 | 25.64% | 0.67 | 2.72 | 22.25 | 3.041 | 0.020 | **+5.38%** | -6.13% | 0.937 | 28.7% | 1.325 | 1.228 |
| 4 | 2 | 4 | 25.64% | 0.68 | 2.71 | 22.25 | 3.062 | 0.034 | **+6.10%** | -6.13% | 0.949 | 28.9% | 1.329 | 1.232 |
| 1 | 4 | 4 | 25.65% | 0.65 | 2.78 | 22.22 | 3.063 | 0.014 | **+6.16%** | -6.13% | 0.956 | 29.2% | 1.329 | 1.216 |
| 2 | 4 | 4 | 25.65% | 0.67 | 2.75 | 22.22 | 3.070 | 0.012 | **+6.38%** | -6.13% | 0.952 | 29.1% | 1.324 | 1.231 |
| 4 | 4 | 4 | 25.65% | 0.68 | 2.75 | 22.22 | 3.101 | 0.022 | **+7.47%** | -6.13% | 0.963 | 29.4% | 1.334 | 1.230 |
| 1 | 8 | 4 | 25.65% | 0.65 | 2.80 | 22.20 | 3.135 | 0.014 | **+8.63%** | -6.13% | 0.949 | 29.6% | 1.304 | 1.225 |
| 2 | 8 | 4 | 25.65% | 0.67 | 2.77 | 22.20 | 3.176 | 0.092 | **+10.07%** | -6.13% | 0.953 | 29.7% | 1.302 | 1.235 |
| 4 | 8 | 4 | 25.65% | 0.68 | 2.76 | 22.20 | 3.194 | 0.063 | **+10.68%** | -6.13% | 0.964 | 30.0% | 1.308 | 1.235 |
| 1 | 1 | 8 | 26.00% | 0.65 | 2.66 | 22.69 | 3.089 | 0.015 | **+7.05%** | -6.22% | 0.889 | 27.3% | 1.305 | 1.216 |
| 2 | 1 | 8 | 26.00% | 0.67 | 2.64 | 22.69 | 3.110 | 0.064 | **+7.79%** | -6.22% | 0.889 | 27.4% | 1.302 | 1.227 |
| 4 | 1 | 8 | 26.00% | 0.68 | 2.63 | 22.69 | 3.114 | 0.015 | **+7.92%** | -6.22% | 0.897 | 27.6% | 1.307 | 1.230 |
| 1 | 2 | 8 | 26.01% | 0.65 | 2.74 | 22.62 | 3.086 | 0.061 | **+6.93%** | -6.22% | 0.892 | 27.5% | 1.291 | 1.220 |
| 2 | 2 | 8 | 26.01% | 0.67 | 2.72 | 22.62 | 3.105 | 0.028 | **+7.59%** | -6.22% | 0.890 | 27.3% | 1.289 | 1.236 |
| 4 | 2 | 8 | 26.01% | 0.68 | 2.71 | 22.62 | 3.270 | 0.383 ⚠ | **+13.33%** | -6.22% | 0.889 | 27.5% | 1.287 | 1.241 |
| 1 | 4 | 8 | 26.01% | 0.65 | 2.78 | 22.58 | 3.168 | 0.051 | **+9.77%** | -6.22% | 0.902 | 27.9% | 1.284 | 1.212 |
| 2 | 4 | 8 | 26.01% | 0.67 | 2.75 | 22.58 | 3.161 | 0.008 | **+9.53%** | -6.22% | 0.895 | 27.7% | 1.276 | 1.223 |
| 4 | 4 | 8 | 26.01% | 0.68 | 2.75 | 22.58 | 3.179 | 0.009 | **+10.18%** | -6.22% | 0.902 | 27.8% | 1.285 | 1.228 |
| 1 | 8 | 8 | 26.01% | 0.65 | 2.80 | 22.57 | 3.233 | 0.039 | **+12.04%** | -6.22% | 0.895 | 28.5% | 1.259 | 1.211 |
| 2 | 8 | 8 | 26.01% | 0.67 | 2.77 | 22.57 | 3.236 | 0.020 | **+12.13%** | -6.22% | 0.900 | 28.7% | 1.258 | 1.228 |
| 4 | 8 | 8 | 26.01% | 0.68 | 2.76 | 22.57 | 3.404 | 0.415 ⚠ | **+17.95%** | -6.22% | 0.890 | 28.2% | 1.256 | 1.234 |
| 1 | 1 | 16 | 26.18% | 0.65 | 2.66 | 22.87 | 3.237 | 0.031 | **+12.19%** | -6.26% | 0.852 | 26.7% | 1.279 | 1.211 |
| 2 | 1 | 16 | 26.18% | 0.67 | 2.64 | 22.87 | 3.261 | 0.026 | **+13.02%** | -6.26% | 0.852 | 26.8% | 1.275 | 1.214 |
| 4 | 1 | 16 | 26.18% | 0.68 | 2.63 | 22.87 | 3.278 | 0.047 | **+13.58%** | -6.26% | 0.863 | 27.1% | 1.279 | 1.222 |
| 1 | 2 | 16 | 26.19% | 0.65 | 2.74 | 22.80 | 3.256 | 0.010 | **+12.82%** | -6.26% | 0.851 | 26.7% | 1.267 | 1.213 |
| 2 | 2 | 16 | 26.19% | 0.67 | 2.72 | 22.80 | 3.263 | 0.061 | **+13.08%** | -6.26% | 0.853 | 26.8% | 1.264 | 1.213 |
| 4 | 2 | 16 | 26.19% | 0.68 | 2.71 | 22.80 | 3.311 | 0.031 | **+14.75%** | -6.26% | 0.857 | 26.9% | 1.266 | 1.223 |
| 1 | 4 | 16 | 26.19% | 0.65 | 2.78 | 22.76 | 3.312 | 0.032 | **+14.76%** | -6.26% | 0.863 | 27.2% | 1.258 | 1.205 |
| 2 | 4 | 16 | 26.19% | 0.67 | 2.75 | 22.76 | 3.312 | 0.015 | **+14.79%** | -6.26% | 0.852 | 27.0% | 1.252 | 1.215 |
| 4 | 4 | 16 | 26.19% | 0.68 | 2.75 | 22.76 | 3.356 | 0.064 | **+16.30%** | -6.26% | 0.861 | 27.1% | 1.256 | 1.214 |
| 1 | 8 | 16 | 26.19% | 0.65 | 2.80 | 22.75 | 3.380 | 0.038 | **+17.12%** | -6.26% | 0.860 | 27.7% | 1.237 | 1.212 |
| 2 | 8 | 16 | 26.19% | 0.67 | 2.77 | 22.75 | 3.386 | 0.014 | **+17.33%** | -6.26% | 0.853 | 27.4% | 1.234 | 1.218 |
| 4 | 8 | 16 | 26.19% | 0.68 | 2.76 | 22.75 | 3.413 | 0.021 | **+18.29%** | -6.26% | 0.860 | 27.7% | 1.237 | 1.224 |

⚠ marks a spread above 0.2 s across the 3 reps. This machine is bimodal under
the `powersave` governor (the same binary lands at either ~2.9 s or ~3.4 s
depending on frequency state), so those rows carry extra uncertainty. They are
all in the slower direction, so they do not affect the conclusion.

## Reproducing

```bash
D=databases/eskape_32bit_fork
perf stat -e cycles,instructions,cycle_activity.stalls_l3_miss,LLC-loads,\
LLC-load-misses,l1d_pend_miss.pending,l1d_pend_miss.pending_cycles \
  scratch_lookaside/bin/classify_hier \
    -H $D/hash.k2d -t $D/taxo.k2d -o $D/opts.k2d -p 16 -g 2 -T 0 \
    -L l1=1,l2=1,l3=4 -F compact \
    -A scratch_lookaside/out/pod5_2_8M.prof -Z \
    perpod5/pod5_2.fastq > /dev/null
```

> **Flags since removed.** The `-A <profile>` and `-Z` options used in this
> command no longer exist — they were deleted on 2026-08-30 once runtime
> learning (`-Y`) replaced the oracle. The command is kept as the record of
> how these numbers were produced; it will not run against the current
> `classify_learn`. See `CHANGELOG.md`.


`-A` supplies the frequency profile that fills the tiers — an **oracle**, built
by counting minimizer frequency on the very file being classified. Not
deployable; it measures the ceiling. Since even the cheating version loses by
this margin, no realistic fill policy can win. That was confirmed directly: a
runtime-learning implementation (`-Y always|second|promote`, binary
`classify_learn`) reaches **12.25%** where the oracle reaches 29.54% on the same
geometry — 41% of the achievable hits.

## Conclusion

A multi-level minimizer→taxon lookaside hierarchy is not merely unhelpful on
this workload — it is **actively harmful, and harmful in proportion to how well
it caches**. The idea is closed by measurement.

The remaining levers are unchanged: shrink the database below L3 (`-M 4000000`,
**−26.7%** measured), give it huge pages (41–53% of cycles sit in 4 KB page
walks), and overlap its misses (MLP is 1.24 of ~12).
