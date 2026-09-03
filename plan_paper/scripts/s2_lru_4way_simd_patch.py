# CHIRAG 04-09-26 :: real N-way caches check every way at once, with parallel
# comparators. s2_lru_4way_noatomics_patch.py's S2Lookup/S2Insert don't - they
# run `for (way = 0; way < S2_WAYS; way++)`, checking one tag at a time, on
# every call, including misses. so a software loop's wall-clock scales with N
# even though real hardware's mostly doesn't. this patch swaps that AoS
# (array-of-structs) scan for a SoA (structure-of-arrays) layout: a 1-byte
# fingerprint per way, packed per set, compared in one SSE2 _mm_cmpeq_epi8
# instead of walked one at a time. only the full 64-bit tag gets checked for a
# fingerprint match, so O(1) SIMD compare on a miss instead of O(ways) branches.
# no atomics, same control-variant pattern as every other noatomics S2 binary.
#
# this is item (ii) from research_brief_associativity_case_study_2026-09-02.md
# ("SIMD/SoA redesign"), dropped that cycle, revived as a lower-priority backlog
# item on 2026-09-04 alongside the Sniper/TEJAS simulator track (week7plan.md
# item 4, which stays the active priority - this is not scheduled this week).
#
# hypothesis this tests: the sequential scan is a confound sitting on top of the
# allocation/first-touch cost the 2026-09-02 debate already locked in as the
# dominant explanation for "more ways, worse wall-clock". not a replacement for
# that diagnosis, an additional one.
#
# status: written, not built, not benchmarked. needs a real run on Luna before
# any number from this goes near the paper. only 4-way is implemented here -
# 8-way fits one XMM register exactly, 16/32/64-way would need AVX2.

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

new_sig = '''// CHIRAG 04-09-26 :: SoA fingerprint array + SSE2 parallel tag-candidate
// compare, replacing S2's sequential AoS scan. No atomics (control variant).
#include <emmintrin.h>

static const size_t S2_NUM_SETS = 4096;
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;

// CHIRAG 04-09-26 :: fingerprints padded to 16 bytes/set so one XMM register
// (_mm_load_si128) covers a whole set in one load. Only the first S2_WAYS
// bytes mean anything - a fingerprint collision on the padding just costs a
// wasted candidate check below, the full 64-bit tag check catches it, so it
// never produces a wrong answer.
struct alignas(16) S2FpRow {
  uint8_t fp[16] = {0};
};

static thread_local S2FpRow s2_fp[S2_NUM_SETS];
static thread_local uint64_t s2_tag[S2_NUM_SETS][S2_WAYS];
static thread_local taxid_t s2_taxon[S2_NUM_SETS][S2_WAYS];
static thread_local uint64_t s2_last_used[S2_NUM_SETS][S2_WAYS];
static thread_local bool s2_init_done = false;
static thread_local uint64_t s2_clock = 0;

static inline void S2EnsureInit() {
  if (s2_init_done) return;
  for (size_t set_idx = 0; set_idx < S2_NUM_SETS; set_idx++) {
    for (size_t way = 0; way < S2_WAYS; way++) {
      s2_tag[set_idx][way] = S2_EMPTY_TAG;
    }
  }
  s2_init_done = true;
}

static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

static inline uint8_t S2Fingerprint(uint64_t tag) {
  return (uint8_t)(tag >> 56);
}

static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t fp = S2Fingerprint(minimizer);

  __m128i fp_vec = _mm_set1_epi8((char)fp);
  __m128i row_vec = _mm_load_si128(reinterpret_cast<const __m128i*>(s2_fp[set_idx].fp));
  __m128i cmp = _mm_cmpeq_epi8(fp_vec, row_vec);
  int mask = _mm_movemask_epi8(cmp) & ((1 << S2_WAYS) - 1);

  while (mask) {
    int way = __builtin_ctz((unsigned)mask);
    mask &= mask - 1;
    if (s2_tag[set_idx][way] == minimizer) {
      *out_taxon = s2_taxon[set_idx][way];
      s2_last_used[set_idx][way] = ++s2_clock;
      return true;
    }
  }
  return false;
}

static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t victim = 0;
  for (uint8_t way = 1; way < S2_WAYS; way++) {
    if (s2_last_used[set_idx][way] < s2_last_used[set_idx][victim]) {
      victim = way;
    }
  }
  s2_fp[set_idx].fp[victim] = S2Fingerprint(minimizer);
  s2_tag[set_idx][victim] = minimizer;
  s2_taxon[set_idx][victim] = taxon;
  s2_last_used[set_idx][victim] = ++s2_clock;
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
              // CHIRAG 04-09-26 :: same wiring as the other S2 variants,
              // SoA fingerprint lookup underneath.
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
