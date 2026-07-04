// cublas_tensor.cu - cuBLAS with Tensor Core acceleration.
// Uses cublasGemmEx with CUBLAS_COMPUTE_32F_FAST_TF32 - inputs are FP32,
// internally rounded to TF32 (10-bit mantissa) for the tensor core multiply,
// accumulated in FP32. About 8x faster than plain SGEMM on Ampere+ (A100/H100).
//
// Requires sm_80+ (Ampere or newer). On older GPUs falls back silently.

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
    cublasSetMathMode(h, CUBLAS_TF32_TENSOR_OP_MATH);
    const float alpha = 1.0f, beta = 0.0f;

    // Warmup.
    cublasGemmEx(h, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N,
                 &alpha, dB, CUDA_R_32F, N,
                         dA, CUDA_R_32F, N,
                 &beta,  dC, CUDA_R_32F, N,
                 CUBLAS_COMPUTE_32F_FAST_TF32,
                 CUBLAS_GEMM_DEFAULT_TENSOR_OP);
    cudaDeviceSynchronize();

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    cublasGemmEx(h, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N,
                 &alpha, dB, CUDA_R_32F, N,
                         dA, CUDA_R_32F, N,
                 &beta,  dC, CUDA_R_32F, N,
                 CUBLAS_COMPUTE_32F_FAST_TF32,
                 CUBLAS_GEMM_DEFAULT_TENSOR_OP);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("cublas_tensor_tf32", N, ms);

    cublasDestroy(h);
    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC);
    return 0;
}
