FROM pathwaycom/pathway:latest

# Install curl for healthcheck and procps for process monitoring
RUN apt-get update && apt-get install -y curl procps && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

EXPOSE 8001
EXPOSE 7001