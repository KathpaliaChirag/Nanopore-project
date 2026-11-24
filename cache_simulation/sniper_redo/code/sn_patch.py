p = "/home/student/e1/sn/src0/src/classify.cc"
s = open(p).read()
def rep(old, new, label):
    global s
    if s.count(old) != 1:
        print("PATCH FAIL", label, s.count(old)); raise SystemExit(1)
    s = s.replace(old, new)
rep("static const size_t S2_WAYS = 4;", "#ifndef S2_WAYS_N\n#define S2_WAYS_N 4\n#endif\nstatic const size_t S2_WAYS = S2_WAYS_N;", "ways")
rep("static const size_t S3_MAX_SETS = 65536;", "#ifndef S2_SETS_N\n#define S2_SETS_N 65536\n#endif\nstatic const size_t S3_MAX_SETS = S2_SETS_N;", "maxsets")
rep("static const size_t S3_MIN_SETS = 65536;", "static const size_t S3_MIN_SETS = S2_SETS_N;", "minsets")
rep("static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {\n", "static inline bool S2Lookup(uint64_t minimizer, taxid_t *out_taxon) {\n#ifdef S2_OFF\n  return false;  // cache-off build: same source, cache never hits\n#endif\n", "off_lookup")
rep("static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {\n", "static inline void S2Insert(uint64_t minimizer, taxid_t taxon) {\n#ifdef S2_OFF\n  return;  // cache-off build: never inserts, never allocates\n#endif\n", "off_insert")
rep("ok_read = reader1.LoadBlock((size_t)(3 * 1024 * 1024));", "ok_read = reader1.LoadBlock(k2_block_bases());", "block")
helper = (
 '#include "aa_translate.h"\n'
 'static size_t k2_block_bases() {  // block size in bases: default 3 MiB (stock); K2_BLOCK overrides it so small inputs can feed several threads\n'
 '  static size_t v = 0;\n'
 '  if (v == 0) { const char *e = getenv("K2_BLOCK"); v = e ? (size_t) atoll(e) : (size_t) 3 * 1024 * 1024; if (v < 1) v = 1; fprintf(stderr, "K2 block bases = %zu\n", v); }\n'
 '  return v;\n'
 '}\n')
rep('#include "aa_translate.h"\n', helper, "blockfn")
open(p, "w").write(s); print("PATCH OK")
