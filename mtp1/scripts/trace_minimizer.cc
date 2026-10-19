// trace_minimizer — follow one minimizer from a read all the way to a taxid.
//
// Backs MEETING_UPDATE_2026-10-20.md Part 2 / FLOW.md. Links kraken2's own
// mmscanner / compact_hash / taxonomy so nothing is reimplemented: every number
// printed is produced by the same code classify runs.
//
//   usage: trace_minimizer <db_dir> <fastq> [read_index] [max_minimizers]
#include "kraken2_headers.h"
#include "mmscanner.h"
#include "compact_hash.h"
#include "taxonomy.h"
#include "kraken2_data.h"
#include <fstream>
#include <iostream>
#include <iomanip>

using namespace kraken2;

// mirrors CompactHashTable::second_hash so the probe sequence can be shown
static inline uint64_t second_hash_of(uint64_t first) { return (first >> 8) | 1; }

int main(int argc, char **argv) {
  if (argc < 3) { std::cerr << "usage: " << argv[0]
    << " <db_dir> <fastq> [read_index] [max_minimizers]\n"; return 1; }
  std::string db = argv[1], fq = argv[2];
  size_t want_read = argc > 3 ? strtoul(argv[3], nullptr, 10) : 0;
  size_t max_mm    = argc > 4 ? strtoul(argv[4], nullptr, 10) : 5;

  IndexOptions opts = {0};
  std::ifstream oin((db + "/opts.k2d").c_str(), std::ios::binary);
  oin.read((char *) &opts, sizeof(opts));
  oin.close();

  CompactHashTable<CompactHashCell> hash((db + "/hash.k2d").c_str(), true);
  Taxonomy tax((db + "/taxo.k2d").c_str(), true);

  std::cout << "database              " << db << "\n"
            << "  k / l               " << opts.k << " / " << opts.l << "\n"
            << "  spaced_seed_mask    " << opts.spaced_seed_mask
            << "  (0x" << std::hex << opts.spaced_seed_mask << std::dec << ")\n"
            << "  toggle_mask         0x" << std::hex << opts.toggle_mask << std::dec << "\n"
            << "  capacity (cells)    " << hash.capacity() << "\n"
            << "  key_bits/value_bits " << hash.key_bits() << " / " << hash.value_bits() << "\n"
            << "  min_acceptable_hash " << opts.minimum_acceptable_hash_value << "\n"
            << "  taxonomy nodes      " << tax.node_count() << "\n\n";

  // pull read #want_read out of the fastq
  std::ifstream in(fq.c_str());
  std::string hdr, seq, plus, qual;
  for (size_t i = 0; i <= want_read; i++) {
    if (!std::getline(in, hdr) || !std::getline(in, seq)
        || !std::getline(in, plus) || !std::getline(in, qual)) {
      std::cerr << "fastq ended before read " << want_read << "\n"; return 1; }
  }
  std::cout << "read                  " << hdr << "\n"
            << "  length              " << seq.size() << " bp\n\n";

  MinimizerScanner scanner(opts.k, opts.l, opts.spaced_seed_mask, true, opts.toggle_mask);
  scanner.LoadSequence(seq);

  uint64_t *mp;
  size_t shown = 0, total = 0;
  uint64_t last = UINT64_MAX;
  while ((mp = scanner.NextMinimizer()) != nullptr) {
    if (scanner.is_ambiguous() || *mp == last) { last = *mp; continue; }
    last = *mp; total++;
    if (shown >= max_mm) continue;
    shown++;

    uint64_t minimizer = *mp;
    uint64_t hc        = MurmurHash3(minimizer);
    uint64_t ckey      = hc >> (64 - hash.key_bits());
    size_t   slot      = hc % hash.capacity();
    bool     skipped   = opts.minimum_acceptable_hash_value
                         && hc < opts.minimum_acceptable_hash_value;
    hvalue_t internal  = skipped ? 0 : hash.Get(minimizer);

    std::cout << "--- minimizer #" << total << " -------------------------------------\n";
    std::cout << "  1 minimizer       " << minimizer
              << "  (0x" << std::hex << std::setw(16) << std::setfill('0')
              << minimizer << std::dec << std::setfill(' ') << ")\n";
    std::cout << "  2 MurmurHash3     " << hc
              << "  (0x" << std::hex << hc << std::dec << ")\n";
    std::cout << "  3 -M gate         " << (opts.minimum_acceptable_hash_value
              ? (skipped ? "SKIPPED (hash < threshold, no lookup)"
                         : "passes (hash >= threshold)") : "no -M, always looks up") << "\n";
    if (!skipped) {
      std::cout << "  4 stored key      hc >> " << (64 - hash.key_bits()) << " = " << ckey
                << "  (0x" << std::hex << ckey << std::dec << ")\n";
      std::cout << "  5 home slot       hc % " << hash.capacity() << " = " << slot << "\n";
      size_t found;
      if (hash.FindIndex(minimizer, &found)) {
        size_t step = second_hash_of(hc);
        std::cout << "  6 found at slot   " << found;
        if (found != slot) std::cout << "   (probed, step = " << step << ")";
        else std::cout << "   (first probe, no collision)";
        std::cout << "\n";
      } else {
        std::cout << "  6 found at slot   -- not in table --\n";
      }
      std::cout << "  7 cell value      " << (unsigned) internal
                << "   = internal node id (" << hash.value_bits() << " bits, max "
                << ((1u << hash.value_bits()) - 1) << ")\n";
      if (internal) {
        std::cout << "  8 taxo.k2d lookup external_id = "
                  << tax.nodes()[internal].external_id << "\n";
        std::cout << "  9 TAXID           " << tax.nodes()[internal].external_id
                  << "   rank=" << (tax.rank_data() + tax.nodes()[internal].rank_offset)
                  << "   name=" << (tax.name_data() + tax.nodes()[internal].name_offset) << "\n";
      } else {
        std::cout << "  8 TAXID           0  (miss - minimizer not in this database)\n";
      }
    }
    std::cout << "\n";
  }
  std::cout << "distinct minimizers in this read: " << total << "\n";
  return 0;
}
