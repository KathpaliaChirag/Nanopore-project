# S4.0b - fix S2SetIndex's bit-mixing, applied to the S4.0 diagnostic
# variant first for a direct before/after measurement (2026-08-30).
#
# S4.0's occupancy instrumentation found a real bug: S2SetIndex is
# `minimizer & (S2_NUM_SETS - 1)` - a raw low-bit mask, no mixing.
# Measured on standard_8gb/T=1: min=0, max=165460, mean=734.02,
# max/mean=225.42 across 4,096 sets - one set absorbing 225x the
# average load while others sit empty. Kraken2's minimizer values
# apparently have badly non-uniform low bits (likely a base-composition
# artifact of how k-mers get packed).
#
# Fix: mix the minimizer through MurmurHash3 before masking - already
# declared in kv_store.h (already #included by classify.cc), already
# used by Kraken2's own main hash table (compact_hash.cc) for exactly
# this purpose. No new includes needed.
#
# Run from ~/tools/kraken2-src-fresh/src, against the S4.0-patched
# classify.cc (built as kraken2-fresh-bin-s4-0-diagnostic).

path = "classify.cc"
with open(path) as f:
    content = f.read()

old_index = '''static inline size_t S2SetIndex(uint64_t minimizer) {
  return minimizer & (S2_NUM_SETS - 1);
}'''

new_index = '''static inline size_t S2SetIndex(uint64_t minimizer) {
  // S4.0b: mix bits via Kraken2's own MurmurHash3 (kv_store.h) before
  // masking - the raw minimizer's low bits are badly non-uniform
  // (measured on standard_8gb/T=1: one set absorbed 225x the average
  // load, another was never touched, across 4,096 sets).
  return MurmurHash3(minimizer) & (S2_NUM_SETS - 1);
}'''

assert content.count(old_index) == 1, "S2SetIndex not found exactly once"
content = content.replace(old_index, new_index)

with open(path, "w") as f:
    f.write(content)
print("patched OK")
