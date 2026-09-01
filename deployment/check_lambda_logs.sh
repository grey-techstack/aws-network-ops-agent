#!/bin/bash

# Check Lambda logs for Teams webhook issues

set -e

FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo "========================================="
echo "Checking Lambda Logs"
echo "========================================="
echo ""

echo "Assuming role..."
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

echo ""
echo "Fetching last 50 log entries (last 10 minutes)..."
echo ""

aws logs tail /aws/lambda/aws-ops-agent-dev \
    --region "$REGION" \
    --since 10m \
    --format short

echo ""
echo "========================================="
echo "Log Check Complete"
echo "========================================="
