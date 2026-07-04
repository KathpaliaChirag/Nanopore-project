// shared_tiled_2d.cu - shared memory tiling plus register tiling.
// Each thread now computes an 8x8 sub-tile of C instead of one element,
// which dramatically increases arithmetic intensity (FLOPs per byte loaded).
//
// Block:  16 x 16 threads -> 128 x 128 output tile (each thread does 8x8).
// Shared: A_s[128][8], B_s[8][128] per k-strip.
//
// This pattern is what real high-performance GEMM kernels look like.
// Expected: approaching cuBLAS within 2-3x on most GPUs.

#include "common.h"

#define BM 128   // output tile rows per block
#define BN 128   // output tile cols per block
#define BK 8     // k-strip width
#define TM 8     // thread sub-tile rows
#define TN 8     // thread sub-tile cols

__global__ void shared_tiled_2d_kernel(const float *A, const float *B, float *C, int N) {
    __shared__ float As[BM][BK];
    __shared__ float Bs[BK][BN];

    int tx = threadIdx.x, ty = threadIdx.y;
    int row0 = blockIdx.y * BM + ty * TM;
    int col0 = blockIdx.x * BN + tx * TN;

    float acc[TM][TN] = {0};

    // Thread linear index for cooperative loading (16*16 = 256 threads per block).
    int tid = ty * 16 + tx;

    for (int kt = 0; kt < N; kt += BK) {
        // Load BM*BK = 1024 floats of A into As cooperatively.
        // 256 threads, each loads 4 floats.
        #pragma unroll
        for (int i = 0; i < 4; ++i) {
            int idx = tid + i * 256;
            int ar = idx / BK, ak = idx % BK;
            int gr = blockIdx.y * BM + ar;
            As[ar][ak] = (gr < N && (kt + ak) < N) ? A[gr * N + kt + ak] : 0.0f;
        }
        // Load BK*BN = 1024 floats of B into Bs cooperatively.
        #pragma unroll
        for (int i = 0; i < 4; ++i) {
            int idx = tid + i * 256;
            int bk = idx / BN, bc = idx % BN;
            int gc = blockIdx.x * BN + bc;
            Bs[bk][bc] = ((kt + bk) < N && gc < N) ? B[(kt + bk) * N + gc] : 0.0f;
        }
        __syncthreads();

        // Each thread accumulates its 8x8 sub-tile.
        #pragma unroll
        for (int k = 0; k < BK; ++k) {
            float a_reg[TM], b_reg[TN];
            #pragma unroll
            for (int i = 0; i < TM; ++i) a_reg[i] = As[ty * TM + i][k];
            #pragma unroll
            for (int j = 0; j < TN; ++j) b_reg[j] = Bs[k][tx * TN + j];
            #pragma unroll
            for (int i = 0; i < TM; ++i)
                #pragma unroll
                for (int j = 0; j < TN; ++j)
                    acc[i][j] += a_reg[i] * b_reg[j];
        }
        __syncthreads();
    }

    #pragma unroll
    for (int i = 0; i < TM; ++i) {
        int r = row0 + i;
        if (r >= N) continue;
        #pragma unroll
        for (int j = 0; j < TN; ++j) {
            int c = col0 + j;
            if (c < N) C[r * N + c] = acc[i][j];
        }
    }
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
    dim3 grid((N + BN - 1) / BN, (N + BM - 1) / BM);

    cudaEvent_t s, e;
    cudaEventCreate(&s); cudaEventCreate(&e);
    cudaEventRecord(s);
    shared_tiled_2d_kernel<<<grid, block>>>(dA, dB, dC, N);
    cudaEventRecord(e); cudaEventSynchronize(e);
    float ms = 0; cudaEventElapsedTime(&ms, s, e);

    report("shared_tiled_2d", N, ms);

    cudaFree(dA); cudaFree(dB); cudaFree(dC);
    free(hA); free(hB); free(hC);
    return 0;
}
