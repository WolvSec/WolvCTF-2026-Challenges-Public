[bits 16]
[org 0x7c00]

; shell script nonsense
db 'qemu-system-x86_64 $0 -boot c -device loader,file=key.bin,addr=0x100000' ;'q' is a branch instruction and 'e' is the offset
db 0xa
db 'echo did ya solve it yet?'
db 0xa
db 'exit'
db 0xa

times 'e'+ 2-($-$$) db 0

; xor setup
mov dword [0x7ff0], 2
mov edi, 0x100000
mov edi, [edi]
and edi, 0xffff
add edi, 0x100000
mov esi, 0x100002
mov dword [0x7ff8], 0x200000


reload:
CALL ld_next
mov eax, 0x8000

next_round:
mov bl, [eax]
xor bl, [esi]
mov ecx, [0x7ff8]
mov [ecx], bl
add esi, 1


cmp esi, edi
jne no_reset
mov esi, 0x100002
no_reset:
add dword [0x7ff8], 1
cmp dword [0x7ff8], 0x206000
je boot
add ax, 1
cmp ax, 0x9000

je reload

jmp next_round

boot:
lgdt [gdt_descriptor]
cli
mov eax, cr0
or eax, 0x1
mov cr0, eax

CALL CODE_SEG:continue

%include "load.asm"
%include "gdt.asm"
continue:
[bits 32]
mov eax, 0x200000
jmp eax
times 510-($-$$) db 0x31
dw 0xaa55

