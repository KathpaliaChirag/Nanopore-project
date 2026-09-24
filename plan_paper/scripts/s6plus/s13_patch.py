# S13 (2026-09-24): vectorized line scan in kseq.
# After S8/S10/S12 the serial FASTQ parser (critical(seqread)) is the wall for
# every DB <= 16GB: parse-only of the 12.5GB input is 10.53s single-threaded,
# 65% of it in ks_getuntil2's byte-at-a-time '\n' search. memchr (SIMD in
# glibc) finds the same position; everything else in the function is
# unchanged, so parsed records are identical.
import re, sys
p = "kseq.h"
s = open(p).read()
pat = re.compile(r"for \(i = ks->begin; i < ks->end; \+\+i\) \\\n\s*if \(ks->buf\[i\] == '\\n'\) break; \\")
assert len(pat.findall(s)) == 1, len(pat.findall(s))
new = ("{ unsigned char *mp_ = (unsigned char*)memchr(ks->buf + ks->begin, '\\n', (size_t)(ks->end - ks->begin)); \\\n"
       "\t\t\t\t  i = mp_ ? (int)(mp_ - ks->buf) : ks->end; } \\")
s = pat.sub(lambda m: new, s)
if len(sys.argv) > 1 and sys.argv[1] == "bigbuf":
    s = s.replace("KSTREAM_INIT(type_t, __read, 16384)", "KSTREAM_INIT(type_t, __read, 1048576)")
open(p, "w").write(s)
print("S13 kseq patched OK", sys.argv[1:])
