# S2-PINNED test variant (2026-08-26) - same base as s2_standalone_patch.py
# (built from the ORIGINAL unpatched classify.cc, S2 wraps hash->Get()
# directly, no S1 layer) but with ONE change: eviction now protects any
# entry that's proven useful (been hit at least once) instead of blindly
# round-robining through all 4 ways. This isolates the eviction-policy
# question from everything else already tested - same cache size (4,096
# sets), same hit/miss counters, same "standalone" wiring - so any
# difference in hit rate vs. s2_standalone_patch.py's ~0.14-0.40% is
# attributable to the eviction policy alone.
#
# Motivation: this project's own prior M5 finding measured 90.7% k-mer
# reuse - high reuse can coexist with near-zero cache hit rate if repeats
# are separated by more distinct intervening minimizers than the cache's
# capacity. Round-robin evicts a proven-useful entry the moment its turn
# comes up, regardless of how recently or often it was hit. This patch
# tests whether even a trivial "give it one grace period" protection
# closes any of that gap.

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

new_sig = '''// S2-PINNED TEST VARIANT (2026-08-26) - same standalone wiring as
// s2_standalone_patch.py, but with a "grace period" eviction rule instead
// of plain round-robin: any entry that's been hit at least once is
// protected from eviction until every other entry in its set has also
// proven itself. Tests whether protecting proven-useful entries raises
// the hit rate at the SAME small capacity, before designing S4's full
// biology-aware eviction policy.
#include <atomic>
#include <cstdio>
#include <cstdlib>
static std::atomic<uint64_t> s2_hits{0};
static std::atomic<uint64_t> s2_misses{0};
static void S2PrintStats() {
  uint64_t hits = s2_hits.load(), misses = s2_misses.load();
  uint64_t total = hits + misses;
  fprintf(stderr, "[S2-PINNED] hits=%llu misses=%llu total=%llu hit_rate=%.4f%%\\n",
          (unsigned long long)hits, (unsigned long long)misses, (unsigned long long)total,
          total ? (100.0 * hits / total) : 0.0);
}
struct S2StatsRegistrar { S2StatsRegistrar() { atexit(S2PrintStats); } };
static S2StatsRegistrar s2_stats_registrar;

static const size_t S2_NUM_SETS = 4096;   // same size as S2-standalone - isolates the eviction-policy variable
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
  bool was_hit = false;   // NEW - "has this entry proven itself useful since it was inserted"
};

static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};   // fallback pointer, used only when every way in a set is protected

static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      s2_cache[set_idx][way].was_hit = true;   // NEW - mark proven-useful, protecting it from the next eviction pass
      s2_hits.fetch_add(1, std::memory_order_relaxed);
      return true;
    }
  }
  s2_misses.fetch_add(1, std::memory_order_relaxed);
  return false;
}

static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  // Prefer evicting a way that has NEVER been hit - the "pinning" rule.
  // A proven-useful entry survives this pass even if round-robin's pointer
  // would otherwise have landed on it.
  uint8_t victim = S2_WAYS;   // sentinel meaning "no unproven way found yet"
  for (uint8_t way = 0; way < S2_WAYS; way++) {
    if (! s2_cache[set_idx][way].was_hit) {
      victim = way;
      break;
    }
  }
  if (victim == S2_WAYS) {
    // Every way in this set has proven itself at least once - fall back to
    // round-robin so we always make forward progress and never get stuck.
    victim = s2_next_way[set_idx];
    s2_next_way[set_idx] = (victim + 1) % S2_WAYS;
  }
  s2_cache[set_idx][victim].tag = minimizer;
  s2_cache[set_idx][victim].taxon = taxon;
  s2_cache[set_idx][victim].was_hit = false;   // reset - the new entry hasn't proven itself yet
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
              // S2-pinned - same wiring as S2-standalone (wraps Get()
              // directly, no S1 layer), only the eviction rule differs.
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
