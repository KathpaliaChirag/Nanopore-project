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

new_sig = '''// S2-STANDALONE TEST VARIANT (2026-08-26) - built from the ORIGINAL
// unpatched classify.cc, not on top of S1's patch. S2's cache wraps
// hash->Get() directly, with nothing else added in between - this answers
// the verification audit's Q1/Q3 finding honestly: does a standalone
// 4-way cache help, without S1's thread-local single slot narrowing what
// traffic S2 ever sees. The only thing still standing between S2 and the
// full stream is Kraken2's own original adjacent-repeat check (below,
// untouched, still function-local) - that's stock behavior, not something
// this project added, so it's not part of what's being tested here.
//
// Real hit/miss counters (global atomics - the simplest correct way to
// aggregate across OpenMP worker threads without extra synchronization
// logic) replace inferring cache behavior only from external perf stat
// proxies (wall-clock, LLC-miss%), which the audit found could not
// distinguish "cache legitimately rarely hits" from "cache never hits due
// to a bug."
#include <atomic>
#include <cstdio>
#include <cstdlib>
static std::atomic<uint64_t> s2_hits{0};
static std::atomic<uint64_t> s2_misses{0};
static void S2PrintStats() {
  uint64_t hits = s2_hits.load(), misses = s2_misses.load();
  uint64_t total = hits + misses;
  fprintf(stderr, "[S2-STANDALONE] hits=%llu misses=%llu total=%llu hit_rate=%.4f%%\\n",
          (unsigned long long)hits, (unsigned long long)misses, (unsigned long long)total,
          total ? (100.0 * hits / total) : 0.0);
}
struct S2StatsRegistrar { S2StatsRegistrar() { atexit(S2PrintStats); } };
static S2StatsRegistrar s2_stats_registrar;

static const size_t S2_NUM_SETS = 4096;   // same size as the original S2 - fair comparison
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
};

static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};

static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx][way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx][way].taxon;
      s2_hits.fetch_add(1, std::memory_order_relaxed);
      return true;
    }
  }
  s2_misses.fetch_add(1, std::memory_order_relaxed);
  return false;
}

static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx][way].tag = minimizer;
  s2_cache[set_idx][way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
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
              // S2, standalone this time - wraps Get() directly. Only
              // Kraken2's own original adjacent-repeat check (unchanged,
              // still function-local, still last_minimizer/last_taxon)
              // sits between here and the full lookup stream - no S1
              // thread-local broadening layer in the way this time.
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
