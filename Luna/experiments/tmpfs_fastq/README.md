# Experiment: FASTQ on tmpfs

**Date:** 2026-05-29
**Server:** Luna (dell-R760) — 2x Xeon Platinum 8468, 503 GB RAM
**Model:** hac, 32 threads, numactl node 0 pinned

---

## Problem

The perf flamegraph (Step 6) showed roughly 20% of Kraken2's wall time inside the Linux kernel's ext4 file read path:

```
read() -> entry_SYSCALL_64 -> do_syscall_64 -> __x64_sys_read
       -> vfs_read -> ext4_file_read_iter -> filemap_read
       -> copy_page_to_iter -> _copy_to_iter
```

This looked like the kernel reading `reads_hac.fastq` (~703 MB on disk) from SSD through ext4 into Kraken2's buffer — pure I/O overhead unrelated to classification. Hypothesis: removing the filesystem layer should eliminate this tower and save ~0.88s (20% of 4.405s baseline).

---

## Idea

`/dev/shm` is a RAM-backed tmpfs — no disk, no ext4, no VFS page cache lookup. Reading from it goes directly from physical memory into the process buffer.

Hypothesis: copying the FASTQ to `/dev/shm` would shorten the read path from:
```
SSD -> ext4 -> page cache -> copy_page_to_iter -> process buffer
```
to:
```
DRAM (/dev/shm) -> process buffer
```
Luna has 503 GB RAM; the 703 MB file fits trivially.

---

## Commands

```bash
# Copy FASTQ to tmpfs
cp ~/results/basecalling/reads_hac.fastq /dev/shm/reads_hac.fastq

# Run from tmpfs (32T, node0 pinned, 5 runs)
for i in 1 2 3 4 5; do
  START=$(date +%s%3N)
  numactl --cpunodebind=0 --membind=0 \
    kraken2 --db ~/data/kraken2_db --threads 32 \
    --report /dev/null --output /dev/null \
    /dev/shm/reads_hac.fastq 2>/dev/null
  END=$(date +%s%3N)
  echo "run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"
done

# Drop page cache to get a cold SSD baseline for comparison
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

# Cold then warm SSD runs (3 runs: run 1 = cold, runs 2-3 = warm)
for i in 1 2 3; do
  START=$(date +%s%3N)
  numactl --cpunodebind=0 --membind=0 \
    kraken2 --db ~/data/kraken2_db --threads 32 \
    --report /dev/null --output /dev/null \
    ~/results/basecalling/reads_hac.fastq 2>/dev/null
  END=$(date +%s%3N)
  echo "SSD run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"
done

# tmpfs runs after cache drop (warm DB, tmpfs FASTQ)
for i in 1 2 3; do
  START=$(date +%s%3N)
  numactl --cpunodebind=0 --membind=0 \
    kraken2 --db ~/data/kraken2_db --threads 32 \
    --report /dev/null --output /dev/null \
    /dev/shm/reads_hac.fastq 2>/dev/null
  END=$(date +%s%3N)
  echo "tmpfs run $i: $(echo "scale=3; ($END-$START)/1000" | bc)s"
done

# Cleanup
rm /dev/shm/reads_hac.fastq
```

---

## Results

### Phase 1 — tmpfs vs warm SSD (before cache drop)

Page cache was warm from many previous runs. DB (8 GB) and FASTQ (703 MB) both resident in RAM.

| Run | SSD warm (baseline) | tmpfs warm |
|---|---|---|
| 1 | 4.775s (warm-up outlier) | 4.427s |
| 2 | 4.400s | 4.377s |
| 3 | 4.398s | 4.408s |
| 4 | 4.393s | 4.387s |
| 5 | 4.430s | 4.378s |
| **Avg (steady state)** | **4.405s** | **4.395s** |
| **Saving** | — | **0.010s** |
| **% reduction** | — | **0.2%** — within noise |

### Phase 2 — Cold SSD vs warm SSD vs tmpfs (after drop_caches)

Page cache fully flushed: `echo 3 > /proc/sys/vm/drop_caches`. Free RAM went from ~290 GB used to 6.8 GB used.

| Config | Run 1 | Run 2 | Run 3 | Avg (runs 2-3) |
|---|---|---|---|---|
| Cold SSD (true disk read) | **10.894s** | — | — | — |
| Warm SSD (page cache) | 4.628s | 4.631s | 4.684s | **4.648s** |
| tmpfs (after warm-up) | 4.632s | 4.661s | 4.653s | **4.649s** |

Warm SSD and tmpfs are identical: **0.001s difference**.

---

## Analysis

### What actually happened

The hypothesis was wrong, and the reason is important.

Luna has 503 GB RAM. The FASTQ file is 703 MB. After the very first Kraken2 run ever, the file went into the Linux page cache and has stayed there permanently across every subsequent run. By the time we measured the SSD baseline (4.405s), the FASTQ was already being served from DRAM — not from SSD.

tmpfs is also DRAM. Both ext4-warm and tmpfs read the same physical memory and both execute `copy_page_to_iter` to move data into the process buffer. The VFS/ext4 overhead above the copy is negligible compared to the copy itself.

**The flamegraph's ~20% I/O tower is `copy_page_to_iter` overhead, not disk I/O.** It is a memory-to-memory copy from page cache to process buffer. This cost exists on both ext4 and tmpfs and cannot be eliminated by changing filesystems.

### What the cold run tells us

The cold SSD run (10.894s) shows what happens when neither the DB nor FASTQ is in cache:
- Cold wall time: 10.894s
- Warm wall time: 4.648s
- Cold overhead: **6.246s** — loading 8 GB DB + 703 MB FASTQ from NVMe SSD

Of that 6.246s, most is the DB (8 GB >> 703 MB). This cold penalty only hits after a reboot or explicit cache flush — in normal operation on Luna it never occurs.

### How to actually eliminate the I/O tower

The copy overhead in `copy_page_to_iter` is fundamental to read()-based I/O. To eliminate it:

1. **mmap the FASTQ** — Kraken2 could mmap the input file instead of reading it with read(). mmap maps the file pages directly into the process address space with no copy. Cost: one page fault per 4 KB page on first access, then zero. This is a code change to Kraken2's FASTQ parser.

2. **O_DIRECT with aligned buffers** — bypasses page cache entirely, reads direct from storage to process buffer. Faster than page cache only if the storage is fast enough. On Luna's NVMe this is plausible but would need benchmarking.

Both approaches require modifying Kraken2's source code.

---

## Ideas Not Pursued

### RAM limiting via cgroups

One proposed further experiment: use cgroups v2 to cap Kraken2's memory to 4 GB, forcing the 8 GB DB to thrash the cache. This would simulate a memory-constrained environment:

```bash
sudo systemd-run --scope -p MemoryMax=4G \
  numactl --cpunodebind=0 --membind=0 \
  kraken2 --db ~/data/kraken2_db --threads 32 ...
```

This was not run because we already know the answer from the cold cache experiment: when the DB cannot fit in memory, performance degrades toward the cold baseline (~10.9s). The cgroups experiment would confirm this but not add new insight. The root cause (DB >> L3 cache, DRAM bandwidth is the bottleneck) is already fully characterised.

---

## Conclusion

tmpfs provides **no benefit** for Kraken2 on Luna under normal operating conditions. The FASTQ file is permanently resident in the 503 GB page cache. The ~20% flamegraph I/O tower is a page-cache-to-process-buffer copy, not disk I/O, and is irreducible without code changes to Kraken2's input handling.

The optimisation ladder remains unchanged:

| Configuration | Wall time | vs 96T baseline |
|---|---|---|
| 96T, no pin (original baseline) | 5.635s | — |
| 32T, no pin | 5.235s | -7.1% |
| 32T, node0+node0 | 4.405s | -21.8% |
| 32T, node0+node0, tmpfs FASTQ | 4.395s | -21.9% — no real gain |

The remaining addressable targets require code changes:
- **CompactHashTable::Get (12% of wall time, 96% of DRAM reads)** — hot k-mer LRU cache (Kolin sir's design)
- **FASTQ I/O copy (~20% of wall time)** — mmap-based input in Kraken2
- **MinimizerScanner::NextMinimizer (25% of wall time)** — SIMD vectorisation
