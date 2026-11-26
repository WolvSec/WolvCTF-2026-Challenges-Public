/* ECU SecurityAccess (ARCH-4, 64-bit, ARM Thumb). AI-hardened keygen.
 *
 * UDS 0x27:  27 01 -> 67 01 <seed:8>            (seed is public, ECU emits it)
 *            27 02 <key:8> -> decrypt-gated flag (NO compare, no stored key/flag)
 *
 * keystream block = SHA256( LE64(transform(key)^SEED) || LE64(key) || LE32(ctr) );
 * flag encrypted (at build) under keystream(a) where a = transform^-1(SEED). Output
 * is the flag iff (transform(key)^SEED, key) == (0, a) iff key == a. The solver
 * reconstructs `transform` from this firmware, inverts it, and computes
 * a = transform^-1(SEED): the standard UDS "key derived from seed" relation, made
 * visible because the firmware computes transform(key)^SEED on the live path. The
 * emitted seed does NOT decrypt the flag (correct keystream hides the secret a).
 *
 * Hardening vs a plain readable Feistel:
 *   - NO static crypto constants: the S-box (a real permutation) and every
 *     per-round multiplier / round key / add const / rotate / structure bit are
 *     DERIVED at init from one 64-bit seed via xorshift64*. Nothing to grep.
 *   - NOT a textbook Feistel: per-round whitening multiply + a per-round OP bit
 *     flipping which half is mixed -> "recognise Feistel, reverse rounds" fails.
 *   - Decrypt-gated: wrong key -> indistinguishable garbage; no compare to patch.
 *   - SHA-256 on the key->flag path -> symbolic execution path-explodes.
 *   - 64-bit key -> 2^64 brute (~585 yrs @1e9/s).
 *   - Flag material = transform(transform(SEED)) is never emitted and never
 *     computed by the firmware, so the emitted seed does NOT decrypt the flag
 *     (the ARCH-3/v32 leak is closed).
 */
#include <stdint.h>

#define NROUNDS 16
#define INIT_SEED   0xA5A5F00DC0DE1234ULL
#define PRNG_MUL    0x2545F4914F6CDD1DULL
static const uint64_t SEED_FIXED = 0x1A2B3C4D5E6F7788ULL;

/* ---- derived schedule (filled by derive(); nothing precomputed in .rodata) ---- */
static uint8_t  SBOX[256];
static uint32_t MW[NROUNDS], MF[NROUNDS], RK[NROUNDS], ADDc[NROUNDS], ROTa[NROUNDS];
static uint8_t  OP[NROUNDS];

static uint64_t prng_s;
static uint64_t prng_next(void){
    uint64_t x = prng_s;
    x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
    prng_s = x;
    return x * PRNG_MUL;
}
static void derive(void){
    prng_s = INIT_SEED;
    for (int i = 0; i < 256; i++) SBOX[i] = (uint8_t)i;
    for (int i = 255; i > 0; i--){                 /* Fisher-Yates permutation */
        uint32_t j = (uint32_t)prng_next() % (uint32_t)(i + 1);  /* 32-bit UDIV */
        uint8_t t = SBOX[i]; SBOX[i] = SBOX[j]; SBOX[j] = t;
    }
    for (int i = 0; i < NROUNDS; i++){
        MW[i]   = (uint32_t)prng_next() | 1u;      /* odd -> invertible mod 2^32 */
        MF[i]   = (uint32_t)prng_next() | 1u;
        RK[i]   = (uint32_t)prng_next();
        ADDc[i] = (uint32_t)prng_next();
        ROTa[i] = ((uint32_t)prng_next() % 31u) + 1;
        OP[i]   = (uint8_t)(prng_next() & 1);
    }
}

static uint32_t rotl32(uint32_t x, int r){ return (x << r) | (x >> (32 - r)); }
static uint32_t subbytes32(uint32_t x){
    uint8_t b0 = SBOX[x & 0xFF], b1 = SBOX[(x >> 8) & 0xFF],
            b2 = SBOX[(x >> 16) & 0xFF], b3 = SBOX[(x >> 24) & 0xFF];
    return (uint32_t)b0 | ((uint32_t)b1 << 8) | ((uint32_t)b2 << 16) | ((uint32_t)b3 << 24);
}
static uint32_t F(uint32_t h, int i){
    uint32_t x = h * MF[i];
    x = subbytes32(x);
    x = rotl32(x, (int)ROTa[i]);
    x = x + ADDc[i];
    x ^= RK[i];
    return x;
}
static uint64_t transform(uint64_t blk){
    uint32_t L = (uint32_t)(blk >> 32), R = (uint32_t)blk;
    for (int i = 0; i < NROUNDS; i++){
        L = L * MW[i];                             /* whitening multiply */
        if (OP[i] == 0) L ^= F(R, i); else R ^= F(L, i);
        uint32_t t = L; L = R; R = t;              /* swap */
    }
    return ((uint64_t)L << 32) | R;
}

/* ---- SHA-256 (real; the symbolic-execution wall on the key->flag path) ---- */
typedef struct { uint32_t s[8]; uint64_t len; uint8_t buf[64]; int n; } sha_t;
static uint32_t ror(uint32_t x, int r){ return (x >> r) | (x << (32 - r)); }
static const uint32_t KC[64] = {0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
static void si(sha_t*c){c->s[0]=0x6a09e667;c->s[1]=0xbb67ae85;c->s[2]=0x3c6ef372;c->s[3]=0xa54ff53a;c->s[4]=0x510e527f;c->s[5]=0x9b05688c;c->s[6]=0x1f83d9ab;c->s[7]=0x5be0cd19;c->len=0;c->n=0;}
static void sbk(sha_t*c,const uint8_t*p){uint32_t w[64];for(int i=0;i<16;i++)w[i]=(p[i*4]<<24)|(p[i*4+1]<<16)|(p[i*4+2]<<8)|p[i*4+3];for(int i=16;i<64;i++){uint32_t a=ror(w[i-15],7)^ror(w[i-15],18)^(w[i-15]>>3),b=ror(w[i-2],17)^ror(w[i-2],19)^(w[i-2]>>10);w[i]=w[i-16]+a+w[i-7]+b;}uint32_t a=c->s[0],b=c->s[1],cc=c->s[2],d=c->s[3],e=c->s[4],f=c->s[5],g=c->s[6],h=c->s[7];for(int i=0;i<64;i++){uint32_t S1=ror(e,6)^ror(e,11)^ror(e,25),ch=(e&f)^((~e)&g),t1=h+S1+ch+KC[i]+w[i],S0=ror(a,2)^ror(a,13)^ror(a,22),mj=(a&b)^(a&cc)^(b&cc),t2=S0+mj;h=g;g=f;f=e;e=d+t1;d=cc;cc=b;b=a;a=t1+t2;}c->s[0]+=a;c->s[1]+=b;c->s[2]+=cc;c->s[3]+=d;c->s[4]+=e;c->s[5]+=f;c->s[6]+=g;c->s[7]+=h;}
static void su(sha_t*c,const uint8_t*p,int len){c->len+=len;while(len){int k=64-c->n;if(k>len)k=len;for(int i=0;i<k;i++)c->buf[c->n+i]=p[i];c->n+=k;p+=k;len-=k;if(c->n==64){sbk(c,c->buf);c->n=0;}}}
static void sf(sha_t*c,uint8_t*o){uint64_t b=c->len*8;uint8_t pad=0x80;su(c,&pad,1);uint8_t z=0;while(c->n!=56)su(c,&z,1);uint8_t L[8];for(int i=0;i<8;i++)L[i]=(uint8_t)(b>>(56-8*i));su(c,L,8);for(int i=0;i<8;i++){o[i*4]=c->s[i]>>24;o[i*4+1]=c->s[i]>>16;o[i*4+2]=c->s[i]>>8;o[i*4+3]=c->s[i];}}
static void sha256(const uint8_t*p,int n,uint8_t*o){sha_t c;si(&c);su(&c,p,n);sf(&c,o);}

/* ---- baked ciphertext: FLAG ^ keystream(transform(transform(SEED))) ---- */
static const uint8_t ENC_FLAG[]={0x21,0x89,0x0d,0xed,0x64,0xb7,0x68,0x34,0xf4,0xdc,0xe9,0x4c,0x51,0xe1,0x19,0xab,0x02,0x9d,0x12,0x3e,0xb4,0x5e,0x9a,0xf5,0x72,0x1c,0xee,0x87,0x98,0x84,0x63,0x10,0x4c,0x26,0x7c,0x34,0x8c,0x6c};
#define FLAG_LEN ((int)sizeof(ENC_FLAG))

/* keystream block = SHA256( LE64(transform(key)^SEED) || LE64(key) || LE32(ctr) ).
 * The transform(key)^SEED term is the (visible) seed->key relation: it vanishes
 * exactly when transform(key)==SEED, i.e. key == transform^-1(SEED). The key term
 * injects the secret answer into the correct keystream so the emitted seed cannot
 * decrypt the flag. */
static void decrypt_with(uint64_t key,char*out){
    uint64_t lo = transform(key) ^ SEED_FIXED;
    uint64_t hi = key;
    uint8_t blk[20];
    for(int i=0;i<8;i++) blk[i]=(uint8_t)(lo>>(8*i));
    for(int i=0;i<8;i++) blk[8+i]=(uint8_t)(hi>>(8*i));
    uint8_t ks[32]; uint32_t ctr=0; int left=0;
    for(int i=0;i<FLAG_LEN;i++){
        if(left==0){ blk[16]=(uint8_t)ctr; blk[17]=(uint8_t)(ctr>>8); blk[18]=(uint8_t)(ctr>>16); blk[19]=(uint8_t)(ctr>>24);
            sha256(blk,20,ks); ctr++; left=32; }
        out[i]=(char)(ENC_FLAG[i]^ks[32-left]); left--;
    }
    out[FLAG_LEN]=0;
}

int uds_read_line(char*buf,int max); void uds_write(const char*s); void uds_write_hex(const uint8_t*b,int n);
static int hv(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static int ph(const char*s,uint8_t*o,int m){int n=0,hi=-1;for(;*s&&n<m;s++){if(*s==' '||*s=='\t')continue;int v=hv(*s);if(v<0)break;if(hi<0)hi=v;else{o[n++]=(uint8_t)((hi<<4)|v);hi=-1;}}return n;}

void run_ecu(void){
    derive();
    char line[160]; uint8_t msg[80]; int seeded=0;
    while(uds_read_line(line,sizeof line)>0){
        int n=ph(line,msg,sizeof msg); if(n<2)continue;
        if(msg[0]==0x27&&msg[1]==0x01){
            uint64_t s=SEED_FIXED; uint8_t r[10]; r[0]=0x67; r[1]=0x01;
            for(int i=0;i<8;i++)r[2+i]=(uint8_t)(s>>(56-8*i));
            uds_write_hex(r,10); uds_write("\n"); seeded=1;
        } else if(msg[0]==0x27&&msg[1]==0x02&&n>=10&&seeded){
            uint64_t key=0; for(int i=0;i<8;i++)key=(key<<8)|msg[2+i];
            char out[FLAG_LEN+1]; decrypt_with(key,out);
            uds_write("67 02\n"); uds_write(out); uds_write("\n");
        } else { uds_write("7F 27 35\n"); }
    }
}

#ifdef SELFTEST
/* Not part of the shipped binary. Prints the derived schedule + transform() of a
 * few inputs so the Python model can confirm the C derivation matches exactly. */
#include <stdio.h>
int uds_read_line(char*b,int m){(void)b;(void)m;return 0;}
void uds_write(const char*s){(void)s;}
void uds_write_hex(const uint8_t*b,int n){(void)b;(void)n;}
int main(void){
    derive();
    printf("SBOX16:"); for(int i=0;i<16;i++)printf(" %02x",SBOX[i]); printf("\n");
    printf("SBOXsum:%d\n",({int s=0;for(int i=0;i<256;i++)s+=SBOX[i];s;}));
    for(int i=0;i<NROUNDS;i++)
        printf("R%02d MW=%08x MF=%08x RK=%08x ADD=%08x ROT=%u OP=%u\n",
               i,MW[i],MF[i],RK[i],ADDc[i],ROTa[i],OP[i]);
    uint64_t tv[4]={0x0ULL,0x1ULL,0x1A2B3C4D5E6F7788ULL,0xFFFFFFFFFFFFFFFFULL};
    for(int i=0;i<4;i++)printf("T(%016llx)=%016llx\n",
        (unsigned long long)tv[i],(unsigned long long)transform(tv[i]));
    return 0;
}
#endif
