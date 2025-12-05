# ============================================================
# STREAMING SERVICE: Multi-stage build for optimized caching
# Build context: streaming/
# ============================================================

# ARG for base image - can be overridden at build time
ARG BASE_IMAGE=python:3.11-slim

FROM ${BASE_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBUG=false
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    gcc \
    g++ \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ============================================================
# DEPS STAGE: Install Python dependencies (cached layer)
# ============================================================
FROM base AS deps

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# FINAL: Production image
# ============================================================
FROM deps AS final

# Copy application code
COPY . .

# Default command (overridden in docker-compose per producer)
CMD ["python", "producers/market_data_producer.py"]