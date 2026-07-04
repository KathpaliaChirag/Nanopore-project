// common.h - shared host-side helpers for all GPU matmul variants.
// Float (single precision) throughout. CPU baseline used double — see README.

#pragma once
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t err = (call);                                              \
        if (err != cudaSuccess) {                                              \
            fprintf(stderr, "CUDA error %s:%d: %s\n",                          \
                    __FILE__, __LINE__, cudaGetErrorString(err));              \
            exit(1);                                                           \
        }                                                                      \
    } while (0)

static inline void fill_random(float *p, size_t n) {
    for (size_t i = 0; i < n; ++i) p[i] = (float)rand() / RAND_MAX;
}

// Allocate host A,B,C of size NxN, fill A and B with random data.
static inline void host_alloc(int N, float **A, float **B, float **C) {
    size_t bytes = (size_t)N * N * sizeof(float);
    *A = (float*)malloc(bytes);
    *B = (float*)malloc(bytes);
    *C = (float*)malloc(bytes);
    fill_random(*A, (size_t)N * N);
    fill_random(*B, (size_t)N * N);
    memset(*C, 0, bytes);
}

// Report wall time + GFLOPS. 2*N^3 FLOPs in matmul.
static inline void report(const char *name, int N, float ms) {
    double flops = 2.0 * (double)N * N * N;
    double gflops = flops / (ms * 1e6);
    printf("%-20s N=%-6d  time=%10.2f ms   %8.1f GFLOPS\n",
           name, N, ms, gflops);
}
