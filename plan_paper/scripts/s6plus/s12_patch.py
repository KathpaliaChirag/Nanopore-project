# S12 (2026-09-24): remove the hidden 64-bit divisions from the lookup path.
# perf (S10, 50MB db): Prefetch 7.7% + GetWithHash 19% of cycles, much of it
# `hc % capacity_` (64-bit div ~30+ cycles) done TWICE per lookup (once in
# Prefetch, once in GetWithHash) plus `idx %= capacity_` on every probe step.
#  1. Index once: PrefetchIndex(hc) computes idx = hc % capacity_ with an
#     exact reciprocal-multiply (FastMod), issues the prefetch, and returns
#     idx; GetAt(key, hc, idx) reuses it. One index computation per lookup.
#  2. FastMod is exact: M = floor(2^64/d); q = mulhi(hc, M) is floor(hc/d) or
#     floor(hc/d)-1, so r = hc - q*d lies in [0, 2d) and one conditional
#     subtract gives hc % d.
#  3. Probe wrap: `idx += step; if (idx >= capacity_) idx %= capacity_;`
#     (identical result to `idx %= capacity_`, division only on actual wrap).
# Table layout and probe order are unchanged, so existing DBs and outputs are
# identical.
p = "kv_store.h"
s = open(p).read()
old = "  virtual void Prefetch(uint64_t hc) const = 0;\n"
assert s.count(old) == 1
s = s.replace(old, old + "  // S12: compute the table index once, prefetch it, return it; GetAt reuses it.\n  virtual size_t PrefetchIndex(uint64_t hc) const = 0;\n  virtual hvalue_t GetAt(hkey_t key, uint64_t hc, size_t idx) const = 0;\n")
open(p, "w").write(s)

p = "compact_hash.h"
s = open(p).read()
old = "  void Prefetch(uint64_t hc) const;\n"
assert s.count(old) == 1
s = s.replace(old, old + "  size_t PrefetchIndex(uint64_t hc) const;\n  hvalue_t GetAt(hkey_t key, uint64_t hc, size_t idx) const;\n")
old = "  size_t capacity_;\n  size_t size_;\n"
assert s.count(old) == 1
s = s.replace(old, old + "  uint64_t cap_recip_ = 0;  // S12: floor(2^64 / capacity_), for FastMod\n")
old = "  void LoadTable(const char *filename, bool memory_mapping);\n"
assert s.count(old) == 1
s = s.replace(old, old + '''  inline uint64_t FastMod(uint64_t hc) const {
    if (__builtin_expect(cap_recip_ == 0, 0)) return hc % capacity_;
    uint64_t q = (uint64_t) (((unsigned __int128) hc * cap_recip_) >> 64);
    uint64_t r = hc - q * capacity_;
    return r >= capacity_ ? r - capacity_ : r;
  }
  void InitRecip() {
    cap_recip_ = capacity_ > 1 ? (uint64_t) ((((unsigned __int128) 1) << 64) / capacity_) : 0;
  }
''')
open(p, "w").write(s)

p = "compact_hash.cc"
s = open(p).read()
# init recip at the end of both load branches: right after file_backed_ is set
old = "    file_backed_ = true;\n  }\n  else {"
assert s.count(old) == 1
s = s.replace(old, "    file_backed_ = true;\n    InitRecip();\n  }\n  else {")
old = "    file_backed_ = false;\n  }\n}\n\nvoid CompactHashTable::WriteTable"
assert s.count(old) == 1
s = s.replace(old, "    file_backed_ = false;\n    InitRecip();\n  }\n}\n\nvoid CompactHashTable::WriteTable")

old = "hvalue_t CompactHashTable::GetWithHash(hkey_t key, uint64_t hc) const {"
assert s.count(old) == 1
s = s.replace(old, '''size_t CompactHashTable::PrefetchIndex(uint64_t hc) const {
  size_t idx = FastMod(hc);
  __builtin_prefetch(&table_[idx], 0, 3);
  return idx;
}

hvalue_t CompactHashTable::GetAt(hkey_t key, uint64_t hc, size_t idx) const {
  uint64_t compacted_key = hc >> (32 + value_bits_);
  size_t first_idx = idx;
  size_t step = 0;
  while (true) {
    if (! table_[idx].value(value_bits_))
      break;
    if (table_[idx].hashed_key(value_bits_) == compacted_key)
      return table_[idx].value(value_bits_);
    if (step == 0)
      step = second_hash(hc);
    idx += step;
    if (idx >= capacity_)
      idx %= capacity_;
    if (idx == first_idx)
      break;
  }
  return 0;
}

''' + old)
open(p, "w").write(s)

p = "classify.cc"
s = open(p).read()
old = "struct PfSlot { uint64_t min; uint64_t hc; bool amb; };"
assert s.count(old) == 1
s = s.replace(old, "struct PfSlot { uint64_t min; uint64_t hc; size_t idx; bool amb; };")
old = "            hash->Prefetch(pf[n_pf].hc);"
assert s.count(old) == 1
s = s.replace(old, "            pf[n_pf].idx = hash->PrefetchIndex(pf[n_pf].hc);")
old = "                taxon = hash->GetWithHash(pf[i].min, pf[i].hc);"
assert s.count(old) == 1
s = s.replace(old, "                taxon = hash->GetAt(pf[i].min, pf[i].hc, pf[i].idx);")
open(p, "w").write(s)
print("S12 patched OK")
