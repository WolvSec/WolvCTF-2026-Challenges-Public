FROM ubuntu:22.04

# Run as root to ensure tcpdump works properly
USER root
WORKDIR /capture

RUN apt update && apt install -y python3 steghide tcpdump wget

COPY capture.sh .

CMD ["./capture.sh"]
