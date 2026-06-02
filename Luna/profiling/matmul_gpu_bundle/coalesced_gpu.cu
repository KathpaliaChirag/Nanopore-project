// coalesced_gpu.cu - same algorithm as naive but with threads laid out so that
// consecutive threads in a warp access consecutive memory addresses.
//
// In naive_gpu.cu, threadIdx.x stepped the COLUMN of C, meaning the inner
// access B[k*N + col] was already coalesced — but A[row*N + k] was a broadcast
// across the warp (32 threads read the same A element). That's fine, but
// the warp also re-reads the entire A row N times redundantly.
//
// This version uses 1D blocks with col = threadIdx.x to make coalescing
// explicit and adds the standard "transpose access pattern" comment.
// Speedup vs naive is modest — the real win comes from shared memory (next).

#include "common.h"

__global__ void coalesced_kernel(const float *A, const float *B, float *C, int N) {
    int row = blockIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (col >= N) return;

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

    dim3 block(256);
    dim3 grid((N + 255) / 256, N);

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    coalesced_kernel<<<grid, block>>>(dA, dB, dC, N);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("coalesced_gpu", N, ms);

    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC);
    return 0;
}
