#!/bin/bash
# AWS 訪問檢查腳本

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AWS 訪問檢查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 檢查 AWS CLI
echo -e "${BLUE}[1/6]${NC} 檢查 AWS CLI..."
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI 未安裝${NC}"
    echo ""
    echo "請安裝 AWS CLI:"
    echo "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi
AWS_CLI_VERSION=$(aws --version 2>&1 | cut -d' ' -f1)
echo -e "${GREEN}✅ AWS CLI 已安裝: $AWS_CLI_VERSION${NC}"
echo ""

# 檢查 AWS 憑證
echo -e "${BLUE}[2/6]${NC} 檢查 AWS 憑證..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS 憑證無效或未配置${NC}"
    echo ""
    echo "請配置 AWS 訪問："
    echo ""
    echo "方法 1: AWS SSO (推薦)"
    echo "  aws configure sso"
    echo "  aws sso login --profile your-profile"
    echo ""
    echo "方法 2: Access Keys"
    echo "  aws configure"
    echo ""
    echo "詳細指南: AWS_ACCESS_SETUP.md"
    exit 1
fi

IDENTITY=$(aws sts get-caller-identity)
ACCOUNT_ID=$(echo "$IDENTITY" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
USER_ARN=$(echo "$IDENTITY" | grep -o '"Arn": "[^"]*"' | cut -d'"' -f4)
AWS_REGION=$(aws configure get region || echo "未設置")

echo -e "${GREEN}✅ AWS 憑證有效${NC}"
echo "   Account ID: $ACCOUNT_ID"
echo "   User/Role: $USER_ARN"
echo "   Region: $AWS_REGION"
echo ""

# 檢查是否是正確的帳戶
if [ "$ACCOUNT_ID" = "234567890123" ]; then
    echo -e "${GREEN}✅ 正確的 AWS 帳戶 (Core Network Account)${NC}"
else
    echo -e "${YELLOW}⚠️  當前帳戶 ($ACCOUNT_ID) 不是 Core Network Account (234567890123)${NC}"
    echo "   這可能沒問題，但請確認您要部署到哪個帳戶"
fi
echo ""

# 檢查 Lambda 權限
echo -e "${BLUE}[3/6]${NC} 檢查 Lambda 權限..."
if aws lambda list-functions --max-items 1 &> /dev/null; then
    echo -e "${GREEN}✅ Lambda 權限正常${NC}"
else
    echo -e "${RED}❌ Lambda 權限不足${NC}"
    echo "   需要: lambda:ListFunctions, lambda:CreateFunction"
fi
echo ""

# 檢查 S3 權限
echo -e "${BLUE}[4/6]${NC} 檢查 S3 權限..."
if aws s3 ls &> /dev/null; then
    echo -e "${GREEN}✅ S3 權限正常${NC}"
else
    echo -e "${RED}❌ S3 權限不足${NC}"
    echo "   需要: s3:ListBucket, s3:CreateBucket, s3:PutObject"
fi
echo ""

# 檢查 IAM 權限
echo -e "${BLUE}[5/6]${NC} 檢查 IAM 權限..."
if aws iam list-roles --max-items 1 &> /dev/null; then
    echo -e "${GREEN}✅ IAM 權限正常${NC}"
else
    echo -e "${RED}❌ IAM 權限不足${NC}"
    echo "   需要: iam:ListRoles, iam:CreateRole, iam:AttachRolePolicy"
fi
echo ""

# 檢查 CloudFormation 權限
echo -e "${BLUE}[6/6]${NC} 檢查 CloudFormation 權限..."
if aws cloudformation list-stacks --max-items 1 &> /dev/null; then
    echo -e "${GREEN}✅ CloudFormation 權限正常${NC}"
else
    echo -e "${RED}❌ CloudFormation 權限不足${NC}"
    echo "   需要: cloudformation:ListStacks, cloudformation:CreateStack"
fi
echo ""

# 總結
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  檢查完成${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 檢查是否所有權限都通過
if aws lambda list-functions --max-items 1 &> /dev/null && \
   aws s3 ls &> /dev/null && \
   aws iam list-roles --max-items 1 &> /dev/null && \
   aws cloudformation list-stacks --max-items 1 &> /dev/null; then
    echo -e "${GREEN}✅ 所有必需的權限都已具備！${NC}"
    echo ""
    echo -e "${GREEN}您可以開始部署了：${NC}"
    echo "  1. 設置 F5 API Token:"
    echo "     export F5_API_TOKEN=your-token"
    echo ""
    echo "  2. 運行部署腳本:"
    echo "     ./setup_deployment.sh"
    echo ""
else
    echo -e "${RED}❌ 缺少某些必需的權限${NC}"
    echo ""
    echo "請聯繫您的 AWS 管理員獲取以下權限："
    echo "  - Lambda 完整訪問"
    echo "  - S3 存儲桶管理"
    echo "  - IAM 角色創建和管理"
    echo "  - CloudFormation 堆疊管理"
    echo "  - API Gateway 管理"
    echo "  - Secrets Manager 訪問"
    echo ""
    echo "詳細信息請查看: AWS_ACCESS_SETUP.md"
    echo ""
    exit 1
fi
