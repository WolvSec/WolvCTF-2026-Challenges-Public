#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

char flag[256];

void loadFlag() {
    FILE *f = fopen("flag.txt", "r");
    if (f == NULL) {
        puts("flag.txt missing");
        exit(1);
    }
    fgets(flag, sizeof(flag), f);
    fclose(f);
}

void feedbackKiosk() {
    char buf[256];
    memset(buf, 0, sizeof(buf));
    puts("=== Dining Hall Feedback Kiosk ===");
    puts("Leave your comment: ");
    read(0, buf, sizeof(buf) - 1);
    printf("Thanks for your comment: ");
    printf(buf);
    putchar('\n');
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stdin, NULL, _IONBF, 0);
    loadFlag();
    feedbackKiosk();
    return 0;
}
