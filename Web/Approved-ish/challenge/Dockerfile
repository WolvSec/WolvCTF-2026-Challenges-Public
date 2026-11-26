FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLAG_FILE=/flag.txt \
    REQUIRE_FLAG_FILE=1 \
    COOKIE_SECURE=1 \
    DATABASE=/data/approved.sqlite3

RUN useradd --system --uid 10001 --no-create-home app \
 && mkdir -p /data && chown app:app /data && chmod 0700 /data

WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY static ./static
COPY templates ./templates
COPY flag.txt /flag.txt
RUN chmod 0444 /flag.txt

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status != 200)"]

# --preload creates the schema once before forking the workers.
CMD ["gunicorn", "--preload", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "4", \
     "--timeout", "30", "--worker-tmp-dir", "/data", "--access-logfile", "-", "app:create_app()"]
