# Build the Motor City Hotwire firmware. Verify the final ELF with
# solution/rev_run.py after any toolchain update; it uses fixed addresses.
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc-arm-none-eabi=15:13.2.rel1-2 binutils-arm-none-eabi \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /chal
COPY challenge/src/ /chal/challenge/src/
RUN arm-none-eabi-gcc -mthumb -mcpu=cortex-m4 -O2 -ffreestanding -nostdlib \
        -Wl,-e,main -Wl,--gc-sections -ffunction-sections \
        -o /tmp/ecu64.elf challenge/src/ecu64.c challenge/src/arm_main.c challenge/src/freestanding.c \
    && arm-none-eabi-strip /tmp/ecu64.elf -o /chal/firmware.bin
