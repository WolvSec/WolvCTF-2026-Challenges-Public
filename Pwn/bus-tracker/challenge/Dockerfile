# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
FROM ubuntu:22.04@sha256:0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY vuln.c /build/vuln.c
RUN gcc /build/vuln.c -no-pie -z execstack -z now -fno-stack-protector -w -static -o /build/chal

FROM scratch AS chroot
COPY --from=build /build/chal /home/user/chal
COPY flag.txt /home/user/flag.txt

FROM gcr.io/kctf-docker/challenge@sha256:738102f3144fd9cd0858b44d4f30f8f94bc73881be44aa8a2d13eee2099b9375

COPY --from=chroot / /chroot

COPY nsjail.cfg /home/user/

CMD ["sh", "-c", "kctf_setup && exec kctf_drop_privs socat TCP-LISTEN:1337,reuseaddr,fork EXEC:'kctf_pow nsjail --config /home/user/nsjail.cfg -- /home/user/chal'"]
