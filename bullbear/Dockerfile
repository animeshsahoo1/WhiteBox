# FROM pathwaycom/pathway:latest

# # Set working directory
# WORKDIR /app

# # Install system dependencies
# RUN apt-get update && apt-get install -y \
#     curl \
#     git \
#     && rm -rf /var/lib/apt/lists/*

# # Copy requirements file and install dependencies
# COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy application code
# COPY . .

# # Create necessary directories
# RUN mkdir -p reports debate_data

# # Expose ports
# # 8001 - Bull-Bear FastAPI server
# EXPOSE 8001

# # Default command (can be overridden in docker-compose)
# CMD ["python", "bull_bear_main.py"]

FROM pathwaycom/pathway:latest

# Install system dependencies (image/plotting, debugging, git, healthchecks)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    curl \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy A-Mem library FIRST for better Docker layer caching
COPY A-mem/ ./A-mem/
RUN pip install --no-cache-dir -e ./A-mem

# Copy application code
COPY . .

# Install dependencies AFTER code is copied
RUN pip install --no-cache-dir -r requirements.txt

# Create required runtime directories
RUN mkdir -p reports debate_data

# Expose Bull-Bear FastAPI port
EXPOSE 8001

# Default start command (can be overridden in docker-compose)
CMD ["python", "bull_bear_main.py"]
