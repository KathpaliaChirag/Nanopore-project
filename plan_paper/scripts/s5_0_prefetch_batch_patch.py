# S5.0 - software-prefetch batched lookup (-B), ported onto the real
# safe/S4.0-hashmix tree (2026-08-31). Source technique: Chirag Suthar's
# mtp1/scripts/kraken2_prefetch.patch (hobbbit branch, a separate MTP
# track in this same repo) - see mtp1/reports/PREFETCH.md and
# plan_paper/track_a_pivot_debate_2026-08-30.md Q3 for the full mechanism
# and why his measured numbers (-20.34% "cooldown protocol," not the
# brief's cited -11.77%) are NOT a Luna number: different machine (16MB L3
# desktop vs Luna's 105MB/socket), different DB (48.8MB eskape_32bit_fork
# vs Luna's 88-96%-LLC-miss standard_8gb/pluspf_103gb), different codebase
# fork (his CompactHashTable is templated <Cell> for his own cell-width
# work; this tree's is not - confirmed directly against this tree, not
# assumed, 2026-08-31).
#
# THE MECHANISM (why this is a genuinely different lever than S1-S4):
# every prior Track A step tried to AVOID the memory access - remember the
# answer so hash->Get() never runs again for that minimizer. All of them
# hit the same wall: 81% of repeats land 10,000-1,000,000 lookups apart
# (S4.0's reuse-distance histogram), far beyond what any bounded cache
# this size can survive. Prefetching does not avoid the access - it
# overlaps it. The stock loop asks for one minimizer's answer and blocks
# ~200 cycles waiting for DRAM before asking for the next one; the core
# can sustain ~12 outstanding requests, this loop uses ~1.24 of that. This
# project's own M4 finding puts Luna's DRAM bandwidth utilization at
# 4.9-10.7% of peak (latency-bound, not bandwidth-bound) - real headroom
# for this to help, though by an amount that has to be measured on Luna,
# not assumed from Suthar's numbers.
#
# WHAT'S GENUINELY DIFFERENT FROM A STRAIGHT PORT (not a flag-flip):
# 1. This tree's CompactHashTable is NOT templated and uses a different
#    cell layout (hc >> (32 + value_bits_), confirmed via
#    src/compact_hash.cc:109-128) than Suthar's fork (hc >> (64 -
#    key_bits_)) - the compact_hash.cc/.h hunks below are rewritten
#    against this tree's real code, not copied from his diff.
# 2. classify.cc's loop already carries three layers his patch never saw:
#    S1's thread_local single-slot repeat skip, S2's 4-way cache, and
#    S4.0's MurmurHash3 mixing inside S2SetIndex. The merge below moves
#    S1's repeat-check and S2's cache-check into pass 2 (resolve step),
#    fed by the hash computed once in pass 1, instead of ripping any of
#    them out.
# 3. Hash reuse, not hardcoded duplication: pass 1 already computes
#    MurmurHash3(minimizer) for the prefetch address. S2SetIndex used to
#    compute that same hash again, separately (S4.0b/c). This patch makes
#    S2SetIndex take the already-computed hash instead of re-deriving it -
#    one hash per non-repeat minimizer instead of two, and one place that
#    defines "the hash" instead of two that could silently drift apart.
# 4. -B stays a runtime CLI flag (1..64, default 1 = exact stock path),
#    exactly as Suthar built it - already the right discipline, nothing
#    to change there.
#
# WHAT THIS PATCH DELIBERATELY DOES NOT DO: pick a batch size. -B 1 is
# the default and is a no-op vs. today's safe/S4.0-hashmix behavior byte-
# for-byte (same order of operations, same hash, same cache logic - just
# computed one iteration ahead of where it's used when la_batch > 1). The
# actual batch size to run at has to be swept on Luna's real DBs/thread
# counts (standard_8gb/pluspf_103gb, 32T/96T) - Suthar's own sweep found
# the knee near B=20-30 on HIS machine, which is not evidence for what it
# will be here.
#
# Run from ~/tools/kraken2-src-fresh/src, against the safe/S4.0-hashmix
# tree. Back up first:
#   cp classify.cc classify.cc.pre-s5.0.bak
#   cp kv_store.h kv_store.h.pre-s5.0.bak
#   cp compact_hash.h compact_hash.h.pre-s5.0.bak
#   cp compact_hash.cc compact_hash.cc.pre-s5.0.bak

import re

# ---------------------------------------------------------------------------
# File 1: kv_store.h - add GetWithHash/Prefetch to the abstract interface.
# CompactHashTable is confirmed the ONLY class implementing KeyValueStore
# (grep -rn "public KeyValueStore" src/ -> exactly one hit), so adding two
# new pure-virtual methods cannot break a second, unrelated subclass.
# ---------------------------------------------------------------------------
path = "kv_store.h"
with open(path) as f:
    content = f.read()

old = '''class KeyValueStore {
  public:
  virtual hvalue_t Get(hkey_t key) const = 0;
  virtual ~KeyValueStore() { }
};'''

new = '''class KeyValueStore {
  public:
  virtual hvalue_t Get(hkey_t key) const = 0;
  // S5.0: look up with a hash the caller already computed, and start the
  // memory fetch for that hash without waiting for it - together these
  // let a caller issue several lookups before consuming any of them.
  virtual hvalue_t GetWithHash(hkey_t key, uint64_t hc) const = 0;
  virtual void Prefetch(uint64_t hc) const = 0;
  virtual ~KeyValueStore() { }
};'''

assert content.count(old) == 1, "kv_store.h: KeyValueStore class body not found exactly once"
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("kv_store.h patched OK")

# ---------------------------------------------------------------------------
# File 2: compact_hash.h - declare the two new methods.
# ---------------------------------------------------------------------------
path = "compact_hash.h"
with open(path) as f:
    content = f.read()

old = '''  hvalue_t Get(hkey_t key) const;
  bool FindIndex(hkey_t key, size_t *idx) const;'''

new = '''  hvalue_t Get(hkey_t key) const;
  hvalue_t GetWithHash(hkey_t key, uint64_t hc) const;
  void Prefetch(uint64_t hc) const;
  bool FindIndex(hkey_t key, size_t *idx) const;'''

assert content.count(old) == 1, "compact_hash.h: Get/FindIndex declarations not found exactly once"
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("compact_hash.h patched OK")

# ---------------------------------------------------------------------------
# File 3: compact_hash.cc - split Get() into a thin wrapper + GetWithHash()
# (identical probe logic, just fed a hash instead of computing its own),
# plus Prefetch(). This tree's real layout (confirmed via direct read,
# src/compact_hash.cc:109-128): compacted_key = hc >> (32 + value_bits_),
# NOT Suthar fork's hc >> (64 - key_bits_) - written against this tree's
# actual code, not his diff.
# ---------------------------------------------------------------------------
path = "compact_hash.cc"
with open(path) as f:
    content = f.read()

old = '''hvalue_t CompactHashTable::Get(hkey_t key) const {
  uint64_t hc = MurmurHash3(key);
  uint64_t compacted_key = hc >> (32 + value_bits_);
  size_t idx = hc % capacity_;
  size_t first_idx = idx;
  size_t step = 0;
  while (true) {
    if (! table_[idx].value(value_bits_))  // value of 0 means data is 0, saves work
      break;  // search over, empty cell encountered in probe
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0)
      step = second_hash(hc);
    idx += step;
    idx %= capacity_;
    if (idx == first_idx)
      break;  // search over, we've exhausted the table
  }
  return 0;
}'''

new = '''hvalue_t CompactHashTable::Get(hkey_t key) const {
  return GetWithHash(key, MurmurHash3(key));
}

// S5.0: issue the memory fetch for the cell this hash lands on, without
// waiting for it - the caller can issue several of these before resolving
// any of them, overlapping DRAM latency across lookups instead of paying
// it out serially, once per lookup.
void CompactHashTable::Prefetch(uint64_t hc) const {
  __builtin_prefetch(&table_[hc % capacity_], 0, 3);
}

hvalue_t CompactHashTable::GetWithHash(hkey_t key, uint64_t hc) const {
  uint64_t compacted_key = hc >> (32 + value_bits_);
  size_t idx = hc % capacity_;
  size_t first_idx = idx;
  size_t step = 0;
  while (true) {
    if (! table_[idx].value(value_bits_))  // value of 0 means data is 0, saves work
      break;  // search over, empty cell encountered in probe
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0)
      step = second_hash(hc);
    idx += step;
    idx %= capacity_;
    if (idx == first_idx)
      break;  // search over, we've exhausted the table
  }
  return 0;
}'''

assert content.count(old) == 1, "compact_hash.cc: Get() body not found exactly once"
content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("compact_hash.cc patched OK")

# ---------------------------------------------------------------------------
# File 4: classify.cc - four edits, in order.
# ---------------------------------------------------------------------------
path = "classify.cc"
with open(path) as f:
    content = f.read()

# --- 4a: S2SetIndex/S2Lookup/S2Insert take the caller's precomputed hash
# instead of re-deriving it, and PfSlot/la_batch/PF_MAX are declared right
# before ClassifySequence - same placement pattern as every prior S-step.
old_helpers = '''// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  // S4.0b/c: mix bits via Kraken2's own MurmurHash3 (kv_store.h)
  // before masking - the raw minimizer's low bits are badly
  // non-uniform (measured on standard_8gb/T=1: one set absorbed 225x
  // the average load, another was never touched, across 4,096 sets).
  // Validated on the S4.0 diagnostic first: fix raised hit rate from
  // 0.4035% to 3.5758% (~8.9x) at the same capacity, occupancy
  // max/mean from 225.42 to 3.95.
  return MurmurHash3(minimizer) & (s2_num_sets - 1);
}

// S2.2: check all 4 ways in the target set. Returns true and fills
// *out_taxon on a hit; on a miss, *out_taxon is left untouched.
static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {
  if (minimizer == S2_EMPTY_TAG) return false;  // S3.3: 0 is now the empty
                                                 // sentinel - a real minimizer
                                                 // of exactly 0 (vanishingly
                                                 // rare) is never cached,
                                                 // always falls through to
                                                 // hash->Get(); correctness
                                                 // unaffected.
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx * S2_WAYS + way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx * S2_WAYS + way].taxon;
      return true;
    }
  }
  return false;
}

// S2.3: insert/overwrite via simple round-robin - always evict whichever
// way is "next" for this set, then advance the pointer. Deliberately
// simple; S4 replaces this with a smarter policy later.
static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {
  if (minimizer == S2_EMPTY_TAG) return;  // S3.3: never insert the sentinel
                                           // value itself - see S2Lookup.
  S2EnsureInit();
  size_t set_idx = S2SetIndex(minimizer);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx * S2_WAYS + way].tag = minimizer;
  s2_cache[set_idx * S2_WAYS + way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}

taxid_t ClassifySequence(Sequence &dna, Sequence &dna2, ostringstream &koss,'''

new_helpers = '''// S2.1: which set a hash belongs to - a bitmask, not a search.
//
// S5.0: takes the already-mixed hash (hc = MurmurHash3(minimizer)), not
// the raw minimizer. Pass 1 of the prefetch loop below computes this hash
// exactly once per non-repeat minimizer and reuses it for the -M skip
// check, this set index, and the real hash table lookup - before S5.0,
// this function called MurmurHash3 itself (S4.0b/c), a second, redundant
// hash of the same value. Moving the call to the one place it's actually
// needed removes the duplicate without changing which bits pick the set.
static inline size_t S2SetIndex(uint64_t hc) {
  return hc & (s2_num_sets - 1);
}

// S2.2: check all 4 ways in the target set. Returns true and fills
// *out_taxon on a hit; on a miss, *out_taxon is left untouched.
static inline bool S2Lookup(uint64_t minimizer, uint64_t hc, taxid_t *out_taxon) {
  if (minimizer == S2_EMPTY_TAG) return false;  // S3.3: 0 is now the empty
                                                 // sentinel - a real minimizer
                                                 // of exactly 0 (vanishingly
                                                 // rare) is never cached,
                                                 // always falls through to
                                                 // hash->Get(); correctness
                                                 // unaffected.
  S2EnsureInit();
  size_t set_idx = S2SetIndex(hc);
  for (size_t way = 0; way < S2_WAYS; way++) {
    if (s2_cache[set_idx * S2_WAYS + way].tag == minimizer) {
      *out_taxon = s2_cache[set_idx * S2_WAYS + way].taxon;
      return true;
    }
  }
  return false;
}

// S2.3: insert/overwrite via simple round-robin - always evict whichever
// way is "next" for this set, then advance the pointer. Deliberately
// simple; S4 replaces this with a smarter policy later.
static inline void S2Insert(uint64_t minimizer, uint64_t hc, taxid_t taxon) {
  if (minimizer == S2_EMPTY_TAG) return;  // S3.3: never insert the sentinel
                                           // value itself - see S2Lookup.
  S2EnsureInit();
  size_t set_idx = S2SetIndex(hc);
  uint8_t way = s2_next_way[set_idx];
  s2_cache[set_idx * S2_WAYS + way].tag = minimizer;
  s2_cache[set_idx * S2_WAYS + way].taxon = taxon;
  s2_next_way[set_idx] = (way + 1) % S2_WAYS;
}

// S5.0 - batched lookup with software prefetch (-B), ported from Chirag
// Suthar's mtp1/scripts/kraken2_prefetch.patch (hobbbit branch). His
// measured -20.34% is on a different machine/DB/codebase fork and is NOT
// a Luna number - see PREFETCH.md and
// plan_paper/track_a_pivot_debate_2026-08-30.md Q3. The mechanism: the
// stock loop below resolves one minimizer at a time, so every lookup
// waits out a ~200-cycle DRAM miss before the next one starts - this
// project's own M4 finding put Luna's DRAM bandwidth utilization at
// 4.9-10.7% of peak (latency-bound, not bandwidth-bound), meaning there
// is real headroom to overlap fetches instead of serializing them. Pass 1
// (below) hashes up to la_batch minimizers and issues a hardware prefetch
// for each; pass 2 resolves them in the original order, by which time the
// fetches have had time to land. -B 1 (the default) is the exact stock
// one-at-a-time path.
static int la_batch = 1;
static const int PF_MAX = 64;
struct PfSlot {
  uint64_t min;   // the minimizer
  uint64_t hc;    // MurmurHash3(min), computed once in pass 1 - reused for
                  // the -M skip check, S2's set index, and GetWithHash
  bool     amb;   // scanner.is_ambiguous() AT THE TIME THIS WAS SCANNED -
                  // the scanner has moved on by pass 2, so this must be
                  // captured here, not re-asked later
};

taxid_t ClassifySequence(Sequence &dna, Sequence &dna2, ostringstream &koss,'''

assert content.count(old_helpers) == 1, "classify.cc: S2 helper block not found exactly once"
content = content.replace(old_helpers, new_helpers)

# --- 4b: the loop itself, split into pass 1 (scan/hash/prefetch) and
# pass 2 (resolve) - S1's repeat check and S2's cache check move into
# pass 2, fed by pf[pf_i].hc instead of a value they compute themselves.
old_loop = '''      while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {
        taxid_t taxon;
        if (scanner.is_ambiguous()) {
          taxon = AMBIGUOUS_SPAN_TAXON;
        }
        else {
          if (*minimizer_ptr != s1_last_minimizer) {
            bool skip_lookup = false;
            if (idx_opts.minimum_acceptable_hash_value) {
              if (MurmurHash3(*minimizer_ptr) < idx_opts.minimum_acceptable_hash_value)
                skip_lookup = true;
            }
            taxon = 0;
            if (! skip_lookup) {
              // S2.2/S2.3 - try the 4-way cache before paying for a real
              // hash table lookup. This ONLY decides whether Get() runs -
              // it does not touch the stats-counting logic below.
              if (! S2Lookup(*minimizer_ptr, &taxon)) {
                taxon = hash->Get(*minimizer_ptr);
                S2Insert(*minimizer_ptr, taxon);
              }
            }
            s1_last_taxon = taxon;
            s1_last_minimizer = *minimizer_ptr;
            // Increment this only if (a) we have DB hit and
            // (b) minimizer != last minimizer
            if (taxon) {
              minimizer_hit_groups++;
              // New minimizer should trigger registering minimizer in RC/HLL
              if (!opts.report_filename.empty()) {
                curr_taxon_counts[taxon].add_kmer(scanner.last_minimizer());
              }
            }
          }
          else {
            taxon = s1_last_taxon;
          }
          if (taxon) {
            if (opts.quick_mode && minimizer_hit_groups >= opts.minimum_hit_groups) {
              call = taxon;
              goto finished_searching;  // need to break 3 loops here
            }
            hit_counts[taxon]++;
          }
        }
        taxa.push_back(taxon);
      }'''

new_loop = '''      PfSlot pf[PF_MAX];
      bool frame_done = false;
      while (! frame_done) {
        // ---- pass 1: scan a batch, hash it, start the memory fetches.
        // Hashes every non-ambiguous minimizer unconditionally, even ones
        // that will turn out to be an immediate repeat of s1_last_minimizer
        // or a hit in S2's cache - a prefetch/hash that turns out
        // unnecessary is harmless (it just starts a fetch nothing ends up
        // using), and checking repeat status here would mean tracking it
        // across batch boundaries for no measured benefit. Same tradeoff
        // Suthar's original patch made, validated there at 16/16 byte-
        // identical output/report vs. stock.
        int n_pf = 0;
        while (n_pf < la_batch) {
          minimizer_ptr = scanner.NextMinimizer();
          if (minimizer_ptr == nullptr) { frame_done = true; break; }
          pf[n_pf].min = *minimizer_ptr;
          pf[n_pf].amb = scanner.is_ambiguous();
          if (! pf[n_pf].amb) {
            pf[n_pf].hc = MurmurHash3(pf[n_pf].min);
            hash->Prefetch(pf[n_pf].hc);
          }
          n_pf++;
        }
        // ---- pass 2: resolve in the original order, by which time the
        // fetches issued above have had time to land.
        for (int pf_i = 0; pf_i < n_pf; pf_i++) {
          taxid_t taxon;
          if (pf[pf_i].amb) {
            taxon = AMBIGUOUS_SPAN_TAXON;
          }
          else {
            if (pf[pf_i].min != s1_last_minimizer) {
              bool skip_lookup = false;
              if (idx_opts.minimum_acceptable_hash_value) {
                if (pf[pf_i].hc < idx_opts.minimum_acceptable_hash_value)
                  skip_lookup = true;
              }
              taxon = 0;
              if (! skip_lookup) {
                // S2.2/S2.3 - try the 4-way cache before paying for a real
                // hash table lookup. This ONLY decides whether Get() runs -
                // it does not touch the stats-counting logic below.
                if (! S2Lookup(pf[pf_i].min, pf[pf_i].hc, &taxon)) {
                  taxon = hash->GetWithHash(pf[pf_i].min, pf[pf_i].hc);
                  S2Insert(pf[pf_i].min, pf[pf_i].hc, taxon);
                }
              }
              s1_last_taxon = taxon;
              s1_last_minimizer = pf[pf_i].min;
              // Increment this only if (a) we have DB hit and
              // (b) minimizer != last minimizer
              if (taxon) {
                minimizer_hit_groups++;
                // New minimizer should trigger registering minimizer in
                // RC/HLL. Uses the captured pf[pf_i].min, not
                // scanner.last_minimizer() - the scanner has advanced past
                // this whole batch by now. Valid because NextMinimizer()
                // returns &last_minimizer_ (mmscanner.cc), so the captured
                // value is identical to what the scanner would have
                // reported at the moment it was scanned.
                if (!opts.report_filename.empty()) {
                  curr_taxon_counts[taxon].add_kmer(pf[pf_i].min);
                }
              }
            }
            else {
              taxon = s1_last_taxon;
            }
            if (taxon) {
              if (opts.quick_mode && minimizer_hit_groups >= opts.minimum_hit_groups) {
                call = taxon;
                goto finished_searching;  // need to break 3 loops here
              }
              hit_counts[taxon]++;
            }
          }
          taxa.push_back(taxon);
        }
      }'''

assert content.count(old_loop) == 1, "classify.cc: main minimizer loop not found exactly once"
content = content.replace(old_loop, new_loop)

# --- 4c: -B flag, ParseCommandLine.
old_getopt = '''  while ((opt = getopt(argc, argv, "h?H:t:o:T:p:R:C:U:O:Q:g:nmzqPSMKD")) != -1) {
    switch (opt) {
      case 'h' : case '?' :
        usage(0);
        break;
      case 'H' :'''

new_getopt = '''  while ((opt = getopt(argc, argv, "h?H:t:o:T:p:R:C:U:O:Q:g:B:nmzqPSMKD")) != -1) {
    switch (opt) {
      case 'h' : case '?' :
        usage(0);
        break;
      case 'B' :
        // S5.0: batch size for prefetch-batched lookup, 1..PF_MAX. 1 (the
        // default) is the exact stock one-at-a-time path - nothing changes
        // unless this flag is passed.
        la_batch = atoi(optarg);
        if (la_batch < 1 || la_batch > PF_MAX)
          errx(EX_USAGE, "-B expects a batch size between 1 and %d", PF_MAX);
        break;
      case 'H' :'''

assert content.count(old_getopt) == 1, "classify.cc: getopt/case block not found exactly once"
content = content.replace(old_getopt, new_getopt)

# --- 4d: usage() text.
old_usage = '''       << "  -K               In comb. w/ -R, provide minimizer information in report" << endl
       << "  -D               Start a daemon, this options is intended to be used with wrappers" << std::endl;'''

new_usage = '''       << "  -K               In comb. w/ -R, provide minimizer information in report" << endl
       << "  -B NUM           Batch NUM minimizers and prefetch their hash-table" << endl
       << "                   lines before resolving them (def. 1 = stock path)" << endl
       << "  -D               Start a daemon, this options is intended to be used with wrappers" << std::endl;'''

assert content.count(old_usage) == 1, "classify.cc: usage() -K/-D lines not found exactly once"
content = content.replace(old_usage, new_usage)

with open(path, "w") as f:
    f.write(content)
print("classify.cc patched OK")
