#!/bin/bash

# Bull-Bear Docker Startup Script
# This script manages the bull-bear debate services using Docker Compose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Bull-Bear Debate System - Docker Setup${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_warn ".env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_info "Created .env file. Please edit it with your API keys."
        print_warn "Opening .env in editor..."
        ${EDITOR:-nano} .env
    else
        print_error ".env.example not found!"
        exit 1
    fi
fi

# Check if OPENAI_API_KEY is set
if ! grep -q "OPENAI_API_KEY=your-" .env 2>/dev/null; then
    print_info "OPENAI_API_KEY appears to be configured"
else
    print_warn "OPENAI_API_KEY not configured in .env file!"
    print_warn "Please edit .env and add your API key"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if stock-network exists
if ! docker network ls | grep -q "kafka_stock-network"; then
    print_warn "kafka_stock-network not found. Creating it..."
    docker network create kafka_stock-network || print_warn "Network might already exist"
fi

# Create necessary directories
print_info "Creating necessary directories..."
mkdir -p reports debate_data

# Parse command line arguments
COMMAND=${1:-up}

case $COMMAND in
    up)
        print_info "Starting Bull-Bear services..."
        docker-compose up -d
        
        print_info "Waiting for services to be healthy..."
        sleep 5
        
        # Check service health
        print_info "Checking service health..."
        
        if curl -f http://localhost:8001/health > /dev/null 2>&1; then
            print_info "✓ Bull-Bear API is healthy"
        else
            print_warn "✗ Bull-Bear API not responding yet (this may be normal during startup)"
        fi
        
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}Services Started Successfully!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo -e "\nAPI Endpoints:"
        echo -e "  - Bull-Bear API: ${YELLOW}http://localhost:8001${NC}"
        echo -e "  - Health Check:  ${YELLOW}http://localhost:8001/health${NC}"
        echo -e "  - API Docs:      ${YELLOW}http://localhost:8001/docs${NC}"
        echo -e "\nUseful Commands:"
        echo -e "  - View logs:     ${YELLOW}docker-compose logs -f${NC}"
        echo -e "  - Stop services: ${YELLOW}./start.sh down${NC}"
        echo -e "  - Restart:       ${YELLOW}./start.sh restart${NC}"
        echo -e "\n"
        ;;
        
    down)
        print_info "Stopping Bull-Bear services..."
        docker-compose down
        print_info "Services stopped successfully"
        ;;
        
    restart)
        print_info "Restarting Bull-Bear services..."
        docker-compose restart
        print_info "Services restarted successfully"
        ;;
        
    logs)
        print_info "Showing logs (Ctrl+C to exit)..."
        docker-compose logs -f
        ;;
        
    build)
        print_info "Building Docker images..."
        docker-compose build --no-cache
        print_info "Build complete"
        ;;
        
    clean)
        print_warn "This will remove all containers, volumes, and generated data!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Cleaning up..."
            docker-compose down -v
            rm -rf reports/* debate_data/*
            print_info "Cleanup complete"
        else
            print_info "Cancelled"
        fi
        ;;
        
    test)
        print_info "Running test debate..."
        curl -X POST http://localhost:8001/begin_debate \
          -H "Content-Type: application/json" \
          -d '{"symbol": "AAPL", "max_rounds": 2}' \
          | jq .
        ;;
        
    *)
        echo "Usage: $0 {up|down|restart|logs|build|clean|test}"
        echo ""
        echo "Commands:"
        echo "  up      - Start all services"
        echo "  down    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - View service logs"
        echo "  build   - Rebuild Docker images"
        echo "  clean   - Remove all containers and data"
        echo "  test    - Run a test debate"
        exit 1
        ;;
esac
