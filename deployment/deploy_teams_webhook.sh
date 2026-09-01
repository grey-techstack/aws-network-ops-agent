#!/bin/bash

# Deploy Teams Webhook Integration
# This script updates the Lambda function to use the Teams webhook handler

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Teams Webhook Integration Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if TEAMS_INCOMING_WEBHOOK_URL is provided
if [ -z "$TEAMS_INCOMING_WEBHOOK_URL" ]; then
    echo -e "${RED}Error: TEAMS_INCOMING_WEBHOOK_URL environment variable is required${NC}"
    echo ""
    echo "Please set it first:"
    echo "  export TEAMS_INCOMING_WEBHOOK_URL='https://outlook.office.com/webhook/...'"
    echo ""
    echo "See TEAMS_WEBHOOK_SETUP.md for instructions on how to create an Incoming Webhook"
    exit 1
fi

echo -e "${YELLOW}Step 1: Building Lambda package (optimized)...${NC}"
# Use optimized build script with pip cache for faster builds
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

echo ""
echo -e "${YELLOW}Step 2: Updating Lambda function code...${NC}"
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://aws-ops-agent-function.zip \
    --region "$REGION"

echo ""
echo -e "${YELLOW}Step 3: Waiting for function update to complete...${NC}"
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo -e "${YELLOW}Step 4: Getting current environment variables...${NC}"
CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json)

# Add TEAMS_INCOMING_WEBHOOK_URL to environment variables
echo ""
echo -e "${YELLOW}Step 5: Updating environment variables...${NC}"
UPDATED_ENV=$(echo "$CURRENT_ENV" | jq --arg url "$TEAMS_INCOMING_WEBHOOK_URL" '. + {TEAMS_INCOMING_WEBHOOK_URL: $url}')

# Wrap in Variables key for AWS CLI
echo "{\"Variables\": $UPDATED_ENV}" > /tmp/lambda-env-vars.json

aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment file:///tmp/lambda-env-vars.json \
    --region "$REGION" \
    > /dev/null

# Clean up temp file
rm -f /tmp/lambda-env-vars.json

echo ""
echo -e "${YELLOW}Step 6: Waiting for configuration update...${NC}"
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo -e "${YELLOW}Step 7: Updating Lambda handler...${NC}"
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --handler src.teams_webhook_handler.lambda_handler \
    --region "$REGION" \
    > /dev/null

echo ""
echo -e "${YELLOW}Step 8: Waiting for handler update...${NC}"
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo -e "${YELLOW}Step 9: Ensuring Lambda can invoke itself (for async processing)...${NC}"

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

# Get Lambda execution role
ROLE_NAME=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Role' \
    --output text | awk -F'/' '{print $NF}')

# Create inline policy for self-invocation
POLICY_NAME="LambdaSelfInvokePolicy"
POLICY_DOCUMENT=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "$LAMBDA_ARN"
    }
  ]
}
EOF
)

# Check if policy already exists
if aws iam get-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    --region "$REGION" \
    > /dev/null 2>&1; then
    echo "  Policy already exists, updating..."
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --policy-document "$POLICY_DOCUMENT" \
        --region "$REGION"
else
    echo "  Creating new policy..."
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --policy-document "$POLICY_DOCUMENT" \
        --region "$REGION"
fi

echo ""
echo -e "${YELLOW}Step 10: Getting API Gateway URL...${NC}"
API_URL=$(aws cloudformation describe-stacks \
    --stack-name aws-ops-agent-api-gateway-dev \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
    --output text 2>/dev/null || echo "")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Lambda function updated${NC}"
echo -e "${GREEN}✓ Handler set to: src.teams_webhook_handler.lambda_handler${NC}"
echo -e "${GREEN}✓ Environment variable TEAMS_INCOMING_WEBHOOK_URL configured${NC}"
echo -e "${GREEN}✓ Self-invocation permission added${NC}"
echo ""

if [ -n "$API_URL" ]; then
    echo -e "${YELLOW}Next Steps:${NC}"
    echo ""
    echo "1. Create Teams Outgoing Webhook:"
    echo "   - In Teams, go to Apps → Search 'Outgoing Webhook'"
    echo "   - Name: AWSBot"
    echo "   - Callback URL: ${GREEN}$API_URL${NC}"
    echo "   - Description: AWS Operations AI Assistant"
    echo ""
    echo "2. Test in Teams Channel:"
    echo "   ${GREEN}@AWSBot 查詢 n8n 的 DNS${NC}"
    echo ""
else
    echo -e "${YELLOW}Warning: Could not retrieve API Gateway URL${NC}"
    echo "Please get it manually:"
    echo "  aws cloudformation describe-stacks \\"
    echo "    --stack-name aws-ops-agent-api-gateway-dev \\"
    echo "    --query 'Stacks[0].Outputs[?OutputKey==\`ApiGatewayUrl\`].OutputValue' \\"
    echo "    --output text"
    echo ""
fi

echo "For detailed setup instructions, see: deployment/TEAMS_WEBHOOK_SETUP.md"
echo ""
