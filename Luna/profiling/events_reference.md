# perf Events Reference — Luna (Sapphire Rapids, Xeon Platinum 8468)

Last updated: 2026-05-29
Verified by running `perf list` on student@dell-R760.

---

## Why stalled-cycles-backend does not work

`stalled-cycles-backend` is a generic perf alias that Intel dropped on Sapphire Rapids.
On older CPUs it mapped to `CYCLE_ACTIVITY.STALLS_TOTAL`. On Sapphire Rapids, Intel
replaced it with more granular per-cache-level stall events and TMA metrics.
It shows as `<not supported>` on this machine and can be ignored.

---

## What to use instead

### Stall events (Sapphire Rapids native)

| Event | What it measures |
|---|---|
| `cycle_activity.stalls_total` | All execution stall cycles combined |
| `cycle_activity.stalls_l1d_miss` | Stall cycles while waiting on L1 cache miss |
| `cycle_activity.stalls_l2_miss` | Stall cycles while waiting on L2 cache miss |
| `cycle_activity.stalls_l3_miss` | Stall cycles while waiting on L3 cache miss |
| `memory_activity.stalls_l1d_miss` | Stall cycles (memory subsystem) — L1 miss |
| `memory_activity.stalls_l2_miss` | Stall cycles (memory subsystem) — L2 miss |
| `memory_activity.stalls_l3_miss` | Stall cycles (memory subsystem) — L3 miss |
| `resource_stalls.sb` | Stall cycles due to store buffer full |
| `uops_executed.stalls` | Cycles where no uops were executed |
| `uops_retired.stalls` | Cycles where no uops were retired |
| `l1d_pend_miss.l2_stalls` | L1D pending miss stalls waiting for L2 |
| `icache_data.stalls` | Cycles stalled on L1 instruction cache miss |
| `icache_tag.stalls` | Cycles stalled on L1 instruction cache tag miss |

### TMA (Top-down Microarchitecture Analysis) metrics

Sapphire Rapids has full TMA Level 1 and Level 2 support via perf metrics.
These give percentage breakdowns of where cycles are being wasted.

| Event | What it measures |
|---|---|
| `tma_memory_bound` | Fraction of slots stalled waiting for memory |
| `tma_core_bound` | Fraction of slots stalled on core execution units |
| `tma_branch_mispredicts` | Slots wasted on branch mispredictions |
| `tma_machine_clears` | Slots lost to pipeline flushes |
| `tma_icache_misses` | Slots lost to instruction cache misses |
| `tma_mispredicts_resteers` | Slots lost to misprediction re-steering |
| `tma_clears_resteers` | Slots lost to clear re-steering |
| `tma_info_core_ilp` | Instruction-level parallelism within the core |
| `tma_info_memory_l2mpki` | L2 misses per thousand instructions |

### Standard hardware events (confirmed working)

| Event | What it measures |
|---|---|
| `cycles` | CPU cycles |
| `instructions` | Instructions retired |
| `cache-misses` | Last-level cache misses |
| `cache-references` | Last-level cache accesses |
| `LLC-load-misses` | LLC load misses |
| `LLC-loads` | LLC load accesses |
| `L1-dcache-load-misses` | L1 data cache load misses |
| `L1-dcache-loads` | L1 data cache load accesses |
| `branch-misses` | Branch prediction misses |
| `branch-instructions` | Total branches |
| `bus-cycles` | Bus cycles |
| `ref-cycles` | Reference cycles (constant frequency) |

---

## Events NOT supported on this CPU

| Event | Reason |
|---|---|
| `stalled-cycles-backend` | Generic alias removed on Sapphire Rapids — use `cycle_activity.stalls_*` instead |
| Tracepoint events | `Error: failed to open tracing events directory` — requires root or paranoid <= 0 |
| `mem-loads`, `mem-stores` | Require PEBS and paranoid <= 0 — may work with sudo |

---

## Recommended perf stat command for Kraken2 profiling

```bash
perf stat \
  -e cycles,instructions \
  -e cache-misses,cache-references \
  -e LLC-load-misses,LLC-loads \
  -e L1-dcache-load-misses,L1-dcache-loads \
  -e branch-misses,branch-instructions \
  -e cycle_activity.stalls_total \
  -e cycle_activity.stalls_l1d_miss \
  -e cycle_activity.stalls_l2_miss \
  -e cycle_activity.stalls_l3_miss \
  -e memory_activity.stalls_l3_miss \
  -e tma_memory_bound,tma_core_bound \
  -e tma_branch_mispredicts,tma_info_core_ilp \
  kraken2 --db ~/data/kraken2_db --threads 96 \
  --report ~/results/profiling/perf_report_hac.txt \
  --output ~/results/profiling/perf_output_hac.txt \
  ~/results/basecalling/reads_hac.fastq
```

Note: perf multiplexes events when more than ~8 are specified. Results are still
accurate enough for relative comparisons. For exact counts, split into separate runs
of 4-6 events each.

---

## Per-core utilization

```bash
# mpstat shows per-core CPU usage — tells us if kraken2 uses all 96 cores.
sudo apt install -y sysstat
mpstat -P ALL 1
```

---

## Note on paranoid setting

perf_event_paranoid is currently 0 (set 2026-05-29).
Hardware PMU events work for all users.
Tracepoint events still require root (separate kernel permission).
