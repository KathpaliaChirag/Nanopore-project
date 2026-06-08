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

## Database Size vs Classification (Luna, reads_hac, standard_8gb, 1T)

25. **Classified% jumps to 95.77% with standard_8gb** — eskape_650mb: 65.28%, eskape_human_4gb: 66.13%, standard_8gb: 95.77%. The standard database has comprehensive taxonomic coverage across bacteria, viruses, and human — nearly all nanopore reads find a match. The ESKAPE databases only covered a narrow set of pathogens.

26. **LLC miss rate converges to cache miss rate at standard_8gb** — both are ~76.6% at 1T. With eskape_650mb they diverged by 4 points (cache 34% vs LLC 30%) and with eskape_human_4gb by ~21 points (cache 78% vs LLC 57%). With a 7.6 GB DB, every LLC access — speculative, prefetcher-driven, or demand — misses because the random hash table access pattern defeats the hardware prefetcher entirely. No differentiation left between access types.

27. **IPC 2.11 at standard_8gb 1T — surprisingly high despite 76% LLC miss rate** — but sys time is 4.3s vs ~2s for smaller DBs. The perf counters capture the full process including DB loading from disk, which is likely more sequential/cache-friendly and inflates IPC. The classification phase IPC is probably lower; this number is not directly comparable to the other DBs.

28. **Amdahl's law visible in standard_8gb thread scaling** — sys time ~4.2s is sequential DB loading that does not parallelize. This is ~25% of 1T wall time (16.778s). Wall-time speedup at 2T: 1.59x (79.4%). But classification-phase-only speedup: ~1.96x — the classification itself still scales well. The fixed DB loading overhead will cap wall-time speedup no matter how many threads are used: even with instant classification, wall time cannot drop below ~4.2s, so the maximum possible speedup is 16.778/4.2 ≈ 4.0x. This is a real practical limit for standard_8gb on Luna.

29. **Classification phase scales near-perfectly to 8T on standard_8gb** — 4T classification speedup: 3.92x (~98%), 8T: 7.99x (~100%). Despite 82% LLC miss rate, the classification work itself parallelizes almost ideally. The DRAM bandwidth is not yet saturated for the classification phase alone at 8T — the high miss rate means more DRAM traffic per thread but the memory bus can still handle it. The wall-time speedup (2.87x at 8T) is misleading — the bottleneck is purely the serial DB loading, not thread scaling or DRAM bandwidth.

30. **LLC miss rate climbing faster than other DBs** — standard_8gb: 1T=76.59%, 2T=77.78%, 4T=79.60%, 8T=82.32% — a 5.7 point rise across 3 doublings. eskape_human_4gb rose only 2.4 points (56.85%→59.27%) over the same range. With a larger DB and higher baseline miss rate, each additional thread generates more DRAM contention with less LLC to absorb it.

31. **Amdahl ceiling fully hit at 16-32T for standard_8gb** — 16T wall: 5.096s, 32T wall: 4.830s — only 0.27s difference from doubling threads. At 32T, Kraken2 classification finishes in ~0.69s but wall time is 4.83s because ~4.7s of sys time (DB loading) cannot be parallelized. This is qualitatively different from the bandwidth wall seen with smaller DBs — here the bottleneck is purely sequential I/O, not DRAM bandwidth.

32. **LLC miss rate dip at 16-32T universal across all DBs** — eskape_650mb: 32.26%→30.53%, eskape_human_4gb: 59.34%→59.03%, standard_8gb: 83.34%→82.90%. All three DBs show the same slight retreat at this thread count. Likely the same mechanism: at 32T the classification finishes so fast that steady-state cache pressure never fully builds, slightly improving measured hit rate.

33. **96T slower than 64T for both wall and classification time on standard_8gb** — wall: 5.119s vs 4.949s; Kraken2 classification: 0.943s vs 0.802s. For eskape_650mb and eskape_human_4gb, 96T was slower only in wall time (the classification was just dominated by overhead). Here, the classification phase itself is slower at 96T — thread spawn/join overhead and cache contention from 96 threads competing on a single socket hurts the actual compute.

34. **Wall speedup ceiling for standard_8gb: ~3.5x (32T)** — across all three DBs the practical limit differs entirely: eskape_650mb peaks at ~22x (64T), eskape_human_4gb at ~10.6x (64T), standard_8gb at ~3.5x (32T). The different mechanisms: eskape_650mb is DRAM-bandwidth-limited, eskape_human_4gb is also bandwidth-limited but more severely, standard_8gb is Amdahl-limited by DB loading overhead.

---

## Database Size vs Classification (Luna, reads_hac, standard_16gb, 1T+2T)

35. **Classified% reaches 97.77% with standard_16gb** — standard_8gb: 95.77%, standard_16gb: 97.77%. Another 2-point gain from doubling the DB size. Diminishing returns — going from 650mb to 4gb added ~1%, 4gb to 8gb added ~30%, 8gb to 16gb adds ~2%. The standard DB at 8gb already captured most classifiable reads.

36. **LLC miss rate 80.15% at 1T — only 3.5 points higher than standard_8gb** — standard_8gb was 76.59%, standard_16gb is 80.15%. The DB is twice as large but LLC miss rate barely moved. Both DBs are far above the LLC capacity; the incremental miss rate impact of doubling an already-uncacheable DB is small.

37. **sys time jumped to ~7.5s from ~4.2s for standard_8gb** — consistent with ~2x larger DB loading from disk. This is the serial non-parallelizable component. Amdahl ceiling for standard_16gb: 23.914 / 7.5 ≈ 3.19x — lower than standard_8gb's ~4.0x ceiling. The extra DB loading overhead directly raises the wall time floor.

38. **1T wall time 23.914s vs 16.778s for standard_8gb** — 7.1s longer, mostly explained by the ~3.3s extra sys time (DB loading). Classification phase itself (wall minus sys) is roughly similar: ~16.4s here vs ~12.5s for standard_8gb — slightly longer due to higher LLC miss rate.

39. **2T speedup only 1.51x vs 1.59x for standard_8gb** — the lower 2T speedup is explained purely by Amdahl: with 7.5s serial overhead instead of 4.2s, even perfect classification parallelism yields less wall speedup. Classification phase speedup at 2T: (23.914-7.5) / (15.827-7.4) ≈ 16.4 / 8.4 ≈ 1.95x — near-perfect. The wall time bottleneck is serial DB loading, not thread scaling.

40. **IPC 1.86 at 1T — lower than standard_8gb's 2.11** — despite standard_16gb having a larger sys time contribution (which is usually cache-friendly sequential I/O and inflates IPC), the overall IPC is lower. The higher LLC miss rate (80% vs 76%) during the classification phase outweighs the sys-time inflation effect.

41. **LLC miss rate climbs sharply 1T→8T: 80.15%→86.04%** — a 5.9-point rise across 3 doublings. standard_8gb rose 5.7 points (76.59%→82.32%) over the same range. Very similar rate of climb despite the larger DB — both are equally past the LLC capacity, and more threads cause the same proportional increase in DRAM contention.

42. **Wall speedup approaching Amdahl ceiling by 8T: 2.49x out of ~3.19x max** — at 8T the classification finishes in ~2.2s but wall time is 9.6s because ~7.5s of sys time (DB loading) is serial. We have only ~0.7x of headroom left before hitting the ceiling, and there are still 16T, 32T, 64T, 96T runs ahead. The Amdahl ceiling will be fully hit earlier than standard_8gb.

43. **Classification phase still scales near-ideally to 8T** — classification time at 4T: ~4.3s (3.81x speedup, 95.3% efficiency); at 8T: ~2.2s (7.56x speedup, 94.5% efficiency). The thread scaling of the compute work itself is excellent — the wall time bottleneck is entirely the serial DB load, not DRAM bandwidth or thread overhead.

44. **Amdahl ceiling essentially hit at 32T: 2.93x out of ~3.19x max** — wall time 8.153s vs theoretical minimum of ~7.5s (sys time). 16T: 2.79x, 32T: 2.93x — only 0.14x gain from doubling threads. Classification itself finishes in ~0.8s at 32T; the run is 92% sys time. 64T and 96T will add essentially nothing to wall speedup.

45. **LLC miss rate dip at 32T holds for standard_16gb** — 8T: 86.04%, 16T: 85.73%, 32T: 85.03%. The same slight retreat seen on all three previous DBs (eskape_650mb, eskape_human_4gb, standard_8gb). Universal pattern confirmed: the 16-32T dip is consistent regardless of DB size or absolute miss rate level.

46. **Classification phase efficiency degrades at 32T: 63.9%** — kraken2-reported processing time: 1T=16.49s, 8T=2.29s (7.2x/89.9%), 16T=1.24s (13.3x/83.4%), 32T=0.81s (20.5x/64%). The classification work starts hitting DRAM bandwidth limits between 16T and 32T — this is separate from the Amdahl wall. At standard_8gb the classification phase scaled well to 32T; at standard_16gb with higher miss rates the bandwidth ceiling is lower.

47. **Peak wall speedup at 32T: 2.93x — 64T and 96T both regress** — 32T=8.153s (2.93x), 64T=8.253s (2.90x), 96T=8.385s (2.85x). Unlike the bandwidth-limited DBs where 64T was the peak, standard_16gb peaks at 32T. The mechanism is different: the Amdahl floor means classification is already done in ~0.8s at 32T; adding more threads only increases OS overhead (thread creation, context switches), which shows up as growing sys time (32T: 7.86s, 64T: 8.38s, 96T: 9.05s).

48. **sys time grows with thread count at 64T+** — 32T: 7.86s, 64T: 8.38s, 96T: 9.05s. The sys time is not a fixed constant — spawning 64-96 threads adds measurable OS overhead to the DB loading phase. This raises the effective Amdahl floor at high thread counts and explains why 64T and 96T are slower than 32T in wall time.

49. **IPC crashes at 64T: 1.43 (down from 1.67 at 32T)** — at 32T the classification finishes in 0.8s and the CPU spends most of the measured time in the sys/overhead phase. By 64T with 96T, IPC 1.37 — the perf counters mostly capture thread management and OS work, not meaningful Kraken2 classification. These IPC values are not directly comparable to the lower-thread-count values which captured more actual classification work.

50. **LLC miss rate dip at 32T holds, then essentially flat 32T→96T** — 8T: 86.04%, 16T: 85.73%, 32T: 85.03%, 64T: 85.04%, 96T: 84.93%. The universal 16-32T dip appears again. Post-32T the rate is flat — the DB is so far above LLC capacity that DRAM pressure from classification barely changes once the classification time is sub-second.

51. **standard_16gb thread scaling summary vs standard_8gb** — standard_8gb peak: 3.47x at 32T; standard_16gb peak: 2.93x at 32T. Both Amdahl-limited with the same peak thread count, but standard_16gb's larger DB loading adds ~3.3s to the serial floor, cutting the ceiling from 4.0x to 3.19x. The classified% gain (95.77%→97.77%) costs ~0.54x of maximum achievable speedup.

---

## Cross-Machine Comparison

*(to be filled after other machines are run)*

---

## Orion (Jetson) Notes

*(to be filled when Orion runs are done — ARM unified memory behavior expected to differ significantly)*
