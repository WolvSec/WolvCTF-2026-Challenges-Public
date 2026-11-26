#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

/* Register-override helper used by the self-checkout firmware.
   (Provides a convenient pop rdi ; ret sequence in .text.) */
__asm__(
"restock_helper:\n"
"    pop %rdi\n"
"    ret\n"
);

void managerOverride(long code) {
    // Keep the flag path dependent on the argument when control flow is hijacked.
    char path[] = "flag.txt";
    unsigned long key = (unsigned long)code ^ 0xC0FFEEUL;
    for (size_t i = 0; i < sizeof(path) - 1; i++)
        path[i] ^= (char)(key >> (8 * i));
    if (code != 0xC0FFEE) {
        puts("Invalid override code. Transaction not voided.");
        return;
    }
    char flag[256];
    FILE *f = fopen(path, "r");
    if (f == NULL) { puts("flag.txt missing"); exit(1); }
    fgets(flag, sizeof(flag), f);
    printf("Override accepted. %s", flag);
    exit(0);
}

void checkout() {
    char buf[64];
    puts("=== Blue Market Self-Checkout ===");
    puts("Scan an item (enter item code): ");
    read(0, buf, 256);
    puts("Item not recognized. Please see an attendant.");
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stdin, NULL, _IONBF, 0);
    checkout();
    return 0;
}
