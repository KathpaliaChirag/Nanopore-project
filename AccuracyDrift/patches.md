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

**sample_targeted uses 26+6 bit split, not 16+16.** With only 6 species + a small LCA tree, taxon IDs fit in 6 bits (max 63 unique IDs). The remaining 26 bits go to the key (fewer hash collisions in a small table). Large pre-built databases need 16 value bits to cover thousands of taxa — leaving only 16 bits for the key, which means slightly higher collision rates.

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

**Expected pattern:**
- `sample_targeted` (50 MB → 12,800 4KB pages): lower raw miss count, but still ~60% per hash access
- `standard_8gb` (8 GB → 2M 4KB pages): measured 16.2M misses at 65%
- `standard_16gb` (16 GB → 4M 4KB pages): ~2× more misses than standard_8gb
- `pluspf_103gb` (103 GB → 27M 4KB pages): highest miss count, but run is warm (~10–15s)

---

## M3–M7 status

| Measurement | Status | What it decides |
|---|---|---|
| M3 — perf annotate CompactHashTable | **Pending** | Confirms exact load line causing LLC misses; validates prefetch target |
| M4 — DRAM bandwidth (uncore IMC) | **Pending** | Latency-bound vs bandwidth-bound → if >70% peak BW, DB compression needed instead |
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
