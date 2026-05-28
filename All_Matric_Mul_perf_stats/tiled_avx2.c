/*
 * Tiled + AVX2 FMA matrix multiplication
 * Combines cache blocking (TILE×TILE sub-blocks stay in L2) with
 * explicit AVX2 vector FMA in the innermost j-loop.
 * Override tile size: -DTILE=64
 * Requires: -mavx2 -mfma
 * Usage: ./tiled_avx2 [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <immintrin.h>

#ifndef TILE
#define TILE 64
#endif

static inline double *alloc_aligned(size_t bytes) {
    void *p = NULL;
    posix_memalign(&p, 32, bytes);
    return (double *)p;
}

int main(int argc, char *argv[]) {
    int N  = (argc > 1) ? atoi(argv[1]) : 1024;
    int Np = (N + 3) & ~3;   /* pad to AVX-friendly width */

    double *A = alloc_aligned(Np * Np * sizeof(double));
    double *B = alloc_aligned(Np * Np * sizeof(double));
    double *C = alloc_aligned(Np * Np * sizeof(double));
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

    for (int ii = 0; ii < N; ii += TILE)
    for (int kk = 0; kk < N; kk += TILE)
    for (int jj = 0; jj < N; jj += TILE) {
        int i_end = ii + TILE < N ? ii + TILE : N;
        int k_end = kk + TILE < N ? kk + TILE : N;
        int j_end = jj + TILE < N ? jj + TILE : N;
        int j_end4 = jj + ((j_end - jj) & ~3);

        for (int i = ii; i < i_end; i++)
        for (int k = kk; k < k_end; k++) {
            __m256d a_ik = _mm256_set1_pd(A[i*Np + k]);
            double *Ci = &C[i*Np];
            double *Bk = &B[k*Np];
            int j;
            for (j = jj; j < j_end4; j += 4) {
                __m256d c = _mm256_load_pd(Ci + j);
                __m256d b = _mm256_load_pd(Bk + j);
                _mm256_store_pd(Ci + j, _mm256_fmadd_pd(a_ik, b, c));
            }
            for (; j < j_end; j++)
                Ci[j] += A[i*Np + k] * Bk[j];
        }
    }

    volatile double sink = C[0];
    printf("N=%d  tile=%d  C[0][0]=%.6f\n", N, TILE, sink);

    free(A); free(B); free(C);
    return 0;
}
