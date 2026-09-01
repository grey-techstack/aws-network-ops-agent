# Terraform configuration for IAM roles and policies

variable "global_reader_role_name" {
  description = "Name of the SSO Global Reader Role"
  type        = string
  default     = "GlobalReaderRole"
}

variable "f5_secret_name" {
  description = "Name of the F5 API credentials secret in Secrets Manager"
  type        = string
  default     = "f5-distributed-cloud-api-credentials"
}

variable "core_network_account_id" {
  description = "AWS Account ID for Core Network resources"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.core_network_account_id))
    error_message = "Core network account ID must be a valid 12-digit AWS Account ID."
  }
}

variable "workload_account_ids" {
  description = "List of Workload Account IDs"
  type        = list(string)
  validation {
    condition = alltrue([
      for account_id in var.workload_account_ids : can(regex("^[0-9]{12}$", account_id))
    ])
    error_message = "All workload account IDs must be valid 12-digit AWS Account IDs."
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Lambda Execution Role
resource "aws_iam_role" "lambda_execution_role" {
  name        = "aws-ops-agent-execution-role"
  description = "Execution role for AWS Operations Agent Lambda function"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Application = "aws-ops-agent"
    ManagedBy   = "Terraform"
  }
}

# Attach AWS managed policy for basic Lambda execution
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for Lambda execution role
resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "aws-ops-agent-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/aws-ops-agent:*"
      },
      {
        Sid    = "AssumeSSORoles"
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Resource = concat(
          [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.global_reader_role_name}",
            "arn:aws:iam::${var.core_network_account_id}:role/${var.global_reader_role_name}"
          ],
          [for account_id in var.workload_account_ids : "arn:aws:iam::${account_id}:role/${var.global_reader_role_name}"]
        )
      },
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.f5_secret_name}-*"
      },
      {
        Sid    = "BedrockAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-*",
          "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
        ]
      }
    ]
  })
}

# SSO Global Reader Role (template)
# Note: Actual SSO roles are typically managed by AWS SSO
# This is provided as a reference for required permissions
resource "aws_iam_role" "global_reader_role" {
  name        = var.global_reader_role_name
  description = "Global reader role for AWS Operations Agent (SSO-managed)"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda_execution_role.arn
        }
        Action = "sts:AssumeRole"
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.core_network_account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "aws-ops-agent"
          }
        }
      }
    ]
  })

  tags = {
    Application = "aws-ops-agent"
    ManagedBy   = "Terraform"
  }
}

# Attach AWS managed ReadOnlyAccess policy
resource "aws_iam_role_policy_attachment" "global_reader_readonly" {
  role       = aws_iam_role.global_reader_role.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Custom policy for Global Reader role
resource "aws_iam_role_policy" "global_reader_policy" {
  name = "aws-ops-agent-reader-policy"
  role = aws_iam_role.global_reader_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Route53ReadAccess"
        Effect = "Allow"
        Action = [
          "route53:GetHostedZone",
          "route53:ListHostedZones",
          "route53:ListResourceRecordSets",
          "route53:GetChange"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudFrontReadAccess"
        Effect = "Allow"
        Action = [
          "cloudfront:GetDistribution",
          "cloudfront:GetDistributionConfig",
          "cloudfront:ListDistributions",
          "cloudfront:ListDistributionsByWebACLId"
        ]
        Resource = "*"
      },
      {
        Sid    = "ELBReadAccess"
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetHealth",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:DescribeTags"
        ]
        Resource = "*"
      },
      {
        Sid    = "AthenaReadAccess"
        Effect = "Allow"
        Action = [
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup",
          "athena:ListWorkGroups",
          "athena:GetDataCatalog",
          "athena:GetDatabase",
          "athena:GetTableMetadata",
          "athena:ListDatabases",
          "athena:ListTableMetadata"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3AthenaAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          "arn:aws:s3:::aws-ops-agent-athena-results-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}",
          "arn:aws:s3:::aws-ops-agent-athena-results-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}/*"
        ]
      },
      {
        Sid    = "EC2ReadAccess"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeAddresses",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribePrefixLists"
        ]
        Resource = "*"
      },
      {
        Sid    = "GlueDataCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions"
        ]
        Resource = "*"
      }
    ]
  })
}

# Outputs
output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "lambda_execution_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda_execution_role.name
}

output "global_reader_role_arn" {
  description = "ARN of the Global Reader role"
  value       = aws_iam_role.global_reader_role.arn
}

output "global_reader_role_name" {
  description = "Name of the Global Reader role"
  value       = aws_iam_role.global_reader_role.name
}
