# S18 (2026-09-24): fix a store-forwarding stall in the sliding-window minimum.
# perf annotate of S17: one `movdqa 0x20(%rsp),%xmm6` (load of the 16-byte
# MinimizerData temp that was just written as two separate 8-byte stores) is
# ~21% of NextMinimizer's samples (NextMinimizer = 43% of all cycles). A wide
# load fed by two narrow stores cannot be store-forwarded and stalls.
# S11 replaced std::deque with a ring but kept `push_back(const MinimizerData&)`
# taking a stack temp, so it hit the same stall (measured null). Here the ring
# has push(candidate, pos) that writes the two fields straight into the slot.
# Same queue semantics (clear/empty/back/pop_back/front/pop_front/push), so the
# minimizer sequence is identical.
p = "mmscanner.h"
s = open(p).read()
old = "struct MinimizerData {\n  uint64_t candidate;\n  ssize_t pos;\n};\n"
assert s.count(old) == 1
s = s.replace(old, old + '''
// S18: fixed-capacity ring for the sliding-window-minimum queue.
// Max live entries = window (k-l+1) + 1 (push happens before expiry pop).
struct MinimizerRing {
  static const size_t CAP = 256;      // power of two
  static const size_t MASK = CAP - 1;
  MinimizerData buf[CAP];
  size_t head = 0;   // index of front
  size_t n = 0;      // live entries
  inline void clear() { head = 0; n = 0; }
  inline bool empty() const { return n == 0; }
  inline MinimizerData &front() { return buf[head & MASK]; }
  inline MinimizerData &back() { return buf[(head + n - 1) & MASK]; }
  inline void pop_front() { head++; n--; }
  inline void pop_back() { n--; }
  inline void push(uint64_t candidate, ssize_t pos) {
    MinimizerData &d = buf[(head + n) & MASK];
    d.candidate = candidate;   // two direct field stores, no 16-byte temp
    d.pos = pos;
    n++;
  }
};
''')
old = "  std::deque<MinimizerData> queue_;"
assert s.count(old) == 1
s = s.replace(old, "  MinimizerRing queue_;")
open(p, "w").write(s)

p = "mmscanner.cc"
s = open(p).read()
old = "    MinimizerData data = { candidate_lmer, queue_pos_ };\n"
assert s.count(old) == 1
s = s.replace(old, "")
old = "    queue_.push_back(data);\n"
assert s.count(old) == 1
s = s.replace(old, "    queue_.push(candidate_lmer, queue_pos_);\n")
# guard: the sliding window (k-l+1, +1 for push-before-pop) must fit the ring
old = "  queue_.clear();\n  queue_pos_ = 0;\n  loaded_ch_ = 0;\n  last_minimizer_ = ~0;"
assert s.count(old) == 1
s = s.replace(old, "  if ((k_ - l_ + 2) > (ssize_t) MinimizerRing::CAP)\n    errx(EX_SOFTWARE, \"k - l too large for minimizer ring buffer\");\n" + old)
open(p, "w").write(s)
print("S18 patched OK")
