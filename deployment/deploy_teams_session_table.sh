#!/bin/bash

# Deploy DynamoDB table for Teams chat sessions

set -e

ENVIRONMENT=${1:-dev}
STACK_NAME="teams-chat-sessions-${ENVIRONMENT}"
TEMPLATE_FILE="teams-session-table.yaml"

echo "========================================="
echo "Deploy Teams Session Table"
echo "========================================="
echo "Environment: $ENVIRONMENT"
echo "Stack Name: $STACK_NAME"
echo ""

# Check if template exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "❌ Template file not found: $TEMPLATE_FILE"
    exit 1
fi

echo "Step 1: Validating CloudFormation template..."
aws cloudformation validate-template \
    --template-body file://$TEMPLATE_FILE \
    > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Template is valid"
else
    echo "❌ Template validation failed"
    exit 1
fi

echo ""
echo "Step 2: Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file $TEMPLATE_FILE \
    --stack-name $STACK_NAME \
    --parameter-overrides Environment=$ENVIRONMENT \
    --tags \
        Environment=$ENVIRONMENT \
        Application=aws-ops-agent \
        Component=teams-chat-sessions

if [ $? -eq 0 ]; then
    echo "✅ Stack deployed successfully"
else
    echo "❌ Stack deployment failed"
    exit 1
fi

echo ""
echo "Step 3: Getting stack outputs..."
TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
    --output text)

TABLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`TableArn`].OutputValue' \
    --output text)

echo "✅ DynamoDB Table Created:"
echo "   Table Name: $TABLE_NAME"
echo "   Table ARN: $TABLE_ARN"

echo ""
echo "Step 4: Verifying table..."
aws dynamodb describe-table --table-name $TABLE_NAME > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Table is accessible"
else
    echo "❌ Table verification failed"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Deployment Complete"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Update Lambda environment variable:"
echo "   TEAMS_SESSION_TABLE_NAME=$TABLE_NAME"
echo ""
echo "2. Add DynamoDB permissions to Lambda role:"
echo "   aws iam put-role-policy \\"
echo "     --role-name aws-ops-agent-execution-role-${ENVIRONMENT} \\"
echo "     --policy-name DynamoDBTeamsSessions \\"
echo "     --policy-document file://teams-session-policy.json"
echo ""
echo "3. Deploy updated Lambda code:"
echo "   bash quick_update_teams.sh"
echo ""
