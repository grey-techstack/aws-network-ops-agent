# Infrastructure as Code Guide

Complete guide for deploying the AWS Operations Agent using Infrastructure as Code (IaC) with CloudFormation or Terraform.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Options](#deployment-options)
4. [Option 1: CloudFormation](#option-1-cloudformation)
5. [Option 2: Terraform](#option-2-terraform)
6. [Complete Deployment Script](#complete-deployment-script)
7. [Configuration Management](#configuration-management)
8. [Multi-Environment Setup](#multi-environment-setup)
9. [CI/CD Integration](#cicd-integration)
10. [Monitoring and Maintenance](#monitoring-and-maintenance)
11. [Troubleshooting](#troubleshooting)

## Overview

The AWS Operations Agent infrastructure includes:

- **Lambda Function**: Core AI agent with LangChain orchestration
- **Lambda Layer**: Dependencies (LangChain, boto3, etc.)
- **IAM Roles**: Execution role with cross-account access
- **API Gateway**: REST API endpoint with CORS support
- **Secrets Manager**: F5 API credentials storage
- **S3 Bucket**: Athena query results storage
- **CloudWatch Logs**: Function logging and monitoring

### Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │───▶│  Lambda Function │───▶│   AWS Services  │
│                 │    │                 │    │  (Route53, ELB, │
│  - REST API     │    │  - Python 3.11  │    │   CloudFront,   │
│  - CORS         │    │  - LangChain     │    │   Athena, etc.) │
│  - API Key      │    │  - 5min timeout  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         │              │ Secrets Manager │              │
         │              │                 │              │
         │              │ F5 API Creds    │              │
         │              └─────────────────┘              │
         │                                               │
         ▼                                               ▼
┌─────────────────┐                            ┌─────────────────┐
│  CloudWatch     │                            │ Cross-Account   │
│  Logs           │                            │ IAM Roles       │
│                 │                            │                 │
│  - Function     │                            │ - Core Network  │
│  - API Gateway  │                            │ - Workload      │
└─────────────────┘                            └─────────────────┘
```

## Prerequisites

### Required Tools

- **AWS CLI v2**: Configured with appropriate credentials
- **CloudFormation** (for CloudFormation deployment)
- **Terraform** (for Terraform deployment)
- **jq**: JSON processing (optional but recommended)
- **bash**: For deployment scripts

### AWS Permissions

Your AWS user/role needs comprehensive permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "iam:*",
        "apigateway:*",
        "secretsmanager:*",
        "s3:*",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### Required Information

Before deployment, gather:

- **Core Network Account ID**: AWS account hosting shared network resources
- **Workload Account IDs**: List of AWS accounts hosting application workloads
- **F5 API URL**: F5 Distributed Cloud API endpoint
- **F5 API Token**: F5 API token with appropriate permissions
- **S3 Buckets**: Deployment bucket and Athena results bucket names

## Deployment Options

### Option 1: CloudFormation (Recommended)

**Pros:**
- Native AWS service
- Built-in rollback and drift detection
- Stack-based resource management
- Parameter validation
- Output exports for cross-stack references

**Cons:**
- AWS-specific (vendor lock-in)
- YAML/JSON syntax can be verbose
- Limited programming constructs

**Best for:**
- AWS-native environments
- Teams familiar with CloudFormation
- Production deployments requiring rollback capabilities

### Option 2: Terraform

**Pros:**
- Multi-cloud support
- HCL syntax is more readable
- State management and planning
- Modular design with modules
- Rich ecosystem of providers

**Cons:**
- Additional tool to learn and maintain
- State file management complexity
- Requires separate state storage

**Best for:**
- Multi-cloud environments
- Teams with Terraform expertise
- Infrastructure requiring complex logic

## Option 1: CloudFormation

### Step 1: Prepare Parameters

Create `parameters.json`:

```json
[
  {
    "ParameterKey": "ProjectName",
    "ParameterValue": "aws-ops-agent"
  },
  {
    "ParameterKey": "Environment",
    "ParameterValue": "prod"
  },
  {
    "ParameterKey": "CoreNetworkAccountId",
    "ParameterValue": "111111111111"
  },
  {
    "ParameterKey": "WorkloadAccountIds",
    "ParameterValue": "222222222222,333333333333"
  },
  {
    "ParameterKey": "F5ApiUrl",
    "ParameterValue": "https://your-tenant.console.ves.volterra.io/api"
  },
  {
    "ParameterKey": "F5ApiToken",
    "ParameterValue": "your-f5-api-token"
  },
  {
    "ParameterKey": "AthenaOutputBucket",
    "ParameterValue": "aws-ops-agent-athena-results-123456789012-us-east-1"
  },
  {
    "ParameterKey": "EnableApiKey",
    "ParameterValue": "true"
  }
]
```

### Step 2: Build and Upload Packages

```bash
# Build deployment packages
cd deployment
./build_package.sh

# Create S3 bucket for deployment artifacts
DEPLOYMENT_BUCKET="aws-ops-agent-deployment-$(aws sts get-caller-identity --query Account --output text)-$(aws configure get region)"
aws s3 mb "s3://$DEPLOYMENT_BUCKET"

# Upload packages
aws s3 cp lambda-layer.zip "s3://$DEPLOYMENT_BUCKET/lambda-layer.zip"
aws s3 cp aws-ops-agent-function.zip "s3://$DEPLOYMENT_BUCKET/aws-ops-agent-function.zip"
```

### Step 3: Deploy Stack

```bash
aws cloudformation create-stack \
  --stack-name aws-ops-agent-complete \
  --template-body file://aws-ops-agent-complete.yaml \
  --parameters file://parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Key=Application,Value=aws-ops-agent \
    Key=Environment,Value=prod \
    Key=ManagedBy,Value=CloudFormation
```

### Step 4: Monitor Deployment

```bash
# Wait for completion
aws cloudformation wait stack-create-complete --stack-name aws-ops-agent-complete

# Check status
aws cloudformation describe-stacks --stack-name aws-ops-agent-complete --query 'Stacks[0].StackStatus'

# View events
aws cloudformation describe-stack-events --stack-name aws-ops-agent-complete
```

### Step 5: Get Outputs

```bash
# Get API Gateway URL
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-complete \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text

# Get API Key (if enabled)
API_KEY_ID=$(aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-complete \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' \
  --output text)

aws apigateway get-api-key --api-key "$API_KEY_ID" --include-value --query 'value' --output text
```

## Option 2: Terraform

### Step 1: Initialize Terraform

```bash
cd deployment
terraform init
```

### Step 2: Create Variables File

Create `terraform.tfvars`:

```hcl
project_name               = "aws-ops-agent"
environment               = "prod"
core_network_account_id   = "111111111111"
workload_account_ids      = ["222222222222", "333333333333"]
f5_api_url               = "https://your-tenant.console.ves.volterra.io/api"
f5_api_token             = "your-f5-api-token"
athena_output_bucket     = "aws-ops-agent-athena-results-123456789012-us-east-1"
deployment_bucket        = "aws-ops-agent-deployment-123456789012-us-east-1"
enable_api_key           = true
```

### Step 3: Plan Deployment

```bash
terraform plan -var-file="terraform.tfvars" -out=tfplan
```

### Step 4: Apply Configuration

```bash
terraform apply tfplan
```

### Step 5: Get Outputs

```bash
terraform output api_gateway_url
terraform output api_key_id
```

## Complete Deployment Script

Use the automated deployment script for streamlined deployment:

### Step 1: Set Environment Variables

```bash
# Required variables
export CORE_NETWORK_ACCOUNT_ID=111111111111
export WORKLOAD_ACCOUNT_IDS=222222222222,333333333333
export F5_API_URL=https://your-tenant.console.ves.volterra.io/api
export F5_API_TOKEN=your-f5-api-token
export ATHENA_OUTPUT_BUCKET=aws-ops-agent-athena-results-123456789012-us-east-1
export DEPLOYMENT_BUCKET=aws-ops-agent-deployment-123456789012-us-east-1

# Optional variables
export ENABLE_API_KEY=true
export ENVIRONMENT=prod
```

### Step 2: Run Deployment Script

```bash
cd deployment
./deploy_complete_infrastructure.sh
```

The script will:
1. Validate prerequisites and parameters
2. Build and upload deployment packages
3. Deploy infrastructure using your chosen method
4. Display deployment outputs and test commands

## Configuration Management

### Environment-Specific Configurations

Create separate parameter files for each environment:

**dev-parameters.json:**
```json
[
  {
    "ParameterKey": "Environment",
    "ParameterValue": "dev"
  },
  {
    "ParameterKey": "LambdaTimeout",
    "ParameterValue": "60"
  },
  {
    "ParameterKey": "EnableApiKey",
    "ParameterValue": "false"
  }
]
```

**prod-parameters.json:**
```json
[
  {
    "ParameterKey": "Environment",
    "ParameterValue": "prod"
  },
  {
    "ParameterKey": "LambdaTimeout",
    "ParameterValue": "300"
  },
  {
    "ParameterKey": "EnableApiKey",
    "ParameterValue": "true"
  }
]
```

### Secrets Management

Store sensitive values in AWS Systems Manager Parameter Store:

```bash
# Store F5 API token
aws ssm put-parameter \
  --name "/aws-ops-agent/f5-api-token" \
  --value "your-f5-api-token" \
  --type "SecureString"

# Reference in CloudFormation
"F5ApiToken": {
  "Type": "AWS::SSM::Parameter::Value<String>",
  "Default": "/aws-ops-agent/f5-api-token"
}
```

## Multi-Environment Setup

### Environment Isolation

Deploy separate stacks for each environment:

```bash
# Development environment
aws cloudformation create-stack \
  --stack-name aws-ops-agent-dev \
  --template-body file://aws-ops-agent-complete.yaml \
  --parameters file://dev-parameters.json

# Production environment
aws cloudformation create-stack \
  --stack-name aws-ops-agent-prod \
  --template-body file://aws-ops-agent-complete.yaml \
  --parameters file://prod-parameters.json
```

### Cross-Environment Dependencies

Use CloudFormation exports for shared resources:

```yaml
# Shared resources stack
Outputs:
  VpcId:
    Value: !Ref VPC
    Export:
      Name: !Sub '${AWS::StackName}-VpcId'

# Application stack
Parameters:
  SharedVpcId:
    Type: String
    Default: !ImportValue shared-resources-VpcId
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy AWS Operations Agent

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1
    
    - name: Build deployment packages
      run: |
        cd deployment
        ./build_package.sh
    
    - name: Deploy infrastructure
      run: |
        cd deployment
        export CORE_NETWORK_ACCOUNT_ID=${{ secrets.CORE_NETWORK_ACCOUNT_ID }}
        export WORKLOAD_ACCOUNT_IDS=${{ secrets.WORKLOAD_ACCOUNT_IDS }}
        export F5_API_URL=${{ secrets.F5_API_URL }}
        export F5_API_TOKEN=${{ secrets.F5_API_TOKEN }}
        export ATHENA_OUTPUT_BUCKET=${{ secrets.ATHENA_OUTPUT_BUCKET }}
        export DEPLOYMENT_BUCKET=${{ secrets.DEPLOYMENT_BUCKET }}
        ./deploy_complete_infrastructure.sh
```

### AWS CodePipeline Example

Create `buildspec.yml`:

```yaml
version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.11
  
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws --version
  
  build:
    commands:
      - echo Build started on `date`
      - cd deployment
      - ./build_package.sh
      - ./deploy_complete_infrastructure.sh
  
  post_build:
    commands:
      - echo Build completed on `date`

artifacts:
  files:
    - '**/*'
```

## Monitoring and Maintenance

### CloudWatch Dashboards

Create monitoring dashboard:

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", "FunctionName", "aws-ops-agent-prod"],
          [".", "Errors", ".", "."],
          [".", "Duration", ".", "."]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Lambda Metrics"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ApiGateway", "Count", "ApiName", "aws-ops-agent-api-prod"],
          [".", "4XXError", ".", "."],
          [".", "5XXError", ".", "."]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "API Gateway Metrics"
      }
    }
  ]
}
```

### CloudWatch Alarms

```bash
# Lambda error alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "aws-ops-agent-lambda-errors" \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=aws-ops-agent-prod

# API Gateway 5xx alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "aws-ops-agent-api-5xx-errors" \
  --alarm-description "Alert on API Gateway 5xx errors" \
  --metric-name 5XXError \
  --namespace AWS/ApiGateway \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ApiName,Value=aws-ops-agent-api-prod
```

### Automated Updates

Create update script:

```bash
#!/bin/bash
# update_infrastructure.sh

# Update Lambda function code
aws lambda update-function-code \
  --function-name aws-ops-agent-prod \
  --s3-bucket "$DEPLOYMENT_BUCKET" \
  --s3-key aws-ops-agent-function.zip

# Update Lambda layer
NEW_LAYER_VERSION=$(aws lambda publish-layer-version \
  --layer-name aws-ops-agent-dependencies-prod \
  --s3-bucket "$DEPLOYMENT_BUCKET" \
  --s3-key lambda-layer.zip \
  --compatible-runtimes python3.11 \
  --query 'Version' \
  --output text)

aws lambda update-function-configuration \
  --function-name aws-ops-agent-prod \
  --layers "arn:aws:lambda:us-east-1:123456789012:layer:aws-ops-agent-dependencies-prod:$NEW_LAYER_VERSION"
```

## Troubleshooting

### Common Issues

#### 1. Stack Creation Failed

**Error**: `CREATE_FAILED` status

**Solution**:
```bash
# View stack events
aws cloudformation describe-stack-events --stack-name aws-ops-agent-complete

# Check specific resource failures
aws cloudformation describe-stack-resources --stack-name aws-ops-agent-complete
```

#### 2. Lambda Function Timeout

**Error**: Function times out during execution

**Solution**:
```bash
# Increase timeout
aws cloudformation update-stack \
  --stack-name aws-ops-agent-complete \
  --use-previous-template \
  --parameters ParameterKey=LambdaTimeout,ParameterValue=600
```

#### 3. API Gateway 403 Errors

**Error**: `{"message":"Forbidden"}`

**Solution**:
- Check API key configuration
- Verify Lambda permissions for API Gateway
- Review CORS settings

#### 4. Cross-Account Access Denied

**Error**: `AccessDenied` when assuming roles

**Solution**:
- Verify trust relationships in target accounts
- Check external ID configuration
- Ensure role exists in target accounts

### Debug Commands

```bash
# Test Lambda function directly
aws lambda invoke \
  --function-name aws-ops-agent-prod \
  --payload '{"body": "{\"query\": \"test\"}"}' \
  response.json

# View Lambda logs
aws logs tail /aws/lambda/aws-ops-agent-prod --follow

# Test API Gateway
curl -X POST https://api-id.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'

# Check secret access
aws secretsmanager get-secret-value --secret-id f5-distributed-cloud-api-credentials
```

### Performance Optimization

1. **Lambda Memory**: Increase memory for better performance
2. **API Gateway Caching**: Enable caching for frequently accessed queries
3. **Lambda Layers**: Use layers to reduce cold start times
4. **Connection Pooling**: Implement connection pooling for AWS services

## Best Practices

1. **Version Control**: Store all IaC templates in version control
2. **Parameter Validation**: Use parameter constraints and validation
3. **Resource Tagging**: Consistent tagging strategy for all resources
4. **Least Privilege**: Minimal IAM permissions for all roles
5. **Monitoring**: Comprehensive monitoring and alerting
6. **Documentation**: Keep deployment documentation up-to-date
7. **Testing**: Test infrastructure changes in non-production environments
8. **Backup**: Regular backups of critical configurations

## Cost Optimization

- Use appropriate Lambda memory allocation
- Enable API Gateway caching
- Set CloudWatch log retention policies
- Use S3 lifecycle policies for Athena results
- Monitor and optimize resource usage

## Security Considerations

- Enable CloudTrail for audit logging
- Use KMS encryption for sensitive data
- Implement least privilege access
- Regular security reviews and updates
- Network isolation where appropriate

## Next Steps

After successful deployment:

1. **Test End-to-End**: Verify all functionality works
2. **Set Up Monitoring**: Configure dashboards and alarms
3. **Document Procedures**: Create operational runbooks
4. **Train Team**: Ensure team understands the infrastructure
5. **Plan Maintenance**: Schedule regular updates and reviews

## Additional Resources

- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Infrastructure as Code Best Practices](https://docs.aws.amazon.com/whitepapers/latest/introduction-devops-aws/infrastructure-as-code.html)