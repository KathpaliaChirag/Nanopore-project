# Luna — Pending Measurements (run before applying patches)

These five measurements answer questions that **decide which patches matter and which
parameters to tune**. Run all five on Luna in the order shown. Results paste back to chat
or commit to `Luna/profiling/results_kraken2.md`. Each command also writes a `.txt`
output file under `~/results/profiling/pending/` for later analysis.

Setup (one-time):
```bash
mkdir -p ~/results/profiling/pending
cd ~/results/profiling/pending
KK=~/tools/kraken2/classify     # or ~/kraken2-build/classify if you rebuilt
DB=~/data/kraken2_db
IN=~/results/basecalling/reads_hac.fastq
```

---

## M1. Hash table header — cell type, capacity, load factor

**Why:** decides prefetch stride (12 vs 16 cells), confirms 40-bit vs 32-bit cells.
Load factor near 1.0 → long clusters → prefetch is high-value.

```bash
python3 - <<'PY' | tee m1_hash_header.txt
import struct, os
p = os.path.expanduser("~/data/kraken2_db/hash.k2d")
with open(p, "rb") as f:
    cap, sz, kb, vb = struct.unpack("<QQQQ", f.read(32))
file_bytes = os.path.getsize(p)
cell_b = (file_bytes - 32) / cap
print(f"capacity      : {cap:,}")
print(f"size          : {sz:,}")
print(f"load_factor   : {sz/cap:.4f}")
print(f"key_bits      : {kb}")
print(f"value_bits    : {vb}")
print(f"key+value     : {kb+vb}  ({'40-bit cell' if kb+vb==40 else '32-bit cell'})")
print(f"file_bytes    : {file_bytes:,}")
print(f"implied bytes/cell : {cell_b:.3f}")
print(f"cells/cache_line   : {64/cell_b:.2f}")
PY
```

**Decision:** if load_factor > 0.95 → expect long probe chains → Patch 1 (prefetch) is
high-leverage. If 40-bit cell → Patch 1's PF_STRIDE = 12.

---

## M2. DTLB pressure — does huge pages help?

**Why:** decides whether Patch 2 (MADV_HUGEPAGE) is worthwhile.

```bash
numactl --cpunodebind=0 --membind=0 \
  perf stat -e cycles,instructions,\
dTLB-loads,dTLB-load-misses,\
dTLB-stores,dTLB-store-misses,\
iTLB-load-misses \
  $KK -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
      -p 32 -R /dev/null -O /dev/null $IN \
  2>&1 | tee m2_dtlb.txt
```

**Decision:**
- `dTLB-load-misses / dTLB-loads > 0.005` (0.5 %) → Patch 2 is worth applying.
- If already < 0.001 → THP is already active; Patch 2 is a no-op.

Cross-check whether THP is already in use on file-backed mmap:
```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# Look for AnonHugePages / FileHugePages in:
cat /proc/$(pgrep classify | head -1)/smaps_rollup 2>/dev/null | grep -i huge
```

---

## M3. perf annotate — exact line in Get() causing the LL misses

**Why:** confirms whether the probe-load (`table_[idx].value(...)`) is the dominant miss
line, or whether `hashed_key()` and `value()` are reading the cell separately and we should
combine.

```bash
# Build with -g (Makefile already has -g) and ensure debug info present.
file $KK | grep -i 'with debug'

numactl --cpunodebind=0 --membind=0 \
  perf record -g --call-graph dwarf -e LLC-load-misses \
  -o m3_perf.data \
  $KK -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
      -p 32 -R /dev/null -O /dev/null $IN
perf annotate --stdio -i m3_perf.data --symbol=CompactHashTable | tee m3_annotate.txt | head -120
```

Note: if the symbol name differs (template mangling), try
`--symbol-filter=CompactHashTable` or `perf report -i m3_perf.data --stdio | head`
to find the exact mangled name first.

**Decision:** the line accounting for > 80 % of LLC misses inside Get() should be the
`table_[idx].value(value_bits_)` read. If it isn't, the inferred algorithm is still wrong
somewhere — re-investigate.

---

## M4. DRAM bandwidth — latency-bound vs bandwidth-bound

**Why:** if uncore IMC counters show DRAM well under saturation (≤ 50 % of peak), we are
**latency-bound** → LRU + prefetch are the right fix. If close to peak → we are
**bandwidth-bound** → compression / DB shrink is needed.

```bash
# Discover IMC PMU names (varies on Sapphire Rapids)
ls /sys/devices/ | grep uncore_imc

# Then measure (CHA list may also vary; first two are sufficient)
numactl --cpunodebind=0 --membind=0 \
  perf stat -a -e \
'uncore_imc_0/cas_count_read/','uncore_imc_0/cas_count_write/',\
'uncore_imc_1/cas_count_read/','uncore_imc_1/cas_count_write/' \
  $KK -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
      -p 32 -R /dev/null -O /dev/null $IN \
  2>&1 | tee m4_imc.txt
```

**Decision:**
- Peak DDR5-4800 per channel = 38.4 GB/s; Sapphire Rapids has 8 channels per socket.
  Single-socket peak ≈ 300 GB/s.
- Compute observed BW: total cas_count × 64 B / wall_seconds.
- Observed / peak < 0.5 → latency-bound (expected) → patches 1, 4 win.
- Observed / peak > 0.7 → bandwidth-bound → defer LRU; investigate DB compression instead.

---

## M5. K-mer reuse rate — validate LRU cache hit-rate before implementing

**Why:** Patch 4 (thread-local LRU) only pays if reuse rate is > 20 %. Measuring it
beforehand prevents wasted patching.

There are two ways:

### M5a (quick, approximate) — minimizer histogram via instrumented build

Add a one-line emit to `classify.cc::ClassifySequence`:
```cpp
// Just before: if (*minimizer_ptr != last_minimizer) {
fprintf(stderr, "MMK %llu\n", (unsigned long long) *minimizer_ptr);
```
Rebuild, then:
```bash
# Tiny run on 5 % of reads
head -n 1000000 $IN > /tmp/sample.fastq    # 250 000 reads
~/kraken2-build/classify -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
   -p 1 -R /dev/null -O /dev/null /tmp/sample.fastq 2> /tmp/mmk.txt
grep '^MMK ' /tmp/mmk.txt | awk '{print $2}' | sort | uniq -c | sort -rn \
  > m5_minimizer_histogram.txt
awk '{n++; s+=$1; if($1>1) r+=$1-1} END {
  printf "unique=%d total=%d reuse_rate=%.4f top1_share=%.4f\n",
    n, s, r/s, NR ? 0 : 0
}' m5_minimizer_histogram.txt | tee -a m5_minimizer_histogram.txt

# Top-1024 cumulative coverage (sanity for direct-mapped cache size choice)
head -n 1024 m5_minimizer_histogram.txt | awk '{s+=$1} END {print "top1024_count="s}' \
  | tee -a m5_minimizer_histogram.txt
```

Revert the fprintf and rebuild.

### M5b (precise, slow) — perf record on Get() call sites

If M5a fprintf is too noisy, count Get() calls precisely:
```bash
perf stat -e \
'cycles','instructions',\
'cpu/event=0xc4,umask=0x00,name=br_inst_retired_all_branches/' \
   $KK ... # not as direct; M5a is simpler
```

**Decision:**
- `reuse_rate > 0.30` → Patch 4 likely lands −20 %+
- `0.10 < reuse_rate < 0.30` → marginal; halve `LRU_BITS` to 13 (8 K entries)
- `reuse_rate < 0.10` → skip Patch 4, focus on Patches 1, 2, 3, 6, 8

---

## M6. perf c2c — false sharing (only matters if scaling beyond 32T)

**Why:** thread sweet spot is 32T; not strictly needed yet. Run if we want to revisit
NUMA Patch 5.

```bash
numactl --cpunodebind=0 --membind=0 \
  perf c2c record -o m6_c2c.data -- \
  $KK -H $DB/hash.k2d -t $DB/taxo.k2d -o $DB/opts.k2d \
      -p 32 -R /dev/null -O /dev/null $IN
perf c2c report -i m6_c2c.data --stdio | head -150 | tee m6_c2c.txt
```

**Decision:** "HITM" events > 5 % of cache traffic → cross-thread sharing on the hash
table is a real issue. With a read-only mmap table, HITM should be ~0 — confirms.

---

## M7. MinimizerScanner vectorisation status (do we have AVX-512?)

**Why:** confirms whether compiler is auto-vectorising and decides whether SIMD work on
MinimizerScanner is needed.

```bash
objdump -d $KK | grep -cE '\bv[a-z]+.*%(y|z)mm' | tee m7_simd_count.txt
# Also break down by opcode width
objdump -d $KK | grep -cE '\b[a-z]+.*%ymm' | tee -a m7_simd_count.txt
objdump -d $KK | grep -cE '\b[a-z]+.*%zmm' | tee -a m7_simd_count.txt
```

**Decision:**
- zmm count > 0 → AVX-512 in use already.
- Only ymm → AVX2 only; rebuild with `-march=sapphirerapids` (Patch 3).
- xmm only → no vectorisation; biggest gap is the MinimizerScanner sliding minimum.

---

## Reporting template (paste this back)

```
M1: cell=??-bit  load_factor=0.???  cells/line=??
M2: dTLB miss rate = ??? %     ← > 0.5 % → apply Patch 2
M3: top miss line in Get() = "?"
M4: observed_DRAM_GBps=???   peak=300   ratio=??   ← < 0.5 → latency-bound
M5: minimizer reuse_rate = 0.??   top-16K coverage = ?? %   ← > 0.30 → apply Patch 4
M6: HITM events = ?? %                       ← > 5 % → revisit NUMA
M7: zmm_count=??  ymm_count=??  xmm_count=??
```
