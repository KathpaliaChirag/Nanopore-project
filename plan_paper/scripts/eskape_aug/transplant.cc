// transplant.cc - teacher-gated k-mer transplant: 103GB ("teacher") -> small ESKAPE db ("student")
//
// why this exists: the 103GB table only keeps 16 of 64 hash bits per cell, so its keys cannot be
// read back out of the file (2^14 candidates per cell). what CAN be done: take minimizers we know
// (from reads), ask the teacher what it stores for them, and write that into the student.
//
// for every distinct minimizer m of the training reads:
//   t = teacher.Get(m)                      (0 -> absent in teacher, e.g. a sequencing-error k-mer: skipped)
//   gate: t must sit inside an allowed genus clade, or be a family/order ancestor of one
//   mapped = nearest ancestor-or-self of t that exists in the student's taxonomy
//   old = student.Get(m);  new = (old==0) ? mapped : LCA_student(old, mapped)
//   write new if it differs from old
// the teacher's value is already the LCA over ALL genomes it contains, so an existing student entry
// can only move UP (more general = fewer false species calls) and absent entries get filled in.
//
// build (stock tree objects):
//   g++ -O2 -std=c++11 -fopenmp -I. -o transplant transplant.cc compact_hash.o mmap_file.o taxonomy.o \
//       mmscanner.o seqreader.o omp_hack.o utilities.o
//
// usage: transplant -S small_db_dir -T teacher_db_dir -o out_hash.k2d [-P] [-E] [-n maxreads] reads.fastq...
//   -P  precision only: only modify entries the student already has (no new k-mers)
//   -E  ESKAPE genera only (exclude Escherichia and any other non-ESKAPE genus in the student tax)
#include "kraken2_headers.h"
#include "kraken2_data.h"
#include "compact_hash.h"
#include "taxonomy.h"
#include "mmscanner.h"
#include "seqreader.h"
#include <set>
#include <new>
#include <functional>

using namespace kraken2;
using std::string;

static IndexOptions read_opts(const string &fn) {
  IndexOptions o = {0};
  struct stat sb;
  if (stat(fn.c_str(), &sb) < 0) errx(1, "cannot stat %s", fn.c_str());
  std::ifstream f(fn);
  f.read((char *) &o, sb.st_size);
  return o;
}

static const char *rank_of(const Taxonomy &t, uint64_t id) {
  return t.rank_data() + t.nodes()[id].rank_offset;
}

int main(int argc, char **argv) {
  string small_dir, teach_dir, out_hash;
  bool precision_only = false, eskape_only = false, genome_pass = false;
  long max_reads = -1;
  std::vector<string> reads, genomes;
  string map_file, extra_file, ncbi_dir, out_dir;
  size_t new_capacity = 0;
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    if (a == "-S") small_dir = argv[++i];
    else if (a == "-T") teach_dir = argv[++i];
    else if (a == "-o") out_hash = argv[++i];
    else if (a == "-P") precision_only = true;
    else if (a == "-A") genome_pass = true;
    else if (a == "-E") eskape_only = true;
    else if (a == "-n") max_reads = atol(argv[++i]);
    else if (a == "-g") genomes.push_back(argv[++i]);
    else if (a == "-X") extra_file = argv[++i];
    else if (a == "-N") ncbi_dir = argv[++i];
    else if (a == "-D") out_dir = argv[++i];
    else if (a == "-m") map_file = argv[++i];
    else if (a == "-c") new_capacity = (size_t) atoll(argv[++i]);
    else reads.push_back(a);
  }
  if (small_dir.empty() || teach_dir.empty() || out_hash.empty() || reads.empty())
    errx(1, "usage: transplant -S small -T teacher -o out_hash.k2d [-P] [-E] [-n N] reads...");

  IndexOptions so = read_opts(small_dir + "/opts.k2d");
  IndexOptions to = read_opts(teach_dir + "/opts.k2d");
  if (so.k != to.k || so.l != to.l || so.toggle_mask != to.toggle_mask ||
      so.spaced_seed_mask != to.spaced_seed_mask || so.revcom_version != to.revcom_version)
    errx(1, "student and teacher minimizer parameters differ; keys are not interchangeable");

  // -X: extend the student taxonomy with extra external taxids (+ all their ancestors) so that
  // competitor species get their own node. internal ids are re-assigned breadth-first, so every
  // table value must be re-derived: this needs the genome rebuild (-g). value bits grow as needed
  // (build_db's own rule: smallest b with 2^b >= node_count), key bits shrink to 32 - b.
  string stax_path = small_dir + "/taxo.k2d";
  bool taxonomy_extended = false;
  if (!extra_file.empty()) {
    if (ncbi_dir.empty() || out_dir.empty()) errx(1, "-X needs -N <ncbi taxonomy dir> and -D <out dir>");
    Taxonomy oldtax(small_dir + "/taxo.k2d", false);
    NCBITaxonomy ncbi(ncbi_dir + "/nodes.dmp", ncbi_dir + "/names.dmp");
    for (uint64_t i = 1; i < oldtax.node_count(); i++) ncbi.MarkNode(oldtax.nodes()[i].external_id);
    { std::ifstream xf(extra_file); uint64_t x; while (xf >> x) ncbi.MarkNode(x); }
    stax_path = out_dir + "/taxo.k2d";
    ncbi.ConvertToKrakenTaxonomy(stax_path.c_str());
    taxonomy_extended = true;
  }
  Taxonomy stax(stax_path, false);
  Taxonomy ttax(teach_dir + "/taxo.k2d", true);
  stax.GenerateExternalToInternalIDMap();
  ttax.GenerateExternalToInternalIDMap();
  // a table loaded from file never initialises its zone locks (classify only reads), and
  // CompareAndSet takes them: on uninitialised stack memory that deadlocks. calloc + placement new
  // keeps them zero, which is a valid unlocked omp_lock_t.
  void *sm = calloc(1, sizeof(CompactHashTable));
  CompactHashTable &student = *new (sm) CompactHashTable(small_dir + "/hash.k2d", false);
  CompactHashTable teacher(teach_dir + "/hash.k2d", true);    // mmap, read only
  std::cerr << "student: capacity " << student.capacity() << " keys " << student.size()
            << " occupancy " << student.occupancy() << " nodes " << stax.node_count() << "\n";

  // T is the table the transplant writes into. default: the loaded student itself (same capacity).
  // with -g: rebuild the student's content from its own genomes into a table of any capacity
  // (positions depend on capacity, so cells cannot be copied across; regenerating the keys is
  // exact), and check the rebuild against the original before trusting it.
  CompactHashTable *T = &student;
  MinimizerScanner gscan(so.k, so.l, so.spaced_seed_mask, so.dna_db, so.toggle_mask, so.revcom_version);
  if (!genomes.empty()) {
    if (map_file.empty() || !new_capacity) errx(1, "-g needs -m seqid2taxid.map and -c capacity");
    std::unordered_map<string, uint64_t> seq2tax;
    { std::ifstream mf(map_file); string sid; uint64_t tid; while (mf >> sid >> tid) seq2tax[sid] = tid; }
    size_t vbits = student.value_bits(), kbits = student.key_bits();
    if (taxonomy_extended) { vbits = 1; while ((1u << vbits) < stax.node_count()) vbits++; kbits = 32 - vbits; }
    T = new CompactHashTable(new_capacity, kbits, vbits);
    std::cerr << "new table: key bits " << kbits << ", value bits " << vbits << ", taxonomy nodes " << stax.node_count() << "\n";
    auto each_seq = [&](const std::function<void(const string &, const string &)> &fn) {
      for (const string &g : genomes) {
        std::ifstream f(g); string line, id, seq;
        auto flush = [&]() { if (!id.empty()) fn(id, seq); seq.clear(); };
        while (std::getline(f, line)) {
          if (!line.empty() && line[0] == '>') {
            flush();
            id = line.substr(1, line.find_first_of(" \t") - 1);
          } else seq += line;
        }
        flush();
      }
    };
    uint64_t nseq = 0, nmiss = 0;
    each_seq([&](const string &id, const string &seq) {
      auto it = seq2tax.find(id);
      uint64_t sint = (it == seq2tax.end()) ? 0 : stax.GetInternalID(it->second);
      if (!sint) { nmiss++; return; }
      nseq++;
      gscan.LoadSequence(seq);
      uint64_t *mp;
      while ((mp = gscan.NextMinimizer()) != nullptr) {
        if (gscan.is_ambiguous()) continue;
        uint64_t cur = T->Get(*mp);
        uint64_t nv = cur ? stax.LowestCommonAncestor(cur, sint) : sint;
        if (nv != cur) { hvalue_t o = (hvalue_t) cur; T->CompareAndSet(*mp, (hvalue_t) nv, &o); }
      }
    });
    uint64_t checked = 0, bad = 0;
    if (!taxonomy_extended)
    each_seq([&](const string &id, const string &seq) {
      gscan.LoadSequence(seq);
      uint64_t *mp;
      while ((mp = gscan.NextMinimizer()) != nullptr) {
        if (gscan.is_ambiguous()) continue;
        checked++;
        if (T->Get(*mp) != student.Get(*mp)) bad++;
      }
    });
    std::cerr << "rebuild from genomes: " << nseq << " sequences (" << nmiss << " without taxid), keys "
              << T->size() << " vs original " << student.size() << ", capacity " << T->capacity()
              << ", validation: " << bad << " of " << checked << " minimizer lookups differ\n";
  }

  // allowed genera: the genus-rank nodes of the student taxonomy (optionally ESKAPE only)
  const std::set<uint64_t> eskape_genus_ext = {286, 570, 547, 469, 1279, 1350};
  std::set<uint64_t> allowed_t;   // teacher internal ids of allowed genera
  std::set<uint64_t> ancestor_t;  // teacher internal ids: family/order ancestors of allowed genera
  for (uint64_t i = 1; i < stax.node_count(); i++) {
    if (strcmp(rank_of(stax, i), "genus") != 0) continue;
    uint64_t ext = stax.nodes()[i].external_id;
    if (eskape_only && !eskape_genus_ext.count(ext)) continue;
    uint64_t ti = ttax.GetInternalID(ext);
    if (!ti) continue;
    allowed_t.insert(ti);
    for (uint64_t n = ttax.nodes()[ti].parent_id; n > 1; n = ttax.nodes()[n].parent_id) {
      const char *r = rank_of(ttax, n);
      if (!strcmp(r, "family") || !strcmp(r, "order")) ancestor_t.insert(n);
    }
  }
  std::cerr << "allowed genera: " << allowed_t.size() << ", family/order ancestors: " << ancestor_t.size() << "\n";

  auto gate = [&](uint64_t t) -> bool {
    if (ancestor_t.count(t)) return true;
    for (uint64_t n = t; n > 1; n = ttax.nodes()[n].parent_id)
      if (allowed_t.count(n)) return true;
    return false;
  };
  auto map_to_student = [&](uint64_t t) -> uint64_t {
    for (uint64_t n = t; n > 0; n = ttax.nodes()[n].parent_id) {
      uint64_t s = stax.GetInternalID(ttax.nodes()[n].external_id);
      if (s) return s;
      if (n == 1) break;
    }
    return 0;
  };

  MinimizerScanner scanner(so.k, so.l, so.spaced_seed_mask, so.dna_db, so.toggle_mask, so.revcom_version);
  std::unordered_set<uint64_t> seen;
  std::unordered_map<uint64_t, bool> gate_cache;      // teacher id -> may a NEW k-mer with this label enter?
  std::unordered_map<uint64_t, uint64_t> map_cache;   // teacher id -> nearest ancestor-or-self in student tax
  uint64_t n_reads = 0, n_min = 0, n_distinct = 0, n_absent = 0, n_gated = 0, n_same = 0,
           n_demoted = 0, n_added = 0, n_skipped_new = 0;

  // -A: genome pass. every minimizer of the student's OWN genomes is asked of the teacher and the
  // student label is generalized where the teacher says the k-mer is shared more widely. this needs
  // no reads, so the precision fix holds for any sample, not just the training pod5.
  if (genome_pass && !genomes.empty()) {
    uint64_t gp_seen = 0, gp_absent = 0, gp_changed = 0, gp_same = 0;
    std::unordered_set<uint64_t> gdone;
    for (const string &g : genomes) {
      std::ifstream f(g); string line, id, seq;
      auto run = [&]() {
        if (seq.empty()) return;
        gscan.LoadSequence(seq);
        uint64_t *mp;
        while ((mp = gscan.NextMinimizer()) != nullptr) {
          if (gscan.is_ambiguous()) continue;
          uint64_t m = *mp;
          if (!gdone.insert(m).second) continue;
          gp_seen++;
          uint64_t t = teacher.Get(m);
          if (!t) { gp_absent++; continue; }
          uint64_t old = T->Get(m);
          if (!old) continue;
          uint64_t mapped;
          auto im = map_cache.find(t);
          if (im != map_cache.end()) mapped = im->second;
          else { mapped = map_to_student(t); map_cache[t] = mapped; }
          if (!mapped) continue;
          uint64_t nv = stax.LowestCommonAncestor(old, mapped);
          if (nv == old) { gp_same++; continue; }
          hvalue_t cur = (hvalue_t) old;
          T->CompareAndSet(m, (hvalue_t) nv, &cur);
          gp_changed++;
        }
        seq.clear();
      };
      while (std::getline(f, line)) {
        if (!line.empty() && line[0] == '>') { run(); } else seq += line;
      }
      run();
    }
    std::cerr << "genome pass: " << gp_seen << " distinct genome minimizers, " << gp_changed
              << " generalized, " << gp_same << " already equal, " << gp_absent << " absent in teacher\n";
  }

  for (const string &fn : reads) {
    BatchSequenceReader r(fn.c_str());
    while (r.LoadBlock((size_t) 8 * 1024 * 1024)) {
      Sequence *s;
      while ((s = r.NextSequence()) != nullptr) {
        if (max_reads >= 0 && (long) n_reads >= max_reads) goto done;
        n_reads++;
        scanner.LoadSequence(s->seq);
        uint64_t *mp;
        while ((mp = scanner.NextMinimizer()) != nullptr) {
          if (scanner.is_ambiguous()) continue;
          uint64_t m = *mp;
          n_min++;
          if (!seen.insert(m).second) continue;
          n_distinct++;
          if (so.minimum_acceptable_hash_value && MurmurHash3(m) < so.minimum_acceptable_hash_value) continue;
          uint64_t t = teacher.Get(m);
          if (!t) { n_absent++; continue; }
          uint64_t old = T->Get(m);
          // mapping (nearest ancestor-or-self present in the student taxonomy) is cached per teacher taxon
          uint64_t mapped;
          auto im = map_cache.find(t);
          if (im != map_cache.end()) mapped = im->second;
          else { mapped = map_to_student(t); map_cache[t] = mapped; }
          if (!mapped) { n_gated++; continue; }
          if (!old) {
            // the genus gate only decides whether a NEW k-mer may enter the db. an entry the
            // student already has is simply too specific if the teacher says the k-mer is shared
            // more widely, whatever rank that is (phylum, domain, ...), so it is always generalized.
            auto ig = gate_cache.find(t);
            bool ok;
            if (ig != gate_cache.end()) ok = ig->second;
            else { ok = gate(t); gate_cache[t] = ok; }
            if (!ok) { n_gated++; continue; }
            if (precision_only) { n_skipped_new++; continue; }
          }
          uint64_t nv = old ? stax.LowestCommonAncestor(old, mapped) : mapped;
          if (nv == old) { n_same++; continue; }
          hvalue_t cur = (hvalue_t) old;   // CompareAndSet compares against the cell's current value
          if (!T->CompareAndSet(m, (hvalue_t) nv, &cur)) {
            cur = (hvalue_t) T->Get(m);    // cell changed under us (cannot happen single-threaded)
            T->CompareAndSet(m, (hvalue_t) nv, &cur);
          }
          if (old) n_demoted++; else n_added++;
        }
      }
    }
  }
done:
  std::cerr << "reads " << n_reads << "  minimizers " << n_min << "  distinct " << n_distinct << "\n"
            << "  absent in teacher (errors / unseen): " << n_absent << "\n"
            << "  rejected by genus gate (non-ESKAPE):  " << n_gated << "\n"
            << "  already identical in student:         " << n_same << "\n"
            << "  existing entries generalized (LCA up):" << n_demoted << "\n"
            << "  new entries added:                    " << n_added << "\n"
            << "  new entries skipped (-P):             " << n_skipped_new << "\n"
            << "student after: keys " << T->size() << " occupancy " << T->occupancy() << "\n";
  T->WriteTable(out_hash.c_str());
  if (!out_dir.empty()) { string cmd = "cp " + small_dir + "/opts.k2d " + out_dir + "/opts.k2d"; if (system(cmd.c_str())) {} }
  return 0;
}
