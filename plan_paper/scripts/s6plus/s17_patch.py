# S17 (2026-09-24): portable CPU reductions (help every machine, esp. few-core ones).
# 1. Rolling reverse-complement in MinimizerScanner. Stock recomputes
#    reverse_complement(lmer_) (5 mask/shift stages) for every l-mer. For DNA
#    with revcom_version >= 1 the reverse complement of a sliding window can be
#    maintained incrementally: rc = (rc >> 2) | (comp(new_char) << 2*(l-1)).
#    Derivation (lmer_ has the oldest char at the top pair, newest at pair 0):
#    the version-1 revcomp puts comp(s_k) at pair k, s_0 = oldest, so sliding by
#    one drops pair 0 (oldest) and inserts comp(new) at pair l-1. Legacy
#    revcom_version 0 and protein DBs keep the stock path.
# 2. FastMod (S12) falls back to plain % when the compiler has no __int128.
p = "mmscanner.h"
s = open(p).read()
old = "  uint64_t lmer_;\n"
assert s.count(old) == 1
s = s.replace(old, old + "  uint64_t rc_lmer_ = 0;  // S17: rolling reverse complement of lmer_ (DNA, revcom v>=1)\n")
open(p, "w").write(s)

p = "mmscanner.cc"
s = open(p).read()
old = '''      if (lookup_code == UINT8_MAX) {
        queue_.clear();
        queue_pos_ = 0;
        lmer_ = 0;
        loaded_ch_ = 0;
        last_ambig_ |= ambig_code;
      }
      else
        lmer_ |= lookup_code;'''
new = '''      if (lookup_code == UINT8_MAX) {
        queue_.clear();
        queue_pos_ = 0;
        lmer_ = 0;
        rc_lmer_ = 0;
        loaded_ch_ = 0;
        last_ambig_ |= ambig_code;
      }
      else {
        lmer_ |= lookup_code;
        if (dna_)   // S17: comp(code) = 3 - code = ~code & 3 for 2-bit DNA codes
          rc_lmer_ = (rc_lmer_ >> 2) | ((uint64_t) ((~lookup_code) & 3u) << (2 * (l_ - 1)));
      }'''
assert s.count(old) == 1
s = s.replace(old, new)

old = "    uint64_t canonical_lmer = dna_ ? canonical_representation(lmer_, l_) : lmer_;"
new = '''    uint64_t canonical_lmer;
    if (dna_ && revcom_version_ != 0)
      canonical_lmer = lmer_ < rc_lmer_ ? lmer_ : rc_lmer_;   // S17: rolling revcomp
    else
      canonical_lmer = dna_ ? canonical_representation(lmer_, l_) : lmer_;'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, "w").write(s)

p = "compact_hash.h"
s = open(p).read()
old = '''    if (__builtin_expect(cap_recip_ == 0, 0)) return hc % capacity_;
    uint64_t q = (uint64_t) (((unsigned __int128) hc * cap_recip_) >> 64);
    uint64_t r = hc - q * capacity_;
    return r >= capacity_ ? r - capacity_ : r;
  }
  void InitRecip() {
    cap_recip_ = capacity_ > 1 ? (uint64_t) ((((unsigned __int128) 1) << 64) / capacity_) : 0;
  }'''
new = '''#ifdef __SIZEOF_INT128__
    if (__builtin_expect(cap_recip_ == 0, 0)) return hc % capacity_;
    uint64_t q = (uint64_t) (((unsigned __int128) hc * cap_recip_) >> 64);
    uint64_t r = hc - q * capacity_;
    return r >= capacity_ ? r - capacity_ : r;
#else
    return hc % capacity_;   // no 128-bit integers on this compiler/target
#endif
  }
  void InitRecip() {
#ifdef __SIZEOF_INT128__
    cap_recip_ = capacity_ > 1 ? (uint64_t) ((((unsigned __int128) 1) << 64) / capacity_) : 0;
#else
    cap_recip_ = 0;
#endif
  }'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, "w").write(s)
print("S17 patched OK")
