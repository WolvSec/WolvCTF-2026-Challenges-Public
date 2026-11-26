// no-open-door — WolvCTF 2026 pwn (seccomp ORW)
// "sandbox rental unit": open/openat/execve/execveat are KILLed by seccomp,
// but openat2 (437) was left in the allowlist. Intended bypass:
// ROP an openat2 + read + write chain to leak /flag.
#include <stdio.h>
#include <unistd.h>
#include <stddef.h>
#include <sys/prctl.h>
#include <linux/seccomp.h>
#include <linux/filter.h>
#include <linux/audit.h>

static ssize_t read_full(int fd, void *buf, size_t length) {
    size_t total = 0;
    while (total < length) {
        ssize_t n = read(fd, (char *)buf + total, length - total);
        if (n <= 0) return -1;
        total += (size_t)n;
    }
    return (ssize_t)total;
}

// ponytail: plant `pop r10; ret` — the openat2 size arg needs r10, and a clean
// pop r10 gadget is often absent from static glibc. Guarantees the intended path.
__attribute__((used)) void g10(void) { asm volatile("pop %r10; ret"); }

// Preserve openat2's returned fd for the following read without assuming fd 3.
__attribute__((used, naked)) void fd_to_rdi(void) { asm volatile("xchg %rax, %rdi; ret"); }

// ponytail: tiny allow/kill macro keeps the BPF array short.
// if nr == (x): fall through to RET ALLOW; else skip it.
#define ALLOW(x) \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (x), 0, 1), \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)

void install_filter(void) {
    struct sock_filter filter[] = {
        // validate arch (anti-x32 / anti-ABI-confusion), else kill.
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        // load syscall number.
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        // ---- allowlist ----
        ALLOW(0),    // read
        ALLOW(1),    // write
        ALLOW(437),  // openat2  <-- ponytail: intended bug, forgot to block it
        ALLOW(9),    // mmap
        ALLOW(231),  // exit_group
        ALLOW(12),   // brk
        ALLOW(15),   // rt_sigreturn
        ALLOW(3),    // close
        ALLOW(8),    // lseek
        // everything else (open=2, openat=257, execve=59, execveat=322, ...) dies.
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
    };
    struct sock_fprog prog = {
        .len = (unsigned short)(sizeof(filter) / sizeof(filter[0])),
        .filter = filter,
    };
    // drop the ability to gain privs, then lock in the filter.
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0 ||
        prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) < 0)
        _exit(1);
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    puts("sandbox rental unit. no exec, no open.");
    install_filter();
    char buf[64];
    if (read_full(0, buf, 0x200) != 0x200) return 1;  // ponytail: classic overflow, 0x200 into a 64-byte buf
    return 0;
}
