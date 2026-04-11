FROM python:3.11-slim

LABEL org.opencontainers.image.title="qtown-asset-pipeline"
LABEL org.opencontainers.image.description="Qtown Asset Pipeline — ComfyUI + S3/R2"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.110.0" \
        "uvicorn[standard]>=0.29.0" \
        "aiokafka>=0.10.0" \
        "httpx>=0.27.0" \
        "boto3>=1.34.0" \
        "pydantic>=2.6.0"

# Copy source
COPY asset_pipeline/ ./asset_pipeline/

# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8005

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

CMD ["uvicorn", "asset_pipeline.main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1"]
