# Complete AWS Operations Agent infrastructure deployment using Terraform

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "project_name" {
  description = "Name of the project (used for resource naming)"
  type        = string
  default     = "aws-ops-agent"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "global_reader_role_name" {
  description = "Name of the SSO Global Reader Role"
  type        = string
  default     = "GlobalReaderRole"
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

variable "f5_secret_name" {
  description = "Name of the F5 API credentials secret in Secrets Manager"
  type        = string
  default     = "f5-distributed-cloud-api-credentials"
}

variable "f5_api_url" {
  description = "F5 Distributed Cloud API URL"
  type        = string
  sensitive   = true
}

variable "f5_api_token" {
  description = "F5 API Token"
  type        = string
  sensitive   = true
}

variable "f5_namespace" {
  description = "F5 Namespace"
  type        = string
  default     = "system"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
  validation {
    condition     = var.lambda_timeout >= 30 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 30 and 900 seconds."
  }
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB."
  }
}

variable "athena_database" {
  description = "Athena database name for log queries"
  type        = string
  default     = "centralized_logging"
}

variable "athena_output_bucket" {
  description = "S3 bucket for Athena query results"
  type        = string
}

variable "api_stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "prod"
}

variable "enable_api_key" {
  description = "Enable API key authentication"
  type        = bool
  default     = false
}

variable "deployment_bucket" {
  description = "S3 bucket containing deployment packages"
  type        = string
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# S3 Bucket for Athena Results
resource "aws_s3_bucket" "athena_results" {
  bucket = var.athena_output_bucket

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "delete_old_query_results"
    status = "Enabled"

    expiration {
      days = 7
    }
  }
}

# Lambda Execution Role
resource "aws_iam_role" "lambda_execution_role" {
  name        = "${var.project_name}-execution-role-${var.environment}"
  description = "Execution role for ${var.project_name} Lambda function"

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
    Application = var.project_name
    Environment = var.environment
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
  name = "${var.project_name}-policy"
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
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}:*"
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

# F5 API Credentials Secret
resource "aws_secretsmanager_secret" "f5_api_credentials" {
  name        = var.f5_secret_name
  description = "F5 Distributed Cloud API credentials for ${var.project_name}"

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_secretsmanager_secret_version" "f5_api_credentials" {
  secret_id = aws_secretsmanager_secret.f5_api_credentials.id
  secret_string = jsonencode({
    api_url   = var.f5_api_url
    api_token = var.f5_api_token
    namespace = var.f5_namespace
  })
}

# Secret Resource Policy
resource "aws_secretsmanager_secret_policy" "f5_api_credentials" {
  secret_arn = aws_secretsmanager_secret.f5_api_credentials.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda_execution_role.arn
        }
        Action   = "secretsmanager:GetSecretValue"
        Resource = "*"
      }
    ]
  })
}

# Lambda Layer
resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "${var.project_name}-dependencies-${var.environment}"
  description         = "Dependencies layer for ${var.project_name}"
  s3_bucket           = var.deployment_bucket
  s3_key              = "lambda-layer.zip"
  compatible_runtimes = ["python3.11"]
  compatible_architectures = ["x86_64"]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}"
  retention_in_days = 7

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Lambda Function
resource "aws_lambda_function" "main" {
  function_name = "${var.project_name}-${var.environment}"
  description   = "AI-powered AWS operations assistant - ${var.environment}"
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "src.lambda_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size
  architectures = ["x86_64"]

  s3_bucket = var.deployment_bucket
  s3_key    = "aws-ops-agent-function.zip"

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      SSO_ROLE_ARN           = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.global_reader_role_name}"
      F5_SECRET_NAME         = var.f5_secret_name
      CORE_NETWORK_ACCOUNT_ID = var.core_network_account_id
      WORKLOAD_ACCOUNT_IDS   = join(",", var.workload_account_ids)
      ATHENA_DATABASE        = var.athena_database
      ATHENA_OUTPUT_BUCKET   = aws_s3_bucket.athena_results.id
      LOG_LEVEL              = "INFO"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "REST API for ${var.project_name} - ${var.environment}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# API Gateway Resource
resource "aws_api_gateway_resource" "query" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "query"
}

# API Gateway Method
resource "aws_api_gateway_method" "query_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "POST"
  authorization = var.enable_api_key ? "AWS_IAM" : "NONE"
  api_key_required = var.enable_api_key
}

# API Gateway Integration
resource "aws_api_gateway_integration" "query_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.main.invoke_arn
}

# API Gateway Method Response
resource "aws_api_gateway_method_response" "query_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_post.http_method
  status_code = "200"

  response_headers = {
    "Access-Control-Allow-Origin"  = true
    "Access-Control-Allow-Headers" = true
    "Access-Control-Allow-Methods" = true
  }
}

# CORS Options Method
resource "aws_api_gateway_method" "query_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "query_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_options.http_method

  type = "MOCK"

  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_method_response" "query_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_options.http_method
  status_code = "200"

  response_headers = {
    "Access-Control-Allow-Origin"  = true
    "Access-Control-Allow-Headers" = true
    "Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "query_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_options.http_method
  status_code = aws_api_gateway_method_response.query_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
  }
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_method.query_post,
    aws_api_gateway_integration.query_post,
    aws_api_gateway_method.query_options,
    aws_api_gateway_integration.query_options,
  ]

  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = var.api_stage_name

  stage_description = "${var.environment} stage for ${var.project_name} API"

  lifecycle {
    create_before_destroy = true
  }
}

# API Key (conditional)
resource "aws_api_gateway_api_key" "main" {
  count = var.enable_api_key ? 1 : 0

  name        = "${var.project_name}-api-key-${var.environment}"
  description = "API key for ${var.project_name} - ${var.environment}"
  enabled     = true

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Usage Plan (conditional)
resource "aws_api_gateway_usage_plan" "main" {
  count = var.enable_api_key ? 1 : 0

  name        = "${var.project_name}-usage-plan-${var.environment}"
  description = "Usage plan for ${var.project_name} - ${var.environment}"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_deployment.main.stage_name
  }

  throttle_settings {
    rate_limit  = 100
    burst_limit = 200
  }

  quota_settings {
    limit  = 10000
    period = "DAY"
  }

  tags = {
    Application = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Usage Plan Key (conditional)
resource "aws_api_gateway_usage_plan_key" "main" {
  count = var.enable_api_key ? 1 : 0

  key_id        = aws_api_gateway_api_key.main[0].id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.main[0].id
}

# Outputs
output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.main.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.main.function_name
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "api_gateway_url" {
  description = "URL of the API Gateway endpoint"
  value       = "${aws_api_gateway_deployment.main.invoke_url}/query"
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_api_gateway_rest_api.main.id
}

output "secret_arn" {
  description = "ARN of the F5 API credentials secret"
  value       = aws_secretsmanager_secret.f5_api_credentials.arn
}

output "secret_name" {
  description = "Name of the F5 API credentials secret"
  value       = aws_secretsmanager_secret.f5_api_credentials.name
}

output "athena_results_bucket_name" {
  description = "Name of the S3 bucket for Athena results"
  value       = aws_s3_bucket.athena_results.id
}

output "api_key_id" {
  description = "ID of the API key (if enabled)"
  value       = var.enable_api_key ? aws_api_gateway_api_key.main[0].id : null
}