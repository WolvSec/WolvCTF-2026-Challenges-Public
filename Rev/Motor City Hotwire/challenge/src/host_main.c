/* Host harness for proto_a.c — maps the freestanding I/O shims to stdio so we
 * can validate the C algorithm matches the Python model before targeting ARM. */
#include <stdio.h>
#include <string.h>

int uds_read_line(char *buf, int max){
    if (!fgets(buf, max, stdin)) return 0;
    return (int)strlen(buf);
}
void uds_write(const char *s){ fputs(s, stdout); }
void uds_write_hex(const unsigned char *b, int n){
    for (int i=0;i<n;i++) printf("%02X ", b[i]);
}
void run_ecu(void);
int main(void){ run_ecu(); return 0; }
