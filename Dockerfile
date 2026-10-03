# Production Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# Create unprivileged system user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

WORKDIR /home/appuser/app

# Install production dependencies only
COPY requirements/base.txt requirements/prod.txt ./requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy production application files (.dockerignore excludes dev/, tests/, _archive/)
COPY --chown=appuser:appgroup config/ ./config/
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup wsgi.py ./
COPY --chown=appuser:appgroup scripts/prod/start.sh ./scripts/prod/start.sh
RUN chmod +x ./scripts/prod/start.sh

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

ENTRYPOINT ["./scripts/prod/start.sh"]
