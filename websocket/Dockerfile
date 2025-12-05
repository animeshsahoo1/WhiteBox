# ============================================================
# WEBSOCKET SERVICE: Multi-stage build for optimized caching
# Build context: websocket/
# ============================================================

# ARG for base image - can be overridden at build time
ARG BASE_IMAGE=python:3.11-slim

FROM ${BASE_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBUG=false
ENV PYTHONPATH=/code

WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ============================================================
# DEPS STAGE: Install Python dependencies (cached layer)
# ============================================================
FROM base AS deps

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# FINAL: Production image (uses volume mount for code)
# ============================================================
FROM deps AS final

EXPOSE 8001

# Default command (overridden in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]