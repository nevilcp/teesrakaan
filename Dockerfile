FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    # Requires a trusted proxy in front; lets the rate limiter see client IPs.
    FORWARDED_ALLOW_IPS=*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py analyzer.py calc.py ratelimit.py sarvam.py ./
COPY static ./static

RUN useradd --system --no-create-home --uid 10001 app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=2)"]

# Shell form expands $PORT; exec keeps uvicorn as PID 1.
CMD exec uvicorn app:app --host 0.0.0.0 --port "$PORT"
