/*
 * KIJ loop-order matrix multiplication
 * Outer k: B-row[k] loaded once, reused across all i
 * Inner j: both C-row and B-row streamed sequentially
 * Usage: ./kij_order [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>

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

    for (int k = 0; k < N; k++)
        for (int i = 0; i < N; i++) {
            double a_ik = A[i*N + k];
            double *Ci = &C[i*N];
            double *Bk = &B[k*N];
            for (int j = 0; j < N; j++)
                Ci[j] += a_ik * Bk[j];
        }

    volatile double sink = C[0];
    printf("N=%d  C[0][0]=%.6f\n", N, sink);

    free(A); free(B); free(C);
    return 0;
}
