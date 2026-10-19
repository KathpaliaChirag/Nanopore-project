# Minimizer trace — backing data for FLOW.md

Read `14f8e11f-1e09-48d1-8a7b-ac43994b3bf0`, pod5_15 read index 1, 2,274 bp,
717 distinct minimizers. Produced by `scripts/trace_minimizer.cc`, which links
kraken2's own mmscanner / compact_hash / taxonomy objects.

| file | contents |
|---|---|
| `read_14f8e11f.fastq` | the single read, extracted |
| `trace_eskape_big_M12000000.txt` | all 717 minimizers traced in the 48 MB DB |
| `trace_standard_16gb.txt` | the same 717 traced in the 16 GB DB |

Regenerate:

    g++ -O2 -std=c++17 -fopenmp -I kraken2/src -o trace_minimizer \
        scripts/trace_minimizer.cc \
        kraken2/src/{mmscanner,compact_hash,taxonomy,mmap_file,utilities,omp_hack}.o
    ./trace_minimizer databases/eskape_big_M12000000 perpod5/pod5_15.fastq 1 999
    ./trace_minimizer databases/standard_16gb        perpod5/pod5_15.fastq 1 999

Headline checks (both files, all 717 minimizers):
  minimizer sets identical      717/717
  hash identical                717/717   (0 differences)
  both DBs performed lookup     154       (rest -M-skipped)
  key_16GB == key_48MB >> 10    154/154
