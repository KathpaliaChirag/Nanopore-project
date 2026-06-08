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

6. **Miss rates peak at 4-8T, dip 16-32T, then jump again at 64T** — Cache miss rate: 1T=34.21%, 4T=37.11%, 8T=37.07%, 16T=36.70%, 32T=36.23%, 64T=38.27%. LLC: same pattern. At 64T the sheer number of concurrent threads generates enough LLC pressure even within a short wall time to push miss rates back to their peak. The dip at 16-32T was a transitional phase.

7. **32T→64T: almost no benefit** — 1.045s → 1.001s, only 4% faster. Efficiency dropped from 65.7% to 34.3%. IPC crashed from 1.37 to 1.18.

8. **96T is slower than 64T** — 1.164s vs 1.001s. Adding 32 more threads actually hurt performance. Thread management overhead, cache thrashing, and DRAM contention on a single socket outweigh any parallelism gain. Sweet spot for hac × eskape_650mb on Luna single socket: **32T**. This matches the earlier profiling finding (Steps 1-51).

9. **IPC trend across all thread counts** — 1T: 1.47 → 2T: 1.46 → 4T: 1.45 → 8T: 1.43 → 16T: 1.41 → 32T: 1.37 → 64T: 1.18 → 96T: 1.13. Gradual decline until 32T, then steep drop at 64T+. The knee at 32T aligns with DRAM bandwidth saturation.

6. **cache-misses vs LLC-load-misses** — `cache-misses` was ~317M vs `LLC-load-misses` ~57M at 1T (5.6x difference). `cache-misses` includes speculative loads and prefetcher activity. `LLC-load-misses` counts only retired demand loads. We switched to LLC-load-misses as it reflects actual program-driven DRAM traffic.

---

## Database Size vs Classification (Luna, reads_hac, 1T)

10. **Cache cliff hit at eskape_human_4gb (3.8 GB)** — LLC miss rate jumped from 30.70% (eskape_650mb, 142MB) to 56.85% (eskape_human_4gb, 3.8GB). Cache miss rate from 34.21% to 78.04%. The 3.8 GB database cannot fit in LLC — nearly every hash table lookup goes to DRAM. This is the cache cliff the experiment is designed to locate.

11. **Classified% slightly higher with larger DB** — eskape_650mb: 65.28%, eskape_human_4gb: 66.13%. The 4GB DB includes the human genome so reads with human-like sequences now classify. Small absolute difference but consistent — larger DB = more reference sequences = more reads find a match.

12. **1T runtime increased only 35% despite 26x larger DB** — eskape_650mb: 21.981s, eskape_human_4gb: 29.818s. DB is 26x larger but only 35% slower. At 1T the bottleneck is sequential DRAM latency — the larger DB causes more misses per lookup but the single thread can only issue one lookup at a time anyway, so the increase is proportional to miss rate increase not DB size.

---

## Cross-Machine Comparison

*(to be filled after other machines are run)*

---

## Orion (Jetson) Notes

*(to be filled when Orion runs are done — ARM unified memory behavior expected to differ significantly)*
