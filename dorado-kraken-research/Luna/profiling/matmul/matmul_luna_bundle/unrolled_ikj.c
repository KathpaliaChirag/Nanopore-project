/*
 * IKJ with 4x manual inner-loop unrolling
 * Reduces loop overhead and exposes more ILP to the out-of-order core.
 * Handles N not divisible by 4 with a scalar tail loop.
 * Usage: ./unrolled_ikj [N]   (default N=1024)
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

    int N4 = N & ~3;   /* largest multiple of 4 <= N */

    for (int i = 0; i < N; i++) {
        for (int k = 0; k < N; k++) {
            double a_ik = A[i*N + k];
            double *Ci  = &C[i*N];
            double *Bk  = &B[k*N];
            int j;
            for (j = 0; j < N4; j += 4) {
                Ci[j+0] += a_ik * Bk[j+0];
                Ci[j+1] += a_ik * Bk[j+1];
                Ci[j+2] += a_ik * Bk[j+2];
                Ci[j+3] += a_ik * Bk[j+3];
            }
            for (; j < N; j++)          /* tail */
                Ci[j] += a_ik * Bk[j];
        }
    }

    volatile double sink = C[0];
    printf("N=%d  C[0][0]=%.6f\n", N, sink);

    free(A); free(B); free(C);
    return 0;
}
