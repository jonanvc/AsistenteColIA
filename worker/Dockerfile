# Worker Dockerfile - Celery Worker with Playwright
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy backend requirements (worker shares dependencies)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (worker needs access to models and services)
COPY backend/app /app/app

# Copy worker code
COPY worker /app/worker

# Set Python path
ENV PYTHONPATH=/app

# Run Celery worker
CMD ["celery", "-A", "worker.worker", "worker", "--loglevel=info", "--concurrency=2"]
