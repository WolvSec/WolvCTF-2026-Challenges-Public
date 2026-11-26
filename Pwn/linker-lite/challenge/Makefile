# ponytail: partial RELRO (gcc default) keeps the lazy PLT that dlresolve needs.
linker-lite: src/linker-lite.c
	gcc -O0 -fno-omit-frame-pointer -fcf-protection=none -fno-pie -fno-stack-protector -no-pie -Wl,-z,relro,-z,lazy,-z,noexecstack -o linker-lite src/linker-lite.c

clean:
	rm -f linker-lite
