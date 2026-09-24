# S16 (2026-09-24): software-pipelined prefetch.
# S9..S15 prefetch a batch and immediately resolve it, so the first lookups in
# each batch have had almost no time for their fetches to land. Here batch n+1
# is scanned/hashed/prefetched BEFORE batch n is resolved, so a full batch of
# resolve work covers the latency of the next batch's fetches. Resolution
# order and per-slot captured state (min, hc, idx, amb) are unchanged, so the
# taxa sequence and all counters are identical.
p = "classify.cc"
s = open(p).read()
a = s.index("      PfSlot pf[PF_MAX];\n      bool frame_done = false;")
b = s.index("      if (opts.use_translated_search && frame_idx != 5)")

new = '''      PfSlot pfA[PF_MAX], pfB[PF_MAX];
      PfSlot *cur = pfA, *nxt = pfB;
      // fill one batch: scan, hash once, start the memory fetches
      auto fill = [&](PfSlot *pf) -> int {
        int n = 0;
        while (n < la_batch) {
          minimizer_ptr = scanner.NextMinimizer();
          if (minimizer_ptr == nullptr) break;
          pf[n].min = *minimizer_ptr;
          pf[n].amb = scanner.is_ambiguous();
          if (! pf[n].amb) {
            pf[n].hc = MurmurHash3(pf[n].min);
            pf[n].idx = hash->PrefetchIndex(pf[n].hc);
          }
          n++;
        }
        return n;
      };
      int n_cur = fill(cur);
      bool exhausted = (n_cur < la_batch);
      while (n_cur > 0) {
        int n_nxt = 0;
        if (! exhausted) {          // start batch n+1 before resolving batch n
          n_nxt = fill(nxt);
          if (n_nxt < la_batch) exhausted = true;
        }
        PfSlot *pf = cur;
        for (int i = 0; i < n_cur; i++) {
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
                taxon = hash->GetAt(pf[i].min, pf[i].hc, pf[i].idx);
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
            }
          }
          taxa.push_back(taxon);
        }
        PfSlot *t = cur; cur = nxt; nxt = t;
        n_cur = n_nxt;
      }
'''
s = s[:a] + new + s[b:]
open(p, "w").write(s)
print("S16 patched OK")
