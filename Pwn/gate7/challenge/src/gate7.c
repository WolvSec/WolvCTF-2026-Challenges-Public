#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>

static ssize_t read_full(int fd, void *buf, size_t length) {
    size_t total = 0;
    while (total < length) {
        ssize_t n = read(fd, (char *)buf + total, length - total);
        if (n <= 0) return -1;
        total += (size_t)n;
    }
    return (ssize_t)total;
}

// ponytail: planted gadget guarantees a pop rdi; ret exists without relying on libc.
__attribute__((used)) void gadget() { asm volatile("pop %rdi; ret"); }

void open_gate(unsigned long code) {
    if (code == 0xC0FFEE) {
        char flag[128];
        int fd = open("/flag", O_RDONLY); // ponytail: absolute path, no cwd guessing under jail chroot
        if (fd < 0) {
            perror("open /flag");
            _exit(1);
        }
        ssize_t n = read(fd, flag, sizeof(flag));
        close(fd);
        if (n < 0 || write(1, flag, (size_t)n) != n) {
            perror("read/write flag");
            _exit(1);
        }
        _exit(0);
    } else {
        puts("Access denied.");
    }
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    puts("Gate 7 keypad. Enter access code:");
    char buf[40];
    read_full(0, buf, 128); // ponytail: 128 into a 40-byte buffer is the intended overflow.
    return 0;
}
