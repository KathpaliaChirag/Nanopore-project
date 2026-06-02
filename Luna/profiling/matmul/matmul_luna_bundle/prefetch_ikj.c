/*
 * IKJ with explicit software prefetch
 * Inserts __builtin_prefetch ahead of the inner loop to hide DRAM latency.
 * PREFETCH_DIST controls how many cache lines ahead to prefetch.
 * Interesting to compare with hardware prefetcher behaviour under perf stat.
 * Usage: ./prefetch_ikj [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>

#ifndef PREFETCH_DIST
#define PREFETCH_DIST 8    /* doubles = 1 cache line ahead per iter */
#endif

int main(int argc, char *argv[]) {
    int N = (argc > 1) ? atoi(argv[1]) : 1024;

    double *A = (double *)malloc(N * N * sizeof(double));
    double *B = (double *)malloc(N * N * sizeof(double));
    double *C = (double *)calloc(N * N, sizeof(double));
    if (!A || !B || !C) { fprintf(stderr, "malloc failed\n"); return 1; }

    srand(42);
    for (int i = 0; i < N * N; i++) {
        A[i] = (double)rand() / RAND_MAX;
        B[i] = (double)rand() / RAND_MAX;
    }

    for (int i = 0; i < N; i++) {
        for (int k = 0; k < N; k++) {
            double a_ik = A[i*N + k];
            double *Ci  = &C[i*N];
            double *Bk  = &B[k*N];
            /* prefetch next B row to hide TLB/cache miss for next k */
            if (k + 1 < N)
                __builtin_prefetch(&B[(k+1)*N], 0, 1);
            for (int j = 0; j < N; j++) {
                __builtin_prefetch(&Bk[j + PREFETCH_DIST], 0, 1);
                Ci[j] += a_ik * Bk[j];
            }
        }
    }

    volatile double sink = C[0];
    printf("N=%d  prefetch_dist=%d  C[0][0]=%.6f\n", N, PREFETCH_DIST, sink);

    free(A); free(B); free(C);
    return 0;
}
