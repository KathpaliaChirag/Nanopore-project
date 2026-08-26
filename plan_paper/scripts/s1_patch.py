# S1.1 patch script - actually run on Luna against
# ~/tools/kraken2-src-fresh/src/classify.cc on 2026-08-25.
#
# Promotes the existing last_minimizer/last_taxon adjacent-repeat cache from
# function-local (reset every ClassifySequence call) to thread_local storage
# (persists across every read/mate/frame processed by that thread). See
# plan_paper/command_log.md's "S1.1 investigation" and "S1.1 patch applied"
# entries for the full reasoning, and plan_paper/patches/s1_thread_local_cache.diff
# for the actual resulting diff.

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

new_sig = '''// S1.1 - thread-local single-slot minimizer cache. One instance per OS
// thread (each OpenMP worker owns its own copy), persisting across every
// read/mate/frame that thread processes - unlike the old last_minimizer/
// last_taxon pair below, which used to be local to one ClassifySequence
// call and forgot everything the moment that call returned. Safe to
// share this widely because hash->Get() is a pure function of the
// minimizer value: whatever thread last computed an answer for a given
// minimizer, that answer is still correct for any other read that thread
// processes next.
static thread_local uint64_t s1_last_minimizer = UINT64_MAX;
static thread_local taxid_t s1_last_taxon = TAXID_MAX;

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

old_reset = '''      uint64_t last_minimizer = UINT64_MAX;
      taxid_t last_taxon = TAXID_MAX;
      while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {'''
new_reset = '''      while ((minimizer_ptr = scanner.NextMinimizer()) != nullptr) {'''
assert content.count(old_reset) == 1, "reset lines not found exactly once"
content = content.replace(old_reset, new_reset)

# Each pattern includes surrounding context specifically so it cannot match
# scanner.last_minimizer() (a MinimizerScanner *method call*, unrelated to
# our variables) - confirmed via a full-file grep before this script was run.
content = content.replace("*minimizer_ptr != last_minimizer", "*minimizer_ptr != s1_last_minimizer")
content = content.replace("last_taxon = taxon;", "s1_last_taxon = taxon;")
content = content.replace("last_minimizer = *minimizer_ptr;", "s1_last_minimizer = *minimizer_ptr;")
content = content.replace("taxon = last_taxon;", "taxon = s1_last_taxon;")

with open(path, "w") as f:
    f.write(content)

print("patched OK")
