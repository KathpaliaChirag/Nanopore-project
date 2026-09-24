# S19 (2026-09-24): portability guard. MADV_HUGEPAGE is Linux-only; on other
# OSes (or old headers) the huge-page hint is simply skipped and the aligned
# allocation still works, so the build never fails and behaviour is unchanged.
p = "compact_hash.cc"
s = open(p).read()
old = "        madvise(hp, tbytes, MADV_HUGEPAGE);\n"
assert s.count(old) == 1
s = s.replace(old, "#ifdef MADV_HUGEPAGE\n        madvise(hp, tbytes, MADV_HUGEPAGE);\n#endif\n")
open(p, "w").write(s)
print("S19 patched OK")
