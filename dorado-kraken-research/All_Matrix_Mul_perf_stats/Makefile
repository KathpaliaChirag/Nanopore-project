##############################################################################
# Matrix multiplication benchmark suite
# Usage:
#   make                 – build everything
#   make SIZE=2048       – (used by run_perf, not compile-time)
#   make run_perf        – perf stat all binaries with SIZE (default 1024)
#   make run_perf SIZE=512
#   make clean
#   make tile32          – rebuild tiled variants with TILE=32
##############################################################################

CC      := gcc
CFLAGS  := -O3 -march=native -funroll-loops -Wall -Wextra
OMPFLAGS:= -fopenmp
AVXFLAGS:= -mavx2 -mfma

SIZE    ?= 1024
THREADS ?= 4

BINS := naive_ijk       \
        ikj_order       \
        kij_order       \
        transpose_B     \
        tiled           \
        omp_parallel    \
        omp_tiled       \
        unrolled_ikj    \
        avx2_manual     \
        auto_vec_O3     \
        tiled_avx2      \
        prefetch_ikj

.PHONY: all clean run_perf tile32

all: $(BINS)

naive_ijk: naive_ijk.c
	$(CC) $(CFLAGS) -o $@ $<

ikj_order: ikj_order.c
	$(CC) $(CFLAGS) -o $@ $<

kij_order: kij_order.c
	$(CC) $(CFLAGS) -o $@ $<

transpose_B: transpose_B.c
	$(CC) $(CFLAGS) -o $@ $<

tiled: tiled.c
	$(CC) $(CFLAGS) -o $@ $<

omp_parallel: omp_parallel.c
	$(CC) $(CFLAGS) $(OMPFLAGS) -o $@ $<

omp_tiled: omp_tiled.c
	$(CC) $(CFLAGS) $(OMPFLAGS) -o $@ $<

unrolled_ikj: unrolled_ikj.c
	$(CC) $(CFLAGS) -o $@ $<

avx2_manual: avx2_manual.c
	$(CC) $(CFLAGS) $(AVXFLAGS) -o $@ $<

auto_vec_O3: auto_vec_O3.c
	$(CC) $(CFLAGS) $(AVXFLAGS) -fopt-info-vec -o $@ $< 2>&1 | grep -E "vectorized|note" || true
	$(CC) $(CFLAGS) $(AVXFLAGS) -o $@ $<

tiled_avx2: tiled_avx2.c
	$(CC) $(CFLAGS) $(AVXFLAGS) -o $@ $<

prefetch_ikj: prefetch_ikj.c
	$(CC) $(CFLAGS) -o $@ $<

# rebuild tiled variants with a custom tile size, e.g. make tile32
tile32: tiled.c omp_tiled.c tiled_avx2.c
	$(CC) $(CFLAGS) -DTILE=32 -o tiled_t32 tiled.c
	$(CC) $(CFLAGS) $(OMPFLAGS) -DTILE=32 -o omp_tiled_t32 omp_tiled.c
	$(CC) $(CFLAGS) $(AVXFLAGS) -DTILE=32 -o tiled_avx2_t32 tiled_avx2.c

##############################################################################
# run_perf: run perf stat on every binary and save per-binary reports
# Output: perf_results/  directory with one .txt per binary
##############################################################################
PERF_EVENTS := cache-misses,cache-references,L1-dcache-load-misses,\
L1-dcache-loads,LLC-load-misses,LLC-loads,\
instructions,cycles,branches,branch-misses,\
cpu-migrations,context-switches,\
mem-loads,mem-stores

run_perf: all
	@mkdir -p perf_results
	@echo "Running perf stat for all binaries with N=$(SIZE), OMP_NUM_THREADS=$(THREADS)"
	@echo "============================================================"
	@for bin in $(BINS); do \
	    echo ">>> $$bin (N=$(SIZE))"; \
	    OMP_NUM_THREADS=$(THREADS) \
	    perf stat -e $(PERF_EVENTS) \
	              -o perf_results/$$bin.txt \
	              --append \
	              ./$$bin $(SIZE) 2>&1; \
	    echo ""; \
	done
	@echo "Results saved in perf_results/"

clean:
	rm -f $(BINS) tiled_t32 omp_tiled_t32 tiled_avx2_t32
	rm -rf perf_results/
