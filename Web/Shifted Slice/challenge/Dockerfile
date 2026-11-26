FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLAG_FILE=/flag \
    COOKIE_SECURE=1 \
    BIND_HOST=127.0.0.1 \
    PORT=8081

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx-light \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin app
WORKDIR /app
COPY app.py /app/app.py
COPY nginx.conf run.sh /app/
COPY --chown=10001:10001 flag.txt /flag
RUN chmod 0400 /flag && chmod 0555 /app/run.sh
USER 10001:10001

EXPOSE 8080
CMD ["/app/run.sh"]
