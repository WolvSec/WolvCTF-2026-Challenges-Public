#include <stdio.h>
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

// linker-lite — "plugin loader" that reads an oversized plugin blob.

void load_plugin() {
    char buf[64];
    if (read_full(0, buf, 256) != 256) return;
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    puts("plugin-loader v0.1");
    puts("send plugin blob:");
    load_plugin();
    return 0;
}

// ponytail: plant arg-control gadget (modern gcc/glibc dropped __libc_csu_init);
// supports the intended ret2dlresolve solve; no address is printed initially.
__attribute__((used)) void g(void){ asm volatile("pop %rdi; pop %rsi; pop %rdx; ret"); }
