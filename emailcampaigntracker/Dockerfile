# Multi-stage build for optimized image size
# Build context: from emailcampaigntracker/ directory
# Usage: cd emailcampaigntracker && docker build -t emailcampaign-api:latest .

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies to /build/wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /build/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels requirements.txt

# Copy application code (build context from emailcampaigntracker directory)
COPY app ./app
COPY database ./database
COPY alembic ./alembic
COPY alembic.ini .

# Create non-root user for security
RUN groupadd -g 1000 appuser && \
    useradd -m -u 1000 -g 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/status || exit 1

# Expose API port
EXPOSE 8000

# Run Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
