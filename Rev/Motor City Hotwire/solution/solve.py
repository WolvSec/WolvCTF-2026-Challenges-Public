#!/usr/bin/env python3
"""
Reference solver - Motor City Immobilizer (WolvCTF).
Reconstructed from the challenge binary alone, following the intended solve:
  1. The ECU (UDS SecurityAccess) returns a fixed seed on 27 01 and, on
     27 02 <key>, streams SHA-256-CTR XOR an embedded ciphertext (decrypt-gated).
  2. The keystream mixes in (transform(key) XOR seed): the intended key zeroes
     that term, i.e. transform(key) == seed, so key = transform^-1(seed).
  3. transform is a 16-round invertible network whose S-box + per-round schedule
     are generated at init by an xorshift64* PRNG (Fisher-Yates). Rebuild that,
     invert the network, recover the key, then decrypt the flag offline.

Self-contained, stdlib only:   python3 solve.py firmware.bin
"""
import sys, struct, hashlib

M32=0xFFFFFFFF; M64=0xFFFFFFFFFFFFFFFF; NR=16
INIT_SEED=0xA5A5F00DC0DE1234; PRNG_MUL=0x2545F4914F6CDD1D
SEED=0x1A2B3C4D5E6F7788                 # the ECU's 27 01 seed response

# --- init: derive the S-box + per-round schedule exactly as the firmware does ---
_s=[INIT_SEED]
def _nxt():
    x=_s[0]; x^=(x>>12)&M64; x^=(x<<25)&M64; x^=(x>>27)&M64; x&=M64; _s[0]=x
    return (x*PRNG_MUL)&M64
def _derive():
    _s[0]=INIT_SEED
    sbox=list(range(256))
    for i in range(255,0,-1):
        j=(_nxt()&M32)%(i+1); sbox[i],sbox[j]=sbox[j],sbox[i]
    MW=[0]*NR;MF=[0]*NR;RK=[0]*NR;ADD=[0]*NR;ROT=[0]*NR;OP=[0]*NR
    for i in range(NR):
        MW[i]=(_nxt()&M32)|1; MF[i]=(_nxt()&M32)|1; RK[i]=_nxt()&M32
        ADD[i]=_nxt()&M32; ROT[i]=((_nxt()&M32)%31)+1; OP[i]=_nxt()&1
    return sbox,MW,MF,RK,ADD,ROT,OP
SBOX,MW,MF,RK,ADD,ROT,OP=_derive()
MWINV=[pow(w,-1,1<<32) for w in MW]

def _rotl(x,r): return ((x<<r)|(x>>(32-r)))&M32
def _sub(x):    return struct.unpack("<I",bytes(SBOX[c] for c in struct.pack("<I",x&M32)))[0]
def _F(h,i):
    x=(h*MF[i])&M32; x=_sub(x); x=_rotl(x,ROT[i]); x=(x+ADD[i])&M32; x^=RK[i]; return x&M32
def transform(b):
    L=(b>>32)&M32; R=b&M32
    for i in range(NR):
        L=(L*MW[i])&M32
        if OP[i]==0: L^=_F(R,i)
        else:        R^=_F(L,i)
        L,R=R,L
    return ((L<<32)|R)&M64
def transform_inv(b):
    L=(b>>32)&M32; R=b&M32
    for i in reversed(range(NR)):
        L,R=R,L
        if OP[i]==0: L^=_F(R,i)
        else:        R^=_F(L,i)
        L=(L*MWINV[i])&M32
    return ((L<<32)|R)&M64

def keystream(key,n):
    lo=(transform(key)^SEED)&M64; hi=key&M64; out=bytearray(); c=0
    while len(out)<n:
        out+=hashlib.sha256(struct.pack("<QQI",lo,hi,c)).digest(); c+=1
    return bytes(out[:n])

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "firmware.bin"
    key=transform_inv(SEED)
    assert transform(key)==SEED
    print("recovered key : 0x%016X   (send: 27 02 %016X)"%(key,key))
    data=open(path,"rb").read()
    ks=keystream(key,128)
    needle=bytes(a^b for a,b in zip(ks[:5], b"wctf{"))   # locate ciphertext in .rodata
    i=data.find(needle)
    if i<0: print("flag ciphertext not found in binary",file=sys.stderr); sys.exit(1)
    pt=bytes(a^b for a,b in zip(data[i:i+128], ks))
    print("flag          :", pt[:pt.index(b"}")+1].decode())

if __name__=="__main__": main()
