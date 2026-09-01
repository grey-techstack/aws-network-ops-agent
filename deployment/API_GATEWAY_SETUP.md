# API Gateway Setup Guide

This guide provides instructions for deploying the API Gateway REST API for the AWS Operations Agent.

## Overview

The API Gateway provides a REST API endpoint that accepts natural language queries and forwards them to the Lambda function. It includes:

- `/query` POST endpoint for submitting queries
- CORS support for web client access
- Optional API key authentication
- Request/response validation
- CloudWatch logging
- Throttling and usage quotas

## Prerequisites

- AWS CLI configured with appropriate credentials
- Lambda function deployed and ARN available
- Appropriate IAM permissions to create API Gateway resources

## Deployment Options

### Option 1: CloudFormation

#### Deploy with CloudFormation

```bash
# Set your Lambda function ARN
LAMBDA_ARN="arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent"

# Deploy the stack
aws cloudformation create-stack \
  --stack-name aws-ops-agent-api \
  --template-body file://api-gateway-cloudformation.yaml \
  --parameters \
    ParameterKey=LambdaFunctionArn,ParameterValue=$LAMBDA_ARN \
    ParameterKey=ApiStageName,ParameterValue=prod \
    ParameterKey=EnableApiKey,ParameterValue=false \
    ParameterKey=EnableCloudWatchLogs,ParameterValue=true \
  --capabilities CAPABILITY_IAM

# Wait for stack creation to complete
aws cloudformation wait stack-create-complete \
  --stack-name aws-ops-agent-api

# Get the API endpoint
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

#### Deploy with API Key Authentication

```bash
aws cloudformation create-stack \
  --stack-name aws-ops-agent-api \
  --template-body file://api-gateway-cloudformation.yaml \
  --parameters \
    ParameterKey=LambdaFunctionArn,ParameterValue=$LAMBDA_ARN \
    ParameterKey=ApiStageName,ParameterValue=prod \
    ParameterKey=EnableApiKey,ParameterValue=true \
    ParameterKey=ApiKeyName,ParameterValue=my-api-key \
    ParameterKey=EnableCloudWatchLogs,ParameterValue=true \
  --capabilities CAPABILITY_IAM

# Retrieve the API key value
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

#### Update Stack

```bash
aws cloudformation update-stack \
  --stack-name aws-ops-agent-api \
  --template-body file://api-gateway-cloudformation.yaml \
  --parameters \
    ParameterKey=LambdaFunctionArn,ParameterValue=$LAMBDA_ARN \
    ParameterKey=ApiStageName,ParameterValue=prod \
    ParameterKey=EnableApiKey,ParameterValue=false \
    ParameterKey=EnableCloudWatchLogs,ParameterValue=true \
  --capabilities CAPABILITY_IAM
```

#### Delete Stack

```bash
aws cloudformation delete-stack --stack-name aws-ops-agent-api
```

### Option 2: Terraform

#### Initialize and Deploy

```bash
# Initialize Terraform
terraform init

# Create terraform.tfvars file
cat > terraform.tfvars <<EOF
lambda_function_arn  = "arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent"
lambda_function_name = "aws-ops-agent"
api_stage_name       = "prod"
enable_api_key       = false
enable_cloudwatch_logs = true
EOF

# Plan the deployment
terraform plan

# Apply the configuration
terraform apply

# Get the API endpoint
terraform output api_endpoint
```

#### Deploy with API Key Authentication

```bash
cat > terraform.tfvars <<EOF
lambda_function_arn  = "arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent"
lambda_function_name = "aws-ops-agent"
api_stage_name       = "prod"
enable_api_key       = true
api_key_name         = "my-api-key"
enable_cloudwatch_logs = true
EOF

terraform apply

# Get the API key value (sensitive output)
terraform output -raw api_key_value
```

#### Destroy Resources

```bash
terraform destroy
```

### Option 3: AWS Console

1. **Create REST API**
   - Go to API Gateway console
   - Click "Create API" → "REST API" → "Build"
   - Name: `aws-ops-agent-api`
   - Endpoint Type: Regional

2. **Create /query Resource**
   - Click "Actions" → "Create Resource"
   - Resource Name: `query`
   - Resource Path: `/query`
   - Enable CORS: Yes

3. **Create POST Method**
   - Select `/query` resource
   - Click "Actions" → "Create Method" → "POST"
   - Integration type: Lambda Function
   - Use Lambda Proxy integration: Yes
   - Lambda Function: Select your Lambda function
   - Save and grant permissions

4. **Configure CORS**
   - Select `/query` resource
   - Click "Actions" → "Enable CORS"
   - Access-Control-Allow-Headers: `Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token`
   - Access-Control-Allow-Methods: `POST,OPTIONS`
   - Access-Control-Allow-Origin: `*`

5. **Deploy API**
   - Click "Actions" → "Deploy API"
   - Deployment stage: `prod` (or create new stage)
   - Deploy

6. **Optional: Create API Key**
   - Go to "API Keys" in left menu
   - Click "Actions" → "Create API Key"
   - Name: `aws-ops-agent-api-key`
   - Save the API key value

7. **Optional: Create Usage Plan**
   - Go to "Usage Plans" in left menu
   - Click "Create"
   - Add API stage
   - Associate API key

## Testing the API

### Without API Key

```bash
# Set your API endpoint
API_ENDPOINT="https://abc123.execute-api.us-east-1.amazonaws.com/prod/query"

# Test with a simple query
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Trace demo.example.com"
  }'

# Test with session ID
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show CloudFront logs for distribution E285K0Z0YGWJXZ",
    "session_id": "test-session-123"
  }'

# Test with max_results
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is 203.0.113.63?",
    "max_results": 50
  }'
```

### With API Key

```bash
# Set your API endpoint and key
API_ENDPOINT="https://abc123.execute-api.us-east-1.amazonaws.com/prod/query"
API_KEY="your-api-key-value"

# Test with API key
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "query": "Trace demo.example.com"
  }'
```

### Test CORS Preflight

```bash
curl -X OPTIONS $API_ENDPOINT \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v
```

## Expected Response Format

### Success Response

```json
{
  "status": "success",
  "result_type": "fqdn_trace",
  "output": "...",
  "query": "Trace demo.example.com",
  "session_id": "test-session-123",
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

## Monitoring and Logging

### CloudWatch Logs

API Gateway logs are available in CloudWatch Logs:

```bash
# View API Gateway logs
aws logs tail /aws/apigateway/aws-ops-agent-api --follow

# View Lambda logs
aws logs tail /aws/lambda/aws-ops-agent --follow
```

### CloudWatch Metrics

Monitor API Gateway metrics:

```bash
# Get API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=aws-ops-agent-api \
  --start-time 2025-01-12T00:00:00Z \
  --end-time 2025-01-12T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

### X-Ray Tracing

X-Ray tracing is enabled by default. View traces in the X-Ray console:

```bash
# Get X-Ray trace summaries
aws xray get-trace-summaries \
  --start-time 2025-01-12T00:00:00Z \
  --end-time 2025-01-12T23:59:59Z
```

## Throttling and Quotas

Default settings:

- **Burst Limit**: 100 requests
- **Rate Limit**: 50 requests per second
- **Daily Quota**: 10,000 requests (when API key is enabled)

To modify these settings, update the CloudFormation/Terraform configuration or adjust in the AWS Console under Usage Plans.

## Security Best Practices

1. **Enable API Key Authentication** for production environments
2. **Use AWS WAF** to protect against common web exploits
3. **Enable CloudWatch Logging** for audit trails
4. **Implement IP Whitelisting** if access should be restricted
5. **Use Custom Domain** with SSL/TLS certificate
6. **Enable X-Ray Tracing** for performance monitoring
7. **Set up CloudWatch Alarms** for error rates and latency

## Troubleshooting

### Common Issues

1. **403 Forbidden**
   - Check Lambda permissions for API Gateway invocation
   - Verify API key is correct (if enabled)

2. **500 Internal Server Error**
   - Check Lambda function logs in CloudWatch
   - Verify Lambda environment variables are set correctly

3. **504 Gateway Timeout**
   - Increase Lambda timeout (max 15 minutes)
   - Optimize query execution time

4. **CORS Errors**
   - Verify OPTIONS method is configured
   - Check CORS headers in Lambda response

### Debug Commands

```bash
# Test Lambda function directly
aws lambda invoke \
  --function-name aws-ops-agent \
  --payload '{"body": "{\"query\": \"Trace demo.example.com\"}"}' \
  response.json

# Check API Gateway configuration
aws apigateway get-rest-api --rest-api-id abc123

# Check Lambda permissions
aws lambda get-policy --function-name aws-ops-agent

# View recent API Gateway logs
aws logs tail /aws/apigateway/aws-ops-agent-api --since 1h
```

## Next Steps

1. **Set up Custom Domain**: Configure a custom domain name for the API
2. **Implement Rate Limiting**: Fine-tune throttling settings based on usage
3. **Add AWS WAF**: Protect the API with AWS WAF rules
4. **Create Client SDK**: Generate SDK for your preferred language
5. **Set up Monitoring**: Create CloudWatch dashboards and alarms
6. **Document API**: Create API documentation using API Gateway's export feature

## Resources

- [API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [Lambda Proxy Integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html)
- [API Gateway CORS](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-cors.html)
- [API Gateway Throttling](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
