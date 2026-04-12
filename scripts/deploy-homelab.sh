#!/bin/bash
# deploy-homelab.sh
# Deploy Kitchen Companion to homelab server

set -e

# Configuration - UPDATE THESE VALUES
HOMELAB_USER="your-user"
HOMELAB_HOST="your-homelab-host"
HOMELAB_SSH_KEY="~/.ssh/your-key"
PROJECT_DIR="/path/to/kitchen-companion"  # Remote path

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Deploying Kitchen Companion to homelab...${NC}"

# SSH command helper
SSH_CMD="ssh -i $HOMELAB_SSH_KEY $HOMELAB_USER@$HOMELAB_HOST"

# Pull latest image from GHCR
echo -e "${YELLOW}Pulling latest image...${NC}"
$SSH_CMD "cd $PROJECT_DIR && docker-compose pull"

# Restart container with docker-compose
echo -e "${YELLOW}Restarting containers...${NC}"
$SSH_CMD "cd $PROJECT_DIR && docker-compose down && docker-compose up -d"

# Health check
echo -e "${YELLOW}Running health check...${NC}"
sleep 5

if $SSH_CMD "cd $PROJECT_DIR && docker-compose ps | grep -q 'Up'"; then
    echo -e "${GREEN}✓ Health check passed!${NC}"
    echo -e "${GREEN}Deployment successful!${NC}"
else
    echo -e "${RED}✗ Health check failed!${NC}"
    echo -e "${RED}Container status:${NC}"
    $SSH_CMD "cd $PROJECT_DIR && docker-compose ps"
    exit 1
fi

echo -e "${GREEN}Done!${NC}"
