# ponytail: static + no-pie => every ROP gadget lives in the binary, no libc to ship.
no-open-door: src/no-open-door.c
	gcc -O0 -fno-omit-frame-pointer -fcf-protection=none -static -fno-pie -fno-stack-protector -no-pie -Wl,-z,relro,-z,lazy,-z,noexecstack -o no-open-door src/no-open-door.c

clean:
	rm -f no-open-door
