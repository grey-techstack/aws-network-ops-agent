#!/bin/bash
# Quick redeploy - skips package building
source deploy-config.sh
aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://aws-ops-agent-complete.yaml \
    --parameters file://cf-parameters.json \
    --capabilities CAPABILITY_NAMED_IAM
echo "Stack deployment initiated. Waiting..."
aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"
echo "Done!"
