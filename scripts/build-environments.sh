#!/bin/bash

# Script to build execution environment Docker images
# Usage: ./scripts/build-environments.sh [environment]
# Example: ./scripts/build-environments.sh python
#          ./scripts/build-environments.sh  # builds all

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENTS_DIR="$PROJECT_DIR/environments"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

build_environment() {
    local env_name=$1
    local env_dir="$ENVIRONMENTS_DIR/$env_name"
    local image_name="code-executor-$env_name"
    
    if [ ! -d "$env_dir" ]; then
        echo -e "${RED}Error: Environment directory not found: $env_dir${NC}"
        return 1
    fi
    
    if [ ! -f "$env_dir/Dockerfile" ]; then
        echo -e "${RED}Error: Dockerfile not found in $env_dir${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Building $image_name...${NC}"
    docker build -t "$image_name" "$env_dir"
    echo -e "${GREEN}✓ Successfully built $image_name${NC}"
}

# If specific environment is provided
if [ -n "$1" ]; then
    build_environment "$1"
    exit 0
fi

# Build all environments
echo "Building all execution environments..."
echo ""

for env_dir in "$ENVIRONMENTS_DIR"/*/; do
    if [ -d "$env_dir" ]; then
        env_name=$(basename "$env_dir")
        build_environment "$env_name"
        echo ""
    fi
done

echo -e "${GREEN}All environments built successfully!${NC}"
echo ""
echo "Available images:"
docker images | grep "code-executor-" | awk '{print "  - " $1 ":" $2}'

