# S14 (2026-09-24): transparent huge pages for the hash table.
# S13 on the 103GB db: sys=220s of 675 CPU-s (27M 4KB page faults during load)
# and every random lookup pays a TLB miss + page walk. Kernel THP mode is
# "madvise" and AnonHugePages was 0, i.e. nothing was using huge pages.
# Fix: allocate the table 2MB-aligned with posix_memalign and madvise
# MADV_HUGEPAGE. Falls back to plain new[] if that fails. Table contents are
# unchanged, so output is identical.
p = "compact_hash.h"
s = open(p).read()
old = "  bool file_backed_;\n"
assert s.count(old) == 1
s = s.replace(old, old + "  bool huge_alloc_ = false;  // S14: table_ came from posix_memalign\n")
open(p, "w").write(s)

p = "compact_hash.cc"
s = open(p).read()
s = s.replace('#include "compact_hash.h"\n', '#include "compact_hash.h"\n#include <sys/mman.h>\n#include <stdlib.h>\n', 1)

old = "  if (! file_backed_)\n    delete[] table_;"
assert s.count(old) == 1
s = s.replace(old, "  if (! file_backed_) {\n    if (huge_alloc_) free(table_);\n    else delete[] table_;\n  }")

old = '''    try {
      table_ = new CompactHashCell[capacity_];
    } catch (std::bad_alloc &ex) {
      std::cerr << "Failed attempt to allocate " << (sizeof(*table_) * capacity_) << "bytes;\\n"
                << "you may not have enough free memory to load this database.\\n"'''
new = '''    try {
      size_t tbytes = capacity_ * sizeof(*table_);
      void *hp = nullptr;
      if (tbytes >= ((size_t) 2 << 20) && posix_memalign(&hp, (size_t) 2 << 20, tbytes) == 0) {
        madvise(hp, tbytes, MADV_HUGEPAGE);
        table_ = (CompactHashCell *) hp;
        huge_alloc_ = true;
      } else {
        table_ = new CompactHashCell[capacity_];
      }
    } catch (std::bad_alloc &ex) {
      std::cerr << "Failed attempt to allocate " << (sizeof(*table_) * capacity_) << "bytes;\\n"
                << "you may not have enough free memory to load this database.\\n"'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
open(p, "w").write(s)
print("S14 patched OK")
