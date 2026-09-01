# Terraform configuration for API Gateway REST API

variable "lambda_function_arn" {
  description = "ARN of the Lambda function to integrate with API Gateway"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "api_stage_name" {
  description = "Name of the API Gateway stage"
  type        = string
  default     = "prod"
}

variable "enable_api_key" {
  description = "Enable API key authentication"
  type        = bool
  default     = false
}

variable "api_key_name" {
  description = "Name for the API key (if enabled)"
  type        = string
  default     = "aws-ops-agent-api-key"
}

variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch logging for API Gateway"
  type        = bool
  default     = true
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# REST API
resource "aws_api_gateway_rest_api" "aws_ops_agent" {
  name        = "aws-ops-agent-api"
  description = "REST API for AWS Operations Agent"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = "execute-api:Invoke"
        Resource  = "*"
      }
    ]
  })
}

# /query resource
resource "aws_api_gateway_resource" "query" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  parent_id   = aws_api_gateway_rest_api.aws_ops_agent.root_resource_id
  path_part   = "query"
}

# Request/Response Models
resource "aws_api_gateway_model" "query_request" {
  rest_api_id  = aws_api_gateway_rest_api.aws_ops_agent.id
  name         = "QueryRequest"
  description  = "Query request model"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "Query Request"
    type      = "object"
    required  = ["query"]
    properties = {
      query = {
        type        = "string"
        minLength   = 1
        description = "Natural language query for the agent"
      }
      session_id = {
        type        = "string"
        description = "Optional session ID for conversation context"
      }
      max_results = {
        type        = "integer"
        minimum     = 1
        maximum     = 1000
        default     = 100
        description = "Maximum number of results to return"
      }
    }
  })
}

resource "aws_api_gateway_model" "query_response" {
  rest_api_id  = aws_api_gateway_rest_api.aws_ops_agent.id
  name         = "QueryResponse"
  description  = "Query response model"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "Query Response"
    type      = "object"
    properties = {
      status = {
        type = "string"
        enum = ["success", "error"]
      }
      result_type = {
        type = "string"
      }
      output = {
        type = "string"
      }
      query = {
        type = "string"
      }
      session_id = {
        type = "string"
      }
      timestamp = {
        type = "string"
      }
      execution_time_ms = {
        type = "integer"
      }
    }
  })
}

resource "aws_api_gateway_model" "error_response" {
  rest_api_id  = aws_api_gateway_rest_api.aws_ops_agent.id
  name         = "ErrorResponse"
  description  = "Error response model"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "Error Response"
    type      = "object"
    properties = {
      status = {
        type = "string"
        enum = ["error"]
      }
      error_type = {
        type = "string"
      }
      error_message = {
        type = "string"
      }
      timestamp = {
        type = "string"
      }
    }
  })
}

# Request Validator
resource "aws_api_gateway_request_validator" "query_validator" {
  rest_api_id           = aws_api_gateway_rest_api.aws_ops_agent.id
  name                  = "query-request-validator"
  validate_request_body = true
  validate_request_parameters = true
}

# POST method for /query
resource "aws_api_gateway_method" "query_post" {
  rest_api_id   = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "POST"
  authorization = var.enable_api_key ? "API_KEY" : "NONE"
  api_key_required = var.enable_api_key

  request_models = {
    "application/json" = aws_api_gateway_model.query_request.name
  }

  request_validator_id = aws_api_gateway_request_validator.query_validator.id
}

# POST method integration
resource "aws_api_gateway_integration" "query_post" {
  rest_api_id             = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id             = aws_api_gateway_resource.query.id
  http_method             = aws_api_gateway_method.query_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"
}

# POST method response
resource "aws_api_gateway_method_response" "query_post_200" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_post.http_method
  status_code = "200"

  response_models = {
    "application/json" = aws_api_gateway_model.query_response.name
  }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

resource "aws_api_gateway_method_response" "query_post_400" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_post.http_method
  status_code = "400"

  response_models = {
    "application/json" = aws_api_gateway_model.error_response.name
  }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

resource "aws_api_gateway_method_response" "query_post_500" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_post.http_method
  status_code = "500"

  response_models = {
    "application/json" = aws_api_gateway_model.error_response.name
  }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# OPTIONS method for CORS preflight
resource "aws_api_gateway_method" "query_options" {
  rest_api_id   = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id   = aws_api_gateway_resource.query.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "query_options" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "query_options_200" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "query_options_200" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  resource_id = aws_api_gateway_resource.query.id
  http_method = aws_api_gateway_method.query_options.http_method
  status_code = aws_api_gateway_method_response.query_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  response_templates = {
    "application/json" = ""
  }
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.aws_ops_agent.execution_arn}/*/*/*"
}

# API Deployment
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id

  depends_on = [
    aws_api_gateway_integration.query_post,
    aws_api_gateway_integration.query_options
  ]

  lifecycle {
    create_before_destroy = true
  }

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.query.id,
      aws_api_gateway_method.query_post.id,
      aws_api_gateway_method.query_options.id,
      aws_api_gateway_integration.query_post.id,
      aws_api_gateway_integration.query_options.id,
    ]))
  }
}

# API Stage
resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.aws_ops_agent.id
  stage_name    = var.api_stage_name
  description   = "${var.api_stage_name} stage for AWS Operations Agent API"

  xray_tracing_enabled = true

  variables = {
    environment = var.api_stage_name
  }

  access_log_settings {
    destination_arn = var.enable_cloudwatch_logs ? aws_cloudwatch_log_group.api_gateway[0].arn : null
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
      errorType      = "$context.error.messageString"
    })
  }
}

# Method Settings
resource "aws_api_gateway_method_settings" "main" {
  rest_api_id = aws_api_gateway_rest_api.aws_ops_agent.id
  stage_name  = aws_api_gateway_stage.main.stage_name
  method_path = "*/*"

  settings {
    logging_level      = var.enable_cloudwatch_logs ? "INFO" : "OFF"
    data_trace_enabled = var.enable_cloudwatch_logs
    metrics_enabled    = true
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  count             = var.enable_cloudwatch_logs ? 1 : 0
  name              = "/aws/apigateway/aws-ops-agent-api"
  retention_in_days = 7

  tags = {
    Name        = "aws-ops-agent-api-logs"
    Environment = var.api_stage_name
  }
}

# IAM Role for API Gateway CloudWatch Logs
resource "aws_iam_role" "api_gateway_cloudwatch" {
  count = var.enable_cloudwatch_logs ? 1 : 0
  name  = "aws-ops-agent-api-gateway-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  count      = var.enable_cloudwatch_logs ? 1 : 0
  role       = aws_iam_role.api_gateway_cloudwatch[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# API Gateway Account (for CloudWatch Logs)
resource "aws_api_gateway_account" "main" {
  count               = var.enable_cloudwatch_logs ? 1 : 0
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch[0].arn
}

# API Key (optional)
resource "aws_api_gateway_api_key" "main" {
  count       = var.enable_api_key ? 1 : 0
  name        = var.api_key_name
  description = "API Key for AWS Operations Agent"
  enabled     = true
}

# Usage Plan (if API key is enabled)
resource "aws_api_gateway_usage_plan" "main" {
  count       = var.enable_api_key ? 1 : 0
  name        = "aws-ops-agent-usage-plan"
  description = "Usage plan for AWS Operations Agent API"

  api_stages {
    api_id = aws_api_gateway_rest_api.aws_ops_agent.id
    stage  = aws_api_gateway_stage.main.stage_name
  }

  throttle_settings {
    burst_limit = 100
    rate_limit  = 50
  }

  quota_settings {
    limit  = 10000
    period = "DAY"
  }
}

# Link API Key to Usage Plan
resource "aws_api_gateway_usage_plan_key" "main" {
  count         = var.enable_api_key ? 1 : 0
  key_id        = aws_api_gateway_api_key.main[0].id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.main[0].id
}

# Outputs
output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = "${aws_api_gateway_stage.main.invoke_url}/query"
}

output "api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.aws_ops_agent.id
}

output "api_key_id" {
  description = "API Key ID (retrieve value from AWS Console or CLI)"
  value       = var.enable_api_key ? aws_api_gateway_api_key.main[0].id : null
}

output "api_key_value" {
  description = "API Key value (sensitive)"
  value       = var.enable_api_key ? aws_api_gateway_api_key.main[0].value : null
  sensitive   = true
}

output "curl_example" {
  description = "Example curl command to test the API"
  value = var.enable_api_key ? <<-EOT
    curl -X POST ${aws_api_gateway_stage.main.invoke_url}/query \
      -H "Content-Type: application/json" \
      -H "x-api-key: YOUR_API_KEY" \
      -d '{"query": "Trace demo.example.com"}'
  EOT : <<-EOT
    curl -X POST ${aws_api_gateway_stage.main.invoke_url}/query \
      -H "Content-Type: application/json" \
      -d '{"query": "Trace demo.example.com"}'
  EOT
}
