FROM pathwaycom/pathway:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy phase2 requirements and install Python dependencies
COPY phase2/requirements.txt /app/phase2/requirements.txt
RUN pip install --no-cache-dir -r /app/phase2/requirements.txt

# Copy entire project (for imports across modules)
COPY . /app/

# Set Python path
ENV PYTHONPATH=/app

# Default command (can be overridden in docker-compose)
CMD ["python", "/app/phase2/run_conversational_orchestrator.py"]
