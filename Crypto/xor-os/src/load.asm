;load the next 0x1000 bytes at address 0x8000

ld_next:
    mov bx, 0x8000
    mov al, 8
    mov cx, [0x7ff0]
    add dword [0x7ff0], 8
    mov dl, 0x80 ; drive
    mov ah, 0x02 ; read
    mov ch, 0x00 ; cylinder 0
    mov dh, 0x00 ; head 0
    int 0x13
    ret 