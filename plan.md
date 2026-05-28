# Kraken-2 Optimisation Plan
**Authors:** Chirag K + Chirag Suthar  
**Supervisor:** Kolin sir, Chayanika mam  
**Direction set:** Meeting 4, 2026-05-28  
**Immediate deliverable:** `kraken2_optimisation_report.md` — due 2026-05-31  
**Full plan (research-grade, professor-verifiable):** `C:\Users\chira\.claude\plans\snappy-plotting-fox.md`

---

## CURRENT STATUS

### What is proven (no need to redo)

| Tool | Finding |
|---|---|
| perf stat (WSL2) | 34.24% cache miss rate, 301M misses per run |
| gprof (WSL2) | `CompactHashTable::Get()` = 67% of runtime, 9.87M calls |
| AMD uProf (local) | IPC = 0.55 — CPU stalling on memory, not computing |

**Derived:** 301M misses ÷ 9.87M calls = ~30 L3 misses per Get() call. At 100 ns/miss → **~30 s of L3 miss latency per run** (baseline: 105.87 s total).

**Platform limitations:** WSL2/Hyper-V blocks LLC-load-misses and stalled-cycles-backend hardware counters. All accurate profiling goes on **Luna (bare metal, perf_event_paranoid=1)**.

### Key hardware advantage on Luna

Luna's 210 MB L3 cache means a single-pathogen ESKAPE DB (~108 MB = 650 MB ÷ 6) fits **entirely in L3**. This is the physical foundation for Proposal B.

---

## PLATFORM MAP

| Capability | WSL2/Ryzen | Minerva | Luna |
|---|---|---|---|
| cache-misses (overall) | ✅ done | ✅ | ✅ |
| LLC-load-misses (real) | ❌ Hyper-V | ✅ | ✅ |
| stalled-cycles-backend | ❌ Hyper-V | ✅ | ✅ |
| TMA (dram_bound, l3_bound) | ❌ | partial | ✅ Sapphire Rapids |
| cachegrind per-function | ✅ (slow, swapped) | ❌ disk full | ✅ fast (503 GB) |
| perf record / source annot. | partial | ✅ | ✅ |
| NUMA analysis | ❌ single socket | ✅ | ✅ 2 NUMA nodes |
| AVX-512 + AMX | ❌ (AVX2 only) | ✅ | ✅ |
| L3 size | 16 MB | 66 MB | **210 MB ← key** |
| **Status** | baseline done | disk full | **PRIMARY** |

---

## STEP 1 — KRAKEN-2 SOURCE STUDY (before any coding)

Clone and annotate on Luna:
```bash
git clone https://github.com/DerrickWood/kraken2.git ~/kraken2-src
```

**Files to read completely:**

| File | Why |
|---|---|
| `src/compact_hash.h` | CompactHashTable class — the data structure we're optimising |
| `src/compact_hash.cc` | CompactHashTable::Get() — the 67% bottleneck |
| `src/classify.cc` | ClassifySequence() — the insertion point for the LRU cache |
| `src/kmer_counter.cc` | MinimizerScanner — 18.74% secondary bottleneck |
| `src/kraken2_data.h` | Core types (taxid_t, uint64_t) — data size affects memory layout |
| `src/utilities.h` | Helpers — potential SIMD opportunities |

**Questions to answer from source (annotate findings):**
- [ ] Exact bit split: key_bits vs taxon_id_bits per entry?
- [ ] What hash function maps key → table index? (MurmurHash? custom?)
- [ ] Is there any existing prefetch call in Get()?
- [ ] Actual load factor of the 8 GB DB? (affects probe chain length)
- [ ] Is the DB loaded via mmap() or malloc()? (affects NUMA allocation policy)
- [ ] Does MinimizerScanner compute canonical k-mers correctly? (min(kmer, revcomp))
- [ ] Any lock or thread synchronisation inside Get()? (expect: none, DB is read-only)
- [ ] How is `--threads` handled — do threads share one CompactHashTable instance?

**Inferred Get() algorithm (verify in source):**
```cpp
taxid_t CompactHashTable::Get(uint64_t key) const {
    uint64_t idx = key % size_;            // O(1) position
    uint64_t probe_key = key & key_mask_;  // bits stored in entry
    while (true) {
        uint64_t entry = table_[idx];      // ← L3 miss here (random 8 GB jump)
        if (entry == 0) return 0;          // empty = not in DB
        if ((entry >> value_bits_) == probe_key)
            return entry & value_mask_;    // hit
        idx = (idx + 1) % size_;           // linear probe
    }
}
```

Cache hostility: `table_[idx]` jumps to a pseudo-random location in an 8 GB flat array. L3 cache = 16 MB local, 210 MB on Luna → L3 miss rate ~97% for the 8 GB DB.

---

## STEP 2 — LUNA DEEP PROFILING (produces 2026-05-31 deliverable)

### Prerequisites

```bash
# Build Kraken-2 on Luna
git clone https://github.com/DerrickWood/kraken2.git ~/kraken2-src
cd ~/kraken2-src && ./install_kraken2.sh ~/kraken2-build

# Transfer data (from local or Minerva)
scp -r ~/eskape_db CK@luna:~/eskape_db
scp ~/barcode02.fastq CK@luna:~/barcode02.fastq
```

### Phase A — Cold vs Warm perf stat (memory-bound vs I/O-bound)

```bash
# COLD (flush page cache first)
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
time perf stat -e LLC-load-misses,LLC-loads,stalled-cycles-backend,\
stalled-cycles-frontend,page-faults,instructions,cycles \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /tmp/r.txt ~/barcode02.fastq \
  > /dev/null 2>&1 | tee ~/luna_perf_cold.txt

# WARM (page cache already hot)
time perf stat -e LLC-load-misses,LLC-loads,stalled-cycles-backend,\
stalled-cycles-frontend,page-faults,instructions,cycles \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /tmp/r.txt ~/barcode02.fastq \
  > /dev/null 2>&1 | tee ~/luna_perf_warm.txt
```

**Decision logic:**
- `page-faults` cold >> warm AND `LLC-load-misses` drops warm → first run is I/O-bound
- `LLC-load-misses` stays high in warm run → **memory-bound** (RAM latency, not disk) — expected
- `stalled-cycles-backend` > 60% → confirmed memory-bound

### Phase B — TMA (Top-Down Microarchitecture Analysis)

Luna has Sapphire Rapids hardware TMA counters — turns "memory-bound" from inference into hardware fact.

```bash
perf stat -e tma_retiring,tma_bad_speculation,tma_frontend_bound,tma_backend_bound,\
tma_memory_bound,tma_core_bound,tma_l1_bound,tma_l2_bound,tma_l3_bound,tma_dram_bound \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq \
  > /dev/null 2>&1 | tee ~/luna_tma.txt
```

Expected: `tma_dram_bound` dominant (>50% of stall cycles).

### Phase C — cachegrind per-function LLC miss rates

```bash
# Use smaller input (cachegrind is 10-50x slower)
head -n 100000 ~/barcode02.fastq > ~/barcode02_small.fastq

valgrind --tool=cachegrind \
  --cachegrind-out-file=~/cg_kraken2.out \
  --LL=210000000,16,64 \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02_small.fastq \
  > /dev/null

cg_annotate --auto=yes ~/cg_kraken2.out | head -100 > ~/cachegrind_report.txt
```

**Note:** `--LL=210000000,16,64` simulates Luna's actual 210 MB L3. Run `getconf LEVEL3_CACHE_SIZE` on Luna to verify.

**Expected:** `CompactHashTable::Get()` dominates `DLmr` (LLC data read misses), ~70-85% of total.

### Phase D — Source-line hotspot inside CompactHashTable::Get()

```bash
# Build with -g (debug symbols) + keep -O2 for realistic profile
perf record -g --call-graph dwarf -e LLC-load-misses \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null

perf annotate --stdio CompactHashTable::Get > ~/perf_annotate_cht.txt
```

Look for: which exact line (`table_[idx]`? hash computation? probe loop?) has highest sample count.

### Phase E — NUMA analysis

```bash
numactl --hardware   # check topology

# Default run (may be cross-NUMA)
/usr/bin/time -v ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null

# NUMA-bound run
numactl --cpunodebind=0 --membind=0 \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null
```

If speedup > 5% with `numactl`: cross-NUMA traffic is significant → add to Proposal F.

### Phase F — DRAM bandwidth

```bash
perf stat -e uncore_imc/cas_count_read/,uncore_imc/cas_count_write/ \
  ~/kraken2-build/kraken2 --db ~/eskape_db --report /dev/null ~/barcode02.fastq > /dev/null
# CAS events × 64 bytes = total DRAM bytes transferred
```

Latency-bound: DRAM utilisation < 30% but LLC miss latency high → LRU cache is the right fix.  
Bandwidth-bound: DRAM utilisation > 70% → need to reduce data volume (Bloom filter, DB compression).

---

## STEP 3 — K-MER REUSE MEASUREMENT

Validates LRU cache ROI. Run on Luna (or locally):

```bash
python3 ~/kmer_reuse.py ~/barcode02.fastq 35 > ~/kmer_reuse_results.txt
```

Script is at `scripts/kmer_reuse.py` (see full plan for complete 80-line version).

**Expected for barcode02 (100% P. aeruginosa):**
- P. aeruginosa genome ≈ 6 MB ≈ 5.6M unique 35-mers
- 104,829 reads × ~350 k-mers/read ≈ 36M total lookups
- Reuse rate: 36M / 5.6M ≈ **6.4× average** → **~84% of lookups are repeatable from cache**
- Top-1024 k-mers: captures ~5-15% of lookups (power-law distribution)

---

## STEP 4 — OPTIMISATION PROPOSALS

### Proposal A — Thread-Local LRU Cache ★★★ HIGH PRIORITY

**Target:** CompactHashTable::Get() (67% runtime)  
**Complexity:** Low (~100 lines)  
**Expected speedup:** 15–50% runtime reduction  
**Accuracy risk:** Zero (cache stores exact results from Get())

Direct-mapped cache (power-of-2 size, `key & MASK` addressing — no multiplication):

```cpp
// src/kmer_cache.h
template<int CAPACITY = 4096>
class KmerCache {
    static_assert((CAPACITY & (CAPACITY-1)) == 0, "must be power of 2");
    struct Entry { uint64_t key; uint32_t value; bool valid; };
    std::array<Entry, CAPACITY> table_;
    static constexpr uint64_t MASK = CAPACITY - 1;
public:
    KmerCache() { table_.fill({0, 0, false}); }
    uint32_t get(uint64_t key) const {
        auto& e = table_[key & MASK];
        return (e.valid && e.key == key) ? e.value : UINT32_MAX;
    }
    void put(uint64_t key, uint32_t value) {
        table_[key & MASK] = {key, value, true};
    }
};
```

```cpp
// In src/classify.cc — wrap CompactHashTable::Get()
thread_local KmerCache<4096> kmer_cache;  // 4096 × 16 bytes = 64 KB fits in L2

taxid_t get_with_cache(const CompactHashTable &cht, uint64_t minimizer) {
    uint32_t cached = kmer_cache.get(minimizer);
    if (cached != UINT32_MAX) return static_cast<taxid_t>(cached);
    taxid_t result = cht.Get(minimizer);
    kmer_cache.put(minimizer, result);
    return result;
}
```

`thread_local` eliminates all locking — each thread has its own cache, no synchronisation needed.

**Benchmark:** cache sizes 1024, 2048, 4096, 8192, 16384 on Luna with warm DB.

---

### Proposal B — Sequential ESKAPE Query Pipeline ★★★ HIGH PRIORITY

**Target:** Reduce active DB size to fit in Luna's L3  
**Complexity:** Medium (DB build scripts + shell wrapper)  
**Expected speedup:** 3–5× for dominant-species samples; same as baseline worst case  
**Accuracy risk:** Medium (shared k-mers; needs validation)

**The cache math:** 650 MB ESKAPE DB ÷ 6 pathogens ≈ **108 MB per pathogen < 210 MB L3**.  
After first read, subsequent lookups hit L3 (10 ns) instead of DRAM (100 ns) → **10× per-lookup speedup**.

Order pathogens by clinical prevalence from AIIMS data: P. aeruginosa first (dominates barcodes 01-07, 14).

```bash
for pathogen in p_aeruginosa k_pneumoniae s_aureus e_faecium a_baumannii e_cloacae; do
    ~/kraken2-build/kraken2 --db ~/eskape_db_${pathogen} \
        --report /tmp/report_${pathogen}.txt $INPUT > /dev/null
    top_pct=$(awk '$4=="S" {print $1}' /tmp/report_${pathogen}.txt | sort -rn | head -1)
    if (( $(echo "$top_pct > 80" | bc -l) )); then
        echo "DOMINANT: $pathogen ($top_pct%)"; break
    fi
done
```

**Accuracy validation required:** compare per-read classification between combined DB and sequential pipeline on all 14 AIIMS barcodes. Acceptable: dominant species call matches, confidence within ±2%.

---

### Proposal D — Batch Prefetch Pipelining ★★★ HIGH IMPACT

**Target:** Hide DRAM latency (100 ns) by issuing prefetch for N k-mers before fetching any result  
**Complexity:** Medium (~50 lines; requires modifying classification loop)  
**Expected speedup:** 1.34–2.68× total (2–4× on CompactHashTable::Get())  
**Accuracy risk:** Zero

```cpp
const int BATCH = 8;

void ClassifyBatch(const CompactHashTable &cht,
                   const uint64_t *minimizers, int n, taxid_t *results) {
    uint64_t table_idxs[BATCH];
    // Stage 1: issue all prefetches
    for (int i = 0; i < n; i++) {
        table_idxs[i] = minimizers[i] % cht.size_;
        __builtin_prefetch(&cht.table_[table_idxs[i]], 0, 0);
    }
    // Stage 2: perform lookups (memory may already be in cache)
    for (int i = 0; i < n; i++) {
        results[i] = cht.GetByIndex(table_idxs[i], minimizers[i]);
    }
}
```

Requires accumulating BATCH minimizers from MinimizerScanner before calling Get(). Complementary to Proposal A — prefetch benefits cache misses that Proposal A doesn't catch.

---

### Proposal E — Single-Line Prefetch in Get() ★ LOW COMPLEXITY

**Target:** Issue prefetch at start of Get() to reduce first-access latency  
**Complexity:** 1 line  
**Expected speedup:** 2–8% total

```cpp
taxid_t CompactHashTable::Get(uint64_t key) const {
    uint64_t idx = key % size_;
    __builtin_prefetch(&table_[idx], 0, 1);  // ← add this line
    // rest of probe loop unchanged
    ...
}
```

Unlike matrix-multiply (where hardware prefetcher already handles sequential access), Kraken-2's random access defeats the hardware prefetcher → software prefetch is NOT redundant here.

---

### Proposal F — NUMA Binding ★ ZERO CODE

**Target:** Eliminate cross-NUMA memory latency (+40 ns per miss)  
**Complexity:** Zero (command-line flag)  
**Expected speedup:** 5–20% on Luna (dual-socket)

```bash
numactl --cpunodebind=0 --membind=0 \
    ~/kraken2-build/kraken2 --db ~/eskape_db ~/barcode02.fastq > output.kraken
```

Verify by measuring wall time with and without `numactl` on Luna.

---

### Proposal G — Bloom Filter Pre-Screen ★★ MEDIUM PRIORITY

**Target:** Skip hash table lookups for k-mers not in DB (reduces misses for unclassified reads)  
**Complexity:** Medium (build filter at DB construction, load and query in classify.cc)

**Impact on barcodes 09-12 (50-60% unclassified):** eliminates 50-60% of hash table lookups.

XOR filter (1.23 bits/key) for 47M entries = ~57.8 MB — fits in Luna's 210 MB L3.  
Standard Bloom filter at 1% FP rate requires ~329 MB — too large for L3.

---

### Proposal C — MinimizerScanner SIMD Vectorisation ★★ RESEARCH TIER

**Target:** MinimizerScanner::NextMinimizer() (18.74% runtime, 354M calls)  
**Hardware:** AVX-512 on Luna (8× uint64_t per instruction), AVX2 on Ryzen (4×)

Process 4–8 minimizer windows in parallel per iteration. If Kraken-2 uses ntHash, a vectorized ntHash library (with published AVX2 implementation) may be a near-drop-in replacement.

Expected: 2–4× speedup on the scanning function → **~4-8% total pipeline improvement**.

---

### Proposal I — Learned Index (Research Horizon)

Replace CompactHashTable with a small neural network (Kraska et al. 2017 SIGMOD) that maps minimizer hash → table position. Learned index for 47M entries ≈ 1-10 MB (fits in L3). Reduces random DRAM jumps from O(probe_length) to near O(1). Publishable result if it outperforms LRU cache.

---

## STEP 5 — IMPLEMENTATION TIMELINE

| Phase | Dates | Tasks |
|---|---|---|
| **Phase 0** (now) | 2026-05-28 to 05-31 | Source study, Luna profiling A-F, k-mer reuse, fill report |
| **Phase 1** | June 1–7 | Proposal F (numactl, 0 code) → Proposal E (1-line prefetch) → Proposal A (LRU cache) |
| **Phase 2** | June 8–21 | Proposal D (batch prefetch) → Proposal B (sequential ESKAPE, accuracy validation) → Proposal G (Bloom filter) |
| **Phase 3+** | June 22+ | Proposal C (SIMD) → Proposal H (DB partitioning) → Proposal I (learned index) |

---

## STEP 6 — VALIDATION PROTOCOL

```bash
# 5 runs, cold cache each time
for i in {1..5}; do
    sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
    /usr/bin/time -v ~/kraken2-build/kraken2 \
        --db ~/eskape_db --report /tmp/report_${i}.txt ~/barcode02.fastq \
        > /dev/null 2>&1 | grep "wall clock" >> timing_${version}.txt
done
```

**Metrics per run:** wall time, LLC-load-misses, stalled-cycles-backend, cache hit rate (from instrumented build), classification accuracy (diff report files).

**Accuracy check:**
```bash
diff baseline.kraken optimized.kraken  # expect zero diff for Proposals A/D/E/F
```

---

## FILES TO CREATE / MODIFY

| File | Action |
|---|---|
| `plan_old.md` | ← was `plan.md` (done) |
| `plan.md` | ← this file (done) |
| `kraken2_optimisation_report.md` | Fill sections 2–5 from Luna results (due 2026-05-31) |
| `scripts/kmer_reuse.py` | Create — k-mer reuse analysis script |
| `scripts/sequential_eskape.sh` | Create — sequential ESKAPE pipeline wrapper |
| `src/kmer_cache.h` | Create — Proposal A LRU cache class |
| `src/classify.cc` | Modify — wrap Get() with cache (Proposal A) |
| `src/compact_hash.cc` | Modify — add prefetch call (Proposal E) |
| `src/compact_hash.h` | Modify — expose GetByIndex() for Proposal D |

---

## IMMEDIATE ACTIONS (2026-05-28 to 05-30)

- [ ] SSH to Luna, run Phase A (perf stat cold/warm)
- [ ] Run Phase B (TMA)
- [ ] Run Phase C (cachegrind with `--LL=210000000,16,64`)
- [ ] Run Phase D (perf record + source annotation)
- [ ] Run Phase E (NUMA numactl comparison)
- [ ] Run Phase F (DRAM bandwidth via uncore_imc)
- [ ] Run k-mer reuse script on barcode02.fastq (k=35)
- [ ] Read compact_hash.h, compact_hash.cc, classify.cc (annotate answers to 8 questions above)
- [ ] Fill result tables in `kraken2_optimisation_report.md`
- [ ] Push complete report to GitHub by 2026-05-31

---

## RESEARCH POSITIONING

**Novel contributions (not published):**
1. Hot-K-mer LRU cache for Kraken-2 clinical metagenomics (non-uniform access exploited)
2. Sequential ESKAPE pipeline exploiting Luna's 210 MB L3 to fit per-pathogen DB
3. Batch prefetch pipelining for compact hash table in bioinformatics context
4. TMA-based profiling of Kraken-2 on Sapphire Rapids (hardware characterisation)

**Academic framing:**
> "We show that clinical metagenomics samples exhibit a highly non-uniform k-mer access distribution — one species dominates — enabling a lightweight thread-local cache to recover 15-50% of runtime lost to cache misses in Kraken-2's compact hash table. We further demonstrate that per-species database partitioning allows the active database slice to fit in modern server L3 caches (Luna: 210 MB L3 vs 108 MB per-pathogen DB), reducing per-lookup latency from DRAM (~100 ns) to L3 (~10 ns) for dominant-species queries."

**Target venues:** ISMB, RECOMB, Bioinformatics journal, FAST/EuroSys.

---

*Full plan with complete code, derivations, and professor-verifiable analysis: `C:\Users\chira\.claude\plans\snappy-plotting-fox.md`*  
*Previous plan (baseline profiling, gprof/cachegrind commands, matmul study): `plan_old.md`*
