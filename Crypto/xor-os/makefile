chal.bin: .FORCE
	mkdir dist build
	cd src && nasm bootloader.asm -o ../build/boot.bin
	dd if=build/boot.bin of=build/chal.bin bs=512 count=1
	/usr/bin/gcc -m32 -c src/source.c -o build/source.o -ffreestanding -nostdlib -fno-builtin -fno-pie -static 

	ld -melf_i386 -T src/linker.ld build/source.o -o build/source.bin --oformat binary -static
	cat build/source.bin /lib32/libc.a > build/to_encrypt.bin
	python3 src/crypt.py build/to_encrypt.bin build/encrypted.bin build/key.bin

	cat build/encrypted.bin >> build/chal.bin
	chmod +x build/chal.bin
	cp build/chal.bin dist/chal.bin


solve: .FORCE
	dd if=chal.bin of=solve/encrypted.bin bs=512 skip=1
	cd solve && python3 decrypt_without_key.py
	
	dd if=chal.bin of=solve/boot_simple.bin bs=512 count=1
	
	cat solve/boot_simple.bin solve/decrypted.bin > solve/decrypted_full.bin

	dd if=/dev/zero bs=$$((0xffff)) count=1 of=solve/key.bin

	chmod +x solve/decrypted_full.bin
	cd solve && ./decrypted_full.bin

clean:
	rm -rf build/* dist/*

.FORCE: