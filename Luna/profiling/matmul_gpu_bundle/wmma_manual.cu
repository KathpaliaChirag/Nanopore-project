// wmma_manual.cu - manual Tensor Core programming via the WMMA C++ API.
// Demonstrates what cuBLAS does internally. Uses FP16 inputs, FP32 accumulate.
// Each warp computes one 16x16 tile of C using a single mma_sync instruction
// per K-step. Tile size 16x16x16 is the smallest Tensor Core fragment shape.
//
// Requires sm_70+ (Volta or newer).

#include "common.h"
#include <cuda_fp16.h>
#include <mma.h>
using namespace nvcuda;

#define WMMA_M 16
#define WMMA_N 16
#define WMMA_K 16

__global__ void wmma_kernel(const half *A, const half *B, float *C, int N) {
    int warpM = (blockIdx.y * blockDim.y + threadIdx.y);
    int warpN = (blockIdx.x * blockDim.x + threadIdx.x) / warpSize;

    wmma::fragment<wmma::matrix_a, WMMA_M, WMMA_N, WMMA_K, half, wmma::row_major> a_frag;
    wmma::fragment<wmma::matrix_b, WMMA_M, WMMA_N, WMMA_K, half, wmma::row_major> b_frag;
    wmma::fragment<wmma::accumulator, WMMA_M, WMMA_N, WMMA_K, float> c_frag;
    wmma::fill_fragment(c_frag, 0.0f);

    int aRow = warpM * WMMA_M;
    int bCol = warpN * WMMA_N;

    for (int k = 0; k < N; k += WMMA_K) {
        int aCol = k, bRow = k;
        if (aRow < N && aCol < N && bRow < N && bCol < N) {
            wmma::load_matrix_sync(a_frag, A + aRow * N + aCol, N);
            wmma::load_matrix_sync(b_frag, B + bRow * N + bCol, N);
            wmma::mma_sync(c_frag, a_frag, b_frag, c_frag);
        }
    }

    if (aRow < N && bCol < N)
        wmma::store_matrix_sync(C + aRow * N + bCol, c_frag, N, wmma::mem_row_major);
}

int main(int argc, char **argv) {
    int N = (argc > 1) ? atoi(argv[1]) : 1024;
    if (N % 16 != 0) { fprintf(stderr, "N must be multiple of 16\n"); return 1; }

    float *hA, *hB, *hC; host_alloc(N, &hA, &hB, &hC);
    size_t n2 = (size_t)N * N;

    // Convert A,B to half on host (simple loop).
    half *hAh = (half*)malloc(n2 * sizeof(half));
    half *hBh = (half*)malloc(n2 * sizeof(half));
    for (size_t i = 0; i < n2; ++i) { hAh[i] = __float2half(hA[i]); hBh[i] = __float2half(hB[i]); }

    half *dA, *dB; float *dC;
    CUDA_CHECK(cudaMalloc(&dA, n2 * sizeof(half)));
    CUDA_CHECK(cudaMalloc(&dB, n2 * sizeof(half)));
    CUDA_CHECK(cudaMalloc(&dC, n2 * sizeof(float)));
    CUDA_CHECK(cudaMemcpy(dA, hAh, n2 * sizeof(half),  cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(dB, hBh, n2 * sizeof(half),  cudaMemcpyHostToDevice));

    // 128 threads per block = 4 warps; each warp does one 16x16 tile.
    dim3 block(128, 4);
    dim3 grid((N + (WMMA_N * 4) - 1) / (WMMA_N * 4),
              (N + (WMMA_M * 4) - 1) / (WMMA_M * 4));

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    wmma_kernel<<<grid, block>>>(dA, dB, dC, N);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("wmma_manual_fp16", N, ms);

    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC); free(hAh); free(hBh);
    return 0;
}
