# S4.0c - port the S4.0b bit-mixing fix into the real, committed S3.3
# tree (2026-08-30). Validated on the S4.0 diagnostic variant first:
# same DB/fastq/T=1, hit rate went from 0.4035% to 3.5758% (~8.9x),
# occupancy max/mean from 225.42 to 3.95 - the raw low-bit mask was a
# real, previously-undiscovered bug undermining the cache's entire
# effective capacity.
#
# This targets the real tree's S2SetIndex, which reads the runtime
# s2_num_sets variable (S3.1/S3.2's dynamic formula) rather than the
# diagnostic variant's fixed S2_NUM_SETS constant - same fix, just
# against the variable name that actually exists in production.
#
# Run from ~/tools/kraken2-src-fresh/src, against the S3.3-patched
# classify.cc (tag safe/S3.3).

path = "classify.cc"
with open(path) as f:
    content = f.read()

old_index = '''// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (s2_num_sets - 1);
}'''

new_index = '''// S2.1: which set a minimizer belongs to - a bitmask, not a search.
static inline size_t S2SetIndex(uint64_t minimizer) {
  // S4.0b/c: mix bits via Kraken2's own MurmurHash3 (kv_store.h)
  // before masking - the raw minimizer's low bits are badly
  // non-uniform (measured on standard_8gb/T=1: one set absorbed 225x
  // the average load, another was never touched, across 4,096 sets).
  // Validated on the S4.0 diagnostic first: fix raised hit rate from
  // 0.4035% to 3.5758% (~8.9x) at the same capacity, occupancy
  // max/mean from 225.42 to 3.95.
  return MurmurHash3(minimizer) & (s2_num_sets - 1);
}'''

assert content.count(old_index) == 1, "S2SetIndex not found exactly once"
content = content.replace(old_index, new_index)

with open(path, "w") as f:
    f.write(content)
print("patched OK")
