// cublas_sgemm.cu - NVIDIA's hand-tuned single-precision GEMM via cuBLAS.
// This is the gold standard - we cannot beat it. Use it as the upper bound.
//
// Note: cuBLAS expects column-major. We compute C^T = B^T * A^T which gives
// the row-major C we want when read back.

#include "common.h"
#include <cublas_v2.h>

int main(int argc, char **argv) {
    int N = (argc > 1) ? atoi(argv[1]) : 1024;
    float *hA, *hB, *hC; host_alloc(N, &hA, &hB, &hC);

    float *dA, *dB, *dC;
    size_t bytes = (size_t)N * N * sizeof(float);
    CUDA_CHECK(cudaMalloc(&dA, bytes));
    CUDA_CHECK(cudaMalloc(&dB, bytes));
    CUDA_CHECK(cudaMalloc(&dC, bytes));
    CUDA_CHECK(cudaMemcpy(dA, hA, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dB, hB, bytes, cudaMemcpyHostToDevice));

    cublasHandle_t h; cublasCreate(&h);
    const float alpha = 1.0f, beta = 0.0f;

    // Warmup (cuBLAS picks a kernel on first call).
    cublasSgemm(h, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N,
                &alpha, dB, N, dA, N, &beta, dC, N);
    cudaDeviceSynchronize();

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    cublasSgemm(h, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N,
                &alpha, dB, N, dA, N, &beta, dC, N);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("cublas_sgemm", N, ms);

    cublasDestroy(h);
    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC);
    return 0;
}
