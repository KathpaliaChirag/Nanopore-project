# S15 (2026-09-24): run-length batching of hit_counts increments.
# perf: std::unordered_map operator[] for `hit_counts[taxon]++` was ~5-6% of
# cycles on every DB. Consecutive minimizers very often resolve to the same
# taxon, so count a run in a local and flush it to the map only when the
# taxon changes (and at the end / before an early quick-mode exit).
# Final counts are identical; keys are inserted in the same first-occurrence
# order as before (runs flush in order), so the map's iteration order, which
# ResolveTree depends on for tie-breaking, is unchanged.
p = "classify.cc"
s = open(p).read()

old = "  int64_t minimizer_hit_groups = 0;\n"
assert s.count(old) == 1
s = s.replace(old, old + "  taxid_t run_taxon = 0;      // S15: pending run of identical hit taxa\n  uint64_t run_count = 0;\n")

old = '''            if (taxon) {
              if (opts.quick_mode && minimizer_hit_groups >= opts.minimum_hit_groups) {
                call = taxon;
                goto finished_searching;  // need to break 3 loops here
              }
              hit_counts[taxon]++;
            }'''
new = '''            if (taxon) {
              if (opts.quick_mode && minimizer_hit_groups >= opts.minimum_hit_groups) {
                call = taxon;
                if (run_count) hit_counts[run_taxon] += run_count;
                run_count = 0;
                goto finished_searching;  // need to break 3 loops here
              }
              if (run_count && taxon == run_taxon) {
                run_count++;
              } else {
                if (run_count) hit_counts[run_taxon] += run_count;
                run_taxon = taxon;
                run_count = 1;
              }
            }'''
assert s.count(old) == 1
s = s.replace(old, new)

old = "  finished_searching:\n"
assert s.count(old) == 1
s = s.replace(old, "  if (run_count) hit_counts[run_taxon] += run_count;  // S15: flush last run\n  run_count = 0;\n\n" + old)
open(p, "w").write(s)
print("S15 patched OK")
