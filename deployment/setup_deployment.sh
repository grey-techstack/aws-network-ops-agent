#!/bin/bash
# 交互式部署配置腳本

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AWS Operations Agent 部署配置${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 獲取 AWS 信息
AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${YELLOW}警告: 無法獲取 AWS Account ID，請確保 AWS CLI 已配置${NC}"
    read -p "請輸入您的 AWS Account ID: " AWS_ACCOUNT_ID
fi

echo -e "${GREEN}AWS 配置:${NC}"
echo "  Region: $AWS_REGION"
echo "  Account ID: $AWS_ACCOUNT_ID"
echo ""

# Core Network Account ID (已知)
CORE_NETWORK_ACCOUNT_ID=234567890123
echo -e "${GREEN}Core Network Account ID: $CORE_NETWORK_ACCOUNT_ID${NC}"
echo ""

# Workload Account IDs
echo -e "${BLUE}Workload Account IDs${NC}"
echo "如果有其他工作負載帳戶，請輸入（逗號分隔）"
echo "如果只有 Core Network Account，直接按 Enter"
read -p "Workload Account IDs [$CORE_NETWORK_ACCOUNT_ID]: " WORKLOAD_INPUT
WORKLOAD_ACCOUNT_IDS=${WORKLOAD_INPUT:-$CORE_NETWORK_ACCOUNT_ID}
echo ""

# F5 API 配置
echo -e "${BLUE}F5 Distributed Cloud API 配置${NC}"
echo ""
echo "是否要配置 F5 API？"
echo "  1) 是 - 我有 F5 API credentials"
echo "  2) 否 - 跳過 F5 配置（稍後可以手動配置）"
read -p "選擇 [1/2]: " f5_choice

if [ "$f5_choice" = "1" ]; then
    echo ""
    read -p "F5 API URL (例如: https://tenant.console.ves.volterra.io/api): " F5_API_URL
    read -p "F5 API Token: " F5_API_TOKEN
    read -p "F5 Namespace [system]: " F5_NAMESPACE_INPUT
    F5_NAMESPACE=${F5_NAMESPACE_INPUT:-system}
    
    # 測試 F5 API
    echo ""
    echo -e "${YELLOW}測試 F5 API 連接...${NC}"
    
    # 創建臨時測試腳本
    cat > /tmp/test_f5.sh << 'EOF'
#!/bin/bash
response=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: APIToken $F5_API_TOKEN" \
    -H "Content-Type: application/json" \
    "$F5_API_URL/web/namespaces" 2>&1)
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "200" ]; then
    echo "✅ F5 API 連接成功！"
    exit 0
else
    echo "❌ F5 API 連接失敗 (HTTP $http_code)"
    echo "請檢查 URL 和 Token 是否正確"
    exit 1
fi
EOF
    
    chmod +x /tmp/test_f5.sh
    export F5_API_URL F5_API_TOKEN
    
    if /tmp/test_f5.sh; then
        echo -e "${GREEN}F5 API 配置成功！${NC}"
    else
        echo -e "${YELLOW}F5 API 測試失敗，但您可以繼續部署並稍後配置${NC}"
        read -p "是否繼續部署？ [y/N]: " continue_choice
        if [[ ! $continue_choice =~ ^[Yy]$ ]]; then
            echo "部署已取消"
            exit 1
        fi
    fi
    rm -f /tmp/test_f5.sh
else
    echo -e "${YELLOW}跳過 F5 API 配置${NC}"
    F5_API_URL="https://placeholder.console.ves.volterra.io/api"
    F5_API_TOKEN="placeholder-token"
    F5_NAMESPACE="system"
fi
echo ""

# S3 存儲桶
DEPLOYMENT_BUCKET="aws-ops-agent-deployment-${AWS_ACCOUNT_ID}-${AWS_REGION}"
ATHENA_OUTPUT_BUCKET="aws-ops-agent-athena-results-${AWS_ACCOUNT_ID}-${AWS_REGION}"

echo -e "${GREEN}S3 存儲桶:${NC}"
echo "  Deployment: $DEPLOYMENT_BUCKET"
echo "  Athena Output: $ATHENA_OUTPUT_BUCKET"
echo ""

# 其他配置
echo -e "${BLUE}其他配置 (使用默認值請直接按 Enter)${NC}"
read -p "Environment [prod]: " ENV_INPUT
ENVIRONMENT=${ENV_INPUT:-prod}

read -p "Lambda Timeout (秒) [300]: " TIMEOUT_INPUT
LAMBDA_TIMEOUT=${TIMEOUT_INPUT:-300}

read -p "Lambda Memory (MB) [512]: " MEMORY_INPUT
LAMBDA_MEMORY_SIZE=${MEMORY_INPUT:-512}

read -p "啟用 API Key 認證？ [Y/n]: " API_KEY_INPUT
if [[ $API_KEY_INPUT =~ ^[Nn]$ ]]; then
    ENABLE_API_KEY=false
else
    ENABLE_API_KEY=true
fi
echo ""

# 生成配置文件
echo -e "${BLUE}生成配置文件...${NC}"

cat > deploy-config.sh << EOF
#!/bin/bash
# AWS Operations Agent 部署配置
# 自動生成於 $(date)

# Core Network Account
export CORE_NETWORK_ACCOUNT_ID=$CORE_NETWORK_ACCOUNT_ID

# Workload Accounts
export WORKLOAD_ACCOUNT_IDS=$WORKLOAD_ACCOUNT_IDS

# F5 API 配置
export F5_API_URL="$F5_API_URL"
export F5_API_TOKEN="$F5_API_TOKEN"
export F5_NAMESPACE="$F5_NAMESPACE"

# AWS 配置
export AWS_REGION=$AWS_REGION
export AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID

# S3 存儲桶
export DEPLOYMENT_BUCKET="$DEPLOYMENT_BUCKET"
export ATHENA_OUTPUT_BUCKET="$ATHENA_OUTPUT_BUCKET"

# Lambda 配置
export LAMBDA_TIMEOUT=$LAMBDA_TIMEOUT
export LAMBDA_MEMORY_SIZE=$LAMBDA_MEMORY_SIZE

# API Gateway 配置
export ENABLE_API_KEY=$ENABLE_API_KEY
export API_STAGE_NAME=prod

# 其他配置
export ENVIRONMENT=$ENVIRONMENT
export STACK_NAME=aws-ops-agent-complete
export PROJECT_NAME=aws-ops-agent
export DEPLOYMENT_METHOD=cloudformation
export GLOBAL_READER_ROLE_NAME=GlobalReaderRole
export F5_SECRET_NAME=f5-distributed-cloud-api-credentials
export ATHENA_DATABASE=centralized_logging

echo "✅ 配置已加載"
EOF

chmod +x deploy-config.sh

echo -e "${GREEN}✅ 配置文件已生成: deploy-config.sh${NC}"
echo ""

# 顯示配置摘要
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  配置摘要${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Core Network Account: $CORE_NETWORK_ACCOUNT_ID"
echo "Workload Accounts: $WORKLOAD_ACCOUNT_IDS"
echo "F5 API URL: $F5_API_URL"
echo "F5 Namespace: $F5_NAMESPACE"
echo "Environment: $ENVIRONMENT"
echo "Lambda Timeout: ${LAMBDA_TIMEOUT}s"
echo "Lambda Memory: ${LAMBDA_MEMORY_SIZE}MB"
echo "Enable API Key: $ENABLE_API_KEY"
echo "Deployment Bucket: $DEPLOYMENT_BUCKET"
echo "Athena Bucket: $ATHENA_OUTPUT_BUCKET"
echo ""

# 詢問是否立即部署
echo -e "${BLUE}========================================${NC}"
read -p "是否立即開始部署？ [Y/n]: " deploy_now

if [[ ! $deploy_now =~ ^[Nn]$ ]]; then
    echo ""
    echo -e "${GREEN}開始部署...${NC}"
    echo ""
    
    # 加載配置
    source deploy-config.sh
    
    # 給腳本執行權限
    chmod +x deploy_complete_infrastructure.sh
    chmod +x build_package.sh
    
    # 執行部署
    ./deploy_complete_infrastructure.sh
else
    echo ""
    echo -e "${YELLOW}配置已保存，您可以稍後運行以下命令開始部署:${NC}"
    echo ""
    echo "  cd deployment"
    echo "  source deploy-config.sh"
    echo "  ./deploy_complete_infrastructure.sh"
    echo ""
fi
