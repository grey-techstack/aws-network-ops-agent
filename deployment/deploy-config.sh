#!/bin/bash
# AWS Operations Agent 部署配置 - DEV ACCOUNT
# 自動生成於 Wed Jan 14 13:58:25 HKT 2026

# Dev Account - All resources in one account
export DEV_ACCOUNT_ID=123456789012

# Core Network Account (using dev account)
export CORE_NETWORK_ACCOUNT_ID=123456789012

# Workload Accounts (using dev account)
export WORKLOAD_ACCOUNT_IDS=123456789012

# F5 API 配置
export F5_API_URL="https://example.console.example.io/api"
export F5_API_TOKEN="YOUR_F5_API_TOKEN_HERE"
export F5_NAMESPACE="acme-net"

# AWS 配置
export AWS_REGION=ap-southeast-1
export AWS_ACCOUNT_ID=123456789012

# S3 存儲桶
export DEPLOYMENT_BUCKET="aws-ops-agent-deployment-123456789012-ap-southeast-1"
export ATHENA_OUTPUT_BUCKET="aws-ops-agent-athena-results-123456789012-ap-southeast-1"

# Lambda 配置
export LAMBDA_TIMEOUT=300
export LAMBDA_MEMORY_SIZE=512

# API Gateway 配置
export ENABLE_API_KEY=true
export API_STAGE_NAME=dev

# 其他配置
export ENVIRONMENT=dev
export STACK_NAME=aws-ops-agent-dev
export PROJECT_NAME=aws-ops-agent
export DEPLOYMENT_METHOD=cloudformation
export GLOBAL_READER_ROLE_NAME=GlobalReaderRole
export F5_SECRET_NAME=f5-distributed-cloud-api-credentials
export ATHENA_DATABASE=centralized_logging

echo "✅ 配置已加載"
