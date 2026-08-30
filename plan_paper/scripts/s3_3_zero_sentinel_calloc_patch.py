# S3.3 - zero-sentinel + calloc allocator, fixing the SEPARATE slowdown
# cliff at >=1,048,576 sets (2026-08-26: up to 22x slower, LLC-miss
# 13%->85%). This is distinct from S3.0's crash fix - S3.0 moved the
# array off thread_local static storage; this patch fixes why touching
# that array (wherever it lives) was slow in the first place.
#
# Diagnosis (from plan_paper/s3_s4_debate_report_2026-08-27.md Q1):
# S2Entry's sentinel values (tag=UINT64_MAX, taxon=TAXID_MAX) are
# non-zero, so allocating the array forces a real constructor loop that
# eagerly writes those values into every entry - defeating the OS's
# normal "new memory starts as one shared zero page, only faulted in on
# first write" optimization, regardless of whether the array is
# thread_local, heap, static, or anything else. The real fix needs two
# changes together:
#   1. Redefine "empty" as all-zero-bits (S2_EMPTY_TAG = 0) and remove
#      S2Entry's default member initializers, making it a trivially
#      constructible type.
#   2. Allocate via calloc instead of new[] - for allocations above
#      glibc's ~128KB mmap threshold (true for every size in this
#      project's [4096, 262144] range - even the smallest, 4,096 sets,
#      is already 256KB), calloc is backed by fresh OS pages that are
#      zero for free, never eagerly touched. A non-trivial type's new[]
#      cannot use this shortcut no matter how the memory was obtained.
#
# One real edge case this introduces: a genuine minimizer value of
# exactly 0 would be indistinguishable from "empty." Handled as a
# permanent, harmless cache-miss special case in S2Lookup/S2Insert -
# that one value (vanishingly rare in practice) simply never benefits
# from caching; correctness is completely unaffected either way, since
# S2 only ever decides whether hash->Get() needs to run again.
#
# S3_MAX_SETS stays at 262,144 in this patch - deliberately NOT raised
# yet. The actual slowdown cliff was only ever observed at >=1,048,576
# sets, above this ceiling, so proving the fix works needs a separate
# temporary large-size build (same technique as S3.0's crash test)
# compared directly against the already-logged 22x-slower baseline,
# before deciding whether to raise the ceiling for real.
#
# Run from ~/tools/kraken2-src-fresh/src, against the S3.1/S3.2-patched
# classify.cc (tag safe/S3.1-S3.2).

path = "classify.cc"
with open(path) as f:
    content = f.read()

old_block = '''static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;      // "nothing here yet" - matches S1's convention

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
};

#include <memory>

// S3.1: Luna's real per-socket L3, confirmed via `lscpu` on 2026-08-30
// (210 MiB total / 2 sockets = 105 MiB/socket; `lscpu -e` also confirmed
// NUMA node == socket, i.e. no Sub-NUMA Clustering splitting this).
static const uint64_t S3_LLC_PER_SOCKET_BYTES = 105ULL * 1024 * 1024;

// S3.2: safety fraction of the per-socket LLC this cache may claim -
// genuinely open, not yet resolved empirically (Round-1 debate guesses
// ranged 0.05-0.5). 0.25 is an interim placeholder pending a real sweep
// against benchmark data - sed this constant to test other values, same
// pattern as every prior size sweep in this project.
static const double S3_LLC_FRACTION = 0.25;

// S3.0 confirmed crash-free up to 262,144 sets with the heap-pointer
// fix; S3.3's pre-touch experiment (not yet run) is needed before
// trusting anything above this - the separate slowdown cliff at
// >=1,048,576 sets is still unaddressed. 4,096 is the floor this
// project has always used.
static const size_t S3_MAX_SETS = 262144;
static const size_t S3_MIN_SETS = 4096;

static thread_local std::unique_ptr<S2Entry[]> s2_cache;
static thread_local std::unique_ptr<uint8_t[]> s2_next_way;
static thread_local size_t s2_num_sets = 0;

// S3.1/S3.2: N_sets(T) = floor(f x LLC_per_socket / (ways x sizeof(entry) x T)),
// rounded down to a power of 2 (S2SetIndex needs a bitmask), clamped to
// [S3_MIN_SETS, S3_MAX_SETS]. T is read live via omp_get_num_threads()
// from inside the active parallel classification region, not hardcoded -
// a size safe for 1 thread can be catastrophic at 96 (confirmed 2026-08-26).
static inline size_t S3ComputeNumSets() {
  int t = omp_get_num_threads();
  if (t < 1) t = 1;
  uint64_t raw = (uint64_t) (S3_LLC_FRACTION * S3_LLC_PER_SOCKET_BYTES
                             / (S2_WAYS * sizeof(S2Entry) * (uint64_t) t));
  size_t sets = S3_MIN_SETS;
  while (sets * 2 <= raw && sets * 2 <= S3_MAX_SETS)
    sets *= 2;
  return sets;
}

static inline void S2EnsureInit() {
  if (! s2_cache) {
    s2_num_sets = S3ComputeNumSets();
    s2_cache.reset(new S2Entry[s2_num_sets * S2_WAYS]);
    s2_next_way.reset(new uint8_t[s2_num_sets]());
  }
}'''

new_block = '''static const size_t S2_WAYS = 4;

// S3.3: redefined to 0 (was UINT64_MAX) so calloc's zero-filled memory
// is already a valid "empty" cache, avoiding the eager per-entry
// constructor write that caused the >=1,048,576-set slowdown cliff
// (confirmed 2026-08-26: up to 22x slower, LLC-miss 13%->85%). A real
// minimizer value of exactly 0 is handled as a permanent, harmless
// cache-miss special case in S2Lookup/S2Insert below - never cached,
// correctness unaffected, just that one value never benefits from it.
static const uint64_t S2_EMPTY_TAG = 0;

// S3.3: no default member initializers - a trivially constructible
// struct is required for calloc-backed allocation to actually skip a
// constructor loop (any non-trivial default member initializer forces
// new[]/value-init to eagerly write every element regardless of the
// value written, which is exactly what caused the slowdown cliff).
struct S2Entry {
  uint64_t tag;
  taxid_t taxon;
};

#include <memory>
#include <cstdlib>

// S3.1: Luna's real per-socket L3, confirmed via `lscpu` on 2026-08-30
// (210 MiB total / 2 sockets = 105 MiB/socket; `lscpu -e` also confirmed
// NUMA node == socket, i.e. no Sub-NUMA Clustering splitting this).
static const uint64_t S3_LLC_PER_SOCKET_BYTES = 105ULL * 1024 * 1024;

// S3.2: safety fraction of the per-socket LLC this cache may claim -
// genuinely open, not yet resolved empirically (Round-1 debate guesses
// ranged 0.05-0.5). 0.25 is an interim placeholder pending a real sweep
// against benchmark data - sed this constant to test other values, same
// pattern as every prior size sweep in this project.
static const double S3_LLC_FRACTION = 0.25;

// S3.0 confirmed crash-free up to 262,144 sets with the heap-pointer
// fix. S3.3 (below) fixes the separate slowdown cliff at >=1,048,576
// sets via a zero-sentinel + calloc allocator; whether to raise this
// ceiling is a separate decision, pending a direct before/after
// measurement at the original worst-case size. 4,096 is the floor
// this project has always used.
static const size_t S3_MAX_SETS = 262144;
static const size_t S3_MIN_SETS = 4096;

// S3.3: free()-based deleter, reusable for both s2_cache (S2Entry[])
// and s2_next_way (uint8_t[]) since any object pointer converts
// implicitly to void*.
struct S2FreeDeleter {
  void operator()(void *p) const { free(p); }
};

static thread_local std::unique_ptr<S2Entry[], S2FreeDeleter> s2_cache;
static thread_local std::unique_ptr<uint8_t[], S2FreeDeleter> s2_next_way;
static thread_local size_t s2_num_sets = 0;

// S3.1/S3.2: N_sets(T) = floor(f x LLC_per_socket / (ways x sizeof(entry) x T)),
// rounded down to a power of 2 (S2SetIndex needs a bitmask), clamped to
// [S3_MIN_SETS, S3_MAX_SETS]. T is read live via omp_get_num_threads()
// from inside the active parallel classification region, not hardcoded -
// a size safe for 1 thread can be catastrophic at 96 (confirmed 2026-08-26).
static inline size_t S3ComputeNumSets() {
  int t = omp_get_num_threads();
  if (t < 1) t = 1;
  uint64_t raw = (uint64_t) (S3_LLC_FRACTION * S3_LLC_PER_SOCKET_BYTES
                             / (S2_WAYS * sizeof(S2Entry) * (uint64_t) t));
  size_t sets = S3_MIN_SETS;
  while (sets * 2 <= raw && sets * 2 <= S3_MAX_SETS)
    sets *= 2;
  return sets;
}

// S3.3: calloc instead of new[] - S2Entry is now trivially constructible
// and S2_EMPTY_TAG is 0, so calloc's zero-filled memory is ALREADY a
// valid, fully "empty" cache. For allocations above glibc's ~128KB
// mmap threshold (true for every size in [S3_MIN_SETS, S3_MAX_SETS] -
// the smallest, 4,096 sets, is already 256KB), calloc is backed by
// fresh OS pages that are zero for free, never eagerly touched - this
// is the actual fix for the first-touch/page-fault slowdown cliff,
// not just moving the array off thread_local storage (that was S3.0).
static inline void S2EnsureInit() {
  if (! s2_cache) {
    s2_num_sets = S3ComputeNumSets();
    S2Entry *cache_mem = static_cast<S2Entry *>(
        calloc(s2_num_sets * S2_WAYS, sizeof(S2Entry)));
    uint8_t *way_mem = static_cast<uint8_t *>(
        calloc(s2_num_sets, sizeof(uint8_t)));
    if (! cache_mem || ! way_mem)
      errx(EX_OSERR, "unable to allocate S2 cache memory");
    s2_cache.reset(cache_mem);
    s2_next_way.reset(way_mem);
  }
}'''

assert content.count(old_block) == 1, "declaration block not found exactly once"
content = content.replace(old_block, new_block)

old_lookup = '''static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx * S2_WAYS + way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx * S2_WAYS + way].taxon;
      return true;
    }
  }
  return false;
}'''

new_lookup = '''static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  if (minimizer == S2_EMPTY_TAG) return false;  // S3.3: 0 is now the empty
                                                 // sentinel - a real minimizer
                                                 // of exactly 0 (vanishingly
                                                 // rare) is never cached,
                                                 // always falls through to
                                                 // hash->Get(); correctness
                                                 // unaffected.
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx * S2_WAYS + way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx * S2_WAYS + way].taxon;
      return true;
    }
  }
  return false;
}'''

assert content.count(old_lookup) == 1, "S2Lookup not found exactly once"
content = content.replace(old_lookup, new_lookup)

old_insert = '''  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx * S2_WAYS + way].tag = minimizer;
  s2_cache[set_idx * S2_WAYS + way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}'''

new_insert = '''  if (minimizer == S2_EMPTY_TAG) return;  // S3.3: never insert the sentinel
                                           // value itself - see S2Lookup.
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx * S2_WAYS + way].tag = minimizer;
  s2_cache[set_idx * S2_WAYS + way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}'''

assert content.count(old_insert) == 1, "S2Insert body not found exactly once"
content = content.replace(old_insert, new_insert)

with open(path, "w") as f:
    f.write(content)
print("patched OK")
