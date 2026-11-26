FROM alpine:3.22 AS build
RUN apk add --no-cache build-base
WORKDIR /src
COPY src/time_capsule.c .
RUN mkdir -p /out && gcc -std=c11 -O2 -s -static -fno-ident \
    -fno-asynchronous-unwind-tables -fno-unwind-tables -fno-stack-protector \
    -no-pie -Wl,--build-id=none time_capsule.c -o /out/time_capsule

FROM scratch AS artifact
COPY --from=build /out/time_capsule /time_capsule
