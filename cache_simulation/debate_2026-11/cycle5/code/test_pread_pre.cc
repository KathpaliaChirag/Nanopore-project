// unit test for the K2_PREAD lock-free chunk reader: new (pread partition + strict parser) vs old (kseq via BatchSequenceReader).
// build: g++ -O2 -std=c++17 -I src test_pread.cc -o test_pread -pthread     (run from ~/e1/impl_pread; use nice -n 10)
#include "seqreader.h"
#include <thread>
#include <functional>
#include <atomic>
#include <random>
#include <sys/stat.h>

using namespace kraken2;

struct R { std::string h, c, s, q; int fmt; };
static long g_pass = 0, g_fail = 0, g_reject = 0, g_bad_ok = 0, g_fallback = 0, g_exact_damaged = 0;
static std::string g_dir = "/tmp/pread_test_dir";

static uint64_t fnv(uint64_t h, const std::string &s, char sep) {
  for (unsigned char ch : s) { h ^= ch; h *= 1099511628211ULL; }
  h ^= (unsigned char)sep; h *= 1099511628211ULL;
  return h;
}
static uint64_t rec_hash(const Sequence &s, bool skipq) {
  uint64_t h = 1469598103934665603ULL;
  h = fnv(h, s.header, 1); h = fnv(h, s.comment, 2); h = fnv(h, s.seq, 3);
  h ^= (uint64_t)s.format; h *= 1099511628211ULL;
  if (s.format == SequenceFormat::FORMAT_FASTQ && !skipq) h = fnv(h, s.quals, 4);
  return h;
}
static R to_r(const Sequence &s, bool skipq) {
  R r; r.h = s.header; r.c = s.comment; r.s = s.seq; r.fmt = (int)s.format;
  if (s.format == SequenceFormat::FORMAT_FASTQ && !skipq) r.q = s.quals;
  return r;
}

struct Out { std::vector<uint64_t> hashes; std::vector<R> full; uint64_t n = 0; uint64_t chain = 0; };

static void add(Out &o, const Sequence &s, bool skipq, bool full) {
  uint64_t h = rec_hash(s, skipq);
  o.hashes.push_back(h);
  if (full) o.full.push_back(to_r(s, skipq));
}

// reference: the old kseq path (all files as one logical stream, exactly as ProcessFiles does)
static Out ref_read(const std::vector<std::string> &files, bool skipq, bool full) {
  k2_skip_qual() = skipq ? 1 : 0;
  Out o;
  BatchSequenceReader r(files[0].c_str());
  for (size_t i = 1; i < files.size(); i++) r.AppendFile(files[i]);
  // models a surviving thread: stock's LoadBlock returns false after a -2 at a block start, but with several threads the next
  // LoadBlock call resumes the stream (kseq resyncs). stop only after two consecutive false returns.
  int falses = 0;
  while (falses < 2) {
    if (!r.LoadBlock((size_t)1 << 40)) { falses++; continue; }
    falses = 0;
    while (Sequence *s = r.NextSequence()) add(o, *s, skipq, full);
  }
  return o;
}

// a sink that is not NullSink, so process_chunk runs the full (non-CHECK) record parse; tail() accepts like NullSink
struct CountSink { uint64_t n = 0; void begin() {} void add(const k2pread::Rec &r) { n += r.sl + r.nl + r.cl + r.ql; } void tail(const char *, size_t) {} };
static long g_variant_cmp = 0;

// new path. status: 0 ok, 1 plan rejected, 2 a chunk reported BAD (runtime guard), 3 pre-pass found damage (fallback to the kseq path)
static Out new_read(const std::vector<std::string> &files, uint64_t B, bool skipq, int nthreads, bool full, int &status, std::string &why) {
  k2_skip_qual() = skipq ? 1 : 0;
  Out o; status = 0;
  k2pread::Plan plan;
  if (!plan.Init(files, B, why)) { status = 1; return o; }
  // pre-pass exactly like classify.cc: NullSink over every chunk; any non-OK means the run would use the stock kseq path (safe fallback)
  {
    std::vector<char> pbuf; k2pread::NullSink ns; CountSink cs;
    bool anybad = false; std::string firstwhy;
    for (uint64_t pt = 0; pt < plan.total; pt++) {
      size_t pf; uint64_t pk; std::string e0, e1, e2, e3;
      plan.Locate(pt, pf, pk);
      // I6: the baseline (pread + NullSink, CHECK parse) must give the same per-chunk verdict as the full parse (CountSink,
      // non-CHECK) and as the mmap reader with and without MAP_POPULATE
      int r0 = k2pread::read_chunk(plan.fds[pf], plan.sizes[pf], pk, plan.B, pbuf, ns, &e0);
      int r1 = k2pread::read_chunk(plan.fds[pf], plan.sizes[pf], pk, plan.B, pbuf, cs, &e1);
      int r2 = k2pread::read_chunk_mm(plan.fds[pf], plan.sizes[pf], pk, plan.B, pbuf, ns, &e2, true);
      int r3 = k2pread::read_chunk_mm(plan.fds[pf], plan.sizes[pf], pk, plan.B, pbuf, ns, &e3, false);
      g_variant_cmp += 3;
      if (r0 != r1 || r0 != r2 || r0 != r3) { g_fail++; fprintf(stderr, "  FAIL prescan variants differ at chunk %llu: pread/null=%d pread/full=%d mm=%d mm_nopop=%d\n", (unsigned long long) pt, r0, r1, r2, r3); }
      if (r0 != k2pread::PR_OK && !anybad) { anybad = true; firstwhy = e0; }
    }
    // the worker (used by classify.cc, inline with OpenMP threads or overlapped with std::threads) must agree on the overall verdict
    for (int cfg = 0; cfg < 4; cfg++) {
      uint64_t ticket = 0; int bad = 0;
      bool mm = (cfg & 1) != 0; int nt = (cfg & 2) ? 4 : 1;
      std::vector<std::thread> ws;
      for (int i = 1; i < nt; i++) ws.emplace_back(k2pread::prescan_worker, std::cref(plan), &ticket, &bad, mm, true, false);
      k2pread::prescan_worker(plan, &ticket, &bad, mm, true, false);
      for (auto &w : ws) w.join();
      g_variant_cmp++;
      if ((bad != 0) != anybad) { g_fail++; fprintf(stderr, "  FAIL prescan_worker cfg %d verdict %d vs baseline %d\n", cfg, bad, (int) anybad); }
    }
    if (anybad) { status = 3; why = firstwhy; return o; }
  }
  uint64_t total = plan.total;
  std::vector<std::vector<uint64_t>> th(total);
  std::vector<std::vector<R>> tf(total);
  std::atomic<uint64_t> next(0);
  std::atomic<int> bad(0);
  std::string badwhy;
  BatchSequenceReader base(files[0].c_str());
  auto worker = [&]() {
    BatchSequenceReader rd(base);
    for (;;) {
      uint64_t t = next.fetch_add(1);
      if (t >= total) break;
      std::string err;
      if (!rd.LoadPreadTry(plan, t, err)) { bad = 1; badwhy = err; continue; }
      while (Sequence *s = rd.NextSequence()) {
        th[t].push_back(rec_hash(*s, skipq));
        if (full) tf[t].push_back(to_r(*s, skipq));
      }
    }
  };
  std::vector<std::thread> ts;
  for (int i = 0; i < nthreads; i++) ts.emplace_back(worker);
  for (auto &t : ts) t.join();
  if (bad) { status = 2; why = badwhy; return o; }
  for (uint64_t t = 0; t < total; t++) {
    for (uint64_t h : th[t]) o.hashes.push_back(h);
    if (full) for (auto &r : tf[t]) o.full.push_back(r);
  }
  return o;
}

static void report_diff(const Out &a, const Out &b, const std::string &name) {
  size_t n = std::min(a.hashes.size(), b.hashes.size());
  size_t i = 0;
  while (i < n && a.hashes[i] == b.hashes[i]) i++;
  fprintf(stderr, "  FAIL %s: ref %zu records, new %zu records, first difference at index %zu\n", name.c_str(), a.hashes.size(), b.hashes.size(), i);
  if (i < a.full.size() && i < b.full.size()) {
    const R &x = a.full[i], &y = b.full[i];
    fprintf(stderr, "    ref h=[%s] c=[%s] s=[%.60s] q=[%.30s] fmt=%d\n    new h=[%s] c=[%s] s=[%.60s] q=[%.30s] fmt=%d\n",
            x.h.c_str(), x.c.c_str(), x.s.c_str(), x.q.c_str(), x.fmt, y.h.c_str(), y.c.c_str(), y.s.c_str(), y.q.c_str(), y.fmt);
  }
}

// must_equal: the plan must be accepted and the result identical.
// !must_equal (damaged input): any of "plan rejected", "guard fired" or "identical" is safe; "ok but different" is a failure.
static void check(const std::vector<std::string> &files, uint64_t B, bool skipq, int nthreads, bool full, bool must_equal, const std::string &name) {
  Out ref = ref_read(files, skipq, full);
  int st; std::string why;
  Out nw = new_read(files, B, skipq, nthreads, full, st, why);
  if (st != 0) {
    if (must_equal) { g_fail++; fprintf(stderr, "  FAIL %s (B=%llu): expected acceptance, got status %d: %s\n", name.c_str(), (unsigned long long)B, st, why.c_str()); }
    else { g_pass++; if (st == 1) g_reject++; else if (st == 3) g_fallback++; else g_bad_ok++; }
    return;
  }
  if (ref.hashes == nw.hashes) g_pass++;
  else { g_fail++; report_diff(ref, nw, name + " B=" + std::to_string(B) + " skipq=" + std::to_string(skipq)); }
}

static void write_file(const std::string &path, const std::string &data) {
  FILE *f = fopen(path.c_str(), "wb"); if (!f) { perror(path.c_str()); abort(); }
  fwrite(data.data(), 1, data.size(), f); fclose(f);
}
static std::string read_file(const std::string &path) {
  FILE *f = fopen(path.c_str(), "rb"); std::string d; char b[65536]; size_t n;
  while ((n = fread(b, 1, sizeof b, f)) > 0) d.append(b, n);
  fclose(f); return d;
}

static std::mt19937_64 rng(getenv("TEST_SEED") ? strtoull(getenv("TEST_SEED"), nullptr, 10) : 12345);
static int rnd(int a, int b) { return (int)(a + rng() % (uint64_t)(b - a + 1)); }

struct GenOpt { bool crlf = false; bool no_final_nl = false; bool tricky_qual = true; bool allow_empty = true; int maxlen = 300; int longread = 0; };

static std::string gen_fastq(int nrec, const GenOpt &o, int idbase = 0) {
  std::string out;
  const char *nl = o.crlf ? "\r\n" : "\n";
  for (int i = 0; i < nrec; i++) {
    std::string name = "read" + std::to_string(idbase + i) + "_" + std::to_string(rng() % 100000);
    std::string comment;
    int cm = rnd(0, 6);
    std::string hdr = "@" + name;
    if (cm == 0) hdr += " runid=abc ch=" + std::to_string(rnd(1, 512)) + " start_time=2026";
    else if (cm == 1) hdr += "\tt=1 u=2";
    else if (cm == 2) hdr += "  two spaces";
    else if (cm == 3) hdr += " ";
    else if (cm == 4) hdr += " @weird +comment";
    int len;
    int lm = rnd(0, 99);
    if (o.allow_empty && lm < 4) len = 0; else if (lm < 8) len = 1; else if (lm < 10) len = 2; else len = rnd(3, o.maxlen);
    if (o.longread && i == nrec / 2) len = o.longread;
    std::string seq(len, 'A'), qual(len, 'I');
    for (int j = 0; j < len; j++) { seq[j] = "ACGTN"[rng() % 5]; qual[j] = (char)rnd('!', 'I'); }
    if (o.tricky_qual && len > 0) {
      int qm = rnd(0, 9);
      if (qm == 0) qual[0] = '@';
      else if (qm == 1) std::fill(qual.begin(), qual.end(), '@');
      else if (qm == 2) qual[0] = '+';
      else if (qm == 3 && len > 1) { qual[0] = '@'; qual[1] = '@'; }
      else if (qm == 4) qual[len - 1] = '@';
    }
    out += hdr + nl + seq + nl + "+" + nl + qual + nl;
  }
  if (o.no_final_nl) {
    // drop the final line terminator (only meaningful when the last quality line is non-empty)
    if (o.crlf && out.size() >= 2) out.resize(out.size() - 2); else if (!out.empty()) out.resize(out.size() - 1);
  }
  return out;
}

static std::string tp(const std::string &n) { return g_dir + "/" + n; }

int main(int argc, char **argv) {
  setvbuf(stdout, nullptr, _IOLBF, 0);
  mkdir(g_dir.c_str(), 0777);
  std::string realdir = "/home/student/chirag_K/results/per_pod5_fastq/";
  bool do_real = !(argc > 1 && std::string(argv[1]) == "noreal");

  // 1. synthetic edge files, chunk size sweep B = 1..260 (hits record start, mid header, on newline, in quality) plus larger sizes
  std::vector<std::pair<std::string, std::string>> edge;
  { GenOpt o; edge.push_back({"lf", gen_fastq(14, o)}); }
  { GenOpt o; o.crlf = true; edge.push_back({"crlf", gen_fastq(14, o)}); }
  { GenOpt o; o.no_final_nl = true; o.allow_empty = false; edge.push_back({"lf_nofinalnl", gen_fastq(12, o)}); }
  { GenOpt o; o.crlf = true; o.no_final_nl = true; o.allow_empty = false; edge.push_back({"crlf_nofinalnl", gen_fastq(12, o)}); }
  { GenOpt o; o.maxlen = 12; edge.push_back({"short", gen_fastq(30, o)}); }
  edge.push_back({"empty_read_only", "@r\n\n+\n\n"});
  edge.push_back({"empty_read_nofinal_qual", "@a\nACGT\n+\nIIII\n@r\n\n+\n"});
  edge.push_back({"empty_read_crlf", "@r\r\n\r\n+\r\n\r\n@s\r\nA\r\n+\r\nI\r\n"});
  edge.push_back({"one_record", "@only desc\nACGT\n+\nIIII\n"});
  edge.push_back({"at_at_qual", "@a\nACGT\n+\n@@@@\n@b\nAC\n+\n@I\n@c\nA\n+\n@\n"});
  edge.push_back({"plus_name", "@a\nACGT\n+a\nIIII\n@b\nAC\n+b desc\nII\n"});
  edge.push_back({"header_comment_cr", "@id \r\nAC\r\n+\r\nII\r\n@id2\r\nAC\r\n+\r\nII\r\n"});
  edge.push_back({"trailing_blank_lines", "@a\nACGT\n+\nIIII\n@b\nAC\n+\nII\n\n\n"});
  { GenOpt o; o.maxlen = 40; edge.push_back({"lf_many", gen_fastq(200, o)}); }
  // a 5 MB read between normal reads
  { GenOpt o; o.longread = 5 * 1000 * 1000; o.allow_empty = true; edge.push_back({"read_5MB", gen_fastq(5, o)}); }
  // 3 MB file with many reads so chunk sizes of 1 MiB / 4 MiB / 64 KiB see many boundaries
  { GenOpt o; o.maxlen = 6000; edge.push_back({"mid_3MB", gen_fastq(900, o)}); }

  std::vector<uint64_t> Bs_small;
  for (uint64_t b = 1; b <= 260; b++) Bs_small.push_back(b);
  std::vector<uint64_t> Bs_big = {1024, 4096, 65536, 1u << 20, 4u << 20};

  printf("[1] synthetic edge files\n");
  for (auto &e : edge) {
    std::string path = tp(e.first + ".fastq");
    write_file(path, e.second);
    bool small = e.second.size() < 20000;
    for (int skipq = 0; skipq <= 1; skipq++) {
      if (small) {
        for (uint64_t B : Bs_small) check({path}, B, skipq, 1 + (B & 1), true, true, e.first);
      }
      for (uint64_t B : Bs_big) {
        if (e.second.size() > 4000000 && B < 65536) continue;   // 5 MB read at 1 KiB chunks: fine but slow, skip
        check({path}, B, skipq, 2, e.second.size() < 4000000, true, e.first);
      }
    }
  }
  printf("    after [1]: pass=%ld fail=%ld\n", g_pass, g_fail);

  // 2. multi-file concatenation (one logical stream), including an empty file and a file without a final newline
  printf("[2] multi-file concatenation\n");
  {
    std::vector<std::string> files;
    std::vector<std::string> names = {"lf", "empty_file", "crlf", "lf_nofinalnl", "one_record", "crlf_nofinalnl", "empty_read_crlf", "short"};
    write_file(tp("empty_file.fastq"), "");
    for (auto &n : names) files.push_back(tp(n + ".fastq"));
    for (int skipq = 0; skipq <= 1; skipq++)
      for (uint64_t B : {1ull, 2ull, 3ull, 7ull, 13ull, 50ull, 100ull, 333ull, 1024ull, 4096ull, 1ull << 20})
        check(files, B, skipq, 3, true, true, "multi");
    // empty file first and last
    std::vector<std::string> f2 = {tp("empty_file.fastq"), tp("lf.fastq"), tp("empty_file.fastq")};
    for (uint64_t B : {5ull, 64ull, 4096ull}) check(f2, B, 0, 2, true, true, "multi_empty_edges");
  }
  printf("    after [2]: pass=%ld fail=%ld\n", g_pass, g_fail);

  // 3. inputs the plan must reject up front (these must take the old path)
  printf("[3] up-front rejection\n");
  {
    std::vector<std::pair<std::string, std::string>> rej = {
      {"fasta", ">a\nACGT\n>b\nAC\n"},
      {"multiline", "@a\nAC\nGT\n+\nII\nII\n@b\nAC\n+\nII\n"},
      {"blank_between", "@a\nAC\n+\nII\n\n@b\nAC\n+\nII\n"},
      {"junk_first", "junk\n@a\nAC\n+\nII\n"},
      {"seq_len_mismatch", "@a\nACGT\n+\nII\n"},
      {"no_plus", "@a\nAC\nXX\nII\n"},
    };
    for (auto &r : rej) {
      std::string path = tp("rej_" + r.first + ".fastq");
      write_file(path, r.second);
      k2pread::Plan plan; std::string why;
      bool ok = plan.Init({path}, 4096, why);
      if (ok) { std::vector<char> pb; k2pread::NullSink ns; for (uint64_t pt = 0; pt < plan.total && ok; pt++) { size_t pf; uint64_t pk; std::string pe; plan.Locate(pt, pf, pk); if (k2pread::read_chunk(plan.fds[pf], plan.sizes[pf], pk, plan.B, pb, ns, &pe) != k2pread::PR_OK) ok = false; } }   // plan or pre-pass rejects
      // accepted is only legal when the damage falls in one tail chunk that is replayed through kseq: then the result must be identical
      if (!ok) g_pass++; else { for (int sq = 0; sq <= 1; sq++) check({path}, 4096, sq, 1, true, true, "rej_" + r.first); }
    }
    // not a regular file (fifo) and a missing file
    mkfifo(tp("fifo").c_str(), 0600);
    { k2pread::Plan plan; std::string why; int fd = open(tp("fifo").c_str(), O_RDWR); bool ok = plan.Init({tp("fifo")}, 4096, why); if (!ok) g_pass++; else { g_fail++; fprintf(stderr, "  FAIL: fifo accepted\n"); } if (fd >= 0) close(fd); }
    { k2pread::Plan plan; std::string why; bool ok = plan.Init({tp("does_not_exist")}, 4096, why); if (!ok) g_pass++; else { g_fail++; fprintf(stderr, "  FAIL: missing file accepted\n"); } }
    { k2pread::Plan plan; std::string why; bool ok = plan.Init({"/dev/null"}, 4096, why); if (!ok) g_pass++; else { g_fail++; fprintf(stderr, "  FAIL: /dev/null accepted\n"); } }
  }
  printf("    after [3]: pass=%ld fail=%ld\n", g_pass, g_fail);

  // 4. late damage the 1 MiB pre-scan cannot see: the runtime guard must fire (or output must still be identical), never differ silently
  printf("[4] late damage after a clean first MiB (guard test)\n");
  {
    GenOpt o; o.maxlen = 3000;
    std::string clean = gen_fastq(900, o);   // about 1.5 MB, first MiB clean
    std::vector<std::string> damage = {"multiline", "blank_line", "short_qual", "fasta_record", "junk_line"};
    for (size_t di = 0; di < damage.size(); di++) {
      std::string d = clean;
      size_t at = d.find("\n@read8", 1300000);       // a record start well past the first MiB
      if (at == std::string::npos) at = d.find("\n@", 1300000);
      at += 1;
      std::string ins;
      if (di == 0) ins = "@mlt\nAC\nGT\n+\nII\nII\n";
      else if (di == 1) ins = "\n";
      else if (di == 2) ins = "@sq\nACGT\n+\nII\n";
      else if (di == 3) ins = ">fa\nACGT\n";
      else ins = "junk junk\n";
      d.insert(at, ins);
      std::string path = tp("late_" + damage[di] + ".fastq");
      write_file(path, d);
      for (uint64_t B : {4096ull, 65536ull, 1ull << 20})
        for (int skipq = 0; skipq <= 1; skipq++) check({path}, B, skipq, 2, true, false, "late_" + damage[di]);
    }
  }
  printf("    after [4]: pass=%ld fail=%ld (guard fired or plan rejected: %ld, identical-by-luck counted as pass)\n", g_pass, g_fail, g_reject + g_bad_ok);

  // 5. random fuzz on small files: 1..3 random byte edits, random chunk size; must be rejected, guarded or identical
  printf("[5] fuzz\n");
  for (int it = 0; it < (getenv("FUZZ_N") ? atoi(getenv("FUZZ_N")) : 600); it++) {
    GenOpt o; o.crlf = rnd(0, 3) == 0; o.maxlen = rnd(5, 60);
    std::string d = gen_fastq(rnd(2, 12), o);
    int nedit = rnd(1, 3);
    for (int e = 0; e < nedit && !d.empty(); e++) {
      size_t at = rng() % d.size();
      int kind = rnd(0, 3);
      const char junk[] = {'\n', '@', '+', '\r', ' ', 'A', '>'};
      if (kind == 0) d[at] = junk[rng() % sizeof junk];
      else if (kind == 1) d.erase(at, 1);
      else if (kind == 2) d.insert(at, 1, junk[rng() % sizeof junk]);
      else d.resize(at);
    }
    std::string path = tp("fuzz.fastq");
    write_file(path, d);
    uint64_t B = (uint64_t)rnd(1, 120);
    check({path}, B, rnd(0, 1), 1, true, false, "fuzz" + std::to_string(it));
  }
  printf("    after [5]: pass=%ld fail=%ld (rejected/guarded among damaged cases: %ld)\n", g_pass, g_fail, g_reject + g_bad_ok);

  // 7. truncated and malformed input, the cycle 4 design: pre-pass fallback plus exact kseq tail replay.
  //    want = 0: pre-pass must accept and the output must be identical to the (surviving thread) kseq reference.
  //    want = 3: the pre-pass must fall back. want = -1: any safe outcome (identical, or fallback), never "ok but different".
  printf("[7] truncation and malformed input\n");
  long ex_before = g_exact_damaged, fb_before = g_fallback;
  auto check_ref = [&](const Out &ref, const std::vector<std::string> &files, const std::vector<uint64_t> &Bs, bool skipq, bool full, int want, const std::string &name) {
    for (uint64_t B : Bs) {
      int st; std::string why;
      Out nw = new_read(files, B, skipq, 1 + (int)(B % 3), full, st, why);
      if (st != 0) {
        bool ok = (want == -1) || (want == 3 && st == 3);
        if (ok) { g_pass++; if (st == 3) g_fallback++; else if (st == 1) g_reject++; else g_bad_ok++; }
        else { g_fail++; fprintf(stderr, "  FAIL %s (B=%llu skipq=%d): want %d got status %d: %s\n", name.c_str(), (unsigned long long)B, (int)skipq, want, st, why.c_str()); }
        continue;
      }
      if (want == 3) { g_fail++; fprintf(stderr, "  FAIL %s (B=%llu): expected a pre-pass fallback, got an accepted run\n", name.c_str(), (unsigned long long)B); continue; }
      if (ref.hashes == nw.hashes) { g_pass++; g_exact_damaged++; }
      else { g_fail++; report_diff(ref, nw, name + " B=" + std::to_string(B) + " skipq=" + std::to_string((int)skipq)); }
    }
  };
  auto run_case = [&](const std::vector<std::string> &files, const std::vector<uint64_t> &Bs, int want, const std::string &name, bool full = true) {
    for (int skipq = 0; skipq <= 1; skipq++) {
      Out ref = ref_read(files, skipq, full);
      check_ref(ref, files, Bs, skipq, full, want, name);
    }
  };
  auto mk_rec = [&](const std::string &name, int len, char q0) {
    std::string seq(len, 'A'), qual(len, 'I');
    for (int j = 0; j < len; j++) { seq[j] = "ACGT"[rng() % 4]; qual[j] = (char)rnd('!', 'I'); }
    if (len > 0 && q0) qual[0] = q0;
    return "@" + name + " d\n" + seq + "\n+\n" + qual + "\n";
  };
  {
    // 7a. byte-by-byte truncation sweep of the last record, behind a prefix of about 1.4 MB (the cut sits after the first MiB),
    //     with chunk sizes that put the cut record across a chunk boundary and in the second-to-last chunk
    GenOpt o; o.maxlen = 3000;
    std::string prefix = gen_fastq(900, o);
    for (int variant = 0; variant < 3; variant++) {
      std::string last = variant == 0 ? mk_rec("lastrec", 100, 0) : variant == 1 ? mk_rec("lastrec", 100, '@') : mk_rec("lastrec", 100, '+');
      uint64_t P = prefix.size();
      std::vector<uint64_t> Bs = {4096, 65536, 1u << 20, 4u << 20, P + 1, P + 40, P + 120, (P + 40) / 2, (P + 120) / 2, P / 2 + 1, P / 3};
      std::string path = tp("sweep.fastq");
      for (size_t cut = 0; cut <= last.size(); cut++) {
        write_file(path, prefix + last.substr(0, cut));
        run_case({path}, Bs, 0, "sweep" + std::to_string(variant) + "_cut" + std::to_string(cut), false);
      }
    }
    printf("    after 7a (big sweep): pass=%ld fail=%ld fallbacks=%ld\n", g_pass, g_fail, g_fallback - fb_before);
    // same sweep on a tiny file so tiny chunk sizes put every byte of the cut record on a boundary
    std::string small = gen_fastq(6, o);
    for (int variant = 0; variant < 3; variant++) {
      std::string last = variant == 0 ? mk_rec("lastrec", 30, 0) : variant == 1 ? mk_rec("lastrec", 30, '@') : mk_rec("lastrec", 0, 0);
      for (size_t cut = 0; cut <= last.size(); cut++) {
        write_file(tp("sweep_small.fastq"), small + last.substr(0, cut));
        std::vector<uint64_t> Bs;
        for (uint64_t b = 1; b <= 80; b += 3) Bs.push_back(b);
        Bs.push_back(small.size() + 5); Bs.push_back(small.size() + 20); Bs.push_back(4096);
        run_case({tp("sweep_small.fastq")}, Bs, 0, "sweepsmall" + std::to_string(variant) + "_cut" + std::to_string(cut));
      }
    }
    printf("    after 7a (small sweep): pass=%ld fail=%ld\n", g_pass, g_fail);

    // 7b. truncation in file 1 of 2, in the last file, in two consecutive files, in 3 files
    GenOpt o2; o2.maxlen = 200;
    std::vector<std::string> body(3);
    for (int i = 0; i < 3; i++) body[i] = gen_fastq(40, o2, i * 1000);
    std::vector<uint64_t> Bs2 = {7, 64, 1000, 4096, 1u << 20};
    std::string lastr = mk_rec("lastrec", 60, '@');
    for (size_t cut = 0; cut <= lastr.size(); cut += 5) {
      std::string t = body[0] + lastr.substr(0, cut), c = body[1], c2 = body[2];
      std::string tt = body[1] + lastr.substr(0, lastr.size() - cut);
      write_file(tp("m_t1.fastq"), t); write_file(tp("m_c1.fastq"), c); write_file(tp("m_c2.fastq"), c2); write_file(tp("m_t2.fastq"), tt);
      std::string nm = "multi_cut" + std::to_string(cut);
      run_case({tp("m_t1.fastq"), tp("m_c1.fastq")}, Bs2, 0, nm + "_trunc_in_file1_of2");
      run_case({tp("m_c1.fastq"), tp("m_t1.fastq")}, Bs2, 0, nm + "_trunc_in_last_file");
      run_case({tp("m_t1.fastq"), tp("m_t2.fastq")}, Bs2, 0, nm + "_two_consecutive");
      run_case({tp("m_t1.fastq"), tp("m_t2.fastq"), tp("m_c2.fastq")}, Bs2, 0, nm + "_two_then_clean");
      run_case({tp("m_c1.fastq"), tp("m_t1.fastq"), tp("m_t2.fastq")}, Bs2, 0, nm + "_clean_then_two");
    }
    // big files: the truncated file is well past the first MiB, cut record after the sequence line, after '+', mid quality
    for (int variant = 0; variant < 3; variant++) {
      std::string l = mk_rec("lastrec", 80, 0);
      size_t nl1 = l.find('\n'), nl2 = l.find('\n', nl1 + 1), nl3 = l.find('\n', nl2 + 1);
      size_t cut = variant == 0 ? nl2 : variant == 1 ? nl3 : nl3 + 20;
      write_file(tp("mb_t1.fastq"), prefix + l.substr(0, cut)); write_file(tp("mb_c1.fastq"), prefix); write_file(tp("mb_t2.fastq"), prefix + l.substr(0, cut));
      run_case({tp("mb_t1.fastq"), tp("mb_c1.fastq")}, {4096, 65536, 1u << 20}, 0, "bigmulti_t1_c1_v" + std::to_string(variant), false);
      run_case({tp("mb_c1.fastq"), tp("mb_t1.fastq")}, {4096, 65536, 1u << 20}, 0, "bigmulti_c1_t1_v" + std::to_string(variant), false);
      run_case({tp("mb_t1.fastq"), tp("mb_t2.fastq"), tp("mb_c1.fastq")}, {65536, 1u << 20}, 0, "bigmulti_t_t_c_v" + std::to_string(variant), false);
    }
    printf("    after 7b (multi-file): pass=%ld fail=%ld\n", g_pass, g_fail);

    // 7c. mid-file damage after the first MiB: short and long quality, junk line, extra record. the pre-pass must fall back when
    //     chunks are small (later strict records exist); with one big chunk the damage is a tail and replays exactly
    write_file(tp("mb_c1.fastq"), prefix);
    for (int kind = 0; kind < 4; kind++) {
      std::string d = prefix;
      size_t at = d.find("\n@read8", 1300000); if (at == std::string::npos) at = d.find("\n@", 1300000);
      at += 1;
      size_t q = at; for (int i = 0; i < 3; i++) q = d.find('\n', q) + 1;   // start of that record's quality line
      size_t qe = d.find('\n', q);
      if (kind == 0) d.erase(qe - 5, 5);
      else if (kind == 1) d.insert(qe, "IIIII");
      else if (kind == 2) d.insert(at, "junk junk\n");
      else d.insert(at, "@dup\nACGT\n+\nIIIII\n");
      write_file(tp("damage_big.fastq"), d);
      std::string nm = "damage_big_kind" + std::to_string(kind);
      run_case({tp("damage_big.fastq")}, {4096, 65536}, 3, nm, false);
      run_case({tp("damage_big.fastq")}, {1u << 20, 4u << 20}, -1, nm + "_bigchunk", false);
      run_case({tp("damage_big.fastq"), tp("mb_c1.fastq")}, {65536, 1u << 20}, -1, nm + "_file1of2", false);
      run_case({tp("mb_c1.fastq"), tp("damage_big.fastq")}, {65536, 1u << 20}, -1, nm + "_lastfile", false);
      // two damages: one mid-file and one truncated tail
      write_file(tp("damage_two.fastq"), d + mk_rec("lastrec", 100, 0).substr(0, 150));
      run_case({tp("damage_two.fastq")}, {4096, 65536}, 3, nm + "_plus_tail", false);
      run_case({tp("damage_two.fastq")}, {1u << 20}, -1, nm + "_plus_tail_bigchunk", false);
    }
    // 7d. small files: '@' or '+' as the first quality byte of every record, one damaged record in the middle, resync lands on '@'
    for (int qc = 0; qc < 2; qc++) {
      char q0 = qc == 0 ? '@' : '+';
      for (int kind = 0; kind < 5; kind++) {
        std::string d;
        for (int i = 0; i < 30; i++) {
          std::string r = mk_rec("r" + std::to_string(i), 40 + i, q0);
          if (i == 12) {
            size_t e = r.size() - 1;
            if (kind == 0) r.erase(e - 5, 5);
            else if (kind == 1) r.insert(e, "IIIII");
            else if (kind == 2) { /* valid control */ }
            else if (kind == 3) r.erase(r.find("+\n"), 2);
            else r.erase(r.rfind('\n', r.size() - 2) + 1);   // drop the quality line
          }
          d += r;
        }
        write_file(tp("dmg_small.fastq"), d);
        std::vector<uint64_t> Bs; for (uint64_t b = 1; b <= 200; b += 7) Bs.push_back(b); Bs.push_back(4096); Bs.push_back(1u << 20);
        run_case({tp("dmg_small.fastq")}, Bs, -1, std::string("dmg_small_q0_") + q0 + "_kind" + std::to_string(kind));
        write_file(tp("dmg_small2.fastq"), d + mk_rec("tailrec", 50, q0).substr(0, 70));
        run_case({tp("dmg_small2.fastq")}, Bs, -1, std::string("dmg_small_tail_q0_") + q0 + "_kind" + std::to_string(kind));
      }
    }
    printf("    after 7c/7d (mid-file damage): pass=%ld fail=%ld\n", g_pass, g_fail);
  }
  printf("    [7] total: runs accepted by the pre-pass and identical on damaged input=%ld, pre-pass fallbacks=%ld\n", g_exact_damaged - ex_before, g_fallback - fb_before);

  // 6. real data: first 3 files of per_pod5_fastq, hash chain comparison, 2 threads
  if (do_real) {
    printf("[6] real data (first 3 files of per_pod5_fastq)\n");
    std::vector<std::string> f3 = {realdir + "pod5_0.fastq", realdir + "pod5_1.fastq", realdir + "pod5_2.fastq"};
    struct stat st;
    if (stat(f3[0].c_str(), &st) != 0) { printf("    real files missing, skipped\n"); }
    else {
      check({f3[0]}, 4u << 20, 0, 2, false, true, "real_file0_quals_4MiB");          // with quality copy
      check(f3, 4u << 20, 1, 2, false, true, "real_3files_skipq_4MiB");
      check({f3[1]}, 64 * 1024, 1, 2, false, true, "real_file1_skipq_64KiB");
      check({f3[2]}, 1000003, 1, 2, false, true, "real_file2_skipq_1000003");        // odd chunk size
      check({f3[0], f3[1]}, 1u << 20, 0, 2, false, true, "real_2files_quals_1MiB");
    }
    printf("    after [6]: pass=%ld fail=%ld\n", g_pass, g_fail);
  }

  printf("TOTAL cases passed=%ld failed=%ld  (damaged-input cases that were rejected up front=%ld, caught by the runtime guard=%ld, pre-pass fallbacks=%ld)\n", g_pass, g_fail, g_reject, g_bad_ok, g_fallback);
  printf("prescan variant comparisons (pread/CHECK vs full parse vs mmap vs mmap-no-populate, plus worker verdicts): %ld\n", g_variant_cmp);
  printf(g_fail == 0 ? "PASS\n" : "FAIL\n");
  return g_fail == 0 ? 0 : 1;
}
