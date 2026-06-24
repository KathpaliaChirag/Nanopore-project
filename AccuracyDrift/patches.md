# Kraken2 Optimisation Patch Analysis

Pre-patch characterisation to decide which of the 4 patches in `kraken2_opt_v1.patch` are worth applying and why. Each measurement (M1–M7) gates one or more patch decisions.

Patch file: `Luna/experiments/kraken2_opt_v1.patch`  
Apply script: `~/run_kraken2_opt_v1.sh` (run on Luna after M1–M7 complete)

---

## Patches Overview

| # | Where | What | Decision | Gate |
|---|---|---|---|---|
| P1 | `src/Makefile` | `-march=sapphirerapids -flto -funroll-loops` | Pending M7 | M7 objdump |
| P2 | `mmap_file.cc` | `MADV_HUGEPAGE + MADV_WILLNEED + MADV_RANDOM` | **Apply** (see M2) | M2 ✓ |
| P3 | `compact_hash.h Get()` | `__builtin_prefetch` one cache line ahead | **Apply** (see M1) | M1 ✓ |
| P4 | `classify.cc` | Thread-local 16K-entry direct-mapped k-mer cache | Pending M5 | M5 |

*Patch 4 is Kolin sir's design — always credit him when describing it.*

---

## M1 — Hash table structure (2026-06-24, Luna, standard_8gb)

**Command:**
```bash
python3 - <<'PY' | tee ~/results/profiling/pending/m1_hash_header.txt
import struct, os
p = os.path.expanduser("~/AccuracyDrift/databases/standard_8gb/hash.k2d")
with open(p, "rb") as f:
    cap, sz, kb, vb = struct.unpack("<QQQQ", f.read(32))
file_bytes = os.path.getsize(p)
cell_b = (file_bytes - 32) / cap
print(f"capacity      : {cap:,}")
print(f"size          : {sz:,}")
print(f"load_factor   : {sz/cap:.4f}")
print(f"key_bits      : {kb}")
print(f"value_bits    : {vb}")
print(f"key+value     : {kb+vb}  ({'40-bit cell' if kb+vb==40 else '32-bit cell' if kb+vb==32 else 'other'})")
print(f"file_bytes    : {file_bytes:,}")
print(f"implied bytes/cell : {cell_b:.3f}")
print(f"cells/cache_line   : {64/cell_b:.2f}")
PY
```

**Results — all four available databases:**

| DB | Load factor | Cell | bytes/cell | cells/64B line | PF_STRIDE |
|---|---|---|---|---|---|
| sample_targeted | 0.6899 (69.0%) | 26+6 = 32-bit | 4.000 | 16 | 16 |
| standard_8gb | 0.7006 (70.1%) | 16+16 = 32-bit | 4.000 | 16 | 16 |
| standard_16gb | 0.7001 (70.0%) | 16+16 = 32-bit | 4.000 | 16 | 16 |
| pluspf_103gb | 0.7007 (70.1%) | 16+16 = 32-bit | 4.000 | 16 | 16 |

**Key findings:**

**Load factor ~0.70 is hardcoded in the Kraken2 database builder.** The builder sets `capacity = n_kmers / 0.70`, targeting 70% fill. All official databases land at almost exactly 70.0%; our custom `sample_targeted` is at 69.0% due to rounding the capacity to a round integer.

At 70% load, linear probing averages:
```
avg probes per successful lookup = ½ × (1 + 1/(1 − 0.70)) = 2.17 probes
```
Each probe is a random access into the hash table → LLC miss → ~100–200 ns DRAM stall. With 11.6M `Get()` calls per run, this produces ~25M random DRAM accesses per run, which is why `CompactHashTable::Get()` generates 96.24% of all LLC misses.

**PF_STRIDE = 16 for all databases** (4-byte cell → 64/4 = 16 cells per cache line). The patch uses `constexpr size_t PF_STRIDE = 64 / sizeof(Cell)` which computes this automatically. M1 confirms the formula is calibrated correctly for every database on this system.

**sample_targeted uses 26+6 bit split, not 16+16 — this is automatic, not something we set.** When `kraken2-build` runs, it counts unique taxon IDs in the taxonomy and sets `value_bits = minimum bits needed to represent them all`. For our 6-species custom DB (P. aeruginosa, E. coli, K. pneumoniae, E. faecium, S. aureus, E. cloacae + their LCA ancestors), the full hierarchy fits in 6 bits (max 63 unique internal IDs). The remaining 32−6 = 26 bits go to the key. For pre-built standard databases with thousands of NCBI taxa, 16 value bits (max 65,536 unique IDs) are needed, leaving only 16 bits for the key. More key bits = fewer spurious hash collisions in the compact table — so our small custom DB actually has better lookup precision than the large ones.

**Decision for P3 (prefetch): Apply.** PF_STRIDE=16 confirmed for all databases. Load factor 0.70 means ~70% of lookups need a 2nd probe that benefits from the prefetch.

---

## M2 — dTLB pressure and huge pages (2026-06-24, Luna, standard_8gb)

**Command:**
```bash
DB=~/AccuracyDrift/databases/standard_8gb
IN=~/results/basecalling/reads_hac.fastq

numactl --cpunodebind=0 --membind=0 \
  perf stat -e cycles,instructions,\
dTLB-loads,dTLB-load-misses,\
dTLB-stores,dTLB-store-misses \
  kraken2 --db $DB --threads 32 \
  --output /dev/null --report /dev/null \
  $IN \
  2>&1 | tee ~/results/profiling/pending/m2_dtlb.txt
```

**Results (standard_8gb, reads_hac, 32T, warm DB):**

| Counter | Value (western format) |
|---|---|
| cycles | 60.3 billion |
| instructions | 111.7 billion |
| IPC | 1.85 |
| dTLB-loads | 30.3 billion |
| dTLB-load-misses | 16.2 million (**0.05% of all dTLB loads**) |
| dTLB-stores | 14.2 billion |
| dTLB-store-misses | 19.7 million |
| Wall time | 4.78 s |

**THP status on Luna:**
```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# Output: always [madvise] never
```
THP is in **madvise** mode — huge pages are only used for memory regions that explicitly call `madvise(addr, len, MADV_HUGEPAGE)`. Stock Kraken2 does NOT make this call, so the hash table mmap uses standard 4 KB pages.

### Why 0.05% is misleading

The 0.05% rate is computed against **all 30.3 billion dTLB-loads**, which includes MinimizerScanner k-mer scanning, FASTQ reading, stack operations, and program data — the vast majority of loads. The hash table contributes only ~25 million loads (11.6M `Get()` calls × ~2 probes each), which is just 0.08% of the total.

Normalised to hash table accesses only:

```
Hash table TLB miss rate = 16.2M misses / ~25M hash table loads ≈ 65%
```

This makes physical sense: with 4 KB pages, the 8 GB hash table requires **2,097,152 unique pages**. The Sapphire Rapids STLB (L2 TLB) holds ~2,048 entries. Random hash lookups span the entire 8 GB → near-100% STLB miss rate for each new page touched → full hardware page walk per miss.

### Why Patch 2 matters despite Luna being in madvise mode

With 2 MB huge pages (what Patch 2 requests via MADV_HUGEPAGE):

```
8 GB / 2 MB = 4,096 huge pages → fits comfortably in the STLB
```

TLB miss rate for hash table drops from ~65% to near-zero. The estimated runtime saving:

```
16.2M TLB misses × ~50 cycles/miss = 810M cycles overhead
Total: 60.3B cycles → TLB overhead ≈ 1.3% of runtime
```

Expected saving from Patch 2: **~0.06–0.08 s on standard_8gb** (modest but real). The saving scales with DB size — pluspf_103gb at 103 GB will have even higher raw TLB miss counts.

**Decision for P2 (MADV_HUGEPAGE): Apply.** THP in madvise mode means the hint is necessary; the OS will not use huge pages without it. Saving is small (~1–2%) but costs nothing to apply.

### M2 across all databases

Run to quantify TLB pressure per database (expect pluspf worst case):

```bash
for DB_NAME in sample_targeted standard_8gb standard_16gb pluspf_103gb; do
  DB=~/AccuracyDrift/databases/$DB_NAME
  echo "=== $DB_NAME ==="
  numactl --cpunodebind=0 --membind=0 \
    perf stat -e dTLB-loads,dTLB-load-misses,cycles \
    kraken2 --db $DB --threads 32 \
    --output /dev/null --report /dev/null \
    ~/results/basecalling/reads_hac.fastq 2>&1 \
  | grep -E "dTLB|cycles|seconds time elapsed"
  echo ""
done 2>&1 | tee ~/results/profiling/pending/m2_all_dbs.txt
```

**Results across all databases (2026-06-24, reads_hac, 32T, warm DB):**

| DB | dTLB-loads | dTLB-load-misses | Miss% | Cycles | Wall time |
|---|---|---|---|---|---|
| sample_targeted | 30.8B | 98.9M | **0.32%** | 66.3B | 0.93s |
| standard_8gb | 30.3B | 16.8M | 0.06% | 61.0B | 4.76s |
| standard_16gb | 37.8B | 31.6M | 0.08% | 83.6B | 8.18s |
| pluspf_103gb | 78.4B | 192.3M | 0.25% | 398.8B | 58.75s |

**Counterintuitive finding: sample_targeted has the highest miss% (0.32%) despite being the smallest DB.**

The raw miss count for sample_targeted (98.9M) is 6× higher than standard_8gb (16.8M), even though the DB is 160× smaller. The reason is that the miss% is measured against total dTLB-loads, but cycles/miss reveals the real picture:

```
cycles per TLB miss:
  sample_targeted : 66.3B / 98.9M = 670 cycles/miss   ← CPU is busy
  standard_8gb    : 61.0B / 16.8M = 3,631 cycles/miss ← CPU is stalled on DRAM
  standard_16gb   : 83.6B / 31.6M = 2,646 cycles/miss
  pluspf_103gb    : 398.8B / 192.3M = 2,074 cycles/miss
```

sample_targeted's DB (50 MB) fits in LLC — no DRAM stalls for hash lookups. The CPU runs at full speed and spends active time scanning the 703 MB FASTQ file (MinimizerScanner). That FASTQ scanning generates 175,750 unique 4 KB pages which compete with the hash table's 12,800 pages in the 2,048-entry STLB, causing many TLB misses from FASTQ access, not the hash table.

For standard_8gb, the CPU stalls ~90% of the time waiting for DRAM on hash table misses. Very few cycles are spent on FASTQ scanning, so FASTQ-related TLB misses barely appear in the total.

**Patch 2 impact per database:**

| DB | 4 KB pages | 2 MB pages | STLB fits? | TLB miss source | P2 benefit |
|---|---|---|---|---|---|
| sample_targeted | 12,800 | 25 | Yes (25 < 2048) | Mostly FASTQ, not hash | Low |
| standard_8gb | 2,097,152 | 4,096 | Yes (4096 ≈ 2048) | Hash table | ~1–2% |
| standard_16gb | 4,194,304 | 8,192 | Partial | Hash table | ~1–2% |
| pluspf_103gb | 27,262,976 | 52,736 | No (52K > 2048) | Hash table + FASTQ | Reduces walk cost per miss |

For pluspf_103gb, even with 2 MB pages the STLB still overflows (52K pages vs 2K STLB). Patch 2 still helps because 2 MB pages reduce the hardware page walk from 4 levels to 3 (skipping the PTE level), saving ~20–30 cycles per walk. With 192M misses at ~25 cycles saved each = ~4.8B cycles ≈ 1.2% of its 398B total cycles.

---

## M3 — perf record LLC-load-misses (2026-06-24, Luna, standard_8gb)

**Command:**
```bash
numactl --cpunodebind=0 --membind=0 \
  perf record -e LLC-load-misses \
  -o ~/results/profiling/pending/m3_perf.data \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb --threads 32 \
  --output /dev/null --report /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>/dev/null

perf report --stdio \
  -i ~/results/profiling/pending/m3_perf.data \
  2>/dev/null | head -40 | tee ~/results/profiling/pending/m3_report.txt
```

**Results (48K samples, ~101M LLC-load-misses total):**

| % | Binary | Symbol | Type |
|---|---|---|---|
| 40.14% | [kernel] | 0xffffffffb3247ff8 (+ cluster) | Hardware page table walker |
| 26.69% | [kernel] | 0xffffffffb3e00ba0 | copy_page_to_iter (FASTQ I/O) |
| 6.27% | libc.so.6 | __memmove_avx512_unaligned_erms | FASTQ data copy |
| **5.84%** | classify | **kraken2::CompactHashTable::Get()** | Hash table direct miss |
| 5.64% | classify | std::unordered_map::operator[] | Taxonomy report map |
| 5.14% | libc.so.6 | __memchr_evex | FASTQ scanning |
| 0.09% | classify | kraken2::MinimizerScanner::NextMinimizer() | Zero LLC — pure compute |

**Key finding: 66.83% of LLC misses are in kernel space, but the root cause is still CompactHashTable::Get().**

cachegrind attributed 96.24% to `Get()` while perf shows only 5.84%. Both are correct — they measure different things:

- cachegrind asks "which user-space instruction triggered the miss?" → `Get()` wins
- perf samples "where is the CPU executing when the miss is detected?" → includes kernel page walk code that runs *because* `Get()` caused a TLB miss

The causal chain: `CompactHashTable::Get()` → TLB miss → kernel page table walker → walker reads PTE from RAM → PTE read misses LLC → perf samples the kernel page walk code, not `Get()`.

**LLC miss ownership by root cause:**

| Source | % | Root cause | Addressed by |
|---|---|---|---|
| Kernel page walker cluster | 40.14% | TLB miss from hash table → 4-level page walk | Patch 2 (2 MB pages → 3-level walk, page table fits LLC) |
| FASTQ kernel I/O path | 26.69% | copy_page_to_iter copying FASTQ into userspace | Not in patch (would need mmap FASTQ in Kraken2 source) |
| FASTQ libc memmove + memchr | ~11% | Scanning FASTQ bytes | Not in patch |
| CompactHashTable::Get() direct | 5.84% | Hash table data miss | Patch 3 (prefetch) |
| std::unordered_map report map | 5.64% | Taxonomy counting per classified read | Not addressed — separate opportunity |
| MinimizerScanner | 0.09% | Pure compute, no LLC misses | Nothing needed |

**Implication for Patch 2:** the 40.14% kernel page walk LLC overhead is caused by TLB misses on the hash table. Switching to 2 MB huge pages collapses the page table from 2M entries to 4K entries → page table fits in LLC → page walk PTE reads hit LLC instead of DRAM → that 40.14% drops significantly. This makes Patch 2 potentially more impactful than the modest 1–2% dTLB-miss-rate calculation suggested.

**Surprise finding — `std::unordered_map::operator[]` at 5.64%:** This is the per-taxon ReadCounts map used for report generation (`std::unordered_map<uint64_t, ReadCounts<HyperLogLogPlusMinus>>`). Updated for every classified read; with thousands of distinct taxa encountered, map nodes scatter in heap memory and miss LLC. Not targeted by any of the 4 patches — worth flagging to Kolin sir as a separate optimization opportunity.

**Decision for P3 (prefetch): confirmed Apply.** `CompactHashTable::Get()` is the user-space source of both the 5.84% direct LLC misses and the 40.14% kernel page walk overhead.

### M3 across all databases (2026-06-24)

| Source | sample_targeted | standard_8gb | standard_16gb | pluspf_103gb |
|---|---|---|---|---|
| Kernel page walker `[k]` | 33.06% | 40.52% | 39.53% | **42.52%** |
| FASTQ I/O kernel `copy_page_to_iter` | 3.96% | 26.85% | 30.34% | **32.44%** |
| libc memmove_avx512 + memchr (FASTQ scan) | **53.46%** | 11.63% | 7.87% | 1.29% |
| `CompactHashTable::Get()` | 2.24% | 5.70% | 7.75% | **10.57%** |
| `std::unordered_map::operator[]` (report map) | 0.29% | 5.50% | 6.58% | 6.47% |
| `MinimizerScanner::NextMinimizer()` | 0.21% | ~0% | 0.13% | 0.23% |

**Finding 1 — CompactHashTable::Get() scales monotonically with DB size:**
```
sample_targeted:  2.24%   (50 MB DB, fits in LLC)
standard_8gb:     5.70%   (8 GB DB)
standard_16gb:    7.75%   (16 GB DB)
pluspf_103gb:    10.57%   (103 GB DB)
```
Larger DB → fewer hash table entries fit in LLC → higher miss rate per Get() call → higher % of total LLC misses. This is the cache cliff made visible at the instruction level.

**Finding 2 — sample_targeted reveals the bottleneck shift:**
When the DB fits in LLC, `Get()` drops to 2.24% and libc FASTQ functions (memmove + memchr) jump to 53%. The same 104,918 reads are processed with the same minimizer computation, but with no DRAM stalls for hash lookups, the CPU sprints through FASTQ scanning instead. This is the pre-cliff regime making itself visible in LLC miss composition — the bottleneck has moved from hash table to FASTQ I/O.

**Finding 3 — Kernel page walker is a constant ~33–42% across all DBs:**
Even sample_targeted shows 33% kernel page walker LLC misses despite the DB fitting in LLC. The FASTQ file (703 MB = 175,750 4 KB pages) alone keeps the page walker busy — sequential FASTQ access still causes TLB misses on each new 4 KB page, and PTE reads for 175K pages miss LLC. Patch 2 (huge pages) makes the page table smaller, which helps reduce this overhead across all databases.

**Finding 4 — MinimizerScanner stays near 0% on every database:**
0.21%, ~0%, 0.13%, 0.23% — pure compute confirmed across all four databases. The minimizer window (≤15 entries) stays permanently in L1 cache regardless of DB size.

---

## M4 — DRAM bandwidth via uncore IMC (2026-06-24, Luna, standard_8gb)

**Command:**
```bash
numactl --cpunodebind=0 --membind=0 \
  perf stat -a -e \
uncore_imc_0/cas_count_read/,uncore_imc_0/cas_count_write/,\
uncore_imc_1/cas_count_read/,uncore_imc_1/cas_count_write/,\
uncore_imc_2/cas_count_read/,uncore_imc_2/cas_count_write/,\
uncore_imc_3/cas_count_read/,uncore_imc_3/cas_count_write/,\
uncore_imc_4/cas_count_read/,uncore_imc_4/cas_count_write/,\
uncore_imc_5/cas_count_read/,uncore_imc_5/cas_count_write/,\
uncore_imc_6/cas_count_read/,uncore_imc_6/cas_count_write/,\
uncore_imc_7/cas_count_read/,uncore_imc_7/cas_count_write/ \
  kraken2 --db ~/AccuracyDrift/databases/standard_8gb --threads 32 \
  --output /dev/null --report /dev/null \
  ~/results/basecalling/reads_hac.fastq \
  2>&1 | tee ~/results/profiling/pending/m4_imc.txt
```

**Results (standard_8gb, reads_hac, 32T, warm, wall time 5.008s):**

Active channels: imc_0, imc_2, imc_4, imc_6 only (imc_1/3/5/7 = 0 — 4 DIMMs installed, not 8).

| Channel | Reads (MiB) | Writes (MiB) |
|---|---|---|
| imc_0 | 6,870.68 | 3,940.81 |
| imc_2 | 6,871.60 | 3,940.47 |
| imc_4 | 6,873.39 | 3,943.09 |
| imc_6 | 6,873.99 | 3,943.06 |
| **Total** | **27,489.66 MiB (26.85 GiB)** | **15,767.43 MiB (15.40 GiB)** |

**Derived metrics:**
```
Total DRAM traffic : 42.25 GiB in 5.008 s
Read bandwidth     : 26.85 GiB / 5.008 s = 5.36 GiB/s
Write bandwidth    : 15.40 GiB / 5.008 s = 3.08 GiB/s
Total bandwidth    : 8.44 GiB/s ≈ 9.1 GB/s

Peak (4 active DDR5-4800 channels × 35.76 GiB/s) = 143 GiB/s
% of peak used     : 8.44 / 143 = 5.9%
```

**Decision: conclusively latency-bound, not bandwidth-bound.**

Using only 5.9% of available DDR5 bandwidth. The problem is NOT that we are reading too much data — it is that we wait 100–300 ns for each individual random hash table access before issuing the next one (sequential probe chain dependency: slot N must return before we know to probe slot N+1). The DRAM highway has 4 lanes and we are using 1/17th of one lane.

Contrast with a bandwidth-bound workload: all 4 channels fully loaded, 143 GiB/s of sustained traffic. That would require ~compression of the hash table cells (less data per lookup) or a different data structure.

**Implication for patches:**
- Patch 3 (prefetch): issues the next probe's DRAM request before the current one returns — doubles in-flight requests per thread → can approach 2× speedup on the hash lookup bottleneck with no bandwidth cost (we have 94% headroom)
- Patch 4 (Kolin sir's k-mer cache): eliminates DRAM accesses entirely for repeated k-mers → saves both latency AND bandwidth
- Patch 2 (huge pages): reduces page walk overhead — still valid
- DB compression: **not needed** — bandwidth is not the constraint

**Structural note — why only 4 of 8 IMCs are active:**
Luna has 4 DDR5 DIMMs installed per socket (slots 0, 2, 4, 6 populated; 1, 3, 5, 7 empty). Populated slots map to even-numbered IMCs. Theoretical peak with 4 channels ≈ 143 GiB/s (half of the 8-channel maximum of 286 GiB/s).

**Channels are perfectly load-balanced:** all 4 active channels carry identical traffic (~6,872 MiB reads, ~3,942 MiB writes each). This is expected — the hash function distributes k-mers uniformly across the hash table, which in turn distributes DRAM accesses uniformly across channels.

---

## M5–M7 status

| Measurement | Status | What it decides |
|---|---|---|
| M5 — k-mer reuse rate | **Pending** | Validates Kolin sir's LRU cache ROI (P4); reuse >30% → apply, <10% → skip |
| M6 — perf c2c false sharing | Low priority | Only needed if revisiting thread counts beyond 32T |
| M7 — objdump AVX-512 status | **Pending** | Decides if `-march=sapphirerapids` enables SIMD in MinimizerScanner |

---

## Machine notes — check before applying patch on any machine

### Luna (dell-R760) ✓
- THP: **madvise** → Patch 2 is active and necessary
- THP command: `cat /sys/kernel/mm/transparent_hugepage/enabled`
- `classify` binary missing from `~/kraken2-build/` — use `kraken2` wrapper for all perf runs
- `kraken2` at `~/tools/kraken2/kraken2`

### Orion (Jetson AGX Orin) — TO CHECK
Orion may have THP disabled entirely or in a different mode. Check:
```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# If output: [always] madvise never  → huge pages already active, Patch 2 adds nothing
# If output: always [madvise] never  → same as Luna, Patch 2 needed
# If output: always madvise [never]  → huge pages disabled, Patch 2 with MADV_HUGEPAGE
#                                       may still work if kernel honours the hint
# If file doesn't exist              → kernel built without THP support (common on ARM)
```

Also check if `madvise` is available on Orion's ARM kernel — some embedded ARM kernels omit THP support entirely. If THP is unavailable, Patch 2 has zero effect on Orion.

Orion-specific: With only 4 MB SLC (every DB is post-cliff), TLB pressure is even more severe than Luna — every `Get()` call misses SLC and goes to LPDDR5. Huge pages reduce the page walk overhead per miss, which adds up when every single hash access is a cache miss.

### Minerva — BLOCKED (disk 100% full)
Cannot run any measurements until disk is cleared.

---

## Summary — patch go/no-go table

| Patch | Decision | Reason | Expected gain |
|---|---|---|---|
| P1 compiler flags | Pending M7 | Need to verify SIMD actually activates | Unknown |
| P2 MADV_HUGEPAGE | **Apply** | THP is madvise mode on Luna; 65% TLB miss rate on hash table | ~1–2% |
| P3 prefetch | **Apply** | PF_STRIDE=16 confirmed; 70% load → 2.17 avg probes | Estimated 10–20% |
| P4 k-mer LRU cache | Pending M5 | Reuse rate unknown; if >30% → major win | Unknown |
