# ── BiblioRegister — Cloud Run Container ─────────────────────────
FROM python:3.11-slim

# Prevent Python from writing .pyc and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run injects PORT (default 8080)
ENV PORT=8080

# Run with Gunicorn (production WSGI server)
# Low-resource config: 1 worker, 2 threads, for small/medium traffic
CMD exec gunicorn \
    --bind :$PORT \
    --workers 1 \
    --threads 2 \
    --worker-class gthread \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level warning \
    "app:create_app()"
