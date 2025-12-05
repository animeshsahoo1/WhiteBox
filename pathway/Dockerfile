FROM pathwaycom/pathway:latest

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create required directories (in case volumes don't exist on host)
RUN mkdir -p /app/reports/fundamental /app/reports/market /app/reports/news \
    /app/reports/sentiment /app/reports/facilitator /app/reports/debate \
    /app/pathway_state /app/knowledge_base

# Expose FastAPI ports
EXPOSE 8000

ENV PYTHONUNBUFFERED=1