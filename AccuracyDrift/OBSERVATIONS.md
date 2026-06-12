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

## Species Breakdown (Luna, reads_hac, 32T)

52. **Sample is a polymicrobial infection dominated by P. aeruginosa** — standard DBs confirm: P. aeruginosa ~35%, E. coli ~16%, K. pneumoniae ~5%, Pseudomonas sp. p1(2021b) ~2%, human background ~0.7%. Classic nosocomial (hospital-acquired) profile — P. aeruginosa + E. coli + K. pneumoniae together is typical of ICU patients (ventilator-associated pneumonia, catheter UTI) or cystic fibrosis lung infection. All three are ESKAPE pathogens.

53. **eskape_650mb inflates P. aeruginosa count by ~33k false positives** — eskape_650mb classifies 68,493 reads as P. aeruginosa, but standard DBs show only ~35,193 true Pseudomonas reads. The ~33,300 difference are E. coli and K. pneumoniae reads that share conserved k-mers with the P. aeruginosa reference — with no competing reference in the small DB, they get forced to P. aeruginosa. This is a fundamental limitation of narrow reference DBs: they inflate the dominant species count by absorbing reads from absent species.

54. **eskape_650mb unclassified (34.72%) are mostly the E. coli and K. pneumoniae reads** — ~36k reads unclassified in eskape DBs. Standard_8gb classifies 31,988 more reads than eskape_650mb, almost exactly accounting for E. coli (15,159) + K. pneumoniae (4,739) + misc species. These reads found no k-mer match in the small eskape DB at all, or were partially absorbed as false P. aeruginosa.

55. **eskape_human_4gb adds only human reads over eskape_650mb** — 1,344 human reads (1.28%) newly classified. E. coli and K. pneumoniae still undetected — the 4gb DB adds the human genome but still has no E. coli/K. pneumoniae references. The 0.41% gain in overall classified% (65.28% → 66.13%) is entirely human DNA.

56. **Massive long tail in standard DBs — ~40% of reads in sub-1% species each** — standard_8gb: 42.60% of all reads (44,695) classify to species each under 1%. Standard_16gb reduces this to 37.14% (38,965) by resolving more ambiguous reads. This long tail is real biological diversity in the sample — many low-abundance organisms — not noise.

57. **standard_16gb increases all major species counts over standard_8gb** — P. aeruginosa: +4,417, E. coli: +2,191, K. pneumoniae: +1,035. The 16gb DB has more strain references, pulling reads that were ambiguous in 8gb into known species. The long tail shrinks by ~5,730 reads correspondingly.

58. **Phikmvvirus LKD16 present in standard DBs (~0.08%)** — a bacteriophage that specifically infects P. aeruginosa. Its presence confirms active phage predation on the dominant pathogen in the sample. Not detectable with eskape DBs (no phage references).

---

## Sample-Targeted DB (50 MB, Luna, reads_hac)

59. **LLC miss rate 10.19% at 1T — 3x lower than eskape_650mb** — the 50 MB hash table fits deep inside the LLC. Every hash lookup is served from cache. Compare: eskape_650mb (150 MB) = 30.70%, eskape_human_4gb (3.8 GB) = 56.85%. This is the lowest LLC miss rate in the experiment and confirms the cache cliff is between 50 MB and 150 MB on Luna.

60. **sample_targeted is faster than eskape_650mb at 1T despite classifying more reads** — 19.73s vs 21.98s. More reads classified (84.80% vs 65.28%) but faster overall because each hash lookup costs far less time (cache hit vs DRAM fetch). Lower miss rate outweighs higher classification count.

61. **Classified% 84.80% — far better than eskape_650mb (65.28%) with a smaller DB** — the 50 MB targeted DB classifies 19.52 percentage points more reads than the 150 MB eskape DB. The eskape DB had correct P. aeruginosa references but lacked E. coli and K. pneumoniae. A targeted DB with the right species beats a generic narrow DB of 3x the size.

62. **sys time ~0.21s — essentially no Amdahl overhead** — the 50 MB DB loads in milliseconds. Contrast: standard_8gb = 4.2s sys, standard_16gb = 7.5s sys. Thread scaling for sample_targeted will be limited only by DRAM bandwidth (similar to eskape_650mb pattern), not DB loading. Expect near-linear scaling up to the bandwidth wall.

63. **Cache cliff confirmed: between 50 MB and 150 MB on Luna** — sample_targeted (50 MB) = 10.19% LLC miss, eskape_650mb (150 MB) = 30.70% LLC miss. The LLC is larger than 50 MB but smaller than 150 MB on this machine (or more precisely, the working set of Kraken2's hash table access pattern exceeds LLC capacity somewhere in this range). This is the tightest bracket we have on the cliff location.

---

## Cross-Machine Comparison

### Luna vs Orion — reads_hac × sample_targeted (50 MB DB) × 1T

#### 1. Cache architecture difference — why cache-miss% diverges but LLC miss% is the right metric

The 0.643% cache miss rate on Orion vs 7.23% on Luna is not evidence that Orion has better cache behavior — it is a measurement artifact from the different perf event mappings on each architecture.

On Luna (x86 Sapphire Rapids), `cache-references` maps to LLC accesses and `cache-misses` maps to LLC misses. The denominator is LLC-level loads — a relatively small count of requests that already survived L1 and L2. A 7.23% miss rate there means 7.23% of LLC accesses went to DRAM.

On Orion (ARM Cortex-A78AE), `cache-references` maps to L1D accesses — every single data memory instruction. The denominator is roughly all memory operations. Most of these hit L1 or L2, so the miss rate looks tiny (0.643%) even though the last-level cache is being hammered. The ~47 billion cache-references on Orion vs Luna's LLC-level counts are measuring completely different things.

The correct cross-machine metric is LLC-load-misses / LLC-loads: both architectures expose this as demand-load traffic to the last-level cache. On Luna this is 10.19%. On Orion it is 78.92%. That 7.7x difference in LLC miss rate is the real signal, and it explains most of the performance gap.

#### 2. Cache cliff location — where Orion crosses its cliff

Luna's SLC per socket is ~105 MB. The cliff (LLC miss rate jumps sharply) lands between 50 MB and 150 MB — sample_targeted (50 MB) = 10.19%, eskape_650mb (150 MB) = 30.70%.

Orion's SLC is ~4 MB. The 50 MB sample_targeted DB is already 12.5x larger than the SLC. With a 78.92% LLC miss rate at 50 MB, Orion is not approaching the cliff — it cleared the cliff well before 50 MB. The cliff on Orion is somewhere below 4 MB, likely between 1 MB and 4 MB given the SLC size and the fact that a Kraken2 hash table has a random-access pattern that rarely reuses the same cache line.

The practical consequence: every database in the AccuracyDrift experiment — sample_targeted, eskape_650mb, eskape_human_4gb, standard_8gb, standard_16gb — will run post-cliff on Orion. There is no "pre-cliff" regime to observe on Orion at any of the planned DB sizes. Luna's pre-cliff behavior (fast, low-latency hash lookups, near-linear thread scaling with high efficiency) does not have an Orion equivalent.

#### 3. Speed difference — quantifying LLC miss rate vs raw hardware contribution

Orion 1T: 47.53s. Luna 1T: 19.73s. Ratio: 2.41x slower.

To isolate the two factors, consider a simplified model. At 1T on a memory-bound workload the dominant cost per read is: (hash lookups per read) × (fraction that miss LLC) × (DRAM latency per miss) + (fraction that hit LLC) × (LLC latency) + (CPU compute overhead).

Luna sample_targeted, 1T: LLC miss rate 10.19%, LLC latency ~10–15 ns, DRAM latency ~80–100 ns. Most lookups hit LLC. DRAM stall cost is modest.

Orion sample_targeted, 1T: LLC miss rate 78.92%, LPDDR5 latency ~100–130 ns (unified memory, higher than DDR5 in absolute ns). 79% of LLC loads go to DRAM — the workload is almost entirely memory-latency-bound.

If Orion had the same 10.19% LLC miss rate as Luna, the DRAM latency contribution would drop by ~(78.92 - 10.19) / 78.92 ≈ 87%. At 1T the thread spends most of its time stalled on DRAM misses. Restoring a 10% miss rate would roughly cut the stall time by ~87%, which would reduce the pure DRAM stall portion of Orion's 47.53s substantially. A rough estimate: if ~70% of Orion's wall time is DRAM stall (consistent with IPC=1.00 and 79% miss rate), that is ~33s of stall time. Reducing the miss rate to 10% cuts that to ~4s, giving a notional ~18–19s — very close to Luna's 19.73s. This suggests roughly 70–80% of the 2.41x slowdown is attributable to LLC miss rate alone.

The remaining 20–30% is raw CPU and memory speed: Cortex-A78 at ~1.7 GHz vs Sapphire Rapids at ~3.0–3.5 GHz (2x clock), plus Sapphire Rapids' deeper pipeline and higher per-clock throughput. Clock speed alone would give ~2x compute advantage to Luna independent of cache behavior, but Kraken2 is not compute-bound — so the clock difference matters less here than the memory subsystem difference.

Summary: the LLC miss rate difference accounts for roughly 70–80% of the 2.41x slowdown. Raw clock speed and memory bandwidth differences account for the rest.

#### 4. IPC difference — out-of-order execution depth and latency hiding

Luna 1T IPC: 1.78. Orion 1T IPC: 1.00.

IPC is determined by how well the CPU fills its pipeline while waiting on memory. The key hardware mechanism is the ROB (reorder buffer): a larger ROB means more instructions can be in-flight simultaneously, letting the CPU find independent instructions to execute while a long-latency DRAM access resolves.

Sapphire Rapids ROB: 512 entries. It can have hundreds of independent instructions queued and executing while one DRAM miss (typically ~200–300 cycles at 3 GHz) resolves. For a workload like Kraken2 where each read generates many hash lookups with significant computation between them, there is meaningful instruction-level parallelism available across lookups. Luna exploits this: IPC 1.78 means nearly 2 instructions retire per cycle on average, even with 10% LLC miss rate producing real DRAM stalls.

Cortex-A78 ROB: approximately 128 entries (Arm's public docs for the A78 family indicate a 6-wide out-of-order core with ROB depth in the ~128 range, substantially smaller than Sapphire Rapids). With 78.92% LLC miss rate, nearly every hash lookup goes to DRAM. DRAM latency at ~100–130 ns on LPDDR5, at ~1.7 GHz, is ~170–220 cycles per miss. With a 128-entry ROB and most outstanding loads stalled waiting on DRAM, the ROB fills with stalled instructions and the frontend stalls — no new instructions can enter. The result is IPC ≈ 1.00: on average the core retires exactly one instruction per cycle, which means it is spending nearly half its time completely stalled (a pipeline with full stalls would have IPC approaching 0; IPC=1.0 in a 4-wide issue machine means the pipeline is ~25% utilized).

In short: Luna hides memory latency behind a deep ROB and finds other work to do. Orion's smaller ROB fills up fast under high LLC miss rates and the core stalls hard.

#### 5. Memory bandwidth — ceiling for thread scaling

Luna DDR5: ~307 GB/s aggregate across both sockets (2 × 8-channel DDR5-4800, roughly 307 GB/s theoretical peak, ~250–280 GB/s practical).
Orion LPDDR5: ~68 GB/s (LPDDR5-6400 × 128-bit bus, ~102 GB/s theoretical peak, ~68 GB/s practical; this pool is shared with the GPU).

Bandwidth ratio: approximately 4.5x in Luna's favor.

For a memory-bound workload at high thread counts, the bandwidth ceiling determines when adding threads stops helping. On Luna, each thread generates a DRAM traffic stream proportional to its LLC miss rate. With sample_targeted at ~10% LLC miss rate, the per-thread DRAM traffic is low — Luna can sustain many threads before hitting its ~250 GB/s bandwidth ceiling, consistent with near-linear scaling to 32T+ observed on eskape_650mb.

On Orion, each thread generates a DRAM traffic stream with ~79% LLC miss rate — roughly 7.7x more DRAM traffic per thread than Luna has for sample_targeted. Orion's bandwidth ceiling is also 4.5x lower. The combined effect: Orion hits its bandwidth ceiling at roughly (4.5 / 7.7) ≈ 0.58x as many threads as Luna would for the equivalent workload. Since Luna's bandwidth wall for a pre-cliff workload is well above 12T, Orion's wall for a post-cliff workload at 79% miss rate should appear within the 1–12T range available on Orion.

The unified memory constraint makes this worse: the GPU driver and background processes consume some portion of the 68 GB/s baseline, so the effective headroom for Kraken2 is below the theoretical ceiling.

#### 6. Prediction for Orion thread scaling (sample_targeted DB)

On Luna, sample_targeted scales near-linearly with essentially no Amdahl overhead (sys time ~0.21s). The expectation was bandwidth-limited scaling similar to eskape_650mb but with a lower miss rate making the bandwidth wall appear later.

On Orion, with 78.92% LLC miss rate already at 1T, the situation is different:

- The 50 MB DB loads in negligible time (~0.274s sys on Orion, comparable to Luna). Amdahl overhead is not a concern — same as Luna.
- Each thread is DRAM-bound from the first instruction. DRAM bandwidth is the only scaling limit.
- Orion has 12 physical cores. At 79% miss rate per thread, the per-thread DRAM demand is high.
- Estimated bandwidth wall: with 47 billion L1D accesses at 1T, and ~588 million LLC-loads of which ~463 million miss to DRAM, each LLC miss transfers a 64-byte cache line: 463M × 64 bytes = ~29.6 GB of DRAM traffic in 47.53s = ~624 MB/s per thread. Scaling linearly, 12 threads would need ~7.5 GB/s. This is well below the 68 GB/s ceiling — so at face value, Orion should scale linearly to 12T.
- However, this estimate assumes ideal scaling with no memory latency effects. In practice, LPDDR5 latency does not improve with parallelism — more threads queuing DRAM requests increases queuing delay. DRAM latency is the bottleneck at 1T (IPC=1.00), not bandwidth. Adding threads increases throughput at the cost of each thread's individual latency. IPC per thread will stay near 1.0 or degrade with more threads.
- Prediction: 2T and 4T should scale near-linearly (2T ~24s, 4T ~12s) because the DRAM bandwidth is not close to saturation and Orion can issue more DRAM requests by having more threads in flight. By 8–12T the bandwidth wall may start to bite — estimate 8T ~7–8s (6–7x speedup from 1T rather than ideal 8x). The scaling efficiency will likely be 80–90% at 4T and drop to 65–75% at 12T. This is worse than Luna's sample_targeted scaling (which would approach 95%+ efficiency at these thread counts) but better than Luna's post-cliff DB scaling.
- The DRAM bandwidth wall on Orion for sample_targeted will appear somewhere between 8T and 12T. Luna would not hit this wall for sample_targeted until well beyond 12T (possibly beyond 32T). Orion hits the wall earlier because its per-thread DRAM traffic is 7.7x higher relative to its bandwidth ceiling.

#### 7. Prediction for larger DBs on Orion

Since the 50 MB DB already gives 78.92% LLC miss rate, larger DBs cannot make the miss rate much worse — the only room to move is from 78.92% toward 100%.

eskape_650mb (150 MB DB): LLC miss rate on Luna jumped from 10.19% to 30.70% going from 50 MB to 150 MB. On Orion, the 50 MB DB is already 12.5x above the SLC; the 150 MB DB is 37.5x above. The incremental miss rate increase will be small — perhaps 82–86% vs 78.92%. The workload character does not change meaningfully. Wall time at 1T will be somewhat slower (more DB entries to hash through, more DRAM traffic) but the miss rate itself is already near its ceiling. Expect ~55–60s at 1T, roughly 15–25% slower than sample_targeted. Classified% will drop from 84.80% to approximately the same ratio as on Luna (~65%), since classification accuracy is independent of hardware.

standard_8gb (7.6 GB DB): LLC miss rate on Luna was 76.59% at 1T. On Orion with a 4 MB SLC, a 7.6 GB DB is 1900x larger than the SLC — the miss rate will be at or above 95%, essentially every LLC load missing to DRAM. The extra wrinkle: standard_8gb on Luna had ~4.2s sys time (DB loading). On Orion's eMMC storage, DB loading will be substantially slower — eMMC read speed is typically 200–400 MB/s vs NVMe/SSD. Loading 7.6 GB from eMMC at ~300 MB/s takes ~25 seconds. This means Amdahl's law will severely limit thread scaling on standard_8gb for Orion in a way it did not for Luna. The wall time at 1T for standard_8gb on Orion could easily exceed 120–150s, with the dominant cost split between DB loading overhead and the per-read DRAM latency.

standard_16gb (15 GB DB): likely infeasible on Orion's current storage (8.5 GB free, confirmed in Orion.md). Even if storage were cleared, a 15 GB DB load from eMMC at ~300 MB/s takes ~50 seconds per run — the Amdahl ceiling would be extremely low (50s serial / 50s wall = near 1.0x at any thread count).

Summary: every DB on Orion will be post-cliff. The meaningful variation between DBs on Orion will be in (a) classified% (bigger DB = better accuracy), (b) DB loading time from eMMC (grows with DB size, adds Amdahl overhead), and (c) classification phase wall time (grows modestly since miss rate is already near ceiling). The LLC miss rate itself will saturate in the 80–95% range across all DBs and provide little differentiation. The interesting cross-machine story is not "where is Orion's cliff" (below 4 MB, too small for any practical DB) but "how does Orion's fixed-near-ceiling miss rate interact with thread scaling and DB loading overhead across the DB size range."

---

## Orion (Jetson AGX Orin 64GB) — reads_hac × sample_targeted × 1T

64. **LLC miss rate 78.92% on Orion vs 10.19% on Luna for the same 50 MB DB** — the most striking cross-machine finding so far. On Luna (105 MB L3 per socket), the 50 MB hash table fits in cache — only 10% of LLC loads miss. On Orion, the ARM Cortex-A78's SLC (System Level Cache) is only ~4 MB — the 50 MB DB doesn't fit at all, giving 79% miss rate. The cache cliff on Orion is below 50 MB. Every single DB in the experiment will be above the cliff on Orion.

65. **Orion 1T is 2.41x slower than Luna 1T for the same workload** — Luna: 19.73s, Orion: 47.53s. Two compounding factors: (1) LLC miss rate 78.92% vs 10.19% means far more DRAM accesses per read; (2) Cortex-A78 at ~1.7 GHz vs Sapphire Rapids at ~3+ GHz, and lower memory bandwidth (LPDDR5 ~68 GB/s vs DDR5 ~307 GB/s on Luna). Both the CPU and memory subsystem are slower.

66. **IPC 1.00 on Orion vs 1.78 on Luna at 1T for sample_targeted** — despite Orion having a 79% LLC miss rate vs Luna's 10%, the IPC difference is stark. Luna's Sapphire Rapids has deeper out-of-order execution (512 ROB entries) and can hide DRAM latency better. Cortex-A78 has a smaller ROB and stalls harder per cache miss. At 79% LLC miss rate, the ARM core spends most of its time waiting on DRAM with no ILP to hide the latency.

67. **cache-references on Orion (~47B) vs Luna (~29B for eskape_650mb 1T) — ARM L1D counts are different** — on ARM, cache-references counts L1D accesses (~47 billion total); on x86, cache-references counts LLC (L3) accesses. These measure completely different cache levels. Orion's 0.643% cache miss rate means 0.643% of L1D accesses missed L1D — expected, L1D has a very high hit rate. Luna's 7.23% means 7.23% of LLC accesses missed the last level — higher because you are already at the bottom of the hierarchy. The two numbers are not comparable at all. The LLC Miss Rate% (LLC-load-misses / LLC-loads) is the apples-to-apples metric: both architectures expose it as demand-load traffic to the last-level cache. That is where the real story is — 78.92% on Orion vs 10.19% on Luna.

68. **Classified% 84.80% matches Luna exactly** — confirms Kraken2 2.1.3 on ARM64 produces identical classification to x86 for the same DB and reads. The algorithm is deterministic and architecture-independent. This validates the cross-machine comparison — any performance differences are purely hardware, not software.

---

## Thread Scaling (Orion, reads_hac, sample_targeted)

69. **Near-perfect scaling on Orion despite 79%+ LLC miss rate** — actual efficiencies: 2T=101.4%, 4T=100.6%, 6T=99.5%, 8T=98.8%, 10T=96.4%, 12T=95.4%. The prediction in section 6 of the cross-machine analysis estimated 80–90% at 4T and 65–75% at 12T — the actual numbers are dramatically better. The bandwidth wall never appeared within the 12-core range. The reason: per-thread DRAM traffic at ~624 MB/s × 12 threads = ~7.5 GB/s, which is well below the 68 GB/s LPDDR5 ceiling. Bandwidth is not the bottleneck here. With enough thread-level parallelism, the CPU stays busy even when each thread is DRAM-latency-bound.

70. **LLC miss rate climbs steadily with threads: 78.92% (1T) → 82.80% (12T)** — a 3.9-point rise across the full range. Compare: eskape_650mb on Luna rose from 30.70% (1T) to 32.56% (96T) over a much larger thread range. The Orion climb is steeper per doubling, reflecting the higher baseline miss rate and tighter bandwidth headroom, but the total range is small. IPC stays essentially flat throughout (1.00 at 1T, 1.02 at 2T–10T, 1.01 at 12T) — adding threads does not worsen per-instruction stall behavior. Each thread independently stalls on DRAM while other threads make progress, which is exactly how latency-tolerant thread scaling works.

71. **Peak speedup 11.44x at 12T — better than Luna's post-cliff DBs at far fewer threads** — Luna on eskape_human_4gb (post-cliff, 57% miss rate) reached only 10.57x at 64T with a 307 GB/s DRAM system. Orion reaches 11.44x at 12T with a 68 GB/s DRAM system and 83% miss rate. The difference is architectural: Orion has 12 physical cores with no hyperthreading and extremely low Amdahl overhead (sys time stays under 0.5s throughout). Luna's 64T runs included NUMA effects and thread management overhead that Orion avoids entirely with a single-node, single-socket design.

72. **sys time grows slightly with thread count: 0.274s (1T) → 0.461s (12T)** — a 0.19s increase across the full range. Negligible compared to the wall time reduction (47.53s → 4.15s). No Amdahl floor visible — unlike Luna's standard_8gb and standard_16gb where sys time (DB loading) was 4–8s and capped speedup below 4x. The 50 MB DB loads in milliseconds on Orion's eMMC, same as on Luna. This will change dramatically with larger DBs.

73. **Orion sample_targeted thread scaling summary** — 1T: 47.53s, 12T: 4.15s, peak speedup 11.44x at 12T (95.4% efficiency). No bandwidth wall, no Amdahl floor, IPC flat. The workload is latency-bound but thread-level parallelism hides that latency almost perfectly across all 12 cores. Contrast with Luna on the same DB: near-linear scaling also expected but with a much lower per-thread DRAM load due to 10% miss rate. Both machines scale well on sample_targeted, but for completely different reasons — Luna because the DB fits in cache, Orion because the thread count ceiling is reached before bandwidth saturates.

---

## Thread Scaling (Orion, reads_hac, eskape_650mb)

74. **3x larger DB, essentially the same 1T wall time on Orion: 47.05s vs 47.53s** — on Luna the same transition (50 MB → 150 MB) cost 2.25s extra (19.73s → 21.98s) because the smaller DB was pre-cliff and the larger was post-cliff. On Orion, both DBs are post-cliff. The LLC miss rate barely moved (78.92% → 80.75%) — adding 100 MB to a DB that already overwhelms a 4 MB SLC changes nothing structurally. The 0.5s difference is within run-to-run noise. DB size is irrelevant to cache behavior once you are past the cliff.

75. **LLC miss rate 80.75% (eskape_650mb) vs 78.92% (sample_targeted) — only 1.83-point difference despite 3x larger DB** — on Luna the same DB size increase caused a 20.5-point jump (10.19% → 30.70%). That dramatic jump was the cache cliff. On Orion there is no cliff to cross at these sizes — the SLC is already overwhelmed. The LLC miss rate on Orion is essentially a function of the access pattern randomness, not DB size. Once the DB exceeds ~4 MB, miss rate saturates near 80% and stays there.

76. **IPC drops from 1.00 (sample_targeted) to 0.93 (eskape_650mb) at 1T** — a meaningful 7% drop in instruction throughput. The eskape_650mb DB has different k-mer lookup patterns: with 65.28% classified vs 84.80%, each read does more searching before giving up. More failed lookups per read = more LLC loads that miss = deeper pipeline stalls per instruction retired. The IPC difference between the two DBs on Orion (0.93 vs 1.00) reflects this extra fruitless DRAM traffic.

77. **Thread scaling near-identical to sample_targeted: 94.5% efficiency at 12T vs 95.4%** — the 1-point difference is negligible. Despite a higher base miss rate (80.75% vs 78.92%) and slightly different access patterns, the thread-level parallelism mechanism works identically. The bandwidth wall did not appear for eskape_650mb either. Per-thread DRAM traffic for eskape_650mb at 1T: ~463M LLC misses × 64 bytes / 47.05s ≈ 629 MB/s — nearly identical to sample_targeted's ~624 MB/s. 12 threads × 629 MB/s = ~7.5 GB/s, still far below the 68 GB/s ceiling. — 1T: 47.53s, 12T: 4.15s, peak speedup 11.44x at 12T (95.4% efficiency). No bandwidth wall, no Amdahl floor, IPC flat. The workload is latency-bound but thread-level parallelism hides that latency almost perfectly across all 12 cores. Contrast with Luna on the same DB: near-linear scaling also expected but with a much lower per-thread DRAM load due to 10% miss rate. Both machines scale well on sample_targeted, but for completely different reasons — Luna because the DB fits in cache, Orion because the thread count ceiling is reached before bandwidth saturates.
