# cycle 2, round 2, agent C (source auditor): the hot-set front table against the real S19 source

read-only ssh to luna, files read: ~/chirag_K/tools/kraken2-src-s19/src/{classify.cc, compact_hash.cc, compact_hash.h, kv_store.h, mmscanner.cc, Makefile}. nothing run, nothing written on luna. line numbers are from that tree. note ~/e1/s19_front does not exist yet (round 1 plan is not built).

## 1. the exact per-lookup data flow

per sequence, per mate, per frame (classify.cc 802-895):
1. `scanner.NextMinimizer()` returns a pointer to one 64-bit minimizer value (mmscanner.cc 116-197, it returns the previous value again when the window minimizer did not change, so roughly one return per base). `scanner.is_ambiguous()` flags windows containing an N-like base.
2. `fill()` (821-835) copies the value into `pf[n].min`. if not ambiguous: `pf[n].hc = MurmurHash3(min)` (kv_store.h 30-38) and `pf[n].idx = hash->PrefetchIndex(hc)` which is `FastMod(hc)` plus a prefetch of `table_[idx]`.
3. batch of la_batch=16 slots (K2_B), two batches in flight (cur, nxt). resolve loop (844-890), per slot:
   - ambiguous: taxon = AMBIGUOUS_SPAN_TAXON, no lookup.
   - else if `min != last_minimizer`: skip_lookup if `hc < minimum_acceptable_hash_value` (the min-clear-hash filter), else `taxon = hash->GetAt(min, hc, idx)`. then `last_taxon`, `last_minimizer` update, `minimizer_hit_groups++` and `curr_taxon_counts[taxon].add_kmer(min)` (hyperloglog, only when --report) if taxon != 0.
   - else (same minimizer as previous slot) taxon = last_taxon, no lookup.
   - run-length merge into `hit_counts` (S15), `taxa.push_back(taxon)`.
4. `last_minimizer`, `last_taxon`, the two PfSlot arrays are locals of the frame loop. dedup is only for consecutive equal minimizers within one frame of one mate, so it never crosses reads, mates or frames.

`GetAt` (compact_hash.cc 179-197): `compacted_key = hc >> (32 + value_bits_)`, start at `idx`, loop: if cell value is 0 stop and return 0; if cell hashed_key equals compacted_key return its value; else step. the `key` argument is unused. the method is `const`, touches only `table_`, `capacity_`, `value_bits_`. no locks, no writes, no counters.

answer to question 1: yes. `GetAt(min, hc, idx)` is a pure function of `hc` given a loaded db, because `idx = hc mod capacity_` is derived from hc and the probe step is a function of hc. there are no side effects. the side effects in the loop (hit groups, HLL add, run counts) all happen after GetAt on the returned taxon and read `min` and `taxon` only. so a front table may replace exactly the single call `hash->GetAt(...)` at line 859 and nothing else. everything downstream stays untouched, which is what makes byte-identity achievable.

S19 build detail: Makefile line 4 has `-DLINEAR_PROBING`, so `second_hash` returns 1 (step 1). a miss on a present line usually touches the same 64 byte line (16 cells), so a normal lookup is one cache line, rarely two. the double-hashing code is compiled out. this matters for front-table value: a hit saves one line (one DRAM/L3 miss), not a probe chain.

## 2. the exact key, and why storing the big-table answer keeps output identical

what the big table stores: a 32-bit cell = (hc >> (32+value_bits)) in the top `32 - value_bits` bits and the taxid in the low `value_bits` bits (CompactHashCell, compact_hash.h 15-40). so the big table identifies a k-mer by only `key_bits = 32 - value_bits` bits of hc plus the start slot. two different minimizers with the same start slot and the same compacted key are indistinguishable, so an absent minimizer can get a wrong nonzero taxon (the false positive of kraken2opti_report). the value for such a minimizer is still a deterministic function of its own hc.

MurmurHash3 here is the 64-bit finalizer, a bijection on uint64. so full `hc` identifies the minimizer exactly (hc == 0 only for min == 0).

rule: key the front table on the full 64-bit hc, and store as value whatever the big table returns for that hc, computed by the big table itself, never from ground truth. then:
- a hit returns `GetAt(hc)` by construction, true hit or false positive, 0 or nonzero. byte-identical.
- a minimizer that is not in the front table goes to the big table as today. a different hc that happens to share compacted key and start slot with a hot hc does not match in the front table (full 64-bit compare), so it still gets the big table's answer, including its false positive. byte-identical.
- the wrong design would be to build the hot set from the db's true k-mers (value known to be right) or to store 0 for "absent in truth". that would change output wherever the big table has a false positive. do not do it. the builder must call the db's own lookup (`GetWithHash(0, hc)` is public, same probe as GetAt: same idx, same step) on every hot hc, including hot hc whose answer is 0 (negative caching).
- correctness precondition: the hot file is valid only for the exact db file and the exact index options (k, l, spaced seed mask, toggle mask, revcom_version, minimum_acceptable_hash_value). header must store capacity, size, key_bits, value_bits, k, l, toggle_mask, min_clear_hash, plus a checksum of 4096 sampled cells from fixed offsets. mismatch means refuse and run stock (or die). a stale file otherwise gives wrong taxa silently.
- hc == 0 hazard: empty slots are zero keys, so a probe with hc 0 would "match" an empty way. guard the probe with `hc != 0` (hc 0 simply bypasses to the big table). builder drops hc 0.
- the compacted key is not a valid front key (too few bits, many collisions), and the start idx is not either. full hc only.

## 3. building the hot set offline with minimal code

no usable frequency exists in the db itself (it stores one cell per k-mer, no counts), so a pilot run is required. minimal route using the existing tracer pattern (e1/tracer_patch.diff, hunk after the GetAt call, thread_local buffer, one file per tid):
- change the one traced line to log the full hash, not idx: `e1_tr.add(pf[i].hc);` (8 bytes, no hit bit needed). log it only on the non-dedup branch, right where the GetAt call is (that is what the tracer already does, so the stream equals the real GetAt calls, ~116.6 per read at 8GB). skip_lookup slots are not traced, correct, they never reach the table.
- offline tool `hotbuild.cpp` (about 80 lines, g++ -O2, links compact_hash.o, mmap_file.o, omp_hack.o from the s19 tree, opens the db with `memory_mapping=true` so no 103GB copy):
  1. read all trace files, sort the uint64s in RAM (109M x 8B = 0.9 GB; use `std::sort`, or radix), run-length count.
  2. take the top K by count (K = lines x 5 x 0.8 for F2, about 262K), ties arbitrary.
  3. for each, `v = table.GetWithHash(0, hc)`; this touches 262K random cells of the mmapped db, seconds.
  4. place into the line layout of section 4 by descending count, first free way, drop when the set is full; write header + lines.
- held-out test per round 1: train on half A, run half B. in-sample test: train on the same reads. the file is a few MB.
- cost to produce the training stream: one pilot run with the traced binary at T=32 (trace overhead was about 3% in e1).
- an in-process alternative (no trace files) is not worth it: a per-thread count table would add exactly the memory traffic we are trying to measure away.

## 4. code sketch

```cpp
// front.h (new)
struct alignas(64) FrontLine {
  uint64_t key[5];     // full hc, 0 = empty
  uint32_t val[5];     // exact GetAt(hc) result, may be 0 (negative cache)
  uint32_t pad[1];     // total 40 + 20 + 4 = 64
};
static_assert(sizeof(FrontLine) == 64, "line");
extern const FrontLine *g_front;   // null = disabled
extern uint64_t g_nsets;

inline const FrontLine *front_line(uint64_t hc) {
  return g_front + (uint64_t)(((unsigned __int128)(hc >> 32) * g_nsets) >> 32);
}
// returns true and sets v on hit. hc==0 never hits.
inline bool front_probe(uint64_t hc, uint32_t &v) {
  const FrontLine *L = front_line(hc);
  for (int w = 0; w < 5; w++)
    if (L->key[w] == hc && hc != 0) { v = L->val[w]; return true; }
  return false;
}

// front.cc: load once, before any parallel region
const FrontLine *g_front = nullptr; uint64_t g_nsets = 0;
void LoadFront(const char *path, const CompactHashTable &t, const IndexOptions &o) {
  FILE *f = fopen(path, "rb"); if (!f) errx(EX_NOINPUT, "hot file");
  FrontHeader h; fread(&h, sizeof h, 1, f);
  if (h.capacity != t.capacity() || h.size != t.size() || h.value_bits != t.value_bits()
      || h.k != o.k || h.l != o.l || h.toggle != o.toggle_mask
      || h.min_clear != o.minimum_acceptable_hash_value || h.cell_sig != SampleSig(t))
    errx(EX_DATAERR, "hot file does not match this db");   // never fall back silently
  size_t bytes = h.nsets * sizeof(FrontLine);
  void *p = nullptr;
  posix_memalign(&p, (size_t)2 << 20, (bytes + (2<<20) - 1) & ~((size_t)(2<<20) - 1));
#ifdef MADV_HUGEPAGE
  madvise(p, bytes, MADV_HUGEPAGE);          // before first touch, like S14
#endif
  fread(p, 1, bytes, f); fclose(f);          // first touch here, one thread
  g_front = (const FrontLine *)p; g_nsets = h.nsets;
}
```
SampleSig needs a public accessor for sampled cells (add `const CompactHashCell *cells() const`) or hash the 4096 values via GetValueCounts-free path; an accessor is a 1 line change in compact_hash.h.

hook in classify.cc. PfSlot gains two fields: `struct PfSlot { uint64_t min, hc; size_t idx; bool amb; bool done; uint32_t val; };`

```cpp
// fill(), replacing lines 828-831
if (! pf[n].amb) {
  pf[n].hc = MurmurHash3(pf[n].min);
  pf[n].done = false;
  uint32_t v;
  if (g_front && front_probe(pf[n].hc, v)) { pf[n].done = true; pf[n].val = v; }
  else pf[n].idx = hash->PrefetchIndex(pf[n].hc);   // hits issue no DRAM prefetch
}
// resolve loop, replacing line 859
if (! skip_lookup)
  taxon = pf[i].done ? (taxid_t) pf[i].val
                     : hash->GetAt(pf[i].min, pf[i].hc, pf[i].idx);
```
this is the "probe in fill" form. the probes of the 16 slots are independent so the core overlaps several L2/L3 hits. a hit in the front table skips both the prefetch and the GetAt. the three-stage version of round 1 (prefetch front line for batch i+2 first) only adds value if the 4-16 MB front lines miss L2 often; try it second.

env switch: `K2_HOT` unset gives `g_front == nullptr`, one well predicted branch. call `LoadFront` in `classify()` right after `load_index` (classify.cc 260-273), before `omp_set_num_threads` and the parallel region at 499. same place for the daemon path (ClassifyDaemon).

builder placement and eviction are static, so no per-thread state at all.

## 5. pitfalls

- OpenMP and init: front table is const after load and shared, no locks, no first-touch by workers. every thread reads one copy. do not load inside `#pragma omp parallel` (would load 32 times or race). the PfSlot arrays are stack locals per frame, so `done` must be set in the else path too (I set it for every non-ambiguous slot; ambiguous slots never read it).
- NUMA: luna is two socket (105 MB L3 per socket in the repo notes). a single first-touch copy lives on one socket and the other socket reads it remotely, which can erase a 10 ns advantage. F1 (1 MB) is cheap to replicate: build one copy per socket (allocate and fill inside a per-socket `numactl`-pinned thread, or use `mbind`), and pick by `sched_getcpu()` cached per thread. measure local vs remote before deciding; 64-thread runs (hyperthreads) share cores' L2 so L2-resident sizing halves.
- the ambiguous path: `pf[n].amb` slots never compute hc or idx and never reach GetAt. hook must not touch them (hc is stale garbage there). the code above keeps this.
- skip_lookup (minimum_acceptable_hash_value): the check at 853-856 stays before the front table use, so a hot hc below the threshold is still dropped to taxon 0 exactly as stock. keep `pf[i].done` use inside `if (!skip_lookup)`. the hot file header stores the threshold so a mismatch refuses.
- quick mode (`goto finished_searching`) and run-length merge happen after the taxon is chosen. unaffected.
- `last_minimizer` dedup: a duplicate slot still probes the front table or prefetches the big table in `fill` (stock also prefetches it). harmless; could skip the probe when `pf[n].min == pf[n-1].min`, but then idx must stay valid for the stale path, so leave it.
- translated search (`use_translated_search`): minimizers come from amino-acid lmers with a different alphabet encoding, `hc = MurmurHash3(min)` is still the same function and GetAt the same, so the front table is valid per db. but the hot set must be trained on a translated pilot run (different frequency profile, 6 frames, plus READING_FRAME_BORDER markers that are not lookups). test with a translated db only if the paper claims it; otherwise refuse `K2_HOT` when `use_translated_search` to avoid claims we did not test.
- paired end: ClassifySequence loops both mates, each frame calls fill with fresh PfSlot arrays and a fresh `last_minimizer`; the hook is inside, so both mates are covered. the pilot for a paired run should use paired input. HLL `add_kmer` uses `min`, unchanged.
- `-M` memory mapping: the db is a file mmap (no S14 hugepage copy), orthogonal to the front table, which is its own allocation. the front table still gets hugepages via posix_memalign + madvise. the page-fault behaviour of the big table changes with -M, so benchmark front-vs-stock under the same flag.
- THP availability: madvise only requests; check `AnonHugePages` in /proc/self/smaps after load for the front region. a 1 MB table does not need a hugepage at all, 4 and 16 MB do (otherwise TLB misses on 4 KB pages eat the gain; 4 MB is 1024 pages, more than an L1 dTLB).
- hash independence: set index uses `hc >> 32`, the big table uses `hc mod capacity_`; the compacted key uses the top `32 - value_bits` bits. the set index overlaps the compacted key bits, which is harmless (the front key is the full hc) but means hot k-mers in the same set often share top bits; the 64-bit full compare is what keeps it exact. use the multiply-shift on the high 32 bits so nsets need not be a power of two.
- false sharing: none, front is read-only. but the builder must `fread` into memory that no thread has touched; do not store counters inside the lines.
- what a hit does not save: with S15/S16 prefetching GetAt is already under 1% of cpu (e1). the gain from a hit is the avoided DRAM line (bandwidth, L3 pollution of the 100 GB table), not the latency. this is why step 0 (the exposed Td_eff) in round 1 gates the build.
- hc == 0: guarded in `front_probe` and dropped by the builder.
- ordering of ties in the report (round 6 note) is unaffected; the hook changes no container.
- scalar compare cost: 5 compares per probe on 8-byte keys; an AVX2 `_mm256_cmpeq_epi64` on keys 0..3 plus scalar key 4 is possible but the loop above compiles to a short unrolled chain; try scalar first.

## summary (6 lines)

1. `GetAt` is a pure const function of hc (start idx and step derive from hc, `key` arg unused), so only the single call at classify.cc 859 may be replaced; HLL, hit groups, runs all consume the returned taxon unchanged.
2. key the front table on full 64-bit hc (Murmur finalizer is a bijection) and store the big table's own answer (`GetWithHash(0, hc)`, also negative answers), never ground truth; then false positives are copied, not fixed, and output is byte-identical by construction.
3. guard hc == 0 against empty ways, bypass ambiguous slots, keep the skip_lookup check first, and put db capacity/size/value_bits/k/l/toggle/min-clear and a cell checksum in the hot-file header and refuse on mismatch.
4. build offline: change the e1 tracer line to log `pf[i].hc`, sort and count, take top K, look up each with the db's own `GetWithHash` on an mmapped db, write 64 byte lines (5 keys + 5 values); train on half A and test on B.
5. hook: probe in `fill()` (hits skip PrefetchIndex), `pf.done/val` consumed at the GetAt call; shared hugepage table loaded once before the parallel region, `K2_HOT` unset means stock; S19 is compiled with -DLINEAR_PROBING so a normal lookup is one line.
6. main risks: NUMA remote reads of a one-socket copy, THP not actually backing 4 to 16 MB, stale hot file silently wrong, translated/paired pilots must match the run type, and the gain is DRAM traffic not latency, so step 0 share measurement still gates everything.
