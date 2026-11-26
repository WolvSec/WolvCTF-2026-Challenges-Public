#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vendor/mldsa/mldsa_native.h"

static FILE *trace_file;
static unsigned long rejected_count;
static unsigned long target_count;

void rejected_trace(const uint8_t *challenge, unsigned int poly,
                    unsigned int index, int32_t value) {
  if (rejected_count >= target_count) return;
  for (unsigned int i = 0; i < 32; ++i) fprintf(trace_file, "%02x", challenge[i]);
  fprintf(trace_file, " %u %u %d\n", poly, index, value);
  ++rejected_count;
}

static void must_write(const char *path, const void *buf, size_t len) {
  FILE *f = fopen(path, "wb");
  if (!f || fwrite(buf, 1, len, f) != len || fclose(f)) {
    perror(path);
    exit(1);
  }
}

static void random_bytes(void *buf, size_t len) {
  FILE *f = fopen("/dev/urandom", "rb");
  if (!f || fread(buf, 1, len, f) != len || fclose(f)) {
    perror("/dev/urandom");
    exit(1);
  }
}

int main(int argc, char **argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: %s output-prefix rejected-count\n", argv[0]);
    return 2;
  }
  unsigned long target = strtoul(argv[2], NULL, 10);
  if (!target) return 2;
  target_count = target;
  char path[1024];
  uint8_t seed[32], rnd[32], pk[MLDSA44_PUBLICKEYBYTES];
  uint8_t sk[MLDSA44_SECRETKEYBYTES], sig[MLDSA44_BYTES];
  uint8_t s1[4 * 256];
  const uint8_t message[] = "WolvCTF 2026: rejected telemetry";
  const uint8_t prefix[] = {0, 0}; /* Pure ML-DSA, empty context. */

  random_bytes(seed, sizeof(seed));
  if (PQCP_MLDSA_NATIVE_MLDSA44_keypair_internal(pk, sk, seed)) return 1;
  snprintf(path, sizeof(path), "%s/public.key", argv[1]);
  must_write(path, pk, sizeof(pk));

  /* FIPS 204 packs eight eta=2 coefficients into three bytes. */
  const uint8_t *packed = sk + 32 + 32 + 64;
  for (unsigned int p = 0; p < 4; ++p) {
    for (unsigned int block = 0; block < 32; ++block) {
      const uint8_t *a = packed + p * 96 + block * 3;
      uint8_t t[8] = {
          a[0] & 7, (a[0] >> 3) & 7,
          ((a[0] >> 6) | (a[1] << 2)) & 7,
          (a[1] >> 1) & 7, (a[1] >> 4) & 7,
          ((a[1] >> 7) | (a[2] << 1)) & 7,
          (a[2] >> 2) & 7, (a[2] >> 5) & 7};
      for (unsigned int k = 0; k < 8; ++k)
        s1[p * 256 + block * 8 + k] = 4 - t[k];
    }
  }
  snprintf(path, sizeof(path), "%s/s1.tmp", argv[1]);
  must_write(path, s1, sizeof(s1));
  snprintf(path, sizeof(path), "%s/rejected.log", argv[1]);
  trace_file = fopen(path, "w");
  if (!trace_file) { perror(path); return 1; }
  while (rejected_count < target) {
    random_bytes(rnd, sizeof(rnd));
    if (PQCP_MLDSA_NATIVE_MLDSA44_signature_internal(sig, message, sizeof(message) - 1,
                                   prefix, sizeof(prefix), rnd, sk, 0)) {
      fprintf(stderr, "signing failed\n");
      return 1;
    }
  }
  if (fclose(trace_file)) return 1;
  fprintf(stderr, "%lu rejected z candidates recorded\n", rejected_count);
  memset(sk, 0, sizeof(sk));
  memset(seed, 0, sizeof(seed));
  return 0;
}
