# AccuracyDrift Observations

Running list of interesting findings as data comes in. Organized by theme.

---

## Thread Scaling (Luna, reads_hac, eskape_650mb)

1. **Near-perfect linear speedup at low thread counts** — 1T=21.924s, 2T=11.150s = 1.97x speedup (98.5% efficiency). 4T=5.722s = 3.83x speedup (95.7% efficiency). The workload parallelizes almost perfectly at low thread counts. This is expected since each thread independently processes reads with no inter-thread communication.

2. **Cache miss rate climbs with thread count** — 1T: 34.21%, 2T: 36.18%, 4T: 37.11%. More threads = more concurrent LLC pressure = more evictions = higher miss rate. The rate of increase is slowing (gap: +1.97% → +0.93%), suggesting the LLC is approaching saturation for this 142 MB database even before we hit high thread counts.

3. **User time stays constant across thread counts** — 1T: 21.58s user, 2T: 22.00s user, 4T: 22.08s user. Wall time halves/quarters, but total CPU work is the same. Confirms true parallelism with no significant overhead.

---

## Database Size vs Classification (Luna, reads_hac)

*(to be filled as runs complete)*

---

## Cross-Machine Comparison

*(to be filled after other machines are run)*

---

## Orion (Jetson) Notes

*(to be filled when Orion runs are done — ARM unified memory behavior expected to differ significantly)*
