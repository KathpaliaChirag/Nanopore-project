# S2-LRU-4WAY, no-instrumentation control (2026-09-02) - identical eviction
# logic to s2_lru_patch.py, atomic hit/miss counters removed. Part of a
# 6-config clean-baseline re-run: CK asked for the associativity grid to
# be anchored to true no-cache (S0), not round-robin's own instrumented
# number - the round-robin-vs-S0 control run confirmed the global
# std::atomic counters (fetch_add on every lookup, every thread) cause a
# 2-3x contention artifact on sample_targeted at 32/96 threads, invisible
# on the other two DBs. Every LRU-way config carries the same counters,
# so all five need the same fix before an honest vs-S0 comparison exists.

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

new_sig = '''// S2-LRU-4WAY-NOATOMICS CONTROL VARIANT (2026-09-02) - same LRU eviction
// as s2_lru_patch.py, atomic hit/miss counters removed (wall-clock only).
static const size_t S2_NUM_SETS = 4096;
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

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
      return true;
    }
  }
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
              // S2-LRU-4WAY-NOATOMICS - same wiring, no counters.
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
