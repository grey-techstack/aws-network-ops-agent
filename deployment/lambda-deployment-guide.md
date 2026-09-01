# Lambda Deployment Guide

Complete guide for deploying the AWS Operations Agent Lambda function with all required configurations.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Build Deployment Package](#build-deployment-package)
3. [Deploy Lambda Layer](#deploy-lambda-layer)
4. [Deploy Lambda Function](#deploy-lambda-function)
5. [Configure Environment Variables](#configure-environment-variables)
6. [Set Up IAM Roles](#set-up-iam-roles)
7. [Test Lambda Function](#test-lambda-function)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools
- AWS CLI v2 (configured with appropriate credentials)
- Python 3.11 or later
- pip (Python package manager)
- zip utility

### AWS Permissions
Your AWS user/role needs the following permissions:
- `lambda:CreateFunction`
- `lambda:UpdateFunctionCode`
- `lambda:UpdateFunctionConfiguration`
- `lambda:PublishLayerVersion`
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `iam:PassRole`
- `secretsmanager:CreateSecret`
- `secretsmanager:PutSecretValue`

### AWS Resources
Before deployment, ensure you have:
- SSO Global Reader Role ARN
- Core Network Account ID
- Workload Account IDs
- Athena database name (centralized_logging)
- S3 bucket for Athena query results
- F5 API credentials (for Secrets Manager)

## Build Deployment Package

### Step 1: Navigate to Deployment Directory

```bash
cd deployment
```

### Step 2: Run Build Script

```bash
./build_package.sh
```

This script will:
- Clean previous builds
- Install dependencies to Lambda layer
- Copy source code to function package
- Create `lambda-layer.zip` (dependencies)
- Create `aws-ops-agent-function.zip` (code)
- Generate `deployment-summary.txt`

### Step 3: Verify Build Output

```bash
ls -lh *.zip
```

Expected output:
```
-rw-r--r-- 1 user user  45M Jan 12 10:00 lambda-layer.zip
-rw-r--r-- 1 user user  50K Jan 12 10:00 aws-ops-agent-function.zip
```

## Deploy Lambda Layer

Lambda layers allow you to separate dependencies from your function code, reducing deployment package size and enabling dependency reuse.

### Option 1: AWS CLI

```bash
# Publish layer
aws lambda publish-layer-version \
  --layer-name aws-ops-agent-dependencies \
  --description "Dependencies for AWS Operations Agent" \
  --zip-file fileb://lambda-layer.zip \
  --compatible-runtimes python3.11 \
  --compatible-architectures x86_64

# Save the layer ARN from the output
LAYER_ARN=$(aws lambda list-layer-versions \
  --layer-name aws-ops-agent-dependencies \
  --query 'LayerVersions[0].LayerVersionArn' \
  --output text)

echo "Layer ARN: $LAYER_ARN"
```

### Option 2: CloudFormation

See `lambda-cloudformation.yaml` for complete template.

### Option 3: Terraform

See `lambda-terraform.tf` for complete configuration.

## Deploy Lambda Function

### Step 1: Create IAM Execution Role

First, create the Lambda execution role (see [Set Up IAM Roles](#set-up-iam-roles) section).

```bash
# Create execution role
aws iam create-role \
  --role-name aws-ops-agent-execution-role \
  --assume-role-policy-document file://iam-trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name aws-ops-agent-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
  --role-name aws-ops-agent-execution-role \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/aws-ops-agent-policy
```

### Step 2: Create Lambda Function

```bash
# Get execution role ARN
EXECUTION_ROLE_ARN=$(aws iam get-role \
  --role-name aws-ops-agent-execution-role \
  --query 'Role.Arn' \
  --output text)

# Create function
aws lambda create-function \
  --function-name aws-ops-agent \
  --runtime python3.11 \
  --role $EXECUTION_ROLE_ARN \
  --handler src.lambda_handler.lambda_handler \
  --zip-file fileb://aws-ops-agent-function.zip \
  --timeout 300 \
  --memory-size 512 \
  --layers $LAYER_ARN \
  --description "AI-powered AWS operations assistant" \
  --architectures x86_64
```

### Step 3: Configure Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --environment file://lambda_environment_variables.json
```

Or set variables individually:

```bash
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --environment Variables='{
    "SSO_ROLE_ARN":"arn:aws:iam::123456789012:role/GlobalReaderRole",
    "F5_SECRET_NAME":"f5-distributed-cloud-api-credentials",
    "CORE_NETWORK_ACCOUNT_ID":"111111111111",
    "WORKLOAD_ACCOUNT_IDS":"222222222222,333333333333",
    "ATHENA_DATABASE":"centralized_logging",
    "ATHENA_OUTPUT_BUCKET":"aws-ops-agent-athena-results-123456789012-us-east-1"
  }'
```

### Step 4: Enable CloudWatch Logs Insights (Optional)

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/aws-ops-agent \
  --retention-in-days 7
```

## Configure Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SSO_ROLE_ARN` | ARN of SSO global reader role | `arn:aws:iam::123456789012:role/GlobalReaderRole` |
| `F5_SECRET_NAME` | Secrets Manager secret name | `f5-distributed-cloud-api-credentials` |
| `CORE_NETWORK_ACCOUNT_ID` | Core network account ID | `111111111111` |
| `WORKLOAD_ACCOUNT_IDS` | Comma-separated workload account IDs | `222222222222,333333333333` |
| `ATHENA_DATABASE` | Athena database name | `centralized_logging` |
| `ATHENA_OUTPUT_BUCKET` | S3 bucket for Athena results | `aws-ops-agent-athena-results-123456789012-us-east-1` |

### Configuration Files

Use one of these configuration files:
- `lambda_environment_variables.json` - AWS CLI format
- `cloudformation_environment_variables.yaml` - CloudFormation format
- `terraform_environment_variables.tf` - Terraform format

See `ENVIRONMENT_VARIABLES.md` for detailed documentation.

## Set Up IAM Roles

### Lambda Execution Role

The Lambda execution role needs permissions for:
1. CloudWatch Logs (write logs)
2. STS AssumeRole (assume SSO role)
3. Secrets Manager (read F5 credentials)

#### Trust Policy

Create `iam-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

#### Permissions Policy

Create `iam-permissions-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/aws-ops-agent:*"
    },
    {
      "Sid": "AssumeSSORoles",
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": [
        "arn:aws:iam::*:role/GlobalReaderRole"
      ]
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:f5-distributed-cloud-api-credentials-*"
    },
    {
      "Sid": "BedrockAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
      ]
    }
  ]
}
```

#### Create Role and Attach Policies

```bash
# Create role
aws iam create-role \
  --role-name aws-ops-agent-execution-role \
  --assume-role-policy-document file://iam-trust-policy.json

# Create custom policy
aws iam create-policy \
  --policy-name aws-ops-agent-policy \
  --policy-document file://iam-permissions-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name aws-ops-agent-execution-role \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/aws-ops-agent-policy
```

### SSO Global Reader Role

The SSO role (assumed by Lambda) needs read-only permissions for:
- Route53
- CloudFront
- Elastic Load Balancing
- Athena
- S3 (for Athena results)
- EC2 (for IP lookups)

See `iam-sso-role-policy.json` for complete policy.

## Test Lambda Function

### Test 1: Basic Invocation

```bash
# Create test event
cat > test-event.json << EOF
{
  "body": "{\"query\": \"test\"}"
}
EOF

# Invoke function
aws lambda invoke \
  --function-name aws-ops-agent \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json

# View response
cat response.json | jq .
```

### Test 2: FQDN Trace

```bash
cat > test-trace.json << EOF
{
  "body": "{\"query\": \"Trace demo.example.com\"}"
}
EOF

aws lambda invoke \
  --function-name aws-ops-agent \
  --payload file://test-trace.json \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | jq .
```

### Test 3: IP Investigation

```bash
cat > test-ip.json << EOF
{
  "body": "{\"query\": \"What is 203.0.113.63?\"}"
}
EOF

aws lambda invoke \
  --function-name aws-ops-agent \
  --payload file://test-ip.json \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | jq .
```

### Test 4: Log Query

```bash
cat > test-logs.json << EOF
{
  "body": "{\"query\": \"Show CloudFront logs for distribution E285K0Z0YGWJXZ with errors from yesterday\"}"
}
EOF

aws lambda invoke \
  --function-name aws-ops-agent \
  --payload file://test-logs.json \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json | jq .
```

## Monitoring and Logging

### CloudWatch Logs

View Lambda logs:

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/aws-ops-agent --follow

# View recent logs
aws logs tail /aws/lambda/aws-ops-agent --since 1h

# Filter logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/aws-ops-agent \
  --filter-pattern "ERROR"
```

### CloudWatch Metrics

Key metrics to monitor:
- **Invocations**: Number of function invocations
- **Duration**: Execution time
- **Errors**: Number of errors
- **Throttles**: Number of throttled invocations
- **ConcurrentExecutions**: Number of concurrent executions

View metrics:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=aws-ops-agent \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### CloudWatch Alarms

Create alarm for errors:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name aws-ops-agent-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=aws-ops-agent
```

## Troubleshooting

### Common Issues

#### 1. Function Timeout

**Symptom**: Lambda times out after 300 seconds

**Solution**:
```bash
# Increase timeout to 900 seconds (15 minutes)
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --timeout 900
```

#### 2. Out of Memory

**Symptom**: Function fails with "Runtime exited with error: signal: killed"

**Solution**:
```bash
# Increase memory to 1024 MB
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --memory-size 1024
```

#### 3. Permission Denied

**Symptom**: "AccessDenied" errors in logs

**Solution**:
- Verify Lambda execution role has required permissions
- Check SSO role trust relationships
- Verify cross-account role assumption is configured

#### 4. Module Import Errors

**Symptom**: "ModuleNotFoundError: No module named 'langchain'"

**Solution**:
- Verify Lambda layer is attached to function
- Rebuild layer with correct dependencies
- Check layer compatibility with Python runtime

#### 5. Environment Variable Missing

**Symptom**: "Missing required environment variables"

**Solution**:
```bash
# Verify environment variables
aws lambda get-function-configuration \
  --function-name aws-ops-agent \
  --query 'Environment.Variables'
```

### Debug Mode

Enable debug logging:

```bash
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --environment Variables='{
    "SSO_ROLE_ARN":"...",
    "LOG_LEVEL":"DEBUG"
  }'
```

### View Function Configuration

```bash
aws lambda get-function-configuration \
  --function-name aws-ops-agent
```

### Update Function Code

```bash
# Rebuild package
cd deployment
./build_package.sh

# Update function
aws lambda update-function-code \
  --function-name aws-ops-agent \
  --zip-file fileb://aws-ops-agent-function.zip
```

### Update Layer

```bash
# Publish new layer version
aws lambda publish-layer-version \
  --layer-name aws-ops-agent-dependencies \
  --zip-file fileb://lambda-layer.zip \
  --compatible-runtimes python3.11

# Get new layer ARN
NEW_LAYER_ARN=$(aws lambda list-layer-versions \
  --layer-name aws-ops-agent-dependencies \
  --query 'LayerVersions[0].LayerVersionArn' \
  --output text)

# Update function to use new layer
aws lambda update-function-configuration \
  --function-name aws-ops-agent \
  --layers $NEW_LAYER_ARN
```

## Next Steps

After successful Lambda deployment:

1. **Deploy API Gateway**: See `API_GATEWAY_SETUP.md`
2. **Set Up Secrets Manager**: See section 12.3 in tasks.md
3. **Configure Cross-Account Access**: Set up trust relationships
4. **Test End-to-End**: Use `test_api_gateway.sh`
5. **Set Up Monitoring**: Configure CloudWatch dashboards and alarms

## Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [IAM Roles for Lambda](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html)
