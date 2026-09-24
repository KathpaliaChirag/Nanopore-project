#include "seqreader.h"
#include <chrono>
int main(int argc, char **argv) {
  kraken2::BatchSequenceReader r(argv[1]);
  auto t0 = std::chrono::steady_clock::now();
  size_t blocks = 0, seqs = 0;
  while (r.LoadBlock((size_t)3 * 1024 * 1024)) { blocks++; while (r.NextSequence()) seqs++; }
  double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  printf("blocks=%zu seqs=%zu parse-only wall=%.2fs\n", blocks, seqs, s);
}
