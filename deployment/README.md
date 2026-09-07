# AWS Operations Agent Deployment

This directory contains scripts and configuration for building and deploying the AWS Operations Agent, including the Lambda function and API Gateway.

## Quick Start

### 1. Standard Deployment

```bash
cd deployment
./build_package.sh
./deploy_complete_infrastructure.sh
```

### 2. Teams Integration (NEW! 🎉)

Integrate with Microsoft Teams to ask questions directly in your channel:

```bash
# Set your Teams Incoming Webhook URL
export TEAMS_INCOMING_WEBHOOK_URL='https://outlook.office.com/webhook/...'

# Deploy Teams integration
./deploy_teams_webhook.sh

# Test the integration
./test_teams_webhook.sh
```

Then in Teams:
```
@AWSBot 查詢 myapp 的 DNS
```

📚 **See [TEAMS_INTEGRATION_QUICKSTART.md](./TEAMS_INTEGRATION_QUICKSTART.md) for complete setup guide**

### 3. Test Deployment

```bash
cd deployment
./test_api_gateway.sh
```

## Deployment Components

### Lambda Function

The Lambda function is the core of the AWS Operations Agent, handling query processing and AWS service interactions.

#### Building the Deployment Package

##### Using Lambda Layers (Recommended)

```bash
# Create layer for dependencies
mkdir -p lambda_layer/python
pip install -r ../requirements.txt -t lambda_layer/python/

# Zip the layer
cd lambda_layer
zip -r ../lambda-layer.zip .
cd ..

# Create function package (code only)
cd ..
zip -r deployment/aws-ops-agent-function.zip src/
```

##### Using Build Script

```bash
cd deployment
./build_package.sh
```

#### Lambda Configuration

##### Environment Variables

- `SSO_ROLE_ARN`: ARN of the SSO global reader role
- `F5_SECRET_NAME`: Secrets Manager secret name for F5 API credentials
- `CORE_NETWORK_ACCOUNT_ID`: Core network AWS account ID
- `WORKLOAD_ACCOUNT_IDS`: Comma-separated workload account IDs
- `ATHENA_DATABASE`: Athena database name (centralized_logging)
- `ATHENA_OUTPUT_BUCKET`: S3 bucket for Athena query results

##### Function Settings

- Runtime: Python 3.11
- Handler: src.lambda_handler.lambda_handler
- Timeout: 300 seconds (5 minutes)
- Memory: 512 MB
- Architecture: x86_64

### API Gateway

The API Gateway provides a REST API endpoint for submitting queries to the Lambda function.

#### Deployment Options

##### Option 1: Automated Deployment Script

```bash
cd deployment
export LAMBDA_FUNCTION_NAME=aws-ops-agent
export STACK_NAME=aws-ops-agent-api
export STAGE_NAME=prod
export ENABLE_API_KEY=false
./deploy_api_gateway.sh
```

##### Option 2: CloudFormation

```bash
aws cloudformation create-stack \
  --stack-name aws-ops-agent-api \
  --template-body file://api-gateway-cloudformation.yaml \
  --parameters \
    ParameterKey=LambdaFunctionArn,ParameterValue=arn:aws:lambda:REGION:ACCOUNT:function:aws-ops-agent \
    ParameterKey=ApiStageName,ParameterValue=prod \
    ParameterKey=EnableApiKey,ParameterValue=false \
  --capabilities CAPABILITY_IAM
```

##### Option 3: Terraform

```bash
cd deployment
terraform init
terraform apply -var="lambda_function_arn=arn:aws:lambda:REGION:ACCOUNT:function:aws-ops-agent"
```

#### Testing API Gateway

```bash
# Automated test suite
cd deployment
./test_api_gateway.sh

# Manual test
curl -X POST https://YOUR-API-ID.execute-api.REGION.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Trace demo.example.com"}'
```

## Detailed Documentation

- **[API Gateway Setup Guide](API_GATEWAY_SETUP.md)**: Complete guide for deploying and configuring API Gateway
- **[Streaming Setup Guide](STREAMING_SETUP.md)**: Optional guide for enabling response streaming
- **[Environment Variables](../ENVIRONMENT_VARIABLES.md)**: Detailed environment variable documentation

## Deployment Files

- `build_package.sh`: Build Lambda deployment package
- `deploy_api_gateway.sh`: Deploy API Gateway using CloudFormation
- `test_api_gateway.sh`: Test API Gateway endpoint
- `api-gateway-cloudformation.yaml`: CloudFormation template for API Gateway
- `api-gateway-terraform.tf`: Terraform configuration for API Gateway
- `cloudformation_environment_variables.yaml`: CloudFormation environment variables snippet
- `terraform_environment_variables.tf`: Terraform environment variables configuration

## Architecture

```
User → API Gateway → Lambda Function → AWS Services (Route53, CloudFront, ELB, Athena, etc.)
                                    → F5 Distributed Cloud API
                                    → CloudWatch Logs
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.11 or later
- Terraform (if using Terraform deployment)
- jq (optional, for JSON formatting in tests)

## Security Considerations

1. **API Key Authentication**: Enable API key authentication for production environments
2. **IAM Roles**: Ensure Lambda execution role has minimal required permissions
3. **Secrets Manager**: Store F5 API credentials securely in Secrets Manager
4. **CloudWatch Logs**: Enable logging for audit trails
5. **VPC**: Consider deploying Lambda in VPC for enhanced security

## Monitoring

- **CloudWatch Logs**: `/aws/lambda/aws-ops-agent` and `/aws/apigateway/aws-ops-agent-api`
- **CloudWatch Metrics**: Monitor Lambda invocations, errors, duration, and API Gateway requests
- **X-Ray Tracing**: Enabled by default for distributed tracing

## Troubleshooting

### Common Issues

1. **Lambda Timeout**: Increase timeout if queries take longer than 5 minutes
2. **Permission Errors**: Verify Lambda execution role has required permissions
3. **API Gateway 403**: Check Lambda permissions for API Gateway invocation
4. **Environment Variables**: Ensure all required environment variables are set

### Debug Commands

```bash
# View Lambda logs
aws logs tail /aws/lambda/aws-ops-agent --follow

# View API Gateway logs
aws logs tail /aws/apigateway/aws-ops-agent-api --follow

# Test Lambda directly
aws lambda invoke \
  --function-name aws-ops-agent \
  --payload '{"body": "{\"query\": \"test\"}"}' \
  response.json

# Get API Gateway configuration
aws apigateway get-rest-api --rest-api-id YOUR-API-ID
```

## Cost Optimization

- Use Lambda layers to reduce deployment package size
- Enable API Gateway caching for frequently accessed queries
- Set appropriate Lambda memory allocation (512 MB recommended)
- Use CloudWatch Logs retention policies to manage log storage costs

## Next Steps

1. Deploy Lambda function with required IAM roles and environment variables
2. Deploy API Gateway using one of the provided methods
3. Test the API endpoint with the test script
4. Configure monitoring and alarms
5. (Optional) Set up custom domain name for API Gateway
6. (Optional) Enable response streaming for long-running queries
