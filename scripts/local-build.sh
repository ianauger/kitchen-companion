#!/bin/bash
# local-build.sh
# Build and run Kitchen Companion locally for testing

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Kitchen Companion - Local Build${NC}"
echo "================================"

# Check if we're in the project root
if [ ! -f "app.py" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t kitchen-companion:latest .

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build successful${NC}"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${YELLOW}Note: docker-compose.yml not found. Running standalone container...${NC}"
    
    # Stop existing container if running
    if docker ps -q --filter "name=kitchen-companion" | grep -q .; then
        echo -e "${YELLOW}Stopping existing container...${NC}"
        docker stop kitchen-companion 2>/dev/null || true
        docker rm kitchen-companion 2>/dev/null || true
    fi
    
    # Run container
    echo -e "${YELLOW}Starting container...${NC}"
    docker run -d \
        --name kitchen-companion \
        -p 5000:5000 \
        -v "$(pwd)/kitchen_companion.db:/app/kitchen_companion.db" \
        -v "$(pwd)/app/static/uploads:/app/app/static/uploads" \
        kitchen-companion:latest
else
    # Run with docker-compose
    echo -e "${YELLOW}Running with docker-compose...${NC}"
    docker-compose down 2>/dev/null || true
    docker-compose up -d
fi

echo -e "${GREEN}✓ Container started${NC}"
echo ""
echo -e "${BLUE}Application should be available at: http://localhost:5000${NC}"
echo -e "${YELLOW}To view logs: docker logs -f kitchen-companion${NC}"
