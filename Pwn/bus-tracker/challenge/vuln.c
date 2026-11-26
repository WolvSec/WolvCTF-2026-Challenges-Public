#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void dispatcherOverride() {
    char flag[256];
    FILE *f = fopen("flag.txt", "r");
    if (f == NULL) {
        puts("flag.txt missing");
        exit(1);
    }
    fgets(flag, sizeof(flag), f);
    printf("%s", flag);
    exit(0);
}

void checkStopName() {
    char buf[64];
    puts("=== Bus Tracker 3000 ===");
    puts("Enter your stop name: ");
    read(0, buf, 256);
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stdin, NULL, _IONBF, 0);
    checkStopName();
    puts("Thanks for riding!");
    return 0;
}
