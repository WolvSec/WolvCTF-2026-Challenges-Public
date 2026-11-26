FROM eclipse-temurin:21.0.9_10-jdk-jammy@sha256:41c8a28993a03b5dd042ce1afc7973c9a98bfbbbd6336eb1e32e673b1718d99c

RUN apt-get update && apt-get install -y --no-install-recommends nginx-core \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin app
WORKDIR /app
COPY SplitDirectory.java nginx.conf run.sh /app/
RUN javac --release 21 SplitDirectory.java
COPY --chown=10001:10001 flag.txt /flag
RUN chmod 0400 /flag && chmod 0555 /app/run.sh && ln -sf /dev/stderr /var/log/nginx/error.log
USER 10001:10001
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=50 -XX:ActiveProcessorCount=2"
EXPOSE 8080
CMD ["/app/run.sh"]
