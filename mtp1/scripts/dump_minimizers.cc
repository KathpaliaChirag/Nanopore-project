// dump every distinct minimizer + its hash, for "why hash at all" analysis
#include "kraken2_headers.h"
#include "mmscanner.h"
#include "kv_store.h"
#include "kraken2_data.h"
#include <fstream>
#include <cstdio>
using namespace kraken2;
int main(int argc, char **argv) {
  IndexOptions opts = {0};
  std::ifstream oin((std::string(argv[1]) + "/opts.k2d").c_str(), std::ios::binary);
  oin.read((char *) &opts, sizeof(opts)); oin.close();
  size_t max_reads = argc > 3 ? strtoul(argv[3], nullptr, 10) : 2000;
  std::ifstream in(argv[2]);
  std::string h, s, p, q;
  MinimizerScanner scanner(opts.k, opts.l, opts.spaced_seed_mask, true, opts.toggle_mask);
  size_t nread = 0;
  while (nread < max_reads && std::getline(in, h) && std::getline(in, s)
         && std::getline(in, p) && std::getline(in, q)) {
    nread++;
    scanner.LoadSequence(s);
    uint64_t *mp, last = UINT64_MAX;
    while ((mp = scanner.NextMinimizer()) != nullptr) {
      if (scanner.is_ambiguous() || *mp == last) { last = *mp; continue; }
      last = *mp;
      printf("%llu %llu\n", (unsigned long long) *mp,
             (unsigned long long) MurmurHash3(*mp));
    }
  }
  fprintf(stderr, "reads %zu\n", nread);
  return 0;
}
