# round 4 conclusion (tally of the three votes)

all three agents (eviction, storage, methodology) attacked each other's picks, retracted their weak ones, and voted. the votes converge.

| experiment | A (eviction) | B (storage) | C (methodology) | verdict |
|---|---|---|---|---|
| E1: probe-slot trace on S19 + big-db lookup-share profile + offline belady/lru/srrip/dedup/coverage | rank 1 | rank 1 | rank 1 | unanimous, run first |
| E2: amac / deeper interleaving over S16 (real wall-clock) | rank 2 | rank 3 | rank 2 | unanimous, the only real speedup shot, depends on E1 lookup share |
| E3: structbench linear vs line-aligned vs double hashing | rank 4 | rank 2 | rank 3 | 3/3 include it, thesis 2 characterisation |
| E4: batched dedup/partition prototype | rank 3 (if dedup >= 30%) | rank 4 (if dedup >= 25%) | rank 4 (if dedup >= 15%) | conditional on E1 |

dropped by consensus: sniper prefetch gate, fitted mlp model (zero degrees of freedom), 16-way simd cache, static hot set (kept only as a free table from E1), mphf/elias-fano for now, hardware policy sweeps (srrip/ship/hawkeye act on levels that see 0.2-0.5% of loads). cat sweep: only if root + resctrl are free.

corrections found during the debate:
- double hashing costs lines: 1.72 hit / 3.33 miss vs 1.07 / 1.32 for linear probing at load 0.70 (+61% / +152%), so predicted slower on big dbs unless every probe is prefetched. tell sir before B1.1.
- break-even h* = Tp/Td must use measured Td_eff after S16, not raw 90 ns dram.
- s2 entry is 24 bytes, a 4-way set is 96 B (1.5 lines), so the "one line per set" simd idea needed two lines.
- the old sniper "2x win" is a binary-lineage artifact and the hardware-assoc null is a one-slice cold-window null. neither speaks for luna.

honest expectation: E1 and E3 are guaranteed publishable characterisations (a belady bound; a priced double-hashing cost). E2 is the only realistic noteworthy positive (~30% chance of >=5% at 103GB, by the agents' own guess).

round 5 prerequisites nobody could verify: ssh to luna, S19 source + build, 8GB/16GB/50MB dbs, read files, perf permission, quiet machine.
