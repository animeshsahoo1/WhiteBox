#!/bin/bash
# ============================================================
# Docker Build Script: Multi-Stage Image Builder
# 
# Builds all service images using the multi-stage Dockerfiles
# for optimal layer caching and smaller final images.
#
# Usage:
#   ./scripts/docker-build.sh           # Build all (dev target)
#   ./scripts/docker-build.sh --prod    # Build all (prod target)
#   ./scripts/docker-build.sh --no-cache # Fresh rebuild
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
TARGET="dev"
NO_CACHE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --prod)
            TARGET="prod"
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Building Docker Images (target: $TARGET)                  ║"
echo "╚════════════════════════════════════════════════════════════╝"

# Build base image first (shared dependencies)
echo ""
echo "📦 Building base image..."
if [ -f "$PROJECT_DIR/docker/Dockerfile.base" ]; then
    docker build $NO_CACHE \
        -f "$PROJECT_DIR/docker/Dockerfile.base" \
        -t pathway-interrit-base:latest \
        --target base \
        "$PROJECT_DIR/docker"
    echo "   ✅ Base image built"
else
    echo "   ⚠️  No base Dockerfile found, skipping..."
fi

# Build pathway services
echo ""
echo "📦 Building Pathway services..."
docker build $NO_CACHE \
    -f "$PROJECT_DIR/pathway/Dockerfile" \
    -t pathway-service:$TARGET \
    --target $TARGET \
    "$PROJECT_DIR/pathway"
echo "   ✅ Pathway service built"

# Build streaming services
echo ""
echo "📦 Building Streaming services..."
docker build $NO_CACHE \
    -f "$PROJECT_DIR/streaming/Dockerfile" \
    -t streaming-service:$TARGET \
    --target $TARGET \
    "$PROJECT_DIR/streaming"
echo "   ✅ Streaming service built"

# Build websocket service
echo ""
echo "📦 Building WebSocket service..."
docker build $NO_CACHE \
    -f "$PROJECT_DIR/websocket/Dockerfile" \
    -t websocket-service:$TARGET \
    --target $TARGET \
    "$PROJECT_DIR/websocket"
echo "   ✅ WebSocket service built"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ All images built successfully!                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Images created:"
docker images | grep -E "(pathway-|streaming-|websocket-)" | head -10

echo ""
echo "To start all services:"
echo "  cd $PROJECT_DIR && docker compose up -d"
