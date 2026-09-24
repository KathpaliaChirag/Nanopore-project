# S11 (2026-09-24): minimizer scanner micro-optimizations (NextMinimizer +
# reverse_complement + canonical_representation were ~33% of CPU cycles on
# the 50MB db in perf). Two changes, both semantics-preserving:
#  1. std::deque<MinimizerData> -> fixed power-of-two ring buffer (same
#     clear/empty/back/pop_back/push_back/front/pop_front behaviour; no
#     chunk allocation or map indirection in the per-base hot loop).
#  2. reverse_complement: swap-bytes/swap-byte-pairs/swap-halves (3 mask
#     stages) == full byte reversal == one bswap64 instruction.
p = "mmscanner.h"
s = open(p).read()

old = "struct MinimizerData {\n  uint64_t candidate;\n  ssize_t pos;\n};\n"
new = old + '''
// S11: fixed-capacity ring used as the sliding-window-minimum queue.
// Max live entries = window (k-l+1) + 1 (push happens before expiry pop).
struct MinimizerRing {
  static const size_t CAP = 256;      // power of two
  static const size_t MASK = CAP - 1;
  MinimizerData buf[CAP];
  size_t head = 0;   // index of front
  size_t n = 0;      // live entries
  inline void clear() { head = 0; n = 0; }
  inline bool empty() const { return n == 0; }
  inline size_t size() const { return n; }
  inline MinimizerData &front() { return buf[head & MASK]; }
  inline MinimizerData &back() { return buf[(head + n - 1) & MASK]; }
  inline void pop_front() { head++; n--; }
  inline void pop_back() { n--; }
  inline void push_back(const MinimizerData &d) { buf[(head + n) & MASK] = d; n++; }
};
'''
assert s.count(old) == 1
s = s.replace(old, new)
old = "  std::deque<MinimizerData> queue_;"
assert s.count(old) == 1
s = s.replace(old, "  MinimizerRing queue_;")
open(p, "w").write(s)

p = "mmscanner.cc"
s = open(p).read()
old = '''  // swap consecutive bytes
  kmer = ((kmer & 0xFF00FF00FF00FF00UL) >> 8)
       | ((kmer & 0x00FF00FF00FF00FFUL) << 8);
  // swap consecutive byte pairs
  kmer = ((kmer & 0xFFFF0000FFFF0000UL) >> 16)
       | ((kmer & 0x0000FFFF0000FFFFUL) << 16);
  // swap halves of 64-bit word
  kmer = ( kmer >> 32 ) | ( kmer << 32);'''
new = '''  // S11: swap bytes + swap byte pairs + swap halves == reverse byte order
  kmer = __builtin_bswap64(kmer);'''
assert s.count(old) == 1
s = s.replace(old, new)

# guard: the sliding window (k-l+1, +1 for push-before-pop) must fit the ring
old = "  queue_.clear();\n  queue_pos_ = 0;\n  loaded_ch_ = 0;\n  last_minimizer_ = ~0;"
assert s.count(old) == 1
s = s.replace(old, "  if ((k_ - l_ + 2) > (ssize_t) MinimizerRing::CAP)\n    errx(EX_SOFTWARE, \"k - l too large for minimizer ring buffer\");\n" + old)
open(p, "w").write(s)
print("S11 patched OK")
