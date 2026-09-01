#!/bin/bash

# Complete F5 Tool Deployment (Setup Secret + Deploy Tool)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Complete F5 Tool Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Setup F5 Secret
echo -e "${YELLOW}Step 1: Setting up F5 API Secret...${NC}"
bash setup_f5_secret.sh

echo ""
echo -e "${YELLOW}Step 2: Deploying F5 Tool to Lambda...${NC}"
export F5_SECRET_NAME="f5-distributed-cloud-api-credentials"
bash deploy_f5_tool.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Complete Deployment Finished!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}✓ F5 API Secret configured${NC}"
echo -e "${GREEN}✓ F5 Tools deployed to Lambda${NC}"
echo -e "${GREEN}✓ Lambda environment variables updated${NC}"
echo ""
echo -e "${YELLOW}Test the F5 tools:${NC}"
echo ""
echo "# List all F5 load balancers"
echo "aws lambda invoke \\"
echo "  --function-name aws-ops-agent-dev \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"query\": \"list all F5 load balancers\"}' \\"
echo "  response.json && cat response.json"
echo ""
echo "Or use the test script:"
echo "  bash test_f5_tool.sh"
echo ""
