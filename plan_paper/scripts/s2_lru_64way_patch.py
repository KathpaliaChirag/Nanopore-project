# S2-LRU-64WAY test variant (2026-09-02) - part of the associativity sweep
# (4/8/16/32/64 ways), S2_WAYS=64 (4,096 sets x 64 ways = 262,144 entries,
# ~4MB/thread at T=1). Same true recency-stamp LRU eviction as the other
# variants. Build on top of the S4.0b hash-mix fix.

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

new_sig = '''// S2-LRU-64WAY TEST VARIANT (2026-09-02) - same true recency-stamp LRU
// eviction as s2_lru_patch.py, S2_WAYS=64 instead of 4 (4,096 sets x 64
// ways = 262,144 entries, ~4MB/thread) - part of the 4/8/16/32/64
// associativity sweep. Build on top of the S4.0b hash-mix fix.
#include <atomic>
#include <cstdio>
#include <cstdlib>

static const size_t S2_NUM_SETS = 4096;   // same set count across the whole sweep - isolates the ways variable
static const size_t S2_WAYS = 64;         // CHANGED from 4
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

static std::atomic<uint64_t> s2_hits{0};
static std::atomic<uint64_t> s2_misses{0};
static void S2PrintStats() {
  uint64_t hits = s2_hits.load(), misses = s2_misses.load();
  uint64_t total = hits + misses;
  fprintf(stderr, "[S2-LRU-64WAY] size=%zu ways=%zu hits=%llu misses=%llu total=%llu hit_rate=%.4f%%\\n",
          S2_NUM_SETS, S2_WAYS,
          (unsigned long long)hits, (unsigned long long)misses, (unsigned long long)total,
          total ? (100.0 * hits / total) : 0.0);
}
struct S2StatsRegistrar { S2StatsRegistrar() { atexit(S2PrintStats); } };
static S2StatsRegistrar s2_stats_registrar;

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
  uint64_t last_used = 0;
};

static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint64_t s2_clock = 0;

static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      s2_cache[set_idx][way].last_used = ++s2_clock;
      s2_hits.fetch_add(1, std::memory_order_relaxed);
      return true;
    }
  }
  s2_misses.fetch_add(1, std::memory_order_relaxed);
  return false;
}

static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
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
              // S2-LRU-64WAY - same wiring as the other standalone variants,
              // only S2_WAYS differs.
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
