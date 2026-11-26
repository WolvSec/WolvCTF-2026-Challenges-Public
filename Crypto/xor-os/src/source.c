char * data = \
"              _    __   __                                                   "\
"__      _____| |_ / _| / /                                                   "\
"\\ \\ /\\ / / __| __| |_ | |                                                    "\
" \\ V  V / (__| |_|  _< <                                                     "\
"  \\_/\\_/ \\___|\\__|_|  | |                                                    "\
" ____                  \\_\\__  _____ _           _____           _  _   ____  "\
"/ ___|  ___  _ __ ___ |___ / |_   _(_)_ __ ___ |___ /     _ __ | || | |  _ \\ "\
"\\___ \\ / _ \\| '_ ` _ \\  |_ \\   | | | | '_ ` _ \\  |_ \\    | '_ \\| || |_| | | |"\
" ___) | (_) | | | | | |___) |  | | | | | | | | |___) |   | |_) |__   _| |_| |"\
"|____/ \\___/|_| |_| |_|____/___|_| |_|_| |_| |_|____/____| .__/   |_| |____/ "\
"\\ \\                       |_____|                  |_____|_|                 "\
" | |                                                                         "\
"  > >                                                                        "\
" | |                                                                         "\
"/_/                                                                          "\
;

unsigned short * buf = (unsigned short *)0xb8000;
void set_char(int x, int y, char c);
int main(){
    for(int i = 0; data[i]; i++){
        int x = i % 77;
        int y = i / 77;
        set_char(x, y, data[i]);
    }
    
    while (1) {}
    return 0;
}
void set_char(int x, int y, char c){
    int index = y * 80 + x;
    unsigned short value = (unsigned short)c | 0x0f << 8; // character with white foreground and black background
    buf[index] = value;
}