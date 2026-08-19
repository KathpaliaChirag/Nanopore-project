/*
 * Compiler auto-vectorised IKJ multiplication
 * Written to give the compiler maximum visibility: restrict pointers,
 * scalar accumulator hoisted, no aliasing.  Compiled with -O3 -march=native
 * so GCC/Clang will emit AVX2/AVX-512 without hand-written intrinsics.
 * Compare generated asm vs avx2_manual with: objdump -d auto_vec_O3
 * Usage: ./auto_vec_O3 [N]   (default N=1024)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void matmul(const double * restrict A,
            const double * restrict B,
            double       * restrict C,
            int N)
{
    for (int i = 0; i < N; i++)
        for (int k = 0; k < N; k++) {
            double a_ik = A[i*N + k];
            const double * restrict Bk = &B[k*N];
            double       * restrict Ci = &C[i*N];
            for (int j = 0; j < N; j++)
                Ci[j] += a_ik * Bk[j];
        }
}

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

    matmul(A, B, C, N);

    volatile double sink = C[0];
    printf("N=%d  C[0][0]=%.6f\n", N, sink);

    free(A); free(B); free(C);
    return 0;
}
