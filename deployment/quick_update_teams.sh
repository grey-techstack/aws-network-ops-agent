#!/bin/bash

# Quick update Lambda code only (no config changes)

set -e

FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"

echo "========================================="
echo "Quick Lambda Code Update"
echo "========================================="
echo ""

echo "Step 1: Assuming role..."
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

echo ""
echo "Step 2: Building package (optimized)..."
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

echo ""
echo "Step 3: Updating Lambda function code..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://aws-ops-agent-function.zip \
    --region "$REGION"

echo ""
echo "Step 4: Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo "========================================="
echo "Update Complete!"
echo "========================================="
echo ""
echo "Lambda function code updated successfully."
echo "You can now test with:"
echo ""
echo "aws lambda invoke \\"
echo "  --function-name aws-ops-agent-dev \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"query\": \"test\"}' \\"
echo "  response.json && cat response.json"
echo ""
