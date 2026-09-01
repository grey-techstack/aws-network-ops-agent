# Terraform configuration for Lambda environment variables

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

variable "athena_database" {
  description = "Name of the Athena database for centralized logging"
  type        = string
  default     = "centralized_logging"
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Lambda function environment variables
resource "aws_lambda_function" "aws_ops_agent" {
  # ... other configuration ...

  environment {
    variables = {
      SSO_ROLE_ARN           = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.global_reader_role_name}"
      F5_SECRET_NAME         = var.f5_secret_name
      CORE_NETWORK_ACCOUNT_ID = var.core_network_account_id
      WORKLOAD_ACCOUNT_IDS   = join(",", var.workload_account_ids)
      ATHENA_DATABASE        = var.athena_database
      ATHENA_OUTPUT_BUCKET   = "aws-ops-agent-athena-results-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.name}"
    }
  }
}

# Example terraform.tfvars file content:
# core_network_account_id = "111111111111"
# workload_account_ids = ["222222222222", "333333333333", "444444444444"]
# global_reader_role_name = "GlobalReaderRole"
# f5_secret_name = "f5-distributed-cloud-api-credentials"
# athena_database = "centralized_logging"