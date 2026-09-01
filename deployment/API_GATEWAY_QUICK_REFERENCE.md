# API Gateway Quick Reference

## Deployment Commands

### Deploy with CloudFormation

```bash
# Set variables
export LAMBDA_ARN="arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent"
export STACK_NAME="aws-ops-agent-api"

# Deploy
aws cloudformation create-stack \
  --stack-name $STACK_NAME \
  --template-body file://api-gateway-cloudformation.yaml \
  --parameters \
    ParameterKey=LambdaFunctionArn,ParameterValue=$LAMBDA_ARN \
    ParameterKey=ApiStageName,ParameterValue=prod \
    ParameterKey=EnableApiKey,ParameterValue=false \
  --capabilities CAPABILITY_IAM

# Wait for completion
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME

# Get endpoint
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

### Deploy with Terraform

```bash
# Initialize
terraform init

# Create variables file
cat > terraform.tfvars <<EOF
lambda_function_arn  = "arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent"
lambda_function_name = "aws-ops-agent"
api_stage_name       = "prod"
enable_api_key       = false
EOF

# Deploy
terraform apply

# Get endpoint
terraform output api_endpoint
```

### Deploy with Script

```bash
export LAMBDA_FUNCTION_NAME=aws-ops-agent
./deploy_api_gateway.sh
```

## Testing Commands

### Run Test Suite

```bash
./test_api_gateway.sh
```

### Manual Tests

```bash
# Set endpoint
export API_ENDPOINT="https://abc123.execute-api.us-east-1.amazonaws.com/prod/query"

# Test basic query
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'

# Test FQDN tracing
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"query": "Trace demo.example.com"}'

# Test with session ID
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"query": "Show CloudFront logs", "session_id": "session-123"}'

# Test CORS
curl -X OPTIONS $API_ENDPOINT \
  -H "Origin: https://example.com" \
  -v
```

## Management Commands

### Get API Information

```bash
# Get API ID
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiId`].OutputValue' \
  --output text

# Get API endpoint
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text

# Get API key (if enabled)
API_KEY_ID=$(aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' \
  --output text)

aws apigateway get-api-key \
  --api-key $API_KEY_ID \
  --include-value \
  --query value \
  --output text
```

### Update Stack

```bash
aws cloudformation update-stack \
  --stack-name aws-ops-agent-api \
  --template-body file://api-gateway-cloudformation.yaml \
  --parameters \
    ParameterKey=LambdaFunctionArn,UsePreviousValue=true \
    ParameterKey=ApiStageName,UsePreviousValue=true \
    ParameterKey=EnableApiKey,ParameterValue=true \
  --capabilities CAPABILITY_IAM
```

### Delete Stack

```bash
aws cloudformation delete-stack --stack-name aws-ops-agent-api
```

## Monitoring Commands

### View Logs

```bash
# API Gateway logs
aws logs tail /aws/apigateway/aws-ops-agent-api --follow

# Lambda logs
aws logs tail /aws/lambda/aws-ops-agent --follow

# Recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/aws-ops-agent \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

### View Metrics

```bash
# API Gateway request count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=aws-ops-agent-api \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=aws-ops-agent \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Troubleshooting Commands

### Test Lambda Directly

```bash
aws lambda invoke \
  --function-name aws-ops-agent \
  --payload '{"body": "{\"query\": \"test\"}"}' \
  response.json

cat response.json | jq .
```

### Check Lambda Permissions

```bash
aws lambda get-policy --function-name aws-ops-agent
```

### Check API Gateway Configuration

```bash
# Get API ID
API_ID=$(aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiId`].OutputValue' \
  --output text)

# Get API details
aws apigateway get-rest-api --rest-api-id $API_ID

# Get resources
aws apigateway get-resources --rest-api-id $API_ID

# Get method
aws apigateway get-method \
  --rest-api-id $API_ID \
  --resource-id RESOURCE_ID \
  --http-method POST
```

### Test with Verbose Output

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' \
  -v
```

## Common Issues and Solutions

### 403 Forbidden

```bash
# Check Lambda permissions
aws lambda get-policy --function-name aws-ops-agent

# Add permission if missing
aws lambda add-permission \
  --function-name aws-ops-agent \
  --statement-id AllowAPIGatewayInvoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:REGION:ACCOUNT:API_ID/*/*/*"
```

### 500 Internal Server Error

```bash
# Check Lambda logs
aws logs tail /aws/lambda/aws-ops-agent --since 5m

# Check environment variables
aws lambda get-function-configuration \
  --function-name aws-ops-agent \
  --query 'Environment.Variables'
```

### 504 Gateway Timeout

```bash
# Increase Lambda timeout
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --timeout 300
```

## API Request Examples

### Basic Query

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is 203.0.113.63?"
  }'
```

### FQDN Tracing

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Trace demo.example.com and show all components"
  }'
```

### CloudFront Logs

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show CloudFront logs for distribution E285K0Z0YGWJXZ with 4xx errors from yesterday"
  }'
```

### VPC Flow Logs

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show VPC flow logs from 10.0.1.100 to 10.0.2.200 in the last hour"
  }'
```

### With API Key

```bash
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "Trace demo.example.com"
  }'
```

## Response Format

### Success Response

```json
{
  "status": "success",
  "result_type": "fqdn_trace",
  "output": "...",
  "query": "Trace demo.example.com",
  "session_id": "session-123",
  "intermediate_steps": [...],
  "timestamp": "2025-01-12T10:30:00.000Z",
  "execution_time_ms": 2500
}
```

### Error Response

```json
{
  "status": "error",
  "error_type": "validation",
  "error_message": "Missing or invalid 'query' field",
  "timestamp": "2025-01-12T10:30:00.000Z"
}
```

## Environment Variables

```bash
# For deployment script
export LAMBDA_FUNCTION_NAME=aws-ops-agent
export STACK_NAME=aws-ops-agent-api
export STAGE_NAME=prod
export ENABLE_API_KEY=false
export ENABLE_CLOUDWATCH_LOGS=true
export API_KEY_NAME=my-api-key

# For testing script
export API_ENDPOINT=https://abc123.execute-api.us-east-1.amazonaws.com/prod/query
export API_KEY=your-api-key-value
export STACK_NAME=aws-ops-agent-api
```

## Resources

- [API Gateway Setup Guide](API_GATEWAY_SETUP.md)
- [Streaming Setup Guide](STREAMING_SETUP.md)
- [Main Deployment README](README.md)
- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
