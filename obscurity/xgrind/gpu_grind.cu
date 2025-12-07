// gpu_grind.cu - GPU-side grinder using CudaBrainSecp math

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

#define CHECK_CUDA(call)                                                     \
    do {                                                                     \
        cudaError_t _e = (call);                                             \
        if (_e != cudaSuccess) {                                             \
            fprintf(stderr, "CUDA error %s:%d: %s\n",                        \
                    __FILE__, __LINE__, cudaGetErrorString(_e));             \
            return 0;                                                        \
        }                                                                    \
    } while (0)

// Priv/pub/match buffers
static uint8_t            *d_priv       = nullptr;
static uint8_t            *d_pub        = nullptr;
static int                *d_match_idx  = nullptr;

// GTable device pointers (host-visible)
static uint8_t *d_gTableX = nullptr;
static uint8_t *d_gTableY = nullptr;

// GTable device pointers (device-visible globals we can read in kernels)
__device__ uint8_t *g_gTableX = nullptr;
__device__ uint8_t *g_gTableY = nullptr;

// Stop flag: set to 1 when a thread finds a match
__device__ int g_stop_flag = 0;

// Forward decls from GPUMath.h (implemented inline there)
__device__ void _PointAddSecp256k1(uint64_t *p1x, uint64_t *p1y, uint64_t *p1z,
                                   uint64_t *p2x, uint64_t *p2y);
__device__ void _ModInv(uint64_t *R);
__device__ void _ModMult(uint64_t *r, uint64_t *a);

//Cuda Secp256k1 Point Multiplication
//Takes 32-byte privKey + gTable and outputs 64-byte public key [qx,qy]
__device__ void _PointMultiSecp256k1(uint64_t *qx, uint64_t *qy,
                                     uint16_t *privKey,
                                     uint8_t *gTableX, uint8_t *gTableY) {

    int chunk = 0;
    uint64_t qz[5] = {1, 0, 0, 0, 0};

    //Find the first non-zero point [qx,qy]
    for (; chunk < NUM_GTABLE_CHUNK; chunk++) {
        if (privKey[chunk] > 0) {
            int index = (CHUNK_FIRST_ELEMENT[chunk] + (privKey[chunk] - 1)) * SIZE_GTABLE_POINT;
            memcpy(qx, gTableX + index, SIZE_GTABLE_POINT);
            memcpy(qy, gTableY + index, SIZE_GTABLE_POINT);
            chunk++;
            break;
        }
    }

    //Add the remaining chunks together
    for (; chunk < NUM_GTABLE_CHUNK; chunk++) {
        if (privKey[chunk] > 0) {
            uint64_t gx[4];
            uint64_t gy[4];

            int index = (CHUNK_FIRST_ELEMENT[chunk] + (privKey[chunk] - 1)) * SIZE_GTABLE_POINT;

            memcpy(gx, gTableX + index, SIZE_GTABLE_POINT);
            memcpy(gy, gTableY + index, SIZE_GTABLE_POINT);

            _PointAddSecp256k1(qx, qy, qz, gx, gy);
        }
    }

    //Performing modular inverse on qz to obtain the public key [qx,qy]
    _ModInv(qz);
    _ModMult(qx, qz);
    _ModMult(qy, qz);
}

__device__ inline void qx_to_be32(const uint64_t qx[4], uint8_t out[32]) {
    // qx[0] = least-significant limb, qx[3] = most-significant
    #pragma unroll
    for (int limb = 0; limb < 4; ++limb) {
        // emit most-significant limb first
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

// priv[32] -> compressed pub[33]
__device__ void dev_secp256k1_mul_gen_compressed(const uint8_t priv[32],
                                                 uint8_t pub[33]) {
    uint64_t qx[4];
    uint64_t qy[4];

    // reinterpret 32 bytes as 16 uint16 chunks (little-endian)
    uint16_t *priv_chunks = (uint16_t *)priv;

    uint8_t *gTableX = g_gTableX;
    uint8_t *gTableY = g_gTableY;

    _PointMultiSecp256k1(qx, qy, priv_chunks, gTableX, gTableY);

    // parity bit from qy[0] LSB
    uint8_t parity = (uint8_t)(qy[0] & 1u);
    pub[0] = (uint8_t)(0x02u | (parity & 1u));

    qx_to_be32(qx, &pub[1]);
}

__global__ void grind_batch_kernel(const uint8_t *priv_in,
                                   uint8_t       *pub_out,
                                   uint32_t       target_32bit,
                                   int           *match_index,
                                   int            n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    // If already found a match, bail early
    if (g_stop_flag) return;

    // Load private key into registers
    uint8_t priv[32];
    #pragma unroll
    for (int i = 0; i < 32; ++i) {
        priv[i] = priv_in[idx * 32 + i];
    }

    uint8_t pub[33];
    dev_secp256k1_mul_gen_compressed(priv, pub);

    // Extract top 32 bits from serialized X
    uint32_t key_32bit =
        ((uint32_t)pub[1] << 24) |
        ((uint32_t)pub[2] << 16) |
        ((uint32_t)pub[3] << 8)  |
        (uint32_t)pub[4];

    if (key_32bit != target_32bit) {
        return;
    }

    // Try to claim the win for this batch
    int old = atomicCAS(match_index, -1, idx);
    if (old == -1) {
        // First winner: copy pubkey into global array
        uint8_t *dst = pub_out + idx * 33;
        #pragma unroll
        for (int i = 0; i < 33; ++i) {
            dst[i] = pub[i];
        }
        // Tell other threads to stop as soon as they check g_stop_flag
        atomicExch(&g_stop_flag, 1);
    }
}

// Initialize GPU buffers and upload GTable from CPU.
// gTableXCPU/gTableYCPU must each point to COUNT_GTABLE_POINTS * SIZE_GTABLE_POINT bytes.
extern "C" int gpu_init(const uint8_t *gTableXCPU, const uint8_t *gTableYCPU) {
    if (d_priv || d_pub || d_match_idx || d_gTableX || d_gTableY) {
        // Already initialized
        return 1;
    }

    size_t gsize = (size_t)COUNT_GTABLE_POINTS * (size_t)SIZE_GTABLE_POINT;

    CHECK_CUDA(cudaMalloc(&d_priv, GPU_BATCH_SIZE * 32));
    CHECK_CUDA(cudaMalloc(&d_pub,  GPU_BATCH_SIZE * 33));
    CHECK_CUDA(cudaMalloc(&d_match_idx, sizeof(int)));

    // Allocate & copy GTable to device
    CHECK_CUDA(cudaMalloc(&d_gTableX, gsize));
    CHECK_CUDA(cudaMalloc(&d_gTableY, gsize));

    CHECK_CUDA(cudaMemcpy(d_gTableX, gTableXCPU, gsize, cudaMemcpyHostToDevice));
    CHECK_CUDA(cudaMemcpy(d_gTableY, gTableYCPU, gsize, cudaMemcpyHostToDevice));

    // Publish pointers to device globals
    CHECK_CUDA(cudaMemcpyToSymbol(g_gTableX, &d_gTableX, sizeof(uint8_t *)));
    CHECK_CUDA(cudaMemcpyToSymbol(g_gTableY, &d_gTableY, sizeof(uint8_t *)));

    return 1;
}

extern "C" void gpu_shutdown(void) {
    if (d_priv)      cudaFree(d_priv),      d_priv = nullptr;
    if (d_pub)       cudaFree(d_pub),       d_pub  = nullptr;
    if (d_match_idx) cudaFree(d_match_idx), d_match_idx = nullptr;
    if (d_gTableX)   cudaFree(d_gTableX),   d_gTableX   = nullptr;
    if (d_gTableY)   cudaFree(d_gTableY),   d_gTableY   = nullptr;
}

// Returns 1 if a match found in this batch (and fills pub_out/match_index_out),
// 0 otherwise. attempts_out = number of attempts in this batch.
extern "C" int gpu_search_batch(uint32_t       target_32bit,
                                const uint8_t *priv32_array,
                                int            batch_size,
                                int           *match_index_out,
                                uint8_t        pub_out[33],
                                uint64_t      *attempts_out) {
    if (batch_size <= 0 || batch_size > GPU_BATCH_SIZE) return 0;

    int h_match = -1;

    // Copy privkeys
    CHECK_CUDA(cudaMemcpy(d_priv, priv32_array,
                          batch_size * 32, cudaMemcpyHostToDevice));

    // Reset match index and attempts
    h_match = -1;
    CHECK_CUDA(cudaMemcpy(d_match_idx, &h_match, sizeof(int),
                        cudaMemcpyHostToDevice));

    // Reset stop flag to 0 for this batch
    int zero = 0;
    CHECK_CUDA(cudaMemcpyToSymbol(g_stop_flag, &zero, sizeof(int)));

    dim3 block(256);
    dim3 grid((batch_size + block.x - 1) / block.x);

    grind_batch_kernel<<<grid, block>>>(
        d_priv, d_pub,
        target_32bit,
        d_match_idx,
        batch_size
    );

    cudaError_t err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {
        fprintf(stderr, "CUDA kernel error: %s\n",
                cudaGetErrorString(err));
        return 0;
    }
    err = cudaGetLastError();
    if (err != cudaSuccess) {
        fprintf(stderr, "CUDA post-kernel error: %s\n",
                cudaGetErrorString(err));
        return 0;
    }

    // Read back match index & attempts
    CHECK_CUDA(cudaMemcpy(&h_match, d_match_idx, sizeof(int),
                          cudaMemcpyDeviceToHost));

    // Approximate attempts: at least (match_index + 1) keys were tried
    if (attempts_out) {
        if (h_match >= 0)
            *attempts_out = (uint64_t)(h_match + 1);
        else
            *attempts_out = (uint64_t)batch_size;
    }

    *match_index_out = h_match;

    if (h_match < 0) {
        // No match in this batch
        return 0;
    }

    // Copy winning pubkey back to host
    CHECK_CUDA(cudaMemcpy(pub_out, d_pub + h_match * 33,
                          33, cudaMemcpyDeviceToHost));

    return 1;
}
