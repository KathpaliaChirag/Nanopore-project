# S2-LRU test variant (2026-09-02) - same base/wiring as s2_standalone_patch.py
# and s2_pinned_patch.py (built from the ORIGINAL unpatched classify.cc, S2
# wraps hash->Get() directly, no S1 layer), same 4,096 sets, same
# std::atomic hit/miss counters - only the eviction rule differs, so any
# hit-rate change vs. round-robin (~0.14-0.40%) or pinning is attributable
# to the eviction policy alone.
#
# Unlike s2_pinned_patch.py's one-bit "has this ever been hit" grace
# period, this is TRUE least-recently-used: each entry carries a recency
# stamp (a monotonically increasing per-thread logical clock), touched on
# every hit; eviction always picks the way with the OLDEST stamp in that
# set. Requested 2026-09-02 after the S4.0 finding that pinning's earlier
# apparent win (+25.2%) was mostly an artifact of the broken hash - this
# variant is meant to be built ON TOP of the s4_0b hash-mix fix (apply
# this patch first, then s4_0b_hash_mix_diagnostic_patch.py), not against
# the old broken hash, so it's tested on the same corrected baseline as
# the pinned-vs-round-robin reversal result.
#
# Implementation note: with only 4 ways, a full doubly-linked LRU list is
# overkill. A per-entry last-used stamp + linear scan for the minimum is
# O(4) per eviction - correct and simple. All stamps start at 0, so the
# first 4 inserts into any set naturally fill empty ways in order before
# any real eviction happens (way 0 is the initial "oldest" until it's
# touched, at which point way 1 becomes oldest, etc.) - no separate
# "is this slot empty" check needed.

path = "classify.cc"
with open(path) as f:
    content = f.read()

old_sig = '''taxid_t ClassifySequence(Sequence &dna, Sequence &dna2, ostringstream &koss,
                         KeyValueStore *hash, Taxonomy &taxonomy,
                         IndexOptions &idx_opts, Options &opts,
                         ClassificationStats &stats, MinimizerScanner &scanner,
                         vector<taxid_t> &taxa, taxon_counts_t &hit_counts,
                         vector<string> &tx_frames,
                         taxon_counters_t &curr_taxon_counts)
{'''

new_sig = '''// S2-LRU TEST VARIANT (2026-09-02) - same standalone wiring as
// s2_standalone_patch.py/s2_pinned_patch.py, but with TRUE
// least-recently-used eviction instead of round-robin or one-bit
// pinning: each entry carries a recency stamp, touched on every hit;
// eviction always evicts the way with the oldest stamp in its set.
// Meant to be built on top of the S4.0b hash-mix fix (apply that patch
// AFTER this one) so eviction policy is tested on the corrected hash,
// not the broken one that made pinning look better than it was.
#include <atomic>
#include <cstdio>
#include <cstdlib>

static const size_t S2_NUM_SETS = 4096;   // same size as standalone/pinned - isolates the eviction-policy variable
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

static std::atomic<uint64_t> s2_hits{0};
static std::atomic<uint64_t> s2_misses{0};
static void S2PrintStats() {
  uint64_t hits = s2_hits.load(), misses = s2_misses.load();
  uint64_t total = hits + misses;
  fprintf(stderr, "[S2-LRU] size=%zu ways=%zu hits=%llu misses=%llu total=%llu hit_rate=%.4f%%\\n",
          S2_NUM_SETS, S2_WAYS,
          (unsigned long long)hits, (unsigned long long)misses, (unsigned long long)total,
          total ? (100.0 * hits / total) : 0.0);
}
struct S2StatsRegistrar { S2StatsRegistrar() { atexit(S2PrintStats); } };
static S2StatsRegistrar s2_stats_registrar;

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
  uint64_t last_used = 0;   // NEW - LRU recency stamp, higher = more recently used
};

static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint64_t s2_clock = 0;   // NEW - monotonically increasing per-thread logical clock

static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      s2_cache[set_idx][way].last_used = ++s2_clock;   // NEW - touch: this way is now the most recently used in its set
      s2_hits.fetch_add(1, std::memory_order_relaxed);
      return true;
    }
  }
  s2_misses.fetch_add(1, std::memory_order_relaxed);
  return false;
}

static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  // NEW - evict whichever of the 4 ways has the SMALLEST last_used stamp,
  // i.e. the true least-recently-used entry (not round-robin's "whoever's
  // turn it is" or pinning's one-bit "has this ever been hit").
  uint8_t victim = 0;
  for (uint8_t way = 1; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].last_used < s2_cache[set_idx][victim].last_used) {
      victim = way;
    }
  }
  s2_cache[set_idx][victim].tag = minimizer;
  s2_cache[set_idx][victim].taxon = taxon;
  s2_cache[set_idx][victim].last_used = ++s2_clock;
}

taxid_t ClassifySequence(Sequence &dna, Sequence &dna2, ostringstream &koss,
                         KeyValueStore *hash, Taxonomy &taxonomy,
                         IndexOptions &idx_opts, Options &opts,
                         ClassificationStats &stats, MinimizerScanner &scanner,
                         vector<taxid_t> &taxa, taxon_counts_t &hit_counts,
                         vector<string> &tx_frames,
                         taxon_counters_t &curr_taxon_counts)
{'''

assert content.count(old_sig) == 1, "signature not found exactly once"
content = content.replace(old_sig, new_sig)

old_lookup = '''            taxon = 0;
            if (! skip_lookup)
              taxon = hash->Get(*minimizer_ptr);
            last_taxon = taxon;'''

new_lookup = '''            taxon = 0;
            if (! skip_lookup) {
              // S2-LRU - same wiring as S2-standalone/S2-pinned (wraps
              // Get() directly, no S1 layer), only the eviction rule differs.
              if (! S2Lookup(*minimizer_ptr, &taxon)) {
                taxon = hash->Get(*minimizer_ptr);
                S2Insert(*minimizer_ptr, taxon);
              }
            }
            last_taxon = taxon;'''

assert content.count(old_lookup) == 1, "lookup site not found exactly once"
content = content.replace(old_lookup, new_lookup)

with open(path, "w") as f:
    f.write(content)
print("patched OK")
