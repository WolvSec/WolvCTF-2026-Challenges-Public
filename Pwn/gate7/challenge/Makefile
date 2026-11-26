gate7: src/gate7.c
	gcc -O0 -fno-omit-frame-pointer -fcf-protection=none -fno-pie -fno-stack-protector -no-pie -Wno-stringop-overflow -Wl,-z,relro,-z,lazy,-z,noexecstack -o gate7 src/gate7.c

clean:
	rm -f gate7
