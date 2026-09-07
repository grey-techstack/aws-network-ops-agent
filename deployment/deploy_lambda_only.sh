#!/bin/bash
# Deploy Lambda only (no API Gateway) - for accounts with SCP restrictions

source deploy-config.sh

echo "Deploying Lambda-only stack (no API Gateway)..."

# Create parameters
cat > cf-parameters-lambda.json << EOF
[
  {"ParameterKey": "ProjectName", "ParameterValue": "$PROJECT_NAME"},
  {"ParameterKey": "Environment", "ParameterValue": "$ENVIRONMENT"},
  {"ParameterKey": "GlobalReaderRoleName", "ParameterValue": "$GLOBAL_READER_ROLE_NAME"},
  {"ParameterKey": "CoreNetworkAccountId", "ParameterValue": "$CORE_NETWORK_ACCOUNT_ID"},
  {"ParameterKey": "WorkloadAccountIds", "ParameterValue": "$WORKLOAD_ACCOUNT_IDS"},
  {"ParameterKey": "F5SecretName", "ParameterValue": "$F5_SECRET_NAME"},
  {"ParameterKey": "F5ApiUrl", "ParameterValue": "$F5_API_URL"},
  {"ParameterKey": "F5ApiToken", "ParameterValue": "$F5_API_TOKEN"},
  {"ParameterKey": "F5Namespace", "ParameterValue": "$F5_NAMESPACE"},
  {"ParameterKey": "LambdaTimeout", "ParameterValue": "$LAMBDA_TIMEOUT"},
  {"ParameterKey": "LambdaMemorySize", "ParameterValue": "$LAMBDA_MEMORY_SIZE"}
]
EOF

# Deploy
aws cloudformation create-stack \
    --stack-name "${STACK_NAME}-lambda" \
    --template-body file://aws-ops-agent-lambda-only.yaml \
    --parameters file://cf-parameters-lambda.json \
    --capabilities CAPABILITY_NAMED_IAM

echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete --stack-name "${STACK_NAME}-lambda"

echo "✅ Lambda deployed! Test with:"
echo "aws lambda invoke --function-name ${PROJECT_NAME}-${ENVIRONMENT} --payload '{\"query\": \"test\"}' response.json"
