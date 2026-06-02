// shared_tiled.cu - classic shared memory tiled GEMM. Each thread block loads
// a TILE x TILE chunk of A and B into shared memory, then all threads in the
// block compute their share of the C tile from on-chip memory.
//
// This is the GPU equivalent of CPU tiled.c. Expected speedup over naive_gpu:
// 5-20x depending on N, because each A/B element is reused TILE times from
// fast shared memory instead of re-fetched from DRAM.

#include "common.h"

#define TILE 32

__global__ void shared_tiled_kernel(const float *A, const float *B, float *C, int N) {
    __shared__ float As[TILE][TILE];
    __shared__ float Bs[TILE][TILE];

    int row = blockIdx.y * TILE + threadIdx.y;
    int col = blockIdx.x * TILE + threadIdx.x;
    float acc = 0.0f;

    for (int t = 0; t < N; t += TILE) {
        // Cooperative load of one tile of A and B into shared memory.
        As[threadIdx.y][threadIdx.x] =
            (row < N && (t + threadIdx.x) < N) ? A[row * N + t + threadIdx.x] : 0.0f;
        Bs[threadIdx.y][threadIdx.x] =
            ((t + threadIdx.y) < N && col < N) ? B[(t + threadIdx.y) * N + col] : 0.0f;
        __syncthreads();

        #pragma unroll
        for (int k = 0; k < TILE; ++k) acc += As[threadIdx.y][k] * Bs[k][threadIdx.x];
        __syncthreads();
    }
    if (row < N && col < N) C[row * N + col] = acc;
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

    dim3 block(TILE, TILE);
    dim3 grid((N + TILE - 1) / TILE, (N + TILE - 1) / TILE);

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    shared_tiled_kernel<<<grid, block>>>(dA, dB, dC, N);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("shared_tiled", N, ms);

    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC);
    return 0;
}
