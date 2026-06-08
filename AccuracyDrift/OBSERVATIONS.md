# AccuracyDrift Observations

Running list of interesting findings as data comes in. Organized by theme.

---

## Thread Scaling (Luna, reads_hac, eskape_650mb)

1. **Near-perfect linear speedup at low thread counts** — 1T=21.924s, 2T=11.150s = 1.97x speedup (98.5% efficiency). 4T=5.722s = 3.83x speedup (95.7% efficiency). The workload parallelizes almost perfectly at low thread counts. This is expected since each thread independently processes reads with no inter-thread communication.

2. **LLC miss rate climbs then plateaus** — 1T: 34.21%, 2T: 36.18%, 4T: 37.11%, 8T: 37.07%. Rate of increase slowed (+1.97% → +0.93%) and fully stopped by 8T. The LLC is saturated for this 142 MB database — all threads are hitting DRAM at the same rate, adding more threads doesn't increase the miss rate further.

3. **User time stays constant across thread counts** — 1T: 21.58s user, 2T: 22.00s user, 4T: 22.08s user, 8T: 22.36s user. Wall time scales down, total CPU work is the same. Confirms true parallelism with negligible overhead.

4. **IPC declines steadily with thread count** — 1T: 1.47, 2T: 1.46, 4T: 1.45, 8T: 1.43, 32T: 1.33 (no numactl). More threads = more concurrent LLC/DRAM stalls = lower instructions-per-cycle. Small per-step but will likely accelerate at high thread counts when memory bandwidth saturates.

5. **Speedup efficiency degrades as threads increase** — 2T: 98.5%, 4T: 95.7%, 8T: 91.5%, 16T: 83.3%. Dropping faster now. Memory bandwidth becoming the limiter. Expected to degrade sharply past 32T.

6. **LLC miss rate dipped at 16T** — 8T: 37.07%, 16T: 36.70%. Small unexpected decrease. Could be measurement noise or a real effect (faster runs = less time for LLC pressure to accumulate). Watch at 32T and 64T to determine if this is a trend or noise.

7. **`cache-misses` in perf stat = LLC miss count on x86** — this is the hardware Last Level Cache miss counter, not L1/L2. So LLC Miss Rate% = cache-misses / cache-references × 100. We are measuring the right thing.

---

## Database Size vs Classification (Luna, reads_hac)

*(to be filled as runs complete)*

---

## Cross-Machine Comparison

*(to be filled after other machines are run)*

---

## Orion (Jetson) Notes

*(to be filled when Orion runs are done — ARM unified memory behavior expected to differ significantly)*
