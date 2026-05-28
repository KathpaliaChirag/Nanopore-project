# Kraken-2 Optimisation Report
**Authors:** Chirag K (CK) + Chirag Suthar  
**Due:** 2026-05-31  
**Supervisor:** Kolin sir, Chayanika mam

---

## 1. Baseline Profiling Recap (already delivered 2026-05-26)

| Tool | Result | Verdict |
|---|---|---|
| `perf stat` (WSL2) | 34.24% cache miss rate, 301M misses/run | Memory-bound |
| `gprof` (WSL2) | 67% runtime in `CompactHashTable::Get()`, 9.87M calls | Hotspot confirmed |
| AMD uProf (local) | IPC = 0.55 | CPU stalling, not computing |

**Key arithmetic:** 301M misses ÷ 9.87M calls = ~30 L3 misses per `CompactHashTable::Get()` call.  
At ~100 ns per L3 miss: 301M × 100 ns = **~30 seconds** in L3 miss latency per run.

**Limitation of baseline:** perf run on WSL2/Hyper-V — `LLC-load-misses` counter may be L2, not LLC. Needs verification on Luna (bare metal, `perf_event_paranoid = 1` confirmed).

---

## 2. Deeper Profiling (to run on Luna)

### 2.1 Confirm memory-bound vs I/O-bound

**Command — Luna:**
```bash
perf stat -e LLC-load-misses,LLC-loads,stalled-cycles-backend,stalled-cycles-frontend,\
dram_bw_use:total,page-faults,instructions,cycles \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null
```

**What to record:**

| Metric | Expected (memory-bound) | Expected (I/O-bound) |
|---|---|---|
| `stalled-cycles-backend` | >50% of cycles | moderate |
| `page-faults` | low (<1000) | very high (millions) |
| `LLC-load-misses` | high (>100M) | moderate |
| DRAM bandwidth utilisation | >50% peak | low |

**Interpretation:**
- High `stalled-cycles-backend` + high `LLC-load-misses` + low `page-faults` = **memory-bound** (RAM latency, not disk)
- High `page-faults` = **I/O-bound** (DB being paged in from disk — fix: ensure DB fits in RAM before run)

### 2.2 Per-function LLC miss rates (cachegrind on Luna)

```bash
valgrind --tool=cachegrind --cachegrind-out-file=~/cg_kraken2.out \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null

cg_annotate --auto=yes ~/cg_kraken2.out > ~/cachegrind_report.txt
```

**What to record:**
- `DLmr` (LLC data read misses) per function — top 5 functions
- Expected: `CompactHashTable::Get()` dominates `DLmr`
- If another function also has high `DLmr` — that is a second optimisation target

### 2.3 Source-line hotspot inside CompactHashTable::Get()

```bash
perf record -g --call-graph dwarf \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null

perf report --sort=dso,symbol,srcline
```

Press `a` on `CompactHashTable::Get()` to annotate source lines. Note:
- Which line accounts for the most samples?
- Is it the hash table read (`table_[idx]`)? The hash computation? The linear probe loop?

### 2.4 NUMA and DRAM bandwidth (Luna has 2 NUMA nodes)

```bash
# Check NUMA topology
numactl --hardware

# Run with NUMA binding — force DB and process to same NUMA node
numactl --cpunodebind=0 --membind=0 \
    ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null

# Compare runtime with and without numactl binding
```

**What to record:** is there a speedup when forcing NUMA locality? If yes — cross-NUMA traffic is contributing to memory latency.

---

## 3. K-mer Reuse Distribution (validates LRU cache ROI)

The 6-second savings estimate (20% hit rate × 9.87M calls × 30 misses × 100 ns) assumes 20% of `CompactHashTable::Get()` calls are for k-mers we've already seen. This needs empirical validation.

**Script to run:**
```python
# Count k-mer frequency distribution in barcode02.fastq
from collections import Counter

k = 35
kmer_counts = Counter()

with open("barcode02.fastq") as f:
    lines = f.readlines()
    # FASTQ: line 0 = header, line 1 = sequence, line 2 = +, line 3 = qual
    for i in range(1, len(lines), 4):
        seq = lines[i].strip()
        for j in range(len(seq) - k + 1):
            kmer_counts[seq[j:j+k]] += 1

total_kmers = sum(kmer_counts.values())
unique_kmers = len(kmer_counts)

# How many k-mers are seen more than once?
repeated = {kmer: count for kmer, count in kmer_counts.items() if count > 1}
repeat_hits = sum(count - 1 for count in repeated.values())

print(f"Total k-mers:          {total_kmers:,}")
print(f"Unique k-mers:         {unique_kmers:,}")
print(f"Repeat lookup savings: {repeat_hits:,} ({100*repeat_hits/total_kmers:.1f}%)")

# Top-100 k-mers: what % of all lookups do they cover?
top100 = kmer_counts.most_common(100)
top100_hits = sum(c for _, c in top100)
print(f"Top-100 k-mers cover:  {100*top100_hits/total_kmers:.1f}% of all lookups")
```

**What to record:**
- `repeat_hits / total_kmers` = actual LRU hit rate if all repeated k-mers are cached
- Top-100 coverage = hit rate achievable with a tiny 100-entry cache
- If top-100 coverage > 20%: the 6-second estimate is conservative, cache ROI is real

---

## 4. Optimisation Proposals

### Proposal A — Hot-K-mer LRU Cache

**Idea:** Wrap `CompactHashTable::Get()` with a small LRU cache. Before calling into the hash table, check a fast in-memory cache of recently-seen k-mers. On a hit, skip the hash table lookup entirely.

**Basis:** 
- `CompactHashTable::Get()` = 67% of runtime, 9.87M calls
- Barcode02 = 100% P. aeruginosa → k-mer access is highly non-uniform (one species dominates)
- Each cache hit saves ~30 L3 misses × 100 ns = ~3 µs per call

**Implementation sketch:**
```cpp
// In classify/kraken2.cc, around CompactHashTable::Get() call:
thread_local LRUCache<uint64_t, taxid_t> kmer_cache(1024);  // 1024-entry per-thread cache

taxid_t get_kmer_taxid(uint64_t kmer, CompactHashTable &cht) {
    taxid_t *cached = kmer_cache.get(kmer);
    if (cached) return *cached;
    taxid_t result = cht.Get(kmer);
    kmer_cache.put(kmer, result);
    return result;
}
```

**Complexity:** Low — wrapper around existing function, no change to data structures.  
**Expected speedup:** 20% hit rate → ~6 s saved per run. 50% hit rate (plausible for single-species samples) → ~15 s saved.  
**Risk:** Cache eviction policy; thread safety (use per-thread cache to avoid locks).

---

### Proposal B — Sequential ESKAPE Query Pipeline

**Idea:** Instead of one Kraken-2 query against a combined ESKAPE DB, run 6 sequential queries, one per pathogen. Short-circuit once a dominant species is found.

**Basis:**
- Clinical samples are typically dominated by one pathogen (barcode02 = 100% P. aeruginosa)
- Per-pathogen DB is ~108 MB (650 MB ÷ 6) — fits entirely in Luna's L3 (210 MB)
- When the active DB fits in L3, `CompactHashTable::Get()` becomes L3 hits instead of RAM accesses → 100 ns → 10 ns per lookup

**Implementation sketch:**
```bash
for pathogen in E S K A P E; do
    kraken2 --db eskape_${pathogen}_db --report ${pathogen}_report.txt input.fastq
    # If dominant species found (>80% reads), stop
    top_pct=$(awk 'NR==2{print $1}' ${pathogen}_report.txt)
    if (( $(echo "$top_pct > 80" | bc -l) )); then
        echo "Dominant species found: $pathogen"
        break
    fi
done
```

**Complexity:** Low for the query loop; medium for building 6 separate sub-databases.  
**Expected speedup:** If dominant species found in first 1–2 queries → 3–5× reduction in total lookup work. Worst case (no dominant species) = 6× slower.  
**Risk:** Accuracy may drop — k-mers shared between pathogens are assigned to the first matching DB. Need accuracy validation against combined-DB baseline on golden dataset.

---

### Proposal C — [To be determined from deeper profiling]

After running cachegrind + perf record on Luna, a third target may emerge (e.g. a secondary function with high DLmr, or a vectorisation opportunity in the hash function itself).

Placeholder candidates:
- **Hash function SIMD vectorisation** — if the MurmurHash3 inner loop is a significant contributor, batch-hashing 4–8 k-mers per AVX2 instruction
- **Compact hash table prefetching** — software prefetch for the next k-mer's table bucket while processing current one (reduces effective latency if accesses are somewhat predictable)

---

## 5. Results Tables (to fill after Luna runs)

### 5.1 Luna perf stat — Kraken-2

| Metric | WSL2 baseline | Luna result | Notes |
|---|---|---|---|
| Wall time (s) | 105.87 s (gprof) / 159.4 s (perf) | TBD | |
| cache-misses | 301M | TBD | |
| LLC-load-misses | N/A (WSL2) | TBD | real LLC counter |
| stalled-cycles-backend | N/A | TBD | |
| page-faults | N/A | TBD | I/O-bound check |
| IPC | 0.55 (AMD uProf) | TBD | expect similar |
| DRAM BW utilisation | N/A | TBD | |

### 5.2 cachegrind — per-function LLC misses

| Function | DLmr (LLC read misses) | % of total |
|---|---|---|
| CompactHashTable::Get() | TBD | TBD |
| (2nd function) | TBD | TBD |
| (3rd function) | TBD | TBD |

### 5.3 K-mer reuse distribution

| Metric | Value |
|---|---|
| Total k-mer lookups | TBD |
| Unique k-mers | TBD |
| Repeated lookup fraction | TBD % |
| Top-100 k-mer coverage | TBD % |
| Estimated LRU hit rate (1024 entries) | TBD % |

---

## 6. Summary of Proposals

| Proposal | Complexity | Expected speedup | Accuracy risk | Priority |
|---|---|---|---|---|
| A — Hot-K-mer LRU Cache | Low | 20–50% runtime reduction | None | High |
| B — Sequential ESKAPE Pipeline | Medium | 3–5× for dominant-species samples | Needs validation | Medium |
| C — TBD from profiling | TBD | TBD | TBD | TBD |

---

## 7. References

- Baseline profiling: `final_report.md`
- Kraken-2 source: `https://github.com/DerrickWood/kraken2`
- `CompactHashTable` implementation: `src/compact_hash.h`, `src/compact_hash.cc`
- Luna server specs: `Luna/luna_stats.md`
- Profiling plan: `plan.md`
