// mmcmp.cc: exactness harness, old MinimizerScanner vs ScanBulk, (value, amb) streams.
// build: g++ -O2 -std=c++11 -I. -o mmcmp mmcmp.cc mmscanner.o
// usage: mmcmp opts.k2d reads.fastq [maxreads]
#include "mmscanner.h"
#include "mmbulk.h"
#include "kraken2_data.h"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>
using namespace kraken2;
using std::string; using std::vector;

struct Item { uint64_t v; uint8_t a; };
static uint64_t items_total = 0, seqs_total = 0, mism_len = 0, mism_val = 0, mism_amb = 0;
static int shown = 0;

static void run_old(MinimizerScanner &sc, const string &s, vector<Item> &out) {
  out.clear();
  sc.LoadSequence(s);
  uint64_t *p;
  while ((p = sc.NextMinimizer())) out.push_back({*p, (uint8_t) sc.is_ambiguous()});
}
static void run_new(const BulkParams &P, const string &s, size_t chunk, vector<Item> &out,
                    vector<uint64_t> &mb, vector<uint8_t> &ab) {
  out.clear();
  BulkState st; st.init();
  if (mb.size() < chunk) { mb.resize(chunk); ab.resize(chunk); }
  for (;;) {
    size_t g = ScanBulk(st, P, s.data(), s.size(), mb.data(), ab.data(), chunk);
    if (g == 0) break;
    for (size_t j = 0; j < g; j++) out.push_back({mb[j], ab[j]});
  }
}
static void compare(const string &s, const vector<Item> &o, const vector<Item> &n, size_t chunk, const char *tag) {
  seqs_total++;
  items_total += o.size();
  if (o.size() != n.size()) {
    mism_len++;
    if (shown++ < 8) printf("LEN MISMATCH tag=%s chunk=%zu n=%zu old=%zu new=%zu seq=%.80s\n", tag, chunk, s.size(), o.size(), n.size(), s.c_str());
    return;
  }
  for (size_t i = 0; i < o.size(); i++) {
    if (o[i].a != n[i].a) { mism_amb++; if (shown++ < 8) printf("AMB MISMATCH tag=%s chunk=%zu item=%zu old=%d new=%d seq=%.80s\n", tag, chunk, i, o[i].a, n[i].a, s.c_str()); }
    else if (o[i].v != n[i].v) { mism_val++; if (shown++ < 8) printf("VAL MISMATCH tag=%s chunk=%zu item=%zu amb=%d old=%llx new=%llx seq=%.80s\n", tag, chunk, i, o[i].a, (unsigned long long) o[i].v, (unsigned long long) n[i].v, s.c_str()); }
  }
}

static uint64_t rs = 88172645463325252ULL;
static uint64_t rnd() { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }
static string randseq(size_t n, double ndens, const string &alpha_amb) {
  string s(n, 'A');
  const char *ac = "ACGT";
  size_t na = alpha_amb.size();
  for (size_t i = 0; i < n; i++) {
    double u = (rnd() >> 11) * (1.0 / 9007199254740992.0);
    if (u < ndens) s[i] = alpha_amb[rnd() % na];
    else s[i] = ac[rnd() & 3];
  }
  return s;
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: mmcmp opts.k2d reads.fastq [maxreads]\n"); return 2; }
  const char *optf = argv[1];
  const char *fq = argv[2];
  size_t maxreads = argc > 3 ? atoll(argv[3]) : 20000;
  IndexOptions io = {0};
  std::ifstream f(optf, std::ios::binary);
  f.read((char *) &io, sizeof(io));
  printf("real db opts: k=%zu l=%zu spaced=%llx toggle=%llx dna=%d revcom=%d (read %ld bytes)\n", io.k, io.l,
         (unsigned long long) io.spaced_seed_mask, (unsigned long long) io.toggle_mask, (int) io.dna_db, io.revcom_version, (long) f.gcount());

  vector<string> edge;
  const string N1 = "N";
  size_t lens[] = {0, 1, 2, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 70, 71, 100, 200};
  for (size_t n : lens) {
    edge.push_back(randseq(n, 0, N1));
    edge.push_back(string(n, 'N'));
    edge.push_back(string(n, 'A'));
    edge.push_back(string(n, 'T'));
  }
  // N runs inside clean reads, run lengths 1..40 at various offsets
  for (int run = 1; run <= 40; run++) {
    for (int off : {0, 1, 20, 33, 34, 35, 36, 50, 100}) {
      string s = randseq(160, 0, N1);
      for (int j = 0; j < run && off + j < (int) s.size(); j++) s[off + j] = 'N';
      edge.push_back(s);
    }
    // clean run of exactly `run` chars between Ns
    edge.push_back("N" + randseq(run, 0, N1) + "N" + randseq(60, 0, N1));
    edge.push_back(randseq(run, 0, N1) + "N" + randseq(run, 0, N1) + "N");
  }
  // N at specific index classes
  for (size_t n : {35UL, 36UL, 40UL, 80UL}) {
    for (size_t pos : {0UL, 1UL, 29UL, 30UL, 31UL, 32UL, 33UL, 34UL, 35UL, 36UL, 37UL, 38UL, 39UL, n - 1}) {
      if (pos >= n) continue;
      string s = randseq(n, 0, N1); s[pos] = 'N'; edge.push_back(s);
    }
    string u = randseq(n, 0, N1); u[n - 31] = 'N'; edge.push_back(u);  // N exactly l chars before the end
  }
  // lowercase, mixed case
  { string s = randseq(300, 0, N1); for (auto &c : s) c = tolower(c); edge.push_back(s); }
  { string s = randseq(300, 0, N1); for (size_t i = 0; i < s.size(); i++) if (rnd() & 1) s[i] = tolower(s[i]); edge.push_back(s); }
  // IUPAC and odd chars (including NUL and tab) at several positions
  const string iu("RYKMSWBDHVNrykmswbdhvn-*.?X\t \0", 30);
  for (size_t p = 0; p < iu.size(); p++) {
    for (size_t pos : {0UL, 10UL, 33UL, 34UL, 35UL, 50UL, 99UL}) {
      string s = randseq(120, 0, N1); s[pos] = iu[p]; edge.push_back(s);
    }
  }
  // homopolymers, palindromes (revcomp equal), periodic ties
  edge.push_back(string(500, 'A')); edge.push_back(string(500, 'C')); edge.push_back(string(500, 'G')); edge.push_back(string(500, 'T'));
  edge.push_back("ACGTACGTTGCATGCAGGCCTTAAGCTAGCTAGCTAGCTTAAGGCCTGCATGCAACGTACGT");
  { string p; for (int i = 0; i < 200; i++) p += "ACGT"; edge.push_back(p); }
  { string p; for (int i = 0; i < 100; i++) p += "ACGTTGCA"; edge.push_back(p); }
  { string p; for (int i = 0; i < 40; i++) p += "AC"; edge.push_back(p); }
  { string p; for (int i = 0; i < 60; i++) p += "GGCC"; edge.push_back(p); }
  // random with N density (second half also mixes IUPAC and lowercase)
  for (double d : {0.0, 0.001, 0.01, 0.1, 0.5})
    for (int r = 0; r < 20000; r++) edge.push_back(randseq(35 + rnd() % 400, d, (r & 1) ? N1 : string("NRYKMnacgt-*")));
  // long reads (chunk joins)
  for (int r = 0; r < 30; r++) edge.push_back(randseq(20000 + rnd() % 30000, r % 3 ? 0.0005 : 0.0, N1));

  vector<string> real;
  {
    std::ifstream in(fq); string h, s, p, q;
    while (real.size() < maxreads && std::getline(in, h) && std::getline(in, s) && std::getline(in, p) && std::getline(in, q)) real.push_back(s);
  }
  printf("edge/synthetic seqs: %zu, real reads: %zu\n", edge.size(), real.size());

  struct PS { const char *name; int64_t k, l; uint64_t sp, tg; int rv; };
  vector<PS> sets = {
    {"real_db", (int64_t) io.k, (int64_t) io.l, io.spaced_seed_mask, io.toggle_mask, io.revcom_version},
    {"k35l31_mask0_defaulttoggle", 35, 31, 0, DEFAULT_TOGGLE_MASK, 1},
    {"k35l31_mask0_toggle0", 35, 31, 0, 0, 1},
    {"k35l31_spaced", 35, 31, 0x3FFFFFFFFFFFFFF0ULL, DEFAULT_TOGGLE_MASK, 1},
    {"k34l30", 34, 30, 0, DEFAULT_TOGGLE_MASK, 1},
    {"k19l15", 19, 15, 0, DEFAULT_TOGGLE_MASK, 1},
  };
  size_t chunks[] = {1, 7, 64, 4096};
  vector<Item> o, n; vector<uint64_t> mb; vector<uint8_t> ab;
  for (auto &ps : sets) {
    if (!BulkSupported(true, ps.rv, ps.k, ps.l)) { printf("set %s not bulk-supported, skipped\n", ps.name); continue; }
    uint64_t before = items_total, bm = mism_len + mism_val + mism_amb;
    MinimizerScanner sc(ps.k, ps.l, ps.sp, true, ps.tg, ps.rv);
    BulkParams P; BulkInitParams(P, ps.k, ps.l, ps.sp, ps.tg);
    for (int pass = 0; pass < 2; pass++) {
      const vector<string> &v = pass ? real : edge;
      for (size_t idx = 0; idx < v.size(); idx++) {
        const string &s = v[idx];
        run_old(sc, s, o);
        for (size_t c : chunks) {
          if (pass == 1 && c == 1 && idx % 10 != 0) continue;  // chunk 1 on every 10th real read only (speed)
          run_new(P, s, c, n, mb, ab);
          compare(s, o, n, c, ps.name);
        }
      }
    }
    printf("set %s (k=%ld l=%ld): items compared %llu, mismatches %llu\n", ps.name, (long) ps.k, (long) ps.l,
           (unsigned long long) (items_total - before), (unsigned long long) (mism_len + mism_val + mism_amb - bm));
  }
  printf("TOTAL seq-compares %llu items %llu len_mismatch %llu value_mismatch %llu amb_mismatch %llu\n",
         (unsigned long long) seqs_total, (unsigned long long) items_total, (unsigned long long) mism_len,
         (unsigned long long) mism_val, (unsigned long long) mism_amb);
  return (mism_len + mism_val + mism_amb) ? 1 : 0;
}
