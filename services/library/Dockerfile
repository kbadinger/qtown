FROM python:3.11-slim

LABEL org.opencontainers.image.title="qtown-library"
LABEL org.opencontainers.image.description="Qtown Library Service — full-text search and aggregation"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.110.0" \
        "uvicorn[standard]>=0.29.0" \
        "elasticsearch[async]>=8.13.0" \
        "aiokafka>=0.10.0" \
        "httpx>=0.27.0"

# Copy source
COPY library/ ./library/

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8004

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

CMD ["uvicorn", "library.main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "1"]
