# AWS Operations Agent - Environment Variables

This document describes the required environment variables for the AWS Operations Agent Lambda function.

## Required Environment Variables

### SSO_ROLE_ARN
- **Description**: ARN of the SSO (IAM Identity Center) global reader role to assume for AWS API access
- **Format**: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`
- **Example**: `arn:aws:iam::123456789012:role/GlobalReaderRole`
- **Requirements**: 
  - The Lambda execution role must have `sts:AssumeRole` permission for this role
  - This role must exist in the same account as the Lambda function
  - The role should have read-only permissions across all required AWS services

### F5_SECRET_NAME
- **Description**: Name of the AWS Secrets Manager secret containing F5 Distributed Cloud API credentials
- **Format**: String (secret name)
- **Example**: `f5-distributed-cloud-api-credentials`
- **Requirements**:
  - Secret must exist in the same region as the Lambda function
  - Lambda execution role must have `secretsmanager:GetSecretValue` permission
  - Secret should contain F5 API credentials in JSON format

### CORE_NETWORK_ACCOUNT_ID
- **Description**: AWS Account ID where core network resources (ALB/NLB) are hosted
- **Format**: 12-digit AWS Account ID
- **Example**: `111111111111`
- **Requirements**:
  - Must be a valid AWS Account ID
  - The SSO role must be assumable in this account for cross-account access

### WORKLOAD_ACCOUNT_IDS
- **Description**: Comma-separated list of AWS Account IDs where workload resources are hosted
- **Format**: Comma-separated list of 12-digit AWS Account IDs
- **Example**: `222222222222,333333333333,444444444444`
- **Requirements**:
  - Each account ID must be valid
  - The SSO role must be assumable in each account for cross-account access
  - No spaces between account IDs in the list

### ATHENA_DATABASE
- **Description**: Name of the Athena database containing centralized logging tables
- **Format**: String (database name)
- **Example**: `centralized_logging`
- **Requirements**:
  - Database must exist in Athena
  - Must contain required tables: `vpc_flow_logs`, `cloudfront_standard_logs`
  - The SSO role must have Athena query permissions

### ATHENA_OUTPUT_BUCKET
- **Description**: S3 bucket name for storing Athena query results
- **Format**: S3 bucket name
- **Example**: `aws-ops-agent-athena-results-123456789012-us-east-1`
- **Requirements**:
  - Bucket must exist in the same region as the Lambda function
  - The SSO role must have S3 read/write permissions for this bucket
  - Recommended naming: `aws-ops-agent-athena-results-{ACCOUNT_ID}-{REGION}`

## Configuration Examples

### AWS CLI
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

### CloudFormation
See `cloudformation_environment_variables.yaml` for a complete CloudFormation template snippet.

### Terraform
See `terraform_environment_variables.tf` for a complete Terraform configuration.

### AWS Console
1. Navigate to the Lambda function in the AWS Console
2. Go to the "Configuration" tab
3. Select "Environment variables" from the left menu
4. Add each environment variable with its corresponding value

## Validation

The Lambda function validates all required environment variables at startup. If any variable is missing or invalid, the function will fail to initialize and return an error.

### Validation Rules
- All variables must be present and non-empty
- `SSO_ROLE_ARN` must be a valid ARN format
- `CORE_NETWORK_ACCOUNT_ID` must be a 12-digit number
- `WORKLOAD_ACCOUNT_IDS` must be comma-separated 12-digit numbers
- `ATHENA_OUTPUT_BUCKET` must be a valid S3 bucket name

## Security Considerations

1. **Least Privilege**: Ensure the SSO role has only the minimum permissions required
2. **Cross-Account Access**: Verify trust relationships are properly configured for cross-account role assumption
3. **Secret Rotation**: Implement regular rotation for F5 API credentials
4. **Logging**: All environment variable access is logged (values are redacted for security)

## Troubleshooting

### Common Issues

1. **Missing Environment Variable**
   - Error: `Missing required environment variables: SSO_ROLE_ARN`
   - Solution: Ensure all required variables are set

2. **Invalid Role ARN**
   - Error: `Permission denied when assuming role`
   - Solution: Verify the Lambda execution role has `sts:AssumeRole` permission

3. **Cross-Account Access Denied**
   - Error: `AccessDenied` when accessing resources in other accounts
   - Solution: Verify the SSO role exists and is assumable in target accounts

4. **Athena Permissions**
   - Error: `Access denied for Athena query`
   - Solution: Verify the SSO role has Athena and S3 permissions

5. **F5 Secret Access**
   - Error: `Unable to retrieve F5 credentials`
   - Solution: Verify the secret exists and Lambda has `secretsmanager:GetSecretValue` permission

### Debugging

Enable debug logging by setting the Lambda function's log level to DEBUG to see detailed environment variable validation and usage information.