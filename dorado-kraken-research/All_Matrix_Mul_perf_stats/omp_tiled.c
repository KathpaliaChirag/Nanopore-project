/*
 * OpenMP + cache-blocked (tiled) matrix multiplication
 * Tile the outermost loop level and parallelise across i-tiles.
 * Override tile size at compile time: -DTILE=64
 * Usage: OMP_NUM_THREADS=8 ./omp_tiled [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

#ifndef TILE
#define TILE 64
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

    #pragma omp parallel for collapse(2) schedule(dynamic)
    for (int ii = 0; ii < N; ii += TILE)
    for (int jj = 0; jj < N; jj += TILE) {
        int i_end = ii + TILE < N ? ii + TILE : N;
        int j_end = jj + TILE < N ? jj + TILE : N;
        for (int kk = 0; kk < N; kk += TILE) {
            int k_end = kk + TILE < N ? kk + TILE : N;
            for (int i = ii; i < i_end; i++)
            for (int k = kk; k < k_end; k++) {
                double a_ik = A[i*N + k];
                for (int j = jj; j < j_end; j++)
                    C[i*N + j] += a_ik * B[k*N + j];
            }
        }
    }

    volatile double sink = C[0];
    printf("N=%d  tile=%d  threads=%d  C[0][0]=%.6f\n",
           N, TILE, omp_get_max_threads(), sink);

    free(A); free(B); free(C);
    return 0;
}
