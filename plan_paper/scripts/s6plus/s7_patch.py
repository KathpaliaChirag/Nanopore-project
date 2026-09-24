# S7 (2026-09-24) = S6 (4-way RR cache, no atomics, MurmurHash-mixed set index)
# + S5.0-style batched software prefetch. Applies to STOCK classify.cc.
# Batch size comes from env K2_B (default 16, 1 = stock one-at-a-time order),
# so it can be swept without rebuilding (the perl wrapper does not pass -B).
# Correctness argument: pass 1 only hashes + prefetches; pass 2 resolves in
# the original order with the same logic, so the taxa sequence is identical.
path = "classify.cc"
content = open(path).read()

old_sig = '''taxid_t ClassifySequence(Sequence &dna, Sequence &dna2, ostringstream &koss,
                         KeyValueStore *hash, Taxonomy &taxonomy,
                         IndexOptions &idx_opts, Options &opts,
                         ClassificationStats &stats, MinimizerScanner &scanner,
                         vector<taxid_t> &taxa, taxon_counts_t &hit_counts,
                         vector<string> &tx_frames,
                         taxon_counters_t &curr_taxon_counts)
{
  uint64_t *minimizer_ptr;'''

new_sig = '''// ---- S7: S6 cache + batched prefetch ----
static const size_t S2_NUM_SETS = 4096;
static const size_t S2_WAYS = 4;
static const uint64_t S2_EMPTY_TAG = UINT64_MAX;
struct S2Entry { uint64_t tag = S2_EMPTY_TAG; taxid_t taxon = TAXID_MAX; };
static thread_local S2Entry s2_cache[S2_NUM_SETS][S2_WAYS];
static thread_local uint8_t s2_next_way[S2_NUM_SETS] = {0};

// hc is the already-computed MurmurHash3(minimizer): one hash per minimizer,
// reused for the -M skip check, the cache set index, and the table lookup.
static inline size_t S2SetIndex(uint64_t hc) { return hc & (S2_NUM_SETS - 1); }
static inline bool S2Lookup(uint64_t minimizer, uint64_t hc, taxid_t *out) {
  size_t s = S2SetIndex(hc);
  for (size_t w = 0; w < S2_WAYS; w++)
    if (s2_cache[s][w].tag == minimizer) { *out = s2_cache[s][w].taxon; return true; }
  return false;
}
static inline void S2Insert(uint64_t minimizer, uint64_t hc, taxid_t taxon) {
  size_t s = S2SetIndex(hc);
  uint8_t w = s2_next_way[s];
  s2_cache[s][w].tag = minimizer; s2_cache[s][w].taxon = taxon;
  s2_next_way[s] = (w + 1) % S2_WAYS;
}
static const int PF_MAX = 64;
static int InitBatch() {
  const char *e = getenv("K2_B");
  int b = e ? atoi(e) : 16;
  if (b < 1) b = 1;
  if (b > PF_MAX) b = PF_MAX;
  return b;
}
static int la_batch = InitBatch();
struct PfSlot { uint64_t min; uint64_t hc; bool amb; };

taxid_t ClassifySequence(Sequence &dna, Sequence &dna2, ostringstream &koss,
                         KeyValueStore *hash, Taxonomy &taxonomy,
                         IndexOptions &idx_opts, Options &opts,
                         ClassificationStats &stats, MinimizerScanner &scanner,
                         vector<taxid_t> &taxa, taxon_counts_t &hit_counts,
                         vector<string> &tx_frames,
                         taxon_counters_t &curr_taxon_counts)
{
  uint64_t *minimizer_ptr;'''
assert content.count(old_sig) == 1
content = content.replace(old_sig, new_sig)

start = content.index("      uint64_t last_minimizer = UINT64_MAX;\n      taxid_t last_taxon = TAXID_MAX;\n      while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {")
end_marker = "        taxa.push_back(taxon);\n      }\n      if (opts.use_translated_search && frame_idx != 5)"
end = content.index(end_marker, start) + len("        taxa.push_back(taxon);\n      }\n")

new_loop = '''      uint64_t last_minimizer = UINT64_MAX;
      taxid_t last_taxon = TAXID_MAX;
      PfSlot pf[PF_MAX];
      bool frame_done = false;
      while (! frame_done) {
        // pass 1: scan a batch, hash once, start the memory fetches
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
        // pass 2: resolve in original order (identical logic to stock)
        for (int i = 0; i < n_pf; i++) {
          taxid_t taxon;
          if (pf[i].amb) {
            taxon = AMBIGUOUS_SPAN_TAXON;
          }
          else {
            if (pf[i].min != last_minimizer) {
              bool skip_lookup = false;
              if (idx_opts.minimum_acceptable_hash_value) {
                if (pf[i].hc < idx_opts.minimum_acceptable_hash_value)
                  skip_lookup = true;
              }
              taxon = 0;
              if (! skip_lookup) {
                if (! S2Lookup(pf[i].min, pf[i].hc, &taxon)) {
                  taxon = hash->GetWithHash(pf[i].min, pf[i].hc);
                  S2Insert(pf[i].min, pf[i].hc, taxon);
                }
              }
              last_taxon = taxon;
              last_minimizer = pf[i].min;
              if (taxon) {
                minimizer_hit_groups++;
                if (!opts.report_filename.empty()) {
                  curr_taxon_counts[taxon].add_kmer(pf[i].min);
                }
              }
            }
            else {
              taxon = last_taxon;
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
      }
'''
content = content[:start] + new_loop + content[end:]
open(path, "w").write(content)
print("S7 patched OK")
