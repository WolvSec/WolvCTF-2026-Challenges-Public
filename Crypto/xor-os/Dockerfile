FROM ubuntu:22.04

RUN apt update 
RUN apt install -y python3 build-essential nasm libc6-dev-i386

RUN mkdir /chal
COPY . /chal/

WORKDIR /chal
RUN make