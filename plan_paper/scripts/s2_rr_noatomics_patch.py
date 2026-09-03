# S2 round-robin, no-instrumentation control variant (2026-09-02).
#
# Why: CK asked whether round-robin-4way (the associativity grid's
# baseline) is itself already slower than having no cache at all. The
# validated 3-run S0 numbers (2026-09-02 "S1 re-measured" entry) show
# round-robin-4way losing ~3x wall-clock on sample_targeted at T=32/T=96
# (0.57s/0.59s -> 1.76s/1.74s) but being flat (within ~1-3%) on
# standard_8gb/pluspf_103gb. That exact DB and exact ~3x magnitude
# matches a previously-diagnosed, unrelated artifact (2026-08-26,
# "Built S2-standalone... audit's Q1/Q3 concern resolved"): global
# std::atomic hit/miss counters, fetch_add'd on every lookup from every
# thread, cause cache-line contention that's invisible on the two slow/
# memory-bound DBs but dominates on sample_targeted where Get() itself
# is fast. This patch is the same round-robin-4way cache logic with that
# instrumentation removed entirely (no counters at all - this run only
# needs wall-clock), to test whether the ~3x gap is the counters, not
# the cache design.
#
# Apply on top of the ORIGINAL unpatched classify.cc.pre-s1.1.bak, same
# as s2_standalone_patch.py, then apply s4_0b_hash_mix_diagnostic_patch.py
# on top for the same MurmurHash3-mixed S2SetIndex as the grid's
# round-robin-4way baseline - this must be apples-to-apples with that
# build except for the counters.

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

new_sig = '''// S2-RR-NOATOMICS CONTROL VARIANT (2026-09-02) - identical cache logic
// to s2_standalone_patch.py's round-robin, 4-way, 4,096 sets, but with
// the global std::atomic hit/miss counters removed entirely. Exists only
// to test whether sample_targeted's ~3x wall-clock loss vs S0 (measured
// on the instrumented round-robin-4way build) is the counter-contention
// artifact diagnosed on 2026-08-26, or a real cache-design cost.
static const size_t S2_NUM_SETS = 4096;
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
      return true;
    }
  }
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
              // S2-RR-NOATOMICS - same wiring as S2-standalone, no counters.
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
