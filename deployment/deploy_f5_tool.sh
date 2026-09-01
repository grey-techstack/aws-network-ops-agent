#!/bin/bash

# Deploy F5 WAF Tool to Lambda

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}F5 WAF Tool Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if F5_SECRET_NAME is set
if [ -z "$F5_SECRET_NAME" ]; then
    echo -e "${YELLOW}Warning: F5_SECRET_NAME not set, using default${NC}"
    F5_SECRET_NAME="f5-distributed-cloud-api-credentials"
fi

echo "F5 Secret Name: $F5_SECRET_NAME"
echo ""

echo -e "${YELLOW}Step 1: Assuming role...${NC}"
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

echo ""
echo -e "${YELLOW}Step 2: Checking if F5 secret exists...${NC}"
if aws secretsmanager describe-secret --secret-id "$F5_SECRET_NAME" --region "$REGION" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ F5 secret exists${NC}"
else
    echo -e "${RED}✗ F5 secret not found: $F5_SECRET_NAME${NC}"
    echo ""
    echo "Please create the secret first:"
    echo ""
    echo "aws secretsmanager create-secret \\"
    echo "  --name $F5_SECRET_NAME \\"
    echo "  --description 'F5 Distributed Cloud API credentials' \\"
    echo "  --secret-string '{"
    echo "    \"api_url\": \"https://example.console.example.io/api\","
    echo "    \"api_token\": \"your-api-token\","
    echo "    \"namespace\": \"system\""
    echo "  }'"
    echo ""
    echo "See deployment/F5_API_SETUP_GUIDE.md for instructions"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3: Building Lambda package (optimized)...${NC}"
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

echo ""
echo -e "${YELLOW}Step 4: Updating Lambda function code...${NC}"
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://aws-ops-agent-function.zip \
    --region "$REGION"

echo ""
echo -e "${YELLOW}Step 5: Waiting for function update...${NC}"
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo -e "${YELLOW}Step 6: Checking current environment variables...${NC}"
CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json)

# Check if F5_SECRET_NAME is already set
EXISTING_F5_SECRET=$(echo "$CURRENT_ENV" | jq -r '.F5_SECRET_NAME // empty')

if [ "$EXISTING_F5_SECRET" == "$F5_SECRET_NAME" ]; then
    echo -e "${GREEN}✓ F5_SECRET_NAME already set correctly${NC}"
else
    echo ""
    echo -e "${YELLOW}Step 7: Updating F5_SECRET_NAME environment variable...${NC}"
    
    UPDATED_ENV=$(echo "$CURRENT_ENV" | jq --arg secret "$F5_SECRET_NAME" '. + {F5_SECRET_NAME: $secret}')
    
    echo "{\"Variables\": $UPDATED_ENV}" > /tmp/lambda-env-vars.json
    
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --environment file:///tmp/lambda-env-vars.json \
        --region "$REGION" \
        > /dev/null
    
    rm -f /tmp/lambda-env-vars.json
    
    echo ""
    echo -e "${YELLOW}Step 8: Waiting for configuration update...${NC}"
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Lambda function updated with F5 WAF tools${NC}"
echo -e "${GREEN}✓ F5_SECRET_NAME configured: $F5_SECRET_NAME${NC}"
echo ""
echo -e "${YELLOW}Available F5 Tools:${NC}"
echo "  1. query_f5_load_balancer - Query F5 load balancer by FQDN"
echo "  2. query_f5_origin_pool - Query F5 origin pool details"
echo "  3. list_f5_load_balancers - List all F5 load balancers"
echo ""
echo -e "${YELLOW}Test Commands:${NC}"
echo ""
echo "# List all F5 load balancers"
echo "aws lambda invoke \\"
echo "  --function-name $FUNCTION_NAME \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"query\": \"list all F5 load balancers\"}' \\"
echo "  response.json && cat response.json"
echo ""
echo "# Query F5 load balancer for a domain"
echo "aws lambda invoke \\"
echo "  --function-name $FUNCTION_NAME \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"query\": \"查詢 demo.example.com 的 F5 load balancer\"}' \\"
echo "  response.json && cat response.json"
echo ""
echo "Or use the test script:"
echo "  bash test_f5_tool.sh"
echo ""
echo "For detailed documentation, see: src/tools/F5_TOOL_README.md"
echo ""
