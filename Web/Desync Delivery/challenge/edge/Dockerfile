FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin app
WORKDIR /app
COPY edge.py /app/edge.py
USER 10001:10001

EXPOSE 8081
CMD ["python", "/app/edge.py"]
