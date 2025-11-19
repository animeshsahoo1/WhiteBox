FROM pathwaycom/pathway:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project structure
COPY . /app/

# Install Python dependencies from phase2
RUN pip install --no-cache-dir -r /app/phase2/requirements.txt

# Set Python path to include project root
ENV PYTHONPATH=/app:/app/phase2

# Set working directory to phase2
WORKDIR /app/phase2

# Default command (can be overridden in docker-compose)
CMD ["python", "run_conversational_orchestrator.py"]

# Expose all service ports
# Hypothesis API, Hypothesis MCP, Redis, Risk Manager MCP, Backtesting API
EXPOSE 9001 9002 9003 9004 9005