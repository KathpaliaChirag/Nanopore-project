// mmbulk.h: scalar bulk minimizer scanner, bit-identical (value, ambiguous) stream
// to MinimizerScanner for dna, revcom_version != 0, k - l == 4 (5-slot window).
#ifndef KRAKEN2_MMBULK_H_
#define KRAKEN2_MMBULK_H_

#include <cstdint>
#include <cstddef>

namespace kraken2 {

struct BulkParams {
  int64_t k, l;
  uint64_t LM, SM, TG;   // l-mer mask, spaced seed (or ~0), toggle & LM
  unsigned SH;           // 2*(l-1)
};

struct BulkState {
  uint64_t lm, rc, run;
  uint64_t c1, c2, c3, c4;   // ce_{t-1} .. ce_{t-4}
  uint64_t p1, p2;           // pair mins p_{t-1}, p_{t-2}
  uint64_t stale;
  size_t i;                  // next char index
  void init() {
    lm = rc = run = 0;
    c1 = c2 = c3 = c4 = p1 = p2 = ~0ull;
    stale = ~0ull;
    i = 0;
  }
};

// true when the bulk path reproduces the old scanner exactly
inline bool BulkSupported(bool dna, int revcom_version, int64_t k, int64_t l) {
  return dna && revcom_version != 0 && k > l && (k - l) == 4 && l >= 2 && l <= 31;
}

inline void BulkInitParams(BulkParams &P, int64_t k, int64_t l,
                           uint64_t spaced_seed_mask, uint64_t toggle_mask) {
  P.k = k; P.l = l;
  P.LM = (1ull << (2 * l)) - 1;
  P.TG = toggle_mask & P.LM;
  P.SM = spaced_seed_mask ? spaced_seed_mask : ~0ull;
  P.SH = (unsigned) (2 * (l - 1));
}

struct BulkTable {
  uint8_t t[256];
  BulkTable() {
    for (int i = 0; i < 256; i++) t[i] = 0xFF;
    t[(int) 'A'] = t[(int) 'a'] = 0;
    t[(int) 'C'] = t[(int) 'c'] = 1;
    t[(int) 'G'] = t[(int) 'g'] = 2;
    t[(int) 'T'] = t[(int) 't'] = 3;
  }
};
inline const uint8_t *BulkTab() { static const BulkTable bt; return bt.t; }

#define K2_BULK_MIN(a, b) ((a) < (b) ? (a) : (b))

// Scan from st.i, writing up to max_items items (one per char from index k-1).
// Returns items written; 0 means the sequence is finished.
inline __attribute__((noinline))
size_t ScanBulk(BulkState &st, const BulkParams &P, const char *s, size_t n,
                uint64_t *mins, uint8_t *amb, size_t max_items) {
  const uint8_t *tab = BulkTab();
  const uint64_t LM = P.LM, SM = P.SM, TG = P.TG;
  const unsigned SH = P.SH;
  const uint64_t l = (uint64_t) P.l, km1 = (uint64_t) (P.k - 1);
  uint64_t lm = st.lm, rc = st.rc, run = st.run;
  uint64_t c1 = st.c1, c2 = st.c2, c3 = st.c3, c4 = st.c4, p1 = st.p1, p2 = st.p2;
  uint64_t stale = st.stale;
  size_t i = st.i, o = 0;

#define K2_BULK_STEP                                                         \
    const uint64_t code = tab[(uint8_t) s[i]];                               \
    const uint64_t keep = (code <= 3) ? ~0ull : 0ull;                        \
    const uint64_t cc = code & 3;                                            \
    lm = (((lm << 2) | cc) & LM) & keep;                                     \
    rc = ((rc >> 2) | ((3 - cc) << SH)) & keep;                              \
    const uint64_t rn = run + 1;                                             \
    run = keep & (rn < 64 ? rn : 64);                                        \
    const uint64_t cand = ((lm < rc ? lm : rc) & SM) ^ TG;                   \
    const bool valid = run >= l;                                             \
    const uint64_t ce = valid ? cand : ~0ull;                                \
    const uint64_t a1 = K2_BULK_MIN(ce, c1);                                 \
    const uint64_t m = K2_BULK_MIN(K2_BULK_MIN(a1, p2), c4);                 \
    c4 = c3; c3 = c2; c2 = c1; c1 = ce; p2 = p1; p1 = a1;

  size_t warm_end = n < km1 ? n : (size_t) km1;
  for (; i < warm_end; ++i) {
    K2_BULK_STEP
    (void) m;
  }
  size_t lim = i;
  if (i < n) {
    size_t rem = n - i;
    lim = i + (rem < max_items ? rem : max_items);
  }
  for (; i < lim; ++i) {
    K2_BULK_STEP
    const uint64_t val = valid ? (m ^ TG) : stale;
    stale = val;
    mins[o] = val;
    amb[o] = (uint8_t) (run < km1);
    o++;
  }
#undef K2_BULK_STEP
  st.lm = lm; st.rc = rc; st.run = run;
  st.c1 = c1; st.c2 = c2; st.c3 = c3; st.c4 = c4; st.p1 = p1; st.p2 = p2;
  st.stale = stale; st.i = i;
  return o;
}

}  // namespace kraken2
#endif
