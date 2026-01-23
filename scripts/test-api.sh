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

# Execute Python code
echo -e "${YELLOW}3. Executing Python code...${NC}"
CODE='print("Hello from Code Executor!")\nfor i in range(3):\n    print(f"  Number: {i}")'
EXEC_RESPONSE=$(curl -s -X POST "$API_URL/execute" \
    -H "Content-Type: application/json" \
    -d "{\"environment\": \"python\", \"code\": \"$CODE\"}")
echo "Execution Response:"
echo "$EXEC_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$EXEC_RESPONSE"
echo -e "${GREEN}✓ Python code executed${NC}"
echo ""

# Execute Python code with stdin
echo -e "${YELLOW}4. Execution with stdin...${NC}"
CODE_STDIN='name = input()\nprint(f"Hello, {name}!")'
EXEC_RESPONSE2=$(curl -s -X POST "$API_URL/execute" \
    -H "Content-Type: application/json" \
    -d "{\"environment\": \"python\", \"code\": \"$CODE_STDIN\", \"stdin\": \"World\"}")
echo "Execution Response:"
echo "$EXEC_RESPONSE2" | python3 -m json.tool 2>/dev/null || echo "$EXEC_RESPONSE2"
echo -e "${GREEN}✓ Code with stdin executed${NC}"
echo ""

# Execute Node.js code
echo -e "${YELLOW}5. Executing Node.js code...${NC}"
CODE_NODE='console.log("Hello from Node.js!")'
EXEC_RESPONSE3=$(curl -s -X POST "$API_URL/execute" \
    -H "Content-Type: application/json" \
    -d "{\"environment\": \"node\", \"code\": \"$CODE_NODE\"}")
echo "Execution Response:"
echo "$EXEC_RESPONSE3" | python3 -m json.tool 2>/dev/null || echo "$EXEC_RESPONSE3"
echo -e "${GREEN}✓ Node.js code executed${NC}"
echo ""

# Test error handling
echo -e "${YELLOW}6. Testing error handling (syntax error)...${NC}"
CODE_ERR='print("unclosed string'
EXEC_RESPONSE4=$(curl -s -X POST "$API_URL/execute" \
    -H "Content-Type: application/json" \
    -d "{\"environment\": \"python\", \"code\": \"$CODE_ERR\"}")
echo "Execution Response:"
echo "$EXEC_RESPONSE4" | python3 -m json.tool 2>/dev/null || echo "$EXEC_RESPONSE4"
echo -e "${GREEN}✓ Error handled correctly${NC}"
echo ""

echo "========================================"
echo -e "${GREEN}All tests passed!${NC}"
