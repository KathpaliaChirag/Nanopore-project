# S3.0 - heap-allocate the S2 cache (2026-08-30). Fixes the confirmed
# crash: a file-scope thread_local ARRAY this large (up to 16MB at
# 262,144 sets) is placed in glibc's static TLS block, a fixed-size
# region reserved per thread BEFORE any thread is created - it competes
# directly with that thread's own stack budget. Confirmed on Luna
# 2026-08-30: ulimit -s = 8192 KB (8MB) default stack vs. a 16MB array;
# no memory cap exists on the account (ulimit -a shows every relevant
# limit as "unlimited"); the 262,144-set/16-thread binary segfaults with
# a bare "Segmentation fault (core dumped)", exit 139, no glibc error
# text - consistent with a thread running out of real stack and faulting
# into its guard page, not an allocator refusing a request.
#
# Fix: replace the static arrays with thread_local POINTERS (8 bytes
# each, fit trivially in static TLS) to heap-allocated arrays, lazily
# initialized on first use per thread. This does NOT fix the separate
# slowdown cliff at >=1,048,576 sets (first-touch/page-fault cost of
# eagerly writing S2_EMPTY_TAG/TAXID_MAX into every entry) - that is a
# distinct, not-yet-attempted fix (zero-sentinel + calloc/mmap),
# deliberately out of scope here so the crash fix and the slowdown fix
# stay independently attributable.
#
# Run from ~/tools/kraken2-src-fresh/src, against the currently
# committed classify.cc (tag safe/S2.4, hash 75f908e).

path = "classify.cc"
with open(path) as f:
    content = f.read()

old_decl = '''static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};  // S2.3: round-robin eviction pointer per set'''

new_decl = '''#include <memory>

// S3.0: thread_local POINTERS (8 bytes each, live in glibc's static TLS
// block same as the old arrays did) to heap-allocated arrays, instead of
// the arrays themselves living directly in that fixed-size block.
static thread_local std::unique_ptr<S2Entry[]> s2_cache;
static thread_local std::unique_ptr<uint8_t[]> s2_next_way;

static inline void S2EnsureInit() {
  if (! s2_cache) {
    s2_cache.reset(new S2Entry[S2_NUM_SETS * S2_WAYS]);
    s2_next_way.reset(new uint8_t[S2_NUM_SETS]());
  }
}'''

assert content.count(old_decl) == 1, "declaration block not found exactly once"
content = content.replace(old_decl, new_decl)

old_lookup = '''static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      return true;
    }
  }
  return false;
}'''

new_lookup = '''static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
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

old_insert = '''  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx][way].tag = minimizer;
  s2_cache[set_idx][way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}'''

new_insert = '''  S2EnsureInit();
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
