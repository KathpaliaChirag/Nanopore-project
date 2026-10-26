# Kraken2 CompactHashTable::Get() - Source-Verified Optimisation Patches

**Source read from:** https://github.com/DerrickWood/kraken2 (master, as of 2026-05-29)
**Files used:** `src/compact_hash.h`, `src/kv_store.h`, `src/classify.cc`, `src/mmscanner.cc`, `src/mmap_file.cc`, `src/Makefile`
**Baseline to beat:** 4.405 s (hac, 32T, numactl node0)

---

## 0. Three corrections to the inferred Get() in the goal

the goal's pseudocode assumes 64-bit cells, linear probing, simple key comparison. the real code in `src/compact_hash.h` differs on three points. those differences change what optimisations make sense:

### 0.1 Cells are 32-bit or 40-bit packed, not 64-bit
```cpp
struct CompactHashCell { uint32_t data; };                   // CompactHash32 path
struct CompactHashCell40 { uint32_t a; uint8_t b; } __attribute__((packed));  // CompactHash40
```
- 32-bit cell → 16 cells per 64-byte cache line
- 40-bit cell → 12 cells per 64-byte cache line (misaligned, packed)
- the cell type is decided at DB-load time by `GetKVStoreCellType()` reading `key_bits + value_bits` from the header (32 or 40)

**implication:** linear probing already touches many consecutive cells per cache line. software prefetch [a CPU hint that starts loading data before it's needed, so the wait is hidden] needs to skip ≥1 cache line ahead (16 or 12 cells, not 1) to actually overlap with DRAM latency.

### 0.2 The default Makefile already enables LINEAR_PROBING
```makefile
CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -fPIC -g
CXXFLAGS += -DLINEAR_PROBING
```
`second_hash()` returns 1 under this flag, so adjacent probes land on adjacent cells and the HW prefetcher [a CPU unit that predicts and preloads upcoming memory] can help. most DBs are built with this flag, which is standard. if yours is, switching it off would require rebuilding the DB.

**implication:** the "every probe is a random L3 miss" story in the goal is wrong. most probes inside a cluster live on the same cache line as the prior probe. the 96.24% cachegrind miss rate likely means this: the first probe of each Get() misses LLC [last-level cache, the biggest and slowest cache before DRAM], then several probes hit L1/L2 from that same line, then we cross a line and miss again. so ~30 misses per call is roughly ~30 cache-line crossings, multiplied by very long probe chains under high load factor (need to confirm with `size_/capacity_`).

### 0.3 `hash->Get()` is virtual through `KeyValueStore`
```cpp
class KeyValueStore { virtual hvalue_t Get(hkey_t key) const = 0; };
```
every call from classify.cc pays one vtable load [the lookup a program does to find the right virtual function at runtime, instead of knowing it at compile time]. LTO [link-time optimisation, letting the compiler see across files when it optimises] is the cheap fix for this. one-shot devirtualisation needs templating the classify loop on cell type instead.

### 0.4 classify.cc already has a 1-entry "cache"
```cpp
if (*minimizer_ptr != last_minimizer) { ... taxon = hash->Get(*minimizer_ptr); ... }
else { taxon = last_taxon; }
```
the 9.87M Get() calls (gprof, 1T) are already after this skip. a bigger thread-local LRU [least-recently-used, a cache eviction policy that discards the entry accessed longest ago] cache has to outperform this same-as-last-minimizer skip to be worth adding.

---

## 1. Cheap measurements to run on Luna before patching

we need these numbers before touching any code, because they decide two of the patch parameters below: whether prefetch stride should be 16 or 12, and whether huge pages are worth adding. they confirm cell type, load factor, and DTLB [data translation lookaside buffer, a small CPU cache that maps memory addresses to physical pages] pressure.

```bash
# 1. Read the hash.k2d header (capacity, size, key_bits, value_bits)
xxd -l 32 ~/data/kraken2_db/hash.k2d
# bytes 0-7  = capacity (LE u64)
# bytes 8-15 = size      (LE u64) → load factor = size/capacity
# bytes 16-23 = key_bits (LE u64)
# bytes 24-31 = value_bits (LE u64)
# key_bits + value_bits = 32  → 32-bit cells (CompactHashCell)
# key_bits + value_bits = 40  → 40-bit cells (CompactHashCell40)

# 2. Cell type sanity: filesize / cell_size should ≈ capacity
stat -c%s ~/data/kraken2_db/hash.k2d

# 3. DTLB pressure (likely high on 8 GB array with 4 KB pages)
perf stat -e dTLB-load-misses,dTLB-loads,iTLB-load-misses \
  ~/tools/kraken2/classify ... ~/results/basecalling/reads_hac.fastq

# 4. Get() call count (lets us compute LLC misses/call accurately)
perf stat -e LLC-load-misses,LLC-loads -- ...
# Combined with perf record + symbol counts gives calls/sec.

# 5. THP status
cat /sys/kernel/mm/transparent_hugepage/enabled
# Want [always] or [madvise]
```

if load factor > 0.95, linear probing is producing long clusters, so prefetch will help a lot.
if DTLB-load-misses > 1% of dTLB-loads, huge pages will help.

---

## 2. Patches - apply in this order, measure after each

all patches target `~/kraken2-src/src/`. after every patch:
```bash
cd ~/kraken2-src/src && make clean && make -j 96
cp classify ~/kraken2-build/
# baseline run
numactl --cpunodebind=0 --membind=0 \
  ~/kraken2-build/classify -H ~/data/kraken2_db/hash.k2d \
  -t ~/data/kraken2_db/taxo.k2d -o ~/data/kraken2_db/opts.k2d \
  -p 32 -R /tmp/r.txt -O /dev/null \
  ~/results/basecalling/reads_hac.fastq 2>&1 | tail -5
# capture cache stats
numactl --cpunodebind=0 --membind=0 \
  perf stat -e cycles,instructions,LLC-loads,LLC-load-misses,dTLB-load-misses,dTLB-loads \
  ~/kraken2-build/classify -H ... -p 32 -O /dev/null reads_hac.fastq
```

compare wall time to 4.405 s and LLC-load-misses to the prior best.

---

### Patch 1 - software prefetch in the probe loop (Proposal E)

**why it helps given the numbers:** 96% of LLC misses are in Get(). with linear probing, probe N+stride is one cache line ahead. issuing `__builtin_prefetch` for that line each iteration starts a DRAM read ~100 ns before the load that needs it, so the load now hits L1 instead of stalling on an L3 miss.

**edit `src/compact_hash.h`, replace the existing `Get()` body:**

```cpp
template<typename Cell>
hvalue_t CompactHashTable<Cell>::Get(hkey_t key) const {
  uint64_t hc = MurmurHash3(key);
  uint64_t compacted_key = hc >> (64 - key_bits_);
  size_t idx = hc % capacity_;
  size_t first_idx = idx;
  size_t step = 0;
  // One cache line ahead in cells:
  //   sizeof(CompactHashCell)   = 4 → stride 16
  //   sizeof(CompactHashCell40) = 5 → stride 12
  constexpr size_t PF_STRIDE = 64 / sizeof(Cell);
  while (true) {
    // Issue DRAM read for the line we'll touch ~PF_STRIDE iters from now.
    size_t pf_idx = idx + PF_STRIDE;
    if (pf_idx >= capacity_) pf_idx -= capacity_;
    __builtin_prefetch(&table_[pf_idx], 0 /*read*/, 0 /*non-temporal*/);

    if (! table_[idx].value(value_bits_))
      break;
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0)
      step = second_hash(hc);
    idx += step;
    idx %= capacity_;
    if (idx == first_idx)
      break;
  }
  return 0;
}
```

**expected delta:** −5% to −15% wall time. the HW prefetcher already streams ahead under linear probing, but only ~2 lines. explicit prefetch extends that further, and it works around double hashing if LINEAR_PROBING were ever turned off.

**risk:** zero. same semantics, prefetch is a no-op hint.

---

### Patch 2 - MADV_HUGEPAGE + MADV_WILLNEED on the mmap'd hash table (Memory layout)

**why it helps:** 8 GB over 4 KB pages works out to 2,097,152 page entries. Sapphire Rapids' DTLB only holds ~96 4 KB entries, so random-ish probes cause constant DTLB misses, and each miss adds ~10 ns and possibly a page-walk LLC miss on top. switching to 2 MB huge pages [larger memory pages that need far fewer TLB entries to cover the same data] cuts that to 4,096 page entries, which fits comfortably in the second-level TLB (1,024-2,048 entries). each DTLB miss saved also avoids roughly one cache line of page-walk traffic.

**edit `src/mmap_file.cc`, inside `OpenFile()` after the `mmap` [memory-map, mapping a file directly into a process's address space instead of reading it into a buffer] call:**

```cpp
  fptr_ = (char *) mmap(0, filesize_, prot_flags, map_flags, fd_, 0);
  if (fptr_ == MAP_FAILED) {
    err(EX_OSERR, "unable to mmap %s", filename);
  }
+ // Optimisation: request 2 MB pages for the kernel-level mapping and
+ // pre-page the entire file so first-touch faults don't appear in the
+ // hot path. Both are hints — kernel may ignore on small files / hostile
+ // THP settings.
+ (void) madvise(fptr_, filesize_, MADV_HUGEPAGE);
+ (void) madvise(fptr_, filesize_, MADV_WILLNEED);
+ (void) madvise(fptr_, filesize_, MADV_RANDOM);
  valid_ = true;
```

order matters here: `MADV_HUGEPAGE` first, then `WILLNEED`, then `RANDOM` (this tells the kernel to skip its readahead, since access is non-sequential). add `#include <sys/mman.h>` if it isn't already in this file (it is, via `kraken2_headers.h`).

**prereq on Luna:**
```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# If "never", run: echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

**expected delta:** −3% to −8% wall time, mostly from dTLB-load-misses dropping by 10-100×.

**risk:** none for the query path. the build path also goes through MMapFile, but it's unaffected.

---

### Patch 3 — compiler flags: -march=sapphirerapids + LTO + -funroll-loops

**why it helps:**
- `-march=sapphirerapids` enables BMI2 / AVX-512 / ADX, and lets the compiler use `MULX`, fast `POPCNT`, and 512-bit ops in `MurmurHash3`. MurmurHash is called once per Get() and dominates the compute portion of cold misses.
- `-flto` lets the compiler inline `hash->Get()` across translation units (devirtualisation), which eliminates the vtable load and probably inlines the whole Get() into ClassifySequence's inner loop.
- `-funroll-loops` lets the compiler unroll the probe loop and overlap prefetch and compare cycles.

**edit `src/Makefile`:**

```makefile
-CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -fPIC -g
-CXXFLAGS += -DLINEAR_PROBING
+CXXFLAGS = $(KRAKEN2_SKIP_FOPENMP) -Wall -std=c++11 -O3 -fPIC -g \
+           -march=sapphirerapids -mtune=sapphirerapids \
+           -flto=auto -funroll-loops -fno-plt
+CXXFLAGS += -DLINEAR_PROBING
+LDFLAGS  += -flto=auto -fuse-linker-plugin
```

if you want to keep portability across nodes, swap `-march=sapphirerapids` for `-march=native` on the build host.

**expected delta:** −5% to −12% wall time, mostly from devirtualisation and a tighter inner loop.

**risk:** none on Sapphire Rapids. the binary won't run on older Xeons, which is fine for a Luna-only build.

---

### Patch 4 — thread-local direct-mapped k-mer cache (Proposal A, lean version)

**why it helps:** the existing same-as-last-minimizer skip catches sliding-window collisions, but not cross-window or cross-read reuse. microbial reads have heavy k-mer redundancy, and a 16K-entry direct-mapped cache costs only 256 KB per thread (fits in L2 on Sapphire Rapids: 2 MB/core), so it intercepts a meaningful fraction of Get() calls. every hit avoids ~30 LLC misses, roughly ~3 µs of DRAM latency.

**the hit rate has to be validated first.** run this awk script on a dump of all minimizer values for the hac input:
```bash
~/kraken2-build/classify ... 2>/dev/null | head -50000 > /dev/null   # placeholder
# Better: instrument classify.cc to emit minimizers, then:
sort minimizers.txt | uniq -c | awk '{n++; s+=$1; if ($1>1) r+=$1-1} END {print "unique="n, "total="s, "reuse_rate="r/s}'
```
if `reuse_rate > 0.20`, the patch is worth it.

**edit `src/classify.cc`, add near top of file (after `using` declarations):**

```cpp
namespace {
constexpr size_t LRU_BITS = 14;            // 16 384 entries
constexpr size_t LRU_SIZE = 1u << LRU_BITS;
constexpr size_t LRU_MASK = LRU_SIZE - 1;
constexpr uint64_t LRU_MIX = 0x9E3779B97F4A7C15ULL;  // golden ratio (Fibonacci hash)

struct LRUEntry {
  uint64_t key;    // full minimizer; 0 is sentinel "empty"
  taxid_t  val;
};
// Per-thread cache. 16K * 16B = 256 KB (fits in L2 per core).
thread_local LRUEntry lru_cache[LRU_SIZE] = {};
}  // namespace
```

**then in `ClassifySequence`, replace the inner Get() block:**

```cpp
          if (*minimizer_ptr != last_minimizer) {
            bool skip_lookup = false;
            if (idx_opts.minimum_acceptable_hash_value) {
              if (MurmurHash3(*minimizer_ptr) < idx_opts.minimum_acceptable_hash_value)
                skip_lookup = true;
            }
            taxon = 0;
-           if (! skip_lookup)
-             taxon = hash->Get(*minimizer_ptr);
+           if (! skip_lookup) {
+             // Thread-local direct-mapped cache in front of the 8 GB DRAM lookup.
+             size_t slot = (*minimizer_ptr * LRU_MIX) >> (64 - LRU_BITS);
+             LRUEntry &e = lru_cache[slot];
+             if (e.key == *minimizer_ptr && e.key != 0) {
+               taxon = e.val;
+             } else {
+               taxon = hash->Get(*minimizer_ptr);
+               e.key = *minimizer_ptr;
+               e.val = taxon;
+             }
+           }
            last_taxon = taxon;
            last_minimizer = *minimizer_ptr;
```

notes:
- we never store `key == 0` as a valid entry. the `e.key != 0` guard exists so a zero-initialised slot never looks like a phantom hit if a real minimizer happens to be 0 (vanishingly unlikely, but cheap to guard against).
- `thread_local` on a 256 KB array means the storage is per-thread but only initialised on first use of that thread. OpenMP threads persist for the whole run, so this is fine.
- no synchronisation is needed, since each thread owns its slice.

**expected delta:** −10% to −30% wall time, conditional on reuse rate ≥ 20%. this stacks with Patch 1, because the cache absorbs the cheapest calls and leaves the long-probe cases, which Patch 1 accelerates, for DRAM.

**risk:** correctness is preserved as long as the `e.key == *minimizer_ptr` comparison is exact, and it is (full 64-bit key compare). false hits are impossible.

**tuning:** if profiling shows a low hit rate, halve `LRU_BITS` to 13 (8K entries, 128 KB/thread). if reuse is huge (a cross-read dominant species), bump it to 16 (64K entries, 1 MB/thread, still fits L2).

---

### Patch 5 — per-socket DB replica via interleave (NUMA, conditional)

**only apply this if** `perf c2c` shows >10% HITM events on the hash table region, or the 32T baseline is consistently better than 64T spread across both sockets (it is: 4.405 s @ node0-only vs ~5.6 s @ 96T). skipping for now, since the current best is already node-bound.

if we do want both sockets active at 64T+: mmap two copies (one per socket) and route threads to the local copy via `numa_alloc_local` [NUMA, non-uniform memory access, means each CPU socket has memory that's faster for it to reach than memory attached to the other socket] after `numa_run_on_node`. that's a ~30-line patch to load_index + ProcessFiles. happy to write it once Patch 1-4 are measured.

---

## 3. Expected combined result

if each patch lands at the middle of its expected range, and they stack independently (which they roughly do, since each targets a different bottleneck), this is what the run adds up to:

| Patch | Mechanism | Independent delta | Cumulative |
|---|---|---:|---:|
| Baseline | — | — | 4.405 s |
| Patch 3 (flags) | inlining + tighter ASM | −8 % | 4.05 s |
| Patch 2 (huge pages) | dTLB | −5 % | 3.85 s |
| Patch 1 (prefetch) | DRAM latency hide | −10 % | 3.47 s |
| Patch 4 (thread LRU) | skip DRAM entirely on hits | −20 % | 2.77 s |

target: ≤3.0 s wall, ≥30% below the 4.405 s best. stop if any patch lands at <2% delta.

---

## 4. What I'm NOT proposing yet

- **SIMD MinimizerScanner:** cachegrind shows zero LL misses there, and gprof says it's 18.74% of 1T runtime. vectorising would help, but the queue-based sliding-window minimum is hard to SIMD-ify [SIMD, single instruction multiple data, doing the same operation on several values at once] cleanly. wait until Get() is no longer the bottleneck.
- **hash algorithm change (Robin Hood / cuckoo):** requires rebuilding the 8 GB DB and changing the on-disk format. defer.
- **DB compression:** needs uncore_imc cas_count first, to confirm bandwidth-bound vs latency-bound. right now the indicators say latency-bound (low IPC, high stall %), so LRU and prefetch beat compression as the next move.
- **sort minimizers by genomic locality before build:** a DB build change, weeks of work.

---

## 5. Decision pipeline for each measured patch

```
After each rebuild + run:
  delta := (baseline - new_walltime) / baseline
  if delta >= 0.02:  keep; baseline := new_walltime; move to next patch
  if delta <  0.02:  discard the patch; move to next
  if delta <  0  :   revert; investigate (compiler bug? cache thrash? false sharing?)
```

stop the whole programme when two consecutive patches both land below 2%. at that point returns are diminishing, and any remaining wins live in DB-rebuild territory.
