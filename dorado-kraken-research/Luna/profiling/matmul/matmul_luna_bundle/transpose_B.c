/*
 * Transpose-B matrix multiplication
 * Pre-transpose B so that B^T is row-major; then both A-row and Bt-row
 * stream sequentially in the innermost loop → near-optimal cache use
 * without tiling complexity.
 * Usage: ./transpose_B [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
    int N = (argc > 1) ? atoi(argv[1]) : 1024;

    double *A  = (double *)malloc(N * N * sizeof(double));
    double *B  = (double *)malloc(N * N * sizeof(double));
    double *Bt = (double *)malloc(N * N * sizeof(double));
    double *C  = (double *)calloc(N * N, sizeof(double));
    if (!A || !B || !Bt || !C) { fprintf(stderr, "malloc failed\n"); return 1; }

    srand(42);
    for (int i = 0; i < N * N; i++) {
        A[i] = (double)rand() / RAND_MAX;
        B[i] = (double)rand() / RAND_MAX;
    }

    /* transpose B → Bt */
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            Bt[j*N + i] = B[i*N + j];

    /* ijk with sequential access to both A-row and Bt-row */
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            double sum = 0.0;
            double *Ai  = &A[i*N];
            double *Btj = &Bt[j*N];
            for (int k = 0; k < N; k++)
                sum += Ai[k] * Btj[k];
            C[i*N + j] = sum;
        }

    volatile double sink = C[0];
    printf("N=%d  C[0][0]=%.6f\n", N, sink);

    free(A); free(B); free(Bt); free(C);
    return 0;
}
