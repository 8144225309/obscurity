// gtable_cpu.cpp - build secp256k1 GTable for GPU

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/resource.h>

#include "GPU/GPUSecp.h"      // for SIZE_CPU_STACK, NUM_GTABLE_CHUNK, etc
#include "CPU/SECP256k1.h"
#include "CPU/Point.h"

// Exactly like CudaBrainSecp's increaseStackSizeCPU()
static void increaseStackSizeCPU() {
    const rlim_t cpuStackSize = SIZE_CPU_STACK;
    struct rlimit rl;
    int result;

    printf("Increasing Stack Size to %lu \n", (unsigned long)cpuStackSize);

    result = getrlimit(RLIMIT_STACK, &rl);
    if (result == 0) {
        if (rl.rlim_cur < cpuStackSize) {
            rl.rlim_cur = cpuStackSize;
            result = setrlimit(RLIMIT_STACK, &rl);
            if (result != 0) {
                fprintf(stderr, "setrlimit returned result = %d\n", result);
            }
        }
    }
}

// Our CPU-side helper: allocate and fill GTable
void build_gtable(uint8_t **outX, uint8_t **outY) {
    increaseStackSizeCPU();

    size_t gsize = (size_t)COUNT_GTABLE_POINTS * (size_t)SIZE_GTABLE_POINT;
    uint8_t *gTableX = (uint8_t*)malloc(gsize);
    uint8_t *gTableY = (uint8_t*)malloc(gsize);

    if (!gTableX || !gTableY) {
        fprintf(stderr, "Failed to allocate GTable (%zu bytes)\n", gsize);
        exit(1);
    }

    printf("build_gtable: creating Secp256K1 context and GTable...\n");

    Secp256K1 *secp = new Secp256K1();
    secp->Init();

    for (int i = 0; i < NUM_GTABLE_CHUNK; i++) {
        for (int j = 0; j < NUM_GTABLE_VALUE - 1; j++) {
            int element = (i * NUM_GTABLE_VALUE) + j;
            Point p = secp->GTable[element];
            for (int b = 0; b < 32; b++) {
                gTableX[(element * SIZE_GTABLE_POINT) + b] = p.x.GetByte64(b);
                gTableY[(element * SIZE_GTABLE_POINT) + b] = p.y.GetByte64(b);
            }
        }
    }

    printf("build_gtable: finished\n");

    delete secp;

    *outX = gTableX;
    *outY = gTableY;
}
