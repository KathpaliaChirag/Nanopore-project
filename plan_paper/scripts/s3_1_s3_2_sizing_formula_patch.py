# S3.1/S3.2 - LLC-topology-aware, thread-count-scaled sizing formula
# (2026-08-30). Replaces the hardcoded S2_NUM_SETS=4096 constant with
# N_sets(T) = floor_pow2(f x LLC_per_socket / (ways x sizeof(entry) x T)),
# clamped to [4096, 262144].
#
# LLC_per_socket = 105 MiB, confirmed directly on Luna via `lscpu`
# ("L3 cache: 210 MiB (2 instances)") - replaces the spec-sheet-derived
# assumption every prior benchmark implicitly used. `lscpu -e` also
# confirmed a strict NODE<->SOCKET 1:1 mapping and one shared L3 index
# per socket, ruling out Sub-NUMA Clustering.
#
# f (S3_LLC_FRACTION) is a genuinely open parameter, NOT resolved by
# this patch - Round-1 debate guesses ranged 0.05-0.5. 0.25 is an
# interim placeholder: at T=1 it lands exactly at 262,144 (S3.0's
# confirmed crash-free ceiling); at T=96 it lands at exactly 4,096 (this
# project's long-validated size). S3.2's real remaining work is sweeping
# this constant empirically against benchmark data - sed it, same
# pattern as every prior size sweep in this project.
#
# T is read live via omp_get_num_threads() from inside the active
# classification parallel region (Options.num_threads is passed to
# omp_set_num_threads() before that region starts, per classify.cc:270),
# not hardcoded - a size safe for 1 thread can be catastrophic at 96,
# confirmed 2026-08-26.
#
# 262,144 stays the max ceiling until S3.3's pre-touch experiment (not
# yet run) establishes a real safe ceiling above it - the separate
# slowdown cliff at >=1,048,576 sets is still unaddressed by this patch.
#
# Run from ~/tools/kraken2-src-fresh/src, against the S3.0-patched
# classify.cc (tag safe/S3.0).

path = "classify.cc"
with open(path) as f:
    content = f.read()

old_decl = '''static const size_t S2_NUM_SETS = 4096;              // must be a power of 2
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;      // "nothing here yet" - matches S1's convention

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
};

#include <memory>

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
}

// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}'''

new_decl = '''static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;      // "nothing here yet" - matches S1's convention

struct S2Entry {
  uint64_t tag = S2_EMPTY_TAG;
  taxid_t taxon = TAXID_MAX;
};

#include <memory>

// S3.1: Luna's real per-socket L3, confirmed via `lscpu` on 2026-08-30
// (210 MiB total / 2 sockets = 105 MiB/socket; `lscpu -e` also confirmed
// NUMA node == socket, i.e. no Sub-NUMA Clustering splitting this).
static const uint64_t S3_LLC_PER_SOCKET_BYTES = 105ULL * 1024 * 1024;

// S3.2: safety fraction of the per-socket LLC this cache may claim -
// genuinely open, not yet resolved empirically (Round-1 debate guesses
// ranged 0.05-0.5). 0.25 is an interim placeholder pending a real sweep
// against benchmark data - sed this constant to test other values, same
// pattern as every prior size sweep in this project.
static const double S3_LLC_FRACTION = 0.25;

// S3.0 confirmed crash-free up to 262,144 sets with the heap-pointer
// fix; S3.3's pre-touch experiment (not yet run) is needed before
// trusting anything above this - the separate slowdown cliff at
// >=1,048,576 sets is still unaddressed. 4,096 is the floor this
// project has always used.
static const size_t S3_MAX_SETS = 262144;
static const size_t S3_MIN_SETS = 4096;

static thread_local std::unique_ptr<S2Entry[]> s2_cache;
static thread_local std::unique_ptr<uint8_t[]> s2_next_way;
static thread_local size_t s2_num_sets = 0;

// S3.1/S3.2: N_sets(T) = floor(f x LLC_per_socket / (ways x sizeof(entry) x T)),
// rounded down to a power of 2 (S2SetIndex needs a bitmask), clamped to
// [S3_MIN_SETS, S3_MAX_SETS]. T is read live via omp_get_num_threads()
// from inside the active parallel classification region, not hardcoded -
// a size safe for 1 thread can be catastrophic at 96 (confirmed 2026-08-26).
static inline size_t S3ComputeNumSets() {
  int t = omp_get_num_threads();
  if (t < 1) t = 1;
  uint64_t raw = (uint64_t) (S3_LLC_FRACTION * S3_LLC_PER_SOCKET_BYTES
                             / (S2_WAYS * sizeof(S2Entry) * (uint64_t) t));
  size_t sets = S3_MIN_SETS;
  while (sets * 2 <= raw && sets * 2 <= S3_MAX_SETS)
    sets *= 2;
  return sets;
}

static inline void S2EnsureInit() {
  if (! s2_cache) {
    s2_num_sets = S3ComputeNumSets();
    s2_cache.reset(new S2Entry[s2_num_sets * S2_WAYS]);
    s2_next_way.reset(new uint8_t[s2_num_sets]());
  }
}

// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (s2_num_sets - 1);
}'''

assert content.count(old_decl) == 1, "declaration block not found exactly once"
content = content.replace(old_decl, new_decl)

with open(path, "w") as f:
    f.write(content)
print("patched OK")
