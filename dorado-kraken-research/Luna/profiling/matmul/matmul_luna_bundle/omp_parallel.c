/*
 * OpenMP parallelised IKJ matrix multiplication
 * Outer i-loop distributed across threads; each thread owns its C-rows.
 * No false sharing (each thread writes distinct rows of C).
 * Usage: OMP_NUM_THREADS=8 ./omp_parallel [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

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

    #pragma omp parallel for schedule(static)
    for (int i = 0; i < N; i++)
        for (int k = 0; k < N; k++) {
            double a_ik = A[i*N + k];
            for (int j = 0; j < N; j++)
                C[i*N + j] += a_ik * B[k*N + j];
        }

    volatile double sink = C[0];
    printf("N=%d  threads=%d  C[0][0]=%.6f\n", N, omp_get_max_threads(), sink);

    free(A); free(B); free(C);
    return 0;
}
