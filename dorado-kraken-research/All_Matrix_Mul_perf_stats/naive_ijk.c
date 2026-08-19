/*
 * Naive IJK matrix multiplication
 * Worst cache behavior: B traversed column-by-column (strided access)
 * Usage: ./naive_ijk [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            for (int k = 0; k < N; k++)
                C[i*N + j] += A[i*N + k] * B[k*N + j];

    /* prevent dead-code elimination */
    volatile double sink = C[0];
    printf("N=%d  C[0][0]=%.6f\n", N, sink);

    free(A); free(B); free(C);
    return 0;
}
