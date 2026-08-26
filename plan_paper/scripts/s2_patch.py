# S2.1-S2.3 patch script - actually run on Luna against
# ~/tools/kraken2-src-fresh/src/classify.cc on 2026-08-25, AFTER s1_patch.py.
#
# Adds a thread-local 4-way set-associative cache (S2_NUM_SETS sets x
# S2_WAYS=4 ways) in front of hash->Get(), and wraps ONLY the Get() call
# with it - the minimizer_hit_groups/curr_taxon_counts stats-counting logic
# stays gated on the original s1_last_minimizer adjacent-check, unchanged.
# See plan_paper/command_log.md's "S2.1/S2.2/S2.3 implemented" entry for the
# full correctness reasoning (why decoupling cache hit/miss from stats-
# counting matters), and plan_paper/patches/s2_4way_associative_cache.diff
# for the actual resulting diff (at the original S2_NUM_SETS=4096).

path = "classify.cc"
with open(path) as f:
    content = f.read()

# --- Step 1: add S2's data structures and helper functions right after the
# S1.1 declarations. thread_local again - same reasoning as S1: one whole
# cache per OpenMP worker thread, persisting across every read it processes.
old_anchor = '''static thread_local uint64_t s1_last_minimizer = UINT64_MAX;
static thread_local taxid_t s1_last_taxon = TAXID_MAX;

taxid_t ClassifySequence('''

new_anchor = '''static thread_local uint64_t s1_last_minimizer = UINT64_MAX;
static thread_local taxid_t s1_last_taxon = TAXID_MAX;

// S2 - 4-way set-associative cache (sir's required Thesis 1 baseline).
// S2_NUM_SETS "buckets," each holding S2_WAYS=4 remembered (minimizer,
// taxon) pairs - a minimizer's low bits pick its set (cheap bitmask, since
// S2_NUM_SETS is a power of 2); within that set it can occupy any of the 4
// "ways." One whole cache per thread (thread_local), same persistence
// reasoning as S1's single slot. Size is a placeholder for now - S3
// (LLC-topology-aware sizing) tunes this properly later.
//
// IMPORTANT - correctness boundary: S2Lookup/S2Insert decide ONLY whether
// hash->Get() needs to run again. They must NEVER be used to decide whether
// minimizer_hit_groups gets incremented or curr_taxon_counts gets updated
// below - that gating stays tied to "different from the immediately
// preceding minimizer" (s1_last_minimizer), exactly as stock Kraken2 always
// did it. Wiring S2's broader cache into that decision would silently
// change what gets counted in the classification report (species counts,
// --quick-mode's early-exit threshold) - a correctness bug, not a
// performance change. Speed and statistics are kept deliberately separate.
static const size_t S2_NUM_SETS = 4096;              // must be a power of 2
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;      // "nothing here yet" - matches S1's convention

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
};

static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};  // S2.3: round-robin eviction pointer per set

// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}

// S2.2: check all 4 ways in the target set. Returns true and fills
// *out_taxon on a hit; on a miss, *out_taxon is left untouched.
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

// S2.3: insert/overwrite via simple round-robin - always evict whichever
// way is "next" for this set, then advance the pointer. Deliberately
// simple; S4 replaces this with a smarter policy later.
static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx][way].tag = minimizer;
  s2_cache[set_idx][way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}

taxid_t ClassifySequence('''

assert content.count(old_anchor) == 1
content = content.replace(old_anchor, new_anchor)

# --- Step 2: wrap ONLY the hash->Get() call with the S2 cache check. The
# outer "if (*minimizer_ptr != s1_last_minimizer)" gate, and everything
# below it (minimizer_hit_groups, curr_taxon_counts), stays byte-for-byte
# unchanged - that's the correctness boundary described in the comment above.
old_lookup = '''            taxon = 0;
            if (! skip_lookup)
              taxon = hash->Get(*minimizer_ptr);
            s1_last_taxon = taxon;'''

new_lookup = '''            taxon = 0;
            if (! skip_lookup) {
              // S2.2/S2.3 - try the 4-way cache before paying for a real
              // hash table lookup. This ONLY decides whether Get() runs -
              // it does not touch the stats-counting logic below.
              if (! S2Lookup(*minimizer_ptr, &taxon)) {
                taxon = hash->Get(*minimizer_ptr);
                S2Insert(*minimizer_ptr, taxon);
              }
            }
            s1_last_taxon = taxon;'''

assert content.count(old_lookup) == 1
content = content.replace(old_lookup, new_lookup)

with open(path, "w") as f:
    f.write(content)
print("patched OK")
