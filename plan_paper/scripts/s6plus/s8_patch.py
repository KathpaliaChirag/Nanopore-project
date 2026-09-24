# S8 (2026-09-24) = S6 + multi-file input streaming.
# Stock kraken2 runs one OpenMP parallel region per input file; each region
# ends in a barrier where threads idle waiting for the last block (~0.15s per
# file at 32 threads). Measured: same 1.87M reads as ONE file is 2.0-2.8s
# faster than as 16 files. Fix: a single shared reader that advances to the
# next file at EOF inside the existing critical(seqread) section, so all
# unpaired input files are one continuous stream. Read order = file order, so
# output order is unchanged. Paired-end paths are left untouched.
import re

# ---------------- seqreader.h ----------------
p = "seqreader.h"
s = open(p).read()

# 1. destructor: close the right fd and free shared state
old = '''  ~BatchSequenceReader() {
    if (primary_) {
      kseq_destroy(kseq_);
      if (fd_ > 2) {
        close(fd_);
      }
    }
  }'''
new = '''  ~BatchSequenceReader() {
    if (primary_) {
      kseq_destroy(kseq_);
      if (multi_) {
        if (multi_->cur_fd > 2) close(multi_->cur_fd);
        delete multi_;
      } else if (fd_ > 2) {
        close(fd_);
      }
    }
  }

  // S8: queue more files to be read, in order, after the first one.
  void AppendFile(const std::string &fn) {
    if (! multi_) {
      multi_ = new Multi();
      multi_->cur_fd = fd_;
    }
    multi_->files.push_back(fn);
  }'''
assert s.count(old) == 1
s = s.replace(old, new)

# 2. constructors init multi_
old = '''    kseq_ = kseq_init(fd_);
    curr_ = 0;
    size_ = 0;'''
new = '''    kseq_ = kseq_init(fd_);
    multi_ = nullptr;
    curr_ = 0;
    size_ = 0;'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''    kseq_ = rhs.kseq_;
    curr_ = rhs.curr_;'''
new = '''    kseq_ = rhs.kseq_;
    multi_ = rhs.multi_;
    curr_ = rhs.curr_;'''
assert s.count(old) == 1
s = s.replace(old, new)

# 3. LoadBlock hops to the next file at EOF
old = '''      } else {
        break;
      }
    }

    curr_ = 0;
    return size_ > 0;
  }

  bool NextSequence(Sequence& seq)'''
new = '''      } else if (AdvanceFile()) {
        continue;
      } else {
        break;
      }
    }

    curr_ = 0;
    return size_ > 0;
  }

  bool NextSequence(Sequence& seq)'''
assert s.count(old) == 1
s = s.replace(old, new)

# 4. private helpers + shared state
old = '''private:
  void copy_from_kseq(Sequence& seq)'''
new = '''private:
  struct Multi {
    std::vector<std::string> files;
    size_t next = 0;
    int cur_fd = -1;
  };

  // Called only from inside critical(seqread) (via LoadBlock): swap the
  // underlying fd of the shared kseq stream to the next queued file.
  bool AdvanceFile() {
    while (multi_ && multi_->next < multi_->files.size()) {
      int nfd = open(multi_->files[multi_->next++].c_str(), O_RDONLY);
      if (nfd < 0) continue;  // unopenable file behaves like an empty one
      if (multi_->cur_fd > 2) close(multi_->cur_fd);
      multi_->cur_fd = nfd;
      kseq_->f->f = nfd;
      kseq_->f->begin = 0;
      kseq_->f->end = 0;
      kseq_->f->is_eof = 0;
      kseq_->last_char = 0;
      return true;
    }
    return false;
  }

  Multi *multi_;
  void copy_from_kseq(Sequence& seq)'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, "w").write(s)

# ---------------- classify.cc ----------------
p = "classify.cc"
s = open(p).read()

i = s.index("void ProcessFiles(")
s = s[:i] + "// S8: extra input files to stream after the first (unpaired mode only).\nstatic const std::vector<std::string> *g_extra_files = nullptr;\n\n" + s[i:]

old = '''  BatchSequenceReader r1(filename1);
  BatchSequenceReader r2(filename2);'''
new = '''  BatchSequenceReader r1(filename1);
  if (filename1 != nullptr && g_extra_files != nullptr)
    for (const std::string &f : *g_extra_files)
      r1.AppendFile(f);
  BatchSequenceReader r2(filename2);'''
assert s.count(old) == 1
s = s.replace(old, new)

old = '''      } else {
        ProcessFiles(opts.filenames[i], nullptr, hash_ptr, taxonomy, idx_opts, opts, stats, outputs, taxon_counters);
      }'''
new = '''      } else if (! opts.paired_end_processing && opts.filenames.size() > 1 && i == 0) {
        // S8: stream every unpaired file through one reader / one parallel region
        std::vector<std::string> rest;
        for (size_t j = 1; j < opts.filenames.size(); j++)
          rest.push_back(opts.filenames[j]);
        g_extra_files = &rest;
        ProcessFiles(opts.filenames[0], nullptr, hash_ptr, taxonomy, idx_opts, opts, stats, outputs, taxon_counters);
        g_extra_files = nullptr;
        break;
      } else {
        ProcessFiles(opts.filenames[i], nullptr, hash_ptr, taxonomy, idx_opts, opts, stats, outputs, taxon_counters);
      }'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, "w").write(s)
print("S8 patched OK")
