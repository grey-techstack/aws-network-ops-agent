#!/bin/bash

# Setup F5 API Secret in AWS Secrets Manager

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SECRET_NAME="f5-distributed-cloud-api-credentials"
REGION="${AWS_REGION:-ap-southeast-1}"

# F5 API credentials from cf-parameters.json
F5_API_URL="https://example.console.example.io/api"
F5_API_TOKEN="YOUR_F5_API_TOKEN_HERE"
F5_NAMESPACE="acme-net"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup F5 API Secret${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${YELLOW}Step 1: Assuming role...${NC}"
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

echo ""
echo -e "${YELLOW}Step 2: Checking if secret exists...${NC}"

if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" > /dev/null 2>&1; then
    echo -e "${YELLOW}Secret already exists, updating...${NC}"
    
    aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --region "$REGION" \
        --secret-string "{
            \"api_url\": \"$F5_API_URL\",
            \"api_token\": \"$F5_API_TOKEN\",
            \"namespace\": \"$F5_NAMESPACE\"
        }"
    
    echo -e "${GREEN}✓ Secret updated successfully${NC}"
else
    echo -e "${YELLOW}Creating new secret...${NC}"
    
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --description "F5 Distributed Cloud API credentials" \
        --region "$REGION" \
        --secret-string "{
            \"api_url\": \"$F5_API_URL\",
            \"api_token\": \"$F5_API_TOKEN\",
            \"namespace\": \"$F5_NAMESPACE\"
        }"
    
    echo -e "${GREEN}✓ Secret created successfully${NC}"
fi

echo ""
echo -e "${YELLOW}Step 3: Verifying secret...${NC}"

SECRET_VALUE=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$REGION" \
    --query SecretString \
    --output text)

echo ""
echo "Secret contents:"
echo "$SECRET_VALUE" | jq '.'

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}✓ Secret Name: $SECRET_NAME${NC}"
echo -e "${GREEN}✓ API URL: $F5_API_URL${NC}"
echo -e "${GREEN}✓ Namespace: $F5_NAMESPACE${NC}"
echo -e "${GREEN}✓ API Token: [HIDDEN]${NC}"
echo ""
echo "Next steps:"
echo "  1. Deploy F5 tool: bash deploy_f5_tool.sh"
echo "  2. Test F5 tool: bash test_f5_tool.sh"
echo ""
