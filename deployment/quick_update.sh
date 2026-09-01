#!/bin/bash

# Quick update Lambda code without full rebuild
# Use this when only source code changed, not dependencies

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo -e "${YELLOW}Quick Lambda Update${NC}"
echo ""

# Step 1: Build package (reuse cached dependencies)
echo -e "${YELLOW}Step 1: Building package (using cache)...${NC}"
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

# Step 2: Update Lambda code
echo ""
echo -e "${YELLOW}Step 2: Updating Lambda code...${NC}"
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://aws-ops-agent-function.zip \
    --region "$REGION" \
    > /dev/null

# Step 3: Wait for update
echo ""
echo -e "${YELLOW}Step 3: Waiting for update...${NC}"
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo -e "${GREEN}✅ Update complete!${NC}"
echo ""
echo "Test the function:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --payload '{\"query\":\"test\"}' response.json"
echo ""
