FROM --platform=linux/amd64 ubuntu:22.04@sha256:0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956 AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential make
COPY Makefile /build/Makefile
COPY src/no-open-door.c /build/src/no-open-door.c
WORKDIR /build
RUN make

FROM scratch AS chroot
COPY chal /home/user/chal
COPY flag.txt /flag

FROM --platform=linux/amd64 gcr.io/kctf-docker/challenge@sha256:738102f3144fd9cd0858b44d4f30f8f94bc73881be44aa8a2d13eee2099b9375
COPY --from=chroot / /chroot
COPY nsjail.cfg /home/user/nsjail.cfg
CMD kctf_setup && kctf_drop_privs socat TCP-LISTEN:1337,reuseaddr,fork EXEC:"kctf_pow nsjail --config /home/user/nsjail.cfg -- /home/user/chal"
