# AWS Secrets Manager Setup Guide

Complete guide for setting up AWS Secrets Manager to store F5 Distributed Cloud API credentials for the AWS Operations Agent.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Deployment Options](#deployment-options)
3. [Option 1: Automated Script](#option-1-automated-script)
4. [Option 2: CloudFormation](#option-2-cloudformation)
5. [Option 3: AWS CLI](#option-3-aws-cli)
6. [Testing Secret Access](#testing-secret-access)
7. [Secret Rotation](#secret-rotation)
8. [Security Best Practices](#security-best-practices)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools
- AWS CLI v2 (configured with appropriate credentials)
- jq (optional, for JSON processing)

### AWS Permissions
Your AWS user/role needs the following permissions:
- `secretsmanager:CreateSecret`
- `secretsmanager:UpdateSecret`
- `secretsmanager:PutResourcePolicy`
- `secretsmanager:GetSecretValue`
- `kms:CreateKey` (optional, for custom encryption)
- `kms:CreateAlias` (optional, for custom encryption)

### Required Information
Before deployment, gather:
- **F5 API URL**: Your F5 Distributed Cloud API endpoint (e.g., `https://your-tenant.console.ves.volterra.io/api`)
- **F5 API Token**: Your F5 API token with appropriate permissions
- **F5 Namespace**: F5 namespace (default: `system`)
- **Lambda Execution Role ARN**: ARN of the Lambda execution role that needs access

## Deployment Options

### Option 1: Automated Script (Recommended)
- **Pros**: Interactive, guided setup, error handling
- **Cons**: Requires bash shell
- **Best for**: Development, testing, first-time setup

### Option 2: CloudFormation
- **Pros**: Declarative, version controlled, rollback support
- **Cons**: Requires parameters file
- **Best for**: Production deployments, CI/CD pipelines

### Option 3: AWS CLI
- **Pros**: Direct control, scriptable
- **Cons**: Manual steps, no rollback
- **Best for**: Automation scripts, custom workflows

## Option 1: Automated Script

### Step 1: Run Setup Script

```bash
cd deployment
./setup_secrets_manager.sh
```

The script will:
1. Check prerequisites
2. Prompt for F5 credentials
3. Create the secret
4. Grant Lambda access
5. Test secret retrieval

### Step 2: Follow Interactive Prompts

```
F5 API URL (e.g., https://your-tenant.console.ves.volterra.io/api): https://your-tenant.console.ves.volterra.io/api
F5 API Token: [enter your token]
F5 Namespace (optional, default: system): system
```

### Step 3: Verify Output

The script will display:
- Secret ARN
- Environment variable for Lambda
- Next steps

## Option 2: CloudFormation

### Step 1: Create Parameters File

Create `secrets-parameters.json`:

```json
[
  {
    "ParameterKey": "SecretName",
    "ParameterValue": "f5-distributed-cloud-api-credentials"
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
    "ParameterKey": "F5Namespace",
    "ParameterValue": "system"
  },
  {
    "ParameterKey": "LambdaExecutionRoleArn",
    "ParameterValue": "arn:aws:iam::123456789012:role/aws-ops-agent-execution-role"
  }
]
```

### Step 2: Deploy Stack

```bash
aws cloudformation create-stack \
  --stack-name aws-ops-agent-secrets \
  --template-body file://secrets-manager-cloudformation.yaml \
  --parameters file://secrets-parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Key=Application,Value=aws-ops-agent \
    Key=ManagedBy,Value=CloudFormation
```

### Step 3: Wait for Completion

```bash
aws cloudformation wait stack-create-complete --stack-name aws-ops-agent-secrets
```

### Step 4: Get Outputs

```bash
# Get secret ARN
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-secrets \
  --query 'Stacks[0].Outputs[?OutputKey==`SecretArn`].OutputValue' \
  --output text

# Get secret name
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-secrets \
  --query 'Stacks[0].Outputs[?OutputKey==`SecretName`].OutputValue' \
  --output text
```

## Option 3: AWS CLI

### Step 1: Create Secret

```bash
# Set variables
SECRET_NAME="f5-distributed-cloud-api-credentials"
F5_API_URL="https://your-tenant.console.ves.volterra.io/api"
F5_API_TOKEN="your-f5-api-token"
F5_NAMESPACE="system"

# Create secret JSON
SECRET_VALUE=$(cat << EOF
{
  "api_url": "$F5_API_URL",
  "api_token": "$F5_API_TOKEN",
  "namespace": "$F5_NAMESPACE"
}
EOF
)

# Create secret
aws secretsmanager create-secret \
  --name "$SECRET_NAME" \
  --description "F5 Distributed Cloud API credentials for AWS Operations Agent" \
  --secret-string "$SECRET_VALUE" \
  --tags Key=Application,Value=aws-ops-agent Key=ManagedBy,Value=CLI
```

### Step 2: Grant Lambda Access

```bash
# Get Lambda role ARN
LAMBDA_ROLE_ARN=$(aws iam get-role \
  --role-name aws-ops-agent-execution-role \
  --query 'Role.Arn' \
  --output text)

# Create resource policy
RESOURCE_POLICY=$(cat << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "$LAMBDA_ROLE_ARN"
      },
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "*"
    }
  ]
}
EOF
)

# Apply resource policy
aws secretsmanager put-resource-policy \
  --secret-id "$SECRET_NAME" \
  --resource-policy "$RESOURCE_POLICY"
```

### Step 3: Test Secret Access

```bash
# Retrieve secret
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --query 'SecretString' \
  --output text | jq .
```

## Testing Secret Access

### Test from Lambda Context

Create a test Lambda function to verify access:

```python
import json
import boto3

def lambda_handler(event, context):
    # Initialize Secrets Manager client
    secrets_client = boto3.client('secretsmanager')
    
    try:
        # Retrieve F5 credentials
        response = secrets_client.get_secret_value(
            SecretId='f5-distributed-cloud-api-credentials'
        )
        
        # Parse credentials
        credentials = json.loads(response['SecretString'])
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Secret retrieved successfully',
                'api_url': credentials['api_url'],
                'namespace': credentials['namespace']
                # Note: Don't return the API token in logs
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
```

### Test F5 API Connectivity

```python
import json
import boto3
import requests

def test_f5_api_connection():
    # Get credentials from Secrets Manager
    secrets_client = boto3.client('secretsmanager')
    response = secrets_client.get_secret_value(
        SecretId='f5-distributed-cloud-api-credentials'
    )
    credentials = json.loads(response['SecretString'])
    
    # Test F5 API connection
    headers = {
        'Authorization': f'APIToken {credentials["api_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Test endpoint (adjust based on your F5 setup)
    test_url = f"{credentials['api_url']}/config/namespaces/{credentials['namespace']}/http_loadbalancers"
    
    try:
        response = requests.get(test_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return {
            'success': True,
            'status_code': response.status_code,
            'message': 'F5 API connection successful'
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': str(e)
        }
```

## Secret Rotation

### Manual Rotation

To manually rotate the F5 API token:

1. **Generate New Token** in F5 Distributed Cloud console
2. **Update Secret**:

```bash
# Create new secret value
NEW_SECRET_VALUE=$(cat << EOF
{
  "api_url": "$F5_API_URL",
  "api_token": "$NEW_F5_API_TOKEN",
  "namespace": "$F5_NAMESPACE"
}
EOF
)

# Update secret
aws secretsmanager update-secret \
  --secret-id "$SECRET_NAME" \
  --secret-string "$NEW_SECRET_VALUE"
```

3. **Test New Token** using the test functions above
4. **Revoke Old Token** in F5 console

### Automatic Rotation (Advanced)

For automatic rotation, you need to:

1. **Create Rotation Lambda Function**:
   - Generate new F5 API token via F5 API
   - Test new token
   - Update secret with new token
   - Revoke old token

2. **Enable Rotation**:

```bash
aws secretsmanager rotate-secret \
  --secret-id "$SECRET_NAME" \
  --rotation-lambda-arn "arn:aws:lambda:region:account:function:f5-secret-rotation" \
  --rotation-rules AutomaticallyAfterDays=30
```

## Security Best Practices

### 1. Encryption
- Secrets are encrypted at rest using AWS KMS
- Consider using customer-managed KMS keys for additional control
- Enable CloudTrail logging for secret access

### 2. Access Control
- Use least privilege IAM policies
- Limit secret access to specific Lambda functions
- Use resource-based policies for fine-grained control

### 3. Monitoring
- Monitor secret access in CloudTrail
- Set up CloudWatch alarms for unusual access patterns
- Enable AWS Config for compliance monitoring

### 4. Rotation
- Implement regular secret rotation
- Test rotation process in non-production environments
- Have rollback procedures for failed rotations

### Example KMS Key Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Enable IAM User Permissions",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "Allow Lambda Role Access",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/aws-ops-agent-execution-role"
      },
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "*"
    }
  ]
}
```

## Troubleshooting

### Common Issues

#### 1. Secret Not Found

**Error**: `ResourceNotFoundException: Secrets Manager can't find the specified secret`

**Solution**:
```bash
# List secrets to verify name
aws secretsmanager list-secrets --query 'SecretList[?contains(Name, `f5`)]'

# Check secret exists in correct region
aws secretsmanager describe-secret --secret-id "f5-distributed-cloud-api-credentials"
```

#### 2. Access Denied

**Error**: `AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue`

**Solution**:
- Verify Lambda execution role has `secretsmanager:GetSecretValue` permission
- Check resource policy allows Lambda role access
- Verify secret ARN in IAM policy

#### 3. Invalid JSON

**Error**: `InvalidParameterException: You provided invalid JSON`

**Solution**:
```bash
# Validate JSON before creating secret
echo "$SECRET_VALUE" | jq .

# Fix JSON formatting
SECRET_VALUE='{"api_url":"https://example.com","api_token":"token","namespace":"system"}'
```

#### 4. F5 API Connection Failed

**Error**: Connection timeout or authentication failed

**Solution**:
- Verify F5 API URL is correct
- Check API token has required permissions
- Test from Lambda VPC if using VPC endpoints
- Verify security groups allow outbound HTTPS

### Debug Commands

```bash
# List all secrets
aws secretsmanager list-secrets

# Get secret metadata
aws secretsmanager describe-secret --secret-id "f5-distributed-cloud-api-credentials"

# Get secret value (be careful with logging)
aws secretsmanager get-secret-value --secret-id "f5-distributed-cloud-api-credentials"

# List secret versions
aws secretsmanager list-secret-version-ids --secret-id "f5-distributed-cloud-api-credentials"

# Get resource policy
aws secretsmanager get-resource-policy --secret-id "f5-distributed-cloud-api-credentials"
```

## Cost Optimization

- **Secret Storage**: $0.40 per secret per month
- **API Calls**: $0.05 per 10,000 API calls
- **Rotation**: Additional Lambda costs for rotation function

## Next Steps

After successful Secrets Manager setup:

1. **Update Lambda Environment Variables**: Set `F5_SECRET_NAME`
2. **Test F5 Integration**: Verify F5 API connectivity from Lambda
3. **Implement Secret Rotation**: Set up automatic rotation (optional)
4. **Monitor Access**: Set up CloudWatch alarms and dashboards
5. **Document Procedures**: Create runbooks for secret management

## Additional Resources

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Secret Rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [F5 Distributed Cloud API Documentation](https://docs.cloud.f5.com/docs/api)