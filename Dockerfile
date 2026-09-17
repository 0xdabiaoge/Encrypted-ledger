# ==============================================================================
# Encrypted Ledger - Institutional Production Dockerfile
# Optimized for Python 3.11-slim, low footprint, high security, and container health checks.
# ==============================================================================
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/backend

# Install curl and ca-certificates for healthchecks and HTTPS requests
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Install dependencies first for optimal Docker layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 2. Copy backend source code & frontend dist bundle
COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/

# 3. Create data & log directories with seed config
RUN mkdir -p /app/data /app/logs /app/data/policy_archives
COPY data/universe.json /app/data/universe.json

# 4. Container Metadata & Expose Port
EXPOSE 8080

# 5. Integrated Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8080/api/v1/system/health || exit 1

# 6. Launch Application Entrypoint
CMD ["python", "backend/run.py"]
