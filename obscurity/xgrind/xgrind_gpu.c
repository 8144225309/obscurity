// xgrind_gpu.c - GPU-based secp256k1 pubkey encoder

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <inttypes.h>
#include <sys/stat.h>

#ifdef __cplusplus
extern "C" {
#endif

int gpu_init(const uint8_t *gTableXCPU, const uint8_t *gTableYCPU);
void gpu_shutdown(void);

int gpu_search_batch(uint32_t       target_32bit,
                     const uint8_t *priv32_array,
                     int            batch_size,
                     int           *match_index_out,
                     uint8_t        pub_out[33],
                     uint64_t      *attempts_out);

#ifdef __cplusplus
}
#endif

void build_gtable(uint8_t **outX, uint8_t **outY);

#define GPU_BATCH_SIZE 16384

static void bytes_to_hex(const unsigned char *in, size_t len, char *out) {
    static const char *hex = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        out[2*i]     = hex[in[i] >> 4];
        out[2*i + 1] = hex[in[i] & 0x0f];
    }
    out[2*len] = '\0';
}

static int hex_to_bytes(const char *hex, unsigned char *out, size_t out_len) {
    size_t len = strlen(hex);
    if (len != out_len * 2) return 0;
    for (size_t i = 0; i < out_len; i++) {
        char c1 = hex[2*i];
        char c2 = hex[2*i + 1];
        int v1 = (c1 >= '0' && c1 <= '9') ? c1 - '0' :
                 (c1 >= 'a' && c1 <= 'f') ? c1 - 'a' + 10 :
                 (c1 >= 'A' && c1 <= 'F') ? c1 - 'A' + 10 : -1;
        int v2 = (c2 >= '0' && c2 <= '9') ? c2 - '0' :
                 (c2 >= 'a' && c2 <= 'f') ? c2 - 'a' + 10 :
                 (c2 >= 'A' && c2 <= 'F') ? c2 - 'A' + 10 : -1;
        if (v1 < 0 || v2 < 0) return 0;
        out[i] = (unsigned char)((v1 << 4) | v2);
    }
    return 1;
}

typedef struct {
    uint64_t s[2];
} xorshift128plus_state;

static inline uint64_t xorshift128plus_next(xorshift128plus_state *st) {
    uint64_t x = st->s[0];
    uint64_t const y = st->s[1];
    st->s[0] = y;
    x ^= x << 23;
    x ^= x >> 17;
    x ^= y ^ (y >> 26);
    st->s[1] = x;
    return x + y;
}

static int rng_init_seed(xorshift128plus_state *st, int fd) {
    if (read(fd, st->s, sizeof(st->s)) != (ssize_t)sizeof(st->s)) {
        perror("read /dev/urandom");
        return 0;
    }
    if (st->s[0] == 0 && st->s[1] == 0) {
        st->s[0] = 0x123456789abcdef0ULL;
        st->s[1] = 0x0fedcba987654321ULL;
    }
    return 1;
}

static inline void rng_fill32(xorshift128plus_state *st, unsigned char out[32]) {
    uint64_t *out64 = (uint64_t *)out;
    out64[0] = xorshift128plus_next(st);
    out64[1] = xorshift128plus_next(st);
    out64[2] = xorshift128plus_next(st);
    out64[3] = xorshift128plus_next(st);
}

static xorshift128plus_state g_rng;

static int init_rng_global(void) {
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) {
        perror("open /dev/urandom");
        return 0;
    }
    if (!rng_init_seed(&g_rng, fd)) {
        close(fd);
        return 0;
    }
    close(fd);
    return 1;
}

static uint32_t get_32_bits(const unsigned char *data, size_t len, size_t chunk_index) {
    size_t bit_pos    = chunk_index * 32;
    size_t total_bits = len * 8;

    if (bit_pos >= total_bits) return 0;

    uint32_t result = 0;

    // Extract 32 bits, one at a time (MSB-first)
    for (int i = 0; i < 32; i++) {
        size_t current_bit = bit_pos + i;
        if (current_bit >= total_bits) {
            // Pad with zeros if we run out of data
            result <<= (32 - i);
            break;
        }

        size_t byte_idx = current_bit / 8;
        // MSB first
        int bit_idx     = 7 - (current_bit % 8);

        unsigned char bit = (data[byte_idx] >> bit_idx) & 1;
        result = (result << 1) | bit;
    }

    return result;
}

static void put_32_bits(unsigned char *out, size_t total_bits,
                        size_t chunk_index, uint32_t v) {
    size_t bit_pos = chunk_index * 32;

    // Write 32 bits, one at a time (MSB-first)
    for (int i = 0; i < 32; i++) {
        size_t current_bit = bit_pos + i;
        if (current_bit >= total_bits) break;

        size_t byte_idx = current_bit / 8;
        int bit_idx     = 7 - (current_bit % 8);

        unsigned char bit = (v >> (31 - i)) & 1;

        if (bit) {
            out[byte_idx] |= (unsigned char)(1u << bit_idx);
        }
        // out must be zero-initialized (calloc), as before
    }
}

static int grind_for_32bit_value_gpu(uint32_t v,
                                     unsigned char priv_out[32],
                                     unsigned char pub_out[33],
                                     uint64_t *attempts_out) {
    unsigned char priv_batch[GPU_BATCH_SIZE][32];
    uint64_t attempts_total = 0;

    for (;;) {
        for (int i = 0; i < GPU_BATCH_SIZE; ++i) {
            rng_fill32(&g_rng, priv_batch[i]);
        }

        int match_index = -1;
        uint64_t attempts_batch = 0;

        int ok = gpu_search_batch(
            v,
            &priv_batch[0][0],
            GPU_BATCH_SIZE,
            &match_index,
            pub_out,
            &attempts_batch
        );

        if (!ok) {
            if (attempts_batch == 0) {
                fprintf(stderr, "GPU error in gpu_search_batch\n");
                return 0;
            }
            attempts_total += attempts_batch;
            continue;
        }

        attempts_total += attempts_batch;

        if (match_index < 0 || match_index >= GPU_BATCH_SIZE) {
            fprintf(stderr, "Invalid match index from GPU\n");
            return 0;
        }

        memcpy(priv_out, priv_batch[match_index], 32);
        if (attempts_out) *attempts_out = attempts_total;
        return 1;
    }
}

static int encode_file(const char *filename) {
    FILE *f = fopen(filename, "rb");
    if (!f) {
        perror("fopen input");
        return 1;
    }
    struct stat st;
    if (stat(filename, &st) != 0) {
        perror("stat");
        fclose(f);
        return 1;
    }
    size_t len = (size_t)st.st_size;
    unsigned char *data = NULL;
    if (len > 0) {
        data = (unsigned char *)malloc(len);
        if (!data) {
            fprintf(stderr, "malloc failed\n");
            fclose(f);
            return 1;
        }
        if (fread(data, 1, len, f) != len) {
            fprintf(stderr, "fread failed\n");
            free(data);
            fclose(f);
            return 1;
        }
    }
    fclose(f);

    char meta_name[4096];
    snprintf(meta_name, sizeof(meta_name), "%s.meta", filename);
    FILE *fmeta = fopen(meta_name, "w");
    if (!fmeta) {
        perror("fopen meta");
        free(data);
        return 1;
    }
    fprintf(fmeta, "%zu\n", len);
    fclose(fmeta);

    char pub_name[4096];
    char priv_name[4096];
    snprintf(pub_name,  sizeof(pub_name),  "%s.realpubkeys.txt", filename);
    snprintf(priv_name, sizeof(priv_name), "%s.privkeys.txt",    filename);

    FILE *fpub  = fopen(pub_name, "w");
    FILE *fpriv = fopen(priv_name, "w");
    if (!fpub || !fpriv) {
        perror("fopen pub/priv");
        if (fpub) fclose(fpub);
        if (fpriv) fclose(fpriv);
        free(data);
        return 1;
    }

    size_t total_bits = len * 8;
    size_t num_chunks = (total_bits + 31) / 32;

    printf("Encoding '%s' (%zu bytes) into %zu pubkeys\n",
           filename, len, num_chunks);
    printf("Using GPU batches of %d keys\n", GPU_BATCH_SIZE);

    unsigned char priv[32];
    unsigned char pub[33];
    uint64_t attempts_sum = 0;

    for (size_t i = 0; i < num_chunks; i++) {
        uint32_t v = get_32_bits(data, len, i);

        if ((i & 15) == 0) {
            printf("Progress: %zu/%zu (%.1f%%)...\r",
                   i, num_chunks, 100.0 * i / num_chunks);
            fflush(stdout);
        }

        uint64_t attempts = 0;
        if (!grind_for_32bit_value_gpu(v, priv, pub, &attempts)) {
            fprintf(stderr, "\nGPU grinding failed\n");
            fclose(fpub);
            fclose(fpriv);
            free(data);
            return 1;
        }

        char priv_hex[65];
        char pub_hex[67];
        bytes_to_hex(priv, 32, priv_hex);
        bytes_to_hex(pub,  33, pub_hex);

        fprintf(fpriv, "%s\n", priv_hex);
        fprintf(fpub,  "%s\n", pub_hex);

        attempts_sum += attempts;
    }

    printf("\nProgress: %zu/%zu (100.0%%)    \n", num_chunks, num_chunks);

    fclose(fpub);
    fclose(fpriv);
    free(data);

    printf("\nCompleted!\n");
    printf("Pubkeys: %s\n",  pub_name);
    printf("Privkeys: %s\n", priv_name);
    printf("Metadata: %s\n", meta_name);

    double avg = (double)attempts_sum / (double)num_chunks;
    printf("Avg attempts: %.1f (expected ~4294967296)\n", avg);

    return 0;
}

static inline uint32_t extract_32bit_from_serialized(const unsigned char *pub_ser) {
    // pub_ser[1..4] are the top 32 bits of X, big-endian
    return ((uint32_t)pub_ser[1] << 24) |
           ((uint32_t)pub_ser[2] << 16) |
           ((uint32_t)pub_ser[3] << 8)  |
           (uint32_t)pub_ser[4];
}

static int decode_file(const char *base) {
    char meta_name[4096];
    snprintf(meta_name, sizeof(meta_name), "%s.meta", base);
    FILE *fmeta = fopen(meta_name, "r");
    if (!fmeta) {
        perror("fopen meta");
        return 1;
    }
    size_t original_size = 0;
    if (fscanf(fmeta, "%zu", &original_size) != 1) {
        fprintf(stderr, "Failed to read meta\n");
        fclose(fmeta);
        return 1;
    }
    fclose(fmeta);

    char pub_name[4096];
    snprintf(pub_name, sizeof(pub_name), "%s.realpubkeys.txt", base);
    FILE *fpub = fopen(pub_name, "r");
    if (!fpub) {
        perror("fopen pubkeys");
        return 1;
    }

    char out_name[4096];
    snprintf(out_name, sizeof(out_name), "%s-recon-real", base);
    FILE *fout = fopen(out_name, "wb");
    if (!fout) {
        perror("fopen output");
        fclose(fpub);
        return 1;
    }

    size_t total_bits = original_size * 8;
    size_t num_chunks = (total_bits + 31) / 32;

    unsigned char *out = NULL;
    if (original_size > 0) {
        out = (unsigned char *)calloc(1, original_size);
        if (!out) {
            fprintf(stderr, "calloc failed\n");
            fclose(fpub);
            fclose(fout);
            return 1;
        }
    }

    char line[4096];
    size_t chunk_idx = 0;

    while (chunk_idx < num_chunks && fgets(line, sizeof(line), fpub)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        char *nl = strchr(p, '\n');
        if (nl) *nl = '\0';
        if (*p == '\0') continue;

        unsigned char pub[33];
        if (!hex_to_bytes(p, pub, 33)) {
            fprintf(stderr, "Invalid pubkey hex on line %zu\n", chunk_idx + 1);
            free(out);
            fclose(fpub);
            fclose(fout);
            return 1;
        }

        uint32_t v = extract_32bit_from_serialized(pub);
        put_32_bits(out, total_bits, chunk_idx, v);
        chunk_idx++;
    }

    fclose(fpub);

    if (chunk_idx < num_chunks) {
        fprintf(stderr, "Warning: expected %zu chunks, read %zu\n",
                num_chunks, chunk_idx);
    }

    if (original_size > 0) {
        fwrite(out, 1, original_size, fout);
    }
    fclose(fout);
    free(out);

    printf("Reconstructed: %s\n", out_name);
    printf("Size: %zu bytes\n", original_size);

    return 0;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage:\n"
        "  %s encode <file>\n"
        "  %s decode <base_file>\n",
        prog, prog);
}

int main(int argc, char **argv) {
    if (argc != 3) {
        usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "encode") == 0) {
        if (!init_rng_global()) {
            fprintf(stderr, "Failed to init RNG\n");
            return 1;
        }

        uint8_t *gTableXCPU = NULL;
        uint8_t *gTableYCPU = NULL;
        build_gtable(&gTableXCPU, &gTableYCPU);

        if (!gpu_init(gTableXCPU, gTableYCPU)) {
            fprintf(stderr, "Failed to init GPU\n");
            free(gTableXCPU);
            free(gTableYCPU);
            return 1;
        }

        int ret = encode_file(argv[2]);

        gpu_shutdown();
        free(gTableXCPU);
        free(gTableYCPU);
        return ret;
    } else if (strcmp(argv[1], "decode") == 0) {
        return decode_file(argv[2]);
    } else {
        usage(argv[0]);
        return 1;
    }
}
