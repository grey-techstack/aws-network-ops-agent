# IAM Deployment Guide

Complete guide for deploying IAM roles and policies for the AWS Operations Agent.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Deployment Options](#deployment-options)
3. [Option 1: CloudFormation Deployment](#option-1-cloudformation-deployment)
4. [Option 2: Terraform Deployment](#option-2-terraform-deployment)
5. [Option 3: AWS CLI Deployment](#option-3-aws-cli-deployment)
6. [Cross-Account Setup](#cross-account-setup)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools
- AWS CLI v2 (configured with appropriate credentials)
- CloudFormation or Terraform (depending on deployment method)

### AWS Permissions
Your AWS user/role needs the following permissions:
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `iam:CreatePolicy`
- `iam:PutRolePolicy`
- `iam:PassRole`
- `iam:TagRole`
- `cloudformation:CreateStack` (for CloudFormation)
- `cloudformation:UpdateStack` (for CloudFormation)

### Required Information
Before deployment, gather:
- **Core Network Account ID**: AWS account hosting shared network resources
- **Workload Account IDs**: List of AWS accounts hosting application workloads
- **SSO Role Name**: Name of the SSO Global Reader Role (default: GlobalReaderRole)
- **F5 Secret Name**: Secrets Manager secret name for F5 credentials (default: f5-distributed-cloud-api-credentials)

## Deployment Options

### Option 1: CloudFormation (Recommended)
- **Pros**: Declarative, rollback support, stack management
- **Cons**: AWS-specific
- **Best for**: Production deployments, teams familiar with CloudFormation

### Option 2: Terraform
- **Pros**: Multi-cloud, state management, modular
- **Cons**: Requires Terraform knowledge
- **Best for**: Infrastructure as Code workflows, multi-cloud environments

### Option 3: AWS CLI
- **Pros**: Simple, direct control
- **Cons**: No rollback, manual cleanup
- **Best for**: Development, testing, one-off deployments

## Option 1: CloudFormation Deployment

### Step 1: Set Environment Variables

```bash
# Required variables
export CORE_NETWORK_ACCOUNT_ID=111111111111
export WORKLOAD_ACCOUNT_IDS=222222222222,333333333333

# Optional variables (with defaults)
export STACK_NAME=aws-ops-agent-iam
export GLOBAL_READER_ROLE_NAME=GlobalReaderRole
export F5_SECRET_NAME=f5-distributed-cloud-api-credentials
```

### Step 2: Deploy Using Script (Recommended)

```bash
cd deployment
./deploy_iam_roles.sh
```

### Step 3: Deploy Manually

```bash
aws cloudformation create-stack \
  --stack-name aws-ops-agent-iam \
  --template-body file://iam-roles.yaml \
  --parameters \
    ParameterKey=GlobalReaderRoleName,ParameterValue=GlobalReaderRole \
    ParameterKey=F5SecretName,ParameterValue=f5-distributed-cloud-api-credentials \
    ParameterKey=CoreNetworkAccountId,ParameterValue=111111111111 \
    ParameterKey=WorkloadAccountIds,ParameterValue="222222222222,333333333333" \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Key=Application,Value=aws-ops-agent \
    Key=ManagedBy,Value=CloudFormation
```

### Step 4: Wait for Completion

```bash
aws cloudformation wait stack-create-complete --stack-name aws-ops-agent-iam
```

### Step 5: Get Outputs

```bash
# Get Lambda execution role ARN
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-iam \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaExecutionRoleArn`].OutputValue' \
  --output text

# Get Global Reader role ARN
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-iam \
  --query 'Stacks[0].Outputs[?OutputKey==`GlobalReaderRoleArn`].OutputValue' \
  --output text
```

## Option 2: Terraform Deployment

### Step 1: Initialize Terraform

```bash
cd deployment
terraform init
```

### Step 2: Create Variables File

Create `terraform.tfvars`:

```hcl
core_network_account_id = "111111111111"
workload_account_ids    = ["222222222222", "333333333333"]
global_reader_role_name = "GlobalReaderRole"
f5_secret_name         = "f5-distributed-cloud-api-credentials"
```

### Step 3: Plan Deployment

```bash
terraform plan -var-file="terraform.tfvars"
```

### Step 4: Apply Configuration

```bash
terraform apply -var-file="terraform.tfvars"
```

### Step 5: Get Outputs

```bash
terraform output lambda_execution_role_arn
terraform output global_reader_role_arn
```

## Option 3: AWS CLI Deployment

### Step 1: Create Lambda Execution Role

```bash
# Create role
aws iam create-role \
  --role-name aws-ops-agent-execution-role \
  --assume-role-policy-document file://iam-trust-policy.json \
  --description "Execution role for AWS Operations Agent Lambda function"

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name aws-ops-agent-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### Step 2: Create Custom Policy

```bash
# Get current account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

# Create policy (update iam-permissions-policy.json with actual values first)
aws iam create-policy \
  --policy-name aws-ops-agent-policy \
  --policy-document file://iam-permissions-policy.json \
  --description "Custom policy for AWS Operations Agent"

# Attach policy to role
aws iam attach-role-policy \
  --role-name aws-ops-agent-execution-role \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/aws-ops-agent-policy
```

### Step 3: Create Global Reader Role (Optional)

```bash
# Create Global Reader role template
aws iam create-role \
  --role-name GlobalReaderRole \
  --assume-role-policy-document file://global-reader-trust-policy.json \
  --description "Global reader role for AWS Operations Agent"

# Attach ReadOnlyAccess policy
aws iam attach-role-policy \
  --role-name GlobalReaderRole \
  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

# Create and attach custom reader policy
aws iam create-policy \
  --policy-name aws-ops-agent-reader-policy \
  --policy-document file://global-reader-permissions-policy.json

aws iam attach-role-policy \
  --role-name GlobalReaderRole \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/aws-ops-agent-reader-policy
```

## Cross-Account Setup

The AWS Operations Agent needs to access resources across multiple AWS accounts. This requires setting up cross-account trust relationships.

### Core Network Account Setup

In the **Core Network Account** (111111111111):

1. **Create Global Reader Role** (if not using SSO):

```bash
# Create trust policy allowing Lambda execution role to assume this role
cat > core-network-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::LAMBDA_ACCOUNT_ID:role/aws-ops-agent-execution-role"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "aws-ops-agent"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name GlobalReaderRole \
  --assume-role-policy-document file://core-network-trust-policy.json
```

2. **Attach Required Policies**:

```bash
# Attach AWS managed ReadOnlyAccess
aws iam attach-role-policy \
  --role-name GlobalReaderRole \
  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

# Attach custom policy for additional permissions
aws iam put-role-policy \
  --role-name GlobalReaderRole \
  --policy-name aws-ops-agent-reader-policy \
  --policy-document file://global-reader-permissions-policy.json
```

### Workload Account Setup

Repeat the above steps in each **Workload Account** (222222222222, 333333333333, etc.).

### SSO Integration

If using AWS SSO (recommended):

1. **Create Permission Set** in AWS SSO with:
   - ReadOnlyAccess managed policy
   - Custom inline policy (see `global-reader-permissions-policy.json`)

2. **Assign Permission Set** to appropriate accounts

3. **Update Trust Policy** to allow Lambda execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::LAMBDA_ACCOUNT_ID:role/aws-ops-agent-execution-role"
      },
      "Action": "sts:AssumeRole"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:saml-provider/AWSSSO_PROVIDER"
      },
      "Action": "sts:AssumeRoleWithSAML"
    }
  ]
}
```

## Verification

### Test Lambda Execution Role

```bash
# Verify role exists
aws iam get-role --role-name aws-ops-agent-execution-role

# List attached policies
aws iam list-attached-role-policies --role-name aws-ops-agent-execution-role

# Test role assumption (from Lambda context)
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/aws-ops-agent-execution-role \
  --role-session-name test-session
```

### Test Global Reader Role

```bash
# Test cross-account role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::CORE_NETWORK_ACCOUNT_ID:role/GlobalReaderRole \
  --role-session-name test-session \
  --external-id aws-ops-agent
```

### Test Permissions

```bash
# Test Route53 access
aws route53 list-hosted-zones

# Test CloudFront access
aws cloudfront list-distributions

# Test ELB access
aws elbv2 describe-load-balancers

# Test Athena access
aws athena list-work-groups

# Test Secrets Manager access
aws secretsmanager get-secret-value --secret-id f5-distributed-cloud-api-credentials
```

## Troubleshooting

### Common Issues

#### 1. Role Already Exists

**Error**: `EntityAlreadyExistsException: Role with name aws-ops-agent-execution-role already exists`

**Solution**:
```bash
# Delete existing role (be careful!)
aws iam detach-role-policy --role-name aws-ops-agent-execution-role --policy-arn POLICY_ARN
aws iam delete-role --role-name aws-ops-agent-execution-role

# Or update existing role
aws iam update-assume-role-policy \
  --role-name aws-ops-agent-execution-role \
  --policy-document file://iam-trust-policy.json
```

#### 2. Permission Denied

**Error**: `AccessDenied: User is not authorized to perform: iam:CreateRole`

**Solution**: Ensure your AWS user/role has the required IAM permissions listed in Prerequisites.

#### 3. Cross-Account Access Denied

**Error**: `AccessDenied: is not authorized to perform: sts:AssumeRole`

**Solution**:
- Verify trust policy in target account allows assumption
- Check external ID if required
- Ensure role exists in target account

#### 4. CloudFormation Stack Failed

**Error**: Stack creation failed

**Solution**:
```bash
# View stack events
aws cloudformation describe-stack-events --stack-name aws-ops-agent-iam

# View stack resources
aws cloudformation describe-stack-resources --stack-name aws-ops-agent-iam

# Delete failed stack
aws cloudformation delete-stack --stack-name aws-ops-agent-iam
```

### Debug Commands

```bash
# List all roles
aws iam list-roles --query 'Roles[?contains(RoleName, `aws-ops-agent`)]'

# Get role details
aws iam get-role --role-name aws-ops-agent-execution-role

# List role policies
aws iam list-role-policies --role-name aws-ops-agent-execution-role
aws iam list-attached-role-policies --role-name aws-ops-agent-execution-role

# Get policy document
aws iam get-role-policy --role-name aws-ops-agent-execution-role --policy-name aws-ops-agent-policy

# Test STS operations
aws sts get-caller-identity
aws sts assume-role --role-arn ROLE_ARN --role-session-name test
```

## Security Best Practices

1. **Principle of Least Privilege**: Only grant minimum required permissions
2. **External ID**: Use external ID for cross-account role assumption
3. **Condition Keys**: Use condition keys to restrict role usage
4. **Regular Audits**: Regularly review and audit role permissions
5. **Rotation**: Rotate credentials and review access patterns

## Next Steps

After successful IAM deployment:

1. **Deploy Lambda Function**: Use the Lambda execution role ARN
2. **Set Up Secrets Manager**: Create F5 API credentials secret
3. **Configure Cross-Account Access**: Set up trust relationships
4. **Test End-to-End**: Verify all permissions work correctly
5. **Deploy API Gateway**: Complete the infrastructure setup

## Additional Resources

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Cross-Account Access](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html)
- [AWS SSO Permission Sets](https://docs.aws.amazon.com/singlesignon/latest/userguide/permissionsetsconcept.html)
- [Lambda Execution Roles](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html)