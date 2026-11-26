CC = gcc
CFLAGS = -O2 -std=c11 -Wall -Wextra -Werror -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fPIE
LDFLAGS = -s -static-pie -Wl,-z,relro,-z,now,-z,noexecstack

all: deferred-receipt

deferred-receipt: src/deferred_receipt.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $<

clean:
	rm -f deferred-receipt
