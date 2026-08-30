# S4.0 - occupancy + reuse-distance diagnostic (2026-08-30). Same
# standalone wiring as s2_standalone_patch.py (built from the ORIGINAL
# unpatched classify.cc, S2 wraps hash->Get() directly, no S1 layer),
# plain round-robin eviction (no pinning - this measures the underlying
# lookup stream, not any particular eviction policy), plus two new
# instruments:
#
# 1. Per-set occupancy counter - how many lookups landed in each of
#    the 4,096 sets, regardless of hit/miss. A markedly uneven
#    distribution would be direct evidence of a real S2SetIndex
#    bit-mixing bug (it's a raw low-bit mask, no mixing) - a higher-
#    priority fix than any eviction-policy work, since a bad hash
#    undermines any eviction scheme built on top of it.
#
# 2. Reuse-distance histogram - minimizer -> last-seen lookup index,
#    bucketed log-scale (<10, <100, <1e3, <1e4, <1e5, <1e6, <1e7,
#    >=1e7) on every repeat. Answers the M5-reuse-rate (90.7% global
#    reuse) vs. low-hit-rate (<2% even at the largest tested capacity)
#    tension directly: if most repeat-distances land far beyond any
#    tested cache capacity, that confirms "locality problem, not
#    reuse absence" and tells S4 what capacity would actually be
#    needed to close the gap.
#
# MUST run T=1 ONLY - the unordered_map alone costs an estimated
# 1.3-1.6GB per thread at full scale (M5's 32.8M unique minimizers),
# fine once but infeasible replicated across many threads. MUST be
# built and used as a separate, non-timed instrumentation binary -
# never fold this into any binary used for real wall-clock/LLC
# comparisons, since the map lookup on every call is real per-call
# overhead that would skew timing numbers (the exact mistake this
# project already made once with global atomic hit/miss counters on
# sample_targeted).
#
# Run from ~/tools/kraken2-src-fresh/src, against the ORIGINAL
# unpatched classify.cc.pre-s1.1.bak (copy it to classify.cc first).

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

new_sig = '''// S4.0 DIAGNOSTIC (2026-08-30) - occupancy + reuse-distance
// instrumentation on top of the standalone S2 wiring. Non-timed,
// T=1 only - see header comment in s4_0_diagnostic_patch.py.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <unordered_map>

static const size_t S2_NUM_SETS = 4096;
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

static std::atomic<uint64_t> s2_hits{0};
static std::atomic<uint64_t> s2_misses{0};

// Per-set occupancy - incremented on every lookup, hit or miss.
static thread_local uint64_t s2_occupancy[S2_NUM_SETS] = {0};

// Reuse-distance tracking - see header comment for why T=1 only.
static thread_local std::unordered_map<uint64_t, uint64_t> s2_last_seen;
static thread_local uint64_t s2_lookup_idx = 0;
static thread_local uint64_t s2_distance_hist[8] = {0};  // <10,<100,<1e3,<1e4,<1e5,<1e6,<1e7,>=1e7

static inline void S2RecordReuse(uint64_t minimizer) {
  auto it = s2_last_seen.find(minimizer);
  if (it != s2_last_seen.end()) {
    uint64_t distance = s2_lookup_idx - it->second;
    int bucket = 0;
    uint64_t threshold = 10;
    while (distance >= threshold && bucket < 7) { threshold *= 10; bucket++; }
    s2_distance_hist[bucket]++;
  }
  s2_last_seen[minimizer] = s2_lookup_idx;
  s2_lookup_idx++;
}

static void S2PrintStats() {
  uint64_t hits = s2_hits.load(), misses = s2_misses.load();
  uint64_t total = hits + misses;
  fprintf(stderr, "[S4.0-STATS] size=%zu ways=%zu hits=%llu misses=%llu total=%llu hit_rate=%.4f%%\\n",
          S2_NUM_SETS, S2_WAYS,
          (unsigned long long)hits, (unsigned long long)misses, (unsigned long long)total,
          total ? (100.0 * hits / total) : 0.0);

  uint64_t occ_min = (uint64_t) -1, occ_max = 0, occ_sum = 0;
  for (size_t i = 0; i < S2_NUM_SETS; i++) {
    if (s2_occupancy[i] < occ_min) occ_min = s2_occupancy[i];
    if (s2_occupancy[i] > occ_max) occ_max = s2_occupancy[i];
    occ_sum += s2_occupancy[i];
  }
  double occ_mean = (double) occ_sum / S2_NUM_SETS;
  fprintf(stderr, "[S4.0-OCCUPANCY] min=%llu max=%llu mean=%.2f max_over_mean=%.2f\\n",
          (unsigned long long) occ_min, (unsigned long long) occ_max, occ_mean,
          occ_mean > 0 ? (double) occ_max / occ_mean : 0.0);

  fprintf(stderr, "[S4.0-REUSE-DISTANCE] lt10=%llu lt100=%llu lt1e3=%llu lt1e4=%llu lt1e5=%llu lt1e6=%llu lt1e7=%llu ge1e7=%llu\\n",
          (unsigned long long)s2_distance_hist[0], (unsigned long long)s2_distance_hist[1],
          (unsigned long long)s2_distance_hist[2], (unsigned long long)s2_distance_hist[3],
          (unsigned long long)s2_distance_hist[4], (unsigned long long)s2_distance_hist[5],
          (unsigned long long)s2_distance_hist[6], (unsigned long long)s2_distance_hist[7]);
}
struct S2StatsRegistrar { S2StatsRegistrar() { atexit(S2PrintStats); } };
static S2StatsRegistrar s2_stats_registrar;

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
  s2_occupancy[set_idx]++;
  S2RecordReuse(minimizer);
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
              // S4.0 diagnostic - same standalone wiring as
              // s2_standalone_patch.py (wraps Get() directly, no S1
              // layer), plain round-robin, plus occupancy/reuse-
              // distance instrumentation inside S2Lookup.
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
