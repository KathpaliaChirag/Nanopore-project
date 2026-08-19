/*
 * Explicit AVX2 (256-bit) matrix multiplication
 * Processes 4 doubles per FMA instruction using _mm256_fmadd_pd.
 * Requires: -mavx2 -mfma  (Haswell / Zen 2+)
 * Pads inner dimension to multiple of 4 internally; supports arbitrary N.
 * Usage: ./avx2_manual [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <immintrin.h>
#include <string.h>

/* Align to 32 bytes for AVX loads */
static inline double *alloc_aligned(int n) {
    void *p = NULL;
    posix_memalign(&p, 32, n * sizeof(double));
    return (double *)p;
}

int main(int argc, char *argv[]) {
    int N = (argc > 1) ? atoi(argv[1]) : 1024;

    /* Pad N to next multiple of 4 for aligned AVX stores/loads */
    int Np = (N + 3) & ~3;

    double *A = alloc_aligned(Np * Np);
    double *B = alloc_aligned(Np * Np);
    double *C = alloc_aligned(Np * Np);
    if (!A || !B || !C) { fprintf(stderr, "malloc failed\n"); return 1; }

    memset(A, 0, Np * Np * sizeof(double));
    memset(B, 0, Np * Np * sizeof(double));
    memset(C, 0, Np * Np * sizeof(double));

    srand(42);
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            A[i*Np + j] = (double)rand() / RAND_MAX;
            B[i*Np + j] = (double)rand() / RAND_MAX;
        }

    for (int i = 0; i < N; i++) {
        for (int k = 0; k < N; k++) {
            __m256d a_ik = _mm256_set1_pd(A[i*Np + k]);
            double *Ci = &C[i*Np];
            double *Bk = &B[k*Np];
            int j;
            for (j = 0; j <= Np - 4; j += 4) {
                __m256d c  = _mm256_load_pd(Ci + j);
                __m256d b  = _mm256_load_pd(Bk + j);
                c = _mm256_fmadd_pd(a_ik, b, c);
                _mm256_store_pd(Ci + j, c);
            }
            /* scalar tail (only if N was not padded-aligned) */
            for (; j < N; j++)
                Ci[j] += A[i*Np + k] * Bk[j];
        }
    }

    volatile double sink = C[0];
    printf("N=%d  Npad=%d  C[0][0]=%.6f\n", N, Np, sink);

    free(A); free(B); free(C);
    return 0;
}
