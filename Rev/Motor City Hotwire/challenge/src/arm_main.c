/* ARM Thumb target harness for proto_a.c — NO embedded answer.
 *
 * Earlier draft baked a test vector ("27 02 F2D1C5D1") into .rodata, leaking the
 * key to `strings`. This version embeds NOTHING precomputed: the seed is a fixed
 * ECU constant (that's fine — the seed is public, the ECU sends it), and the key
 * is read at runtime. For a static-binary challenge with no live service, we read
 * the submitted key from a known memory location the harness exposes, OR (simpler
 * for distribution) the challenge ships as: binary + a captured seed; solver
 * computes key offline. Here we keep a runtime read path so nothing is precomputed.
 *
 * The distributable artifact is the stripped ELF; the solver reverses derive_key,
 * computes key for the published seed, and we verify via the companion checker.
 */
#include <stdint.h>

void run_ecu(void);

/* Input is left EMPTY in the binary. A real deployment feeds the CAN frames in
 * at runtime. For the static challenge, the solver doesn't RUN this to win — they
 * reverse derive_key and compute the key. We still compile run_ecu in so the
 * algorithm + decrypt path are present and reachable in .text. */
static char inbuf[64];       /* zero-filled .bss, no answer embedded */
static int inpos = 0;
static char outbuf[256];
static int outpos = 0;

int uds_read_line(char *buf, int max){
    int n = 0;
    if (inbuf[inpos] == 0) return 0;
    while (inbuf[inpos] && inbuf[inpos] != '\n' && n < max - 1)
        buf[n++] = inbuf[inpos++];
    if (inbuf[inpos] == '\n') inpos++;
    buf[n] = 0;
    return n;
}
void uds_write(const char *s){ while (*s && outpos < 255) outbuf[outpos++] = *s++; }
void uds_write_hex(const uint8_t *b, int n){
    const char *h = "0123456789ABCDEF";
    for (int i = 0; i < n; i++){
        if (outpos < 254){ outbuf[outpos++] = h[b[i] >> 4]; outbuf[outpos++] = h[b[i] & 0xF]; }
        if (outpos < 255) outbuf[outpos++] = ' ';
    }
}
int main(void){ run_ecu(); return outbuf[0]; }
