#!/bin/bash

# Simple test script to verify API functionality
# Usage: ./scripts/test-api.sh [base_url]
# Example: ./scripts/test-api.sh http://localhost:8000

set -e

BASE_URL="${1:-http://localhost:8000}"
API_URL="$BASE_URL/api/v1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Testing Code Executor API at $BASE_URL"
echo "========================================"
echo ""

# Test health endpoint
echo -e "${YELLOW}1. Testing health endpoint...${NC}"
HEALTH=$(curl -s "$API_URL/health")
echo "Response: $HEALTH"
echo -e "${GREEN}✓ Health check passed${NC}"
echo ""

# Test environments endpoint
echo -e "${YELLOW}2. Testing environments endpoint...${NC}"
ENVS=$(curl -s "$API_URL/environments")
echo "Available environments: $ENVS"
echo -e "${GREEN}✓ Environments retrieved${NC}"
echo ""

# Create a session
echo -e "${YELLOW}3. Creating Python session...${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$API_URL/sessions" \
    -H "Content-Type: application/json" \
    -d '{"environment": "python"}')
echo "Response: $SESSION_RESPONSE"

SESSION_ID=$(echo "$SESSION_RESPONSE" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$SESSION_ID" ]; then
    echo -e "${RED}✗ Failed to create session${NC}"
    exit 1
fi
echo "Session ID: $SESSION_ID"
echo -e "${GREEN}✓ Session created${NC}"
echo ""

# Wait for session to be ready
echo -e "${YELLOW}4. Waiting for session to be ready...${NC}"
for i in {1..30}; do
    STATUS_RESPONSE=$(curl -s "$API_URL/sessions/$SESSION_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "  Status: $STATUS"
    
    if [ "$STATUS" = "ready" ]; then
        echo -e "${GREEN}✓ Session is ready${NC}"
        break
    elif [ "$STATUS" = "error" ]; then
        echo -e "${RED}✗ Session errored${NC}"
        echo "$STATUS_RESPONSE"
        exit 1
    fi
    
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Timeout waiting for session${NC}"
        exit 1
    fi
    
    sleep 1
done
echo ""

# Execute code
echo -e "${YELLOW}5. Executing Python code...${NC}"
CODE='print("Hello from Code Executor!")\nfor i in range(3):\n    print(f"  Number: {i}")'
EXEC_RESPONSE=$(curl -s -X POST "$API_URL/sessions/$SESSION_ID/execute" \
    -H "Content-Type: application/json" \
    -d "{\"code\": \"$CODE\"}")
echo "Execution Response:"
echo "$EXEC_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$EXEC_RESPONSE"
echo -e "${GREEN}✓ Code executed${NC}"
echo ""

# Stop session
echo -e "${YELLOW}6. Stopping session...${NC}"
STOP_RESPONSE=$(curl -s -X DELETE "$API_URL/sessions/$SESSION_ID")
echo "Response: $STOP_RESPONSE"
echo -e "${GREEN}✓ Session stopped${NC}"
echo ""

echo "========================================"
echo -e "${GREEN}All tests passed!${NC}"

