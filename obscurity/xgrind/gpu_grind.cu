#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <cuda_runtime.h>
#include "GPU/GPUSecp.h"
#include "GPU/GPUHash.h"
#include "GPU/GPUMath.h"

#ifndef GPU_BATCH_SIZE
#define GPU_BATCH_SIZE 16384
#endif

#define CHECK_CUDA(call) { \
    cudaError_t _e = (call); \
    if (_e != cudaSuccess) { \
        fprintf(stderr, "CUDA error %s:%d: %s\n", __FILE__, __LINE__, cudaGetErrorString(_e)); \
        return 0; \
    } \
}

static uint8_t *d_priv = nullptr;
static uint8_t *d_pub = nullptr;
static int *d_match_idx = nullptr;
static uint8_t *d_gTableX = nullptr;
static uint8_t *d_gTableY = nullptr;

__device__ uint8_t *g_gTableX = nullptr;
__device__ uint8_t *g_gTableY = nullptr;
__device__ int g_stop_flag = 0;

__device__ void _PointAddSecp256k1(uint64_t *p1x, uint64_t *p1y, uint64_t *p1z, uint64_t *p2x, uint64_t *p2y);
__device__ void _ModInv(uint64_t *R);
__device__ void _ModMult(uint64_t *r, uint64_t *a);

__device__ void _PointMultiSecp256k1(uint64_t *qx, uint64_t *qy, uint16_t *privKey, uint8_t *gTableX, uint8_t *gTableY) {
    int chunk = 0;
    uint64_t qz[5] = {1, 0, 0, 0, 0};
    for (; chunk < NUM_GTABLE_CHUNK; chunk++) {
        if (privKey[chunk] > 0) {
            int index = (CHUNK_FIRST_ELEMENT[chunk] + (privKey[chunk] - 1)) * SIZE_GTABLE_POINT;
            memcpy(qx, gTableX + index, SIZE_GTABLE_POINT);
            memcpy(qy, gTableY + index, SIZE_GTABLE_POINT);
            chunk++;
            break;
        }
    }
    for (; chunk < NUM_GTABLE_CHUNK; chunk++) {
        if (privKey[chunk] > 0) {
            uint64_t gx[4], gy[4];
            int index = (CHUNK_FIRST_ELEMENT[chunk] + (privKey[chunk] - 1)) * SIZE_GTABLE_POINT;
            memcpy(gx, gTableX + index, SIZE_GTABLE_POINT);
            memcpy(gy, gTableY + index, SIZE_GTABLE_POINT);
            _PointAddSecp256k1(qx, qy, qz, gx, gy);
        }
    }
    _ModInv(qz);
    _ModMult(qx, qz);
    _ModMult(qy, qz);
}

__device__ inline void qx_to_be32(const uint64_t qx[4], uint8_t out[32]) {
    #pragma unroll
    for (int limb = 0; limb < 4; ++limb) {
        uint64_t w = qx[3 - limb];
        int base = limb * 8;
        out[base + 0] = (uint8_t)(w >> 56);
        out[base + 1] = (uint8_t)(w >> 48);
        out[base + 2] = (uint8_t)(w >> 40);
        out[base + 3] = (uint8_t)(w >> 32);
        out[base + 4] = (uint8_t)(w >> 24);
        out[base + 5] = (uint8_t)(w >> 16);
        out[base + 6] = (uint8_t)(w >> 8);
        out[base + 7] = (uint8_t)(w >> 0);
    }
}

__device__ void dev_secp256k1_mul_gen_compressed(const uint8_t priv[32], uint8_t pub[33]) {
    uint64_t qx[4], qy[4];
    uint16_t *priv_chunks = (uint16_t *)priv;
    _PointMultiSecp256k1(qx, qy, priv_chunks, g_gTableX, g_gTableY);
    pub[0] = (uint8_t)(0x02u | ((uint8_t)(qy[0] & 1u)));
    qx_to_be32(qx, &pub[1]);
}

__global__ void grind_batch_kernel(const uint8_t *priv_in, uint8_t *pub_out, uint32_t target_32bit, uint32_t mask, int *match_index, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n || g_stop_flag) return;

    uint8_t priv[32];
    #pragma unroll
    for (int i = 0; i < 32; ++i) priv[i] = priv_in[idx * 32 + i];

    uint8_t pub[33];
    dev_secp256k1_mul_gen_compressed(priv, pub);

    uint32_t key_32bit = ((uint32_t)pub[1] << 24) | ((uint32_t)pub[2] << 16) | ((uint32_t)pub[3] << 8) | (uint32_t)pub[4];

    if ((key_32bit & mask) != (target_32bit & mask)) return;

    if (atomicCAS(match_index, -1, idx) == -1) {
        uint8_t *dst = pub_out + idx * 33;
        #pragma unroll
        for (int i = 0; i < 33; ++i) dst[i] = pub[i];
        atomicExch(&g_stop_flag, 1);
    }
}

extern "C" int gpu_init(const uint8_t *gTableXCPU, const uint8_t *gTableYCPU) {
    if (d_priv) return 1;
    size_t gsize = (size_t)COUNT_GTABLE_POINTS * (size_t)SIZE_GTABLE_POINT;
    CHECK_CUDA(cudaMalloc(&d_priv, GPU_BATCH_SIZE * 32));
    CHECK_CUDA(cudaMalloc(&d_pub, GPU_BATCH_SIZE * 33));
    CHECK_CUDA(cudaMalloc(&d_match_idx, sizeof(int)));
    CHECK_CUDA(cudaMalloc(&d_gTableX, gsize));
    CHECK_CUDA(cudaMalloc(&d_gTableY, gsize));
    CHECK_CUDA(cudaMemcpy(d_gTableX, gTableXCPU, gsize, cudaMemcpyHostToDevice));
    CHECK_CUDA(cudaMemcpy(d_gTableY, gTableYCPU, gsize, cudaMemcpyHostToDevice));
    CHECK_CUDA(cudaMemcpyToSymbol(g_gTableX, &d_gTableX, sizeof(uint8_t *)));
    CHECK_CUDA(cudaMemcpyToSymbol(g_gTableY, &d_gTableY, sizeof(uint8_t *)));
    return 1;
}

extern "C" void gpu_shutdown(void) {
    if (d_priv) cudaFree(d_priv), d_priv = nullptr;
    if (d_pub) cudaFree(d_pub), d_pub = nullptr;
    if (d_match_idx) cudaFree(d_match_idx), d_match_idx = nullptr;
    if (d_gTableX) cudaFree(d_gTableX), d_gTableX = nullptr;
    if (d_gTableY) cudaFree(d_gTableY), d_gTableY = nullptr;
}

extern "C" int gpu_search_batch(uint32_t target_32bit, uint32_t mask, const uint8_t *priv32_array, int batch_size, int *match_index_out, uint8_t pub_out[33], uint64_t *attempts_out) {
    if (batch_size <= 0 || batch_size > GPU_BATCH_SIZE) return 0;
    int h_match = -1;
    CHECK_CUDA(cudaMemcpy(d_priv, priv32_array, batch_size * 32, cudaMemcpyHostToDevice));
    CHECK_CUDA(cudaMemcpy(d_match_idx, &h_match, sizeof(int), cudaMemcpyHostToDevice));
    int zero = 0;
    CHECK_CUDA(cudaMemcpyToSymbol(g_stop_flag, &zero, sizeof(int)));

    grind_batch_kernel<<<(batch_size + 255) / 256, 256>>>(d_priv, d_pub, target_32bit, mask, d_match_idx, batch_size);
    cudaDeviceSynchronize();

    CHECK_CUDA(cudaMemcpy(&h_match, d_match_idx, sizeof(int), cudaMemcpyDeviceToHost));
    if (attempts_out) *attempts_out = (h_match >= 0) ? (uint64_t)(h_match + 1) : (uint64_t)batch_size;
    *match_index_out = h_match;

    if (h_match >= 0) {
        CHECK_CUDA(cudaMemcpy(pub_out, d_pub + h_match * 33, 33, cudaMemcpyDeviceToHost));
        return 1;
    }
    return 0;
}
