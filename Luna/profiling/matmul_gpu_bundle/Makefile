##############################################################################
# GPU matmul benchmark suite for Luna.
# Usage:
#   make            - build all variants
#   make clean
#   make ARCH=sm_80 - override target architecture (default: native)
##############################################################################

NVCC    := nvcc
ARCH    ?= native
NVFLAGS := -O3 -std=c++14 -arch=$(ARCH) -Xcompiler -O3 -lineinfo
LIBS    := -lcublas

BINS := naive_gpu coalesced_gpu shared_tiled shared_tiled_2d \
        cublas_sgemm cublas_tensor wmma_manual

.PHONY: all clean
all: $(BINS)

naive_gpu: naive_gpu.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $<

coalesced_gpu: coalesced_gpu.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $<

shared_tiled: shared_tiled.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $<

shared_tiled_2d: shared_tiled_2d.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $<

cublas_sgemm: cublas_sgemm.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $< $(LIBS)

cublas_tensor: cublas_tensor.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $< $(LIBS)

wmma_manual: wmma_manual.cu common.h
	$(NVCC) $(NVFLAGS) -o $@ $<

clean:
	rm -f $(BINS)
	rm -rf gpu_results/
