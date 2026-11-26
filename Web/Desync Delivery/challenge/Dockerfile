FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin app
WORKDIR /app
COPY gateway/server.py /app/gateway/server.py
COPY edge/edge.py /app/edge/edge.py
COPY backend/server.py backend/entrypoint.sh /app/backend/
COPY run.sh /app/run.sh
COPY --chown=10001:10001 flag.txt /flag
RUN chmod 0555 /app/run.sh /app/backend/entrypoint.sh && chmod 0400 /flag
USER 10001:10001

EXPOSE 8080
CMD ["/app/run.sh"]
