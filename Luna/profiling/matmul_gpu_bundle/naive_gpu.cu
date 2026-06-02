// naive_gpu.cu - one thread per C[i,j], all reads from global memory.
// Expected: terrible. Every thread re-reads its full A row and B column.
// This is the GPU equivalent of CPU naive_ijk - shows what NOT to do.

#include "common.h"

__global__ void naive_kernel(const float *A, const float *B, float *C, int N) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= N || col >= N) return;

    float acc = 0.0f;
    for (int k = 0; k < N; ++k) acc += A[row * N + k] * B[k * N + col];
    C[row * N + col] = acc;
}

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

    dim3 block(16, 16);
    dim3 grid((N + 15) / 16, (N + 15) / 16);

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    naive_kernel<<<grid, block>>>(dA, dB, dC, N);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("naive_gpu", N, ms);

    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC);
    return 0;
}
