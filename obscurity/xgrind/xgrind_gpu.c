#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <inttypes.h>

#ifdef __cplusplus
extern "C" {
#endif
int gpu_init(const uint8_t *gTableXCPU, const uint8_t *gTableYCPU);
void gpu_shutdown(void);
int gpu_search_batch(uint32_t target, uint32_t mask, const uint8_t *priv, int batch, int *idx, uint8_t pub[33], uint64_t *att);
#ifdef __cplusplus
}
#endif

void build_gtable(uint8_t **outX, uint8_t **outY);
#define GPU_BATCH_SIZE 16384

static void bytes_to_hex(const unsigned char *in, size_t len, char *out) {
    static const char *hex = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        out[2*i] = hex[in[i] >> 4];
        out[2*i+1] = hex[in[i] & 0x0f];
    }
    out[2*len] = 0;
}

typedef struct { uint64_t s[2]; } xorshift128plus_state;
static xorshift128plus_state g_rng;

static inline uint64_t xorshift128plus_next(xorshift128plus_state *st) {
    uint64_t x = st->s[0], y = st->s[1];
    st->s[0] = y;
    x ^= x << 23; x ^= x >> 17; x ^= y ^ (y >> 26);
    st->s[1] = x;
    return x + y;
}

static int init_rng_global(void) {
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) return 0;
    if (read(fd, g_rng.s, 16) != 16) { close(fd); return 0; }
    if (g_rng.s[0] == 0 && g_rng.s[1] == 0) g_rng.s[0] = 1;
    close(fd);
    return 1;
}

static int grind_for_32bit_value_gpu(uint32_t v, uint32_t mask, unsigned char priv_out[32], unsigned char pub_out[33], uint64_t *attempts_out) {
    unsigned char priv_batch[GPU_BATCH_SIZE][32];
    uint64_t attempts_total = 0;
    for (;;) {
        for (int i = 0; i < GPU_BATCH_SIZE; ++i) {
            uint64_t *p = (uint64_t*)priv_batch[i];
            p[0] = xorshift128plus_next(&g_rng); p[1] = xorshift128plus_next(&g_rng);
            p[2] = xorshift128plus_next(&g_rng); p[3] = xorshift128plus_next(&g_rng);
        }
        int match_idx = -1;
        uint64_t attempts_batch = 0;
        int ok = gpu_search_batch(v, mask, &priv_batch[0][0], GPU_BATCH_SIZE, &match_idx, pub_out, &attempts_batch);
        attempts_total += attempts_batch;
        if (ok && match_idx >= 0 && match_idx < GPU_BATCH_SIZE) {
            memcpy(priv_out, priv_batch[match_idx], 32);
            if (attempts_out) *attempts_out = attempts_total;
            return 1;
        }
    }
}

static int grind_stream_mode(int bits) {
    if (!init_rng_global()) return 1;
    uint8_t *gX = NULL, *gY = NULL;
    build_gtable(&gX, &gY);
    if (!gpu_init(gX, gY)) { free(gX); free(gY); return 1; }

    uint32_t mask = 0xFFFFFFFF;
    if (bits < 32 && bits > 0) mask = (uint32_t)((0xFFFFFFFFULL << (32 - bits)) & 0xFFFFFFFF);
    
    // Unbuffered output for python
    setvbuf(stdout, NULL, _IONBF, 0);
    // Print to stderr so Python doesn't parse it as a key
    fprintf(stderr, "Grind Stream Started. Bits: %d, Mask: %08X\n", bits, mask);

    unsigned char priv[32], pub[33];
    char priv_hex[65], pub_hex[67], line[256];

    while (fgets(line, sizeof(line), stdin)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '\0' || *p == '\n') continue;
        if (!strncmp(p, "quit", 4) || !strncmp(p, "exit", 4)) break;
        if (!strncmp(p, "0x", 2)) p += 2;

        uint32_t target = (uint32_t)strtoul(p, NULL, 16);
        uint64_t attempts = 0;
        
        if (grind_for_32bit_value_gpu(target, mask, priv, pub, &attempts)) {
            bytes_to_hex(priv, 32, priv_hex);
            bytes_to_hex(pub, 33, pub_hex);
            printf("%s %s %" PRIu64 "\n", priv_hex, pub_hex, attempts);
        }
    }
    gpu_shutdown();
    free(gX); free(gY);
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "grind_stream")) {
        int bits = 32;
        if (argc >= 3) bits = atoi(argv[2]);
        if (bits < 1 || bits > 32) bits = 32;
        return grind_stream_mode(bits);
    }
    fprintf(stderr, "Usage: %s grind_stream [bits]\n", argv[0]);
    return 1;
}
