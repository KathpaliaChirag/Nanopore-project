# Does MurmurHash3 earn its place? — backs FLOW.md §7

2,727,687 distinct minimizers from 3,000 reads of `perpod5/pod5_15.fastq`,
extracted with kraken2's own `MinimizerScanner` (`scripts/dump_minimizers.cc`),
analysed by `scripts/hash_uniformity.py`. Output in `RESULT.txt`.

The question: the hash is a bijection on 64 bits (62-bit input, 64-bit output),
so it compresses nothing. What does it buy?

| property | raw minimizer | MurmurHash3 |
|---|---|---|
| slots occupied of 12 M (ideal 2,439,888) | 602,438 — 24.7% | **2,439,465 — 100.0%** |
| worst slot | 25 keys | **6 keys** |
| chi2/dof vs uniform | 6.62 | **1.00** |
| top-26-bit fingerprint, keys separable | 82.4% | **98.0%** |
| `-M` gate skip fraction (target 76.92%) | 100.00% — dead | **76.95%** |
| low-26 vs high-26 bit correlation | +0.0008 | −0.0033 |

Conclusion: the hash buys **uniformity**, **fingerprint discrimination**, and
**the existence of `-M` subsampling**. It does not buy slot/fingerprint
independence — that is ~0 for both, measured and discarded.

Regenerate:

    g++ -O2 -std=c++17 -fopenmp -I kraken2/src -o dump_minimizers \
        scripts/dump_minimizers.cc kraken2/src/{mmscanner,mmap_file,utilities,omp_hack}.o
    ./dump_minimizers databases/eskape_big_M12000000 perpod5/pod5_15.fastq 3000 > mm.txt
    python3 scripts/hash_uniformity.py mm.txt
