# S10 (2026-09-24): parallel hash-table load.
# Stock: LoadTable() reads the whole table with ONE ifstream::read() on one
# thread (103GB db: ~55s, ~65% of a 103GB run's wall time; first-touch page
# faults and the kernel copy are both serial). Fix: read the payload as
# 64MB chunks with pread() from up to 32 OpenMP threads straight into the
# table, so page faults + copies run in parallel. Table bytes are identical,
# so classification output is identical. Falls back to the stock path if the
# open/pread fails.
p = "compact_hash.cc"
s = open(p).read()

old = '''    ifs.read((char *) table_, capacity_ * sizeof(*table_));
    if (! ifs)
      errx(EX_OSERR, "Error reading in hash table");
    file_backed_ = false;'''
new = '''    size_t payload_off = (size_t) ifs.tellg();
    size_t payload_bytes = capacity_ * sizeof(*table_);
    bool parallel_ok = false;
    {
      int pfd = open(filename, O_RDONLY);
      if (pfd >= 0) {
        const size_t CHUNK = (size_t) 64 << 20;
        size_t nchunks = (payload_bytes + CHUNK - 1) / CHUNK;
        int nthr = omp_get_max_threads();
        if (nthr > 32) nthr = 32;
        if (nthr < 1) nthr = 1;
        bool failed = false;
        #pragma omp parallel for schedule(dynamic, 1) num_threads(nthr)
        for (size_t c = 0; c < nchunks; c++) {
          if (failed) continue;
          size_t off = c * CHUNK;
          size_t len = std::min(CHUNK, payload_bytes - off);
          char *dst = ((char *) table_) + off;
          size_t done = 0;
          while (done < len) {
            ssize_t r = pread(pfd, dst + done, len - done, payload_off + off + done);
            if (r <= 0) { failed = true; break; }
            done += (size_t) r;
          }
        }
        close(pfd);
        parallel_ok = ! failed;
      }
    }
    if (! parallel_ok) {
      ifs.clear();
      ifs.seekg(payload_off);
      ifs.read((char *) table_, payload_bytes);
    }
    if (! ifs)
      errx(EX_OSERR, "Error reading in hash table");
    file_backed_ = false;'''
assert s.count(old) == 1
s = s.replace(old, new)
s = s.replace('#include "compact_hash.h"\n', '#include "compact_hash.h"\n#include <fcntl.h>\n#include <unistd.h>\n#include <algorithm>\n', 1)
open(p, "w").write(s)
print("S10 patched OK")
