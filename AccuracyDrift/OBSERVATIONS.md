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

13. **2T scaling stays strong even post-cache-cliff** — eskape_human_4gb 2T: 1.87x speedup (93.5% efficiency) vs eskape_650mb 2T: 1.97x (98.5%). Despite LLC miss rate nearly doubling (57% vs 31%), two threads still scale close to linearly. At just 2 threads, DRAM bandwidth is not yet saturated even with a 3.8 GB DB. The cliff affects latency per access but not bandwidth headroom at low thread counts.

14. **IPC unchanged from 1T to 2T on eskape_human_4gb** — stays at 1.25 for both 1T and 2T. Contrast with eskape_650mb where IPC dropped from 1.47 (1T) to 1.46 (2T). Post-cliff, the CPU is already spending so much time waiting on DRAM at 1T that adding a second thread does not change the per-instruction stall profile — both threads stall on DRAM independently.

15. **Efficiency collapse at 4T post-cliff vs pre-cliff** — eskape_650mb 4T: 3.85x (96.3% efficiency). eskape_human_4gb 4T: 3.33x (83.2%). A 13-point efficiency gap at just 4 threads. With LLC miss rate at 58%, each thread generates far more DRAM requests than with the smaller DB — bandwidth saturation kicks in sooner, and scaling ceiling will be lower across the board.

16. **LLC miss rate climbing steadily with threads (eskape_human_4gb)** — 1T: 56.85%, 2T: 57.44%, 4T: 58.41%, 8T: 59.27%. Consistent ~0.5-1% climb per doubling of threads. On eskape_650mb the same metric was flat (30.70% → 31.49% → 32.09% → 32.26%). The post-cliff DB is sensitive to thread count: more threads = more concurrent DRAM inflight = higher measured miss rate as the DRAM queue stays full.

17. **Efficiency gap widens rapidly past 4T** — eskape_650mb vs eskape_human_4gb efficiency at each thread count: 2T=98.5% vs 93.5% (5pt gap), 4T=96.3% vs 83.2% (13pt gap), 8T=92.1% vs 67.9% (24pt gap), 16T=84.1% vs 49.5% (35pt gap). The gap keeps growing. On the larger DB, DRAM bandwidth is the dominant bottleneck — the scaling ceiling is well below the 32T sweet spot seen with eskape_650mb.

18. **LLC miss rate plateaus at 8-16T for eskape_human_4gb** — 8T: 59.27%, 16T: 59.34% — essentially no change. Contrast with 1T→8T where it climbed from 56.85% to 59.27%. The DRAM is fully saturated from 8T onward: every LLC load is a miss, there is no headroom left. On eskape_650mb this plateau never appeared in the same range — miss rate even dipped at 16T. The difference reveals how completely the larger DB overwhelms the LLC.

19. **Efficiency below 50% at 16T post-cliff** — 7.93x out of possible 16x. For eskape_650mb, efficiency did not drop below 50% until somewhere past 32T. The cache cliff effectively halves the useful thread count: the bandwidth wall hits at ~8T instead of ~32T.

20. **LLC miss rate dip at 16-32T is consistent across both DBs** — eskape_650mb: 32.26% (8T) → 31.31% (16T) → 30.53% (32T). eskape_human_4gb: 59.27% (8T) → 59.34% (16T) → 59.03% (32T). Both show the same slight retreat at 32T despite the absolute values being completely different. Likely a measurement artifact: at higher thread counts the run completes faster, so the perf counters capture less steady-state cache pressure per unit time.

21. **16T→32T gain only 26% on eskape_human_4gb** — speedup goes 7.93x → 10.02x. On eskape_650mb the same doubling went 13.45x → 21.03x (56% gain). The post-cliff DRAM bandwidth wall completely kills the benefit of adding threads beyond 16. IPC dropped from 1.21 to 1.16 — threads are spending more time stalled, not executing.

22. **Scaling ceiling ~10.6x for eskape_human_4gb vs ~22x for eskape_650mb** — 32T: 10.02x, 64T: 10.57x, 96T: 10.12x — essentially flat. The maximum achievable speedup on Luna is halved by the cache cliff. Post-cliff, DRAM bandwidth is the hard ceiling; more threads cannot overcome it.

23. **96T slower than 64T on both DBs** — eskape_650mb: 1.001s (64T) vs 1.164s (96T). eskape_human_4gb: 2.823s (64T) vs 2.947s (96T). The pattern is consistent across DB sizes. On a single socket, 96 threads generate more overhead (scheduler contention, cache line sharing, NUMA effects) than they contribute. 64T is the practical thread ceiling for Luna single-socket Kraken2 runs.

24. **IPC drops below 1.0 at 96T post-cliff** — 0.98 IPC means the CPU is stalling for more than one cycle per instruction executed on average. This is the clearest signature of a memory-bound workload at its limit — the pipeline is almost entirely idle, waiting on DRAM. At eskape_650mb 96T, IPC was 1.13 — still above 1.0, meaning some useful execution was still happening between stalls.

---

## Cross-Machine Comparison

*(to be filled after other machines are run)*

---

## Orion (Jetson) Notes

*(to be filled when Orion runs are done — ARM unified memory behavior expected to differ significantly)*
