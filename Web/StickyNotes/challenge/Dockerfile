FROM python:3.12.15-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py flag.txt ./
ENV FLAG_FILE=/app/flag.txt
EXPOSE 8080
# Keep one worker because notes are stored in process memory. Cloud Run sets PORT.
USER 10001
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 app:app"]
