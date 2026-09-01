#!/bin/bash

# Rollback Teams Webhook Integration
# This script restores the Lambda function to use the original handler

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"
ORIGINAL_HANDLER="src.lambda_handler.lambda_handler"

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Teams Integration Rollback${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Confirm rollback
echo -e "${YELLOW}⚠️  This will rollback the Teams integration:${NC}"
echo "  - Restore handler to: $ORIGINAL_HANDLER"
echo "  - Remove Teams environment variables"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled"
    exit 0
fi

echo ""
echo -e "${GREEN}Starting rollback...${NC}"
echo ""

# Step 1: Restore original handler
echo -e "${YELLOW}Step 1: Restoring original handler...${NC}"
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --handler "$ORIGINAL_HANDLER" \
    --region "$REGION" \
    > /dev/null

echo -e "${GREEN}✓ Handler updated${NC}"

# Step 2: Wait for update to complete
echo ""
echo -e "${YELLOW}Step 2: Waiting for update to complete...${NC}"
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo -e "${GREEN}✓ Update complete${NC}"

# Step 3: Remove Teams environment variables (optional)
echo ""
echo -e "${YELLOW}Step 3: Removing Teams environment variables...${NC}"

# Get current environment variables
CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json)

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠️  jq not found, skipping environment variable cleanup${NC}"
    echo -e "${YELLOW}   Teams variables will remain but won't affect functionality${NC}"
else
    # Remove Teams-related variables
    UPDATED_ENV=$(echo "$CURRENT_ENV" | jq 'del(.TEAMS_INCOMING_WEBHOOK_URL, .TEAMS_SECURITY_TOKEN)')
    
    # Wrap in Variables key for AWS CLI
    echo "{\"Variables\": $UPDATED_ENV}" > /tmp/lambda-env-vars.json
    
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --environment file:///tmp/lambda-env-vars.json \
        --region "$REGION" \
        > /dev/null
    
    # Clean up temp file
    rm -f /tmp/lambda-env-vars.json
    
    echo -e "${GREEN}✓ Environment variables cleaned${NC}"
    
    # Wait for update
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
fi

# Verification
echo ""
echo -e "${YELLOW}Step 4: Verifying rollback...${NC}"

CURRENT_HANDLER=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Handler' \
    --output text)

if [ "$CURRENT_HANDLER" = "$ORIGINAL_HANDLER" ]; then
    echo -e "${GREEN}✓ Handler verified: $CURRENT_HANDLER${NC}"
else
    echo -e "${RED}✗ Handler mismatch!${NC}"
    echo "  Expected: $ORIGINAL_HANDLER"
    echo "  Current: $CURRENT_HANDLER"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Rollback Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Lambda handler restored${NC}"
echo -e "${GREEN}✓ Teams variables removed${NC}"
echo -e "${GREEN}✓ Function ready to use${NC}"
echo ""
echo -e "${YELLOW}Test the function:${NC}"
echo ""
echo "  aws lambda invoke \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --cli-binary-format raw-in-base64-out \\"
echo "    --payload '{\"query\": \"查詢 n8n 的 DNS\"}' \\"
echo "    response.json"
echo ""
echo "  cat response.json"
echo ""
echo -e "${YELLOW}Or with assume role:${NC}"
echo ""
echo "  eval \"\$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)\""
echo ""
echo "  aws lambda invoke \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --cli-binary-format raw-in-base64-out \\"
echo "    --payload '{\"query\": \"查詢 n8n 的 DNS\"}' \\"
echo "    response.json && cat response.json"
echo ""
