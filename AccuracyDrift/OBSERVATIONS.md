# AccuracyDrift Observations

Running list of interesting findings as data comes in. Organized by theme.

---

## Thread Scaling (Luna, reads_hac, eskape_650mb)

Corrected data uses LLC-load-misses / LLC-loads (retired demand loads only). Earlier runs used cache-misses / cache-references which was ~5.6x inflated due to speculative and prefetch activity.

1. **Near-perfect linear speedup at low thread counts** — 1T=21.981s, 2T=11.136s = 1.97x (98.5% efficiency), 4T=5.701s = 3.85x (96.3%), 8T=2.981s = 7.37x (92.1%), 16T=1.634s = 13.45x (84.1%). Still good but degrading as memory bandwidth fills up.

2. **LLC miss rate climbs with threads then dips at 16T** — 1T: 30.70%, 2T: 31.49%, 4T: 32.09%, 8T: 32.26%, 16T: 31.31%. Peaks at 8T and drops at 16T — same pattern seen with old metric. Likely noise or a real effect where shorter wall time means less total LLC pressure. Watch at 32T+.

3. **User time stays constant across thread counts** — ~21.7s to ~22.6s user time regardless of thread count. Wall time scales down. Confirms true parallelism with negligible synchronization overhead.

4. **IPC declines steadily with thread count** — 1T: 1.47, 2T: 1.46, 4T: 1.45, 8T: 1.43, 16T: 1.41. More threads = more concurrent DRAM stalls = lower IPC. Will likely drop faster at very high thread counts.

5. **Speedup efficiency degrading** — 2T: 98.5%, 4T: 96.3%, 8T: 92.1%, 16T: 84.1%, 32T: 65.7%. Big jump in degradation between 16T and 32T — confirms DRAM bandwidth fully saturated. Adding more threads past 32T will likely yield diminishing returns.

6. **Both miss rate metrics peak at 4-8T then decline** — Cache miss rate: 1T=34.21%, 4T=37.11%, 8T=37.07%, 16T=36.70%, 32T=36.23%. LLC miss rate: 1T=30.70%, 4T=32.09%, 8T=32.26%, 16T=31.31%, 32T=30.53%. At high thread counts, wall time shrinks so fast that total cache pressure per run decreases even though per-thread pressure is high.

6. **cache-misses vs LLC-load-misses** — `cache-misses` was ~317M vs `LLC-load-misses` ~57M at 1T (5.6x difference). `cache-misses` includes speculative loads and prefetcher activity. `LLC-load-misses` counts only retired demand loads. We switched to LLC-load-misses as it reflects actual program-driven DRAM traffic.

---

## Database Size vs Classification (Luna, reads_hac)

*(to be filled as runs complete)*

---

## Cross-Machine Comparison

*(to be filled after other machines are run)*

---

## Orion (Jetson) Notes

*(to be filled when Orion runs are done — ARM unified memory behavior expected to differ significantly)*
