#!/bin/bash

# Check Lambda configuration

set -e

FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo "========================================="
echo "Checking Lambda Configuration"
echo "========================================="
echo ""

echo "Assuming role..."
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

echo ""
echo "Lambda Handler:"
aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Handler' \
    --output text

echo ""
echo "Environment Variables:"
aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json | jq '.'

echo ""
echo "Checking if TEAMS_INCOMING_WEBHOOK_URL is set:"
WEBHOOK_URL=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables.TEAMS_INCOMING_WEBHOOK_URL' \
    --output text)

if [ "$WEBHOOK_URL" != "None" ] && [ -n "$WEBHOOK_URL" ]; then
    echo "✓ TEAMS_INCOMING_WEBHOOK_URL is set"
    echo "  URL starts with: ${WEBHOOK_URL:0:50}..."
else
    echo "✗ TEAMS_INCOMING_WEBHOOK_URL is NOT set!"
fi

echo ""
echo "========================================="
echo "Configuration Check Complete"
echo "========================================="
