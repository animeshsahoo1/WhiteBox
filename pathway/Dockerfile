# ============================================================
# PATHWAY SERVICE: Multi-stage build for optimized caching
# Build context: pathway/
# ============================================================

# ARG for base image - can be overridden at build time
ARG BASE_IMAGE=pathwaycom/pathway:latest

FROM ${BASE_IMAGE} AS pathway-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBUG=false
ENV PYTHONPATH=/app

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ============================================================
# DEPS STAGE: Install Python dependencies (cached layer)
# ============================================================
FROM pathway-base AS deps

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# FINAL: Production image
# ============================================================
FROM deps AS final

# Create required directories
RUN mkdir -p /app/reports/fundamental /app/reports/market /app/reports/news \
    /app/reports/sentiment /app/reports/facilitator /app/reports/debate \
    /app/pathway_state /app/knowledge_base

# Copy application code
COPY . .

EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["python", "-m", "uvicorn", "api.fastapi_server:app", "--host", "0.0.0.0", "--port", "8000"]